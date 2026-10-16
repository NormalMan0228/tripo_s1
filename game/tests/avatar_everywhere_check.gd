extends SceneTree
## One look everywhere: two clients (A, whose look changes, and friend B) check that every place
## that draws A shows the same character file, part colours, hat and backpack, read back from the
## built bodies (avatar_look.gd applied()), and that a change shows everywhere without re-entering:
##   village: the wardrobe preview, A's walker, A's HUD medallion and B's view of A (wardrobe saves)
##   expedition: A's walker and B's view of A in a co-op run (a look saved on another device)
##   rooms: A's walker at home and B visiting A's home (another device again)
## Bodies are rebuilt once per change, not on every presence poll.
## --capture (windowed) saves a cropped tile of each place and look to artifacts/avatar-everywhere/.
const Main = preload("res://scripts/main.gd")
const AvatarLook = preload("res://scripts/avatar_look.gd")
const MODELS := {"explorer_b":"explorer_b_wardrobe", "explorer":"explorer", "ranger":"ranger", "tinker":"tinker",
	"m3":"m3", "f2":"f2"}
const LOOKS := [
	{"character":"ranger", "hair":"#8a3b2a", "coat":"#2f5f9e", "pants":"#3b3b3b", "boots":"#5a3a22", "skin":"#bc865c", "headwear":"cap", "backpack":false},
	{"character":"tinker", "hair":"#774f3d", "coat":"#ab789f", "pants":"#526552", "boots":"#c47b50", "skin":"#895b43", "headwear":"beret", "backpack":true},
	{"character":"explorer", "hair":"#d5a250", "coat":"#6889a1", "pants":"#774f3d", "boots":"#30595b", "skin":"#f0cdb1", "headwear":"none", "backpack":false},
	{"character":"explorer_b", "hair":"#30595b", "coat":"#c47b50", "pants":"#6889a1", "boots":"#774f3d", "skin":"#e4b587", "headwear":"cap", "backpack":true},
	# The eight new characters (avatar_v2, N1): one man and one woman with changed colours.
	{"character":"m3", "hair":"#30595b", "coat":"#c47b50", "pants":"#2b394e", "boots":"#20201d", "skin":"#975a38", "headwear":"none", "backpack":true, "accent":"#cfc2ad"},
	{"character":"f2", "hair":"#7a3b2a", "coat":"#5fa8a0", "pants":"#1e1f42", "boots":"#603222", "skin":"#d09988", "headwear":"beret", "backpack":false, "accent":"#6f4146"},
]
var server := preload("res://tests/qa_server.gd").url()
var failures: Array[String] = []
var capture := false
var out_dir := ""
var password := "Avatar-everywhere-check-1"
var device: Node
var pressed_at := 0

func check(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ")+message)
	if not value: failures.append(message)

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("Avatar everywhere check exceeded 240 seconds")
		quit(2))

func seconds(value: float) -> void:
	await create_timer(value).timeout

## Does this body show `look`? Compares what was built (model file, tint per part, hat, bag).
func shows(body: Node, look: Dictionary) -> bool:
	if not is_instance_valid(body): return false
	var seen: Dictionary = AvatarLook.applied(body)
	if seen.model != MODELS[look.character] or seen.headwear != look.headwear or seen.backpack != look.backpack: return false
	for part in AvatarLook.PARTS:
		var wanted := str(look[part]).to_lower()
		if look.character == "explorer_b":
			# The traveller keeps her own hair and skin; default cloth stays the authored texture.
			if part in ["hair", "skin"] or wanted == str(AvatarLook.DEFAULTS[part]): continue
		if str(seen.tints.get(part, "")).to_lower() != wanted: return false
	return true

func describe(body: Node) -> String:
	return JSON.stringify(AvatarLook.applied(body)) if is_instance_valid(body) else "none"

## Waits (up to `limit` s) until every body in `bodies` shows `look`; returns the seconds it took.
func until_shown(bodies: Callable, look: Dictionary, limit := 4.0) -> float:
	var started := Time.get_ticks_msec()
	while (Time.get_ticks_msec()-started)*0.001 < limit:
		if bodies.call().all(func(b): return shows(b, look)): break
		await seconds(0.05)
	return (Time.get_ticks_msec()-started)*0.001

## The HUD medallion has drawn `look` (it draws a few frames after the walker is dressed).
func medal_drawn(app: Node, look: Dictionary, limit := 3.0) -> bool:
	var started := Time.get_ticks_msec()
	while (Time.get_ticks_msec()-started)*0.001 < limit:
		if is_instance_valid(app.portrait_view) and app.portrait_view.ready_for(look) and app.frame.portrait.texture == app.portrait_view.get_texture(): return true
		await seconds(0.05)
	return false

## Captures wait for the loading veil to lift.
func veil_clear() -> void:
	var veil = load("res://scripts/transition.gd").instance
	for i in 100:
		if not is_instance_valid(veil) or veil.veil.modulate.a < 0.01: return
		await seconds(0.05)

func add_client(name: String) -> Node:
	var app: Node = Main.new()
	root.add_child(app)
	# A window shows the title for a couple of frames first (main._ready); sign in after it.
	await seconds(0.5)
	await app.authenticate(true, server, name, password, "")
	for i in 120:
		if app.screen == "village": break
		await seconds(0.25)
	return app

## A save from another device (a second sign-in of A's account).
func save_elsewhere(look: Dictionary) -> int:
	var me: Dictionary = (await device.request("/v1/me")).data
	pressed_at = Time.get_ticks_msec()
	var saved: Dictionary = await device.post("/v1/profile", device.mutation({"version":me.profile.version, "avatar":look}))
	check(saved.ok, "look %s saved on another device" % look.character)
	return int(saved.get("data", {}).get("version", -1))

func wardrobe_editor(app: Node) -> Node:
	app.open_wardrobe()
	await seconds(0.2)
	for node in app.village_modal.find_children("*", "HBoxContainer", true, false):
		if node.get_script() == preload("res://scripts/wardrobe.gd"): return node
	return null

## Dresses A through the wardrobe window and its save button, as a player does.
func dress_in_wardrobe(app: Node, look: Dictionary, label: String) -> void:
	var editor: Node = await wardrobe_editor(app)
	check(editor != null, "wardrobe opens")
	if editor == null: return
	editor.avatar = look.duplicate(true)
	editor.refresh()
	await seconds(0.3)
	check(shows(editor.actor, look), "wardrobe preview shows look %s (%s)" % [label, describe(editor.actor)])
	await snap("wardrobe", label, editor.actor, editor.actor.get_viewport(), editor.find_children("*", "Camera3D", true, false)[0])
	var version: int = int(app.me.profile.version)
	pressed_at = Time.get_ticks_msec()
	for button in app.village_modal.find_children("*", "Button", true, false):
		if button.text == app.tr("이 모습으로 저장"): button.emit_signal("pressed")
	for i in 40:
		if int(app.me.get("profile", {}).get("version", -1)) > version: break
		await seconds(0.1)
	check(int(app.me.profile.version) == version+1, "wardrobe save stored look %s (version %d)" % [label, int(app.me.profile.version)])

## A cropped tile around a body (3D view) for the montage.
func snap(place: String, label: String, body: Node3D, viewport: Viewport, camera: Camera3D) -> void:
	if not capture or not is_instance_valid(body): return
	for i in 4: await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = viewport.get_texture().get_image()
	var scale := Vector2(image.get_size())/viewport.get_visible_rect().size
	var feet := camera.unproject_position(body.global_position)*scale
	var head := camera.unproject_position(body.global_position+Vector3(0,1.9,0))*scale
	var tall := maxf(absf(feet.y-head.y), 40.0)*1.35
	var middle := (feet+head)*0.5
	var rect := Rect2i(Vector2i(middle-Vector2(tall*0.4, tall*0.5)), Vector2i(Vector2(tall*0.8, tall))).intersection(Rect2i(Vector2i.ZERO, image.get_size()))
	save_tile(image.get_region(rect), place, label)

## A tile of a piece of the HUD as it is on screen.
func snap_control(place: String, label: String, control: Control) -> void:
	if not capture or not is_instance_valid(control): return
	for i in 4: await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = control.get_viewport().get_texture().get_image()
	var scale := Vector2(image.get_size())/control.get_viewport().get_visible_rect().size
	var box := control.get_global_rect().grow(4)
	var rect := Rect2i(Vector2i(box.position*scale), Vector2i(box.size*scale)).intersection(Rect2i(Vector2i.ZERO, image.get_size()))
	save_tile(image.get_region(rect), place, label)

func save_tile(image: Image, place: String, label: String) -> void:
	if image == null or image.is_empty(): return
	image.convert(Image.FORMAT_RGBA8)
	var fit := minf(240.0/maxf(image.get_width()*1.25, image.get_height()), 2.5)
	image.resize(maxi(1, int(image.get_width()*fit)), maxi(1, int(image.get_height()*fit)), Image.INTERPOLATE_LANCZOS)
	image.save_png(out_dir.path_join("%s-%s.png" % [place, label]))

## Shows only one client (or room) on screen for a capture.
func solo(shown: Node, others: Array) -> void:
	for node in others:
		if not is_instance_valid(node): continue
		node.visible = node == shown
		if node.has_method("build_world") and is_instance_valid(node.ui): node.ui.get_parent().visible = node == shown
	if shown.has_method("build_world"): shown.camera.current = true

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	capture = "--capture" in OS.get_cmdline_user_args() and DisplayServer.get_name() != "headless"
	out_dir = ProjectSettings.globalize_path("res://../artifacts/avatar-everywhere")
	if capture: DirAccess.make_dir_recursive_absolute(out_dir)
	var stamp := str(Time.get_unix_time_from_system()).replace(".", "").right(9)
	var name_a := "look_a_"+stamp
	var name_b := "look_b_"+stamp
	var a: Node = await add_client(name_a)
	var b: Node = await add_client(name_b)
	check(a.screen == "village" and b.screen == "village" and a.social.enabled, "two clients in their villages")
	device = load("res://scripts/api.gd").new(); root.add_child(device); device.base_url = server
	device.token = (await device.post("/v1/auth/login", {"username":name_a, "password":password})).data.get("token", "")
	# B visits A's village.
	check((await a.social.perform("/v1/social/invites", {"username":name_b, "kind":"village"})).ok, "village invitation sent")
	var inbox: Dictionary = await b.api.request("/v1/social")
	for entry in inbox.data.invites:
		if entry.kind == "village": await b.social.answer(entry, "accept")
	b.close_village_modal()
	var id_a := str(a.social.data.get("self_id", ""))
	var id_b := str(b.social.data.get("self_id", ""))
	for i in 60:
		if b.social.peers.has(id_a) and a.social.peers.has(id_b): break
		await seconds(0.1)
	check(b.social.peers.has(id_a) and a.social.peers.has(id_b), "A and B see each other in A's village")
	# Stand next to each other so both are on screen.
	b.player.position = a.player.position+Vector3(1.6, 0, 0.4)
	var friend_view := func() -> Array: return [b.social.peers.get(id_a, {}).get("node")]
	var a_views := func() -> Array: return [a.player, a.portrait_view.actor if is_instance_valid(a.portrait_view) else null]

	# ---------------------------------------------------------------- village: two wardrobe saves
	for index in 2:
		var look: Dictionary = LOOKS[index]
		var label := str(index+1)
		solo(a, [a, b])
		await dress_in_wardrobe(a, look, label)
		a.close_village_modal()
		await until_shown(func(): return a_views.call()+friend_view.call(), look)
		var took := (Time.get_ticks_msec()-pressed_at)*0.001
		check(shows(a.player, look), "village walker shows look %s (%s)" % [label, describe(a.player)])
		check(await medal_drawn(a, look) and shows(a.portrait_view.actor, look), "HUD medallion draws look %s from the same walker" % label)
		check(shows(friend_view.call()[0], look), "friend's view of A in the village shows look %s %.2f s after the save click (%s)" % [label, took, describe(friend_view.call()[0])])
		await snap("village", label, a.player, a.get_viewport(), a.camera)
		await snap_control("hud", label, a.frame.portrait.get_parent().get_parent())
		solo(b, [a, b])
		b.player.position = a.player.position+Vector3(1.6, 0, 0.4)
		await snap("friend-village", label, friend_view.call()[0], b.get_viewport(), b.camera)
	# The friend's copy is rebuilt once per change, not on every presence poll (about 4 a second).
	var peer: Node = friend_view.call()[0]
	var builds: int = int(peer.look_builds)
	await seconds(1.5)
	check(is_instance_valid(peer) and friend_view.call()[0] == peer and int(peer.look_builds) == builds and builds == 3, "friend's copy rebuilt only per change (%d builds for 2 changes)" % builds)
	var walker_builds: int = int(a.player.look_builds)
	check(walker_builds == 3, "A's village walker built once per look (%d)" % walker_builds)
	# Reopening the wardrobe shows the saved look.
	var editor: Node = await wardrobe_editor(a)
	check(editor != null and shows(editor.actor, LOOKS[1]), "wardrobe preview reopens in the saved look")
	a.close_village_modal()

	# ---------------------------------------------------------------- co-op expedition
	await a.social.perform("/v1/party")
	check((await a.social.perform("/v1/social/invites", {"username":name_b, "kind":"party"})).ok, "party invitation sent")
	inbox = await b.api.request("/v1/social")
	for entry in inbox.data.invites:
		if entry.kind == "party": await b.social.answer(entry, "accept")
	b.close_village_modal()
	await seconds(0.7)
	var started: Dictionary = await a.social.perform("/v1/party/runs", {"map_id":"forest", "difficulty":"relaxed"})
	check(started.ok, "co-op expedition starts")
	for i in 120:
		if a.screen == "survival" and b.screen == "survival" and b.social.peers.has(id_a) and a.social.peers.has(id_b): break
		await seconds(0.1)
	check(a.screen == "survival" and b.screen == "survival", "both clients in the expedition")
	check(shows(a.player, LOOKS[1]), "expedition walker shows look 2 (%s)" % describe(a.player))
	check(shows(friend_view.call()[0], LOOKS[1]), "friend's view of A in the expedition shows look 2 (%s)" % describe(friend_view.call()[0]))
	b.player.position = a.player.position+Vector3(1.2, 0, 0.3)
	solo(a, [a, b])
	await snap("expedition", "2", a.player, a.get_viewport(), a.camera)
	solo(b, [a, b])
	await snap("friend-expedition", "2", friend_view.call()[0], b.get_viewport(), b.camera)
	await save_elsewhere(LOOKS[2])
	await until_shown(func(): return [a.player]+friend_view.call(), LOOKS[2], 6.0)
	var took := (Time.get_ticks_msec()-pressed_at)*0.001
	check(shows(a.player, LOOKS[2]), "expedition walker follows a look saved on another device (%.2f s after the save)" % took)
	check(shows(friend_view.call()[0], LOOKS[2]), "friend's view in the expedition follows it too (%s)" % describe(friend_view.call()[0]))
	solo(a, [a, b])
	await snap("expedition", "3", a.player, a.get_viewport(), a.camera)
	solo(b, [a, b])
	await snap("friend-expedition", "3", friend_view.call()[0], b.get_viewport(), b.camera)
	await a.leave_run()
	await b.leave_run()
	for i in 60:
		if a.screen == "village" and b.screen == "village": break
		await seconds(0.1)
	check(a.screen == "village" and shows(a.player, LOOKS[2]) and int(a.me.profile.version) == 3, "back in the village in look 3 (version %d)" % int(a.me.profile.version))
	await until_shown(func(): return a_views.call(), LOOKS[2])
	check(await medal_drawn(a, LOOKS[2]) and shows(a.portrait_view.actor, LOOKS[2]), "HUD medallion shows look 3 after the expedition")
	solo(a, [a, b])
	await veil_clear()
	await snap("village", "3", a.player, a.get_viewport(), a.camera)
	await snap_control("hud", "3", a.frame.portrait.get_parent().get_parent())

	# ---------------------------------------------------------------- rooms: A at home, B visiting
	var profile_a: Dictionary = a.me.profile.duplicate(true)
	var token_a: String = a.api.token
	var token_b: String = b.api.token
	var host_name: String = str(b.social.data.get("host_name", name_a))
	a.queue_free()
	b.queue_free()
	await seconds(0.3)
	Engine.set_meta("studio_session", {"token":token_a, "url":server, "room":"home", "multiplayer":true, "profile":profile_a})
	var home: Control = load("res://scenes/studio.tscn").instantiate()
	root.add_child(home)
	Engine.set_meta("studio_session", {"token":token_b, "url":server, "room":"home", "multiplayer":true, "visit_host":id_a, "visit_name":host_name})
	var visit: Control = load("res://scenes/studio.tscn").instantiate()
	root.add_child(visit)
	await process_frame
	home.hero.position = Vector3(-0.8, 0, 0.6)
	visit.hero.position = Vector3(0.8, 0, 0.9)
	var guest_view := func() -> Array: return [visit.peers.get(id_a, {}).get("node")]
	took = await until_shown(func(): return [home.hero]+guest_view.call(), LOOKS[2], 6.0)
	check(shows(home.hero, LOOKS[2]) and int(home.hero.look_builds) == 1, "room walker wears look 3 from its first frame (%d builds)" % int(home.hero.look_builds))
	check(shows(guest_view.call()[0], LOOKS[2]), "friend visiting A's home sees look 3 (%s)" % describe(guest_view.call()[0]))
	home.visible = true; visit.visible = false
	await snap("room", "3", home.hero, home.viewport, home.camera)
	home.visible = false; visit.visible = true
	await snap("friend-room", "3", guest_view.call()[0], visit.viewport, visit.camera)
	await save_elsewhere(LOOKS[3])
	await until_shown(func(): return [home.hero]+guest_view.call(), LOOKS[3], 6.0)
	took = (Time.get_ticks_msec()-pressed_at)*0.001
	check(shows(home.hero, LOOKS[3]), "room walker and the friend's copy follow a look saved elsewhere (%.2f s after the save)" % took)
	check(shows(guest_view.call()[0], LOOKS[3]), "friend's view in the room follows it (%s)" % describe(guest_view.call()[0]))
	var guest_copy: Node = guest_view.call()[0]
	await seconds(1.2)
	check(guest_view.call()[0] == guest_copy and int(guest_copy.look_builds) == 2, "friend's room copy rebuilt once for the change (%d builds)" % int(guest_copy.look_builds))
	home.visible = true; visit.visible = false
	await snap("room", "4", home.hero, home.viewport, home.camera)
	home.visible = false; visit.visible = true
	await snap("friend-room", "4", guest_view.call()[0], visit.viewport, visit.camera)
	# The village opens from the room in the same look (no default walker first).
	var veil = load("res://scripts/transition.gd").instance
	if is_instance_valid(veil): veil.door.stop()
	visit.queue_free()
	home.queue_free()
	await process_frame
	Engine.set_meta("studio_session", {"token":token_a, "url":server, "room":"home", "profile":{"avatar":LOOKS[3], "version":4}})
	var village: Node = load("res://scenes/main.tscn").instantiate()
	root.add_child(village)
	for i in 60:
		if village.screen == "village": break
		await seconds(0.2)
	check(shows(village.player, LOOKS[3]) and int(village.player.look_builds) == 1, "village from the room: walker in look 4 from its first frame (%d builds)" % int(village.player.look_builds))
	await until_shown(func(): return [village.portrait_view.actor if is_instance_valid(village.portrait_view) else null], LOOKS[3])
	check(await medal_drawn(village, LOOKS[3]) and shows(village.portrait_view.actor, LOOKS[3]), "HUD medallion in look 4")
	await veil_clear()
	# A few steps out of the doorway, clear of the house front.
	village.player.position += Vector3(0, 0.3, 2.5)
	await seconds(0.6)
	await snap("village", "4", village.player, village.get_viewport(), village.camera)
	await snap_control("hud", "4", village.frame.portrait.get_parent().get_parent())
	if is_instance_valid(veil): veil.door.stop()
	OS.delay_msec(100)
	print("AVATAR_EVERYWHERE " + ("FAILED: "+"; ".join(failures) if failures else "OK"))
	quit(1 if failures else 0)
