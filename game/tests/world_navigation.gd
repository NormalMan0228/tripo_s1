extends SceneTree
const Main = preload("res://scripts/main.gd")
var app: Node3D
var failed := false

func _initialize() -> void: call_deferred("walk")

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed=true

func walk() -> void:
	app=Main.new()
	root.add_child(app)
	await process_frame
	app.screen="map_review"
	app.clear_ui()
	app.player.controls_enabled=true
	app.player.position=Vector3(-7,0.2,10.3)
	Input.action_press("move_back")
	await create_timer(2).timeout
	Input.action_release("move_back")
	expect(app.player.position.z>15.1 and app.player.position.z<15.65,"harbor walkway is reachable and end rail blocks exit")
	expect(app.player.position.y>-.05 and app.player.position.y<0.2,"pier has a stable physical floor")
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/harbor-walk.png"))
	Input.action_press("move_right")
	await create_timer(0.8).timeout
	Input.action_release("move_right")
	expect(app.player.position.x< -6,"pier side rail prevents walking into sea")
	Input.action_press("move_forward")
	await create_timer(1.4).timeout
	Input.action_release("move_forward")
	expect(app.player.position.z<10.5,"player can return from pier to village")
	app.player.position=Vector3(-5,0.1,-2.7)
	Input.action_press("move_forward")
	await create_timer(1).timeout
	Input.action_release("move_forward")
	expect(app.player.position.z> -3.35,"workshop collision prevents entering building mesh")
	app.player.position=Vector3(-9.3,0.1,9)
	Input.action_press("move_back")
	await create_timer(0.8).timeout
	Input.action_release("move_back")
	expect(app.player.position.z<10.05,"bench has a matching solid collision")
	app.queue_free()
	await process_frame
	await process_frame
	print("WORLD_NAVIGATION_COMPLETE")
	quit(1 if failed else 0)
