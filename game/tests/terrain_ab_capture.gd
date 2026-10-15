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
const SPOTS := [["square", Vector2(-33,37)], ["cafe", Vector2(-60.2,-27.6)], ["meadow", Vector2(-18,-31)], ["headland", Vector2(62,-38)],
	["camp", Vector2(52,36)], ["lighthouse", Vector2(5,74)], ["falls", Vector2(2,-14)], ["shore", Vector2(-80,10)],
	["south_lamps", Vector2(-25,57)], ["bridge_lamps", Vector2(16,27)], ["camp_lamp", Vector2(66,44)]]
var app: Node
var out_dir := "res://../artifacts/terrain_p2/ab/"
var label := "cap"
var zooms := [6.5, 10.0, 22.0]
var report := {}

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="): out_dir = arg.trim_prefix("--out=").trim_suffix("/")+"/"
		if arg.begins_with("--label="): label = arg.trim_prefix("--label=")
		if arg.begins_with("--zooms="): zooms = Array(arg.trim_prefix("--zooms=").split(",")).map(func(z): return float(z))
	call_deferred("run")

func run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_dir))
	if not await enter_village():
		quit(1)
		return
	var args := OS.get_cmdline_user_args()
	# Time almost stopped (0 makes the walker's physics divide by it): residents, water and clouds hold still.
	Engine.time_scale = 0.0001
	for arg in args:
		if arg.begins_with("--switch-hour="):
			set_hour(float(arg.trim_prefix("--switch-hour=")))
			for i in 30: await process_frame
	if "--views" in args: await views()
	if "--lampsets" in args: await lamp_sets()
	if "--ab" in args: await ab()
	Engine.time_scale = 1.0
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
	free_camera(true)
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
	free_camera(true)
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
	free_camera(false)
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
	# Cracks: both grounds white and unshaded on magenta, the rest hidden.
	var white := StandardMaterial3D.new()
	white.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	white.albedo_color = Color.WHITE
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
		if not before: parts = map.get_node("Ground").get_children()
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
	free_camera(false)
	use(map, false, full, chunked)
	report["ab_pairs"] = pairs
