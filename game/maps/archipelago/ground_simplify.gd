extends RefCounted
## Fewer ground triangles where nobody can tell (plan C step 1b; bake only: tools/bake_archipelago.gd
## hands it to GroundChunks.build). Each chunk's triangles are split into zones and each zone is
## simplified on its own (SurfaceTool.generate_lod, positions only: the kept vertices stay bit copies,
## so their normals, tangents and UVs are the ground's own) within its zone's error bound:
##   lock   exactly as they are: anything a vertex of which lies in a LOCK zone (see below)
##   coast  reaching below COAST_BELOW (the water line and the beach): 5 mm, 1.0 degree
##   land   10 mm, 1.5 degrees
##   rough  steep (face normal y under STEEP_NORMAL_Y) or under the sea (all below SUBMERGED_BELOW):
##          20 mm, 2 degrees
## generate_lod keeps the open border of what it is given (tests/terrain_probe.gd --border: every
## border vertex and edge, also on long straight borders), so zones and chunks meet as before: no
## cracks, no T-junctions. Each simplified zone is then checked at its original triangles' corners,
## centres and edge middles (height and interpolated normal against the original surface); triangles where
## a check fails are pinned (locked) and the zone simplified again, up to PIN_ROUNDS times; a zone
## that still fails, or whose border did not survive, keeps its triangles as they are.
## LOCK zones (painted on a GRID metre raster over the map): the headland cliff, the ponds (+2 m),
## the waterfall (8 m), every building pad, the roads and their plazas, bridge and pier ends, the
## points stories and quests use (doors, places, the cafe terrace slot, pavilion floors) 2 m and more,
## the village furniture area, every placed prop (lamps 4 m, trees 2.5 m), and the shore rocks,
## cliff rocks and detail meshes where they touch the ground.
const ZONES := {"coast": [0.005, 1.0], "land": [0.010, 1.5], "rough": [0.020, 2.0]}
const COAST_BELOW := 0.6
const SUBMERGED_BELOW := -0.15
const STEEP_NORMAL_Y := 0.9
const PIN_ROUNDS := 4
const GRID := 0.25
const GRID_FROM := Vector2(-136, -120)
const GRID_CELLS := Vector2i(960, 960)

var locks := PackedByteArray()
var stats := {"zones": {}, "pinned": 0, "kept_exact_zones": 0, "border_fallbacks": 0, "locked_tris": 0, "tris_in": 0, "tris_out": 0}

func _init(map: Node3D) -> void:
	locks.resize(GRID_CELLS.x*GRID_CELLS.y)
	_paint(map)

## --- lock raster ---------------------------------------------------------------------------

func _cell(p: Vector2) -> Vector2i:
	return Vector2i(floori((p.x-GRID_FROM.x)/GRID), floori((p.y-GRID_FROM.y)/GRID))

func locked_at(x: float, z: float) -> bool:
	var c := _cell(Vector2(x, z))
	if c.x < 0 or c.y < 0 or c.x >= GRID_CELLS.x or c.y >= GRID_CELLS.y: return false
	return locks[c.y*GRID_CELLS.x+c.x] != 0

## Marks every raster cell whose centre `inside` says is in.
func _area(low: Vector2, high: Vector2, inside: Callable) -> void:
	var a := _cell(low)-Vector2i.ONE
	var b := _cell(high)+Vector2i.ONE
	for cz in range(maxi(a.y, 0), mini(b.y+1, GRID_CELLS.y)):
		for cx in range(maxi(a.x, 0), mini(b.x+1, GRID_CELLS.x)):
			var p := GRID_FROM+Vector2(cx+0.5, cz+0.5)*GRID
			if inside.call(p): locks[cz*GRID_CELLS.x+cx] = 1

func circle(at: Vector2, radius: float) -> void:
	var r := radius+GRID
	_area(at-Vector2.ONE*r, at+Vector2.ONE*r, func(p: Vector2): return p.distance_to(at) <= r)

func ellipse(at: Vector2, radii: Vector2) -> void:
	var r := radii+Vector2.ONE*GRID
	_area(at-r, at+r, func(p: Vector2): return ((p-at)/r).length() <= 1.0)

func capsule(a: Vector2, b: Vector2, radius: float) -> void:
	var r := radius+GRID
	_area(a.min(b)-Vector2.ONE*r, a.max(b)+Vector2.ONE*r, func(p: Vector2): return p.distance_to(Geometry2D.get_closest_point_to_segment(p, a, b)) <= r)

## A rectangle (half extents) turned by `yaw` degrees as building_layout.gd turns pads.
func box(at: Vector2, half: Vector2, yaw: float) -> void:
	var h := half+Vector2.ONE*GRID
	var reach := h.length()
	var a := deg_to_rad(yaw)
	_area(at-Vector2.ONE*reach, at+Vector2.ONE*reach, func(p: Vector2):
		var o := p-at
		return absf(o.x*cos(a)-o.y*sin(a)) <= h.x and absf(o.x*sin(a)+o.y*cos(a)) <= h.y)

func _paint(map: Node3D) -> void:
	var Town = load("res://scripts/town.gd")
	var Roads = load("res://scripts/roads.gd")
	# The headland cliff (its own normal field in ground_surface.gdshader), the ponds, the waterfall.
	ellipse(Vector2(-2.6, -10.3), Vector2(4.8, 3.6)*2.15+Vector2.ONE)
	ellipse(Vector2(51, -43), Vector2(9, 7)+Vector2.ONE*2.0)
	ellipse(Vector2(-48, 44), Vector2(12, 9)+Vector2.ONE*2.0)
	circle(Vector2(0.996, -7.937), 8.0)
	# Building pads with their blend and a metre more.
	var placements: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://maps/archipelago/building_placements.json"))
	for spec: Dictionary in placements.buildings:
		var blend := float(spec.pad_blend_m)+1.0
		box(Vector2(spec.position[0], spec.position[2]), Vector2(spec.pad_half_extents[0], spec.pad_half_extents[1])+Vector2.ONE*blend, float(spec.yaw_degrees))
	# Roads (half width and a metre for their border stones and tufts) and their plazas.
	for road: Array in Roads.ROADS:
		var points: Array = road[2]
		for k in points.size()-1: capsule(points[k], points[k+1], float(road[1])*0.5+1.0)
		for point: Vector2 in points: circle(point, 3.5)
	# Bridge and pier ends, pavilion floors and their ramps.
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://maps/archipelago/environment_layout.json"))
	for bridge: Dictionary in layout.bridges:
		circle(Vector2(bridge.a[0], bridge.a[1]), 5.0)
		circle(Vector2(bridge.b[0], bridge.b[1]), 5.0)
	for pier: Dictionary in layout.piers:
		capsule(Vector2(pier.landing[0], pier.landing[1]), Vector2(pier.tip[0], pier.tip[1]), 4.0)
	var Map = load("res://maps/archipelago/archipelago.gd")
	for id in Map.OPEN_STRUCTURES: circle(Map.OPEN_STRUCTURES[id][0], float(Map.OPEN_STRUCTURES[id][1])+2.6)
	# Points the stories and quests use.
	for door: Dictionary in Town.DOORS:
		circle(Vector2(door.at), 3.0)
		if door.has("center"): circle(Vector2(door.center), 2.0)
	for place: Dictionary in Town.PLACES: circle(Vector2(place.at), 3.0)
	for point: Vector2 in [Town.SPAWN, Town.HOME_DOOR, Town.HOME_RETURN_AT, Town.WORKSHOP_DOOR, Town.WORKSHOP_RETURN_AT, Town.GATE, Vector2(-60.2, -27.6)]: circle(point, 3.0)
	for plot: Vector2 in Town.PLOTS: circle(plot, 2.5)
	# The village furniture area (server coordinates |x|, |z| <= 11 around the town green).
	box(Town.VILLAGE_ORIGIN, Vector2(13, 13), 0.0)
	# Every placed prop: lamps 4 m, trees 2.5 m (their buried roots), the rest 1.5 m (by scale).
	for spec: Dictionary in layout.instances:
		var id := String(spec.id)
		var scale := float(spec.get("scale", 1.0))
		var radius := 4.0 if id == "27_lamp" else (2.5*scale if id in ["37_round_tree", "38_conifer", "39_palm"] else maxf(1.0, 1.5*scale))
		circle(Vector2(spec.position[0], spec.position[2]), radius)
	# Rocks and detail meshes where they come near the ground.
	var terrain: Node = map.get_child(0)
	for mesh: MeshInstance3D in terrain.find_children("*", "MeshInstance3D", true, false):
		var name := String(mesh.name)
		if not ("__shore_rock" in name or "Waterfall__cliff_rock" in name or name.begins_with("Details__")) or mesh.mesh == null: continue
		var reach := 0.75 if not name.begins_with("Details__") else 0.5
		for surface in mesh.mesh.get_surface_count():
			for point: Vector3 in mesh.mesh.surface_get_arrays(surface)[Mesh.ARRAY_VERTEX]:
				var world := mesh.global_transform*point
				if world.y < 4.0: circle(Vector2(world.x, world.z), reach)
	var painted := 0
	for value in locks: painted += value
	stats["locked_area_m2"] = snappedf(painted*GRID*GRID, 1.0)

## --- simplification ----------------------------------------------------------------------

## The zone of triangle (a, b, c): "lock", "coast", "rough" or "land".
func zone_of(a: Vector3, b: Vector3, c: Vector3, pinned: Dictionary, key: Vector3i) -> String:
	if pinned.has(key) or locked_at(a.x, a.z) or locked_at(b.x, b.z) or locked_at(c.x, c.z): return "lock"
	var centre := (a+b+c)/3.0
	if locked_at(centre.x, centre.z): return "lock"
	var low := minf(a.y, minf(b.y, c.y))
	var high := maxf(a.y, maxf(b.y, c.y))
	if high < SUBMERGED_BELOW: return "rough"
	if low < COAST_BELOW: return "coast"
	var normal := (b-a).cross(c-a).normalized()
	if absf(normal.y) < STEEP_NORMAL_Y: return "rough"
	return "land"

## The triangles one chunk keeps (vertex indices of `arrays`, 3 a triangle).
func triangles(arrays: Array, triples: PackedInt32Array, island: String) -> PackedInt32Array:
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	stats.tris_in += triples.size()/3
	var pinned := {}
	var out := PackedInt32Array()
	for round in PIN_ROUNDS+1:
		var zones := {"lock": PackedInt32Array(), "coast": PackedInt32Array(), "land": PackedInt32Array(), "rough": PackedInt32Array()}
		for t in range(0, triples.size(), 3):
			var key := Vector3i(triples[t], triples[t+1], triples[t+2])
			var zone := zone_of(verts[triples[t]], verts[triples[t+1]], verts[triples[t+2]], pinned, key)
			zones[zone].append_array(PackedInt32Array([triples[t], triples[t+1], triples[t+2]]))
		out = zones.lock.duplicate()
		var failed := 0
		var last := round == PIN_ROUNDS
		var simplified := {}
		for zone: String in ["coast", "land", "rough"]:
			var tris: PackedInt32Array = zones[zone]
			if tris.size() < 9:
				out.append_array(tris)
				continue
			var bound: Array = ZONES[zone]
			var lod := _simplify(verts, tris, float(bound[0]))
			if lod.is_empty():
				stats.border_fallbacks += 1
				out.append_array(tris)
				continue
			var bad := _check(verts, normals, tris, lod, float(bound[0]), float(bound[1]))
			if bad.is_empty():
				simplified[zone] = [tris.size()/3, lod.size()/3]
				out.append_array(lod)
				continue
			if last:
				stats.kept_exact_zones += 1
				out.append_array(tris)
				continue
			failed += bad.size()
			for key in bad: pinned[key] = true
		if failed == 0 or last:
			for zone in simplified:
				var z: Dictionary = stats.zones.get(zone, {"in": 0, "out": 0})
				z["in"] += simplified[zone][0]
				z["out"] += simplified[zone][1]
				stats.zones[zone] = z
			break
	stats.pinned += pinned.size()
	stats.tris_out += out.size()/3
	var locked := 0
	for t in range(0, triples.size(), 3):
		if zone_of(verts[triples[t]], verts[triples[t+1]], verts[triples[t+2]], {}, Vector3i.ZERO) == "lock": locked += 1
	stats.locked_tris += locked
	return out

## generate_lod on a zone's triangles (positions only), as vertex indices of `verts`; empty when the
## zone's open border did not come through whole.
func _simplify(verts: PackedVector3Array, tris: PackedInt32Array, bound: float) -> PackedInt32Array:
	var remap := {}
	var order := PackedInt32Array()
	var local := PackedInt32Array()
	local.resize(tris.size())
	var points := PackedVector3Array()
	for n in tris.size():
		var i := tris[n]
		if not remap.has(i):
			remap[i] = order.size()
			order.append(i)
			points.append(verts[i])
		local[n] = remap[i]
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = points
	arrays[Mesh.ARRAY_INDEX] = local
	var tool := SurfaceTool.new()
	tool.create_from_arrays(arrays)
	var box := AABB(points[0], Vector3.ZERO)
	for p in points: box = box.expand(p)
	var extent := maxf(box.size.x, maxf(box.size.y, box.size.z))
	var lod := tool.generate_lod(bound/maxf(extent, 0.0001), 3)
	# Its open border must come through whole (edges and vertices).
	var edges := {}
	for t in range(0, lod.size(), 3):
		for k in 3:
			var a := lod[t+k]
			var b := lod[t+(k+1)%3]
			edges[Vector2i(mini(a, b), maxi(a, b))] = true
	var uses := {}
	for t in range(0, local.size(), 3):
		for k in 3:
			var a := local[t+k]
			var b := local[t+(k+1)%3]
			var e := Vector2i(mini(a, b), maxi(a, b))
			uses[e] = uses.get(e, 0)+1
	for e in uses:
		if uses[e] == 1 and not edges.has(e): return PackedInt32Array()
	var out := PackedInt32Array()
	out.resize(lod.size())
	for n in lod.size(): out[n] = order[lod[n]]
	return out

## The original triangles (as Vector3i keys) where the simplified surface strays past the bounds:
## height at every original vertex and triangle centre, interpolated normal at the same points.
func _check(verts: PackedVector3Array, normals: PackedVector3Array, tris: PackedInt32Array, lod: PackedInt32Array, height: float, angle: float) -> Array:
	var after := Patch.new(verts, normals, lod)
	var bad := {}
	var limit := deg_to_rad(angle)
	for t in range(0, tris.size(), 3):
		var key := Vector3i(tris[t], tris[t+1], tris[t+2])
		var a := verts[tris[t]]
		var b := verts[tris[t+1]]
		var c := verts[tris[t+2]]
		# Corners, centre and edge middles (where an original edge crosses a new one the difference bends).
		var samples := [(a+b+c)/3.0, a, b, c, (a+b)*0.5, (b+c)*0.5, (c+a)*0.5]
		var weights := [Vector3.ONE/3.0, Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1), Vector3(0.5, 0.5, 0), Vector3(0, 0.5, 0.5), Vector3(0.5, 0, 0.5)]
		for s in samples.size():
			var p: Vector3 = samples[s]
			var w: Vector3 = weights[s]
			var before_normal := (normals[tris[t]]*w.x+normals[tris[t+1]]*w.y+normals[tris[t+2]]*w.z).normalized()
			var hit := after.sample(Vector2(p.x, p.z))
			if hit.is_empty():
				# On the zone's border (kept): a point there is on a kept edge.
				continue
			if absf(float(hit.y)-p.y) > height or before_normal.angle_to(hit.normal) > limit:
				bad[key] = true
				break
	return bad.keys()

## The surface of some triangles: height and interpolated normal under a point.
class Patch:
	const BUCKET := 1.0
	var verts: PackedVector3Array
	var normals: PackedVector3Array
	var tris: PackedInt32Array
	var buckets := {}

	func _init(v: PackedVector3Array, n: PackedVector3Array, t: PackedInt32Array) -> void:
		verts = v
		normals = n
		tris = t
		for i in range(0, t.size(), 3):
			var a := v[t[i]]
			var b := v[t[i+1]]
			var c := v[t[i+2]]
			var low := Vector2i(floori(minf(a.x, minf(b.x, c.x))/BUCKET), floori(minf(a.z, minf(b.z, c.z))/BUCKET))
			var high := Vector2i(floori(maxf(a.x, maxf(b.x, c.x))/BUCKET), floori(maxf(a.z, maxf(b.z, c.z))/BUCKET))
			for bz in range(low.y, high.y+1):
				for bx in range(low.x, high.x+1):
					var key := Vector2i(bx, bz)
					if not buckets.has(key): buckets[key] = PackedInt32Array()
					buckets[key].append(i)

	func sample(at: Vector2) -> Dictionary:
		var key := Vector2i(floori(at.x/BUCKET), floori(at.y/BUCKET))
		if not buckets.has(key): return {}
		var best := {}
		for i in buckets[key]:
			var a := verts[tris[i]]
			var b := verts[tris[i+1]]
			var c := verts[tris[i+2]]
			var v0 := Vector2(b.x-a.x, b.z-a.z)
			var v1 := Vector2(c.x-a.x, c.z-a.z)
			var v2 := Vector2(at.x-a.x, at.y-a.z)
			var den := v0.x*v1.y-v1.x*v0.y
			if absf(den) < 1e-12: continue
			var u := (v2.x*v1.y-v1.x*v2.y)/den
			var v := (v0.x*v2.y-v2.x*v0.y)/den
			if u < -1e-5 or v < -1e-5 or u+v > 1.0+1e-5: continue
			var y := a.y+u*(b.y-a.y)+v*(c.y-a.y)
			if best.is_empty() or y > float(best.y):
				best = {"y": y, "normal": (normals[tris[i]]*(1.0-u-v)+normals[tris[i+1]]*u+normals[tris[i+2]]*v).normalized()}
		return best
