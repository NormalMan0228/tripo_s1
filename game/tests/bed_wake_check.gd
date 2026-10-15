extends SceneTree
## A new session's home opens in the attic bed (bed_wake.gd): lying under the card, the eyes open,
## the walker gets up the driver's way, no frame jumps, and the home works as before afterwards.
## Captures (--capture): artifacts/bed_wake_{shut,half,open,up}.png.
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
	var login: Dictionary=await api.post("/v1/auth/register",{"username":"wake_"+str(Time.get_ticks_usec()),"password":"Local-wake-qa-password"})
	check(login.ok,"login")
	if not login.ok:quit(1);return
	Engine.set_meta("studio_session",{"token":login.data.token,"url":api.base_url,"room":"home","wake":true})
	change_scene_to_file("res://scenes/studio.tscn")
	var veil=load("res://scripts/transition.gd")
	var deadline:=Time.get_ticks_msec()+60000
	while Time.get_ticks_msec()<deadline and not (is_instance_valid(current_scene) and current_scene.get("hero")!=null and is_instance_valid(current_scene.bed_wake) and is_instance_valid(current_scene.bed_wake.lids)):await process_frame
	var home=current_scene
	check(is_instance_valid(home.bed_wake),"wake-up started")
	check(home.floor_index==1,"wakes in the attic (floor %d)"%home.floor_index)
	# Wait for the card to lift.
	while Time.get_ticks_msec()<deadline and veil.instance.veil.modulate.a>0.02:await process_frame
	check(home.resting=="lie","lying in bed as the card lifts (%s)"%home.resting)
	await capture("bed_wake_shut.png")
	var start:=Time.get_ticks_msec()
	var last: Vector3=home.hero.global_position
	var max_step:=0.0
	var shots:={"bed_wake_half.png":900,"bed_wake_open.png":1900,"bed_wake_up.png":3600}
	while Time.get_ticks_msec()-start<4200:
		await process_frame
		var at: Vector3=home.hero.global_position
		max_step=maxf(max_step,at.distance_to(last));last=at
		for shot in shots.keys():
			if Time.get_ticks_msec()-start>=int(shots[shot]):shots.erase(shot);await capture(shot)
	check(max_step<0.25,"no jump while getting up (max %.3f m/frame)"%max_step)
	check(home.resting=="","up out of bed (%s)"%home.resting)
	check(not is_instance_valid(home.bed_wake),"wake-up done")
	check(home.walk_allowed(),"walking allowed after waking")
	print("BED_WAKE ",JSON.stringify({"ok":failures.is_empty(),"failures":failures,"max_step":max_step}))
	quit(0 if failures.is_empty() else 1)
