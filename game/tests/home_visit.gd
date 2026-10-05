extends SceneTree
## Two accounts: the host places furniture at home and invites a friend; the friend
## opens the host's home read-only and both see each other inside.
var failed := false
var url := "http://127.0.0.1:8766"

func _initialize() -> void:
	call_deferred("run")
	create_timer(120).timeout.connect(func():
		push_error("Home visit exceeded 120 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func account(api: Node, name: String) -> String:
	var login: Dictionary = await api.post("/v1/auth/register",{"username":name,"password":"home-visit-password-1"})
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
	host_api.token = await account(host_api, "host_"+stamp)
	guest_api.token = await account(guest_api, "guest_"+stamp)
	expect(not host_api.token.is_empty() and not guest_api.token.is_empty(), "two accounts on the server")
	var me: Dictionary = (await host_api.request("/v1/me")).data
	var chair: Dictionary = me.objects[0]
	var placed: Dictionary = await host_api.post("/v1/objects/"+chair.id+"/placement",host_api.mutation({"version":chair.version,"room":"home","x":1.5,"z":-1.5}))
	expect(placed.ok, "host placed furniture at home")
	var invite: Dictionary = await host_api.post("/v1/social/invites",host_api.mutation({"username":"guest_"+stamp,"kind":"village"}))
	var accepted: Dictionary = await guest_api.post("/v1/social/invites/"+str(invite.data.get("id",""))+"/accept",guest_api.mutation())
	expect(accepted.ok and accepted.data.visiting, "friend accepted the visit")
	var host_room := open_room(host_api.token, {})
	var guest_room := open_room(guest_api.token, {"visit_host":accepted.data.host_id,"visit_name":accepted.data.host_name})
	host_room.hero.position = Vector3(-1.5,0,0)
	guest_room.hero.position = Vector3(1,0,3)
	for i in 40:
		await create_timer(0.25).timeout
		if guest_room.placed.has(chair.id) and guest_room.peers.size()==1 and host_room.peers.size()==1: break
	expect(guest_room.title_label.text.contains("host_"+stamp), "friend sees whose home it is")
	expect(not guest_room.dock_panel.visible, "friend has no editing tools")
	expect(guest_room.placed.has(chair.id), "friend sees the host's furniture")
	expect(guest_room.peers.size()==1, "friend sees the host inside")
	expect(host_room.peers.size()==1, "host sees the friend inside")
	if "--capture" in OS.get_cmdline_user_args():
		host_room.visible = false
		await create_timer(0.6).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/home-visit-guest.png"))
		host_room.visible = true
		guest_room.visible = false
		await create_timer(0.6).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/home-visit-host.png"))
	# Leaving the visit (host ends it) sends the friend back out.
	await host_api.post("/v1/social/eject",host_api.mutation({"user_id":accepted.data.self_id}))
	for i in 20:
		await create_timer(0.25).timeout
		if guest_room.visit_host.is_empty(): break
	expect(guest_room.visit_host.is_empty(), "friend leaves when the visit ends")
	quit(1 if failed else 0)
