extends Node3D
## Village add-on (main.gd VILLAGE_MODULES): raises the look of the Tripo building
## GLBs without replacing them.
##  - Each building's baked material becomes maps/archipelago/building_exterior.gdshader:
##    crisp anisotropic atlas, sane metal/roughness, contact shading at the base, a
##    dark interior on back faces, and window glass that glows warm at night.
##  - Wall lanterns beside every door (TownLayout.DOORS), lit at night with a halo, a
##    warm wash on the wall and a pool of light on the step.
##  - A soft contact shadow on the ground around each footprint.
## Everything is attached to the kept map once (dress()); the module instance only
## follows the clock (update()). Nothing here collides, so doors and paths stay free.
## A few MultiMeshes hold all lanterns and glows, so the dressing adds ~7 draw calls.
const Daylight = preload("res://scripts/daylight.gd")
const Town = preload("res://scripts/town.gd")
## Window lights follow who is home: a building whose people are all asleep or out
## keeps dark windows at night (residents.gd building_state().lights_on).
const Residents = preload("res://scripts/residents.gd")
const SHADER := "res://maps/archipelago/building_exterior.gdshader"
const PLACEMENTS := "res://maps/archipelago/building_placements.json"
const NODE_NAME := "BuildingDressing"
## Open pavilions have no walls to light or shade.
const OPEN := ["08_gazebo","14_stage","15_picnic_shelter"]
## Per building: which texels count as window glass and how warmly they glow.
## glass_max_luma keeps light-blue walls (blue house, cottage) and domes dark.
const TUNING := {
	"01_cafe":{"glass_max_luma":.42},
	"05_observatory":{"glass_max_luma":.30,"glow_band":Vector2(.6,4.6)},
	"04_windmill":{"glow_band":Vector2(.6,5.5)},
	"07_greenhouse":{"glow_energy":.55,"glass_max_luma":.5},
	"08_gazebo":{"glow_energy":0.0},
	"12_blue_house":{"glass_max_luma":.33},
	"14_stage":{"glow_energy":0.0},
	"15_picnic_shelter":{"glow_energy":0.0},
	"16_blue_cottage":{"glass_max_luma":.33},
	"17_lighthouse":{"glow_band":Vector2(.6,9.5)},
	"09_town_hall":{"glow_band":Vector2(.6,6.0)},
}
const LANTERN_HEIGHT := 2.15
## Lantern glows. Quads are baked into one world-space mesh per kind; billboards keep
## all four corners on the lantern centre and spread them towards the camera here.
const HALO_SHADER := """
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;
uniform float strength = 0.0;
uniform vec4 tint : source_color = vec4(1.0, 0.74, 0.40, 1.0);
uniform bool billboard = true;
uniform float size = 1.0;
uniform float pull = 0.3;
void vertex() {
	if (billboard) {
		vec2 corner = (UV-vec2(0.5))*vec2(1.0, -1.0)*size;
		VERTEX += INV_VIEW_MATRIX[0].xyz*corner.x+INV_VIEW_MATRIX[1].xyz*corner.y+INV_VIEW_MATRIX[2].xyz*pull;
	}
}
void fragment() {
	float d = length(UV-vec2(0.5))*2.0;
	float glow = billboard ? pow(max(1.0-d, 0.0), 2.2) : pow(max(1.0-d, 0.0), 1.5);
	ALBEDO = tint.rgb*glow*strength;
}
"""
## Ground contact shadow: multiplies the ground darker towards the footprint edge.
## UV is the footprint-local position and UV2 the half footprint, both in metres.
const CONTACT_SHADER := """
shader_type spatial;
render_mode unshaded, blend_mul, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;
uniform float reach = 0.75;
uniform float depth = 0.3;
void fragment() {
	vec2 q = abs(UV)-UV2;
	float outside = length(max(q, 0.0))+min(max(q.x, q.y), 0.0);
	float shade = depth*(1.0-smoothstep(-0.25, reach, outside));
	ALBEDO = vec3(1.0-shade, 1.0-shade*0.96, 1.0-shade*0.9);
}
"""

var app: Node
var map: Node3D
var _until := 0.0

## Village module entry: dress the kept map once and follow the clock.
func setup(owner_app: Node) -> void:
	app = owner_app
	if app == null or not ("town" in app) or not is_instance_valid(app.town): return
	map = app.town.map
	if not is_instance_valid(map): return
	dress(map)
	update(map, _hour())

func _hour() -> float:
	if is_instance_valid(app) and "daylight" in app and is_instance_valid(app.daylight) and app.daylight.has_method("current_hour"):
		return app.daylight.current_hour()
	return Daylight.clock_hour()

func _process(delta: float) -> void:
	_until -= delta
	if _until > 0.0 or not is_instance_valid(map): return
	_until = 1.0
	update(map, _hour())

func leave() -> void:
	map = null

## Builds the dressing on the map (idempotent) and returns its node.
static func dress(host: Node3D) -> Node3D:
	if host == null: return null
	var existing := host.get_node_or_null(NODE_NAME) as Node3D
	if existing: return existing
	var root := Node3D.new()
	root.name = NODE_NAME
	host.add_child(root)
	var materials: Array[ShaderMaterial] = []
	var glass: Array[StandardMaterial3D] = []
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(PLACEMENTS))
	var buildings := host.get_node_or_null("Buildings")
	var shader: Shader = load(SHADER)
	var shadows := SurfaceTool.new()
	shadows.begin(Mesh.PRIMITIVE_TRIANGLES)
	for spec: Dictionary in manifest.buildings:
		var building := buildings.get_node_or_null(String(spec.id)) as Node3D if buildings else null
		if building == null: continue
		_restyle(building, String(spec.id), shader, materials, glass, float(spec.dimensions_m[1]))
		if String(spec.id) in OPEN: continue
		# The quad stays on the levelled pad (building_layout.gd), so it never floats
		# over a slope; the shade fades out from the walls to the pad edge.
		var half := Vector2(float(spec.dimensions_m[0]), float(spec.dimensions_m[2]))*.5*.86
		var reach := Vector2(float(spec.pad_half_extents[0]), float(spec.pad_half_extents[1]))
		var frame := Transform3D(Basis(Vector3.UP, building.rotation.y), building.global_position+Vector3(0, .05, 0))
		_quad_into(shadows, frame, reach, half)
	var contact := ShaderMaterial.new()
	contact.shader = Shader.new()
	contact.shader.code = CONTACT_SHADER
	contact.render_priority = 2
	_mesh_node(root, "ContactShadows", shadows.commit(), contact)
	var lights := {"halo":_halo_material(true), "wash":_halo_material(false), "pool":_halo_material(false), "glass":_lantern_glass()}
	(lights.pool as ShaderMaterial).set_shader_parameter("tint", Color(1.0, .66, .34))
	var space := host.get_world_3d().direct_space_state
	var spots: Array[Dictionary] = []
	for door: Dictionary in Town.DOORS:
		spots.append_array(_door_walls(space, door))
	var bodies: Array[Transform3D] = []
	var halos := SurfaceTool.new()
	var washes := SurfaceTool.new()
	var pools := SurfaceTool.new()
	for tool in [halos, washes, pools]: tool.begin(Mesh.PRIMITIVE_TRIANGLES)
	for spot in spots:
		var frame := Transform3D(Basis.looking_at(spot.normal, Vector3.UP), spot.wall)
		bodies.append(frame)
		# Billboard: a zero-size quad at the lantern centre (the shader spreads it).
		_quad_into(halos, Transform3D(Basis.from_scale(Vector3(.0001, .0001, .0001)), frame*Vector3(0, -.15, -.3)), Vector2.ONE*.5, Vector2.ZERO, true)
		# Upright wash on the wall: the quad lies in the wall plane (x, y of the frame).
		_quad_into(washes, frame*Transform3D(Basis(Vector3.RIGHT, PI*.5), Vector3(0, -.25, -.03)), Vector2(1.0, 1.1), Vector2.ZERO, true)
		var foot: Vector3 = spot.wall+spot.normal*.9
		_quad_into(pools, Transform3D(Basis.IDENTITY, Vector3(foot.x, float(spot.ground)+.06, foot.z)), Vector2(1.7, 1.7), Vector2.ZERO, true)
	(lights.halo as ShaderMaterial).set_shader_parameter("size", 1.0)
	_batch(root, "Lanterns", _lantern_mesh(lights.glass), null, bodies)
	_mesh_node(root, "LanternHalos", halos.commit(), lights.halo)
	_mesh_node(root, "LanternWash", washes.commit(), lights.wash)
	_mesh_node(root, "LanternPools", pools.commit(), lights.pool)
	root.set_meta("materials", materials)
	root.set_meta("glass", glass)
	root.set_meta("lights", lights)
	root.set_meta("lanterns", spots.size())
	return root

## Applies the clock to the dressing: window glow and lanterns follow the night.
static func update(host: Node3D, hour: float) -> void:
	var root := host.get_node_or_null(NODE_NAME) if host else null
	if root == null: return
	var values := Daylight.sample(hour)
	var night: float = values.night
	var lamps := clampf(float(values.lamp_energy)/Daylight.LAMP_NIGHT_GAIN, 0.0, 1.0)
	_update_rooms(host, root, hour, night)
	if is_equal_approx(float(root.get_meta("night", -1.0)), night) and is_equal_approx(float(root.get_meta("lamps", -1.0)), lamps): return
	root.set_meta("night", night)
	root.set_meta("lamps", lamps)
	for material: ShaderMaterial in root.get_meta("materials", []):
		material.set_shader_parameter("night", night)
	for material: StandardMaterial3D in root.get_meta("glass", []):
		# Panes of a lived-in building follow its occupants (_update_rooms).
		if not material.has_meta("room"): material.emission_energy_multiplier = 1.4*night
	var lights: Dictionary = root.get_meta("lights", {})
	if lights.is_empty(): return
	(lights.halo as ShaderMaterial).set_shader_parameter("strength", .9*lamps)
	(lights.wash as ShaderMaterial).set_shader_parameter("strength", 1.1*lamps)
	(lights.pool as ShaderMaterial).set_shader_parameter("strength", 1.0*lamps)
	(lights.glass as StandardMaterial3D).emission_energy_multiplier = lerpf(.15, 2.6, lamps)
	for name in ["LanternHalos", "LanternWash", "LanternPools"]:
		var node := root.get_node_or_null(name) as Node3D
		if node: node.visible = lamps > .01

## Per building window glow: on while someone inside is awake, dark when everyone is
## asleep or out. Indexed once (materials by building), then a cheap pass per call
## (update() runs once a second); a change fades over two calls.
static func _update_rooms(host: Node3D, root: Node, hour: float, night: float) -> void:
	if not root.has_meta("rooms"): root.set_meta("rooms", _index_rooms(host))
	var rooms: Dictionary = root.get_meta("rooms")
	var day := int(Residents.clock().day)
	for id in rooms:
		var room: Dictionary = rooms[id]
		var target := 1.0 if night < 0.02 or Residents.building_state(id, hour, day).lights_on else 0.0
		room.lit = move_toward(float(room.lit), target, 0.5)
		var written := Vector2(room.lit, night)
		if written == room.written: continue
		room.written = written
		for material: ShaderMaterial in room.mats: material.set_shader_parameter("glow_energy", float(room.base)*float(room.lit))
		for pane: StandardMaterial3D in room.glass: pane.emission_energy_multiplier = 1.4*night*float(room.lit)

## {building id: {mats, glass, base, lit, written}} for buildings with a door.
static func _index_rooms(host: Node3D) -> Dictionary:
	var rooms := {}
	var buildings := host.get_node_or_null("Buildings")
	if buildings == null: return rooms
	for door: Dictionary in Town.DOORS:
		var building := buildings.get_node_or_null(String(door.id)) as Node3D
		if building == null: continue
		var tune: Dictionary = TUNING.get(String(door.id), {})
		var room := {"mats":[], "glass":[], "base":float(tune.get("glow_energy", 1.6)), "lit":1.0, "written":Vector2(-1, -1)}
		for item in building.find_children("*", "MeshInstance3D", true, false):
			var mesh := item as MeshInstance3D
			for i in mesh.get_surface_override_material_count():
				var material := mesh.get_surface_override_material(i)
				if material is ShaderMaterial and (material as ShaderMaterial).shader != null and (material as ShaderMaterial).shader.resource_path == SHADER: room.mats.append(material)
				elif material is StandardMaterial3D and (material as StandardMaterial3D).emission_enabled:
					material.set_meta("room", String(door.id))
					room.glass.append(material)
		rooms[String(door.id)] = room
	return rooms

static func _restyle(building: Node3D, id: String, shader: Shader, materials: Array[ShaderMaterial], glass: Array[StandardMaterial3D], height: float) -> void:
	var tune: Dictionary = TUNING.get(id, {})
	for item in building.find_children("*", "MeshInstance3D", true, false):
		var mesh := item as MeshInstance3D
		for i in mesh.mesh.get_surface_count():
			var source := mesh.get_active_material(i) as StandardMaterial3D
			if source == null: continue
			if source.albedo_texture != null:
				var material := ShaderMaterial.new()
				material.shader = shader
				material.set_shader_parameter("albedo_tex", source.albedo_texture)
				var orm: Texture2D = source.roughness_texture if source.roughness_texture else source.metallic_texture
				material.set_shader_parameter("has_orm", orm != null)
				if orm: material.set_shader_parameter("orm_tex", orm)
				material.set_shader_parameter("has_normal", source.normal_enabled and source.normal_texture != null)
				if source.normal_texture: material.set_shader_parameter("normal_tex", source.normal_texture)
				material.set_shader_parameter("normal_depth", source.normal_scale)
				# Windows sit below the eaves; dark teal fascia boards above must not glow.
				material.set_shader_parameter("glow_band", Vector2(.6, height*.45))
				for key in tune: material.set_shader_parameter(key, tune[key])
				mesh.set_surface_override_material(i, material)
				materials.append(material)
			elif source.transparency == BaseMaterial3D.TRANSPARENCY_DISABLED and source.albedo_color.b > source.albedo_color.r+.15 and source.roughness < .35 and float(tune.get("glow_energy", 1.0)) > 0.0:
				# Separate window-glass parts (recessed panes) light up with the rooms.
				var pane: StandardMaterial3D = source.duplicate()
				pane.emission_enabled = true
				pane.emission = Color(1.0, .68, .34)
				pane.emission_energy_multiplier = 0.0
				mesh.set_surface_override_material(i, pane)
				glass.append(pane)

## One MultiMesh per kind of dressing keeps the whole village to a few draw calls.
static func _batch(root: Node3D, name: String, mesh: Mesh, material: Material, transforms: Array[Transform3D], custom: Array[Color] = []) -> MultiMeshInstance3D:
	var multi := MultiMesh.new()
	multi.transform_format = MultiMesh.TRANSFORM_3D
	multi.use_custom_data = not custom.is_empty()
	multi.mesh = mesh
	multi.instance_count = transforms.size()
	for i in transforms.size():
		multi.set_instance_transform(i, transforms[i])
		if multi.use_custom_data: multi.set_instance_custom_data(i, custom[i])
	var node := MultiMeshInstance3D.new()
	node.name = name
	node.multimesh = multi
	if material: node.material_override = material
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(node)
	return node

## A flat quad (in the frame's XZ plane) of the given half size. unit_uv maps UV to
## 0..1 corners; otherwise UV is the local position in metres and UV2 carries extra.
static func _quad_into(tool: SurfaceTool, frame: Transform3D, half: Vector2, extra: Vector2, unit_uv := false) -> void:
	var corners := [Vector2(-1, -1), Vector2(1, -1), Vector2(1, 1), Vector2(-1, -1), Vector2(1, 1), Vector2(-1, 1)]
	for c: Vector2 in corners:
		var local := Vector2(c.x*half.x, c.y*half.y)
		tool.set_uv(Vector2(c.x*.5+.5, c.y*.5+.5) if unit_uv else local)
		tool.set_uv2(extra)
		tool.set_normal(frame.basis*Vector3.UP)
		tool.add_vertex(frame*Vector3(local.x, 0, local.y))

static func _mesh_node(root: Node3D, name: String, mesh: Mesh, material: Material) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.name = name
	node.mesh = mesh
	node.material_override = material
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(node)
	return node

static func _halo_material(billboard: bool) -> ShaderMaterial:
	var shader := Shader.new()
	shader.code = HALO_SHADER
	var material := ShaderMaterial.new()
	material.shader = shader
	material.render_priority = 3
	material.set_shader_parameter("billboard", billboard)
	return material

static func _lantern_glass() -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = Color("f3dfab")
	material.emission_enabled = true
	material.emission = Color(1.0, .74, .38)
	material.emission_energy_multiplier = .15
	material.roughness = .4
	return material

## Wall plate, arm, lantern box with glowing panes, cap; -Z points out of the wall.
static func _lantern_mesh(glass: Material) -> ArrayMesh:
	var iron := StandardMaterial3D.new()
	iron.albedo_color = Color("2b2622")
	iron.roughness = .55
	iron.metallic = .2
	var frame := SurfaceTool.new()
	frame.begin(Mesh.PRIMITIVE_TRIANGLES)
	var parts := [[Vector3(0, .05, -.015), Vector3(.14, .26, .03)], [Vector3(0, .12, -.17), Vector3(.035, .035, .32)],
		[Vector3(0, -.02, -.3), Vector3(.2, .03, .2)], [Vector3(0, -.285, -.3), Vector3(.2, .03, .2)]]
	for corner in [Vector2(-1, -1), Vector2(-1, 1), Vector2(1, -1), Vector2(1, 1)]:
		parts.append([Vector3(corner.x*.088, -.15, -.3+corner.y*.088), Vector3(.022, .26, .022)])
	for part in parts:
		var box := BoxMesh.new()
		box.size = part[1]
		frame.append_from(box, 0, Transform3D(Basis.IDENTITY, part[0]))
	var cap := CylinderMesh.new()
	cap.top_radius = .02
	cap.bottom_radius = .16
	cap.height = .12
	cap.radial_segments = 4
	cap.rings = 0
	frame.append_from(cap, 0, Transform3D(Basis(Vector3.UP, PI*.25), Vector3(0, .06, -.3)))
	var mesh := frame.commit()
	mesh.surface_set_material(0, iron)
	var pane := BoxMesh.new()
	pane.size = Vector3(.17, .24, .17)
	var panes := SurfaceTool.new()
	panes.begin(Mesh.PRIMITIVE_TRIANGLES)
	panes.append_from(pane, 0, Transform3D(Basis.IDENTITY, Vector3(0, -.15, -.3)))
	panes.commit(mesh)
	mesh.surface_set_material(1, glass)
	return mesh

## The wall either side of a door at lantern height: [{wall, normal, ground}].
static func _door_walls(space: PhysicsDirectSpaceState3D, door: Dictionary) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var at: Vector2 = door.at
	var out: Vector2 = (at-Vector2(door.center)).normalized()
	var side_dir := out.orthogonal()
	var floor_hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(at.x, 40, at.y), Vector3(at.x, -10, at.y), 1|2))
	if floor_hit.is_empty(): return found
	var base_y: float = floor_hit.position.y
	for side in [-1.0, 1.0]:
		var from2: Vector2 = at+side_dir*float(side)*1.25+out*1.0
		var from := Vector3(from2.x, base_y+LANTERN_HEIGHT, from2.y)
		var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(from, from-Vector3(out.x, 0, out.y)*6.0, 2))
		if hit.is_empty() or absf(hit.normal.y) > .45: continue
		found.append({"wall":hit.position, "normal":Vector3(hit.normal.x, 0, hit.normal.z).normalized(), "ground":base_y})
	if found.size() == 2 and absf(Vector2(found[0].wall.x-found[1].wall.x, found[0].wall.z-found[1].wall.z).dot(out)) > .8:
		# Different walls (a porch column against the façade): keep the one nearer the door.
		found.sort_custom(func(a, b): return Vector2(a.wall.x, a.wall.z).distance_to(at) < Vector2(b.wall.x, b.wall.z).distance_to(at))
		found.resize(1)
	return found
