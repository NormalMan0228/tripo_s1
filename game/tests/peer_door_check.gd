extends SceneTree
## A friend coming into the home walks in through the front door, and walks out through it when
## they leave (room_door.gd arrive / walk_peer_in / depart), as the host sees it.
## Captures (--capture): artifacts/peer_door_{in,out}.png.
var failed := false
var url := preload("res://tests/qa_server.gd").url()

func _initialize() -> void:
	call_deferred("run")
	create_timer(150).timeout.connect(func():
		push_error("Peer door exceeded 150 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func capture(path: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/"+path))

func account(api: Node, name: String) -> String:
	var login: Dictionary = await api.post("/v1/auth/register",{"username":name,"password":"Peer-door-password-1"})
	return login.data.token if login.ok else ""

func open_room(token: String, extra: Dictionary) -> Control:
	var session := {"token":token,"url":url,"room":"home","multiplayer":true}
	session.merge(extra, true)
	Engine.set_meta("studio_session",session)
	var room: Control = load("res://scenes/studio.tscn").instantiate()
	root.add_child(room)
	return room

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): url = arg.trim_prefix("--server=")
	var host_api: Node = load("res://scripts/api.gd").new(); root.add_child(host_api); host_api.base_url = url
	var guest_api: Node = load("res://scripts/api.gd").new(); root.add_child(guest_api); guest_api.base_url = url
	var stamp := str(Time.get_ticks_msec())
	host_api.token = await account(host_api, "phost_"+stamp)
	guest_api.token = await account(guest_api, "pguest_"+stamp)
	var invite: Dictionary = await host_api.post("/v1/social/invites",host_api.mutation({"username":"pguest_"+stamp,"kind":"village"}))
	var accepted: Dictionary = await guest_api.post("/v1/social/invites/"+str(invite.data.get("id",""))+"/accept",guest_api.mutation())
	expect(accepted.ok and accepted.data.visiting, "friend visiting the host's village")
	var host_room := open_room(host_api.token, {})
	# The host is in and settled (walked in, door shut, the first presence answer taken).
	for i in 40:
		await create_timer(0.25).timeout
		if host_room.peer_baseline and is_instance_valid(host_room.front_door) and host_room.front_door.steer==null and not host_room.front_door.opened: break
	expect(host_room.peer_baseline and not host_room.front_door.opened, "host inside, door shut")
	# The friend comes in, out of the host's sight (their own room hidden), to a spot in the room.
	var guest_room := open_room(guest_api.token, {"visit_host":accepted.data.host_id,"visit_name":accepted.data.host_name})
	guest_room.visible = false
	var entry := {}
	for i in 60:
		await create_timer(0.1).timeout
		if host_room.peers.size()==1: entry=host_room.peers.values()[0]; break
	expect(not entry.is_empty(), "host sees the friend")
	if entry.is_empty(): quit(1); return
	var door: Node = host_room.front_door
	expect(door.opened, "the door opens for the friend")
	var node: Node3D = entry.node
	expect(node.position.z > door.doorway().z-0.6, "the friend starts at the doorway (z %.2f)" % node.position.z)
	await create_timer(0.35).timeout
	await capture("peer_door_in.png")
	for i in 40:
		await create_timer(0.25).timeout
		if not entry.get("arrive",false): break
	expect(not entry.get("arrive",false), "the friend walked in")
	await create_timer(1.5).timeout
	expect(not door.opened, "the door shut behind the friend")
	# The friend leaves the home.
	guest_room.queue_free()
	await guest_api.post("/v1/social/presence",{"scene":"away"})
	for i in 60:
		await create_timer(0.1).timeout
		if host_room.peers.is_empty(): break
	expect(host_room.peers.is_empty(), "the friend is gone from the home")
	expect(is_instance_valid(node) and door.departing.size()==1, "the friend walks out through the door")
	await create_timer(0.5).timeout
	await capture("peer_door_out.png")
	for i in 40:
		await create_timer(0.25).timeout
		if not is_instance_valid(node): break
	expect(not is_instance_valid(node), "the friend went out")
	var veil = load("res://scripts/transition.gd").instance
	if is_instance_valid(veil): veil.door.stop()
	OS.delay_msec(100)
	quit(1 if failed else 0)
