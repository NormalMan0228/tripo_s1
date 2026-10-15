extends Node
## ISS-1 interaction driver: takes a walker onto a socket and off it again with no jump.
##   CLAIM -> APPROACH -> ALIGN -> ENTER -> HOLD -> EXIT -> RECOVER   (ABORT from anywhere)
## CLAIM picks the nearest free, valid socket and a free feet point in front of it; APPROACH walks
## there (the player's own physics in the village, studio.move_hero in rooms); ALIGN slides the last
## centimetres and turns round (<= 10 rad/s); ENTER plays the procedural virtual clip (the body
## eases back and down while the pose layer bends the legs); HOLD follows a moving seat every tick;
## EXIT is the mirror image to a free feet point; RECOVER hands the walker back facing out of the
## seat. Every body move happens inside player._physics_process (render interpolation stays on),
## at most 0.08 m and 0.35 rad of visual yaw per tick.
##
## Safety: movement input cancels APPROACH/ALIGN at once and ends HOLD; E/Esc go through
## request_exit(); a foreign move (a door, a teleport) aborts and leaves the body where it was put;
## any state that overruns its time is aborted; control always comes back.
const IxMath = preload("res://scripts/ix/ix_math.gd")
const IxSources = preload("res://scripts/ix/ix_sources.gd")
const IxRig = preload("res://scripts/ix/ix_rig.gd")
const IxPose = preload("res://scripts/ix/ix_pose.gd")

enum {IDLE, APPROACH, ALIGN, ENTER, HOLD, EXIT, RECOVER, ABORT}
const STATE_NAMES := ["idle", "approach", "align", "enter", "hold", "exit", "recover", "abort"]
const MOVE_THRESHOLD := 0.3
## A movement key shortens getting up (0.8: the per-tick bound still holds for the longest step).
const FAST_EXIT := 0.8
const ARRIVE := 0.10
const SKIP_APPROACH := 0.12
const MAX_START := 2.6
const SHORT_ALIGN := 1.2
## Seconds a state may last before the driver gives up and hands control back.
const WATCHDOG := {APPROACH: 4.0, ALIGN: 1.0, ENTER: 2.5, EXIT: 2.5, RECOVER: 0.5, ABORT: 0.5}

## Who sits where: "<object instance id>:<socket id or group>" -> actor instance id.
static var claims := {}

var state := IDLE
var state_time := 0.0
var actor: Node3D
## "sit" or "lie" while seated (rest_seat's mode); the pose variant ("sit", "sit_low", "perch", ...).
var kind := ""
var variant := ""
var socket: Dictionary = {}
var entry: Dictionary = {}
var target: Node3D
var pose: SkeletonModifier3D
var m: Dictionary = {}
## Strategies: mover(direction: Vector3, delta) for rooms (empty: the player's own steer); whether
## movement input counts now; whether a feet point is free.
var mover := Callable()
var input_allowed := Callable()
var free_check := Callable()
var on_done := Callable()
var on_settled := Callable()

var approach := {}
var exit_point := Vector3.ZERO
var enter_from := Vector3.ZERO
var hold_at := Vector3.ZERO
var edge_at := Vector3.ZERO
var yaw_now := 0.0
var socket_yaw := 0.0
var lie_yaw := 0.0
var align_from := Vector3.ZERO
var phase_t := 0.0
var phase_len := 0.0
var lie_phase := 0
var exit_requested := false
var exit_fast := false
var was_visual_only := false
var last_written := Vector3.INF
var best_distance := INF
var stall := 0.0
var claim_key := ""
## The planted leg angles of the seat (a bed's edge before lying back).
var sit_legs := Vector2.ZERO
## The carrier's turn in the object's frame when the walker sat down (its rock is measured from it).
var carrier_rest := Basis.IDENTITY
var fade_from := 0.0
## Measured each tick, for the lab and the tests.
var contact_error := 0.0
var max_step := 0.0
var max_yaw_step := 0.0
var phases: Array = []
var max_step_at := ""
var align_speed := 0.0
var max_yaw_at := ""
var why := ""

func busy() -> bool: return state != IDLE
func seated() -> bool: return state in [ENTER, HOLD, EXIT]
## The walker's own movement is taken over (APPROACH through EXIT).
func locks_input() -> bool: return state in [APPROACH, ALIGN, ENTER, HOLD, EXIT, RECOVER]
func state_name() -> String: return STATE_NAMES[state]

## Starts an interaction: {node | record, hint "sit"/"lie", socket_id}. False (and nothing changes)
## when there is no free, valid socket within reach.
func begin(opts: Dictionary) -> bool:
	if busy() or not is_instance_valid(actor) or not actor.is_inside_tree(): return false
	var entries: Array = []
	if opts.has("record"):
		entries = IxSources.for_room(opts.record)
		target = opts.record.get("node")
	elif opts.has("node") and is_instance_valid(opts.node):
		target = opts.node
		entries = IxSources.for_node(target, str(opts.get("hint", "")))
	if entries.is_empty() or not is_instance_valid(target): return false
	var hint := str(opts.get("hint", "sit"))
	var types := ["lie"] if hint == "lie" else ["sit", "perch", "sit_ground"]
	var pick := choose(entries, types, str(opts.get("socket_id", "")))
	if pick.is_empty() and hint == "lie": pick = choose(entries, ["sit", "perch"], "")
	if pick.is_empty():
		why = "no_socket"
		return false
	socket = pick.socket
	entry = pick.entry
	approach = pick.approach
	approach.pos = clear_spot(approach.pos, Vector3(approach.pos.x - socket.origin.x, 0, approach.pos.z - socket.origin.z))
	if actor.global_position.distance_to(approach.pos) > MAX_START + 0.5:
		why = "far"
		return false
	claim_key = key_of(target, socket)
	if is_instance_valid(entry.get("carrier")): carrier_rest = target.global_basis.orthonormalized().inverse() * (entry.carrier as Node3D).global_basis.orthonormalized()
	claims[claim_key] = actor.get_instance_id()
	kind = "lie" if socket.type == "lie" else "sit"
	variant = "lie" if socket.type == "lie" else IxMath.sit_variant(float(socket.height))
	if socket.type == "perch": variant = "perch"
	m = IxRig.measure(actor.hand_skeleton, actor.visual) if "hand_skeleton" in actor and is_instance_valid(actor.hand_skeleton) else IxRig.fallback()
	socket_yaw = float(socket.yaw)
	was_visual_only = bool(actor.visual_only) if "visual_only" in actor else false
	exit_requested = false
	exit_fast = false
	max_step = 0.0
	max_yaw_step = 0.0
	phases.clear()
	why = ""
	yaw_now = IxMath.yaw_of(actor.facing) if actor.facing.length_squared() > 0.01 else socket_yaw
	if "ix" in actor: actor.ix = self
	ensure_pose()
	var flat := Vector2(actor.global_position.x - approach.pos.x, actor.global_position.z - approach.pos.z).length()
	if flat <= SKIP_APPROACH: go(ALIGN)
	else: go(APPROACH)
	return true

## The best {socket, entry, approach} for this walker, or {} when none is free and valid.
func choose(entries: Array, types: Array, wanted_id: String) -> Dictionary:
	var best := {}
	var best_score := INF
	var here: Vector3 = actor.global_position
	var facing_yaw := IxMath.yaw_of(actor.facing) if actor.facing.length_squared() > 0.01 else 0.0
	for e in entries:
		var r := IxSources.resolve(e)
		if not r.get("valid", false) or not str(r.type) in types: continue
		if not wanted_id.is_empty() and str(r.id) != wanted_id: continue
		var key := key_of(target, r)
		if claims.has(key) and int(claims[key]) != actor.get_instance_id() and is_instance_id_valid(int(claims[key])): continue
		var ranked := IxMath.rank_approach(r.approach, here, facing_yaw, func(p): return spot_free(p))
		if ranked.is_empty(): continue
		var a: Dictionary = ranked[0]
		var score := float(a.score) + Vector2(here.x - r.origin.x, here.z - r.origin.z).length() * 0.5
		if score < best_score:
			best_score = score
			best = {"socket": r, "entry": e, "approach": a}
	return best

static func key_of(node: Node, resolved: Dictionary) -> String:
	var group := str(resolved.get("entry", {}).get("rec", {}).get("group", ""))
	return "%d:%s" % [node.get_instance_id() if is_instance_valid(node) else 0, group if not group.is_empty() else str(resolved.get("id", ""))]

## E / Esc or a movement key: cancel an approach, end a hold; buffered during ENTER.
func request_exit(fast := false) -> void:
	match state:
		APPROACH, ALIGN: cancel("input")
		ENTER:
			exit_requested = true
			exit_fast = exit_fast or fast
		HOLD: start_exit(fast)

## Stops at once: the body stays where it is (it was moved by something else) and gets its
## controls back; the pose fades out over 0.15 s.
func abort(reason := "") -> void:
	if state in [IDLE, ABORT]: return
	why = reason
	hand_back(false)
	fade_from = pose.weight if is_instance_valid(pose) else 0.0
	go(ABORT)

## Called by player._physics_process right after tick_from, while busy().
func drive(body: Node3D, delta: float) -> void:
	if body != actor: return
	state_time += delta
	if WATCHDOG.has(state) and state_time > float(WATCHDOG[state]):
		abort("timeout")
	if state == ABORT:
		_fade(delta)
		return
	if not is_instance_valid(target) or not target.is_inside_tree():
		if state in [ENTER, HOLD]: start_exit(true)
		elif state in [APPROACH, ALIGN]:
			cancel("gone")
			return
	# Something else moved the walker (a door, a teleport, a scene change): let it go.
	if state in [ALIGN, ENTER, HOLD, EXIT] and last_written.is_finite() and actor.global_position.distance_to(last_written) > 0.05:
		abort("moved")
		return
	ensure_pose()
	var moving := movement()
	var before: Vector3 = actor.global_position
	var yaw_before := yaw_now
	# The tick ALIGN takes the yaw over from the walker's own turning is not a driver turn.
	var took_over := state == APPROACH
	match state:
		APPROACH: _approach(delta, moving)
		ALIGN: _align(delta, moving)
		ENTER: _enter(delta, moving)
		HOLD: _hold(delta, moving)
		EXIT: _exit(delta, moving)
		RECOVER: _recover()
	if state in [ALIGN, ENTER, HOLD, EXIT] or (state == IDLE and phases.size() > 1):
		var step := actor.global_position.distance_to(before)

		if step > max_step:
			max_step = step
			max_step_at = "%s/%d %.2f" % [STATE_NAMES[state], lie_phase, phase_t]
		var turn := absf(angle_difference(yaw_before, yaw_now)) if not took_over else 0.0
		if turn > max_yaw_step:
			max_yaw_step = turn
			max_yaw_at = "%s/%d %.2f" % [STATE_NAMES[state], lie_phase, phase_t]

func movement() -> Vector2:
	if input_allowed.is_valid() and not input_allowed.call(): return Vector2.ZERO
	return Input.get_vector("move_left", "move_right", "move_forward", "move_back")

func go(next: int) -> void:
	state = next
	state_time = 0.0
	phase_t = 0.0
	phases.append(STATE_NAMES[next])
	match next:
		APPROACH:
			best_distance = INF
			stall = 0.0
		ALIGN:
			hold_body()
			# Take over from where the walker really faces (it turned while walking up).
			if "visual" in actor and is_instance_valid(actor.visual): yaw_now = wrapf(actor.visual.rotation.y - PI, -PI, PI)
			align_from = actor.global_position
			align_speed = (actor.locomotion_velocity as Vector2).length() if "locomotion_velocity" in actor else 0.0
			var target_pos: Vector3 = approach.pos
			enter_from = Vector3(target_pos.x, actor.global_position.y, target_pos.z)
			var distance := Vector2(enter_from.x - align_from.x, enter_from.z - align_from.z).length()
			phase_len = IxMath.align_duration(distance, angle_difference(yaw_now, socket_yaw))
		ENTER:
			lie_phase = 0
			plan_enter()
		EXIT:
			lie_phase = 0
		RECOVER:
			pass

# ------------------------------------------------------------------ states

func _approach(delta: float, moving: Vector2) -> void:
	if moving.length() > MOVE_THRESHOLD:
		cancel("input")
		return
	var here: Vector3 = actor.global_position
	var to: Vector3 = approach.pos
	var flat := Vector2(to.x - here.x, to.z - here.z)
	var distance := flat.length()
	if state_time < delta * 1.5 and distance > MAX_START:
		cancel("far")
		return
	if distance <= ARRIVE:
		_stop_steer()
		go(ALIGN)
		return
	if distance < best_distance - 0.02:
		best_distance = distance
		stall = 0.0
	else:
		stall += delta
	if stall > 0.5 or state_time > 3.0:
		_stop_steer()
		if distance <= SHORT_ALIGN: go(ALIGN)
		else: cancel("blocked")
		return
	var pace := clampf(distance / 0.5, 0.2, 1.0)
	var direction := flat / distance * pace
	if mover.is_valid():
		mover.call(Vector3(direction.x, 0, direction.y), delta)
	elif "steer" in actor:
		actor.steer = direction

func _align(delta: float, moving: Vector2) -> void:
	if moving.length() > MOVE_THRESHOLD:
		cancel("input")
		return
	phase_t += delta
	var u := clampf(phase_t / maxf(0.01, phase_len), 0.0, 1.0)
	var turn := angle_difference(yaw_now, socket_yaw)
	yaw_now = IxMath.turn_toward(yaw_now, socket_yaw, IxMath.TURN_RATE, delta)
	write(align_from.lerp(enter_from, smoothstep(0.0, 1.0, u)))
	face()
	# A big turn on the spot plays steps; the arrival pace eases out instead of stopping dead (the
	# walk clip and foot contacts let go gradually).
	if "external_velocity" in actor:
		var f := IxMath.dir_of(yaw_now)
		align_speed = move_toward(align_speed, 0.6 if absf(turn) > deg_to_rad(60.0) else 0.0, 5.0 * delta)
		actor.external_velocity = Vector2(f.x, f.z) * align_speed
		actor.external_motion = Vector2.ZERO
	if u >= 1.0 and absf(angle_difference(yaw_now, socket_yaw)) < 0.01:
		go(ENTER)

## The hold root and, for a bed, the edge seat before lying back.
func plan_enter() -> void:
	refresh_socket()
	var point: Vector3 = socket.origin
	if kind == "lie":
		var fwd := IxMath.dir_of(socket_yaw)
		var width := float(socket.params.get("width", 0.9))
		var edge_point := point + fwd * clampf(width * 0.5 - 0.22, 0.05, 0.4)
		edge_at = IxMath.hold_root(edge_point, socket_yaw, m.seat_contact)
		var basis: Basis = socket.basis
		var head_left := str(socket.params.get("head", "l")) == "l"
		lie_yaw = IxMath.yaw_of(-basis.x if head_left else basis.x)
		hold_at = IxMath.hold_root(point + Vector3(0, float(m.lie_lift), 0), lie_yaw, m.pelvis)
		set_pose("sit", float(socket.height))
	else:
		hold_at = IxMath.hold_root(point, socket_yaw, m.seat_contact)
		set_pose(variant, float(socket.height))
	if is_instance_valid(pose):
		pose.mode = kind
		pose.carrier = Basis.IDENTITY

func set_pose(preset: String, height: float) -> void:
	if not is_instance_valid(pose): return
	pose.set_preset(preset)
	if preset in ["sit", "sit_low"]:
		pose.plant_legs(m, height + float(m.seat_drop) - float(m.ankle))
	sit_legs = Vector2(pose.thigh, pose.calf)

func _enter(delta: float, moving: Vector2) -> void:
	if moving.length() > MOVE_THRESHOLD:
		exit_requested = true
		exit_fast = true
	phase_t += delta
	if kind == "lie" and lie_phase == 1:
		var len2 := float(IxMath.ENTER_SECONDS.lie)
		var u := clampf(phase_t / len2, 0.0, 1.0)
		var s := smoothstep(0.0, 1.0, u)
		refresh_socket()
		hold_at = IxMath.hold_root(Vector3(socket.origin) + Vector3(0, float(m.lie_lift), 0), lie_yaw, m.pelvis)
		write(edge_at.lerp(hold_at, s))
		yaw_now = lerp_angle(socket_yaw, lie_yaw, s)
		face()
		if is_instance_valid(pose):
			pose.blend_presets("sit", "lie", s)
			pose.thigh = lerpf(sit_legs.x, float(IxPose.PRESETS.lie[0]), s)
			pose.calf = lerpf(sit_legs.y, float(IxPose.PRESETS.lie[1]), s)
			pose.tilt = lerpf(0.0, PI * 0.5 - deg_to_rad(float(socket.params.get("recline_deg", 0.0))), s)
			pose.weight = 1.0
		if u >= 1.0: _settled()
		return
	if kind != "lie":
		refresh_socket()
		hold_at = IxMath.hold_root(socket.origin, socket_yaw, m.seat_contact)
	var goal := edge_at if kind == "lie" else hold_at
	var length := maxf(float(IxMath.ENTER_SECONDS.get("lie_sit" if kind == "lie" else variant, 0.55)), enter_from.distance_to(goal) * 0.5)
	var u := clampf(phase_t / length, 0.0, 1.0)
	write(IxMath.enter_curve(u, enter_from, goal))
	yaw_now = socket_yaw
	face()
	if is_instance_valid(pose): pose.weight = IxMath.enter_weight(u)
	if "external_velocity" in actor: actor.external_velocity = Vector2.ZERO
	if u >= 1.0:
		if kind == "lie":
			lie_phase = 1
			phase_t = 0.0
		else: _settled()

func _settled() -> void:
	go(HOLD)
	if on_settled.is_valid(): on_settled.call()
	if exit_requested: start_exit(exit_fast)

func _hold(delta: float, moving: Vector2) -> void:
	phase_t += delta
	refresh_socket()
	var point: Vector3 = socket.origin
	if kind == "lie": hold_at = IxMath.hold_root(point + Vector3(0, float(m.lie_lift), 0), lie_yaw, m.pelvis)
	else: hold_at = IxMath.hold_root(point, socket_yaw, m.seat_contact)
	write(hold_at)
	face()
	# A rocking or swinging carrier tilts the pose, never the body.
	if is_instance_valid(pose):
		pose.weight = 1.0
		pose.carrier = carrier_tilt()
	if moving.length() > MOVE_THRESHOLD and phase_t > 0.2: start_exit(true)

func start_exit(fast: bool) -> void:
	if not state in [ENTER, HOLD]: return
	exit_fast = fast
	refresh_socket()
	# The way out: the approach spot when it is still free, else the best free one.
	var points: Array = socket.get("approach", [])
	var ranked := IxMath.rank_approach(points, actor.global_position, socket_yaw, func(p): return spot_free(p))
	var out: Vector3 = approach.pos
	if not spot_free(out) and not ranked.is_empty() and bool(ranked[0].free): out = ranked[0].pos
	# Never hand the walker back inside something: step the spot out of the seat until it is free.
	out = clear_spot(out, Vector3(out.x - socket.origin.x, 0, out.z - socket.origin.z))
	exit_point = Vector3(out.x, enter_from.y if absf(enter_from.y - out.y) < 0.3 else out.y, out.z)
	hold_at = actor.global_position
	edge_at = IxMath.hold_root(Vector3(socket.origin) + IxMath.dir_of(socket_yaw) * clampf(float(socket.params.get("width", 0.9)) * 0.5 - 0.22, 0.05, 0.4), socket_yaw, m.seat_contact) if kind == "lie" else hold_at
	if is_instance_valid(pose): pose.carrier = Basis.IDENTITY
	go(EXIT)

func _exit(delta: float, moving: Vector2) -> void:
	phase_t += delta
	if kind == "lie" and lie_phase == 0:
		var len1 := float(IxMath.EXIT_SECONDS.lie) * (FAST_EXIT if exit_fast else 1.0)
		var u := clampf(phase_t / len1, 0.0, 1.0)
		var s := smoothstep(0.0, 1.0, u)
		write(hold_at.lerp(edge_at, s))
		yaw_now = lerp_angle(lie_yaw, socket_yaw, s)
		face()
		if is_instance_valid(pose):
			pose.blend_presets("lie", "sit", s)
			pose.thigh = lerpf(float(IxPose.PRESETS.lie[0]), sit_legs.x, s)
			pose.calf = lerpf(float(IxPose.PRESETS.lie[1]), sit_legs.y, s)
			pose.tilt = lerpf(PI * 0.5 - deg_to_rad(float(socket.params.get("recline_deg", 0.0))), 0.0, s)
			pose.weight = 1.0
		if u >= 1.0:
			lie_phase = 1
			phase_t = 0.0
			set_pose("sit", float(socket.height))
		return
	var from := edge_at if kind == "lie" else hold_at
	# Longer for a far exit spot, so no tick moves the body more than the bound.
	var length := maxf(float(IxMath.EXIT_SECONDS.get("lie_sit" if kind == "lie" else variant, 0.5)) * (FAST_EXIT if exit_fast else 1.0), from.distance_to(exit_point) * 0.5)
	var u := clampf(phase_t / length, 0.0, 1.0)
	write(IxMath.exit_curve(u, from, exit_point))
	yaw_now = socket_yaw
	face()
	if is_instance_valid(pose): pose.weight = IxMath.exit_weight(u)
	if u >= 1.0 or (u >= 0.8 and moving.length() > MOVE_THRESHOLD):
		# Walking off early: the walker is let go where it is (its own walk takes the last centimetres).
		if u < 1.0: exit_point = actor.global_position
		go(RECOVER)
		_recover()

func _recover() -> void:
	write(exit_point)
	if is_instance_valid(pose):
		pose.weight = 0.0
		pose.mode = ""
	hand_back(true)
	go(IDLE)
	phases.append("done")
	if on_done.is_valid(): on_done.call()

func _fade(delta: float) -> void:
	if is_instance_valid(pose):
		pose.weight = move_toward(pose.weight, 0.0, maxf(fade_from, 0.01) * delta / 0.15)
		if pose.weight <= 0.0:
			pose.mode = ""
			go(IDLE)
	else: go(IDLE)

func cancel(reason: String) -> void:
	why = reason
	_stop_steer()
	hand_back(false)
	if is_instance_valid(pose):
		pose.weight = 0.0
		pose.mode = ""
	go(IDLE)
	if on_done.is_valid(): on_done.call()

## Controls back: physics, facing, claim. facing_out turns the walker to face out of the seat.
func hand_back(facing_out: bool) -> void:
	_stop_steer()
	if is_instance_valid(actor):
		if "visual_only" in actor: actor.visual_only = was_visual_only
		if "face_override" in actor: actor.face_override = NAN
		if facing_out:
			actor.facing = IxMath.dir_of(socket_yaw)
			if "visual" in actor and is_instance_valid(actor.visual): actor.visual.rotation.y = socket_yaw + PI
		if actor is CharacterBody3D: actor.velocity = Vector3.ZERO
		if "external_velocity" in actor:
			actor.external_velocity = Vector2.ZERO
			actor.external_motion = Vector2.ZERO
	if claims.get(claim_key, -1) == (actor.get_instance_id() if is_instance_valid(actor) else -2): claims.erase(claim_key)
	claim_key = ""
	last_written = Vector3.INF

# ------------------------------------------------------------------ helpers

func hold_body() -> void:
	if "visual_only" in actor: actor.visual_only = true
	if actor is CharacterBody3D: actor.velocity = Vector3.ZERO
	_stop_steer()

func _stop_steer() -> void:
	if is_instance_valid(actor) and "steer" in actor: actor.steer = Vector2.ZERO

func write(at: Vector3) -> void:
	actor.global_position = at
	last_written = at

## The walker faces yaw_now exactly (its visual faces -Z, so the visual yaw is yaw + PI).
func face() -> void:
	actor.facing = IxMath.dir_of(yaw_now)
	if "face_override" in actor: actor.face_override = wrapf(yaw_now + PI, -PI, PI)

func refresh_socket() -> void:
	if entry.is_empty() or not is_instance_valid(entry.get("carrier")): return
	var point := IxSources.point_now(entry)
	socket.origin = point

## The carrier's pitch and roll against its resting orientation (a rocking chair's rock).
func carrier_tilt() -> Basis:
	if entry.is_empty() or not is_instance_valid(entry.get("carrier")) or not is_instance_valid(target): return Basis.IDENTITY
	var carrier: Node3D = entry.carrier
	var object := target.global_basis.orthonormalized()
	var rel_now := object.inverse() * carrier.global_basis.orthonormalized()
	var rel := object * (rel_now * carrier_rest.inverse()) * object.inverse()
	# Keep only the tilt (no yaw): the up vector's turn.
	var up := rel * Vector3.UP
	if up.distance_to(Vector3.UP) < 0.001: return Basis.IDENTITY
	var axis := Vector3.UP.cross(up)
	if axis.length() < 1e-5: return Basis.IDENTITY
	return Basis(axis.normalized(), Vector3.UP.angle_to(up))

## The walker's seat_contact (or hips, lying) where the skeleton is now.
func measured_contact() -> Vector3:
	if not "hand_skeleton" in actor or not is_instance_valid(actor.hand_skeleton): return actor.global_position
	var skel: Skeleton3D = actor.hand_skeleton
	if kind == "lie":
		var hip := IxRig.bone(skel, "Hips")
		return skel.global_transform * skel.get_bone_global_pose(hip).origin if hip >= 0 else actor.global_position
	return IxRig.socket_global(skel, "seat_contact", actor.visual).origin

func ensure_pose() -> void:
	if not "hand_skeleton" in actor or not is_instance_valid(actor.hand_skeleton): return
	if is_instance_valid(pose) and pose.get_parent() == actor.hand_skeleton: return
	# First use, or a new look rebuilt the character while seated: the new skeleton sits too.
	var weight: float = pose.weight if is_instance_valid(pose) else 0.0
	var params: Array = [pose.thigh, pose.calf, pose.spine, pose.arm, pose.forearm, pose.tilt, pose.foot_follow] if is_instance_valid(pose) else []
	pose = IxPose.attach(actor)
	if not is_instance_valid(pose): return
	pose.driven = true
	pose.weight = weight
	if not params.is_empty():
		pose.thigh = params[0]; pose.calf = params[1]; pose.spine = params[2]; pose.arm = params[3]
		pose.forearm = params[4]; pose.tilt = params[5]; pose.foot_follow = params[6]
		pose.mode = kind
	m = IxRig.measure(actor.hand_skeleton, actor.visual)

## A feet point is free: the injected check (rooms), else a capsule test in the walker's world on
## buildings, props and furniture, with ground under it.
func spot_free(point: Vector3) -> bool:
	if free_check.is_valid(): return bool(free_check.call(point))
	if not is_instance_valid(actor) or not actor.is_inside_tree(): return true
	var space := actor.get_world_3d().direct_space_state
	var capsule := CapsuleShape3D.new()
	# The walker's own body size: a spot it is handed back on must not overlap anything.
	capsule.radius = 0.33
	capsule.height = 1.5
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = capsule
	query.transform = Transform3D(Basis.IDENTITY, point + Vector3(0, 0.05 + 0.75, 0))
	query.collision_mask = 2 | 8 | 16
	query.exclude = [actor.get_rid()] if actor is CollisionObject3D else []
	if not space.intersect_shape(query, 1).is_empty(): return false
	var ray := PhysicsRayQueryParameters3D.create(point + Vector3(0, 0.6, 0), point + Vector3(0, -0.8, 0), 1 | 2)
	return not space.intersect_ray(ray).is_empty()

## The first free spot from `point` outward (up to 0.5 m), or `point` when none is.
func clear_spot(point: Vector3, outward: Vector3) -> Vector3:
	if spot_free(point) or outward.length() < 0.001: return point
	var dir := outward.normalized()
	for i in range(1, 11):
		var p := point + dir * (0.05 * i)
		if spot_free(p): return p
	return point

func _exit_tree() -> void:
	if not claim_key.is_empty() and claims.get(claim_key, -1) == (actor.get_instance_id() if is_instance_valid(actor) else -2): claims.erase(claim_key)
	if is_instance_valid(actor) and "ix" in actor and actor.ix == self:
		if busy() and "visual_only" in actor: actor.visual_only = was_visual_only
		if "face_override" in actor: actor.face_override = NAN
		if "steer" in actor: actor.steer = Vector2.ZERO
		actor.ix = null
