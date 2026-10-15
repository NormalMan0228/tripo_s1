extends SceneTree
## The room's front door (room_door.gd): shut while nobody passes; the walker steps in through the
## open door as the card lifts and it shuts behind; walking out opens it again. No frame jumps.
## Captures (--capture): artifacts/room_door_{in,shut,out}.png.
var failures: Array[String]=[]
func check(value: bool, message: String) -> void:
	if not value:failures.append(message);printerr(message)
func _initialize() -> void:call_deferred("run")
func capture(path: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args():return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://../artifacts/"+path)
func run() -> void:
	var api=load("res://scripts/api.gd").new();root.add_child(api);api.base_url=preload("res://tests/qa_server.gd").url()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="):api.base_url=arg.trim_prefix("--server=")
	var login: Dictionary=await api.post("/v1/auth/register",{"username":"door_"+str(Time.get_ticks_usec()),"password":"Local-door-qa-password"})
	check(login.ok,"login")
	if not login.ok:quit(1);return
	Engine.set_meta("studio_session",{"token":login.data.token,"url":api.base_url,"room":"home"})
	# The welcome letter keeps the door shut until it is opened (off by default in test runs).
	Engine.set_meta("qa_letter_first",true)
	change_scene_to_file("res://scenes/studio.tscn")
	var veil=load("res://scripts/transition.gd")
	var deadline:=Time.get_ticks_msec()+60000
	while Time.get_ticks_msec()<deadline and not (is_instance_valid(current_scene) and current_scene.get("front_door")!=null and is_instance_valid(current_scene.front_door) and current_scene.front_door.steer!=null):await process_frame
	var home=current_scene
	var door=home.front_door
	check(is_instance_valid(door) and is_instance_valid(door.hinge),"front door bound")
	if not is_instance_valid(door):quit(1);return
	check(door.opened,"door open as the walker comes in")
	var start:=Time.get_ticks_msec()
	var last: Vector3=home.hero.global_position
	var last_us:=Time.get_ticks_usec()
	var prev_dt:=0.001
	var max_step:=0.0
	var max_speed:=0.0
	var walking:=0
	var shot:=false
	while Time.get_ticks_msec()-start<2600:
		await process_frame
		var at: Vector3=home.hero.global_position
		var moved: float=at.distance_to(last);last=at
		# Per frame and as a speed: a slow frame on a busy PC moves further, a teleport is fast.
		# The walk of a frame uses that frame's delta, measured here one frame later: judge it by the
		# longer of the two frame times, so a slow frame on a busy PC is no teleport.
		var dt:=maxf((Time.get_ticks_usec()-last_us)/1000000.0,0.001);last_us=Time.get_ticks_usec()
		max_step=maxf(max_step,moved);max_speed=maxf(max_speed,moved/maxf(dt,prev_dt));prev_dt=dt
		if door.steer!=null: walking+=1
		if not shot and veil.instance.veil.modulate.a<0.05 and door.steer!=null:shot=true;await capture("room_door_in.png")
	check(walking>10,"walked in over frames (%d)"%walking)
	# Walking pace is 2.3 m/s (room_door.gd PACE): a teleport shows as a far higher speed.
	# room_door.gd counts a frame as at most 0.05 s: 2.3 m/s x 0.05 = 0.115 m is the most one frame moves.
	check(max_step<0.13,"no jump walking in (max %.3f m/frame, %.2f m/s)"%[max_step,max_speed])
	check(home.hero.position.distance_to(load("res://scripts/interiors.gd").spawn_point(home.room_spec))<0.1,"stands at the spawn spot")
	check(not door.opened and door.amount<0.02,"door shut behind (%.2f open)"%door.amount)
	await capture("room_door_shut.png")
	# The welcome letter is unread: the door stays shut (story_home.gd hold_at_door).
	check(is_instance_valid(home.story_home) and home.story_home.keeps_door_shut(),"the unread letter keeps the door shut")
	if is_instance_valid(home.story_home) and home.story_home.keeps_door_shut():
		home.leave()
		await create_timer(0.3).timeout
		check(not door.opened and not home.leaving,"door stays shut until the letter is read")
		# Opening the letter lets the walker out even when the server could not save it.
		home.story_home.letter_seen=true
	home.leave()
	await create_timer(0.3).timeout
	check(door.opened,"door opens to walk out")
	await capture("room_door_out.png")
	await create_timer(3.5).timeout
	check(current_scene!=home,"left the room")
	print("ROOM_DOOR ",JSON.stringify({"ok":failures.is_empty(),"failures":failures,"max_step":max_step,"max_speed":max_speed}))
	quit(0 if failures.is_empty() else 1)
