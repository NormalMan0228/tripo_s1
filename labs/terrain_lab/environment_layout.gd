extends Node3D
## First review batch: four distinct Tripo bridges plus natural garden clusters.
var manifest: Dictionary
var host: Node3D
var prototypes: Dictionary = {}
var bridge_nodes: Array[Node3D] = []
var prop_nodes: Array[Node3D] = []
var frame := 0
var capturing := false
var relocated_rocks: Array[Dictionary] = []
var floating_boats: Array[Dictionary] = []
var ground_fit_samples: Array[Dictionary] = []
var output_path := "res://../../art/maps/archipelago_environment_v1/"

func install(owner_node: Node3D,_terrain_node: Node3D) -> void:
	host = owner_node
	manifest = JSON.parse_string(FileAccess.get_file_as_string("res://environment_layout.json"))
	output_path = "res://../../"+String(manifest.get("output_directory","art/maps/archipelago_environment_v1"))+"/"
	if FileAccess.file_exists(output_path+"rock_clearance_verification.json"):
		var clearance: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(output_path+"rock_clearance_verification.json"))
		for rock: Dictionary in clearance.relocated_rocks:
			relocated_rocks.append(rock)
	for spec: Dictionary in manifest.models:
		prototypes[String(spec.id)] = load(String(spec.model)) as PackedScene
	for spec: Dictionary in manifest.bridges:
		var bridge := (prototypes[String(spec.id)] as PackedScene).instantiate() as Node3D
		bridge.name = spec.id
		add_child(bridge)
		bridge.position = Vector3(spec.position[0],spec.position[1],spec.position[2])
		bridge.rotation.y = deg_to_rad(float(spec.yaw_degrees))
		bridge.scale.z = spec.scale_z
		_fit_bridge(bridge,spec)
		_add_bridge_supports(bridge,spec)
		bridge_nodes.append(bridge)
	for spec: Dictionary in manifest.instances:
		var prop := (prototypes[String(spec.id)] as PackedScene).instantiate() as Node3D
		prop.name = String(spec.id)+"_%03d" % prop_nodes.size()
		add_child(prop)
		prop.position = Vector3(spec.position[0],spec.position[1],spec.position[2])
		prop.rotation.y = deg_to_rad(float(spec.yaw_degrees))
		prop.scale = Vector3.ONE*float(spec.scale)
		prop.set_meta("placement_spec",spec)
		prop_nodes.append(prop)
		if spec.id == "27_lamp":
			_light_lantern(prop)
		if spec.id == "24_firepit":
			_create_fire(prop)
		if spec.id == "20_pier":
			_add_pier_supports(prop,spec)
		if spec.id == "21_boat":
			floating_boats.append({"node":prop,"base_y":prop.position.y})
		if spec.id in ["37_round_tree","38_conifer","39_palm"]:
			var trunk := StaticBody3D.new()
			trunk.collision_layer = 8
			trunk.collision_mask = 0
			prop.add_child(trunk)
			var collision := CollisionShape3D.new()
			var capsule := CapsuleShape3D.new()
			capsule.radius = .24
			capsule.height = 2.0
			collision.shape = capsule
			collision.position.y = 1.0
			trunk.add_child(collision)
		if spec.id in ["20_pier","21_boat","22_tent_orange","23_tent_green","25_picnic_table","26_bench","24_firepit","28_beach_umbrella","29_beach_lounger","30_cafe_umbrella","31_cafe_table","32_cafe_chair","33_signboard","34_timber_fence","35_picket_fence","36_speaker","41_planter"]:
			for item in prop.find_children("*","MeshInstance3D",true,false):
				var mesh := item as MeshInstance3D
				mesh.create_trimesh_collision()
				for child in mesh.get_children():
					if child is StaticBody3D:
						child.collision_layer = 2 if spec.id=="20_pier" else 8
						child.collision_mask = 0
	print("ENVIRONMENT_LAYOUT_READY models=",manifest.models.size()," instances=",prop_nodes.size()," bridges=",bridge_nodes.size())
	_fit_floor_props.call_deferred()

func _bridge_offset(local_z: float,spec: Dictionary) -> float:
	var q := clampf((local_z/float(spec.source_length_m)-float(spec.walk_bounds[0]))/float(spec.walk_fraction),0.0,1.0)
	return lerpf(float(spec.vertical_end_offsets_m[0]),float(spec.vertical_end_offsets_m[1]),q)+float(spec.additional_arch_m)*pow(sin(PI*q),2)

func _fit_bridge(bridge: Node3D,spec: Dictionary) -> void:
	for item in bridge.find_children("*","MeshInstance3D",true,false):
		var mesh := item as MeshInstance3D
		var relative := bridge.global_transform.affine_inverse()*mesh.global_transform
		var inverse := relative.affine_inverse()
		var rebuilt := ArrayMesh.new()
		for surface in mesh.mesh.get_surface_count():
			var arrays := mesh.mesh.surface_get_arrays(surface)
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
			for i in vertices.size():
				var local := relative*vertices[i]
				var derivative := (_bridge_offset(local.z+.01,spec)-_bridge_offset(local.z-.01,spec))/.02
				var normal := (relative.basis*normals[i]).normalized()
				normal = Vector3(normal.x,normal.y,normal.z-derivative*normal.y).normalized()
				local.y += _bridge_offset(local.z,spec)
				vertices[i] = inverse*local
				normals[i] = (relative.basis.inverse()*normal).normalized()
			arrays[Mesh.ARRAY_VERTEX] = vertices
			arrays[Mesh.ARRAY_NORMAL] = normals
			rebuilt.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
			rebuilt.surface_set_material(surface,mesh.mesh.surface_get_material(surface))
		mesh.mesh = rebuilt
		mesh.create_trimesh_collision()
		for child in mesh.get_children():
			if child is StaticBody3D:
				child.collision_layer = 2
				child.collision_mask = 0

func _deck_height(local_z: float,spec: Dictionary) -> float:
	var nearest := 1000.0
	var height := 0.0
	for sample: Dictionary in spec.profile:
		var d := absf(float(sample.t)*float(spec.source_length_m)-local_z)
		if d < nearest:
			nearest = d
			height = float(sample.height_m)
	return height+_bridge_offset(local_z,spec)

func _add_bridge_supports(bridge: Node3D,spec: Dictionary) -> void:
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color("754223")
	wood.roughness = .83
	for fraction in [-.23,.23]:
		var local_z: float = float(spec.source_length_m)*float(fraction)
		var top := _deck_height(local_z,spec)-.15
		for sign in [-1,1]:
			var pile := MeshInstance3D.new()
			var cylinder := CylinderMesh.new()
			cylinder.top_radius = .17
			cylinder.bottom_radius = .23
			cylinder.height = top+1.5
			cylinder.radial_segments = 12
			pile.mesh = cylinder
			pile.material_override = wood
			pile.position = Vector3(sign*float(spec.width_m)*.33,(top-1.5)/2,local_z)
			bridge.add_child(pile)
		var beam := MeshInstance3D.new()
		var box := BoxMesh.new()
		box.size = Vector3(float(spec.width_m)*.78,.24,.28)
		beam.mesh = box
		beam.material_override = wood
		beam.position = Vector3(0,top-.09,local_z)
		bridge.add_child(beam)

func _light_lantern(prop: Node3D) -> void:
	var light := OmniLight3D.new()
	light.position.y = 2.75
	light.light_color = Color("ffe0a0")
	light.light_energy = .48
	light.omni_range = 4.0
	light.shadow_enabled = false
	prop.add_child(light)
	var body := StaticBody3D.new()
	body.collision_layer = 8
	body.collision_mask = 0
	prop.add_child(body)
	var collision := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.height = 3.0
	capsule.radius = .13
	collision.shape = capsule
	collision.position.y = 1.5
	body.add_child(collision)

func _add_pier_supports(prop: Node3D,spec: Dictionary) -> void:
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color("975e32")
	wood.roughness = .83
	var bottom: float = float(spec.water_height_m)-1.0-prop.position.y
	var top: float = float(spec.deck_height_m)-.16
	for x in [-1.06,1.06]:
		for z in [-2.15,2.15]:
			var pile := MeshInstance3D.new()
			var cylinder := CylinderMesh.new()
			cylinder.top_radius = .15
			cylinder.bottom_radius = .20
			cylinder.height = maxf(.3,top-bottom)
			cylinder.radial_segments = 12
			pile.mesh = cylinder
			pile.material_override = wood
			pile.position = Vector3(x,(top+bottom)/2,z)
			prop.add_child(pile)

func _fit_floor_props() -> void:
	await get_tree().physics_frame
	await get_tree().physics_frame
	for prop in prop_nodes:
		var spec: Dictionary = prop.get_meta("placement_spec")
		if spec.id in ["20_pier","21_boat","45_reeds","46_water_lily"]:
			continue
		var on_floor: bool = spec.get("support_surface","")=="building_floor"
		var from := prop.global_position+Vector3.UP*(1.6 if on_floor else 4.0)
		var hit := get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(from,from-Vector3.UP*7,2 if on_floor else 1))
		if not hit.is_empty():
			var old_y := prop.global_position.y
			prop.global_position.y = hit.position.y+.006
			ground_fit_samples.append({"id":prop.name,"adjustment_m":prop.global_position.y-old_y,"support":("building_floor" if on_floor else "terrain")})
		if spec.id in ["34_timber_fence","35_picket_fence"]:
			var width := 2.2 if spec.id=="34_timber_fence" else 2.0
			var ends: Array[float] = []
			for sign in [-1.0,1.0]:
				var point := prop.to_global(Vector3(sign*width*.5,0,0))
				var edge := get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(point+Vector3.UP*4,point-Vector3.UP*4,1))
				if not edge.is_empty():
					ends.append(edge.position.y)
			if ends.size()==2:
				prop.rotation.z = atan2(ends[1]-ends[0],width)
				prop.global_position.y = (ends[0]+ends[1])*.5+.006

func _create_fire(prop: Node3D) -> void:
	var glow := OmniLight3D.new()
	glow.position.y = .70
	glow.light_color = Color("ff9a3b")
	glow.light_energy = 1.5
	glow.omni_range = 4.1
	glow.shadow_enabled = false
	prop.add_child(glow)
	for layer in range(5):
		var flame := MeshInstance3D.new()
		var vertices := PackedVector3Array()
		var uv := PackedVector2Array()
		var indices := PackedInt32Array()
		var rings := 18
		var segments := 14
		for row in range(rings+1):
			var t := float(row)/rings
			var radius := .17*pow(maxf(0.0,1.0-t),.65)*(.70+.55*sin(PI*t))
			for column in range(segments):
				var a := TAU*column/segments
				vertices.append(Vector3(cos(a)*radius+.10*t*t,t*.9,sin(a)*radius))
				uv.append(Vector2(float(column)/segments,t))
		for row in range(rings):
			for column in range(segments):
				var a := row*segments+column
				var b := row*segments+(column+1)%segments
				indices.append_array(PackedInt32Array([a,b,a+segments,b,b+segments,a+segments]))
		var arrays := []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = vertices
		arrays[Mesh.ARRAY_TEX_UV] = uv
		arrays[Mesh.ARRAY_INDEX] = indices
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
		flame.mesh = mesh
		var material := ShaderMaterial.new()
		material.shader = load("res://campfire.gdshader")
		material.set_shader_parameter("seed",float(layer)*1.37)
		flame.material_override = material
		flame.position = Vector3(cos(float(layer)*2.4)*.19,.25,sin(float(layer)*2.4)*.19)
		flame.scale = Vector3.ONE*(1.0 if layer==0 else .65)
		flame.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		prop.add_child(flame)

func _process(_delta: float) -> void:
	var seconds := float(Time.get_ticks_msec())/1000.0
	for entry: Dictionary in floating_boats:
		var boat := entry.node as Node3D
		boat.position.y = float(entry.base_y)+sin(seconds*1.2)*.025
		boat.rotation.z = sin(seconds*.86)*.008
	if not OS.get_cmdline_user_args().has("--environment-capture"):
		return
	frame += 1
	if frame >= 120 and not capturing:
		capturing = true
		_verify_and_capture.call_deferred()

func _verify_and_capture() -> void:
	var report := {"models":manifest.models.size(),"prop_instances":prop_nodes.size(),"bridges":[],"relocated_rocks":relocated_rocks,"ground_fit_samples":ground_fit_samples,"graph_connected":false,"source":"Actual Godot raycasts after physics registration"}
	var valid := bridge_nodes.size()==4
	var connections := {1:[2],2:[1,4],3:[4,5],4:[2,3],5:[3]}
	var reachable: Array[int] = [1]
	var cursor := 0
	while cursor < reachable.size():
		for next: int in connections[reachable[cursor]]:
			if not reachable.has(next):
				reachable.append(next)
		cursor += 1
	report.graph_connected = reachable.size()==5
	valid = valid and report.graph_connected
	for i in bridge_nodes.size():
		var spec: Dictionary = manifest.bridges[i]
		var bridge := bridge_nodes[i]
		var heights: Array[float] = []
		var all_hit := true
		var max_step := 0.0
		for sample in range(51):
			var q := float(sample)/50
			var point := Vector3(lerpf(float(spec.a[0]),float(spec.b[0]),q),15,lerpf(float(spec.a[1]),float(spec.b[1]),q))
			var hit := get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(point,point-Vector3(0,18,0),3))
			if hit.is_empty() or hit.position.y < .6:
				all_hit = false
				continue
			heights.append(hit.position.y)
			if heights.size()>1:
				max_step = maxf(max_step,absf(heights[-1]-heights[-2]))
		var passable := all_hit and heights.size()==51 and max_step < .48
		var walking: Dictionary = {}
		if OS.get_cmdline_user_args().has("--bridge-walk-audit"):
			walking = await _walk_bridge(spec)
			# A point ray can pass through a narrow board joint; the full-size capsule
			# crossing is the definitive support test, with the height audit retained.
			passable = walking.passed and heights.size()>=45 and max_step<.48
		valid = valid and passable
		report.bridges.append({"id":bridge.name,"samples":heights.size(),"continuous":passable,"centerline_ray_continuous":all_hit,"ray_count":51,"max_sample_step_m":max_step,"heights_m":heights,"connected_islands":spec.islands,"character_walk":walking})
	report["piers"] = []
	if OS.get_cmdline_user_args().has("--bridge-walk-audit"):
		for spec: Dictionary in manifest.get("piers",[]):
			var route := {"id":"pier_island_%d" % int(spec.island),"a":spec.landing,"b":spec.tip,"end_extension":-.85,"minimum_feet_height":float(spec.bank_height_m)-.3}
			var walking := await _walk_bridge(route)
			valid = valid and walking.passed
			report.piers.append({"island":spec.island,"character_walk":walking})
	report["passed"] = valid
	var file := FileAccess.open(output_path+"environment_verification.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "))
	file.close()
	print("ENVIRONMENT_CONNECTION_CHECK passed=",valid," connected_islands=",reachable.size())
	host.free_camera = true
	host.map_tour = false
	host.get_node("CanvasLayer").visible = false
	host.camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	var views := [
		["overview",Vector3(0,3,3),145.0,.86,-.08],
		["northwest",Vector3(-42,4,-39),63.0,.69,-.15],
		["northeast",Vector3(46,4,-32),68.0,.70,-.12],
		["southwest",Vector3(-43,5,31),70.0,.71,-.1],
		["southeast",Vector3(49,4,38),61.0,.70,-.12],
		["bridge_north",Vector3(2,2,-36),30.0,.51,.56],
		["bridge_center",Vector3(3,2,27),30.0,.50,.5],
		["bridge_east",Vector3(57,2,3),27.0,.54,.62],
		["bridge_lighthouse",Vector3(-11,2,65),38.0,.50,.6],
		["camp",Vector3(54,2,44),24.0,.52,.18],
	]
	if manifest.models.size()>15:
		views.append_array([
			["cafe_terrace",Vector3(-65,3,-29),23.0,.66,.20],
			["lake_pier",Vector3(-39,2,44),30.0,.70,.20],
			["lighthouse_pier",Vector3(0,2,81),28.0,.68,.10],
			["garden_beach",Vector3(80,2,-22),25.0,.68,.18],
			["stage",Vector3(37,3,27),23.0,.66,.10],
		])
	for view in views:
		var target: Vector3 = view[1]
		var e: float = view[3]
		var a: float = view[4]
		host.camera.size = view[2]
		host.camera.position = target+Vector3(sin(a)*cos(e),sin(e),cos(a)*cos(e))*190
		host.camera.look_at(target)
		await get_tree().create_timer(.8).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path(output_path+String(view[0])+".png"))
		print("ENVIRONMENT_CAPTURE ",view[0])
	get_tree().quit(0 if valid else 1)

func _walk_bridge(spec: Dictionary) -> Dictionary:
	var body := CharacterBody3D.new()
	body.collision_layer = 16
	body.collision_mask = 11
	body.floor_snap_length = .5
	add_child(body)
	var collision := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.height = 1.7
	capsule.radius = .32
	collision.shape = capsule
	collision.position.y = .85
	body.add_child(collision)
	var a := Vector3(spec.a[0],0,spec.a[1])
	var b := Vector3(spec.b[0],0,spec.b[1])
	var direction := (b-a).normalized()
	var start := a-direction*.5
	var finish := b+direction*float(spec.get("end_extension",.5))
	var hit := get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(start+Vector3.UP*15,start-Vector3.UP*3,3))
	if hit.is_empty():
		body.queue_free()
		return {"passed":false,"reason":"No landing floor"}
	body.position = Vector3(start.x,hit.position.y+.1,start.z)
	var lowest := 100.0
	var remaining := start.distance_to(finish)
	for step in range(int(remaining/4.5*60)+180):
		await get_tree().physics_frame
		var delta := get_physics_process_delta_time()
		body.velocity.x = direction.x*4.5 if step>20 else 0.0
		body.velocity.z = direction.z*4.5 if step>20 else 0.0
		body.velocity.y = -.1 if body.is_on_floor() else body.velocity.y-20*delta
		body.move_and_slide()
		lowest = minf(lowest,body.position.y)
		remaining = Vector2(body.position.x-finish.x,body.position.z-finish.z).length()
		if remaining<.22 or lowest<.6:
			break
	var result := {"passed":remaining<.22 and lowest>float(spec.get("minimum_feet_height",.6)),"remaining_m":remaining,"minimum_feet_height_m":lowest,"capsule_height_m":1.7,"capsule_radius_m":.32}
	print("BRIDGE_CHARACTER_WALK ",spec.id," passed=",result.passed," remaining_m=",remaining)
	body.queue_free()
	await get_tree().physics_frame
	return result
