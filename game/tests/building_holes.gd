extends SceneTree
## Renders every placed building through the village camera direction (orthographic,
## Profile.CAMERA_OFFSET, never rotates) to find holes in the Tripo exteriors.
## Needs a window (not --headless):
##   Godot --path game --script res://tests/building_holes.gd -- [--tag=before]
##       [--ids=01_cafe,09_town_hall] [--hours=12,21] [--no-debug] [--no-dress]
## Per building writes artifacts/holes-<tag>-<id>.png, a 3x2 sheet:
##   top row    noon: default zoom (size 10), close zoom (size 6.5), hole map
##   bottom row night: default zoom, close zoom, hole map with the building alone
## The hole map draws only that building, unshaded: front faces grey by facing,
## back faces magenta (a crack or an opening showing the inside), background green
## (seen straight through). HOLES <id> back=<px> through=<px> counts them.
const Map = preload("res://maps/archipelago/archipelago.gd")
const Daylight = preload("res://scripts/daylight.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const DRESSING := "res://scripts/building_dressing.gd"
const CELL := Vector2i(960, 600)
const DEBUG_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled, fog_disabled;
void fragment() {
	if (FRONT_FACING) {
		float lit = 0.35+0.6*clamp(dot(NORMAL, normalize(vec3(0.4, 0.8, 0.5))), 0.0, 1.0);
		ALBEDO = vec3(lit);
	} else {
		ALBEDO = vec3(1.0, 0.0, 1.0);
	}
}
"""
var map: Node3D
var camera: Camera3D
var env: Environment
var sun: DirectionalLight3D
var daylight: Node
var dressing: Script

func _initialize() -> void:
	call_deferred("run")
	create_timer(900).timeout.connect(func(): quit(2))

func run() -> void:
	var tag := "before"
	var ids: Array = []
	var hours: Array[float] = [12.0, 21.0]
	var args := OS.get_cmdline_user_args()
	for arg in args:
		if arg.begins_with("--tag="): tag = arg.trim_prefix("--tag=")
		if arg.begins_with("--ids="): ids = Array(arg.trim_prefix("--ids=").split(","))
		if arg.begins_with("--hours="):
			hours.clear()
			for value in arg.trim_prefix("--hours=").split(","): hours.append(float(value))
	camera = Camera3D.new()
	camera.far = 400
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	root.add_child(camera)
	camera.current = true
	map = Map.new()
	map.name = "Archipelago"
	root.add_child(map)
	map.build(camera)
	var world := WorldEnvironment.new()
	env = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	world.environment = env
	root.add_child(world)
	sun = DirectionalLight3D.new()
	sun.shadow_enabled = true
	root.add_child(sun)
	Map.apply_lighting(env, sun)
	for i in 8: await physics_frame
	if ResourceLoader.exists(DRESSING) and "--no-dress" not in args:
		dressing = load(DRESSING)
		dressing.dress(map)
	daylight = Daylight.new()
	root.add_child(daylight)
	daylight.attach(env, sun, map)
	var buildings := map.get_node("Buildings")
	if ids.is_empty():
		for child in buildings.get_children(): ids.append(String(child.name))
	var sheets := {}
	for id in ids: sheets[id] = Image.create(CELL.x*3, CELL.y*2, false, Image.FORMAT_RGB8)
	for row in hours.size():
		var hour := hours[row]
		daylight.override_hour = hour
		daylight.refresh(true)
		if dressing: dressing.update(map, hour)
		for id in ids:
			var building := buildings.get_node(String(id)) as Node3D
			var box := _bounds(building)
			var centre := box.get_center()
			# Close zoom looks at the lower walls (doors, windows) where cracks matter.
			var low := Vector3(centre.x, box.position.y+minf(box.size.y*.4, 3.2), centre.z)
			_frame(centre, 10.0)
			sheets[id].blit_rect(await _grab(), Rect2i(Vector2i.ZERO, CELL), Vector2i(0, row*CELL.y))
			_frame(low, 6.5)
			sheets[id].blit_rect(await _grab(), Rect2i(Vector2i.ZERO, CELL), Vector2i(CELL.x, row*CELL.y))
	if "--no-debug" not in args:
		_debug_mode(true)
		for id in ids:
			var building := buildings.get_node(String(id)) as Node3D
			for child in buildings.get_children(): child.visible = child == building
			var box := _bounds(building)
			var centre := box.get_center()
			# Fit the whole building: the ortho size is the vertical extent.
			var fit := maxf(box.size.y*1.25, maxf(box.size.x, box.size.z)*.75)
			_frame(centre, fit)
			var image := await _grab()
			var counts := _count(image)
			sheets[id].blit_rect(image, Rect2i(Vector2i.ZERO, CELL), Vector2i(CELL.x*2, 0))
			_frame(Vector3(centre.x, box.position.y+minf(box.size.y*.4, 3.2), centre.z), 6.5)
			image = await _grab()
			sheets[id].blit_rect(image, Rect2i(Vector2i.ZERO, CELL), Vector2i(CELL.x*2, CELL.y))
			print("HOLES %s back=%d through=%d fit=%.1f" % [id, counts.x, counts.y, fit])
		_debug_mode(false)
	for id in ids:
		var path := ProjectSettings.globalize_path("res://../artifacts/holes-%s-%s.png" % [tag, id])
		print("CAPTURE ", sheets[id].save_png(path), " ", path)
	quit(0)

func _bounds(node: Node3D) -> AABB:
	var bounds := AABB()
	var first := true
	for item in node.find_children("*", "MeshInstance3D", true, false):
		var mesh := item as MeshInstance3D
		var box: AABB = mesh.global_transform*mesh.get_aabb()
		bounds = box if first else bounds.merge(box)
		first = false
	return bounds

func _frame(target: Vector3, size: float) -> void:
	camera.size = size
	camera.position = target+Profile.CAMERA_OFFSET.normalized()*60.0
	camera.look_at(target)
	map.camera = camera

func _grab() -> Image:
	for i in 5: await process_frame
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	if image.get_size() != CELL: image.resize(CELL.x, CELL.y, Image.INTERPOLATE_LANCZOS)
	return image

var _saved := []
## Debug look: only buildings, unshaded, back faces magenta on a green background.
func _debug_mode(on: bool) -> void:
	if on:
		var debug := ShaderMaterial.new()
		debug.shader = Shader.new()
		debug.shader.code = DEBUG_SHADER
		for child in map.get_children():
			_saved.append([child, child.visible])
			if child.name != "Buildings": child.visible = false
		var pane := StandardMaterial3D.new()
		pane.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		pane.cull_mode = BaseMaterial3D.CULL_DISABLED
		pane.albedo_color = Color(0.1, 0.6, 1.0)
		for item in map.get_node("Buildings").find_children("*", "MeshInstance3D", true, false):
			var mesh := item as MeshInstance3D
			for i in mesh.mesh.get_surface_count():
				var active := mesh.get_active_material(i)
				var textured := active is ShaderMaterial or (active is BaseMaterial3D and active.albedo_texture != null)
				_saved.append([mesh, i, mesh.get_surface_override_material(i)])
				mesh.set_surface_override_material(i, debug if textured else pane)
		daylight.process_mode = Node.PROCESS_MODE_DISABLED
		_saved.append([env, [env.background_color, env.fog_enabled, env.adjustment_enabled]])
		env.background_color = Color(0, 1, 0)
		env.fog_enabled = false
		env.adjustment_enabled = false
		_saved.append([sun, sun.visible])
		sun.visible = false
	else:
		for entry in _saved:
			if entry[0] is Environment:
				entry[0].background_color = entry[1][0]
				entry[0].fog_enabled = entry[1][1]
				entry[0].adjustment_enabled = entry[1][2]
			elif entry.size() == 3: entry[0].set_surface_override_material(entry[1], entry[2])
			else: entry[0].visible = entry[1]
		_saved.clear()
		daylight.process_mode = Node.PROCESS_MODE_INHERIT
		for child in map.get_node("Buildings").get_children(): child.visible = true

## x: magenta (back face) pixels, y: green pixels enclosed left and right by the
## building on the same row (seen straight through a gap).
func _count(image: Image) -> Vector2i:
	var back := 0
	var through := 0
	for y in image.get_height():
		var first := -1
		var last := -1
		for x in image.get_width():
			var c := image.get_pixel(x, y)
			if not (c.g > .8 and c.r < .2 and c.b < .2):
				if first < 0: first = x
				last = x
		for x in range(first+1, last):
			var c := image.get_pixel(x, y)
			if c.r > .8 and c.b > .8 and c.g < .25: back += 1
			elif c.g > .8 and c.r < .2 and c.b < .2:
				# Only count gaps with building above and below as well (not a porch notch).
				if _solid(image, x, y, Vector2i(0, -1)) and _solid(image, x, y, Vector2i(0, 1)): through += 1
	return Vector2i(back, through)

func _solid(image: Image, x: int, y: int, step: Vector2i) -> bool:
	var p := Vector2i(x, y)+step
	for i in 25:
		if p.y < 0 or p.y >= image.get_height(): return false
		var c := image.get_pixel(p.x, p.y)
		if not (c.g > .8 and c.r < .2 and c.b < .2): return true
		p += step
	return false
