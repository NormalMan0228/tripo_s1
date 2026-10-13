extends SceneTree
## Captures for the world-presentation pass (needs a window, no server):
##   artifacts/world-nameplate-before.png  a shadow on a village path with the road
##                                          ribbon drawn after its name (the order the
##                                          distance sort picked from some views)
##   artifacts/world-nameplate-after.png   the same with the road drawn first
##   artifacts/world-dialogue-<who>-<scale>.png  the dialogue window with an
##                                          illustrated speaker at UI scale 80/100/140 %
##   Godot --path game --script res://tests/world_polish_capture.gd [-- --shot=nameplate|dialogue]
const Stub = preload("res://tests/shadow_folk_stub.gd")
const Folk = preload("res://scripts/shadow_folk.gd")
const Map = preload("res://maps/archipelago/archipelago.gd")
const Daylight = preload("res://scripts/daylight.gd")
const Profile = preload("res://scripts/controller_profile.gd")
var app: Node3D
var folk: Node3D
var camera: Camera3D
var env: Environment
var sun: DirectionalLight3D
var shot := ""

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shot="): shot = arg.trim_prefix("--shot=")
	call_deferred("run")
	create_timer(240).timeout.connect(func(): quit(2))

func artifact(file: String) -> String:
	return ProjectSettings.globalize_path("res://../artifacts/"+file)

func run() -> void:
	seed(11)
	if shot == "dialogue":
		await dialogue()
		quit()
		return
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
	if shot in ["", "nameplate"]: await nameplate()
	quit()

## The dialogue window over a plain backdrop: a cast standee (waist-up) and two
## shadow standees (head and shoulders), at three interface sizes.
func dialogue() -> void:
	var RpgUi = load("res://scripts/rpg_ui.gd")
	var layer := CanvasLayer.new()
	root.add_child(layer)
	var back := ColorRect.new()
	back.color = Color("6d8f73")
	back.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	layer.add_child(back)
	for scale in [1.0, 1.4, 0.8]:
		root.content_scale_factor = scale
		for who in [["haeru", "res://assets/portraits/haeru.png"], ["postman", "res://assets/ui/shadow_postman.png"], ["farmer", "res://assets/ui/shadow_farmer.png"]]:
			var window: Dictionary = RpgUi.dialogue(back, who[0], who[1])
			window.body.text = "Line one of the conversation, long enough to wrap onto a second line in the box."
			await create_timer(0.6).timeout
			var standee: Control = window.get("standee")
			var box: Control = window.box
			if standee:
				print("DIALOGUE ", who[0], " scale=", scale, " standee=", standee.get_global_rect(), " box_top=", box.get_global_rect().position.y, " view=", back.size)
			await capture("world-dialogue-%s-%d.png" % [who[0], roundi(scale*100)], 2)
			window.root.queue_free()
			await process_frame
	root.content_scale_factor = 1.0

func named(id: String) -> Node3D:
	for walker in folk.walkers:
		if walker.spec.id == id: return walker
	return null

## Stands the postman on the cobbled road east of the town green and looks down the
## road, so the ribbon fills the frame behind his name.
func nameplate() -> void:
	var walker := named("postman")
	var spot := Vector2(-28.15, -26.5)
	for other in folk.walkers:
		if other != walker and other.xz().distance_to(spot) < 14.0: other.position = other.ground_point(Vector2(-60, 48), 0.1)
	walker.set_present(true)
	walker.fade = 1.0
	walker.visible = true
	walker.position = walker.ground_point(spot, 0.05)
	walker.state = "pause"
	walker.pause_left = 999.0
	walker.look_clock = 999.0
	walker.has_face = true
	walker.face_yaw = 0.3
	var road := app.town.find_child("RoadSurface", true, false) as MeshInstance3D
	var material := road.material_override as ShaderMaterial
	var fixed: int = material.render_priority
	focus(spot, 8.0)
	# The old failure: the island-wide ribbon sorted after the name and painted over it.
	material.render_priority = 10
	await capture("world-nameplate-before.png")
	material.render_priority = fixed
	await capture("world-nameplate-after.png")
	print("NAMEPLATE road_priority=", fixed, " plate_priority=", walker.nameplate.render_priority)

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
	image.resize(image.get_width()/2, image.get_height()/2)
	print("CAPTURE ", image.save_png(artifact(file)), " ", artifact(file))
