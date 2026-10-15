extends SceneTree
## Tick trace of the real Player at one village spot (motion_continuity follow-up):
##   Godot --headless --fixed-fps 60 --path game --script res://tests/motion_diag.gd -- --from=x,z --to=x,z [--ticks=150]
const Stub = preload("res://tests/shadow_folk_stub.gd")
const Town = preload("res://scripts/town.gd")
const PlayerBody = preload("res://scripts/player.gd")

func _initialize() -> void: call_deferred("run")

func vec(name: String, fallback: Vector2) -> Vector2:
	for item in OS.get_cmdline_user_args():
		if item.begins_with("--"+name+"="):
			var parts := item.trim_prefix("--"+name+"=").split(",")
			return Vector2(float(parts[0]), float(parts[1]))
	return fallback

func run() -> void:
	var camera := Camera3D.new()
	root.add_child(camera)
	var app = Stub.new()
	root.add_child(app)
	app.build(camera)
	for i in 8: await physics_frame
	var player = PlayerBody.new()
	player.min_ground_y = Town.SHORE_MIN_Y
	app.add_child(player)
	var from := vec("from", Vector2(-33.23, 33.0))
	var to := vec("to", Vector2(-33, 37))
	player.global_position = Town.point(from, 0.15)
	var ticks := 150
	for item in OS.get_cmdline_user_args():
		if item.begins_with("--ticks="): ticks = int(item.trim_prefix("--ticks="))
	for i in 20: await physics_frame
	var last: Vector3 = player.global_position
	for i in ticks:
		var d := (to-Vector2(player.position.x, player.position.z)).normalized()
		for action in ["move_left", "move_right", "move_forward", "move_back"]: Input.action_release(action)
		if d.x > 0.05: Input.action_press("move_right", d.x)
		if d.x < -0.05: Input.action_press("move_left", -d.x)
		if d.y > 0.05: Input.action_press("move_back", d.y)
		if d.y < -0.05: Input.action_press("move_forward", -d.y)
		await physics_frame
		var p: Vector3 = player.global_position
		var hit := ""
		for c in player.get_slide_collision_count():
			var col := player.get_slide_collision(c)
			var body = col.get_collider()
			hit += " %s(L%d n=%s)" % [body.get_parent().name if body and body.get_parent() else "?", body.collision_layer if body is CollisionObject3D else -1, str(col.get_normal().snapped(Vector3.ONE*0.01))]
		print("T%03d p=%s d=%.3f dy=%+.3f floor=%s wall=%s lag=%.2f esc=%d%s" % [i, str(p.snapped(Vector3.ONE*0.01)), Vector2(p.x-last.x, p.z-last.z).length(), p.y-last.y, player.is_on_floor(), player.is_on_wall(), player.step_lag, player.trapped_escapes, hit])
		last = p
	quit(0)
