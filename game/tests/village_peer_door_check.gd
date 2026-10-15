extends SceneTree
## In the village, a friend who walks up to a door and goes in (vanishes there) swings that door, as
## does one who comes out of it (village_doors.gd watch_peers). The friend is played by the API.
var failed := false
var url := preload("res://tests/qa_server.gd").url()

func _initialize() -> void:
	call_deferred("run")
	create_timer(150).timeout.connect(func():
		push_error("Village peer door exceeded 150 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func capture(path: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/"+path))

func account(api: Node, name: String) -> String:
	var login: Dictionary = await api.post("/v1/auth/register",{"username":name,"password":"Village-peer-door-1"})
	return login.data.token if login.ok else ""

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): url = arg.trim_prefix("--server=")
	var host_api: Node = load("res://scripts/api.gd").new(); root.add_child(host_api); host_api.base_url = url
	var guest_api: Node = load("res://scripts/api.gd").new(); root.add_child(guest_api); guest_api.base_url = url
	var stamp := str(Time.get_ticks_msec())
	host_api.token = await account(host_api, "vhost_"+stamp)
	guest_api.token = await account(guest_api, "vguest_"+stamp)
	var invite: Dictionary = await host_api.post("/v1/social/invites",host_api.mutation({"username":"vguest_"+stamp,"kind":"village"}))
	var accepted: Dictionary = await guest_api.post("/v1/social/invites/"+str(invite.data.get("id",""))+"/accept",guest_api.mutation())
	expect(accepted.ok and accepted.data.visiting, "friend visiting the host's village")
	# The host comes out of the home into the village (multiplayer on).
	Engine.set_meta("studio_session",{"token":host_api.token,"url":url,"room":"home","multiplayer":true})
	change_scene_to_file("res://scenes/main.tscn")
	var deadline:=Time.get_ticks_msec()+60000
	while Time.get_ticks_msec()<deadline and not (is_instance_valid(current_scene) and current_scene.get("screen")=="village" and is_zero_approx(load("res://scripts/transition.gd").instance.veil.modulate.a)):await process_frame
	var village=current_scene
	var Doors=load("res://scripts/village_doors.gd")
	var Town=load("res://scripts/town.gd")
	# Past the doors' settle time, the host's own walk out finished.
	await create_timer(5.0).timeout
	var cafe: Dictionary=Town.door_for("01_cafe")
	var out: Vector2=(cafe.at-cafe.center).normalized()
	var spot: Vector2=cafe.at+out*0.6
	# The friend walks up to the café door...
	for i in 12:
		await guest_api.post("/v1/social/presence",{"scene":"village","x":spot.x+out.x*(2.0-i*0.15),"z":spot.y+out.y*(2.0-i*0.15),"y":Town.height_at(spot.x,spot.y),"yaw":0.0})
		await create_timer(0.25).timeout
	var seen := false
	for i in 20:
		await create_timer(0.25).timeout
		if village.social.peers.size()==1: seen=true; break
	expect(seen, "host sees the friend at the café door")
	var door: Dictionary=Doors.find(village,"01_cafe")
	expect(float(door.get("open",0.0))<0.05, "café door shut while the friend stands outside")
	# ... and goes in.
	await guest_api.post("/v1/social/presence",{"scene":"away","place":"room"})
	var swung := false
	for i in 40:
		await create_timer(0.1).timeout
		if float(Doors.find(village,"01_cafe").get("open",0.0))>0.3: swung=true; break
	expect(village.social.peers.is_empty(), "the friend went in")
	expect(swung, "the café door swings for the friend going in")
	await capture("village_peer_door.png")
	await create_timer(2.5).timeout
	expect(float(Doors.find(village,"01_cafe").get("open",0.0))<0.05, "the café door shuts again")
	quit(1 if failed else 0)
