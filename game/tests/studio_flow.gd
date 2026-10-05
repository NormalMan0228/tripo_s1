extends SceneTree
var failures: Array[String]=[]
func check(value: bool, message: String) -> void:
	if not value:failures.append(message);printerr(message)
func _initialize() -> void:call_deferred("run")
func run() -> void:
	var api=load("res://scripts/api.gd").new();root.add_child(api);api.base_url="http://127.0.0.1:8766"
	var login: Dictionary=await api.post("/v1/auth/login",{"username":"workshop","password":"Tripothon-local-demo"})
	check(login.ok,"login")
	if not login.ok:quit(1);return
	Engine.set_meta("studio_session",{"token":login.data.token,"url":api.base_url,"room":"workshop"})
	var studio=load("res://scenes/studio.tscn").instantiate();root.add_child(studio)
	await create_timer(3).timeout
	check(studio.placed.size()==4,"four real generated comparison props loaded")
	for i in studio.data.objects.size():
		if "열리는 상자" in studio.data.objects[i].name and "텍스처" in studio.data.objects[i].name:
			await studio.select_item(i);break
	check(is_instance_valid(studio.inspected),"selected assembly")
	if is_instance_valid(studio.inspected):
		var before: float=studio.inspected.pivots.lid.rotation_degrees.x
		await studio.interact_selected();await create_timer(1.5).timeout
		check(absf(studio.inspected.pivots.lid.rotation_degrees.x-before)>50,"hinge moves on server-authorized click")
		await studio.paint("#789887")
		check(studio.inspected.colors.get("lid")=="#789887","paint applied")
		await studio.interact_selected();await create_timer(1).timeout
		print("ASSEMBLY_OK parts=",studio.inspected.pivots.size()," version=",studio.inspected.runtime_version)
	if is_instance_valid(studio.hero):
		print("CHARACTER_CLIPS ",studio.hero.animator.get_animation_list())
		check(studio.hero.animator.has_animation("movement/B_TrailWalk"),"authored walk retained")
		studio.set_process(false)
		studio.hero.set_walking(true);await create_timer(.5).timeout
		check(studio.hero.active=="movement/B_TrailWalk","walk playing")
		studio.hero.set_walking(false)
	var tabs=studio.find_children("*","TabContainer",true,false)
	if not tabs.is_empty():tabs[0].current_tab=1
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://../artifacts/studio-interaction.png")
	print("STUDIO_FLOW ",JSON.stringify({"ok":failures.is_empty(),"failures":failures}))
	quit(0 if failures.is_empty() else 1)
