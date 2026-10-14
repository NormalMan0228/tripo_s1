extends RefCounted
## Another player's walk, drawn smoothly from presence replies that come irregularly (social.gd:
## the village, visits and the co-op expedition; studio.gd: the home).
##
## Each spot carries the moment it was taken on the sender's own clock (presence `t`; `seen`, the
## server's clock, from older games; the server's clock in co-op), so a reply that arrives late, or
## two that arrive together, still sit at their true moments. The walker is drawn a short delay in
## the past, between two spots: a cubic curve through the sent velocities (estimated when none
## come), so turns are round and stops are clean. The delay adapts to how irregularly the spots
## arrive (most arrive in time; a late one is bridged). When the next spot is late the walker carries
## on briefly and eases to a stop; when it comes, the difference blends out over a few frames
## instead of jumping. A jump of several metres (a door, a respawn) snaps (teleported, for a small
## effect). The drawn velocity drives the walk/run cycle (player.gd), so the feet match the ground.

const DELAY_MIN := 0.12
const DELAY_MAX := 0.5
## The share of arrivals the delay waits for (plus a small margin); the rest are bridged.
const DELAY_QUANTILE := 0.8
const DELAY_MARGIN := 0.05
## Past the newest spot the walker carries on at its pace for CARRY seconds, then slows to a stop
## over EASE seconds (a spot that is only late is bridged; a lost connection ends in a stand).
const CARRY := 0.2
const EASE := 0.3
const EXTRAPOLATE := CARRY+EASE
const TELEPORT_DISTANCE := 4.0
const TELEPORT_SPEED := 12.0
## No walker is faster (co-op sprint 6.75 m/s): two spots closer in time than that allows were
## stamped on arrival (the server's clock) and are spread out to a believable pace.
const SPEED_CAP := 9.0
## Corrections (a late spot, a changed estimate) fade at this rate per second, never faster than
## CORRECT_SPEED m/s on top of the walk.
const BLEND_RATE := 7.0
const CORRECT_SPEED := 1.0
const ARRIVALS := 24
## The fastest the playhead runs to win back the delay after a wait.
const CATCH_UP := 1.1
const DELAY_RELEASE := 0.1
## With less than this much path left ahead of the playhead, playback slows (down to 60%) while
## the next spot is on its way.
const HEADROOM := 0.04
const LAGS := 40

var times: Array[float] = []
var points: Array[Vector3] = []
var sent: Array = []
var yaws: Array[float] = []
var has_yaw := false
var lags: Array[float] = []
var needs: Array[float] = []
## The fastest observed (local arrival - sample time): the two clocks' offset plus the quickest trip.
var base := 0.0
## How far in the past the walker is drawn: rises at once when a spot needed more, eases back
## down (DELAY_RELEASE per second) when the feed calms.
var delay := 0.3
var wanted_delay := 0.3
## The sender's moment being drawn.
var playhead := 0.0
var started := false
var last_arrival := 0.0
var last_extra := 0.0
var correction := Vector3.ZERO
## Drawn this frame: position, velocity (m/s, for the walk cycle) and heading.
var position := Vector3.ZERO
var velocity := Vector3.ZERO
var yaw := 0.0
## Set when the walker snapped to a far spot; the caller plays an effect and clears it.
var teleported := false

static func now() -> float:
	return Time.get_ticks_usec()*0.000001

## Forgets the path (a floor change, a long absence): the next spot is drawn where it is.
func reset() -> void:
	times.clear()
	points.clear()
	sent.clear()
	yaws.clear()
	started = false
	correction = Vector3.ZERO

## A presence record: x/z (and y), yaw, vx/vz and the moment t (or seen); point is where it stands
## in the caller's space.
func push_record(record: Dictionary, point: Vector3, at := -1.0) -> void:
	var stamp = record.get("t")
	if stamp == null: stamp = record.get("seen")
	var arrival := now() if at < 0.0 else at
	var moment := float(stamp) if stamp != null else arrival
	var heading = record.get("yaw")
	var speed = null
	if record.get("vx") != null and record.get("vz") != null:
		speed = Vector3(float(record.vx), 0.0, float(record.vz))
	push(moment, point, arrival, heading, speed)

## One spot taken at `moment` (sender's clock), arriving now (`arrival`, local clock).
func push(moment: float, point: Vector3, arrival: float, heading = null, speed = null) -> void:
	if started:
		var newest: float = times[-1]
		if moment <= newest:
			# An answer that was overtaken, or the same spot again; a clock that went far back
			# means the sender started again.
			if moment > newest-5.0: return
			reset()
		elif moment > newest+30.0:
			reset()
		else:
			var walked := _flat(point-points[-1])
			if walked < TELEPORT_DISTANCE: moment = maxf(moment, newest+walked/SPEED_CAP)
	var lag := arrival-moment
	lags.append(lag)
	if lags.size() > LAGS: lags.pop_front()
	base = lags.min()
	if not started:
		times.append(moment); points.append(point); sent.append(speed); yaws.append(float(heading) if heading != null else 0.0)
		has_yaw = heading != null
		started = true
		playhead = moment
		position = point
		velocity = Vector3.ZERO
		yaw = yaws[0]
		last_arrival = arrival
		last_extra = lag-base
		return
	# How long the drawing must lag to have had this spot in time: the wait since the previous one
	# arrived plus how late that one was.
	needs.append(arrival-last_arrival+last_extra)
	if needs.size() > ARRIVALS: needs.pop_front()
	var sorted := needs.duplicate()
	sorted.sort()
	wanted_delay = clampf(sorted[mini(sorted.size()-1, int(sorted.size()*DELAY_QUANTILE))]+DELAY_MARGIN, DELAY_MIN, DELAY_MAX)
	delay = maxf(delay, wanted_delay)
	last_arrival = arrival
	last_extra = lag-base
	var jump := point-points[-1]
	if jump.length() > TELEPORT_DISTANCE and jump.length()/maxf(moment-times[-1], 0.05) > TELEPORT_SPEED:
		reset()
		times.append(moment); points.append(point); sent.append(speed); yaws.append(float(heading) if heading != null else yaw)
		started = true
		playhead = maxf(playhead, moment-delay)
		position = point
		velocity = Vector3.ZERO
		teleported = true
		return
	# The drawn path stays continuous: whatever the new spot changes at the playhead blends out.
	var before := evaluate(playhead)
	times.append(moment); points.append(point); sent.append(speed); yaws.append(float(heading) if heading != null else yaws[-1])
	has_yaw = has_yaw or heading != null
	correction += before-evaluate(playhead)

## Advances the drawing by one frame.
func update(delta: float, at := -1.0) -> void:
	if not started or delta <= 0.0: return
	var clock := now() if at < 0.0 else at
	delay = move_toward(delay, wanted_delay, DELAY_RELEASE*delta)
	var target := clock-base-delay
	var gap := target-playhead
	# The playhead runs a little fast or slow to follow the target delay, so it never jumps; with no
	# newer spot it waits at the end of the carry-on (a lost connection) and catches up afterwards.
	if absf(gap) > 2.0: playhead = target
	else:
		var rate := clampf(1.0+gap*2.0, 0.8, CATCH_UP)
		# The next spot is late: play slower rather than run ahead of the data.
		var headroom := times[-1]-playhead
		if headroom < HEADROOM: rate = minf(rate, 0.6+0.4*clampf(headroom/HEADROOM, 0.0, 1.0))
		playhead += delta*rate
	playhead = minf(playhead, times[-1]+EXTRAPOLATE)
	var drawn := evaluate(playhead)
	var fade := minf(correction.length()*(1.0-exp(-BLEND_RATE*delta)), CORRECT_SPEED*delta)
	correction = correction.move_toward(Vector3.ZERO, fade)
	drawn += correction
	var moved := (drawn-position)/delta
	velocity = velocity.lerp(moved, 1.0-exp(-delta/0.06))
	position = drawn
	# Spots the playhead has passed are no longer needed (one stays behind it).
	while times.size() > 2 and times[1] < playhead-0.05:
		times.pop_front(); points.pop_front(); sent.pop_front(); yaws.pop_front()

## The spot at the sender's moment t (also sets yaw).
func evaluate(t: float) -> Vector3:
	var count := times.size()
	if t <= times[0] or count == 1:
		var only := points[0]
		if count == 1 and t > times[0]: only = carry(0, t)
		yaw = yaws[0]
		return only
	if t >= times[count-1]:
		yaw = yaws[count-1]
		return carry(count-1, t)
	var i := 0
	while times[i+1] < t: i += 1
	var span := times[i+1]-times[i]
	var s := (t-times[i])/span
	var a := points[i]
	var b := points[i+1]
	var flat := Vector3(b.x-a.x, 0.0, b.z-a.z)
	var limit := flat.length()*1.5+0.05
	var m0 := (tangent(i)*span).limit_length(limit)
	var m1 := (tangent(i+1)*span).limit_length(limit)
	var s2 := s*s
	var s3 := s2*s
	var at := a*(2*s3-3*s2+1)+m0*(s3-2*s2+s)+b*(-2*s3+3*s2)+m1*(s3-s2)
	# Height (steps, bridges) follows straight between spots.
	at.y = lerpf(a.y, b.y, s)
	yaw = lerp_angle(yaws[i], yaws[i+1], s)
	return at

## Past the newest spot: on at its velocity for CARRY seconds, then slowing evenly to a stop.
func carry(index: int, t: float) -> Vector3:
	var over := minf(t-times[index], EXTRAPOLATE)
	var v := tangent(index)
	if over <= CARRY: return points[index]+v*over
	var easing := over-CARRY
	return points[index]+v*(CARRY+easing-easing*easing/(2.0*EASE))

## The horizontal velocity at a spot: the one sent, or from the neighbouring spots (none beside a stop).
func tangent(i: int) -> Vector3:
	if sent[i] != null: return sent[i]
	var count := times.size()
	var v := Vector3.ZERO
	if i > 0 and i < count-1: v = (points[i+1]-points[i-1])/maxf(times[i+1]-times[i-1], 0.001)
	elif i > 0: v = (points[i]-points[i-1])/maxf(times[i]-times[i-1], 0.001)
	elif count > 1: v = (points[1]-points[0])/maxf(times[1]-times[0], 0.001)
	if i > 0 and _flat(points[i]-points[i-1]) < 0.02: return Vector3.ZERO
	if i < count-1 and _flat(points[i+1]-points[i]) < 0.02: return Vector3.ZERO
	return Vector3(v.x, 0.0, v.z)

static func _flat(v: Vector3) -> float:
	return Vector2(v.x, v.z).length()

## Puts the drawing on a walker (player.gd, visual_only): its place, the velocity its walk/run
## cycle follows, and its heading (the sender's own; from the motion when none is sent).
func apply_to(actor) -> void:
	if not is_instance_valid(actor) or not started: return
	actor.position = position
	var flat := Vector2(velocity.x, velocity.z)
	actor.external_velocity = flat if flat.length() > 0.15 else Vector2.ZERO
	if has_yaw: actor.external_motion = Vector2(-sin(yaw), -cos(yaw))
	elif flat.length() > 0.15: actor.external_motion = flat.normalized()
	else: actor.external_motion = Vector2.ZERO
	if teleported:
		teleported = false
		var fx = load("res://scripts/fx.gd")
		if actor.get("visual") is Node3D: fx.squash(actor.visual, 0.2, 0.3)
		if actor.is_inside_tree() and actor.get_parent() is Node3D:
			fx.burst(actor.get_parent(), actor.position+Vector3(0, 1.0, 0), "sparkle", 8, Color(0, 0, 0, 0), 0.3)
