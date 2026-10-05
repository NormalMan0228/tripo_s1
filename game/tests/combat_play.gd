extends "res://tests/seven_days.gd"
## Public-input integration test: prepare a spear, wait for night, dodge, fight, return.

func gather(kind: String,item: String,amount: int) -> void:
	plan_resource(kind)
	var started := Time.get_ticks_msec()
	while app.run.inventory[item]<amount and Time.get_ticks_msec()-started<16000:
		follow_route()
		if Vector2(app.run.x,app.run.z).distance_to(destination)<0.4: app.intent("harvest")
		await create_timer(0.12).timeout
	steer(Vector2(app.run.x,app.run.z))

func key(code: Key, pressed: bool) -> void:
	var event := InputEventKey.new()
	event.physical_keycode=code
	event.pressed=pressed
	Input.parse_input_event(event)

func play() -> void:
	app=Main.new()
	root.add_child(app)
	await process_frame
	await app.authenticate(true,"http://127.0.0.1:8766","combat_"+str(Time.get_ticks_usec()),"Local-combat-test-123","")
	if app.screen!="village": quit(1); return
	var region := "forest"
	var difficulty := "standard"
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--region="): region=argument.trim_prefix("--region=")
		if argument.begins_with("--difficulty="): difficulty=argument.trim_prefix("--difficulty=")
	await app.start_run(region,difficulty)
	await gather("tree","wood",4)
	await gather("stone","stone",2)
	app.intent("craft","spear")
	for i in 20:
		await create_timer(0.1).timeout
		if app.run.inventory.spear==1: break
	expect(app.run.inventory.spear==1,"spear crafted from real harvested materials")
	plan_resource("")
	for i in 60:
		follow_route()
		await create_timer(0.1).timeout
		if Vector2(app.run.x,app.run.z).distance_to(destination)<0.4: break
	steer(Vector2(app.run.x,app.run.z))
	app.toggle_drawer()
	await capture("survival-bag")
	app.toggle_drawer()
	var limit := Time.get_ticks_msec()+70000
	var telegraph: Dictionary={}
	while telegraph.is_empty() and Time.get_ticks_msec()<limit and app.run.status=="active":
		await create_timer(0.05).timeout
		for enemy in app.run.enemies:
			if enemy.get("phase","")=="windup": telegraph=enemy.duplicate()
	expect(not telegraph.is_empty(),"real night enemy publishes a visible attack telegraph")
	if not telegraph.is_empty():
		await capture("combat-telegraph")
		var hp: float=app.run.hp
		var before := Vector2(app.run.x,app.run.z)
		# Run away from the central fire pit into the open southern lane.
		key(KEY_SHIFT,true)
		Input.action_press("move_back")
		await create_timer(0.8).timeout
		Input.action_release("move_back")
		key(KEY_SHIFT,false)
		expect(Vector2(app.run.x,app.run.z).distance_to(before)>1.4 and app.run.stamina<100,"Shift sprint moves using server stamina")
		expect(app.run.hp>hp-3,"leaving telegraph avoids enemy impact damage")
		await capture("combat-dodge")
		var deadline := Time.get_ticks_msec()+14000
		while app.run.kills<1 and Time.get_ticks_msec()<deadline and app.run.status=="active":
			app.intent("attack")
			await create_timer(0.75).timeout
		expect(app.run.kills>=1,"server-confirmed spear attacks defeat a night enemy")
		await capture("combat-victory")
	await app.leave_run()
	expect(app.screen=="village","combat expedition returns safely")
	await app.logout()
	app.queue_free()
	await process_frame
	await process_frame
	print("COMBAT_PLAY_COMPLETE")
	quit(1 if failed else 0)
