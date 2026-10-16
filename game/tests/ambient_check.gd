extends SceneTree
## Village air life (ambient_fx.gd) without a server: fireflies at night, petals by day, nothing
## outside the village; --capture (windowed) saves night and day: artifacts/ambient.png.
const AmbientFx := preload("res://scripts/ambient_fx.gd")

class FakeLight extends Node:
	var current := {"night": 1.0}

class FakeApp extends Node:
	var world: Node3D
	var player: Node3D
	var screen := "village"
	var daylight: Node

var app: FakeApp
var env: Environment
var failures: Array[String] = []

func _initialize() -> void: call_deferred("run_test")

func check(ok: bool, what: String) -> void:
	print(("PASS " if ok else "FAIL ")+what)
	if not ok: failures.append(what)

func wait(seconds: float) -> void:
	var until := Time.get_ticks_msec()+int(seconds*1000.0)
	while Time.get_ticks_msec() < until: await process_frame

func run_test() -> void:
	var capture := "--capture" in OS.get_cmdline_user_args()
	app = FakeApp.new()
	root.add_child(app)
	app.world = Node3D.new()
	app.add_child(app.world)
	app.player = Node3D.new()
	app.world.add_child(app.player)
	app.daylight = FakeLight.new()
	app.add_child(app.daylight)
	if capture: stage()
	var air: Node = AmbientFx.attach(app)
	await wait(0.2)
	check(air.flies.emitting and not air.drift.emitting, "night: fireflies, no petals")
	var shots: Array[Image] = []
	if capture:
		await wait(3.5)
		shots.append(await shot())
	app.daylight.current = {"night": 0.0}
	if capture:
		env.background_color = Color("8fb3cf")
		env.ambient_light_color = Color("dfe7ee")
		env.ambient_light_energy = 1.0
	await wait(0.2)
	check(not air.flies.emitting and air.drift.emitting, "day: petals, no fireflies")
	if capture:
		await wait(4.0)
		shots.append(await shot())
	app.screen = "survival"
	await wait(0.2)
	check(not air.flies.emitting and not air.drift.emitting, "outside the village: nothing")
	check(air.flies.amount + air.drift.amount <= 40, "about forty particles at most (%d)" % (air.flies.amount + air.drift.amount))
	if capture:
		var w := shots[0].get_width()
		var h := shots[0].get_height()
		var sheet := Image.create(w*2, h, false, shots[0].get_format())
		for i in 2: sheet.blit_rect(shots[i], Rect2i(0, 0, w, h), Vector2i(w*i, 0))
		var path := ProjectSettings.globalize_path("res://../artifacts/ambient.png")
		print("SHEET ", sheet.save_png(path), " ", path)
	print("AMBIENT %s failures=%d" % ["PASS" if failures.is_empty() else "FAIL", failures.size()])
	quit(0 if failures.is_empty() else 1)

func stage() -> void:
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -30, 0)
	sun.light_energy = 0.25
	app.world.add_child(sun)
	var we := WorldEnvironment.new()
	env = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("121a2c")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("3a4a6e")
	env.ambient_light_energy = 0.7
	we.environment = env
	app.world.add_child(we)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(30, 30)
	ground.mesh = plane
	var m := StandardMaterial3D.new()
	m.albedo_color = Color("4f7a3e")
	ground.material_override = m
	app.world.add_child(ground)
	var cam := Camera3D.new()
	cam.fov = 55
	app.world.add_child(cam)
	cam.look_at_from_position(Vector3(0, 3.2, 8.0), Vector3(0, 1.2, 0))
	cam.current = true

func shot() -> Image:
	await RenderingServer.frame_post_draw
	return root.get_texture().get_image()
