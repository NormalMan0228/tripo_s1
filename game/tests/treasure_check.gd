extends SceneTree
## Treasure chests end to end on the QA server, the way a new player meets them:
##   a new account starts at home -> the chest glows against the back wall -> the key chip says
##   "보물상자 열기" -> E: the lid opens, the stars fly into the counter that slides in, the server pays
##   10 starseeds exactly once, a second E does nothing -> out in the village the café chest (a few
##   steps from 모카's terrace) glows -> E there: +4, the HUD counter ends at the new total -> signing
##   in again (this login's memory cleared) the home chest and the café chest are still open, lid up,
##   no glow, no prompt.
##   godot --path game --script res://tests/treasure_check.gd -- --server=URL [--capture]
## --capture saves artifacts/treasure-shot-*.png (a window; tools/test.ps1 -Capture).
const Transition = preload("res://scripts/transition.gd")
const Town = preload("res://scripts/town.gd")
const Treasure = preload("res://scripts/treasure.gd")
const PASSWORD := "Chest-check-pass-1"
var failed := false
var url := preload("res://tests/qa_server.gd").url()
var capture := "--capture" in OS.get_cmdline_user_args()
var shots := 0

func _initialize() -> void:
	call_deferred("run")
	create_timer(420).timeout.connect(func():
		push_error("Treasure check exceeded 420 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func wait_for(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec()+int(seconds*1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return condition.call()

func shot(name: String, settle := 0.8) -> void:
	if not capture: return
	await create_timer(settle).timeout
	await RenderingServer.frame_post_draw
	shots += 1
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/treasure-shot-%02d-%s.png" % [shots, name]))

func village() -> Node:
	await wait_for(func() -> bool: return is_instance_valid(current_scene) and current_scene.get("screen") == "village" and Transition.instance != null and is_zero_approx(Transition.instance.veil.modulate.a), 90.0)
	return current_scene

func home() -> Node:
	await wait_for(func() -> bool: return is_instance_valid(current_scene) and current_scene.get("room") == "home" and is_instance_valid(current_scene.get("hero")) and Transition.instance != null and is_zero_approx(Transition.instance.veil.modulate.a), 90.0)
	return current_scene

func new_api(token := "") -> Node:
	var api: Node = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = url
	api.token = token
	return api

## The game's own sign-in path: a new session starts at home.
func start_at_home(token: String) -> Node:
	Engine.set_meta("studio_session", {"token":token, "url":url, "room":"home"})
	change_scene_to_file("res://scenes/studio.tscn")
	return await home()

func shards(api: Node) -> int:
	var me: Dictionary = await api.request("/v1/me")
	return int(me.data.get("shards", -1)) if me.ok else -1

func key(app: Node, code: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.physical_keycode = code
	event.pressed = true
	app._unhandled_input(event)

func home_chest(room: Node) -> Dictionary:
	var at_home: Node = Treasure.home_of(room)
	await wait_for(func() -> bool: return Treasure.home_of(room) != null and not Treasure.home_of(room).chests.is_empty(), 15.0)
	at_home = Treasure.home_of(room)
	return at_home.chests[0] if at_home != null and not at_home.chests.is_empty() else {}

func treasure_module(town: Node) -> Node:
	for module in town.modules:
		if is_instance_valid(module) and module.has_method("chest_of"): return module
	return null

func run() -> void:
	preload("res://scripts/npc.gd").pinned = true  # the cast at their work spots whatever the clock
	var name := "chest_"+str(Time.get_ticks_msec()%1000000)
	var api := new_api()
	var signup: Dictionary = await api.post("/v1/auth/register", {"username":name, "password":PASSWORD})
	expect(signup.ok, "a new account")
	if not signup.ok:
		quit(1)
		return
	api.token = signup.data.token
	var start := await shards(api)
	var listed: Dictionary = await api.request("/v1/chests")
	expect(listed.ok and int(listed.data.chests.total) == 11 and listed.data.chests.opened.is_empty(), "the server lists eleven chests, none open")

	# 1. Home: the chest glows against the back wall; the chip offers to open it.
	var room: Node = await start_at_home(signup.data.token)
	var chest := await home_chest(room)
	expect(not chest.is_empty() and chest.state == "closed" and chest.halo.visible, "the home chest stands closed and glowing")
	expect(not chest.is_empty() and room.decor_by_floor[0].has(chest.record) and chest.record.solid, "the chest is solid room furniture on the ground floor")
	if chest.is_empty():
		quit(1)
		return
	var record: Dictionary = chest.record
	var size: Vector2 = Vector2(room.room_spec.get("size", Vector2(10, 10)))
	expect(record.center.z < -size.y*0.5+0.75 and absf(record.center.x) < 1.5, "it stands against the back wall, facing the door (%s)" % str(record.center))
	await shot("home-closed", 1.4)
	room.hero.position = record.center+Vector3(0.1, 0, Treasure.DEPTH*0.5+0.55)
	room.hero.face_point(record.center)
	room.update_hint()
	expect(room.controls_label.text == tr("보물상자 열기"), "the key chip says 보물상자 열기 (%s)" % room.controls_label.text)
	room.interact_nearest()
	expect(chest.state == "opening", "E starts opening it (the lid rattles while the server answers)")
	expect(await wait_for(func() -> bool: return chest.state == "open", 10.0), "the chest opens")
	expect(await wait_for(func() -> bool: return chest.lid.rotation.x < -1.0, 2.0), "the lid swings up")
	expect(not chest.halo.visible and not record.interactive, "no glow and no prompt once open")
	expect(room.find_children("ChestCounter", "PanelContainer", true, false).size() == 1 or room.find_children("ChestStar", "TextureRect", true, false).size() > 0, "the starseed counter slides in under the room's name for the flying stars")
	await shot("home-open", 0.3)
	await create_timer(2.0).timeout
	var after_home := await shards(api)
	expect(after_home == start+10, "the server paid 10 starseeds (%d -> %d)" % [start, after_home])
	expect(room.wallet.text.contains(str(after_home)), "the bag's wallet line shows the new count")
	room.update_hint()
	expect(room.controls_label.text != tr("보물상자 열기"), "the chip no longer offers the open chest")
	room.interact_nearest()
	await create_timer(1.0).timeout
	expect(await shards(api) == start+10, "a second E pays nothing")
	room.leave()

	# 2. Village: the café chest a few steps from 모카's terrace.
	var town: Node = await village()
	var chests: Node = treasure_module(town)
	expect(chests != null, "the village has its treasure module")
	if chests == null:
		quit(1)
		return
	expect(await wait_for(func() -> bool: return chests.shown and chests.visible, 10.0), "the field chests show once /v1/me says which are open")
	expect(chests.skipped.is_empty() and chests.chests.size() == 10, "ten field chests placed (skipped %s)" % str(chests.skipped))
	var cafe: Dictionary = chests.chest_of("fields_cafe")
	expect(not cafe.is_empty() and cafe.state == "closed", "the café chest is closed")
	var front := Vector2(sin(cafe.root.rotation.y), cos(cafe.root.rotation.y))
	var stand: Vector2 = Vector2(cafe.at)+front*1.0
	town.close_village_modal()
	town.player.position = Town.point(stand, 0.3)
	town.player.velocity = Vector3.ZERO
	town.follow_camera(1.0)
	for i in 8: await physics_frame
	var near: Dictionary = town.module_closest()
	expect(str(near.get("id", "")) == "fields_cafe", "standing in front of it the E prompt is the chest's (%s)" % str(near.get("id", "")))
	await wait_for(func() -> bool: return str(town.hint.get_meta("prompt", "")).contains(tr("보물상자 열기")), 3.0)
	expect(str(town.hint.get_meta("prompt", "")).contains(tr("보물상자 열기")), "the prompt says 보물상자 열기 (%s)" % str(town.hint.get_meta("prompt", "")))
	await shot("cafe-closed", 0.6)
	var before := await shards(api)
	key(town, KEY_E)
	if not await wait_for(func() -> bool: return cafe.state != "closed", 1.5):
		print("  E went elsewhere: life ", town.life.closest(), " npc ", town.nearest_npc(), " modal ", is_instance_valid(town.village_modal))
	expect(await wait_for(func() -> bool: return cafe.state == "open", 10.0), "E opens the café chest")
	await shot("cafe-open", 0.5)
	expect(await wait_for(func() -> bool: return int(town.frame.stars.text) == before+4, 6.0), "the stars fly into the HUD counter, which ends at %d (%s)" % [before+4, town.frame.stars.text])
	var after_cafe := await shards(api)
	expect(after_cafe == before+4, "the server paid 4 starseeds (%d -> %d)" % [before, after_cafe])
	near = town.module_closest()
	expect(str(near.get("id", "")) != "fields_cafe", "the open chest offers no E")
	key(town, KEY_E)
	await create_timer(1.0).timeout
	expect(await shards(api) == after_cafe, "E again pays nothing")

	# 3. Signing in again: both still open (this login's memory cleared, so the server says so).
	if Engine.has_meta(Treasure.META): Engine.remove_meta(Treasure.META)
	room = await start_at_home(signup.data.token)
	chest = await home_chest(room)
	expect(not chest.is_empty() and chest.state == "open" and chest.lid.rotation.x < -1.0 and not chest.halo.visible and not chest.heap.visible, "signed in again: the home chest is open, lid up, no glow, empty")
	if not chest.is_empty():
		room.hero.position = chest.record.center+Vector3(0.1, 0, Treasure.DEPTH*0.5+0.55)
		room.update_hint()
		expect(room.controls_label.text != tr("보물상자 열기"), "and offers no E")
	await shot("home-again", 0.8)
	room.leave()
	town = await village()
	chests = treasure_module(town)
	expect(chests != null and await wait_for(func() -> bool: return chests.shown and chests.chest_of("fields_cafe").state == "open", 10.0), "the café chest is still open in the village")
	expect(chests != null and chests.chest_of("camp_tents").state == "closed", "the others are still closed")
	var final: Dictionary = await api.request("/v1/chests")
	expect(final.ok and int(final.data.chests.found) == 2 and await shards(api) == start+14, "two found, 14 starseeds in all")
	print("RESULT %s" % ("FAIL" if failed else "PASS"))
	quit(1 if failed else 0)
