extends SceneTree
## The one craft window (craft_panel.gd) in the village (C) and in a room: a text-only craft shows the
## AI's concept picture with the text sent to Tripo, can be redrawn, then is built from the picture
## and lands in the bag. Runs against the QA server (demo mode: placeholder picture, sample shapes).
const Main = preload("res://scripts/main.gd")
const CraftPanel = preload("res://scripts/craft_panel.gd")
var failed := false
var app: Node

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func _initialize() -> void:
	call_deferred("run")

func capture(name: String) -> void:
	if DisplayServer.get_name() == "headless": return
	for i in 6: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/craft-panel-"+name+".png"))

func wait_state(panel: CraftPanel, states: Array, seconds := 30.0) -> Dictionary:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		if str(panel.job.get("state", "")) in states: return panel.job
		await create_timer(0.25).timeout
	return panel.job

func labels(node: Node) -> String:
	var out := []
	for l in node.find_children("*", "Label", true, false): out.append(l.text)
	for b in node.find_children("*", "Button", true, false): out.append(b.text)
	return "\n".join(out)

func run() -> void:
	app = Main.new()
	root.add_child(app)
	await create_timer(0.4).timeout
	await app.authenticate(true, "http://127.0.0.1:8766", "panel_"+str(Time.get_ticks_msec()), "Panel-check-password-1", "")
	expect(app.screen == "village", "logged in")
	var shards: int = int(app.me.shards)
	# The village window is the shared panel.
	await app.open_craft()
	var panel: CraftPanel = app.craft_box
	expect(panel is CraftPanel and panel.form.visible, "village C opens the shared craft window")
	expect(panel.concept_note.visible and not panel.ask.disabled, "text-only craft offers the concept picture first")
	expect(panel.motion.selected == 0 and panel.find_children("*", "TextEdit", true, false).size() == 1, "static furniture and a text box by default")
	await create_timer(0.5).timeout
	await capture("form")
	await app.request_craft("small wooden chest")
	expect(not app.craft_job.is_empty(), "village craft request accepted")
	var job := await wait_state(panel, ["awaiting_confirmation", "failed"])
	expect(str(job.get("state")) == "awaiting_confirmation" and not job.get("concept", {}).is_empty(), "concept picture drawn before 3D")
	var deadline := Time.get_ticks_msec() + 5000
	var picture: TextureRect = null
	while Time.get_ticks_msec() < deadline:
		var pictures := panel.status.find_children("*", "TextureRect", true, false)
		if not pictures.is_empty() and pictures[0].texture != null:
			picture = pictures[0]
			break
		await create_timer(0.2).timeout
	expect(picture != null, "the picture is shown in the window")
	var text := labels(panel.status)
	expect(text.contains("Tripo") and text.contains("•"), "the text sent to Tripo is shown with the picture")
	await capture("concept")
	await panel.redraw_concept()
	await create_timer(0.3).timeout
	job = await wait_state(panel, ["awaiting_confirmation"])
	deadline = Time.get_ticks_msec() + 15000
	while Time.get_ticks_msec() < deadline and int(panel.job.get("concept", {}).get("draws", 0)) < 2:
		await create_timer(0.25).timeout
	expect(int(panel.job.get("concept", {}).get("draws", 0)) == 2, "redraw makes a second picture")
	await app.confirm_craft()
	job = await wait_state(panel, ["ready", "failed"], 40.0)
	expect(str(job.get("state")) == "ready", "built from the approved picture")
	expect(app.craft_job.is_empty() and not app.craft_done.is_empty(), "village knows the craft is done")
	expect(labels(panel.status).contains(tr("지금 마을에 놓기")), "place button offered")
	var mine: Array = app.me.objects.filter(func(o) -> bool: return o.id == str(job.get("object_id", "")))
	expect(mine.size() == 1 and int(app.me.shards) < shards, "object in the bag and starseeds spent")
	await capture("ready")
	app.close_village_modal()
	# Photo crafts skip the picture; cancelling gives the starseeds back.
	await app.open_craft()
	panel = app.craft_box
	expect(labels(panel.status).contains(tr("지금 마을에 놓기")), "reopening shows the finished craft")
	panel.status.find_children("*", "Button", true, false).filter(func(b) -> bool: return b.text == tr("새로 만들기"))[0].pressed.emit()
	await process_frame
	expect(panel.form.visible and app.craft_done.is_empty(), "새로 만들기 returns to the form")
	shards = int(app.me.shards)
	panel.prompt.text = "a round lamp"
	await panel.request()
	job = await wait_state(panel, ["awaiting_confirmation"])
	await app.cancel_craft()
	await create_timer(0.5).timeout
	await app.refresh_inventory()
	expect(app.craft_job.is_empty() and int(app.me.shards) == shards and panel.form.visible, "cancel refunds and returns to the form")
	app.close_village_modal()
	# The room's [만들기] tab is the same window and places the craft in the room.
	Engine.set_meta("studio_session", {"token": app.api.token, "url": app.api.base_url, "room": "home"})
	var studio: Node = load("res://scenes/studio.tscn").instantiate()
	app.queue_free()
	root.add_child(studio)
	await create_timer(2.5).timeout
	panel = studio.craft
	expect(panel is CraftPanel and panel.form.visible and studio.prompt == panel.prompt, "room create tab is the shared craft window")
	studio.set_dock_open(true)
	await create_timer(0.3).timeout
	await capture("room-form")
	studio.prompt.text = "tiny round stool"
	await studio.generate()
	expect(not studio.job_id.is_empty(), "room craft request accepted")
	job = await wait_state(panel, ["awaiting_confirmation"])
	expect(not job.get("concept", {}).is_empty(), "room craft shows the concept picture too")
	await capture("room-concept")
	await studio.confirm_job()
	job = await wait_state(panel, ["ready", "failed"], 40.0)
	expect(str(job.get("state")) == "ready" and labels(panel.status).contains(tr("이 방에 놓기")), "room craft finished with a place-here button")
	await create_timer(0.8).timeout
	await studio.place_crafted(str(job.get("object_id", "")))
	expect(studio.placement_mode and str(studio.selected.get("id", "")) == str(job.get("object_id", "")), "place-here starts placing the new object")
	await capture("room-place")
	print("CRAFT_PANEL " + ("FAILED" if failed else "OK"))
	studio.queue_free()
	await process_frame
	quit(1 if failed else 0)
