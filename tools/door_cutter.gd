extends SceneTree
## Cuts doors and windows out of the village building models along outlines the user drew on facade
## renders (artifacts/outline_tool: renders/<model>__<face>.png + .json, outlines/<render_id>.json).
## Headless, from the repository root:
##   .tools/godot/Godot_v4.7.2-stable_win64_console.exe --headless --path game --script res://../tools/door_cutter.gd
##       [-- --renders=DIR --outlines=DIR --only=<render_id> --synthetic]
## Render metadata (model-local, Y up): {model, building_ids, face, width_px, height_px, mpp, origin_tl,
## u (+pixel x), v (+pixel y, down), view_dir (into the facade)}; a pixel (px, py) is the model point
## origin_tl + px*mpp*u + py*mpp*v (+ depth along view_dir).
## Outlines: {render_id, polys: [{kind: "door"|"window", hinge: "left"|"right"|null, closed, pts: [[px, py]...]}]}.
## For every outline the mesh the camera sees inside it is taken whole: each building triangle facing the
## camera on the visible surface (within SURFACE_BAND of the front-most depth there) is split along the
## outline (Geometry2D polygon clipping, any simple polygon, attributes interpolated): the part inside
## goes to the door (or window), the part outside stays in the building, so nothing of the door is left
## on the wall and nothing of the wall comes with the door.
##  door    doors/<model>.res          the leaf: the inside faces made solid THICKNESS deep (back faces,
##                                     side faces coloured by the door's edge), hinge corner at the origin
##          doors/<model>_opening.res  the inside faces alone, for the dark doorway
##          doors/<model>_cut.res      per building surface, the outside parts of the split triangles
##          door_leaves.json           per building id: frame (hinge corner, x across towards the free
##                                     edge's opposite, y up, z out), hinge side, size, the dropped
##                                     triangles per surface ("drop"), the resources
##  window  windows/<model>_glass.res  the panes inside the window outlines (item 9's glass)
## Prints DOOR_CUT <render_id> <kind> {...} per outline: triangles taken, split, the outline's area and
## the area cut, and the visible building area left inside the outline after the cut (must be 0).
## --synthetic writes a render description and a rectangle outline round the red house's door from
## door_leaves.json (no image) under artifacts/outline_tool/synthetic/ and cuts that, to try the cutter
## before real outlines arrive.
const Doors = preload("res://maps/archipelago/building_doors.gd")
const PLACEMENTS := "res://maps/archipelago/building_placements.json"
const WINDOWS_DIR := "res://maps/archipelago/windows/"
const THICKNESS := 0.06
const CELL := 0.02
## A piece belongs to what the camera sees when it lies this close to the front-most surface there.
const SURFACE_BAND := 0.08
const EDGE_STEP := 0.03
## Hinge sides and opening directions as decided (or set by the user: "override": true).
const HINGES := "res://maps/archipelago/door_hinges.json"
## A single outline at least this wide (metres), or this wide for its height, is a pair of doors.
const DOUBLE_WIDTH := 1.6
const DOUBLE_ASPECT := 0.9
var hinges := {}
var overrides := {}
var renders_dir := "res://../artifacts/outline_tool/renders/"
var outlines_dir := "res://../artifacts/outline_tool/outlines/"

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var only := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--renders="): renders_dir = arg.trim_prefix("--renders=").trim_suffix("/")+"/"
		if arg.begins_with("--outlines="): outlines_dir = arg.trim_prefix("--outlines=").trim_suffix("/")+"/"
		if arg.begins_with("--only="): only = arg.trim_prefix("--only=")
	if "--synthetic" in OS.get_cmdline_user_args():
		renders_dir = "res://../artifacts/outline_tool/synthetic/renders/"
		outlines_dir = "res://../artifacts/outline_tool/synthetic/outlines/"
	renders_dir = absolute(renders_dir)
	outlines_dir = absolute(outlines_dir)
	if "--synthetic" in OS.get_cmdline_user_args(): write_synthetic()
	var table: Dictionary = Doors.table().duplicate(true)
	hinges = {}
	if FileAccess.file_exists(HINGES):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(HINGES))
		if parsed is Dictionary: overrides = parsed
	var placements: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(PLACEMENTS))
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(Doors.DOORS_DIR))
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(WINDOWS_DIR))
	var files := DirAccess.get_files_at(outlines_dir)
	var cut := 0
	for name in files:
		if not name.ends_with(".json"): continue
		var render_id := name.get_basename()
		if not only.is_empty() and render_id != only: continue
		var outline = JSON.parse_string(FileAccess.get_file_as_string(outlines_dir+name))
		var meta = JSON.parse_string(FileAccess.get_file_as_string(renders_dir+render_id+".json"))
		if not (outline is Dictionary) or not (meta is Dictionary):
			print("DOOR_CUT ", render_id, " missing render metadata or outline")
			continue
		var model := model_path(String(meta.model))
		var ids: Array = meta.get("building_ids", [])
		if ids.is_empty():
			for spec: Dictionary in placements.buildings:
				if String(spec.model) == model: ids.append(String(spec.id))
		var mesh_faces := load_model(model)
		var windows := ArrayMesh.new()
		var doors := []
		for poly: Dictionary in outline.get("polys", []):
			var pts: Array = poly.get("pts", [])
			if pts.size() < 3: continue
			if String(poly.kind) == "door":
				var px := PackedVector2Array()
				for p in pts: px.append(Vector2(float(p[0]), float(p[1])))
				doors.append(px)
				continue
			var result := cut_outline(mesh_faces, meta, pts)
			print("DOOR_CUT ", render_id, " window ", JSON.stringify(result.stats))
			cut += 1
			append_pieces(windows, result.inside, mesh_faces.materials)
		# Doors: the user's outlines joined into one opening and split into leaves; the hinges and the
		# opening direction are decided here (door_hinges.json overrides them).
		var image: Image = Image.load_from_file(renders_dir+render_id+".png") if FileAccess.file_exists(renders_dir+render_id+".png") else null
		var plan := plan_opening(doors, meta, image, ids)
		if not plan.is_empty():
			var union_pts := []
			for p in plan.union: union_pts.append([p.x, p.y])
			var result := cut_outline(mesh_faces, meta, union_pts)
			print("DOOR_CUT ", render_id, " door ", JSON.stringify(result.stats), " leaves=", plan.leaves.map(func(l): return [l.hinge, l.reason]), " opens=", plan.opens)
			cut += 1
			var entry := save_opening(model, result, plan, mesh_faces, float(meta.mpp))
			entry["render_id"] = render_id
			for id in ids:
				table[id] = entry
				hinges[id] = {"leaves": plan.leaves.map(func(l): return {"hinge": l.hinge, "reason": l.reason}), "opens": plan.opens}
		if windows.get_surface_count() > 0:
			ResourceSaver.save(windows, WINDOWS_DIR+model.get_file().get_basename()+"_glass.res")
	var file := FileAccess.open(Doors.RECTS, FileAccess.WRITE)
	file.store_string(JSON.stringify(table, "\t", true))
	file.close()
	# The decisions, for the user to flip: an entry with "override": true is kept as it is next time.
	for id in overrides:
		if (overrides[id] as Dictionary).get("override", false): hinges[id] = overrides[id]
	var saved := FileAccess.open(HINGES, FileAccess.WRITE)
	saved.store_string(JSON.stringify(hinges, "\t", true))
	saved.close()
	print("DOOR_CUT_DONE outlines=", cut)
	quit(0)

## "res://../x" (outside the project) or a relative path as an absolute folder path ending in "/".
static func absolute(path: String) -> String:
	if path.begins_with("res://"): path = ProjectSettings.globalize_path("res://").path_join(path.trim_prefix("res://"))
	elif path.is_relative_path(): path = ProjectSettings.globalize_path("res://").path_join(path)
	return path.simplify_path()+"/"

static func model_path(model: String) -> String:
	if model.begins_with("res://"): return model
	return "res://maps/archipelago/assets/buildings/"+model.get_file().get_basename()+".glb"

## Every triangle of the model with its attributes, in model space:
## {tris: [{key, index, p: [3 Vector3], n, tg, uv}], materials: {key: material}, keys: {key: [path, surface]}}.
static func load_model(model: String) -> Dictionary:
	var scene: PackedScene = load(model)
	var root := scene.instantiate() as Node3D
	var tris := []
	var materials := {}
	for item in root.find_children("*", "MeshInstance3D", true, false):
		var mesh := item as MeshInstance3D
		var t := Transform3D()
		var node: Node = mesh
		while node != root and node != null:
			t = (node as Node3D).transform*t
			node = node.get_parent()
		var path := String(root.get_path_to(mesh))
		for s in mesh.mesh.get_surface_count():
			var arrays := mesh.mesh.surface_get_arrays(s)
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var normals = arrays[Mesh.ARRAY_NORMAL]
			var tangents = arrays[Mesh.ARRAY_TANGENT]
			var uvs = arrays[Mesh.ARRAY_TEX_UV]
			var index = arrays[Mesh.ARRAY_INDEX]
			if not (index is PackedInt32Array): continue
			var key := "%s|%d" % [path, s]
			materials[key] = mesh.get_active_material(s)
			for i in range(0, index.size(), 3):
				var tri := {"key": key, "index": i/3, "p": [], "n": [], "tg": [], "uv": []}
				for k in 3:
					var v: int = index[i+k]
					tri.p.append(t*vertices[v])
					tri.n.append((t.basis*normals[v]).normalized() if normals is PackedVector3Array else Vector3.UP)
					if tangents is PackedFloat32Array and tangents.size() >= (v+1)*4:
						var tg := t.basis*Vector3(tangents[v*4], tangents[v*4+1], tangents[v*4+2])
						tri.tg.append(Vector4(tg.x, tg.y, tg.z, tangents[v*4+3]))
					else: tri.tg.append(Vector4(1, 0, 0, 1))
					tri.uv.append(uvs[v] if uvs is PackedVector2Array else Vector2.ZERO)
				tris.append(tri)
	root.free()
	return {"tris": tris, "materials": materials}

## Splits the model along one outline. Returns {inside: [pieces], outside: {key: [pieces]}, drop: {key:
## [triangle index]}, frame: {...}, stats}. A piece is {key, verts: [[position, normal, tangent, uv]...]}
## (triangles, model space, source winding).
func cut_outline(model: Dictionary, meta: Dictionary, pts: Array) -> Dictionary:
	var mpp := float(meta.mpp)
	var o := vec(meta.origin_tl)
	var u := vec(meta.u)
	var v := vec(meta.v)
	var into := vec(meta.view_dir).normalized()
	var poly := PackedVector2Array()
	for p in pts: poly.append(Vector2(float(p[0]), float(p[1]))*mpp)
	var box := Rect2(poly[0], Vector2.ZERO)
	for p in poly: box = box.expand(p)
	var project := func(p: Vector3) -> Vector3: return Vector3((p-o).dot(u), (p-o).dot(v), -(p-o).dot(into))
	# Triangles facing the camera that reach into the outline's box, projected (x right, y down, z out).
	var near := []
	for tri: Dictionary in model.tris:
		var a: Vector3 = project.call(tri.p[0])
		var b: Vector3 = project.call(tri.p[1])
		var c: Vector3 = project.call(tri.p[2])
		if maxf(a.x, maxf(b.x, c.x)) < box.position.x or minf(a.x, minf(b.x, c.x)) > box.end.x: continue
		if maxf(a.y, maxf(b.y, c.y)) < box.position.y or minf(a.y, minf(b.y, c.y)) > box.end.y: continue
		var area := (b.x-a.x)*(c.y-a.y)-(c.x-a.x)*(b.y-a.y)
		if absf(area) < 1e-9: continue
		# Facing the camera: the outward normal (Godot winds front faces clockwise) points to +z.
		var outward: Vector3 = -((tri.p[1] as Vector3)-(tri.p[0] as Vector3)).cross((tri.p[2] as Vector3)-(tri.p[0] as Vector3))
		if outward.dot(-into) <= 0.0: continue
		near.append([tri, [a, b, c]])
	# The front-most depth seen in each cell of the outline's box.
	var front := {}
	for entry in near:
		var q: Array = entry[1]
		var lo := Vector2(minf(q[0].x, minf(q[1].x, q[2].x)), minf(q[0].y, minf(q[1].y, q[2].y)))
		var hi := Vector2(maxf(q[0].x, maxf(q[1].x, q[2].x)), maxf(q[0].y, maxf(q[1].y, q[2].y)))
		for cx in range(floori(maxf(lo.x, box.position.x)/CELL), floori(minf(hi.x, box.end.x)/CELL)+1):
			for cy in range(floori(maxf(lo.y, box.position.y)/CELL), floori(minf(hi.y, box.end.y)/CELL)+1):
				var w := bary(Vector2((cx+.5)*CELL, (cy+.5)*CELL), Vector2(q[0].x, q[0].y), Vector2(q[1].x, q[1].y), Vector2(q[2].x, q[2].y))
				if w.x < -1e-4 or w.y < -1e-4 or w.z < -1e-4: continue
				var z: float = q[0].z*w.x+q[1].z*w.y+q[2].z*w.z
				var cell := Vector2i(cx, cy)
				if not front.has(cell) or z > float(front[cell][0]): front[cell] = [z, (entry[0].uv[0] as Vector2)*w.x+(entry[0].uv[1] as Vector2)*w.y+(entry[0].uv[2] as Vector2)*w.z]
	var inside := []
	var outside := {}
	var drop := {}
	var taken := []
	var stats := {"triangles_near": near.size(), "taken_whole": 0, "split": 0, "outline_m2": 0.0, "cut_m2": 0.0, "left_m2": 0.0}
	stats.outline_m2 = absf(signed_area(poly))
	for entry in near:
		var tri: Dictionary = entry[0]
		var q: Array = entry[1]
		var tri2 := PackedVector2Array([Vector2(q[0].x, q[0].y), Vector2(q[1].x, q[1].y), Vector2(q[2].x, q[2].y)])
		var pieces_in := Geometry2D.intersect_polygons(tri2, poly)
		if pieces_in.is_empty(): continue
		# Only the surface the camera sees: a hidden face behind the door stays where it is.
		var visible := false
		for piece in pieces_in:
			var c := centroid(piece)
			var w := bary(c, tri2[0], tri2[1], tri2[2])
			var z: float = q[0].z*w.x+q[1].z*w.y+q[2].z*w.z
			var cell := Vector2i(floori(c.x/CELL), floori(c.y/CELL))
			if not front.has(cell) or z >= float(front[cell][0])-SURFACE_BAND: visible = true
		if not visible: continue
		var pieces_out := Geometry2D.clip_polygons(tri2, poly)
		var turns := pieces_out.map(func(p): return Geometry2D.is_polygon_clockwise(p))
		if turns.has(true) and turns.has(false):
			# The outline lies inside this one triangle (it would leave a hole): cut the triangle in two
			# down a line through the outline first, then each half has no hole.
			stats["holes"] = int(stats.get("holes", 0))+1
			var x := centroid(poly).x
			var span := 1000.0
			pieces_in = []
			pieces_out = []
			for half in [PackedVector2Array([Vector2(x-span, -span), Vector2(x, -span), Vector2(x, span), Vector2(x-span, span)]),
					PackedVector2Array([Vector2(x, -span), Vector2(x+span, -span), Vector2(x+span, span), Vector2(x, span)])]:
				for part in Geometry2D.intersect_polygons(tri2, half):
					pieces_in.append_array(Geometry2D.intersect_polygons(part, poly))
					pieces_out.append_array(Geometry2D.clip_polygons(part, poly))
		if not drop.has(tri.key): drop[tri.key] = []
		drop[tri.key].append(int(tri.index))
		taken.append([tri, tri2])
		var whole := absf(signed_area(tri2)) > 0.0 and is_equal_approx(area_sum(pieces_in), absf(signed_area(tri2))) and pieces_out.is_empty()
		stats.taken_whole += 1 if whole else 0
		stats.split += 0 if whole else 1
		for piece in pieces_in:
			stats.cut_m2 += absf(signed_area(piece))
			inside.append({"key": tri.key, "verts": triangulate(piece, tri, tri2)})
		if not whole:
			if not outside.has(tri.key): outside[tri.key] = []
			for piece in pieces_out:
				if piece.size() >= 3: outside[tri.key].append({"key": tri.key, "verts": triangulate(piece, tri, tri2)})
	# What the camera would still see of the building inside the outline after the cut (must be 0):
	# cells whose front-most surface came from a triangle that stayed.
	stats.left_m2 = snappedf(float(left_inside(near, drop, poly, front)), 0.0001)
	stats.outline_m2 = snappedf(stats.outline_m2, 0.0001)
	stats.cut_m2 = snappedf(stats.cut_m2, 0.0001)
	var deepest := -INF
	for cell in front:
		if Geometry2D.is_point_in_polygon((Vector2(cell)+Vector2(.5, .5))*CELL, poly): deepest = maxf(deepest, float(front[cell][0]))
	return {"inside": inside, "outside": outside, "drop": drop, "taken": taken, "poly": poly, "front": front, "box": box, "front_z": deepest,
		"o": o, "u": u, "v": v, "into": into, "stats": stats}

## Visible building area left inside the outline: cells inside it whose front-most face is not dropped.
func left_inside(near: Array, drop: Dictionary, poly: PackedVector2Array, front: Dictionary) -> float:
	var left := 0
	for entry in near:
		var tri: Dictionary = entry[0]
		if drop.has(tri.key) and (drop[tri.key] as Array).has(int(tri.index)): continue
		var q: Array = entry[1]
		var lo := Vector2(minf(q[0].x, minf(q[1].x, q[2].x)), minf(q[0].y, minf(q[1].y, q[2].y)))
		var hi := Vector2(maxf(q[0].x, maxf(q[1].x, q[2].x)), maxf(q[0].y, maxf(q[1].y, q[2].y)))
		for cx in range(floori(lo.x/CELL), floori(hi.x/CELL)+1):
			for cy in range(floori(lo.y/CELL), floori(hi.y/CELL)+1):
				var at := Vector2((cx+.5)*CELL, (cy+.5)*CELL)
				if not Geometry2D.is_point_in_polygon(at, poly) or not front.has(Vector2i(cx, cy)): continue
				var w := bary(at, Vector2(q[0].x, q[0].y), Vector2(q[1].x, q[1].y), Vector2(q[2].x, q[2].y))
				if w.x < -1e-4 or w.y < -1e-4 or w.z < -1e-4: continue
				var z: float = q[0].z*w.x+q[1].z*w.y+q[2].z*w.z
				if z >= float(front[Vector2i(cx, cy)][0])-0.002: left += 1
	return left*CELL*CELL

## A clipped polygon of a source triangle as triangles with interpolated attributes, source winding.
static func triangulate(piece: PackedVector2Array, tri: Dictionary, tri2: PackedVector2Array) -> Array:
	var verts := []
	var order := Geometry2D.triangulate_polygon(piece)
	var source_cw := signed_area(tri2) < 0.0
	for k in range(0, order.size(), 3):
		var ids := [order[k], order[k+1], order[k+2]]
		var a := piece[ids[0]]
		var b := piece[ids[1]]
		var c := piece[ids[2]]
		if absf((b.x-a.x)*(c.y-a.y)-(c.x-a.x)*(b.y-a.y)) < 1e-12: continue
		if ((b.x-a.x)*(c.y-a.y)-(c.x-a.x)*(b.y-a.y) < 0.0) != source_cw: ids = [ids[0], ids[2], ids[1]]
		for id in ids:
			var w := bary(piece[id], tri2[0], tri2[1], tri2[2])
			verts.append([(tri.p[0] as Vector3)*w.x+(tri.p[1] as Vector3)*w.y+(tri.p[2] as Vector3)*w.z,
				((tri.n[0] as Vector3)*w.x+(tri.n[1] as Vector3)*w.y+(tri.n[2] as Vector3)*w.z).normalized(),
				(tri.tg[0] as Vector4)*w.x+(tri.tg[1] as Vector4)*w.y+(tri.tg[2] as Vector4)*w.z,
				(tri.uv[0] as Vector2)*w.x+(tri.uv[1] as Vector2)*w.y+(tri.uv[2] as Vector2)*w.z])
	return verts

## The door plan of one render: the user's door outlines (pixels) joined where they touch into one
## opening; leaves: the outlines as drawn when there are two or more, else the opening split down the
## middle when it is a pair's width (DOUBLE_WIDTH, DOUBLE_ASPECT), else one leaf. Hinges: on the outer
## edges of a pair; a single leaf hangs opposite its handle (dark or metal fittings near one side of
## the leaf in the render), or without one on the side nearer the facade's end (the open door rests
## against the wall). Doors open inward. door_hinges.json entries with "override": true win.
## Returns {union: PackedVector2Array (px), leaves: [{poly (px), hinge, reason}], opens} or {}.
func plan_opening(doors: Array, meta: Dictionary, image: Image, ids: Array) -> Dictionary:
	if doors.is_empty(): return {}
	var mpp := float(meta.mpp)
	var union: PackedVector2Array = doors[0]
	for i in range(1, doors.size()):
		var grown := Geometry2D.offset_polygon(doors[i], 3.0)
		var merged := Geometry2D.merge_polygons(union, grown[0] if not grown.is_empty() else doors[i])
		var outer := merged.filter(func(p): return not Geometry2D.is_polygon_clockwise(p) or merged.size() == 1)
		union = largest(outer if not outer.is_empty() else merged)
	var box := bounds(union)
	var leaves := []
	if doors.size() >= 2:
		# Two drawn leaves: each one as drawn, the later one without what the earlier ones already cover.
		var sorted := doors.duplicate()
		sorted.sort_custom(func(a, b): return bounds(a).get_center().x < bounds(b).get_center().x)
		var covered: Array = []
		for i in sorted.size():
			var poly: PackedVector2Array = sorted[i]
			for c in covered:
				var rest := Geometry2D.clip_polygons(poly, c)
				if not rest.is_empty(): poly = largest(rest)
			covered.append(sorted[i])
			leaves.append({"poly": poly, "hinge": "left" if i == 0 else "right", "reason": "double"})
	elif box.size.x*mpp >= DOUBLE_WIDTH or box.size.x >= box.size.y*DOUBLE_ASPECT:
		var mid := box.get_center().x
		for side in ["left", "right"]:
			var half := Rect2(box.position.x-10, box.position.y-10, mid-box.position.x+10, box.size.y+20) if side == "left" else Rect2(mid, box.position.y-10, box.end.x-mid+10, box.size.y+20)
			var parts := Geometry2D.intersect_polygons(union, rect_poly(half))
			if not parts.is_empty(): leaves.append({"poly": largest(parts), "hinge": side, "reason": "double"})
	else:
		var side := handle_side(image, union)
		if not side.is_empty(): leaves.append({"poly": union, "hinge": "left" if side == "right" else "right", "reason": "handle"})
		else: leaves.append({"poly": union, "hinge": wall_side(image, union), "reason": "wall"})
	var plan := {"union": union, "leaves": leaves, "opens": "in"}
	for id in ids:
		var set: Dictionary = overrides.get(id, {})
		if not set.get("override", false): continue
		plan.opens = String(set.get("opens", plan.opens))
		var given: Array = set.get("leaves", [])
		for i in mini(given.size(), leaves.size()):
			leaves[i].hinge = String(given[i].get("hinge", leaves[i].hinge))
			leaves[i].reason = "user"
	return plan

static func largest(polys: Array) -> PackedVector2Array:
	var best := PackedVector2Array()
	for p in polys:
		if absf(signed_area(p)) > absf(signed_area(best)): best = p
	return best

static func bounds(poly: PackedVector2Array) -> Rect2:
	var box := Rect2(poly[0], Vector2.ZERO)
	for p in poly: box = box.expand(p)
	return box

static func rect_poly(r: Rect2) -> PackedVector2Array:
	return PackedVector2Array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)])

## "left" / "right": the side of the leaf whose third holds clearly more handle-like texels (dark iron,
## grey metal or brass) in its middle height; "" when neither does.
static func handle_side(image: Image, poly: PackedVector2Array) -> String:
	if image == null: return ""
	var box := bounds(poly)
	var counts := {"left": 0, "right": 0}
	var step := 2
	for y in range(int(box.position.y+box.size.y*0.3), int(box.position.y+box.size.y*0.75), step):
		for x in range(int(box.position.x), int(box.end.x), step):
			if x < 0 or y < 0 or x >= image.get_width() or y >= image.get_height(): continue
			var at := Vector2(x, y)
			if not Geometry2D.is_point_in_polygon(at, poly): continue
			var t := (x-box.position.x)/maxf(box.size.x, 1.0)
			if t > 0.3 and t < 0.7: continue
			var c := image.get_pixel(x, y)
			var metal := c.v < 0.2 or (c.s < 0.22 and c.v > 0.3 and c.v < 0.7) or (c.h > 0.1 and c.h < 0.17 and c.s > 0.45 and c.v > 0.65)
			if metal: counts["left" if t <= 0.3 else "right"] += 1
	if maxi(counts.left, counts.right) < 12: return ""
	if counts.left >= counts.right*1.6: return "left"
	if counts.right >= counts.left*1.6: return "right"
	return ""

## The side nearer the facade's end at the door's middle height (the render's background beyond it).
static func wall_side(image: Image, poly: PackedVector2Array) -> String:
	if image == null: return "right"
	var box := bounds(poly)
	var y := clampi(int(box.get_center().y), 0, image.get_height()-1)
	var background := image.get_pixel(0, 0)
	var reach := func(dir: int) -> int:
		var x := int(box.get_center().x)
		var n := 0
		while x > 0 and x < image.get_width()-1:
			x += dir
			n += 1
			var c := image.get_pixel(x, y)
			if absf(c.r-background.r)+absf(c.g-background.g)+absf(c.b-background.b) < 0.03 or c.a < 0.1: break
		return n
	return "left" if int(reach.call(-1)) < int(reach.call(1)) else "right"

## Saves an opening's leaves (one resource each), its doorway and the building's cut, and returns its
## door_leaves.json entry. Frame: the wall's (x = u, image right; y up; z = -view_dir, out of the
## wall) at the opening's bottom left on its front-most surface. A leaf's hinge sits on its outer edge
## at the bottom; the leaf reaches from it across the opening, 6 cm deep into the wall; "sign" is the
## rotation that opens it the planned way (+1 swings its far edge out of the wall for a right-hung
## leaf, into it for a left-hung one).
func save_opening(model: String, result: Dictionary, plan: Dictionary, mesh_faces: Dictionary, mpp: float) -> Dictionary:
	var o: Vector3 = result.o
	var u: Vector3 = result.u
	var v: Vector3 = result.v
	var out: Vector3 = -(result.into as Vector3)
	var box: Rect2 = result.box
	var front_z := float(result.front_z)
	var origin: Vector3 = o+u*box.position.x+v*box.end.y+out*front_z
	var frame := Transform3D(Basis(u, -v, out), origin)
	var to_frame := frame.affine_inverse()
	var name := model.get_file().get_basename()
	var leaves := []
	for i in plan.leaves.size():
		var leaf: Dictionary = plan.leaves[i]
		var poly := PackedVector2Array()
		for p in leaf.poly: poly.append(p*mpp)
		var lbox := bounds(poly)
		var hinge_x: float = lbox.end.x if leaf.hinge == "right" else lbox.position.x
		var pivot: Vector3 = to_frame*(o+u*hinge_x+v*lbox.end.y+out*front_z)
		var to_leaf := Transform3D(Basis.IDENTITY, pivot).affine_inverse()*to_frame
		var parts := {}
		for t in result.taken:
			for piece in Geometry2D.intersect_polygons(t[1], poly):
				var verts := triangulate(piece, t[0], t[1])
				if not parts.has(t[0].key): parts[t[0].key] = []
				for k in range(0, verts.size(), 3):
					var front_tri := []
					for j in 3:
						var vtx: Array = verts[k+j]
						var n: Vector3 = (to_leaf.basis*(vtx[1] as Vector3)).normalized()
						var tg4: Vector4 = vtx[2]
						var tg: Vector3 = to_leaf.basis*Vector3(tg4.x, tg4.y, tg4.z)
						front_tri.append([to_leaf*(vtx[0] as Vector3), vtx[3], n, Vector4(tg.x, tg.y, tg.z, tg4.w)])
					parts[t[0].key].append_array(front_tri)
					for j in [0, 2, 1]:
						var f: Array = front_tri[j]
						parts[t[0].key].append([(f[0] as Vector3)-Vector3(0, 0, THICKNESS), f[1], -(f[2] as Vector3), f[3]])
		side_faces(parts, poly, result, to_leaf, o, u, v, out)
		var mesh := ArrayMesh.new()
		for key in parts: commit(mesh, "leaf|"+key, parts[key], mesh_faces.materials.get(key))
		var path: String = Doors.DOORS_DIR+name+("" if i == 0 else str(i+1))+".res"
		ResourceSaver.save(mesh, path)
		var sign := (1.0 if leaf.hinge == "right" else -1.0)*(1.0 if plan.opens == "out" else -1.0)
		leaves.append({"mesh": path, "hinge": leaf.hinge, "reason": leaf.reason, "pivot": [pivot.x, pivot.y, pivot.z], "sign": sign,
			"width": snappedf(lbox.size.x, .001), "height": snappedf(lbox.size.y, .001)})
	# The doorway: a doorway opening out shows the dark surface where the door was; one opening in is
	# a dark recess as deep as the widest leaf, so the leaf can be seen swinging into it.
	var depth := 0.0
	for leaf in leaves: depth = maxf(depth, float(leaf.width))
	var doorway := ArrayMesh.new()
	var tool := SurfaceTool.new()
	tool.begin(Mesh.PRIMITIVE_TRIANGLES)
	var w := box.size.x
	var h := box.size.y
	if plan.opens == "out":
		for piece: Dictionary in result.inside:
			for vtx in piece.verts:
				var p: Vector3 = to_frame*(vtx[0] as Vector3)
				tool.set_normal(Vector3.BACK)
				tool.set_uv(Vector2(p.x/maxf(w, .01), 1.0-p.y/maxf(h, .01)))
				tool.add_vertex(p)
	else:
		var d := depth+0.15
		# Five inner faces of a box behind the opening (seen from outside: back, sides, top, floor).
		var faces := [[Vector3(0, 0, -d), Vector3(w, 0, -d), Vector3(w, h, -d), Vector3(0, h, -d)],
			[Vector3(0, 0, 0), Vector3(0, 0, -d), Vector3(0, h, -d), Vector3(0, h, 0)],
			[Vector3(w, 0, -d), Vector3(w, 0, 0), Vector3(w, h, 0), Vector3(w, h, -d)],
			[Vector3(0, h, -d), Vector3(w, h, -d), Vector3(w, h, 0), Vector3(0, h, 0)],
			[Vector3(0, 0, 0), Vector3(w, 0, 0), Vector3(w, 0, -d), Vector3(0, 0, -d)]]
		for quad in faces:
			var centre: Vector3 = (quad[0]+quad[1]+quad[2]+quad[3])*0.25
			var inward := (Vector3(w*0.5, h*0.5, -d*0.5)-centre).normalized()
			var tris := [[quad[0], quad[1], quad[2]], [quad[0], quad[2], quad[3]]]
			for tri in tris:
				# Front faces wind clockwise seen from their side: facing into the box.
				if ((tri[1]-tri[0]) as Vector3).cross(tri[2]-tri[0]).dot(inward) > 0.0: tri = [tri[0], tri[2], tri[1]]
				for p in tri:
					tool.set_normal(inward)
					tool.set_uv(Vector2(clampf(p.x/maxf(w, .01), 0, 1), clampf(1.0-p.y/maxf(h, .01), 0, 1)))
					tool.add_vertex(p)
	tool.index()
	tool.commit(doorway)
	ResourceSaver.save(doorway, Doors.DOORS_DIR+name+"_opening.res")
	var cut := ArrayMesh.new()
	for key in result.outside:
		var list := []
		for piece: Dictionary in result.outside[key]: list.append_array(piece.verts.map(func(vtx): return [vtx[0], vtx[3], vtx[1], vtx[2]]))
		if list.size() >= 3: commit(cut, "cut|"+key, list, mesh_faces.materials.get(key))
	ResourceSaver.save(cut, Doors.DOORS_DIR+name+"_cut.res")
	var drop := {}
	for key in result.drop: drop[key] = result.drop[key]
	var outline := []
	for p in plan.union: outline.append([p.x, p.y])
	return {"model": model, "leaves": leaves, "opens": plan.opens, "opening": Doors.DOORS_DIR+name+"_opening.res",
		"cut": Doors.DOORS_DIR+name+"_cut.res", "drop": drop, "thickness": THICKNESS,
		"frame": [frame.basis.x.x, frame.basis.x.y, frame.basis.x.z, frame.basis.y.x, frame.basis.y.y, frame.basis.y.z,
			frame.basis.z.x, frame.basis.z.y, frame.basis.z.z, frame.origin.x, frame.origin.y, frame.origin.z],
		"width": snappedf(w, .001), "height": snappedf(h, .001), "depth": snappedf(depth+0.15, .001), "outline_px": outline, "stats": result.stats}

## Side faces round a leaf's outline (image metres), from the door's surface to THICKNESS behind it,
## coloured by the door just inside the edge; added to the surface most of the leaf uses.
func side_faces(parts: Dictionary, poly: PackedVector2Array, result: Dictionary, to_leaf: Transform3D, o: Vector3, u: Vector3, v: Vector3, out: Vector3) -> void:
	var main := ""
	for key in parts: if main.is_empty() or (parts[key] as Array).size() > (parts[main] as Array).size(): main = key
	if main.is_empty(): return
	var centre := centroid(poly)
	var front_z := float(result.front_z)
	for i in poly.size():
		var a := poly[i]
		var b := poly[(i+1) % poly.size()]
		var n2 := Vector2(b.y-a.y, -(b.x-a.x)).normalized()
		if n2.dot((a+b)*0.5-centre) < 0.0: n2 = -n2
		var normal: Vector3 = (to_leaf.basis*(u*n2.x+v*n2.y)).normalized()
		var steps := maxi(1, ceili(a.distance_to(b)/EDGE_STEP))
		for k in steps:
			var q1 := a.lerp(b, float(k)/steps)
			var q2 := a.lerp(b, float(k+1)/steps)
			var s1 := surface_at(result, q1, centre)
			var s2 := surface_at(result, q2, centre)
			var f1: Vector3 = to_leaf*(o+u*q1.x+v*q1.y+out*float(s1.z))
			var f2: Vector3 = to_leaf*(o+u*q2.x+v*q2.y+out*float(s2.z))
			var back := Vector3(0, 0, THICKNESS)
			var quad := [[f1, s1.uv], [f2, s2.uv], [f2-back, s2.uv], [f1, s1.uv], [f2-back, s2.uv], [f1-back, s1.uv]]
			if ((quad[1][0] as Vector3)-(quad[0][0] as Vector3)).cross((quad[2][0] as Vector3)-(quad[0][0] as Vector3)).dot(normal) > 0.0:
				quad = [quad[0], quad[2], quad[1], quad[3], quad[5], quad[4]]
			for q in quad: parts[main].append([q[0], q[1], normal, Vector4(0, 1, 0, 1)])

## The door's surface at a point of the outline (image metres), looked up just inside it: {z, uv}
## (z: depth towards the camera from the render's origin plane).
static func surface_at(result: Dictionary, q: Vector2, centre: Vector2) -> Dictionary:
	var inside := q+(centre-q).normalized()*0.02
	var cell := Vector2i(floori(inside.x/CELL), floori(inside.y/CELL))
	var front: Dictionary = result.front
	if front.has(cell): return {"z": float(front[cell][0]), "uv": front[cell][1]}
	return {"z": float(result.front_z), "uv": Vector2.ZERO}

func append_pieces(mesh: ArrayMesh, pieces: Array, materials: Dictionary) -> void:
	var by_key := {}
	for piece: Dictionary in pieces:
		if not by_key.has(piece.key): by_key[piece.key] = []
		by_key[piece.key].append_array(piece.verts.map(func(vtx): return [vtx[0], vtx[3], vtx[1], vtx[2]]))
	for key in by_key: commit(mesh, "glass|"+key, by_key[key], materials.get(key))

## One surface from [position, uv, normal, tangent] triangles, named, with a copy of the material.
static func commit(mesh: ArrayMesh, name: String, verts: Array, material) -> void:
	var tool := SurfaceTool.new()
	tool.begin(Mesh.PRIMITIVE_TRIANGLES)
	for vtx in verts:
		tool.set_normal((vtx[2] as Vector3).normalized())
		var tg: Vector4 = vtx[3]
		tool.set_tangent(Plane(tg.x, tg.y, tg.z, tg.w))
		tool.set_uv(vtx[1])
		tool.add_vertex(vtx[0])
	tool.index()
	var before := mesh.get_surface_count()
	tool.commit(mesh)
	mesh.surface_set_name(before, name)
	if material is Material: mesh.surface_set_material(before, (material as Material).duplicate())

static func vec(value) -> Vector3: return Vector3(float(value[0]), float(value[1]), float(value[2]))

static func bary(q: Vector2, a: Vector2, b: Vector2, c: Vector2) -> Vector3:
	var v0 := b-a
	var v1 := c-a
	var v2 := q-a
	var d := v0.x*v1.y-v1.x*v0.y
	if absf(d) < 1e-14: return Vector3(-1, -1, -1)
	var v := (v2.x*v1.y-v1.x*v2.y)/d
	var w := (v0.x*v2.y-v2.x*v0.y)/d
	return Vector3(1.0-v-w, v, w)

static func signed_area(poly: PackedVector2Array) -> float:
	var area := 0.0
	for i in poly.size(): area += poly[i].cross(poly[(i+1) % poly.size()])
	return area*0.5

static func area_sum(polys: Array) -> float:
	var total := 0.0
	for p in polys: total += absf(signed_area(p))
	return total

static func centroid(poly: PackedVector2Array) -> Vector2:
	var c := Vector2.ZERO
	for p in poly: c += p/poly.size()
	return c

## A render description and a rectangle outline round the red house's door (from door_leaves.json),
## to try the cutter without real renders.
func write_synthetic() -> void:
	var rect: Dictionary = Doors.table().get("10_red_house", {})
	if rect.is_empty(): return
	var out := vec(rect.out)
	var side := vec(rect.side)
	var origin := vec(rect.origin)
	var mpp := 0.005
	var tl := origin+side*(float(rect.left)-0.6)+Vector3.UP*(float(rect.bottom)+float(rect.height)+0.6)+out*2.0
	var size := Vector2((float(rect.width)+1.2)/mpp, (float(rect.height)+1.2)/mpp)
	var meta := {"model": "res://maps/archipelago/assets/buildings/red_house.glb", "building_ids": ["10_red_house"], "face": "front",
		"width_px": int(size.x), "height_px": int(size.y), "mpp": mpp, "origin_tl": [tl.x, tl.y, tl.z],
		"u": [side.x, side.y, side.z], "v": [0, -1, 0], "view_dir": [-out.x, -out.y, -out.z], "synthetic": true}
	var px := func(x: float, y: float) -> Array: return [roundi((x-(float(rect.left)-0.6))/mpp), roundi(((float(rect.bottom)+float(rect.height)+0.6)-y)/mpp)]
	var l := float(rect.left)
	var b := float(rect.bottom)
	var r := l+float(rect.width)
	var t := b+float(rect.height)
	var outline := {"render_id": "red_house__front", "polys": [{"kind": "door", "hinge": "right", "closed": true,
		"pts": [px.call(l, b), px.call(r, b), px.call(r, t), px.call(l, t)]}], "done": true}
	DirAccess.make_dir_recursive_absolute(renders_dir)
	DirAccess.make_dir_recursive_absolute(outlines_dir)
	var f := FileAccess.open(renders_dir+"red_house__front.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(meta, "\t"))
	f.close()
	f = FileAccess.open(outlines_dir+"red_house__front.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(outline, "\t"))
	f.close()
	print("DOOR_CUT synthetic red_house__front: ", outline.polys[0].pts)
