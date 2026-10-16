extends SceneTree
## Frame time on the first vs later campfire effects (windowed): does a first use hitch?
const CombatFx := preload("res://scripts/combat_fx.gd")
const BuffFx := preload("res://scripts/campfire_buff_fx.gd")
const AvatarLook := preload("res://scripts/avatar_look.gd")
class FakeApp extends Node:
	var world: Node3D
	var player: CharacterBody3D
	var screen := "survival"
	var ui: Control
	var flame: Node3D
var app: FakeApp
func _initialize() -> void: call_deferred("run")
func frames(label: String, n := 20) -> void:
	var worst := 0.0
	var last := Time.get_ticks_usec()
	for i in n:
		await process_frame
		var now := Time.get_ticks_usec()
		worst = maxf(worst, (now-last)/1000.0)
		last = now
	print("HITCH %s worst_ms=%.1f" % [label, worst])
func run() -> void:
	app = FakeApp.new(); root.add_child(app)
	app.world = Node3D.new(); app.add_child(app.world)
	var cam := Camera3D.new(); app.world.add_child(cam); cam.look_at_from_position(Vector3(0,2,5), Vector3(0,1,0)); cam.current = true
	var sun := DirectionalLight3D.new(); app.world.add_child(sun)
	app.player = AvatarLook.walker({}, -1); app.player.visual_only = true; app.world.add_child(app.player)
	app.flame = Node3D.new(); app.world.add_child(app.flame); app.flame.position = Vector3(1, 0, 0)
	var layer := CanvasLayer.new(); app.add_child(layer); app.ui = Control.new(); layer.add_child(app.ui)
	await frames("idle", 60)
	if "--warm" in OS.get_cmdline_user_args():
		CombatFx.warm_up(app, Vector3(0, 1.0, 0))
		await frames("warm_up", 60)
	CombatFx.fuel(app); await frames("fuel_first")
	await frames("idle2", 60)
	CombatFx.fuel(app); await frames("fuel_second")
	var run_state := {"status":"active","hp":80.0,"fire_remaining":20.0,"campfire":{"mode":"buff","active":true,"x":1.0,"z":0.0,"radius":4.0},"buffs":[{"id":"campfire_regeneration","remaining":10.0}]}
	BuffFx.apply(app, run_state); await frames("buff_first", 30)
	BuffFx.apply(app, {"campfire":{"mode":"buff"},"buffs":[]}); await frames("buff_off", 60)
	BuffFx.apply(app, run_state); await frames("buff_second", 30)
	for i in 2:
		var beast := preload("res://scripts/shadow_beast.gd").new()
		beast.kind = "wolf"
		beast.from_enemy({"id": "probe%d" % i, "kind": "wolf", "x": 1.5+i, "z": -1.0, "hp": 30.0, "max_hp": 30.0, "phase": "idle"})
		app.world.add_child(beast)
		beast.position = Vector3(1.5+i, 0, -1.0)
		await frames("beast_%s" % ["first", "second"][i])
	var beasts := app.world.get_children().filter(func(n): return n.has_method("die"))
	for i in mini(2, beasts.size()):
		beasts[i].die()
		await frames("death_%s" % ["first", "second"][i], 30)
	CombatFx.strike(app, Vector3(0.5,0,-1), true); await frames("strike_first")
	CombatFx.strike(app, Vector3(0.5,0,-1), true); await frames("strike_second")
	quit(0)
