extends Node3D
## The archipelago from labs/terrain_lab as the game's village map. Terrain, water,
## buildings and props come from the reviewed lab assets (tools/port_archipelago_map.py).
const ROOT := "res://maps/archipelago/"
const TERRAIN := ROOT+"assets/archipelago_terrain_environment_v1.glb"
## Ground and rocks use layer 1, buildings, bridges and piers layer 2, props layer 8.
const WALK_MASK := 1|2|8
const SPRAY_AT := Vector3(.996,0,-7.937)
## Under the loading card the build is paced over frames and its models load on worker threads.
const LoadPace = preload("res://scripts/load_pace.gd")
## Generated data (simplified collision, tools/bake_archipelago.gd), used only while it matches the inputs.
const IslandBake = preload("res://maps/archipelago/island_bake.gd")
var camera: Camera3D
var spray: MultiMeshInstance3D
var mist: MultiMeshInstance3D
var water_time := 0.0

static func available() -> bool:
	return ResourceLoader.exists(TERRAIN)

## Every model and texture build() loads, for LoadPace.want() to start on worker threads early.
## In the order build() uses them (they load one at a time).
static func resource_paths() -> Array:
	var paths := ([IslandBake.COLLISION] if IslandBake.fresh() else [])+[TERRAIN]+textures()
	var placements = JSON.parse_string(FileAccess.get_file_as_string(ROOT+"building_placements.json"))
	if placements is Dictionary:
		for spec in placements.get("buildings", []): paths.append(String(spec.model))
	var layout = JSON.parse_string(FileAccess.get_file_as_string(ROOT+"environment_layout.json"))
	if layout is Dictionary:
		for spec in layout.get("models", []):
			paths.append(String(spec.model))
			paths.append(ROOT+"assets/prop_lods/"+String(spec.id)+".glb")
		for spec in layout.get("bridges", []):
			if spec.has("fitted_model"): paths.append(String(spec.fitted_model))
	# The baked island last: what it uses is in by then, one piece at a time.
	if IslandBake.island_ready(): paths.append(IslandBake.ISLAND)
	return paths

## The water, ground and rock textures build() puts on the terrain.
static func textures() -> Array:
	var paths := []
	# (The water shaders never sample a surface colour map: v3/*_surface_color.png is not loaded.)
	for prefix in ["ocean", "pond"]:
		paths.append(ROOT+"assets/v3/"+prefix+"_surface_normal.png")
	for name in ["current_field", "coast_field", "shore_distance", "organic_foam", "grass_detail", "sand_detail", "rock_detail",
			"grass_detail_normal", "sand_detail_normal", "headland_normals"]:
		paths.append(ROOT+"assets/v5/"+name+".png")
	return paths

## Paced under the loading card (await it); uncovered it runs in one go as before. The baked island
## (island_bake.gd) when it is fresh, else built here from the layouts.
func build(view: Camera3D) -> void:
	camera = view
	if IslandBake.island_ready() and await _build_from_bake(): return
	await _build_runtime()

## The baked island (tools/bake_archipelago.gd): read with everything it uses on the worker thread,
## made in a frame of its own, moved in a piece at a time, its scripts' lists found again, then its
## colliders made a chunk a frame from the generated collision. False (nothing added) when the
## scene cannot be read.
func _build_from_bake() -> bool:
	var paths := resource_paths()
	var span := LoadPace.narrow(0.0, 0.7)
	# Held here until the island has them (uncovered, fetch() only loads; nothing else holds them).
	var keep := []
	for index in paths.size():
		LoadPace.done(float(index)/paths.size())
		var path: String = paths[index]
		if path != IslandBake.ISLAND and ResourceLoader.exists(path) and (LoadPace.pending(path) or not LoadPace.covered): keep.append(await LoadPace.fetch(path))
	LoadPace.span = span
	LoadPace.mark("island models and textures in")
	var packed := await LoadPace.fetch(IslandBake.ISLAND) as PackedScene
	LoadPace.mark("island scene read")
	if packed == null:
		push_warning("The baked island could not be read: the map builds from its layouts")
		return false
	# Made on the main thread at the start of a frame of its own (2500 nodes, 25-40 ms): made on a
	# worker thread it usually cost the main thread nothing but now and then held it 0.7 s.
	if LoadPace.covered: await get_tree().process_frame
	var baked := packed.instantiate() as Node3D
	if baked != null:
		await LoadPace.step("baked island")
		_settle_baked(baked)
	if baked == null: return false
	LoadPace.mark("island instantiated")
	var colliders: Array = baked.get_meta("baked_colliders", [])
	span = LoadPace.narrow(0.7, 0.85)
	# Each piece goes in whole (a fresh subtree enters the tree in a few ms; its nodes taken out and
	# put in one by one cost a millisecond each), a frame apart: each is first drawn (its materials
	# set up, its meshes sent to the GPU) in a frame of its own.
	var pieces := baked.get_children()
	for index in pieces.size():
		var piece: Node = pieces[index]
		LoadPace.done(float(index)/pieces.size())
		baked.remove_child(piece)
		add_child(piece)
		if LoadPace.covered: await get_tree().process_frame
	baked.free()
	LoadPace.mark("island in the tree")
	LoadPace.span = span
	(get_node("Buildings") as Node).restore(self)
	(get_node("Environment") as Node).restore(self)
	_create_water_spray()
	LoadPace.mark("island lists restored")
	span = LoadPace.narrow(0.85, 1.0)
	var shared := {}
	for index in colliders.size():
		var entry: Dictionary = colliders[index]
		LoadPace.done(float(index)/colliders.size())
		if entry.has("faces"):
			# A ramp or a bridge deck: its body is there, the shape comes back.
			var body := get_node_or_null(NodePath(String(entry.body))) as StaticBody3D
			if body == null: continue
			await LoadPace.step("baked collider")
			var shape := ConcavePolygonShape3D.new()
			shape.backface_collision = entry.get("backface", false)
			var holder := CollisionShape3D.new()
			holder.shape = shape
			shape.set_faces(entry.faces)
			body.add_child(holder, true)
			continue
		var mesh := get_node_or_null(NodePath(String(entry.mesh))) as MeshInstance3D
		if mesh == null: continue
		var shapes: Array = []
		if entry.get("shared", false):
			if not shared.has(entry.key): shared[entry.key] = []
			shapes = shared[entry.key]
		await LoadPace.collide_chunks(mesh, IslandBake.collision_chunks(String(entry.key)), int(entry.layer), int(entry.mask), shapes)
	LoadPace.span = span
	IslandBake.drop_collision()
	LoadPace.mark("island colliders made")
	return true

## The baked scene's nodes get what the build changed inside the model instances set again.
static func _settle_baked(baked: Node3D) -> void:
	for change: Array in baked.get_meta("baked_overrides", []):
		var node := baked.get_node_or_null(NodePath(String(change[0])))
		if node: node.set(String(change[1]), change[2])
	# Its nodes move into the live map: they belong to no scene there (as the runtime build's).
	for node in baked.find_children("*", "", true, true): node.owner = null

func _build_runtime() -> void:
	var span := LoadPace.narrow(0.0, 0.08)
	var terrain_scene: PackedScene = await LoadPace.fetch(TERRAIN)
	var terrain: Node3D = terrain_scene.instantiate()
	add_child(terrain)
	LoadPace.done(1.0)
	LoadPace.span = span
	await LoadPace.step("terrain")
	var buildings := load(ROOT+"building_layout.gd").new() as Node3D
	buildings.name = "Buildings"
	add_child(buildings)
	span = LoadPace.narrow(0.08, 0.5)
	await buildings.install(self, terrain)
	LoadPace.span = span
	for path in textures(): if LoadPace.pending(path): await LoadPace.fetch(path)
	var meshes := terrain.find_children("*", "MeshInstance3D", true, false)
	for index in meshes.size():
		LoadPace.done(0.5+0.1*index/meshes.size())
		await LoadPace.step("terrain material")
		var item: Node = meshes[index]
		var m := item as MeshInstance3D
		if "__ground" in m.name or "__shore_rock" in m.name or "Waterfall__cliff_rock" in m.name:
			var chunks := IslandBake.collision_chunks(IslandBake.collider_key(self, m))
			if not chunks.is_empty(): await LoadPace.collide_chunks(m, chunks)
			elif LoadPace.covered: await LoadPace.collide(m)
			else: m.create_trimesh_collision()
		if ("Ocean__" in m.name and "seabed" not in m.name) or "__pond" in m.name or "Waterfall__spring_pool" in m.name:
			m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			var water := ShaderMaterial.new()
			water.shader = load(ROOT+("water_surface.gdshader" if "Ocean__" in m.name else "pond_water.gdshader"))
			var prefix := "ocean" if "Ocean__" in m.name else "pond"
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
	span = LoadPace.narrow(0.6, 1.0)
	await props.install(self, terrain)
	LoadPace.span = span
	IslandBake.drop_collision()
	_create_water_spray()
	if LoadPace.covered:
		# Under the card the map is finished before it shows: rock walls paced (in one go they held a
		# frame), then the roots and ramps that wait a few physics steps (bury waits fewer than ramp).
		await _wall_tall_rocks(terrain)
		_bury_tree_roots(props)
		await _ramp_open_structures()
		return
	_bury_tree_roots.call_deferred(props)
	_ramp_open_structures.call_deferred()
	_wall_tall_rocks.call_deferred(terrain)

## Walkers could climb the shore rocks a step at a time and wedge themselves in
## the gaps. Every rock cluster taller than ROCK_WALL_HEIGHT gets an invisible
## prism around its footprint on ROCK_WALL_LAYER, which only the player collides
## with; low rocks stay walkable, and rays (footsteps, placement) never see it.
const ROCK_WALL_LAYER := 32
const ROCK_WALL_HEIGHT := 0.8
func _wall_tall_rocks(terrain: Node3D) -> void:
	var rocks := terrain.find_children("*__shore_rock*","MeshInstance3D",true,false)
	if rocks.is_empty(): return
	var mesh_node := rocks[0] as MeshInstance3D
	var walls := StaticBody3D.new()
	walls.name = "RockWalls"
	walls.collision_layer = ROCK_WALL_LAYER
	walls.collision_mask = 0
	# Filled before it joins the tree: every shape added to a body in the tree updates all its shapes
	# (650 prisms one by one took over a second).
	for surface in mesh_node.mesh.get_surface_count():
		var arrays := mesh_node.mesh.surface_get_arrays(surface)
		var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var index: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		if index.is_empty(): continue
		# Union vertices that share a triangle (or a 5 cm cell, for split seams).
		var parent := PackedInt32Array()
		parent.resize(verts.size())
		for i in verts.size(): parent[i] = i
		var cells := {}
		for i in verts.size():
			if i % 4096 == 4095: await LoadPace.step("rock walls")
			var key := Vector3i((verts[i]/0.05).round())
			if cells.has(key): _union(parent, i, cells[key])
			else: cells[key] = i
		for t in range(0, index.size(), 3):
			if t % 12288 == 12285: await LoadPace.step("rock walls")
			_union(parent, index[t], index[t+1])
			_union(parent, index[t], index[t+2])
		var clusters := {}
		for i in verts.size():
			if i % 4096 == 4095: await LoadPace.step("rock walls")
			var r := _find(parent, i)
			if not clusters.has(r): clusters[r] = PackedVector3Array()
			clusters[r].append(mesh_node.global_transform*verts[i])
		for key in clusters:
			await LoadPace.step("rock wall")
			var points: PackedVector3Array = clusters[key]
			var low := INF
			var high := -INF
			var flat := PackedVector2Array()
			for p in points:
				low = minf(low, p.y)
				high = maxf(high, p.y)
				flat.append(Vector2(p.x, p.z))
			if high-low < ROCK_WALL_HEIGHT or points.size() < 8: continue
			var hull := Geometry2D.convex_hull(flat)
			var centre := Vector2.ZERO
			for h in hull: centre += h
			centre /= maxf(1.0, hull.size())
			var prism := PackedVector3Array()
			for h in hull:
				# Pull the wall in a little so the walker can still touch the stone.
				var q := centre+(h-centre)*0.9
				prism.append(Vector3(q.x, low-0.3, q.y))
				prism.append(Vector3(q.x, high+2.0, q.y))
			var shape := ConvexPolygonShape3D.new()
			shape.points = prism
			var holder := CollisionShape3D.new()
			holder.shape = shape
			walls.add_child(holder)
	add_child(walls)

static func _find(parent: PackedInt32Array, i: int) -> int:
	while parent[i] != i:
		parent[i] = parent[parent[i]]
		i = parent[i]
	return i

static func _union(parent: PackedInt32Array, a: int, b: int) -> void:
	var ra := _find(parent, a)
	var rb := _find(parent, b)
	if ra != rb: parent[ra] = rb

## Open structures (gazebo, music stage, picnic shelter) stand on raised floors
## that are taller than a step. An invisible ring ramp around each floor edge lets
## walkers stroll up from any side; railings and pillars keep their colliders.
const OPEN_STRUCTURES := {"08_gazebo":[Vector2(71,-36),2.9],"14_stage":[Vector2(37,26),4.5],"15_picnic_shelter":[Vector2(65,29),4.1]}
func _ramp_open_structures() -> void:
	await LoadPace.physics_frames(self, 5)
	var space := get_world_3d().direct_space_state
	for id in OPEN_STRUCTURES:
		var centre: Vector2 = OPEN_STRUCTURES[id][0]
		var inner: float = OPEN_STRUCTURES[id][1]
		var outer := inner+1.6
		var ground_hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(centre.x,40,centre.y+outer),Vector3(centre.x,-5,centre.y+outer),1))
		if ground_hit.is_empty(): continue
		var floor_hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(centre.x,ground_hit.position.y+2.2,centre.y),Vector3(centre.x,ground_hit.position.y-1,centre.y),2))
		if floor_hit.is_empty(): continue
		var top: float = floor_hit.position.y+0.01
		var faces := PackedVector3Array()
		var segments := 32
		for s in segments:
			var a := TAU*s/segments
			var b := TAU*(s+1)/segments
			var low: Array[float] = []
			for angle in [a,b]:
				var edge := centre+Vector2(sin(angle),cos(angle))*outer
				var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(edge.x,40,edge.y),Vector3(edge.x,-5,edge.y),1))
				low.append((hit.position.y if not hit.is_empty() else ground_hit.position.y)-0.05)
			var p := Vector3(centre.x+sin(a)*inner,top,centre.y+cos(a)*inner)
			var q := Vector3(centre.x+sin(b)*inner,top,centre.y+cos(b)*inner)
			var r := Vector3(centre.x+sin(a)*outer,low[0],centre.y+cos(a)*outer)
			var t := Vector3(centre.x+sin(b)*outer,low[1],centre.y+cos(b)*outer)
			faces.append_array(PackedVector3Array([p,r,q,q,r,t]))
		var body := StaticBody3D.new()
		body.name = "Ramp_"+id
		body.collision_layer = 2
		body.collision_mask = 0
		add_child(body)
		var shape := ConcavePolygonShape3D.new()
		shape.backface_collision = true
		shape.set_faces(faces)
		var collision := CollisionShape3D.new()
		collision.shape = shape
		body.add_child(collision)

## The tree models carry broad root flares that sit on top of the meadow. After
## the layout snaps props to the ground, sink each tree so the flares are buried.
const ROOT_DEPTH := {"37_round_tree":0.42,"38_conifer":0.22,"39_palm":0.12}
func _bury_tree_roots(props: Node) -> void:
	await LoadPace.physics_frames(self, 4)
	for prop in props.prop_nodes:
		var spec: Dictionary = prop.get_meta("placement_spec",{})
		if ROOT_DEPTH.has(spec.get("id","")):
			prop.global_position.y -= ROOT_DEPTH[spec.id]*float(spec.get("scale",1.0))

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
