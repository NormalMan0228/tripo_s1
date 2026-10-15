extends SceneTree
## The village doors (village_doors.gd): coming back from the home the walker walks out of the open
## door and it shuts behind; walking in from the doorstep swings the door open and the walker walks
## in under the fade; the round trip ends on the same doorstep. Every physics tick of each walk is
## recorded: no step over 0.25 m, no jump in pace (abrupt start or stop), no turn pop.
## --capture saves artifacts/village_doors_*.png (a test leaf opening, the walk in, back out).
const Town = preload("res://scripts/town.gd")
const Doors = preload("res://scripts/village_doors.gd")
var failures: Array[String] = []
var recording := false
var samples: Array = []

func check(value: bool, message: String) -> void:
	if not value:
		failures.append(message)
		printerr(message)

func _initialize() -> void:
	physics_frame.connect(_tick)
	call_deferred("run")

func capturing() -> bool: return "--capture" in OS.get_cmdline_user_args()

func shot(name: String) -> void:
	if not capturing(): return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/village_doors_%s.png" % name))

func wait(seconds: float) -> void:
	await create_timer(seconds).timeout

## One sample per physics tick: [position, yaw, walking].
func _tick() -> void:
	if not recording: return
	var scene := current_scene
	if not is_instance_valid(scene) or not ("player" in scene): return
	var walker = scene.get("player")
	if not (walker is Node3D) or not is_instance_valid(walker) or not walker.is_inside_tree(): return
	samples.append([walker.global_position, walker.visual.rotation.y, scene.get_node_or_null("DoorWalk") != null])

## Judges a recorded walk from `first` on: steps, changes of pace (m/s per tick) and turns per tick.
func judge(label: String, from_walk: bool) -> void:
	var first := 0
	if from_walk:
		while first < samples.size() and not samples[first][2]: first += 1
	var walked := 0
	for s in samples: walked += 1 if s[2] else 0
	check(walked > 10, "%s: the walk ran (%d ticks)" % [label, walked])
	var max_step := 0.0
	var max_pace := 0.0
	var max_turn := 0.0
	var previous := -1.0
	for i in range(first+1, samples.size()):
		var a: Vector3 = samples[i-1][0]
		var b: Vector3 = samples[i][0]
		max_step = maxf(max_step, a.distance_to(b))
		var pace := Vector2(b.x-a.x, b.z-a.z).length()*60.0
		if previous >= 0.0: max_pace = maxf(max_pace, absf(pace-previous))
		previous = pace
		max_turn = maxf(max_turn, absf(angle_difference(float(samples[i-1][1]), float(samples[i][1]))))
	print("DOOR_WALK %s ticks=%d walked=%d max_step=%.3f max_pace_change=%.2f max_turn=%.3f" % [label, samples.size()-first, walked, max_step, max_pace, max_turn])
	check(max_step <= .25, "%s: a step of %.2f m in one tick" % [label, max_step])
	check(max_pace <= 1.0, "%s: pace changed %.2f m/s in one tick (abrupt start or stop)" % [label, max_pace])
	check(max_turn <= .35, "%s: turned %.2f rad in one tick" % [label, max_turn])

func door_angle(village: Node, key: String) -> float:
	return float(Doors.find(village, key).get("open", -1.0))

## Waits for the village after a scene change and for its walk out of the door to end.
func village_back() -> Node:
	var deadline := Time.get_ticks_msec()+90000
	while Time.get_ticks_msec() < deadline:
		var scene := current_scene
		if is_instance_valid(scene) and scene.get("screen") == "village" and scene.get_node_or_null("DoorWalk") == null and samples.any(func(s): return s[2]): break
		await process_frame
	await wait(.8)
	return current_scene

func run() -> void:
	var api = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = preload("res://tests/qa_server.gd").url()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): api.base_url = arg.trim_prefix("--server=")
	var login: Dictionary = await api.post("/v1/auth/register", {"username":"doors_"+str(Time.get_ticks_usec()), "password":"Local-doors-qa-password"})
	check(login.ok, "login")
	if not login.ok:
		quit(1)
		return
	# 1. Back from the home: the walk out of its door.
	samples.clear()
	recording = true
	Engine.set_meta("studio_session", {"token":login.data.token, "url":api.base_url, "room":"home"})
	change_scene_to_file("res://scenes/main.tscn")
	var village := await village_back()
	recording = false
	check(is_instance_valid(village) and village.screen == "village", "village loaded")
	if failures.size() > 0:
		finish()
		return
	check(not Doors.find(village, "home").is_empty() and not Doors.find(village, "workshop").is_empty(), "home and workshop doors built")
	print("DOORS_BUILT ", (village.town.map.get_node("VillageDoors").get_meta("doors", {}) as Dictionary).size())
	judge("walk_out", true)
	var home_spot := Town.point(Town.HOME_RETURN_AT, .3)
	check(village.player.global_position.distance_to(home_spot) < .5, "walked out to the home doorstep (%.2f m off)" % village.player.global_position.distance_to(home_spot))
	check(is_zero_approx(door_angle(village, "home")), "home door shut behind the walker")
	# 2. A leaf handed over by register() turns and shuts (no door node: sounds only).
	await leaf_check(village)
	# 3. Walking in from the doorstep, then out again.
	var door := Doors.find(village, "home")
	village.player.global_position = Town.door_return("home")
	await wait(1.0)
	samples.clear()
	recording = true
	await wait(.2)
	village.open_studio("home")
	await wait(.35)
	await shot("walk_in")
	check(door_angle(village, "home") > .5, "home door opening for the walk in")
	var deadline := Time.get_ticks_msec()+8000
	while Time.get_ticks_msec() < deadline and current_scene == village: await process_frame
	recording = false
	judge("walk_in", false)
	await wait(3.0)
	var home := current_scene
	check(home.get("room") == "home", "entered the home")
	samples.clear()
	recording = true
	home.leave()
	await process_frame
	village = await village_back()
	recording = false
	judge("walk_out_again", true)
	check(village.screen == "village", "back in the village")
	check(village.player.global_position.distance_to(home_spot) < .5, "round trip ends on the home doorstep")
	check(is_zero_approx(door_angle(village, "home")), "home door shut after the round trip")
	await wait(.3)
	await shot("back_out")
	finish()

func finish() -> void:
	print("VILLAGE_DOORS ", JSON.stringify({"ok":failures.is_empty(), "failures":failures}))
	quit(0 if failures.is_empty() else 1)

## A test-only leaf (a plain board, the map session's real door node replaces it): registered on the
## home, it turns about its origin by the opening angle and comes back shut.
func leaf_check(village: Node) -> void:
	var door := Doors.find(village, "home")
	var board := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(1.0, 2.0, .06)
	board.mesh = box
	village.town.map.add_child(board)
	var normal: Vector3 = door.normal
	board.global_transform = Transform3D(Basis.looking_at(-normal), door.base)
	var rest := board.global_transform.basis
	Doors.register("10_red_house", board)
	Doors.open(village, "home")
	await wait(.25)
	await shot("leaf_opening")
	await wait(.6)
	var turned := rest.z.angle_to(board.global_transform.basis.z)
	check(absf(turned-Doors.OPEN_ANGLE) < .02, "registered leaf opens by its angle (%.2f rad)" % turned)
	Doors.close(village, "home")
	await wait(.8)
	check(rest.z.angle_to(board.global_transform.basis.z) < .01, "registered leaf shuts")
	Doors.leaves.erase("10_red_house")
	board.queue_free()
