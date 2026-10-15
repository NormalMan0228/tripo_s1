extends SceneTree
## The performance overlay (F2) over the real HUD, against recorded replies as tests/hud_layout_check.gd:
## in the village and on an expedition it must not cover the frame, minimap / map card, goal card,
## day counter, hotbar or chat. With a window it saves artifacts/perf-overlay-{village,survival}.png.
##   godot --path game --script res://tests/perf_overlay_hud.gd -- --qa      (or --headless)
const Main = preload("res://scripts/main.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const I18n = preload("res://scripts/i18n.gd")
const SocialHud = preload("res://scripts/social_hud.gd")
var failures := 0

func _initialize() -> void:
	call_deferred("run")
	create_timer(200).timeout.connect(func(): quit(2))

func expect(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ")+message)
	if not value: failures += 1

func settle(seconds := 0.3) -> void:
	await create_timer(seconds).timeout

func clear_of(overlay: Control, pieces: Dictionary, place: String) -> void:
	var box := overlay.get_global_rect()
	for name in pieces:
		var piece = pieces[name]
		if not piece is Control or not (piece as Control).is_visible_in_tree(): continue
		expect(not box.intersects((piece as Control).get_global_rect()), "%s: overlay %s clear of %s %s" % [place, str(box), name, str((piece as Control).get_global_rect())])

## The visible tray of a hotbar row (the row itself spans the screen), as hud_layout_check.gd.
func hotbar_tray(bar: Node) -> Control:
	return bar.get_meta("tray") if bar and bar.has_meta("tray") else null

func capture(name: String) -> void:
	if DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	var out := ProjectSettings.globalize_path("res://../artifacts")
	DirAccess.make_dir_recursive_absolute(out)
	root.get_texture().get_image().save_png(out.path_join("perf-overlay-%s.png" % name))
	print("CAPTURE ", out.path_join("perf-overlay-%s.png" % name))

func run() -> void:
	I18n.setup()
	RpgUi.set_folds(RpgUi.FOLD_TIPS.keys()+["chat"], false, false)
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	fixture["/v1/social/presence"] = {"self_id":"me", "host_id":"me", "host_name":"haneul", "visiting":false, "party":null, "invites":[],
		"pending_rewards":[], "village":{"players":[{"id":"me", "username":"haneul", "x":0, "z":0}]}, "messages":[]}
	var app = Main.new()
	root.add_child(app)
	current_scene = app
	await settle(1.6)
	app.api.queue_free()
	var stub = Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = true
	await app.enter_village()
	preload("res://scripts/transition.gd").of(self).fade_in()
	await settle(1.2)
	var hub = SocialHud.of(stub)
	var overlay = root.get_node("ImeCaret").perf_overlay()
	overlay.show_overlay(true)
	await settle(1.2)
	var panel: Control = overlay.panel
	clear_of(panel, {"frame": app.frame.get("panel"), "minimap": app.minimap, "objective": app.objective_card,
		"hotbar": hotbar_tray(app.expedition_button.get_parent()), "chat": hub.chat if hub else null}, "village")
	await capture("village")
	await app.start_run("forest", "standard")
	await settle(1.6)
	clear_of(panel, {"frame": app.left.get_parent(), "map": app.field_panel, "objective": app.objective_card,
		"day": app.day_track.get_parent(), "hotbar": hotbar_tray(app.toolbar_bar), "chat": hub.chat if hub else null}, "survival")
	await capture("survival")
	overlay.show_overlay(false)
	app.queue_free()
	await settle(0.4)
	SocialHud.end()
	print("PERF_OVERLAY_HUD ", "FAIL" if failures > 0 else "PASS")
	quit(1 if failures > 0 else 0)
