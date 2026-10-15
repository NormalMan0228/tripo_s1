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
	for word in ["하나", "둘", "셋", "넷"]: RpgUi.toast(lane, word)
	await process_frame
	expect(texts(lane) == ["둘", "셋", "넷"], "four pushes show three, the oldest left: %s" % [texts(lane)])
	var first: Control = RpgUi.find_toast(lane, "셋")
	var timer: Tween = first.get_meta("timer")
	var again := RpgUi.toast(lane, "셋")
	expect(again == first and texts(lane) == ["둘", "셋", "넷"] and first.get_meta("timer") != timer and not timer.is_valid(), "the same text refreshes its toast instead of stacking")
	var kinds := []
	for kind in ["success", "warn", "error", "social"]:
		var item := RpgUi.toast(lane, kind, kind)
		kinds.append(item.find_child("Kind", true, false) != null and item.get_meta("kind") == kind)
	expect(not false in kinds and RpgUi.toasts(lane).size() == 3, "kinds carry their icon; still three on the lane")
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
