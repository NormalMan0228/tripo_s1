extends SceneTree
## Art-review capture only; this never claims to verify an authenticated game session.
const Main = preload("res://scripts/main.gd")
var app: Node3D

func _initialize() -> void: call_deferred("capture_worlds")

func capture(name: String) -> void:
	await create_timer(0.45).timeout
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/"+name+".png"))

func capture_worlds() -> void:
	app=Main.new()
	root.add_child(app)
	await create_timer(0.3).timeout
	await capture("login-polished")
	app.clear_ui()
	app.screen="art_review"
	app.player.controls_enabled=false
	app.player.position=Vector3(0,0,1)
	app.camera.size=23
	await capture("village-overview")
	app.player.position=Vector3(-4,0,-2)
	app.camera.size=12
	await capture("workshop-detail")
	app.build_world(true)
	app.player.controls_enabled=false
	app.camera.size=16
	app.player.position=Vector3(16,0,16)
	await capture("forest-edge-review")
	app.player.position=Vector3.ZERO
	app.flame.visible=true
	app.environment.ambient_light_color=Color("788fab")
	app.environment.ambient_light_energy=0.25
	app.sun.light_color=Color("7fa9cf")
	app.sun.light_energy=0.22
	await capture("camp-art-review")
	app.run={"status":"won","day":7,"harvested":38,"kills":4,"reward":65}
	app.show_results()
	await capture("results-layout-fixture")
	quit()
