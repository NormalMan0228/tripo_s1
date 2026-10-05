extends SceneTree
var failures: Array[String]=[]
func check(value: bool,message: String) -> void:
	if not value:failures.append(message);printerr(message)
func _initialize() -> void:call_deferred("run")
func run() -> void:
	var app=load("res://scripts/main.gd").new();root.add_child(app);await process_frame
	await app.authenticate(true,"http://127.0.0.1:8766","journal"+str(Time.get_ticks_usec()),"Local-journal-test","")
	check(app.screen=="village","journal account loaded")
	app.open_story();await process_frame
	for button in app.village_modal.find_children("*","Button",true,false):
		if button.text.begins_with("2장"):button.pressed.emit()
	for button in app.village_modal.find_children("*","Button",true,false):
		if button.text=="이야기 시작":check(button.disabled,"locked chapter cannot start from UI")
	for button in app.village_modal.find_children("*","Button",true,false):
		if button.text.begins_with("1장"):button.pressed.emit()
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png("res://../artifacts/story-journal.png")
	for button in app.village_modal.find_children("*","Button",true,false):
		if button.text=="이야기 시작":check(not button.disabled,"first chapter available");button.pressed.emit();break
	for attempt in 50:
		if app.screen=="survival":break
		await create_timer(.1).timeout
	check(app.screen=="survival" and app.run.get("chapter_id")=="first_fire","actual chapter started from UI")
	await create_timer(.4).timeout
	check(app.objective.text.contains("모닥불 피우기"),"authoritative progress shown on survival HUD")
	await app.leave_run()
	check(not app.me.campaign[0].completed and not app.me.campaign[1].unlocked,"abandoning cannot unlock next chapter")
	print("STORY_JOURNAL ",JSON.stringify({"ok":failures.is_empty(),"failures":failures}))
	await app.logout();quit(0 if failures.is_empty() else 1)
