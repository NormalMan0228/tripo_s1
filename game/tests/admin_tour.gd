extends SceneTree
## Logs in with an operator account (--user, --password) and captures the admin
## hotbar slot, the F9 window and a teleport. It grants nothing.
const Main = preload("res://scripts/main.gd")
const Town = preload("res://scripts/town.gd")
func _initialize() -> void: call_deferred("run")
func shot(name: String) -> void:
	for i in 8: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/admin-"+name+".png"))
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
	await create_timer(2).timeout
	print("ADMIN ",preload("res://scripts/build_mode.gd").admin," screen=",app.screen," shards=",app.me.get("shards")," role=",app.me.get("role"))
	await shot("village")
	app.open_admin()
	await shot("window")
	app.close_village_modal()
	app.player.position = Town.point(Town.GATE+Vector2(0,1.2),.3)
	app.camera_focus_ready = false
	await create_timer(1).timeout
	print("TELEPORT ",app.near(Town.GATE,3))
	await shot("teleport")
	quit()
