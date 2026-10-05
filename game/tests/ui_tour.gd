extends SceneTree
## Player-facing screens in each language: title menu, settings, login card,
## village HUD, craft window and map. Captures land in artifacts/ui-*.png.
const Main = preload("res://scripts/main.gd")
const I18n = preload("res://scripts/i18n.gd")
var failed := false
var app: Node3D

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("UI tour exceeded 240 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func capture(name: String) -> void:
	for i in 8: await process_frame
	# Headless runs never draw, so only wait for a frame when capturing.
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/ui-"+name+".png"))

func find_text(node: Node, needle: String) -> bool:
	if (node is Label or node is Button) and needle in node.text: return true
	for child in node.get_children():
		if find_text(child, needle): return true
	return false

func run() -> void:
	var languages := ["ko","en","zh"]
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--languages="): languages = Array(arg.trim_prefix("--languages=").split(","))
	I18n.setup()
	for code in languages:
		I18n.set_language(code)
		app = Main.new()
		root.add_child(app)
		await create_timer(1.6).timeout
		expect(app.screen=="login","title screen in "+code)
		await capture(code+"-title")
		app.login_ui("settings")
		await create_timer(.4).timeout
		await capture(code+"-settings")
		app.login_ui("login")
		await create_timer(.4).timeout
		await capture(code+"-login")
		if code=="en": expect(find_text(app.ui,"Log In"),"English login button")
		if code=="zh": expect(find_text(app.ui,"登录"),"Chinese login button")
		await app.authenticate(true,"http://127.0.0.1:8766","ui_"+code+"_"+str(Time.get_ticks_msec()),"Ui-tour-password-123","")
		await create_timer(1.2).timeout
		expect(app.screen=="village","village after login in "+code)
		await capture(code+"-village")
		await app.open_craft()
		await create_timer(.5).timeout
		await capture(code+"-craft")
		app.close_village_modal()
		app.life.open_map()
		await create_timer(.4).timeout
		await capture(code+"-map")
		app.close_village_modal()
		app.queue_free()
		await create_timer(.5).timeout
	I18n.set_language("ko")
	quit(1 if failed else 0)
