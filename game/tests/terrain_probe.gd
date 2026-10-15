extends SceneTree
## Step 0 probe for the village ground chunks (plan C step 1). Two parts:
##   --border  (headless): does SurfaceTool.generate_lod keep the border of a sub-region of the ground
##             (a 32 m cell cut by triangle centroid)? Every border vertex and edge must survive at the
##             error bounds a per-zone simplification would use, or neighbouring cells crack.
##   default   (window, logged-in village like perf_probe; pass --server=URL, --hour=H): the ocean's
##             LODs and the triangles it draws, the ground's primitives and draw calls (visible and
##             shadow passes) with the ground and the ocean shown and hidden at a few spots and the
##             village zooms (6.5 / 10 / 22), video memory, and the lights over each ground mesh and
##             over each 32 m chunk.
## Prints TERRAIN_PROBE {...} (and TERRAIN_BORDER {...}).
const Town = preload("res://scripts/town.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const GroundChunks = preload("res://maps/archipelago/ground_chunks.gd")
const SPOTS := [["square", Vector2(-33,37)], ["meadow", Vector2(-18,-31)], ["headland", Vector2(62,-38)], ["camp", Vector2(52,36)], ["lighthouse", Vector2(5,74)], ["falls", Vector2(2,-14)]]
const ZOOMS := [6.5, 10.0, 22.0]
var app: Node

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	if "--border" in OS.get_cmdline_user_args():
		border_test()
		quit(0)
		return
	if not await enter_village():
		quit(1)
		return
	var report := {"hour": app.daylight.current_hour() if is_instance_valid(app.get("daylight")) else -1.0}
	var map: Node3D = app.town.map
	var chunks: Node3D = map.get_node_or_null("Ground")
	# The ground as drawn: the model's ground meshes (before the chunks) or the chunks.
	var grounds := ground_nodes(map).filter(func(g): return (g as MeshInstance3D).mesh != null)
	if chunks: grounds += chunks.get_children().filter(func(c): return String(c.name).begins_with("Chunk_") or String(c.name).begins_with("Shade_"))
	var ocean := [chunks.get_node("Ocean")] if chunks and chunks.has_node("Ocean") else map.find_children("Ocean__central_surface", "MeshInstance3D", true, false)
	report["ocean_lods"] = lods_of((ocean[0] as MeshInstance3D).mesh) if not ocean.is_empty() and (ocean[0] as MeshInstance3D).mesh else []
	report["ground_meshes"] = grounds.size()
	report["ground_tris"] = grounds.reduce(func(n, g): return n+tris_of((g as MeshInstance3D).mesh), 0)
	report["ground_chunks"] = chunks.get_child_count() if chunks else 0
	report["vram_mb"] = vram()
	# Nothing moves on its own meanwhile (time almost stopped; 0 makes the walker's physics divide by it).
	Engine.time_scale = 0.0001
	var views := []
	for spot in SPOTS:
		for zoom in ZOOMS:
			place(spot[1], zoom)
			var all := await info()
			if not ocean.is_empty(): ocean[0].visible = false
			var no_ocean := await info()
			if not ocean.is_empty(): ocean[0].visible = true
			for g in grounds: g.visible = false
			var no_ground := await info()
			for g in grounds: g.visible = true
			views.append({"spot": spot[0], "zoom": zoom, "all": all,
				"ocean_prims": all.prims-no_ocean.prims, "ocean_draws": all.draws-no_ocean.draws,
				"ground_prims": all.prims-no_ground.prims, "ground_draws": all.draws-no_ground.draws,
				"ground_shadow_prims": all.shadow_prims-no_ground.shadow_prims, "ground_shadow_draws": all.shadow_draws-no_ground.shadow_draws})
			print("VIEW %-10s zoom %4.1f prims %7d draws %4d | ocean %6d | ground %7d / %3d draws | ground shadow %7d / %3d" % [spot[0], zoom, all.prims, all.draws,
				all.prims-no_ocean.prims, all.prims-no_ground.prims, all.draws-no_ground.draws, all.shadow_prims-no_ground.shadow_prims, all.shadow_draws-no_ground.shadow_draws])
	report["views"] = views
	report["lights"] = light_pressure(map, grounds)
	Engine.time_scale = 1.0
	print("TERRAIN_PROBE ", JSON.stringify(report))
	quit(0)

## Logs a fresh QA account in and waits for the village (perf_probe.gd).
func enter_village() -> bool:
	var api = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = preload("res://tests/qa_server.gd").url()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): api.base_url = arg.trim_prefix("--server=")
	var login: Dictionary = await api.post("/v1/auth/register", {"username":"terrain_"+str(Time.get_ticks_usec()), "password":"Terrain-probe-password-1"})
	if not login.ok:
		print("LOGIN_FAILED")
		return false
	Engine.set_meta("studio_session", {"token":login.data.token, "url":api.base_url, "room":"home"})
	change_scene_to_file("res://scenes/main.tscn")
	var deadline := Time.get_ticks_msec()+90000
	while Time.get_ticks_msec() < deadline and not (is_instance_valid(current_scene) and current_scene.get("screen") == "village" and is_instance_valid(current_scene.get("player"))):
		await process_frame
	app = current_scene
	if not is_instance_valid(app) or app.get("screen") != "village":
		print("VILLAGE_NOT_READY")
		return false
	await create_timer(4.0).timeout
	return true

func ground_nodes(map: Node) -> Array:
	return map.find_children("*__ground", "MeshInstance3D", true, false)

## The village camera at a spot and zoom, as follow_camera() puts it over the walker standing there
## (set directly: the walker's drawn position only moves at the next physics step).
func place(at: Vector2, zoom: float) -> void:
	app.player.position = Town.point(at, 0.1)
	var focus: Vector3 = Town.point(at, 0.1)+Profile.CAMERA_FOCUS_OFFSET
	app.camera_focus = focus
	app.camera_focus_ready = true
	app.camera_zoom_active = false
	app.camera.size = zoom
	app.camera.position = focus+Profile.CAMERA_OFFSET*Profile.CAMERA_PULLBACK
	app.camera.look_at(focus)

## This view's render counters (a few frames after it changed).
func info() -> Dictionary:
	for i in 4: await process_frame
	var vp := root.get_viewport_rid()
	var r := RenderingServer
	return {"prims": r.viewport_get_render_info(vp, r.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, r.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME),
		"draws": r.viewport_get_render_info(vp, r.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, r.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME),
		"objects": r.viewport_get_render_info(vp, r.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, r.VIEWPORT_RENDER_INFO_OBJECTS_IN_FRAME),
		"shadow_prims": r.viewport_get_render_info(vp, r.VIEWPORT_RENDER_INFO_TYPE_SHADOW, r.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME),
		"shadow_draws": r.viewport_get_render_info(vp, r.VIEWPORT_RENDER_INFO_TYPE_SHADOW, r.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)}

func vram() -> Dictionary:
	var r := RenderingServer
	return {"total": snappedf(r.get_rendering_info(r.RENDERING_INFO_VIDEO_MEM_USED)/1048576.0, 0.1),
		"buffers": snappedf(r.get_rendering_info(r.RENDERING_INFO_BUFFER_MEM_USED)/1048576.0, 0.1),
		"textures": snappedf(r.get_rendering_info(r.RENDERING_INFO_TEXTURE_MEM_USED)/1048576.0, 0.1)}

static func lods_of(mesh: Mesh) -> Array:
	if mesh == null: return []
	var out := []
	for s in mesh.get_surface_count():
		var d := RenderingServer.mesh_get_surface(mesh.get_rid(), s)
		var wide: bool = int(d.vertex_count) > 65535
		out.append({"verts": d.vertex_count, "tris": int(d.index_count)/3,
			"lods": (d.get("lods", []) as Array).map(func(l): return [snappedf(float(l.edge_length), 0.0001), (l.index_data as PackedByteArray).size()/(4 if wide else 2)/3])})
	return out

static func tris_of(mesh: Mesh) -> int:
	if mesh == null: return 0
	var n := 0
	for s in mesh.get_surface_count(): n += RenderingServer.mesh_get_surface(mesh.get_rid(), s).index_count/3
	return n

## Lights (visible omni and spot lights, in tree order) whose range box meets each ground mesh's box
## and each 32 m chunk's box (the chunks' boxes from the ground's triangles the chunks keep).
func light_pressure(map: Node3D, grounds: Array) -> Dictionary:
	var lights := []
	for node in app.find_children("*", "Light3D", true, false):
		if node is DirectionalLight3D or not (node as Light3D).is_visible_in_tree(): continue
		var reach: float = node.omni_range if node is OmniLight3D else (node as SpotLight3D).spot_range
		var at: Vector3 = (node as Node3D).global_position
		lights.append({"name": String(app.get_path_to(node)).get_slice("/", 2)+"/"+String(node.get_parent().name), "box": AABB(at-Vector3.ONE*reach, Vector3.ONE*reach*2.0), "energy": node.light_energy, "mask": (node as Light3D).light_cull_mask})
	var out := {"count": lights.size(), "grounds": {}, "chunks": {}}
	for g: MeshInstance3D in grounds:
		if g.mesh == null or not String(g.name).ends_with("__ground"): continue
		var box := g.global_transform*g.get_aabb()
		var hits := lights.filter(func(l): return (l.box as AABB).intersects(box)).map(func(l): return l.name)
		out.grounds[String(g.name)] = {"count": hits.size(), "first": hits.slice(0, 12)}
	# Per chunk: the lights whose reach meets it, and of those the ones its render layer lets in.
	var chunk_nodes := grounds.filter(func(g): return String(g.name).begins_with("Chunk_"))
	var boxes := {}
	var layers := {}
	if chunk_nodes.is_empty(): boxes = GroundChunks.cell_boxes(grounds)
	for chunk: MeshInstance3D in chunk_nodes:
		boxes[String(chunk.name).trim_prefix("Chunk_")] = chunk.global_transform*chunk.get_aabb()
		layers[String(chunk.name).trim_prefix("Chunk_")] = chunk.layers
	var worst := 0
	var over := 0
	var worst_lit := 0
	for key: String in boxes:
		var near := lights.filter(func(l): return (l.box as AABB).intersects(boxes[key]))
		var lit := near.filter(func(l): return not layers.has(key) or (int(l.mask) & int(layers[key])) != 0)
		out.chunks[key] = [near.size(), lit.size()]
		worst = maxi(worst, near.size())
		worst_lit = maxi(worst_lit, lit.size())
		if lit.size() > 8: over += 1
	out["chunk_worst"] = worst
	out["chunk_worst_lit"] = worst_lit
	out["chunks_over_8"] = over
	# The same with the chunks' boxes grown by a cull margin (the engine pairs lights by the grown box).
	var grown := {}
	for margin in [1.0, 2.0, 4.0]:
		var most := 0
		for key: String in boxes:
			var near := lights.filter(func(l): return (l.box as AABB).intersects((boxes[key] as AABB).grow(margin)) and (not layers.has(key) or (int(l.mask) & int(layers[key])) != 0))
			most = maxi(most, near.size())
		grown[str(margin)] = most
	out["chunk_worst_lit_with_margin"] = grown
	return out

## generate_lod on one 32 m cell of the town ground: are its border vertices and edges kept?
func border_test() -> void:
	var scene: PackedScene = load("res://maps/archipelago/assets/archipelago_terrain_environment_v1.glb")
	var terrain: Node3D = scene.instantiate()
	root.add_child(terrain)
	var report := {}
	for island in ["03_town_common", "01_village_meadow"]:
		var ground := terrain.find_child(island+"__ground", true, false) as MeshInstance3D
		var arrays := ground.mesh.surface_get_arrays(0)
		var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var index: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		# The busiest cell of this island.
		var counts := {}
		for t in range(0, index.size(), 3):
			var cell := GroundChunks.cell_of((verts[index[t]]+verts[index[t+1]]+verts[index[t+2]])/3.0)
			counts[cell] = counts.get(cell, 0)+1
		var best: Vector2i = counts.keys()[0]
		for cell in counts: if counts[cell] > counts[best]: best = cell
		var sub := PackedInt32Array()
		for t in range(0, index.size(), 3):
			var a := verts[index[t]]; var b := verts[index[t+1]]; var c := verts[index[t+2]]
			if maxf(a.y, maxf(b.y, c.y)) < GroundChunks.DROP_BELOW: continue
			if GroundChunks.cell_of((a+b+c)/3.0) == best: sub.append_array(PackedInt32Array([index[t], index[t+1], index[t+2]]))
		# Compact the vertices the cell uses (bit copies), then simplify like a per-zone pass would.
		var remap := {}
		var tool := SurfaceTool.new()
		tool.begin(Mesh.PRIMITIVE_TRIANGLES)
		var local := PackedVector3Array()
		var local_index := PackedInt32Array()
		for i in sub:
			if not remap.has(i):
				remap[i] = local.size()
				local.append(verts[i])
			local_index.append(remap[i])
		var cell_arrays := []
		cell_arrays.resize(Mesh.ARRAY_MAX)
		cell_arrays[Mesh.ARRAY_VERTEX] = local
		cell_arrays[Mesh.ARRAY_INDEX] = local_index
		tool.create_from_arrays(cell_arrays)
		var box := AABB(local[0], Vector3.ZERO)
		for p in local: box = box.expand(p)
		var extent := maxf(box.size.x, maxf(box.size.y, box.size.z))
		var border := border_edges(local_index)
		var border_vertices := {}
		for edge: Vector2i in border: border_vertices[edge.x] = true; border_vertices[edge.y] = true
		var results := []
		for epsilon in [0.005, 0.01, 0.02]:
			var lod := tool.generate_lod(epsilon/extent, 3)
			var used := {}
			for i in lod: used[i] = true
			var kept_vertices := border_vertices.keys().filter(func(v): return used.has(v)).size()
			var lod_edges := {}
			for t in range(0, lod.size(), 3):
				for k in 3:
					var a := lod[t+k]; var b := lod[t+(k+1)%3]
					lod_edges[Vector2i(mini(a, b), maxi(a, b))] = true
			var kept_edges := border.keys().filter(func(e): return lod_edges.has(e)).size()
			results.append({"epsilon_m": epsilon, "tris": local_index.size()/3, "lod_tris": lod.size()/3,
				"border_vertices": border_vertices.size(), "border_vertices_kept": kept_vertices, "border_edges": border.size(), "border_edges_kept": kept_edges})
		report[island] = {"cell": [best.x, best.y], "results": results}
	var locks := true
	for island in report:
		for r in report[island].results: locks = locks and r.border_vertices_kept == r.border_vertices and r.border_edges_kept == r.border_edges
	report["keeps_borders"] = locks
	print("TERRAIN_BORDER ", JSON.stringify(report))

## Edges used by one triangle only (as sorted vertex pairs).
static func border_edges(index: PackedInt32Array) -> Dictionary:
	var uses := {}
	for t in range(0, index.size(), 3):
		for k in 3:
			var a := index[t+k]; var b := index[t+(k+1)%3]
			var e := Vector2i(mini(a, b), maxi(a, b))
			uses[e] = uses.get(e, 0)+1
	var out := {}
	for e in uses: if uses[e] == 1: out[e] = true
	return out
