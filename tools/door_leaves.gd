extends SceneTree
## Door leaves for the village buildings (game/maps/archipelago/building_doors.gd) and their rooms
## (interiors.gd front()). The front doors are painted into the baked Tripo building GLBs: this finds
## each Town.DOORS door on its building's wall, copies the building faces inside the door's outline
## (clipped to it; texcoords, normals, tangents kept) and makes them a solid leaf THICKNESS deep, so
## the door swings open with the very look it has closed, the same door outside and in. Headless:
##   .tools/godot/Godot_v4.7.2-stable_win64_console.exe --headless --path game --script res://../tools/door_leaves.gd
## Writes per building model game/maps/archipelago/doors/<model>.res (the leaf, an ArrayMesh with the
## building's materials) and <model>_opening.res (the dark doorway), and door_leaves.json (per door id:
## model, resources, the wall frame and the outline in building space). Run it again when a building
## GLB, its placement or a door in Town.DOORS changes (about 10 s for all fourteen). --sheet=PATH also
## saves a contact sheet of every wall as sampled with the outline found.
const Town = preload("res://scripts/town.gd")
const Doors = preload("res://maps/archipelago/building_doors.gd")
const PLACEMENTS := "res://maps/archipelago/building_placements.json"
## The wall around the door point is sampled on a grid of CELL metres: SPAN either side, up to TALL.
const CELL := 0.04
const SPAN := 1.6
const TALL := 3.4
## The leaf is the door's own faces made solid: this thick, into the wall.
const THICKNESS := 0.06
## Side faces: a sample every EDGE_STEP metres along the outline, coloured by the door just inside it.
const EDGE_STEP := 0.04

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var sheet_path := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--sheet="): sheet_path = arg.trim_prefix("--sheet=")
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(PLACEMENTS))
	var specs := {}
	for spec: Dictionary in manifest.buildings: specs[String(spec.id)] = spec
	var tiles: Array[Image] = []
	var rects := {}
	var started := Time.get_ticks_msec()
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(Doors.DOORS_DIR))
	for door: Dictionary in Town.DOORS:
		var spec: Dictionary = specs[String(door.id)]
		var wall := sample_wall(door, spec)
		# Town.DOORS gives the door point and the building centre, not the wall's direction: sample
		# again square to the wall the door is on (its faces' mean normal).
		if not wall.is_empty():
			var facing := wall_normal(wall)
			if facing != Vector3.ZERO and facing.angle_to(wall.out) > deg_to_rad(2.0): wall = sample_wall(door, spec, facing)
		if wall.is_empty():
			print("DOOR_LEAF ", door.id, " no wall found")
			continue
		var shape := find_shape(String(door.id), wall)
		if shape.size() < 3:
			print("DOOR_LEAF ", door.id, " no door paint found: a plain doorway")
			shape = rect_shape(Rect2(-0.5, 0.0, 1.0, 2.1))
		var box := bounds(shape)
		var front := front_depth(wall.cells, shape)
		tiles.append(wall_image(wall, shape))
		# One door resource per building model (buildings sharing a model share the door).
		var out := ArrayMesh.new()
		var doorway := ArrayMesh.new()
		var made := build_door(wall, shape, front, out, doorway)
		var resource: String = Doors.DOORS_DIR+String(spec.model).get_file().get_basename()+".res"
		ResourceSaver.save(out, resource)
		ResourceSaver.save(doorway, resource.trim_suffix(".res")+"_opening.res")
		if "--debug" in OS.get_cmdline_user_args():
			var inside := 0
			var zs := []
			for face: Dictionary in wall.faces:
				var c: Vector3 = (face.p[0]+face.p[1]+face.p[2])/3.0
				if box.has_point(Vector2(c.x, c.y)):
					inside += 1
					if zs.size() < 6: zs.append(snappedf(c.z-front, .01))
			print("  debug faces_in_box=", inside, " of ", wall.faces.size(), " front=", front, " z-front=", zs)
		var outline := []
		for p in shape: outline.append([snappedf(p.x-box.position.x, .001), snappedf(p.y-box.position.y, .001)])
		rects[String(door.id)] = {"model": String(spec.model), "mesh": resource, "opening": resource.trim_suffix(".res")+"_opening.res", "hinge": "right",
			"origin": vec(wall.origin), "out": vec(wall.out), "side": vec(wall.side),
			"left": snappedf(box.position.x, .001), "bottom": snappedf(box.position.y, .001), "width": snappedf(box.size.x, .001),
			"height": snappedf(box.size.y, .001), "front": snappedf(front, .001), "outline": outline, "triangles": made,
			"thickness": THICKNESS}
		print("DOOR_LEAF ", door.id, " box=", box, " points=", shape.size(), " triangles=", made)
	if not sheet_path.is_empty(): save_sheet(tiles, sheet_path)
	var file := FileAccess.open(Doors.RECTS, FileAccess.WRITE)
	file.store_string(JSON.stringify(rects, "\t", true))
	file.close()
	print("DOOR_LEAVES doors=", rects.size(), " ms=", Time.get_ticks_msec()-started)
	quit(0)

static func vec(v: Vector3) -> Array: return [snappedf(v.x, .0001), snappedf(v.y, .0001), snappedf(v.z, .0001)]

## The building's meshes with their transforms in building space: [[MeshInstance3D, Transform3D, path]].
static func building_meshes(root: Node3D) -> Array:
	var found := []
	for item in root.find_children("*", "MeshInstance3D", true, false):
		var mesh := item as MeshInstance3D
		var t := Transform3D()
		var node: Node = mesh
		while node != root and node != null:
			t = (node as Node3D).transform*t
			node = node.get_parent()
		found.append([mesh, t, String(root.get_path_to(mesh))])
	return found

## The building's wall at the door, in building space: a grid over the plane facing out of the door
## (side = across, up = height above the pad), each cell the front-most outward face there:
## {origin, out, side, cells: {Vector2i: [depth, uv, colour, surface key]}, faces: [...], ...}.
func sample_wall(door: Dictionary, spec: Dictionary, facing := Vector3.ZERO) -> Dictionary:
	var scene: PackedScene = load(String(spec.model))
	var root := scene.instantiate() as Node3D
	var place := Transform3D(Basis(Vector3.UP, deg_to_rad(float(spec.yaw_degrees))).scaled(Vector3.ONE*float(spec.scale)), Vector3(spec.position[0], spec.position[1], spec.position[2]))
	var to_local := place.affine_inverse()
	var at: Vector2 = door.at
	var out2: Vector2 = (at-Vector2(door.center)).normalized()
	var origin := to_local*Vector3(at.x, float(spec.position[1]), at.y)
	var out := (to_local.basis*Vector3(out2.x, 0, out2.y)).normalized() if facing == Vector3.ZERO else facing
	var side := Vector3.UP.cross(out).normalized()
	var faces := []
	var images := {}
	var materials := {}
	for entry in building_meshes(root):
		var mesh: MeshInstance3D = entry[0]
		var t: Transform3D = entry[1]
		for s in mesh.mesh.get_surface_count():
			var material := mesh.get_active_material(s) as BaseMaterial3D
			if material == null or material.albedo_texture == null: continue
			var arrays := mesh.mesh.surface_get_arrays(s)
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var uvs = arrays[Mesh.ARRAY_TEX_UV]
			var index = arrays[Mesh.ARRAY_INDEX]
			if not (uvs is PackedVector2Array) or not (index is PackedInt32Array): continue
			var key := "%s|%d" % [entry[2], s]
			materials[key] = material
			var normals = arrays[Mesh.ARRAY_NORMAL]
			var tangents = arrays[Mesh.ARRAY_TANGENT]
			var to_building := t.basis
			var path := material.albedo_texture.resource_path
			if not images.has(path): images[path] = Image.load_from_file(ProjectSettings.globalize_path(path))
			# Building-space positions projected on the wall frame: (across, height, out of the wall).
			var projected := PackedVector3Array()
			projected.resize(vertices.size())
			for i in vertices.size():
				var rel := t*vertices[i]-origin
				projected[i] = Vector3(rel.dot(side), rel.y, rel.dot(out))
			for i in range(0, index.size(), 3):
				var a := projected[index[i]]
				var b := projected[index[i+1]]
				var c := projected[index[i+2]]
				if maxf(a.x, maxf(b.x, c.x)) < -SPAN or minf(a.x, minf(b.x, c.x)) > SPAN: continue
				if maxf(a.y, maxf(b.y, c.y)) < -0.3 or minf(a.y, minf(b.y, c.y)) > TALL: continue
				if maxf(a.z, maxf(b.z, c.z)) < -3.5 or minf(a.z, minf(b.z, c.z)) > 1.5: continue
				# Facing out of the door (the projected z axis); (x, y) winding tells it apart from inner faces.
				var normal := (b-a).cross(c-a)
				if normal.length() < 1e-9 or absf(normal.normalized().z) < 0.45: continue
				var face := {"p": [a, b, c], "uv": [uvs[index[i]], uvs[index[i+1]], uvs[index[i+2]]], "key": key, "image": path, "n": [], "tg": []}
				for k in 3:
					var v: int = index[i+k]
					var n: Vector3 = (to_building*normals[v]).normalized() if normals is PackedVector3Array else Vector3.BACK
					face.n.append(Vector3(n.dot(side), n.y, n.dot(out)))
					if tangents is PackedFloat32Array and tangents.size() >= (v+1)*4:
						var tg: Vector3 = to_building*Vector3(tangents[v*4], tangents[v*4+1], tangents[v*4+2])
						face.tg.append(Vector4(tg.dot(side), tg.y, tg.dot(out), tangents[v*4+3]))
					else: face.tg.append(Vector4(1, 0, 0, 1))
				faces.append(face)
	root.free()
	if faces.is_empty(): return {}
	var cells := {}
	for f in faces.size():
		var face: Dictionary = faces[f]
		var p: Array = face.p
		var lo := Vector2(minf(p[0].x, minf(p[1].x, p[2].x)), minf(p[0].y, minf(p[1].y, p[2].y)))
		var hi := Vector2(maxf(p[0].x, maxf(p[1].x, p[2].x)), maxf(p[0].y, maxf(p[1].y, p[2].y)))
		for cx in range(int(floor(maxf(lo.x, -SPAN)/CELL)), int(ceil(minf(hi.x, SPAN)/CELL))+1):
			for cy in range(int(floor(maxf(lo.y, -0.2)/CELL)), int(ceil(minf(hi.y, TALL)/CELL))+1):
				var q := Vector2((cx+.5)*CELL, (cy+.5)*CELL)
				var w := bary(q, Vector2(p[0].x, p[0].y), Vector2(p[1].x, p[1].y), Vector2(p[2].x, p[2].y))
				if w.x < -1e-4 or w.y < -1e-4 or w.z < -1e-4: continue
				var depth: float = p[0].z*w.x+p[1].z*w.y+p[2].z*w.z
				var cell := Vector2i(cx, cy)
				if cells.has(cell) and float(cells[cell][0]) >= depth: continue
				var uv: Vector2 = face.uv[0]*w.x+face.uv[1]*w.y+face.uv[2]*w.z
				cells[cell] = [depth, uv, Color(), f]
	for cell in cells:
		var face: Dictionary = faces[int(cells[cell][3])]
		var image: Image = images[face.image]
		var uv: Vector2 = cells[cell][1]
		uv = Vector2(fposmod(uv.x, 1.0), fposmod(uv.y, 1.0))
		cells[cell][2] = image.get_pixel(clampi(int(uv.x*image.get_width()), 0, image.get_width()-1), clampi(int(uv.y*image.get_height()), 0, image.get_height()-1))
	return {"origin": origin, "out": out, "side": side, "cells": cells, "faces": faces, "materials": materials}

## The wall's outward direction at the door (building space, level): the mean normal of the front-most
## faces over the door's middle (across +-0.6 m, 0.5..2 m up).
static func wall_normal(wall: Dictionary) -> Vector3:
	var sum := Vector3.ZERO
	for cell: Vector2i in wall.cells:
		if absf(cell.x*CELL) > 0.6 or cell.y*CELL < 0.5 or cell.y*CELL > 2.0: continue
		var p: Array = wall.faces[int(wall.cells[cell][3])].p
		var n: Vector3 = ((p[1] as Vector3)-(p[0] as Vector3)).cross((p[2] as Vector3)-(p[0] as Vector3)).normalized()
		if n.z < 0.0: n = -n
		sum += (wall.side as Vector3)*n.x+Vector3.UP*n.y+(wall.out as Vector3)*n.z
	sum.y = 0.0
	return sum.normalized() if sum.length() > 0.001 else Vector3.ZERO

static func bary(q: Vector2, a: Vector2, b: Vector2, c: Vector2) -> Vector3:
	var v0 := b-a
	var v1 := c-a
	var v2 := q-a
	var d := v0.x*v1.y-v1.x*v0.y
	if absf(d) < 1e-12: return Vector3(-1, -1, -1)
	var v := (v2.x*v1.y-v1.x*v2.y)/d
	var w := (v0.x*v2.y-v2.x*v0.y)/d
	return Vector3(1.0-v-w, v, w)

## Wood-brown door paint (the village's doors are all wooden): hue, saturation and value bounds.
static func is_door_paint(c: Color) -> bool:
	return c.h > 0.025 and c.h < 0.14 and c.s > 0.38 and c.v > 0.1 and c.v < 0.8

## The door's outline on the wall (across, height; convex, counter-clockwise): the convex hull of the
## door-paint cells connected to the one nearest the door point at door height (the panes inside a
## door are enclosed by the hull). An override rectangle (building_doors.gd) wins.
func find_shape(id: String, wall: Dictionary) -> PackedVector2Array:
	if Doors.RECT_OVERRIDES.has(id): return override_shape(Doors.RECT_OVERRIDES[id])
	var cells: Dictionary = wall.cells
	var seed := Vector2i(999, 999)
	var mid := int(1.0/CELL)
	for cell: Vector2i in cells:
		if cell.y*CELL < 0.5 or cell.y*CELL > 1.6 or absf(cell.x*CELL) > 1.2: continue
		if not is_door_paint(cells[cell][2]): continue
		if absi(cell.x)+absi(cell.y-mid) < absi(seed.x)+absi(seed.y-mid): seed = cell
	if seed.x == 999: return PackedVector2Array()
	# Row by row from the seed: the run of door paint (gaps up to GAP cells: panes, handles) over the
	# run of the row before. Going down the run may not widen (doors have upright sides); going up it
	# may not widen either and stops where the arch closes.
	var runs := {}
	# The widest row near the seed sets the door's width (a row across a pane or a ring is narrower).
	var first := Vector2i(1, 0)
	var first_y := seed.y
	for y in range(seed.y-6, seed.y+7):
		var run := run_at(cells, y, seed.x, seed.x)
		if run.y-run.x > first.y-first.x:
			first = run
			first_y = y
	if first.x > first.y: return PackedVector2Array()
	seed.y = first_y
	runs[seed.y] = first
	for dir in [-1, 1]:
		var prev: Vector2i = first
		var y: int = seed.y+dir
		var missed := 0
		while y*CELL > -0.2 and y*CELL < 3.2:
			var run := run_at(cells, y, prev.x, prev.y)
			run = Vector2i(maxi(run.x, first.x-1), mini(run.y, first.y+1))
			if run.x > run.y or (dir > 0 and run.y-run.x+1 < 4):
				# A row of iron straps or a pane's frame: look a few rows further before ending.
				missed += 1
				if missed > 5: break
				y += dir
				continue
			missed = 0
			runs[y] = run
			prev = run
			y += dir
	var points := PackedVector2Array()
	for y: int in runs:
		var run: Vector2i = runs[y]
		points.append_array([Vector2(run.x, y)*CELL, Vector2(run.y+1, y)*CELL, Vector2(run.x, y+1)*CELL, Vector2(run.y+1, y+1)*CELL])
	var hull := Geometry2D.convex_hull(points)
	if hull.size() > 1 and hull[0] == hull[hull.size()-1]: hull.resize(hull.size()-1)
	return ccw(hull)

const GAP := 10
## The run of door paint in row y that overlaps columns lo..hi (gaps up to GAP cells bridged);
## Vector2i(1, 0) (empty) when that row has no paint there.
static func bridgeable(c: Color) -> bool:
	# Panes (bluish), iron fittings and shadows (dark); not stone frames or walls.
	return c.v < 0.36 or (c.b > c.r+0.05 and c.v < 0.85)

static func run_at(cells: Dictionary, y: int, lo: int, hi: int) -> Vector2i:
	var start := 999
	for x in range(lo, hi+1):
		if cells.has(Vector2i(x, y)) and is_door_paint(cells[Vector2i(x, y)][2]):
			start = x
			break
	if start == 999: return Vector2i(1, 0)
	var left := start
	var gap := 0
	var x := start-1
	while gap <= GAP and x > -int(SPAN/CELL):
		if not cells.has(Vector2i(x, y)): break
		var c: Color = cells[Vector2i(x, y)][2]
		if is_door_paint(c):
			left = x
			gap = 0
		elif bridgeable(c): gap += 1
		else: break
		x -= 1
	var right := start
	gap = 0
	x = start+1
	while gap <= GAP and x < int(SPAN/CELL):
		if not cells.has(Vector2i(x, y)): break
		var c: Color = cells[Vector2i(x, y)][2]
		if is_door_paint(c):
			right = x
			gap = 0
		elif bridgeable(c): gap += 1
		else: break
		x += 1
	return Vector2i(left, right)

## [left, bottom, width, height, arch rise]: a rectangle whose top `rise` metres are a half ellipse.
static func override_shape(values: Array) -> PackedVector2Array:
	var rect := Rect2(values[0], values[1], values[2], values[3])
	var rise: float = values[4]
	if rise <= 0.0: return rect_shape(rect)
	var shape := PackedVector2Array([rect.position, Vector2(rect.end.x, rect.position.y)])
	var centre := Vector2(rect.get_center().x, rect.end.y-rise)
	for k in 9:
		var a := PI*k/8.0
		shape.append(centre+Vector2(cos(a)*rect.size.x*.5, sin(a)*rise))
	return shape

static func rect_shape(rect: Rect2) -> PackedVector2Array:
	return PackedVector2Array([rect.position, Vector2(rect.end.x, rect.position.y), rect.end, Vector2(rect.position.x, rect.end.y)])

static func ccw(poly: PackedVector2Array) -> PackedVector2Array:
	var area := 0.0
	for i in poly.size(): area += poly[i].cross(poly[(i+1) % poly.size()])
	if area < 0.0: poly.reverse()
	return poly

static func bounds(poly: PackedVector2Array) -> Rect2:
	var box := Rect2(poly[0], Vector2.ZERO)
	for p in poly: box = box.expand(p)
	return box

## The door's own depth on the wall: the cells inside its outline (frames and arches stand in front of
## a recessed door; the opening lies just in front of the door, not of them).
static func front_depth(cells: Dictionary, shape: PackedVector2Array) -> float:
	var shrunk := Geometry2D.offset_polygon(shape, -0.06)
	var outline: PackedVector2Array = shrunk[0] if not shrunk.is_empty() else shape
	var depths := []
	for cell: Vector2i in cells:
		if Geometry2D.is_point_in_polygon((Vector2(cell)+Vector2(.5, .5))*CELL, outline): depths.append(float(cells[cell][0]))
	if depths.is_empty(): return 0.0
	depths.sort()
	if "--debug" in OS.get_cmdline_user_args():
		print("  depth min=%.3f p10=%.3f med=%.3f p90=%.3f max=%.3f" % [depths[0], depths[depths.size()/10], depths[depths.size()/2], depths[depths.size()*9/10], depths[-1]])
	# Doors bulge and lean a little: the opening goes in front of all of it, handles and knockers
	# included when they stand out less than 8 cm (deeper outliers are frames the outline caught).
	var most: float = depths[mini(depths.size()-1, depths.size()*97/100)]
	return minf(depths[-1], most+0.08)

## Makes the door's meshes into `out` (the door resource of the building's model) and returns the
## leaf's triangle count. Positions are in the door frame relative to the hinge corner: the outline's
## right-hand edge seen from outside, its bottom, z 0 on the opening plane (the door's front-most
## depth); x across (the leaf reaches along -x from the hinge), y up, z out of the wall.
##  "leaf|<surface>"  the building's own door faces inside the outline (clipped; texcoords, normals and
##                    tangents kept), made solid THICKNESS deep into the wall: the same faces again
##                    behind, turned round (the back of the door, seen from the room), and side faces
##                    round the outline coloured by the door just inside its edge. Exterior and
##                    interior doors are this one mesh (interiors.gd front()).
##  "opening"         the same front faces alone, for the dark doorway (UV: across 0..1 from the far
##                    edge, 0 at the top .. 1 at the bottom).
func build_door(wall: Dictionary, shape: PackedVector2Array, front: float, out: ArrayMesh, doorway: ArrayMesh) -> int:
	var box := bounds(shape)
	var corner := Vector3(box.end.x, box.position.y, front)
	var made := commit_parts(solid(wall, shape, corner), out, "leaf|", wall.materials)
	var opening := SurfaceTool.new()
	opening.begin(Mesh.PRIMITIVE_TRIANGLES)
	var any := false
	for face: Dictionary in door_faces(wall, shape, front):
		for tri in fan(face.poly):
			for v in tri:
				var p: Vector3 = (v[0] as Vector3)-corner
				opening.set_normal(Vector3.BACK)
				opening.set_uv(Vector2((p.x+box.size.x)/maxf(box.size.x, .01), 1.0-p.y/maxf(box.size.y, .01)))
				opening.add_vertex(p)
				any = true
	if any:
		opening.index()
		opening.commit(doorway)
		doorway.surface_set_name(0, "opening")
	return made

## The building's outward faces inside the outline near the door's depth, clipped to it:
## [{key, poly: [[position, uv, normal, tangent], ...]}].
func door_faces(wall: Dictionary, shape: PackedVector2Array, front: float) -> Array:
	var found := []
	for face: Dictionary in wall.faces:
		var p: Array = face.p
		var depth := ((p[0] as Vector3).z+(p[1] as Vector3).z+(p[2] as Vector3).z)/3.0
		if depth < front-0.45 or depth > front+0.12: continue
		# Godot's front faces wind clockwise: outward faces (towards +z) have a cross product towards -z.
		if ((p[1] as Vector3)-(p[0] as Vector3)).cross((p[2] as Vector3)-(p[0] as Vector3)).normalized().z > -0.2: continue
		var poly := []
		for k in 3: poly.append([p[k], face.uv[k], face.n[k], face.tg[k]])
		for i in shape.size():
			poly = clip(poly, shape[i], shape[(i+1) % shape.size()])
			if poly.size() < 3: break
		if poly.size() >= 3: found.append({"key": face.key, "poly": poly})
	return found

static func fan(poly: Array) -> Array:
	var tris := []
	for k in range(1, poly.size()-1): tris.append([poly[0], poly[k], poly[k+1]])
	return tris

## The solid leaf for an outline: {surface key: [vertices as [position, uv, normal, tangent]]}, front
## and back faces per building surface, the side faces with the surface most of the door is drawn with.
func solid(wall: Dictionary, shape: PackedVector2Array, corner: Vector3) -> Dictionary:
	var parts := {}
	var count := {}
	for face: Dictionary in door_faces(wall, shape, corner.z):
		if not parts.has(face.key): parts[face.key] = []
		count[face.key] = int(count.get(face.key, 0))+1
		for tri in fan(face.poly):
			var vs := []
			for v in tri: vs.append([(v[0] as Vector3)-corner, v[1], v[2], v[3]])
			parts[face.key].append_array(vs)
			# Behind: the same face THICKNESS deeper, turned round.
			for k in [0, 2, 1]:
				var v: Array = vs[k]
				parts[face.key].append([(v[0] as Vector3)-Vector3(0, 0, THICKNESS), v[1], -(v[2] as Vector3), v[3]])
	if parts.is_empty(): return parts
	var main: String = count.keys()[0]
	for key in count: if int(count[key]) > int(count[main]): main = key
	# Sides: round the outline, from the door's surface to THICKNESS behind it.
	var centre := Vector2.ZERO
	for p in shape: centre += p/shape.size()
	for i in shape.size():
		var a := shape[i]
		var b := shape[(i+1) % shape.size()]
		var normal := Vector3(b.y-a.y, -(b.x-a.x), 0).normalized()
		var steps := maxi(1, ceili(a.distance_to(b)/EDGE_STEP))
		for k in steps:
			var q1 := a.lerp(b, float(k)/steps)
			var q2 := a.lerp(b, float(k+1)/steps)
			var s1 := edge_sample(wall.cells, q1, centre)
			var s2 := edge_sample(wall.cells, q2, centre)
			var f1 := Vector3(q1.x, q1.y, s1.z)-corner
			var f2 := Vector3(q2.x, q2.y, s2.z)-corner
			var b1 := f1-Vector3(0, 0, THICKNESS)
			var b2 := f2-Vector3(0, 0, THICKNESS)
			var quad := [[f1, s1.uv], [f2, s2.uv], [b2, s2.uv], [f1, s1.uv], [b2, s2.uv], [b1, s1.uv]]
			if ((quad[1][0] as Vector3)-(quad[0][0] as Vector3)).cross((quad[2][0] as Vector3)-(quad[0][0] as Vector3)).dot(normal) > 0.0:
				quad = [quad[0], quad[2], quad[1], quad[3], quad[5], quad[4]]
			for v in quad: parts[main].append([v[0], v[1], normal, Vector4(0, 1, 0, 1)])
	return parts

## The door's surface at an outline point, looked up just inside it: {z: depth, uv}.
static func edge_sample(cells: Dictionary, q: Vector2, centre: Vector2) -> Dictionary:
	var inside := q+(centre-q).normalized()*0.03
	var cell := Vector2i(floori(inside.x/CELL), floori(inside.y/CELL))
	if cells.has(cell): return {"z": float(cells[cell][0]), "uv": cells[cell][1]}
	for step in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		if cells.has(cell+step): return {"z": float(cells[cell+step][0]), "uv": cells[cell+step][1]}
	return {"z": 0.0, "uv": Vector2.ZERO}

## Writes parts ({key: vertices}) as surfaces named prefix+key, each with a copy of the building
## surface's material (textures referenced). Returns the triangle count.
func commit_parts(parts: Dictionary, out: ArrayMesh, prefix: String, materials: Dictionary) -> int:
	var made := 0
	for key in parts:
		var list: Array = parts[key]
		if list.size() < 3: continue
		var tool := SurfaceTool.new()
		tool.begin(Mesh.PRIMITIVE_TRIANGLES)
		for v in list:
			tool.set_normal((v[2] as Vector3).normalized())
			var tg: Vector4 = v[3]
			tool.set_tangent(Plane(tg.x, tg.y, tg.z, tg.w))
			tool.set_uv(v[1])
			tool.add_vertex(v[0])
		tool.index()
		var before := out.get_surface_count()
		tool.commit(out)
		out.surface_set_name(before, prefix+key)
		var source := materials.get(key) as BaseMaterial3D
		if source: out.surface_set_material(before, source.duplicate())
		made += list.size()/3
	return made

## Sutherland-Hodgman against one edge (a2 -> b2) of a counter-clockwise convex outline: keeps the
## left. Vertices are [position, uv, normal, tangent]; everything is interpolated.
static func clip(poly: Array, a2: Vector2, b2: Vector2) -> Array:
	var result := []
	var edge := b2-a2
	for i in poly.size():
		var a: Array = poly[i]
		var b: Array = poly[(i+1) % poly.size()]
		var pa := Vector2((a[0] as Vector3).x, (a[0] as Vector3).y)
		var pb := Vector2((b[0] as Vector3).x, (b[0] as Vector3).y)
		var da := edge.cross(pa-a2)
		var db := edge.cross(pb-a2)
		if da >= 0: result.append(a)
		if (da >= 0) != (db >= 0):
			var t := da/(da-db)
			result.append([(a[0] as Vector3).lerp(b[0], t), (a[1] as Vector2).lerp(b[1], t), (a[2] as Vector3).lerp(b[2], t), (a[3] as Vector4).lerp(b[3], t)])
	return result

func wall_image(wall: Dictionary, shape: PackedVector2Array) -> Image:
	var w := int(SPAN*2/CELL)
	var h := int((TALL+.2)/CELL)
	var image := Image.create(w, h, false, Image.FORMAT_RGB8)
	image.fill(Color(1, 0, 1))
	for cell: Vector2i in wall.cells:
		var x := cell.x+int(SPAN/CELL)
		var y := h-1-(cell.y+int(.2/CELL))
		if x >= 0 and x < w and y >= 0 and y < h: image.set_pixel(x, y, wall.cells[cell][2])
	image.resize(w*3, h*3, Image.INTERPOLATE_NEAREST)
	# A metre grid: a line every 0.1 m (dark), every 0.5 m (white); x = 0 at the door point.
	for k in range(-16, 35):
		var strong := k % 5 == 0
		var line := Color(1, 1, 1) if strong else Color(0.15, 0.15, 0.15)
		var px := int((k*0.1+SPAN)/CELL*3)
		if k >= -16 and k <= 16 and px >= 0 and px < w*3:
			for py in range(0, h*3, 1 if strong else 3): image.set_pixel(px, py, line)
		var py := h*3-1-int((k*0.1+.2)/CELL*3)
		if k >= -2 and py >= 0 and py < h*3:
			for qx in range(0, w*3, 1 if strong else 3): image.set_pixel(qx, py, line)
	# The outline in green.
	for i in shape.size():
		var a := shape[i]
		var b := shape[(i+1) % shape.size()]
		for k in 80:
			var q := a.lerp(b, k/80.0)
			var px := int((q.x+SPAN)/CELL*3)
			var py := h*3-1-int((q.y+.2)/CELL*3)
			if px >= 0 and px < w*3 and py >= 0 and py < h*3: image.set_pixel(px, py, Color(0, 1, 0))
	return image

static func save_sheet(tiles: Array[Image], path: String) -> void:
	if tiles.is_empty(): return
	var tw := tiles[0].get_width()
	var th := tiles[0].get_height()
	var columns := 4
	var sheet := Image.create(tw*columns, th*int(ceil(tiles.size()/float(columns))), false, Image.FORMAT_RGB8)
	for i in tiles.size():
		sheet.blit_rect(tiles[i], Rect2i(0, 0, tw, th), Vector2i((i % columns)*tw, (i/columns)*th))
	sheet.save_png(path)
