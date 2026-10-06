extends SceneTree
## Survival map check (maps/survival/survival_map.gd through scripts/biomes.gd), standalone: no server.
## Reads server states written by tools/survival_map_states.py, builds each map the way main.gd does
## (world node, resource roots with a "kind" meta, orthographic follow camera at CAMERA_DEFAULT), then:
##  - walkability on the server's collision rules from camp to every resource and around obstacles,
##    and no solid-looking decor standing where the walker can go;
##  - captures from the game camera, day and night: artifacts/survival-<map>-<view>-<day|night>.png and
##    artifacts/survival-maps-sheet.png;
##  - performance at 1280x800 (vsync off): frame times standing at camp and walking a loop, draw calls,
##    primitives, video memory -> artifacts/survival-maps/report.json.
## Needs a window:
##   .tools/server-venv/Scripts/python.exe tools/survival_map_states.py
##   Godot --path game --script res://tests/survival_maps.gd -- [--maps=forest,quarry,frost] [--no-perf]
const Biomes = preload("res://scripts/biomes.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const MOCK := "extends Node3D\nvar camera: Camera3D\nvar environment: Environment\nvar sun: DirectionalLight3D\nvar player: Node3D\nvar run := {}\n"
const FOLIAGE := ["bush_round","fern_clump","mushroom_cluster","white_flowers","yellow_flowers","pink_flowers","reeds","dry_shrub","frost_shrub","berry_bush","fiber_grass"]
const VIEWS := {
	"forest":{"camp":Vector2(0,1.4),"ruin":Vector2(-7.5,-9.5),"pond":Vector2(6.5,6.0),"edge":Vector2(2,-19)},
	"quarry":{"camp":Vector2(0,1.4),"crane":Vector2(7.5,-11.0),"fissure":Vector2(-7.0,-3.0),"edge":Vector2(-4,-19)},
	"frost":{"camp":Vector2(0,1.4),"shrine":Vector2(-1.0,-11.5),"lake":Vector2(-6.0,-2.0),"edge":Vector2(10,-19)},
}
var host: Node3D
var world: Node3D
var camera: Camera3D
var env: Environment
var sun: DirectionalLight3D
var player: Node3D
var map: Node3D
var failures: Array[String] = []
var report := {"viewport":[1280,800],"maps":{}}
var sheet_tiles: Array[Image] = []

func _initialize() -> void:
	call_deferred("run")

func artifact(file: String) -> String:
	return ProjectSettings.globalize_path("res://../artifacts/"+file)

func run() -> void:
	var maps := ["forest","quarry","frost"]
	var perf := true
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--maps="): maps = Array(arg.trim_prefix("--maps=").split(","))
		if arg == "--no-perf": perf = false
	DisplayServer.window_set_size(Vector2i(1280,800))
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	root.size = Vector2i(1280,800)
	DirAccess.make_dir_recursive_absolute(artifact("survival-maps"))
	for map_id in maps:
		await check_map(map_id,perf)
	contact_sheet()
	report["failures"] = failures
	FileAccess.open(artifact("survival-maps/report.json"),FileAccess.WRITE).store_string(JSON.stringify(report,"  "))
	print("SURVIVAL_MAPS ","FAIL " if failures.size() else "OK ",failures)
	quit(1 if failures.size() else 0)

func setup(state: Dictionary) -> void:
	if is_instance_valid(host):
		host.queue_free()
		await process_frame
	var script := GDScript.new()
	script.source_code = MOCK
	script.reload()
	host = Node3D.new()
	host.set_script(script)
	root.add_child(host)
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = Profile.CAMERA_DEFAULT
	camera.current = true
	host.add_child(camera)
	var we := WorldEnvironment.new()
	env = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	we.environment = env
	host.add_child(we)
	sun = DirectionalLight3D.new()
	sun.shadow_enabled = true
	# main.gd's medium preset after fit_shadow_to_camera().
	var back := Profile.CAMERA_OFFSET.length()*(Profile.CAMERA_PULLBACK-1.0)
	var base := sun.directional_shadow_max_distance
	sun.directional_shadow_max_distance = base+back
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS
	sun.directional_shadow_split_1 = (back+base*0.25)/(base+back)
	host.add_child(sun)
	host.set("camera",camera); host.set("environment",env); host.set("sun",sun); host.set("run",state)
	root.get_viewport().msaa_3d = Viewport.MSAA_2X
	world = Node3D.new()
	host.add_child(world)
	map = Biomes.build(world,state)
	player = _make_player()
	world.add_child(player)
	host.set("player",player)
	# main.gd: one root per resource with a "kind" meta; the map swaps in its Tripo models.
	for n in state.nodes:
		var node_root := Node3D.new()
		world.add_child(node_root)
		node_root.position = Vector3(n.x,0,n.z)
		var stub := MeshInstance3D.new(); stub.mesh = SphereMesh.new(); node_root.add_child(stub)
		node_root.set_meta("kind",n.kind)
		node_root.set_meta("resource_id",n.id)

func _make_player() -> Node3D:
	var body: Node3D
	var script := load("res://scripts/player.gd") as GDScript
	if script:
		body = script.new()
		body.set("visual_only",true)
	if body == null:
		body = Node3D.new()
		var capsule := MeshInstance3D.new(); capsule.mesh = CapsuleMesh.new(); capsule.position.y = 0.9
		body.add_child(capsule)
	return body

func place(at: Vector2, size := Profile.CAMERA_DEFAULT) -> void:
	player.position = Vector3(at.x,0.03,at.y)
	var focus := player.position+Profile.CAMERA_FOCUS_OFFSET
	camera.size = size
	camera.position = focus+Profile.CAMERA_OFFSET*Profile.CAMERA_PULLBACK
	camera.look_at(focus)

func set_time(progress: float) -> void:
	var run: Dictionary = host.get("run")
	run["day_progress"] = progress
	run["night"] = progress >= 0.65
	map.night = 1.0 if progress >= 0.7 else 0.0
	map.dusk = 0.0
	map._process(0.0)

func capture(file: String, settle := 6) -> Image:
	for i in settle: await process_frame
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	image.save_png(artifact(file))
	print("CAPTURE ",file)
	return image

func check_map(map_id: String, perf: bool) -> void:
	var path := artifact("survival-maps/state-%s.json" % map_id)
	if not FileAccess.file_exists(path):
		failures.append("missing state "+path); return
	var state: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	var started := Time.get_ticks_msec()
	await setup(state)
	var build_ms := Time.get_ticks_msec()-started
	for i in 4: await process_frame
	var entry := {"build_ms":build_ms,"map_report":map.report()}
	entry["walkability"] = walkability(state)
	entry["decor_in_walkable_area"] = decor_check(state)
	var views: Dictionary = VIEWS[map_id]
	for view in views:
		place(views[view])
		set_time(0.3)
		var image := await capture("survival-%s-%s-day.png" % [map_id,view])
		if view in ["camp","edge"] or views.keys().find(view) == 1: sheet_tiles.append(image)
		if view in ["camp",views.keys()[1]]:
			set_time(0.82)
			var night_image := await capture("survival-%s-%s-night.png" % [map_id,view])
			if view == "camp": sheet_tiles.append(night_image)
	place(views.camp,Profile.CAMERA_MAX)
	set_time(0.3)
	await capture("survival-%s-wide-day.png" % map_id)
	if perf:
		entry["performance"] = await measure(views)
	report.maps[map_id] = entry
	print("MAP ",map_id," ",JSON.stringify(entry))

func clear_at(state: Dictionary, x: float, z: float) -> bool:
	if Vector2(x,z).length() < 1.05: return false
	for o in state.obstacles:
		if Vector2(x-o.x,z-o.z).length() < float(o.radius)+0.25: return false
	for n in state.nodes:
		if n.kind in ["tree","stone"] and n.quantity > 0 and Vector2(x-n.x,z-n.z).length() < 0.85: return false
	return true

## The server's own collision rules on a 0.4 m grid, flood-filled from the spawn point.
func walkability(state: Dictionary) -> Dictionary:
	var limit := float(map.bounds)
	var step := 0.4
	var size := int(limit*2.0/step)+1
	var seen := {}
	var start := Vector2i(roundi((float(state.x)+limit)/step),roundi((float(state.z)+limit)/step))
	var queue: Array[Vector2i] = [start]
	seen[start] = true
	var head := 0
	while head < queue.size():
		var c := queue[head]; head += 1
		for d in [Vector2i(1,0),Vector2i(-1,0),Vector2i(0,1),Vector2i(0,-1)]:
			var n: Vector2i = c+d
			if seen.has(n) or n.x < 0 or n.y < 0 or n.x >= size or n.y >= size: continue
			if clear_at(state,-limit+n.x*step,-limit+n.y*step):
				seen[n] = true
				queue.append(n)
	var cells: Array[Vector2] = []
	for c in seen: cells.append(Vector2(-limit+c.x*step,-limit+c.y*step))
	var unreachable := []
	for n in state.nodes:
		var ok := false
		for p in cells:
			if p.distance_to(Vector2(n.x,n.z)) <= 2.0: ok = true; break
		if not ok: unreachable.append(n.id)
	var enclosed := []
	for o in state.obstacles:
		var sectors := {}
		for p in cells:
			var d := p.distance_to(Vector2(o.x,o.z))
			if d > float(o.radius)+0.3 and d < float(o.radius)+1.6:
				sectors[int(floor((atan2(p.y-o.z,p.x-o.x)+PI)/TAU*8.0))%8] = true
		# Sides that run into a neighbouring solid (a pond made of three circles) count as the union's.
		for k in 8:
			var a := (k+0.5)/8.0*TAU-PI
			var q := Vector2(o.x,o.z)+Vector2(cos(a),sin(a))*(float(o.radius)+0.8)
			for other in state.obstacles:
				if other != o and q.distance_to(Vector2(other.x,other.z)) < float(other.radius)+0.3: sectors[k] = true
		var touches_edge := maxf(absf(o.x),absf(o.z))+float(o.radius) > limit-1.2
		if sectors.size() < (4 if touches_edge else 7): enclosed.append([o.kind if o.has("kind") else "?",o.x,o.z,sectors.size()])
	if not unreachable.is_empty(): failures.append("%s unreachable nodes %s" % [state.map_id,unreachable])
	if not enclosed.is_empty(): failures.append("%s obstacles not walkable around %s" % [state.map_id,enclosed])
	return {"reachable_cells":cells.size(),"nodes":state.nodes.size(),"unreachable":unreachable,"obstacles":state.obstacles.size(),"not_walkable_around":enclosed}

## Every non-foliage prop taller than 0.6 m must stand outside the walkable square or on a solid circle.
func decor_check(state: Dictionary) -> Dictionary:
	var limit := float(map.bounds)
	var bad := []
	var checked := 0
	var props_root := map.get_node("Props")
	for node in props_root.get_children():
		var mmi := node as MultiMeshInstance3D
		var id := str(mmi.get_meta("prop",""))
		if id in FOLIAGE: continue
		var mm := mmi.multimesh
		var aabb := mm.mesh.get_aabb()
		for i in mm.instance_count:
			var xf := mm.get_instance_transform(i)
			var tall := aabb.end.y*xf.basis.get_scale().y
			if tall < 0.6: continue
			checked += 1
			var p := Vector2(xf.origin.x,xf.origin.z)
			if maxf(absf(p.x),absf(p.y)) > limit+0.5: continue
			var covered := false
			for o in state.obstacles:
				if p.distance_to(Vector2(o.x,o.z)) < float(o.radius)+0.6: covered = true; break
			if not covered: bad.append([id,snappedf(p.x,0.1),snappedf(p.y,0.1),snappedf(tall,0.01)])
	# Single authored props (landmarks, camp kit) too.
	for node in map.get_children():
		if not (node is MeshInstance3D) or (node as MeshInstance3D).mesh == null: continue
		var mi := node as MeshInstance3D
		if not map.props.has(str(mi.name)): continue  # ground, water, rails: not props
		if str(mi.name) == "forest_ruin": continue  # the arch opening is walkable; its pillars are server circles
		if str(mi.name) in FOLIAGE or mi.get_aabb().end.y*mi.scale.y < 0.6: continue
		checked += 1
		var q := Vector2(mi.position.x,mi.position.z)
		if maxf(absf(q.x),absf(q.y)) > limit+0.5: continue
		var on_solid := false
		for o in state.obstacles:
			if q.distance_to(Vector2(o.x,o.z)) < float(o.radius)+0.6: on_solid = true; break
		if not on_solid: bad.append([str(mi.name),snappedf(q.x,0.1),snappedf(q.y,0.1)])
	if not bad.is_empty(): failures.append("%s solid decor in walkable area %s" % [state.map_id,bad.slice(0,6)])
	return {"checked_tall_instances":checked,"in_walkable_area":bad}

func measure(views: Dictionary) -> Dictionary:
	place(views.camp)
	set_time(0.3)
	for i in 90: await process_frame
	var standing := await frames(360,func(_i): pass)
	var info := {
		"draw_calls":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
		"primitives":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
		"objects":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME),
		"video_memory_mb":snappedf(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_VIDEO_MEM_USED)/1048576.0,0.1),
	}
	# Walk a loop around camp at run speed with the follow camera (chunk culling, LOD, shadows move).
	var loop := func(i: int) -> void:
		var a := i/360.0*TAU
		place(Vector2(cos(a)*12.0,sin(a)*12.0))
	var walking := await frames(360,loop)
	set_time(0.82)
	for i in 30: await process_frame
	var night_stats := await frames(240,func(_i): pass)
	place(views.camp,Profile.CAMERA_MAX)
	set_time(0.3)
	for i in 30: await process_frame
	var zoomed := await frames(240,func(_i): pass)
	var zoom_info := {"draw_calls":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
		"primitives":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)}
	return {"standing":standing,"walking":walking,"night":night_stats,"zoomed_out":zoomed,"camp_frame":info,"zoomed_frame":zoom_info}

func frames(count: int, step: Callable) -> Dictionary:
	var times: Array[float] = []
	var last := Time.get_ticks_usec()
	for i in count:
		step.call(i)
		await process_frame
		var now := Time.get_ticks_usec()
		times.append((now-last)/1000.0)
		last = now
	times.sort()
	var total := 0.0
	for t in times: total += t
	return {"median_ms":snappedf(times[times.size()/2],0.01),"p95_ms":snappedf(times[int(times.size()*0.95)],0.01),
		"p99_ms":snappedf(times[int(times.size()*0.99)],0.01),"max_ms":snappedf(times[-1],0.01),"mean_ms":snappedf(total/times.size(),0.01)}

func contact_sheet() -> void:
	if sheet_tiles.is_empty(): return
	var columns := 4
	var w := 480; var h := 300
	var rows := int(ceil(sheet_tiles.size()/float(columns)))
	var sheet := Image.create(w*columns,h*rows,false,Image.FORMAT_RGB8)
	for i in sheet_tiles.size():
		var tile := sheet_tiles[i].duplicate() as Image
		tile.resize(w,h,Image.INTERPOLATE_LANCZOS)
		sheet.blit_rect(tile,Rect2i(0,0,w,h),Vector2i((i%columns)*w,(i/columns)*h))
	sheet.save_png(artifact("survival-maps-sheet.png"))
	print("CAPTURE survival-maps-sheet.png")
