extends SceneTree
var failures: Array[String]=[]
func check(value: bool,message: String) -> void:
	if not value:failures.append(message);printerr(message)
func _initialize() -> void:call_deferred("run")
func run() -> void:
	var api=load("res://scripts/api.gd").new();root.add_child(api);api.base_url="http://127.0.0.1:8766"
	var login: Dictionary=await api.post("/v1/auth/login",{"username":"workshop","password":"tripothon-local-demo"})
	if not login.ok:quit(1);return
	Engine.set_meta("studio_session",{"token":login.data.token,"url":api.base_url,"room":"workshop"})
	var app=load("res://scenes/studio.tscn").instantiate();root.add_child(app)
	await create_timer(3).timeout
	for i in app.data.objects.size():
		if app.data.objects[i].name=="H3 열리는 상자 · 직접 색칠":await app.select_item(i);break
	check(is_instance_valid(app.inspected),"comparison selected")
	if not is_instance_valid(app.inspected):quit(1);return
	var original: Array=app.inspected.manifest.plan.parts[1].position.duplicate()
	app.binding_part.select(1);app.load_binding_fields(1)
	app.binding_fields.position[1].value=original[1]+.1
	await app.save_binding(false)
	check(absf(app.inspected.manifest.plan.parts[1].position[1]-original[1]-.1)<.001,"binding persisted and reloaded")
	await app.save_binding(true)
	check(app.inspected.manifest.plan.parts[1].position==original,"original binding restored")
	var tabs=app.find_children("*","TabContainer",true,false);tabs[0].current_tab=3
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png("res://../artifacts/studio-binding.png")
	print("STUDIO_BINDING ",JSON.stringify({"ok":failures.is_empty(),"failures":failures}))
	quit(0 if failures.is_empty() else 1)
