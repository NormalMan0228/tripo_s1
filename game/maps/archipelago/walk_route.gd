extends RefCounted
## Walkable route for the route guide (scripts/guide.gd): the roads, bridges and door
## spurs (shadow_paths.gd) carry the long way, and the off-road legs (walker -> road,
## road -> goal, the straight shortcut to a close goal) are drawn only where the walker
## can really go. Every SPACING metres along such a line the ground (the guide's cached
## probe, roofs skipped) must be dry land or a deck, may not jump more than MAX_RISE
## from the last sample (a wall, a ledge, a cliff), and a walker-sized capsule standing
## there may touch nothing static (buildings, fences, rocks, props). When the nearest
## way onto the road is blocked the next cheapest road point in sight is taken; a goal
## (or a walker) no road point sees is walked round to on a coarse grid (A*, detour()),
## and one nothing reaches (inside a building, out at sea) ends the trail on the road
## nearest to it. Line and cell answers are cached until the goal changes, so a refresh
## (guide.gd REFRESH 0.3 s) repeats a few shape queries per metre walked at most;
## nothing runs per frame.
##   plan(guide, goal)                once per goal (Dijkstra over ~150 road nodes)
##   route(guide, from) -> PackedVector2Array   walker -> goal polyline
## `guide` gives paths (shadow_paths.gd), field(seeds), ground_y(p) and the world.
const Town := preload("res://scripts/town.gd")

## Static colliders only: other walkers (layer 4) are left out.
const MASK := 1|2|8|16|32
const SPACING := 0.5
## A little under the walker's radius (controller_profile.gd BODY_RADIUS .32): a gap it fits is open.
const RADIUS := 0.28
const HEIGHT := 1.5
## The capsule floats this high over the ground sample (steps and kerbs are fine).
const LIFT := 0.36
const MAX_RISE := 0.45
const DRY := Town.SHORE_MIN_Y+0.15
## The walker's own spot and the goal's last metre are not checked (it stands where it
## stands; the goal may be a prop, a door step or a fishing spot at the water's edge).
const SKIP_START := 0.5
const SKIP_END := 1.0
const CACHE_LIMIT := 4096
## Road points within REACH are tried for an off-road leg, cheapest first, at most
## GOAL_CHECKS / START_CHECKS lines each; past SLACK metres beyond the first one in
## sight the goal stops looking.
const REACH := 30.0
const GOAL_CHECKS := 10
const START_CHECKS := 8
const SLACK := 8.0
## A goal this close may be reached straight when the roads go round (guide.gd DIRECT).
const DIRECT := 14.0
## Closer than this to the road counts as on it.
const ON_ROAD := 0.4
## Detour grid: CELL-metre cells in the box round both ends grown by MARGIN (at most
## MAX_CELLS), tried toward the first LEAD_TRIES road points.
const CELL := 1.0
const MARGIN := 8.0
const MAX_CELLS := 4000
const LEAD_TRIES := 3

var paths
var query: PhysicsShapeQueryParameters3D
var cache := {}
var strict := {}
## Detour grid: cell -> ground height, NAN where the walker cannot stand.
var cells := {}
## Shape queries since the last plan (tests watch the cost), and the last plan/route time.
var queries := 0
var plan_usec := 0
var route_usec := 0
var goal := Vector2.INF
var cost := PackedFloat32Array()
var next := PackedInt32Array()
## Seed node -> the way off the road toward the goal (the exit point, then any detour
## corners; not the goal itself).
var exits := {}
## Road piece Vector2i(low, high) -> [exit way, metres from its first point to the goal],
## for a walker on the same piece (it walks along it, not out to a node and back).
var edge_exits := {}
## False when nothing reaches the goal: the trail ends on the road.
var reaches := true
## The map's colliders were not there when the goal was planned: plan again.
var stale := false
## The walker's last detour onto the road ([] none) and the pick it leads to.
var lead := PackedVector2Array()
var lead_pick: Array = []

## Bridge decks from the layout: [a, b, half width] (on_deck()).
static var decks: Array = []
const LAYOUT := "res://maps/archipelago/environment_layout.json"

## True on a bridge deck: a deck high over a low bank is ground, not a roof to look under
## (guide.gd probe()).
static func on_deck(p: Vector2) -> bool:
	if decks.is_empty():
		var manifest = JSON.parse_string(FileAccess.get_file_as_string(LAYOUT)) if FileAccess.file_exists(LAYOUT) else null
		if manifest is Dictionary and manifest.get("bridges") is Array:
			for bridge in manifest.bridges:
				decks.append([Vector2(bridge.a[0], bridge.a[1]), Vector2(bridge.b[0], bridge.b[1]), float(bridge.get("width_m", 3.4))*0.5+0.3])
		if decks.is_empty(): decks.append([Vector2.INF, Vector2.INF, 0.0])
	for deck in decks:
		if deck[2] > 0.0 and Geometry2D.get_closest_point_to_segment(p, deck[0], deck[1]).distance_to(p) < deck[2]: return true
	return false

func _init() -> void:
	var capsule := CapsuleShape3D.new()
	capsule.radius = RADIUS
	capsule.height = HEIGHT
	query = PhysicsShapeQueryParameters3D.new()
	query.shape = capsule
	query.collision_mask = MASK
	query.collide_with_areas = false

func plan(guide: Node, at: Vector2) -> void:
	var started := Time.get_ticks_usec()
	paths = guide.paths
	goal = at
	cache.clear()
	strict.clear()
	cells.clear()
	queries = 0
	exits = {}
	edge_exits = {}
	reaches = true
	stale = false
	lead = PackedVector2Array()
	lead_pick = []
	var seeds := {}
	var found := INF
	var checks := 0
	var list := hooks(at)
	for hook in list:
		if checks >= GOAL_CHECKS or float(hook[3]) > found+SLACK: break
		checks += 1
		if not clear(guide, hook[0], at): continue
		found = minf(found, hook[3])
		_seed(seeds, hook, hook[3], PackedVector2Array([hook[0]]))
	if seeds.is_empty():
		# No road point sees the goal: walk round to it from the nearest few.
		for hook in list.slice(0, LEAD_TRIES):
			var way := detour(guide, hook[0], at)
			if way.is_empty(): continue
			_seed(seeds, hook, length_of(way), way.slice(0, way.size()-1))
			break
	if seeds.is_empty() and not list.is_empty():
		reaches = false
		_seed(seeds, list[0], 0.0, PackedVector2Array([list[0][0]]))
	if seeds.is_empty():
		cost = PackedFloat32Array()
		next = PackedInt32Array()
	else:
		var result: Array = guide.field(seeds)
		cost = result[0]
		next = result[1]
	plan_usec = Time.get_ticks_usec()-started

func _seed(seeds: Dictionary, hook: Array, base: float, way: PackedVector2Array) -> void:
	var q: Vector2 = hook[0]
	if hook[1] != hook[2]:
		var key := Vector2i(mini(hook[1], hook[2]), maxi(hook[1], hook[2]))
		if not edge_exits.has(key) or float(edge_exits[key][1]) > base: edge_exits[key] = [way, base]
	for node in [hook[1], hook[2]]:
		var c: float = base+q.distance_to(paths.points[node])
		if c < float(seeds.get(node, INF)):
			seeds[node] = c
			exits[node] = way

## Road points near p, nearest first, as [point, node a, node b, metres]: the closest
## point of every road piece within REACH and both of its ends (a == b for an end).
## The closest point of the whole network is always there.
func hooks(p: Vector2) -> Array:
	var out: Array = []
	var seen := {}
	var nearest: Array = []
	var gap := INF
	for edge in paths.edges():
		var q := Geometry2D.get_closest_point_to_segment(p, paths.points[edge[0]], paths.points[edge[1]])
		var d := q.distance_to(p)
		if d < gap:
			gap = d
			nearest = [q, edge[0], edge[1], d]
		if d > REACH: continue
		out.append([q, edge[0], edge[1], d])
		for node in edge:
			if seen.has(node): continue
			seen[node] = true
			var at: Vector2 = paths.points[node]
			out.append([at, node, node, at.distance_to(p)])
	if out.is_empty() and not nearest.is_empty(): out.append(nearest)
	out.sort_custom(func(x, y): return x[3] < y[3])
	return out

func route(guide: Node, from: Vector2) -> PackedVector2Array:
	if stale: plan(guide, goal)
	var started := Time.get_ticks_usec()
	var out := PackedVector2Array([from])
	if cost.is_empty():
		out.append(goal)
		route_usec = Time.get_ticks_usec()-started
		return out
	# Every road point near the walker with the cheapest way on from it:
	# [order, hook, node or -2 (same piece as the goal's exit), total metres]. The nearest
	# road point comes first (the walker steps onto the road, not across the grass to a far
	# one); the cost only breaks near ties, a farther one is for when the nearer are blocked.
	var picks: Array = []
	for hook in hooks(from):
		var total := INF
		var via := -1
		for node in [hook[1], hook[2]]:
			var c: float = hook[0].distance_to(paths.points[node])+cost[node]
			if c < total:
				total = c
				via = node
		if hook[1] != hook[2]:
			var key := Vector2i(mini(hook[1], hook[2]), maxi(hook[1], hook[2]))
			if edge_exits.has(key):
				var c: float = hook[0].distance_to(edge_exits[key][0][0])+float(edge_exits[key][1])
				if c <= total:
					total = c
					via = -2
		if total < INF: picks.append([float(hook[3])+(float(hook[3])+total)*0.01, hook, via, float(hook[3])+total])
	picks.sort_custom(func(x, y): return x[0] < y[0])
	var straight := from.distance_to(goal)
	if reaches and straight < DIRECT and (picks.is_empty() or straight <= float(picks[0][3])+0.5) and clear(guide, from, goal):
		out.append(goal)
		route_usec = Time.get_ticks_usec()-started
		return out
	if picks.is_empty():
		out.append(goal)
		route_usec = Time.get_ticks_usec()-started
		return out
	var pick: Array = []
	var checks := 0
	for candidate in picks:
		if float(candidate[1][3]) < ON_ROAD:
			pick = candidate
			break
		if checks >= START_CHECKS: break
		checks += 1
		if clear(guide, from, candidate[1][0]):
			pick = candidate
			break
	if pick.is_empty():
		# No road point in sight (a back garden): walk round to one on the grid.
		pick = lead_in(guide, from, picks, out)
	if pick.is_empty():
		# Walled in, out on the rocks: the nearest road point, as the old guide did.
		pick = picks[0]
		for candidate in picks:
			if float(candidate[1][3]) < float(pick[1][3]): pick = candidate
	var hook: Array = pick[1]
	_add(out, hook[0])
	if int(pick[2]) == -2:
		var key := Vector2i(mini(hook[1], hook[2]), maxi(hook[1], hook[2]))
		for p in edge_exits[key][0]: _add(out, p)
	else:
		var node: int = pick[2]
		var last := node
		var guard := 0
		while node >= 0 and guard < 512:
			_add(out, paths.points[node])
			last = node
			node = next[node]
			guard += 1
		if exits.has(last):
			for p in exits[last]: _add(out, p)
	if reaches: _add(out, goal)
	route_usec = Time.get_ticks_usec()-started
	return out

func _add(out: PackedVector2Array, p: Vector2) -> void:
	if out[out.size()-1].distance_to(p) > 0.3: out.append(p)

static func length_of(way: PackedVector2Array) -> float:
	var total := 0.0
	for i in way.size()-1: total += way[i].distance_to(way[i+1])
	return total

## The walker's detour onto the road: the cached one while the walker stays on it and
## sees its next corner, else a fresh one to the cheapest of the first few road points.
## Appends its corners to out and returns the pick it reaches ([] none).
func lead_in(guide: Node, from: Vector2, picks: Array, out: PackedVector2Array) -> Array:
	if lead.size() >= 2:
		var k := 0
		for i in lead.size():
			if lead[i].distance_to(from) < lead[k].distance_to(from): k = i
		if lead[k].distance_to(from) < 3.0 and k+1 < lead.size() and clear(guide, from, lead[k+1]):
			for i in range(k+1, lead.size()-1): _add(out, lead[i])
			return lead_pick
	lead = PackedVector2Array()
	lead_pick = []
	for candidate in picks.slice(0, LEAD_TRIES):
		var way := detour(guide, from, candidate[1][0])
		if way.is_empty(): continue
		lead = way
		lead_pick = candidate
		for i in range(1, way.size()-1): _add(out, way[i])
		return candidate
	return []

## Walkable way a -> b on the detour grid (a and b included, corners only), [] when the
## box holds none. Both ends count as walkable (the walker stands there; the goal may be a prop).
func detour(guide: Node, a: Vector2, b: Vector2) -> PackedVector2Array:
	if not guide.is_inside_tree(): return PackedVector2Array()
	var ca := Vector2i(roundi(a.x/CELL), roundi(a.y/CELL))
	var cb := Vector2i(roundi(b.x/CELL), roundi(b.y/CELL))
	var grow := ceili(MARGIN/CELL)
	var lo := Vector2i(mini(ca.x, cb.x)-grow, mini(ca.y, cb.y)-grow)
	var hi := Vector2i(maxi(ca.x, cb.x)+grow, maxi(ca.y, cb.y)+grow)
	if (hi.x-lo.x+1)*(hi.y-lo.y+1) > MAX_CELLS: return PackedVector2Array()
	var space: PhysicsDirectSpaceState3D = guide.get_world_3d().direct_space_state
	var ends := {ca: guide.ground_y(a), cb: guide.ground_y(b)}
	if is_nan(ends[ca]) or is_nan(ends[cb]): return PackedVector2Array()
	var g := {ca: 0.0}
	var came := {}
	var heap_f := PackedFloat32Array()
	var heap_c: Array[Vector2i] = []
	_push(heap_f, heap_c, ca.distance_to(cb)*CELL, ca)
	var found := false
	while not heap_c.is_empty():
		var c := _pop(heap_f, heap_c)
		if c == cb:
			found = true
			break
		var yc: float = ends[c] if ends.has(c) else cell_y(guide, space, c)
		for dx in [-1, 0, 1]:
			for dy in [-1, 0, 1]:
				if dx == 0 and dy == 0: continue
				var n := c+Vector2i(dx, dy)
				if n.x < lo.x or n.y < lo.y or n.x > hi.x or n.y > hi.y: continue
				var yn: float = ends[n] if ends.has(n) else cell_y(guide, space, n)
				if is_nan(yn): continue
				var step := CELL*(1.4142 if dx != 0 and dy != 0 else 1.0)
				if absf(yn-yc) > MAX_RISE*step/SPACING: continue
				if dx != 0 and dy != 0:
					# No cutting a corner past a blocked cell.
					var side_a := c+Vector2i(dx, 0)
					var side_b := c+Vector2i(0, dy)
					if not ends.has(side_a) and is_nan(cell_y(guide, space, side_a)): continue
					if not ends.has(side_b) and is_nan(cell_y(guide, space, side_b)): continue
				var cost_n: float = float(g[c])+step
				if cost_n < float(g.get(n, INF)):
					g[n] = cost_n
					came[n] = c
					_push(heap_f, heap_c, cost_n+n.distance_to(cb)*CELL, n)
	if not found: return PackedVector2Array()
	var chain: Array[Vector2i] = [cb]
	while chain[chain.size()-1] != ca: chain.append(came[chain[chain.size()-1]])
	chain.reverse()
	# Corners only, then straight cuts across corners the walker can see past.
	var way := PackedVector2Array([a])
	for i in range(1, chain.size()-1):
		if chain[i+1]-chain[i] != chain[i]-chain[i-1]: way.append(Vector2(chain[i])*CELL)
	way.append(b)
	var smooth := PackedVector2Array([way[0]])
	var i := 0
	var tries := 0
	while i < way.size()-1:
		var j := way.size()-1
		while j > i+1:
			if tries >= 16:
				j = i+1
				break
			tries += 1
			if clear_strict(guide, way[i], way[j]): break
			j -= 1
		smooth.append(way[j])
		i = j
	return smooth

func cell_y(guide: Node, space: PhysicsDirectSpaceState3D, c: Vector2i) -> float:
	if cells.has(c): return cells[c]
	var p := Vector2(c)*CELL
	var y: float = guide.ground_y(p)
	if is_nan(y) or y < DRY:
		y = NAN
	else:
		query.transform = Transform3D(Basis.IDENTITY, Vector3(p.x, y+LIFT+HEIGHT*0.5, p.y))
		queries += 1
		if not space.intersect_shape(query, 1).is_empty(): y = NAN
	cells[c] = y
	return y

static func _push(heap_f: PackedFloat32Array, heap_c: Array[Vector2i], f: float, c: Vector2i) -> void:
	heap_f.append(f)
	heap_c.append(c)
	var i := heap_f.size()-1
	while i > 0:
		var up := (i-1)/2
		if heap_f[up] <= heap_f[i]: break
		var tf := heap_f[up]
		heap_f[up] = heap_f[i]
		heap_f[i] = tf
		var tc := heap_c[up]
		heap_c[up] = heap_c[i]
		heap_c[i] = tc
		i = up

static func _pop(heap_f: PackedFloat32Array, heap_c: Array[Vector2i]) -> Vector2i:
	var top := heap_c[0]
	var last := heap_f.size()-1
	heap_f[0] = heap_f[last]
	heap_c[0] = heap_c[last]
	heap_f.resize(last)
	heap_c.resize(last)
	var i := 0
	while true:
		var l := i*2+1
		var r := l+1
		var m := i
		if l < last and heap_f[l] < heap_f[m]: m = l
		if r < last and heap_f[r] < heap_f[m]: m = r
		if m == i: break
		var tf := heap_f[m]
		heap_f[m] = heap_f[i]
		heap_f[i] = tf
		var tc := heap_c[m]
		heap_c[m] = heap_c[i]
		heap_c[i] = tc
		i = m
	return top

## True when the walker can go straight from a to b (cached per goal on a half-metre grid).
func clear(guide: Node, a: Vector2, b: Vector2) -> bool:
	var key := Vector4i(roundi(a.x*2.0), roundi(a.y*2.0), roundi(b.x*2.0), roundi(b.y*2.0))
	if cache.has(key): return cache[key]
	var state := _check(guide, a, b)
	if state < 0:
		stale = true
		return false
	if cache.size() > CACHE_LIMIT: cache.clear()
	cache[key] = state == 1
	return state == 1

## A detour cut: every sample checked but the very ends (corners stand on walkable cells).
func clear_strict(guide: Node, a: Vector2, b: Vector2) -> bool:
	var key := Vector4i(roundi(a.x*2.0), roundi(a.y*2.0), roundi(b.x*2.0), roundi(b.y*2.0))
	if strict.has(key): return strict[key]
	var ok := _check(guide, a, b, 0.25, 0.25) == 1
	strict[key] = ok
	return ok

## 1 clear, 0 blocked, -1 unknown (no ground under a yet: the map is still loading).
func _check(guide: Node, a: Vector2, b: Vector2, skip_start := SKIP_START, skip_end := SKIP_END) -> int:
	if not guide.is_inside_tree(): return -1
	var last: float = guide.ground_y(a)
	if is_nan(last): return -1
	var length := a.distance_to(b)
	if length < skip_start+skip_end: return 1
	var space: PhysicsDirectSpaceState3D = guide.get_world_3d().direct_space_state
	var steps := ceili(length/SPACING)
	for i in range(1, steps):
		var d := length*i/steps
		if d < skip_start or length-d < skip_end: continue
		var p := a.lerp(b, float(i)/steps)
		var y: float = guide.ground_y(p)
		if is_nan(y) or y < DRY: return 0
		if absf(y-last) > MAX_RISE: return 0
		last = y
		query.transform = Transform3D(Basis.IDENTITY, Vector3(p.x, y+LIFT+HEIGHT*0.5, p.y))
		queries += 1
		if not space.intersect_shape(query, 1).is_empty(): return 0
	return 1
