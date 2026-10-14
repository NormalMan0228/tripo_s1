extends SceneTree
## Other players' walk under a jittery feed (remote_motion.gd). A walker follows a 20 s route (walk,
## stop, run, a right-angle turn, a ramp, a zigzag, a door that moves it 12 m, a circle) and posts its
## spot on a schedule; another client polls and draws it each frame (60 fps), the 0.11.4 way (chase
## the newest spot) and with RemoteMotion. Two feeds, five seeds each:
## - harsh: both poll every 0.25 s ± 0.15 s, 5-6% latency spikes (bunched replies), 3% dropped
##   replies and a 1.2 s outage mid-run;
## - steady: a kept-alive connection, 0.25 s ± 0.02 s, rare spikes, the same outage.
## The spots carry the sender's clock (this game) or only the server's (seen: older games).
## Pure logic: no server, no window. Prints METRIC/SUMMARY lines and REMOTE_MOTION_CHECK_COMPLETE.
const RemoteMotion = preload("res://scripts/remote_motion.gd")
const DT := 1.0/60.0
const TICK := 1.0/120.0
const LENGTH := 20.0
const TELEPORT_AT := 15.0
## The sender's clock and the server's clock are far from the observer's.
const SENDER_EPOCH := 1234.5
const SERVER_EPOCH := 1.76e9
var failed := false
var rng := RandomNumberGenerator.new()
var src_t: Array[float] = []
var src_p: Array[Vector3] = []
var src_v: Array[Vector3] = []
var src_yaw: Array[float] = []
## The feed's irregularity: poll jitter (s), spike chance, drop chance.
var jitter := 0.15
var spikes := 0.06
var drops := 0.03

func _initialize() -> void:
	call_deferred("run")

func expect(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ")+label)
	if not value: failed = true

## Where the walker wants to go at time t: direction (x, z), speed, height.
func plan(t: float) -> Array:
	if t < 1.0: return [Vector2.ZERO, 0.0, 0.0]
	if t < 5.0:
		var a := (t-1.0)*0.6
		return [Vector2(cos(a), sin(a)), 2.8, 0.0]
	if t < 6.5: return [Vector2.ZERO, 0.0, 0.0]
	if t < 8.0: return [Vector2(1, 0), 4.5, 0.0]
	if t < 10.0: return [Vector2(0, 1), 4.5, 0.0]
	if t < 11.0: return [Vector2(-1, 0), 2.8, 0.6*(t-10.0)]
	if t < 12.5:
		var side := 1.0 if int((t-11.0)/0.5)%2 == 0 else -1.0
		return [Vector2(-1, side).normalized(), 2.8, 0.6]
	if t < 13.5: return [Vector2.ZERO, 0.0, 0.6]
	if t < LENGTH*0.75: return [Vector2(0, -1), 2.8, 0.3]
	var c := (t-TELEPORT_AT)*0.8
	return [Vector2(cos(c), sin(c)), 2.8, 0.3]

## The sender's walk, integrated like player.gd (acceleration, turn shedding, eased heading).
func simulate() -> void:
	var p := Vector3.ZERO
	var v := Vector2.ZERO
	var yaw := 0.0
	var t := 0.0
	var jumped := false
	while t <= LENGTH+1.0:
		var want: Array = plan(t)
		var wanted: Vector2 = want[0]*want[1]
		if wanted.length() > 0.1 and v.length() > 0.5 and wanted.normalized().dot(v.normalized()) < 0.2: v *= 0.82
		v = v.move_toward(wanted, (14.0 if wanted.length() > v.length() else 18.0)*TICK)
		p += Vector3(v.x, 0, v.y)*TICK
		p.y = want[2]
		if not jumped and t >= TELEPORT_AT:
			jumped = true
			p += Vector3(12, 0, 0)
		if v.length() > 0.1: yaw = lerp_angle(yaw, atan2(-v.x, -v.y), 1.0-exp(-14.0*TICK))
		src_t.append(t); src_p.append(p); src_v.append(Vector3(v.x, 0, v.y)); src_yaw.append(yaw)
		t += TICK

func source_index(t: float) -> int:
	return clampi(int(t/TICK), 0, src_t.size()-1)

## The feed: the replies the observer receives, [arrival, record], under jitter, spikes and drops.
func feed() -> Array:
	var posts := []   # [server arrival, record]
	var s := 0.1
	while s < LENGTH:
		var i := source_index(s)
		var up := rng.randf_range(0.015, 0.05)+(rng.randf_range(0.1, 0.3) if rng.randf() < spikes*0.8 else 0.0)
		var record := {"x":src_p[i].x, "y":src_p[i].y, "z":src_p[i].z, "yaw":src_yaw[i], "vx":src_v[i].x, "vz":src_v[i].z, "t":SENDER_EPOCH+s}
		posts.append([s+up, record])
		s = maxf(s+0.25+rng.randf_range(-jitter, jitter), s+up+0.03)
	for k in posts.size(): posts[k][1]["seen"] = SERVER_EPOCH+posts[k][0]
	var replies := []
	var o := 0.05
	while o < LENGTH:
		var at_server := o+rng.randf_range(0.015, 0.05)
		var latest = null
		for post in posts:
			if post[0] <= at_server: latest = post[1]
		var down := rng.randf_range(0.015, 0.06)+(rng.randf_range(0.2, 0.45) if rng.randf() < spikes else 0.0)
		var dropped := rng.randf() < drops or (o > 9.0 and o < 10.2)
		var done := at_server+down
		if latest != null and not dropped: replies.append([done, latest])
		# The next poll: on schedule, but never before this one ended (a lost one times out).
		o = maxf(o+0.25+rng.randf_range(-jitter, jitter), (o+0.6) if dropped else done)
	return replies

func measure(label: String, drawn: Array, moving: Array) -> Dictionary:
	var max_step := 0.0
	var stalls := 0
	var steady := 0
	var change := 0.0
	var speeds := []
	var errors := []
	var lag := 0.0
	var lagged := 0
	var flips := 0
	for f in range(1, drawn.size()):
		var tau := f*DT
		if tau < 1.5 or (tau > TELEPORT_AT-0.6 and tau < TELEPORT_AT+1.2): continue
		var step: float = drawn[f].distance_to(drawn[f-1])
		max_step = maxf(max_step, step)
		var speed: float = Vector2(drawn[f].x-drawn[f-1].x, drawn[f].z-drawn[f-1].z).length()/DT
		if moving[f] != moving[f-1]: flips += 1
		# Steady stretches of the route (constant pace for over a second before the frame).
		var steady_speed := 0.0
		# Drawn 0.3-0.7 s late, these frames show the sender's steady stretches (the outage, 9.0-10.2 s,
		# stalls by nature: it is left out here and counted in max_step).
		for span in [[2.6, 5.0, 2.8], [7.6, 8.3, 4.5], [16.5, 19.8, 2.8]]:
			if tau >= span[0] and tau < span[1]: steady_speed = span[2]
		if steady_speed > 0.0:
			steady += 1
			speeds.append(speed/steady_speed)
			var before: float = Vector2(drawn[f-1].x-drawn[f-2].x, drawn[f-1].z-drawn[f-2].z).length()/DT
			change += absf(speed-before)
			if speed < steady_speed*0.4: stalls += 1
		# Distance from the route the sender walked over the last 1.5 s, and how far behind.
		var best := INF
		var best_t := tau
		for i in range(source_index(tau-1.5), source_index(tau)+1, 2):
			var d: float = drawn[f].distance_to(src_p[i])
			if d < best:
				best = d
				best_t = src_t[i]
		errors.append(best)
		if steady_speed > 0.0:
			lag += tau-best_t
			lagged += 1
	var mean := 0.0
	for v in speeds: mean += v
	mean /= maxf(speeds.size(), 1)
	var variance := 0.0
	for v in speeds: variance += (v-mean)*(v-mean)
	var cv := sqrt(variance/maxf(speeds.size(), 1))/maxf(mean, 0.001)
	errors.sort()
	var mean_error := 0.0
	for e in errors: mean_error += e
	mean_error /= maxf(errors.size(), 1)
	var result := {"max_step":max_step, "stall_pct":100.0*stalls/maxf(steady, 1), "speed_cv":cv, "speed_change":change/maxf(steady, 1),
		"path_mean":mean_error, "path_p95":errors[int(errors.size()*0.95)], "lag":lag/maxf(lagged, 1), "anim_flips":flips}
	if OS.get_cmdline_user_args().has("--verbose"): print("METRIC %-22s max_step %.3f m  stalls %5.1f%%  speed_cv %.3f  |dv|/frame %.3f m/s  path mean %.3f p95 %.3f m  lag %.2f s  walk/idle flips %d" % [label, result.max_step, result.stall_pct, result.speed_cv, result.speed_change, result.path_mean, result.path_p95, result.lag, result.anim_flips])
	return result

func play(replies: Array, use_clock: bool) -> Dictionary:
	var old_drawn := []
	var new_drawn := []
	var old_moving := []
	var new_moving := []
	var old_pos := Vector3.ZERO
	var old_target := Vector3.ZERO
	var old_started := false
	var motion = RemoteMotion.new()
	var next := 0
	var teleports := 0
	var delays := []
	var frames := int(LENGTH/DT)
	for f in frames:
		var tau := f*DT
		while next < replies.size() and replies[next][0] <= tau:
			var record: Dictionary = replies[next][1].duplicate()
			if not use_clock: record.erase("t")
			var point := Vector3(record.x, record.y, record.z)
			old_target = point
			if not old_started:
				old_pos = point
				old_started = true
			motion.push_record(record, point, replies[next][0])
			next += 1
		# 0.11.4: chase the newest spot (social.gd _process).
		var before := old_pos
		old_pos = old_pos.lerp(old_target, 1.0-exp(-12.0*DT))
		old_drawn.append(old_pos)
		old_moving.append(Vector2(old_pos.x-before.x, old_pos.z-before.z).length()/DT > 0.28)
		motion.update(DT, tau)
		if motion.teleported:
			teleports += 1
			motion.teleported = false
		new_drawn.append(motion.position)
		new_moving.append(Vector2(motion.velocity.x, motion.velocity.z).length() > 0.28)
		delays.append(motion.delay)
	var source_moving := []
	for f in frames: source_moving.append(src_v[source_index(f*DT)].length() > 0.28)
	var source_flips := 0
	for f in range(1, frames):
		var tau := f*DT
		if tau >= 1.5 and not (tau > TELEPORT_AT-0.6 and tau < TELEPORT_AT+1.2) and source_moving[f] != source_moving[f-1]: source_flips += 1
	delays.sort()
	return {"old":measure("0.11.4 chase", old_drawn, old_moving), "new":measure("smooth "+("sender clock" if use_clock else "server clock"), new_drawn, new_moving),
		"teleports":teleports, "source_flips":source_flips, "delay":delays[delays.size()/2], "drawn":new_drawn}

func run() -> void:
	simulate()
	for scenario in [["harsh", 0.15, 0.06, 0.03], ["steady", 0.02, 0.01, 0.0]]:
		jitter = scenario[1]
		spikes = scenario[2]
		drops = scenario[3]
		print("FEED ", scenario[0])
		var worst := {}
		var sums := {}
		var delays := []
		for seed in [11, 23, 37, 41, 59]:
			rng.seed = seed
			var replies := feed()
			for use_clock in [true, false]:
				var result: Dictionary = play(replies, use_clock)
				var key := "clock" if use_clock else "seen"
				if use_clock: delays.append(result.delay)
				expect(result.teleports == 1, "%s seed %d: the door jump snaps once (%s)" % [scenario[0], seed, key])
				for name in ["old", "new"]:
					for metric in result[name]:
						var id: String = name+"_"+key+"_"+metric
						worst[id] = maxf(worst.get(id, -INF), float(result[name][metric]))
						sums[id] = sums.get(id, 0.0)+float(result[name][metric])/5.0
				worst["flips_"+key] = maxf(worst.get("flips_"+key, -INF), result["new"].anim_flips-result.source_flips)
		delays.sort()
		print("SUMMARY %s feed, mean of 5 seeds (median drawing delay %.2f s)" % [scenario[0], delays[2]])
		for name in ["old_clock", "new_clock", "new_seen"]:
			print("  %-10s max_step %.3f m  stalls %.1f%%  speed_cv %.3f  |dv| %.3f m/s  path mean %.3f p95 %.3f m  lag %.2f s  walk/idle flips %.1f" % [{"old_clock":"0.11.4", "new_clock":"new", "new_seen":"new (seen)"}[name], sums[name+"_max_step"], sums[name+"_stall_pct"], sums[name+"_speed_cv"], sums[name+"_speed_change"], sums[name+"_path_mean"], sums[name+"_path_p95"], sums[name+"_lag"], sums[name+"_anim_flips"]])
		# Continuous: no frame moves further than the 4.5 m/s run at 1.6 times (catching up after a
		# wait plays at 1.1 times, and a correction blends in at up to 1 m/s).
		expect(worst.new_clock_max_step <= 4.5*1.6*DT, "%s: no jumps between frames, worst %.3f m (0.11.4 %.3f)" % [scenario[0], worst.new_clock_max_step, worst.old_clock_max_step])
		expect(worst.new_clock_stall_pct <= 1.0, "%s: no halts mid-walk, worst %.1f%% of frames (0.11.4 %.1f%%)" % [scenario[0], worst.new_clock_stall_pct, worst.old_clock_stall_pct])
		expect(worst.new_clock_speed_cv <= (0.35 if scenario[0] == "harsh" else 0.1), "%s: even pace on steady stretches, worst cv %.3f (0.11.4 %.3f)" % [scenario[0], worst.new_clock_speed_cv, worst.old_clock_speed_cv])
		expect(worst.new_clock_path_p95 <= 0.25, "%s: stays on the walked route, worst p95 %.3f m" % [scenario[0], worst.new_clock_path_p95])
		expect(worst.flips_clock <= 5, "%s: walk/idle changes only when the sender's do, worst +%d" % [scenario[0], int(worst.flips_clock)])
		expect(worst.new_seen_max_step <= 0.25 and worst.new_seen_stall_pct <= 5.0, "%s: older senders (server clock) stay continuous, worst %.3f m, %.1f%% halts" % [scenario[0], worst.new_seen_max_step, worst.new_seen_stall_pct])
	print("REMOTE_MOTION_CHECK_COMPLETE")
	quit(1 if failed else 0)
