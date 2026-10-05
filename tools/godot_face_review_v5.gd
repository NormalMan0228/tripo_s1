extends SceneTree

func _initialize() -> void:
	call_deferred("capture")

func capture() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() < 2:
		quit(2)
		return
	var viewport := SubViewport.new()
	viewport.size = Vector2i(900,1000)
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.msaa_3d = Viewport.MSAA_4X
	root.add_child(viewport)
	var world := Node3D.new()
	viewport.add_child(world)
	var state := GLTFState.new()
	var doc := GLTFDocument.new()
	var error := doc.append_from_file(args[0], state)
	if error != OK:
		push_error("GLB_LOAD_FAILED %s" % error)
		quit(3)
		return
	var character := doc.generate_scene(state)
	world.add_child(character)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.18, 0.19, 0.21)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.9, 0.92, 1.0)
	env.ambient_light_energy = 0.18
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	var we := WorldEnvironment.new()
	we.environment = env
	world.add_child(we)
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 1.23
	world.add_child(camera)
	camera.position = Vector3(3, 0.04, 0)
	camera.look_at(Vector3(0, 0.04, 0))
	camera.current = true
	for settings in [[Vector3(3, 2.8, 2), 0.32, Color(1.0,0.92,0.84)], [Vector3(2,1,-2.5),0.14,Color(0.85,0.91,1)], [Vector3(-2,2,-1),0.17,Color(1,1,1)]]:
		var light := DirectionalLight3D.new()
		world.add_child(light)
		light.position = settings[0]
		light.look_at(Vector3(0,0.1,0))
		light.light_energy = settings[1]
		light.light_color = settings[2]
		light.shadow_enabled = true
	root.size = Vector2i(480,640)
	for i in range(20):
		await process_frame
	await RenderingServer.frame_post_draw
	var result := viewport.get_texture().get_image().save_png(args[1])
	print("ACTUAL_GODOT_CAPTURE renderer=", ProjectSettings.get_setting("rendering/renderer/rendering_method"), " result=", result)
	quit(result)
