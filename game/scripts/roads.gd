extends Node3D
## Village paths that follow the island terrain between doors, the town green and
## the bridge ends. Main roads (2.2 m) are cobbled with low border stones; side paths
## (1.7 m) are packed earth. Junctions get round cobbled plazas, doors a paved apron
## up to the step, bridge ends a few boards, and grass tufts soften every edge. Small
## props on a path are hidden; footsteps use on_road() to switch to the gravel sound.
## Everything is batched: one ribbon mesh (maps/archipelago/road_surface.gdshader)
## plus one MultiMesh each for stones, tufts and boards.
const Art = preload("res://scripts/art.gd")
const SHADER := "res://maps/archipelago/road_surface.gdshader"
const ENVIRONMENT := "res://maps/archipelago/environment_layout.json"
const ROADS := [
	["sw_hall",2.2,[Vector2(-33,37),Vector2(-33.2,30.0)]],
	["sw_east",2.2,[Vector2(-33,37),Vector2(-26,36.5),Vector2(-20,35),Vector2(-15.5,36.2),Vector2(-14,33.4),Vector2(-13,31),Vector2(-10.3,27)]],
	["sw_shop",1.7,[Vector2(-20,35),Vector2(-18.2,31.2)]],
	["sw_west",2.2,[Vector2(-33,37),Vector2(-40,34.5),Vector2(-46,33),Vector2(-50.5,27.5),Vector2(-54.1,23.4)]],
	# Bends south round the shore rock at (-59.4, 35.6) that blocked the walk.
	["sw_purple",1.7,[Vector2(-46,33),Vector2(-56,35),Vector2(-59.4,36.7),Vector2(-64.4,37.2)]],
	["sw_blue",1.7,[Vector2(-56,35),Vector2(-61,40.5),Vector2(-60.8,52),Vector2(-66,54.2),Vector2(-70.2,50.0)]],
	["sw_south",1.7,[Vector2(-33,37),Vector2(-29,42),Vector2(-29.8,49),Vector2(-25.5,57.5)]],
	["lh",1.7,[Vector2(2.5,73.5),Vector2(3,77),Vector2(4.6,80.6),Vector2(7,81.3)]],
	["se_main",2.2,[Vector2(16.5,27),Vector2(24,30.5),Vector2(34,33.5),Vector2(44,36),Vector2(52,38.5)]],
	["se_north",1.7,[Vector2(44,36),Vector2(52,28),Vector2(56.5,15)]],
	["se_cottage",1.7,[Vector2(52,38.5),Vector2(58,39.5),Vector2(65,44.5),Vector2(65.5,52),Vector2(66.5,57),Vector2(70,56.6)]],
	["se_picnic",1.7,[Vector2(52,28),Vector2(60,29)]],
	["ne_main",1.7,[Vector2(57,-6.5),Vector2(53,-12),Vector2(49.2,-15.6)]],
	["ne_west",2.2,[Vector2(53,-12),Vector2(44,-13),Vector2(32,-21),Vector2(25,-24.6)]],
	["ne_obs",1.7,[Vector2(32,-21),Vector2(29.5,-26),Vector2(30,-31),Vector2(29.3,-37),Vector2(30.2,-41.9)]],
	["ne_bridge",1.7,[Vector2(15.5,-36),Vector2(22,-36),Vector2(31,-33)]],
	["ne_gazebo",1.7,[Vector2(53,-12),Vector2(63,-25),Vector2(68,-32)]],
	["nw_main",1.7,[Vector2(-10.5,-36),Vector2(-14,-33),Vector2(-16,-29.5)]],
	["nw_mill",1.7,[Vector2(-14,-33),Vector2(-15,-37.5),Vector2(-18.8,-40.5)]],
	["nw_teal",2.2,[Vector2(-16,-29.5),Vector2(-23,-24.5),Vector2(-30,-23.3),Vector2(-35.2,-22.8)]],
	["nw_timber",1.7,[Vector2(-28,-25),Vector2(-28.5,-33),Vector2(-36,-36),Vector2(-40.6,-44.6)]],
	["nw_cafe",1.7,[Vector2(-36,-36),Vector2(-46,-33),Vector2(-55,-32),Vector2(-61.2,-32.4)]],
]
const HIDE_ON_ROAD := ["41_planter","42_white_flowers","43_yellow_flowers","44_pink_flowers","40_shrub","45_reeds"]
## Roads this wide or wider are cobbled main roads.
const MAIN_WIDTH := 2.0
## The ribbon is drawn this much wider than the road; the extra fades into the grass.
const FRINGE := 1.3
const LIFT := 0.04
## Across-road sample positions, in half-widths of the drawn ribbon.
const ACROSS := [-1.0, -0.72, -0.36, 0.0, 0.36, 0.72, 1.0]

static func on_road(at: Vector2) -> bool:
	for road in ROADS:
		var pts: Array=road[2]
		for i in pts.size()-1:
			if Geometry2D.get_closest_point_to_segment(at,pts[i],pts[i+1]).distance_to(at)<float(road[1])*0.5: return true
	return false

var space: PhysicsDirectSpaceState3D
var surface: SurfaceTool
var rng := RandomNumberGenerator.new()
var stones: Array[Transform3D] = []
var stone_colors: Array[Color] = []
var tufts: Array[Transform3D] = []
var tuft_colors: Array[Color] = []
var boards: Array[Transform3D] = []
var board_colors: Array[Color] = []
## Junction plazas ([centre, radius]); edge tufts keep clear of them.
var crossings: Array = []

func build(physics: PhysicsDirectSpaceState3D, layout: Node) -> void:
	space = physics
	rng.seed = 2610
	surface = SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	crossings = junctions()
	for index in ROADS.size():
		ribbon(ROADS[index][2], float(ROADS[index][1]), LIFT+index*0.001)
	for spot in crossings:
		plaza(spot[0], spot[1], LIFT+0.03)
	door_aprons()
	bridge_boards()
	var mesh := MeshInstance3D.new()
	mesh.name = "RoadSurface"
	mesh.mesh = surface.commit()
	var material := ShaderMaterial.new()
	material.shader = load(SHADER)
	mesh.material_override = material
	mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mesh)
	scatter("BorderStones", stone_mesh(), stones, stone_colors, false)
	scatter("EdgeTufts", tuft_mesh(), tufts, tuft_colors, true)
	scatter("Boards", board_mesh(), boards, board_colors, false)
	if layout and "prop_nodes" in layout:
		for prop in layout.prop_nodes:
			var spec: Dictionary=prop.get_meta("placement_spec",{})
			if spec.get("id","") in HIDE_ON_ROAD and on_road(Vector2(prop.global_position.x,prop.global_position.z)):
				prop.visible=false
				for body in prop.find_children("*","StaticBody3D",true,false): body.collision_layer=0

## Terrain height (layer 1) under a point, ignoring the shore rocks that sit on it.
func ground(at: Vector2) -> float:
	var query := PhysicsRayQueryParameters3D.create(Vector3(at.x,40,at.y),Vector3(at.x,-10,at.y),1)
	for attempt in 3:
		var hit := space.intersect_ray(query)
		if hit.is_empty(): return 2.0
		var owner_node: Node = hit.collider.get_parent()
		if owner_node == null or "rock" not in String(owner_node.name): return hit.position.y
		var skip := query.exclude
		skip.append(hit.rid)
		query.exclude = skip
	return 2.0

## True where a building, bridge or pier deck covers the ground.
func covered(at: Vector2, ground_y: float) -> bool:
	var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(at.x,40,at.y),Vector3(at.x,ground_y-0.5,at.y),2))
	return not hit.is_empty() and hit.position.y > ground_y+0.02

func vertex(at: Vector3, u: float, v: float, cobbled: float) -> void:
	surface.set_color(Color(cobbled, 0, 0, 1))
	surface.set_uv(Vector2(u, v))
	surface.set_normal(Vector3.UP)
	surface.add_vertex(at)

func ribbon(pts: Array, width: float, lift: float) -> void:
	var samples: Array[Vector2]=[]
	for i in pts.size()-1:
		var a: Vector2=pts[i]
		var b: Vector2=pts[i+1]
		var steps := maxi(1,int(a.distance_to(b)/0.4))
		for s in steps: samples.append(a.lerp(b,float(s)/steps))
	samples.append(pts[pts.size()-1])
	var cobbled := 1.0 if width >= MAIN_WIDTH else 0.0
	var half := width*0.5*FRINGE
	var rows: Array=[]
	var along := 0.0
	var distances: Array[float] = []
	for i in samples.size():
		var here: Vector2=samples[i]
		if i > 0: along += here.distance_to(samples[i-1])
		distances.append(along)
		var ahead: Vector2=samples[mini(i+1,samples.size()-1)]
		var behind: Vector2=samples[maxi(i-1,0)]
		var side: Vector2=(ahead-behind).normalized().orthogonal()
		var row: Array=[]
		for u in ACROSS:
			var at: Vector2=here+side*float(u)*half
			row.append(Vector3(at.x,ground(at)+lift,at.y))
		rows.append(row)
		var near_end := minf(here.distance_to(pts[0]), here.distance_to(pts[pts.size()-1])) < 4.0
		edge_dressing(here, side, width, row, i, cobbled > 0.5, near_end)
	for i in rows.size()-1:
		for k in ACROSS.size()-1:
			var quad := [rows[i][k],rows[i][k+1],rows[i+1][k],rows[i+1][k+1]]
			var us := [ACROSS[k],ACROSS[k+1],ACROSS[k],ACROSS[k+1]]
			var vs := [distances[i],distances[i],distances[i+1],distances[i+1]]
			for n in [0,1,2,2,1,3]:
				vertex(quad[n], us[n], vs[n], cobbled)

## Border stones along cobbled roads and grass tufts along every edge.
## Heights come from the ribbon row (no extra rays) except near road ends, where
## bridge decks and door steps are checked so nothing pokes through them.
func edge_dressing(here: Vector2, side: Vector2, width: float, row: Array, index: int, main: bool, near_end: bool) -> void:
	for s in [-1.0, 1.0]:
		var kerb_y: float = row[1 if s < 0 else ACROSS.size()-2].y-LIFT
		var rim_y: float = row[0 if s < 0 else ACROSS.size()-1].y-LIFT
		if main:
			# A kerb of rounded stones every ~0.4 m (one per sample), half sunk.
			var at: Vector2 = here+side*float(s)*(width*0.5+0.02)+Vector2(rng.randf_range(-.06,.06), rng.randf_range(-.06,.06))
			if not near_end or not covered(at, kerb_y):
				var size := Vector3(rng.randf_range(.17,.24), rng.randf_range(.07,.1), rng.randf_range(.13,.18))
				stones.append(Transform3D(Basis(Vector3.UP, atan2(side.x, side.y)+rng.randf_range(-.3,.3))*Basis.from_scale(size), Vector3(at.x, kerb_y+.012, at.y)))
				var tone := rng.randf_range(.0, 1.0)
				stone_colors.append(Color(.74,.71,.64).lerp(Color(.56,.54,.5), tone))
		if index % 2 == 0 and rng.randf() < .75:
			var at: Vector2 = here+side*float(s)*(width*0.5*rng.randf_range(1.0, 1.25))+Vector2(rng.randf_range(-.2,.2), rng.randf_range(-.2,.2))
			var y := lerpf(kerb_y, rim_y, .6)
			var clear := true
			for spot in crossings:
				if at.distance_to(spot[0]) < float(spot[1])*1.6: clear = false
			if clear and y > 1.2 and (not near_end or not covered(at, y)):
				var scale := rng.randf_range(.75, 1.25)
				tufts.append(Transform3D(Basis(Vector3.UP, rng.randf_range(0, TAU))*Basis.from_scale(Vector3(scale, scale*rng.randf_range(.8,1.2), scale)), Vector3(at.x, y-.02, at.y)))
				tuft_colors.append(Color(1,1,1).lerp(Color(.86,.92,.78), rng.randf()))

## Points where a road ends on another road, merged; radius from the widest road.
func junctions() -> Array:
	var found: Array = []
	for road in ROADS:
		var pts: Array = road[2]
		for end in [pts[0], pts[pts.size()-1]]:
			var widest := 0.0
			var meets := 0
			for other in ROADS:
				var ops: Array = other[2]
				for i in ops.size()-1:
					if Geometry2D.get_closest_point_to_segment(end, ops[i], ops[i+1]).distance_to(end) < 0.4:
						meets += 1
						widest = maxf(widest, float(other[1]))
						break
			if meets < 2: continue
			var merged := false
			for spot in found:
				if Vector2(spot[0]).distance_to(end) < 1.5: merged = true
			if not merged: found.append([end, widest*0.62+0.25])
	return found

## A round cobbled patch draped on the ground; UV.x runs 0 at the centre to 1 at the rim.
func plaza(centre: Vector2, radius: float, lift: float) -> void:
	var drawn := radius*FRINGE
	var rings := [0.0, 0.5, 0.8, 1.0]
	var segments := 20
	var grid: Array = []
	for r in rings:
		var ring: Array = []
		for s in segments:
			var angle := TAU*s/segments
			var at := centre+Vector2(cos(angle), sin(angle))*drawn*float(r)
			ring.append(Vector3(at.x, ground(at)+lift, at.y))
		grid.append(ring)
	for r in rings.size()-1:
		for s in segments:
			var t := (s+1)%segments
			var quad := [grid[r][s], grid[r][t], grid[r+1][s], grid[r+1][t]]
			var us := [rings[r], rings[r], rings[r+1], rings[r+1]]
			# Wound the other way from ribbons so the plaza faces up.
			for n in [0,2,1,1,2,3]:
				vertex(quad[n], float(us[n]), 0.0, 1.0)

## Each door the roads lead to gets a short paved link and apron up to its step.
func door_aprons() -> void:
	var town: Script = load("res://scripts/town.gd")
	for door: Dictionary in town.DOORS:
		var at: Vector2 = door.at
		var best := Vector2.INF
		var width := 1.7
		for road in ROADS:
			var pts: Array = road[2]
			for i in pts.size()-1:
				var p := Geometry2D.get_closest_point_to_segment(at, pts[i], pts[i+1])
				if p.distance_to(at) < best.distance_to(at):
					best = p
					width = float(road[1])
		var gap := best.distance_to(at)
		if gap > 4.0: continue
		var out: Vector2 = (at-Vector2(door.center)).normalized()
		# The apron sits just outside the step so it never climbs the building.
		var apron := at+out*0.35
		if gap > 0.6: ribbon([best, apron], minf(width, 1.6), LIFT+0.02)
		plaza(apron, 1.05, LIFT+0.035)

## Boards across the path where a road meets a bridge end, easing earth into deck.
func bridge_boards() -> void:
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(ENVIRONMENT))
	var ends: Array[Vector2] = []
	for bridge in layout.get("bridges", []):
		ends.append(Vector2(bridge.a[0], bridge.a[1]))
		ends.append(Vector2(bridge.b[0], bridge.b[1]))
	for road in ROADS:
		var pts: Array = road[2]
		for pair in [[pts[0], pts[1]], [pts[pts.size()-1], pts[pts.size()-2]]]:
			var end: Vector2 = pair[0]
			var near := false
			for e in ends:
				if e.distance_to(end) < 2.0: near = true
			if not near: continue
			var inland: Vector2 = (Vector2(pair[1])-end).normalized()
			var across := inland.orthogonal()
			var laid := 0
			var d := 0.0
			while d < 4.0 and laid < 4:
				var at := end+inland*d
				var y := ground(at)
				d += 0.36
				if covered(at, y): continue
				var length := float(road[1])*rng.randf_range(.88, 1.0)
				var basis := Basis(Vector3.UP, atan2(across.x, across.y)+rng.randf_range(-.05,.05))*Basis.from_scale(Vector3(.26, .05, length))
				boards.append(Transform3D(basis, Vector3(at.x, y+.02, at.y)))
				board_colors.append(Color(.55,.4,.27).lerp(Color(.42,.3,.2), rng.randf()))
				laid += 1

func scatter(name: String, mesh: Mesh, transforms: Array[Transform3D], colors: Array[Color], two_sided: bool) -> void:
	if transforms.is_empty(): return
	var multi := MultiMesh.new()
	multi.transform_format = MultiMesh.TRANSFORM_3D
	multi.use_colors = true
	multi.mesh = mesh
	multi.instance_count = transforms.size()
	for i in transforms.size():
		multi.set_instance_transform(i, transforms[i])
		multi.set_instance_color(i, colors[i])
	var node := MultiMeshInstance3D.new()
	node.name = name
	node.multimesh = multi
	var material := StandardMaterial3D.new()
	material.vertex_color_use_as_albedo = true
	material.roughness = 0.9
	if two_sided: material.cull_mode = BaseMaterial3D.CULL_DISABLED
	node.material_override = material
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)

## A rounded, slightly faceted stone (unit size; instances scale it).
func stone_mesh() -> Mesh:
	var sphere := SphereMesh.new()
	sphere.radius = 0.5
	sphere.height = 1.0
	sphere.radial_segments = 7
	sphere.rings = 3
	return sphere

## Five tapered blades, dark at the root and sunlit at the tip.
func tuft_mesh() -> Mesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var blade_rng := RandomNumberGenerator.new()
	blade_rng.seed = 7
	for b in 6:
		var angle := TAU*b/6.0+blade_rng.randf_range(-.3,.3)
		var lean := Vector3(cos(angle), 0, sin(angle))*blade_rng.randf_range(.06,.13)
		var side := Vector3(-sin(angle), 0, cos(angle))*.028
		var root := Vector3(cos(angle), 0, sin(angle))*.03
		var tip := root+lean+Vector3(0, blade_rng.randf_range(.2,.3), 0)
		var base_color := Color(.33,.5,.17)
		var tip_color := Color(.64,.8,.32)
		for v in [[root-side, base_color], [root+side, base_color], [tip, tip_color]]:
			st.set_color(v[1])
			st.set_normal(Vector3.UP)
			st.add_vertex(v[0])
	return st.commit()

func board_mesh() -> Mesh:
	var box := BoxMesh.new()
	box.size = Vector3.ONE
	return box
