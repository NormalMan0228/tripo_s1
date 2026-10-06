extends SceneTree
## Renders head-and-shoulder portraits of the four player characters for the HUD frame.
func _initialize() -> void: call_deferred("run")
func run() -> void:
	for id in ["explorer_b","explorer","ranger","tinker"]:
		var frame := SubViewport.new()
		frame.size = Vector2i(768,768)
		frame.transparent_bg = true
		frame.own_world_3d = true
		frame.msaa_3d = Viewport.MSAA_4X
		frame.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		root.add_child(frame)
		var stage := Node3D.new()
		frame.add_child(stage)
		var env := WorldEnvironment.new()
		env.environment = Environment.new()
		env.environment.background_mode = Environment.BG_CLEAR_COLOR
		env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		env.environment.ambient_light_color = Color.WHITE
		env.environment.ambient_light_energy = 0.75
		stage.add_child(env)
		var light := DirectionalLight3D.new()
		light.rotation_degrees = Vector3(-25,-35,0)
		light.light_energy = 0.9
		stage.add_child(light)
		var actor: CharacterBody3D = preload("res://scripts/player.gd").new()
		actor.avatar = {"character":id}
		actor.controls_enabled = false
		actor.visual_only = true
		stage.add_child(actor)
		actor.facing = Vector3(0,0,1)
		actor.visual.rotation.y = PI
		if actor.animation_player and actor.animation_player.has_animation("idle"): actor.animation_player.play("idle")
		var camera := Camera3D.new()
		camera.projection = Camera3D.PROJECTION_ORTHOGONAL
		camera.size = 0.62
		stage.add_child(camera)
		for i in 6: await process_frame
		# Frame the head: the top of the character's meshes minus a little.
		var whole := AABB()
		var first := true
		for node in actor.visual.find_children("*","MeshInstance3D",true,false):
			if not node.visible: continue
			var box: AABB = node.global_transform*node.get_aabb()
			whole = box if first else whole.merge(box)
			first = false
		var height := whole.size.y
		var head := Vector3(whole.get_center().x, whole.end.y-height*0.32, 0)
		camera.size = height*0.75
		camera.position = head+Vector3(0,0.02,2)
		camera.look_at(head)
		camera.current = true
		for i in 20: await process_frame
		await RenderingServer.frame_post_draw
		var path := ProjectSettings.globalize_path("res://assets/ui/portrait_%s.png" % id)
		print("PORTRAIT ", id, " ", frame.get_texture().get_image().save_png(path))
		frame.queue_free()
	quit()
