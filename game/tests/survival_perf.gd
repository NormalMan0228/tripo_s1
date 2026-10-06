extends SceneTree
## Measures the expedition frame cost and what each part adds: registers, starts a run in
## --region (default forest), then hides map parts and switches systems off one at a time.
## Vsync is off so frame times are real. Run rendered: tools/test.ps1 -ClientScript survival_perf -Capture
const Main = preload("res://scripts/main.gd")
var app: Node3D

func _initialize() -> void:
	call_deferred("run")

func sample(seconds := 1.5) -> Dictionary:
	for i in 15: await process_frame
	var frames := 0
	var worst := 0.0
	var started := Time.get_ticks_usec()
	var last := started
	var cpu := 0.0
	var draws := 0.0
	var prims := 0.0
	while Time.get_ticks_usec()-started < seconds*1000000.0:
		await process_frame
		var now := Time.get_ticks_usec()
		worst = maxf(worst, (now-last)/1000.0)
		last = now
		frames += 1
		cpu += Performance.get_monitor(Performance.TIME_PROCESS)*1000.0
		draws += Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
		prims += Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)
	var ms := (Time.get_ticks_usec()-started)/1000.0/frames
	return {"ms":ms,"fps":1000.0/ms,"worst":worst,"process":cpu/frames,"draws":int(draws/frames),"prims":int(prims/frames)}

func report(name: String, d: Dictionary) -> void:
	print("SPERF %-34s ms=%6.2f fps=%6.1f worst=%6.1f process=%5.2f draws=%5d prims=%8d" % [name, d.ms, d.fps, d.worst, d.process, d.draws, d.prims])

func run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	var region := "forest"
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--region="): region = argument.trim_prefix("--region=")
	app = Main.new()
	root.add_child(app)
	await create_timer(0.4).timeout
	await app.authenticate(true, "http://127.0.0.1:8766", "perf_"+str(Time.get_ticks_msec()), "Perf-probe-password-1", "")
	report("village", await sample())
	await app.start_run(region, "standard")
	await create_timer(3.0).timeout
	var map: Node = app.world.get_node_or_null("SurvivalMap")
	print("SPERF_INFO region=", region, " stats=", map.stats if map else {}, " meshes=", app.find_children("*", "MeshInstance3D", true, false).size(),
		" multimesh=", app.find_children("*", "MultiMeshInstance3D", true, false).size(), " particles=", app.find_children("*", "GPUParticles3D", true, false).size()+app.find_children("*", "CPUParticles3D", true, false).size(),
		" omni=", app.find_children("*", "OmniLight3D", true, false).size(), " nodes=", Performance.get_monitor(Performance.OBJECT_NODE_COUNT))
	report(region+" baseline", await sample())
	report(region+" baseline again", await sample())
	if map:
		for child in map.get_children():
			if child is Node3D and child.visible:
				child.visible = false
				report("hide "+str(child.name), await sample(1.0))
				child.visible = true
	var sun: DirectionalLight3D = map.sun if map else null
	if sun:
		sun.shadow_enabled = false; report("no sun shadow", await sample()); sun.shadow_enabled = true
	if map:
		map.set_process(false); report("map _process off", await sample()); map.set_process(true)
	app.set_process(false); report("main _process off", await sample()); app.set_process(true)
	app.set_physics_process(false); report("main _physics off", await sample()); app.set_physics_process(true)
	for node in app.world.get_children():
		if node != map and node is Node3D and node.visible:
			node.visible = false
			report("hide world/"+str(node.name), await sample(1.0))
			node.visible = true
	get_root().msaa_3d = Viewport.MSAA_DISABLED; report("msaa off", await sample())
	report(region+" end", await sample())
	quit(0)
