extends SceneTree
## Rendered HUD fold states: logs in against the QA server (tools/test.ps1
## -ClientScript hud_fold_tour -Capture), then captures the village HUD open and
## folded (artifacts/hud-fold-unfolded.png, hud-fold-folded.png) and the field HUD
## the same way (hud-fold-field-unfolded.png, hud-fold-field-folded.png).
const Main = preload("res://scripts/main.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const I18n = preload("res://scripts/i18n.gd")
var failed := false
var app: Node3D

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("HUD fold tour exceeded 240 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func capture(name: String) -> void:
	for i in 8: await process_frame
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/hud-fold-"+name+".png"))

func run() -> void:
	I18n.setup()
	I18n.set_language("ko")
	app = Main.new()
	root.add_child(app)
	await create_timer(1.6).timeout
	await app.authenticate(true,"http://127.0.0.1:8766","fold_"+str(Time.get_ticks_msec()),"Fold-tour-password-123","")
	await create_timer(1.2).timeout
	expect(app.screen=="village","village after login")
	app.message(tr("물결빛 마을에 오신 것을 환영해요! 다리를 건너 다섯 섬을 둘러보세요."))
	await create_timer(0.8).timeout
	expect(RpgUi.fold_ids().size()==4 and RpgUi.fold_ids().all(func(id): return not RpgUi.folded(id)), "village HUD starts open")
	await capture("unfolded")
	expect(RpgUi.toggle_all_folds(), "every village panel folded")
	await create_timer(0.6).timeout
	await capture("folded")
	expect(not RpgUi.toggle_all_folds(), "village panels open again")
	await create_timer(0.5).timeout
	await app.start_run()
	await create_timer(1.6).timeout
	expect(app.screen=="survival","field run started")
	await capture("field-unfolded")
	expect(RpgUi.toggle_all_folds(), "field panels folded")
	await create_timer(0.6).timeout
	await capture("field-folded")
	RpgUi.toggle_all_folds()
	await create_timer(0.4).timeout
	app.queue_free()
	await create_timer(0.5).timeout
	quit(1 if failed else 0)
