extends SceneTree
const Player=preload("res://scripts/player.gd")
const Profile=preload("res://scripts/controller_profile.gd")
const Main=preload("res://scripts/main.gd")
var failures: Array[String]=[]
var report: Dictionary={}
func _initialize() -> void:call_deferred("run_test")
func expect(ok: bool,label: String) -> void:
	print(("PASS " if ok else "FAIL ")+label)
	if not ok:failures.append(label)
func release_keys() -> void:
	for action in ["move_left","move_right","move_forward","move_back"]:Input.action_release(action)
func frames(count: int) -> void:
	for frame in count:await physics_frame;await process_frame
func capture(name: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args():return
	await RenderingServer.frame_post_draw
	var folder := ProjectSettings.globalize_path("res://../artifacts")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--artifacts="):folder=arg.trim_prefix("--artifacts=")
	root.get_texture().get_image().save_png(folder.path_join(name+".png"))
func run_test() -> void:
	Engine.max_fps=60
	var stage := Node3D.new();root.add_child(stage)
	var ground := StaticBody3D.new();stage.add_child(ground)
	var collision := CollisionShape3D.new();ground.add_child(collision)
	var shape := BoxShape3D.new();shape.size=Vector3(60,.2,60);collision.shape=shape;ground.position.y=-.1
	var mesh := MeshInstance3D.new();var box := BoxMesh.new();box.size=shape.size;mesh.mesh=box;ground.add_child(mesh)
	var sun := DirectionalLight3D.new();stage.add_child(sun);sun.rotation_degrees=Vector3(-45,-25,0)
	var camera := Camera3D.new();stage.add_child(camera);camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=5;camera.current=true
	var player := Player.new();stage.add_child(player);player.position=Vector3(0,.1,0)
	await frames(20)
	expect(player.finger_pose.samples.size()>=24,"reviewed individual finger rotations remain attached")
	expect(player.hand_skeleton.find_bone("Face_Jaw")<0,"original face is retained")
	var bone_count: int=player.hand_skeleton.get_bone_count()
	var walking_speed := 0.0;var contact_error := 0.0;var contacts := 0
	Input.action_press("move_right")
	for frame in 100:
		await frames(1)
		if frame>30:
			walking_speed=maxf(walking_speed,player.locomotion_velocity.length())
			contact_error=maxf(contact_error,player.locomotion_pose.contact_error)
			for leg in player.locomotion_pose.legs:
				if leg.contact:contacts+=1
	camera.position=player.position+Vector3(3,2.4,5);camera.look_at(player.position+Vector3.UP*.9)
	await capture("controller-walking")
	release_keys();await frames(15)
	expect(absf(walking_speed-Profile.VILLAGE_WALK)<.1,"village walking speed matches profile")
	expect(player.current_clip=="idle" and player.locomotion_velocity.length()<.01,"release stops movement and returns to idle")
	expect(contacts>30 and contact_error<.04,"planted foot follows its fixed contact within 4 cm")
	Input.action_press("move_right");Input.action_press("move_back");player.sprinting=true
	var run_contact_error := 0.0
	for frame in 50:
		await frames(1)
		if frame>15:run_contact_error=maxf(run_contact_error,player.locomotion_pose.contact_error)
	var run_speed: float=player.locomotion_velocity.length()
	expect(absf(run_speed-Profile.VILLAGE_RUN)<.1,"diagonal sprint is normalized")
	expect(player.current_clip=="run","faster motion selects the authored run clip")
	expect(run_contact_error<.06,"diagonal run contact stays within 6 cm")
	camera.position=player.position+Vector3(3,2.4,5);camera.look_at(player.position+Vector3.UP*.9)
	await capture("controller-running")
	release_keys();player.sprinting=false;await frames(15)
	var wall := StaticBody3D.new();stage.add_child(wall)
	var wall_collision := CollisionShape3D.new();wall.add_child(wall_collision)
	var wall_shape := BoxShape3D.new();wall_shape.size=Vector3(.5,4,8);wall_collision.shape=wall_shape
	wall.position=player.position+Vector3(.9,1,0)
	Input.action_press("move_right");await frames(50)
	expect(player.current_clip=="idle" and player.locomotion_velocity.length()<.1,"pushing a wall does not walk in place")
	release_keys()
	report={"walking_speed":walking_speed,"diagonal_run_speed":run_speed,"max_foot_contact_error_m":contact_error,"run_contact_error_m":run_contact_error,"contact_samples":contacts,"bones":bone_count}
	stage.queue_free();await process_frame
	var app := Main.new();root.add_child(app);await process_frame
	await app.authenticate(true,"http://127.0.0.1:8766","control_"+str(Time.get_ticks_usec()),"Controller-test-password","")
	expect(app.screen=="village","controller test reaches authenticated village")
	if app.screen!="village":quit(1);return
	if preload("res://scripts/build_mode.gd").developer():
		app.developer_panel.visible=true;await frames(4)
		expect(app.developer_label.text.contains("입력") and app.developer_label.text.contains("접지 오차"),"developer diagnostics include controller metrics")
		await capture("controller-developer-hud")
		app.developer_panel.visible=false
	else:expect(not is_instance_valid(app.developer_panel),"player has no developer diagnostic panel")
	Input.action_press("move_right");app.toggle_drawer();await frames(5)
	var before: Vector3=app.player.position
	await frames(25)
	expect(app.player.position.distance_to(before)<.03,"inventory blocks held movement input")
	app.toggle_drawer();app.modal_card("입력 잠금 검사");await frames(5);before=app.player.position
	await frames(25)
	expect(app.player.position.distance_to(before)<.03,"dialogue blocks held movement input")
	app.close_village_modal();release_keys()
	var orientation: Basis=app.camera.global_basis
	var focus_start: Vector3=app.player.position
	app.player.position+=Vector3(1,0,1);await frames(30)
	expect(orientation.z.dot(app.camera.global_basis.z)>.99999,"camera keeps its angle during diagonal tracking")
	var wheel := InputEventMouseButton.new();wheel.button_index=MOUSE_BUTTON_WHEEL_UP;wheel.pressed=true
	var initial_size: float=app.camera.size;app._unhandled_input(wheel)
	expect(app.camera.size==initial_size,"zoom changes smoothly instead of jumping")
	await frames(30)
	expect(absf(app.camera.size-(initial_size-1))<.02,"zoom reaches the requested size")
	# Same stationary target over one second at different update rates.
	var targets: Array[Vector3]=[]
	app.set_process(false)
	for fps in [30,60,144]:
		app.camera_focus=focus_start;app.camera_focus_ready=true
		for frame in fps:app.follow_camera(1.0/fps)
		targets.append(app.camera_focus)
	expect(targets[0].distance_to(targets[2])<.0001,"camera tracking is independent of render frame rate")
	app.set_process(true)
	await app.start_run();await frames(10)
	expect(app.player.visual_only,"survival display does not apply local collision to server position")
	Input.action_press("move_right");app.toggle_pause()
	expect(app.movement_input()==Vector2.ZERO,"paused survival does not send movement")
	app.toggle_pause();app.toggle_drawer()
	expect(app.movement_input()==Vector2.ZERO,"survival inventory does not send movement")
	app.toggle_drawer();release_keys();await app.leave_run()
	app.queue_free();await frames(3)
	print("CONTROLLER_ACCEPTANCE ",JSON.stringify({"ok":failures.is_empty(),"failures":failures,"metrics":report,"paid_calls":0}))
	quit(0 if failures.is_empty() else 1)
