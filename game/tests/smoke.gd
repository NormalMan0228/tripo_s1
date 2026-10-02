extends SceneTree

const Loader = preload("res://scripts/model_loader.gd")
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
	else:
		print("PASS: ", message)

func run() -> void:
	var village = load("res://scenes/village.tscn").instantiate()
	root.add_child(village)
	await process_frame
	village.set_process(false)
	var a := Loader.load_sample("res://assets/sample_stool.glb")
	var b := Loader.load_sample("res://assets/sample_stool.glb")
	check(a != null and b != null, "Runtime GLB import succeeds twice")
	if a == null or b == null:
		quit(1)
		return
	root.add_child(a)
	root.add_child(b)
	var meshes: Array[MeshInstance3D] = []
	Loader._collect_meshes(a, meshes)
	check(meshes.size() == 5, "All five stool parts survive GLB import")
	var bounds := AABB()
	for index in meshes.size():
		var part_bounds: AABB = meshes[index].global_transform * meshes[index].get_aabb()
		bounds = part_bounds if index == 0 else bounds.merge(part_bounds)
	check(absf(bounds.position.y) < 0.001, "Normalized model rests on the floor")
	check(absf(maxf(bounds.size.x, maxf(bounds.size.y, bounds.size.z)) - 1.6) < 0.001, "Longest model dimension is 1.6 units")
	Loader.paint(a, Color.RED)
	var other: Array[MeshInstance3D] = []
	Loader._collect_meshes(b, other)
	check(meshes[0].material_override.albedo_color == Color.RED and other[0].material_override.albedo_color == Color.WHITE, "Painting one model does not recolor another")
	a.free()
	b.free()
	for frame in 20:
		await physics_frame
	check(village.player.is_on_floor(), "Player settles on the solid ground")
	var initial_x: float = village.player.position.x
	Input.action_press("move_right")
	for frame in 30:
		await physics_frame
	Input.action_release("move_right")
	check(village.player.position.x > initial_x + 1.5, "Movement input moves the player")
	village.player.position = Vector3(0, 0.1, 4)
	village.begin_sample()
	village.preview.position = Vector3(0, 0, 1)
	village.set_paint(Color("70afa3"))
	check(village.place_preview(), "An empty location accepts a painted sample")
	village.begin_sample()
	village.preview.position = Vector3(0, 0, 1)
	check(not village.place_preview(), "Overlapping decorations are rejected")
	village.preview.position = Vector3(0, 0, 4)
	check(not village.place_preview(), "Placing on the player is rejected")
	village.preview.position = Vector3(13, 0, 4)
	check(not village.place_preview(), "Placing outside the village is rejected")
	village.cancel_preview()
	Input.action_press("move_forward")
	for frame in 70:
		await physics_frame
	Input.action_release("move_forward")
	check(village.player.position.z > 2.0 and village.player.position.z < 2.5, "Placed sample blocks player movement")
	if OS.get_cmdline_user_args().has("--capture"):
		village.player.position = Vector3(0, 0, 4)
		village._follow_camera()
		for info in [[Vector3(3, 0, 1), Color("e9b959")], [Vector3(-3, 0, 2), Color("de806b")]]:
			village.begin_sample()
			village.preview.position = info[0]
			village.set_paint(info[1])
			village.place_preview()
		for frame in 8:
			await process_frame
		await RenderingServer.frame_post_draw
		var image := root.get_texture().get_image()
		var output := ProjectSettings.globalize_path("res://../artifacts/village-preview.png")
		DirAccess.make_dir_recursive_absolute(output.get_base_dir())
		check(image.save_png(output) == OK, "Rendered preview saved")
	village.queue_free()
	await process_frame
	print("SMOKE RESULT: ", "PASS" if failures == 0 else "FAIL", " (", failures, " failures)")
	quit(0 if failures == 0 else 1)
