extends Node3D
## Field trees you shake one at a time. Every round tree, conifer and palm on the map
## is its own server node ("apple_tree_07", "pine_tree_03", "palm_tree_01": numbered in
## map order per kind, see server/homestead.py TREES). A ripe tree shows its fruit in
## the crown; shaking it asks the server, which drops that fruit (plus a rolled bonus)
## on the ground and starts the tree's regrowth. The fruit falls out of the crown,
## bounces and rolls to rest near the walker's side of the tree, and is picked up by
## walking over it or pressing E: each pick-up is one server "pickup", so the bag only
## changes on the server. Fruit left lying is restored from the server after a revisit.
## Cost: trees are indexed once; a 0.25 s tick checks distances and only trees within
## NEAR metres get fruit drawn (one 2-3 instance MultiMesh each, built on first approach)
## and synced; falling fruit is simulated only while it moves.
const Fx := preload("res://scripts/fx.gd")
const Art := preload("res://scripts/life_art.gd")
## Map prop -> tree kind (server TREES keys).
const KINDS := {"37_round_tree":"apple","38_conifer":"pine","39_palm":"palm"}
const FRUIT := {"apple":"apple","pine":"pinecone","palm":"coconut"}
## Fallback hanging range; the server catalog ("trees") wins when present.
const HANG := {"apple":[2,3],"pine":[2,3],"palm":[1,2]}
## Ground contact radius per item (m) and how big each looks.
const RADIUS := {"apple":0.18,"pinecone":0.12,"coconut":0.2,"branch":0.06}
const SIZE := {"apple":1.2,"pinecone":1.3,"coconut":1.2,"branch":1.2}
const NEAR := 26.0
const TICK := 0.25
const WALK_PICK := 0.8
const E_REACH := 1.7
const GRAVITY := 12.0
const GROUND_MASK := 1
const BLOCK_MASK := 2|8|16|32

var trees: Array = []
var by_node := {}
var by_id := {}
## Live fallen items: {tree, item, node, shadow, pos, vel, axis, spin, state ("hang", "fall", "rest", "take"), wait, cool}
var drops: Array = []
var app: Node
var wait := 0.0
var queue: Array = []
var draining := false
static var kind_cache := {}
static var meshes := {}
static var fruit_material: StandardMaterial3D
static var shadow_material: StandardMaterial3D
static var shadow_mesh: PlaneMesh

# ------------------------------------------------------------------ index
## Called by town.gd once the map props exist. Ids follow the layout order per kind.
func build(prop_nodes: Array) -> void:
	trees.clear()
	by_node.clear()
	by_id.clear()
	var counters := {}
	for node in prop_nodes:
		if not is_instance_valid(node): continue
		var spec: Dictionary = node.get_meta("placement_spec", {})
		var kind: String = KINDS.get(String(spec.get("id","")), "")
		if kind.is_empty(): continue
		counters[kind] = int(counters.get(kind, 0))+1
		var old: Node = node.get_node_or_null("TreeFruit")
		if old:
			node.remove_child(old)
			old.queue_free()
		var tree := {"id":"%s_tree_%02d" % [kind, counters[kind]],"kind":kind,"prop":String(spec.id),"node":node,
			"at":Vector2(node.global_position.x, node.global_position.z),"fruit":null,"slots":[],"ready":true,"built":false,
			"spots":[],"busy":false,"near":false,"crown":Vector3.ZERO,"faded":false,"grow":1.0}
		trees.append(tree)
		by_node[node] = tree
		by_id[tree.id] = tree
	# Crown ray data is built once per kind (~12 ms each) while the village loads,
	# not on the first walk past a tree.
	for tree in trees:
		if not kind_cache.has(tree.prop) and tree.node.is_inside_tree(): crown_info(tree)

func _exit_tree() -> void:
	for tree in trees:
		if is_instance_valid(tree.fruit): tree.fruit.queue_free()

func tree_for(node: Node) -> Dictionary: return by_node.get(node, {})

func hang_count(tree: Dictionary) -> int:
	var range_: Array = HANG[tree.kind]
	if is_instance_valid(app) and "life" in app and is_instance_valid(app.life) and app.life.state is Dictionary:
		range_ = app.life.state.get("catalog", {}).get("trees", {}).get(tree.kind, {}).get("hang", range_)
	var low := int(range_[0])
	var high := int(range_[1])
	return low+int(String(tree.id).right(2))%(high-low+1)

# ------------------------------------------------------------------ server state
func life() -> Node:
	if is_instance_valid(app) and "life" in app and is_instance_valid(app.life) and app.life.has_method("request"): return app.life
	return null

## True when shakes and pick-ups go to the server (own village, state loaded).
func online() -> bool:
	var l := life()
	if l == null or not l.state is Dictionary or l.state.is_empty(): return false
	if "social" in app and is_instance_valid(app.social) and app.social.has_method("visiting") and app.social.visiting(): return false
	return true

func server_ready(tree: Dictionary) -> bool:
	if not online(): return true
	return life().now() >= float(life().state.get("nodes", {}).get(tree.id, 0))

func server_drops(tree: Dictionary) -> Array:
	if not online(): return []
	var drop = life().state.get("drops", {}).get(tree.id)
	if not drop is Dictionary or life().now() >= float(drop.get("until", 0)): return []
	return drop.get("items", [])

## One server action at a time: waits for an earlier request to finish first.
func call_server(kind: String, extra: Dictionary) -> Dictionary:
	var l := life()
	if l == null: return {}
	for i in 240:
		if not l.pending: break
		await get_tree().process_frame
		if not is_instance_valid(l): return {}
	return await l.request(kind, extra)

# ------------------------------------------------------------------ frame updates
func _process(delta: float) -> void:
	if not is_instance_valid(app): app = find_app()
	if not is_instance_valid(app) or not "player" in app or not is_instance_valid(app.player): return
	wait -= delta
	if wait <= 0.0:
		wait = TICK
		tick()
	if not drops.is_empty(): step_drops(delta)

func find_app() -> Node:
	var n := get_parent()
	while n != null:
		if "life" in n and "player" in n: return n
		n = n.get_parent()
	return null

func walker() -> Vector3: return app.player.global_position

## Distance check over the indexed trees (four times a second); only near ones work.
func tick() -> void:
	var p := walker()
	var here := Vector2(p.x, p.z)
	for tree in trees:
		var near: bool = here.distance_to(tree.at) < NEAR and is_instance_valid(tree.node) and tree.node.visible
		tree.near = near
		if not near: continue
		if not tree.built: build_fruit(tree)
		if tree.busy: continue
		var ready := server_ready(tree)
		if ready != tree.ready:
			tree.ready = ready
			if ready: regrow(tree)
		var faded := faded_now(tree)
		tree.faded = faded
		if is_instance_valid(tree.fruit): tree.fruit.visible = tree.ready and not faded
		reconcile(tree)

func faded_now(tree: Dictionary) -> bool:
	if not tree.has("mesh"): tree.mesh = kind_mesh(tree.node)
	var mesh: MeshInstance3D = tree.mesh
	if not is_instance_valid(mesh): return false
	if mesh.mesh == null: return false
	var m := mesh.get_surface_override_material(0) as BaseMaterial3D
	return m != null and m.albedo_color.a < 0.95

# ------------------------------------------------------------------ hanging fruit
func kind_mesh(node: Node3D) -> MeshInstance3D:
	for child in node.find_children("*", "MeshInstance3D", true, false):
		return child
	return null

## Shared crown data per tree kind: triangle mesh for ray hits and its placement.
func crown_info(tree: Dictionary) -> Dictionary:
	if kind_cache.has(tree.prop): return kind_cache[tree.prop]
	var mesh := kind_mesh(tree.node)
	var info := {}
	if mesh != null and mesh.mesh != null:
		var local: Transform3D = tree.node.global_transform.affine_inverse()*mesh.global_transform
		info = {"tri":mesh.mesh.generate_triangle_mesh(),"xf":local,"aabb":mesh.mesh.get_aabb()}
		if tree.kind == "palm":
			# Fronds radiate from the trunk top: the centroid of the top band finds it.
			var sum := Vector3.ZERO
			var n := 0
			var aabb: AABB = info.aabb
			var faces := mesh.mesh.get_faces()
			for i in range(0, faces.size(), 7):
				var v: Vector3 = faces[i]
				if v.y > aabb.position.y+aabb.size.y*0.8:
					sum += v
					n += 1
			info.top = sum/maxf(1.0, n) if n > 0 else aabb.get_center()+Vector3(0, aabb.size.y*0.4, 0)
	kind_cache[tree.prop] = info
	return info

## Puts the tree's fruit on the camera side of its crown (the camera looks from +Z).
func build_fruit(tree: Dictionary) -> void:
	tree.built = true
	var info := crown_info(tree)
	var node: Node3D = tree.node
	if info.is_empty(): return
	var count := hang_count(tree)
	var aabb: AABB = info.aabb
	var xf: Transform3D = info.xf
	var tri: TriangleMesh = info.tri
	var to_mesh := (node.global_basis*xf.basis).inverse()
	var tree_scale := node.global_basis.get_scale().x
	var seed_value := String(tree.id).hash()
	var slots: Array = []
	# Directions around the camera's line of sight (it looks from +Z, 28 degrees down),
	# tipped a little lower so the fruit sits on the crown's visible front.
	var view := Vector3(0, 0.47, 0.88)
	var yaws := [-0.5, 0.12, 0.62, -0.15]
	var dips := [0.45, 0.2, 0.55, 0.05] if tree.kind == "apple" else [0.35, 0.15, 0.5, 0.0]
	var middle := 0.6 if tree.kind == "apple" else 0.45
	for i in count:
		var p := Vector3.ZERO
		if tree.kind == "palm":
			var top: Vector3 = info.top
			# A cluster under the fronds, on the camera side of the trunk top.
			var around := Vector3(-0.12+i*0.26, -0.5-0.1*(i%2), 0.36)
			p = top+to_mesh*around
		else:
			var yaw: float = yaws[i%yaws.size()]+float((seed_value >> (i*4))%7-3)*0.04
			var dir_world := Basis(Vector3.UP, yaw)*(Basis(Vector3.RIGHT, float(dips[i%dips.size()]))*view)
			var dir := (to_mesh*dir_world).normalized()
			var centre := Vector3(aabb.get_center().x, aabb.position.y+aabb.size.y*middle, aabb.get_center().z)
			var hit: Dictionary = tri.intersect_ray(centre+dir*12.0, -dir)
			if hit.is_empty(): p = centre+dir*minf(aabb.size.x, aabb.size.z)*0.35
			else: p = hit.position+dir*0.03/maxf(tree_scale, 0.2)
		slots.append(xf*p)
	tree.slots = slots
	var crown_local: Vector3 = info.top if tree.kind == "palm" else Vector3(aabb.get_center().x, aabb.position.y+aabb.size.y*0.62, aabb.get_center().z)
	tree.crown = node.global_transform*(xf*crown_local)
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = item_mesh(FRUIT[tree.kind])
	mm.instance_count = slots.size()
	var fruit := MultiMeshInstance3D.new()
	fruit.name = "TreeFruit"
	fruit.multimesh = mm
	fruit.material_override = material()
	fruit.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	node.add_child(fruit)
	tree.fruit = fruit
	tree.ready = server_ready(tree)
	place_fruit(tree, 1.0)
	fruit.visible = tree.ready

## Instance transforms: hanging fruit, unscaled by the tree's own scale, grown by `grow`.
func place_fruit(tree: Dictionary, grow: float) -> void:
	if not is_instance_valid(tree.fruit): return
	var node: Node3D = tree.node
	var inv := 1.0/maxf(node.global_basis.get_scale().x, 0.1)
	var mm: MultiMesh = tree.fruit.multimesh
	for i in tree.slots.size():
		var tilt := Basis(Vector3(1,0,1).normalized(), 0.25*sin(i*1.7))
		mm.set_instance_transform(i, Transform3D(tilt.scaled(Vector3.ONE*inv*maxf(grow, 0.01)), tree.slots[i]))
	tree.grow = grow

func regrow(tree: Dictionary) -> void:
	if not is_instance_valid(tree.fruit): return
	tree.fruit.visible = not tree.faded
	var t := create_tween()
	t.tween_method(func(g: float): place_fruit(tree, g), 0.05, 1.0, 0.7).set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)
	if tree.near: Fx.burst(self, tree.crown, "sparkle", 6, Color(0,0,0,0), 0.8)

func slot_world(tree: Dictionary, i: int) -> Vector3:
	var node: Node3D = tree.node
	if tree.slots.is_empty(): return tree.crown
	return node.global_transform*Vector3(tree.slots[i%tree.slots.size()])

# ------------------------------------------------------------------ shaking
## E on a tree: the walker gives it a shove, the crown sways and sheds leaves; a ripe
## tree's fruit falls once the server agrees.
func shake(app_ref: Node, node: Node3D) -> void:
	var tree := tree_for(node)
	if tree.is_empty(): return
	app = app_ref
	if not tree.built: build_fruit(tree)
	var player: Node3D = app.player
	var away := node.global_position-player.global_position
	away.y = 0.0
	if away.length() < 0.01: away = Vector3.FORWARD
	if player.has_method("face_point"): player.face_point(node.global_position)
	if player.has_method("react"): player.react("attack")
	var ripe: bool = tree.ready and online() and not tree.busy
	var strength := 0.085 if ripe else 0.06
	if tree.kind == "palm": strength *= 0.7
	Fx.wobble(node, strength, Vector3.UP.cross(away.normalized()), 5, 1.15)
	var front: Vector3 = Vector3(tree.crown)+Vector3(0, 0.6, 1.6)*(0.7 if tree.kind == "palm" else 1.0)
	Fx.burst(self, front, "leaf", 20 if ripe else 12, Color(0,0,0,0), 1.1)
	Fx.sound(app, "leaves", node.global_position, 1.0 if ripe else 1.15)
	if not ripe: return
	tree.busy = true
	var data: Dictionary = await call_server("shake", {"node":tree.id})
	tree.busy = false
	if not is_instance_valid(self) or not is_instance_valid(node): return
	if data.is_empty() or not data.get("reward", {}) is Dictionary:
		tree.ready = server_ready(tree)
		return
	var items: Array = data.reward.get("drops", [])
	tree.ready = false
	if is_instance_valid(tree.fruit): tree.fruit.visible = false
	var spots := pick_spots(tree, items.size(), player.global_position)
	var fruit_index := 0
	for i in items.size():
		var item := String(items[i])
		var start: Vector3 = slot_world(tree, fruit_index) if item == FRUIT[tree.kind] else Vector3(tree.crown)+Vector3(randf_range(-0.6,0.6), -0.3, 0.5)
		if item == FRUIT[tree.kind]: fruit_index += 1
		var d := spawn(tree, item, start)
		launch(d, spots[i], i*0.13+(0.05 if item == FRUIT[tree.kind] else 0.3))

## Landing spots around the trunk: on open ground, not water, buildings or props.
func ground_spots(tree: Dictionary) -> Array:
	if not tree.spots.is_empty(): return tree.spots
	var space := get_world_3d().direct_space_state
	var base: Vector3 = tree.node.global_position
	var ball := SphereShape3D.new()
	ball.radius = 0.2
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = ball
	query.collision_mask = BLOCK_MASK
	var spots: Array = []
	for radius: float in ([2.0, 2.4] if tree.kind == "pine" else [1.25, 1.65]):
		for k in 16:
			var a := TAU*k/16.0+radius
			var at := Vector2(base.x, base.z)+Vector2(sin(a), cos(a))*radius
			var y := ground_y(at)
			if is_nan(y) or y < 1.45 or absf(y-base.y) > 1.3: continue
			var cover := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(at.x, y+6.0, at.y), Vector3(at.x, y+0.15, at.y), 2|32))
			if not cover.is_empty(): continue
			query.transform = Transform3D(Basis.IDENTITY, Vector3(at.x, y+0.35, at.y))
			if not space.intersect_shape(query, 1).is_empty(): continue
			spots.append(Vector3(at.x, y, at.y))
	if spots.is_empty(): spots.append(base+Vector3(0, 0, 1.0))
	tree.spots = spots
	return spots

func ground_y(at: Vector2) -> float:
	var hit := get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(at.x, 60, at.y), Vector3(at.x, -20, at.y), GROUND_MASK))
	return hit.position.y if not hit.is_empty() else NAN

## Spots beside the walker on the camera side, never under their feet, spread apart
## so fruit does not pile up (the camera looks from +Z, so north spots hide behind the crown).
func pick_spots(tree: Dictionary, count: int, toward: Vector3) -> Array:
	var spots := ground_spots(tree)
	var base: Vector3 = tree.node.global_position
	var want := Vector2(toward.x-base.x, toward.z-base.z).angle()
	var feet := Vector2(toward.x, toward.z)
	var score := func(s: Vector3) -> float:
		var value := absf(angle_difference(want, Vector2(s.x-base.x, s.z-base.z).angle()))*0.6+(s-base).length()*0.1
		if s.z < base.z-0.3: value += 0.8
		if feet.distance_to(Vector2(s.x, s.z)) < 1.2: value += 5.0
		return value
	var ranked := spots.duplicate()
	ranked.sort_custom(func(a: Vector3, b: Vector3) -> bool: return score.call(a) < score.call(b))
	var chosen: Array = []
	for spot in ranked:
		if chosen.size() >= count: break
		if chosen.all(func(c: Vector3) -> bool: return c.distance_to(spot) > 0.55): chosen.append(spot)
	var i := 0
	while chosen.size() < count:
		chosen.append(ranked[i%ranked.size()])
		i += 1
	return chosen

# ------------------------------------------------------------------ fallen items
func spawn(tree: Dictionary, item: String, at: Vector3) -> Dictionary:
	var node := MeshInstance3D.new()
	node.mesh = item_mesh(item)
	node.material_override = material()
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
	node.global_position = at
	var shadow := MeshInstance3D.new()
	shadow.mesh = blob_mesh()
	shadow.material_override = blob_material()
	shadow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(shadow)
	shadow.visible = false
	var d := {"tree":tree,"item":item,"node":node,"shadow":shadow,"pos":at,"vel":Vector3.ZERO,"axis":Vector3.RIGHT,"spin":0.0,
		"state":"hang","wait":0.0,"cool":0.0,"ground":NAN,"bounces":0}
	drops.append(d)
	return d

## Throws a fallen item from the crown so it lands on `target` (then bounces a little).
func launch(d: Dictionary, target: Vector3, delay: float) -> void:
	var start: Vector3 = d.pos
	var up := 1.4
	var r: float = RADIUS.get(d.item, 0.12)
	var drop_h := maxf(0.2, start.y-(target.y+r))
	var t: float = (up+sqrt(up*up+2.0*GRAVITY*drop_h))/GRAVITY
	var flat := Vector3(target.x-start.x, 0, target.z-start.z)*0.82/t
	d.vel = Vector3(flat.x, up, flat.z)
	d.axis = Vector3(randf_range(-1,1), randf_range(-0.3,0.3), randf_range(-1,1)).normalized()
	d.spin = randf_range(7.0, 12.0)
	d.wait = delay
	d.state = "fall"
	d.ground = target.y

## Places an item already lying on the ground (restored from the server).
func lay(d: Dictionary, spot: Vector3) -> void:
	var r: float = RADIUS.get(d.item, 0.12)
	d.pos = spot+Vector3(0, r, 0)
	d.ground = spot.y
	d.state = "rest"
	var node: MeshInstance3D = d.node
	node.global_position = d.pos
	settle_pose(d, true)
	update_shadow(d)
	node.scale = Vector3.ONE*0.05
	node.create_tween().tween_property(node, "scale", Vector3.ONE, 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)

func step_drops(delta: float) -> void:
	var here := walker()
	for d in drops.duplicate():
		var node: MeshInstance3D = d.node
		if not is_instance_valid(node):
			drops.erase(d)
			continue
		d.cool = maxf(0.0, float(d.cool)-delta)
		match String(d.state):
			"fall": fall(d, delta)
			"rest":
				# Walking over picks it up; standing still where it landed does not.
				if d.has("still") and Vector2(here.x, here.z).distance_to(d.still) < 0.3: continue
				d.erase("still")
				var gap := Vector2(here.x-d.pos.x, here.z-d.pos.z).length()
				if gap < WALK_PICK and absf(here.y-float(d.ground)) < 1.4 and d.cool <= 0.0: pick(d)

func fall(d: Dictionary, delta: float) -> void:
	if float(d.wait) > 0.0:
		d.wait = float(d.wait)-delta
		return
	var node: MeshInstance3D = d.node
	var r: float = RADIUS.get(d.item, 0.12)
	var vel: Vector3 = d.vel
	vel.y -= GRAVITY*delta
	var next: Vector3 = d.pos+vel*delta
	var g := ground_y(Vector2(next.x, next.z))
	if is_nan(g) or g < 1.45 or g > float(d.ground)+0.6:
		# Off the edge, into water or against a bank: stop sliding sideways.
		vel.x = 0.0
		vel.z = 0.0
		next = Vector3(d.pos.x, next.y, d.pos.z)
		g = float(d.ground)
	else:
		d.ground = g
	var flat := Vector2(vel.x, vel.z)
	if next.y-r <= g:
		next.y = g+r
		if vel.y < -1.3:
			# Bounce: lose most of the drop, keep some roll.
			if int(d.bounces) == 0:
				Fx.sound(app, "thud", next, randf_range(0.9, 1.15) if d.item != "coconut" else 0.75, -2.0)
				Fx.burst(self, Vector3(next.x, g+0.05, next.z), "dust", 4, Color(0,0,0,0), 0.1)
			d.bounces = int(d.bounces)+1
			vel.y = -vel.y*0.32
			flat *= 0.6
		else:
			vel.y = 0.0
			flat *= exp(-5.5*delta)
		d.axis = Vector3.UP.cross(Vector3(flat.x, 0, flat.y)).normalized() if flat.length() > 0.02 else d.axis
		d.spin = flat.length()/r
		if vel.y == 0.0 and flat.length() < 0.06:
			d.pos = next
			node.global_position = next
			d.state = "rest"
			d.still = Vector2(walker().x, walker().z)
			settle_pose(d, false)
			update_shadow(d)
			return
	vel.x = flat.x
	vel.z = flat.y
	d.vel = vel
	d.pos = next
	node.global_position = next
	if float(d.spin) > 0.0 and Vector3(d.axis).length() > 0.5:
		node.global_basis = Basis(Vector3(d.axis).normalized(), float(d.spin)*delta)*node.global_basis.orthonormalized()
	update_shadow(d)

## Long items lie down when they stop.
func settle_pose(d: Dictionary, snap: bool) -> void:
	if not d.item in ["pinecone","branch"]: return
	var node: MeshInstance3D = d.node
	var yaw := randf()*TAU
	var lying := Basis(Vector3.UP, yaw)*Basis(Vector3.FORWARD, PI/2)
	if d.item == "branch": lying = Basis(Vector3.UP, yaw)
	if snap: node.global_basis = lying
	else: node.create_tween().tween_property(node, "global_basis", lying, 0.18)

func update_shadow(d: Dictionary) -> void:
	var shadow: MeshInstance3D = d.shadow
	if not is_instance_valid(shadow) or is_nan(float(d.ground)): return
	var h: float = float(d.pos.y)-float(d.ground)
	shadow.visible = h < 7.0
	var r: float = RADIUS.get(d.item, 0.12)
	var s := r*2.6*clampf(1.15-h*0.12, 0.45, 1.15)
	shadow.global_position = Vector3(d.pos.x, float(d.ground)+0.025, d.pos.z)
	shadow.scale = Vector3(s*(2.2 if d.item in ["branch","pinecone"] and d.state == "rest" else 1.0), 1, s)

func remove(d: Dictionary, fade := true) -> void:
	drops.erase(d)
	var node: MeshInstance3D = d.node
	var shadow: MeshInstance3D = d.shadow
	if is_instance_valid(shadow): shadow.queue_free()
	if not is_instance_valid(node): return
	if not fade:
		node.queue_free()
		return
	var t := node.create_tween()
	t.tween_property(node, "scale", Vector3.ONE*0.01, 0.3)
	t.tween_callback(node.queue_free)

# ------------------------------------------------------------------ picking up
## The resting item closest to `at` within E reach (town.gd offers it before props).
func nearest_drop(at: Vector2) -> Dictionary:
	var best := {}
	var gap := E_REACH
	for d in drops:
		if d.state != "rest": continue
		var g := at.distance_to(Vector2(d.pos.x, d.pos.z))
		if g < gap:
			gap = g
			best = d
	return best

func prompt(d: Dictionary) -> String:
	var names: Dictionary = life().state.get("catalog", {}).get("names", {}) if life() != null and life().state is Dictionary else {}
	return tr("%s 줍기") % tr(String(names.get(d.item, {"apple":"사과","pinecone":"솔방울","coconut":"코코넛","branch":"나뭇가지"}.get(d.item, d.item))))

func pick(d: Dictionary, by_hand := false) -> void:
	if d.state != "rest" or not is_instance_valid(d.node): return
	d.state = "take"
	Fx.squash(d.node, 0.2, 0.25)
	if by_hand and is_instance_valid(app) and app.player.has_method("react"):
		app.player.face_point(d.pos)
		app.player.react("gather")
	queue.append(d)
	if not draining: drain()

## Pick-ups go to the server one by one, in the order they were touched.
func drain() -> void:
	draining = true
	while not queue.is_empty():
		var d: Dictionary = queue.pop_front()
		if not is_instance_valid(d.node): continue
		var data: Dictionary = {}
		if online(): data = await call_server("pickup", {"node":d.tree.id, "item":d.item})
		if not is_instance_valid(self): return
		if data.is_empty():
			if online() and not server_drops(d.tree).has(d.item): remove(d)
			else:
				d.state = "rest"
				d.cool = 2.0
			continue
		collect(d)
	draining = false

func collect(d: Dictionary) -> void:
	drops.erase(d)
	var node: MeshInstance3D = d.node
	var at: Vector3 = d.pos
	if is_instance_valid(d.shadow): d.shadow.queue_free()
	if is_instance_valid(node):
		var t := node.create_tween()
		t.tween_property(node, "global_position", at+Vector3(0, 0.55, 0), 0.16).set_ease(Tween.EASE_OUT)
		t.parallel().tween_property(node, "scale", Vector3.ONE*1.35, 0.16)
		t.tween_property(node, "scale", Vector3.ONE*0.01, 0.14).set_ease(Tween.EASE_IN)
		t.tween_callback(node.queue_free)
	Fx.burst(self, at+Vector3(0, 0.2, 0), "sparkle", 5, Color(0,0,0,0), 0.15)
	Fx.item_pop(app, at, d.item, 1)
	Fx.fly_to_bag(app, {d.item:1}, at+Vector3(0, 0.4, 0), 0.12)
	var l := life()
	if l != null and "sfx" in l and is_instance_valid(l.sfx): l.sfx.play("collect", randf_range(1.0, 1.12), -3)
	else: Fx.sound(app, "pop", at)

## Matches the items lying under a near tree with the server's list: restores items
## after a revisit, removes ones that spoiled or were taken elsewhere.
func reconcile(tree: Dictionary) -> void:
	if not online(): return
	var want: Array = server_drops(tree).duplicate()
	var mine: Array = drops.filter(func(d): return d.tree == tree)
	for d in mine:
		var i := want.find(d.item)
		if i >= 0: want.remove_at(i)
		elif d.state == "rest": remove(d)
	if want.is_empty(): return
	var spots := ground_spots(tree)
	var taken := mine.map(func(d): return Vector3(d.pos))
	var k := 0
	for item in want:
		var spot: Vector3 = spots[(k*5+String(tree.id).hash())%spots.size()]
		for j in spots.size():
			var s: Vector3 = spots[(k*5+j)%spots.size()]
			if taken.all(func(p: Vector3) -> bool: return Vector2(p.x-s.x, p.z-s.z).length() > 0.5):
				spot = s
				break
		taken.append(spot)
		lay(spawn(tree, String(item), spot), spot)
		k += 1

# ------------------------------------------------------------------ art
static func material() -> StandardMaterial3D:
	if fruit_material == null:
		fruit_material = StandardMaterial3D.new()
		fruit_material.vertex_color_use_as_albedo = true
		fruit_material.roughness = 0.55
	return fruit_material

static func blob_mesh() -> PlaneMesh:
	if shadow_mesh == null:
		shadow_mesh = PlaneMesh.new()
		shadow_mesh.size = Vector2.ONE
	return shadow_mesh

static func blob_material() -> StandardMaterial3D:
	if shadow_material == null:
		shadow_material = StandardMaterial3D.new()
		shadow_material.albedo_texture = Fx.tex("soft")
		shadow_material.albedo_color = Color(0.05, 0.06, 0.04, 0.5)
		shadow_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		shadow_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	return shadow_material

## One vertex-coloured mesh per item, shared by hanging and fallen copies.
static func item_mesh(item: String) -> ArrayMesh:
	if meshes.has(item): return meshes[item]
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	match item:
		"apple":
			_add(st, Art.mesh("ball"), Transform3D(Basis.from_scale(Vector3(0.3, 0.27, 0.3)), Vector3.ZERO), Color("d43d33"), Color("f07a45"))
			_add(st, Art.mesh("rod"), Transform3D(Basis(Vector3.FORWARD, 0.25).scaled(Vector3(0.025, 0.12, 0.025)), Vector3(0.01, 0.15, 0)), Color("6b4a2c"))
			_add(st, Art.mesh("ball"), Transform3D(Basis(Vector3.FORWARD, -0.6).scaled(Vector3(0.12, 0.025, 0.06)), Vector3(0.07, 0.18, 0)), Color("5f9e3f"))
			_add(st, Art.mesh("ball"), Transform3D(Basis.from_scale(Vector3(0.07, 0.07, 0.07)), Vector3(-0.07, 0.06, 0.11)), Color("ffb08a"))
		"pinecone":
			_add(st, Art.mesh("facet"), Transform3D(Basis.from_scale(Vector3(0.17, 0.3, 0.17)), Vector3.ZERO), Color("7b5232"), Color("a87848"))
			for ring in 4:
				for k in 6:
					var a := TAU*k/6.0+ring*0.5
					var y := -0.1+ring*0.07
					var w := 0.085-absf(ring-1.5)*0.012
					_add(st, Art.mesh("facet"), Transform3D(Basis(Vector3.UP, a).scaled(Vector3(0.07, 0.05, 0.05)), Vector3(sin(a)*w, y, cos(a)*w)), Color("8d5e36").lerp(Color("b4834f"), ring/3.0))
			_add(st, Art.mesh("rod"), Transform3D(Basis.from_scale(Vector3(0.02, 0.06, 0.02)), Vector3(0, 0.16, 0)), Color("5d4128"))
		"coconut":
			_add(st, Art.mesh("ball"), Transform3D(Basis.from_scale(Vector3(0.33, 0.31, 0.33)), Vector3.ZERO), Color("6e4a2a"), Color("9a6d40"))
			for k in 3:
				var a := TAU*k/3.0
				_add(st, Art.mesh("ball"), Transform3D(Basis.from_scale(Vector3.ONE*0.045), Vector3(sin(a)*0.05, 0.145, cos(a)*0.05)), Color("2e2015"))
		"branch":
			_add(st, Art.mesh("rod"), Transform3D(Basis(Vector3.FORWARD, PI/2).scaled(Vector3(0.05, 0.6, 0.05)), Vector3.ZERO), Color("8a6443"))
			_add(st, Art.mesh("rod"), Transform3D(Basis(Vector3.FORWARD, PI/2-0.6).scaled(Vector3(0.035, 0.25, 0.035)), Vector3(0.12, 0.05, 0)), Color("7c5a3c"))
			for k in 3:
				_add(st, Art.mesh("ball"), Transform3D(Basis(Vector3.UP, k*1.9).scaled(Vector3(0.11, 0.02, 0.05)), Vector3(-0.2+k*0.17, 0.04, 0.03*(k%2))), Color("7fb35a"))
		_:
			_add(st, Art.mesh("ball"), Transform3D(Basis.from_scale(Vector3.ONE*0.25), Vector3.ZERO), Color("c9d58f"))
	st.index()
	st.generate_normals()
	var mesh := st.commit()
	# Finds read at the default zoom a touch larger than life (like forage spots).
	var grown := ArrayMesh.new()
	var arrays := mesh.surface_get_arrays(0)
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	for i in verts.size(): verts[i] *= SIZE.get(item, 1.2)
	arrays[Mesh.ARRAY_VERTEX] = verts
	grown.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	mesh = grown
	meshes[item] = mesh
	return mesh

## Appends a primitive with a vertical colour gradient (bottom -> top).
static func _add(st: SurfaceTool, prim: Mesh, xf: Transform3D, bottom: Color, top := Color(0,0,0,0)) -> void:
	var arrays := prim.surface_get_arrays(0)
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var index: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
	var aabb := prim.get_aabb()
	var order := index if not index.is_empty() else PackedInt32Array(range(verts.size()))
	for i in order:
		var v: Vector3 = verts[i]
		var k := clampf((v.y-aabb.position.y)/maxf(aabb.size.y, 0.001), 0.0, 1.0)
		st.set_color(bottom if top.a == 0.0 else bottom.lerp(top, k))
		st.add_vertex(xf*v)
