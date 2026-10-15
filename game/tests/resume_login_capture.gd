extends SceneTree
## Signing in through the title (main.gd authenticate) with the server's resume (server/last_spot.py):
##  1. a player who left from their own village soon after comes back on that spot, facing the same
##     way, in the village (no home, no bed);
##  2. a first sign-in wakes up in the attic bed.
## Captures (--capture): artifacts/resume_village.png, artifacts/resume_wake.png.
var failures: Array[String]=[]
func check(value: bool, message: String) -> void:
	if not value:failures.append(message);printerr(message)
func _initialize() -> void:call_deferred("run")
func capture(path: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args():return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://../artifacts/"+path)
func title() -> Node:
	change_scene_to_file("res://scenes/main.tscn")
	var deadline:=Time.get_ticks_msec()+60000
	while Time.get_ticks_msec()<deadline and not (is_instance_valid(current_scene) and current_scene.get("screen")=="login" and current_scene.get("title_page")=="menu"):await process_frame
	return current_scene
func settled(wanted: String) -> void:
	var veil=load("res://scripts/transition.gd")
	var deadline:=Time.get_ticks_msec()+60000
	while Time.get_ticks_msec()<deadline:
		await process_frame
		if not is_instance_valid(current_scene) or veil.instance.veil.modulate.a>0.02:continue
		if wanted=="village" and current_scene.get("screen")=="village":return
		if wanted=="home" and current_scene.get("room")=="home" and current_scene.get("hero")!=null:return
func run() -> void:
	var url:String=preload("res://tests/qa_server.gd").url()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="):url=arg.trim_prefix("--server=")
	var api=load("res://scripts/api.gd").new();root.add_child(api);api.base_url=url
	var Town=load("res://scripts/town.gd")
	# 1. A player last seen in their own village, a moment ago.
	var name:="back_"+str(Time.get_ticks_usec())
	var reg: Dictionary=await api.post("/v1/auth/register",{"username":name,"password":"Local-back-qa-password"})
	check(reg.ok,"register")
	if not reg.ok:quit(1);return
	api.token=reg.data.token
	var door: Vector3=Town.door_return("home")
	var spot:=Vector3(door.x-1.5,0,door.z+3.0)
	spot.y=Town.height_at(spot.x,spot.z)
	var seen: Dictionary=await api.post("/v1/social/presence",{"scene":"village","x":spot.x,"z":spot.z,"y":spot.y,"yaw":0.8})
	check(seen.ok,"presence in the own village")
	await api.post("/v1/social/offline",{})
	var main:=await title()
	main.authenticate(false,url,name,"Local-back-qa-password","")
	await settled("village")
	main=current_scene
	check(main.get("screen")=="village","signed in to the village, not the home")
	if main.get("screen")=="village":
		check(Vector2(main.player.position.x-spot.x,main.player.position.z-spot.z).length()<0.3,"back on the spot (%.2f m off)"%Vector2(main.player.position.x-spot.x,main.player.position.z-spot.z).length())
		await create_timer(0.6).timeout
		await capture("resume_village.png")
	# 2. A first sign-in: the attic bed.
	var fresh:="wake_"+str(Time.get_ticks_usec())
	var reg2: Dictionary=await api.post("/v1/auth/register",{"username":fresh,"password":"Local-wake-qa-password"})
	check(reg2.ok and reg2.data.get("resume")==null,"first sign-in has no resume")
	main=await title()
	main.authenticate(false,url,fresh,"Local-wake-qa-password","")
	await settled("home")
	var home=current_scene
	check(home.get("room")=="home","first sign-in opens the home")
	check(is_instance_valid(home.get("bed_wake")) and home.resting=="lie","wakes up in the attic bed")
	await create_timer(1.5).timeout
	await capture("resume_wake.png")
	print("RESUME_LOGIN ",JSON.stringify({"ok":failures.is_empty(),"failures":failures}))
	await create_timer(3.0).timeout
	quit(0 if failures.is_empty() else 1)
