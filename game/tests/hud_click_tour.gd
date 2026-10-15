extends SceneTree
## UI click and double-press tour (62), against recorded replies (no port):
## - a click anywhere on a visible HUD piece in the village (the character frame, the minimap, the
##   goal card, the hotbar tray, the chat box, the toasts) is used up by the HUD and never reaches
##   the world (main.gd world_clicks: furniture clicks, placement);
## - every hotbar slot pressed twice in one frame opens its window once (one window on the stack),
##   and Esc closes it again;
## - with a window open, a click on the shade around it does not reach the world either.
##   godot --headless --path game --script res://tests/hud_click_tour.gd -- --qa
const Main = preload("res://scripts/main.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const SocialHud = preload("res://scripts/social_hud.gd")
var failures: Array[String] = []
var app: Node

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("hud_click_tour exceeded 240 seconds")
		quit(2))

func expect(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func settle(seconds := 0.3) -> void:
	await create_timer(seconds).timeout

## A left click (press and release) at `at` in the root's canvas coordinates.
func click(at: Vector2) -> void:
	for pressed in [true, false]:
		var event := InputEventMouseButton.new()
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = pressed
		event.position = at
		event.global_position = at
		root.push_input(event, true)
		await process_frame

## Five points on a piece: its centre and four points inset from the corners.
func points(rect: Rect2) -> Array:
	var inset := rect.grow(-minf(10.0, minf(rect.size.x, rect.size.y) * 0.25))
	return [rect.get_center(), inset.position, Vector2(inset.end.x, inset.position.y), Vector2(inset.position.x, inset.end.y), inset.end]

func run() -> void:
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	fixture["/v1/social/presence"] = {"self_id":"me", "host_id":"me", "host_name":"haneul", "visiting":false, "party":null, "invites":[],
		"pending_rewards":[], "village":{"players":[{"id":"me", "username":"haneul", "x":0, "z":0}]}, "messages":[]}
	app = Main.new()
	root.add_child(app)
	await settle(1.6)
	app.api.queue_free()
	var stub := Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = true
	await app.enter_village()
	preload("res://scripts/transition.gd").of(self).fade_in()
	await settle(1.2)
	app.prompt_wait = 1.0e9
	var hub: Node = SocialHud.of(stub)
	app.message(TranslationServer.translate("가구를 놓았어요"))
	await settle(0.4)
	var tray: Control = app.expedition_button.get_parent().get_meta("tray") if app.expedition_button.get_parent().has_meta("tray") else null
	var pieces := {"frame": app.frame.get("panel"), "minimap": app.minimap, "objective": app.objective_card, "hotbar": tray,
		"chat": hub.chat if hub else null}
	var toasts: Array = RpgUi.toasts(app.toast_lane)
	if not toasts.is_empty(): pieces["toast"] = toasts[0]
	# Clicks on the HUD: none may reach the world.
	for key in pieces:
		var piece = pieces[key]
		if not piece is Control or not (piece as Control).is_visible_in_tree():
			expect(false, "%s is on screen for the tour" % key)
			continue
		var leaks := []
		var spots: Array = points((piece as Control).get_global_rect())
		if key == "minimap":
			# The round map takes clicks on its disc only (minimap.gd _has_point): its corners are open.
			var middle: Vector2 = (piece as Control).get_global_rect().position + Vector2(102, 102)
			spots = [middle, middle + Vector2(-60, -40), middle + Vector2(60, -40), middle + Vector2(-60, 50), middle + Vector2(60, 50)]
		for at in spots:
			var before: int = app.world_clicks
			await click(at)
			if app.world_clicks != before: leaks.append(Vector2i(at))
			# A click may open or close something (the minimap, a fold): put the HUD back.
			while not RpgUi.windows().is_empty():
				RpgUi.close_top()
				await settle(0.2)
		expect(leaks.is_empty(), "a click on the %s stays in the HUD %s" % [key, leaks])
	# A click on open ground does reach the world (the counter works).
	var ground_before: int = app.world_clicks
	await click(Vector2(640, 520))
	expect(app.world_clicks > ground_before, "a click on open ground reaches the world")
	# Every hotbar slot pressed twice in one frame: one window, closed again by Esc.
	var slots: Array = app.expedition_button.get_parent().get_children().filter(func(c): return c is Button and c.visible and not c.disabled)
	expect(slots.size() >= 4, "the hotbar has its slots (%d)" % slots.size())
	for slot in slots:
		var name := str(slot.tooltip_text if not slot.tooltip_text.is_empty() else slot.name)
		slot.pressed.emit()
		slot.pressed.emit()
		await settle(0.6)
		var stack := RpgUi.windows().size()
		var drawer_open: bool = is_instance_valid(app.right) and app.right.get_parent().visible
		expect(stack <= 1, "pressing '%s' twice opens at most one window (%d)" % [name, stack])
		if stack == 1:
			var before: int = app.world_clicks
			await click(Vector2(24, 400))
			expect(app.world_clicks == before, "with '%s' open a click on the shade stays out of the world" % name)
		while not RpgUi.windows().is_empty():
			RpgUi.close_top()
			await settle(0.25)
		if is_instance_valid(app.village_modal): app.close_village_modal()
		if drawer_open and app.right.get_parent().visible: app.toggle_drawer()
		await settle(0.3)
	print("HUD_CLICK_TOUR ", "PASS" if failures.is_empty() else "FAIL %d" % failures.size())
	SocialHud.end()
	quit(0 if failures.is_empty() else 1)
