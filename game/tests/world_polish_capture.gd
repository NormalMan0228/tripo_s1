extends SceneTree
## Captures for the world-presentation pass (needs a window, no server):
##   artifacts/world-nameplate-before.png  a shadow on a village path with the road
##                                          ribbon drawn after its name (the order the
##                                          distance sort picked from some views)
##   artifacts/world-nameplate-after.png   the same with the road drawn first
##   artifacts/world-dialogue-<who>-<scale>.png  the dialogue window with an
##                                          illustrated speaker at UI scale 80/100/140 %
##   artifacts/world-folk-day.png             the shadow folk's rounds at noon: villagers
##   artifacts/world-folk-dusk.png            the same five mid-dissolve at dusk
##   artifacts/world-folk-night.png           and at night: the shadows
##   artifacts/world-folk-lineup.png          all fifteen daytime villagers over their shadows
##   artifacts/world-folk-room-<hour>.png     the cafe at 13:00 (villagers) and 22:30
##   artifacts/world-gait-turn.png            strip of frames while the walker reverses
##                                          at a run (lower body during the turn)
##   artifacts/world-loading-<kind>.png      the loading card: game start over the cover
##                                          art, a room, an expedition
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
	if shot == "stairs":
		await stairs()
		quit()
		return
	if shot == "gait":
		await gait()
		quit()
		return
	if shot == "loading":
		await loading_cards()
		quit()
		return
	if shot == "room":
		for hour in [13.0, 22.5]:
			Engine.set_meta("interior_hour", hour)
			Engine.set_meta("studio_session", {"token":"", "url":"http://127.0.0.1:9", "room":"01_cafe"})
			var studio: Control = load("res://scenes/studio.tscn").instantiate()
			root.add_child(studio)
			await create_timer(2.0).timeout
			var names: Array = []
			for entry in studio.npcs.values(): names.append(str(entry.body.get("title")))
			print("ROOM hour=", hour, " ", names)
			await capture("world-folk-room-%d.png" % int(hour), 2)
			studio.queue_free()
			await process_frame
		Engine.remove_meta("interior_hour")
		quit()
		return
	if shot == "lineup":
		await lineup()
		quit()
		return
	if shot == "boot":
		# The real start: main.tscn shows the cover card while the village builds.
		change_scene_to_file("res://scenes/main.tscn")
		await process_frame
		await process_frame
		await capture("world-boot-loading.png", 0)
		await create_timer(6.0).timeout
		await capture("world-boot-title.png", 0)
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
	if shot in ["", "folk"]: await folk_day_night()
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

## Climbs the first stair of a few rooms and logs the walker's clip on the way.
func stairs() -> void:
	Engine.set_meta("interior_hour", 13.0)
	for room in ["home", "11_purple_house", "17_lighthouse"]:
		Engine.set_meta("studio_session", {"token":"", "url":"http://127.0.0.1:9", "room":room})
		var studio: Control = load("res://scenes/studio.tscn").instantiate()
		root.add_child(studio)
		await create_timer(1.0).timeout
		for record in studio.decor:
			if not record.has("link"): continue
			var front := Vector3(0, 0, 1).rotated(Vector3.UP, float(record.yaw))
			for distance in [0.7, 0.9, 1.1, 1.4]:
				var at: Vector3 = record.center+front*(float(record.half.y)+distance)
				at.y = 0
				if studio.can_stand(at):
					studio.hero.position = at
					break
			studio.update_camera(0.0, true)
			await create_timer(0.4).timeout
			if room == "home": await capture("world-stairs-idle.png", 0, false)
			studio.travel(record)
			var hero = studio.hero
			for i in 24:
				await create_timer(0.1).timeout
				print("STAIR %s %s t=%.1f y=%.2f clip=%s anim=%s playing=%s vel=%s ext=%s" % [room, record.kind, i*0.1, hero.position.y, hero.current_clip, hero.animation_player.current_animation, hero.animation_player.is_playing(), hero.locomotion_velocity, hero.external_velocity])
				if i == 7: await capture("world-stairs-%s.png" % room, 0, room != "home")
				if not studio.travelling: break
			break
		studio.queue_free()
		await process_frame
		await process_frame
	Engine.remove_meta("interior_hour")

## A walker on a plain floor reverses at a run; eight frames through the turn.
func gait() -> void:
	var stage := Node3D.new()
	root.add_child(stage)
	var floor_body := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(200, 1, 200)
	shape.shape = box
	shape.position.y = -0.5
	floor_body.add_child(shape)
	stage.add_child(floor_body)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(200, 200)
	ground.mesh = plane
	var paint := StandardMaterial3D.new()
	paint.albedo_color = Color("8fae84")
	ground.material_override = paint
	stage.add_child(ground)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-50, -30, 0)
	stage.add_child(light)
	var walker: CharacterBody3D = load("res://scripts/player.gd").new()
	stage.add_child(walker)
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 3.2
	stage.add_child(camera)
	camera.current = true
	var frames: Array[Image] = []
	Input.action_press("move_right")
	Input.action_press("run")
	for i in 70:
		await physics_frame
		frame_on(walker)
	Input.action_release("move_right")
	Input.action_press("move_left")
	for i in 24:
		await physics_frame
		frame_on(walker)
		if i % 3 == 0:
			await RenderingServer.frame_post_draw
			var image := root.get_texture().get_image()
			image.convert(Image.FORMAT_RGB8)
			image = image.get_region(Rect2i(440, 180, 400, 440))
			image.resize(200, 220)
			frames.append(image)
	Input.action_release("move_left")
	Input.action_release("run")
	var strip := Image.create(200*frames.size(), 220, false, Image.FORMAT_RGB8)
	for i in frames.size(): strip.blit_rect(frames[i], Rect2i(0, 0, 200, 220), Vector2i(i*200, 0))
	print("CAPTURE ", strip.save_png(artifact("world-gait-turn.png")))
	stage.queue_free()

func frame_on(walker: Node3D) -> void:
	var at: Vector3 = walker.global_position+Vector3(0, 0.9, 0)
	camera.position = at+Vector3(0, 1.6, 5.0)
	camera.look_at(at)

func loading_cards() -> void:
	var Transition = load("res://scripts/transition.gd")
	var veil = Transition.of(self)
	await process_frame
	for card in [["start", "", "start"], ["room", "나의 집", ""], ["run", "솔바람 숲", "run"]]:
		veil.loading(tr(card[1]), card[2])
		veil.cover()
		await create_timer(1.2).timeout
		await capture("world-loading-%s.png" % card[0], 2)
	await veil.fade_in()
	print("LOADING card_cleared=", not veil.card.visible)

## Five residents on the town green at noon, mid-change at dusk and at night.
func folk_day_night() -> void:
	var ids := ["postman", "sweeper", "kid", "lamplighter", "gentleman"]
	await stage(ids, 12.0)
	focus(Vector2(-32.5, 37.2), 9.0)
	await capture("world-folk-day.png")
	await stage(ids, 21.5)
	for walker in folk.walkers:
		if walker.spec.id in ids:
			walker.set_day(true, true)
			walker.set_day(false)
			walker.day_blend = 0.5
			walker.push_day()
	focus(Vector2(-32.5, 37.2), 9.0)
	await capture("world-folk-dusk.png", 2)
	for walker in folk.walkers:
		if walker.spec.id in ids: walker.set_day(false, true)
	await capture("world-folk-night.png", 4)
	var titles: Array = []
	for walker in folk.walkers:
		if walker.spec.id in ids: titles.append(walker.title)
	print("FOLK night titles ", titles)

func stage(ids: Array, hour: float) -> void:
	app.daylight.override_hour = hour
	app.daylight.refresh(true)
	folk.clock = 0.0
	await physics_frame
	await physics_frame
	# One schedule pass picks the looks for the hour; then the module holds still so
	# nobody walks home mid-capture.
	folk.set_process(false)
	var spots := [Vector2(-35.2, 36.4), Vector2(-32.6, 38.6), Vector2(-30.3, 36.6), Vector2(-28.4, 38.4), Vector2(-37.4, 38.2)]
	for i in ids.size():
		var walker: Node3D = named(ids[i])
		walker.set_present(true)
		# Just under full, so the next step pushes the presence to every material.
		walker.fade = 0.999
		walker.visible = true
		walker.position = walker.ground_point(spots[i], 0.05)
		walker.state = "pause"
		walker.pause_left = 999.0
		walker.look_clock = 999.0
		walker.face_yaw = [0.35, -0.1, -0.3, 0.15, 0.5][i]
		walker.has_face = true
		walker.visual.rotation.y = walker.face_yaw
	for walker in folk.walkers:
		if not walker.spec.id in ids and walker.xz().distance_to(Vector2(-32.5, 37.2)) < 12.0:
			walker.position = walker.ground_point(Vector2(-60, 48), 0.1)
	for i in 20: await physics_frame
	var titles: Array = []
	for id in ids: titles.append("%s=%s" % [id, named(id).title])
	print("FOLK hour=", hour, " ", titles)

## Every resident twice on a plain floor: the daytime villager in front, the shadow behind.
func lineup() -> void:
	var stage := Node3D.new()
	root.add_child(stage)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(60, 30)
	ground.mesh = plane
	var paint := StandardMaterial3D.new()
	paint.albedo_color = Color("9cb88f")
	ground.material_override = paint
	stage.add_child(ground)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-45, -25, 0)
	stage.add_child(light)
	var world := WorldEnvironment.new()
	world.environment = Environment.new()
	world.environment.background_mode = Environment.BG_COLOR
	world.environment.background_color = Color("cfe3e8")
	world.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	world.environment.ambient_light_color = Color.WHITE
	world.environment.ambient_light_energy = 0.55
	stage.add_child(world)
	var Figure = load("res://scripts/shadow_figure.gd")
	var ids: Array = load("res://scripts/day_folk.gd").LOOKS.keys()
	for i in ids.size():
		for day in [true, false]:
			var who: Node3D = Figure.create_still(ids[i])
			stage.add_child(who)
			who.position = Vector3((i-(ids.size()-1)*0.5)*0.95, 0, 0.0 if day else -1.6)
			who.face(0.0)
			who.set_day(day, true)
			who.nameplate.visible = false
	# The player's own look at the end of the row, for comparison.
	var player: CharacterBody3D = load("res://scripts/player.gd").new()
	player.controls_enabled = false
	player.visual_only = true
	player.facing = Vector3(0, 0, 1)
	stage.add_child(player)
	player.position = Vector3((ids.size()+0.5-(ids.size()-1)*0.5)*0.95, 0, 0)
	player.visual.rotation.y = PI
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 9.6
	stage.add_child(camera)
	camera.position = Vector3(0.5, 2.6, 9.0)
	camera.look_at(Vector3(0.5, 0.9, -0.8))
	camera.current = true
	await create_timer(1.0).timeout
	await capture("world-folk-lineup.png", 2, false)
	stage.queue_free()

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

func capture(file: String, settle := 8, half := true) -> void:
	for i in settle: await process_frame
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	if half: image.resize(image.get_width()/2, image.get_height()/2)
	print("CAPTURE ", image.save_png(artifact(file)), " ", artifact(file))
