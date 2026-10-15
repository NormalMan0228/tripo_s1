extends SceneTree
## The ISS-1 socket gizmo draws a crafted chair's sockets and the driver's state without errors, and
## nothing of it exists before it is switched on.
##   godot --headless --path game --script res://tests/ix_debug_check.gd
const Kit = preload("res://tests/ix_fixture_kit.gd")
const Driver = preload("res://scripts/ix/ix_driver.gd")

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var stage := Node3D.new()
	root.add_child(stage)
	Kit.floor_body(stage)
	var player: CharacterBody3D = load("res://scripts/player.gd").new()
	stage.add_child(player)
	var seat: Node = load("res://scripts/rest_seat.gd").new()
	stage.add_child(seat)
	seat.hero = player
	var chair := Kit.build(Kit.archetypes().seat)
	stage.add_child(chair)
	player.global_position = Vector3(0.3, 0.02, 1.2)
	for i in 6: await physics_frame
	var none_before := stage.find_children("IxDebug", "", true, false).is_empty()
	var gizmo: Node3D = load("res://scripts/ix/ix_debug.gd").new()
	gizmo.player = player
	gizmo.nodes = func() -> Array: return [chair]
	stage.add_child(gizmo)
	seat.crafted(chair, "sit")
	var labels := 0
	for i in 150:
		await physics_frame
		labels = maxi(labels, gizmo._used)
		if seat.driver.state == Driver.HOLD and i > 120: break
	var ok: bool = none_before and labels >= 2 and seat.driver.busy()
	seat.stand()
	for i in 60: await physics_frame
	print("IX_DEBUG_CHECK ", JSON.stringify({"ok": ok, "labels": labels, "state": seat.driver.state_name()}))
	quit(0 if ok else 1)
