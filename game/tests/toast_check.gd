extends SceneTree
## The shared toast lane (U-WP-08, RpgUi.toast_lane / toast): four pushes show three and the
## oldest leaves; the same text refreshes the toast on screen instead of stacking; action toasts
## stay 12 s and their buttons run and dismiss; the village, the field and a room all toast through
## the lane (main.message, studio.message), the field silently; the craft window's notes use a
## lane of their own. Headless:
##   godot --headless --path game --script res://tests/toast_check.gd -- --qa
const Main = preload("res://scripts/main.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const I18n = preload("res://scripts/i18n.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
var failures := 0
var checks := 0

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("Toast check exceeded 240 seconds")
		quit(2))

func expect(ok: bool, what: String) -> void:
	checks += 1
	print(("PASS " if ok else "FAIL ") + what)
	if not ok: failures += 1

func settle(seconds := 0.3) -> void:
	await create_timer(seconds).timeout

func texts(lane: Control) -> Array:
	return RpgUi.toasts(lane).map(func(t): return str(t.get_meta("toast")))

func run() -> void:
	I18n.setup()
	await lane_rules()
	await places()
	print("TOAST_CHECK ", JSON.stringify({"checks":checks, "failures":failures}))
	quit(1 if failures else 0)

func lane_rules() -> void:
	var host := Control.new()
	host.size = Vector2(1280, 800)
	root.add_child(host)
	var lane := RpgUi.toast_lane(host)
	expect(lane.offset_top == 94.0 and lane.alignment == BoxContainer.ALIGNMENT_BEGIN, "the lane sits at y 94, top centre")
	RpgUi.toast(lane, "하나")
	await settle(0.35)
	for word in ["둘", "셋", "넷"]: RpgUi.toast(lane, word)
	await process_frame
	expect(texts(lane) == ["둘", "셋", "넷"], "four pushes show three, the oldest left: %s" % [texts(lane)])
	var evicted: Control = lane.get_child(0)
	expect(lane.get_child_count() == 4 and str(evicted.get_meta("toast")) == "하나" and evicted.get_meta("leaving", false),
		"the evicted toast keeps its slot while it fades (no jump in the stack)")
	await settle(0.08)
	var fading := evicted.modulate.a
	expect(is_instance_valid(evicted) and fading < 1.0 and fading > 0.0, "it fades rather than vanishing (alpha %.2f)" % fading)
	await settle(0.45)
	expect(not is_instance_valid(evicted) and lane.get_child_count() == 3, "then its slot closes and it is freed (%d left)" % lane.get_child_count())
	var first: Control = RpgUi.find_toast(lane, "셋")
	var timer: Tween = first.get_meta("timer")
	var again := RpgUi.toast(lane, "셋")
	expect(again == first and texts(lane) == ["둘", "셋", "넷"] and first.get_meta("timer") != timer and not timer.is_valid(), "the same text refreshes its toast instead of stacking")
	# Said again and again (a refresh loop): after the first 2 s it no longer keeps the toast up.
	first.set_meta("born", Time.get_ticks_msec() * 0.001 - RpgUi.TOAST_REFRESH_WINDOW - 0.5)
	var held: Tween = first.get_meta("timer")
	RpgUi.toast(lane, "셋")
	expect(first.get_meta("timer") == held and held.is_valid(), "a repeat after its first 2 s does not keep the toast up (it leaves on time)")
	var kinds := []
	for kind in ["success", "warn", "error", "social"]:
		var item := RpgUi.toast(lane, kind, kind)
		kinds.append(item.find_child("Kind", true, false) != null and item.get_meta("kind") == kind)
	expect(not false in kinds and RpgUi.toasts(lane).size() == 3, "kinds carry their icon; still three on the lane")
	var glyph := func(kind: String) -> String:
		var item := RpgUi.toast(lane, "glyph " + kind, kind)
		return (item.find_child("Kind", true, false) as TextureRect).texture.resource_path
	var close_art := RpgUi.icon_texture("close").resource_path
	var info_art: String = glyph.call("info")
	var warn_art: String = glyph.call("warn")
	var error_art: String = glyph.call("error")
	expect(error_art != close_art and warn_art != info_art and error_art != warn_art and error_art.ends_with("alert.png") and warn_art.ends_with("warn.png"),
		"error and warn have their own painted glyphs, not the close key or the info glint (%s, %s)" % [error_art.get_file(), warn_art.get_file()])
	expect((RpgUi.find_toast(lane, "glyph warn").find_child("Kind", true, false) as CanvasItem).modulate == Color.WHITE, "the warn glyph is not a tinted info glint")
	var ran := [0]
	var card := RpgUi.toast(lane, "초대가 왔어요", "social", {"actions":[{"label":"수락", "call":func(): ran[0] += 1}]})
	var accept: Button = card.find_children("*", "Button", true, false)[0]
	expect(is_equal_approx(float(card.get_meta("life")), 12.0) and card.mouse_filter == Control.MOUSE_FILTER_STOP and accept.text == "수락", "an action toast stays 12 s and takes clicks")
	accept.pressed.emit()
	await process_frame
	expect(ran[0] == 1 and not card in RpgUi.toasts(lane), "its button runs and dismisses it")
	var quick := RpgUi.toast(lane, "곧 사라져요", "info", {"seconds":0.3})
	await settle(0.9)
	expect(not is_instance_valid(quick) or quick.is_queued_for_deletion() or not quick in RpgUi.toasts(lane), "a toast leaves when its time is up")
	RpgUi.clear_toasts(lane)
	expect(RpgUi.toasts(lane).is_empty(), "clear_toasts empties the lane")
	var fixed := RpgUi.toast_lane(host, 94, 520)
	var wide := RpgUi.toast(fixed, "짧아요")
	expect(wide.custom_minimum_size.x == 520.0, "a fixed-width lane gives 520 px pills")
	var low := RpgUi.toast_lane(host, 520, 520)
	expect(low.alignment == BoxContainer.ALIGNMENT_END and is_equal_approx(low.offset_bottom, -(800.0 - 520.0 - 44.0)), "a lower lane stacks upward from its spot")
	var up := RpgUi.toast_lane(host, 82, 0, 680, {"grow":"up", "max":2})
	for word in ["하나", "둘", "셋"]: RpgUi.toast(up, word)
	await process_frame
	expect(up.alignment == BoxContainer.ALIGNMENT_END and up.anchor_bottom == 0.0 and up.offset_bottom == 82.0 and texts(up) == ["둘", "셋"],
		"grow up: the lane's foot is pinned at y 82 and opts.max keeps two (%s)" % [texts(up)])
	host.free()

func places() -> void:
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	var app = Main.new()
	root.add_child(app)
	await settle(1.6)
	app.api.queue_free()
	var stub := Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = false
	await app.enter_village()
	await settle(0.8)
	var lane: Control = app.toast_lane
	expect(is_instance_valid(lane) and lane.get_parent() == app.ui and lane.offset_top == 94.0, "the village HUD has the toast lane at y 94")
	var chimes: int = RpgUi.toast_chimes
	app.message("마을 소식")
	app.message("마을 소식")
	expect(texts(lane).count("마을 소식") == 1 and app.notice.text == "마을 소식" and app.last_notice == "마을 소식", "main.message toasts once and keeps the line in notice")
	expect(RpgUi.toast_chimes == chimes + 1, "the village toast chimes once")
	expect(RpgUi.find_toast(lane, "마을 소식").custom_minimum_size.x == 520.0, "village toasts keep their 520 px pill")
	await app.open_craft()
	await settle(0.4)
	var window = app.craft_window
	var notes: Control = window.note_lane if is_instance_valid(window) else null
	if is_instance_valid(window): window.note("그림이 준비됐어요")
	expect(is_instance_valid(notes) and texts(notes) == ["그림이 준비됐어요"] and notes.get_parent() == window, "the craft window's notes use their own lane over the card")
	if is_instance_valid(window):
		# Notes within the stay never reach the card: two short ones stack up from just above it,
		# and one that wraps takes the room of two (the older leaves).
		var card_top: float = (window.card as Control).get_global_rect().position.y
		var rects := func() -> Array:
			return notes.get_children().map(func(n): return (n as Control).get_global_rect())
		var shown := func() -> Array:
			return notes.get_children().map(func(n): return "%s %s" % [str(n.get_meta("toast", "")).left(6), n.size])
		window.note("제작을 받았어요")
		await settle(0.5)
		var two: Array = rects.call()
		expect(two.size() == 2 and RpgUi.toasts(notes).size() == 2 and two.all(func(r): return r.end.y <= card_top - window.NOTE_GAP + 0.5 and r.position.y >= 0.0)
			and two[1].end.y > two[0].end.y, "two notes stack upward, the newest nearest the card, all above it (card top %.0f, %s)" % [card_top, shown.call()])
		window.note("공방이 너무 오래 걸려 이번 제작을 멈췄어요. 맡긴 별씨는 돌려드렸어요. 조금 뒤에 다른 설명으로 다시 맡겨 주시면 공방이 다시 그려 볼게요.")
		await settle(0.5)
		var after: Array = rects.call()
		expect(after.size() == 1 and RpgUi.toasts(notes).size() == 1 and after[0].size.y > 45.0 and after[0].end.y <= card_top - window.NOTE_GAP + 0.5 and after[0].position.y >= 0.0,
			"a note that wraps takes the room of two: the older leaves and it ends above the card (%s)" % [shown.call()])
	app.close_craft()
	await settle(0.3)
	await app.start_run("forest", "standard")
	await settle(1.2)
	var field: Control = app.toast_lane
	chimes = RpgUi.toast_chimes
	app.message("해가 졌어요")
	expect(is_instance_valid(field) and field != lane and texts(field).has("해가 졌어요"), "the field toasts on its own lane")
	expect(RpgUi.toast_chimes == chimes, "field toasts are silent")
	app.queue_free()
	await settle(0.5)
	Engine.set_meta("studio_session", {"token":"", "url":"http://gallery.invalid", "room":"01_cafe"})
	var studio: Node = load("res://scenes/studio.tscn").instantiate()
	root.add_child(studio)
	await settle(2.5)
	studio.message("가구를 놓았어요")
	var room_lane: Control = studio.toast_lane
	expect(is_instance_valid(room_lane) and texts(room_lane).has("가구를 놓았어요") and studio.status_label.text == "가구를 놓았어요", "studio.message toasts on the room's lane and keeps status_label")
	studio.message("조용히", false)
	expect(RpgUi.toasts(room_lane).is_empty() and studio.status_label.text == "조용히", "a quiet message clears the lane")
	studio.queue_free()
	Engine.remove_meta("studio_session")
	await settle(0.5)
