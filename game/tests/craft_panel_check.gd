extends SceneTree
## The one craft window (craft_panel.gd) in the village (C) and in a room: a text-only craft shows the
## AI's concept picture with the text sent to Tripo, can be redrawn, then is built from the picture
## and lands in the bag. Runs against the QA server (demo mode: placeholder picture, sample shapes).
const Main = preload("res://scripts/main.gd")
const CraftPanel = preload("res://scripts/craft_panel.gd")
const Assembly = preload("res://scripts/asset_assembly.gd")
const Fx = preload("res://scripts/fx.gd")
const CraftBadge = preload("res://scripts/craft_badge.gd")
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
	var server := preload("res://tests/qa_server.gd").url()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	await app.authenticate(true, server, "panel_"+str(Time.get_ticks_msec()), "Panel-check-password-1", "")
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
	expect(app.craft_announced == CraftPanel.announce_key(job), "the village announces the picture once")
	expect(job.get("stages", []) == ["design", "concept", "mesh", "done"] and str(job.get("stage")) == "confirm", "the server names the steps")
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
	expect(labels(panel.status).contains(tr("여기에 놓기")), "place button offered")
	var mine: Array = app.me.objects.filter(func(o) -> bool: return o.id == str(job.get("object_id", "")))
	expect(mine.size() == 1 and int(app.me.shards) < shards, "object in the bag and starseeds spent")
	await capture("ready")
	app.close_village_modal()
	# While a craft waits for the player with the window closed, the HUD's craft slot (C) wears a badge (17).
	var tracker: Node = app.craft_tracker()
	tracker.badge(true)
	await process_frame
	var slots := CraftBadge.slots()
	expect(not slots.is_empty() and slots.all(func(slot: Control) -> bool: return slot.get_node_or_null(CraftBadge.NAME) != null), "the HUD craft slot wears a badge while the craft waits")
	await create_timer(0.8).timeout
	await capture("badge")
	# Photo crafts skip the picture; cancelling gives the starseeds back.
	await app.open_craft()
	panel = app.craft_box
	await process_frame
	expect(not tracker.needs_you and CraftBadge.slots().all(func(slot: Control) -> bool:
		var dot := slot.get_node_or_null(CraftBadge.NAME)
		return dot == null or dot.is_queued_for_deletion()), "opening the craft window clears the badge")
	expect(labels(panel.status).contains(tr("여기에 놓기")), "reopening shows the finished craft")
	panel.status.find_children("*", "Button", true, false).filter(func(b) -> bool: return b.text == tr("새로 만들기"))[0].pressed.emit()
	await process_frame
	expect(panel.form.visible and app.craft_done.is_empty(), "새로 만들기 returns to the form")
	# A clock is always made moving (its hands are free): the form picks that and says why.
	panel.prompt.text = "벽시계"
	await panel._ask_kind()
	expect(panel.motion.selected == 1 and panel.motion.is_item_disabled(0) and panel.concept_note.visible and panel.concept_note.text.contains("바늘"),
		"a clock is made moving, and the form says its hands are free")
	panel.prompt.text = "a round lamp"
	await panel._ask_kind()
	expect(panel.motion.selected == 0 and not panel.motion.is_item_disabled(0), "other words give the choice back")
	shards = int(app.me.shards)
	await panel.request()
	job = await wait_state(panel, ["awaiting_confirmation"])
	await app.cancel_craft()
	await create_timer(0.5).timeout
	await app.refresh_inventory()
	expect(app.craft_job.is_empty() and int(app.me.shards) == shards and panel.form.visible, "cancel refunds and returns to the form")
	# Two letters name furniture; a craft under way is followed again after a relaunch (/v1/me).
	panel.prompt.text = "의자"
	await panel.request()
	var two_letters := panel.job_id
	expect(not two_letters.is_empty(), "a two-letter craft (의자) is accepted")
	app.craft_tracker().job_id = ""
	await app.refresh_inventory()
	expect(app.craft_job == two_letters, "the village resumes the craft under way from /v1/me")
	job = await wait_state(panel, ["awaiting_confirmation"])
	await app.cancel_craft()
	await create_timer(0.5).timeout
	expect(panel._explain("invalid_craft_request").contains("2~1500") and not panel._explain("invalid_request").contains("비밀번호"), "bad craft input is worded for crafting, not the login form")
	# The steps view: built once and updated in place; Tripo's percentage when it reports one.
	panel.show_job({"id": "steps", "state": "planning", "stage": "concept", "stages": ["design", "concept", "mesh", "done"]})
	var view: Control = panel.working.get("root")
	var modes: Array = panel.working.steps.map(func(step: Dictionary) -> String: return str(step.mode))
	expect(view != null and modes == ["done", "active", "pending", "pending"] and str(panel.working.title.text).contains("그림"), "the picture step is current while it is drawn (%s)" % [modes])
	panel.show_job({"id": "steps", "state": "building", "stage": "mesh", "stages": ["design", "concept", "mesh", "done"], "progress": 0.42, "parts": {"base": "ready", "lid": "generating"}})
	var bar: ProgressBar = panel.working.bar
	expect(panel.working.get("root") == view and not bar.indeterminate and str(panel.working.percent.text) == "42%", "the same view shows Tripo's percentage")
	expect(str(panel.working.steps[2].caption.text).ends_with("1/2") and str(panel.working.steps[1].mode) == "done", "the 3D step counts finished parts")
	await capture("steps")
	panel.show_job({"id": "steps", "state": "unknown"})
	expect(labels(panel.status).contains(tr("확인이 필요해요")) and panel.working.is_empty() and "unknown" in CraftPanel.TERMINAL, "a held craft ends in a clear state")
	panel.show_job({"id": "steps", "state": "failed", "error": "generation_timeout"})
	expect(panel.form.visible and labels(panel.status).contains(tr("오래")), "a craft stopped at its deadline says so")
	# A refused (inappropriate) craft and every other failure say why, above the form.
	panel.show_job({"id": "steps", "state": "failed", "error": "refused_person", "reason": "refused", "refusal": "person"})
	text = labels(panel.status)
	expect(panel.form.visible and text.contains(tr("만들 수 없는 의뢰예요")) and text.contains("실제 사람") and text.contains("돌려드렸어요"), "a refused craft says why and that the starseeds came back")
	await capture("refused")
	panel.show_job({"id": "steps", "state": "failed", "error": "llm_invalid_design", "reason": "design"})
	expect(labels(panel.status).contains("설계도"), "a failed design says so")
	panel.show_job({"id": "steps", "state": "failed", "error": "refused_hate"})
	expect(labels(panel.status).contains("혐오"), "an older server's refusal code is worded too")
	panel.show_job({})
	panel.prompt.text = "나치 깃발 액자"
	await panel.request()
	expect(panel.job_id.is_empty() and app.craft_job.is_empty(), "a listed word is refused before anything is made")
	expect(panel._explain("refused_drugs").contains("마약") and panel._explain("image_too_large").contains("20MB"), "refusals and photo problems are worded")
	# The picture step can be skipped (69): the craft is built from the words.
	panel.prompt.text = "a round lamp"
	panel.picture_first.button_pressed = false
	await capture("text-only")
	expect(panel.picture_first.visible and panel._body().get("concept") == false and panel.concept_note.text.contains("그림 단계 없이"), "text-only craft skips the picture when asked")
	panel.picture_first.button_pressed = true
	expect(panel._body().get("concept") == true, "and draws it again when asked")
	# Photos: any size up to 20 MB is scaled down and re-encoded under 1 MB; bad files say why.
	var big := Image.create(3000, 2000, false, Image.FORMAT_RGB8)
	big.fill(Color(0.8, 0.5, 0.2))
	var big_path := OS.get_user_data_dir().path_join("craft_check_big.png")
	big.save_png(big_path)
	var photo := CraftPanel.read_photo(big_path)
	expect(not photo.has("error") and maxi(photo.image.get_width(), photo.image.get_height()) == CraftPanel.PHOTO_SIDE and str(photo.data).begins_with("data:image/jpeg;base64,"), "a large photo is scaled to %d px" % CraftPanel.PHOTO_SIDE)
	expect(Marshalls.base64_to_raw(str(photo.data).get_slice(",", 1)).size() <= CraftPanel.PHOTO_SEND_BYTES, "and sent under 1 MB")
	var tiny := Image.create(8, 8, false, Image.FORMAT_RGB8)
	var tiny_path := OS.get_user_data_dir().path_join("craft_check_tiny.png")
	tiny.save_png(tiny_path)
	var junk_path := OS.get_user_data_dir().path_join("craft_check_junk.png")
	var junk := FileAccess.open(junk_path, FileAccess.WRITE)
	junk.store_string("not a picture")
	junk.close()
	expect(CraftPanel.read_photo(tiny_path).get("error") == "image_too_small" and CraftPanel.read_photo(junk_path).get("error") == "image_unreadable", "tiny and broken pictures say why")
	for path in [big_path, tiny_path, junk_path]: DirAccess.remove_absolute(path)
	panel.prompt.text = ""
	expect(CraftPanel.poll_pause(1) == 4.0 and CraftPanel.poll_pause(9) == 30.0, "failed polls back off up to 30 s")
	panel.show_job({})
	app.close_village_modal()
	# A room opens the same window (C) and places the craft in the room.
	Engine.set_meta("studio_session", {"token": app.api.token, "url": app.api.base_url, "room": "home"})
	var studio: Node = load("res://scenes/studio.tscn").instantiate()
	app.queue_free()
	root.add_child(studio)
	await create_timer(2.5).timeout
	await studio.open_craft()
	panel = studio.craft
	expect(panel is CraftPanel and panel.form.visible and studio.prompt == panel.prompt, "the room's C opens the same craft window")
	await create_timer(0.3).timeout
	await capture("room-form")
	# Named styles and sizes from the server, remembered for the next craft.
	expect(panel.style_buttons.size() == 9 and panel.size_buttons.size() == 6 and panel.style_grid.visible, "style and size choices offered (5 sizes + 직접 정하기)")
	# "직접 정하기" opens the drag box; a finished box goes out as dims, the size as auto.
	panel.size_buttons["custom"].pressed.emit()
	panel.size_box.set_dims(Vector3(1.2, 0.9, 0.6))
	var boxed := panel._body()
	expect(panel.size_box.visible and boxed.get("dims", []) == [1.2, 0.9, 0.6] and boxed.get("size") == "auto", "the dragged box is sent as dims")
	await create_timer(0.6).timeout
	await capture("size-box")
	panel.style_buttons["anime"].pressed.emit()
	panel.size_buttons["large"].pressed.emit()
	expect(panel.style_id == "anime" and panel.size_id == "large" and panel.style_buttons["anime"].button_pressed and not panel.style_buttons["rpg"].button_pressed, "picking a style and a size")
	studio.prompt.text = "tiny round stool"
	await studio.generate()
	expect(not studio.job_id.is_empty(), "room craft request accepted")
	job = await wait_state(panel, ["awaiting_confirmation"])
	expect(not job.get("concept", {}).is_empty(), "room craft shows the concept picture too")
	expect(str(job.get("provenance", {}).get("style")) == "anime" and float(job.get("provenance", {}).get("size_m", 0)) == 1.8, "the craft carries the chosen style and size")
	expect(labels(panel.status).contains("애니메이션"), "the quote names the style")
	await capture("room-concept")
	await studio.confirm_job()
	job = await wait_state(panel, ["ready", "failed"], 40.0)
	expect(str(job.get("state")) == "ready" and labels(panel.status).contains(tr("여기에 놓기")), "room craft finished with a place-here button")
	await create_timer(0.8).timeout
	await studio.place_crafted(str(job.get("object_id", "")))
	expect(studio.placement_mode and str(studio.selected.get("id", "")) == str(job.get("object_id", "")), "place-here starts placing the new object")
	var built: Vector3 = studio.inspected.get_meta("size", Vector3.ZERO) if is_instance_valid(studio.inspected) else Vector3.ZERO
	expect(absf(maxf(built.x, maxf(built.y, built.z)) - 1.8) < 0.03, "the object is 1.8 m on its longest side (%s)" % built)
	await capture("room-place")
	# Putting it down keeps the ghost as the placed piece (no reload, no blink) and plays the arrival.
	var crafted := str(job.get("object_id", ""))
	var ghost: Node3D = studio.ghost
	for spot in [Vector3(-2.5, 0, -2.5), Vector3(2.5, 0, -2.5), Vector3(-2.5, 0, 0.5), Vector3(2.5, 0, 0.5), Vector3(0, 0, -2.5)]:
		if studio.placement_problem(spot).is_empty():
			studio.place_at = spot
			break
	var fetched := Assembly.downloads
	var effects := Fx.played
	await studio.commit_place()
	await capture("room-placed")
	expect(is_instance_valid(ghost) and studio.placed.get(crafted) == ghost and ghost.get_parent() == studio.furniture and not studio.placement_mode, "the ghost becomes the placed piece")
	expect(Assembly.downloads == fetched and Fx.played > effects, "placing downloads nothing again and plays the arrival effect")
	expect(not str(studio.status_label.text).contains("꾸민 모습"), "refreshes no longer claim something was saved")
	print("CRAFT_PANEL " + ("FAILED" if failed else "OK"))
	studio.queue_free()
	await process_frame
	quit(1 if failed else 0)
