extends SceneTree
## Real wall-clock play through the actual client, without setting HP, time or position.
const Main = preload("res://scripts/main.gd")
var app: Node3D
var failed := false
var route := PackedVector2Array()
var resource_id := ""
var destination := Vector2.ZERO

func _initialize() -> void: call_deferred("play")

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed=true

func capture(name: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	await RenderingServer.frame_post_draw
	var path := ProjectSettings.globalize_path("res://../artifacts/"+name+".png")
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--artifacts="): path=argument.trim_prefix("--artifacts=").path_join(name+".png")
	if root.get_texture().get_image().save_png(path)!=OK:
		failed=true
		push_error("Could not save playthrough evidence: "+name)

func steer(target: Vector2) -> void:
	for key in ["move_left","move_right","move_forward","move_back"]: Input.action_release(key)
	var offset := target-Vector2(app.run.x,app.run.z)
	if absf(offset.x)>0.22: Input.action_press("move_right" if offset.x>0 else "move_left")
	if absf(offset.y)>0.22: Input.action_press("move_back" if offset.y>0 else "move_forward")

func plan_resource(kind: String) -> void:
	var grid := AStarGrid2D.new()
	grid.region=Rect2i(-18,-18,37,37)
	grid.diagonal_mode=AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	grid.update()
	for p in [Vector2i.ZERO,Vector2i(1,0),Vector2i(-1,0),Vector2i(0,1),Vector2i(0,-1)]: grid.set_point_solid(p)
	for n in app.run.nodes:
		if n.quantity<=0 or n.kind not in ["tree","stone"]: continue
		for x in range(maxi(-18,int(n.x)-2),mini(19,int(n.x)+3)):
			for z in range(maxi(-18,int(n.z)-2),mini(19,int(n.z)+3)):
				if Vector2(x-n.x,z-n.z).length()<1.1: grid.set_point_solid(Vector2i(x,z))
	for obstacle in app.run.get("obstacles",[])+app.run.get("hazards",[]):
		for x in range(-18,19):
			for z in range(-18,19):
				if Vector2(x-obstacle.x,z-obstacle.z).length()<obstacle.radius+0.7: grid.set_point_solid(Vector2i(x,z))
	var from := Vector2i(roundi(app.run.x),roundi(app.run.z))
	grid.set_point_solid(from,false)
	var best := INF
	resource_id=""
	route=PackedVector2Array()
	if kind.is_empty():
		route=grid.get_point_path(from,Vector2i(0,2))
		resource_id="camp"
		destination=Vector2(0,2)
		return
	for n in app.run.nodes:
		if n.kind!=kind or n.quantity<=0: continue
		for i in 8:
			var at := Vector2i(roundi(n.x+cos(i*TAU/8)*1.7),roundi(n.z+sin(i*TAU/8)*1.7))
			if not grid.is_in_boundsv(at) or grid.is_point_solid(at): continue
			if Vector2(at).distance_to(Vector2(n.x,n.z))>2.2: continue
			var candidate := grid.get_point_path(from,at)
			if not candidate.is_empty() and candidate.size()<best:
				best=candidate.size()
				route=candidate
				resource_id=n.id
				destination=Vector2(at)

func follow_route() -> void:
	var here := Vector2(app.run.x,app.run.z)
	while route.size()>0 and here.distance_to(route[0])<0.4: route.remove_at(0)
	steer(route[0] if route.size()>0 else destination)

func play() -> void:
	app=Main.new()
	root.add_child(app)
	await process_frame
	var user := "survival_"+str(Time.get_ticks_usec())
	var register := true
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--account="):user=argument.trim_prefix("--account=");register=false
	await app.authenticate(register,"http://127.0.0.1:8766",user,"local-survival-test-123","")
	expect(app.screen=="village","full-run account created through game")
	if app.screen!="village": quit(1); return
	var wallet_before: int=app.me.shards
	var completed_chapters: Array=[]
	for entry in app.me.get("campaign",[]):
		if entry.completed:completed_chapters.append(entry.id)
	var region := "forest"
	var difficulty := "standard"
	var chapter := ""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--region="): region=argument.trim_prefix("--region=")
		if argument.begins_with("--difficulty="): difficulty=argument.trim_prefix("--difficulty=")
		if argument.begins_with("--chapter="): chapter=argument.trim_prefix("--chapter=")
	var started := Time.get_ticks_msec()
	await app.start_run(region,difficulty,chapter)
	var recorded_day := 0
	var night_captured := false
	while app.run.status=="active" and Time.get_ticks_msec()-started<520000:
		await create_timer(0.1).timeout
		var state: Dictionary=app.run
		var inv: Dictionary=state.inventory
		var phase := fmod(float(state.elapsed),60)
		# Gather while safe; stay near the fire after dusk. Every action uses public inputs.
		var wanted := ""
		if not state.night and phase<30:
			if inv.wood<12: wanted="tree"
			elif inv.berry<6: wanted="berry"
			elif inv.stone<4 and (inv.axe==0 or inv.spear==0): wanted="stone"
		var target_valid := false
		for n in state.nodes:
			if n.id==resource_id and n.kind==wanted and n.quantity>0: target_valid=true
		if not wanted.is_empty():
			if not target_valid: plan_resource(wanted)
			follow_route()
		else:
			if resource_id!="camp": plan_resource("")
			follow_route()
		if state.hunger<65 and (inv.berry>0 or inv.soup>0): app.intent("eat")
		elif phase>37 and state.fire_remaining<2 and inv.wood>=2 and Vector2(state.x,state.z).length()<3: app.intent("fire")
		elif resource_id not in ["","camp"] and Vector2(state.x,state.z).distance_to(destination)<0.4: app.intent("harvest",resource_id)
		elif not state.night and inv.axe==0 and inv.wood>=7 and inv.stone>=2: app.intent("craft","axe")
		elif not state.night and inv.spear==0 and inv.wood>=8 and inv.stone>=2: app.intent("craft","spear")
		elif chapter=="returning_light" and not state.night and state.get("crafted",{}).get("soup",0)<2 and inv.wood>=7 and inv.berry>=3:app.intent("craft","soup")
		if int(state.day)!=recorded_day:
			recorded_day=int(state.day)
			print("DAY ",recorded_day," elapsed=",int(state.elapsed)," hp=",int(state.hp)," wood=",inv.wood," food=",inv.berry)
			await capture("full-run-day-"+str(recorded_day))
		if state.night and state.day==7 and not night_captured:
			night_captured=true
			await capture("full-run-seventh-night")
	steer(Vector2(app.run.x,app.run.z))
	var real_seconds := (Time.get_ticks_msec()-started)*0.001
	expect(app.run.status=="won" and app.run.elapsed>=420,"all seven days completed without clock shortcuts")
	expect(real_seconds>=420,"420+ real seconds elapsed")
	expect(app.run.inventory.axe==1 and app.run.inventory.spear==1,"tools crafted from collected resources")
	expect(app.run.harvested>=14,"supplies gathered during actual play")
	if not chapter.is_empty():expect(app.run.story.objectives_met and (app.run.story_bonus==0 if chapter in completed_chapters else app.run.story_bonus>0),"story objectives met through real play; bonus only on first completion")
	var reward: int=app.run.get("reward",0)
	var run_id: String=app.run_id
	await capture("full-run-victory")
	await app.leave_run()
	expect(reward>=35 and app.screen=="village" and app.me.shards==wallet_before+reward,"survival reward received in village")
	if not chapter.is_empty():
		for entry in app.me.campaign:
			if entry.id==chapter:expect(entry.completed,"story completion persisted in journal")
	var duplicate: Dictionary=await app.api.post("/v1/runs/"+run_id+"/claim",app.api.mutation())
	expect(not duplicate.ok and duplicate.error=="reward_already_claimed","second reward claim rejected")
	await capture("full-run-home")
	print("SEVEN_DAYS_COMPLETE real_seconds=",real_seconds," reward=",reward)
	await app.logout()
	app.queue_free()
	await process_frame
	await process_frame
	quit(1 if failed else 0)
