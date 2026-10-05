extends SceneTree
## Loads the archipelago map, then reports ground heights and blockers at candidate
## village sites. Optional --topdown writes the Tab map image.
const Map = preload("res://maps/archipelago/archipelago.gd")
var map: Node3D
var camera: Camera3D

func _initialize() -> void:
	call_deferred("run")

func ray(space: PhysicsDirectSpaceState3D, x: float, z: float, mask: int) -> Dictionary:
	var q := PhysicsRayQueryParameters3D.create(Vector3(x,60,z),Vector3(x,-20,z),mask)
	return space.intersect_ray(q)

func run() -> void:
	var started := Time.get_ticks_msec()
	camera = Camera3D.new()
	root.add_child(camera)
	map = Map.new()
	root.add_child(map)
	map.build(camera)
	print("MAP_BUILD_MS ", Time.get_ticks_msec()-started)
	for i in 4: await physics_frame
	var space := map.get_world_3d().direct_space_state
	var sites := {}
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--sites="):
			sites = JSON.parse_string(arg.trim_prefix("--sites=").replace("'", "\""))
	var report := {}
	for key in sites:
		var at: Array = sites[key]
		var ground := ray(space, at[0], at[1], 1)
		var any := ray(space, at[0], at[1], 1|2|8)
		var blockers := 0
		var shape := SphereShape3D.new()
		shape.radius = float(at[2]) if at.size() > 2 else 1.0
		var query := PhysicsShapeQueryParameters3D.new()
		query.shape = shape
		query.collision_mask = 2|8
		if not ground.is_empty():
			query.transform = Transform3D(Basis.IDENTITY, ground.position+Vector3(0,shape.radius+.2,0))
			blockers = space.intersect_shape(query, 8).size()
		report[key] = {"ground": snappedf(ground.position.y, .01) if not ground.is_empty() else null,
			"top": snappedf(any.position.y, .01) if not any.is_empty() else null, "blockers": blockers}
	print("PROBE ", JSON.stringify(report))
	if "--topdown" in OS.get_cmdline_user_args():
		await topdown()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--view="):
			await game_view(arg.trim_prefix("--view=").split(","))
		if arg.begins_with("--top="):
			await top_view(arg.trim_prefix("--top=").split(","))
		if arg.begins_with("--shot="):
			await shot(arg.trim_prefix("--shot=").split(","))
	quit()

## Perspective still for menus: --shot=px,py,pz,tx,ty,tz,fov,name (1920 x 1080).
func shot(v: PackedStringArray) -> void:
	var frame := SubViewport.new()
	frame.size = Vector2i(1920, 1080)
	frame.msaa_3d = Viewport.MSAA_4X
	frame.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(frame)
	var view := Camera3D.new()
	view.fov = float(v[6])
	view.far = 3000
	frame.add_child(view)
	view.position = Vector3(float(v[0]), float(v[1]), float(v[2]))
	view.look_at(Vector3(float(v[3]), float(v[4]), float(v[5])))
	view.current = true
	var e := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.environment = env
	frame.add_child(e)
	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = true
	frame.add_child(sun)
	Map.apply_lighting(env, sun)
	sun.directional_shadow_max_distance = 260
	map.camera = view
	for i in 40: await process_frame
	await RenderingServer.frame_post_draw
	var path := ProjectSettings.globalize_path("res://../artifacts/island-shot-"+v[7]+".png")
	print("SHOT ", frame.get_texture().get_image().save_png(path), " ", path)
	frame.queue_free()

## Straight-down square image for measuring: --top=x,z,size,name (800 px = size m).
func top_view(v: PackedStringArray) -> void:
	var frame := SubViewport.new()
	frame.size = Vector2i(800, 800)
	frame.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(frame)
	var view := Camera3D.new()
	view.projection = Camera3D.PROJECTION_ORTHOGONAL
	view.size = float(v[2])
	view.far = 400
	view.position = Vector3(float(v[0]), 150, float(v[1]))
	view.rotation_degrees = Vector3(-90, 0, 0)
	frame.add_child(view)
	view.current = true
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-70, 160, 0)
	light.light_specular = 0.0
	frame.add_child(light)
	for i in 12: await process_frame
	await RenderingServer.frame_post_draw
	var path := ProjectSettings.globalize_path("res://../artifacts/island-top-"+v[3]+".png")
	print("TOP ", frame.get_texture().get_image().save_png(path), " ", path)
	frame.queue_free()

## Renders the game's follow camera at a village point with the lighting under test:
## --view=x,z,size,name,sun_energy,ambient_energy,tonemap(0 linear/1 aces),exposure
func game_view(v: PackedStringArray) -> void:
	const Profile = preload("res://scripts/controller_profile.gd")
	var e := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color.WHITE
	e.environment = env
	root.add_child(e)
	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = true
	root.add_child(sun)
	Map.apply_lighting(env, sun)
	sun.light_energy = float(v[4])
	env.ambient_light_energy = float(v[5])
	env.tonemap_mode = Environment.TONE_MAPPER_ACES if v[6] == "1" else Environment.TONE_MAPPER_LINEAR
	env.tonemap_exposure = float(v[7])
	var focus := Vector3(float(v[0]), 0, float(v[1]))
	focus.y = ray(map.get_world_3d().direct_space_state, focus.x, focus.z, 1).get("position", Vector3.ZERO).y
	focus += Profile.CAMERA_FOCUS_OFFSET
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = float(v[2])
	camera.position = focus + Profile.CAMERA_OFFSET
	camera.look_at(focus)
	camera.current = true
	for i in 20: await process_frame
	await RenderingServer.frame_post_draw
	var path := ProjectSettings.globalize_path("res://../artifacts/island-view-"+v[3]+".png")
	print("VIEW ", root.get_texture().get_image().save_png(path), " ", path)
	e.queue_free()
	sun.queue_free()

func topdown() -> void:
	var view := Camera3D.new()
	view.projection = Camera3D.PROJECTION_ORTHOGONAL
	view.size = 180
	view.near = 1
	view.far = 400
	view.position = Vector3(2.5, 200, 10)
	view.rotation_degrees = Vector3(-90, 0, 0)
	# A square SubViewport shares the map's world, so the image covers exactly 180 x 180 m.
	var frame := SubViewport.new()
	frame.size = Vector2i(800, 800)
	frame.msaa_3d = Viewport.MSAA_4X
	frame.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(frame)
	frame.add_child(view)
	view.current = true
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-70, 160, 0)
	light.light_energy = 1.1
	light.light_specular = 0.0
	root.add_child(light)
	var e := WorldEnvironment.new()
	e.environment = Environment.new()
	e.environment.background_mode = Environment.BG_COLOR
	e.environment.background_color = Color("5fb8c9")
	e.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.environment.ambient_light_color = Color.WHITE
	e.environment.ambient_light_energy = .5
	root.add_child(e)
	for i in 30: await process_frame
	await RenderingServer.frame_post_draw
	var path := ProjectSettings.globalize_path("res://assets/archipelago_map.png")
	print("TOPDOWN ", frame.get_texture().get_image().save_png(path), " ", path)
