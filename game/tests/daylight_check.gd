extends SceneTree
## Visual check for scripts/daylight.gd and maps/archipelago/pond_water.gdshader.
## Loads the village map and renders, through the game's follow camera:
##  - the town green under Daylight.sample() at several hours, to
##    artifacts/daylight-<hour>.png plus artifacts/daylight-sheet.png, and a night
##    close-up of a lamp to artifacts/daylight-lamp-<hour>.png;
##  - the town-green pond with pond_water.gdshader swapped in (parameters copied
##    from the map's material) twice, 1 s apart, to artifacts/pond-a.png / pond-b.png,
##    and once at night to artifacts/pond-night.png.
## Needs a window (not --headless):
##   Godot --path game --script res://tests/daylight_check.gd -- [--only=daylight|pond]
##       [--hours=6,12,20] [--pond-debug=1..3]
const Map = preload("res://maps/archipelago/archipelago.gd")
const Daylight = preload("res://scripts/daylight.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const POND_SHADER := "res://maps/archipelago/pond_water.gdshader"
const TOWN_GREEN := Vector2(-33, 37)
const LAMP_VIEW := Vector2(-25, 31)
const POND_VIEW := Vector2(-44, 41)
var hours: Array[float] = [6.0, 9.0, 12.0, 17.0, 18.5, 20.0, 23.0, 2.0]
var map: Node3D
var camera: Camera3D
var env: Environment
var sun: DirectionalLight3D
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func hour_name(hour: float) -> String:
	return str(int(hour)) if is_equal_approx(hour, roundf(hour)) else String.num(hour)

func artifact(file: String) -> String:
	return ProjectSettings.globalize_path("res://../artifacts/"+file)

func run() -> void:
	var only := ""
	var pond_debug := 0
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--only="):
			only = arg.trim_prefix("--only=")
		if arg.begins_with("--hours="):
			hours.clear()
			for value in arg.trim_prefix("--hours=").split(","):
				hours.append(float(value))
		if arg.begins_with("--pond-debug="):
			pond_debug = int(arg.trim_prefix("--pond-debug="))
	DirAccess.make_dir_recursive_absolute(artifact(""))
	camera = Camera3D.new()
	root.add_child(camera)
	map = Map.new()
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
	for i in 6: await physics_frame
	check_noon()
	if only != "pond":
		await daylight_pass()
	if only != "daylight":
		await pond_pass(pond_debug)
	print("DAYLIGHT_CHECK ", "FAIL " if failures else "OK ", failures)
	quit(1 if failures else 0)

## Noon must stay on the tuned Archipelago.apply_lighting values.
func check_noon() -> void:
	var noon := Daylight.sample(12.0)
	var ok: bool = noon.sun_rotation.is_equal_approx(sun.rotation_degrees) \
		and absf(noon.sun_energy-sun.light_energy) < .005 \
		and absf(noon.ambient_energy-env.ambient_light_energy) < .005 \
		and noon.sun_color.is_equal_approx(sun.light_color) \
		and noon.ambient_color.is_equal_approx(env.ambient_light_color) \
		and noon.background_color.is_equal_approx(env.background_color) \
		and noon.fog_density < .0002 and noon.lamp_energy < .01
	print("NOON_MATCH ", ok, " ", noon)
	if not ok:
		failures += 1
	var previous := Daylight.sample(0.0)
	var worst := 0.0
	for step in range(1, 24*12+1):
		var now := Daylight.sample(step/12.0)
		worst = maxf(worst, absf(now.ambient_energy-previous.ambient_energy)+absf(now.sun_energy-previous.sun_energy))
		previous = now
	print("MAX_5MIN_STEP ", snappedf(worst, .0001))
	if worst > .05:
		failures += 1

func focus_camera(at: Vector2, size: float) -> void:
	var from := Vector3(at.x, 60, at.y)
	var hit := map.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(from, from+Vector3.DOWN*80, Map.WALK_MASK))
	var focus := Vector3(at.x, maxf(hit.get("position", Vector3(0, 1.2, 0)).y, 1.2), at.y)+Profile.CAMERA_FOCUS_OFFSET
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = size
	camera.position = focus+Profile.CAMERA_OFFSET
	camera.look_at(focus)
	camera.current = true

func capture(file: String, settle := 8) -> Image:
	for i in settle: await process_frame
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	var path := artifact(file)
	print("CAPTURE ", image.save_png(path), " ", path)
	return image

func daylight_pass() -> void:
	var daylight := Daylight.new()
	root.add_child(daylight)
	daylight.override_hour = 12.0
	daylight.attach(env, sun, map)
	print("LAMPS ", daylight.lamps.size())
	if daylight.lamps.is_empty():
		failures += 1
	focus_camera(TOWN_GREEN, Profile.VILLAGE_CAMERA_DEFAULT)
	var shots: Array[Image] = []
	for hour in hours:
		daylight.override_hour = hour
		daylight.refresh(true)
		var values := daylight.current
		print("HOUR ", hour, " sun=", values.sun_energy, " rot=", values.sun_rotation, " ambient=", values.ambient_energy, " night=", snappedf(values.night, .01), " daylight=", snappedf(values.daylight, .01), " lamps=", snappedf(values.lamp_energy, .01), " fog=", values.fog_density)
		shots.append(await capture("daylight-"+hour_name(hour)+".png"))
	await contact_sheet(shots)
	focus_camera(LAMP_VIEW, Profile.VILLAGE_CAMERA_DEFAULT)
	for hour in [20.0]:
		daylight.override_hour = hour
		daylight.refresh(true)
		await capture("daylight-lamp-"+hour_name(hour)+".png")
	await live_update(daylight)
	# Re-attaching (the village rebuilt on a kept map) must not stack lamp glows.
	daylight.attach(env, sun, map)
	var glows := 0
	for lamp in daylight.lamps:
		glows += lamp.find_children("DaylightHalo", "", false, false).size()
	print("REATTACH_GLOWS ", glows, " lamps=", daylight.lamps.size())
	if glows != daylight.lamps.size():
		failures += 1
	daylight.detach()
	var restored := not env.adjustment_enabled and not env.fog_enabled
	for lamp in Daylight.find_lamps(map):
		restored = restored and lamp.visible and is_equal_approx(lamp.light_energy, lamp.get_meta("daylight_base_energy")) 			and lamp.find_children("DaylightHalo", "", false, false).is_empty()
	print("DETACH_RESTORED ", restored)
	if not restored:
		failures += 1
	daylight.queue_free()
	Map.apply_lighting(env, sun)

## The node itself, as the game runs it: a new hour is picked up by _process
## within update_interval and eased in, ending exactly on sample().
func live_update(daylight: Node) -> void:
	daylight.override_hour = 12.0
	daylight.refresh(true)
	daylight.override_hour = 21.0
	await create_timer(daylight.update_interval+daylight.blend_seconds+.5).timeout
	var want := Daylight.sample(21.0)
	var ok: bool = absf(sun.light_energy-want.sun_energy) < .001 and absf(env.ambient_light_energy-want.ambient_energy) < .001 		and sun.rotation_degrees.is_equal_approx(want.sun_rotation) and env.adjustment_enabled and env.fog_enabled 		and daylight.lamps.all(func(lamp: OmniLight3D) -> bool: return lamp.visible and lamp.light_energy > lamp.get_meta("daylight_base_energy"))
	print("LIVE_UPDATE ", ok, " sun=", sun.light_energy, " ambient=", env.ambient_light_energy)
	if not ok:
		failures += 1
	daylight.override_hour = 12.0
	daylight.refresh(true)

## 4 x 2 grid of half-size shots with their hour.
func contact_sheet(shots: Array[Image]) -> void:
	var cell := Vector2i(640, 400)
	var columns := 4
	var rows := ceili(shots.size()/float(columns))
	var frame := SubViewport.new()
	frame.disable_3d = true
	frame.size = Vector2i(cell.x*columns, cell.y*rows)
	frame.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(frame)
	for i in shots.size():
		var picture := TextureRect.new()
		picture.texture = ImageTexture.create_from_image(shots[i])
		picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		picture.stretch_mode = TextureRect.STRETCH_SCALE
		picture.position = Vector2((i%columns)*cell.x, (i/columns)*cell.y)
		picture.size = Vector2(cell)
		frame.add_child(picture)
		var label := Label.new()
		var hour := hours[i]
		label.text = "%02d:%02d" % [int(hour), int(round(fmod(hour, 1.0)*60.0))]
		label.add_theme_font_size_override("font_size", 26)
		label.add_theme_color_override("font_color", Color.WHITE)
		label.add_theme_color_override("font_outline_color", Color.BLACK)
		label.add_theme_constant_override("outline_size", 6)
		label.position = picture.position+Vector2(14, 8)
		frame.add_child(label)
	for i in 4: await process_frame
	await RenderingServer.frame_post_draw
	var path := artifact("daylight-sheet.png")
	print("SHEET ", frame.get_texture().get_image().save_png(path), " ", path)
	frame.queue_free()

func pond_pass(debug_view: int) -> void:
	var swapped := 0
	for item in map.find_children("*", "MeshInstance3D", true, false):
		var mesh := item as MeshInstance3D
		if not ("__pond" in mesh.name or "Waterfall__spring_pool" in mesh.name):
			continue
		var original := mesh.material_override as ShaderMaterial
		var water := ShaderMaterial.new()
		water.shader = load(POND_SHADER)
		for uniform in original.shader.get_shader_uniform_list():
			var value = original.get_shader_parameter(uniform.name)
			if value != null:
				water.set_shader_parameter(uniform.name, value)
		water.set_shader_parameter("debug_view", debug_view)
		mesh.material_override = water
		swapped += 1
	print("POND_MATERIALS ", swapped)
	if swapped == 0:
		failures += 1
	focus_camera(POND_VIEW, 12.0)
	var suffix := "" if debug_view == 0 else "-debug%d" % debug_view
	var first := await capture("pond-a"+suffix+".png", 30)
	await create_timer(1.0).timeout
	var second := await capture("pond-b"+suffix+".png", 1)
	# Motion check: the pond area of the two frames must differ.
	var changed := 0
	var total := 0
	var difference := 0.0
	for y in range(0, first.get_height(), 4):
		for x in range(0, first.get_width(), 4):
			var a := first.get_pixel(x, y)
			var b := second.get_pixel(x, y)
			var delta := absf(a.r-b.r)+absf(a.g-b.g)+absf(a.b-b.b)
			difference += delta
			total += 1
			if delta > .03:
				changed += 1
	print("POND_MOTION mean=", snappedf(difference/total, .0001), " changed=", snappedf(changed/float(total), .001))
	if changed/float(total) < .05:
		failures += 1
	if debug_view == 0:
		# The same pond by moonlight, lamps on.
		var daylight := Daylight.new()
		root.add_child(daylight)
		daylight.override_hour = 21.0
		daylight.attach(env, sun, map)
		await capture("pond-night.png", 10)
		daylight.detach()
		daylight.queue_free()
		Map.apply_lighting(env, sun)
