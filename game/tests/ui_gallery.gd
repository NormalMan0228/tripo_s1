extends SceneTree
## Builds every player-facing screen against recorded server replies (no port)
## and captures each to artifacts/<prefix><screen>.png. Run windowed:
##   godot --path game --script res://tests/ui_gallery.gd -- --prefix=ui-after- --hour=12
## Optional: --languages=ko,en,zh  --only=title,village
const SocialHud = preload("res://scripts/social_hud.gd")
const Main = preload("res://scripts/main.gd")
const I18n = preload("res://scripts/i18n.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
const PauseMenu = preload("res://scripts/pause_menu.gd")
const SettingsMenu = preload("res://scripts/settings_menu.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const ShapePanel = preload("res://scripts/shape_panel.gd")
const InteractionPanel = preload("res://scripts/interaction_panel.gd")
var app: Node
var prefix := "ui-gallery-"
var only: PackedStringArray = []
var lang := "ko"
var shots: Array[String] = []

func _initialize() -> void:
	call_deferred("run")
	create_timer(420).timeout.connect(func():
		push_error("UI gallery exceeded 420 seconds")
		quit(2))

func wanted(name: String) -> bool:
	return only.is_empty() or name in only

func capture(name: String) -> void:
	for i in 10: await process_frame
	if DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	var file := prefix + (name if lang == "ko" else lang + "-" + name) + ".png"
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/" + file))
	shots.append(file)
	print("SHOT ", file)

func settle(seconds: float) -> void:
	await create_timer(seconds).timeout

## Waits (up to 8 s) until the start card (transition.gd) has faded off the title.
func uncovered() -> void:
	var cover: CanvasLayer = load("res://scripts/transition.gd").of(self)
	for i in 80:
		if not is_instance_valid(cover) or cover.veil.modulate.a < 0.02: return
		await settle(0.1)

func close_modal() -> void:
	app.close_village_modal()
	await settle(0.25)

func run() -> void:
	var languages := ["ko"]
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--prefix="): prefix = arg.trim_prefix("--prefix=")
		if arg.begins_with("--only="): only = arg.trim_prefix("--only=").split(",")
		if arg.begins_with("--languages="): languages = Array(arg.trim_prefix("--languages=").split(","))
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	I18n.setup()
	for code in languages:
		lang = code
		I18n.set_language(code)
		await tour(fixture.duplicate(true))
	I18n.set_language("ko")
	print("UI_GALLERY ", JSON.stringify({"shots": shots.size()}))
	quit(0)

func tour(fixture: Dictionary) -> void:
	app = Main.new()
	root.add_child(app)
	await settle(1.6)
	if wanted("title"): await capture("title")
	if wanted("title-menu"):
		# The title's menu plates once the start card has faded (the version check may still be asking).
		await uncovered()
		app.login_ui("menu")
		await settle(0.8)
		await capture("title-menu")
	if wanted("login"):
		app.login_ui("login")
		await settle(0.5)
		await capture("login")
	if wanted("settings"):
		await uncovered()
		app.login_ui("settings")
		await settle(0.5)
		await capture("settings")
	# Swap the network for the recorded replies and walk into the village.
	app.api.queue_free()
	var stub := Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = false
	await app.enter_village()
	# The start card covers the screen until a sign-in lifts it (main._ready); lift it here.
	preload("res://scripts/transition.gd").of(self).fade_in()
	await settle(1.2)
	app.message(tr("물결빛 마을에 오신 것을 환영해요! 다리를 건너 다섯 섬을 둘러보세요."))
	await settle(0.6)
	if wanted("village"): await capture("village")
	if wanted("bag"):
		app.toggle_drawer()
		await settle(0.6)
		await capture("bag")
		app.toggle_drawer()
	var crafted: Dictionary = fixture["/v1/me"].objects[0] if not fixture["/v1/me"].get("objects", []).is_empty() else {"id":"gallery", "name":"의자"}
	if wanted("shape"):
		# The bag's 모양 바꾸기 drawer (night glass on the right, over the bag).
		app.toggle_drawer()
		await settle(0.4)
		var shape := ShapePanel.new()
		shape.setup(app.api, crafted, func(): return [], app.message)
		app.ui.add_child(shape)
		await settle(0.6)
		await capture("shape")
		shape.close()
		app.toggle_drawer()
	if wanted("interaction-editor"):
		# The interaction editor on a recorded reply (no model: the stage stays empty).
		app.api.data["/v1/objects/%s/interaction" % crafted.id] = {"spec":{"mode":"original"}, "moving":false, "listed":false, "parts":[],
			"describe":{"left":3, "text_limit":200}, "runtime_version":1}
		var editor := InteractionPanel.new()
		editor.setup(app.api, crafted, null, {})
		app.ui.add_child(editor)
		await settle(1.0)
		await capture("interaction-editor")
		editor.close_panel()
		await settle(0.3)
	if wanted("craft"):
		await app.open_craft()
		await settle(0.5)
		await capture("craft")
		await close_modal()
	if wanted("expedition"):
		await app.open_expedition()
		await settle(0.5)
		await capture("expedition")
		await close_modal()
	if wanted("story"):
		app.open_story()
		await settle(0.5)
		await capture("story")
		await close_modal()
	if wanted("dialogue"):
		var plan: Dictionary = app.npc_script("map")
		app.open_dialogue(tr("나루 · 길잡이"), "naru", plan.lines, plan.choices)
		await settle(2.0)
		await capture("dialogue")
		for i in plan.lines.size() * 2: app.village_modal.get_meta("advance").call()
		await settle(0.6)
		await capture("dialogue-choices")
		await close_modal()
	for cast in [["sora","wardrobe","소라 · 재단사"],["moru","guide","모루 · 야영 전문가"],["haeru","angler","해루 · 낚시꾼"]]:
		if not wanted("dialogue-"+cast[0]): continue
		var lines: Dictionary = app.npc_script(cast[1])
		app.open_dialogue(tr(cast[2]), cast[0], lines.lines, lines.choices)
		for i in lines.lines.size() * 2: app.village_modal.get_meta("advance").call()
		await settle(1.0)
		await capture("dialogue-"+cast[0])
		await close_modal()
	if wanted("dialogue-shadow"):
		app.open_dialogue(tr("정원사"), "res://assets/ui/shadow_gardener.png", [tr("이쪽이에요, 조금만 더 가면 돼요!")], [[tr("따라간다"), Callable()]])
		await settle(1.6)
		await capture("dialogue-shadow")
		await close_modal()
	if wanted("pause-menu") or wanted("pause-controls") or wanted("pause-settings"):
		var pause = PauseMenu.open(app)
		await settle(0.8)
		if wanted("pause-menu"): await capture("pause-menu")
		if wanted("pause-controls"):
			pause.show_controls()
			await settle(0.6)
			await capture("pause-controls")
			pause.show_main()
		if wanted("pause-settings"):
			# Settings over the pause page: one shade under both.
			pause.show_settings()
			await settle(0.8)
			await capture("pause-settings")
		PauseMenu.close()
		await settle(0.4)
	if wanted("settings-menu"):
		var menu: Control = SettingsMenu.open(app.ui)
		await settle(0.8)
		await capture("settings-menu")
		if is_instance_valid(menu): menu.queue_free()
		await settle(0.3)
	if wanted("mailbox"):
		for module in app.modules:
			if module.has_method("use_mailbox"):
				for entry in module.objects:
					if entry.kind == "mailbox":
						module.use_mailbox(entry)
						break
		await settle(1.6)
		await capture("mailbox")
		await close_modal()
	if wanted("wardrobe"):
		app.open_wardrobe()
		await settle(1.0)
		await capture("wardrobe")
		await close_modal()
	for screen in ["map", "storage", "shop", "log"]:
		if not wanted(screen): continue
		app.life.call("open_" + screen)
		await settle(0.6)
		await capture(screen)
		await close_modal()
	if wanted("seeds"):
		var free_plot := 0
		for i in app.life.state.plots.size():
			if not app.life.state.plots[i].get("crop"):
				free_plot = i
				break
		app.life.open_plot(free_plot)
		await settle(0.5)
		await capture("seeds")
		await close_modal()
	if wanted("social"):
		# The 함께하기 drawer and the chat box live on the social layer (social_hud.gd).
		app.social.enabled = true
		var hub: Node = SocialHud.of(app.api)
		if hub:
			hub.bind(app, "village", app.toast_lane)
			hub.open_window("village")
			await settle(0.6)
			await capture("social")
			hub.close_window()
			hub.unbind(app)
			SocialHud.end(app.api)
		app.social.enabled = false
	if wanted("admin"):
		app.open_admin()
		await settle(0.5)
		await capture("admin")
		await close_modal()
	if wanted("survival") or wanted("survival-bag") or wanted("pause") or wanted("return-confirm") or wanted("results"):
		await app.start_run("forest", "standard")
		await settle(1.4)
		app.message(tr("해가 졌어요. 야영지로 돌아가 불을 지키세요."))
		await settle(0.4)
		if wanted("survival"): await capture("survival")
		if wanted("survival-bag"):
			app.toggle_drawer()
			await settle(0.5)
			await capture("survival-bag")
			app.toggle_drawer()
		if wanted("pause"):
			app.toggle_pause()
			await settle(0.5)
			await capture("pause")
			app.toggle_pause()
		if wanted("return-confirm"):
			app.confirm_return()
			await settle(0.5)
			await capture("return-confirm")
			if is_instance_valid(app.return_dialog): RpgUi.close_window(app.return_dialog.get_meta("rpg_window", {}), false)
			await settle(0.2)
		if wanted("results"):
			app.paused = true
			fixture.run.status = "won"
			fixture.run.reward = 84
			app.run.status = "won"
			app.run.reward = 84
			app.results_shown = true
			app.show_results()
			await settle(0.8)
			await capture("results")
	app.queue_free()
	await settle(0.5)
	if wanted("studio") or wanted("studio-talk") or wanted("studio-craft") or wanted("storage-chest"): await studio_tour()
	if wanted("studio-bag") or wanted("studio-hud"): await workshop_tour(fixture)

## A public room (the café) with its resident: the studio HUD and its dialogue.
func studio_tour() -> void:
	Engine.set_meta("studio_session", {"token":"", "url":"http://gallery.invalid", "room":"01_cafe", "username":"haneul", "coins":12})
	var studio: Node = load("res://scenes/studio.tscn").instantiate()
	root.add_child(studio)
	await settle(2.5)
	if wanted("studio"): await capture("studio")
	if wanted("studio-talk") and studio.npcs is Dictionary and not studio.npcs.is_empty():
		var id: String = studio.npcs.keys()[0]
		for key in studio.npcs.keys():
			if not studio.npcs[key].state.get("asleep", false):
				id = key
				break
		studio.open_talk(id)
		for i in 6: studio.advance_talk() if studio.talk_page < studio.talk_lines.size()-1 or studio.talk_body.visible_ratio < 1.0 else null
		await settle(1.2)
		await capture("studio-talk")
		studio.close_talk()
	if wanted("storage-chest"):
		# The storage chest of a residents' house, on a recorded reply.
		var stub := Stub.new()
		stub.data = {"/v1/social/npc-homes/gallery_home": {"stored": [{"name":"찻잔 세트", "npc":"", "tags":["cup"]},
			{"name":"작은 화분", "npc":"", "tags":["plant"]}, {"name":"별빛 오르골", "npc":"", "tags":["music"]}]}}
		studio.add_child(stub)
		var network: Node = studio.api
		studio.api = stub
		studio.gift_home = "gallery_home"
		await studio.open_storage({})
		await settle(0.6)
		await capture("storage-chest")
		studio.close_talk()
		studio.api = network
		studio.gift_home = ""
		stub.queue_free()
		await settle(0.3)
	if wanted("studio-craft"):
		# The room's craft window (C): the same window as the village's.
		studio.api.token = "gallery"
		studio.open_craft()
		await settle(0.8)
		await capture("studio-craft")
		studio.close_craft()
		studio.api.token = ""
	studio.queue_free()
	await settle(0.5)

## The player's workshop on the recorded replies: the 가방 drawer open (studio-bag), then the room's
## HUD alone (studio-hud: character frame, location card, hotbar).
func workshop_tour(fixture: Dictionary) -> void:
	Engine.set_meta("studio_session", {"token":"gallery", "url":"http://gallery.invalid", "room":"workshop", "username":"haneul", "coins":12,
		"profile":fixture["/v1/me"].get("profile", {})})
	var studio: Node = load("res://scenes/studio.tscn").instantiate()
	root.add_child(studio)
	# The room made its own connection while entering the tree; the recorded replies answer instead.
	studio.api.queue_free()
	var stub := Stub.new()
	stub.data = fixture
	studio.api = stub
	studio.add_child(stub)
	await settle(3.0)
	if wanted("studio-bag"):
		studio.set_dock_open(true)
		if studio.inventory.item_count > 0:
			studio.inventory.select(0)
			studio.inventory.item_selected.emit(0)
		await settle(1.5)
		await capture("studio-bag")
	if wanted("studio-hud"):
		studio.set_dock_open(false)
		await settle(0.8)
		await capture("studio-hud")
	studio.queue_free()
	await settle(0.5)
