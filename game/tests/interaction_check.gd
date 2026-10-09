extends SceneTree
## End to end against a local demo server: the village bag opens the interaction editor on a crafted
## chest, picks ready-made behaviours (spin on click, light when near, open the lid on click, a seat),
## previews and saves them; the placed village copy runs them (E/click and walking up), a fresh load
## does too, a visitor's copy plays them, and in a room the walker sits on it while it spins.
##   godot --path game --script res://tests/interaction_check.gd -- --server=http://127.0.0.1:8813
const Assembly = preload("res://scripts/asset_assembly.gd")
const Api = preload("res://scripts/api.gd")
const Town = preload("res://scripts/town.gd")

var server := "http://127.0.0.1:8813"
var failures: Array[String] = []
var passes := 0

func check(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ") + label)
	if value: passes += 1
	else: failures.append(label)

func _initialize() -> void:
	call_deferred("run")

func wait_until(condition: Callable, seconds := 20.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return false

func finish() -> void:
	print("INTERACTION_CHECK ", JSON.stringify({"ok": failures.is_empty(), "passed": passes, "failures": failures}))
	quit(0 if failures.is_empty() else 1)

## Strongest glow on any surface of a copy.
func glow(item: Node3D) -> float:
	var best := 0.0
	for id in item.surfaces:
		for mesh in item.surfaces[id]:
			for i in mesh.mesh.get_surface_count():
				var mat := mesh.get_surface_override_material(i) as StandardMaterial3D
				if mat and mat.emission_enabled: best = maxf(best, mat.emission_energy_multiplier)
	return best

## Whole-object spin angle (0 at rest) and the lid's hinge angle.
func spin(item: Node3D) -> float:
	return absf(wrapf(item.whole_root.rotation_degrees.y, -180.0, 180.0))

func lid(item: Node3D) -> float:
	return item.pivots["lid"].rotation_degrees.x

## Fires E/click on a copy and reports the biggest spin seen while it plays.
func spin_peak(item: Node3D, fire: Callable) -> float:
	await fire.call()
	var peak := 0.0
	var deadline := Time.get_ticks_msec() + 1600
	while Time.get_ticks_msec() < deadline and is_instance_valid(item):
		peak = maxf(peak, spin(item))
		await process_frame
	return peak

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	var app = load("res://scripts/main.gd").new()
	root.add_child(app)
	await process_frame
	var password := "Local-interact-qa-1!"
	# The village builds itself first; signing in waits for that.
	await wait_until(func(): return not app.busy and app.screen == "login", 60.0)
	# The very first request of a fresh window can fail to connect: try signing in again.
	for _attempt in 3:
		await app.authenticate(true, server, "act_" + str(Time.get_ticks_usec() % 100000000), password, "")
		if app.screen == "village": break
		await create_timer(0.5).timeout
	check(app.screen == "village", "registered and in the village (%s)" % app.screen)
	if app.screen != "village": finish(); return
	var token: String = app.api.token

	# A moving fixture craft: a chest with a body and a lid.
	var queued: Dictionary = await app.api.post("/v1/studio/jobs", app.api.mutation({"prompt": "wooden chest", "geometry": "proxy", "designer": "fixture"}))
	var id := ""
	for _i in 60:
		var job: Dictionary = await app.api.request("/v1/studio/jobs/" + str(queued.get("data", {}).get("id", "")))
		if job.ok and job.data.state == "ready": id = job.data.object_id; break
		await create_timer(0.5).timeout
	check(not id.is_empty(), "fixture chest crafted")
	if id.is_empty(): finish(); return
	await app.refresh_inventory()
	var index := -1
	for i in app.me.objects.size():
		if app.me.objects[i].id == id: index = i
	app.select_object(index)
	check(await wait_until(func(): return is_instance_valid(app.inspect_model) and app.selected.get("id") == id and app.inspect_model.get_meta("studio", false)), "chest inspected in the bag")
	var bag_model: Node3D = app.inspect_model
	var bag_stage: Node = bag_model.get_parent()

	# The editor: spin on click, light when near, open the lid on click, a seat.
	app.open_interactions()
	var panel: Control = app.interaction_panel
	check(await wait_until(func(): return is_instance_valid(panel) and not panel.info.is_empty()), "interaction editor opens")
	if not is_instance_valid(panel) or panel.info.is_empty(): finish(); return
	check(bag_model.get_parent() == panel.turntable, "the bag's copy is borrowed into the editor stage")
	check(not app.world_movement_allowed(), "the walker stays still while editing")
	if "--capture" in OS.get_cmdline_user_args():
		panel._pick_card("spin"); panel._pick_card("glow"); panel._pick_card("hinge")
		await create_timer(1.0).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://../artifacts/interaction-editor.png")
		panel.choice.presets.clear()
	# 글로 설명하기 (the demo server's fixture designer): a program for the existing parts, paid once.
	var shards_before := int(app.me.shards)
	panel._set_mode("custom")
	panel.describe_text.text = "다가가면 은은하게 빛나요"
	await panel._describe()
	check(not panel.draft.is_empty() and bag_model.vm.program.get("events", {}).has("near"), "a description becomes a program on the copy")
	var me_now: Dictionary = await app.api.request("/v1/me")
	check(me_now.ok and int(me_now.data.shards) == shards_before - 5, "a description costs 5 starseeds")
	panel._set_mode("presets")
	panel._pick_card("spin")
	panel._pick_card("glow")
	panel._set_option("trigger", "near")
	panel._set_option("level", 3)
	panel._pick_card("hinge")
	check(panel.choice.presets.size() == 3 and panel.choice.presets[2].target == "lid", "hinge picks the lid")
	panel._set_option("angle", -90)
	panel._set_rest("sit")
	await panel._preview(true)
	check(bag_model.vm.program.get("events", {}).has("near"), "preview runs the choice on the borrowed copy")
	var version_before := int(app.me.objects[index].runtime_version)
	await panel._save()
	check(panel.saved_once, "saved")
	check(int(app.me.objects[index].runtime_version) == version_before + 1, "the bag knows the new runtime version")
	check(str(bag_model.manifest.get("interaction", {}).get("rest", "")) == "sit", "the borrowed copy runs the saved interaction")
	var gone: WeakRef = weakref(panel)
	panel.close_panel()
	check(await wait_until(func(): return gone.get_ref() == null), "editor closes")
	check(bag_model.get_parent() == bag_stage, "the copy goes back to the bag preview")

	# The village: place it, then E (click) spins it and opens the lid, walking up lights it.
	await app.begin_place()
	if is_instance_valid(app.preview):
		app.preview.position = Town.furniture_point(4, 3)
		await app.place_preview()
	check(await wait_until(func(): return app.loaded.has(id) and is_instance_valid(app.loaded[id])), "placed in the village")
	if not app.loaded.has(id): finish(); return
	var village_copy: Node3D = app.loaded[id]
	check(village_copy.rest == "sit" and village_copy.vm.program.get("events", {}).has("near"), "the village copy loads the interaction")
	app.player.position = Town.furniture_point(4, 4.4)
	await app.village_furniture_proximity()
	check(await wait_until(func(): return glow(village_copy) > 2.5, 5.0), "walking up lights it (emission %.2f)" % glow(village_copy))
	var peak: float = await spin_peak(village_copy, func(): await app.village_furniture_event(id, "click"))
	check(peak > 60.0, "E spins the whole chest (peak %.0f°)" % peak)
	check(await wait_until(func(): return lid(village_copy) < -80.0, 5.0), "E opens the lid (%.0f°)" % lid(village_copy))
	app.player.position = Town.furniture_point(9, 9)
	await app.village_furniture_proximity()
	check(await wait_until(func(): return glow(village_copy) < 0.2, 5.0), "walking away dims it")

	# A fresh load (another session) runs the same.
	var old_copy: Node3D = app.loaded[id]
	app.loaded.erase(id)
	old_copy.queue_free()
	await app.refresh_inventory()
	check(await wait_until(func(): return app.loaded.has(id) and is_instance_valid(app.loaded[id])), "reloaded")
	var reloaded: Node3D = app.loaded[id]
	check(reloaded.rest == "sit" and spin(reloaded) < 1.0, "after a reload the interaction is there and the last spin is not replayed")
	peak = await spin_peak(reloaded, func(): await app.village_furniture_event(id, "click"))
	check(peak > 60.0, "after a reload E still spins it (peak %.0f°)" % peak)
	# Another device adds a bounce: the kept village copy picks it up on the next refresh, in place.
	var current: Dictionary = await app.api.request("/v1/objects/" + id + "/interaction")
	var presets: Array = current.data.spec.presets if current.ok else []
	presets.append({"kind": "bounce", "trigger": "always", "target": "whole", "level": 1, "direction": 1, "axis": "x", "angle": 90})
	var other: Dictionary = await app.api.post("/v1/objects/" + id + "/interaction", app.api.mutation({"version": int(current.data.get("runtime_version", 0)) if current.ok else 0, "mode": "presets", "presets": presets, "keep": true, "rest": "sit"}))
	check(other.ok, "another device saves a change")
	await app.refresh_inventory()
	check(app.loaded.get(id) == reloaded and JSON.stringify(reloaded.vm.program).contains("offset_y"), "the kept village copy runs the other device's change")

	# A visiting friend's copy plays it on their screen.
	var guest := Api.new(); root.add_child(guest); guest.base_url = server
	var guest_name := "actg_" + str(Time.get_ticks_usec() % 100000000)
	var login: Dictionary = await guest.post("/v1/auth/register", {"username": guest_name, "password": password})
	guest.token = login.data.get("token", "") if login.ok else ""
	var invite: Dictionary = await app.api.post("/v1/social/invites", app.api.mutation({"username": guest_name, "kind": "village"}))
	var accepted: Dictionary = await guest.post("/v1/social/invites/" + str(invite.get("data", {}).get("id", "")) + "/accept", guest.mutation())
	check(invite.ok and accepted.ok, "friend invited into the village")
	var visit_copy: Node3D = await Assembly.fetch(guest, id, "/v1/social/village/objects/")
	check(visit_copy != null and visit_copy.rest == "sit", "the visitor's copy has the interaction")
	if visit_copy:
		root.add_child(visit_copy)
		peak = await spin_peak(visit_copy, func(): visit_copy.local_event("click"))
		check(peak > 60.0, "the visitor sees it spin (peak %.0f°)" % peak)
		visit_copy.local_event("near")
		check(await wait_until(func(): return glow(visit_copy) > 2.5, 5.0), "the visitor sees it light up")
		visit_copy.queue_free()
	guest.queue_free()

	# A room: move it into the workshop; E sits on it and spins it, walking up lights it.
	var obj: Dictionary = {}
	for item in app.me.objects:
		if item.id == id: obj = item
	var moved: Dictionary = await app.api.post("/v1/objects/" + id + "/placement", app.api.mutation({"version": int(obj.version), "action": "retrieve"}))
	var placed: Dictionary = await app.api.post("/v1/objects/" + id + "/placement", app.api.mutation({"version": int(obj.version) + 1, "room": "workshop", "x": 2, "z": 0}))
	check(moved.ok and placed.ok, "moved into the workshop")
	app.queue_free()
	await process_frame
	Engine.set_meta("studio_session", {"token": token, "url": server, "room": "workshop"})
	change_scene_to_file("res://scenes/studio.tscn")
	check(await wait_until(func(): return current_scene != null and "placed" in current_scene and current_scene.placed.has(id), 30.0), "the workshop loads the chest")
	var studio = current_scene
	if studio == null or not studio.placed.has(id): finish(); return
	var room_copy: Node3D = studio.placed[id]
	check(room_copy.rest == "sit", "the room copy is a seat")
	studio.hero.position = room_copy.position + Vector3(0, 0, 1.2)
	studio.proximity()
	check(await wait_until(func(): return glow(room_copy) > 2.5, 8.0), "walking up lights it in the room")
	peak = await spin_peak(room_copy, func(): await studio.interact_nearest())
	check(studio.resting == "sit", "E sits on it")
	check(peak > 60.0, "E spins it in the room (peak %.0f°)" % peak)
	studio.stand_up()
	# The 보관함 tab opens the editor too; 원래대로 + save brings the crafted chest back.
	var studio_index := -1
	for i in studio.data.objects.size():
		if studio.data.objects[i].id == id: studio_index = i
	await studio.select_item(studio_index)
	studio.open_interactions()
	var room_panel: Control = studio.interaction_panel
	check(await wait_until(func(): return is_instance_valid(room_panel) and not room_panel.info.is_empty()), "the 보관함 tab opens the editor")
	if is_instance_valid(room_panel):
		check(room_panel.choice.presets.size() == 4 and room_panel.choice.rest == "sit", "the editor shows the saved choice")
		room_panel._reset_choice()
		await room_panel._save()
		room_panel.close_panel()
	check(await wait_until(func(): return room_copy.rest == "" and not room_copy.manifest.has("interaction")), "원래대로 brings the crafted behaviour back to the placed copy")
	var after: Dictionary = await studio.api.request("/v1/objects/" + id + "/assembly")
	check(after.ok and not after.data.has("interaction"), "the server runs the crafted program again")
	finish()
