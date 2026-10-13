extends RefCounted
## Shape-fitted collision for crafted objects (instead of one box around everything).
##
## The model's triangles are dropped into a coarse grid (GRID cells along the longest side),
## the closed inside is filled, and the filled cells are merged into a few boxes. A table
## becomes a top and four legs, so walkers pass under it and between chair legs, and a low
## bench is something to step onto. Boxes are the cheapest static shapes for the physics
## server, and the build is plain arithmetic over at most a few thousand Tripo faces.
##
## Boxes are kept in the model's made shape ("base"); object_transform.gd scales them with
## the player's shape edit (width, depth, height, size, mirror) without rebuilding.
const GRID := 10
## Coarser grids are tried when a ragged model would need more boxes than this.
const MAX_BOXES := 24
const FALLBACK_GRIDS := [7, 5]

## Root-local boxes (AABB) fitted to the model's own surfaces, [] when it has none.
static func boxes_for(root: Node3D) -> Array:
	var parts := surfaces(root)
	if parts.is_empty(): return []
	var bounds := AABB()
	var first := true
	for part in parts:
		for p in part[0]:
			bounds = AABB(p, Vector3.ZERO) if first else bounds.expand(p)
			first = false
	if bounds.get_longest_axis_size() < 0.001: return []
	for grid in [GRID] + FALLBACK_GRIDS:
		var boxes := voxel_boxes(parts, bounds, grid)
		if boxes.size() <= MAX_BOXES: return boxes
	return [bounds]

## The model's triangle surfaces in root-local space: [vertices, indices] each, indices in
## threes. Where model_loader tagged the crafted surfaces ("craft_surface") only those count,
## so markers do not; studio assemblies (asset_assembly.gd) are all model.
static func surfaces(root: Node3D) -> Array:
	var out: Array = []
	var meshes: Array[MeshInstance3D] = []
	_collect(root, meshes)
	var tagged := meshes.filter(func(m): return m.has_meta("craft_surface"))
	if not tagged.is_empty(): meshes.assign(tagged)
	for instance in meshes:
		var to_root := _to_root(instance, root)
		for surface in instance.mesh.get_surface_count():
			# Lines and points have no volume (primitive meshes are always triangles).
			if instance.mesh is ArrayMesh and (instance.mesh as ArrayMesh).surface_get_primitive_type(surface) != Mesh.PRIMITIVE_TRIANGLES: continue
			var arrays := instance.mesh.surface_get_arrays(surface)
			var vertices: PackedVector3Array = to_root * (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array)
			var indices = arrays[Mesh.ARRAY_INDEX]
			if not (indices is PackedInt32Array) or indices.is_empty():
				indices = PackedInt32Array(range(vertices.size()))
			if indices.size() >= 3: out.append([vertices, indices])
	return out

## Number of faces collision is built from (for reports and tests).
static func face_count(root: Node3D) -> int:
	var total := 0
	for part in surfaces(root): total += part[1].size() / 3
	return total

## Fills a grid over `bounds` (about `grid` cells along the longest side, each axis split
## evenly so the boxes end exactly on the model's bounds) and merges it into boxes.
static func voxel_boxes(parts: Array, bounds: AABB, grid: int) -> Array:
	var step := bounds.get_longest_axis_size() / grid
	var n := Vector3i(_cells(bounds.size.x, step, grid), _cells(bounds.size.y, step, grid), _cells(bounds.size.z, step, grid))
	# A flat model (a rug, a sign) still gets a thin slab rather than a zero-width cell.
	var cell := Vector3(maxf(bounds.size.x / n.x, 0.01), maxf(bounds.size.y / n.y, 0.01), maxf(bounds.size.z / n.z, 0.01))
	# A one-cell border of air around the model, so the outside is connected for the fill.
	var dim := n + Vector3i(2, 2, 2)
	var solid := PackedByteArray()
	solid.resize(dim.x * dim.y * dim.z)
	for part in parts:
		var vertices: PackedVector3Array = part[0]
		var indices: PackedInt32Array = part[1]
		# Each vertex in cell units and its cell, once; most faces of a 3,000-face model sit
		# inside one cell.
		var q := PackedVector3Array()
		q.resize(vertices.size())
		var at := PackedInt32Array()
		at.resize(vertices.size())
		var inverse := Vector3.ONE / cell
		for v in vertices.size():
			var u := (vertices[v] - bounds.position) * inverse
			q[v] = u
			at[v] = ((clampi(int(u.y), 0, n.y - 1) + 1) * dim.z + clampi(int(u.z), 0, n.z - 1) + 1) * dim.x + clampi(int(u.x), 0, n.x - 1) + 1
		for t in range(0, indices.size() - 2, 3):
			var ia := indices[t]
			var ib := indices[t + 1]
			var ic := indices[t + 2]
			if at[ia] == at[ib] and at[ib] == at[ic]:
				solid[at[ia]] = 1
				continue
			# Faces crossing cells: sample at under half a cell so no crossed cell is skipped.
			var a := q[ia]
			var ab := q[ib] - a
			var ac := q[ic] - a
			var steps := clampi(int(ceilf(maxf(ab.length(), maxf(ac.length(), (ac - ab).length())) * 2.0)), 1, 64)
			var inv_steps := 1.0 / steps
			for i in steps + 1:
				for j in steps + 1 - i:
					var w := a + ab * (i * inv_steps) + ac * (j * inv_steps)
					solid[((clampi(int(w.y), 0, n.y - 1) + 1) * dim.z + clampi(int(w.z), 0, n.z - 1) + 1) * dim.x + clampi(int(w.x), 0, n.x - 1) + 1] = 1
	_fill_inside(solid, dim)
	return _merge(solid, dim, bounds.position, cell)

static func _cells(length: float, step: float, grid: int) -> int:
	return clampi(int(roundf(length / step)), 1, grid)

static func _index(dim: Vector3i, x: int, y: int, z: int) -> int:
	return (y * dim.z + z) * dim.x + x

## Cells the outside air cannot reach are inside the model and become solid. A model with an
## open hole wider than a cell stays a hollow shell, which still blocks walkers.
static func _fill_inside(solid: PackedByteArray, dim: Vector3i) -> void:
	var outside := PackedByteArray()
	outside.resize(solid.size())
	var queue := PackedInt32Array()
	queue.resize(solid.size())
	queue[0] = 0
	outside[0] = 1
	var head := 0
	var tail := 1
	var row := dim.x
	var layer := dim.x * dim.z
	while head < tail:
		var i := queue[head]
		head += 1
		var x := i % row
		var z := (i / row) % dim.z
		var y := i / layer
		for j in [i + 1 if x + 1 < dim.x else -1, i - 1 if x > 0 else -1, i + row if z + 1 < dim.z else -1,
				i - row if z > 0 else -1, i + layer if y + 1 < dim.y else -1, i - layer if y > 0 else -1]:
			if j < 0 or outside[j] == 1 or solid[j] == 1: continue
			outside[j] = 1
			queue[tail] = j
			tail += 1
	for i in solid.size():
		if outside[i] == 0: solid[i] = 1

## Greedy merge: grow each unclaimed solid cell along x, then whole rows along z, then whole
## slabs along y.
static func _merge(solid: PackedByteArray, dim: Vector3i, origin: Vector3, cell: Vector3) -> Array:
	var used := PackedByteArray()
	used.resize(solid.size())
	var boxes: Array = []
	var free := func(x: int, y: int, z: int) -> bool:
		var i := _index(dim, x, y, z)
		return solid[i] == 1 and used[i] == 0
	for y in range(1, dim.y - 1):
		for z in range(1, dim.z - 1):
			for x in range(1, dim.x - 1):
				if not free.call(x, y, z): continue
				var x1 := x
				while x1 + 1 < dim.x - 1 and free.call(x1 + 1, y, z): x1 += 1
				var z1 := z
				while z1 + 1 < dim.z - 1 and _row_free(free, x, x1, y, z1 + 1): z1 += 1
				var y1 := y
				while y1 + 1 < dim.y - 1 and _slab_free(free, x, x1, z, z1, y1 + 1): y1 += 1
				for yy in range(y, y1 + 1):
					for zz in range(z, z1 + 1):
						for xx in range(x, x1 + 1):
							used[_index(dim, xx, yy, zz)] = 1
				var start := origin + Vector3(x - 1, y - 1, z - 1) * cell
				boxes.append(AABB(start, Vector3(x1 - x + 1, y1 - y + 1, z1 - z + 1) * cell))
	return boxes

static func _row_free(free: Callable, x0: int, x1: int, y: int, z: int) -> bool:
	for x in range(x0, x1 + 1):
		if not free.call(x, y, z): return false
	return true

static func _slab_free(free: Callable, x0: int, x1: int, z0: int, z1: int, y: int) -> bool:
	for z in range(z0, z1 + 1):
		if not _row_free(free, x0, x1, y, z): return false
	return true

static func _collect(node: Node, out: Array[MeshInstance3D]) -> void:
	if node is MeshInstance3D and node.mesh != null: out.append(node)
	for child in node.get_children(): _collect(child, out)

static func _to_root(node: Node3D, root: Node3D) -> Transform3D:
	var result := node.transform
	var current := node.get_parent() as Node3D
	while current != null and current != root:
		result = current.transform * result
		current = current.get_parent() as Node3D
	return result
