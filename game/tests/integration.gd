extends SceneTree

const Main = preload("res://scripts/main.gd")
var failed := false
var app: Node3D
var test_url := "http://127.0.0.1:8766"

func _initialize() -> void:
	call_deferred("run_test")

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed=true

func capture(name: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	await process_frame
	await RenderingServer.frame_post_draw
	var path := ProjectSettings.globalize_path("res://../artifacts/"+name+".png")
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--artifacts="):
			path=argument.trim_prefix("--artifacts=").path_join(name+".png")
	if root.get_texture().get_image().save_png(path)!=OK:
		failed=true
		push_error("Could not save integration evidence: "+name)

func run_test() -> void:
	app=Main.new()
	root.add_child(app)
	await process_frame
	await create_timer(0.4).timeout
	await capture("login")
	var name := "qa_"+str(Time.get_unix_time_from_system()).replace(".","_")
	await app.authenticate(true,test_url,name,"Qa-local-password-123","")
	expect(app.screen=="village","Godot registration and village bootstrap")
	if app.screen!="village":
		print(app.notice.text)
		quit(1)
		return
	expect(app.me.shards==80,"server wallet received")
	expect(app.sound.music[app.sound.music_index].stream!=null and app.sound.music[app.sound.music_index].playing and app.sound.music_mode=="village","village music is included and playing")
	expect(not app.right.get_parent().visible,"compact HUD starts with inventory drawer closed")
	await app.paint_object("#70afa3")
	expect(app.selected.color=="#70afa3","paint saved via API")
	await app.begin_place()
	expect(is_instance_valid(app.preview),"authenticated GLB loaded from bytes")
	if is_instance_valid(app.preview):
		app.preview.position=preload("res://scripts/town.gd").furniture_point(4,4)
		await app.place_preview()
	expect(app.me.objects[0].state=="placed","server-authorized placement")
	await capture("village-online")
	app.toggle_drawer()
	for i in 40:
		if is_instance_valid(app.inspect_model): break
		await create_timer(0.05).timeout
	expect(app.right.get_parent().visible and is_instance_valid(app.inspect_model),"owned GLB appears in inventory turntable")
	await capture("inventory-online")
	app.toggle_drawer()
	await app.start_run()
	expect(app.screen=="survival","survival map opened")
	while app.ticking: await process_frame
	app.toggle_pause()
	await create_timer(0.15).timeout
	var paused_elapsed: float=app.run.elapsed
	await create_timer(0.7).timeout
	expect(app.paused and is_equal_approx(app.run.elapsed,paused_elapsed),"pause stops survival input and elapsed time")
	await capture("survival-paused")
	app.toggle_pause()
	await create_timer(0.25).timeout
	expect(not app.paused and app.run.elapsed>paused_elapsed,"resume continues the same survival run")
	app.confirm_return()
	expect(is_instance_valid(app.return_dialog) and app.run.status=="active","early return requires deliberate confirmation")
	app.return_dialog.canceled.emit()
	await process_frame
	expect(app.sound.music[app.sound.music_index].stream!=null and app.sound.music[app.sound.music_index].playing and app.sound.music_mode=="forest","forest music is included and playing")
	await create_timer(0.4).timeout
	# Drive the real client using input intents; the server computes coordinates.
	Input.action_press("move_right")
	var approach_deadline := Time.get_ticks_msec()+3000
	while app.run.x<1.85 and Time.get_ticks_msec()<approach_deadline:
		await create_timer(.05).timeout
	Input.action_release("move_right")
	await create_timer(0.3).timeout
	expect(app.run.x>0 and app.run.x<3,"server-authoritative movement")
	print("HARVEST_APPROACH x=",app.run.x," z=",app.run.z)
	app.intent("harvest","n0")
	await create_timer(0.6).timeout
	expect(app.run.inventory.wood>3,"nearby harvest confirmed by server")
	app.intent("fire")
	await create_timer(0.6).timeout
	expect(app.run.fire_remaining>0,"campfire resource consumption")
	await capture("survival-online")
	if "--night" in OS.get_cmdline_user_args():
		while app.run.elapsed<37: await create_timer(0.2).timeout
		app.intent("fire")
		while app.run.elapsed<41: await create_timer(0.2).timeout
		expect(app.run.night and app.run.hp>90,"real server night transition and camp protection")
		await capture("survival-night")
		print("RENDER_METRIC fps=",Engine.get_frames_per_second()," draw_calls=",Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
	while app.ticking: await process_frame
	var saved_id: String=app.run_id
	var saved_elapsed: float=app.run.elapsed
	var saved_wood: int=app.run.inventory.wood
	await app.suspend_run()
	expect(app.screen=="village" and app.me.active_run==saved_id,"suspend preserves active expedition in village")
	await capture("village-resume")
	await app.logout()
	await app.authenticate(false,test_url,name,"Qa-local-password-123","")
	expect(app.me.active_run==saved_id and app.me.active_run_summary.day>=1,"saved expedition survives session replacement")
	await app.start_run()
	expect(app.run_id==saved_id and absf(app.run.elapsed-saved_elapsed)<0.5 and app.run.inventory.wood==saved_wood,"resume restores the same day, inventory and run")
	while app.ticking: await process_frame
	await app.leave_run()
	expect(app.screen=="village","abandon returns to village")
	if "--loss" in OS.get_cmdline_user_args():
		var balance_before: int=app.me.shards
		await app.start_run()
		var lost_id: String=app.run_id
		var deadline := Time.get_ticks_msec()+150000
		# Stand unprotected: use the real server clock, enemy attacks and loss screen.
		while app.run.status=="active" and Time.get_ticks_msec()<deadline:
			await create_timer(0.2).timeout
		expect(app.run.status=="lost" and app.run.hp==0 and app.results_shown,"unguarded player dies and sees the actual loss screen")
		await capture("survival-lost")
		var claim: Dictionary=await app.api.post("/v1/runs/"+lost_id+"/claim",app.api.mutation())
		expect(not claim.ok,"failed expedition cannot claim completion reward")
		await app.retry_run()
		expect(app.screen=="survival" and app.run_id!=lost_id and app.run.hp>99 and app.run.status=="active","retry creates a fresh playable expedition")
		await app.leave_run()
		expect(app.me.shards==balance_before,"loss and retry do not award currency")
	# Same network adapter and worker used for a mock generation.
	app.prompt.text="round wooden chair"
	await app.generate()
	for i in 40:
		await create_timer(0.25).timeout
		if app.job_id.is_empty() and app.me.objects.size()==2 and not app.refreshing: break
	expect(app.job_id.is_empty() and app.me.objects.size()==2,"game-server-worker-GLB pipeline")
	await app.logout()
	await process_frame
	expect(not is_instance_valid(app.inspect_model),"logout frees protected inventory preview")
	await app.authenticate(false,test_url,name,"Qa-local-password-123","")
	expect(app.me.objects.size()==2 and app.me.objects[0].state=="placed","objects persist after relogin")
	expect(app.me.shards==55,"generation billed exactly once")
	await app.logout()
	# Release scene-owned render resources before shutting down the capture harness.
	app.queue_free()
	await process_frame
	await create_timer(0.06).timeout
	if "--capture" in OS.get_cmdline_user_args(): await RenderingServer.frame_post_draw
	print("INTEGRATION_COMPLETE")
	quit(1 if failed else 0)
