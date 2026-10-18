extends Node3D
## Village add-on (main.gd VILLAGE_MODULES): the building doors open, and the walker walks through
## them into a room and back out. The Tripo building GLBs bake their doors into the walls; the map
## session cuts each door out as its own node (origin on the hinge) and hands it over here:
##   VillageDoors.register(id, door_node, hinge_axis := Vector3.UP, open_angle := deg(100), outward := true)
## A child named "Door", "door", "Door_<id>" or "door_<id>" under the building node is registered
## by itself when the doors are laid out. With no leaf a door still works: its sounds play and
## the walker walks through the doorway (the leaf just isn't animated).
##  - open(host, key) / close(host, key) / swing(host, key, hold): the leaf turns about its own
##    origin, eased, with DoorAudio's latch/creak/close sounds. Only a tween while it moves.
##  - Items 49/51: walk_in() (main.open_studio) turns the walker to the door, opens it and walks it
##    into the doorway under the fade; walk_out() (main._ready, back from a room) starts the walker
##    just inside the open door, walks it out to TownLayout.door_return() and shuts the door behind.
##    The walk is kinematic (DoorWalk below, on the player's ix hook): continuous, eased, walking clip.
##  - Item 32, optional: attach_glow(id, backing) (or a child "DoorBacking"/"door_backing_<id>")
##    makes the dark doorway behind the leaf glow warmer and brighter the more people are inside
##    (residents.gd building_state; the player's rooms 1, or set_occupancy()).
##  - Other players: a peer who vanishes into / appears out of a doorway swings that door.
## key: a building id ("10_red_house") or its room ("home", "workshop", "01_cafe").
const Town = preload("res://scripts/town.gd")
const Residents = preload("res://scripts/residents.gd")
const DoorAudio = preload("res://scripts/door_audio.gd")
const Daylight = preload("res://scripts/daylight.gd")
## The map's doors cut out of the buildings themselves (Buildings/<id>/DoorFrame/DoorLeaf, hinge +Y
## at its origin, outward OPEN_DEGREES; DoorOpening with `inner_light`): used first when a building has one.
const BuildingDoors = preload("res://maps/archipelago/building_doors.gd")
const NODE_NAME := "VillageDoors"
## Swing times (s) and the leaf's default opening.
const SWING := 0.6
const SHUT := 0.5
const OPEN_ANGLE := deg_to_rad(100.0)
## The walker: cruise speed (player.SPEED is 2.8), easing in and out, metres past the doorway.
const CRUISE := 2.6
const ACCEL := 6.0
const BRAKE := 3.2
const NEAR := 3.4
const INSIDE := 0.9
## The doorway glow's colour (emission on a backing without a "glow" shader parameter).
const WARM := Color(1.0, .62, .32)

var app: Node
var map: Node3D
var _until := 0.0
var _peer_wait := 0.0
## Peers the first polls report were already about: only later arrivals and departures count.
var _settle := 3.0
## Peers last seen: id -> world position (to tell a walk through a door from a log-in or log-out).
var _peers := {}
## Counts fed from outside (the lead's real counts for the player's rooms): key -> people.
static var occupancy := {}
## Door leaves and glows handed over: building id -> {node, axis, angle, rest} / GeometryInstance3D.
static var leaves := {}
static var glows := {}

## Village module entry: lay the doors out on the kept map once and light them.
func setup(owner_app: Node) -> void:
	app = owner_app
	if app == null or not ("town" in app) or not is_instance_valid(app.town): return
	map = app.town.map
	if not is_instance_valid(map): return
	var root := dress(map)
	# A door left open when the village was put away (walked into a room) is shut again; walk_out()
	# opens the one the walker comes back through.
	for door: Dictionary in (root.get_meta("doors", {}) as Dictionary).values(): turn(app, door.id, 0.0, 0.0, false)
	update_glow(map, _hour(), true)

func _hour() -> float:
	if is_instance_valid(app) and "daylight" in app and is_instance_valid(app.daylight) and app.daylight.has_method("current_hour"):
		return app.daylight.current_hour()
	return Daylight.clock_hour()

func _process(delta: float) -> void:
	if not is_instance_valid(map): return
	_until -= delta
	if _until <= 0.0:
		_until = 1.0
		update_glow(map, _hour())
	_peer_wait -= delta
	_settle -= delta
	if _peer_wait <= 0.0:
		_peer_wait = 0.25
		watch_peers()

func leave() -> void:
	map = null

## Lays out every door's doorway (idempotent): where the wall is, which way is out, and any leaf or
## backing the building node carries. Returns the root holding {id: door record} as meta "doors".
static func dress(host: Node3D) -> Node3D:
	if host == null: return null
	var existing := host.get_node_or_null(NODE_NAME) as Node3D
	if existing: return existing
	var root := Node3D.new()
	root.name = NODE_NAME
	host.add_child(root)
	var space := host.get_world_3d().direct_space_state
	var buildings := host.get_node_or_null("Buildings")
	var doors := {}
	for entry: Dictionary in Town.DOORS:
		var id := String(entry.id)
		var building := buildings.get_node_or_null(id) as Node3D if buildings else null
		var floor_y: float = building.global_position.y if building else Town.height_at(entry.at.x, entry.at.y)
		var fit := _fit(space, entry, floor_y)
		var base: Vector3 = fit.base
		doors[id] = {"id":id, "room":String(entry.room), "base":base, "at":Vector2(entry.at), "normal":fit.normal, "ground":float(fit.ground),
			"sound":base+Vector3(0, 1.1, 0)+(fit.normal as Vector3)*.3, "open":0.0, "glow":-1.0, "tween":null}
		if building == null: continue
		if not leaves.has(id) or not is_instance_valid(leaves[id].node):
			var cut := BuildingDoors.door_leaf(id)
			# The map's own door: its hinge side, one or two leaves and the way it opens are the map's
			# (BuildingDoors.set_door_open); here only how far open.
			if cut: leaves[id] = {"node":cut, "cut":true}
			else:
				var leaf := _child(building, ["Door", "door", "Door_"+id, "door_"+id])
				if leaf: register(id, leaf)
		if not glows.has(id) or not is_instance_valid(glows[id]):
			var backing: GeometryInstance3D = BuildingDoors.door_opening(id)
			if backing == null: backing = _child(building, ["DoorBacking", "door_backing", "DoorBacking_"+id, "door_backing_"+id]) as GeometryInstance3D
			if backing: attach_glow(id, backing)
	root.set_meta("doors", doors)
	return root

static func _child(building: Node, names: Array) -> Node3D:
	for name in names:
		var found := building.find_child(name, true, false) as Node3D
		if found: return found
	return null

## The façade at a door: {base (sill centre on the wall), normal (out), ground}. Without a wall hit
## (no building collision) the door point itself, facing away from the building's centre.
static func _fit(space: PhysicsDirectSpaceState3D, entry: Dictionary, floor_y: float) -> Dictionary:
	var at: Vector2 = entry.at
	var out: Vector2 = (at-Vector2(entry.center)).normalized()
	var ground := _ground(space, Vector3(at.x, floor_y, at.y))
	var fallback := {"base":Vector3(at.x, ground, at.y)-Vector3(out.x, 0, out.y)*.6, "normal":Vector3(out.x, 0, out.y), "ground":ground}
	var side := Vector2(out.y, -out.x)
	var hits: Array = []
	for lateral in [-.35, 0.0, .35]:
		var from2: Vector2 = at+out*1.6+side*float(lateral)
		var from := Vector3(from2.x, ground+1.0, from2.y)
		var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(from, from-Vector3(out.x, 0, out.y)*7.0, 2))
		hits.append(hit if not hit.is_empty() and absf(hit.normal.y) < .5 else {})
	if hits[1].is_empty(): return fallback
	var spot: Vector3 = hits[1].position
	var normal := Vector3(hits[1].normal.x, 0, hits[1].normal.z).normalized()
	if not hits[0].is_empty() and not hits[2].is_empty():
		var tangent: Vector3 = hits[2].position-hits[0].position
		if absf(Vector2(tangent.x, tangent.z).dot(out)) < .25: normal = Vector3(tangent.z, 0, -tangent.x).normalized()
	if normal.dot(Vector3(out.x, 0, out.y)) < 0.0: normal = -normal
	var sill := _ground(space, Vector3(spot.x, ground, spot.z)+normal*.22)
	return {"base":Vector3(spot.x, sill, spot.z), "normal":normal, "ground":ground}

## Ground height under a point from just below its eaves (porch roofs never count).
static func _ground(space: PhysicsDirectSpaceState3D, at: Vector3) -> float:
	var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(at+Vector3(0, 1.4, 0), at-Vector3(0, 4.0, 0), 1|2))
	return hit.position.y if not hit.is_empty() else at.y

## A door leaf for a building: it turns about its own origin (the hinge) around hinge_axis (in the
## node's own space) by open_angle; outward false swings it the other way. Its pose now is closed.
static func register(id: String, door_node: Node3D, hinge_axis := Vector3.UP, open_angle := OPEN_ANGLE, outward := true) -> void:
	if door_node == null: return
	leaves[id] = {"node":door_node, "axis":hinge_axis.normalized(), "angle":open_angle*(1.0 if outward else -1.0), "rest":door_node.transform.basis}

## The dark doorway behind a building's leaf, lit by the people inside (update_glow()).
static func attach_glow(id: String, backing: GeometryInstance3D) -> void:
	if backing == null: return
	glows[id] = backing

## The door record for a building id or a room id, else {}.
static func find(host: Node, key: String) -> Dictionary:
	var root := _root(host)
	if root == null: return {}
	var doors: Dictionary = root.get_meta("doors", {})
	if doors.has(key): return doors[key]
	for id in doors:
		if doors[id].room == key: return doors[id]
	return {}

static func _root(host: Node) -> Node3D:
	if host == null or not is_instance_valid(host) or not ("town" in host) or not is_instance_valid(host.town): return null
	var map: Node3D = host.town.map
	return map.get_node_or_null(NODE_NAME) as Node3D if is_instance_valid(map) else null

## Swings a door to `to` (0 shut .. 1 open) over `seconds` (0: at once), with its sounds; a door
## without a leaf only sounds. Returns the door record ({} when unknown).
static func turn(host: Node, key: String, to: float, seconds: float, sound := true) -> Dictionary:
	var door := find(host, key)
	if door.is_empty(): return {}
	var tween: Tween = door.tween
	if tween != null and tween.is_valid(): tween.kill()
	door.tween = null
	var from := float(door.open)
	if sound and absf(to-from) > .1:
		if to > from: DoorAudio.door_open(host, door.room, door.sound, seconds)
		else: DoorAudio.door_close(host, door.room, door.sound, seconds)
	var leaf: Dictionary = leaves.get(door.id, {})
	if leaf.is_empty() or not is_instance_valid(leaf.node) or not (leaf.node as Node).is_inside_tree() or seconds <= 0.0 or is_equal_approx(from, to):
		_pose(door, to)
		return door
	tween = (leaf.node as Node).create_tween()
	# Opening: the latch gives and the leaf swings, slowing as it opens. Shutting: it gathers pace
	# and lands on the frame (the close take plays at that moment, DoorAudio.door_close).
	var step := func(value: float): _pose(door, value)
	if to > from: tween.tween_method(step, from, to, seconds).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	else: tween.tween_method(step, from, to, seconds).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	door.tween = tween
	return door

static func _pose(door: Dictionary, value: float) -> void:
	door.open = value
	var leaf: Dictionary = leaves.get(door.id, {})
	if leaf.is_empty() or not is_instance_valid(leaf.node): return
	if leaf.get("cut", false):
		BuildingDoors.set_door_open(String(door.id), value)
		return
	(leaf.node as Node3D).transform.basis = (leaf.rest as Basis)*Basis(leaf.axis, float(leaf.angle)*value)

static func open(host: Node, key: String, seconds := SWING) -> void: turn(host, key, 1.0, seconds)
static func close(host: Node, key: String, seconds := SHUT) -> void: turn(host, key, 0.0, seconds)

## Open, hold a moment, shut: someone else went through.
static func swing(host: Node, key: String, hold := 1.0) -> void:
	var door := turn(host, key, 1.0, SWING)
	if door.is_empty() or not is_instance_valid(host): return
	var ref: WeakRef = weakref(host)
	host.get_tree().create_timer(SWING+hold).timeout.connect(func():
		var node = ref.get_ref()
		if node != null and is_instance_valid(node) and node.is_inside_tree(): turn(node, door.id, 0.0, SHUT))

## People inside a building (the player's rooms: what the lead feeds, else 1). count < 0 clears.
static func set_occupancy(key: String, count: int) -> void:
	if count < 0: occupancy.erase(key)
	else: occupancy[key] = count

## The glow of each attached doorway: dim when nobody is in, warmer and brighter with each person
## (1 - e^-0.65n: one 0.48, two 0.73, three 0.86), dark when all inside are asleep. A backing whose
## material has a "glow" shader parameter gets it (and "night"); otherwise its material's emission.
static func update_glow(host: Node3D, hour: float, now := false) -> void:
	var root := host.get_node_or_null(NODE_NAME) if host else null
	if root == null or glows.is_empty(): return
	var night: float = Daylight.sample(hour).night
	var day := int(Residents.clock().day)
	var doors: Dictionary = root.get_meta("doors", {})
	for id in doors:
		# A village rebuild frees the old backing. Check the Variant before assigning a
		# typed Object: Godot rejects freed instances at assignment, before the guard.
		var candidate = glows.get(id)
		if not is_instance_valid(candidate): continue
		var backing := candidate as GeometryInstance3D
		if backing == null: continue
		var door: Dictionary = doors[id]
		var count := 0
		if occupancy.has(id): count = int(occupancy[id])
		elif occupancy.has(door.room): count = int(occupancy[door.room])
		elif door.room in Residents.PLAYER_ROOMS or id in Residents.PLAYER_ROOMS: count = 1
		else:
			var state := Residents.building_state(id, hour, day)
			count = state.occupants.filter(func(o): return not o.asleep).size() if state.lights_on else 0
		var target := 0.06 if count <= 0 else 1.0-exp(-.65*count)
		var glow := target if now or float(door.glow) < 0.0 else move_toward(float(door.glow), target, .2)
		if is_equal_approx(glow, float(door.glow)) and is_equal_approx(night, float(door.get("night", -1.0))): continue
		door.glow = glow
		door.night = night
		var material := backing.material_override
		if material == null and backing is MeshInstance3D and (backing as MeshInstance3D).mesh:
			var source := (backing as MeshInstance3D).get_active_material(0)
			material = (source.duplicate() as Material) if source else StandardMaterial3D.new()
			backing.material_override = material
		if material is ShaderMaterial:
			(material as ShaderMaterial).set_shader_parameter("glow", glow)
			(material as ShaderMaterial).set_shader_parameter("night", night)
			# The map's doorway (building_doors.gd DoorOpening): one light level, 0..1.
			(material as ShaderMaterial).set_shader_parameter("inner_light", clampf(glow*lerpf(.75, 1.0, night), 0.0, 1.0))
		elif material is StandardMaterial3D:
			var lit := material as StandardMaterial3D
			lit.emission_enabled = true
			lit.emission = WARM
			lit.emission_energy_multiplier = glow*lerpf(1.0, 1.6, night)

## A peer who vanished next to a door went in; one who appeared next to it came out: that door
## swings (social.gd adds and drops peers as the village poll reports them).
func watch_peers() -> void:
	if not is_instance_valid(app) or not ("social" in app) or not is_instance_valid(app.social): return
	var peers: Dictionary = app.social.peers
	var seen := {}
	for id in peers:
		var node = peers[id].get("node")
		if not (node is Node3D) or not is_instance_valid(node): continue
		seen[id] = (node as Node3D).global_position
		if not _peers.has(id) and _settle <= 0.0: _near_door(seen[id])
	for id in _peers:
		if not seen.has(id) and _settle <= 0.0: _near_door(_peers[id])
	_peers = seen

func _near_door(at: Vector3) -> void:
	var root := map.get_node_or_null(NODE_NAME) if is_instance_valid(map) else null
	if root == null: return
	var doors: Dictionary = root.get_meta("doors", {})
	for id in doors:
		var base: Vector3 = doors[id].base
		# By the wall or on the doorstep (a recessed door, the café's, stands back from its step).
		var step: Vector2 = doors[id].get("at", Vector2(base.x, base.z))
		if minf(Vector2(at.x-base.x, at.z-base.z).length(), Vector2(at.x, at.z).distance_to(step)) < 2.6:
			swing(app, id, 0.9)
			return

## The walker is in a door walk (entering or leaving): no other door or prompt may start.
static func walking(host: Node) -> bool:
	var walk := host.get_node_or_null("DoorWalk") if host != null and is_instance_valid(host) else null
	return walk != null and walk.busy()

## Entering a building from the village (main.open_studio): when the walker is near the door, it
## turns to it, the door swings open and the walker walks in while the veil fades out. Returns
## once the veil is dark; false (nothing done) when the door or the walker is not there.
static func walk_in(host: Node, room: String, veil: Node) -> bool:
	var door := find(host, room)
	var player = host.get("player") if host != null else null
	if door.is_empty() or not (player is Node3D) or not is_instance_valid(player) or walking(host): return false
	var base: Vector3 = door.base
	var normal: Vector3 = door.normal
	var from: Vector3 = player.global_position
	var depth := (from-base).dot(normal)
	if Vector2(from.x-base.x, from.z-base.z).length() > NEAR or depth < -.2: return false
	var inside := base-normal*(INSIDE+.9)
	var axis := base+normal*clampf(depth, .7, 2.2)
	var path := _bezier(from, axis, base+normal*.4, inside)
	var speed: float = Vector2(player.velocity.x, player.velocity.z).length() if "velocity" in player else 0.0
	var walk := DoorWalk.begin(host, player, path, door, false, speed)
	walk.delay = 0.0 if speed > .5 else .12
	player.face_point(base)
	turn(host, door.id, 1.0, SWING)
	# The veil darkens as the walker reaches the doorway (or after 1.3 s whatever happens); the
	# walk goes on into the room under it.
	var reach := walk.crossing(base, normal)-.3
	var deadline := Time.get_ticks_msec()+1300
	while is_instance_valid(walk) and walk.travelled < reach and Time.get_ticks_msec() < deadline: await host.get_tree().process_frame
	await veil.fade_out()
	return true

## Back from a room (main._ready): the walker starts just inside the open door facing out, walks out
## to the doorstep spot as the veil lifts, and the door shuts behind it. False when there is no door
## to walk out of (the caller then places the walker as before).
static func walk_out(host: Node, room: String, veil: Node) -> bool:
	var door := find(host, room)
	var player = host.get("player") if host != null else null
	if door.is_empty() or not (player is Node3D) or not is_instance_valid(player) or walking(host): return false
	var base: Vector3 = door.base
	var normal: Vector3 = door.normal
	var goal := Town.door_return(room)
	var start := base-normal*.55
	var path := _bezier(start, base+normal*.5, base+normal*.9, Vector3(goal.x, base.y, goal.z))
	turn(host, door.id, 1.0, 0.0, false)
	player.global_position = path[0]
	player.velocity = Vector3.ZERO
	player.facing = normal
	if "visual" in player and is_instance_valid(player.visual): player.visual.rotation.y = atan2(-normal.x, -normal.z)
	var walk := DoorWalk.begin(host, player, path, door, true, 0.0)
	walk.delay = .12
	# The door shuts once the walker is a stride clear of it.
	var ref: WeakRef = weakref(host)
	walk.at(.55+1.0, func():
		var node = ref.get_ref()
		if node != null and is_instance_valid(node) and node.is_inside_tree(): turn(node, door.id, 0.0, SHUT))
	if host.has_method("follow_camera"): host.follow_camera(1)
	veil.fade_in()
	return true

## A smooth path through four points (cubic Bézier), sampled every few centimetres; y is laid on
## the ground later (DoorWalk.lay).
static func _bezier(a: Vector3, b: Vector3, c: Vector3, d: Vector3) -> PackedVector3Array:
	var points := PackedVector3Array()
	var steps := 48
	for i in steps+1:
		var t := float(i)/steps
		var u := 1.0-t
		points.append(a*u*u*u+b*3.0*u*u*t+c*3.0*u*t*t+d*t*t*t)
	return points

## The door walk: a stand-in for the interaction driver on the player's `ix` hook (player.gd calls
## drive() inside its physics tick, so the drawn walker stays interpolated). The body is moved along
## the path (visual_only: no collision with the wall it walks through), eased in and, when `stop`,
## out to a halt on the last point; external_velocity drives the walking clip and the facing.
class DoorWalk extends Node:
	var body: Node3D
	var points := PackedVector3Array()
	var lengths := PackedFloat32Array()
	var length := 0.0
	var travelled := 0.0
	var speed := 0.0
	var stop := false
	var delay := 0.0
	var elapsed := 0.0
	var index := 0
	var done := false
	var events: Array = []
	var old_ix: Node
	var old_visual_only := false

	static func begin(host: Node, walker: Node3D, path: PackedVector3Array, door: Dictionary, halt: bool, start_speed: float) -> DoorWalk:
		var old := host.get_node_or_null("DoorWalk")
		if old: old.finish()
		var walk := DoorWalk.new()
		walk.name = "DoorWalk"
		host.add_child(walk)
		walk.body = walker
		walk.stop = halt
		walk.speed = minf(start_speed, CRUISE)
		walk.lay(path, door)
		walk.old_ix = walker.ix if is_instance_valid(walker.ix) else null
		walk.old_visual_only = walker.visual_only
		walker.ix = walk
		walker.visual_only = true
		walker.velocity = Vector3.ZERO
		return walk

	## Heights along the path: the ground in front of the wall (eased over steps), the sill behind it.
	func lay(path: PackedVector3Array, door: Dictionary) -> void:
		var space := body.get_world_3d().direct_space_state
		var base: Vector3 = door.base
		var normal: Vector3 = door.normal
		var heights := PackedFloat32Array()
		for p in path:
			var depth := (p-base).dot(normal)
			var y := base.y
			if depth > .05:
				var from := Vector3(p.x, base.y+1.3, p.z)
				var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(from, from-Vector3(0, 4.5, 0), 1|2))
				if not hit.is_empty(): y = hit.position.y
				# Close to the wall the step blends into the sill.
				y = lerpf(base.y, y, smoothstep(.05, .5, depth))
			heights.append(y)
		for i in path.size():
			var sum := 0.0
			var weight := 0.0
			for j in range(maxi(i-3, 0), mini(i+4, path.size())):
				sum += heights[j]
				weight += 1.0
			points.append(Vector3(path[i].x, sum/weight, path[i].z))
		lengths.append(0.0)
		for i in range(1, points.size()):
			var flat := Vector2(points[i].x-points[i-1].x, points[i].z-points[i-1].z).length()
			lengths.append(lengths[i-1]+flat)
		length = lengths[lengths.size()-1]

	## How far along the path it passes through the doorway plane.
	func crossing(base: Vector3, normal: Vector3) -> float:
		for i in points.size():
			if (points[i]-base).dot(normal) <= 0.0: return lengths[i]
		return length

	## Runs `call` once the walker has gone `metres` along the path.
	func at(metres: float, call: Callable) -> void:
		events.append([metres, call])

	func busy() -> bool: return not done
	func seated() -> bool: return false
	func locks_input() -> bool: return not done

	func point_at(distance: float) -> Vector3:
		while index < lengths.size()-2 and lengths[index+1] < distance: index += 1
		var span := maxf(lengths[index+1]-lengths[index], .0001)
		return points[index].lerp(points[index+1], clampf((distance-lengths[index])/span, 0.0, 1.0))

	func drive(walker: Node3D, delta: float) -> void:
		if done or walker != body: return
		elapsed += delta
		if elapsed < delay:
			walker.external_velocity = Vector2.ZERO
			walker.external_motion = Vector2.ZERO
			return
		var target := CRUISE
		if stop: target = minf(CRUISE, sqrt(2.0*BRAKE*maxf(length-travelled, 0.0)))
		speed = move_toward(speed, target, (ACCEL if target > speed else BRAKE*3.0)*delta)
		if stop and length-travelled > .002: speed = maxf(speed, .12)
		travelled = minf(travelled+speed*delta, length)
		var before := walker.global_position
		var now := point_at(travelled)
		walker.global_position = now
		var step := Vector2(now.x-before.x, now.z-before.z)
		walker.external_velocity = step/maxf(delta, .001)
		walker.external_motion = step.normalized() if step.length() > .0001 else Vector2.ZERO
		for event in events.duplicate():
			if travelled >= float(event[0]):
				events.erase(event)
				(event[1] as Callable).call()
		if travelled >= length-.002: finish()

	## Hands the walker back to its own physics where the walk left it. leaving: the walk goes with its
	## scene (a scene change, quitting); what was due at the door is dropped, the door with it.
	func finish(leaving := false) -> void:
		if done: return
		done = true
		if is_instance_valid(body):
			if body.ix == self: body.ix = old_ix if is_instance_valid(old_ix) else null
			body.visual_only = old_visual_only
			body.velocity = Vector3.ZERO
			body.external_velocity = Vector2.ZERO
			body.external_motion = Vector2.ZERO
		if not leaving:
			for event in events: (event[1] as Callable).call()
		events.clear()
		queue_free()

	func _exit_tree() -> void:
		if not done: finish(true)
