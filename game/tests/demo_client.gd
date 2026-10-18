extends SceneTree
const Main = preload("res://scripts/main.gd")
var capture_wait := 1.0
var capturing := false

func _process(delta: float) -> bool:
	capture_wait -= delta
	if capture_wait > 0.0 or capturing or DisplayServer.get_name() == "headless": return false
	capture_wait = 1.0
	var folder := OS.get_environment("VILLAGEN_DEMO_READY").get_base_dir()
	if not folder.is_empty() and FileAccess.file_exists(folder.path_join("capture.request")):
		capturing = true
		capture_frame.call_deferred(folder)
	return false

func capture_frame(folder: String) -> void:
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(folder.path_join("multiplayer.png"))
	DirAccess.remove_absolute(folder.path_join("capture.request"))
	capturing = false

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var url := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server=http://127.0.0.1:"): url = arg.trim_prefix("--server=")
	if url.is_empty():
		push_error("The demo client only accepts the local demo server")
		quit(1)
		return
	var app := Main.new()
	root.add_child(app)
	# Keep real scene changes (entering a house and returning) working normally.
	for i in 900:
		if app.title_page == "menu": break
		await create_timer(.1).timeout
	await app.authenticate(false, url, OS.get_environment("VILLAGEN_DEMO_USER"), OS.get_environment("VILLAGEN_DEMO_PASSWORD"), "")
	if app.screen != "village":
		push_error("Demo login failed")
		quit(1)
		return
	current_scene = app
	DisplayServer.window_set_title("Villagen 0.11.9.5 · " + OS.get_environment("VILLAGEN_DEMO_USER"))
	var file := FileAccess.open(OS.get_environment("VILLAGEN_DEMO_READY"), FileAccess.WRITE)
	file.store_string(JSON.stringify({"ready":true,"user_dir":OS.get_user_data_dir()}))
	file.close()
	print("DEMO_CLIENT_READY ", OS.get_environment("VILLAGEN_DEMO_USER"))
