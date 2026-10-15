extends SceneTree
## The expedition walker faces where the player steers, never where a server correction nudges it
## (assignment 7: "캐릭터가 계속 특정 방향을 보는 버그"). The walker's position folds in each server
## answer a little at a time (main.gd predict_walker); those few-centimetre moves used to set the
## facing as if the player walked that way, so a standing walker kept turning toward the drift.
## Walks right, stops, then feeds corrections from other directions (standing and while walking up)
## and checks the visual yaw. Prints FACING PASS/FAIL lines and FACING_RESULT {json}.
## Usage: tools/test.ps1 -SkipServerTests -ClientScript survival_facing
const Main = preload("res://scripts/main.gd")
var app: Node3D
var failed := false
var result := {}

func _initialize() -> void:
	call_deferred("run")

func expect(value: bool, description: String) -> void:
	print(("FACING PASS " if value else "FACING FAIL ")+description)
	if not value: failed = true

## The yaw a walker heading along `motion` (x, z) turns to (player.gd: atan2(-x, -z)).
func yaw_of(motion: Vector2) -> float:
	return atan2(-motion.x, -motion.y)

func off(a: float, b: float) -> float:
	return absf(angle_difference(a, b))

## Holds `action` for `seconds`, then lets the walker settle.
func walk(action: String, seconds: float) -> void:
	Input.action_press(action)
	await create_timer(seconds*0.7).timeout
	result["mid_"+action] = [app.player.visual.rotation.y, app.player.external_motion, app.player.controls_enabled]
	await create_timer(seconds*0.3).timeout
	Input.action_release(action)
	await create_timer(0.5).timeout

## Feeds `count` server corrections of `step` metres each, `gap` seconds apart, and returns the
## largest turn away from `yaw` seen meanwhile.
func drift(step: Vector2, count: int, gap: float, yaw: float) -> float:
	var worst := 0.0
	for i in count:
		app.predict_fix += step
		var until := Time.get_ticks_msec()+int(gap*1000.0)
		while Time.get_ticks_msec() < until:
			await process_frame
			worst = maxf(worst, off(app.player.visual.rotation.y, yaw))
	return worst

## Frame by frame (the 77 continuity rule): the walker's largest one-frame move and turn.
## Rates per second, so a slow frame on a busy PC is not taken for a jump.
var last_pos := Vector3.INF
var last_yaw := 0.0
var last_at := 0
var max_step := 0.0
var max_turn := 0.0
var max_speed := 0.0
var max_turn_rate := 0.0
func watch_frame() -> void:
	if not is_instance_valid(app) or app.screen != "survival": return
	var p: Vector3 = app.player.position
	var y: float = app.player.visual.rotation.y
	var now := Time.get_ticks_usec()
	if last_pos != Vector3.INF and now > last_at:
		var dt := (now-last_at)/1000000.0
		var step := Vector2(p.x-last_pos.x, p.z-last_pos.z).length()
		var turn := absf(angle_difference(last_yaw, y))
		max_step = maxf(max_step, step)
		max_turn = maxf(max_turn, turn)
		max_speed = maxf(max_speed, step/dt)
		max_turn_rate = maxf(max_turn_rate, turn/dt)
	last_pos = p
	last_yaw = y
	last_at = now

func run() -> void:
	var server := preload("res://tests/qa_server.gd").url()
	app = Main.new()
	root.add_child(app)
	await create_timer(0.4).timeout
	await app.authenticate(true, server, "face_"+str(Time.get_ticks_msec()), "Facing-probe-password-1", "")
	await app.start_run("forest", "standard")
	await create_timer(2.0).timeout
	while app.ticking: await process_frame
	expect(app.world_movement_allowed(), "the expedition takes movement input")
	process_frame.connect(watch_frame)
	# 1. Walk right and stop: the walker faces right.
	await walk("move_right", 1.0)
	var right := yaw_of(Vector2(1, 0))
	result.after_walk = off(app.player.visual.rotation.y, right)
	expect(result.after_walk < 0.15, "faces right after walking right (off %.2f rad)" % result.after_walk)
	# 2. Standing still, server corrections pull the walker up, down and left (30 cm, then 2 cm steps).
	result.standing_big = await drift(Vector2(0, -0.3), 1, 1.0, right)
	result.standing_small = await drift(Vector2(0, 0.02), 8, 0.12, right)
	result.standing_back = await drift(Vector2(-0.25, 0), 1, 1.0, right)
	expect(result.standing_big < 0.15, "a 30 cm correction does not turn a standing walker (%.2f rad)" % result.standing_big)
	expect(result.standing_small < 0.15, "a run of 2 cm corrections does not turn it (%.2f rad)" % result.standing_small)
	expect(result.standing_back < 0.15, "a correction from behind does not turn it around (%.2f rad)" % result.standing_back)
	# 3. Walking up while a sideways correction folds in: the walker keeps facing up.
	Input.action_press("move_forward")
	await create_timer(0.5).timeout
	var up := yaw_of(Vector2(0, -1))
	result.walking_side = await drift(Vector2(0.35, 0), 3, 0.3, up)
	Input.action_release("move_forward")
	await create_timer(0.5).timeout
	expect(result.walking_side < 0.2, "a sideways correction while walking up keeps the walker facing up (%.2f rad)" % result.walking_side)
	result.after_up = off(app.player.visual.rotation.y, up)
	expect(result.after_up < 0.15, "faces up after walking up (off %.2f rad)" % result.after_up)
	# 4. A standing walker shows no walk cycle while a correction slides it a few centimetres.
	var clips := {}
	app.predict_fix += Vector2(0.06, 0.04)
	for i in 30:
		await process_frame
		clips[str(app.player.current_clip)] = true
	result.idle_clips = clips.keys()
	expect(not clips.has("walk") and not clips.has("run"), "a small correction keeps the idle clip (%s)" % [clips.keys()])
	process_frame.disconnect(watch_frame)
	result.max_step = max_step
	result.max_turn = max_turn
	result.max_speed = max_speed
	result.max_turn_rate = max_turn_rate
	# Sprint is 6.75 m/s, and a correction folds in at most 8x its size a second (30 cm: 2.4 m/s).
	# The turn eases (Profile.TURN_RESPONSE); a snap would be a half turn in one 16 ms frame (~190 rad/s).
	expect(max_speed < 9.5, "no teleport: the walker never outruns a sprint plus a fold (%.1f m/s, step %.3f m)" % [max_speed, max_step])
	expect(max_turn_rate < 30.0 and max_turn < 1.6, "no snap turn (%.1f rad/s, largest turn %.2f rad)" % [max_turn_rate, max_turn])
	print("FACING_RESULT "+JSON.stringify(result))
	quit(1 if failed else 0)
