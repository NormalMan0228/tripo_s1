extends SceneTree
var failures: Array[String]=[]
func check(value: bool,message: String) -> void:
	print(("PASS " if value else "FAIL ")+message)
	if not value:failures.append(message)
func _initialize() -> void:call_deferred("run")
func run() -> void:
	var app=load("res://scripts/main.gd").new();root.add_child(app);await process_frame
	await create_timer(0.4).timeout
	await app.authenticate(true,"http://127.0.0.1:8766","villageprop_"+str(Time.get_ticks_msec()),"Local-furniture-qa-password1","")
	for _i in 20:
		if app.screen=="village":break
		await create_timer(0.25).timeout
	if app.screen!="village":print("FAIL login screen=",app.screen);quit(1);return
	var queued: Dictionary=await app.api.post("/v1/studio/jobs",app.api.mutation({"prompt":"flower lamp","geometry":"proxy","designer":"fixture"}))
	if not queued.ok:quit(1);return
	var id := ""
	for _i in 30:
		var job: Dictionary=await app.api.request("/v1/studio/jobs/"+queued.data.id)
		if job.ok and job.data.state=="ready":id=job.data.object_id;break
		await create_timer(1).timeout
	check(not id.is_empty(),"fixture assembly created")
	if id.is_empty():quit(1);return
	await app.refresh_inventory()
	for i in app.me.objects.size():
		if app.me.objects[i].id==id:app.select_object(i);break
	await create_timer(1).timeout
	await app.paint_object("#a8bcad")
	check(app.inspect_model.colors.size()==8,"village paint covers all eight parts")
	await app.begin_place();app.preview.position=preload("res://scripts/town.gd").furniture_point(4,3);await app.place_preview()
	check(app.loaded.has(id) and app.loaded[id].pivots.size()==8,"full assembly placed in village")
	app.player.position=preload("res://scripts/town.gd").furniture_point(4,4.6);await app.village_furniture_proximity();await create_timer(1).timeout
	check(app.loaded[id].nearby,"village proximity event authorized")
	var before: Dictionary=app.loaded[id].vm.state.duplicate()
	await app.village_furniture_event(id,"click")
	check(app.loaded[id].vm.state!=before,"village click changes generated state")
	app.player.position=preload("res://scripts/town.gd").furniture_point(8,4);await app.village_furniture_proximity()
	check(not app.loaded[id].nearby,"village leave event authorized")
	await app.refresh_inventory();await create_timer(.5).timeout
	check(app.loaded[id].colors.size()==8 and app.loaded[id].colors.values()[0]=="#a8bcad","part paint survives village reload")
	var result: Dictionary=await app.api.request("/v1/objects/"+id+"/assembly")
	check(result.ok and result.data.runtime.colors.size()==8,"server owns persisted paint")
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png("res://../artifacts/village-furniture.png")
	print("VILLAGE_FURNITURE ",JSON.stringify({"ok":failures.is_empty(),"failures":failures}))
	quit(0 if failures.is_empty() else 1)
