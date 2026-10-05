extends SceneTree
const Main = preload("res://scripts/main.gd")
var apps: Array = []
var names: Array[String] = []
var failed := false
var url := "http://127.0.0.1:8766"

func _initialize() -> void:
	Engine.set_meta("multiplayer_feature", true)
	call_deferred("run_test")
	create_timer(150).timeout.connect(func():
		push_error("Multiplayer integration exceeded 150 seconds")
		quit(2))

func expect(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ")+label)
	if not value: failed = true

func wait_seconds(seconds: float) -> void:
	await create_timer(seconds).timeout

func capture(label: String, selected: int) -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	for index in apps.size():
		apps[index].visible = index == selected
		apps[index].ui.get_parent().visible = index == selected
	apps[selected].camera.current = true
	await process_frame
	await RenderingServer.frame_post_draw
	var path := ProjectSettings.globalize_path("res://../artifacts/multiplayer-"+label+".png")
	expect(root.get_texture().get_image().save_png(path) == OK, "capture "+label)
	for app in apps:
		app.visible = true
		app.ui.get_parent().visible = true

func add_client(index: int, register: bool) -> Node3D:
	var app := Main.new()
	root.add_child(app)
	await process_frame
	await app.authenticate(register, url, names[index], "multiplayer-test-password", "")
	expect(app.screen == "village", "client %d authenticated" % index)
	return app

func invitation(sender: int, recipient: int, kind: String) -> void:
	var response: Dictionary = await apps[sender].social.perform("/v1/social/invites", {"username":names[recipient], "kind":kind})
	expect(response.ok, kind+" invitation sent")
	var inbox: Dictionary = await apps[recipient].api.request("/v1/social")
	var found := false
	for entry in inbox.data.invites:
		if entry.kind == kind:
			await apps[recipient].social.answer(entry, "accept")
			apps[recipient].close_village_modal()
			found = true
			break
	expect(found, kind+" invitation accepted by intended player")

func run_test() -> void:
	var suffix := str(Time.get_unix_time_from_system()).replace(".", "").right(10)
	for index in 3:
		names.append("multi_"+suffix+"_"+str(index))
		apps.append(await add_client(index, true))
	await wait_seconds(1)
	expect(apps[0].social.enabled, "multiplayer capability negotiated")
	expect(apps[0].social.data.host_id != apps[1].social.data.host_id and apps[1].social.data.host_id != apps[2].social.data.host_id, "three private villages")
	var object_id: String = apps[0].me.objects[0].id
	await apps[0].edit_object({"action":"place", "x":5, "z":4, "rotation":0})
	await apps[0].refresh_inventory()
	await invitation(0, 1, "village")
	await invitation(0, 2, "village")
	for attempt in 60:
		if apps.all(func(a): return a.social.peers.size() == 2): break
		await wait_seconds(.1)
	for index in 3:
		if apps[index].social.peers.size() != 2: print("PEER_DIAGNOSTIC ", index, " ", apps[index].social.data.get("village", {}))
		expect(apps[index].social.peers.size() == 2, "client %d sees two other players" % index)
	for index in [1, 2]:
		expect(apps[index].social.visiting() and apps[index].loaded.has(object_id), "visitor sees host furniture")
		expect(not await apps[index].life.action("gather", {"item":"apple"}), "visitor cannot edit host life")
	await apps[0].social.send_message("동료들과 같은 마을에서 만났어요")
	await wait_seconds(.7)
	expect(not apps[1].social.data.messages.is_empty(), "village conversation delivered")
	await capture("village", 0)
	await apps[1].social.open_menu()
	await capture("invitation-panel", 1)
	apps[1].close_village_modal()
	await apps[0].social.perform("/v1/party")
	await invitation(0, 1, "party")
	await invitation(0, 2, "party")
	await wait_seconds(.7)
	var started: Dictionary = await apps[0].social.perform("/v1/party/runs", {"map_id":"forest", "difficulty":"relaxed"})
	expect(started.ok, "party leader starts a shared expedition")
	if not started.ok:
		quit(1)
		return
	var shared_id: String = started.data.id
	for attempt in 100:
		if apps.all(func(a): return a.screen == "survival" and a.coop_run): break
		await wait_seconds(.1)
	for index in 3:
		expect(apps[index].screen == "survival" and apps[index].run_id == shared_id, "client %d joins same cooperative run" % index)
		expect(apps[index].social.peers.size() == 2, "cooperative peer rendering %d" % index)
	if failed:
		quit(1)
		return
	apps[1].intent("fire")
	await wait_seconds(1)
	for app in apps: expect(app.run.fire_remaining > 0, "shared campfire visible")
	apps[1].intent("harvest", "n3")
	await wait_seconds(1)
	var quantities := []
	for app in apps:
		for node in app.run.nodes:
			if node.id == "n3": quantities.append(int(node.quantity))
	expect(quantities.size() == 3 and quantities[0] == quantities[1] and quantities[1] == quantities[2] and quantities[0] < 6, "shared resource consumed once")
	var elapsed: float = apps[0].run.elapsed
	apps[0].toggle_pause()
	await wait_seconds(.8)
	expect(apps[0].run.elapsed > elapsed and apps[1].run.elapsed > elapsed, "menu does not pause teammates")
	apps[0].toggle_pause()
	await capture("coop", 0)
	await apps[2].leave_run()
	await wait_seconds(.7)
	expect(apps[2].screen == "village" and apps[0].run.status == "active", "one player can withdraw without ending party run")
	# Destroy one real client, then log in through a fresh client instance.
	apps[1].queue_free()
	await process_frame
	await wait_seconds(1)
	apps[1] = await add_client(1, false)
	for attempt in 100:
		if apps[1].screen == "survival" and apps[1].run_id == shared_id: break
		await wait_seconds(.1)
	expect(apps[1].screen == "survival" and apps[1].run_id == shared_id, "relogin resumes same cooperative expedition")
	expect(apps[1].run.inventory.fiber > 0, "private inventory persists across reconnect")
	await apps[0].leave_run()
	await apps[1].leave_run()
	await apps[2].social.return_home()
	expect(not apps[2].social.visiting(), "visitor can return to own village")
	for app in apps:
		await app.logout()
		app.queue_free()
	await process_frame
	print("MULTIPLAYER_INTEGRATION_COMPLETE")
	quit(1 if failed else 0)
