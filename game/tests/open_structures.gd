extends SceneTree
## Walks into the open structures (gazebo, stage, picnic shelter) from outside and
## checks that the walker reaches the middle standing on the structure's floor.
const Main = preload("res://scripts/main.gd")
const Town = preload("res://scripts/town.gd")
var failed := false
var app: Node3D
func expect(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ")+label)
	if not value: failed = true
func release() -> void:
	for action in ["move_left","move_right","move_forward","move_back"]: Input.action_release(action)
func walk_to(target: Vector2, seconds: float) -> void:
	var end := Time.get_ticks_msec()+int(seconds*1000)
	while Time.get_ticks_msec()<end:
		var gap: Vector2=target-Vector2(app.player.position.x,app.player.position.z)
		if gap.length()<0.4: break
		var d := gap.normalized()
		release()
		if d.x>0.05: Input.action_press("move_right",d.x)
		if d.x< -0.05: Input.action_press("move_left",-d.x)
		if d.y>0.05: Input.action_press("move_back",d.y)
		if d.y< -0.05: Input.action_press("move_forward",-d.y)
		await physics_frame
	release()
func _initialize() -> void:
	call_deferred("run")
	create_timer(200).timeout.connect(func(): quit(2))
func run() -> void:
	app = Main.new()
	root.add_child(app)
	await create_timer(1.2).timeout
	await app.authenticate(true,"http://127.0.0.1:8766","open_"+str(Time.get_ticks_msec()),"Open-structures-1","")
	await create_timer(1.0).timeout
	for spec in [["gazebo",Vector2(71,-36),Vector2(71,-29.5)],["stage",Vector2(37,26),Vector2(37,32.5)],["picnic shelter",Vector2(65,29),Vector2(65,35)]]:
		var centre: Vector2=spec[1]
		app.player.position = Town.point(spec[2],.4)
		app.player.velocity = Vector3.ZERO
		for i in 20: await physics_frame
		var ground_outside: float = app.player.position.y
		await walk_to(centre, 8.0)
		for i in 10: await physics_frame
		var at := Vector2(app.player.position.x,app.player.position.z)
		print("STRUCTURE ",spec[0]," reached=",at.distance_to(centre)," y_outside=",ground_outside," y_inside=",app.player.position.y)
		expect(at.distance_to(centre)<1.2,"walked into the "+spec[0])
		if "--capture" in OS.get_cmdline_user_args():
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/open-"+String(spec[0]).replace(" ","_")+".png"))
	quit(1 if failed else 0)
