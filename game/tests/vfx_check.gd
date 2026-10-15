extends SceneTree
## Under-foot effects (foot_fx.gd) and expedition combat effects (combat_fx.gd), without a server.
## Checks every surface and every combat helper draws (Fx.played rises), hard floors stay empty,
## the shared budget caps a crowd, and nothing errors. With --capture (windowed) it lays every
## effect out on a stage and saves two moments as one sheet: artifacts/vfx_sheet.png.
const Fx := preload("res://scripts/fx.gd")
const FootFx := preload("res://scripts/foot_fx.gd")
const CombatFx := preload("res://scripts/combat_fx.gd")
const RpgUi := preload("res://scripts/rpg_ui.gd")

class FakeApp extends Node:
	var world: Node3D
	var player: CharacterBody3D
	var screen := "expedition"
	var ui: Control

var failures: Array[String] = []
var app: FakeApp
var feet: Node

func _initialize() -> void: call_deferred("run_test")

func check(ok: bool, what: String) -> void:
	print(("PASS " if ok else "FAIL ")+what)
	if not ok: failures.append(what)

func step(fx: String, surface: String, at: Vector3, gait := "walk", kind := "step", foot := 0, who := "hero") -> void:
	feet.on_stepped({"kind": kind, "who": who, "surface": surface, "fx": fx, "at": at, "speed": 4.0, "gait": gait, "foot": foot, "size": 1.0})

func build() -> void:
	app = FakeApp.new()
	app.name = "App"
	root.add_child(app)
	app.world = Node3D.new()
	app.world.name = "World"
	app.add_child(app.world)
	app.player = CharacterBody3D.new()
	app.world.add_child(app.player)
	var layer := CanvasLayer.new()
	app.add_child(layer)
	app.ui = Control.new()
	app.ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	app.ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(app.ui)
	feet = FootFx.attach(app, null)

func run_test() -> void:
	build()
	var capture := "--capture" in OS.get_cmdline_user_args()
	await process_frame
	# --- every surface kind draws, hard floors do not
	for pair in [["dust","sand"],["dust","dirt"],["dust","gravel"],["splash","shallow"],["snow","snow"],["leaves","leaves"],["grass","grass"]]:
		feet.tokens = FootFx.BANK
		var before := Fx.played
		app.player.velocity = Vector3(3, 0, 0)
		for i in 6: step(pair[0], pair[1], Vector3(i, 0, 0), "run", "step", i%2)
		check(Fx.played > before, "foot %s/%s draws" % [pair[0], pair[1]])
	feet.tokens = FootFx.BANK
	var hard := Fx.played
	step("", "stone", Vector3.ZERO)
	step("", "planks", Vector3.ZERO)
	check(Fx.played == hard, "hard floors draw nothing")
	# land and splash events
	feet.tokens = FootFx.BANK
	var before_land := Fx.played
	step("dust", "sand", Vector3.ZERO, "run", "land", -1)
	step("splash", "shallow", Vector3.ZERO, "run", "splash", -1)
	check(Fx.played >= before_land+4, "landing and splash draw rings and puffs")
	# --- the budget: 40 remote steps in one frame draw at most BANK
	feet.tokens = FootFx.BANK
	var drawn_before: int = feet.drawn
	for i in 40: step("dust", "dirt", Vector3(i*0.3, 0, 2), "walk", "step", -1, "remote")
	var crowd: int = feet.drawn-drawn_before
	check(crowd <= int(FootFx.BANK) and crowd >= 1, "crowd capped by the budget (%d drawn of 40)" % crowd)
	# --- combat helpers
	var c0 := Fx.played
	CombatFx.slash(app)
	CombatFx.slash(app, true)
	CombatFx.strike(app, Vector3(1, 0, -1))
	CombatFx.strike(app, Vector3(1, 0, -1), true)
	CombatFx.strike(app, Vector3(1, 0, -1), false, true)
	CombatFx.hurt(app)
	for kind in ["tree", "stone", "fiber", "berry", "other"]: CombatFx.harvest(app, kind, Vector3(-1, 0, 1))
	CombatFx.crafted(app)
	check(Fx.played-c0 >= 20, "combat helpers all draw (%d effects)" % (Fx.played-c0))
	for i in 30: await process_frame
	if capture: await shoot()
	print("VFX_CHECK %s failures=%d" % ["PASS" if failures.is_empty() else "FAIL", failures.size()])
	quit(0 if failures.is_empty() else 1)

# ------------------------------------------------------------------ capture
func stage() -> Camera3D:
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-55, -35, 0)
	sun.light_energy = 1.1
	app.world.add_child(sun)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color("7fa7c4")
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color("c9d6e0")
	env.environment.ambient_light_energy = 0.7
	app.world.add_child(env)
	# Ground strips per surface, back row (feet) and front row (combat).
	var strips := [["모래", Color("dcc9a0")], ["흙", Color("8d7152")], ["얕은 물", Color("4f8fa8")], ["눈", Color("eef3f8")], ["낙엽", Color("8a6a3c")], ["풀", Color("6f9c4c")]]
	for i in strips.size():
		var tile := MeshInstance3D.new()
		var plane := PlaneMesh.new()
		plane.size = Vector2(2.6, 3.4)
		tile.mesh = plane
		var m := StandardMaterial3D.new()
		m.albedo_color = strips[i][1]
		m.roughness = 1.0
		tile.material_override = m
		tile.position = Vector3(-6.5+i*2.6, 0, -2.2)
		app.world.add_child(tile)
		label(strips[i][0], tile.position+Vector3(0, 0.05, 1.9))
	var floor := MeshInstance3D.new()
	var big := PlaneMesh.new()
	big.size = Vector2(16, 4.6)
	floor.mesh = big
	var fm := StandardMaterial3D.new()
	fm.albedo_color = Color("6e7f5a")
	fm.roughness = 1.0
	floor.material_override = fm
	floor.position = Vector3(0, -0.01, 2.0)
	app.world.add_child(floor)
	var cam := Camera3D.new()
	cam.fov = 50
	app.world.add_child(cam)
	cam.look_at_from_position(Vector3(0, 7.2, 10.5), Vector3(0, 0.4, 0.2))
	cam.current = true
	return cam

func label(text: String, at: Vector3) -> void:
	var l := Label3D.new()
	l.text = text
	l.font = RpgUi.FONT_BOLD
	l.font_size = 40
	l.pixel_size = 0.006
	l.outline_size = 10
	l.modulate = Color("fff3c4")
	l.outline_modulate = Color(0.15, 0.1, 0.05)
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	l.position = at
	app.world.add_child(l)

func feet_walk(t: int) -> void:
	# A walker crossing each strip toward the camera, alternating feet, running.
	var pairs := [["dust","sand"],["dust","dirt"],["splash","shallow"],["snow","snow"],["leaves","leaves"],["grass","grass"]]
	app.player.velocity = Vector3(0, 0, 4)
	for i in pairs.size():
		feet.tokens = FootFx.BANK
		step(pairs[i][0], pairs[i][1], Vector3(-6.5+i*2.6, 0, -3.6+0.5*t), "run", "step", t%2)

func combat_all() -> void:
	app.player.position = Vector3(-6.0, 0, 1.0)
	CombatFx.slash(app, true, Vector3.BACK)
	app.player.position = Vector3(-6.0, 0, 2.2)
	CombatFx.strike(app, Vector3(-3.6, 0, 2.2))
	CombatFx.strike(app, Vector3(-1.2, 0, 2.2), true)
	CombatFx.harvest(app, "tree", Vector3(1.2, 0, 2.2))
	CombatFx.harvest(app, "stone", Vector3(3.2, 0, 2.2))
	CombatFx.harvest(app, "berry", Vector3(5.0, 0, 2.2))
	app.player.position = Vector3(6.6, 0, 2.2)
	CombatFx.crafted(app)
	app.player.position = Vector3(-6.0, 0, 2.2)
	CombatFx.hurt(app)

func shoot() -> void:
	# Let the checks' own puffs above finish first (smoke lives 2 s).
	for f in 200: await process_frame
	var cam := stage()
	for item in [["휘두르기", -6.0], ["타격", -3.6], ["처치", -1.2], ["나무 채집", 1.2], ["돌 채집", 3.2], ["열매", 5.0], ["제작", 6.6]]:
		label(item[0], Vector3(item[1], 0.05, 3.5))
	await process_frame
	var shots: Array[Image] = []
	# 1. under-foot: close on the strips while the walkers run.
	cam.look_at_from_position(Vector3(0, 3.6, 2.6), Vector3(0, 0.2, -2.0))
	for t in 7:
		feet_walk(t)
		for f in 5: await process_frame
	await RenderingServer.frame_post_draw
	shots.append(root.get_texture().get_image())
	# 2. combat: the blow's first instant (slash, flash, sparks) and a moment later (smoke, chips).
	cam.look_at_from_position(Vector3(0, 4.4, 11.6), Vector3(0, 0.5, 2.0))
	for f in 40: await process_frame
	combat_all()
	for f in 4: await process_frame
	await RenderingServer.frame_post_draw
	shots.append(root.get_texture().get_image())
	for f in 14: await process_frame
	await RenderingServer.frame_post_draw
	shots.append(root.get_texture().get_image())
	var w := shots[0].get_width()
	var h := shots[0].get_height()
	var sheet := Image.create(w, h*shots.size(), false, shots[0].get_format())
	for i in shots.size(): sheet.blit_rect(shots[i], Rect2i(0, 0, w, h), Vector2i(0, h*i))
	var path := ProjectSettings.globalize_path("res://../artifacts/vfx_sheet.png")
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	print("SHEET ", sheet.save_png(path), " ", path)
