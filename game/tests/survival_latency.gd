extends SceneTree
## Walks in an expedition through a slow link and checks the walker answers at once and stays
## in step with the server. Pass --server=http://127.0.0.1:<port> (a delaying proxy in front of
## the QA server); defaults to the QA server itself.
const Main = preload("res://scripts/main.gd")
var app: Node3D
var failed := false

func _initialize() -> void:
	call_deferred("run")

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func run() -> void:
	var server := "http://127.0.0.1:8766"
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--server="): server = argument.trim_prefix("--server=")
	app = Main.new()
	root.add_child(app)
	await create_timer(0.4).timeout
	await app.authenticate(true, server, "lag_"+str(Time.get_ticks_msec()), "Lag-probe-password-1", "")
	await app.start_run("forest", "standard")
	await create_timer(2.0).timeout
	while app.ticking: await process_frame
	var start_server := Vector2(app.run.x, app.run.z)
	var start_walker := Vector2(app.player.position.x, app.player.position.z)
	var first_sequence := int(app.run.sequence)
	Input.action_press("move_right")
	var started := Time.get_ticks_msec()
	var first_move_ms := -1
	var steps: Array[float] = []
	var last: float = app.player.position.x
	while Time.get_ticks_msec()-started < 2500:
		await process_frame
		var x: float = app.player.position.x
		if first_move_ms < 0 and x-start_walker.x > 0.05: first_move_ms = Time.get_ticks_msec()-started
		steps.append(x-last)
		last = x
	Input.action_release("move_right")
	var ticks := int(app.run.sequence)-first_sequence
	await create_timer(1.5).timeout
	var walker := Vector2(app.player.position.x, app.player.position.z)
	var server_at := Vector2(app.run.x, app.run.z)
	var backwards := steps.filter(func(s: float) -> bool: return s < -0.02).size()
	print("LATENCY first_move_ms=%d ticks_per_s=%.1f walked=%.2f server_walked=%.2f gap_after_stop=%.2f backwards_frames=%d frames=%d" % [first_move_ms, ticks/2.5, walker.x-start_walker.x, server_at.x-start_server.x, walker.distance_to(server_at), backwards, steps.size()])
	expect(first_move_ms >= 0 and first_move_ms < 120, "walker moves at once (%d ms)" % first_move_ms)
	expect(walker.distance_to(server_at) < 0.6, "walker settles where the server is")
	expect(backwards < 3, "no rubber-banding while walking")
	expect(server_at.x-start_server.x > 3.0, "server moved the walker at normal speed")
	quit(1 if failed else 0)
