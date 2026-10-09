extends SceneTree
## The title key art follows the player's clock: morning to afternoon, golden hour, night.
const Main = preload("res://scripts/main.gd")
var failures: Array[String] = []

func check(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	check(Main.title_art_for(9.0).ends_with("title_morning.jpg"), "09:00 shows the morning art")
	check(Main.title_art_for(14.5).ends_with("title_morning.jpg"), "14:30 shows the morning art")
	check(Main.title_art_for(17.0).ends_with("title_golden.jpg"), "17:00 shows the golden-hour art")
	check(Main.title_art_for(19.0).ends_with("title_golden.jpg"), "19:00 shows the golden-hour art")
	check(Main.title_art_for(21.0).ends_with("title_evening.jpg"), "21:00 shows the night art")
	check(Main.title_art_for(3.0).ends_with("title_evening.jpg"), "03:00 shows the night art")
	for path in ["res://assets/title_morning.jpg", "res://assets/title_golden.jpg", "res://assets/title_evening.jpg"]:
		check(load(path) is Texture2D, "%s loads" % path.get_file())
	var app: Node = Main.new()
	root.add_child(app)
	await create_timer(0.6).timeout
	for hour in [9.0, 18.0, 22.0]:
		app.daylight.override_hour = hour
		app.login_ui()
		for i in 8: await process_frame
		var shown: Array = app.ui.find_children("*", "TextureRect", true, false).filter(func(r) -> bool: return r.texture != null and r.texture.resource_path.begins_with("res://assets/title_"))
		check(shown.size() == 1 and shown[0].texture.resource_path == Main.title_art_for(hour), "the title shows %s at %02d:00" % [Main.title_art_for(hour).get_file(), int(hour)])
		if DisplayServer.get_name() != "headless":
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/title-%02d.png" % int(hour)))
	app.queue_free()
	for i in 4: await process_frame
	print("TITLE_ART " + ("FAILED" if failures else "OK"))
	quit(1 if failures else 0)
