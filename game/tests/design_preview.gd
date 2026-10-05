extends SceneTree
var failures: Array[String]=[]
func check(value: bool,message: String) -> void:
	if not value:failures.append(message);printerr(message)
func _initialize() -> void:call_deferred("run")
func run() -> void:
	var api=load("res://scripts/api.gd").new();root.add_child(api);api.base_url="http://127.0.0.1:8766"
	var account := "preview"+str(Time.get_ticks_msec())
	var login: Dictionary=await api.post("/v1/auth/register",{"username":account,"password":"Private-local-test"})
	if not login.ok:quit(1);return
	api.token=login.data.token
	for prompt in ["wooden chest","flower"]:
		var queued: Dictionary=await api.post("/v1/studio/jobs",api.mutation({"prompt":prompt}))
		if not queued.ok:quit(1);return
		var job: String=queued.data.id
		for attempt in 50:
			var status: Dictionary=await api.request("/v1/studio/jobs/"+job)
			if status.ok and status.data.state=="ready":break
			await create_timer(.15).timeout
		var response: Dictionary=await api.request("/v1/studio/jobs/"+job+"/preview")
		check(response.ok,"private plan preview fetched")
		if not response.ok:quit(1);return
		var window=load("res://scripts/design_preview.gd").new();root.add_child(window)
		check(window.show_plan(response.data),"preview mesh assembled")
		window.popup_centered();window.simulate("click")
		await create_timer(.7).timeout
		check(window.item.healthy,"bounded preview simulation healthy")
		check(window.item.vm.state.get("open",0)==1,"click opens preview")
		window.rebuild();window.simulate("near")
		await create_timer(.5).timeout
		window.simulate("leave")
		check(window.item.healthy,"near and leave healthy")
		if "--capture" in OS.get_cmdline_user_args():
			await RenderingServer.frame_post_draw
			window.get_texture().get_image().save_png("res://../artifacts/design-preview-"+("chest" if prompt.contains("chest") else "flower")+".png")
		window.queue_free();await process_frame
	print("DESIGN_PREVIEW ",JSON.stringify({"ok":failures.is_empty(),"failures":failures}))
	quit(0 if failures.is_empty() else 1)
