extends SceneTree
## Captures the walk out of the home and back in from the village camera (village_doors.gd with the
## map's cut door leaf when building_doors.gd has one for the home). Needs a window (--capture).
## Images: artifacts/village_walk_{out,in}_<n>.png. Prints VILLAGE_WALK_CAPTURE {...}.
func _initialize() -> void:call_deferred("run")
func capture(path: String) -> void:
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://../artifacts/"+path)
func run() -> void:
	var api=load("res://scripts/api.gd").new();root.add_child(api);api.base_url=preload("res://tests/qa_server.gd").url()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="):api.base_url=arg.trim_prefix("--server=")
	var login: Dictionary=await api.post("/v1/auth/register",{"username":"vwalk_"+str(Time.get_ticks_usec()),"password":"Local-vwalk-qa-password"})
	if not login.ok:quit(1);return
	Engine.set_meta("studio_session",{"token":login.data.token,"url":api.base_url,"room":"home"})
	change_scene_to_file("res://scenes/main.tscn")
	var veil=load("res://scripts/transition.gd")
	var Doors=load("res://scripts/village_doors.gd")
	var deadline:=Time.get_ticks_msec()+60000
	while Time.get_ticks_msec()<deadline and not (is_instance_valid(current_scene) and current_scene.get("screen")=="village"):await process_frame
	var leaf=load("res://maps/archipelago/building_doors.gd").door_leaf("10_red_house")
	var shots:=0
	var start:=Time.get_ticks_msec()
	while Time.get_ticks_msec()-start<4000 and shots<4:
		await create_timer(0.35).timeout
		if veil.instance.veil.modulate.a<0.3:await capture("village_walk_out_%d.png"%shots);shots+=1
	var village=current_scene
	village.open_studio("home")
	for i in 3:
		await create_timer(0.22).timeout
		await capture("village_walk_in_%d.png"%i)
	print("VILLAGE_WALK_CAPTURE ",JSON.stringify({"leaf":leaf!=null,"out":shots}))
	await create_timer(2.0).timeout
	quit(0)
