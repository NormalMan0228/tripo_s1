extends RefCounted
## Frame-by-frame continuity watch for anything that walks (the player, residents, other players,
## monsters). A test registers the bodies it shows, then calls frame(dt) after every drawn frame and
## tick() after every physics tick. It fails a body that, while on screen and shown:
##  - jumps: moves farther in one drawn frame than twice its top speed allows (a teleport, a snap);
##  - pops up or down: changes height faster than VERTICAL_SPEED (a step lifted in one tick);
##  - spins: turns more than TURN_LIMIT in one drawn frame;
##  - judders: stands still for a drawn frame while it is walking (a body moved only on physics
##    ticks, drawn at a faster screen rate, or one skipped tick);
##  - pops its pose: a bone moves more than POSE_POP in one physics tick (a clip switched with no
##    blend, a T-pose frame);
##  - holds a stale pose: on screen and walking, the skeleton did not move for STALE_TICKS ticks in
##    a row (animation level of detail too coarse near the camera).
## Bodies off screen or hidden (fade, doors, scene changes) are not judged, and a jump into or out of
## hiding is allowed. Pure measurement: no rendering needed; works headless with Engine.max_fps.
## Usage:
##   var watch = MotionWatch.new(camera)
##   watch.add("player", player, {"speed": 4.5, "draw": player.visual, "skeleton": player.hand_skeleton})
##   ...each process frame: watch.frame(delta)   ...each physics frame: watch.tick()
##   watch.report() -> {"pass": bool, "issues": [...], "counts": {...}, "max": {...}}

## Allowed vertical speed of the drawn body (m/s): stairs at a run, never a whole step in one tick.
const VERTICAL_SPEED := 3.2
## Extra slack per frame for a body that eases its speed (m).
const SLACK := 0.05
## A drawn frame may turn the body at most this much (rad) at 60 fps (scaled with the frame time).
const TURN_LIMIT := 0.75
## A bone may move at most this far (m, body space) in one 60 Hz physics tick.
const POSE_POP := 0.24
## Ticks in a row a walking on-screen skeleton may hold the same pose.
const STALE_TICKS := 2
## Fraction of moving frames that may stand still (one in fifty: OS hitches in a test run).
const JUDDER_SHARE := 0.03
## Frames a body must be walking before its stillness counts as judder.
const MOVING_MIN := 0.6

var camera: Camera3D
var tracks: Array = []
var issues: Array = []
var counts := {}
var maxima := {"jump_ratio":0.0, "vertical_speed":0.0, "turn":0.0, "pose_step":0.0, "stale_run":0}
var frames := 0
var ticks := 0
## Issues of one kind and body are kept up to this many (all are counted).
var keep_per_kind := 6

func _init(view: Camera3D = null) -> void:
	camera = view

## Registers a body. options:
##  speed     top ground speed (m/s), required
##  draw      the node actually drawn (default: the body) — its global position is judged
##  skeleton  Skeleton3D for pose checks (optional)
##  shown     Callable -> bool: the body is drawn (default: is_visible_in_tree)
##  walking   Callable -> bool: the body means to walk now (default: drawn speed > MOVING_MIN)
##  yaw_node  node whose global yaw is the facing (default: draw)
##  vertical  allowed vertical speed (m/s, default VERTICAL_SPEED; a carried item swings faster)
func add(label: String, body: Node3D, options: Dictionary) -> void:
	var draw: Node3D = options.get("draw", body)
	tracks.append({"label":label, "body":body, "draw":draw, "speed":float(options.speed),
		"skeleton":options.get("skeleton", null), "shown":options.get("shown", Callable()),
		"walking":options.get("walking", Callable()), "yaw_node":options.get("yaw_node", draw),
		"last":Vector3.INF, "last_yaw":NAN, "was_seen":false, "speed_now":0.0,
		"pose":PackedVector3Array(), "stale":0, "moving_frames":0, "still_frames":0,
		"seen_frames":0, "excused":0, "vertical":float(options.get("vertical", VERTICAL_SPEED))})

## Lets a body jump for the next `frame_count` frames (a door, a respawn, a scene cut the test made).
func excuse(label: String, frame_count := 2) -> void:
	for track in tracks:
		if track.label == label: track.excused = maxi(track.excused, frame_count)

func on_screen(point: Vector3) -> bool:
	if camera == null or not camera.is_inside_tree(): return true
	# Inside the frustum with a small margin, so a body walking off the edge is still judged.
	for plane in camera.get_frustum():
		if plane.distance_to(point) > 0.5: return false
	return true

func shown(track: Dictionary) -> bool:
	if not is_instance_valid(track.body) or not is_instance_valid(track.draw): return false
	var body: Node3D = track.body
	var draw: Node3D = track.draw
	if not is_instance_valid(body) or not is_instance_valid(draw): return false
	if not draw.is_visible_in_tree(): return false
	var check: Callable = track.shown
	if check.is_valid() and not bool(check.call()): return false
	return on_screen(draw.global_position+Vector3(0, 1.0, 0))

func note(track: Dictionary, kind: String, text: String) -> void:
	var key := "%s:%s" % [track.label, kind]
	counts[key] = int(counts.get(key, 0))+1
	counts[kind] = int(counts.get(kind, 0))+1
	if int(counts[key]) <= keep_per_kind:
		issues.append("%s %s frame=%d %s" % [track.label, kind, frames, text])

## After every drawn frame.
func frame(dt: float) -> void:
	frames += 1
	if dt <= 0.0: return
	var scale60 := dt*60.0
	for track in tracks:
		var seen := shown(track)
		if not seen:
			track.was_seen = false
			track.last = Vector3.INF
			track.last_yaw = NAN
			continue
		var draw: Node3D = track.draw
		var p: Vector3 = draw.global_position
		var yaw: float = (track.yaw_node as Node3D).global_rotation.y
		track.seen_frames += 1
		if track.excused > 0:
			track.excused -= 1
		elif track.was_seen and track.last != Vector3.INF:
			var last: Vector3 = track.last
			var step: Vector3 = p-last
			var flat := Vector2(step.x, step.z).length()
			# Twice the top speed: a teleport or a snap, not the uneven share of a tick a frame gets.
			var allowed: float = track.speed*2.0*dt+SLACK
			maxima.jump_ratio = maxf(maxima.jump_ratio, flat/allowed)
			if flat > allowed:
				note(track, "jump", "%.2fm in %.1fms (limit %.2fm) at %s" % [flat, dt*1000.0, allowed, str(p.snapped(Vector3.ONE*0.01))])
			var vspeed := absf(step.y)/dt
			maxima.vertical_speed = maxf(maxima.vertical_speed, vspeed)
			if absf(step.y) > float(track.vertical)*dt+0.02:
				note(track, "vertical_pop", "dy=%.2fm in %.1fms at %s" % [step.y, dt*1000.0, str(p.snapped(Vector3.ONE*0.01))])
			if not is_nan(track.last_yaw):
				var turn := absf(angle_difference(float(track.last_yaw), yaw))
				maxima.turn = maxf(maxima.turn, turn/maxf(scale60, 0.25))
				if turn > TURN_LIMIT*maxf(scale60, 1.0):
					note(track, "spin", "%.2frad in one frame at %s" % [turn, str(p.snapped(Vector3.ONE*0.01))])
			# Judder: a walking body that did not move at all this frame.
			var speed_now: float = flat/dt
			track.speed_now = lerpf(float(track.speed_now), speed_now, 0.3)
			var walking: bool = track.speed_now > MOVING_MIN
			var wants: Callable = track.walking
			if wants.is_valid(): walking = bool(wants.call()) and track.speed_now > MOVING_MIN*0.5
			if walking:
				track.moving_frames += 1
				if flat < 0.0005: track.still_frames += 1
		track.last = p
		track.last_yaw = yaw
		track.was_seen = true

## After every physics tick (steps: ticks since the last call, when a frame ran several).
func tick(steps := 1) -> void:
	ticks += steps
	for track in tracks:
		var skeleton = track.skeleton
		if skeleton is Callable: skeleton = (skeleton as Callable).call()
		if not is_instance_valid(skeleton) or not shown(track):
			track.pose = PackedVector3Array()
			track.stale = 0
			continue
		var draw: Node3D = track.draw
		var into := draw.global_transform.affine_inverse()*(skeleton as Skeleton3D).global_transform
		var pose := PackedVector3Array()
		var count: int = (skeleton as Skeleton3D).get_bone_count()
		pose.resize(count)
		for i in count: pose[i] = into*(skeleton as Skeleton3D).get_bone_global_pose(i).origin
		var previous: PackedVector3Array = track.pose
		if previous.size() == count and track.excused <= 0:
			var biggest := 0.0
			var bone := -1
			for i in count:
				var d := pose[i].distance_to(previous[i])
				if d > biggest:
					biggest = d
					bone = i
			biggest /= maxf(1.0, float(steps))
			maxima.pose_step = maxf(maxima.pose_step, biggest)
			if biggest > POSE_POP:
				note(track, "pose_pop", "bone %s moved %.2fm in one tick" % [(skeleton as Skeleton3D).get_bone_name(bone), biggest])
			var walking: bool = track.speed_now > MOVING_MIN
			var wants: Callable = track.walking
			if wants.is_valid(): walking = bool(wants.call())
			if walking and biggest < 0.0002:
				track.stale += 1
				maxima.stale_run = maxi(maxima.stale_run, track.stale)
				if track.stale == STALE_TICKS+1: note(track, "stale_pose", "same pose for %d ticks while walking on screen" % track.stale)
			else:
				track.stale = 0
		track.pose = pose

func report() -> Dictionary:
	var judder := {}
	var judder_fail := false
	for track in tracks:
		if track.moving_frames < 30: continue
		var share: float = float(track.still_frames)/float(track.moving_frames)
		judder[track.label] = snappedf(share, 0.001)
		if share > JUDDER_SHARE:
			judder_fail = true
			note(track, "judder", "%d of %d walking frames stood still (%.0f%%)" % [track.still_frames, track.moving_frames, share*100.0])
	var hard := 0
	for kind in ["jump", "vertical_pop", "spin", "pose_pop", "stale_pose"]: hard += int(counts.get(kind, 0))
	return {"pass": hard == 0 and not judder_fail, "frames":frames, "ticks":ticks, "issues":issues,
		"counts":counts, "max":maxima, "judder":judder,
		"seen":tracks.map(func(t): return "%s:%d" % [t.label, t.seen_frames])}

## One line per issue plus a summary line, for test logs.
static func print_report(name: String, result: Dictionary) -> void:
	for line in result.issues: print("  MOTION_ISSUE ", name, " ", line)
	print("MOTION_WATCH ", name, " ", "PASS" if result.pass else "FAIL", " frames=", result.frames, " ticks=", result.ticks,
		" counts=", JSON.stringify(result.counts), " max=", JSON.stringify(result.max), " judder=", JSON.stringify(result.judder))
