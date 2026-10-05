extends SceneTree
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var api=load("res://scripts/api.gd").new();root.add_child(api);api.base_url="http://127.0.0.1:8766"
	var response: Dictionary=await api.post("/v1/auth/login",{"username":"workshop","password":"Tripothon-local-demo"})
	if not response.ok:printerr("Review server not available");quit(1);return
	Engine.set_meta("studio_session",{"token":response.data.token,"url":api.base_url,"room":"workshop"})
	var studio=load("res://scenes/studio.tscn").instantiate();root.add_child(studio)
	await create_timer(6).timeout
	print("REVIEW_READY objects=",studio.data.get("objects",[]).size())
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://../artifacts/studio-review.png")
		quit()
