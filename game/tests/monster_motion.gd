extends SceneTree
## Expedition monsters (the 29 species with their own GLB in assets/monsters/<species>_<map>.glb, stats from
## server/catalog.py ENEMIES) driven through the real shadow_beast.gd / monster.gd by synthetic server
## snapshots (no server), drawn at a faster screen rate than the 60 Hz physics, in real time. Per species:
##  1 locomotion  idle 1 s, walk 2 s at the catalog speed, run 2 s at monster.gd RUN_REF (run clip at 1x),
##                stop, idle, on the solo feed (a snapshot every 0.1 s, main.gd tick_run), judged by
##                tests/motion_watch.gd (jump, vertical pop, spin, judder, stale pose, pose pop with
##                POSE_POP scaled by height/1.7 for monsters taller than 1.7 m);
##  2 foot slide  foot/toe bones' world positions every tick in the steady walk and run (rigs without
##                foot/toe names: their leaf bones that come within 15% of the height of the ground, see
##                contact_bones()): while a bone is within 3 cm of its lowest height it is planted, and its
##                horizontal travel over the ground is summed (cm per step; per foot the best-planted bone,
##                the worse foot counts; flag > 4 cm; named feet that never come within 12 cm x height/1.7
##                of the ground float (a warning), beyond 50 cm x height/1.7 the body flies (not judged);
##  3 attack      a wind-up snapshot as the server sends a melee one (phase windup, windup = catalog, then
##                recover 0.85 s, then chase): the time from the wind-up to the speed peak of the fastest
##                hand/foot/toe/head/jaw/limb bone (body space; after the 0.08 s blend into the clip)
##                against the server wind-up (flag |diff| > 0.1 s);
##  4 hurt        a snapshot with less hp: the additive overlay's flash turns on; a hit branch run by the
##                first snapshot (no hit) fails as spawn_flash;
##  5 death       die() as main.gd calls it: the death clip is judged by a watch until the body starts to
##                sink, the node must free itself within the death clip + 3 s (a body still more than
##                0.25 m high when freed is a warning);
##  6 co-op       a fresh body on a jittered feed (0.1-0.25 s apart, 40-70 ms latency) with a right-angle
##                turn into a run: no jump / judder / pose pop (watch.excuse at spawn).
## Also reported, not judged: the drawn speed's ripple (stdev / mean per frame) in the steady stretches.
## Prints MOTION_WATCH lines (one per phase), one MONSTER_MOTION line per species, then
## MONSTER_MOTION PASS/FAIL {json}; exit code 0/1. Headless, no server, no credits:
##   Godot --headless --path game --script res://tests/monster_motion.gd -- [--species=goblin,troll] [--fps=144] [--hitch=N] [--out=path.json]
## --hitch=N stalls every Nth frame for 70 ms (a loaded PC). Do not pass --fixed-fps.
const MotionWatch = preload("res://tests/motion_watch.gd")
const Beast = preload("res://scripts/shadow_beast.gd")
const Monster = preload("res://scripts/monster.gd")
const IDS := ["goblin", "werewolf", "troll", "cyclops", "treant", "skeleton", "lizardman", "minotaur", "mummy_king",
	"chimera", "ghoul", "ice_shardling", "draugr", "yeti", "wendigo", "frost_hag", "frost_knight", "ice_golem",
	"glacier_giant", "dragon", "harpy", "imp", "gargoyle", "frost_wraith", "lich", "centipede", "mimic", "basilisk", "naga"]
## Solo snapshot cadence (main.gd tick_run: every 0.1 s alone, 0.2 s in a co-op run, plus the reply).
const SOLO_FEED := 0.1
## A foot bone within this of its lowest height is planted (m).
const PLANT := 0.03
## Planted travel per step that fails (cm).
const SLIDE_LIMIT := 4.0
## Lowest foot height above which a walker floats (a warning) and above which it flies (its feet are not
## judged for sliding) (m, at 1.7 m; scaled up with the height: a 5 m body's toe joint sits higher).
const FLOAT_FOOT := 0.12
const FLY_FOOT := 0.5
## Allowed gap between the blow's speed peak and the server wind-up (s).
const ATTACK_LIMIT := 0.1
## Start of the attack peak search after the wind-up: past the 0.08 s blend into the clip (s).
const ATTACK_BLEND := 0.1
## Contact bones count when they come within this of the body's lowest contact bone (m, at 1.7 m).
const CONTACT_BAND := 0.1
## A body whose highest bone is still this far above the ground when it frees itself vanishes in sight
## (a warning, not a failure: die() sinks 0.9 m and shrinks to 0.6 high, then frees) (m).
const DEATH_VISIBLE := 0.25
## server/simulation.py advance_enemy: recover after a melee wind-up (s).
const RECOVER := 0.85
const START := Vector3(-8, 0, -2)
const REMOTE_START := Vector3(-8, 0, -6)

## MotionWatch with its pose-pop limit per body (a 5 m dragon's hand travels 3x a 1.7 m goblin's).
## Same checks as motion_watch.gd tick(); only the POSE_POP constant is this watch's pose_pop.
class MonsterWatch extends "res://tests/motion_watch.gd":
	var pose_pop := 0.24
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
				if biggest > pose_pop:
					note(track, "pose_pop", "bone %s moved %.2fm in one tick (limit %.2f)" % [(skeleton as Skeleton3D).get_bone_name(bone), biggest, pose_pop])
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

## Samples after every other node's _process (lowest priority), as in motion_continuity.gd: the frame's
## physics ticks and its _process moves are both in, and judged with this frame's time.
class Sampler extends Node:
	var test: SceneTree
	func _init() -> void:
		process_priority = 1000000
		process_mode = Node.PROCESS_MODE_ALWAYS
	func _process(delta: float) -> void:
		test.sample(delta)

## The "server": moves the creature and posts its snapshot before any other node's _process (main.gd
## update_run calls update_snapshot from its own _process, before the creature draws).
class Driver extends Node:
	var test: SceneTree
	func _init() -> void:
		process_priority = -1000000
		process_mode = Node.PROCESS_MODE_ALWAYS
	func _process(delta: float) -> void:
		test.drive(delta)

var catalog := {}
var camera: Camera3D
var stage: Node3D
var watches: Array = []
var results := {}
var failed := false
var _last_ticks := 0
var _hitch_count := 0
var hitch_every := 0
var rng := RandomNumberGenerator.new()

# The feed: the body being fed and what the server says about it.
var fed: Node3D
var feed_on := false
var feed_jitter := false
var feed_speed := 0.0
var feed_dir := Vector2(1, 0)
var feed_phase := "chase"
var feed_hp := 45.0
var feed_max_hp := 45.0
var feed_windup := 0.0
var feed_target := Vector3.ZERO
var feed_variant := ""
var server_at := Vector3.ZERO
var history: Array = []
var next_post := 0.0
var posts := 0

# Probes.
var segment := ""                 # "walk" / "run" / "rwalk" / "rrun" while a steady stretch is sampled
var foot_bones: PackedInt32Array
var foot_samples := {}            # segment -> {bone: PackedVector3Array}
var body_low := INF               # lowest bone of the whole body in the steady walk (m, world)
var feet_named := true            # the rig names its feet (foot/toe): its lowest foot height tells flying
var speeds := {}                  # segment -> [drawn ground speed per frame]
var clip_scales := {}             # segment -> [lowest, highest] AnimationPlayer speed_scale seen
var last_drawn := Vector3.INF
var attack_on := false
var attack_t0 := -1.0
var attack_bones: PackedInt32Array
var attack_trace: Array = []      # [time, PackedVector3Array body space]
var flash_on := false
var flash_max := 0.0
var hurt_seen := false
var death_body: Node3D
var death_on := false
var death_top := 0.0
## When the dying body starts to sink (die(): the death clip + 0.25 s): the death watch stops there.
var sink_at := INF
## Frame (of the watch that is judging) at which each phase began, to place MOTION_ISSUE frames.
var marks := {}

func _initialize() -> void:
	call_deferred("run")
	create_timer(2400).timeout.connect(func():
		push_error("monster motion exceeded 40 minutes")
		quit(2))

func arg(name: String, fallback: String) -> String:
	for item in OS.get_cmdline_user_args():
		if item.begins_with("--"+name+"="): return item.trim_prefix("--"+name+"=")
	return fallback

static func clock() -> float:
	return Time.get_ticks_usec()/1000000.0

## server/catalog.py ENEMIES: the numbers this test needs, read from the source (one flat dict per species).
func load_catalog() -> Dictionary:
	var path := ProjectSettings.globalize_path("res://").path_join("../server/catalog.py").simplify_path()
	var text := FileAccess.get_file_as_string(path)
	var out := {}
	if text == "":
		push_error("cannot read "+path)
		return out
	for id in IDS:
		var at := text.find("'%s': {" % id)
		if at < 0: continue
		var block := text.substr(at, text.find("}", at)-at)
		var stats := {}
		for key in ["speed", "windup", "reach", "height", "hp", "impact"]:
			var found := RegEx.create_from_string("'%s':\\s*([0-9.]+)" % key).search(block)
			if found: stats[key] = found.get_string(1).to_float()
		for key in ["map", "tier", "stand_in", "behavior"]:
			var found := RegEx.create_from_string("'%s':\\s*'(\\w+)'" % key).search(block)
			if found: stats[key] = found.get_string(1)
		out[id] = stats
	return out

func run() -> void:
	Engine.max_fps = int(arg("fps", "144"))
	hitch_every = int(arg("hitch", "0"))
	seed(20261016)
	rng.seed = 20261016
	catalog = load_catalog()
	var sampler := Sampler.new()
	sampler.test = self
	root.add_child(sampler)
	var driver := Driver.new()
	driver.test = self
	root.add_child(driver)
	stage = Node3D.new()
	root.add_child(stage)
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 40.0
	camera.far = 400.0
	stage.add_child(camera)
	camera.position = Vector3(0, 25, 35)
	camera.look_at(Vector3.ZERO)
	camera.current = true
	var wanted := arg("species", ",".join(IDS)).split(",")
	var started := clock()
	for id in wanted:
		_last_ticks = Engine.get_physics_frames()
		var result: Dictionary = await run_species(id)
		results[id] = result
		print_line(result)
		if not result.fail.is_empty(): failed = true
	var summary := {}
	for id in results: summary[id] = "PASS" if results[id].fail.is_empty() else "FAIL:"+",".join(PackedStringArray(results[id].fail))
	var out := arg("out", "")
	if out != "":
		var file := FileAccess.open(out, FileAccess.WRITE)
		if file: file.store_string(JSON.stringify(results, "  "))
	print("MONSTER_MOTION_SECONDS ", snappedf(clock()-started, 0.1))
	print("MONSTER_MOTION ", "FAIL" if failed else "PASS", " ", JSON.stringify(summary))
	quit(1 if failed else 0)

## ------------------------------------------------------------------ frames and sampling
func one_frame() -> void:
	_hitch_count += 1
	if hitch_every > 0 and _hitch_count % hitch_every == 0: OS.delay_msec(70)
	await process_frame

func frames(count: int) -> void:
	for i in count: await one_frame()

func seconds(t: float) -> void:
	var end := clock()+t
	while clock() < end: await one_frame()

func sample(delta: float) -> void:
	var now := Engine.get_physics_frames()
	var steps := now-_last_ticks
	_last_ticks = now
	for w in watches:
		if steps > 0: w.tick(steps)
		w.frame(delta)
	if steps > 0: probe_tick()
	probe_frame(delta)

static func skeleton_of(beast: Node3D) -> Skeleton3D:
	if not is_instance_valid(beast) or beast.monster == null or beast.monster.model == null: return null
	var found: Array = beast.monster.model.find_children("*", "Skeleton3D", true, false)
	return found[0] if not found.is_empty() else null

## Foot and toe bones' world positions, every tick of a steady walk or run.
func probe_tick() -> void:
	if segment == "" or not is_instance_valid(fed): return
	var skeleton := skeleton_of(fed)
	if skeleton == null: return
	var per: Dictionary = foot_samples.get(segment, {})
	for bone in foot_bones:
		var p: Vector3 = skeleton.global_transform*skeleton.get_bone_global_pose(bone).origin
		var list: PackedVector3Array = per.get(bone, PackedVector3Array())
		list.append(p)
		per[bone] = list
	foot_samples[segment] = per
	if segment == "walk":
		for bone in skeleton.get_bone_count(): body_low = minf(body_low, (skeleton.global_transform*skeleton.get_bone_global_pose(bone).origin).y)

func probe_frame(delta: float) -> void:
	if is_instance_valid(fed) and fed.monster != null:
		var drawn: Vector3 = fed.monster.global_position
		if segment != "" and last_drawn != Vector3.INF and delta > 0.0:
			var list: Array = speeds.get(segment, [])
			list.append(Vector2(drawn.x-last_drawn.x, drawn.z-last_drawn.z).length()/delta)
			speeds[segment] = list
			var scale: float = fed.monster.player.speed_scale
			var seen: Array = clip_scales.get(segment, [scale, scale])
			clip_scales[segment] = [minf(seen[0], scale), maxf(seen[1], scale)]
		last_drawn = drawn
		if attack_on and attack_t0 >= 0.0:
			if fed.monster.clip == "attack":
				var skeleton := skeleton_of(fed)
				var into := fed.global_transform.affine_inverse()*skeleton.global_transform
				var pose := PackedVector3Array()
				for bone in attack_bones: pose.append(into*skeleton.get_bone_global_pose(bone).origin)
				attack_trace.append([clock(), pose])
			elif clock()-attack_t0 > 0.2: attack_on = false
		if flash_on:
			flash_max = maxf(flash_max, float(fed.monster.overlay.get_shader_parameter("flash")))
			if fed.monster.clip == "hurt": hurt_seen = true
	else: last_drawn = Vector3.INF
	if death_on and is_instance_valid(death_body):
		var skeleton := skeleton_of(death_body)
		if skeleton != null:
			var top := -INF
			for bone in skeleton.get_bone_count(): top = maxf(top, (skeleton.global_transform*skeleton.get_bone_global_pose(bone).origin).y)
			death_top = top

## ------------------------------------------------------------------ the feed
func drive(delta: float) -> void:
	if not feed_on or not is_instance_valid(fed): return
	var now := clock()
	server_at += Vector3(feed_dir.x, 0, feed_dir.y)*feed_speed*delta
	history.append([now, server_at])
	if history.size() > 600: history = history.slice(history.size()-400)
	if now < next_post: return
	var latency := 0.0
	if feed_jitter:
		# A co-op client: replies 0.1-0.25 s apart, each 40-70 ms old.
		next_post = now+rng.randf_range(0.1, 0.25)
		latency = rng.randf_range(0.04, 0.07)
	else: next_post = now+SOLO_FEED
	var at: Vector3 = history[0][1]
	for i in range(history.size()-1, -1, -1):
		if float(history[i][0]) <= now-latency:
			at = history[i][1]
			break
	post(at)

## One snapshot as main.gd hands it to shadow_beast.gd (server/simulation.py enemy fields).
func post(at: Vector3) -> void:
	var state := {"x": at.x, "z": at.z, "phase": feed_phase, "hp": feed_hp, "max_hp": feed_max_hp,
		"windup": feed_windup, "variant": feed_variant}
	if feed_phase == "windup":
		state.target_x = feed_target.x
		state.target_z = feed_target.z
	# The player stands ahead on the path: a standing creature faces where it walks.
	var player_at := at+Vector3(feed_dir.x, 0, feed_dir.y)*3.0
	fed.update_snapshot(state, player_at)
	posts += 1
	if feed_phase == "windup" and attack_on and attack_t0 < 0.0: attack_t0 = clock()

func send_now() -> void:
	next_post = 0.0

func enemy_for(id: String, stats: Dictionary, variant: String, at: Vector3) -> Dictionary:
	var enemy := {"id": 1, "x": at.x, "z": at.z, "kind": stats.get("stand_in", id), "species": id,
		"stand_in": stats.get("stand_in", id), "variant": variant, "behavior": stats.get("behavior", "melee"),
		"hp": stats.get("hp", 45.0), "max_hp": stats.get("hp", 45.0), "windup": stats.get("windup", 1.0),
		"reach": stats.get("reach", 2.0), "impact": stats.get("impact", 1.4), "phase": "chase",
		"boss": stats.get("tier", "") == "boss"}
	if stats.has("height"): enemy.height = stats.height
	return enemy

## main.gd update_run: a new enemy gets a shadow_beast with kind, variant and from_enemy, then its position.
func spawn(id: String, stats: Dictionary, variant: String, at: Vector3) -> Node3D:
	var enemy := enemy_for(id, stats, variant, at)
	var beast = Beast.new()
	beast.kind = str(enemy.kind)
	beast.variant = variant
	beast.from_enemy(enemy)
	stage.add_child(beast)
	beast.position = Vector3(enemy.x, 0, enemy.z)
	return beast

func start_feed(beast: Node3D, stats: Dictionary, variant: String, at: Vector3, jitter: bool) -> void:
	fed = beast
	feed_on = true
	feed_jitter = jitter
	feed_speed = 0.0
	feed_dir = Vector2(1, 0)
	feed_phase = "chase"
	feed_hp = float(stats.get("hp", 45.0))
	feed_max_hp = feed_hp
	feed_windup = float(stats.get("windup", 1.0))
	feed_variant = variant
	server_at = at
	history = [[clock(), at]]
	next_post = 0.0
	last_drawn = Vector3.INF

func new_watch(id: String, beast: Node3D, top: float, pop: float, also_shown: Callable, excuse := 3) -> MonsterWatch:
	var w := MonsterWatch.new(camera)
	w.pose_pop = pop
	w.keep_per_kind = 40
	var skeleton := skeleton_of(beast)
	w.add("mon_"+id, beast, {"speed": top*1.2, "draw": beast.monster,
		"skeleton": func(): return skeleton if is_instance_valid(skeleton) else null,
		"shown": func(): return is_instance_valid(beast) and beast.is_visible_in_tree() and bool(also_shown.call())})
	if excuse > 0: w.excuse("mon_"+id, excuse)
	watches.append(w)
	return w

func mark(phase: String) -> void:
	marks[phase] = watches[-1].frames if not watches.is_empty() else 0

func close_watch(w: MonsterWatch, name: String) -> Dictionary:
	watches.erase(w)
	var result := w.report()
	MotionWatch.print_report(name, result)
	var kinds := PackedStringArray()
	for key in result.counts:
		if not ":" in str(key): kinds.append("%s=%d" % [key, result.counts[key]])
	# Each kept issue placed in the phase it happened in ("pose_pop@attack": 5).
	var where := {}
	var frame_of := RegEx.create_from_string("^[^ ]+ ([a-z_]+) frame=([0-9]+)")
	for line in result.issues:
		var found := frame_of.search(str(line))
		if found == null: continue
		var at := int(found.get_string(2))
		var phase := "start"
		var best := -1
		for key in marks:
			if int(marks[key]) <= at and int(marks[key]) > best:
				best = int(marks[key])
				phase = key
		var key := "%s@%s" % [found.get_string(1), phase]
		where[key] = int(where.get(key, 0))+1
	marks = {}
	return {"where": where, "pass": result.pass, "kinds": kinds, "jumps": int(result.counts.get("jump", 0)),
		"pose_pops": int(result.counts.get("pose_pop", 0)), "pose_step": snappedf(result.max.pose_step, 0.001),
		"jump_ratio": snappedf(result.max.jump_ratio, 0.01), "judder": result.judder.values()[0] if not result.judder.is_empty() else 0.0}

## ------------------------------------------------------------------ analysis
## Planted travel per step of one bone's samples (world): planted = within PLANT of its lowest height.
static func slide_of(samples: PackedVector3Array) -> Dictionary:
	var low := INF
	for p in samples: low = minf(low, p.y)
	var high := -INF
	for p in samples: high = maxf(high, p.y)
	var travel := 0.0
	var steps := 0
	var run := 0
	var run_travel := 0.0
	for i in range(1, samples.size()+1):
		var planted := i < samples.size() and samples[i].y <= low+PLANT and samples[i-1].y <= low+PLANT
		if planted:
			run += 1
			run_travel += Vector2(samples[i].x-samples[i-1].x, samples[i].z-samples[i-1].z).length()
		else:
			if run >= 3:
				steps += 1
				travel += run_travel
			run = 0
			run_travel = 0.0
	return {"low": low, "lift": high-low, "steps": steps, "cm": travel/steps*100.0 if steps > 0 else NAN}

## cm per step of the worse foot (each foot: its best-planted contact bone) and the lowest foot height.
## Only bones that come within `band` of the lowest contact bone count (a raised claw is no foot).
func foot_slide(skeleton: Skeleton3D, seg: String, band: float, height: float) -> Dictionary:
	var per: Dictionary = foot_samples.get(seg, {})
	var sides := {}
	var low := INF
	var each := {}
	for bone in per:
		each[bone] = slide_of(per[bone])
		low = minf(low, each[bone].low)
	# A rig without named feet whose leaves stay high (a snake body, a floating torso): no feet to judge.
	if not feet_named and low > height*0.15:
		return {"cm": -1.0, "low": snappedf(low, 0.001), "fly": false, "float": false, "lift": -1.0, "feet": 0, "used": PackedStringArray()}
	var used := PackedStringArray()
	var lifts := {}
	for bone in per:
		var s: Dictionary = each[bone]
		if s.low > low+band: continue
		var side := foot_key(skeleton.get_bone_name(bone))
		used.append(skeleton.get_bone_name(bone))
		if s.steps > 0 and (not sides.has(side) or s.cm < sides[side]):
			sides[side] = s.cm
			lifts[side] = s.lift
	var worst := NAN
	for side in sides: worst = sides[side] if is_nan(worst) else maxf(worst, sides[side])
	# How high the planted bone of the foot that lifts least rises in the stretch (m): a foot that never
	# leaves its 3 cm band stays "planted" for the whole stretch and slides with the body.
	var lift := INF
	for side in lifts: lift = minf(lift, lifts[side])
	var scale := maxf(1.0, height/1.7)
	return {"cm": snappedf(worst, 0.1) if not is_nan(worst) else -1.0, "low": snappedf(low, 0.001),
		"fly": feet_named and low > FLY_FOOT*scale, "float": feet_named and low > FLOAT_FOOT*scale and low <= FLY_FOOT*scale,
		"lift": snappedf(lift, 0.001) if lift != INF else -1.0, "feet": sides.size(), "used": used}

## Which foot a contact bone belongs to: a Tripo limb chain ("tripo__0_Left_Limb_3" -> "tripo__0_Left"),
## a Mixamo / CC side ("mixamorig_LeftToeBase", "L_Foot" -> "L"), else the bone itself.
static func foot_key(bone_name: String) -> String:
	if "_Limb" in bone_name: return bone_name.left(bone_name.find("_Limb"))
	var lower := bone_name.to_lower()
	if "left" in lower or bone_name.begins_with("L_") or bone_name.ends_with("_L") or bone_name.ends_with(".L"): return "L"
	if "right" in lower or bone_name.begins_with("R_") or bone_name.ends_with("_R") or bone_name.ends_with(".R"): return "R"
	return bone_name

## Bones that may touch the ground: named foot/toe bones, else (Tripo "Other" rigs: limbs, legs as bone_N)
## every leaf bone but tails, snake chains and head parts. foot_slide() keeps those that come within
## CONTACT_BAND of the body's lowest one.
func contact_bones(skeleton: Skeleton3D) -> PackedInt32Array:
	var named := PackedInt32Array()
	for bone in skeleton.get_bone_count():
		var lower := skeleton.get_bone_name(bone).to_lower()
		if "foot" in lower or "toe" in lower: named.append(bone)
	feet_named = not named.is_empty()
	if feet_named: return named
	var leaves := PackedInt32Array()
	for bone in skeleton.get_bone_count():
		var lower := skeleton.get_bone_name(bone).to_lower()
		if not skeleton.get_bone_children(bone).is_empty(): continue
		if "tail" in lower or "snake" in lower or "head" in lower or "jaw" in lower or "lid" in lower or "eye" in lower: continue
		leaves.append(bone)
	return leaves

## Peak of the fastest attack bone (body space, backward difference over >= 20 ms) after the wind-up.
func attack_peak() -> Dictionary:
	var best := 0.0
	var at := -1.0
	var curve: Array = []
	var k := 0
	for i in range(1, attack_trace.size()):
		# The first 0.1 s is the 0.08 s blend into the clip (shadow_beast.gd play("attack", 0.08)), not the blow.
		if float(attack_trace[i][0])-attack_t0 < ATTACK_BLEND: continue
		while k < i-1 and float(attack_trace[k+1][0]) <= float(attack_trace[i][0])-0.02: k += 1
		var dt: float = float(attack_trace[i][0])-float(attack_trace[k][0])
		if dt < 0.012: continue
		var a: PackedVector3Array = attack_trace[k][1]
		var b: PackedVector3Array = attack_trace[i][1]
		var fastest := 0.0
		for j in a.size(): fastest = maxf(fastest, a[j].distance_to(b[j]))
		var t: float = (float(attack_trace[i][0])+float(attack_trace[k][0]))*0.5-attack_t0
		curve.append([t, fastest/dt])
		if fastest/dt > best:
			best = fastest/dt
			at = t
	# The blow stops: the first moment after the peak below a quarter of its speed (the build's impact).
	var stop := -1.0
	for point in curve:
		if float(point[0]) > at and float(point[1]) < best*0.25:
			stop = point[0]
			break
	return {"peak": snappedf(at, 0.01), "stop": snappedf(stop, 0.01), "speed": snappedf(best, 0.01)}

static func ripple(list: Array) -> float:
	if list.size() < 10: return -1.0
	var mean := 0.0
	for v in list: mean += float(v)
	mean /= list.size()
	if mean < 0.01: return -1.0
	var spread := 0.0
	for v in list: spread += pow(float(v)-mean, 2)
	return snappedf(sqrt(spread/list.size())/mean, 0.01)

## ------------------------------------------------------------------ one species
func run_species(id: String) -> Dictionary:
	var r := {"id": id, "fail": [], "warn": []}
	var stats: Dictionary = catalog.get(id, {})
	if stats.is_empty():
		r.fail.append("not_in_catalog")
		return r
	var variant := Monster.resolved_variant(id, str(stats.get("map", "forest")))
	if variant == "":
		r.fail.append("no_glb")
		return r
	print("  MONSTER_CASE ", id, "_", variant, " ", JSON.stringify(stats))
	r.variant = variant
	# ---- 1 locomotion and 2 foot slide (solo feed)
	foot_samples = {}
	speeds = {}
	clip_scales = {}
	body_low = INF
	# The survival map reads the GLB on a worker thread before the night (monster.gd resolved_path): load it
	# first, so the spawn frame is not a long one.
	load(Monster.resolved_path(id, variant))
	await frames(5)
	var beast := spawn(id, stats, variant, START)
	if beast.monster == null:
		r.fail.append("no_monster_body")
		beast.queue_free()
		return r
	var skeleton := skeleton_of(beast)
	var height: float = beast.monster.height*beast.monster.stride
	foot_bones = contact_bones(skeleton)
	attack_bones = PackedInt32Array()
	for bone in skeleton.get_bone_count():
		var lower := skeleton.get_bone_name(bone).to_lower()
		for part in ["hand", "foot", "toe", "head", "jaw", "limb"]:
			if part in lower:
				attack_bones.append(bone)
				break
	# A rig with no named extremities: the whole skeleton's fastest bone.
	if attack_bones.size() < 2:
		attack_bones = PackedInt32Array()
		for bone in skeleton.get_bone_count(): attack_bones.append(bone)
	r.foot_bones = foot_bones.size()
	var walk_speed := float(stats.get("speed", 1.0))
	var run_speed: float = float(Monster.RUN_REF.get(id, 2.6))*beast.monster.stride
	var top := maxf(walk_speed, run_speed)
	var pop := MotionWatch.POSE_POP*maxf(1.0, height/1.7)
	r.height = snappedf(height, 0.01)
	r.pose_limit = snappedf(pop, 0.01)
	r.walk_speed = walk_speed
	r.run_speed = snappedf(run_speed, 0.01)
	var local := new_watch(id, beast, top, pop, func(): return not beast.dying)
	start_feed(beast, stats, variant, START, false)
	await frames(3)
	# A hit with no hit: the first snapshot's hp below shadow_beast's starting last_hp (45) runs the hit
	# branch (flash, hurt clip, hurt call). Its own `flash` is set only there.
	r.spawn_flash = float(beast.flash) > 0.0
	mark("idle")
	await seconds(1.0)
	mark("walk")
	feed_speed = walk_speed
	await seconds(0.6)
	segment = "walk"
	await seconds(1.4)
	r.walk_clip = "%s x%.2f" % [beast.monster.clip, beast.monster.player.speed_scale]
	segment = ""
	mark("run")
	feed_speed = run_speed
	await seconds(0.6)
	segment = "run"
	await seconds(1.4)
	r.run_clip = "%s x%.2f" % [beast.monster.clip, beast.monster.player.speed_scale]
	segment = ""
	mark("stop")
	feed_speed = 0.0
	await seconds(1.5)
	var band := CONTACT_BAND*maxf(1.0, height/1.7)
	var walk := foot_slide(skeleton, "walk", band, height)
	var run := foot_slide(skeleton, "run", band, height)
	r.contact = walk.used
	r.feet = walk.feet
	r.feet_named = feet_named
	r.slide_walk = walk.cm
	r.slide_run = run.cm
	r.foot_low = minf(walk.low, run.low)
	r.foot_low_walk = walk.low
	r.foot_low_run = run.low
	r.hover = walk.fly and run.fly
	r.floating = walk.float or run.float
	r.lift_walk = walk.lift
	r.lift_run = run.lift
	r.body_low = snappedf(body_low, 0.001)
	r.ripple_walk = ripple(speeds.get("walk", []))
	r.ripple_run = ripple(speeds.get("run", []))
	# ---- 3 attack (as the server sends a melee wind-up)
	attack_trace = []
	attack_t0 = -1.0
	attack_on = true
	mark("attack")
	feed_phase = "windup"
	feed_target = server_at+Vector3(feed_dir.x, 0, feed_dir.y)*1.5
	send_now()
	await seconds(feed_windup*0.5)
	r.attack_speed_seen = snappedf(beast.monster.player.speed_scale, 0.01)
	r.attack_speed_meant = snappedf(beast.monster.attack_speed(feed_windup), 0.01)
	await seconds(feed_windup*0.5)
	feed_phase = "recover"
	send_now()
	await seconds(RECOVER)
	feed_phase = "chase"
	send_now()
	var until := clock()+2.0
	while attack_on and clock() < until: await one_frame()
	attack_on = false
	var peak := attack_peak()
	r.windup = feed_windup
	r.attack_peak = peak.peak
	r.attack_stop = peak.stop
	r.attack_diff = snappedf(peak.peak-feed_windup, 0.01) if peak.peak >= 0.0 else 99.0
	r.impact_clip = float(Monster.ATTACK_IMPACT.get(id, 0.0))
	await seconds(0.6)
	# ---- 4 hurt
	mark("hurt")
	flash_max = 0.0
	hurt_seen = false
	flash_on = true
	feed_hp -= maxf(5.0, feed_max_hp*0.1)
	send_now()
	await seconds(0.4)
	flash_on = false
	var overlaid := false
	for mesh in beast.monster.model.find_children("*", "MeshInstance3D", true, false):
		if (mesh as MeshInstance3D).material_overlay == beast.monster.overlay: overlaid = true
	r.flash = snappedf(flash_max, 0.01)
	r.flash_overlay = overlaid
	r.hurt_clip = hurt_seen
	await seconds(1.0)
	r.local = close_watch(local, "mon_"+id+"/local")
	# ---- 5 death (main.gd: the enemy left the list at night -> die())
	feed_on = false
	sink_at = INF
	# The same body goes on being drawn: nothing to excuse.
	var dying := new_watch(id, beast, top, pop, func(): return clock() < sink_at, 0)
	mark("death")
	var death_len: float = beast.monster.length("death")
	beast.die()
	var died := clock()
	sink_at = died+death_len+0.25
	death_body = beast
	death_top = 0.0
	death_on = true
	while is_instance_valid(beast) and clock()-died < death_len+6.0: await one_frame()
	death_on = false
	r.death_clip = snappedf(death_len, 0.01)
	r.death_s = snappedf(clock()-died, 0.01) if not is_instance_valid(beast) else -1.0
	r.death_top = snappedf(death_top, 0.01)
	r.death = close_watch(dying, "mon_"+id+"/death")
	if is_instance_valid(beast): beast.queue_free()
	await frames(2)
	# ---- 6 co-op: a fresh body on a jittered feed
	var other := spawn(id, stats, variant, REMOTE_START)
	var remote := new_watch(id, other, top, pop, func(): return not other.dying)
	remote.excuse("mon_"+id, 3)
	mark("remote")
	start_feed(other, stats, variant, REMOTE_START, true)
	await seconds(0.6)
	feed_speed = walk_speed
	await seconds(0.6)
	segment = "rwalk"
	await seconds(1.8)
	segment = ""
	# A right-angle turn into a run, then a stop.
	mark("remote_turn_run")
	feed_dir = Vector2(0, 1)
	feed_speed = run_speed
	await seconds(0.6)
	segment = "rrun"
	await seconds(1.4)
	segment = ""
	feed_speed = 0.0
	await seconds(1.5)
	for seg in clip_scales: clip_scales[seg] = [snappedf(clip_scales[seg][0], 0.01), snappedf(clip_scales[seg][1], 0.01)]
	r.clip_scales = clip_scales
	r.ripple_remote_walk = ripple(speeds.get("rwalk", []))
	r.ripple_remote_run = ripple(speeds.get("rrun", []))
	r.remote = close_watch(remote, "mon_"+id+"/remote")
	feed_on = false
	other.queue_free()
	fed = null
	await frames(2)
	# ---- verdict
	if not r.local.pass: r.fail.append("motion(%s)" % " ".join(r.local.kinds))
	if r.feet > 0 and not r.hover and maxf(r.slide_walk, r.slide_run) > SLIDE_LIMIT: r.fail.append("foot_slide")
	if absf(r.attack_diff) > ATTACK_LIMIT: r.fail.append("attack_timing")
	if r.flash < 0.5 or not r.flash_overlay: r.fail.append("hit_flash")
	if r.spawn_flash: r.fail.append("spawn_flash")
	if r.death_s < 0.0 or r.death_s > death_len+3.0: r.fail.append("death_hide")
	if not r.death.pass: r.fail.append("death_motion(%s)" % " ".join(r.death.kinds))
	if not r.remote.pass: r.fail.append("remote(%s)" % " ".join(r.remote.kinds))
	if r.death_s >= 0.0 and r.death_top > DEATH_VISIBLE: r.warn.append("death_visible_at_free(%.2fm)" % r.death_top)
	if r.hover: r.warn.append("flies(feet %.2fm up, slide not judged)" % r.foot_low)
	if r.floating: r.warn.append("floats(feet %.2fm up walking, %.2fm running)" % [r.foot_low_walk, r.foot_low_run])
	if r.feet == 0: r.warn.append("no_feet")
	return r

func print_line(r: Dictionary) -> void:
	if not r.has("local"):
		print("MONSTER_MOTION ", r.id, " FAIL ", ",".join(PackedStringArray(r.fail)))
		return
	print("MONSTER_MOTION %s h=%.2f pose=%.3f/%.2f jumps=%d judder=%.3f slide_cm=walk %s run %s lift_m=%s/%s feet=%d foot_low=%.3f body_low=%.3f%s attack=%.2fs/windup %.2fs (diff %+.2f, clip x%.2f meant x%.2f, stop %.2f) flash=%.2f%s%s death=%.2fs top=%.2f death_pops=%d remote=jumps %d pose_pops %d judder %.3f ripple=%.2f/%.2f/%.2f %s %s" % [
		r.id, r.height, r.local.pose_step, r.pose_limit, r.local.jumps, r.local.judder,
		str(r.slide_walk), str(r.slide_run), str(r.lift_walk), str(r.lift_run), r.feet, r.foot_low, r.body_low, " flies" if r.hover else (" floats" if r.floating else ""),
		r.attack_peak, r.windup, r.attack_diff, r.attack_speed_seen, r.attack_speed_meant, r.attack_stop,
		r.flash, "" if r.flash_overlay else " no_overlay", " spawn_flash" if r.spawn_flash else "",
		r.death_s, r.death_top, r.death.pose_pops, r.remote.jumps, r.remote.pose_pops, r.remote.judder,
		r.ripple_walk, r.ripple_run, r.ripple_remote_walk,
		"PASS" if r.fail.is_empty() else "FAIL", ",".join(PackedStringArray(r.fail+r.warn))])
