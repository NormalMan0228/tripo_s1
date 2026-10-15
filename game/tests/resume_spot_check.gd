extends SceneTree
## Signing in again onto the last spot in the own village (bed_wake.gd resume_spot, item 55): an open
## spot is kept with its facing; a spot that is no longer open ground falls back to the home door.
var failures: Array[String]=[]
func check(value: bool, message: String) -> void:
	if not value:failures.append(message);printerr(message)
func _initialize() -> void:call_deferred("run")
func run() -> void:
	var api=load("res://scripts/api.gd").new();root.add_child(api);api.base_url=preload("res://tests/qa_server.gd").url()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="):api.base_url=arg.trim_prefix("--server=")
	var login: Dictionary=await api.post("/v1/auth/register",{"username":"resume_"+str(Time.get_ticks_usec()),"password":"Local-resume-qa-password"})
	check(login.ok,"login")
	if not login.ok:quit(1);return
	check(login.data.has("resume"),"sign-in carries resume")
	check(login.data.get("resume")==null,"first sign-in: no resume (wakes in bed)")
	Engine.set_meta("studio_session",{"token":login.data.token,"url":api.base_url,"room":"home"})
	change_scene_to_file("res://scenes/main.tscn")
	var deadline:=Time.get_ticks_msec()+60000
	while Time.get_ticks_msec()<deadline and not (is_instance_valid(current_scene) and current_scene.get("screen")=="village" and is_zero_approx(load("res://scripts/transition.gd").instance.veil.modulate.a)):await process_frame
	var village=current_scene
	var Town=load("res://scripts/town.gd")
	var BedWake=load("res://scripts/bed_wake.gd")
	var door: Vector3=Town.door_return("home")
	var open: Vector3=door+Vector3(2.0,0,1.5)
	var ground: Vector3=BedWake.ground_at(village.player,open)
	check(ground!=Vector3.INF,"open ground near the home door")
	BedWake.resume_spot(village,{"scene":"village","x":open.x,"y":ground.y,"z":open.z,"yaw":1.0})
	check(Vector2(village.player.position.x-open.x,village.player.position.z-open.z).length()<0.05,"kept the open spot")
	check(village.player.facing.distance_to(Vector3(-sin(1.0),0,-cos(1.0)))<0.01,"kept the facing")
	BedWake.resume_spot(village,{"scene":"village","x":open.x,"y":ground.y+40.0,"z":open.z,"yaw":0.0})
	check(village.player.position.distance_to(door)<0.05,"a spot in the air falls back to the home door")
	print("RESUME_SPOT ",JSON.stringify({"ok":failures.is_empty(),"failures":failures}))
	quit(0 if failures.is_empty() else 1)
