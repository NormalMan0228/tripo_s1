extends SceneTree
var failures: Array[String]=[]
func check(value: bool, message: String) -> void:
	if not value:failures.append(message);printerr(message)
func _initialize() -> void:call_deferred("run")
func capture(path: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args():return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://../artifacts/"+path)
func run() -> void:
	var api=load("res://scripts/api.gd").new();root.add_child(api);api.base_url="http://127.0.0.1:8766"
	var login: Dictionary=await api.post("/v1/auth/login",{"username":"workshop","password":"tripothon-local-demo"})
	check(login.ok,"login")
	if not login.ok:quit(1);return
	Engine.set_meta("studio_session",{"token":login.data.token,"url":api.base_url,"room":"home"})
	change_scene_to_file("res://scenes/main.tscn")
	await create_timer(4).timeout
	var village=current_scene
	check(village.screen=="village","village loaded")
	check(village.player.position.distance_to(load("res://scripts/town.gd").HOME_RETURN)<0.5,"home doorstep return position")
	await capture("home-exterior.png")
	village.open_studio("home")
	await create_timer(3).timeout
	var home=current_scene
	check(home.room=="home","entered home interior")
	check(home.placed.is_empty(),"workshop furniture does not leak into home")
	check(not home.placement_problem(Vector3(0,0,4)).is_empty(),"door placement preview rejects obstruction")
	await capture("home-interior.png")
	home.leave()
	await create_timer(4).timeout
	check(current_scene.screen=="village","returned village")
	check(current_scene.player.position.distance_to(load("res://scripts/town.gd").HOME_RETURN)<0.5,"return to same door")
	print("HOME_ROUNDTRIP ",JSON.stringify({"ok":failures.is_empty(),"failures":failures}))
	quit(0 if failures.is_empty() else 1)
