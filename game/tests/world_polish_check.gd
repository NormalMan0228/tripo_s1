extends SceneTree
## Headless checks for the world-presentation pass (no server):
##  - stairs: a room's stair climb plays the walk clip, never a gliding idle pose.
##  - gait: walking, sharp turns, reversals, stops, running and an attack keep the
##    lower body with the upper body (hips square to the chest, knees bending forward,
##    feet on their own side, planted feet on the ground up and down a slope) in
##    the final drawn pose.
##  - fade: every change of place fades out and in over the same short times, a
##    fade-in after a long build frame still fades (no pop), and the loading card
##    shows while covered and is cleared once the veil is gone.
##  - folk: shadow folk only after dark; villagers on the same rounds by day; a
##    dissolve in view, an instant change out of sight; rooms and names agree.
##   Godot --headless --path game --script res://tests/world_polish_check.gd [-- --only=stairs|gait|fade|folk]
var failures: Array[String] = []
var only := ""

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--only="): only = arg.trim_prefix("--only=")
	call_deferred("run")
	create_timer(300).timeout.connect(func():
		push_error("world_polish_check exceeded 300 seconds")
		quit(2))

func check(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failures.append(description)

func wants(name: String) -> bool:
	return only.is_empty() or only == name

func run() -> void:
	if wants("stairs"): await stairs()
	if wants("gait"): await gait()
	if wants("fade"): await fade()
	if wants("folk"): await folk()
	print("WORLD_POLISH ", JSON.stringify({"ok":failures.is_empty(), "failures":failures}))
	quit(0 if failures.is_empty() else 1)

## Climbs a straight staircase and the lighthouse's spiral: while the walker is on
## the stair (above the floor) the walk clip runs and the body reports motion.
func stairs() -> void:
	Engine.set_meta("interior_hour", 13.0)
	for room in ["home", "17_lighthouse"]:
		Engine.set_meta("studio_session", {"token":"", "url":"http://127.0.0.1:9", "room":room})
		var studio: Control = load("res://scenes/studio.tscn").instantiate()
		root.add_child(studio)
		await create_timer(0.8).timeout
		var record: Dictionary = {}
		for item in studio.decor:
			if item.has("link"):
				record = item
				break
		check(not record.is_empty(), "%s has a stair" % room)
		if record.is_empty(): continue
		var front := Vector3(0, 0, 1).rotated(Vector3.UP, float(record.yaw))
		for distance in [0.7, 0.9, 1.1, 1.4]:
			var at: Vector3 = record.center+front*(float(record.half.y)+distance)
			at.y = 0
			if studio.can_stand(at):
				studio.hero.position = at
				break
		await create_timer(0.3).timeout
		studio.travel(record)
		var climbing := 0
		var walking := 0
		for i in 120:
			await physics_frame
			if studio.floor_index != 0 or not studio.travelling: break
			if studio.hero.position.y > 0.05:
				climbing += 1
				if studio.hero.current_clip == "walk" and studio.hero.locomotion_velocity.length() > 0.5: walking += 1
		check(climbing > 20, "%s: the walker climbs the %s (%d frames)" % [room, record.kind, climbing])
		check(walking >= climbing*0.9, "%s: the walk clip runs on the %s (%d of %d frames)" % [room, record.kind, walking, climbing])
		studio.queue_free()
		await process_frame
		await process_frame
	Engine.remove_meta("interior_hour")

## ------------------------------------------------------------------ gait

var walker: CharacterBody3D
var skeleton: Skeleton3D
var bones := {}
var worst := {}
var phase_name := ""
var samples := 0
var ankle_height := 0.0

## Drives the village walker with the real input actions over a flat floor and reads
## every final pose (after the contact IK) the skeleton draws.
func gait() -> void:
	var stage := Node3D.new()
	root.add_child(stage)
	var floor_body := StaticBody3D.new()
	floor_body.collision_layer = 1
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(200, 1, 200)
	shape.shape = box
	shape.position.y = -0.5
	floor_body.add_child(shape)
	stage.add_child(floor_body)
	walker = load("res://scripts/player.gd").new()
	stage.add_child(walker)
	await physics_frame
	await physics_frame
	skeleton = walker.hand_skeleton
	for bone in ["Pelvis", "L_Thigh", "R_Thigh", "L_Calf", "R_Calf", "L_Foot", "R_Foot", "L_Upperarm", "R_Upperarm"]:
		bones[bone] = skeleton.find_bone(bone)
	check(not bones.values().has(-1), "gait: the rig has hips, legs and shoulders")
	if bones.values().has(-1): return
	ankle_height = point("L_Foot").y-walker.global_position.y
	skeleton.skeleton_updated.connect(sample)
	var steps := [["idle", [], 0.6], ["walk", ["move_forward"], 1.6], ["turn right", ["move_right"], 1.0],
		["reverse", ["move_left"], 1.0], ["diagonal", ["move_back", "move_left"], 0.8], ["stop", [], 0.8],
		["run", ["move_forward", "run"], 1.4], ["run reverse", ["move_back", "run"], 1.0], ["run stop", [], 0.8],
		["zigzag", ["move_left"], 0.25], ["zigzag", ["move_right"], 0.25], ["zigzag", ["move_left"], 0.25], ["zigzag", ["move_right"], 0.25],
		["settle", [], 0.8], ["attack", [], 0.6], ["to ramp", [], 0.1], ["uphill", ["move_forward"], 2.2], ["downhill", ["move_back"], 2.2], ["ramp stop", [], 0.6]]
	for step in steps:
		phase_name = step[0]
		if phase_name == "attack": walker.react("attack")
		if phase_name == "to ramp":
			# An 18 degree slope (the island's steeper paths) rising toward -Z.
			var ramp := StaticBody3D.new()
			var slope := CollisionShape3D.new()
			var plank := BoxShape3D.new()
			plank.size = Vector3(6, 1, 14)
			slope.shape = plank
			ramp.add_child(slope)
			stage.add_child(ramp)
			ramp.position = Vector3(40, -0.5*cos(deg_to_rad(18.0))+0.02, -2.0)
			ramp.rotation.x = deg_to_rad(18.0)
			walker.global_position = Vector3(40, 0.05, 6.5)
			walker.velocity = Vector3.ZERO
		for action in step[1]: Input.action_press(action)
		await create_timer(float(step[2])).timeout
		for action in step[1]: Input.action_release(action)
	skeleton.skeleton_updated.disconnect(sample)
	for key in worst: print("GAIT worst %s = %.3f (%s)" % [key, worst[key][0], worst[key][1]])
	check(samples > 400, "gait: sampled %d drawn poses" % samples)
	check(worst.hip_twist[0] < 40.0, "gait: hips stay square to the chest (worst %.1f deg, %s)" % worst.hip_twist)
	check(worst.knee_back[0] < 0.035, "gait: knees never fold backwards (worst %.3f m, %s)" % worst.knee_back)
	check(worst.feet_cross[0] < 0.06, "gait: feet stay on their own side (worst %.3f m, %s)" % worst.feet_cross)
	check(worst.hip_yaw[0] < 40.0, "gait: hips face where the body faces (worst %.1f deg, %s)" % worst.hip_yaw)
	check(worst.knee_flex[0] < 100.0, "gait: knees bend no deeper than a stride (worst %.1f deg, %s)" % worst.knee_flex)
	check(worst.plant_gap[0] < 0.2, "gait: planted feet stay on the ground, slopes too (worst %.3f m, %s)" % worst.plant_gap)
	stage.queue_free()
	await process_frame

func note(key: String, value: float) -> void:
	if not worst.has(key) or value > worst[key][0]: worst[key] = [value, phase_name]

func point(bone: String) -> Vector3:
	return skeleton.global_transform*skeleton.get_bone_global_pose(bones[bone]).origin

func flat(v: Vector3) -> Vector3:
	return Vector3(v.x, 0, v.z).normalized()

func sample() -> void:
	samples += 1
	var forward := flat(-walker.visual.global_basis.z)
	var right := forward.cross(Vector3.UP)
	# Right is whichever thigh / shoulder the body's right side holds.
	var hips := flat(point("R_Thigh")-point("L_Thigh"))
	var shoulders := flat(point("R_Upperarm")-point("L_Upperarm"))
	if hips.dot(right) < 0.0: hips = -hips
	if shoulders.dot(right) < 0.0: shoulders = -shoulders
	note("hip_twist", rad_to_deg(hips.angle_to(shoulders)))
	note("hip_yaw", rad_to_deg(hips.angle_to(right)))
	for side in ["L", "R"]:
		var hip := point(side+"_Thigh")
		var knee := point(side+"_Calf")
		var foot := point(side+"_Foot")
		var line := (foot-hip).normalized()
		var bend := (knee-hip)-line*(knee-hip).dot(line)
		note("knee_back", maxf(0.0, -bend.dot(forward)))
	var pose: SkeletonModifier3D = walker.locomotion_pose
	for i in pose.legs.size():
		var leg: Dictionary = pose.legs[i]
		var hip := point(["L", "R"][i]+"_Thigh")
		var knee := point(["L", "R"][i]+"_Calf")
		var foot := point(["L", "R"][i]+"_Foot")
		note("knee_flex", 180.0-rad_to_deg((hip-knee).angle_to(foot-knee)))
		if leg.contact and pose.blend > 0.9:
			var ray := PhysicsRayQueryParameters3D.create(foot+Vector3.UP*0.6, foot+Vector3.DOWN*0.8, 1)
			var hit := walker.get_world_3d().direct_space_state.intersect_ray(ray)
			if not hit.is_empty(): note("plant_gap", absf(foot.y-hit.position.y-ankle_height))
	var left_side := (point("L_Foot")-point("R_Foot")).dot(right)
	var thighs := (point("L_Thigh")-point("R_Thigh")).dot(right)
	# The feet cross when they sit on the opposite sides of the thighs' order.
	note("feet_cross", maxf(0.0, -left_side*signf(thighs)))

## ------------------------------------------------------------------ fade

func fade() -> void:
	var Transition = load("res://scripts/transition.gd")
	var veil = Transition.of(self)
	await process_frame
	# The stair check may have left a room mid-climb under the veil.
	if veil.veil.modulate.a > 0.0: await veil.fade_in()
	veil.loading(TranslationServer.translate("나의 집"))
	var started := Time.get_ticks_msec()
	await veil.fade_out()
	var out_ms := Time.get_ticks_msec()-started
	check(absf(out_ms-Transition.OUT*1000.0) < 120.0, "fade: out takes %d ms (%.0f)" % [out_ms, Transition.OUT*1000.0])
	check(is_equal_approx(veil.veil.modulate.a, 1.0) and veil.card.visible and veil.heading.text != "", "fade: covered by the loading card with the place name")
	check(not veil.tip.text.is_empty(), "fade: the card carries a tip")
	# The new place builds in one long frame, then fades in.
	veil.fade_in()
	OS.delay_msec(700)
	started = Time.get_ticks_msec()
	var first_frames: Array[float] = []
	while veil.veil.modulate.a > 0.0 and Time.get_ticks_msec()-started < 3000:
		await process_frame
		if first_frames.size() < 4: first_frames.append(veil.veil.modulate.a)
	var in_ms := Time.get_ticks_msec()-started
	check(first_frames[0] > 0.9, "fade: still covered right after the long build frame (%.2f)" % first_frames[0])
	check(in_ms > Transition.IN*1000.0*0.8 and in_ms < Transition.IN*1000.0+300.0, "fade: in takes %d ms (%.0f)" % [in_ms, Transition.IN*1000.0])
	check(not veil.card.visible, "fade: the card is cleared once the veil is gone")
	# A plain fade (a stair) stays a dark veil.
	await veil.fade_out()
	check(not veil.card.visible, "fade: a plain fade shows no card")
	await veil.fade_in()

## ------------------------------------------------------------------ folk

## The shadow folk by the player's clock: villagers at noon, shadows at night, a
## dissolve (never a pop) when the change happens next to the walker, at once out of
## sight, staggered switch points, and the same rule for room figures and names.
func folk() -> void:
	var Stub = load("res://tests/shadow_folk_stub.gd")
	var Folk = load("res://scripts/shadow_folk.gd")
	var DayFolk = load("res://scripts/day_folk.gd")
	var Interiors = load("res://scripts/interiors.gd")
	var Figure = load("res://scripts/shadow_figure.gd")
	var camera := Camera3D.new()
	root.add_child(camera)
	var app: Node3D = Stub.new()
	root.add_child(app)
	app.build(camera)
	for i in 8: await physics_frame
	app.spawn_villagers()
	app.daylight.override_hour = 12.0
	var module: Node3D = Folk.new()
	module.persist = false
	app.add_child(module)
	module.setup(app)
	for i in 10: await physics_frame
	var day_ok := true
	var shadows_by_day: Array = []
	for walker in module.walkers:
		if not (walker.day_target and walker.day_blend == 1.0 and walker.look_phase == 2 and not str(walker.title).contains("그림자")):
			day_ok = false
			shadows_by_day.append(walker.spec.id)
	check(day_ok and module.walkers.size() >= 10, "folk: at noon all %d residents are villagers (%s)" % [module.walkers.size(), shadows_by_day])
	var outdoors: Array = module.walkers.filter(func(w): return w.visible and w.present)
	check(not outdoors.is_empty(), "folk: %d villagers are out on their rounds at noon" % outdoors.size())
	# Night with the walker far away: everyone changes at once.
	app.player.position = Vector3(0, 30, -400)
	app.daylight.override_hour = 23.0
	module.clock = 0.0
	for i in 4: await physics_frame
	var night_ok := true
	for walker in module.walkers:
		if walker.day_target or walker.day_blend != 0.0 or walker.look_phase != 0 or not str(walker.title).contains("그림자"): night_ok = false
	check(night_ok, "folk: at 23:00 out of sight every resident is a shadow at once")
	# Morning beside a walker who is out: it dissolves over seconds.
	app.daylight.override_hour = 12.0
	module.clock = 0.0
	for i in 4: await physics_frame
	var near: Node3D = null
	for walker in module.walkers:
		if walker.visible and walker.present and walker.state != "hidden": near = walker
	check(near != null, "folk: someone is outdoors to watch change")
	if near == null: return
	app.player.position = near.global_position+Vector3(2.0, 0, 0)
	app.daylight.override_hour = 23.0
	module.clock = 0.0
	var started := Time.get_ticks_msec()
	var blends: Array[float] = []
	var mixed := false
	while Time.get_ticks_msec()-started < 4000:
		await physics_frame
		app.player.position = near.global_position+Vector3(2.0, 0, 0)
		blends.append(near.day_blend)
		if near.look_phase == 1: mixed = true
		if near.day_blend == 0.0 and blends.size() > 10: break
	var seconds := (Time.get_ticks_msec()-started)/1000.0
	var steps: int = blends.filter(func(b): return b > 0.05 and b < 0.95).size()
	check(not near.day_target and near.day_blend == 0.0, "folk: the %s in view became a shadow" % near.spec.id)
	check(mixed and steps > 30 and seconds > 1.5, "folk: it dissolved over %.1f s (%d mixed frames), no pop" % [seconds, steps])
	# Talking to a villager by day: its own name, words and voice, no shadow picture.
	var postman: Node3D = null
	for walker in module.walkers:
		if walker.spec.id == "postman": postman = walker
	postman.set_day(true, true)
	app.player.position = postman.global_position+Vector3(1.2, 0, 0)
	module.talk(postman)
	var said: Dictionary = app.dialogues[-1] if not app.dialogues.is_empty() else {}
	var words := " ".join(said.get("lines", []))
	check(said.get("speaker", "") == DayFolk.title("postman") and not words.contains("그림자"), "folk: the daytime postman talks as %s: %s" % [said.get("speaker", ""), words.left(40)])
	check(str(said.get("cast", "")).contains("day_postman") and load("res://scripts/voice_babble.gd").resolve(str(said.get("cast", ""))) == "postman", "folk: no shadow picture, the postman's voice")
	postman.end_talk()
	# Staggered: residents change at different points of dusk.
	var points: Array = []
	for id in DayFolk.LOOKS: points.append(DayFolk.switch_point(id))
	check(points.max()-points.min() > 0.2, "folk: switch points spread %.2f..%.2f" % [points.min(), points.max()])
	# Every resident changes on both sides of dusk and dawn, by the local clock.
	var by_clock := true
	for id in DayFolk.LOOKS:
		if not DayFolk.is_day(id, 13.0) or DayFolk.is_day(id, 1.0): by_clock = false
	check(by_clock, "folk: everyone is a villager at 13:00 and a shadow at 01:00")
	# Rooms: the still figures and the names follow the same rule.
	var still: Node3D = Figure.create_still("miller")
	root.add_child(still)
	still.set_day(DayFolk.is_day("miller", 13.0), true)
	check(still.look_phase == 2 and still.nameplate.text == DayFolk.title("miller"), "folk: the miller in the windmill is %s by day" % still.nameplate.text)
	still.set_day(DayFolk.is_day("miller", 1.0), true)
	check(still.look_phase == 0 and str(still.nameplate.text).contains("그림자"), "folk: and a shadow at night")
	still.queue_free()
	check(str(Interiors.resident_title("miller", 13.0)) == str(DayFolk.LOOKS.miller.title) and str(Interiors.resident_title("miller", 1.0)).contains("그림자"), "folk: room dialogue names follow the clock")
	check(Interiors.portrait("miller", 13.0).contains("day_") and Interiors.portrait("miller", 1.0).contains("shadow_"), "folk: daytime villagers have no shadow illustration")
	app.queue_free()
	camera.queue_free()
	await process_frame
