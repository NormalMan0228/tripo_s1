extends RefCounted
## ISS-1 socket sources: where the sockets of a thing in the world come from, in priority order.
##   1. owner override (after v1)
##   2. authored data (ix_data.gd): room furniture kinds, map props, field swings
##   3. crafted objects, derived on the client from their real geometry: server hints when present
##      (WP16), the designed part boxes of a multi-part craft (carried by the part's own pivot, so a
##      rocking or swinging seat carries the sitter), or the collision boxes of a one-piece craft;
##      the height is always snapped onto the mesh's own triangles
##   4. the bounding box (today's formula, corrected), shown amber in the gizmo
## The owner's 쉬기 flag (rest: sit/lie) decides whether something is a seat; sockets say where and how.
##
## An entry is {rec, carrier, box, node, shape_node, k_on_point, floor_offset}: the record in its
## carrier's frame and what is needed to resolve it live every tick (resolve()).
const Schema = preload("res://scripts/ix/ix_schema.gd")
const IxMath = preload("res://scripts/ix/ix_math.gd")
const IxData = preload("res://scripts/ix/ix_data.gd")
const CraftCollision = preload("res://scripts/craft_collision.gd")
const ObjectTransform = preload("res://scripts/object_transform.gd")
const CACHE_META := "ix_sockets"
## Bumped when the derivation rules change, so cached sockets are rebuilt.
const RULES := 3

# ------------------------------------------------------------------ entry points

## Sockets of a node: a crafted object (asset_assembly or a sample model) or anything with a size.
## hint: "sit" / "lie" (the owner's rest flag) or "" (whatever the shape offers).
static func for_node(node: Node3D, hint := "") -> Array:
	if not is_instance_valid(node): return []
	if node.has_meta("ix_record"): return for_room(node.get_meta("ix_record"))
	var spec = node.get_meta("placement_spec") if node.has_meta("placement_spec") else null
	if spec is Dictionary and IxData.PROP_MODELS.has(str(spec.get("id", ""))): return for_prop(node, str(spec.id))
	return for_crafted(node, hint)

## A map prop with measured sockets (ix_data.gd PROP_MODELS), carried by the prop's own transform
## (its yaw and uniform scale). [] for a model nobody measured.
static func for_prop(node: Node3D, model: String) -> Array:
	var data: Dictionary = IxData.PROP_MODELS.get(model, {})
	if data.is_empty() or not bool(data.get("calibrated", false)): return []
	var key := "prop|%s|%d" % [model, RULES]
	if node.has_meta(CACHE_META) and str(node.get_meta(CACHE_META).get("key", "")) == key: return node.get_meta(CACHE_META).entries
	var entries: Array = []
	for r in data.sockets:
		var rec := Schema.normalize(r)
		rec.source = "authored"
		for one in IxMath.expand(rec, Vector3.ONE):
			entries.append({"rec": one, "carrier": node, "box": AABB(), "node": node, "shape_node": null, "k_on_point": false, "floor_offset": 0.0})
	node.set_meta(CACHE_META, {"key": key, "entries": entries})
	return entries

## A room piece (an Interiors record {kind, node, size, ...}).
static func for_room(record: Dictionary) -> Array:
	var node: Node3D = record.get("node")
	if not is_instance_valid(node): return []
	var kind := str(record.get("kind", ""))
	var size: Vector3 = record.get("size", Vector3.ONE)
	var key := "room|%s|%s|%d" % [kind, str(size), RULES]
	if node.has_meta(CACHE_META) and str(node.get_meta(CACHE_META).get("key", "")) == key: return node.get_meta(CACHE_META).entries
	var actions: Dictionary = load("res://scripts/interiors.gd").ACTIONS
	var raw := IxData.interior(kind, str(actions.get(kind, "")))
	var box := AABB(Vector3(-size.x * 0.5, 0.0, -size.z * 0.5), size)
	var tris: Array = []
	var entries: Array = []
	for r in raw:
		var rec := Schema.normalize(r)
		absolute_params(rec, box)
		for one in IxMath.expand(rec, Vector3.ONE):
			if bool(one.get("snap", true)):
				if tris.is_empty(): tris = triangles(node)
				var p := IxMath.base_point(one, box)
				var hit := ray_down(tris, p.x, p.z, p.y + 0.25, p.y - 0.25)
				if not is_nan(hit):
					one["pos"] = Vector3(p.x, hit, p.z)
					one.erase("rep_dx")
			entries.append({"rec": one, "carrier": node, "box": box, "node": node, "shape_node": null, "k_on_point": false,
				"floor_offset": node.position.y if node.position.y < 0.1 else 0.0})
	node.set_meta(CACHE_META, {"key": key, "entries": entries})
	return entries

## A crafted object: derived from its parts or collision, snapped to its mesh, cached per size/shape.
static func for_crafted(node: Node3D, hint := "") -> Array:
	var shape = node.get_meta("shape") if node.has_meta("shape") else null
	var k := ObjectTransform.factors(shape)
	# Geometry changes with the size and shape edits (and the rest flag decides the hint), not with
	# the runtime state, so clicks do not rebuild it.
	var key := "craft|%s|%s|%s|%s|%d" % [str(node.get_meta("size", Vector3.ONE)), str(shape), str(node.get("rest")), hint, RULES]
	if node.has_meta(CACHE_META) and str(node.get_meta(CACHE_META).get("key", "")) == key: return node.get_meta(CACHE_META).entries
	var boxes := crafted_boxes(node, k)
	var recs: Array = []
	var hints = crafted_hints(node)
	if hints is Array and not hints.is_empty(): recs = hints
	else: recs = derive(boxes, hint, k)
	var source := "derived"
	if recs.is_empty():
		recs = bbox_fallback(base_size(node, k), hint)
		source = "bbox"
	var whole: Node3D = node.get("whole_root") if "whole_root" in node and is_instance_valid(node.get("whole_root")) else node
	var size_base := base_size(node, k)
	var box := AABB(Vector3(-size_base.x * 0.5, 0.0, -size_base.z * 0.5), size_base)
	var tris: Array = []
	var entries: Array = []
	for r in recs:
		var rec := Schema.normalize(r)
		if str(rec.source) == "authored": rec.source = source
		for one in IxMath.expand(rec, k):
			var p := IxMath.base_point(one, box)
			one["pos"] = p
			one.erase("rep_dx")
			one.erase("at")
			if bool(one.get("snap", true)) and k.y != 0.0:
				if tris.is_empty(): tris = triangles(node)
				# Triangles are in the root's frame with the shape applied (and the whole's motion).
				var shaped := whole.transform * (p * k) if whole != node else p * k
				var hit := ray_down(tris, shaped.x, shaped.z, shaped.y + 0.25, shaped.y - 0.25)
				if not is_nan(hit):
					one.pos = Vector3(p.x, p.y + (hit - shaped.y) / k.y, p.z)
					one["snapped"] = true
			var part := str(one.get("carrier", ""))
			var entry := {"rec": one, "carrier": whole, "box": box, "node": node, "shape_node": node, "k_on_point": true, "floor_offset": 0.0}
			# A seat on a moving part rides that part's pivot (a swing's plank, a rocker's seat).
			if not part.is_empty() and "pivots" in node and node.pivots.has(part):
				var rest = part_rest(node, part, k)
				if rest != null:
					var local: Vector3 = (rest as Transform3D).affine_inverse() * (Vector3(one.pos) * k)
					var carried: Dictionary = one.duplicate(true)
					carried.pos = local
					entry = {"rec": carried, "carrier": node.pivots[part], "box": AABB(), "node": node, "shape_node": node, "k_on_point": false, "floor_offset": 0.0}
			entries.append(entry)
	node.set_meta(CACHE_META, {"key": key, "entries": entries})
	return entries

## The resolve context of an entry right now (the carrier may be moving).
static func context(entry: Dictionary) -> Dictionary:
	var carrier: Node3D = entry.carrier
	var shape_node: Node3D = entry.get("shape_node")
	var k := Vector3.ONE
	if is_instance_valid(shape_node): k = ObjectTransform.factors(shape_node.get_meta("shape") if shape_node.has_meta("shape") else null)
	var node: Node3D = entry.node
	var ctx := {"xform": carrier.global_transform, "box": entry.box, "k": k if entry.k_on_point else Vector3.ONE, "mirror": k.x < 0.0, "scale": k.abs()}
	if is_instance_valid(node): ctx["floor_y"] = node.global_position.y - float(entry.get("floor_offset", 0.0))
	return ctx

static func resolve(entry: Dictionary) -> Dictionary:
	if not is_instance_valid(entry.get("carrier")): return {"valid": false, "why": "gone"}
	var out := IxMath.resolve(entry.rec, context(entry))
	out["entry"] = entry
	return out

## Every entry resolved, offered types first ([] when the node has none).
static func resolve_all(entries: Array, types: Array = []) -> Array:
	var out: Array = []
	for e in entries:
		if not types.is_empty() and not str(e.rec.type) in types: continue
		out.append(resolve(e))
	return out

## The socket's point right now without building a dictionary (HOLD re-reads it every tick).
static func point_now(entry: Dictionary) -> Vector3:
	return IxMath.socket_point(entry.rec, context(entry))

# ------------------------------------------------------------------ crafted geometry

## Server hints (WP16): interaction.sockets in the assembly manifest; [] when absent.
static func crafted_hints(node: Node3D):
	if not "manifest" in node or not node.manifest is Dictionary: return []
	var interaction = node.manifest.get("interaction")
	if not interaction is Dictionary or not interaction.get("sockets") is Array: return []
	var out: Array = []
	for s in interaction.sockets:
		if s is Dictionary and str(s.get("type", "")) in Schema.TYPES:
			var r: Dictionary = s.duplicate(true)
			r["source"] = "server"
			r["snap"] = true
			out.append(r)
	return out

## The object's size before its shape edit.
static func base_size(node: Node3D, k: Vector3) -> Vector3:
	if node.has_meta("shape_base"): return node.get_meta("shape_base").size
	var size: Vector3 = node.get_meta("size", Vector3.ONE)
	return size / k.abs()

## Boxes of the made shape in the object's base frame (k = 1): [{box: AABB, part: id}].
static func crafted_boxes(node: Node3D, k: Vector3) -> Array:
	var out: Array = []
	if "pivots" in node and "manifest" in node and not bool(node.get("one_piece")) and node.pivots.size() > 1 and node.manifest.has("plan"):
		for p in node.manifest.plan.parts:
			var id := str(p.id)
			var rest = part_rest(node, id, Vector3.ONE)
			if rest == null: continue
			var size := Vector3(p.size[0], p.size[1], p.size[2])
			var pivot := Vector3(p.get("pivot", [0, 0, 0])[0], p.get("pivot", [0, 0, 0])[1], p.get("pivot", [0, 0, 0])[2])
			out.append({"box": transform_box(rest, AABB((-pivot - Vector3(0.5, 0.5, 0.5)) * size, size)), "part": id})
		if not out.is_empty(): return out
	for body in node.get_children():
		if not body is StaticBody3D: continue
		for child in body.get_children():
			if child is CollisionShape3D and child.has_meta("base_size"):
				var s: Vector3 = child.get_meta("base_size")
				out.append({"box": AABB(Vector3(child.get_meta("base_center")) - s * 0.5, s), "part": ""})
	if not out.is_empty(): return out
	for b in CraftCollision.boxes_for(node):
		out.append({"box": unscale_box(b, k), "part": ""})
	return out

## A part pivot's rest transform in the whole_root frame with shape k (its own and its ancestors'
## motion left out): the ShapeFrame and the chain of holders. null when the part is unknown.
static func part_rest(node: Node3D, part: String, k: Vector3):
	if not "pose_nodes" in node or not node.pose_nodes.has(part): return null
	var holder: Node3D = node.pose_nodes[part]
	var frame := ObjectTransform.frame_of(node)
	if frame == null: return null
	var chain := Transform3D.IDENTITY
	var current: Node = holder
	while current != null and current != frame:
		if current is Node3D and str(current.name).ends_with("_pose"): chain = (current as Node3D).transform * chain
		current = current.get_parent()
	if current != frame: return null
	var base_scale: Vector3 = frame.scale
	var base_position: Vector3 = frame.position
	if node.has_meta("shape_base"):
		base_scale = node.get_meta("shape_base").scale
		base_position = node.get_meta("shape_base").position
	return Transform3D(Basis.from_scale(base_scale * k), base_position * k) * chain

static func transform_box(t: Transform3D, box: AABB) -> AABB:
	var out := AABB(t * box.position, Vector3.ZERO)
	for i in 8: out = out.expand(t * box.get_endpoint(i))
	return out

static func scale_box(box: AABB, k: Vector3) -> AABB:
	var a := box.position * k
	var b := box.end * k
	return AABB(Vector3(minf(a.x, b.x), minf(a.y, b.y), minf(a.z, b.z)), (b - a).abs())

static func unscale_box(box: AABB, k: Vector3) -> AABB:
	return scale_box(box, Vector3(1.0 / k.x, 1.0 / k.y, 1.0 / k.z))

## Converts *_frac params to metres of the box.
static func absolute_params(rec: Dictionary, box: AABB) -> void:
	var p: Dictionary = rec.params
	if p.has("width_frac"): p["width"] = box.size.x * float(p.width_frac)
	if p.has("depth_frac"): p["depth"] = box.size.z * float(p.depth_frac)
	if p.has("length_frac"): p["length"] = (box.size.z if str(p.get("head", "l")) in ["l", "r"] and absf(float(rec.yaw)) > 45.0 else box.size.x) * float(p.length_frac)
	for key in ["width_frac", "depth_frac", "length_frac"]: p.erase(key)

# ------------------------------------------------------------------ derivation (pure)

## Socket records (base frame, `pos` in metres) from boxes [{box, part}] of the made shape; k is the
## player's shape edit (decisions use the real, shaped sizes). hint "lie" prefers lying.
static func derive(boxes: Array, hint: String, k := Vector3.ONE) -> Array:
	var shaped: Array = []
	for b in boxes: shaped.append({"box": scale_box(b.box, k), "part": str(b.get("part", ""))})
	var tops := exposed_tops(shaped)
	var out: Array = []
	if hint == "lie":
		out = derive_lie(tops, shaped)
		if out.is_empty(): out = derive_sit(tops, shaped, true)
	else:
		out = derive_sit(tops, shaped, false)
	# Back to the base frame.
	var ak := k.abs()
	for r in out:
		r.pos = Vector3(r.pos) / k
		var p: Dictionary = r.params
		if p.has("width"): p.width = float(p.width) / ak.x
		if p.has("depth"): p.depth = float(p.depth) / ak.z
		if p.has("length"): p.length = float(p.length) / (ak.z if absf(float(r.yaw)) > 45.0 and absf(float(r.yaw)) < 135.0 else ak.x)
		if k.x < 0.0:
			# Records are stored unmirrored; the resolution mirrors them again.
			r.yaw = -float(r.yaw)
			if p.has("head"): p.head = IxMath.mirror_side(str(p.head))
	return out

## Upward faces nothing rests on: [{rect: Rect2 (x, z), t, area, part, box}], coplanar touching
## tops merged (|dt| < 0.06), largest first.
static func exposed_tops(shaped: Array) -> Array:
	var raw: Array = []
	for i in shaped.size():
		var b: AABB = shaped[i].box
		var rect := Rect2(b.position.x, b.position.z, b.size.x, b.size.z)
		if rect.get_area() < 0.02: continue
		var t := b.end.y
		var free := 0
		for gx in 6:
			for gz in 6:
				var px := rect.position.x + rect.size.x * (gx + 0.5) / 6.0
				var pz := rect.position.y + rect.size.y * (gz + 0.5) / 6.0
				var covered := false
				for j in shaped.size():
					if j == i: continue
					var o: AABB = shaped[j].box
					if o.position.y < t - 0.03 or o.position.y > t + 0.45 or o.end.y < t + 0.02: continue
					if px >= o.position.x and px <= o.end.x and pz >= o.position.z and pz <= o.end.z:
						covered = true
						break
				if not covered: free += 1
		if free < 12: continue
		raw.append({"rect": rect, "t": t, "part": shaped[i].part, "box": b, "free": free / 36.0})
	# Merge coplanar tops that touch (seat cushions, a pad on a frame).
	var merged: Array = []
	for top in raw:
		var joined := false
		for m in merged:
			if absf(float(m.t) - float(top.t)) < 0.06 and (m.rect as Rect2).grow(0.02).intersects(top.rect):
				var bigger: bool = (top.rect as Rect2).get_area() > (m.rect as Rect2).get_area()
				m.rect = (m.rect as Rect2).merge(top.rect)
				if float(top.t) > float(m.t): m.t = top.t
				if bigger: m.part = top.part
				joined = true
				break
		if not joined: merged.append(top.duplicate())
	for m in merged: m["area"] = (m.rect as Rect2).get_area()
	merged.sort_custom(func(a, b): return float(a.area) > float(b.area) + 1e-6 or (absf(float(a.area) - float(b.area)) <= 1e-6 and float(a.t) < float(b.t)))
	return merged

## Which edge of a seat rect a tall box stands on: "-z", "+z", "-x", "+x" or "".
static func back_edge(rect: Rect2, t: float, shaped: Array, rise := 0.20) -> Dictionary:
	var best := {"edge": "", "top": -INF}
	for s in shaped:
		var o: AABB = s.box
		if o.end.y < t + rise: continue
		var cx := o.get_center().x
		var cz := o.get_center().z
		var span_x := maxf(0.0, minf(o.end.x, rect.end.x) - maxf(o.position.x, rect.position.x)) / maxf(0.01, rect.size.x)
		var span_z := maxf(0.0, minf(o.end.z, rect.end.y) - maxf(o.position.z, rect.position.y)) / maxf(0.01, rect.size.y)
		var edge := ""
		if span_x >= 0.5 and o.end.z >= rect.position.y - 0.05 and o.position.z <= rect.position.y + 0.15 and cz < rect.get_center().y: edge = "-z"
		elif span_x >= 0.5 and o.position.z <= rect.end.y + 0.05 and o.end.z >= rect.end.y - 0.15 and cz > rect.get_center().y: edge = "+z"
		elif span_z >= 0.5 and o.end.x >= rect.position.x - 0.05 and o.position.x <= rect.position.x + 0.15 and cx < rect.get_center().x: edge = "-x"
		elif span_z >= 0.5 and o.position.x <= rect.end.x + 0.05 and o.end.x >= rect.end.x - 0.15 and cx > rect.get_center().x: edge = "+x"
		if edge.is_empty(): continue
		var score := o.end.y + (0.3 if edge in ["-z", "+z"] else 0.0)
		if score > float(best.top):
			best = {"edge": edge, "top": score, "box": o}
	return best

static func derive_sit(tops: Array, shaped: Array, edge_only: bool) -> Array:
	var pick := {}
	var kind := "sit"
	for top in tops:
		if float(top.t) >= 0.25 and float(top.t) <= 0.75 and (top.rect as Rect2).size.x >= 0.25 and (top.rect as Rect2).size.y >= 0.25:
			pick = top
			break
	if pick.is_empty():
		for top in tops:
			if float(top.t) > 0.75 and float(top.t) <= 1.10 and (top.rect as Rect2).get_area() >= 0.06:
				pick = top
				kind = "perch"
				break
	if pick.is_empty():
		var highest := -INF
		for top in tops:
			if float(top.t) < 0.15 and float(top.t) > highest and (top.rect as Rect2).get_area() >= 0.2:
				highest = float(top.t)
				pick = top
				kind = "sit_ground"
	if pick.is_empty(): return []
	var rect: Rect2 = pick.rect
	var t := float(pick.t)
	var back := back_edge(rect, t, shaped) if not edge_only else {"edge": ""}
	var edge := str(back.edge)
	# Front is opposite the back; default +Z.
	var yaw := {"-z": 0.0, "+z": 180.0, "-x": 90.0, "+x": -90.0}.get(edge, 0.0) as float
	var fwd := IxMath.dir_of(deg_to_rad(yaw))
	var side := Vector3(fwd.z, 0, -fwd.x)
	# Seat extent along the sitter's forward and sideways axes.
	var centre := Vector3(rect.get_center().x, t, rect.get_center().y)
	var half_depth := absf(fwd.x) * rect.size.x * 0.5 + absf(fwd.z) * rect.size.y * 0.5
	var half_width := absf(side.x) * rect.size.x * 0.5 + absf(side.z) * rect.size.y * 0.5
	var front_edge := half_depth
	var back_edge_at := -half_depth
	if back.has("box"):
		var b: AABB = back.box
		# The back's front face along forward from the seat centre: the seat's depth ends there.
		var face := -INF
		for i in 8: face = maxf(face, (b.get_endpoint(i) - centre).dot(fwd))
		back_edge_at = clampf(face, -half_depth, front_edge - 0.2)
	var depth := front_edge - back_edge_at
	# Arms on the sides narrow the seat.
	var left_in := half_width
	var right_in := half_width
	var arms := false
	for s in shaped:
		var o: AABB = s.box
		if o.end.y < t + 0.05 or o.end.y > t + 0.55 or (back.has("box") and o == back.box): continue
		var c := o.get_center() - centre
		var along := c.dot(side)
		var across := absf(c.dot(fwd))
		if across > half_depth: continue
		var extent := absf(side.x) * o.size.x * 0.5 + absf(side.z) * o.size.z * 0.5
		if along > half_width * 0.55 and along - extent < half_width + 0.05:
			left_in = minf(left_in, along - extent)
			arms = true
		elif along < -half_width * 0.55 and -along - extent < half_width + 0.05:
			right_in = minf(right_in, -along - extent)
			arms = true
	var width := maxf(0.2, left_in + right_in)
	var middle := (left_in - right_in) * 0.5
	var count := clampi(int(floor(width / 0.55)), 1, 4)
	if kind == "sit_ground": count = 1
	var inset := clampf(depth * 0.55, 0.12, 0.30)
	var out: Array = []
	for i in count:
		var lateral := middle + ((float(i) + 0.5) / count - 0.5) * width
		var p := centre + fwd * (front_edge - inset) + side * lateral
		var variant := "bench" if count > 1 else ("chair" if not edge.is_empty() else "stool")
		if arms and count == 1 and not edge.is_empty(): variant = "armchair"
		if kind == "perch": variant = "stool"
		out.append({"id": "seat_%d" % i, "type": kind, "variant": variant, "carrier": str(pick.part), "pos": p, "yaw": yaw, "snap": true,
			"params": {"back": not edge.is_empty(), "arms": arms, "width": width / count, "depth": depth}, "source": "derived"})
	return out

static func derive_lie(tops: Array, shaped: Array) -> Array:
	var pick := {}
	for top in tops:
		var r: Rect2 = top.rect
		var long := maxf(r.size.x, r.size.y)
		var short := minf(r.size.x, r.size.y)
		if float(top.t) < 0.12 or float(top.t) > 1.05 or short < 0.45: continue
		# A raised backrest at one end lengthens a lounger.
		var ext := _backrest(r, float(top.t), shaped)
		if long + float(ext.length) >= 1.3:
			pick = top.duplicate()
			pick["ext"] = ext
			break
	if pick.is_empty(): return []
	var rect: Rect2 = pick.rect
	var t := float(pick.t)
	var along_x := rect.size.x > rect.size.y
	var ext: Dictionary = pick.ext
	var long := maxf(rect.size.x, rect.size.y)
	var short := minf(rect.size.x, rect.size.y)
	# The head goes toward a headboard or backrest, else toward -Z (or -X when the bed lies along x).
	var head_sign := -1.0
	var tall := _end_box(rect, t, shaped, along_x)
	if not ext.end.is_empty(): head_sign = -1.0 if ext.end == "-" else 1.0
	elif tall != 0.0: head_sign = tall
	var axis := Vector3.RIGHT if along_x else Vector3.BACK
	var centre := Vector3(rect.get_center().x, t, rect.get_center().y)
	var recline := float(ext.recline)
	# Hips: the middle shifted 0.10 toward the feet (on a lounger, just past the backrest's foot).
	var pelvis := centre - axis * head_sign * 0.10
	if recline > 0.0: pelvis = centre + axis * head_sign * (long * 0.5 - 0.35)
	var out: Array = []
	var sides := [Vector3(0, 0, 1), Vector3(0, 0, -1)] if along_x else [Vector3(1, 0, 0), Vector3(-1, 0, 0)]
	for i in 2:
		var out_dir: Vector3 = sides[i]
		var yaw := rad_to_deg(atan2(out_dir.x, out_dir.z))
		# Head side as seen sitting on this edge facing out: the character's left is up x forward.
		var left := Vector3.UP.cross(out_dir)
		var head_dir := axis * head_sign
		var head := "l" if left.dot(head_dir) > 0.0 else "r"
		out.append({"id": "lie_%d" % i, "type": "lie", "variant": "lounger" if recline > 0.0 else "bed", "group": "lie", "carrier": str(pick.part),
			"pos": pelvis, "yaw": yaw, "snap": true, "source": "derived",
			"params": {"head": head, "length": long + float(ext.length), "width": short, "recline_deg": recline}})
	return out

## A box rising at one short end of a lying surface: {end "-"/"+"/"", length, recline (deg)}.
static func _backrest(rect: Rect2, t: float, shaped: Array) -> Dictionary:
	var along_x := rect.size.x > rect.size.y
	for s in shaped:
		var o: AABB = s.box
		if o.end.y < t + 0.15 or o.end.y > t + 0.9: continue
		var o_lo := o.position.x if along_x else o.position.z
		var o_hi := o.end.x if along_x else o.end.z
		var r_lo := rect.position.x if along_x else rect.position.y
		var r_hi := rect.end.x if along_x else rect.end.y
		var across_lo := o.position.z if along_x else o.position.x
		var across_hi := o.end.z if along_x else o.end.x
		var c_lo := rect.position.y if along_x else rect.position.x
		var c_hi := rect.end.y if along_x else rect.end.x
		if minf(across_hi, c_hi) - maxf(across_lo, c_lo) < (c_hi - c_lo) * 0.5: continue
		var depth := o_hi - o_lo
		if depth < 0.25: continue
		var rise := o.end.y - t
		var recline := clampf(rad_to_deg(atan2(rise, depth)), 15.0, 45.0)
		if o_lo < r_lo + 0.1 and o_hi <= r_lo + depth + 0.05: return {"end": "-", "length": maxf(0.0, r_lo - o_lo), "recline": recline}
		if o_hi > r_hi - 0.1 and o_lo >= r_hi - depth - 0.05: return {"end": "+", "length": maxf(0.0, o_hi - r_hi), "recline": recline}
	return {"end": "", "length": 0.0, "recline": 0.0}

## +1 / -1 for the short end with a taller box (a headboard), 0 when neither or both.
static func _end_box(rect: Rect2, t: float, shaped: Array, along_x: bool) -> float:
	var lo := false
	var hi := false
	for s in shaped:
		var o: AABB = s.box
		if o.end.y < t + 0.15: continue
		var c := o.get_center()
		var at := c.x if along_x else c.z
		var r_lo := rect.position.x if along_x else rect.position.y
		var r_hi := rect.end.x if along_x else rect.end.y
		if absf(at - r_lo) < 0.2: lo = true
		elif absf(at - r_hi) < 0.2: hi = true
	if lo == hi: return 0.0
	return -1.0 if lo else 1.0

## Today's formula, corrected: a seat at half the height but at most 0.5 m; a bed lies along its length.
static func bbox_fallback(size: Vector3, hint: String) -> Array:
	if hint == "lie":
		var along_x := size.x > size.z
		var yaw := 0.0 if along_x else 90.0
		return [{"id": "lie_0", "type": "lie", "variant": "bed", "pos": Vector3(0, minf(size.y * 0.5, 0.62), 0), "yaw": yaw, "snap": true, "source": "bbox",
			"params": {"head": "r" if along_x else "l", "length": maxf(size.x, size.z), "width": minf(size.x, size.z)}}]
	return [{"id": "seat_0", "type": "sit", "variant": "chair", "pos": Vector3(0, minf(size.y * 0.5, 0.5), 0.04), "yaw": 0.0, "snap": true, "source": "bbox",
		"params": {"width": minf(size.x, 0.6), "depth": minf(size.z, 0.5)}}]

# ------------------------------------------------------------------ mesh snap

## The node's triangles in its own frame as [PackedVector3Array a, b, c] flattened per mesh, with an
## xz bound per triangle for a fast reject: [[verts PackedVector3Array (3 per tri)], ...].
static func triangles(node: Node3D) -> Array:
	var out: Array = []
	for part in CraftCollision.surfaces(node):
		var vertices: PackedVector3Array = part[0]
		var indices: PackedInt32Array = part[1]
		var flat := PackedVector3Array()
		flat.resize(indices.size() - indices.size() % 3)
		for i in flat.size(): flat[i] = vertices[indices[i]]
		out.append(flat)
	return out

## The highest surface hit by a vertical ray at (x, z) between y_top and y_bottom (NAN: none).
static func ray_down(tris: Array, x: float, z: float, y_top: float, y_bottom: float) -> float:
	var best := NAN
	var from := Vector3(x, y_top, z)
	var dir := Vector3.DOWN
	for flat in tris:
		var v: PackedVector3Array = flat
		for i in range(0, v.size() - 2, 3):
			var a := v[i]
			var b := v[i + 1]
			var c := v[i + 2]
			if x < minf(a.x, minf(b.x, c.x)) or x > maxf(a.x, maxf(b.x, c.x)) or z < minf(a.z, minf(b.z, c.z)) or z > maxf(a.z, maxf(b.z, c.z)): continue
			var hit = Geometry3D.ray_intersects_triangle(from, dir, a, b, c)
			if hit == null: continue
			var y: float = (hit as Vector3).y
			if y < y_bottom or y > y_top: continue
			if is_nan(best) or y > best: best = y
	return best
