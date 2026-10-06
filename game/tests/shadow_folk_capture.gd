extends SceneTree
## Looks at the shadow folk in the real village through the game's orthographic
## follow camera, with scripts/daylight.gd driving the light:
##   artifacts/shadow-folk-day.png    five shadows staged on the town green at noon
##   artifacts/shadow-folk-night.png  the same corner at 21:30 (lanterns, eye glints)
##   artifacts/shadow-folk-walk.png   a close view of a shadow mid-stride
##   artifacts/shadow-folk-bridge.png a shadow crossing a bridge
## Needs a window (not --headless):
##   Godot --path game --script res://tests/shadow_folk_capture.gd
const Stub = preload("res://tests/shadow_folk_stub.gd")
const Folk = preload("res://scripts/shadow_folk.gd")
const Map = preload("res://maps/archipelago/archipelago.gd")
const Daylight = preload("res://scripts/daylight.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const Town = preload("res://scripts/town.gd")
var app: Node3D
var folk: Node3D
var camera: Camera3D
var env: Environment
var sun: DirectionalLight3D

func _initialize() -> void:
	call_deferred("run")

func artifact(file: String) -> String:
	return ProjectSettings.globalize_path("res://../artifacts/"+file)

func run() -> void:
	seed(7)
	camera = Camera3D.new()
	root.add_child(camera)
	app = Stub.new()
	root.add_child(app)
	app.build(camera)
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
	app.spawn_villagers()
	app.daylight.override_hour = 12.0
	app.daylight.attach(env, sun, app.town.map)
	folk = Folk.new()
	folk.persist = false
	app.add_child(folk)
	folk.setup(app)
	for i in 30: await physics_frame
	await stage(["postman", "sweeper", "kid", "lamplighter", "gentleman"], 12.0)
	focus(Vector2(-32.5, 37.2), 10.0)
	await capture("shadow-folk-day.png")
	await stage(["postman", "sweeper", "stroller", "lamplighter", "stargazer"], 21.5)
	focus(Vector2(-32.5, 37.2), 10.0)
	await capture("shadow-folk-night.png", 40)
	# Free walking: follow the postman for a few seconds, then a close look.
	app.daylight.override_hour = 16.5
	app.daylight.refresh(true)
	folk.clock = 0.0
	var postman: Node3D = named("postman")
	for walker in folk.walkers:
		if walker.state == "pause": walker.pause_left = 0.1
	for frame in 200:
		await physics_frame
		focus(postman.xz(), 6.0)
	await capture("shadow-folk-walk.png", 2)
	# A bridge crossing: put the gentleman at the start of the rope bridge.
	var gentleman: Node3D = named("gentleman")
	var paths = folk.paths
	var start: int = paths.nearest(Vector2(16.5, 27))
	var far: int = paths.nearest(Vector2(-10.3, 27))
	gentleman.position = gentleman.ground_point(paths.points[start], 0.1)
	gentleman.at_node = start
	gentleman.begin_lead(paths.route(start, far))
	folk.leader = null
	print("BRIDGE start ", gentleman.xz(), " state=", gentleman.state, " route=", gentleman.lead_route, " present=", gentleman.present)
	for frame in 420:
		if frame % 60 == 0: print("  t=", frame/60, " ", gentleman.xz(), " y=", snappedf(gentleman.position.y, 0.01), " ", gentleman.state)
		# The walker trails a few metres behind so the shadow does not wait.
		var behind: Vector2 = gentleman.xz()+Vector2(4.0, 0.6)
		app.player.position = Vector3(behind.x, gentleman.position.y, behind.y)
		await physics_frame
		focus(gentleman.xz(), 9.0)
	print("BRIDGE gentleman at ", gentleman.xz(), " y=", snappedf(gentleman.position.y, 0.01))
	await capture("shadow-folk-bridge.png", 2)
	quit()

func named(id: String) -> Node3D:
	for walker in folk.walkers:
		if walker.spec.id == id: return walker
	return null

## Puts the named shadows around the town green facing the camera.
func stage(ids: Array, hour: float) -> void:
	app.daylight.override_hour = hour
	app.daylight.refresh(true)
	folk.clock = 0.0
	await physics_frame
	var spots := [Vector2(-35.2, 36.4), Vector2(-32.6, 38.6), Vector2(-30.3, 36.6), Vector2(-28.4, 38.4), Vector2(-37.4, 38.2)]
	for i in ids.size():
		var walker: Node3D = named(ids[i])
		walker.set_present(true)
		walker.fade = 1.0
		walker.visible = true
		walker.position = walker.ground_point(spots[i], 0.05)
		walker.state = "pause"
		walker.pause_left = 999.0
		walker.look_clock = 999.0
		walker.face_yaw = [0.35, -0.1, -0.3, 0.15, 0.5][i]
		walker.has_face = true
		walker.visual.rotation.y = walker.face_yaw
		if i == 2: walker.smile(999.0)
	for walker in folk.walkers:
		if not walker.spec.id in ids and walker.xz().distance_to(Vector2(-32.5, 37.2)) < 12.0:
			walker.position = walker.ground_point(Vector2(-60, 48), 0.1)
	folk.night = Daylight.sample(hour).night
	for walker in folk.walkers: walker.set_night(folk.night)
	for i in 20: await physics_frame

func focus(at: Vector2, size: float) -> void:
	var from := Vector3(at.x, 60, at.y)
	var hit := app.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(from, from+Vector3.DOWN*80, Map.WALK_MASK))
	var target := Vector3(at.x, maxf(hit.get("position", Vector3(0, 1.2, 0)).y, 1.2), at.y)+Profile.CAMERA_FOCUS_OFFSET
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = size
	camera.position = target+Profile.CAMERA_OFFSET
	camera.look_at(target)
	camera.current = true

func capture(file: String, settle := 8) -> void:
	for i in settle: await process_frame
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	print("CAPTURE ", image.save_png(artifact(file)), " ", artifact(file))
