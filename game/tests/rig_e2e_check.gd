extends SceneTree
## Task 67 end to end, no credits: a QA server with the fake Tripo and rigging on
## (TRIPOTHON_FAKE_TRIPO=true, TRIPO_ENABLE_PAID=true, TRIPOTHON_RIG_ANIM_ENABLED=true) makes a moving
## character from the room's craft window (mesh -> rig -> idle and walk clips), it is placed in the room,
## and the placed character's bones really move.
const Main = preload("res://scripts/main.gd")
const CraftPanel = preload("res://scripts/craft_panel.gd")
const RigMotion = preload("res://scripts/rig_motion.gd")
var failed := false

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ") + description)
	if not value: failed = true

func _initialize() -> void:
	call_deferred("run")

func wait_state(panel: CraftPanel, states: Array, seconds := 60.0) -> Dictionary:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	var seen := []
	while Time.get_ticks_msec() < deadline:
		var stage := str(panel.job.get("stage", ""))
		if not stage.is_empty() and not seen.has(stage): seen.append(stage)
		if str(panel.job.get("state", "")) in states:
			panel.job["seen_stages"] = seen
			return panel.job
		await create_timer(0.25).timeout
	panel.job["seen_stages"] = seen
	return panel.job

func run() -> void:
	var app: Node = Main.new()
	root.add_child(app)
	await create_timer(0.4).timeout
	var server := preload("res://tests/qa_server.gd").url()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	await app.authenticate(true, server, "rig_" + str(Time.get_ticks_msec()), "Rig-check-password-1", "")
	expect(app.screen == "village", "logged in")
	Engine.set_meta("studio_session", {"token": app.api.token, "url": app.api.base_url, "room": "home"})
	var studio: Node = load("res://scenes/studio.tscn").instantiate()
	app.queue_free()
	root.add_child(studio)
	await create_timer(2.5).timeout
	await studio.open_craft()
	var panel: CraftPanel = studio.craft
	await create_timer(0.5).timeout
	expect(not panel._rigging().is_empty() and panel._tripo(), "the server offers rigging and builds with (fake) Tripo")
	panel.prompt.text = "친근한 로봇 캐릭터"
	panel.picture_first.button_pressed = false
	panel.animate_box.button_pressed = true
	var body := panel._body()
	expect(body.get("animate") == true and body.get("geometry") == "tripo", "the craft goes out as a moving character")
	await studio.generate()
	var job := await wait_state(panel, ["awaiting_confirmation", "failed"])
	expect(str(job.get("state")) == "awaiting_confirmation" and job.get("stages", []).has("rig"), "quoted with a rig step (%s, %s)" % [job.get("state"), job.get("error")])
	await studio.confirm_job()
	job = await wait_state(panel, ["ready", "failed"], 120.0)
	expect(str(job.get("state")) == "ready", "built, rigged and animated (%s, %s)" % [job.get("state"), job.get("error")])
	expect(job.get("seen_stages", []).has("rig") or job.get("seen_stages", []).has("mesh"), "the window followed the steps (%s)" % [job.get("seen_stages")])
	var rig: Dictionary = job.get("provenance", {}).get("rig", {})
	expect(rig.get("moves") == true and rig.get("clips", []).has("walk"), "the server marks it moving with idle and walk")
	var crafted := str(job.get("object_id", ""))
	await create_timer(0.8).timeout
	await studio.place_crafted(crafted)
	expect(studio.placement_mode, "place-here starts placing the character")
	for spot in [Vector3(-2.5, 0, -2.5), Vector3(2.5, 0, -2.5), Vector3(-2.5, 0, 0.5), Vector3(2.5, 0, 0.5), Vector3(0, 0, -2.5)]:
		if studio.placement_problem(spot).is_empty():
			studio.place_at = spot
			break
	await studio.commit_place()
	var placed: Node = studio.placed.get(crafted)
	expect(is_instance_valid(placed), "the character stands in the room")
	if is_instance_valid(placed):
		var moving := await RigMotion.verify(placed)
		var players := RigMotion.players(placed)
		expect(moving and not players.is_empty() and players[0].current_animation == "idle", "placed, it idles and its bones move")
	print("RIG_E2E " + ("FAILED" if failed else "OK"))
	studio.queue_free()
	await process_frame
	quit(1 if failed else 0)
