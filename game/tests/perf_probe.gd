extends SceneTree
## Measures the village frame cost and what each system adds. Logs in, stands at a
## few spots, then switches systems off one at a time at the square (night and day
## follow --hour). Vsync is off so frame times are real. Prints a table.
var app: Node

func _initialize() -> void:
	call_deferred("run")

func sample(seconds := 2.0) -> Dictionary:
	for i in 20: await process_frame
	var frames := 0
	var worst := 0.0
	var started := Time.get_ticks_usec()
	var last := started
	var cpu := 0.0
	var physics := 0.0
	var draws := 0.0
	var objects := 0.0
	var primitives := 0.0
	while Time.get_ticks_usec()-started < seconds*1000000.0:
		await process_frame
		var now := Time.get_ticks_usec()
		worst = maxf(worst, (now-last)/1000.0)
		last = now
		frames += 1
		cpu += Performance.get_monitor(Performance.TIME_PROCESS)*1000.0
		physics += Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)*1000.0
		draws += Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
		objects += Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME)
		primitives += Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)
	var ms := (Time.get_ticks_usec()-started)/1000.0/frames
	return {"ms":snappedf(ms,0.01),"fps":snappedf(1000.0/ms,0.1),"worst":snappedf(worst,0.1),"process":snappedf(cpu/frames,0.01),
		"physics":snappedf(physics/frames,0.01),"draws":int(draws/frames),"objects":int(objects/frames),"prims":int(primitives/frames)}

func report(name: String, data: Dictionary) -> void:
	print("PERF %-26s ms=%6.2f fps=%6.1f worst=%6.1f process=%5.2f physics=%5.2f draws=%5d objects=%5d prims=%8d" % [name, data.ms, data.fps, data.worst, data.process, data.physics, data.draws, data.objects, data.prims])

func stand(at: Vector2) -> void:
	var p: Vector3 = load("res://scripts/town.gd").point(at, .1)
	app.player.position = p
	app.follow_camera(1)

func lights(on: bool) -> void:
	for light in app.find_children("*", "OmniLight3D", true, false):
		light.visible = on

func module(path_part: String) -> Node:
	for m in app.modules:
		if is_instance_valid(m) and str(m.get_script().resource_path).contains(path_part): return m
	return null

func toggle(node: Node, on: bool) -> void:
	if node == null: return
	node.process_mode = Node.PROCESS_MODE_INHERIT if on else Node.PROCESS_MODE_DISABLED
	for child in node.get_children():
		if child is Node3D: child.visible = on
	if node is Node3D: node.visible = on

func run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	var api = load("res://scripts/api.gd").new(); root.add_child(api); api.base_url = "http://127.0.0.1:8766"
	var login: Dictionary = await api.post("/v1/auth/register", {"username":"perf_"+str(Time.get_ticks_usec()), "password":"Perf-probe-password-1"})
	if not login.ok: print("LOGIN_FAILED"); quit(1); return
	Engine.set_meta("studio_session", {"token":login.data.token, "url":api.base_url, "room":"home"})
	change_scene_to_file("res://scenes/main.tscn")
	await create_timer(5.0).timeout
	app = current_scene
	print("OMNI_LIGHTS ", app.find_children("*", "OmniLight3D", true, false).size(), " visible=", app.find_children("*", "OmniLight3D", true, false).filter(func(l): return l.is_visible_in_tree()).size())
	print("MESHES ", app.find_children("*", "MeshInstance3D", true, false).size(), " multimesh=", app.find_children("*", "MultiMeshInstance3D", true, false).size())
	if "--jitter" in OS.get_cmdline_user_args():
		await jitter_check()
		quit(0)
		return
	if "--segment" in OS.get_cmdline_user_args():
		await segment_breakdown()
		quit(0)
		return
	if "--walk" in OS.get_cmdline_user_args():
		await walk_route()
		quit(0)
		return
	if "--pond" in OS.get_cmdline_user_args():
		await pond_breakdown()
		quit(0)
		return
	for spot in [["square", Vector2(-33,37)], ["pond", Vector2(-40,40)], ["camp", Vector2(52,36)], ["lighthouse", Vector2(5,74)], ["windmill", Vector2(-20,-36)]]:
		stand(spot[1])
		report("spot "+spot[0], await sample())
	stand(Vector2(-33,37))
	report("square baseline", await sample())
	lights(false); report("no omni lights", await sample()); lights(true)
	app.sun.shadow_enabled = false; report("no sun shadow", await sample()); app.sun.shadow_enabled = true
	for part in ["shadow_folk","field_objects","building_dressing","occluder_fade"]:
		var m := module(part)
		toggle(m, false); report("without "+part, await sample()); toggle(m, true)
	var map: Node = app.town.map
	for child_name in ["Roads","Environment","Buildings"]:
		var n: Node = map.get_node_or_null(child_name)
		if n: n.visible = false; report("hide "+child_name, await sample()); n.visible = true
	var life_root: Node = app.life
	toggle(life_root, false); report("without village_life", await sample()); toggle(life_root, true)
	get_root().msaa_3d = Viewport.MSAA_DISABLED; report("msaa off", await sample()); get_root().msaa_3d = Viewport.MSAA_4X
	app.environment.adjustment_enabled = false; report("no color grade", await sample())
	report("square end", await sample())
	quit(0)

## Finds what makes the pond slow: each system off in turn while standing there.
func pond_breakdown() -> void:
	for spot in [["pond", Vector2(-40,40)], ["pond west", Vector2(-50,38)], ["pond pier", Vector2(-44,33)]]:
		stand(spot[1])
		report("at "+spot[0], await sample(1.5))
	stand(Vector2(-40,40))
	report("pond baseline", await sample(1.5))
	for part in ["shadow_folk","field_objects","building_dressing","occluder_fade"]:
		var m := module(part)
		toggle(m, false); report("pond without "+part, await sample(1.5)); toggle(m, true)
	app.life.process_mode = Node.PROCESS_MODE_DISABLED
	report("pond life paused", await sample(1.5))
	app.life.process_mode = Node.PROCESS_MODE_INHERIT
	for child in app.life.get_children():
		var was: int = child.process_mode
		child.process_mode = Node.PROCESS_MODE_DISABLED
		report("pond without life/"+str(child.name), await sample(1.0))
		child.process_mode = was
	app.set_process(false); report("pond main _process off", await sample(1.0)); app.set_process(true)
	app.set_physics_process(false); report("pond main _physics off", await sample(1.0)); app.set_physics_process(true)
	app.player.set_physics_process(false); report("pond player physics off", await sample(1.0)); app.player.set_physics_process(true)
	lights(false); report("pond no omni", await sample(1.0)); lights(true)
	var map: Node = app.town.map
	for child in map.get_children():
		if child is Node3D and child.visible:
			child.visible = false
			report("pond hide map/"+str(child.name), await sample(1.0))
			child.visible = true

## Walks a long route with real input and logs every frame over 40 ms (a visible
## hitch) with where it happened, plus the frame-time distribution.
const ROUTE := [Vector2(-33,37),Vector2(-40,34.5),Vector2(-46,33),Vector2(-50.5,27.5),Vector2(-46,33),Vector2(-33,37),
	Vector2(-26,36.5),Vector2(-20,35),Vector2(-15.5,36.2),Vector2(-14,33.4),Vector2(-13,31),Vector2(-12,27)]
func walk_route() -> void:
	var times: Array[float] = []
	var hitches := 0
	var last := Time.get_ticks_usec()
	for target in ROUTE:
		var started := Time.get_ticks_msec()
		while Time.get_ticks_msec()-started < 9000:
			var at := Vector2(app.player.position.x, app.player.position.z)
			var to: Vector2 = target-at
			if to.length() < 0.7: break
			var d := to.normalized()
			for action in ["move_left","move_right","move_forward","move_back"]: Input.action_release(action)
			if d.x > 0.05: Input.action_press("move_right", d.x)
			if d.x < -0.05: Input.action_press("move_left", -d.x)
			if d.y > 0.05: Input.action_press("move_back", d.y)
			if d.y < -0.05: Input.action_press("move_forward", -d.y)
			await process_frame
			var now := Time.get_ticks_usec()
			var ms := (now-last)/1000.0
			last = now
			times.append(ms)
			if ms > 40.0:
				hitches += 1
				print("HITCH %.1f ms at (%.1f, %.1f) frame %d nodes=%d" % [ms, at.x, at.y, times.size(), Performance.get_monitor(Performance.OBJECT_NODE_COUNT)])
	for action in ["move_left","move_right","move_forward","move_back"]: Input.action_release(action)
	times.sort()
	var n := times.size()
	print("WALK frames=%d p50=%.2f p95=%.2f p99=%.2f max=%.1f hitches=%d" % [n, times[n/2], times[int(n*0.95)], times[int(n*0.99)], times[-1], hitches])

## Walks the slow stretch (home door -> pond pier) with one system off at a time.
func walk_segment(from: Vector2, to: Vector2) -> Dictionary:
	stand(from)
	for i in 10: await process_frame
	var times: Array[float] = []
	var last := Time.get_ticks_usec()
	var started := Time.get_ticks_msec()
	while Time.get_ticks_msec()-started < 12000:
		var at := Vector2(app.player.position.x, app.player.position.z)
		var d: Vector2 = to-at
		if d.length() < 0.7: break
		d = d.normalized()
		for action in ["move_left","move_right","move_forward","move_back"]: Input.action_release(action)
		if d.x > 0.05: Input.action_press("move_right", d.x)
		if d.x < -0.05: Input.action_press("move_left", -d.x)
		if d.y > 0.05: Input.action_press("move_back", d.y)
		if d.y < -0.05: Input.action_press("move_forward", -d.y)
		await process_frame
		var now := Time.get_ticks_usec()
		times.append((now-last)/1000.0)
		last = now
	for action in ["move_left","move_right","move_forward","move_back"]: Input.action_release(action)
	var total := 0.0
	var worst := 0.0
	for t in times:
		total += t
		worst = maxf(worst, t)
	return {"avg":snappedf(total/maxf(1,times.size()),0.1),"worst":snappedf(worst,0.1),"frames":times.size()}

func segment_breakdown() -> void:
	var a := Vector2(-52,23.5)
	var b := Vector2(-40,32)
	print("SEG baseline ", await walk_segment(a,b))
	print("SEG baseline again ", await walk_segment(a,b))
	for part in ["occluder_fade","field_objects","shadow_folk","building_dressing"]:
		var m := module(part)
		toggle(m, false)
		print("SEG without ", part, " ", await walk_segment(a,b))
		toggle(m, true)
	app.life.process_mode = Node.PROCESS_MODE_DISABLED
	print("SEG life paused ", await walk_segment(a,b))
	app.life.process_mode = Node.PROCESS_MODE_INHERIT
	var main_script: Node = app
	main_script.hint.visible = false
	print("SEG hint hidden ", await walk_segment(a,b))
	main_script.hint.visible = true

## Walks straight along the square road and measures how evenly the walker moves
## on screen: frame-to-frame screen speed should vary smoothly, not in steps.
func jitter_check() -> void:
	stand(Vector2(-40,34.6))
	for i in 30: await process_frame
	Input.action_press("move_right")
	for i in 40: await process_frame
	var last := Vector2.ZERO
	var world_last := Vector3.ZERO
	var steps: Array[float] = []
	var world_steps: Array[float] = []
	var raw_steps: Array[float] = []
	var raw_last := Vector3.ZERO
	var fractions: Array[float] = []
	for i in 240:
		# Read what is about to be drawn: after physics and _process, before rendering.
		await RenderingServer.frame_pre_draw
		var shown: Vector3 = app.player.visual.global_position
		var p: Vector2 = app.camera.unproject_position(shown)
		var raw: Vector3 = app.player.global_position
		fractions.append(Engine.get_physics_interpolation_fraction())
		if i > 0:
			steps.append(p.x-last.x)
			world_steps.append((shown-world_last).length())
			raw_steps.append((raw-raw_last).length())
		last = p
		world_last = shown
		raw_last = raw
	Input.action_release("move_right")
	var mean := 0.0
	for v in steps: mean += v
	mean /= steps.size()
	var spread := 0.0
	for v in steps: spread += (v-mean)*(v-mean)
	spread = sqrt(spread/steps.size())
	var wmean := 0.0
	for v in world_steps: wmean += v
	wmean /= world_steps.size()
	var wspread := 0.0
	for v in world_steps: wspread += (v-wmean)*(v-wmean)
	wspread = sqrt(wspread/world_steps.size())
	var rmean := 0.0
	for v in raw_steps: rmean += v
	rmean /= raw_steps.size()
	var rspread := 0.0
	for v in raw_steps: rspread += (v-rmean)*(v-rmean)
	rspread = sqrt(rspread/raw_steps.size())
	print("JITTER raw_body_step_mean=%.4f raw_body_step_sd=%.4f fractions=%s" % [rmean, rspread, str(fractions.slice(0,12))])
	print("JITTER screen_step_mean=%.3f px screen_step_sd=%.3f px world_step_mean=%.4f m world_step_sd=%.4f m fps=%d" % [mean, spread, wmean, wspread, Engine.get_frames_per_second()])
