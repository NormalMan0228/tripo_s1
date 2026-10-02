extends SceneTree
const Main=preload("res://scripts/main.gd")
var app: Node3D
func _initialize() -> void: call_deferred("review")
func capture(name: String) -> void:
	await RenderingServer.frame_post_draw
	var result := root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/"+name+".png"))
	if result!=OK: quit(1)
func review() -> void:
	app=Main.new()
	root.add_child(app)
	await process_frame
	app.screen="map_review"
	app.clear_ui()
	app.player.controls_enabled=false
	app.player.position=Vector3(27,3.05,-27)
	await create_timer(.5).timeout
	await capture("lookout-review-07")
	app.player.position=Vector3(-7,.1,14.5)
	await create_timer(.8).timeout
	await capture("lake-review-07")
	# Review camera only; not evidence of a player-accessible flight/teleport ability.
	app.set_process(false)
	app.camera.size=86
	app.camera.position=Vector3(38,85,90)
	app.camera.look_at(Vector3(0,0,0))
	await create_timer(.25).timeout
	await capture("town-overview-07")
	app.queue_free()
	await process_frame
	print("TOWN_VISUAL_REVIEW_COMPLETE")
	quit(0)
