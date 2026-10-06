extends SceneTree
## Renders the village outdoors through the game's follow camera at chosen hours, for
## judging roads (scripts/roads.gd) and building exteriors (scripts/building_dressing.gd).
## Needs a window (not --headless):
##   Godot --path game --script res://tests/exterior_views.gd -- [--hours=12,21]
##       [--spots=green,cafe] [--tag=after] [--size=12] [--bare] [--no-dress]
## Writes artifacts/exterior-<tag>-<spot>-<hour>.png. --bare skips roads and dressing.
const Town = preload("res://scripts/town.gd")
const Map = preload("res://maps/archipelago/archipelago.gd")
const Daylight = preload("res://scripts/daylight.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const DRESSING := "res://scripts/building_dressing.gd"
const SPOTS := {
	"green":Vector2(-31,33), "shop":Vector2(-18,32.5), "redhouse":Vector2(-53,24), "purple":Vector2(-61,38),
	"blue":Vector2(-65,52), "cafe":Vector2(-58,-31), "timber":Vector2(-37,-40), "teal":Vector2(-29,-21),
	"windmill":Vector2(-16,-36), "observatory":Vector2(30,-37), "orange":Vector2(27,-21), "greenhouse":Vector2(50,-11),
	"stage":Vector2(36,33), "cottage":Vector2(67,59), "lighthouse":Vector2(5,82), "bridge_sw":Vector2(-12,29),
	"bridge_ne":Vector2(18,-34), "camp":Vector2(52,40)}
var map: Node3D
var camera: Camera3D
var env: Environment
var sun: DirectionalLight3D
var daylight: Node
var dressing: Script

func _initialize() -> void:
	call_deferred("run")
	create_timer(400).timeout.connect(func(): quit(2))

func run() -> void:
	var hours: Array[float] = [12.0, 21.0]
	var spots: Array = SPOTS.keys()
	var tag := "after"
	var size := 12.0
	var bare := "--bare" in OS.get_cmdline_user_args()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--hours="):
			hours.clear()
			for value in arg.trim_prefix("--hours=").split(","): hours.append(float(value))
		if arg.begins_with("--spots="): spots = Array(arg.trim_prefix("--spots=").split(","))
		if arg.begins_with("--tag="): tag = arg.trim_prefix("--tag=")
		if arg.begins_with("--size="): size = float(arg.trim_prefix("--size="))
	camera = Camera3D.new()
	camera.far = 400
	root.add_child(camera)
	var started := Time.get_ticks_msec()
	map = Map.new()
	map.name = "Archipelago"
	root.add_child(map)
	map.build(camera)
	print("MAP_MS ", Time.get_ticks_msec()-started)
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
	Town.space = map.get_world_3d().direct_space_state
	if not bare:
		var roads: Node3D = preload("res://scripts/roads.gd").new()
		roads.name = "Roads"
		map.add_child(roads)
		var t := Time.get_ticks_msec()
		roads.build(map.get_world_3d().direct_space_state, map.get_node("Environment"))
		print("ROADS_MS ", Time.get_ticks_msec()-t)
		if ResourceLoader.exists(DRESSING) and "--no-dress" not in OS.get_cmdline_user_args():
			dressing = load(DRESSING)
			t = Time.get_ticks_msec()
			dressing.dress(map)
			print("DRESSING_MS ", Time.get_ticks_msec()-t)
	daylight = Daylight.new()
	root.add_child(daylight)
	daylight.attach(env, sun, map)
	for hour in hours:
		daylight.override_hour = hour
		daylight.refresh(true)
		if dressing: dressing.update(map, hour)
		for spot in spots:
			focus(SPOTS[spot], size)
			await capture("exterior-%s-%s-%s.png" % [tag, spot, str(int(hour))])
	quit(0)

func focus(at: Vector2, size: float) -> void:
	var from := Vector3(at.x, 60, at.y)
	var hit := map.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(from, from+Vector3.DOWN*80, 1))
	var target := Vector3(at.x, hit.get("position", Vector3(0, 2, 0)).y, at.y)+Profile.CAMERA_FOCUS_OFFSET
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = size
	var pullback: float = Profile.CAMERA_PULLBACK
	camera.position = target+Profile.CAMERA_OFFSET*pullback
	camera.look_at(target)
	camera.current = true
	map.camera = camera

func capture(file: String) -> void:
	for i in 6: await process_frame
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	var path := ProjectSettings.globalize_path("res://../artifacts/"+file)
	print("CAPTURE ", image.save_png(path), " ", path)
