extends SceneTree
## Campfire buff look (campfire_buff_fx.gd) on the real walker, fed run states shaped like the
## server's (docs/design/CAMPFIRE_BUFF_KO.md), without a server: barrier mode shows nothing; buff mode
## inside the radius flares, puts the rim on and starts the embers and heal shimmers; outside the
## after-heat fades it; with no buffs it ends (the rim stays on at strength 0 on the field, put on
## under the run's card so the fire's first warmth compiles nothing); a revived teammate pulses.
## --capture (windowed): artifacts/campfire_buff.png — off / flare / steady, at night.
const BuffFx := preload("res://scripts/campfire_buff_fx.gd")
const AvatarLook := preload("res://scripts/avatar_look.gd")
const RpgUi := preload("res://scripts/rpg_ui.gd")

class FakeApp extends Node:
	var world: Node3D
	var player: CharacterBody3D
	var screen := "survival"
	var ui: Control

var app: FakeApp
var failures: Array[String] = []

func _initialize() -> void: call_deferred("run_test")

func check(ok: bool, what: String) -> void:
	print(("PASS " if ok else "FAIL ")+what)
	if not ok: failures.append(what)

func state(mode: String, buffs: Array, players := []) -> Dictionary:
	return {"status": "active", "hp": 80.0, "fire_remaining": 20.0,
		"campfire": {"mode": mode, "active": true, "x": 1.6, "z": -1.4, "radius": 4.0}, "buffs": buffs, "players": players}

func overlaid() -> int:
	var n := 0
	for mesh in app.player.find_children("*", "MeshInstance3D", true, false):
		if mesh.material_overlay != null: n += 1
	return n

func wait(seconds: float) -> void:
	var until := Time.get_ticks_msec()+int(seconds*1000.0)
	while Time.get_ticks_msec() < until: await process_frame

func run_test() -> void:
	var capture := "--capture" in OS.get_cmdline_user_args()
	app = FakeApp.new()
	root.add_child(app)
	app.world = Node3D.new()
	app.add_child(app.world)
	app.player = AvatarLook.walker({}, -1)
	# As on an expedition: the server places the walker (no falling through the test's floor).
	app.player.visual_only = true
	app.world.add_child(app.player)
	var layer := CanvasLayer.new()
	app.add_child(layer)
	app.ui = Control.new()
	layer.add_child(app.ui)
	var shots: Array[Image] = []
	if capture: await stage()
	for i in 10: await process_frame
	var fx: Node = BuffFx.of(app)
	# barrier: nothing at all
	BuffFx.apply(app, state("barrier", []))
	await wait(0.3)
	check(fx.flares == 0 and fx.level < 0.01, "barrier mode shows nothing")
	# The rim is put on at strength 0 on the field, so the fire's first warmth compiles nothing.
	check(overlaid() > 0, "on the field the rim is already on (at strength 0)")
	if capture: shots.append(await shot())
	# buff, inside the radius
	var inside := [{"id": "campfire_regeneration", "remaining": 18.0, "hp_per_second": 0.6}, {"id": "warmed", "remaining": 5.0, "attack_multiplier": 1.1}]
	BuffFx.apply(app, state("buff", inside))
	await wait(0.18)
	if capture: shots.append(await shot())
	check(fx.flares == 1, "the buff starts with one flare")
	check(overlaid() > 0, "the rim is on the hero's meshes (%d)" % overlaid())
	await wait(1.7)
	check(fx.level > 0.95, "inside the radius the look is full (%.2f)" % fx.level)
	check(fx.shimmers >= 1, "heal ticks shimmer (%d)" % fx.shimmers)
	var ember: CPUParticles3D = app.player.get_node_or_null("BuffEmbers")
	check(ember != null and ember.emitting, "embers rise at the feet")
	if capture: shots.append(await shot())
	# outside: only the after-heat, 2.5 of 5 s left
	BuffFx.apply(app, state("buff", [{"id": "warmed", "remaining": 2.5, "attack_multiplier": 1.1}]))
	await wait(0.8)
	check(fx.level < 0.6 and fx.level > 0.2, "outside, the after-heat fades the look (%.2f)" % fx.level)
	# ended
	BuffFx.apply(app, state("buff", []))
	await wait(1.0)
	check(fx.level < 0.01, "with no buffs the look fades out (the rim stays on at strength 0)")
	# a teammate being revived pulses
	BuffFx.apply(app, state("buff", [], [{"x": -1.0, "z": 0.5, "revive": {"active": true, "progress": 0.4}}]))
	await wait(1.2)
	check(fx.pulses >= 1, "a revived teammate pulses (%d)" % fx.pulses)
	if capture: save(shots)
	print("CAMPFIRE_BUFF %s failures=%d" % ["PASS" if failures.is_empty() else "FAIL", failures.size()])
	quit(0 if failures.is_empty() else 1)

# ------------------------------------------------------------------ capture
func stage() -> void:
	var moon := DirectionalLight3D.new()
	moon.rotation_degrees = Vector3(-50, 30, 0)
	moon.light_energy = 0.35
	moon.light_color = Color("9fb4e6")
	app.world.add_child(moon)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color("141c2e")
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color("3a4a6e")
	env.environment.ambient_light_energy = 0.8
	app.world.add_child(env)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(14, 14)
	ground.mesh = plane
	var m := StandardMaterial3D.new()
	m.albedo_color = Color("3e5a34")
	ground.material_override = m
	app.world.add_child(ground)
	var fire := OmniLight3D.new()
	fire.light_color = Color("ff9a48")
	fire.light_energy = 1.6
	fire.omni_range = 6.0
	fire.position = Vector3(1.6, 0.8, -1.4)
	app.world.add_child(fire)
	var cam := Camera3D.new()
	cam.fov = 40
	app.world.add_child(cam)
	cam.look_at_from_position(Vector3(0.4, 1.7, 3.6), Vector3(0, 0.9, 0))
	cam.current = true
	await process_frame

func shot() -> Image:
	await RenderingServer.frame_post_draw
	return root.get_texture().get_image()

func save(shots: Array[Image]) -> void:
	var w := shots[0].get_width()
	var h := shots[0].get_height()
	var crop := Rect2i(w/4, 0, w/2, h)
	var sheet := Image.create(crop.size.x*shots.size(), h, false, shots[0].get_format())
	for i in shots.size(): sheet.blit_rect(shots[i], crop, Vector2i(crop.size.x*i, 0))
	var path := ProjectSettings.globalize_path("res://../artifacts/campfire_buff.png")
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	print("SHEET ", sheet.save_png(path), " ", path)
