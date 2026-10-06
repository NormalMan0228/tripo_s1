extends RefCounted
## Walkable graph for the shadow folk, rebuilt from roads.gd ROADS every time the
## village loads (another pass may re-route the polylines). Road ends that touch
## another road are joined to it, the four bridges join the islands, a few authored
## spurs reach piers and the orchard, and dead ends at a door stop short of the
## door pad so a shadow never stands where the walker enters a building.

## Shadows stop this far from a door's step (village_life opens doors at 1.9 m).
const DOOR_CLEARANCE := 2.9
const MERGE := 0.6
const JOIN := 2.4

var points: Array[Vector2] = []
var links: Array = []
## "road", "bridge", "spur", "spot" (spur tip: a view), "porch" (stops before a door)
var kinds: Array[String] = []
## For porches: where the door is, so the shadow can face it.
var faces: Dictionary = {}
## Spot node -> spot id (SPURS name or road-end name).
var spot_names: Dictionary = {}
## Side offset per directed edge (Vector2i(a, b) -> metres to the right of a->b),
## chosen by fit_lanes() so the lane clears props that poke onto the path.
var lanes: Dictionary = {}
const LANE := 0.32
## Each edge as [a, b]; rebuilt by edges().
var _edges: Array = []

func build(roads: Array, bridges: Array, doors: Array, spurs: Array) -> void:
	points.clear(); links.clear(); kinds.clear(); faces.clear(); spot_names.clear()
	var road_ends: Array = []
	for road in roads:
		var pts: Array = road[2]
		var previous := -1
		for i in pts.size():
			var node := add_point(pts[i], "road")
			if previous >= 0 and previous != node: link(previous, node)
			previous = node
		road_ends.append([nearest(pts[0]), pts[1]])
		road_ends.append([nearest(pts[pts.size()-1]), pts[pts.size()-2]])
	# A road that ends beside another road's segment (not on a vertex) joins it there.
	for entry in road_ends:
		var end: int = entry[0]
		if links[end].size() != 1: continue
		var best := JOIN
		var best_edge: Array = []
		var best_point := Vector2.ZERO
		for edge in edges():
			if end in edge or edge[0] in links[end] or edge[1] in links[end]: continue
			var q := Geometry2D.get_closest_point_to_segment(points[end], points[edge[0]], points[edge[1]])
			var gap := q.distance_to(points[end])
			if gap < best:
				best = gap; best_edge = edge; best_point = q
		if not best_edge.is_empty():
			link(end, split(best_edge[0], best_edge[1], best_point))
	for bridge in bridges:
		var a: Vector2 = bridge[0]
		var b: Vector2 = bridge[1]
		var na := nearest(a)
		var nb := nearest(b)
		if na < 0 or nb < 0 or points[na].distance_to(a) > 4.0 or points[nb].distance_to(b) > 4.0: continue
		# Walk the deck along its centre line: bank -> deck end -> deck end -> bank.
		var chain: Array[int] = [na]
		for t in [0.0, 0.5, 1.0]:
			var node := add_point(a.lerp(b, t), "bridge")
			if node != chain[chain.size()-1]: chain.append(node)
		if nb != chain[chain.size()-1]: chain.append(nb)
		for i in chain.size()-1: link(chain[i], chain[i+1])
	for spur in spurs:
		var pts: Array = spur[1]
		var start := nearest(pts[0])
		if start < 0: continue
		if points[start].distance_to(pts[0]) > MERGE:
			var edge := nearest_edge(pts[0])
			if edge.is_empty(): continue
			start = split(edge[0], edge[1], Geometry2D.get_closest_point_to_segment(pts[0], points[edge[0]], points[edge[1]]))
		var previous := start
		for i in range(1, pts.size()):
			var node := add_point(pts[i], "spot" if i == pts.size()-1 else "spur")
			link(previous, node)
			previous = node
		spot_names[previous] = spur[0]
	# Dead ends at a door: pull the end back along its only edge.
	for node in points.size():
		if links[node].size() != 1 or kinds[node] != "road": continue
		for door in doors:
			var step: Vector2 = door.at
			if points[node].distance_to(step) >= DOOR_CLEARANCE+0.3: continue
			var other: int = links[node][0]
			var from := points[node]
			var to := points[other]
			var t := 0.0
			while t < 1.0 and from.lerp(to, t).distance_to(step) < DOOR_CLEARANCE: t += 0.02
			points[node] = from.lerp(to, minf(t, 0.92))
			kinds[node] = "porch"
			faces[node] = step
			break
	_edges.clear()

func add_point(p: Vector2, kind: String) -> int:
	for i in points.size():
		if points[i].distance_to(p) < MERGE: return i
	points.append(p)
	links.append([])
	kinds.append(kind)
	_edges.clear()
	return points.size()-1

func link(a: int, b: int) -> void:
	if a == b or b in links[a]: return
	links[a].append(b)
	links[b].append(a)
	_edges.clear()

func unlink(a: int, b: int) -> void:
	links[a].erase(b)
	links[b].erase(a)
	_edges.clear()

## Inserts a node on edge a-b at p and returns it.
func split(a: int, b: int, p: Vector2) -> int:
	if p.distance_to(points[a]) < MERGE: return a
	if p.distance_to(points[b]) < MERGE: return b
	unlink(a, b)
	points.append(p)
	links.append([])
	kinds.append(kinds[a] if kinds[a] == kinds[b] else "road")
	var node := points.size()-1
	link(a, node)
	link(node, b)
	return node

func edges() -> Array:
	if _edges.is_empty():
		for a in points.size():
			for b in links[a]:
				if a < b: _edges.append([a, b])
	return _edges

func nearest(p: Vector2) -> int:
	var best := -1
	var gap := INF
	for i in points.size():
		var d := points[i].distance_to(p)
		if d < gap:
			gap = d; best = i
	return best

func nearest_edge(p: Vector2) -> Array:
	var best: Array = []
	var gap := INF
	for edge in edges():
		var d := Geometry2D.get_closest_point_to_segment(p, points[edge[0]], points[edge[1]]).distance_to(p)
		if d < gap:
			gap = d; best = edge
	return best

## The point of the network closest to p.
func closest_point(p: Vector2) -> Vector2:
	var edge := nearest_edge(p)
	if edge.is_empty(): return p
	return Geometry2D.get_closest_point_to_segment(p, points[edge[0]], points[edge[1]])

## Distance from p to the closest edge of the network.
func distance_to_network(p: Vector2) -> float:
	var edge := nearest_edge(p)
	if edge.is_empty(): return INF
	return Geometry2D.get_closest_point_to_segment(p, points[edge[0]], points[edge[1]]).distance_to(p)

## Shortest node route from a to b (both included), or [] when unreachable.
func route(a: int, b: int) -> Array[int]:
	var result: Array[int] = []
	if a < 0 or b < 0: return result
	var cost := {a: 0.0}
	var back := {}
	var open: Array[int] = [a]
	while not open.is_empty():
		var best := 0
		for i in open.size():
			if cost[open[i]] < cost[open[best]]: best = i
		var node: int = open[best]
		open.remove_at(best)
		if node == b: break
		for next in links[node]:
			var c: float = cost[node]+points[node].distance_to(points[next])
			if not cost.has(next) or c < cost[next]:
				cost[next] = c
				back[next] = node
				if next not in open: open.append(next)
	if not cost.has(b): return result
	var node := b
	result.append(node)
	while node != a:
		node = back[node]
		result.push_front(node)
	return result

func route_length(nodes: Array[int]) -> float:
	var total := 0.0
	for i in nodes.size()-1: total += points[nodes[i]].distance_to(points[nodes[i+1]])
	return total

## Keep-right offset for walking a -> b.
func lane(a: int, b: int) -> float:
	return float(lanes.get(Vector2i(a, b), LANE))

## Probes each edge with a body-sized capsule along a few side offsets and keeps,
## per direction, the first clear one in keep-right order (right, centre, further
## right, left...). Props, furniture, decks and walls block (layers 2, 8, 16).
func fit_lanes(space: PhysicsDirectSpaceState3D) -> int:
	lanes.clear()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.26
	capsule.height = 1.1
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = capsule
	query.collision_mask = 2|8|16
	var moved := 0
	for edge in edges():
		var a: int = edge[0]
		var b: int = edge[1]
		if kinds[a] == "bridge" and kinds[b] == "bridge": continue
		var along := points[b]-points[a]
		var length := along.length()
		if length < 1.4: continue
		var right := Vector2(-along.y, along.x)/length
		var blocked := {}
		for direction in [1.0, -1.0]:
			var order := [LANE, 0.0, LANE+0.25, -LANE, -LANE-0.25]
			var best := LANE
			var best_hits := 1 << 30
			for offset in order:
				var side: float = offset*direction
				if not blocked.has(side):
					var hits := 0
					var steps := int((length-1.2)/0.5)
					for i in steps+1:
						var p: Vector2 = points[a]+along/length*(0.6+i*0.5)+right*side
						var ground := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(p.x, 60, p.y), Vector3(p.x, -20, p.y), 1|2))
						if ground.is_empty(): continue
						query.transform = Transform3D(Basis.IDENTITY, ground.position+Vector3(0, 0.38+0.55, 0))
						if not space.intersect_shape(query, 1).is_empty(): hits += 1
					blocked[side] = hits
				if blocked[side] < best_hits:
					best_hits = blocked[side]
					best = offset
				if best_hits == 0: break
			if not is_equal_approx(best, LANE): moved += 1
			if direction > 0.0: lanes[Vector2i(a, b)] = best
			else: lanes[Vector2i(b, a)] = best
	return moved
