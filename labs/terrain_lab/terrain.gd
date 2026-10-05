extends Node3D
## An independent art review scene; no production game, account or server writes.
var camera: Camera3D
var actor: CharacterBody3D
var model: Node3D
var follow := false
var free_camera := false
var free_speed := 24.0
var free_yaw := 0.0
var free_pitch := 0.0
var controls: Label
var map_tour := OS.get_cmdline_user_args().has("--map-tour")
const TOUR_DURATION := 48.0
# Camera and look-at paths stay above the terrain; close views retain the skyline.
var tour_positions := [Vector3(0,112,174), Vector3(-88,39,92), Vector3(-49,24,72), Vector3(7,8,1), Vector3(-8,14,-2), Vector3(72,28,-15), Vector3(51,25,-20), Vector3(94,25,55), Vector3(23,22,109), Vector3(78,80,164)]
var tour_targets := [Vector3(0,0,3), Vector3(-44,1,39), Vector3(-48,1.18,44), Vector3(.4,1.8,-8.1), Vector3(-3,3.5,-10), Vector3(42,1,-39), Vector3(51,1.35,-43), Vector3(46,1,38), Vector3(7,1,78), Vector3(0,0,3)]
var azimuth := 0.0
var elevation := 0.78
var distance := 170.0
var center := Vector3(0, 0, 3)
var building_focus_index := -1
var bridge_focus_index := -1
var bridge_centers := [Vector3(2,2,-36),Vector3(57,2,3),Vector3(3,2,27),Vector3(-11,2,65)]
var building_centers := [Vector3(-42,4,-39), Vector3(46,4,-32), Vector3(-43,5,31), Vector3(49,3,38), Vector3(7,5,78)]
var animation: AnimationPlayer
var status: Label
var frame := 0
var capture := OS.get_cmdline_user_args().has("--capture")
var shore_capture := OS.get_cmdline_user_args().has("--shore-capture")
var lake_capture := OS.get_cmdline_user_args().has("--lake-capture")
var coast_regions_capture := OS.get_cmdline_user_args().has("--coast-regions-capture")
var offshore_capture := OS.get_cmdline_user_args().has("--offshore-capture")
var lake_focus := OS.get_cmdline_user_args().has("--lake-view") or lake_capture
var lake_center := Vector3(51,1.35,-43) if OS.get_cmdline_user_args().has("--northeast-lake") else Vector3(-48,1.18,44)
var audit := OS.get_cmdline_user_args().has("--audit")
var audit_island := 0
var sidefall_capture := OS.get_cmdline_user_args().has("--sidefall-capture")
var backfall_capture := OS.get_cmdline_user_args().has("--backfall-capture")
var waterfall_focus := OS.get_cmdline_user_args().has("--waterfall-view") or OS.get_cmdline_user_args().has("--waterfall-capture") or sidefall_capture or backfall_capture
var waterfall_capture := OS.get_cmdline_user_args().has("--waterfall-capture")
var camera_capture := OS.get_cmdline_user_args().has("--camera-capture")
var perspective := OS.get_cmdline_user_args().has("--perspective")
var frame_samples: Array[float] = []
var spray: MultiMeshInstance3D
var mist: MultiMeshInstance3D
var water_time := 0.0
var spawn_points := [Vector3(-45, 8, -35), Vector3(34, 8, -36), Vector3(-33, 8, 37), Vector3(49, 8, 37), Vector3(2, 8, 79)]

func _ready() -> void:
	if OS.get_cmdline_user_args().has("--performance-benchmark"):
		var profiler := load("res://performance_audit.gd").new() as Node
		add_child(profiler)
		profiler.run.call_deferred(self)
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("b8e3ee")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color("d5e6ee")
	environment.ambient_light_energy = 0.40
	environment.tonemap_mode = Environment.TONE_MAPPER_ACES
	environment.tonemap_exposure = 0.85
	environment.ssao_enabled = true
	environment.ssao_radius = 1.0
	environment.ssao_intensity = 1.2
	environment.fog_enabled = true
	environment.fog_light_color = Color("b8dfe7")
	environment.fog_density = 0.0003
	var world := WorldEnvironment.new()
	world.environment = environment
	add_child(world)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-54, -32, 0)
	sun.light_color = Color("fff5df")
	sun.light_energy = 1.15
	sun.shadow_enabled = true
	sun.shadow_bias = .08
	sun.shadow_normal_bias = 0.35
	sun.directional_shadow_max_distance = 210
	add_child(sun)
	var terrain_path := "res://assets/archipelago_terrain_environment_v1.glb" if FileAccess.file_exists("res://assets/archipelago_terrain_environment_v1.glb") else "res://assets/archipelago_terrain_v6.glb"
	var terrain: Node3D = load(terrain_path).instantiate()
	add_child(terrain)
	var buildings := load("res://building_layout.gd").new() as Node3D
	buildings.name = "ReferenceBuildings"
	add_child(buildings)
	buildings.install(self, terrain)
	for item in terrain.find_children("*", "MeshInstance3D", true, false):
		var m := item as MeshInstance3D
		if "__ground" in m.name or "__shore_rock" in m.name or "Waterfall__cliff_rock" in m.name:
			m.create_trimesh_collision()
		if ("Ocean__" in m.name and "seabed" not in m.name) or "__pond" in m.name or "Waterfall__spring_pool" in m.name:
			m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			var water := ShaderMaterial.new()
			water.shader = load("res://water_surface.gdshader")
			var prefix := "ocean" if "Ocean__" in m.name else "pond"
			water.set_shader_parameter("surface_color", load("res://assets/v3/"+prefix+"_surface_color.png"))
			water.set_shader_parameter("surface_normal", load("res://assets/v3/"+prefix+"_surface_normal.png"))
			water.set_shader_parameter("current_field", load("res://assets/v5/current_field.png"))
			water.set_shader_parameter("coast_field", load("res://assets/v5/coast_field.png"))
			water.set_shader_parameter("shore_distance", load("res://assets/v5/shore_distance.png"))
			water.set_shader_parameter("organic_foam", load("res://assets/v5/organic_foam.png"))
			water.set_shader_parameter("water_kind", 2 if "spring_pool" in m.name else (1 if prefix == "pond" else 0))
			water.set_shader_parameter("debug_view", 1 if OS.get_cmdline_user_args().has("--water-debug") else 0)
			water.set_shader_parameter("pool_center", Vector2(51,-43) if "02_" in m.name else Vector2(-48,44))
			water.set_shader_parameter("pool_radii", Vector2(9,7) if "02_" in m.name else Vector2(12,9))
			m.material_override = water
		if "Waterfall__water_volume" in m.name or "Waterfall__stream_volume_" in m.name:
			var waterfall := ShaderMaterial.new()
			waterfall.shader = load("res://waterfall.gdshader" if "stream_volume" in m.name else "res://waterfall_body.gdshader")
			waterfall.render_priority = 2 if "stream_volume" in m.name else 1
			waterfall.set_shader_parameter("surface_normal", load("res://assets/v3/pond_surface_normal.png"))
			waterfall.set_shader_parameter("organic_foam", load("res://assets/v5/organic_foam.png"))
			waterfall.set_shader_parameter("stream_layer", 1.0 if "stream_volume" in m.name else 0.0)
			waterfall.set_shader_parameter("stream_seed", float(String(m.name).get_slice("volume_",1).to_int())*.139)
			m.material_override = waterfall
			m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if "Waterfall__impact_foam" in m.name:
			var splash := ShaderMaterial.new()
			splash.shader = load("res://waterfall_splash.gdshader")
			splash.render_priority = 3
			splash.set_shader_parameter("organic_foam", load("res://assets/v5/organic_foam.png"))
			m.material_override = splash
			m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if "Waterfall__source_white_strand" in m.name:
			m.visible = false
		if "__ground" in m.name:
			for i in m.mesh.get_surface_count():
				var source := m.mesh.surface_get_material(i) as StandardMaterial3D
				var mat := ShaderMaterial.new()
				mat.shader = load("res://ground_surface.gdshader")
				mat.set_shader_parameter("macro_color", source.albedo_texture)
				mat.set_shader_parameter("macro_normal", source.normal_texture)
				for texture_name in ["grass_detail","sand_detail","rock_detail"]:
					mat.set_shader_parameter(texture_name, load("res://assets/v5/"+texture_name+".png"))
				mat.set_shader_parameter("grass_normal", load("res://assets/v5/grass_detail_normal.png"))
				mat.set_shader_parameter("sand_normal", load("res://assets/v5/sand_detail_normal.png"))
				mat.set_shader_parameter("headland_normals", load("res://assets/v5/headland_normals.png"))
				m.set_surface_override_material(i, mat)
		if "__shore_rock" in m.name or "Waterfall__cliff_rock" in m.name:
			var stone := ShaderMaterial.new()
			stone.shader = load("res://rock_surface.gdshader")
			stone.set_shader_parameter("rock_detail", load("res://assets/v5/rock_detail.png"))
			m.material_override = stone
	if FileAccess.file_exists("res://environment_layout.json"):
		var environment_layout := load("res://environment_layout.gd").new() as Node3D
		environment_layout.name = "ReferenceEnvironment"
		add_child(environment_layout)
		environment_layout.install(self,terrain)
	_create_water_spray()
	actor = CharacterBody3D.new()
	actor.collision_layer = 4
	actor.collision_mask = 11
	actor.floor_snap_length = 0.5
	add_child(actor)
	var capsule := CapsuleShape3D.new()
	capsule.height = 1.7
	capsule.radius = .32
	var shape := CollisionShape3D.new()
	shape.shape = capsule
	shape.position.y = .85
	actor.add_child(shape)
	model = load("res://assets/explorer_b_reference.glb").instantiate()
	actor.add_child(model)
	var bounds := AABB()
	var first := true
	for item in model.find_children("*", "MeshInstance3D", true, false):
		var m := item as MeshInstance3D
		var relative := model.global_transform.affine_inverse() * m.global_transform
		var b: AABB = relative * m.get_aabb()
		bounds = b if first else bounds.merge(b)
		first = false
	if bounds.size.y > .001:
		var scale_factor := 1.7 / bounds.size.y
		model.scale = Vector3.ONE * scale_factor
		model.position = -Vector3(bounds.get_center().x, bounds.position.y, bounds.get_center().z) * scale_factor
	var animations := model.find_children("*", "AnimationPlayer", true, false)
	if not animations.is_empty():
		animation = animations[0]
		if animation.has_animation("idle"):
			animation.play("idle")
	actor.position = spawn_points[2]
	if audit:
		actor.position = spawn_points[0]
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_PERSPECTIVE if perspective else Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 135
	camera.near = 0.35
	camera.far = 6000
	camera.fov = 42
	add_child(camera)
	if waterfall_focus:
		camera.size = 11
		azimuth = .6
		elevation = .55
	if lake_focus:
		camera.size = 25
		azimuth = .15
		elevation = 1.05
	if sidefall_capture:
		camera.size = 9
		azimuth = 1.65
		elevation = .42
	if backfall_capture:
		camera.size = 13
		azimuth = 3.8
		elevation = .62
	if camera_capture:
		camera.size = 190
		azimuth = 2.6
		elevation = .48 if perspective else .38
	if shore_capture:
		actor.position = Vector3(-54,8,66)
		follow = true
		camera.size = 13
		azimuth = -.45
		elevation = .6
	var layer := CanvasLayer.new()
	layer.name = "CanvasLayer"
	add_child(layer)
	var panel := PanelContainer.new()
	panel.position = Vector2(20,20)
	layer.add_child(panel)
	var margin := MarginContainer.new()
	for side in ["left","right","top","bottom"]:
		margin.add_theme_constant_override("margin_"+side,14)
	panel.add_child(margin)
	var column := VBoxContainer.new()
	margin.add_child(column)
	var title := Label.new()
	title.text = "TRIPOTHON  ·  섬과 다리, 정원" if FileAccess.file_exists("res://environment_layout.json") else "TRIPOTHON  ·  레퍼런스 건물 배치"
	title.add_theme_font_size_override("font_size", 24)
	column.add_child(title)
	status = Label.new()
	status.text = "건물 17개 · 섬 5개 · 캐릭터 1.70m"
	if FileAccess.file_exists("res://environment_layout.json"):
		var layout_summary: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://environment_layout.json"))
		status.text = "건물 17개 · 다리 4개 · 소품 %d개 · 캐릭터 1.70m" % layout_summary.instances.size()
	column.add_child(status)
	controls = Label.new()
	column.add_child(controls)
	_update_controls()
	_update_camera()
	if OS.get_cmdline_user_args().has("--free-camera"):
		_set_free_camera(true)
	if map_tour:
		layer.visible = false
		camera.projection = Camera3D.PROJECTION_PERSPECTIVE
		camera.fov = 55
		camera.near = .15
		_update_tour_camera(0.0)
	print("TERRAIN_LAB_READY character_height_m=1.7 islands=5")

func _unhandled_input(event: InputEvent) -> void:
	if map_tour:
		return
	if free_camera and event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_RIGHT:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if event.pressed else Input.MOUSE_MODE_VISIBLE
	if event is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		if free_camera:
			free_yaw -= event.relative.x * .003
			free_pitch = clampf(free_pitch - event.relative.y * .003, -1.55, 1.55)
			camera.rotation = Vector3(free_pitch, free_yaw, 0)
		else:
			azimuth -= event.relative.x * .005
			elevation = clampf(elevation + event.relative.y * .004, .48 if perspective else .38, 1.42)
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			if free_camera:
				free_speed = minf(120, free_speed * 1.25)
			else:
				camera.size = maxf(6, camera.size * .88)
		if event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			if free_camera:
				free_speed = maxf(1, free_speed / 1.25)
			else:
				camera.size = minf(190, camera.size / .88)
		_update_controls()
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_H:
			var guide := get_node_or_null("CanvasLayer")
			if guide:
				guide.visible = not guide.visible
			return
		if event.keycode == KEY_ESCAPE:
			if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
				Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
			elif free_camera:
				_set_free_camera(false)
			else:
				get_tree().quit()
			return
		if event.keycode == KEY_C:
			_set_free_camera(not free_camera)
			return
		if event.keycode in [KEY_P, KEY_L, KEY_TAB, KEY_R, KEY_F, KEY_B] or (event.keycode >= KEY_1 and event.keycode <= KEY_5):
			_set_free_camera(false)
		if event.keycode in [KEY_L, KEY_TAB, KEY_R, KEY_F]:
			building_focus_index = -1
			bridge_focus_index = -1
		if event.keycode == KEY_B and FileAccess.file_exists("res://environment_layout.json"):
			bridge_focus_index = (bridge_focus_index+1)%4
			building_focus_index = -1
			follow = false
			lake_focus = false
			waterfall_focus = false
			camera.size = 34
			azimuth = .6
			elevation = .54
		if event.keycode == KEY_P:
			perspective = not perspective
			camera.projection = Camera3D.PROJECTION_PERSPECTIVE if perspective else Camera3D.PROJECTION_ORTHOGONAL
			if perspective:
				elevation = maxf(elevation,.48)
		if event.keycode == KEY_L:
			lake_center = Vector3(51,1.35,-43) if lake_focus and lake_center.x<0 else Vector3(-48,1.18,44)
			lake_focus = true
			waterfall_focus = false
			follow = false
			camera.size = 25
			azimuth = .15
			elevation = 1.05
		if event.keycode == KEY_TAB:
			lake_focus = false
			waterfall_focus = false
			follow = not follow
			camera.size = 12 if follow else 135
		if event.keycode == KEY_R:
			lake_focus = false
			waterfall_focus = false
			follow = false
			camera.size = 135
			azimuth = 0
			elevation = .78
		if event.keycode == KEY_F:
			lake_focus = false
			waterfall_focus = true
			follow = false
			camera.size = 11
			azimuth = .6
			elevation = .55
		if event.keycode >= KEY_1 and event.keycode <= KEY_5:
			bridge_focus_index = -1
			lake_focus = false
			waterfall_focus = false
			actor.position = spawn_points[event.keycode - KEY_1]
			actor.velocity = Vector3.ZERO
			follow = false
			building_focus_index = event.keycode - KEY_1
			camera.size = 22 if building_focus_index == 4 else 66
			azimuth = -.12
			elevation = .74

func _physics_process(delta: float) -> void:
	if actor == null:
		return
	if free_camera and DisplayServer.window_is_focused():
		var camera_input := Vector3(float(Input.is_physical_key_pressed(KEY_D))-float(Input.is_physical_key_pressed(KEY_A)), float(Input.is_physical_key_pressed(KEY_E))-float(Input.is_physical_key_pressed(KEY_Q)), float(Input.is_physical_key_pressed(KEY_S))-float(Input.is_physical_key_pressed(KEY_W)))
		var multiplier := 3.0 if Input.is_physical_key_pressed(KEY_SHIFT) else (.25 if Input.is_physical_key_pressed(KEY_ALT) else 1.0)
		_move_free_camera(delta, camera_input, multiplier)
	var input := Vector2(float(Input.is_physical_key_pressed(KEY_D))-float(Input.is_physical_key_pressed(KEY_A)), float(Input.is_physical_key_pressed(KEY_S))-float(Input.is_physical_key_pressed(KEY_W)))
	if not follow or free_camera:
		input = Vector2.ZERO
	var direction := camera.global_basis.x * input.x + Vector3(camera.global_basis.z.x, 0, camera.global_basis.z.z).normalized() * input.y
	direction.y = 0
	direction = direction.normalized()
	var speed := 4.5 if Input.is_physical_key_pressed(KEY_SHIFT) else 2.8
	actor.velocity.x = direction.x * speed
	actor.velocity.z = direction.z * speed
	if not actor.is_on_floor():
		actor.velocity.y -= 20 * delta
	else:
		actor.velocity.y = -.1
	if direction.length_squared() > .01:
		model.rotation.y = atan2(-direction.x, -direction.z)
	var previous := actor.position
	actor.move_and_slide()
	if actor.position.y < .45:
		actor.position = previous
		actor.velocity = Vector3.ZERO
	_update_camera()
	frame += 1
	if frame == 90 or (audit and frame > 90 and (frame-90) % 60 == 0):
		print("TERRAIN_GROUND_CHECK grounded=", actor.is_on_floor(), " position=", actor.position)
		if audit:
			if not actor.is_on_floor():
				get_tree().quit(1)
				return
			audit_island += 1
			if audit_island == 5:
				_verify_relief()
				print("TERRAIN_AUDIT_PASS all_five_islands_grounded")
				get_tree().quit()
				return
			actor.position = spawn_points[audit_island]
			actor.velocity = Vector3.ZERO
		if capture or shore_capture or waterfall_capture or camera_capture or sidefall_capture or backfall_capture or lake_capture or coast_regions_capture or offshore_capture:
			_capture.call_deferred()

func _update_camera() -> void:
	if free_camera or map_tour:
		return
	center = Vector3(.4,1.6,-8.1) if waterfall_focus else (actor.position + Vector3(0,.7,0) if follow else Vector3(0,0,3))
	if building_focus_index >= 0:
		center = building_centers[building_focus_index]
	if bridge_focus_index >= 0:
		center = bridge_centers[bridge_focus_index]
	if lake_focus:
		center = lake_center
	if offshore_capture:
		center = Vector3(290,0,20)
	# Orthographic rays at low pitch can cross the sea behind the camera.
	# Move the orbit back as the framing grows; the near plane then stays clear.
	var d := camera.size * 1.55 if perspective else maxf(40.0 if follow or waterfall_focus else distance, camera.size/(2.0*tan(elevation))+35.0)
	camera.position = center + Vector3(sin(azimuth)*cos(elevation), sin(elevation), cos(azimuth)*cos(elevation)) * d
	camera.look_at(center)

func _set_free_camera(enabled: bool) -> void:
	free_camera = enabled
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	if enabled:
		free_yaw = camera.rotation.y
		free_pitch = camera.rotation.x
		camera.projection = Camera3D.PROJECTION_PERSPECTIVE
		camera.fov = 55
		camera.near = .12
	else:
		camera.projection = Camera3D.PROJECTION_PERSPECTIVE if perspective else Camera3D.PROJECTION_ORTHOGONAL
		camera.fov = 42
		camera.near = .35
		_update_camera()
	_update_controls()

func _move_free_camera(delta: float, movement: Vector3, multiplier: float = 1.0) -> void:
	var direction := camera.global_basis.x * movement.x + Vector3.UP * movement.y + camera.global_basis.z * movement.z
	camera.global_position += direction.normalized() * free_speed * multiplier * delta

func _update_controls() -> void:
	if controls == null:
		return
	if free_camera:
		status.text = "자유 카메라 · 속도 %d m/s" % free_speed
		controls.text = "WASD: 이동 · Q/E: 하강/상승 · 오른쪽 드래그: 시점\nShift: 빠르게 · Alt: 천천히 · 휠: 속도 · C: 카메라 전환\n1–5: 섬 · B: 다리 · R: 전체 · H: 안내 숨기기"
	else:
		status.text = "건물 17개 · 섬 5개 · 캐릭터 1.70m"
		controls.text = "C: 자유 카메라 · 오른쪽 드래그: 회전 · 휠: 확대\n1–5: 섬 · B: 다리 · R: 전체 · H: 안내 숨기기\nTab: 산책 · WASD: 이동 · L: 호수 · F: 폭포 · P: 원근"

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func _tour_curve(points: Array, segment: int, weight: float) -> Vector3:
	var a: Vector3 = points[maxi(segment - 1, 0)]
	var b: Vector3 = points[segment]
	var c: Vector3 = points[mini(segment + 1, points.size() - 1)]
	var d: Vector3 = points[mini(segment + 2, points.size() - 1)]
	return .5 * ((2.0 * b) + (-a + c) * weight + (2.0*a - 5.0*b + 4.0*c - d) * weight*weight + (-a + 3.0*b - 3.0*c + d) * weight*weight*weight)

func _update_tour_camera(elapsed: float) -> void:
	var progress := clampf(elapsed / TOUR_DURATION, 0, 1)
	# Ease only the beginning/end; each intermediate stop remains continuous.
	progress = progress * progress * (3.0 - 2.0 * progress)
	var path_time := progress * (tour_positions.size() - 1)
	var segment := mini(int(path_time), tour_positions.size() - 2)
	var weight := path_time - segment
	camera.global_position = _tour_curve(tour_positions, segment, weight)
	camera.look_at(_tour_curve(tour_targets, segment, weight))

func _capture() -> void:
	await RenderingServer.frame_post_draw
	var filename := ("terrain_camera_perspective_godot.png" if perspective else "terrain_camera_godot.png") if camera_capture else ("waterfall_godot.png" if waterfall_capture else ("terrain_scale_godot.png" if shore_capture else "terrain_godot.png"))
	if sidefall_capture:
		filename = "waterfall_side_godot.png"
	if backfall_capture:
		filename = "headland_back_godot.png"
	if lake_capture:
		filename = "lake_northeast_godot.png" if OS.get_cmdline_user_args().has("--northeast-lake") else "lake_southwest_godot.png"
	if coast_regions_capture:
		filename = "coast_regions_godot.png"
	if offshore_capture:
		filename = "offshore_godot.png"
	var path := ProjectSettings.globalize_path("res://../../art/maps/archipelago_terrain_v6/" + filename)
	get_viewport().get_texture().get_image().save_png(path)
	print("TERRAIN_CAPTURE ", path)
	if waterfall_capture or shore_capture or sidefall_capture or lake_capture:
		await get_tree().create_timer(2.0).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(path.replace(".png", "_after_2s.png"))
	if coast_regions_capture:
		var timestamps: Array[float] = [water_time]
		for second in range(1,9):
			await get_tree().create_timer(1.0).timeout
			await RenderingServer.frame_post_draw
			get_viewport().get_texture().get_image().save_png(path.replace(".png", "_%02ds.png" % second))
			timestamps.append(water_time)
		var timing := FileAccess.open(path.replace(".png","_timing.json"),FileAccess.WRITE)
		timing.store_string(JSON.stringify(timestamps,"  "))
	if not frame_samples.is_empty():
		var sorted := frame_samples.duplicate()
		sorted.sort()
		var total := 0.0
		for value in sorted:
			total += value
		var result := {"rendered_frames":sorted.size(),"mean_frame_ms":total/float(sorted.size())*1000.0,"p95_frame_ms": sorted[int(float(sorted.size()-1)*.95)]*1000.0,"reported_fps":Engine.get_frames_per_second(),"viewport":get_viewport().get_visible_rect().size}
		var file := FileAccess.open(path.replace(".png","_performance.json"),FileAccess.WRITE)
		file.store_string(JSON.stringify(result,"  "))
		print("TERRAIN_RENDER_PERFORMANCE ", result)
	get_tree().quit()

func _verify_relief() -> void:
	var samples := {"grass": Vector3(-31,10,22), "pond_bottom": Vector3(-48,10,44), "sand_beach": Vector3(-54,10,69.5), "coastal_bank": Vector3(-54,10,66)}
	var heights := {}
	for id in samples:
		var point: Vector3 = samples[id]
		var query := PhysicsRayQueryParameters3D.create(point, point-Vector3(0,30,0), 1, [actor.get_rid()])
		var hit := get_world_3d().direct_space_state.intersect_ray(query)
		if not hit.is_empty():
			heights[id] = hit.position.y
	var valid: bool = heights.has("grass") and heights.has("pond_bottom") and heights["grass"]-heights["pond_bottom"] > 1.5
	var submerged := {}
	var coast_samples := {"northwest": Vector3(-42,10,-70), "northeast": Vector3(50,10,-68), "southwest": Vector3(-54,10,74), "southeast": Vector3(49,10,73), "lighthouse": Vector3(7,10,91)}
	for id in coast_samples:
		var point: Vector3 = coast_samples[id]
		var query := PhysicsRayQueryParameters3D.create(point,point-Vector3(0,30,0),1,[actor.get_rid()])
		var hit := get_world_3d().direct_space_state.intersect_ray(query)
		if not hit.is_empty():
			submerged[id] = hit.position.y
			valid = valid and hit.position.y < -0.15
		else:
			valid = false
	print("TERRAIN_SUBMERGED_SKIRT_CHECK ", submerged, " pass=",valid)
	print("TERRAIN_RELIEF_CHECK ", heights, " pass=", valid)
	var path := ProjectSettings.globalize_path("res://../../art/maps/archipelago_terrain_v6/verification.json")
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify({"all_five_islands_grounded": true, "sample_heights_m": heights, "submerged_coast_heights_m":submerged,"relief_pass": valid}, "  "))
	assert(valid, "Terrain relief check failed")

func _create_water_spray() -> void:
	spray = MultiMeshInstance3D.new()
	var drops := MultiMesh.new()
	drops.transform_format = MultiMesh.TRANSFORM_3D
	var droplet := CapsuleMesh.new()
	droplet.radius = .006
	droplet.height = .065
	droplet.radial_segments = 8
	droplet.rings = 2
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(.78,.94,.96,.62)
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.render_priority = 4
	material.roughness = 0.23
	droplet.material = material
	drops.mesh = droplet
	drops.instance_count = 112
	spray.multimesh = drops
	spray.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(spray)
	var gradient := Gradient.new()
	gradient.offsets = PackedFloat32Array([0.0,0.5,1.0])
	gradient.colors = PackedColorArray([Color(0.85,0.96,0.97,0.16),Color(0.85,0.96,0.97,0.04),Color(0.85,0.96,0.97,0)])
	var soft := GradientTexture2D.new()
	soft.gradient = gradient
	soft.width = 128
	soft.height = 128
	soft.fill = GradientTexture2D.FILL_RADIAL
	soft.fill_from = Vector2(.5,.5)
	soft.fill_to = Vector2(1,.5)
	var haze := StandardMaterial3D.new()
	haze.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	haze.render_priority = 4
	haze.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	haze.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	haze.vertex_color_use_as_albedo = true
	haze.albedo_texture = soft
	haze.no_depth_test = false
	var puff := QuadMesh.new()
	puff.material = haze
	puff.size = Vector2.ONE
	var puffs := MultiMesh.new()
	puffs.transform_format = MultiMesh.TRANSFORM_3D
	puffs.use_colors = true
	puffs.mesh = puff
	puffs.instance_count = 64
	mist = MultiMeshInstance3D.new()
	mist.multimesh = puffs
	mist.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mist)

func _process(delta: float) -> void:
	water_time += delta
	if map_tour:
		_update_tour_camera(water_time)
		if water_time >= TOUR_DURATION:
			print("TERRAIN_MAP_TOUR_COMPLETE seconds=", TOUR_DURATION)
			get_tree().quit()
	if frame>30 and (capture or shore_capture or waterfall_capture or camera_capture or sidefall_capture or backfall_capture or lake_capture or coast_regions_capture or offshore_capture):
		frame_samples.append(delta)
	if spray == null:
		return
	for i in spray.multimesh.instance_count:
		var cycle := 1.1+.5*(.5+.5*sin(float(i)*7.1))
		var time := fmod(water_time+float(i)*.731,cycle)
		var angle := float(i) * 2.399
		var launch := 1.7 + .9 * sin(float(i)*3.1)*sin(float(i)*3.1)
		var flight := 2.0 * launch / 9.81
		var spread := .16 + time * (1.3 + .5*sin(float(i)))
		var lateral := sin(float(i)*9.7)*.72
		var position := Vector3(.996 + lateral*.692 + cos(angle)*spread, .09 + launch*time - .5*9.81*time*time, -7.937 - lateral*.722 + sin(angle)*spread)
		var velocity := Vector3(cos(angle)*1.5,launch-9.81*time,sin(angle)*1.5).normalized()
		var right := velocity.cross(Vector3.FORWARD).normalized()
		var orient := Basis(right,velocity,right.cross(velocity).normalized())
		var size := (1.0-smoothstep(flight*.6,flight,time))*(.65+.35*sin(float(i)*4.1)*sin(float(i)*4.1))
		spray.multimesh.set_instance_transform(i, Transform3D(orient.scaled(Vector3.ONE*size), position))
	for i in mist.multimesh.instance_count:
		var phase := fmod(water_time*.38+float(i)/64.0,1.0)
		var angle := float(i)*2.399
		var position := Vector3(.996+cos(angle)*(.4+phase*.65),.22+phase*.86,-7.937+sin(angle)*(.4+phase*.65))
		var size := .55+phase*.78
		mist.multimesh.set_instance_transform(i,Transform3D(Basis.IDENTITY.scaled(Vector3.ONE*size),position))
		mist.multimesh.set_instance_color(i,Color(1,1,1,sin(phase*PI)*.68))
