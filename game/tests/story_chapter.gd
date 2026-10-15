extends SceneTree
## The opening story chapter "마을의 첫 선물" end to end on the QA server (demo mode crafts with the
## offline fixtures, no paid generation), the way a new player meets it:
##   a new account starts at home -> the welcome letter glows on the desk, E reads it -> the
##   village guides to this island's signpost and across to the café -> a resident greets the
##   newcomer once -> 모카 waits on the terrace, asks for a chair -> the craft window makes "나무
##   의자" -> 모카 offers to take it -> it stands on the café terrace at the slot, a passer-by sits
##   on it, the ribbon shows -> 모카's reply letter (with a present) is read at the mailbox and
##   the goal is done;
## then a second account signs in again in the middle of the chapter (the home and the village
## pick it up where it was) and gives a lamp (decoration: nobody sits); and the operator reset
## (python -m server.admin_cli story reset) puts the first account back at the letter.
## --capture saves artifacts/story-shot-*.png at each step (a window; tools/test.ps1 -Capture).
const Transition = preload("res://scripts/transition.gd")
const Town = preload("res://scripts/town.gd")
const Residents = preload("res://scripts/residents.gd")
const Guide = preload("res://scripts/guide.gd")
const NpcGifts = preload("res://scripts/npc_gifts.gd")
const Story = preload("res://scripts/story.gd")
const PASSWORD := "Story-chapter-pass-1"
var failed := false
var url := preload("res://tests/qa_server.gd").url()
var capture := "--capture" in OS.get_cmdline_user_args()
var shots := 0

func _initialize() -> void:
	call_deferred("run")
	create_timer(540).timeout.connect(func():
		push_error("Story chapter check exceeded 540 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func wait_for(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec()+int(seconds*1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return condition.call()

func shot(name: String, settle := 1.0) -> void:
	if not capture: return
	await create_timer(settle).timeout
	await RenderingServer.frame_post_draw
	shots += 1
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/story-shot-%02d-%s.png" % [shots, name]))

func village() -> Node:
	await wait_for(func() -> bool: return is_instance_valid(current_scene) and current_scene.get("screen") == "village" and Transition.instance != null and is_zero_approx(Transition.instance.veil.modulate.a), 90.0)
	return current_scene

func home() -> Node:
	await wait_for(func() -> bool: return is_instance_valid(current_scene) and current_scene.get("room") == "home" and is_instance_valid(current_scene.get("hero")) and Transition.instance != null and is_zero_approx(Transition.instance.veil.modulate.a), 90.0)
	return current_scene

func chapter(app: Node) -> Node:
	return app.chapter() if is_instance_valid(app) else null

func modal_text(app: Node) -> String:
	var text := ""
	if is_instance_valid(app.village_modal):
		for label in app.village_modal.find_children("*", "Label", true, false): text += (label as Label).text+"\n"
	return text

func choice_button(app: Node, label: String) -> Button:
	if not is_instance_valid(app.village_modal): return null
	for b in app.village_modal.find_children("*", "Button", true, false):
		if (b as Button).text.strip_edges() == label and (b as Button).is_visible_in_tree(): return b
	return null

## Reads the open dialogue on until a choice with this label shows, and presses it.
func press_choice(app: Node, label: String, seconds := 10.0) -> bool:
	var deadline := Time.get_ticks_msec()+int(seconds*1000)
	while Time.get_ticks_msec() < deadline:
		var button := choice_button(app, label)
		if button:
			button.pressed.emit()
			return true
		if is_instance_valid(app.village_modal) and app.village_modal.has_meta("advance"): app.village_modal.get_meta("advance").call()
		await create_timer(0.2).timeout
	return false

func teleport(app: Node, at: Vector2) -> void:
	app.player.position = Town.point(at, 0.3)
	app.player.velocity = Vector3.ZERO
	app.follow_camera(1.0)
	for i in 6: await physics_frame

func story_of(api: Node) -> Dictionary:
	var reply: Dictionary = await api.request("/v1/story")
	return reply.data.get("story", {}) if reply.ok and reply.data.get("story") is Dictionary else {}

func new_api(token := "") -> Node:
	var api: Node = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = url
	api.token = token
	return api

## The game's own sign-in path: a new session starts at home.
func start_at_home(token: String) -> Node:
	Engine.set_meta("studio_session", {"token":token, "url":url, "room":"home"})
	change_scene_to_file("res://scenes/studio.tscn")
	return await home()

func craft_by_api(api: Node, prompt: String) -> String:
	var queued: Dictionary = await api.post("/v1/studio/jobs", api.mutation({"prompt":prompt, "geometry":"proxy", "designer":"fixture"}))
	for i in 120:
		var job: Dictionary = await api.request("/v1/studio/jobs/"+str(queued.get("data", {}).get("id", "")))
		if job.ok and job.data.state == "awaiting_confirmation":
			await api.post("/v1/studio/jobs/%s/confirm" % job.data.id, api.mutation({"use_concept":false}))
		if job.ok and job.data.state == "ready": return str(job.data.object_id)
		await create_timer(0.5).timeout
	return ""

func run() -> void:
	preload("res://scripts/npc.gd").pinned = true  # the cast at their work spots whatever the clock
	var stamp := str(Time.get_ticks_msec()%1000000)
	var first := "maker_"+stamp
	var api := new_api()
	var signup: Dictionary = await api.post("/v1/auth/register", {"username":first, "password":PASSWORD})
	expect(signup.ok, "a new account")
	if not signup.ok:
		quit(1)
		return
	api.token = signup.data.token
	var begun := await story_of(api)
	expect(begun.get("step", "") == "letter" and begun.get("run", 0) == 1, "a new account starts the chapter at the letter")

	# 1. Home: the letter glows on the desk; E reads it.
	var room: Node = await start_at_home(signup.data.token)
	var at_home: Node = room.get("story_home")
	await wait_for(func() -> bool: return is_instance_valid(at_home) and is_instance_valid(at_home.letter), 15.0)
	expect(is_instance_valid(at_home) and is_instance_valid(at_home.letter) and at_home.glow.visible, "the welcome letter glows on the desk at home")
	expect(is_instance_valid(at_home.card) and at_home.card_lines.get_child_count() > 0, "the home's goal card says to read the letter")
	await shot("home-arrive", 1.6)
	room.hero.position = at_home.record.center+Vector3(-0.9, 0, 0)
	room.hero.face_point(at_home.record.center)
	room.update_hint()
	expect(room.controls_label.text == tr("편지 읽기"), "the key chip offers 편지 읽기 at the desk")
	room.interact_nearest()
	expect(is_instance_valid(at_home.reading) and room.talk_box == at_home.reading, "E opens the letter as a parchment card")
	var words := ""
	for label in at_home.reading.find_children("*", "Label", true, false): words += (label as Label).text
	expect(words.contains(tr("카페 주인이 새 의자를 기다리고 있대.")) and words.contains(tr("산책하다 들러서 인사해 보는 건 어때?")), "the letter tells about the café owner's chair")
	await shot("letter-open", 0.8)
	expect(await wait_for(func() -> bool: return at_home.state.get("step", "") == "cafe", 10.0), "reading marks the letter read on the server")
	room.advance_talk()
	await process_frame
	await process_frame
	expect(not is_instance_valid(at_home.reading) and not at_home.glow.visible, "E folds the letter away; it stops glowing")
	room.leave()

	# 2. Village: the goal and the route (this island's signpost first).
	var town: Node = await village()
	var story: Node = chapter(town)
	expect(story != null and story.step() == "cafe", "the village knows the chapter (go to the café)")
	await wait_for(func() -> bool: return town.objective.text.contains(tr("카페 '빨간 지붕'에 인사하러 가기")), 10.0)
	expect(town.objective.text.contains(tr("카페 '빨간 지붕'에 인사하러 가기")), "the tracker says: go say hello at the café")
	var guide: Node = Guide.current
	await wait_for(func() -> bool: return is_instance_valid(guide) and guide.active(), 10.0)
	var sign_square: Dictionary = story.signpost("square")
	await wait_for(func() -> bool:
		var post: Dictionary = story.signpost("square")
		return not post.is_empty() and guide.active() and Vector2(guide.target.at).distance_to(post.at) < 0.5, 10.0)
	sign_square = story.signpost("square")
	if sign_square.is_empty() or not guide.active():
		var field: Node = story.field_module()
		print("DEBUG field=", field, " objects=", field.objects.size() if field else -1, " guide=", guide.target if is_instance_valid(guide) else {}, " walker=", story.walker_at())
	expect(is_instance_valid(guide) and guide.active() and str(guide.target.key) == "story_cafe" and Vector2(guide.target.at).distance_to(sign_square.get("at", Vector2.INF)) < 0.5,
		"the guide leads to this island's signpost on the way to the café")
	expect(Residents.held.has("regular"), "모카 is held for the chapter (her walker and the café interior agree)")
	await shot("guide", 1.6)

	# 3. A resident greets the newcomer once (Naru, the cast guide at the camp).
	var naru: Node3D
	for npc in town.npcs:
		if str(npc.get_meta("cast", "")) == "naru": naru = npc
	await teleport(town, Vector2(naru.position.x, naru.position.z)+Vector2(0, 2.6))
	expect(await wait_for(func() -> bool: return "naru" in story.story.get("greeted", []), 8.0), "Naru greets the newcomer (kept on the server)")
	expect(town.ui.find_children("StoryBubble*", "PanelContainer", true, false).size() > 0, "the greeting shows as a speech bubble")
	await shot("greeting", 0.5)
	await create_timer(3.5).timeout
	expect(story.greeted_here.count("naru") == 1, "Naru greets only once")

	# 4. Across the islands: at the signpost its travel choices open with the café's island first.
	if sign_square.is_empty():
		quit(1)
		return
	await teleport(town, sign_square.at+Vector2(1.6, 1.2))
	expect(await wait_for(func() -> bool: return choice_button(town, tr("%s(으)로 가기") % tr("풍차 들판")) != null or is_instance_valid(town.village_modal), 8.0), "arriving at the signpost opens its travel choices")
	await press_choice(town, tr("%s(으)로 가기") % tr("풍차 들판"))
	expect(await wait_for(func() -> bool: return Story.island_of(story.walker_at()) == "fields" and is_zero_approx(Transition.instance.veil.modulate.a), 15.0), "the signpost takes the walker to the café's island")
	expect(await wait_for(func() -> bool: return guide.active() and Vector2(guide.target.at).distance_to(Story.MOKA_AT) < 2.0, 6.0), "the guide goes on to 모카 at the café")

	# 5. 모카 waits on the terrace; her words open when the walker arrives.
	await teleport(town, Story.MOKA_AT+Vector2(4.5, 1.6))
	expect(await wait_for(func() -> bool: return is_instance_valid(story.moka), 5.0), "모카 stands on the café terrace")
	await teleport(town, Story.MOKA_AT+Vector2(1.5, 0.3))
	expect(await wait_for(func() -> bool: return modal_text(town).contains(tr("모카")) or modal_text(town).contains(tr("카페")), 8.0), "모카 speaks by herself when the walker arrives")
	# On to her request (the chair) for the picture.
	for i in 24:
		if modal_text(town).contains(tr("부탁이 하나 있어. 산책하다 쉬어 갈 손님을 위해 의자 하나가 필요해.")): break
		if is_instance_valid(town.village_modal) and town.village_modal.has_meta("advance"): town.village_modal.get_meta("advance").call()
		await create_timer(0.5).timeout
	await shot("request", 2.2)
	expect(await press_choice(town, tr("지금 바로 만들기 · C")), "모카 asks for a chair: '지금 바로 만들기 · C'")
	expect(await wait_for(func() -> bool: return story.step() == "craft" and is_instance_valid(town.craft_window), 8.0), "the request is accepted and the craft window opens")

	# 6. The ordinary craft window makes the chair (demo mode: the offline chair).
	await wait_for(func() -> bool: return not town.craft_box.style_buttons.is_empty(), 10.0)
	# A moving piece is built from the design's parts (seat, legs, back): the offline chair looks
	# like a chair (a static one is a single proxy box until Tripo makes the real mesh).
	town.craft_box.motion.select(1)
	town.craft_box._update_options()
	town.craft_box.prompt.text = "카페 테라스에 둘 나무 의자"
	await shot("craft-window", 0.6)
	await town.request_craft("카페 테라스에 둘 나무 의자")
	var tracker: Node = town.craft_tracker()
	expect(not str(tracker.job_id).is_empty(), "the craft was accepted")
	await wait_for(func() -> bool: return town.objective.text.contains(tr("제작 중 · 완성되면 모카에게 가져가기")), 6.0)
	expect(town.objective.text.contains(tr("제작 중 · 완성되면 모카에게 가져가기")), "the tracker says what happens while it is made")
	await wait_for(func() -> bool: return str(tracker.job.get("state", "")) == "awaiting_confirmation" or not tracker.done.is_empty(), 40.0)
	if str(tracker.job.get("state", "")) == "awaiting_confirmation": await town.confirm_craft()
	expect(await wait_for(func() -> bool: return not tracker.done.is_empty(), 60.0), "the chair is finished")
	var chair_id := str(tracker.done.get("object_id", ""))
	town.close_village_modal()
	await town.refresh_inventory()
	await wait_for(func() -> bool: return town.objective.text.contains(tr("완성! 모카에게 가져가기")), 6.0)
	expect(town.objective.text.contains(tr("완성! 모카에게 가져가기")), "the tracker says: bring it to 모카")
	var chair_name := ""
	for obj in town.me.objects:
		if str(obj.id) == chair_id: chair_name = str(obj.name)

	# 7. 모카 takes it: on the terrace at once, a passer-by sits, the ribbon shows.
	await teleport(town, Story.MOKA_AT+Vector2(5.0, 1.6))
	await teleport(town, Story.MOKA_AT+Vector2(1.5, 0.3))
	expect(await press_choice(town, tr("%s 건네기") % chair_name, 12.0), "모카 offers to take the chair just made")
	expect(await wait_for(func() -> bool: return is_instance_valid(story.piece), 15.0), "the chair appears on the terrace at once")
	if is_instance_valid(story.piece):
		expect(Vector2(story.piece.global_position.x, story.piece.global_position.z).distance_to(Story.TERRACE) < 0.3, "the chair stands at the terrace slot")
	expect(story.piece_seat, "the chair is a seat")
	expect(await press_choice(town, tr("다행이에요"), 10.0), "모카 is delighted")
	expect(await wait_for(func() -> bool: return story.guest_seated and is_instance_valid(story.guest), 20.0), "a passer-by walks over and sits on it")
	if is_instance_valid(story.guest) and is_instance_valid(story.piece):
		expect(story.guest.pose == "sit" and Vector2(story.guest.global_position.x-story.piece.global_position.x, story.guest.global_position.z-story.piece.global_position.z).length() < 0.4, "the guest sits on the chair")
	await shot("terrace-guest", 0.3)
	expect(await wait_for(func() -> bool: return is_instance_valid(story.banner_node), 6.0), "the chapter's ribbon shows")
	await shot("terrace", 1.0)
	var done := await story_of(town.api)
	expect(done.get("step", "") == "done" and done.get("gift", {}).get("id", "") == chair_id and done.get("gift", {}).get("sittable", false), "the server has the chapter done with the chair")
	await wait_for(func() -> bool: return town.objective.text.contains(tr("우편함에서 모카의 편지 읽기")), 6.0)
	expect(town.objective.text.contains(tr("마을의 첫 선물 · 완료")) and town.objective.text.contains(tr("우편함에서 모카의 편지 읽기")), "the tracker shows the chapter done and the letter waiting")

	# 8. 모카's reply letter (with a present) at the mailbox; then the goal is gone.
	var mail: Dictionary = await town.api.request("/v1/letters")
	var reply_letter: Dictionary = mail.data.letters[0] if mail.ok and not mail.data.letters.is_empty() else {}
	expect(reply_letter.get("npc", "") == "regular" and reply_letter.get("story") is Dictionary and reply_letter.get("gift") is Dictionary, "모카's thank-you letter came with a present")
	var field: Node = story.field_module()
	var box: Dictionary = story.field_entry("mailbox")
	await teleport(town, Vector2(box.at)+Vector2(0, 1.4))
	field.use_mailbox(box)
	expect(await wait_for(func() -> bool: return modal_text(town).contains(tr("마을의 첫 선물")), 8.0), "the mailbox reads 모카's letter out")
	await shot("reply-letter", 3.0)
	town.close_village_modal()
	await wait_for(func() -> bool: return bool(story.story.get("letter", {}).get("read", false)), 12.0)
	await create_timer(0.3).timeout
	expect(not town.objective.text.contains(tr("마을의 첫 선물")), "with the letter read the chapter leaves the tracker")
	var bag := false
	var chair_kept := false
	for obj in (await town.api.request("/v1/me")).data.objects:
		if reply_letter.get("gift") is Dictionary and str(obj.id) == str(reply_letter.gift.id): bag = true
		if str(obj.id) == chair_id: chair_kept = true
	expect(bag and not chair_kept, "the present is in the bag; the chair left it")

	# 9. A second maker signs in again in the middle of the chapter and gives a lamp.
	var second := "lamper_"+stamp
	var other := new_api()
	var made: Dictionary = await other.post("/v1/auth/register", {"username":second, "password":PASSWORD})
	other.token = str(made.get("data", {}).get("token", ""))
	await other.post("/v1/story/step", other.mutation({"action":"read_letter"}))
	await other.post("/v1/story/step", other.mutation({"action":"accept"}))
	await town.logout()
	await create_timer(0.5).timeout
	town.authenticate(false, url, second, PASSWORD, "")
	room = await home()
	await wait_for(func() -> bool: return is_instance_valid(room.get("story_home")) and is_instance_valid(room.story_home.card), 15.0)
	var lines := ""
	if is_instance_valid(room.get("story_home")):
		for label in room.story_home.card_lines.find_children("*", "Label", true, false): lines += (label as Label).text
	expect(lines.contains(tr("C · 모카의 의자 만들기")), "signing in again, the home card picks the chapter up (make the chair)")
	room.leave()
	town = await village()
	story = chapter(town)
	await wait_for(func() -> bool: return town.objective.text.contains(tr("C · 모카의 의자 만들기")), 10.0)
	expect(town.objective.text.contains(tr("C · 모카의 의자 만들기")), "the village tracker picks it up too")
	var lamp_id := await craft_by_api(other, "등불")
	expect(not lamp_id.is_empty(), "a lamp was made")
	await town.refresh_inventory()
	await wait_for(func() -> bool: return town.objective.text.contains(tr("완성! 모카에게 가져가기")), 6.0)
	await teleport(town, Story.MOKA_AT+Vector2(4.5, 1.6))
	await wait_for(func() -> bool: return is_instance_valid(story.moka), 5.0)
	var lamp: Dictionary = {}
	for obj in town.me.objects:
		if str(obj.id) == lamp_id: lamp = obj
	town.close_village_modal()
	await story.give(lamp)
	expect(await wait_for(func() -> bool: return is_instance_valid(story.piece) and str(story.piece_item.get("id", "")) == lamp_id, 15.0), "the lamp stands on the terrace")
	expect(not story.piece_seat, "a lamp is decoration, not a seat")
	expect(await press_choice(town, tr("다행이에요"), 10.0), "모카 likes it anyway")
	await wait_for(func() -> bool: return is_instance_valid(story.banner_node), 8.0)
	expect(is_instance_valid(story.banner_node) and not is_instance_valid(story.guest), "the ribbon shows and nobody sits on a lamp")
	await shot("terrace-lamp", 1.0)

	# 10. The operator reset puts the first maker back at the letter (rehearsals).
	var data_dir := OS.get_environment("TRIPOTHON_DATA_DIR")
	if data_dir.is_empty():
		print("SKIP reset: no TRIPOTHON_DATA_DIR (run through tools/test.ps1)")
	else:
		var repo := ProjectSettings.globalize_path("res://..").simplify_path()
		var output: Array = []
		# The operator's command, run from the repository (python -m needs the server package on the path).
		OS.set_environment("PYTHONPATH", repo)
		var code := OS.execute(repo.path_join(".tools/server-venv/Scripts/python.exe"), ["-m", "server.admin_cli", "story", "reset", first, "--data-dir", data_dir], output, true)
		print("RESET ", code, " ", "".join(output).strip_edges())
		expect(code == 0, "python -m server.admin_cli story reset ran")
		# The game signed out of that session; the checks sign in again.
		var relog: Dictionary = await api.post("/v1/auth/login", {"username":first, "password":PASSWORD})
		api.token = str(relog.get("data", {}).get("token", ""))
		var again := await story_of(api)
		expect(again.get("step", "") == "letter" and again.get("run", 0) == 2, "the first maker is back at the letter (second run)")
		var terrace: Dictionary = await api.request("/v1/social/npc-homes/cafe_terrace")
		expect(terrace.ok and terrace.get("data", {}).get("items", [1]).is_empty(), "the terrace is empty again")
		var back := false
		var mine: Dictionary = await api.request("/v1/me")
		for obj in mine.get("data", {}).get("objects", []):
			if str(obj.id) == chair_id: back = str(obj.state) == "inventory"
		expect(back, "the chair went back to the bag, nothing was deleted")
	await town.logout()
	print("STORY_CHAPTER " + ("FAILED" if failed else "OK"))
	quit(1 if failed else 0)
