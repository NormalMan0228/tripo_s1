extends SceneTree
## A visitor's copy of the host's village furniture follows the host in place: a runtime-only change
## (the host using a crafted chest; walking up to furniture does the same every few moments) reloads
## no model and the copy takes the new state; a move and turn moves the same model; a retrieved
## object leaves and a newly placed one loads, without touching the others.
##   godot --headless --path game --script res://tests/visit_furniture_sync.gd -- --mute --qa --server=http://127.0.0.1:8813
const Main = preload("res://scripts/main.gd")
const Town = preload("res://scripts/town.gd")
var server := preload("res://tests/qa_server.gd").url()
var failed := false

func expect(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ")+label)
	if not value: failed = true

func _initialize() -> void:
	call_deferred("run")
	create_timer(180).timeout.connect(func(): print("VISIT_SYNC timeout"); quit(2))

func wait_until(condition: Callable, seconds := 15.0) -> bool:
	var deadline := Time.get_ticks_msec()+int(seconds*1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return condition.call()

func client(name: String) -> Node3D:
	var app := Main.new()
	root.add_child(app)
	await wait_until(func(): return not app.busy and app.screen == "login", 60.0)
	for _attempt in 3:
		await app.authenticate(true, server, name, "Visit-sync-password-1", "")
		if app.screen == "village": break
		await create_timer(0.5).timeout
	expect(app.screen == "village", name+" signed in")
	return app

func owned(app: Node3D, id: String) -> Dictionary:
	var me: Dictionary = await app.api.request("/v1/me")
	for obj in me.data.objects:
		if obj.id == id: return obj
	return {}

func edit(app: Node3D, id: String, path: String, change: Dictionary) -> Dictionary:
	var obj := await owned(app, id)
	var reply: Dictionary = await app.api.post("/v1/objects/"+id+path, app.api.mutation(change.merged({"version": obj.get("version")})))
	if not reply.ok: print("  ", path, " ", change, " -> ", reply.get("error"))
	return reply

func standing_as(copy: Node3D, obj: Dictionary) -> bool:
	return is_instance_valid(copy) and copy.position.distance_to(Town.furniture_point(obj.x, obj.z)) < 0.01 and absf(wrapf(copy.rotation_degrees.y-float(obj.rotation), -180, 180)) < 0.1

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	var suffix := str(Time.get_ticks_msec())
	var host := await client("vhost_"+suffix)
	var guest := await client("vguest_"+suffix)
	if failed: quit(1); return
	# A crafted chest (the demo server's free fixture designer) and a starter object, both placed.
	var queued: Dictionary = await host.api.post("/v1/studio/jobs", host.api.mutation({"prompt": "wooden chest", "geometry": "proxy", "designer": "fixture"}))
	var chest := ""
	for _i in 60:
		var job: Dictionary = await host.api.request("/v1/studio/jobs/"+str(queued.get("data", {}).get("id", "")))
		if job.ok and job.data.state == "ready": chest = job.data.object_id; break
		await create_timer(0.5).timeout
	expect(not chest.is_empty(), "host crafted a chest")
	if chest.is_empty(): quit(1); return
	expect((await edit(host, chest, "", {"action": "place", "x": 5, "z": 4, "rotation": 0})).ok, "host placed the chest")
	await host.refresh_inventory()
	var starter := ""
	for obj in host.me.objects:
		if obj.id != chest and not obj.get("studio", false): starter = obj.id; break
	if (await owned(host, starter)).get("state") != "placed":
		await edit(host, starter, "", {"action": "place", "x": 8, "z": 6, "rotation": 0})
	# The guest visits.
	expect((await host.social.perform("/v1/social/invites", {"username": "vguest_"+suffix, "kind": "village"})).ok, "invitation sent")
	var inbox: Dictionary = await guest.api.request("/v1/social")
	for entry in inbox.data.invites:
		if entry.kind == "village":
			await guest.social.answer(entry, "accept")
			guest.close_village_modal()
	expect(await wait_until(func(): return guest.social.visiting() and is_instance_valid(guest.loaded.get(chest)) and is_instance_valid(guest.loaded.get(starter)), 30.0), "the visitor sees the host's chest and starter object")
	if failed: quit(1); return
	var copy: Node3D = guest.loaded[chest]
	var other: Node3D = guest.loaded[starter]
	var loads := [0]
	guest.object_root.child_entered_tree.connect(func(_node): loads[0] += 1)

	# 1. Runtime only: the host uses the chest (near/leave from walking about bump the same version).
	for round in 3:
		var obj := await owned(host, chest)
		var used: Dictionary = await host.api.post("/v1/objects/"+chest+"/event", host.api.mutation({"version": obj.runtime_version, "event": "click"}))
		expect(used.ok, "host uses the chest (%d)" % round)
		if not used.ok: break
		var version := int(used.data.version)
		expect(await wait_until(func(): return is_instance_valid(copy) and int(copy.runtime_version) == version), "the visitor's chest takes runtime version %d" % version)
		var same_state := true
		for key in used.data.state:
			if is_instance_valid(copy) and copy.vm.state.has(key) and str(copy.vm.state[key]) != str(used.data.state[key]): same_state = false
		expect(same_state, "the visitor's chest has the host's state")
	expect(is_instance_valid(copy) and guest.loaded.get(chest) == copy and is_instance_valid(other) and guest.loaded.get(starter) == other and loads[0] == 0, "no model reloaded for runtime-only changes (loads=%d)" % loads[0])

	# 2. A move and a turn: the same model stands at the new spot.
	expect((await edit(host, chest, "/placement", {"room": "village", "x": 6, "z": 3, "rotation": 90})).ok, "host moved and turned the chest")
	var moved := await owned(host, chest)
	expect(await wait_until(func(): return standing_as(copy, moved)), "the visitor's chest moved and turned in place")
	expect(guest.loaded.get(chest) == copy and loads[0] == 0, "no model reloaded for a move (loads=%d)" % loads[0])

	# 3. Retrieved: it leaves. 4. Placed again: it loads; the chest is untouched.
	expect((await edit(host, starter, "", {"action": "retrieve"})).ok, "host retrieved the starter object")
	var leaving: WeakRef = weakref(other)
	expect(await wait_until(func(): return not guest.loaded.has(starter) and leaving.get_ref() == null), "the retrieved object left the visitor's village")
	expect((await edit(host, starter, "", {"action": "place", "x": 9, "z": 7, "rotation": 0})).ok, "host placed it again")
	expect(await wait_until(func(): return is_instance_valid(guest.loaded.get(starter))), "the placed object appeared for the visitor")
	expect(standing_as(guest.loaded.get(starter), await owned(host, starter)), "at the host's spot")
	expect(guest.loaded.get(chest) == copy and loads[0] == 1, "only the placed object loaded (loads=%d)" % loads[0])
	for app in [guest, host]:
		await app.logout()
		app.queue_free()
	await process_frame
	print("VISIT_SYNC_DONE")
	quit(1 if failed else 0)
