extends SceneTree
## Select real map cards with a new account, before the optional tutorial is cleared.
const Main = preload("res://scripts/main.gd")
var app: Node
var failures := 0
var checks := 0
var server := "http://127.0.0.1:8766"

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, words: String) -> void:
	checks += 1
	print(("PASS " if ok else "FAIL ")+words)
	if not ok: failures += 1

func until_ready(screen: String) -> bool:
	for i in 900:
		var veil = preload("res://scripts/transition.gd").of(self)
		if app.screen==screen and not app.busy and veil.veil.mouse_filter==Control.MOUSE_FILTER_IGNORE: return true
		await create_timer(.1).timeout
	return false

func find_button(node: Node, words: String) -> Button:
	for child in node.get_children():
		if child is Button and child.text == words: return child
		var found := find_button(child,words)
		if found: return found
	return null

func click(button: Button) -> void:
	var at := button.get_global_transform_with_canvas()*(button.size*.5)
	var motion := InputEventMouseMotion.new()
	motion.position=at; motion.global_position=at
	root.push_input(motion,true)
	await process_frame
	for down in [true,false]:
		var event := InputEventMouseButton.new()
		event.position=at; event.global_position=at
		event.button_index=MOUSE_BUTTON_LEFT; event.pressed=down
		root.push_input(event,true)
		await process_frame
	await create_timer(.3).timeout

func capture(name: String) -> void:
	if DisplayServer.get_name()=="headless": return
	await RenderingServer.frame_post_draw
	var folder := ProjectSettings.globalize_path("res://../artifacts")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--artifacts="): folder=arg.trim_prefix("--artifacts=")
	check(root.get_texture().get_image().save_png(folder.path_join("map-selection-"+name+".png"))==OK,"capture "+name)

func selected_map(expected: String) -> void:
	check(await until_ready("survival"),"expedition loading completes: "+expected)
	check(str(app.run.get("map_id",""))==expected,"selected map reaches server run: "+expected)
	var snapshot: Dictionary = await app.api.request(app.run_route())
	check(snapshot.ok and str(snapshot.data.get("map_id",""))==expected,"server snapshot agrees: "+expected)
	var map = app.world.get_node_or_null("SurvivalMap")
	check(is_instance_valid(map) and str(map.state.get("map_id",""))==expected,"rendered map uses selected state: "+expected)
	if expected!="tutorial":
		check(is_instance_valid(map) and map.map_id==expected and not is_instance_valid(map.guide),"region appearance is not the tutorial: "+expected)
		check(str(app.run.get("difficulty",""))=="standard","selected difficulty remains: "+expected)
	else:
		check(is_instance_valid(map) and is_instance_valid(map.guide) and bool(app.run.get("tutorial",false)),"explicit tutorial keeps its guide")
	await capture(expected)

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server=arg.trim_prefix("--server=")
	preload("res://scripts/i18n.gd").remember("server",server)
	app=Main.new()
	root.add_child(app)
	check(await until_ready("login"),"title ready")
	await app.authenticate(true,server,"map_pick_"+str(Time.get_ticks_msec()),"Map-selection-qa123","")
	check(await until_ready("village"),"new account reaches village")
	check(not bool(app.me.get("tutorial_done",true)),"new account has not cleared tutorial")
	for wanted in ["forest","quarry","frost","tutorial"]:
		app.open_expedition()
		await create_timer(.4).timeout
		var card = app.village_modal.find_child("Map_"+wanted,true,false)
		check(is_instance_valid(card),"map card available: "+wanted)
		if not is_instance_valid(card): break
		await click(card)
		check(app.chosen_map==wanted,"map card records choice: "+wanted)
		await click(find_button(app.village_modal,"준비 완료 · 출발하기"))
		await selected_map(wanted)
		await app.leave_run()
		check(await until_ready("village"),"return from "+wanted)
		check(not bool(app.me.get("tutorial_done",true)),"leaving early does not fabricate tutorial completion")
	# A saved expedition resumes on its actual map/difficulty rather than the default forest.
	await app.start_run("frost","relaxed")
	check(await until_ready("survival"),"saved-run setup ready")
	var saved_id: String=app.run_id
	await app.suspend_run()
	check(await until_ready("village"),"saved expedition returns to village")
	check(app.me.get("active_run_summary") is Dictionary and app.me.active_run_summary.map_id=="frost","resume summary keeps actual map")
	app.open_expedition()
	check(await until_ready("survival"),"resume finishes loading")
	check(app.run_id==saved_id and app.run.map_id=="frost" and app.run.difficulty=="relaxed","resume keeps saved expedition map and difficulty")
	await app.leave_run()
	await until_ready("village")
	var chapters: Array=app.me.get("campaign",[])
	if not chapters.is_empty():
		var chapter: Dictionary=chapters[0]
		await app.start_run(chapter.map_id,"standard",chapter.id)
		check(await until_ready("survival"),"story expedition ready")
		check(app.run.get("chapter_id")==chapter.id and app.run.get("map_id")==chapter.map_id,"story selection retains chapter before tutorial clear")
	app.queue_free()
	await process_frame
	print("EXPEDITION_MAP_SELECTION_DONE checks=%d failures=%d" % [checks,failures])
	quit(1 if failures else 0)
