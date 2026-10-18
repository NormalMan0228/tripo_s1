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
const THICKNESS := 0.05
const CELL := 0.02
## A piece belongs to what the camera sees when it lies this close to the front-most surface there.
const SURFACE_BAND := 0.08
const REMOVE_DEPTH := 2.0
## A pane faces the facade's camera within acos(0.5) = 60 degrees (a sloped roof inside a window's
## outline is not glass).
const PANE_TURN := 0.5
## A door plate follows its wall when the door's faces turn this many degrees or more from the
## render's front (the observatory's door, on its round tower, turns about 27; the others under 7).
const TILT_MIN := 10.0
## A drawn pair's seam counts as slanted from this slope (pixels across per pixel down).
const SEAM_SLANT := 0.05
## Floaters: pieces of the building left loose round a cut doorway (Tripo layers, plates, handles):
## connected parts (vertices welded within 1 mm) lying wholly within FLOAT_MARGIN of the outline, from
## the facade's front back REMOVE_DEPTH, smaller than FLOAT_AREA, are taken out too.
const FLOAT_MARGIN := 0.5
const FLOAT_AREA := 1.5
const EDGE_STEP := 0.03
## Hinge sides and opening directions as decided (or set by the user: "override": true).
const HINGES := "res://maps/archipelago/door_hinges.json"
## A single outline at least this wide (metres), or this wide for its height, is a pair of doors.
const DOUBLE_WIDTH := 1.6
const DOUBLE_ASPECT := 0.9
## The hole's reveal (the cut wall's edge) reaches this far into the wall.
const REVEAL := 0.22
var hinges := {}
var glass := {}
var floating := {}
var overrides := {}
var renders_dir := "res://../artifacts/outline_tool/renders/"
var outlines_dir := "res://../artifacts/outline_tool/outlines/"

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var only := ""
	# The merged outlines (tools/window_panes.py: the user's doors and windows, the auto panes, the
	# see-through holes) when they are there: cutting the user's outlines alone would shrink the glass.
	if DirAccess.dir_exists_absolute(absolute("res://../artifacts/outline_tool/merged/")):
		outlines_dir = "res://../artifacts/outline_tool/merged/"
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
		# Every building on this model gets the door (the render may list only the one it was made for).
		var ids: Array = (meta.get("building_ids", []) as Array).duplicate()
		for spec: Dictionary in placements.buildings:
			if String(spec.model) == model and not ids.has(String(spec.id)): ids.append(String(spec.id))
		var mesh_faces := load_model(model)
		# A model's panes from all its faces go into one glass mesh.
		if not glass.has(model): glass[model] = ArrayMesh.new()
		var windows: ArrayMesh = glass[model]
		var doors := []
		for poly: Dictionary in outline.get("polys", []):
			var pts: Array = poly.get("pts", [])
			if pts.size() < 3: continue
			if String(poly.kind) == "door":
				var px := PackedVector2Array()
				for p in pts: px.append(Vector2(float(p[0]), float(p[1])))
				doors.append(px)
				continue
			if String(poly.kind) == "hole":
				# A see-through hole (tools/window_panes.py): a pane plugs it, flush with the wall round it.
				var plug := hole_plug(mesh_faces, meta, pts)
				if not plug.is_empty():
					var material = null
					for key in mesh_faces.materials:
						var m = mesh_faces.materials[key]
						if m is BaseMaterial3D and (m as BaseMaterial3D).albedo_texture != null:
							material = m
							break
					commit(windows, "hole", plug, material)
					cut += 1
				continue
			var result := cut_outline(mesh_faces, meta, pts, true)
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
			var loose := floaters(mesh_faces, meta, result)
			floating[render_id] = loose
			print("DOOR_CUT ", render_id, " door ", JSON.stringify(result.stats), " leaves=", plan.leaves.map(func(l): return [l.hinge, l.reason]), " opens=", plan.opens, " floaters=", loose.count)
			cut += 1
			var entry := save_opening(model, result, plan, mesh_faces, float(meta.mpp), image)
			entry["render_id"] = render_id
			for id in ids:
				table[id] = entry
				hinges[id] = {"leaves": plan.leaves.map(func(l): return {"hinge": l.hinge, "reason": l.reason}), "opens": plan.opens}
		pass
	for model in glass:
		if (glass[model] as ArrayMesh).get_surface_count() > 0:
			ResourceSaver.save(glass[model], WINDOWS_DIR+String(model).get_file().get_basename()+"_glass.res")
	var file := FileAccess.open(Doors.RECTS, FileAccess.WRITE)
	file.store_string(JSON.stringify(table, "\t", true))
	file.close()
	# The decisions, for the user to flip: an entry with "override": true is kept as it is next time.
	for id in overrides:
		if (overrides[id] as Dictionary).get("override", false): hinges[id] = overrides[id]
	var saved := FileAccess.open(HINGES, FileAccess.WRITE)
	saved.store_string(JSON.stringify(hinges, "\t", true))
	saved.close()
	var log_file := FileAccess.open(absolute("res://../artifacts/mapdoor")+"floaters.json", FileAccess.WRITE)
	if log_file:
		log_file.store_string(JSON.stringify(floating, "\t", true))
		log_file.close()
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
## surface_only (windows): only the pane itself, the camera-facing front surface (within SURFACE_BAND,
## turned at most PANE_TURN off the view) - not the 2 m behind a door's outline (a dormer's roof, the
## window's reveal sides would glow with the glass).
func cut_outline(model: Dictionary, meta: Dictionary, pts: Array, surface_only := false) -> Dictionary:
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
	# The model's triangles facing this render's camera, projected, once per render (many outlines).
	if not meta.has("_facing"):
		var facing := []
		for tri: Dictionary in model.tris:
			var outward: Vector3 = -((tri.p[1] as Vector3)-(tri.p[0] as Vector3)).cross((tri.p[2] as Vector3)-(tri.p[0] as Vector3))
			# Facing the camera: the outward normal (Godot winds front faces clockwise) points to +z.
			# The others are kept too: relief sides inside a door outline go with it.
			var faces_camera := outward.dot(-into) > 0.0
			var a: Vector3 = project.call(tri.p[0])
			var b: Vector3 = project.call(tri.p[1])
			var c: Vector3 = project.call(tri.p[2])
			# Edge-on faces (a doorway's floor, the lintel's underside) project to lines: kept, marked flat.
			var flat := absf((b.x-a.x)*(c.y-a.y)-(c.x-a.x)*(b.y-a.y)) < 1e-6
			facing.append([tri, [a, b, c], faces_camera and not flat, Rect2(Vector2(minf(a.x, minf(b.x, c.x)), minf(a.y, minf(b.y, c.y))), Vector2.ZERO).expand(Vector2(maxf(a.x, maxf(b.x, c.x)), maxf(a.y, maxf(b.y, c.y)))), flat])
		meta["_facing"] = facing
	var near := []
	for entry in meta._facing:
		var r: Rect2 = entry[3]
		if r.end.x < box.position.x or r.position.x > box.end.x or r.end.y < box.position.y or r.position.y > box.end.y: continue
		near.append([entry[0], entry[1], entry[2], entry[4] if entry.size() > 4 else false])
	# The front-most depth seen in each cell of the outline's box.
	var front := {}
	for entry in near:
		if not entry[2]: continue
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
	# Everything the outline holds goes (the user's rule): every camera-facing face inside it down to
	# REMOVE_DEPTH behind its front-most surface (Tripo doors are painted on more than one layer; the
	# building's far walls lie much deeper and stay).
	var top := -INF
	for cell in front:
		if Geometry2D.is_point_in_polygon((Vector2(cell)+Vector2(.5, .5))*CELL, poly): top = maxf(top, float(front[cell][0]))
	var grown_polys := Geometry2D.offset_polygon(poly, 0.03)
	var grown: PackedVector2Array = grown_polys[0] if not grown_polys.is_empty() else poly
	var stats := {"triangles_near": near.size(), "taken_whole": 0, "split": 0, "outline_m2": 0.0, "cut_m2": 0.0, "left_m2": 0.0}
	stats.outline_m2 = absf(signed_area(poly))
	for entry in near:
		var tri: Dictionary = entry[0]
		var q: Array = entry[1]
		var tri2 := PackedVector2Array([Vector2(q[0].x, q[0].y), Vector2(q[1].x, q[1].y), Vector2(q[2].x, q[2].y)])
		if surface_only:
			if not entry[2] or entry[3] or absf(signed_area(tri2)) < 1e-6: continue
			var normal: Vector3 = -((tri.p[1] as Vector3)-(tri.p[0] as Vector3)).cross((tri.p[2] as Vector3)-(tri.p[0] as Vector3))
			if normal.normalized().dot(-into) < PANE_TURN: continue
		elif entry[3] or absf(signed_area(tri2)) < 1e-6:
			# Edge-on: inside the doorway (its middle within the outline grown 3 cm, from the door's
			# front back to REMOVE_DEPTH) it goes whole; elsewhere it stays.
			var mid := (Vector2(q[0].x, q[0].y)+Vector2(q[1].x, q[1].y)+Vector2(q[2].x, q[2].y))/3.0
			var depth := (float(q[0].z)+float(q[1].z)+float(q[2].z))/3.0
			if Geometry2D.is_point_in_polygon(mid, grown) and depth <= top+0.02 and depth >= top-REMOVE_DEPTH:
				if not drop.has(tri.key): drop[tri.key] = []
				drop[tri.key].append(int(tri.index))
				stats["edge_on"] = int(stats.get("edge_on", 0))+1
			continue
		var pieces_in := Geometry2D.intersect_polygons(tri2, poly)
		if pieces_in.is_empty(): continue
		# Only the surface the camera sees: a hidden face behind the door stays where it is.
		var visible := false
		for piece in pieces_in:
			var c := centroid(piece)
			var w := bary(c, tri2[0], tri2[1], tri2[2])
			var z: float = q[0].z*w.x+q[1].z*w.y+q[2].z*w.z
			var cell := Vector2i(floori(c.x/CELL), floori(c.y/CELL))
			if entry[2] and (not front.has(cell) or z >= float(front[cell][0])-SURFACE_BAND): visible = true
			elif not surface_only and z >= top-REMOVE_DEPTH and z <= top+0.02: visible = true
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
		taken.append([tri, tri2, entry[2]])
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
	# A pair whose meeting seam runs on a slant in the facade (the observatory): split along the seam
	# found in the render (the dark line between the leaves), and widen the side the user could not
	# draw whole (behind a column) to the other leaf's width; hinges on the outer edges.
	var seam := find_seam(doors) if doors.size() >= 2 else {}
	if not seam.is_empty():
		union = widen_pair(union, seam)
		box = bounds(union)
		var line_a := float(seam.a)
		var line_b := float(seam.b)
		var far := 10000.0
		var left_side := PackedVector2Array([Vector2(line_a*-far+line_b, -far), Vector2(line_a*far+line_b, far), Vector2(-far, far), Vector2(-far, -far)])
		var right_side := PackedVector2Array([Vector2(line_a*-far+line_b, -far), Vector2(far, -far), Vector2(far, far), Vector2(line_a*far+line_b, far)])
		for side in ["left", "right"]:
			var parts := Geometry2D.intersect_polygons(union, left_side if side == "left" else right_side)
			if not parts.is_empty(): leaves.append({"poly": largest(parts), "hinge": side, "reason": "double"})
	elif doors.size() >= 2:
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

## The seam of a drawn pair (pixels: x = a*y + b) when it runs on a slant (|a| >= SEAM_SLANT): per row,
## the middle between the left leaf's right edge and the right leaf's left edge (the user's two outlines
## meet or overlap there), a line fitted through them. {} for a seam that stands upright.
static func find_seam(doors: Array) -> Dictionary:
	var sorted := doors.duplicate()
	sorted.sort_custom(func(p, q): return bounds(p).get_center().x < bounds(q).get_center().x)
	var left: PackedVector2Array = sorted[0]
	var right: PackedVector2Array = sorted[sorted.size()-1]
	var box := bounds(left).merge(bounds(right))
	var xs := []
	var ys := []
	for k in range(1, 20):
		var y := box.position.y+box.size.y*k/20.0
		var l := row_extent(left, y)
		var r := row_extent(right, y)
		if l.x > l.y or r.x > r.y: continue
		xs.append((l.y+r.x)*0.5)
		ys.append(y)
	if xs.size() < 6: return {}
	var fit := line_fit(xs, ys)
	if absf(float(fit.a)) < SEAM_SLANT: return {}
	return fit

## Where a horizontal line at y crosses a polygon: Vector2(leftmost, rightmost) (x > y when it misses).
static func row_extent(poly: PackedVector2Array, y: float) -> Vector2:
	var lo := INF
	var hi := -INF
	for i in poly.size():
		var a := poly[i]
		var b := poly[(i+1) % poly.size()]
		if (a.y-y)*(b.y-y) > 0.0 or is_equal_approx(a.y, b.y): continue
		var x := a.x+(b.x-a.x)*(y-a.y)/(b.y-a.y)
		lo = minf(lo, x)
		hi = maxf(hi, x)
	return Vector2(lo, hi)

static func line_fit(xs: Array, ys: Array) -> Dictionary:
	var n := float(xs.size())
	var sy := 0.0
	var sx := 0.0
	var syy := 0.0
	var sxy := 0.0
	for i in xs.size():
		sy += float(ys[i])
		sx += float(xs[i])
		syy += float(ys[i])*float(ys[i])
		sxy += float(xs[i])*float(ys[i])
	var d := n*syy-sy*sy
	if absf(d) < 1e-9: return {"a": 0.0, "b": sx/maxf(n, 1.0)}
	var a := (n*sxy-sx*sy)/d
	return {"a": a, "b": (sx-a*sy)/n}

## A pair's outline widened on the narrower side to the other leaf's width (measured across from the
## seam at mid height), the extra a strip as tall as the outline: the leaf behind a column is cut whole.
static func widen_pair(union: PackedVector2Array, seam: Dictionary) -> PackedVector2Array:
	var box := bounds(union)
	var y := box.get_center().y
	var mid := float(seam.a)*y+float(seam.b)
	var left := mid-box.position.x
	var right := box.end.x-mid
	if absf(left-right) < 0.08*maxf(left, right): return union
	var strip := Rect2(box.end.x-2.0, box.position.y, left-right+2.0, box.size.y) if right < left else Rect2(mid-right-(right-left), box.position.y, right-left+2.0, box.size.y)
	var merged := Geometry2D.merge_polygons(union, rect_poly(strip))
	var outer := merged.filter(func(q): return not Geometry2D.is_polygon_clockwise(q) or merged.size() == 1)
	return largest(outer if not outer.is_empty() else merged)

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
func save_opening(model: String, result: Dictionary, plan: Dictionary, mesh_faces: Dictionary, mpp: float, image: Image = null) -> Dictionary:
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
	# A doorway in a turned wall (TILT_MIN or more, the observatory): one plane for all its leaves, the
	# doorway's own faces' turn through the median of its front surface round the outline.
	var union_m := PackedVector2Array()
	for p in plan.union: union_m.append(p*mpp)
	var shared := door_plane(result.taken, union_m, to_frame)
	var plane_n := 0.0
	if not shared.is_empty() and absf(rad_to_deg(float(shared.tilt))) >= TILT_MIN:
		var along := []
		var union_centre := centroid(union_m)
		for q in union_m: along.append((to_frame*(o+u*q.x+v*q.y+out*float(surface_at(result, q, union_centre).z))).dot(shared.normal))
		along.sort()
		plane_n = float(along[along.size()/2])
	else:
		shared = {}
	for i in plan.leaves.size():
		var leaf: Dictionary = plan.leaves[i]
		var poly := PackedVector2Array()
		for p in leaf.poly: poly.append(p*mpp)
		var lbox := bounds(poly)
		var hinge_x: float = lbox.end.x if leaf.hinge == "right" else lbox.position.x
		var pivot: Vector3 = to_frame*(o+u*hinge_x+v*lbox.end.y+out*front_z)
		var to_leaf := Transform3D(Basis.IDENTITY, pivot).affine_inverse()*to_frame
		# A door set in a wall at an angle to the render's front (TILT_MIN or more, measured from the
		# door's own faces) gets its plate along that wall: built in a space turned by `tilt` about the
		# hinge's vertical (its plane z = 0 there), then turned back into the frame.
		var plane := door_plane(result.taken, poly, to_frame)
		var tilt := 0.0
		var outline_point := func(q: Vector2) -> Vector3: return to_frame*(o+u*q.x+v*q.y+out*front_z)
		var dir: Vector3 = (to_frame.basis*(result.into as Vector3)).normalized()
		# Frame point -> onto the leaf's plane along the render's view (no change while the leaf is flat).
		var project := func(at: Vector3) -> Vector3: return at
		if not shared.is_empty():
			tilt = float(shared.tilt)
			var nf: Vector3 = shared.normal
			# Through the doorway's front surface (the faces' middle lies deeper, the layers behind the
			# door counted in).
			var cf: Vector3 = nf*plane_n
			project = func(at: Vector3) -> Vector3: return at+dir*(nf.dot(cf-at)/nf.dot(dir))
			outline_point = func(q: Vector2) -> Vector3:
				var at: Vector3 = to_frame*(o+u*q.x+v*q.y+out*front_z)
				return at+dir*(nf.dot(cf-at)/nf.dot(dir))
			pivot = outline_point.call(Vector2(hinge_x, lbox.end.y))
			to_leaf = Transform3D(Basis(Vector3.UP, tilt), pivot).affine_inverse()*to_frame
		# A new leaf, a plate in the outline's shape (the user's rule): its front is the facade's own
		# door, the cut pieces laid flat (their layering kept a hair apart, no relief), textured as the
		# building; back and edges in the door's colour; a handle on both faces at the free edge.
		var parts := {}
		var to_plate := Transform3D(Basis(Vector3.UP, tilt), pivot).affine_inverse()
		for t in result.taken:
			if not t[2]: continue
			for piece in Geometry2D.intersect_polygons(t[1], poly):
				var verts := triangulate(piece, t[0], t[1])
				if not parts.has(t[0].key): parts[t[0].key] = []
				for vtx in verts:
					# Projected onto the plate along the view (a turned plate keeps the facade's picture),
					# its depth off the plate squeezed.
					var at: Vector3 = to_frame*(vtx[0] as Vector3)
					var on: Vector3 = project.call(at)
					var p: Vector3 = to_plate*on
					p.z = clampf((p.z+(at-on).dot(-dir))*0.03, -0.008, 0.004)
					parts[t[0].key].append([p, vtx[3], Vector3.BACK, Vector4(1, 0, 0, 1)])
		var leaf_poly := PackedVector2Array()
		for q in poly:
			var at: Vector3 = to_plate*(outline_point.call(q) as Vector3)
			leaf_poly.append(Vector2(at.x, at.y))
		if signed_area(leaf_poly) < 0.0: leaf_poly.reverse()
		var colour := region_colour(image, leaf.poly, false)
		var paint := StandardMaterial3D.new()
		paint.albedo_color = colour
		paint.roughness = 0.8
		var plate := []
		var order := Geometry2D.triangulate_polygon(leaf_poly)
		var back := Vector3(0, 0, -THICKNESS)
		for k in range(0, order.size(), 3):
			var a := leaf_poly[order[k]]
			var b := leaf_poly[order[k+1]]
			var c := leaf_poly[order[k+2]]
			var tri := [Vector3(a.x, a.y, 0)+back, Vector3(b.x, b.y, 0)+back, Vector3(c.x, c.y, 0)+back]
			# Seen from behind (-z): front faces wind clockwise from that side.
			if ((tri[1]-tri[0]) as Vector3).cross(tri[2]-tri[0]).z < 0.0: tri = [tri[0], tri[2], tri[1]]
			for p in tri: plate.append([p, Vector2.ZERO, Vector3.FORWARD, Vector4(1, 0, 0, 1)])
		var centre2 := centroid(leaf_poly)
		for k in leaf_poly.size():
			var a := leaf_poly[k]
			var b := leaf_poly[(k+1) % leaf_poly.size()]
			var n2 := Vector2(b.y-a.y, -(b.x-a.x)).normalized()
			if n2.dot((a+b)*0.5-centre2) < 0.0: n2 = -n2
			var normal := Vector3(n2.x, n2.y, 0)
			var quad := [Vector3(a.x, a.y, 0), Vector3(b.x, b.y, 0), Vector3(b.x, b.y, 0)+back, Vector3(a.x, a.y, 0), Vector3(b.x, b.y, 0)+back, Vector3(a.x, a.y, 0)+back]
			if ((quad[1]-quad[0]) as Vector3).cross(quad[2]-quad[0]).dot(normal) > 0.0: quad = [quad[0], quad[2], quad[1], quad[3], quad[5], quad[4]]
			for p in quad: plate.append([p, Vector2.ZERO, normal, Vector4(1, 0, 0, 1)])
		parts["paint"] = plate
		var plate_box := bounds(leaf_poly)
		var lh := plate_box.size.y
		var handle_x: float = (plate_box.position.x+0.1) if leaf.hinge == "right" else (plate_box.end.x-0.1)
		parts["metal"] = handle(Vector3(handle_x, plate_box.position.y+minf(1.0, lh*0.45), 0.0), THICKNESS)
		if tilt != 0.0:
			# Back into the frame's directions (the hinge node stays unturned while closed).
			var turn := Basis(Vector3.UP, tilt)
			for key in parts:
				var list: Array = parts[key]
				for k in list.size():
					var vtx: Array = list[k]
					list[k] = [turn*(vtx[0] as Vector3), vtx[1], (turn*(vtx[2] as Vector3)).normalized(), vtx[3]]
		var mesh := ArrayMesh.new()
		var iron := StandardMaterial3D.new()
		iron.albedo_color = Color(0.2, 0.18, 0.16)
		iron.metallic = 0.6
		iron.roughness = 0.4
		for key in parts:
			var material = paint if key == "paint" else iron if key == "metal" else mesh_faces.materials.get(key)
			commit(mesh, "leaf|"+key, parts[key], material)
		var path: String = Doors.DOORS_DIR+name+("" if i == 0 else str(i+1))+".res"
		ResourceSaver.save(mesh, path)
		var sign := (1.0 if leaf.hinge == "right" else -1.0)*(1.0 if plan.opens == "out" else -1.0)
		leaves.append({"mesh": path, "hinge": leaf.hinge, "reason": leaf.reason, "pivot": [pivot.x, pivot.y, pivot.z], "sign": sign, "tilt_degrees": snappedf(rad_to_deg(tilt), 0.1),
			"wall_degrees": snappedf(rad_to_deg(float(plane.tilt)), 0.1) if not plane.is_empty() else 0.0,
			"width": snappedf(lbox.size.x, .001), "height": snappedf(lbox.size.y, .001)})
	# The hole's edge: a reveal from the wall's surface REVEAL metres in, in the wall's colour, so the
	# cut never shows the hollow building (the dark doorway lies behind it).
	var wall := StandardMaterial3D.new()
	wall.albedo_color = region_colour(image, plan.union, true)
	wall.roughness = 0.9
	var ring := PackedVector2Array()
	for q in plan.union: ring.append(q*mpp)
	var ring_centre := centroid(ring)
	# The reveal runs from the door's surface round the hole straight into the wall (its turn: the
	# leaves' mean tilt) back to `inner`, REVEAL behind the front-most point of that surface along the
	# wall's normal, a centimetre inside the outline. The dark doorway behind it is the outline itself
	# pushed back into the wall (not a box round it): nothing of it shows outside the hole, on a slanted
	# wall (the observatory) or over an arch's corners (16).
	var turned := 0.0
	for leaf in leaves: turned += deg_to_rad(float(leaf.tilt_degrees))/leaves.size()
	var wall_basis := Basis(Vector3.UP, turned)
	var normal: Vector3 = wall_basis.z
	var depths := []
	var across := Vector2(INF, -INF)
	var shape := PackedVector2Array()
	for q in ring:
		var at: Vector3 = to_frame*(o+u*q.x+v*q.y+out*float(surface_at(result, q, ring_centre).z))
		depths.append(at.dot(normal))
		across = Vector2(minf(across.x, at.dot(wall_basis.x)), maxf(across.y, at.dot(wall_basis.x)))
		shape.append(Vector2(at.dot(wall_basis.x), at.y))
	depths.sort()
	var front_n: float = float(depths.back()) if not depths.is_empty() else 0.0
	var inner := front_n-REVEAL
	# A turned wall (the observatory): the outline laid on the leaves' plane along the render's view and
	# pushed along the wall's normal, for the reveal and the tube alike, so they meet the leaves' edges
	# and each other (the surface's own points zig-zag across: gaps, the sky through the doorway).
	var view: Vector3 = (to_frame.basis*(result.into as Vector3)).normalized()
	# The frame depth (z) of the leaves' plane over a frame point (a turned wall only).
	var plane_z := func(at: Vector3) -> float: return (plane_n-normal.x*at.x-normal.y*at.y)/normal.z
	var on_plane := func(q: Vector2) -> Vector3:
		var at: Vector3 = to_frame*(o+u*q.x+v*q.y+out*front_z)
		return at+view*((plane_n-at.dot(normal))/view.dot(normal))
	if turned != 0.0:
		shape = PackedVector2Array()
		across = Vector2(INF, -INF)
		# A centimetre in, like the reveal, so the two meet edge to edge.
		var shrunk := Geometry2D.offset_polygon(ring, -0.01)
		for q in (shrunk[0] if not shrunk.is_empty() else ring):
			var at: Vector3 = on_plane.call(q)
			shape.append(Vector2(at.dot(wall_basis.x), at.y))
			across = Vector2(minf(across.x, at.dot(wall_basis.x)), maxf(across.y, at.dot(wall_basis.x)))
	var reveal := []
	for k in ring.size():
		var a := ring[k]
		var b := ring[(k+1) % ring.size()]
		var steps := maxi(1, ceili(a.distance_to(b)/0.1))
		var n2 := Vector2(b.y-a.y, -(b.x-a.x)).normalized()
		if n2.dot(ring_centre-(a+b)*0.5) < 0.0: n2 = -n2
		var inward: Vector3 = (to_frame.basis*(u*n2.x+v*n2.y)).normalized()
		for j in steps:
			var q1 := a.lerp(b, float(j)/steps)
			var q2 := a.lerp(b, float(j+1)/steps)
			var i1 := q1+n2*0.01
			var i2 := q2+n2*0.01
			var f1: Vector3 = to_frame*(o+u*i1.x+v*i1.y+out*float(surface_at(result, q1, ring_centre).z))
			var f2: Vector3 = to_frame*(o+u*i2.x+v*i2.y+out*float(surface_at(result, q2, ring_centre).z))
			var d1 := f1+normal*(inner-f1.dot(normal))
			var d2 := f2+normal*(inner-f2.dot(normal))
			if turned != 0.0:
				# Straight back along the render's view, the cut's own prism (pushed along the wall's normal
				# it left gaps to the grass and kept the building's faces inside the tube): from the wall's
				# surface or the leaves' plane, whichever is further out, to REVEAL behind the plane.
				var p1: float = plane_z.call(f1)
				var p2: float = plane_z.call(f2)
				d1 = Vector3(f1.x, f1.y, p1-REVEAL)
				d2 = Vector3(f2.x, f2.y, p2-REVEAL)
				f1 = Vector3(f1.x, f1.y, maxf(f1.z, p1))
				f2 = Vector3(f2.x, f2.y, maxf(f2.z, p2))
			var quad := [f1, f2, d2, f1, d2, d1]
			# Facing into the hole (seen from the doorway): clockwise from the inward side.
			if ((quad[1]-quad[0]) as Vector3).cross(quad[2]-quad[0]).dot(inward) > 0.0: quad = [quad[0], quad[2], quad[1], quad[3], quad[5], quad[4]]
			for p in quad: reveal.append([p, Vector2.ZERO, inward, Vector4(1, 0, 0, 1)])
	var reveal_mesh := ArrayMesh.new()
	if not reveal.is_empty(): commit(reveal_mesh, "reveal", reveal, wall)
	ResourceSaver.save(reveal_mesh, Doors.DOORS_DIR+name+"_reveal.res")
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
		var x0 := across.x
		var x1 := across.y
		# On a turned wall the dark tube starts behind the reveal, so between a leaf's edge and the wall
		# the reveal shows, not the tube.
		var z0 := front_n if turned == 0.0 else inner
		var z1 := front_n-(REVEAL+depth+0.15)
		# The outline pushed back from the front-most surface (z0) to z1, in the wall's directions: its
		# sides and its back, facing in, then turned into the frame.
		var tris := []
		var middle := centroid(shape)
		for k in shape.size():
			var a := shape[k]
			var b := shape[(k+1) % shape.size()]
			var n2 := Vector2(b.y-a.y, -(b.x-a.x)).normalized()
			if n2.dot(middle-(a+b)*0.5) < 0.0: n2 = -n2
			var inward := Vector3(n2.x, n2.y, 0)
			tris.append([[Vector3(a.x, a.y, z0), Vector3(b.x, b.y, z0), Vector3(b.x, b.y, z1)], inward])
			tris.append([[Vector3(a.x, a.y, z0), Vector3(b.x, b.y, z1), Vector3(a.x, a.y, z1)], inward])
		var order := Geometry2D.triangulate_polygon(shape)
		for k in range(0, order.size(), 3):
			tris.append([[Vector3(shape[order[k]].x, shape[order[k]].y, z1), Vector3(shape[order[k+1]].x, shape[order[k+1]].y, z1),
				Vector3(shape[order[k+2]].x, shape[order[k+2]].y, z1)], Vector3.BACK])
		var turn := wall_basis
		if turned != 0.0:
			# A turned wall: the tube runs straight back along the render's view too (the cut's prism, in
			# frame directions), from REVEAL behind the leaves' plane, a centimetre inside the outline.
			turn = Basis.IDENTITY
			tris = []
			var flat := PackedVector2Array()
			var fronts := []
			var shrunk := Geometry2D.offset_polygon(ring, -0.01)
			for q in (shrunk[0] if not shrunk.is_empty() else ring):
				var at: Vector3 = to_frame*(o+u*q.x+v*q.y+out*front_z)
				flat.append(Vector2(at.x, at.y))
				fronts.append(float(plane_z.call(at))-REVEAL)
			x0 = INF
			x1 = -INF
			for q in flat:
				x0 = minf(x0, q.x)
				x1 = maxf(x1, q.x)
			var reach := depth+0.15
			var centre_flat := centroid(flat)
			for k in flat.size():
				var a := flat[k]
				var b := flat[(k+1) % flat.size()]
				var za: float = fronts[k]
				var zb: float = fronts[(k+1) % flat.size()]
				var n2 := Vector2(b.y-a.y, -(b.x-a.x)).normalized()
				if n2.dot(centre_flat-(a+b)*0.5) < 0.0: n2 = -n2
				var inward := Vector3(n2.x, n2.y, 0)
				tris.append([[Vector3(a.x, a.y, za), Vector3(b.x, b.y, zb), Vector3(b.x, b.y, zb-reach)], inward])
				tris.append([[Vector3(a.x, a.y, za), Vector3(b.x, b.y, zb-reach), Vector3(a.x, a.y, za-reach)], inward])
			var cap := Geometry2D.triangulate_polygon(flat)
			for k in range(0, cap.size(), 3):
				var corners := []
				for c in [cap[k], cap[k+1], cap[k+2]]: corners.append(Vector3(flat[c].x, flat[c].y, float(fronts[c])-reach))
				tris.append([corners, normal])
		for entry in tris:
			var tri: Array = entry[0]
			var inward: Vector3 = entry[1]
			# Front faces wind clockwise seen from their side: facing into the doorway.
			if ((tri[1]-tri[0]) as Vector3).cross(tri[2]-tri[0]).dot(inward) > 0.0: tri = [tri[0], tri[2], tri[1]]
			for p in tri:
				tool.set_normal(turn*inward)
				tool.set_uv(Vector2(clampf((p.x-x0)/maxf(x1-x0, .01), 0, 1), clampf(1.0-p.y/maxf(h, .01), 0, 1)))
				tool.add_vertex(turn*p)
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
	return {"model": model, "leaves": leaves, "opens": plan.opens, "opening": Doors.DOORS_DIR+name+"_opening.res", "reveal": Doors.DOORS_DIR+name+"_reveal.res",
		"cut": Doors.DOORS_DIR+name+"_cut.res", "drop": drop, "thickness": THICKNESS,
		"frame": [frame.basis.x.x, frame.basis.x.y, frame.basis.x.z, frame.basis.y.x, frame.basis.y.y, frame.basis.y.z,
			frame.basis.z.x, frame.basis.z.y, frame.basis.z.z, frame.origin.x, frame.origin.y, frame.origin.z],
		"width": snappedf(w, .001), "height": snappedf(h, .001), "depth": snappedf(REVEAL+depth+0.15, .001), "reveal_depth": snappedf(-inner, .001), "outline_px": outline, "stats": result.stats}

## Loose parts round a cut doorway (see FLOAT_MARGIN): added to the cut's dropped triangles. Returns
## {count, area_m2, parts: [{triangles, area_m2, centre (model space), size}]}.
func floaters(model: Dictionary, meta: Dictionary, result: Dictionary) -> Dictionary:
	var o: Vector3 = result.o
	var u: Vector3 = result.u
	var v: Vector3 = result.v
	var into: Vector3 = result.into
	var top := float(result.front_z)
	var grown := Geometry2D.offset_polygon(result.poly, FLOAT_MARGIN)
	var region: PackedVector2Array = grown[0] if not grown.is_empty() else result.poly
	var drop: Dictionary = result.drop
	var dropped := {}
	for key in drop:
		for index in drop[key]: dropped["%s#%d" % [key, index]] = true
	# Union-find over the building's remaining triangles, joined where they share a welded vertex.
	var parent: Array = []
	var tris: Array = model.tris
	parent.resize(tris.size())
	for i in tris.size(): parent[i] = i
	var welded := {}
	var alive := PackedByteArray()
	alive.resize(tris.size())
	for i in tris.size():
		var tri: Dictionary = tris[i]
		if dropped.has("%s#%d" % [tri.key, int(tri.index)]): continue
		alive[i] = 1
		for p: Vector3 in tri.p:
			var cell := Vector3i(roundi(p.x*1000.0), roundi(p.y*1000.0), roundi(p.z*1000.0))
			if welded.has(cell):
				var a := root_of(parent, i)
				var b := root_of(parent, int(welded[cell]))
				if a != b: parent[a] = b
			else: welded[cell] = i
	# Each part: wholly in the region (in the outline's margin, from the facade's front back)?
	var parts := {}
	for i in tris.size():
		if alive[i] == 0: continue
		var root := root_of(parent, i)
		if not parts.has(root): parts[root] = {"inside": true, "area": 0.0, "members": [], "box": AABB()}
		var part: Dictionary = parts[root]
		if not part.inside: continue
		var tri: Dictionary = tris[i]
		var c: Vector3 = ((tri.p[0] as Vector3)+(tri.p[1] as Vector3)+(tri.p[2] as Vector3))/3.0
		var img := Vector2((c-o).dot(u), (c-o).dot(v))
		var depth := -(c-o).dot(into)
		if not Geometry2D.is_point_in_polygon(img, region) or depth > top+0.02 or depth < top-REMOVE_DEPTH:
			part.inside = false
			part.members = []
			continue
		part.area += 0.5*((tri.p[1] as Vector3)-(tri.p[0] as Vector3)).cross((tri.p[2] as Vector3)-(tri.p[0] as Vector3)).length()
		part.box = AABB(c, Vector3.ZERO) if part.members.is_empty() else (part.box as AABB).expand(c)
		part.members.append(i)
	var report := {"count": 0, "area_m2": 0.0, "parts": []}
	for root in parts:
		var part: Dictionary = parts[root]
		if not part.inside or part.members.is_empty() or float(part.area) >= FLOAT_AREA: continue
		for i in part.members:
			var tri: Dictionary = tris[i]
			if not drop.has(tri.key): drop[tri.key] = []
			drop[tri.key].append(int(tri.index))
		var box: AABB = part.box
		report.count += 1
		report.area_m2 = snappedf(float(report.area_m2)+float(part.area), 0.0001)
		report.parts.append({"triangles": part.members.size(), "area_m2": snappedf(float(part.area), 0.0001),
			"centre": [snappedf(box.get_center().x, .01), snappedf(box.get_center().y, .01), snappedf(box.get_center().z, .01)],
			"size": [snappedf(box.size.x, .01), snappedf(box.size.y, .01), snappedf(box.size.z, .01)]})
	return report

## A pane over a see-through hole: the hole's outline (pixels) laid on the wall's surface round it (the
## middle depth of the faces in a band just outside the hole, 1 cm behind), facing out, one texel of
## the wall's texture. [] when there is no wall round it.
func hole_plug(model: Dictionary, meta: Dictionary, pts: Array) -> Array:
	var poly := PackedVector2Array()
	for p in pts: poly.append(Vector2(float(p[0]), float(p[1])))
	var grown := Geometry2D.offset_polygon(poly, 14.0)
	if grown.is_empty(): return []
	var ring_pts := []
	for p in grown[0]: ring_pts.append([p.x, p.y])
	var probe := cut_outline_front(model, meta, ring_pts)
	var mpp := float(meta.mpp)
	var depths := []
	var uvs := []
	for cell: Vector2i in probe:
		var at := (Vector2(cell)+Vector2(0.5, 0.5))*CELL/mpp
		if Geometry2D.is_point_in_polygon(at, poly): continue
		depths.append(float(probe[cell][0]))
		uvs.append(probe[cell][1])
	if depths.size() < 4: return []
	depths.sort()
	var depth: float = depths[depths.size()/2]-0.01
	var uv: Vector2 = uvs[uvs.size()/2]
	var o := vec(meta.origin_tl)
	var u := vec(meta.u)
	var v := vec(meta.v)
	var out := -vec(meta.view_dir).normalized()
	var points := PackedVector3Array()
	for p in poly: points.append(o+u*p.x*mpp+v*p.y*mpp+out*depth)
	var order := Geometry2D.triangulate_polygon(poly)
	var verts := []
	for k in range(0, order.size(), 3):
		var tri := [points[order[k]], points[order[k+1]], points[order[k+2]]]
		# Front faces wind clockwise as the viewer outside sees them: the cross points away (-out).
		if ((tri[1]-tri[0]) as Vector3).cross(tri[2]-tri[0]).dot(out) > 0.0: tri = [tri[0], tri[2], tri[1]]
		for q in tri: verts.append([q, uv, out, Vector4(1, 0, 0, 1)])
	return verts

## The front-most depth and texcoord per cell over an outline's box (cut_outline's grid, nothing cut).
func cut_outline_front(model: Dictionary, meta: Dictionary, pts: Array) -> Dictionary:
	return cut_outline(model, meta, pts).front

## Union-find root with path halving (parent: an Array, changed in place).
static func root_of(parent: Array, i: int) -> int:
	while int(parent[i]) != i:
		parent[i] = parent[int(parent[i])]
		i = int(parent[i])
	return i

## The plane the door's own faces lie in (camera-facing taken faces inside the leaf outline), in frame
## space: {normal (level), point (area-weighted middle), tilt (radians about +y from the frame's +z)}.
static func door_plane(taken: Array, poly: PackedVector2Array, to_frame: Transform3D) -> Dictionary:
	var normal := Vector3.ZERO
	var middle := Vector3.ZERO
	var total := 0.0
	for t in taken:
		if not t[2]: continue
		for piece in Geometry2D.intersect_polygons(t[1], poly):
			var area := absf(signed_area(piece))
			if area <= 0.0: continue
			var tri: Dictionary = t[0]
			var outward: Vector3 = -((tri.p[1] as Vector3)-(tri.p[0] as Vector3)).cross((tri.p[2] as Vector3)-(tri.p[0] as Vector3))
			if outward.length() < 1e-9: continue
			normal += (to_frame.basis*outward.normalized())*area
			middle += (to_frame*(((tri.p[0] as Vector3)+(tri.p[1] as Vector3)+(tri.p[2] as Vector3))/3.0))*area
			total += area
	normal.y = 0.0
	if total <= 0.0 or normal.length() < 1e-6: return {}
	normal = normal.normalized()
	return {"normal": normal, "point": middle/total, "tilt": atan2(normal.x, normal.z)}

## A small iron handle (rose and lever) on both faces of a leaf THICKNESS deep, at `at` on the front.
static func handle(at: Vector3, thickness: float) -> Array:
	var tool := SurfaceTool.new()
	tool.begin(Mesh.PRIMITIVE_TRIANGLES)
	for side in [1.0, -1.0]:
		var z := at.z+0.012 if side > 0.0 else at.z-thickness-0.012
		var rose := BoxMesh.new()
		rose.size = Vector3(0.05, 0.12, 0.012)
		tool.append_from(rose, 0, Transform3D(Basis.IDENTITY, Vector3(at.x, at.y, z)))
		var stem := BoxMesh.new()
		stem.size = Vector3(0.02, 0.02, 0.045)
		tool.append_from(stem, 0, Transform3D(Basis.IDENTITY, Vector3(at.x, at.y+0.03, z+side*0.022)))
		var lever := BoxMesh.new()
		lever.size = Vector3(0.11, 0.022, 0.022)
		var reach := -0.045 if at.x < 0.0 else 0.045
		tool.append_from(lever, 0, Transform3D(Basis.IDENTITY, Vector3(at.x-reach, at.y+0.03, z+side*0.045)))
	var arrays := tool.commit_to_arrays()
	var out := []
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var index = arrays[Mesh.ARRAY_INDEX]
	if index is PackedInt32Array and not index.is_empty():
		for i in index: out.append([vertices[i], Vector2.ZERO, normals[i], Vector4(1, 0, 0, 1)])
	else:
		for i in vertices.size(): out.append([vertices[i], Vector2.ZERO, normals[i], Vector4(1, 0, 0, 1)])
	return out

## The mean colour of the render inside an outline (pixels), or of a band just outside it (`ring`:
## the wall round the door), the render's background left out.
static func region_colour(image: Image, pts, ring: bool) -> Color:
	if image == null: return Color(0.45, 0.3, 0.2) if not ring else Color(0.85, 0.8, 0.7)
	var poly := PackedVector2Array()
	for p in pts: poly.append(Vector2(p.x, p.y) if p is Vector2 else Vector2(float(p[0]), float(p[1])))
	var outer := poly
	if ring:
		var grown := Geometry2D.offset_polygon(poly, 22.0)
		if not grown.is_empty(): outer = grown[0]
	var box := Rect2(outer[0], Vector2.ZERO)
	for p in outer: box = box.expand(p)
	var background := image.get_pixel(0, 0)
	var sum := Color(0, 0, 0, 0)
	var n := 0
	for y in range(int(box.position.y), int(box.end.y), 3):
		for x in range(int(box.position.x), int(box.end.x), 3):
			if x < 0 or y < 0 or x >= image.get_width() or y >= image.get_height(): continue
			var at := Vector2(x, y)
			var inside := Geometry2D.is_point_in_polygon(at, poly)
			if ring == inside or (ring and not Geometry2D.is_point_in_polygon(at, outer)): continue
			var c := image.get_pixel(x, y)
			if absf(c.r-background.r)+absf(c.g-background.g)+absf(c.b-background.b) < 0.03: continue
			sum += c
			n += 1
	if n == 0: return Color(0.45, 0.3, 0.2) if not ring else Color(0.85, 0.8, 0.7)
	return Color(sum.r/n, sum.g/n, sum.b/n)

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
