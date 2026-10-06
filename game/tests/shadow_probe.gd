extends SceneTree
## Renders the village follow view with the camera at several pull-back distances
## and shadow settings, to check shadows survive the longer camera distance.
const Map = preload("res://maps/archipelago/archipelago.gd")
const Profile = preload("res://scripts/controller_profile.gd")

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var camera := Camera3D.new()
	root.add_child(camera)
	var map := Map.new()
	root.add_child(map)
	map.build(camera)
	var e := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.environment = env
	root.add_child(e)
	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = true
	root.add_child(sun)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 10
	camera.current = true
	for i in 6: await physics_frame
	var focus := Vector3(-30, 0, 36)
	var size := 10.0
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--focus="):
			var v := arg.trim_prefix("--focus=").split(",")
			focus = Vector3(float(v[0]), 0, float(v[1])); size = float(v[2])
	camera.size = size
	var hit := map.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(focus+Vector3(0,60,0), focus-Vector3(0,20,0), 1))
	focus.y = hit.get("position", Vector3.ZERO).y
	focus += Profile.CAMERA_FOCUS_OFFSET
	for setup in [[1.0, false], [2.5, false], [2.5, true]]:
		Map.apply_lighting(env, sun)
		sun.directional_shadow_split_1 = 0.1
		sun.directional_shadow_split_2 = 0.2
		sun.directional_shadow_split_3 = 0.5
		var pull: float = setup[0]
		if setup[1]:
			var back := Profile.CAMERA_OFFSET.length()*(pull-1.0)
			var base := sun.directional_shadow_max_distance
			sun.directional_shadow_max_distance = base+back
			sun.directional_shadow_split_1 = (back+base*0.1)/(base+back)
			sun.directional_shadow_split_2 = (back+base*0.2)/(base+back)
			sun.directional_shadow_split_3 = (back+base*0.5)/(base+back)
		camera.position = focus+Profile.CAMERA_OFFSET*pull
		camera.look_at(focus)
		for i in 12: await process_frame
		await RenderingServer.frame_post_draw
		var name := "shadow-%s-%s-%d.png" % [str(pull), "fit" if setup[1] else "raw", int(focus.z)]
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/"+name))
		print("SHOT ", name, " max=", sun.directional_shadow_max_distance, " mode=", sun.directional_shadow_mode)
	quit()
