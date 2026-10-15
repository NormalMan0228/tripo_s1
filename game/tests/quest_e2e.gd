extends SceneTree
## Residents' requests in the village, end to end on the QA server, the way a player meets them:
##   while the opening chapter runs nobody asks; once it is over and 모카's letter is read the
##   village says so and "!" stands over the residents with a request;
##   소라 (the cast tailor): "✦ 부탁 들어주기" -> "맡겨 줘요 · 별씨 +3" -> the tracker shows the goal
##   and its reward -> "부탁 이야기" -> "옷장 열기" -> a new look saved -> "다 됐어요!" and "?" over
##   her -> "✦ 부탁을 마쳤어요" -> her thanks, stars burst and fly into the counter, which goes up
##   by 3 exactly once (and stays there through the village's polls);
##   해루 (the angler): taken at the pier, a sea fish caught while the walker is on another island
##   -> the tracker says to bring it and the guide leads back (this island's signpost first) ->
##   handed over: the fish leaves the bag, the counter goes up by 5;
##   the tracker's book line opens the request book with every request.
## --capture saves artifacts/quest-shot-*.png (offer, tracker, reward) for the sheet.
const Main = preload("res://scripts/main.gd")
const Quests = preload("res://scripts/quests.gd")
const Town = preload("res://scripts/town.gd")
const Guide = preload("res://scripts/guide.gd")
const PASSWORD := "Quest-e2e-pass-1"
var failed := false
var capture := "--capture" in OS.get_cmdline_user_args()
var shots := 0
var app: Node

func _initialize() -> void:
	call_deferred("run")
	create_timer(420).timeout.connect(func():
		push_error("Quest e2e exceeded 420 seconds")
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

func shot(name: String, settle := 0.6) -> void:
	if not capture: return
	await create_timer(settle).timeout
	await RenderingServer.frame_post_draw
	shots += 1
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/quest-shot-%02d-%s.png" % [shots, name]))

func modal_text() -> String:
	var text := ""
	if is_instance_valid(app.village_modal):
		for label in app.village_modal.find_children("*", "Label", true, false): text += (label as Label).text+"\n"
	return text

func choices() -> Array:
	var out: Array = []
	if not is_instance_valid(app.village_modal): return out
	for b in app.village_modal.find_children("*", "Button", true, false):
		if (b as Button).is_visible_in_tree(): out.append((b as Button).text.strip_edges())
	return out

## Reads the open dialogue on until a choice with this label shows, and presses it.
func press(label: String, seconds := 10.0) -> bool:
	var deadline := Time.get_ticks_msec()+int(seconds*1000)
	while Time.get_ticks_msec() < deadline:
		if is_instance_valid(app.village_modal):
			for b in app.village_modal.find_children("*", "Button", true, false):
				if (b as Button).text.strip_edges() == label and (b as Button).is_visible_in_tree():
					(b as Button).pressed.emit()
					return true
			if app.village_modal.has_meta("advance"): app.village_modal.get_meta("advance").call()
		await create_timer(0.2).timeout
	print("  choices: ", choices())
	return false

## The first choice once the dialogue's last page shows.
func first_choice(seconds := 8.0) -> String:
	var deadline := Time.get_ticks_msec()+int(seconds*1000)
	while Time.get_ticks_msec() < deadline:
		var shown := choices()
		if not shown.is_empty(): return str(shown[0])
		if is_instance_valid(app.village_modal) and app.village_modal.has_meta("advance"): app.village_modal.get_meta("advance").call()
		await create_timer(0.2).timeout
	return ""

func teleport(at: Vector2) -> void:
	app.player.position = Town.point(at, 0.3)
	app.player.velocity = Vector3.ZERO
	app.follow_camera(1.0)
	for i in 6: await physics_frame

func cast(id: String) -> Node3D:
	for npc in app.npcs:
		if is_instance_valid(npc) and str(npc.get_meta("cast", "")) == id: return npc
	return null

func talk(id: String) -> void:
	var npc := cast(id)
	await teleport(Vector2(npc.position.x, npc.position.z)+Vector2(0, 1.6))
	app.close_village_modal()
	app.talk_to(npc)

func mark_of(id: String) -> String:
	var npc := cast(id)
	var label := npc.get_node_or_null("QuestMark") as Label3D if npc else null
	return label.text if label else ""

func counter() -> int:
	return int(app.frame.stars.text)

func quests_module() -> Node:
	return Quests.village_of(app)

func act(action: String, extra := {}) -> Dictionary:
	var state: Dictionary = (await app.api.request("/v1/homestead")).data
	var reply: Dictionary = await app.api.post("/v1/homestead", app.api.mutation(extra.merged({"action":action, "version":int(state.get("version", 0))})))
	return reply.data if reply.ok else {}

func sea_fish() -> int:
	var bag: Dictionary = (await app.api.request("/v1/homestead")).data.get("bag", {})
	return int(bag.get("mackerel", 0))+int(bag.get("puffer", 0))+int(bag.get("squid", 0))+int(bag.get("tuna", 0))+int(bag.get("silverfish", 0))

func run() -> void:
	preload("res://scripts/npc.gd").pinned = true  # the cast at their work spots whatever the clock
	app = Main.new()
	root.add_child(app)
	await create_timer(1.0).timeout
	var name := "asked_"+str(Time.get_ticks_msec()%1000000)
	await app.authenticate(true, preload("res://tests/qa_server.gd").url(), name, PASSWORD, "")
	expect(await wait_for(func() -> bool: return app.screen == "village" and quests_module() != null, 60.0), "the village with its requests module")
	var api: Node = app.api

	# 1. While the chapter runs nobody asks.
	await create_timer(1.0).timeout
	await talk("sora")
	var offered := await first_choice()
	expect(offered != "" and not offered.begins_with("✦ 부탁"), "while the chapter runs 소라 has no request (first choice: %s)" % offered)
	app.close_village_modal()
	expect(not app.objective.text.contains("부탁") and mark_of("sora").is_empty(), "no request on the tracker or over the residents")
	# The chapter, quickly (its own test walks it): the welcome chair on the terrace, the letter read.
	await api.post("/v1/story/step", api.mutation({"action":"read_letter"}))
	await api.post("/v1/story/step", api.mutation({"action":"accept"}))
	var chair: Dictionary = (await api.request("/v1/me")).data.objects.filter(func(o): return str(o.name) == "환영의 나무 의자")[0]
	var gift: Dictionary = await api.post("/v1/story/gift", api.mutation({"object_id":chair.id, "version":chair.version}))
	await api.post("/v1/letters/read", api.mutation({"ids":[gift.data.letters[0].id]}))
	await app.refresh_inventory()
	expect(await wait_for(func() -> bool: return app.notice.text.contains(app.tr("마을 주민들이 부탁을 기다리고 있어요")), 8.0), "the village says the residents have requests")
	expect(await wait_for(func() -> bool: return mark_of("sora") == "!" and mark_of("haeru") == "!", 4.0), "\"!\" over 소라 and 해루")
	expect(app.objective.text.contains(app.tr("✦ 주민들의 부탁 %d개 · 수첩 보기") % 19), "the tracker counts the requests (수첩 보기)")

	# 2. 소라: offered, taken, the tracker shows it.
	await talk("sora")
	expect(await first_choice() == app.tr("✦ 부탁 들어주기"), "소라's first choice is her request")
	expect(await press(app.tr("✦ 부탁 들어주기")), "the request opens")
	# Her request read through to its last page, where the choices are.
	expect((await first_choice()) == app.tr("다음에요"), "'다음에요' comes first")
	await shot("offer", 1.2)
	expect(await press(app.tr("맡겨 줘요 · 별씨 +%d") % 3), "taken: '맡겨 줘요 · 별씨 +3'")
	expect(await wait_for(func() -> bool: return app.objective.text.contains("▸ "+app.tr("옷장에서 새 차림 갈아입기")) and app.objective.text.contains(app.tr("소라의 새 옷 맞춤")+" · "+app.tr("별씨 +%d") % 3), 6.0), "the tracker: the goal, the request and its reward")
	expect(await wait_for(func() -> bool: return mark_of("sora").is_empty(), 3.0), "the \"!\" over 소라 is gone")
	app.close_village_modal()
	await shot("tracker", 1.2)
	# Her wardrobe from the reminder; a new look saved.
	await talk("sora")
	expect(await press(app.tr("부탁 이야기")), "부탁 이야기")
	expect(await press(app.tr("옷장 열기")), "옷장 열기 from the reminder")
	expect(await wait_for(func() -> bool: return is_instance_valid(app.village_modal) and app.village_modal.find_children("*", "HBoxContainer", true, false).any(func(n): return n.get_script() == preload("res://scripts/wardrobe.gd")), 5.0), "the wardrobe opens")
	var editor: Node = app.village_modal.find_children("*", "HBoxContainer", true, false).filter(func(n): return n.get_script() == preload("res://scripts/wardrobe.gd"))[0]
	editor.avatar.coat = "#4a7fb5"
	expect(await press(app.tr("이 모습으로 저장")), "the new look is saved")
	expect(await wait_for(func() -> bool: return app.notice.text.contains(app.tr("다 됐어요! %s에게 알려 주세요") % "소라"), 8.0), "'다 됐어요! 소라에게 알려 주세요'")
	expect(await wait_for(func() -> bool: return mark_of("sora") == "?", 3.0), "\"?\" over 소라")
	# The hand-over: the counter goes up by 3, once.
	var before := counter()
	var server_before := int((await api.request("/v1/me")).data.shards)
	expect(before == server_before, "the counter shows the server's starseeds (%d)" % before)
	await talk("sora")
	expect(await press(app.tr("✦ 부탁을 마쳤어요")), "'✦ 부탁을 마쳤어요'")
	expect(await wait_for(func() -> bool: return modal_text().contains(app.tr("정말 잘 어울려요! 섬 바람이랑 색이 딱 맞네요.")), 6.0), "소라 thanks")
	expect(await wait_for(func() -> bool: return app.ui.find_children("QuestStars", "", true, false).size() > 0, 3.0), "'+3' rises over her while she thanks")
	expect(counter() == before, "the counter waits for the thanks to close")
	# Closing the thanks brings the HUD back: the stars fly into the counter.
	expect(await press(app.tr("천만에요")), "'천만에요'")
	expect(await wait_for(func() -> bool: return app.ui.find_children("QuestStar", "", true, false).size() > 0, 3.0), "stars fly toward the counter")
	await shot("reward", 0.45)
	expect(await wait_for(func() -> bool: return counter() == before+3, 5.0), "the counter ticks up to %d" % (before+3))
	await create_timer(7.0).timeout
	expect(counter() == before+3 and int((await api.request("/v1/me")).data.shards) == before+3, "still +3 after the village's polls (paid once)")
	app.close_village_modal()
	await talk("sora")
	expect(not (await first_choice()).begins_with("✦"), "소라 has no request left")
	app.close_village_modal()

	# 3. 해루: taken at the pier, the fish caught away, the guide leads back, handed over.
	await talk("haeru")
	expect(await press(app.tr("✦ 부탁 들어주기")), "해루's request")
	expect(await press(app.tr("맡겨 줘요 · 별씨 +%d") % 5), "taken: '맡겨 줘요 · 별씨 +5'")
	# The server's yes comes back as 해루's answer; then the walk away.
	expect(await wait_for(func() -> bool: return modal_text().contains(app.tr("고마워요! 숯불은 제가 피워 둘게요.")), 6.0), "해루 answers")
	app.close_village_modal()
	var requests: Node = quests_module()
	await teleport(Vector2(-30, 38))
	for attempt in 5:
		if await sea_fish() >= 1: break
		var thrown := await act("cast", {"spot":"sea"})
		await create_timer(maxf(0.1, float(thrown.get("fishing", {}).get("bite_at", 0))-float(thrown.get("server_time", 0))+0.3)).timeout
		var hooked := await act("reel")
		if hooked.get("reward", {}).get("kind", "") != "hooked": continue
		await create_timer(float(hooked.get("fishing", {}).get("fight_min", 3.5))+0.4).timeout
		await act("reel", {"outcome":"landed"})
	expect(await sea_fish() == 1, "a sea fish is in the bag")
	await app.life.refresh()
	expect(await wait_for(func() -> bool: return app.objective.text.contains("▸ "+app.tr("다 모았어요! %s에게 가져가기") % "해루"), 6.0), "the tracker: bring it to 해루")
	var guide: Node = Guide.current
	expect(await wait_for(func() -> bool: return is_instance_valid(guide) and guide.active() and str(guide.target.get("key", "")) == Quests.KEY+"haeru_fish", 4.0), "the guide leads back to 해루")
	if is_instance_valid(guide) and guide.active():
		# field_objects.gd sometimes cannot place a signpost (no ground found while the island
		# loads; it lists it in `skipped`): then the way goes straight to 해루.
		var story_module: Node = app.chapter()
		var sign: Dictionary = story_module.signpost("square")
		if sign.is_empty():
			print("SKIP signpost hop: field_objects skipped ", story_module.field_module().skipped)
			expect(Vector2(guide.target.at).distance_to(requests.npc_goal("haeru", "").at) < 3.0, "without this island's signpost the way leads straight to 해루")
		else:
			var hopped := await wait_for(func() -> bool: return str(guide.target.get("name", "")).begins_with(app.tr("이정표 · %s(으)로") % app.tr("등대섬")), 3.0)
			expect(hopped, "from another island: this island's signpost first (%s)" % str(guide.target.get("name", "")))
	await shot("guide", 1.0)
	# The book from the tracker's last line.
	expect(requests.row(Quests.BOOK_KEY) and is_instance_valid(app.village_modal) and modal_text().contains(app.tr("부탁 수첩")), "the tracker's book line opens the request book")
	# Three pages (under way, new, finished): every request on exactly one of them.
	var tabs: Control = app.village_modal.find_child("QuestBookTabs", true, false)
	var pages := {}
	for page in ["open", "new", "done"]:
		preload("res://scripts/rpg_ui.gd").select_tab(tabs, page)
		await process_frame
		for row in app.village_modal.find_children("Quest_*", "HBoxContainer", true, false): pages[str(row.name)] = page
	expect(tabs != null and pages.size() == 19 and pages.get("Quest_haeru_fish") == "open" and pages.get("Quest_sora_outfit") == "done", "the book's pages hold all nineteen (해루's on 진행 중, 소라's on 완료: %s)" % [pages.size()])
	preload("res://scripts/rpg_ui.gd").select_tab(tabs, "open")
	await process_frame
	await shot("book", 0.8)
	app.close_village_modal()
	before = counter()
	await talk("haeru")
	expect(await press(app.tr("✦ 부탁한 것 건네기")), "'✦ 부탁한 것 건네기'")
	expect(await press(app.tr("천만에요")), "해루 thanks; '천만에요'")
	expect(await wait_for(func() -> bool: return counter() == before+5, 6.0), "the counter ticks up by 5")
	var local_bag: Dictionary = app.life.state.get("bag", {})
	var local_fish := 0
	for kind in ["mackerel", "puffer", "squid", "tuna", "silverfish"]: local_fish += int(local_bag.get(kind, 0))
	expect(await sea_fish() == 0 and local_fish == 0, "the fish left the bag (the village's bag too)")
	var listing: Dictionary = (await api.request("/v1/quests")).data.quests
	var done: Array = listing.list.filter(func(q): return str(q.state) == "done").map(func(q): return str(q.id))
	expect(done == ["sora_outfit", "haeru_fish"], "the server has the two done (%s)" % str(done))
	await create_timer(4.0).timeout
	expect(counter() == before+5, "still +5 after polls")
	app.close_village_modal()
	# 4. Signed in again: the requests were open all along, so no "residents are waiting" word;
	# the full list comes once (/v1/me carries the states only).
	await app.logout()
	await create_timer(1.0).timeout
	await app.authenticate(false, preload("res://tests/qa_server.gd").url(), name, PASSWORD, "")
	expect(await wait_for(func() -> bool: return app.screen == "village" and quests_module() != null, 60.0), "back in the village")
	var toast := app.tr("마을 주민들이 부탁을 기다리고 있어요")
	var toasted := false
	var deadline := Time.get_ticks_msec()+8000
	while Time.get_ticks_msec() < deadline:
		if is_instance_valid(app.notice) and app.notice.text.contains(toast): toasted = true
		await create_timer(0.2).timeout
	expect(not toasted, "a new login of an open account does not say the residents are waiting")
	expect(Quests.open_for(str(app.api.token)) and Quests.listed(str(app.api.token)).size() == 19 and str(Quests.by_id(str(app.api.token), "haeru_fish").get("state", "")) == "done", "the full list came with the new login")
	expect(await wait_for(func() -> bool: return mark_of("sora").is_empty() and app.objective.text.contains("부탁"), 6.0), "the tracker and the marks follow it")
	print("QUEST_E2E " + ("FAILED" if failed else "OK"))
	await app.logout()
	quit(1 if failed else 0)
