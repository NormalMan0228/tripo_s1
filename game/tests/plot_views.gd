extends SceneTree
## The new outdoor places of MAP 40 through the game's follow camera: the 단비 plot (empty and built,
## maps/archipelago/plots.gd) and 풍차 언덕 하숙집 (18_meadow_house), at the given zooms and hours,
## plus straight-down views for measuring doors. Needs a window (not --headless):
##   Godot --path game -s res://tests/plot_views.gd -- [--zooms=10,22] [--hours=12,21] [--tag=40]
##       [--top=x,z,size,name ...] [--out=DIR]
## Writes <out>/<tag>-<spot>-z<zoom>-h<hour>.png (the plot as "danbi-empty" and "danbi-built").
## Checks: the plot's API answers, the lot hides when built and its walls block, the door is clear.
const Town = preload("res://scripts/town.gd")
const Map = preload("res://maps/archipelago/archipelago.gd")
const Daylight = preload("res://scripts/daylight.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const Plots = preload("res://maps/archipelago/plots.gd")
const DRESSING := "res://scripts/building_dressing.gd"
const SPOTS := {"meadow_house":Vector2(-21.5,-50.0), "danbi":Vector2(-23.0,13.0)}
var map: Node3D
var camera: Camera3D
var env: Environment
var sun: DirectionalLight3D
var daylight: Node
var dressing: Script
var out := ""
var failures: Array[String] = []

func check(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ")+label)
	if not value: failures.append(label)

func _initialize() -> void:
	call_deferred("run")
	create_timer(500).timeout.connect(func(): quit(2))

func arg(name: String, fallback: String) -> String:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--%s=" % name): return a.get_slice("=",1)
	return fallback

func run() -> void:
	var hours: Array = Array(arg("hours","12,21").split(",")).map(func(v): return float(v))
	var zooms: Array = Array(arg("zooms","10,22").split(",")).map(func(v): return float(v))
	var tag := arg("tag","40")
	out = arg("out",ProjectSettings.globalize_path("res://../artifacts/mapinterior").simplify_path())
	DirAccess.make_dir_recursive_absolute(out)
	camera = Camera3D.new()
	camera.far = 400
	root.add_child(camera)
	map = Map.new()
	map.name = "Archipelago"
	root.add_child(map)
	await map.build(camera)
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
	var space := map.get_world_3d().direct_space_state
	Town.space = space
	var roads: Node3D = preload("res://scripts/roads.gd").new()
	roads.name = "Roads"
	map.add_child(roads)
	await roads.build(space, map.get_node("Environment"))
	if ResourceLoader.exists(DRESSING):
		dressing = load(DRESSING)
		dressing.dress(map)
	var holder := Node3D.new()
	holder.name = "Town"
	root.add_child(holder)
	await Plots.install(holder, space)
	daylight = Daylight.new()
	root.add_child(daylight)
	daylight.attach(env, sun, map)
	for i in 30: await process_frame
	# The API story code uses.
	var info := Plots.plot_info("danbi_plot")
	check(not info.is_empty() and info.sign_label is Label3D and str(info.sign_label.text) == TranslationServer.translate("곧 새 이웃이 이사 와요"), "plot_info gives the sign's label with the default text")
	check(info.room == "danbi_house" and Town.door_for("danbi_house").get("plot","") == "danbi_plot", "the plot's room and door")
	check(Plots.doors().is_empty() and not info.built, "an empty plot has no door")
	print("DANBI_PLOT ", JSON.stringify({"center":[info.center.x, info.center.y, info.center.z], "radius":info.radius, "door":[info.door.x, info.door.y], "yaw":info.yaw,
		"sign":[info.sign.global_position.x, info.sign.global_position.y, info.sign.global_position.z]}))
	var door_hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(info.door.x, 60, info.door.y), Vector3(info.door.x, -20, info.door.y), 2|8))
	check(door_hit.is_empty(), "nothing stands on the plot's door step while empty")
	for top in OS.get_cmdline_user_args():
		if top.begins_with("--top="): await top_view(top.trim_prefix("--top=").split(","))
	await shoot(tag, "danbi-empty", SPOTS.danbi, zooms, hours)
	Plots.set_plot_built("danbi_plot", true)
	for i in 120:
		await process_frame
		if holder.get_node_or_null("Plot_danbi_plot/House/Model"): break
	for i in 4: await physics_frame
	var lot := holder.get_node("Plot_danbi_plot/Lot") as Node3D
	var house := holder.get_node("Plot_danbi_plot/House") as Node3D
	check(not lot.visible and house.visible and house.get_node_or_null("Model") != null, "built: the house shows, the stakes hide")
	var wall_hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(info.center_2d.x, 60, info.center_2d.y), Vector3(info.center_2d.x, -20, info.center_2d.y), 2))
	check(not wall_hit.is_empty(), "built: the house blocks (buildings layer)")
	check(Plots.doors().size() == 1 and Vector2(Plots.doors()[0].at).distance_to(info.door) < 0.01, "built: the door entry is offered")
	for top in OS.get_cmdline_user_args():
		if top.begins_with("--top="):
			var v := top.trim_prefix("--top=").split(",")
			v[3] = v[3]+"-built"
			await top_view(v)
	await shoot(tag, "danbi-built", SPOTS.danbi, zooms, hours)
	await shoot(tag, "meadow_house", SPOTS.meadow_house, zooms, hours)
	for f in failures: print("FAIL ", f)
	print("PLOT_VIEWS ", "ok" if failures.is_empty() else "failed")
	quit(0 if failures.is_empty() else 1)

func shoot(tag: String, spot: String, at: Vector2, zooms: Array, hours: Array) -> void:
	for hour in hours:
		daylight.override_hour = hour
		daylight.refresh(true)
		if dressing: dressing.update(map, hour)
		for zoom in zooms:
			focus(at, zoom)
			await capture("%s-%s-z%d-h%d.png" % [tag, spot, int(zoom), int(hour)])

func focus(at: Vector2, size: float) -> void:
	var from := Vector3(at.x, 60, at.y)
	var hit := map.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(from, from+Vector3.DOWN*80, 1))
	var target := Vector3(at.x, hit.get("position", Vector3(0, 2, 0)).y, at.y)+Profile.CAMERA_FOCUS_OFFSET
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = size
	camera.position = target+Profile.CAMERA_OFFSET*Profile.CAMERA_PULLBACK
	camera.look_at(target)
	camera.current = true
	map.camera = camera

func capture(file: String) -> void:
	for i in 8: await process_frame
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	image.save_png(out.path_join(file))

## Straight-down square image for measuring: x,z,size,name (800 px = size m).
func top_view(v: PackedStringArray) -> void:
	var frame := SubViewport.new()
	frame.size = Vector2i(800, 800)
	frame.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(frame)
	var view := Camera3D.new()
	view.projection = Camera3D.PROJECTION_ORTHOGONAL
	view.size = float(v[2])
	view.far = 400
	view.position = Vector3(float(v[0]), 150, float(v[1]))
	view.rotation_degrees = Vector3(-90, 0, 0)
	frame.add_child(view)
	view.current = true
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-70, 160, 0)
	frame.add_child(light)
	for i in 12: await process_frame
	await RenderingServer.frame_post_draw
	frame.get_texture().get_image().save_png(out.path_join("top-"+v[3]+".png"))
	frame.queue_free()
