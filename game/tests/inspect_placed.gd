extends SceneTree
## Logs in as --user and frames each placed village object for a capture.
const Main = preload("res://scripts/main.gd")
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var user := ""
	var password := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--user="): user = arg.trim_prefix("--user=")
		if arg.begins_with("--password="): password = arg.trim_prefix("--password=")
	var app = Main.new()
	root.add_child(app)
	await create_timer(1.5).timeout
	await app.authenticate(false,"http://127.0.0.1:8765",user,password,"")
	await create_timer(4).timeout
	for id in app.loaded:
		var node: Node3D = app.loaded[id]
		print("PLACED ",id," at=",node.global_position," size=",node.get_meta("size",Vector3.ZERO))
		app.player.position = node.global_position+Vector3(-1.8,0.3,1.8)
		await create_timer(1.5).timeout
		app.camera.size = 6.5
		await create_timer(.3).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/placed-"+id.left(8)+".png"))
	quit()
