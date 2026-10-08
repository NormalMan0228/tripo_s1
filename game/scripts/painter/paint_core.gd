extends RefCounted
## The painter's engine, without UI: surface baking, picking, brushes, fill, gradient,
## layers, compositing and undo history. Everything here is plain data (packed arrays),
## so tests drive it headless and the workspace runs the slow steps on a worker thread.
##
## Space: "object space" is the painted model's root space. The paint texture is one
## square atlas (size x size, RGBA8, sRGB values like Photoshop): each mesh surface
## ("slot") owns one square tile of it (one slot -> the whole texture), and the slot's
## own UVs (0..1) map into its tile. bake() rasterises every triangle into its tile, so
## each covered texel knows its 3D position and normal; brushes then act by 3D distance
## on the surface (no seams, symmetry is a mirrored 3D point). A grid sorted by 3D cell
## keeps a stamp to the texels near it.

const NORMAL := 0
const MULTIPLY := 1
const SCREEN := 2
const OVERLAY := 3
const ADD := 4
const MODE_COUNT := 5
const TIP_ROUND := 0
const TIP_FLAT := 1
const TIP_NOISE := 2
const TILE := 64
const MAX_LAYERS := 8
## Texels of colour copied outward around every UV island (bilinear and mip sampling at
## island borders then never reaches unpainted gutter texels).
const PAD := 6
const HISTORY_BYTES := 96 * 1024 * 1024
const HISTORY_STEPS := 60
const NOISE_SIDE := 64

class Layer:
	var name := ""
	var data := PackedByteArray()
	var opacity := 1.0
	var mode := 0
	var visible := true
	## Bumped on every pixel change, so a view knows when to upload.
	var revision := 0

	func props() -> Dictionary:
		return {"name": name, "opacity": opacity, "mode": mode, "visible": visible}

	func set_props(value: Dictionary) -> void:
		name = str(value.get("name", name))
		opacity = clampf(float(value.get("opacity", opacity)), 0.0, 1.0)
		mode = clampi(int(value.get("mode", mode)), 0, MODE_COUNT - 1)
		visible = bool(value.get("visible", visible))

var size := 1024
var tiles_side := 16
# Triangles in object space (3 entries per triangle).
var tri_count := 0
var tri_v := PackedVector3Array()
var tri_n := PackedVector3Array()
var tri_uv := PackedVector2Array()
var tri_slot := PackedInt32Array()
var slot_count := 0
var slot_rects: Array[Rect2i] = []
var bounds := AABB()
var uv_ok := false
# Bake results.
var baked := false
var progress := 0.0
var covered := 0
var overlap := 0
var texel_world := 0.01
var texel_slot := PackedInt32Array()      # per texel: slot, -1 when no triangle covers it
var sorted_index := PackedInt32Array()    # per texel: index into the sorted arrays, -1 uncovered
var s_texel := PackedInt32Array()         # covered texels sorted by grid cell
var s_pos := PackedVector3Array()
var s_nrm := PackedVector3Array()
var cell := 0.01
var grid_origin := Vector3.ZERO
var grid_dims := Vector3i.ONE
var cell_start := PackedInt32Array()
var pad_dst := PackedInt32Array()         # padding pairs grouped by destination tile
var pad_src := PackedInt32Array()
var pad_tile_start := PackedInt32Array()
var texel_tri := PackedInt32Array()       # per texel: the triangle that wrote it
var seam_links := {}                      # texel -> PackedInt32Array, built on first fill
var link_mask := PackedByteArray()        # per texel: bits 1/2/4/8 = left/right/up/down neighbour is the same surface
# Picking (bounding volume hierarchy over triangles).
var bvh_min := PackedVector3Array()
var bvh_max := PackedVector3Array()
var bvh_left := PackedInt32Array()        # -1 for a leaf
var bvh_start := PackedInt32Array()       # leaf: first entry in bvh_tris; inner: right child
var bvh_count := PackedInt32Array()
var bvh_tris := PackedInt32Array()
# Pixels.
var backdrop := PackedByteArray()         # the object's look under every layer (opaque)
var layers: Array[Layer] = []
var current := 0
var symmetry := 0                         # 0 off, 1 mirror X, 2 mirror Z (around bounds centre)
var noise := PackedFloat32Array()
# Stroke in progress.
var stroke_layer: Layer
var stroke_pre := PackedByteArray()
var stroke_alpha := PackedFloat32Array()
var stroke_touched := PackedInt32Array()
var stroke_tiles := PackedByteArray()
var stroke_erase := false
var stroke_count := 0
# History.
var history: Array[Dictionary] = []
var history_index := 0
var history_bytes := 0
var history_serial := 0

# ------------------------------------------------------------------ mesh

## slots: [{vertices: PackedVector3Array (object space), normals, uvs: PackedVector2Array,
## indices: PackedInt32Array}], one per mesh surface, in the order the world applies them.
func setup(slots: Array, texture_size := 1024) -> void:
	size = texture_size
	tiles_side = maxi(1, size / TILE)
	slot_count = slots.size()
	slot_rects.clear()
	var grid := grid_side(slot_count)
	var tile := size / grid
	for k in slot_count:
		slot_rects.append(Rect2i((k % grid) * tile, (k / grid) * tile, tile, tile))
	tri_v = PackedVector3Array(); tri_n = PackedVector3Array(); tri_uv = PackedVector2Array(); tri_slot = PackedInt32Array()
	uv_ok = slot_count > 0
	var first := true
	for k in slot_count:
		var slot: Dictionary = slots[k]
		var vertices: PackedVector3Array = slot.get("vertices", PackedVector3Array())
		var normals: PackedVector3Array = slot.get("normals", PackedVector3Array())
		var uvs: PackedVector2Array = slot.get("uvs", PackedVector2Array())
		var indices: PackedInt32Array = slot.get("indices", PackedInt32Array())
		if indices.is_empty():
			for i in vertices.size(): indices.append(i)
		if uvs.size() != vertices.size() or not usable_uvs(uvs): uv_ok = false
		var rect: Rect2i = slot_rects[k]
		for v in vertices:
			bounds = AABB(v, Vector3.ZERO) if first else bounds.expand(v)
			first = false
		for i in range(0, indices.size() - 2, 3):
			var ia := indices[i]; var ib := indices[i + 1]; var ic := indices[i + 2]
			if ia >= vertices.size() or ib >= vertices.size() or ic >= vertices.size(): continue
			var a := vertices[ia]; var b := vertices[ib]; var c := vertices[ic]
			var face := (b - a).cross(c - a)
			if face.length_squared() < 1e-20: continue
			face = face.normalized()
			tri_v.append(a); tri_v.append(b); tri_v.append(c)
			for index in [ia, ib, ic]:
				var n: Vector3 = normals[index] if index < normals.size() else face
				tri_n.append(n.normalized() if n.length_squared() > 1e-12 else face)
			if uv_ok:
				for index in [ia, ib, ic]:
					tri_uv.append(Vector2(rect.position) + uvs[index] * float(rect.size.x))
			tri_slot.append(k)
	tri_count = tri_slot.size()
	if tri_count == 0: uv_ok = false

static func grid_side(count: int) -> int:
	return maxi(1, int(ceil(sqrt(float(maxi(count, 1))))))

## Missing or collapsed UVs (all in one point) cannot carry a texture.
static func usable_uvs(uvs: PackedVector2Array) -> bool:
	if uvs.is_empty(): return false
	var box := Rect2(uvs[0], Vector2.ZERO)
	for uv in uvs: box = box.expand(uv)
	return box.size.x * box.size.y > 1e-6

# ------------------------------------------------------------------ bake

## Rasterises the triangles into texel positions/normals, builds the padding pairs, the
## texel grid and the picking hierarchy. Slow (about a second at 1024); call it from a
## worker thread. progress goes 0..1.
func bake() -> void:
	var texels := size * size
	texel_slot = PackedInt32Array(); texel_slot.resize(texels); texel_slot.fill(-1)
	texel_tri = PackedInt32Array(); texel_tri.resize(texels); texel_tri.fill(-1)
	seam_links = {}; link_mask = PackedByteArray()
	var pos := PackedVector3Array(); pos.resize(texels)
	var nrm := PackedVector3Array(); nrm.resize(texels)
	covered = 0; overlap = 0
	var area3 := 0.0
	var area_uv := 0.0
	if uv_ok:
		for t in tri_count:
			if t % 256 == 0: progress = 0.55 * float(t) / tri_count
			var i := t * 3
			var a: Vector2 = tri_uv[i]; var b: Vector2 = tri_uv[i + 1]; var c: Vector2 = tri_uv[i + 2]
			var twice := (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
			if absf(twice) < 1e-9: continue
			# Triangles with UVs outside 0..1 are moved back a whole tile (repeat) and clipped.
			var rect: Rect2i = slot_rects[tri_slot[t]]
			var lo := Vector2(minf(a.x, minf(b.x, c.x)), minf(a.y, minf(b.y, c.y)))
			var hi := Vector2(maxf(a.x, maxf(b.x, c.x)), maxf(a.y, maxf(b.y, c.y)))
			var tile_size := float(rect.size.x)
			var off := Vector2(floor((lo.x - rect.position.x) / tile_size), floor((lo.y - rect.position.y) / tile_size)) * tile_size
			if off != Vector2.ZERO:
				a -= off; b -= off; c -= off; lo -= off; hi -= off
			var pa: Vector3 = tri_v[i]; var pb: Vector3 = tri_v[i + 1]; var pc: Vector3 = tri_v[i + 2]
			var na: Vector3 = tri_n[i]; var nb: Vector3 = tri_n[i + 1]; var nc: Vector3 = tri_n[i + 2]
			area3 += (pb - pa).cross(pc - pa).length() * 0.5
			area_uv += absf(twice) * 0.5
			var x0 := maxi(rect.position.x, int(floor(lo.x)))
			var x1 := mini(rect.end.x - 1, int(ceil(hi.x)))
			var y0 := maxi(rect.position.y, int(floor(lo.y)))
			var y1 := mini(rect.end.y - 1, int(ceil(hi.y)))
			if x0 > x1 or y0 > y1: continue
			var inv := 1.0 / twice
			var d0 := (b.y - c.y) * inv
			var d1 := (c.y - a.y) * inv
			var slot := tri_slot[t]
			var near := texel_world_estimate(pa, pb, pc, twice)
			for y in range(y0, y1 + 1):
				var py := y + 0.5
				var px := x0 + 0.5
				var w0 := ((b.x - px) * (c.y - py) - (b.y - py) * (c.x - px)) * inv
				var w1 := ((c.x - px) * (a.y - py) - (c.y - py) * (a.x - px)) * inv
				var row := y * size
				for x in range(x0, x1 + 1):
					var w2 := 1.0 - w0 - w1
					if w0 >= -1e-5 and w1 >= -1e-5 and w2 >= -1e-5:
						var texel := row + x
						var p := pa * w0 + pb * w1 + pc * w2
						if texel_slot[texel] < 0: covered += 1
						elif pos[texel].distance_squared_to(p) > near: overlap += 1
						texel_slot[texel] = slot
						texel_tri[texel] = t
						pos[texel] = p
						nrm[texel] = (na * w0 + nb * w1 + nc * w2).normalized()
					w0 += d0
					w1 += d1
	texel_world = sqrt(area3 / maxf(area_uv, 1.0)) if area_uv > 0.0 else 0.01
	progress = 0.55
	_build_padding()
	progress = 0.7
	_build_grid(pos, nrm)
	progress = 0.9
	_build_bvh()
	stroke_alpha = PackedFloat32Array(); stroke_alpha.resize(texels)
	stroke_tiles = PackedByteArray(); stroke_tiles.resize(tiles_side * tiles_side)
	_build_noise()
	baked = true
	progress = 1.0

## Squared 3D distance under which two triangles writing one texel are the same surface.
func texel_world_estimate(pa: Vector3, pb: Vector3, pc: Vector3, twice_uv: float) -> float:
	var world := sqrt((pb - pa).cross(pc - pa).length() / maxf(absf(twice_uv), 1e-9))
	return (world * 3.0) * (world * 3.0)

## Share of covered texels written by two distant triangles (mirrored or stacked UVs).
func overlap_ratio() -> float:
	return float(overlap) / maxf(1.0, float(covered))

func _build_padding() -> void:
	var texels := size * size
	var source := PackedInt32Array(); source.resize(texels); source.fill(-1)
	var frontier := PackedInt32Array()
	for t in texels:
		if texel_slot[t] >= 0:
			source[t] = t
			var x := t % size
			if (x > 0 and texel_slot[t - 1] < 0) or (x < size - 1 and texel_slot[t + 1] < 0) \
					or (t >= size and texel_slot[t - size] < 0) or (t < texels - size and texel_slot[t + size] < 0):
				frontier.append(t)
	var dst := PackedInt32Array()
	var src := PackedInt32Array()
	for ring in PAD:
		var next := PackedInt32Array()
		for t in frontier:
			var x := t % size
			var from := source[t]
			for n in [t - 1 if x > 0 else -1, t + 1 if x < size - 1 else -1, t - size, t + size]:
				if n < 0 or n >= texels or source[n] >= 0: continue
				source[n] = from
				dst.append(n); src.append(from); next.append(n)
		frontier = next
	# Group the pairs by destination tile so a stroke pads only the tiles it touched.
	var tiles := tiles_side * tiles_side
	pad_tile_start = PackedInt32Array(); pad_tile_start.resize(tiles + 1); pad_tile_start.fill(0)
	for d in dst: pad_tile_start[tile_of(d) + 1] += 1
	for i in tiles: pad_tile_start[i + 1] += pad_tile_start[i]
	var fill := pad_tile_start.slice(0, tiles)
	pad_dst = PackedInt32Array(); pad_dst.resize(dst.size())
	pad_src = PackedInt32Array(); pad_src.resize(dst.size())
	for i in dst.size():
		var tile := tile_of(dst[i])
		var at := fill[tile]
		pad_dst[at] = dst[i]; pad_src[at] = src[i]
		fill[tile] = at + 1

func tile_of(texel: int) -> int:
	return ((texel / size) / TILE) * tiles_side + (texel % size) / TILE

func _build_grid(pos: PackedVector3Array, nrm: PackedVector3Array) -> void:
	var texels := size * size
	var box := bounds.grow(maxf(bounds.get_longest_axis_size() * 0.001, 1e-4))
	cell = maxf(texel_world * 6.0, box.get_longest_axis_size() / 96.0)
	grid_origin = box.position
	grid_dims = Vector3i(maxi(1, int(ceil(box.size.x / cell))), maxi(1, int(ceil(box.size.y / cell))), maxi(1, int(ceil(box.size.z / cell))))
	var cells := grid_dims.x * grid_dims.y * grid_dims.z
	cell_start = PackedInt32Array(); cell_start.resize(cells + 1); cell_start.fill(0)
	var cell_of := PackedInt32Array(); cell_of.resize(texels)
	var inv := 1.0 / cell
	for t in texels:
		if texel_slot[t] < 0: continue
		var q := (pos[t] - grid_origin) * inv
		var id := (clampi(int(q.z), 0, grid_dims.z - 1) * grid_dims.y + clampi(int(q.y), 0, grid_dims.y - 1)) * grid_dims.x + clampi(int(q.x), 0, grid_dims.x - 1)
		cell_of[t] = id
		cell_start[id + 1] += 1
	for i in cells: cell_start[i + 1] += cell_start[i]
	var fill := cell_start.slice(0, cells)
	s_texel = PackedInt32Array(); s_texel.resize(covered)
	s_pos = PackedVector3Array(); s_pos.resize(covered)
	s_nrm = PackedVector3Array(); s_nrm.resize(covered)
	sorted_index = PackedInt32Array(); sorted_index.resize(texels); sorted_index.fill(-1)
	for t in texels:
		if texel_slot[t] < 0: continue
		var id := cell_of[t]
		var at := fill[id]
		fill[id] = at + 1
		s_texel[at] = t; s_pos[at] = pos[t]; s_nrm[at] = nrm[t]
		sorted_index[t] = at

func _build_noise() -> void:
	var generator := FastNoiseLite.new()
	generator.seed = 7
	generator.frequency = 0.11
	generator.fractal_octaves = 3
	noise = PackedFloat32Array(); noise.resize(NOISE_SIDE * NOISE_SIDE)
	for y in NOISE_SIDE:
		for x in NOISE_SIDE:
			# Tileable: blend the four wrapped samples.
			var u := float(x) / NOISE_SIDE; var v := float(y) / NOISE_SIDE
			var value := generator.get_noise_2d(x, y) * (1.0 - u) * (1.0 - v) + generator.get_noise_2d(x - NOISE_SIDE, y) * u * (1.0 - v) \
				+ generator.get_noise_2d(x, y - NOISE_SIDE) * (1.0 - u) * v + generator.get_noise_2d(x - NOISE_SIDE, y - NOISE_SIDE) * u * v
			noise[y * NOISE_SIDE + x] = clampf(value * 1.6 + 0.55, 0.0, 1.0)

# ------------------------------------------------------------------ picking

func _build_bvh() -> void:
	bvh_min = PackedVector3Array(); bvh_max = PackedVector3Array()
	bvh_left = PackedInt32Array(); bvh_start = PackedInt32Array(); bvh_count = PackedInt32Array()
	bvh_tris = PackedInt32Array(); bvh_tris.resize(tri_count)
	var centre := PackedVector3Array(); centre.resize(tri_count)
	var tmin := PackedVector3Array(); tmin.resize(tri_count)
	var tmax := PackedVector3Array(); tmax.resize(tri_count)
	for t in tri_count:
		var a := tri_v[t * 3]; var b := tri_v[t * 3 + 1]; var c := tri_v[t * 3 + 2]
		tmin[t] = a.min(b).min(c); tmax[t] = a.max(b).max(c)
		centre[t] = (a + b + c) / 3.0
		bvh_tris[t] = t
	if tri_count == 0: return
	_bvh_node(0, tri_count, tmin, tmax)
	var stack: Array[Vector3i] = [Vector3i(0, 0, tri_count)]
	while not stack.is_empty():
		var item: Vector3i = stack.pop_back()
		var node := item.x; var start := item.y; var end := item.z
		if end - start <= 4:
			bvh_left[node] = -1; bvh_start[node] = start; bvh_count[node] = end - start
			continue
		var lo := centre[bvh_tris[start]]; var hi := lo
		for i in range(start, end):
			var c := centre[bvh_tris[i]]
			lo = lo.min(c); hi = hi.max(c)
		var extent := hi - lo
		var axis := 0 if extent.x >= extent.y and extent.x >= extent.z else (1 if extent.y >= extent.z else 2)
		var split := (lo[axis] + hi[axis]) * 0.5
		var i := start; var j := end - 1
		while i <= j:
			if centre[bvh_tris[i]][axis] < split: i += 1
			else:
				var swap := bvh_tris[i]; bvh_tris[i] = bvh_tris[j]; bvh_tris[j] = swap; j -= 1
		var mid := i
		if mid == start or mid == end: mid = (start + end) / 2
		var left := _bvh_node(start, mid, tmin, tmax)
		var right := _bvh_node(mid, end, tmin, tmax)
		bvh_left[node] = left; bvh_start[node] = right; bvh_count[node] = 0
		stack.append(Vector3i(left, start, mid)); stack.append(Vector3i(right, mid, end))

func _bvh_node(start: int, end: int, tmin: PackedVector3Array, tmax: PackedVector3Array) -> int:
	var lo := tmin[bvh_tris[start]]; var hi := tmax[bvh_tris[start]]
	for i in range(start + 1, end):
		lo = lo.min(tmin[bvh_tris[i]]); hi = hi.max(tmax[bvh_tris[i]])
	bvh_min.append(lo - Vector3.ONE * 1e-5); bvh_max.append(hi + Vector3.ONE * 1e-5)
	bvh_left.append(-1); bvh_start.append(0); bvh_count.append(0)
	return bvh_min.size() - 1

## Nearest surface hit along a ray in object space: {hit, position, normal, triangle, slot,
## distance}. Back faces are hit too (open furniture shows its inside).
func pick(origin: Vector3, direction: Vector3) -> Dictionary:
	var miss := {"hit": false}
	if tri_count == 0 or bvh_min.is_empty(): return miss
	var dir := direction.normalized()
	var inv := Vector3(1.0 / dir.x if absf(dir.x) > 1e-12 else 1e12, 1.0 / dir.y if absf(dir.y) > 1e-12 else 1e12, 1.0 / dir.z if absf(dir.z) > 1e-12 else 1e12)
	var best := INF
	var best_tri := -1
	var best_u := 0.0; var best_v := 0.0
	var stack := PackedInt32Array([0])
	while not stack.is_empty():
		var node := stack[stack.size() - 1]
		stack.resize(stack.size() - 1)
		var t1 := (bvh_min[node] - origin) * inv
		var t2 := (bvh_max[node] - origin) * inv
		var near := maxf(maxf(minf(t1.x, t2.x), minf(t1.y, t2.y)), minf(t1.z, t2.z))
		var far := minf(minf(maxf(t1.x, t2.x), maxf(t1.y, t2.y)), maxf(t1.z, t2.z))
		if far < maxf(near, 0.0) or near > best: continue
		if bvh_left[node] >= 0:
			stack.append(bvh_left[node]); stack.append(bvh_start[node])
			continue
		for k in range(bvh_start[node], bvh_start[node] + bvh_count[node]):
			var t := bvh_tris[k]
			var a := tri_v[t * 3]
			var e1 := tri_v[t * 3 + 1] - a
			var e2 := tri_v[t * 3 + 2] - a
			var p := dir.cross(e2)
			var det := e1.dot(p)
			if absf(det) < 1e-14: continue
			var f := 1.0 / det
			var s := origin - a
			var u := s.dot(p) * f
			if u < 0.0 or u > 1.0: continue
			var q := s.cross(e1)
			var v := dir.dot(q) * f
			if v < 0.0 or u + v > 1.0: continue
			var dist := e2.dot(q) * f
			if dist > 1e-6 and dist < best:
				best = dist; best_tri = t; best_u = u; best_v = v
	if best_tri < 0: return miss
	var w := 1.0 - best_u - best_v
	var normal := (tri_n[best_tri * 3] * w + tri_n[best_tri * 3 + 1] * best_u + tri_n[best_tri * 3 + 2] * best_v).normalized()
	# Facing the viewer, so brushes treat the visible side as the front.
	if normal.dot(dir) > 0.0: normal = -normal
	return {"hit": true, "position": origin + dir * best, "normal": normal, "triangle": best_tri,
		"slot": tri_slot[best_tri], "distance": best}

## The covered texel closest to a surface point (fill seeds, the eyedropper), -1 if none.
func nearest_texel(point: Vector3, normal := Vector3.ZERO) -> int:
	if not baked or covered == 0: return -1
	var radius := maxf(texel_world * 2.0, cell * 0.5)
	for attempt in 6:
		var best := -1
		var best_d := radius * radius
		for range_cell in _cell_ranges(point, radius):
			for k in range(cell_start[range_cell], cell_start[range_cell + 1]):
				var d := s_pos[k].distance_squared_to(point)
				if d < best_d and (normal == Vector3.ZERO or s_nrm[k].dot(normal) > -0.3):
					best_d = d; best = s_texel[k]
		if best >= 0: return best
		radius *= 2.0
	return -1

func _cell_ranges(point: Vector3, radius: float) -> PackedInt32Array:
	var out := PackedInt32Array()
	var inv := 1.0 / cell
	var lo := ((point - Vector3.ONE * radius) - grid_origin) * inv
	var hi := ((point + Vector3.ONE * radius) - grid_origin) * inv
	var x0 := clampi(int(floor(lo.x)), 0, grid_dims.x - 1); var x1 := clampi(int(floor(hi.x)), 0, grid_dims.x - 1)
	var y0 := clampi(int(floor(lo.y)), 0, grid_dims.y - 1); var y1 := clampi(int(floor(hi.y)), 0, grid_dims.y - 1)
	var z0 := clampi(int(floor(lo.z)), 0, grid_dims.z - 1); var z1 := clampi(int(floor(hi.z)), 0, grid_dims.z - 1)
	if hi.x < 0 or hi.y < 0 or hi.z < 0 or lo.x >= grid_dims.x or lo.y >= grid_dims.y or lo.z >= grid_dims.z: return out
	for z in range(z0, z1 + 1):
		for y in range(y0, y1 + 1):
			var row := (z * grid_dims.y + y) * grid_dims.x
			for x in range(x0, x1 + 1):
				if cell_start[row + x + 1] > cell_start[row + x]: out.append(row + x)
	return out

func texel_position(texel: int) -> Vector3:
	var at := sorted_index[texel] if texel >= 0 and texel < sorted_index.size() else -1
	return s_pos[at] if at >= 0 else Vector3.ZERO

func texel_normal(texel: int) -> Vector3:
	var at := sorted_index[texel] if texel >= 0 and texel < sorted_index.size() else -1
	return s_nrm[at] if at >= 0 else Vector3.UP

# ------------------------------------------------------------------ layers

## base: the starting look of the first layer; under: what shows below every layer (the
## object's unpainted look). Both RGBA8 size x size.
func start_layers(base: PackedByteArray, under: PackedByteArray, base_name := "바탕") -> void:
	backdrop = under.duplicate()
	layers.clear()
	var layer := Layer.new()
	layer.name = base_name
	layer.data = base.duplicate()
	layers.append(layer)
	current = 0
	history.clear(); history_index = 0; history_bytes = 0

func blank() -> PackedByteArray:
	var data := PackedByteArray()
	data.resize(size * size * 4)
	return data

func layer_index(layer: Layer) -> int:
	return layers.find(layer)

func add_layer(name: String) -> int:
	if layers.size() >= MAX_LAYERS: return -1
	var layer := Layer.new()
	layer.name = name
	layer.data = blank()
	var index := current + 1
	layers.insert(index, layer)
	current = index
	_push({"type": "add", "name": "레이어 추가", "layer": layer, "index": index, "bytes": 0})
	return index

func duplicate_layer(index: int, name: String) -> int:
	if layers.size() >= MAX_LAYERS or index < 0 or index >= layers.size(): return -1
	var source := layers[index]
	var layer := Layer.new()
	layer.set_props(source.props())
	layer.name = name
	layer.data = source.data.duplicate()
	layers.insert(index + 1, layer)
	current = index + 1
	_push({"type": "add", "name": "레이어 복제", "layer": layer, "index": index + 1, "bytes": 0})
	return index + 1

func delete_layer(index: int) -> bool:
	if layers.size() <= 1 or index < 0 or index >= layers.size(): return false
	var layer := layers[index]
	layers.remove_at(index)
	current = clampi(index - 1 if index > 0 else 0, 0, layers.size() - 1)
	# The removed pixels stay with the history entry so undo brings them back.
	_push({"type": "delete", "name": "레이어 삭제", "layer": layer, "index": index, "bytes": layer.data.size()})
	return true

func move_layer(index: int, to: int) -> bool:
	if index < 0 or index >= layers.size() or to < 0 or to >= layers.size() or index == to: return false
	var layer := layers[index]
	layers.remove_at(index)
	layers.insert(to, layer)
	current = to
	_push({"type": "move", "name": "레이어 순서", "from": index, "to": to, "bytes": 0})
	return true

## Opacity, blend mode, visibility or name. Repeated edits of one property (dragging a
## slider) become one history step.
func set_layer_props(index: int, value: Dictionary, label := "레이어 설정") -> void:
	if index < 0 or index >= layers.size(): return
	var layer := layers[index]
	var before := layer.props()
	layer.set_props(value)
	var after := layer.props()
	if before == after: return
	var key := str(value.keys())
	if history_index > 0 and history_index == history.size():
		var last: Dictionary = history[history_index - 1]
		if last.type == "props" and last.layer == layer and last.key == key and Time.get_ticks_msec() - int(last.time) < 1500:
			last.after = after
			last.time = Time.get_ticks_msec()
			return
	_push({"type": "props", "name": label, "layer": layer, "before": before, "after": after, "key": key, "time": Time.get_ticks_msec(), "bytes": 0})

# ------------------------------------------------------------------ strokes

## Starts a stroke on the current layer (brush or eraser). Every stamp until end_stroke()
## builds one coverage per texel (opacity caps it, flow builds toward it), so crossing
## your own stroke does not darken it, like Photoshop.
func begin_stroke(erase := false) -> void:
	if stroke_layer != null: end_stroke()
	stroke_layer = layers[current]
	stroke_pre = stroke_layer.data.duplicate()
	stroke_touched = PackedInt32Array()
	stroke_tiles.fill(0)
	stroke_erase = erase
	stroke_count = 0

func stroke_active() -> bool:
	return stroke_layer != null

## brush: {color: Color, mode, opacity, flow, hardness (0..1), tip, roundness (0..1), angle
## (radians), right/up (screen axes in object space, for flat and noisy tips), seed}.
## With symmetry on, the mirrored stamp is applied too. Returns texels changed.
func stamp(center: Vector3, normal: Vector3, radius: float, brush: Dictionary) -> int:
	var changed := _stamp_once(center, normal, radius, brush)
	if symmetry != 0:
		# Reflecting the tip's axes too makes the mirrored dab the mirror image of this one.
		var mirrored := brush.duplicate()
		mirrored.right = mirror_vector(brush.get("right", Vector3.RIGHT))
		mirrored.up = mirror_vector(brush.get("up", Vector3.UP))
		changed += _stamp_once(mirror_point(center), mirror_vector(normal), radius, mirrored)
	return changed

func mirror_point(p: Vector3) -> Vector3:
	var c := bounds.get_center()
	if symmetry == 1: return Vector3(2.0 * c.x - p.x, p.y, p.z)
	if symmetry == 2: return Vector3(p.x, p.y, 2.0 * c.z - p.z)
	return p

func mirror_vector(v: Vector3) -> Vector3:
	if symmetry == 1: return Vector3(-v.x, v.y, v.z)
	if symmetry == 2: return Vector3(v.x, v.y, -v.z)
	return v

func _stamp_once(center: Vector3, normal: Vector3, radius: float, brush: Dictionary) -> int:
	if stroke_layer == null or not baked or radius <= 0.0: return 0
	var color: Color = brush.get("color", Color.BLACK)
	var mode: int = int(brush.get("mode", NORMAL))
	var cap: float = clampf(float(brush.get("opacity", 1.0)), 0.0, 1.0)
	var flow: float = clampf(float(brush.get("flow", 1.0)), 0.0, 1.0)
	var hardness: float = clampf(float(brush.get("hardness", 0.8)), 0.0, 1.0)
	var tip: int = int(brush.get("tip", TIP_ROUND))
	var roundness: float = clampf(float(brush.get("roundness", 1.0)), 0.05, 1.0)
	var angle: float = float(brush.get("angle", 0.0))
	var right: Vector3 = brush.get("right", Vector3.RIGHT)
	var up: Vector3 = brush.get("up", Vector3.UP)
	var facing: float = float(brush.get("facing", -0.25))
	if cap <= 0.0 or flow <= 0.0: return 0
	# At least a texel of soft edge keeps hard brushes from aliasing.
	var edge := clampf(1.0 - texel_world * 1.5 / radius, 0.0, 1.0)
	var hard := minf(hardness, edge)
	var soft := maxf(1e-4, 1.0 - hard)
	var r2 := radius * radius
	var inv_r := 1.0 / radius
	var ca := cos(angle); var sa := sin(angle)
	var inv_round := 1.0 / roundness
	var stretch := tip != TIP_ROUND
	var rng := RandomNumberGenerator.new()
	rng.seed = int(brush.get("seed", stroke_count))
	var noise_x := rng.randi_range(0, NOISE_SIDE - 1)
	var noise_y := rng.randi_range(0, NOISE_SIDE - 1)
	var noise_scale := float(NOISE_SIDE) * 0.5
	var cr := color.r * 255.0; var cg := color.g * 255.0; var cb := color.b * 255.0
	var layer := stroke_layer
	var data := layer.data
	layer.data = PackedByteArray()  # keep `data` the only reference (no copy-on-write)
	var alpha := stroke_alpha
	stroke_alpha = PackedFloat32Array()
	var pre := stroke_pre
	var touched := stroke_touched
	stroke_touched = PackedInt32Array()
	var tiles := stroke_tiles
	stroke_tiles = PackedByteArray()
	var erase := stroke_erase
	var changed := 0
	for c in _cell_ranges(center, radius):
		for k in range(cell_start[c], cell_start[c + 1]):
			var p: Vector3 = s_pos[k]
			var d2 := p.distance_squared_to(center)
			if d2 >= r2: continue
			if s_nrm[k].dot(normal) < facing: continue
			var x: float
			var dab := flow
			if stretch:
				var offset := p - center
				var u := offset.dot(right)
				var v := offset.dot(up)
				var ur := u * ca + v * sa
				var vr := (v * ca - u * sa) * inv_round
				x = sqrt(ur * ur + vr * vr) * inv_r
				if x >= 1.0: continue
				if tip == TIP_NOISE:
					var nx := (int((ur * inv_r + 1.0) * noise_scale) + noise_x) & (NOISE_SIDE - 1)
					var ny := (int((vr * roundness * inv_r + 1.0) * noise_scale) + noise_y) & (NOISE_SIDE - 1)
					dab *= noise[ny * NOISE_SIDE + nx]
			else:
				x = sqrt(d2) * inv_r
			if x > hard:
				var f := (x - hard) / soft
				dab *= 1.0 - f * f * (3.0 - 2.0 * f)
			var t: int = s_texel[k]
			var before: float = alpha[t]
			if before >= cap: continue
			var after := before + (cap - before) * dab
			if after <= before + 1e-5: continue
			if before == 0.0:
				touched.append(t)
				tiles[((t / size) / TILE) * tiles_side + (t % size) / TILE] = 1
			alpha[t] = after
			var o := t * 4
			var pa: int = pre[o + 3]
			if erase:
				data[o + 3] = int(pa * (1.0 - after) + 0.5)
			elif pa == 255 and mode == NORMAL:
				var r0: int = pre[o]; var g0: int = pre[o + 1]; var b0: int = pre[o + 2]
				data[o] = int(r0 + (cr - r0) * after + 0.5)
				data[o + 1] = int(g0 + (cg - g0) * after + 0.5)
				data[o + 2] = int(b0 + (cb - b0) * after + 0.5)
			elif pa == 0:
				# Nothing below on this layer: every mode paints as normal.
				data[o] = int(cr + 0.5); data[o + 1] = int(cg + 0.5); data[o + 2] = int(cb + 0.5)
				data[o + 3] = int(after * 255.0 + 0.5)
			else:
				_blend_into(data, pre, o, after, color, mode)
			changed += 1
	layer.data = data
	stroke_alpha = alpha
	stroke_touched = touched
	stroke_tiles = tiles
	stroke_count += 1
	if changed > 0: layer.revision += 1
	return changed

## Brush colour over a (possibly transparent) layer pixel with a blend mode; W3C/Photoshop
## compositing: the mode applies where the layer already has paint.
static func _blend_into(data: PackedByteArray, pre: PackedByteArray, o: int, s: float, color: Color, mode: int) -> void:
	var al := pre[o + 3] / 255.0
	var lr := pre[o] / 255.0; var lg := pre[o + 1] / 255.0; var lb := pre[o + 2] / 255.0
	var mr := (1.0 - al) * color.r + al * blend_channel(lr, color.r, mode)
	var mg := (1.0 - al) * color.g + al * blend_channel(lg, color.g, mode)
	var mb := (1.0 - al) * color.b + al * blend_channel(lb, color.b, mode)
	var out_a := s + al * (1.0 - s)
	if out_a <= 0.0:
		data[o + 3] = 0
		return
	var keep := al * (1.0 - s)
	data[o] = int(clampf((mr * s + lr * keep) / out_a, 0.0, 1.0) * 255.0 + 0.5)
	data[o + 1] = int(clampf((mg * s + lg * keep) / out_a, 0.0, 1.0) * 255.0 + 0.5)
	data[o + 2] = int(clampf((mb * s + lb * keep) / out_a, 0.0, 1.0) * 255.0 + 0.5)
	data[o + 3] = int(out_a * 255.0 + 0.5)

static func blend_channel(base: float, top: float, mode: int) -> float:
	match mode:
		MULTIPLY: return base * top
		SCREEN: return base + top - base * top
		OVERLAY: return 2.0 * base * top if base < 0.5 else 1.0 - 2.0 * (1.0 - base) * (1.0 - top)
		ADD: return minf(1.0, base + top)
	return top

## Finishes the stroke: pads the touched islands and records one history step.
func end_stroke(label := "") -> bool:
	if stroke_layer == null: return false
	var layer := stroke_layer
	stroke_layer = null
	var touched := stroke_touched
	for t in touched: stroke_alpha[t] = 0.0
	stroke_touched = PackedInt32Array()
	if touched.is_empty():
		stroke_pre = PackedByteArray()
		return false
	var dirty := PackedInt32Array()
	for i in stroke_tiles.size():
		if stroke_tiles[i] != 0: dirty.append(i)
	_pad_tiles(layer, dirty)
	var name := label if not label.is_empty() else ("지우개" if stroke_erase else "붓")
	_push_pixels(name, layer, stroke_pre, dirty)
	stroke_pre = PackedByteArray()
	return true

## Copies island-edge colours outward in the given tiles (and their neighbours, whose
## padding may come from these).
func _pad_tiles(layer: Layer, dirty: PackedInt32Array) -> void:
	if dirty.is_empty(): return
	var wanted := PackedByteArray(); wanted.resize(tiles_side * tiles_side)
	for tile in dirty:
		var tx := tile % tiles_side; var ty := tile / tiles_side
		for dy in [-1, 0, 1]:
			for dx in [-1, 0, 1]:
				var nx: int = tx + dx; var ny: int = ty + dy
				if nx >= 0 and ny >= 0 and nx < tiles_side and ny < tiles_side: wanted[ny * tiles_side + nx] = 1
	var data := layer.data
	layer.data = PackedByteArray()
	for tile in wanted.size():
		if wanted[tile] == 0: continue
		for i in range(pad_tile_start[tile], pad_tile_start[tile + 1]):
			var d := pad_dst[i] * 4; var s := pad_src[i] * 4
			data[d] = data[s]; data[d + 1] = data[s + 1]; data[d + 2] = data[s + 2]; data[d + 3] = data[s + 3]
	layer.data = data

func _pad_all(layer: Layer) -> void:
	var all := PackedInt32Array()
	for i in tiles_side * tiles_side: all.append(i)
	_pad_tiles(layer, all)

# ------------------------------------------------------------------ fill and gradient

## Texels next to each other in the texture are one surface only when they are close in 3D
## too (UV islands can touch in the atlas without touching on the model).
func _joined(a: int, b: int, reach2: float) -> bool:
	var ia := sorted_index[a]; var ib := sorted_index[b]
	return ia >= 0 and ib >= 0 and s_pos[ia].distance_squared_to(s_pos[ib]) <= reach2

## Flood fill from a texel across the surface (through UV seams), taking texels whose colour
## is within tolerance (0..255 per channel) of the seed's. sample_all: compare the composite
## (all layers) instead of the current layer alone. Returns the texels filled.
func fill(seed: int, color: Color, tolerance: int, brush: Dictionary, sample_all := true) -> int:
	if not baked or seed < 0 or seed >= texel_slot.size() or texel_slot[seed] < 0: return 0
	if link_mask.is_empty(): build_links()
	var source: PackedByteArray = composite() if sample_all else layers[current].data
	var seeds := PackedInt32Array([seed])
	if symmetry != 0:
		var other := nearest_texel(mirror_point(texel_position(seed)), mirror_vector(texel_normal(seed)))
		if other >= 0 and other != seed: seeds.append(other)
	var mask := link_mask
	var region := PackedInt32Array()
	var seen := PackedByteArray(); seen.resize(size * size)
	for start in seeds:
		if seen[start] != 0: continue
		var o := start * 4
		var sr: int = source[o]; var sg: int = source[o + 1]; var sb: int = source[o + 2]; var sa: int = source[o + 3]
		var queue := PackedInt32Array([start])
		seen[start] = 1
		var head := 0
		while head < queue.size():
			var t := queue[head]
			head += 1
			var q := t * 4
			if absi(source[q] - sr) > tolerance or absi(source[q + 1] - sg) > tolerance or absi(source[q + 2] - sb) > tolerance or absi(source[q + 3] - sa) > tolerance:
				continue
			region.append(t)
			var bits: int = mask[t]
			if bits & 1 and seen[t - 1] == 0: seen[t - 1] = 1; queue.append(t - 1)
			if bits & 2 and seen[t + 1] == 0: seen[t + 1] = 1; queue.append(t + 1)
			if bits & 4 and seen[t - size] == 0: seen[t - size] = 1; queue.append(t - size)
			if bits & 8 and seen[t + size] == 0: seen[t + size] = 1; queue.append(t + size)
			if bits & 16:
				for n in seam_links[t]:
					if seen[n] == 0: seen[n] = 1; queue.append(n)
	begin_stroke(false)
	_apply_region(region, PackedFloat32Array(), color, color, clampf(float(brush.get("opacity", 1.0)), 0.0, 1.0), int(brush.get("mode", NORMAL)))
	end_stroke("채우기")
	return region.size()

## Surface connectivity for fill, built once (on the first fill): link_mask has a bit per
## texture neighbour on the same surface (written by the same triangle, or close in 3D), and
## texels on the edge of a UV island are linked to the texels at the same 3D spot on the
## other side of the seam (bit 16 + seam_links).
func build_links() -> void:
	seam_links = {}
	var texels := size * size
	var mask := PackedByteArray(); mask.resize(texels)
	var reach := texel_world * 1.75
	var reach2 := reach * reach
	var apart2 := (texel_world * 4.0) * (texel_world * 4.0)
	var edges := PackedInt32Array()
	var slots := texel_slot
	var tris := texel_tri
	for t in texels:
		if slots[t] < 0: continue
		var x := t % size
		var tri := tris[t]
		var bits := 0
		var edge := false
		if x > 0 and slots[t - 1] >= 0 and (tris[t - 1] == tri or _joined(t, t - 1, apart2)): bits |= 1
		else: edge = true
		if x < size - 1 and slots[t + 1] >= 0 and (tris[t + 1] == tri or _joined(t, t + 1, apart2)): bits |= 2
		else: edge = true
		if t >= size and slots[t - size] >= 0 and (tris[t - size] == tri or _joined(t, t - size, apart2)): bits |= 4
		else: edge = true
		if t < texels - size and slots[t + size] >= 0 and (tris[t + size] == tri or _joined(t, t + size, apart2)): bits |= 8
		else: edge = true
		mask[t] = bits
		if edge: edges.append(t)
	for t in edges:
		var x := t % size
		var row := t / size
		var p := texel_position(t)
		var links := PackedInt32Array()
		for c in _cell_ranges(p, reach):
			for k in range(cell_start[c], cell_start[c + 1]):
				var other: int = s_texel[k]
				if other == t or s_pos[k].distance_squared_to(p) > reach2: continue
				# Neighbours in the texture are already connected.
				if absi(other % size - x) <= 1 and absi(other / size - row) <= 1: continue
				links.append(other)
		if not links.is_empty():
			seam_links[t] = links
			mask[t] = mask[t] | 16
	link_mask = mask

## Linear (radial = false) or radial gradient from a to b in object space, colour from c1
## to c2 (c2 alpha 0 = fade to transparent). slot >= 0 limits it to one part.
func gradient(a: Vector3, b: Vector3, radial: bool, c1: Color, c2: Color, brush: Dictionary, slot := -1) -> int:
	if not baked: return 0
	var axis := b - a
	var length2 := axis.length_squared()
	if length2 < 1e-12: return 0
	var inv_length := 1.0 / sqrt(length2)
	var inv_length2 := 1.0 / length2
	var count := s_texel.size()
	var region := PackedInt32Array(); region.resize(count)
	var amount := PackedFloat32Array(); amount.resize(count)
	var used := 0
	for k in count:
		var t: int = s_texel[k]
		if slot >= 0 and texel_slot[t] != slot: continue
		var offset: Vector3 = s_pos[k] - a
		region[used] = t
		amount[used] = clampf(offset.length() * inv_length if radial else offset.dot(axis) * inv_length2, 0.0, 1.0)
		used += 1
	region.resize(used); amount.resize(used)
	begin_stroke(false)
	_apply_region(region, amount, c1, c2, clampf(float(brush.get("opacity", 1.0)), 0.0, 1.0), int(brush.get("mode", NORMAL)))
	end_stroke("그라데이션")
	return used

## Paints texels at full stroke coverage: colour c1 (or c1->c2 by amount), alpha scaled by
## the colours' alpha and the cap. Used by fill and gradient inside a stroke.
func _apply_region(region: PackedInt32Array, amount: PackedFloat32Array, c1: Color, c2: Color, cap: float, mode: int) -> void:
	if region.is_empty() or cap <= 0.0: return
	var layer := stroke_layer
	var data := layer.data
	layer.data = PackedByteArray()
	var alpha := stroke_alpha
	stroke_alpha = PackedFloat32Array()
	var touched := stroke_touched
	stroke_touched = PackedInt32Array()
	var tiles := stroke_tiles
	stroke_tiles = PackedByteArray()
	var pre := stroke_pre
	var graded := not amount.is_empty()
	var r1 := c1.r; var g1 := c1.g; var b1 := c1.b; var a1 := c1.a
	var dr := c2.r - r1; var dg := c2.g - g1; var db := c2.b - b1; var da := c2.a - a1
	var color := Color(r1, g1, b1)
	for i in region.size():
		var t := region[i]
		var f := amount[i] if graded else 0.0
		var s := cap * (a1 + da * f)
		if s <= 0.0: continue
		var cr := r1 + dr * f; var cg := g1 + dg * f; var cb := b1 + db * f
		if alpha[t] == 0.0:
			touched.append(t)
			tiles[((t / size) / TILE) * tiles_side + (t % size) / TILE] = 1
		alpha[t] = s
		var o := t * 4
		var pa: int = pre[o + 3]
		if pa == 0:
			data[o] = int(cr * 255.0 + 0.5); data[o + 1] = int(cg * 255.0 + 0.5); data[o + 2] = int(cb * 255.0 + 0.5)
			data[o + 3] = int(s * 255.0 + 0.5)
		elif pa == 255 and mode == NORMAL:
			var r0: int = pre[o]; var g0: int = pre[o + 1]; var b0: int = pre[o + 2]
			data[o] = int(r0 + (cr * 255.0 - r0) * s + 0.5)
			data[o + 1] = int(g0 + (cg * 255.0 - g0) * s + 0.5)
			data[o + 2] = int(b0 + (cb * 255.0 - b0) * s + 0.5)
		else:
			color.r = cr; color.g = cg; color.b = cb
			_blend_into(data, pre, o, s, color, mode)
	layer.data = data
	stroke_alpha = alpha
	stroke_touched = touched
	stroke_tiles = tiles
	layer.revision += 1

# ------------------------------------------------------------------ composite

## Every visible layer over the backdrop, as opaque RGBA8 (the texture that is saved).
## Normal layers are blended natively (Image.blend_rect, with the layer opacity folded into
## the alpha first); the other modes run per texel where the layer has paint.
func composite() -> PackedByteArray:
	var image := Image.create_from_data(size, size, false, Image.FORMAT_RGBA8, backdrop)
	var whole := Rect2i(0, 0, size, size)
	var data := PackedByteArray()
	var native := true
	for layer in layers:
		if not layer.visible or layer.opacity <= 0.0: continue
		if layer.mode == NORMAL:
			if not native:
				image = Image.create_from_data(size, size, false, Image.FORMAT_RGBA8, data)
				native = true
			var top := layer.data
			if layer.opacity < 1.0:
				top = top.duplicate()
				var scale := layer.opacity
				for o in range(3, top.size(), 4):
					var la: int = top[o]
					if la != 0: top[o] = int(la * scale + 0.5)
			image.blend_rect(Image.create_from_data(size, size, false, Image.FORMAT_RGBA8, top), whole, Vector2i.ZERO)
		else:
			if native:
				data = image.get_data()
				native = false
			_composite_layer(data, layer)
	return image.get_data() if native else data

func _composite_layer(out: PackedByteArray, layer: Layer) -> void:
	var data := layer.data
	var mode := layer.mode
	var scale := layer.opacity / 255.0
	for o in range(0, data.size(), 4):
		var la: int = data[o + 3]
		if la == 0: continue
		var a := la * scale
		for c in 3:
			var base := out[o + c] / 255.0
			var top := data[o + c] / 255.0
			var mixed: float
			match mode:
				MULTIPLY: mixed = base * top
				SCREEN: mixed = base + top - base * top
				OVERLAY: mixed = 2.0 * base * top if base < 0.5 else 1.0 - 2.0 * (1.0 - base) * (1.0 - top)
				_: mixed = minf(1.0, base + top)
			out[o + c] = int(clampf(base + (mixed - base) * a, 0.0, 1.0) * 255.0 + 0.5)

## The composite colour at one texel (the eyedropper).
func sample(texel: int) -> Color:
	if texel < 0 or texel >= size * size: return Color.BLACK
	var o := texel * 4
	var r := backdrop[o] / 255.0; var g := backdrop[o + 1] / 255.0; var b := backdrop[o + 2] / 255.0
	for layer in layers:
		if not layer.visible or layer.opacity <= 0.0: continue
		var a := layer.data[o + 3] / 255.0 * layer.opacity
		if a <= 0.0: continue
		r += (blend_channel(r, layer.data[o] / 255.0, layer.mode) - r) * a
		g += (blend_channel(g, layer.data[o + 1] / 255.0, layer.mode) - g) * a
		b += (blend_channel(b, layer.data[o + 2] / 255.0, layer.mode) - b) * a
	return Color(r, g, b)

# ------------------------------------------------------------------ history

func _push_pixels(name: String, layer: Layer, before: PackedByteArray, tiles: PackedInt32Array) -> void:
	var old := Image.create_from_data(size, size, false, Image.FORMAT_RGBA8, before)
	var now := Image.create_from_data(size, size, false, Image.FORMAT_RGBA8, layer.data)
	var shots_before: Array[Image] = []
	var shots_after: Array[Image] = []
	for tile in tiles:
		var rect := tile_rect(tile)
		shots_before.append(old.get_region(rect))
		shots_after.append(now.get_region(rect))
	_push({"type": "pixels", "name": name, "layer": layer, "tiles": tiles, "before": shots_before, "after": shots_after,
		"bytes": tiles.size() * TILE * TILE * 8})

func tile_rect(tile: int) -> Rect2i:
	return Rect2i((tile % tiles_side) * TILE, (tile / tiles_side) * TILE, TILE, TILE)

func _push(entry: Dictionary) -> void:
	# A new step drops the redo branch.
	while history.size() > history_index:
		history_bytes -= int(history.pop_back().bytes)
	history_serial += 1
	entry.serial = history_serial
	history.append(entry)
	history_bytes += int(entry.bytes)
	history_index = history.size()
	while history.size() > 1 and (history.size() > HISTORY_STEPS or history_bytes > HISTORY_BYTES):
		history_bytes -= int(history.pop_front().bytes)
		history_index -= 1

func can_undo() -> bool:
	return history_index > 0 and stroke_layer == null

func can_redo() -> bool:
	return history_index < history.size() and stroke_layer == null

func undo() -> bool:
	if not can_undo(): return false
	history_index -= 1
	_apply_entry(history[history_index], false)
	return true

func redo() -> bool:
	if not can_redo(): return false
	_apply_entry(history[history_index], true)
	history_index += 1
	return true

## Undo/redo to a list position (the history panel): steps applied = position.
func jump(position: int) -> void:
	position = clampi(position, 0, history.size())
	while history_index > position and undo(): pass
	while history_index < position and redo(): pass

func _apply_entry(entry: Dictionary, forward: bool) -> void:
	match str(entry.type):
		"pixels":
			var layer: Layer = entry.layer
			var image := Image.create_from_data(size, size, false, Image.FORMAT_RGBA8, layer.data)
			var shots: Array = entry.after if forward else entry.before
			var tiles: PackedInt32Array = entry.tiles
			for i in tiles.size():
				image.blit_rect(shots[i], Rect2i(0, 0, TILE, TILE), tile_rect(tiles[i]).position)
			layer.data = image.get_data()
			layer.revision += 1
		"add":
			if forward:
				layers.insert(int(entry.index), entry.layer); current = int(entry.index)
			else:
				layers.erase(entry.layer); current = clampi(int(entry.index) - 1, 0, layers.size() - 1)
		"delete":
			if forward:
				layers.erase(entry.layer); current = clampi(int(entry.index) - 1, 0, layers.size() - 1)
			else:
				layers.insert(int(entry.index), entry.layer); current = int(entry.index)
		"move":
			var from := int(entry.to) if not forward else int(entry.from)
			var to := int(entry.from) if not forward else int(entry.to)
			var layer := layers[from]
			layers.remove_at(from); layers.insert(to, layer); current = to
		"props":
			var layer: Layer = entry.layer
			layer.set_props(entry.after if forward else entry.before)
			current = maxi(0, layers.find(layer))

func history_names() -> PackedStringArray:
	var out := PackedStringArray()
	for entry in history: out.append(str(entry.name))
	return out
