extends RefCounted
## The village ground cut into chunks on a fixed grid (generated/ground.scn, made by
## tools/bake_archipelago.gd; installed by archipelago.gd when the bake is fresh).
##
## The five island ground meshes (pads levelled by building_layout.gd) are drawn whole today: every
## view draws 200-330 k triangles of ground, most of them off screen or under the sea. Here:
##  - triangles entirely below DROP_BELOW go: the ocean is opaque (its shader writes no ALPHA), so
##    nothing under it is ever seen;
##  - the rest is cut by triangle centroid into CELL metre cells from ORIGIN, one MeshInstance3D per
##    (cell, island): "Chunk_<cx>_<cz>_<island number>". Whole triangles, so no T-junctions; the
##    vertices are copies of the levelled ground's (same floats, same encoding: no compression, no
##    LODs), so a chunk draws exactly the triangles it had, and only chunks in view are drawn.
## Collision is not touched (the ground's colliders stay as they are).
const CELL := 32.0
const ORIGIN := Vector2(-128, -112)
const DROP_BELOW := -0.30
## Except under the waterfall's splash (Waterfall__impact_foam and 2 m round it): its shader fades
## by the depth of what is behind it (waterfall_splash.gdshader), so the ground there stays.
const KEEP_UNDER := [Rect2(-3.4, -11.74, 8.8, 7.6)]
## The dropped triangles that reach SHADE_FROM or higher still cast shadows (positions only, one
## "Shade_<cx>_<cz>" node a cell, drawn in shadow maps alone): near the water line the shadow
## filter reached them from rocks and shores above the water.
const SHADE_FROM := -1.0
## Chunks are culled with this margin (metres): the renderer culls shadow casters against a
## cascade's box, but the shadow filter reads a few texels past it, so a chunk just outside that
## the whole island ground used to put in the shadow map changed shadows at the screen's edges.
const CULL_MARGIN := 4.0
## When true the bake simplifies the chunks within error bounds (ground_simplify.gd).
const SIMPLIFY := false
const FORMAT := 1
## While baking (tools/bake_archipelago.gd), building_layout.gd keeps the float arrays it builds
## each levelled ground from on the ground node under this meta: the chunks copy them, so their
## vertex data is encoded from the same numbers (bit for bit the same on the GPU).
const ARRAYS_META := "ground_chunk_arrays"
static var keep_arrays := false

## Lamp light on the ground. The Compatibility renderer lights an object with at most 8 omni lights.
## Each island's ground was one object, so the lights beyond the first 8 over an island's (sea-wide)
## ground box lit none of it: measured at night (tests/terrain_ab_capture.gd --lampsets, 2026-10-15,
## two sessions alike) 34 of the 39 lights made a pool on the ground and the five DARK_LAMPS did not.
## No chunk is reached by more than 8 lights, so in chunks every lamp would pool. To keep the night
## as it was, the chunks draw on GROUND_LAYER alone and these lamps leave it out of their cull mask,
## set as they are made (environment_layout.gd), before the renderer pairs them: changing a light's
## mask later re-pairs it and reorders the lights of everything it reaches (roads, props).
## --all-lamp-pools (or ALL_LAMP_POOLS): the chunks on layer 1 too, so these five pool as well.
const GROUND_LAYER := 1 << 19
const DARK_LAMPS := ["27_lamp_452", "27_lamp_464", "27_lamp_465", "27_lamp_466", "27_lamp_467"]
const ALL_LAMP_POOLS := false
static var all_lamp_pools := ALL_LAMP_POOLS or "--all-lamp-pools" in OS.get_cmdline_user_args()

## The cull mask for a lamp of the prop named `prop_name` (its other bits as they are).
static func lamp_cull_mask(prop_name: String, mask: int) -> int:
	return mask & ~GROUND_LAYER if prop_name in DARK_LAMPS else mask

## The cell (column, row) a point falls in.
static func cell_of(p: Vector3) -> Vector2i:
	return Vector2i(floori((p.x-ORIGIN.x)/CELL), floori((p.z-ORIGIN.y)/CELL))

## "03" for "03_town_common__ground".
static func island_number(ground: Node) -> String:
	return String(ground.name).substr(0, 2)

static func chunk_name(cell: Vector2i, island: String) -> String:
	return "Chunk_%d_%d_%s" % [cell.x, cell.y, island]

## The arrays a ground surface was built from: the kept floats while baking, else the mesh's own.
static func source_arrays(ground: MeshInstance3D, surface: int) -> Array:
	var kept: Array = ground.get_meta(ARRAYS_META, [])
	if surface < kept.size(): return kept[surface]
	return ground.mesh.surface_get_arrays(surface)

## The triangles a chunk keeps: {Vector2i cell: PackedInt32Array of triangle starts (index offsets)}.
static func bin(verts: PackedVector3Array, index: PackedInt32Array) -> Dictionary:
	var cells := {}
	for t in range(0, index.size(), 3):
		var a := verts[index[t]]
		var b := verts[index[t+1]]
		var c := verts[index[t+2]]
		var centre := (a+b+c)/3.0
		if a.y < DROP_BELOW and b.y < DROP_BELOW and c.y < DROP_BELOW and not kept_under(centre): continue
		var cell := cell_of(centre)
		if not cells.has(cell): cells[cell] = PackedInt32Array()
		cells[cell].append(t)
	return cells

## The dropped triangles that still cast shadows (SHADE_FROM), as index offsets.
static func shaded(verts: PackedVector3Array, index: PackedInt32Array) -> PackedInt32Array:
	var out := PackedInt32Array()
	for t in range(0, index.size(), 3):
		var a := verts[index[t]]
		var b := verts[index[t+1]]
		var c := verts[index[t+2]]
		var high := maxf(a.y, maxf(b.y, c.y))
		if high < DROP_BELOW and high >= SHADE_FROM and not kept_under((a+b+c)/3.0): out.append(t)
	return out

## Under the waterfall's splash (KEEP_UNDER): kept however deep.
static func kept_under(p: Vector3) -> bool:
	for area: Rect2 in KEEP_UNDER:
		if area.has_point(Vector2(p.x, p.z)): return true
	return false

## World boxes of the chunks the ground nodes would be cut into ("<cx>_<cz>_<island>": AABB).
static func cell_boxes(grounds: Array) -> Dictionary:
	var out := {}
	for ground: MeshInstance3D in grounds:
		if ground.mesh == null: continue
		for surface in ground.mesh.get_surface_count():
			var arrays := source_arrays(ground, surface)
			var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var index: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
			var cells := bin(verts, index)
			for cell: Vector2i in cells:
				var box := AABB(verts[index[cells[cell][0]]], Vector3.ZERO)
				for t in cells[cell]:
					for k in 3: box = box.expand(verts[index[t+k]])
				out["%d_%d_%s" % [cell.x, cell.y, island_number(ground)]] = ground.global_transform*box
	return out

## Per-vertex arrays (copied entry by entry for the vertices a chunk uses), with their width.
const PER_VERTEX := {Mesh.ARRAY_VERTEX: 1, Mesh.ARRAY_NORMAL: 1, Mesh.ARRAY_TANGENT: 4, Mesh.ARRAY_COLOR: 1,
	Mesh.ARRAY_TEX_UV: 1, Mesh.ARRAY_TEX_UV2: 1, Mesh.ARRAY_BONES: 4, Mesh.ARRAY_WEIGHTS: 4}

## The vertex index triples of the triangles starting at `starts` (index offsets).
static func triples_of(index: PackedInt32Array, starts: PackedInt32Array) -> PackedInt32Array:
	var out := PackedInt32Array()
	out.resize(starts.size()*3)
	for n in starts.size():
		for k in 3: out[n*3+k] = index[starts[n]+k]
	return out

## One surface's arrays for the triangles `triples` (vertex indices of `arrays`, 3 a triangle), the
## vertices compacted in first-use order.
static func cut(arrays: Array, triples: PackedInt32Array) -> Array:
	var remap := {}
	var order := PackedInt32Array()
	var local := PackedInt32Array()
	local.resize(triples.size())
	for n in triples.size():
		var i := triples[n]
		if not remap.has(i):
			remap[i] = order.size()
			order.append(i)
		local[n] = remap[i]
	var out := []
	out.resize(Mesh.ARRAY_MAX)
	for type: int in PER_VERTEX:
		var source = arrays[type]
		if source == null: continue
		var width: int = PER_VERTEX[type]
		var copy = source.duplicate()
		copy.resize(order.size()*width)
		for j in order.size():
			for w in width: copy[j*width+w] = source[order[j]*width+w]
		out[type] = copy
	out[Mesh.ARRAY_INDEX] = local
	return out

## The chunk scene's root: a Node3D "Ground" with a MeshInstance3D per (cell, island), owned by it
## (ready to pack). `grounds`: the levelled ground nodes with their surface materials set.
## `simplifier` (ground_simplify.gd, or null for the triangles as they are): its
## triangles(arrays, triples, island) gives the triangles a chunk keeps. Each chunk carries the
## triangles it was cut from (vertex indices of its ground) in the meta "source_triangles" for
## validate(); the bake removes it before saving.
static func build(grounds: Array, simplifier: Object = null) -> Node3D:
	var root := Node3D.new()
	root.name = "Ground"
	var stats := {"tris_before": 0, "tris_after": 0, "dropped": 0, "vertices_after": 0, "chunks": 0, "cells": 0, "islands": {}}
	var cells_seen := {}
	var shades := {}
	var sorted := grounds.duplicate()
	sorted.sort_custom(func(a, b): return String(a.name) < String(b.name))
	for ground: MeshInstance3D in sorted:
		var island := island_number(ground)
		var island_stats := {"tris_before": 0, "tris_after": 0, "chunks": 0}
		for surface in ground.mesh.get_surface_count():
			var arrays := source_arrays(ground, surface)
			var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var index: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
			var material := ground.get_surface_override_material(surface)
			if material == null: material = ground.mesh.surface_get_material(surface)
			var cells := bin(verts, index)
			var keys := cells.keys()
			keys.sort()
			island_stats.tris_before += index.size()/3
			for t in shaded(verts, index):
				var at := ground.global_transform
				var cell := cell_of((verts[index[t]]+verts[index[t+1]]+verts[index[t+2]])/3.0)
				if not shades.has(cell): shades[cell] = PackedVector3Array()
				shades[cell].append_array(PackedVector3Array([at*verts[index[t]], at*verts[index[t+1]], at*verts[index[t+2]]]))
			for cell: Vector2i in keys:
				var triples := triples_of(index, cells[cell])
				if simplifier: triples = simplifier.triangles(arrays, triples, island)
				var piece := cut(arrays, triples)
				var mesh := ArrayMesh.new()
				mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, piece)
				mesh.surface_set_material(0, material)
				mesh.surface_set_name(0, String(ground.name))
				var chunk := MeshInstance3D.new()
				chunk.name = chunk_name(cell, island)
				chunk.mesh = mesh
				chunk.transform = ground.global_transform
				for property in ["cast_shadow", "gi_mode", "layers", "lod_bias", "extra_cull_margin", "ignore_occlusion_culling", "transparency",
						"visibility_range_begin", "visibility_range_end", "visibility_range_fade_mode"]:
					chunk.set(property, ground.get(property))
				chunk.set_meta("island", island)
				chunk.set_meta("source_triangles", triples)
				chunk.layers = GROUND_LAYER
				chunk.extra_cull_margin = CULL_MARGIN
				root.add_child(chunk)
				chunk.owner = root
				cells_seen[cell] = true
				island_stats.tris_after += (piece[Mesh.ARRAY_INDEX] as PackedInt32Array).size()/3
				island_stats.chunks += 1
				stats.vertices_after += (piece[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()
		stats.tris_before += island_stats.tris_before
		stats.tris_after += island_stats.tris_after
		stats.chunks += island_stats.chunks
		stats.islands[island] = island_stats
	stats.dropped = stats.tris_before-stats.tris_after
	stats.cells = cells_seen.size()
	stats["shade_tris"] = 0
	var shade_cells := shades.keys()
	shade_cells.sort()
	for cell: Vector2i in shade_cells:
		var mesh := ArrayMesh.new()
		var arrays := []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = shades[cell]
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		var shade := MeshInstance3D.new()
		shade.name = "Shade_%d_%d" % [cell.x, cell.y]
		shade.mesh = mesh
		shade.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
		shade.layers = GROUND_LAYER
		shade.extra_cull_margin = CULL_MARGIN
		root.add_child(shade)
		shade.owner = root
		stats.shade_tris += (shades[cell] as PackedVector3Array).size()/3
	root.set_meta("format", FORMAT)
	root.set_meta("cell", CELL)
	root.set_meta("origin", ORIGIN)
	root.set_meta("drop_below", DROP_BELOW)
	root.set_meta("simplified", simplifier != null)
	if simplifier: stats["simplify"] = simplifier.stats
	root.set_meta("stats", stats)
	return root

## Checks the chunks against the levelled ground they were cut from: every triangle that reaches
## DROP_BELOW is in the chunk of its centroid's cell, every dropped triangle lies wholly below
## DROP_BELOW, and every chunk vertex is one of the ground's, every attribute equal as floats and as
## the bytes the GPU gets. Unsimplified (meta "simplified" false) the chunks hold exactly the cell's
## triangles; simplified, the triangles the simplifier gave (meta "source_triangles"; without it, as
## after loading, only that each chunk vertex's bytes are some ground vertex's).
## Returns {"ok", "failures": [...], ...counts}.
static func validate(root: Node3D, grounds: Array) -> Dictionary:
	var failures := []
	var kept := 0
	var dropped := 0
	var checked_vertices := 0
	var simplified: bool = root.get_meta("simplified", false)
	var by_name := {}
	for chunk in root.get_children(): by_name[String(chunk.name)] = chunk
	for ground: MeshInstance3D in grounds:
		var island := island_number(ground)
		for surface in ground.mesh.get_surface_count():
			var arrays := ground.mesh.surface_get_arrays(surface)
			var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var index: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
			var cells := bin(verts, index)
			var in_cells := 0
			for cell: Vector2i in cells: in_cells += cells[cell].size()
			dropped += index.size()/3-in_cells
			# Dropped means wholly below the line.
			var below := 0
			for t in range(0, index.size(), 3):
				if maxf(verts[index[t]].y, maxf(verts[index[t+1]].y, verts[index[t+2]].y)) < DROP_BELOW and not kept_under((verts[index[t]]+verts[index[t+1]]+verts[index[t+2]])/3.0): below += 1
			if below != index.size()/3-in_cells: failures.append("%s: %d triangles dropped, %d lie below %.2f m" % [ground.name, index.size()/3-in_cells, below, DROP_BELOW])
			var source := RenderingServer.mesh_get_surface(ground.mesh.get_rid(), surface)
			# Simplified chunks without their source list: any of the ground's vertices, by bytes.
			var known := {}
			for cell: Vector2i in cells:
				var chunk := by_name.get(chunk_name(cell, island)) as MeshInstance3D
				if chunk == null:
					failures.append("missing chunk %s" % chunk_name(cell, island))
					continue
				var piece := chunk.mesh.surface_get_arrays(0)
				var chunk_index: PackedInt32Array = piece[Mesh.ARRAY_INDEX]
				var target := RenderingServer.mesh_get_surface(chunk.mesh.get_rid(), 0)
				var expected: PackedInt32Array = triples_of(index, cells[cell]) if not simplified else chunk.get_meta("source_triangles", PackedInt32Array())
				var bad := 0
				if expected.is_empty():
					if known.is_empty():
						for i in verts.size(): known[vertex_bytes(source, i)] = true
					for j in int(target.vertex_count):
						checked_vertices += 1
						if not known.has(vertex_bytes(target, j)): bad += 1
					kept += chunk_index.size()/3
				elif chunk_index.size() != expected.size():
					failures.append("%s: %d triangles, %d expected" % [chunk.name, chunk_index.size()/3, expected.size()/3])
					continue
				else:
					kept += expected.size()/3
					for n in expected.size():
						var i := expected[n]
						var j := chunk_index[n]
						checked_vertices += 1
						for type: int in PER_VERTEX:
							if arrays[type] == null: continue
							var width: int = PER_VERTEX[type]
							for w in width:
								if arrays[type][i*width+w] != piece[type][j*width+w]: bad += 1
						if not same_bytes(source, i, target, j): bad += 1
				if bad > 0: failures.append("%s: %d vertex values differ from the ground's" % [chunk.name, bad])
	var held := 0
	for chunk in root.get_children():
		if String(chunk.name).begins_with("Chunk_"): held += (chunk as MeshInstance3D).mesh.surface_get_arrays(0)[Mesh.ARRAY_INDEX].size()/3
	if held != kept: failures.append("the chunks hold %d triangles, %d expected" % [held, kept])
	# The shadow casters: the dropped triangles reaching SHADE_FROM, cell by cell, the same positions.
	var shades := {}
	var in_order := grounds.duplicate()
	in_order.sort_custom(func(a, b): return String(a.name) < String(b.name))
	for ground: MeshInstance3D in in_order:
		for surface in ground.mesh.get_surface_count():
			var arrays := ground.mesh.surface_get_arrays(surface)
			var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var index: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
			for t in shaded(verts, index):
				var cell := cell_of((verts[index[t]]+verts[index[t+1]]+verts[index[t+2]])/3.0)
				var key := "Shade_%d_%d" % [cell.x, cell.y]
				if not shades.has(key): shades[key] = PackedVector3Array()
				var at := ground.global_transform
				shades[key].append_array(PackedVector3Array([at*verts[index[t]], at*verts[index[t+1]], at*verts[index[t+2]]]))
	var shade_tris := 0
	for key: String in shades:
		var node := by_name.get(key) as MeshInstance3D
		if node == null or node.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY:
			failures.append("%s missing or drawn" % key)
			continue
		var held_faces: PackedVector3Array = node.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
		if held_faces != shades[key]: failures.append("%s: its faces differ from the ground's" % key)
		shade_tris += held_faces.size()/3
	for child in root.get_children():
		if String(child.name).begins_with("Shade_") and not shades.has(String(child.name)): failures.append("%s casts nothing of the ground's" % child.name)
	return {"ok": failures.is_empty(), "failures": failures.slice(0, 12), "kept": kept, "dropped": dropped, "shade_tris": shade_tris, "vertices_checked": checked_vertices}

## The ocean surface keeps a 204,800-triangle base the view never gets close enough to draw: the sea
## is flat, so even its coarsest LOD is under a pixel off at every village zoom (it draws 1,600
## triangles). Its LODs at least OCEAN_FINEST_LOD coarse (edge length) are kept, the finest of them
## as the base, with the same indices and vertex bytes (only the vertices they use), as the node
## "Ocean" under `root` (the model's ocean node's settings and material). The engine picks among them
## as it did; the finer LODs it never picks at these zooms are left out.
const OCEAN_FINEST_LOD := 0.001
static func add_ocean(root: Node3D, ocean: MeshInstance3D) -> Dictionary:
	var source := RenderingServer.mesh_get_surface(ocean.mesh.get_rid(), 0)
	var lods := []
	for lod: Dictionary in source.get("lods", []):
		if float(lod.edge_length) >= OCEAN_FINEST_LOD: lods.append([float(lod.edge_length), indices_of(lod.index_data, int(source.vertex_count))])
	if lods.is_empty(): return {"ok": false, "failures": ["the ocean has no LOD as coarse as %s" % OCEAN_FINEST_LOD]}
	var remap := {}
	var order := PackedInt32Array()
	var remapped := []
	for lod: Array in lods:
		var local := PackedInt32Array()
		local.resize((lod[1] as PackedInt32Array).size())
		var n := 0
		for i in lod[1]:
			if not remap.has(i):
				remap[i] = order.size()
				order.append(i)
			local[n] = remap[i]
			n += 1
		remapped.append(local)
	# The kept vertices' bytes as they are (decoded and encoded again, a tangent can move by a bit).
	var count := int(source.vertex_count)
	var vertex: PackedByteArray = source.vertex_data
	var attribute: PackedByteArray = source.get("attribute_data", PackedByteArray())
	var position := 8 if int(source.format) & Mesh.ARRAY_FLAG_COMPRESS_ATTRIBUTES else 12
	var rest := vertex.size()/count-position
	var stride := attribute.size()/count
	var positions := PackedByteArray()
	var normals := PackedByteArray()
	var attributes := PackedByteArray()
	for i in order:
		positions.append_array(vertex.slice(i*position, (i+1)*position))
		if rest > 0: normals.append_array(vertex.slice(count*position+i*rest, count*position+(i+1)*rest))
		if stride > 0: attributes.append_array(attribute.slice(i*stride, (i+1)*stride))
	var surface := {"primitive": Mesh.PRIMITIVE_TRIANGLES, "format": source.format, "vertex_data": positions+normals, "attribute_data": attributes,
		"vertex_count": order.size(), "index_data": index_bytes(remapped[0], order.size()), "index_count": remapped[0].size(),
		"aabb": source.aabb, "uv_scale": source.get("uv_scale", Vector4.ZERO), "material": ocean.mesh.surface_get_material(0), "name": String(ocean.name)}
	var coarser := []
	for k in range(1, lods.size()): coarser.append_array([lods[k][0], index_bytes(remapped[k], order.size())])
	surface["lods"] = coarser
	var mesh := ArrayMesh.new()
	mesh.set("_surfaces", [surface])
	var node := MeshInstance3D.new()
	node.name = "Ocean"
	node.mesh = mesh
	node.transform = ocean.global_transform
	for property in ["cast_shadow", "gi_mode", "layers", "lod_bias", "extra_cull_margin", "ignore_occlusion_culling", "transparency",
			"visibility_range_begin", "visibility_range_end", "visibility_range_fade_mode", "material_override", "sorting_offset"]:
		node.set(property, ocean.get(property))
	root.add_child(node)
	node.owner = root
	var check := validate_ocean(mesh, ocean.mesh)
	return {"ok": check.ok, "failures": check.failures, "vertices": order.size(), "base_tris": remapped[0].size()/3,
		"lods": lods.map(func(l): return [l[0], (l[1] as PackedInt32Array).size()/3]), "tris_before": int(source.index_count)/3, "vertices_before": source.vertex_count}

## The ocean mesh against the model's: each of its LODs (the base first) is the model's LOD of the same
## edge length, triangle by triangle, with the same vertex bytes; same bounds and UV scale.
static func validate_ocean(mesh: Mesh, model: Mesh) -> Dictionary:
	var failures := []
	var source := RenderingServer.mesh_get_surface(model.get_rid(), 0)
	var target := RenderingServer.mesh_get_surface(mesh.get_rid(), 0)
	if target.aabb != source.aabb or target.get("uv_scale") != source.get("uv_scale"): failures.append("ocean bounds or UV scale differ")
	var wanted := {}
	for lod: Dictionary in source.get("lods", []): wanted[float(lod.edge_length)] = indices_of(lod.index_data, int(source.vertex_count))
	var made := [[-1.0, indices_of(target.index_data, int(target.vertex_count))]]
	for lod: Dictionary in target.get("lods", []): made.append([float(lod.edge_length), indices_of(lod.index_data, int(target.vertex_count))])
	# The base is the finest kept LOD: the model's LOD whose edge length is just under the next one's.
	var finest := INF
	for lod: Dictionary in source.get("lods", []): if float(lod.edge_length) >= OCEAN_FINEST_LOD: finest = minf(finest, float(lod.edge_length))
	made[0][0] = finest
	for entry: Array in made:
		if not wanted.has(entry[0]):
			failures.append("ocean LOD %s is not one of the model's" % entry[0])
			continue
		var a: PackedInt32Array = wanted[entry[0]]
		var b: PackedInt32Array = entry[1]
		if a.size() != b.size():
			failures.append("ocean LOD %s: %d indices, the model's %d" % [entry[0], b.size(), a.size()])
			continue
		var bad := 0
		for n in a.size(): if vertex_bytes(source, a[n]) != vertex_bytes(target, b[n]): bad += 1
		if bad > 0: failures.append("ocean LOD %s: %d corners differ" % [entry[0], bad])
	var kept := 0
	for lod: Dictionary in source.get("lods", []): if float(lod.edge_length) >= OCEAN_FINEST_LOD: kept += 1
	if made.size() != kept: failures.append("ocean: %d LODs, the model has %d at least %s" % [made.size(), kept, OCEAN_FINEST_LOD])
	if int(target.format) != int(source.format): failures.append("ocean format differs")
	return {"ok": failures.is_empty(), "failures": failures, "lods": made.size()}

## Indices as a surface's index buffer bytes (32-bit above 65,535 vertices, else 16-bit).
static func index_bytes(indices: PackedInt32Array, vertex_count: int) -> PackedByteArray:
	if vertex_count > 65535: return indices.to_byte_array()
	var out := PackedByteArray()
	out.resize(indices.size()*2)
	for i in indices.size(): out.encode_u16(i*2, indices[i])
	return out

## A surface's index buffer bytes as indices (32-bit above 65,535 vertices, else 16-bit).
static func indices_of(data: PackedByteArray, vertex_count: int) -> PackedInt32Array:
	if vertex_count > 65535: return data.to_int32_array()
	var out := PackedInt32Array()
	out.resize(data.size()/2)
	for i in out.size(): out[i] = data.decode_u16(i*2)
	return out

## The GPU bytes of vertex `i` of surface `a` and vertex `j` of surface `b` are the same (vertex and
## attribute streams, same format).
static func same_bytes(a: Dictionary, i: int, b: Dictionary, j: int) -> bool:
	if int(a.format) != int(b.format): return false
	return vertex_bytes(a, i) == vertex_bytes(b, j)

## Vertex `i`'s bytes in a surface's buffers. The vertex stream holds every position first (12 bytes,
## 8 compressed), then every normal and tangent; the attribute stream (UVs, colours) is interleaved.
static func vertex_bytes(surface: Dictionary, i: int) -> PackedByteArray:
	var count := int(surface.vertex_count)
	var vertex: PackedByteArray = surface.get("vertex_data", PackedByteArray())
	var attribute: PackedByteArray = surface.get("attribute_data", PackedByteArray())
	var position := 8 if int(surface.format) & Mesh.ARRAY_FLAG_COMPRESS_ATTRIBUTES else 12
	var rest := vertex.size()/count-position
	var out := vertex.slice(i*position, (i+1)*position)
	if rest > 0: out.append_array(vertex.slice(count*position+i*rest, count*position+(i+1)*rest))
	var stride := attribute.size()/count
	if stride > 0: out.append_array(attribute.slice(i*stride, (i+1)*stride))
	return out
