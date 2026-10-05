extends SceneTree

func _initialize() -> void:
	_run.call_deferred()

func _key(scene: Node, code: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.pressed = true
	scene._unhandled_input(event)

func _run() -> void:
	var scene = load("res://terrain.tscn").instantiate()
	root.add_child(scene)
	await process_frame
	_key(scene, KEY_C)
	assert(scene.free_camera)
	assert(scene.camera.projection == Camera3D.PROJECTION_PERSPECTIVE)
	var start: Vector3 = scene.camera.position
	var forward: Vector3 = -scene.camera.global_basis.z
	scene._move_free_camera(1.0, Vector3(0,0,-1))
	assert(scene.camera.position.is_equal_approx(start + forward * 24.0))
	var moved: Vector3 = scene.camera.position
	scene._update_camera()
	assert(scene.camera.position.is_equal_approx(moved), "Orbit must not reset free movement")
	scene._move_free_camera(1.0, Vector3.UP)
	assert(scene.camera.position.is_equal_approx(moved + Vector3.UP * 24.0))
	start = scene.camera.position
	scene._move_free_camera(1.0, Vector3(1,0,-1), 3.0)
	assert(is_equal_approx(scene.camera.position.distance_to(start),72.0), "Diagonal must not exceed boost speed")
	start = scene.camera.position
	scene._move_free_camera(1.0, Vector3(0,0,1), .25)
	assert(is_equal_approx(scene.camera.position.distance_to(start),6.0))
	var scroll := InputEventMouseButton.new()
	scroll.pressed = true
	scroll.button_index = MOUSE_BUTTON_WHEEL_UP
	scene._unhandled_input(scroll)
	assert(scene.free_speed == 30.0)
	_key(scene, KEY_F)
	assert(not scene.free_camera and scene.waterfall_focus)
	assert(scene.camera.projection == Camera3D.PROJECTION_ORTHOGONAL)
	_key(scene, KEY_C)
	_key(scene, KEY_L)
	assert(not scene.free_camera and scene.lake_focus)
	_key(scene, KEY_R)
	assert(not scene.follow and not scene.lake_focus and not scene.waterfall_focus)
	_key(scene, KEY_C)
	_key(scene, KEY_ESCAPE)
	assert(not scene.free_camera)
	_key(scene, KEY_P)
	_key(scene, KEY_C)
	_key(scene, KEY_C)
	assert(scene.camera.projection == Camera3D.PROJECTION_PERSPECTIVE)
	var minimum_height := 1000.0
	var max_step := 0.0
	var previous: Vector3 = scene.tour_positions[0]
	for i in range(1441):
		scene._update_tour_camera(float(i)/30.0)
		var point: Vector3 = scene.camera.position
		assert(point.is_finite())
		assert(absf(scene.camera.global_basis.determinant()-1.0) < .001)
		minimum_height = minf(minimum_height, point.y)
		max_step = maxf(max_step, point.distance_to(previous))
		previous = point
	assert(minimum_height > 6.0, "Tour must remain above cliffs")
	assert(max_step < 1.5, "Tour must have continuous camera movement")
	var report := {"free_camera_movement":true, "vertical_movement":true, "diagonal_speed_normalized":true, "boost_and_slow":true, "no_orbit_reset":true, "preset_switches":true, "perspective_restored":true, "tour_seconds":48, "tour_minimum_height_m":minimum_height, "tour_maximum_step_at_30fps_m":max_step}
	var file := FileAccess.open(ProjectSettings.globalize_path("res://../../art/maps/archipelago_terrain_v6/camera_navigation_verification.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"\t"))
	print("CAMERA_NAVIGATION_CHECK_PASS ",JSON.stringify(report))
	quit()
