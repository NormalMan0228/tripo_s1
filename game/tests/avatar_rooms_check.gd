extends SceneTree
## The look chosen in the wardrobe (/v1/profile) is the one the walker wears in the village, at home
## and back in the village, and no other character appears.
const Main = preload("res://scripts/main.gd")
var failures: Array[String] = []
var server := "http://127.0.0.1:8766"

func check(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func _initialize() -> void:
	call_deferred("run")

func capture(name: String) -> void:
	if DisplayServer.get_name() == "headless": return
	for i in 8: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/avatar-" + name + ".png"))

func describe(walker: Node) -> String:
	if not is_instance_valid(walker): return "none"
	var kids := []
	for child in walker.visual.get_children(): kids.append(child.get_class() + ":" + str(child.name))
	return "%s %s" % [JSON.stringify(walker.avatar), kids]

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	var app: Node = Main.new()
	root.add_child(app)
	await create_timer(0.4).timeout
	await app.authenticate(true, server, "look_" + str(Time.get_ticks_msec()), "Local-look-qa-password1", "")
	for _i in 20:
		if app.screen == "village": break
		await create_timer(0.25).timeout
	var look := {"character": "ranger", "hair": "#8a3b2a", "coat": "#2f5f9e", "pants": "#3b3b3b", "boots": "#5a3a22", "skin": "#bc865c", "headwear": "cap", "backpack": false}
	var saved: Dictionary = await app.api.post("/v1/profile", app.api.mutation({"version": app.me.get("profile", {}).get("version", 0), "avatar": look}))
	check(saved.ok, "wardrobe look saved")
	await app.refresh_inventory()
	await create_timer(0.5).timeout
	print("VILLAGE ", describe(app.player))
	check(app.player.avatar.get("character") == "ranger" and app.player.avatar.get("coat") == "#2f5f9e", "village walker wears the saved look")
	await capture("village")
	# Home, the way the game opens it.
	# The session main.open_studio hands to the room scene (it carries the saved look).
	Engine.set_meta("studio_session", {"token": app.api.token, "url": app.api.base_url, "room": "home", "avatar": app.me.profile.avatar.duplicate(true)})
	app.queue_free()
	await process_frame
	var studio: Node = load("res://scenes/studio.tscn").instantiate()
	root.add_child(studio)
	var seen := []
	for i in 30:
		if i > 0: await create_timer(0.2).timeout
		if is_instance_valid(studio.hero):
			var now := describe(studio.hero)
			if seen.is_empty() or seen[-1] != now: seen.append(now)
	print("HOME ", seen)
	check(seen.size() == 1 and str(seen[0]).contains("ranger"), "the home walker never shows another look first")
	check(is_instance_valid(studio.hero) and studio.hero.avatar.get("character") == "ranger" and studio.hero.avatar.get("coat") == "#2f5f9e", "home walker wears the saved look")
	await capture("home")
	# A refresh at home (every 20 s in play) must not change the look.
	await studio.refresh()
	await create_timer(0.5).timeout
	check(studio.hero.avatar.get("character") == "ranger", "a home refresh keeps the look (%s)" % describe(studio.hero))
	studio.queue_free()
	await process_frame
	print("AVATAR_ROOMS " + ("FAILED" if failures else "OK"))
	quit(1 if failures else 0)
