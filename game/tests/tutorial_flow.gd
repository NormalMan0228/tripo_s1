extends SceneTree
## Reduced onboarding check: isolated fixture server/settings, no paid provider.
const Main=preload("res://scripts/main.gd")
const I18n=preload("res://scripts/i18n.gd")
const Town=preload("res://scripts/town.gd")
var app: Node3D
var failed := false
var korea := RegEx.new()
var username := ""

func _initialize() -> void:
	call_deferred("run")
	create_timer(150).timeout.connect(func(): quit(2))

func expect(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ")+message)
	failed=failed or not value

func settle() -> void: await create_timer(.35).timeout

func capture(name: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	await create_timer(.5).timeout;await RenderingServer.frame_post_draw
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--artifacts="):
			if root.get_texture().get_image().save_png(arg.trim_prefix("--artifacts=").path_join("tutorial-"+name+".png"))!=OK:failed=true

func login(register: bool) -> void:
	app=Main.new();root.add_child(app);await process_frame
	await app.authenticate(register,"http://127.0.0.1:8766",username,"Tutorial-test-password!","")
	await settle()

func drop() -> void:
	app.queue_free();await settle()

func stored_step() -> int:
	var config := ConfigFile.new();config.load("user://tutorial.cfg")
	return int(config.get_value(app.tutorial.account,"step",-1))

func run() -> void:
	I18n.setup()
	if "--reload-only" in OS.get_cmdline_user_args():
		var config := ConfigFile.new();var ok: bool=config.load("user://tutorial.cfg")==OK
		var done := 0;var skipped := 0
		for section in config.get_sections():
			if config.get_value(section,"step",0)==6:done+=1
			if config.get_value(section,"skipped",false):skipped+=1
		expect(ok and done==2 and skipped==1,"two completed accounts and one skipped account survive a separate Godot process")
		quit(1 if failed else 0);return
	korea.compile("[가-힣]")
	if "--policy-only" in OS.get_cmdline_user_args():
		# UI-only policy states. No generation request or provider call is made.
		I18n.set_language("en");username="tut_policy_"+str(Time.get_ticks_usec());await login(true)
		app.tutorial.step=4;app.me.studio_tripo_enabled=true;app.me.shards=0
		app.frame.stars.text="0"
		await app.open_craft();await settle();app.close_village_modal();await settle()
		expect(not app.tutorial.can_craft() and app.tutorial.policy.text.contains("more Starseeds") and app.tutorial.craft_seen,"UI-only funds shortage explains existing-item practice")
		await capture("en-funds-policy")
		app.me.shards=80
		app.tutorial.accepted_craft({"id":"ui-only-pending","state":"queued"})
		app.me.shards=0 # A pending job may already have reserved the player's funds.
		app.tutorial.update()
		var pending_policy_ok: bool=not app.tutorial.policy.text.contains("more Starseeds")
		await app.tutorial.perform();await settle()
		expect(app.tutorial.step==5 and app.tutorial.craft_requested and pending_policy_ok,"UI-only reserved-funds pending job allows practice without a misleading shortage or completion wait")
		await drop();quit(1 if failed else 0);return
	for code in ["ko","en"]:
		I18n.set_language(code)
		username="tut_"+code+"_"+str(Time.get_ticks_usec())
		await login(true)
		if app.screen!="village": expect(false,"new tutorial account logs in");quit(1);return
		var stars: int=app.me.shards
		var leaves: int=app.life.state.coins
		await app.tutorial.perform();await settle()
		expect(app.tutorial.active() and app.tutorial.step==0 and app.me.shards==stars and app.life.state.coins==leaves,code+" route button cannot complete a goal or grant currency")
		await capture(code+"-home")
		app.player.position=Town.point(Town.HOME_DOOR,.3);await settle()
		expect(app.tutorial.step==1 and app.life.goal.id=="apple",code+" actual home proximity advances to the orchard route")
		app.player.position=Town.point(Vector2(-50,-44),.3)
		var gathered: bool=await app.life.action("gather",{"item":"apple"});await settle()
		expect(gathered and app.life.state.bag.apple==2 and app.tutorial.step==2 and app.life.state.coins==leaves,code+" server-owned apples advance gathering without bonus coins")
		app.player.position=Town.point(Vector2(-35.6,-23.2),.3)
		app.life.open_shop();await settle()
		var sale: Button
		for b in app.village_modal.find_children("*","Button",true,false):
			if b.text.begins_with(I18n.t("사과")+" "):sale=b;break
		if sale==null:expect(false,code+" shop apple sale button");quit(1);return
		sale.pressed.emit();await create_timer(.6).timeout
		expect(app.tutorial.step==3 and app.life.state.coins==leaves+2 and app.life.state.bag.apple==1,code+" actual shop sale earns exactly two Leaf coins and advances")
		app.close_village_modal();await app.tutorial.perform();await settle()
		expect(app.tutorial.step==4 and app.me.shards==stars and app.life.state.coins==leaves+2,code+" currency explanation next button grants nothing")
		await app.tutorial.perform();await settle()
		var idea: LineEdit=app.craft_box.find_children("*","LineEdit",true,false)[0]
		idea.text="친구에게 주는 작은 사과 의자"
		app.close_village_modal();await settle()
		var translated: bool=code!="en" or (korea.search(app.tutorial.body.text)==null and korea.search(app.tutorial.policy.text)==null and korea.search(app.tutorial.title.text)==null)
		expect(app.tutorial.craft_seen and not app.me.studio_tripo_enabled and translated and app.tutorial.panel.get_rect().end.y<=800,code+" disabled crafting is clearly explained, localized and fits the screen")
		await capture(code+"-craft-policy")
		await app.tutorial.perform();await settle()
		expect(app.tutorial.step==5 and stored_step()==5,code+" existing-item practice can continue without waiting for generation")
		await drop();await login(false)
		expect(app.tutorial.step==5 and app.tutorial.craft_seen,code+" unfinished tutorial resumes after reconnect")
		await app.tutorial.perform();app.select_object(0);await app.begin_place();await settle()
		app.tutorial.show_help();await settle()
		expect(is_instance_valid(app.preview) and app.tutorial.blocks_input() and not app.world_movement_allowed(),code+" help pauses movement without losing an in-progress placement")
		if code=="en":await capture("en-help")
		app.tutorial.close_help()
		if not is_instance_valid(app.preview):expect(false,code+" placement preview");quit(1);return
		app.preview.position=Town.furniture_point(4,4);await app.place_preview();await settle()
		expect(app.tutorial.completed and not app.tutorial.active() and stored_step()==6 and app.me.shards==stars and app.life.state.coins==leaves+2,code+" server-saved placement completes onboarding without extra rewards")
		await capture(code+"-free-play")
		await drop();await login(false)
		expect(app.tutorial.completed and not app.tutorial.panel.visible and app.me.objects[0].state=="placed" and app.life.state.coins==leaves+2,code+" completion and funds survive reconnect without reopening the tutorial")
		app.tutorial.show_help();app.tutorial.resume();await settle()
		app.tutorial.skip();await settle()
		expect(app.tutorial.completed and stored_step()==6 and app.life.state.coins==leaves+2,code+" replay and skip preserve completion and never mint rewards")
		await drop()
	username="tut_skip_"+str(Time.get_ticks_usec());await login(true)
	app.tutorial.skip();await settle()
	expect(app.tutorial.skipped and not app.tutorial.completed and app.tutorial.step==0,"a different account starts fresh and skipping does not claim completion")
	await drop();await login(false)
	expect(app.tutorial.skipped and not app.tutorial.panel.visible,"skipping survives reconnect for that account only")
	await drop()
	print("TUTORIAL_FLOW ",JSON.stringify({"ok":not failed,"paid_provider_calls":0,"new_reward_routes":0,"proximity":"position-based predicate; not a navigation playthrough"}))
	quit(1 if failed else 0)
