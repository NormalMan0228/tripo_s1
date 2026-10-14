extends SceneTree
## When the host goes, the guests go home, told why (server/multiplayer.py leave, visit_over;
## social.gd announce_visit_end; studio.gd share_presence). Real clients on a QA server:
## 1. a guest watches the host walk: the host's walker moves without jumps or halts;
## 2. the host logs out: the guest is home within moments, with "<host>님이 마을을 떠나서…";
## 3. the host's game dies (no logout, no farewell): the guest is home once the host has been
##    silent for HOST_GONE_SECONDS (20 s), with the lost-connection reason;
## 4. the reverse: a guest who closes the game is gone from the host's village at once;
## 5. in the host's home: the host closes the game and the visiting friend's room sends it home.
const Main = preload("res://scripts/main.gd")
const PASSWORD := "Host-leaves-password-1"
var failed := false
var url := preload("res://tests/qa_server.gd").url()
var names: Array[String] = []

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("Host leaves exceeded 240 seconds")
		quit(2))

func expect(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ")+label)
	if not value: failed = true

func wait_seconds(seconds: float) -> void:
	await create_timer(seconds).timeout

func client(index: int, register: bool) -> Node3D:
	var app := Main.new()
	root.add_child(app)
	await process_frame
	# The title first asks its default world about this version; signing in meanwhile was refused.
	for i in 300:
		if app.title_page != "checking": break
		await process_frame
	await app.authenticate(register, url, names[index], PASSWORD, "")
	expect(app.screen == "village", "%s signed in (%s, %s)" % [names[index], app.screen, str(app.last_notice)])
	return app

func visit(host: Node3D, guest: Node3D, guest_index: int) -> void:
	var sent: Dictionary = await host.social.perform("/v1/social/invites", {"username":names[guest_index], "kind":"village"})
	var inbox: Dictionary = await guest.api.request("/v1/social")
	for entry in inbox.data.get("invites", []):
		if entry.kind == "village":
			await guest.social.answer(entry, "accept")
			guest.close_village_modal()
			break
	for i in 60:
		if guest.social.visiting() and guest.screen == "village" and guest.social.peers.size() == 1 and host.social.peers.size() == 1: break
		await wait_seconds(.1)
	expect(sent.ok and guest.social.visiting() and guest.social.peers.size() == 1 and host.social.peers.size() == 1, "%s visits and both see each other" % guest.me.username)

## Waits until the guest is back in its own village; returns the seconds it took.
func sent_home(guest: Node3D, limit: float) -> float:
	var start := Time.get_ticks_msec()
	while (Time.get_ticks_msec()-start)*.001 < limit:
		if not guest.social.visiting() and guest.screen == "village" and str(guest.social.data.get("host_id", "")) == str(guest.social.data.get("self_id", "-")): break
		await wait_seconds(.1)
	await wait_seconds(.3)
	return (Time.get_ticks_msec()-start)*.001

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): url = arg.trim_prefix("--server=")
	var suffix := str(Time.get_unix_time_from_system()).replace(".", "").right(9)
	for index in 2: names.append("leave_"+suffix+"_"+str(index))
	var host := await client(0, true)
	var guest := await client(1, true)
	# 1. The guest watches the host walk two seconds and stop.
	await visit(host, guest, 1)
	var walker: Node3D = guest.social.peers.values()[0].node
	var steps := []
	var start: Vector3 = walker.position
	Input.action_press("move_right")
	for frame in 200:
		var before: Vector3 = walker.position
		await process_frame
		steps.append(walker.position.distance_to(before))
		if frame == 120: Input.action_release("move_right")
	Input.action_release("move_right")
	for i in 40: await process_frame
	var moved := 0
	var biggest := 0.0
	for step in steps:
		biggest = maxf(biggest, step)
		if step > 0.002: moved += 1
	expect(walker.position.distance_to(start) > 2.0, "the host's walker crossed %.1f m on the guest's screen" % walker.position.distance_to(start))
	expect(biggest < 0.2, "no jumps: largest step %.3f m in a frame" % biggest)
	print("SMOOTH_LIVE moved_frames=%d of %d biggest_step=%.3f delay=%.2f" % [moved, steps.size(), biggest, guest.social.peers.values()[0].motion.delay])
	# 2. The host logs out.
	await host.logout()
	var took := await sent_home(guest, 5.0)
	var info = guest.social.data.get("visit_ended")
	expect(not guest.social.visiting() and info is Dictionary and info.reason == "left", "host logged out: guest home in %.1f s" % took)
	expect(names[0] in str(guest.last_notice), "guest is told: "+str(guest.last_notice))
	host.queue_free()
	await process_frame
	# 3. The host's game dies: no logout, no farewell.
	host = await client(0, false)
	await visit(host, guest, 1)
	host.queue_free()
	await process_frame
	took = await sent_home(guest, 35.0)
	info = guest.social.data.get("visit_ended")
	expect(not guest.social.visiting() and info is Dictionary and info.reason == "host_lost" and took < 32.0, "host's game died: guest home after %.1f s of silence" % took)
	expect(names[0] in str(guest.last_notice), "guest is told: "+str(guest.last_notice))
	# 4. The reverse: the guest closes the game; the host sees it leave at once.
	host = await client(0, false)
	await visit(host, guest, 1)
	guest.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
	guest.queue_free()
	await process_frame
	var gone_start := Time.get_ticks_msec()
	while host.social.peers.size() > 0 and Time.get_ticks_msec()-gone_start < 5000: await wait_seconds(.05)
	var gone := (Time.get_ticks_msec()-gone_start)*.001
	expect(host.social.peers.is_empty() and gone < 1.5, "a guest who closes the game leaves the host's village in %.2f s" % gone)
	var back: Dictionary = await host.api.request("/v1/social")
	await host.logout()
	host.queue_free()
	await process_frame
	# 5. In the host's home: the host closes the game; the friend's room sends it home.
	await rooms()
	print("HOST_LEAVES_COMPLETE")
	quit(1 if failed else 0)

func account(api: Node, name: String) -> String:
	var login: Dictionary = await api.post("/v1/auth/register", {"username":name, "password":PASSWORD})
	return login.data.token if login.ok else ""

func open_room(token: String, extra: Dictionary) -> Control:
	var session := {"token":token, "url":url, "room":"home", "multiplayer":true}
	session.merge(extra, true)
	Engine.set_meta("studio_session", session)
	var room: Control = load("res://scenes/studio.tscn").instantiate()
	root.add_child(room)
	return room

func rooms() -> void:
	var host_api: Node = load("res://scripts/api.gd").new(); root.add_child(host_api); host_api.base_url = url
	var guest_api: Node = load("res://scripts/api.gd").new(); root.add_child(guest_api); guest_api.base_url = url
	var stamp := str(Time.get_ticks_msec())
	host_api.token = await account(host_api, "roomhost_"+stamp)
	guest_api.token = await account(guest_api, "roomguest_"+stamp)
	var invite: Dictionary = await host_api.post("/v1/social/invites", host_api.mutation({"username":"roomguest_"+stamp, "kind":"village"}))
	var accepted: Dictionary = await guest_api.post("/v1/social/invites/"+str(invite.data.get("id", ""))+"/accept", guest_api.mutation())
	var host_room := open_room(host_api.token, {})
	var guest_room := open_room(guest_api.token, {"visit_host":accepted.data.host_id, "visit_name":accepted.data.host_name})
	for i in 40:
		await wait_seconds(.25)
		if guest_room.peers.size() == 1 and host_room.peers.size() == 1: break
	expect(guest_room.peers.size() == 1 and host_room.peers.size() == 1, "host and friend meet in the host's home")
	var walker: Node3D = guest_room.peers.values()[0].node
	expect(guest_room.peers.values()[0].motion.started and walker.position.distance_to(host_room.hero.position) < 1.0, "the friend sees the host where the host stands")
	host_room.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
	var start := Time.get_ticks_msec()
	while not guest_room.visit_host.is_empty() and Time.get_ticks_msec()-start < 5000: await wait_seconds(.05)
	expect(guest_room.visit_host.is_empty(), "host closed the game: the friend's room heads home after %.2f s" % ((Time.get_ticks_msec()-start)*.001))
	var social: Dictionary = await guest_api.request("/v1/social")
	expect(social.ok and not social.data.visiting and social.data.visit_ended.reason == "left", "the friend's village says why (%s)" % str(social.data.get("visit_ended", {})))
	# Quit before the room's switch to the village (as home_visit.gd): stop the door sound first.
	var veil = load("res://scripts/transition.gd").instance
	if is_instance_valid(veil): veil.door.stop()
	OS.delay_msec(100)
