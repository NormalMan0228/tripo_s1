extends SceneTree
## Captures for the village ground chunks (maps/archipelago/ground_chunks.gd). Needs a window and a QA
## server (--server=URL); the village opens at --hour=H. Images go to --out=DIR (default
## artifacts/terrain_p2/ab); tools/terrain_ab_diff.py compares them.
##   --views     this build as it is: every spot at the village zooms (6.5 / 10 / 22) with the lights
##               as the game has them, then with every omni light hidden ("<label>_<spot>_z<zoom>_h<hour>.png"
##               and "..._dark.png"). --label=NAME names them; --zooms=10 limits the zooms.
##   --ab        in one process with time held still, the chunked ground (B) against the levelled
##               ground the game drew before (A, rebuilt here as building_layout.gd levels it, with the
##               ocean's own mesh): every spot and zoom at hour 12 and 21 with every omni light hidden
##               (strict), then with the lights on (report only); "ab_h<hour>_<spot>_z<zoom>_<A|B>[_lit].png".
##               Then the crack test: both grounds white and unshaded on magenta from above ("crack_<A|B>.png").
##   --lampsets  which lights reach the ground: the ground alone from above, each light's energy off in
##               turn; prints LAMP_SETS {"<island>": [lights that change its ground]}.
## Prints AB_CAPTURE {...} when done.
const Town = preload("res://scripts/town.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const ALL_SPOTS := [["square", Vector2(-33,37)], ["cafe", Vector2(-60.2,-27.6)], ["meadow", Vector2(-18,-31)], ["headland", Vector2(62,-38)],
	["camp", Vector2(52,36)], ["lighthouse", Vector2(5,74)], ["falls", Vector2(2,-14)], ["shore", Vector2(-80,10)],
	["south_lamps", Vector2(-25,57)], ["bridge_lamps", Vector2(16,27)], ["camp_lamp", Vector2(66,44)]]
var app: Node
var out_dir := "res://../artifacts/terrain_p2/ab/"
var label := "cap"
var zooms := [6.5, 10.0, 22.0]
var report := {}
var only := []

var SPOTS: Array:
	get: return ALL_SPOTS.filter(func(spot): return only.is_empty() or only.has(spot[0]))

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="): out_dir = arg.trim_prefix("--out=").trim_suffix("/")+"/"
		if arg.begins_with("--label="): label = arg.trim_prefix("--label=")
		if arg.begins_with("--zooms="): zooms = Array(arg.trim_prefix("--zooms=").split(",")).map(func(z): return float(z))
		if arg.begins_with("--spots="): only = Array(arg.trim_prefix("--spots=").split(","))
	call_deferred("run")

func run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_dir))
	if not await enter_village():
		quit(1)
		return
	var args := OS.get_cmdline_user_args()
	# Time stopped: residents, water and clouds hold still (the hidden walker rests: its physics divides
	# by the step); the camera stays where place() puts it (the follow view would drift it to the walker).
	app.player.process_mode = Node.PROCESS_MODE_DISABLED
	Engine.time_scale = 0.0
	# The boats bob on the wall clock.
	var props: Node = app.town.map.get_node_or_null("Environment")
	if props: props.floating_boats.clear()
	free_camera(true)
	for arg in args:
		if arg.begins_with("--switch-hour="):
			set_hour(float(arg.trim_prefix("--switch-hour=")))
			for i in 30: await process_frame
	# --no-sun-shadows: tells shadow-map differences from the rest.
	if "--no-sun-shadows" in args:
		for sun in app.find_children("*", "DirectionalLight3D", true, false): sun.shadow_enabled = false
	if "--views" in args: await views()
	if "--lampsets" in args: await lamp_sets()
	if "--ab" in args: await ab()
	Engine.time_scale = 1.0
	app.player.process_mode = Node.PROCESS_MODE_INHERIT
	print("AB_CAPTURE ", JSON.stringify(report))
	quit(0)

func enter_village() -> bool:
	var api = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = preload("res://tests/qa_server.gd").url()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): api.base_url = arg.trim_prefix("--server=")
	var login: Dictionary = await api.post("/v1/auth/register", {"username":"terrain_"+str(Time.get_ticks_usec()), "password":"Terrain-capture-password-1"})
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
	# The opening line, the guide and the HUD stay out of the pictures.
	await create_timer(4.0).timeout
	for layer in app.find_children("*", "CanvasLayer", true, false): layer.visible = false
	app.player.visible = false
	return true

func place(at: Vector2, zoom: float) -> void:
	var focus: Vector3 = Town.point(at, 0.1)+Profile.CAMERA_FOCUS_OFFSET
	app.camera_focus = focus
	app.camera_focus_ready = true
	app.camera_zoom_active = false
	app.camera.size = zoom
	app.camera.position = focus+Profile.CAMERA_OFFSET*Profile.CAMERA_PULLBACK
	app.camera.look_at(focus)

func shot(file: String) -> Image:
	for i in 6: await process_frame
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	if not file.is_empty(): image.save_png(ProjectSettings.globalize_path(out_dir+file))
	return image

func hour() -> int:
	return int(round(app.daylight.current_hour()))

func set_hour(h: float) -> void:
	app.daylight.override_hour = h
	app.daylight.refresh(true)

## Omni and spot lights (not the sun or the moon).
func point_lights() -> Array:
	return app.find_children("*", "Light3D", true, false).filter(func(l): return not l is DirectionalLight3D)

func views() -> void:
	var h := hour()
	for spot in SPOTS:
		for zoom in zooms:
			place(spot[1], zoom)
			await shot("%s_%s_z%s_h%d.png" % [label, spot[0], str(zoom), h])
	# The same without any omni light (they are not shown again: showing them pairs them anew).
	for light in point_lights(): light.visible = false
	for spot in SPOTS:
		for zoom in zooms:
			place(spot[1], zoom)
			await shot("%s_%s_z%s_h%d_dark.png" % [label, spot[0], str(zoom), h])
	report["views"] = SPOTS.size()*zooms.size()*2

## The ground alone (everything else hidden), from straight above over the whole archipelago.
func ground_only(on: bool, keep := []) -> Dictionary:
	var hidden := {}
	if on:
		for node in app.find_children("*", "GeometryInstance3D", true, false):
			if keep.any(func(k): return node == k or (k as Node).is_ancestor_of(node)): continue
			if (node as GeometryInstance3D).visible:
				hidden[node] = true
				node.visible = false
	return hidden

## The game's follow view lets go of the camera (main.gd skips follow_camera while it warms shaders).
func free_camera(on: bool) -> void:
	app.warming = on

func top_view() -> void:
	app.camera.size = 210.0
	app.camera.position = Vector3(-5, 300, 0)
	app.camera.look_at(Vector3(-5, 0, 0.001), Vector3.FORWARD)
	app.camera.far = 1000.0

func ground_parts(map: Node) -> Array:
	var parts: Array = map.find_children("*__ground", "MeshInstance3D", true, false).filter(func(g): return (g as MeshInstance3D).mesh != null)
	var chunks := map.get_node_or_null("Ground")
	if chunks: parts.append(chunks)
	return parts

## Which lights make a pool on the ground: the ground alone (everything else hidden, which leaves the
## ground's light pairing as it is), from straight above around each light in turn, its energy off and
## on again (an energy change keeps the pairing too). A small view each: the renderer draws at most
## 32 lights a frame, and the whole map in one view would drop some of its ~40.
func lamp_sets() -> void:
	var map: Node3D = app.town.map
	var keep_far: float = app.camera.far
	var hidden := ground_only(true, ground_parts(map))
	var lights := point_lights().filter(func(l): return (l as Light3D).is_visible_in_tree())
	var pooled := []
	var quiet := []
	var means := {}
	for light: Light3D in lights:
		var reach: float = light.omni_range if light is OmniLight3D else 4.0
		app.camera.size = reach*2.0+2.0
		app.camera.far = 1000.0
		app.camera.global_transform = Transform3D(Basis.looking_at(Vector3.DOWN, Vector3.FORWARD), light.global_position+Vector3(0, 200, 0))
		var base := await shot("")
		var energy := light.light_energy
		light.light_energy = 0.0
		var image := await shot("")
		light.light_energy = energy
		var mean := float(image.compute_image_metrics(base, false).get("mean", 0.0))
		means[light_key(light)] = snappedf(mean, 0.001)
		if mean > 0.05: pooled.append(light_key(light))
		else: quiet.append(light_key(light))
	for node in hidden: node.visible = true
	app.camera.far = keep_far
	report["lamp_sets"] = {"pooled": pooled, "quiet": quiet}
	print("LAMP_SETS ", JSON.stringify({"hour": app.daylight.current_hour(), "lights": lights.size(), "pooled": pooled.size(), "quiet": quiet, "means": means}))

## A light by its place on the map (x, z to 0.1 m) and what holds it.
func light_key(light: Node3D) -> String:
	return "%.1f,%.1f %s" % [light.global_position.x, light.global_position.z, light_name(light)]

func light_name(light: Node) -> String:
	var path := String(app.get_path_to(light))
	var parts := path.split("/")
	return "/".join(parts.slice(maxi(0, parts.size()-3)))

## The levelled ground as the game drew it before the chunks (building_layout.gd levels a fresh copy
## of the terrain model), on the map's own ground nodes; the ocean's model mesh back. Returns what to
## undo: {node: [mesh, materials]}.
func full_ground(map: Node3D) -> Dictionary:
	var holder := Node3D.new()
	holder.visible = false
	root.add_child(holder)
	var terrain: Node3D = (load(map.TERRAIN) as PackedScene).instantiate()
	holder.add_child(terrain)
	var layout: Node3D = load("res://maps/archipelago/building_layout.gd").new()
	layout.manifest = JSON.parse_string(FileAccess.get_file_as_string("res://maps/archipelago/building_placements.json"))
	layout.terrain_root = terrain
	await layout._prepare_ground()
	var materials := {}
	var chunks := map.get_node_or_null("Ground")
	if chunks:
		for chunk: MeshInstance3D in chunks.get_children(): materials[chunk.mesh.surface_get_name(0)] = chunk.mesh.surface_get_material(0)
	var undo := {}
	for ground: MeshInstance3D in map.find_children("*__ground", "MeshInstance3D", true, false):
		var fresh := terrain.find_child(String(ground.name), true, false) as MeshInstance3D
		undo[ground] = [ground.mesh, ground.visible]
		ground.mesh = fresh.mesh
		ground.set_surface_override_material(0, materials.get(String(ground.name)))
		ground.visible = true
	for ocean: MeshInstance3D in map.find_children("Ocean__central_surface", "MeshInstance3D", true, false):
		var fresh := terrain.find_child("Ocean__central_surface", true, false) as MeshInstance3D
		undo[ocean] = [ocean.mesh, ocean.visible]
		ocean.mesh = fresh.mesh
		if chunks and chunks.has_node("Ocean"): ocean.material_override = (chunks.get_node("Ocean") as MeshInstance3D).material_override
	holder.free()
	layout.free()
	return undo

## A (before) or B (chunks) on the map.
func use(map: Node3D, before: bool, full: Dictionary, chunked: Dictionary) -> void:
	var chunks := map.get_node_or_null("Ground") as Node3D
	var state := full if before else chunked
	for node: MeshInstance3D in state:
		node.mesh = state[node][0]
		node.visible = state[node][1]
	if chunks: chunks.visible = not before

func ab() -> void:
	var map: Node3D = app.town.map
	if map.get_node_or_null("Ground") == null:
		print("AB_CAPTURE no ground chunks in this build")
		return
	var chunked := {}
	for node: MeshInstance3D in map.find_children("*__ground", "MeshInstance3D", true, false)+map.find_children("Ocean__central_surface", "MeshInstance3D", true, false):
		chunked[node] = [node.mesh, node.visible]
	var undo := await full_ground(map)
	var full := {}
	for node: MeshInstance3D in undo: full[node] = [node.mesh, true]
	if "--merged" in OS.get_cmdline_user_args():
		# Experiment: A is the chunks' triangles merged back into one mesh per island (no dropped ones).
		var parts := {}
		for chunk: MeshInstance3D in map.get_node("Ground").get_children().filter(func(c): return String(c.name).begins_with("Chunk_")):
			var key := String(chunk.mesh.surface_get_name(0))
			if not parts.has(key): parts[key] = []
			parts[key].append(chunk)
		for node: MeshInstance3D in undo:
			if not parts.has(String(node.name)): continue
			var tool := SurfaceTool.new()
			for chunk: MeshInstance3D in parts[String(node.name)]: tool.append_from(chunk.mesh, 0, Transform3D.IDENTITY)
			var merged := tool.commit()
			merged.surface_set_material(0, (parts[String(node.name)][0] as MeshInstance3D).mesh.surface_get_material(0))
			full[node] = [merged, true]
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--margin="):
			# Experiment: the chunks culled with a margin (shadow casters near the edge of a split).
			for chunk in map.get_node("Ground").get_children(): if chunk is GeometryInstance3D: chunk.extra_cull_margin = float(arg.trim_prefix("--margin="))
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shadow-skirt="):
			# Experiment: the dropped triangles reaching above this height kept as shadow casters only.
			var reach := float(arg.trim_prefix("--shadow-skirt="))
			var kept := 0
			for node: MeshInstance3D in undo:
				if not String(node.name).ends_with("__ground"): continue
				var arrays := (full[node][0] as Mesh).surface_get_arrays(0)
				var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
				var index: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
				var faces := PackedVector3Array()
				for t in range(0, index.size(), 3):
					var high := maxf(verts[index[t]].y, maxf(verts[index[t+1]].y, verts[index[t+2]].y))
					if high < -0.30 and high >= reach: faces.append_array(PackedVector3Array([verts[index[t]], verts[index[t+1]], verts[index[t+2]]]))
				if faces.is_empty(): continue
				kept += faces.size()/3
				var shell := ArrayMesh.new()
				var shell_arrays := []
				shell_arrays.resize(Mesh.ARRAY_MAX)
				shell_arrays[Mesh.ARRAY_VERTEX] = faces
				shell.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, shell_arrays)
				var caster := MeshInstance3D.new()
				caster.mesh = shell
				caster.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
				map.get_node("Ground").add_child(caster)
			print("SHADOW_SKIRT ", reach, " triangles ", kept)
	if "--anchors" in OS.get_cmdline_user_args():
		# Experiment: shadow-only stand-ins with each island ground's whole box, under the chunks.
		for node: MeshInstance3D in undo:
			if not String(node.name).ends_with("__ground"): continue
			var anchor := MeshInstance3D.new()
			var tiny := ArrayMesh.new()
			var arrays := []
			arrays.resize(Mesh.ARRAY_MAX)
			var at := (full[node][0] as Mesh).get_aabb().get_center()
			arrays[Mesh.ARRAY_VERTEX] = PackedVector3Array([at, at, at])
			tiny.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
			anchor.mesh = tiny
			anchor.custom_aabb = (full[node][0] as Mesh).get_aabb()
			anchor.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
			map.get_node("Ground").add_child(anchor)
	use(map, false, full, chunked)
	var lights := point_lights()
	var shown := lights.filter(func(l): return (l as Light3D).visible)
	var pairs := 0
	for h in [12.0, 21.0]:
		set_hour(h)
		for lit in [false, true]:
			for light in lights: light.visible = lit and shown.has(light)
			# With the lights on, a lamp's day/night state is the daylight's again.
			if lit: set_hour(h)
			for spot in SPOTS:
				for zoom in zooms:
					place(spot[1], zoom)
					for before in [true, false]:
						use(map, before, full, chunked)
						await shot("ab_h%d_%s_z%s_%s%s.png" % [int(h), spot[0], str(zoom), "A" if before else "B", "_lit" if lit else ""])
					pairs += 1
	if "--chunk-ids" in OS.get_cmdline_user_args():
		# Experiment: each chunk a flat colour (its index), at the same views, to place differences.
		use(map, false, full, chunked)
		var chunk_list := map.get_node("Ground").get_children().filter(func(c): return String(c.name).begins_with("Chunk_"))
		for index in chunk_list.size():
			var flat := StandardMaterial3D.new()
			flat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			flat.albedo_color = Color8(index*6, 255-index*6, (index*37) % 256)
			chunk_list[index].material_override = flat
		set_hour(12.0)
		for spot in SPOTS:
			for zoom in zooms:
				place(spot[1], zoom)
				await shot("ids_%s_z%s.png" % [spot[0], str(zoom)])
		for chunk in chunk_list: chunk.material_override = null
		print("CHUNK_IDS ", JSON.stringify(chunk_list.map(func(c): return String(c.name))))
	# Cracks: both grounds white and unshaded on magenta, the rest hidden; below the line the chunks
	# leave out nothing is drawn in either (a chunk keeps a whole triangle that reaches above it).
	var white := ShaderMaterial.new()
	white.shader = Shader.new()
	white.shader.code = " ".join(["shader_type spatial;", "render_mode unshaded, cull_disabled;", "varying float height;",
		"void vertex() { height = (MODEL_MATRIX*vec4(VERTEX, 1.0)).y; }", "void fragment() { if (height < -0.30) { discard; } ALBEDO = vec3(1.0); }"])
	var env: Environment = app.environment
	var keep_bg := [env.background_mode, env.background_color, env.fog_enabled, env.adjustment_enabled, env.glow_enabled, env.tonemap_mode]
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color.MAGENTA
	env.fog_enabled = false
	env.adjustment_enabled = false
	env.glow_enabled = false
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var keep_far: float = app.camera.far
	for before in [true, false]:
		use(map, before, full, chunked)
		var parts := map.find_children("*__ground", "MeshInstance3D", true, false).filter(func(g): return (g as MeshInstance3D).mesh != null and g.visible)
		if not before: parts = map.get_node("Ground").get_children().filter(func(c): return String(c.name).begins_with("Chunk_"))
		var hidden := ground_only(true, parts)
		for part: MeshInstance3D in parts: part.material_override = white
		top_view()
		await shot("crack_%s.png" % ("A" if before else "B"))
		# Closer, where the chunk borders cross the town.
		app.camera.size = 40.0
		app.camera.position = Vector3(-32, 300, 0)
		app.camera.look_at(Vector3(-32, 0, 0.001), Vector3.FORWARD)
		await shot("crack_close_%s.png" % ("A" if before else "B"))
		for part: MeshInstance3D in parts: part.material_override = null
		for node in hidden: node.visible = true
	env.background_mode = keep_bg[0]; env.background_color = keep_bg[1]; env.fog_enabled = keep_bg[2]
	env.adjustment_enabled = keep_bg[3]; env.glow_enabled = keep_bg[4]; env.tonemap_mode = keep_bg[5]
	app.camera.far = keep_far
	use(map, false, full, chunked)
	report["ab_pairs"] = pairs
