extends SceneTree
## Windowed title shots: the painted art and the turning World Labs sky (title_sky.gd),
## artifacts/title-art.png and title-sky-*.png.
##   godot --path game --script res://tests/title_shot.gd
const Main = preload("res://scripts/main.gd")

func _initialize() -> void:
	call_deferred("run")
	create_timer(120).timeout.connect(func(): quit(2))

func capture(name: String) -> void:
	for i in 6: await process_frame
	if DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/title-%s.png" % name))
	print("SHOT title-", name)

func run() -> void:
	var app := Main.new()
	root.add_child(app)
	await create_timer(3.0).timeout
	app.login_ui("menu")
	await create_timer(1.5).timeout
	await capture("art")
	Main.title_sky = true
	app.login_ui("menu")
	await create_timer(1.5).timeout
	await capture("sky-a")
	await create_timer(6.0).timeout
	await capture("sky-b")
	quit(0)
