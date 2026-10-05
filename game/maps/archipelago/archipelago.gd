extends Node3D
## The archipelago from labs/terrain_lab as the game's village map. Terrain, water,
## buildings and props come from the reviewed lab assets (tools/port_archipelago_map.py).
const ROOT := "res://maps/archipelago/"
const TERRAIN := ROOT+"assets/archipelago_terrain_environment_v1.glb"
## Ground and rocks use layer 1, buildings, bridges and piers layer 2, props layer 8.
const WALK_MASK := 1|2|8
const SPRAY_AT := Vector3(.996,0,-7.937)
var camera: Camera3D
var spray: MultiMeshInstance3D
var mist: MultiMeshInstance3D
var water_time := 0.0

static func available() -> bool:
	return ResourceLoader.exists(TERRAIN)

func build(view: Camera3D) -> void:
	camera = view
	var terrain: Node3D = load(TERRAIN).instantiate()
	add_child(terrain)
	var buildings := load(ROOT+"building_layout.gd").new() as Node3D
	buildings.name = "Buildings"
	add_child(buildings)
	buildings.install(self, terrain)
	for item in terrain.find_children("*", "MeshInstance3D", true, false):
		var m := item as MeshInstance3D
		if "__ground" in m.name or "__shore_rock" in m.name or "Waterfall__cliff_rock" in m.name:
			m.create_trimesh_collision()
		if ("Ocean__" in m.name and "seabed" not in m.name) or "__pond" in m.name or "Waterfall__spring_pool" in m.name:
			m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			var water := ShaderMaterial.new()
			water.shader = load(ROOT+"water_surface.gdshader")
			var prefix := "ocean" if "Ocean__" in m.name else "pond"
			water.set_shader_parameter("surface_color", load(ROOT+"assets/v3/"+prefix+"_surface_color.png"))
			water.set_shader_parameter("surface_normal", load(ROOT+"assets/v3/"+prefix+"_surface_normal.png"))
			water.set_shader_parameter("current_field", load(ROOT+"assets/v5/current_field.png"))
			water.set_shader_parameter("coast_field", load(ROOT+"assets/v5/coast_field.png"))
			water.set_shader_parameter("shore_distance", load(ROOT+"assets/v5/shore_distance.png"))
			water.set_shader_parameter("organic_foam", load(ROOT+"assets/v5/organic_foam.png"))
			water.set_shader_parameter("water_kind", 2 if "spring_pool" in m.name else (1 if prefix == "pond" else 0))
			water.set_shader_parameter("pool_center", Vector2(51,-43) if "02_" in m.name else Vector2(-48,44))
			water.set_shader_parameter("pool_radii", Vector2(9,7) if "02_" in m.name else Vector2(12,9))
			m.material_override = water
		if "Waterfall__water_volume" in m.name or "Waterfall__stream_volume_" in m.name:
			var waterfall := ShaderMaterial.new()
			waterfall.shader = load(ROOT+("waterfall.gdshader" if "stream_volume" in m.name else "waterfall_body.gdshader"))
			waterfall.render_priority = 2 if "stream_volume" in m.name else 1
			waterfall.set_shader_parameter("surface_normal", load(ROOT+"assets/v3/pond_surface_normal.png"))
			waterfall.set_shader_parameter("organic_foam", load(ROOT+"assets/v5/organic_foam.png"))
			waterfall.set_shader_parameter("stream_layer", 1.0 if "stream_volume" in m.name else 0.0)
			waterfall.set_shader_parameter("stream_seed", float(String(m.name).get_slice("volume_",1).to_int())*.139)
			m.material_override = waterfall
			m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if "Waterfall__impact_foam" in m.name:
			var splash := ShaderMaterial.new()
			splash.shader = load(ROOT+"waterfall_splash.gdshader")
			splash.render_priority = 3
			splash.set_shader_parameter("organic_foam", load(ROOT+"assets/v5/organic_foam.png"))
			m.material_override = splash
			m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if "Waterfall__source_white_strand" in m.name:
			m.visible = false
		if "__ground" in m.name:
			for i in m.mesh.get_surface_count():
				var source := m.mesh.surface_get_material(i) as StandardMaterial3D
				var mat := ShaderMaterial.new()
				mat.shader = load(ROOT+"ground_surface.gdshader")
				mat.set_shader_parameter("macro_color", source.albedo_texture)
				mat.set_shader_parameter("macro_normal", source.normal_texture)
				for texture_name in ["grass_detail","sand_detail","rock_detail"]:
					mat.set_shader_parameter(texture_name, load(ROOT+"assets/v5/"+texture_name+".png"))
				mat.set_shader_parameter("grass_normal", load(ROOT+"assets/v5/grass_detail_normal.png"))
				mat.set_shader_parameter("sand_normal", load(ROOT+"assets/v5/sand_detail_normal.png"))
				mat.set_shader_parameter("headland_normals", load(ROOT+"assets/v5/headland_normals.png"))
				m.set_surface_override_material(i, mat)
		if "__shore_rock" in m.name or "Waterfall__cliff_rock" in m.name:
			var stone := ShaderMaterial.new()
			stone.shader = load(ROOT+"rock_surface.gdshader")
			stone.set_shader_parameter("rock_detail", load(ROOT+"assets/v5/rock_detail.png"))
			m.material_override = stone
	var props := load(ROOT+"environment_layout.gd").new() as Node3D
	props.name = "Environment"
	add_child(props)
	props.install(self, terrain)
	_create_water_spray()

## Daylight for the islands in the game's Compatibility renderer. The lab's
## Forward+ values (sun 1.15, ACES) wash the meadows out to yellow here; these keep
## the reviewed greens and match the characters' existing lighting.
static func apply_lighting(environment: Environment, sun: DirectionalLight3D) -> void:
	environment.background_color = Color("b8e3ee")
	environment.ambient_light_color = Color("e4eef2")
	environment.ambient_light_energy = 0.36
	environment.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	environment.tonemap_exposure = 1.0
	sun.rotation_degrees = Vector3(-54,-32,0)
	sun.light_color = Color("fff5df")
	sun.light_energy = 0.3
	# A short shadow range keeps the follow view's shadow map sharp and free of acne.
	sun.directional_shadow_max_distance = 45

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
	# The waterfall spray is only worth animating when the camera can see it.
	if camera == null or spray == null or camera.global_position.distance_to(SPRAY_AT) > 60.0:
		return
	for i in spray.multimesh.instance_count:
		var cycle := 1.1+.5*(.5+.5*sin(float(i)*7.1))
		var time := fmod(water_time+float(i)*.731,cycle)
		var angle := float(i) * 2.399
		var launch := 1.7 + .9 * sin(float(i)*3.1)*sin(float(i)*3.1)
		var flight := 2.0 * launch / 9.81
		var spread := .16 + time * (1.3 + .5*sin(float(i)))
		var lateral := sin(float(i)*9.7)*.72
		var at := Vector3(SPRAY_AT.x + lateral*.692 + cos(angle)*spread, .09 + launch*time - .5*9.81*time*time, SPRAY_AT.z - lateral*.722 + sin(angle)*spread)
		var velocity := Vector3(cos(angle)*1.5,launch-9.81*time,sin(angle)*1.5).normalized()
		var right := velocity.cross(Vector3.FORWARD).normalized()
		var orient := Basis(right,velocity,right.cross(velocity).normalized())
		var size := (1.0-smoothstep(flight*.6,flight,time))*(.65+.35*sin(float(i)*4.1)*sin(float(i)*4.1))
		spray.multimesh.set_instance_transform(i, Transform3D(orient.scaled(Vector3.ONE*size), at))
	for i in mist.multimesh.instance_count:
		var phase := fmod(water_time*.38+float(i)/64.0,1.0)
		var angle := float(i)*2.399
		var at := Vector3(SPRAY_AT.x+cos(angle)*(.4+phase*.65),.22+phase*.86,SPRAY_AT.z+sin(angle)*(.4+phase*.65))
		mist.multimesh.set_instance_transform(i,Transform3D(Basis.IDENTITY.scaled(Vector3.ONE*(.55+phase*.78)),at))
		mist.multimesh.set_instance_color(i,Color(1,1,1,sin(phase*PI)*.68))
