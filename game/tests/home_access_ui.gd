extends SceneTree
## The home's door on screen (home_door_panel.gd, home_door.gd; server/home_access.py): the owner's
## card lists the guest inside, the padlock locks on the server (one request at a time), folds, asks
## before sending a guest out; the guest sent out gets the card and walks out; the village's shut
## door pops a padlock over the player. --capture saves artifacts/home_access_*.png.
const RpgUi = preload("res://scripts/rpg_ui.gd")
const HomeDoor = preload("res://scripts/home_door.gd")
const HomeDoorPanel = preload("res://scripts/home_door_panel.gd")
const AvatarLook = preload("res://scripts/avatar_look.gd")
var failed := false
var url := preload("res://tests/qa_server.gd").url()
var capture := false

func _initialize() -> void:
	call_deferred("run")
	create_timer(150).timeout.connect(func():
		push_error("Home access UI exceeded 150 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func account(api: Node, name: String) -> String:
	var login: Dictionary = await api.post("/v1/auth/register",{"username":name,"password":"Home-access-password-1"})
	return login.data.token if login.ok else ""

func open_room(token: String, extra: Dictionary) -> Control:
	var session := {"token":token,"url":url,"room":"home","multiplayer":true}
	session.merge(extra, true)
	Engine.set_meta("studio_session",session)
	var room: Control = load("res://scenes/studio.tscn").instantiate()
	root.add_child(room)
	return room

## Waits (up to `seconds`) until check() holds; its last answer.
func until(check: Callable, seconds := 10.0) -> bool:
	var waited := 0.0
	while waited < seconds and not check.call():
		await create_timer(0.1).timeout
		waited += 0.1
	return check.call()

func shot(name: String, settle := 0.5) -> void:
	if not capture: return
	await create_timer(settle).timeout
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/home_access_%s.png" % name))

## A node built from source (stand-ins for the village and a guest's room).
func scripted(base: String, body: String) -> Node:
	var script := GDScript.new()
	script.source_code = "extends %s\n%s\n" % [base, body]
	script.reload()
	return script.new()

## The village around a shut friend's door: a walker under a camera, and refuse() keeping the lines.
func stand_in_village() -> Node3D:
	var village: Node3D = scripted("Node3D", "var player: Node3D\nvar lines := []\nfunc refuse(value: String) -> void:\n\tlines.append(value)")
	village.name = "StandInVillage"
	root.add_child(village)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color("9cc7d8")
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color("f2e4cb")
	village.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 25, 0)
	village.add_child(sun)
	var ground := MeshInstance3D.new()
	ground.mesh = PlaneMesh.new()
	(ground.mesh as PlaneMesh).size = Vector2(30, 30)
	var grass := StandardMaterial3D.new()
	grass.albedo_color = Color("7fa45a")
	ground.material_override = grass
	village.add_child(ground)
	var wall := MeshInstance3D.new()
	wall.mesh = BoxMesh.new()
	(wall.mesh as BoxMesh).size = Vector3(5, 3.2, 0.4)
	var plaster := StandardMaterial3D.new()
	plaster.albedo_color = Color("e8d8b8")
	wall.material_override = plaster
	wall.position = Vector3(0, 1.6, -1.2)
	village.add_child(wall)
	var door := MeshInstance3D.new()
	door.mesh = BoxMesh.new()
	(door.mesh as BoxMesh).size = Vector3(1.1, 2.1, 0.1)
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color("7a4f2c")
	door.material_override = wood
	door.position = Vector3(0, 1.05, -0.97)
	village.add_child(door)
	var walker: Node3D = AvatarLook.walker({}, -1)
	walker.controls_enabled = false
	walker.visual_only = true
	village.add_child(walker)
	walker.position = Vector3(0, 0, 0.4)
	village.player = walker
	var camera := Camera3D.new()
	camera.fov = 40
	village.add_child(camera)
	camera.position = Vector3(0, 3.4, 7.5)
	camera.look_at(Vector3(0, 1.6, 0))
	camera.current = true
	return village

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): url = arg.trim_prefix("--server=")
	capture = "--capture" in OS.get_cmdline_user_args()
	var host_api: Node = load("res://scripts/api.gd").new(); root.add_child(host_api); host_api.base_url = url
	var guest_api: Node = load("res://scripts/api.gd").new(); root.add_child(guest_api); guest_api.base_url = url
	var stamp := str(Time.get_ticks_msec())
	var host_name := "host_"+stamp
	var guest_name := "guest_"+stamp
	host_api.token = await account(host_api, host_name)
	guest_api.token = await account(guest_api, guest_name)
	expect(not host_api.token.is_empty() and not guest_api.token.is_empty(), "two accounts on the server")
	var invite: Dictionary = await host_api.post("/v1/social/invites",host_api.mutation({"username":guest_name,"kind":"village"}))
	var accepted: Dictionary = await guest_api.post("/v1/social/invites/"+str(invite.data.get("id",""))+"/accept",guest_api.mutation())
	expect(accepted.ok and accepted.data.visiting, "friend accepted the visit")
	var guest_id := str(accepted.data.get("self_id",""))
	var host_room := open_room(host_api.token, {})
	# The guest walks in once the owner is inside (the village's door asks first in the game).
	var owner_in := func() -> bool:
		var door: Dictionary = await guest_api.request("/v1/home/access")
		return door.ok and bool(door.data.get("owner_in", false))
	for i in 40:
		if await owner_in.call(): break
		await create_timer(0.25).timeout
	var guest_room := open_room(guest_api.token, {"visit_host":accepted.data.host_id,"visit_name":accepted.data.host_name})
	await until(func(): return is_instance_valid(host_room.hero) and is_instance_valid(guest_room.hero))
	expect(guest_room.get_node_or_null("HomeRefusal") == null and not guest_room.leaving, "the guest is let in while the owner is home")
	host_room.hero.position = Vector3(-1.5,0,0)
	guest_room.hero.position = Vector3(1,0,3)
	var panel = host_room.hud.get_node_or_null("HomeDoorPanel")
	expect(panel != null, "the owner's home has the door card")
	expect(guest_room.hud.get_node_or_null("HomeDoorPanel") == null, "a guest has no door card")
	if panel == null:
		quit(1)
		return
	await until(func(): return panel.rows.size()==1 and host_room.peers.size()==1 and guest_room.peers.size()==1, 12.0)
	expect(panel.rows.has(guest_id) and str(panel.rows[guest_id].name).contains(guest_name), "the card lists the guest inside by name")
	expect(panel.mouse_filter==Control.MOUSE_FILTER_IGNORE and not panel.empty_label.visible, "the card lets clicks through to the room")
	expect(not panel.locked and panel.state_label.text==TranslationServer.translate("열림"), "the door starts unlocked")
	guest_room.visible = false
	await shot("panel")
	# The padlock: one request at a time, the server keeps it, a guest already inside stays.
	panel.lock_key.pressed.emit()
	expect(panel.busy and panel.lock_key.disabled, "the padlock waits for its answer")
	panel.lock_key.pressed.emit()
	await until(func(): return not panel.busy)
	expect(panel.locked and panel.state_label.text==TranslationServer.translate("잠금"), "the padlock shows locked")
	var access: Dictionary = await host_api.request("/v1/home/access")
	expect(access.ok and bool(access.data.locked), "the server keeps the lock (one press, not two)")
	var inside: Dictionary = await guest_api.request("/v1/home/access")
	expect(inside.ok and bool(inside.data.open) and bool(inside.data.locked), "the guest already inside stays when the door locks")
	await shot("panel_locked")
	RpgUi.set_folded(HomeDoorPanel.FOLD_ID, true)
	await create_timer(0.4).timeout
	expect(not panel.list.get_parent().get_parent().visible and panel.count_box.visible, "folded, the card keeps the padlock and the guest count")
	await shot("panel_folded", 0.1)
	RpgUi.set_folded(HomeDoorPanel.FOLD_ID, false, false)
	# The village at a shut door, and a guest's card when the owner walks out (stand-ins).
	host_room.visible = false
	var village := stand_in_village()
	await create_timer(0.3).timeout
	HomeDoor.refuse_at_door(village, {"home":{"open":false,"owner":false,"locked":true,"reason":"owner_away"}})
	var pop: Node = village.player.get_node_or_null("DoorLockPop")
	expect(village.lines.size()==1 and pop != null and pop.get_node("Tag").text==TranslationServer.translate("부재중"), "a shut door: the line and a padlock over the player (부재중)")
	await shot("door_away", 0.45)
	var now := Time.get_unix_time_from_system()
	HomeDoor.refuse_at_door(village, {"home":{"open":false,"owner":false,"locked":false,"reason":"ejected","until":now+590.0},"village":{"crops":{"server_time":now}}})
	pop = village.player.get_node_or_null("DoorLockPop")
	expect(village.lines.size()==2 and str(village.lines[1]).contains("10") and pop != null and str(pop.get_node("Tag").text).contains("10"), "sent out: the minutes left on the line and over the padlock")
	await shot("door_ejected", 0.45)
	village.queue_free()
	var stand_in: Control = scripted("Control", "var leaving := false\nvar left := 0\nfunc leave() -> void:\n\tleft += 1")
	stand_in.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(stand_in)
	HomeDoorPanel.show_refusal(stand_in, {"open":false,"reason":"owner_away"}, host_name)
	HomeDoorPanel.show_refusal(stand_in, {"open":false,"reason":"owner_away"}, host_name)
	var away_card: Node = stand_in.get_node_or_null("HomeRefusal")
	expect(away_card != null and stand_in.get_children().filter(func(c): return str(c.name).begins_with("HomeRefusal")).size()==1, "the owner walked out: one card for the guest")
	await shot("guest_owner_away")
	await until(func(): return stand_in.left > 0, 4.0)
	expect(stand_in.left==1, "the guest walks out after the card")
	stand_in.queue_free()
	host_room.visible = true
	# Sending the guest out: asked first, then the row leaves and the guest gets the card.
	expect(panel.rows.has(guest_id) and not guest_room.leaving, "the guest is still inside before being sent out")
	if not panel.rows.has(guest_id):
		quit(1)
		return
	panel.rows[guest_id].get_meta("key").pressed.emit()
	expect(not panel.ask.is_empty() and is_instance_valid(panel.ask.root), "내보내기 asks first")
	await shot("confirm")
	panel.ask.body.find_child("Confirm", true, false).pressed.emit()
	await until(func(): return panel.rows.is_empty(), 6.0)
	expect(panel.rows.is_empty() and panel.empty_label.visible, "the guest's row leaves at once")
	host_room.visible = false
	guest_room.visible = true
	await until(func(): return guest_room.get_node_or_null("HomeRefusal") != null, 6.0)
	var card: Node = guest_room.get_node_or_null("HomeRefusal")
	expect(card != null and str(card.find_child("Title", true, false).text).contains(host_name), "the guest sent out gets the card naming the owner")
	await shot("guest_ejected", 0.4)
	var outside: Dictionary = await guest_api.request("/v1/home/access")
	expect(outside.ok and not bool(outside.data.open) and str(outside.data.get("reason",""))=="ejected" and HomeDoor.minutes_left(outside.data)==10, "the server keeps the guest out for 10 minutes")
	await until(func(): return guest_room.leaving, 4.0)
	expect(guest_room.leaving, "the guest walks out after the card")
	# Quit before the walk-out's switch to the village (home_visit.gd does the same).
	var veil = load("res://scripts/transition.gd").instance
	if is_instance_valid(veil): veil.door.stop()
	OS.delay_msec(100)
	quit(1 if failed else 0)
