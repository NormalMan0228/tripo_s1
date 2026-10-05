extends SceneTree
## Focused release check, against an isolated fixture server on loopback only.
## Paid generation stays disabled. Quote/results states below are UI-only previews.
const Main = preload("res://scripts/main.gd")
const I18n = preload("res://scripts/i18n.gd")
const Town = preload("res://scripts/town.gd")
var failed := false
var app: Node3D
var korean := RegEx.new()

func _initialize() -> void:
	call_deferred("run")
	create_timer(180).timeout.connect(func(): quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	failed = failed or not value

func settled() -> void:
	for i in 3: await process_frame

func capture(name: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	await settled()
	await RenderingServer.frame_post_draw
	var folder := ProjectSettings.globalize_path("res://../artifacts")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--artifacts="): folder=arg.trim_prefix("--artifacts=")
	if root.get_texture().get_image().save_png(folder.path_join("stage1-"+name+".png"))!=OK: failed=true

func visible_text(node: Node) -> String:
	var value := ""
	if node is Control and not node.is_visible_in_tree(): return value
	if node is Label or node is Button:
		value = node.text if node.auto_translate_mode==Node.AUTO_TRANSLATE_MODE_DISABLED else node.tr(node.text)
	for child in node.get_children(): value+="\n"+visible_text(child)
	return value

func language_ok(node: Node, code: String) -> bool:
	var value := visible_text(node)
	return korean.search(value)==null if code=="en" else korean.search(value)!=null

func press(node: Node, caption: String) -> bool:
	for b in node.find_children("*","Button",true,false):
		if b.text==caption: b.pressed.emit(); return true
	return false

func login_fits() -> bool:
	for line in app.ui.find_children("*","LineEdit",true,false):
		if not line.is_visible_in_tree(): continue
		var font: Font=line.get_theme_font("font")
		var margins: float=line.get_theme_stylebox("normal").get_minimum_size().x
		if font.get_string_size(line.placeholder_text,HORIZONTAL_ALIGNMENT_LEFT,-1,line.get_theme_font_size("font_size")).x>line.size.x-margins-8: return false
	for b in app.ui.find_children("*","Button",true,false):
		if b.text==I18n.t("뒤로") and b.get_global_rect().end.y>root.get_visible_rect().size.y: return false
	return true

func run() -> void:
	I18n.setup()
	if "--reload-only" in OS.get_cmdline_user_args():
		expect(I18n.language()=="en" and TranslationServer.get_locale().begins_with("en"),"English survives a separate Godot process")
		quit(1 if failed else 0); return
	korean.compile("[가-힣]")
	I18n.remember("server","http://127.0.0.1:8766")
	for code in ["ko","en"]:
		app=Main.new();root.add_child(app);await create_timer(.6).timeout
		app.login_ui("settings")
		press(app.ui,"한국어" if code=="ko" else "English")
		await settled()
		press(app.ui,I18n.t("뒤로"));await settled()
		expect(I18n.language()==code and language_ok(app.ui,code),code+" language chosen through title settings")
		app.login_ui("login");await create_timer(.4).timeout
		app.message(app.error_message("weak_password"));await settled()
		expect(login_fits(),code+" login hints and back button fit with custom server and password error")
		if code=="en": await capture("en-login")
		var username: String="i18n_"+code+"_"+str(Time.get_ticks_usec())
		await app.authenticate(true,"http://127.0.0.1:8766",username,"Stage1-local-password!","")
		expect(app.screen=="village",code+" authenticated village")
		if app.screen!="village": quit(1);return
		if code=="ko": await capture("ko-village")
		app.open_story();await settled()
		var chapters_ok := true
		for b in app.village_modal.find_children("*","Button",true,false):
			if b.has_meta("id"): b.pressed.emit();await settled();chapters_ok=chapters_ok and language_ok(app.village_modal,code)
		expect(chapters_ok,code+" all three story introductions and counted objectives are localized")
		app.me.campaign[0].completed=true # UI-only completed-title regression; never claims a reward.
		app.open_story();await settled()
		expect(language_ok(app.village_modal,code) and visible_text(app.village_modal).contains("✓"),code+" completed chapter caption retains translation and checkmark")
		app.me.campaign[0].completed=false
		if code=="en": await capture("en-story")
		app.close_village_modal();app.open_expedition();await settled()
		var regions_ok := true
		for b in app.village_modal.find_children("*","Button",true,false):
			if b.has_meta("id"): b.pressed.emit();await settled();regions_ok=regions_ok and language_ok(app.village_modal,code)
		expect(regions_ok,code+" region and difficulty descriptions are localized")
		if code=="en": await capture("en-expedition")
		app.close_village_modal()
		await app.start_run("forest","relaxed","first_fire");app.paused=true;await settled()
		expect(app.screen=="survival" and language_ok(app.objective,code) and app.objective.text.contains("/ 20"),code+" authoritative story HUD keeps translated labels and counts")
		if code=="en": await capture("en-story-hud")
		var active_run: Dictionary=app.run.duplicate(true)
		app.run.status="won";app.run.story.objectives_met=true;app.run.story_bonus=20
		app.show_results();await settled()
		expect(language_ok(app.ui,code) and visible_text(app.ui).contains("20"),code+" result ending and bonus preview are localized (UI only)")
		if code=="en": await capture("en-result-preview")
		app.run=active_run;await app.leave_run()
		await app.open_craft();await settled()
		var idea: LineEdit=app.craft_box.find_children("*","LineEdit",true,false)[0]
		idea.text="설정" # An exact translation key must still remain a personal input.
		expect(not app.me.studio_tripo_enabled and language_ok(app.craft_box,code) and idea.text=="설정" and idea.auto_translate_mode==Node.AUTO_TRANSLATE_MODE_DISABLED,code+" disabled generation explains policy and preserves personal input")
		idea.text=""
		if code=="en": await capture("en-craft-disabled")
		var states_ok := true
		for state in ["queued","planning","building","unknown","failed","ready","awaiting_confirmation"]:
			app.render_craft({"state":state,"cost":20,"provenance":{"quoted_game_cost":40}});await settled()
			states_ok=states_ok and language_ok(app.craft_box,code)
		expect(states_ok and visible_text(app.craft_box).contains("40") and (code!="en" or korean.search(app.error_message("insufficient_shards"))==null),code+" status, failure, funds shortage and quote preview preserve translated text and price (UI only)")
		if code=="en": await capture("en-quote-preview")
		app.close_village_modal()
		var object_id: String=app.me.objects[0].id
		var personal_name: String=app.me.objects[0].name
		app.select_object(0)
		await app.begin_place()
		if not is_instance_valid(app.preview): expect(false,code+" owned starter model loads");quit(1);return
		app.preview.position=Town.furniture_point(0,0)
		var blocked: String=app.placement_problem()
		app.preview.position=Town.furniture_point(4,4)
		await app.place_preview()
		expect(not blocked.is_empty() and (code!="en" or korean.search(blocked)==null) and app.me.objects[0].state=="placed" and app.object_info.text.begins_with(personal_name) and app.objects_list.auto_translate_mode==Node.AUTO_TRANSLATE_MODE_DISABLED,code+" existing object placement, obstruction hint and personal name")
		await capture(code+"-placement")
		var token: String=app.api.token
		app.queue_free();await settled()
		Engine.set_meta("studio_session",{"token":token,"url":"http://127.0.0.1:8766","room":"home"})
		var studio=load("res://scenes/studio.tscn").instantiate();root.add_child(studio);await create_timer(.8).timeout
		studio.prompt.text="나루의 개인 의뢰"
		var studio_ok: bool=studio.prompt.text=="나루의 개인 의뢰" and studio.prompt.auto_translate_mode==Node.AUTO_TRANSLATE_MODE_DISABLED and studio.inventory.auto_translate_mode==Node.AUTO_TRANSLATE_MODE_DISABLED
		for state in ["queued","planning","awaiting_confirmation","building","ready","failed"]:
			studio_ok=studio_ok and (code!="en" or korean.search(studio.job_status(state))==null)
		expect(studio_ok,code+" interior craft states and personal prompt are preserved")
		if code=="en": await capture("en-home")
		studio.queue_free();Engine.remove_meta("studio_session");await settled()
		app=Main.new();root.add_child(app);await process_frame
		await app.authenticate(false,"http://127.0.0.1:8766",username,"Stage1-local-password!","")
		expect(app.screen=="village" and app.me.objects[0].id==object_id and app.me.objects[0].state=="placed" and I18n.language()==code,code+" reconnect keeps placed object and selected language")
		app.queue_free();await settled()
	print("I18N_FLOW ",JSON.stringify({"ok":not failed,"paid_provider_calls":0,"quote_and_result":"UI-only previews"}))
	quit(1 if failed else 0)
