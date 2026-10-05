extends SceneTree
## Read-only art captures. The village life integration test verifies interaction.
const Main=preload("res://scripts/main.gd")

func _initialize() -> void: call_deferred("run_review")

func capture(name: String) -> void:
	await create_timer(0.8).timeout
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/"+name+".png"))

func run_review() -> void:
	var app := Main.new()
	root.add_child(app)
	await process_frame
	app.clear_ui()
	app.screen="review"
	app.player.controls_enabled=false
	app.player.position=Vector3(-17,0.1,2.2)
	app.camera.size=12
	app.follow_camera(1)
	await capture("seed-shop-review")
	app.player.position=Vector3(29,0.1,28)
	app.follow_camera(1)
	await capture("fishing-shack-review")
	quit()
