extends SceneTree
const Main=preload("res://scripts/main.gd")
var app: Node3D
var failed := false
var start_time := 0.0
func _initialize() -> void: call_deferred("run_test")
func expect(value: bool,label: String) -> void:
	print(("PASS " if value else "FAIL ")+label)
	failed=failed or not value
func capture(label: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	await process_frame
	await RenderingServer.frame_post_draw
	var path := ProjectSettings.globalize_path("res://../artifacts/"+label+".png")
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--artifacts="): path=argument.trim_prefix("--artifacts=").path_join(label+".png")
	expect(root.get_texture().get_image().save_png(path)==OK,"capture "+label)
func stop() -> void:
	for key in ["move_left","move_right","move_forward","move_back"]: Input.action_release(key)
func walk(to: Vector2) -> bool:
	app.close_village_modal()
	var started := Time.get_ticks_msec()
	while Time.get_ticks_msec()-started<18000:
		var p := Vector2(app.player.position.x,app.player.position.z)
		var d := to-p
		stop()
		if d.length()<0.35: return true
		if absf(d.x)>0.15: Input.action_press("move_right" if d.x>0 else "move_left",1)
		if absf(d.y)>0.15: Input.action_press("move_back" if d.y>0 else "move_forward",1)
		await physics_frame
	stop()
	print("BLOCKED at ",app.player.position," target ",to)
	return false
func run_test() -> void:
	app=Main.new()
	root.add_child(app)
	await process_frame
	var username := "village_"+str(Time.get_unix_time_from_system()).replace(".","_")
	await app.authenticate(true,"http://127.0.0.1:8766",username,"qa-village-123","")
	expect(app.screen=="village" and not app.life.state.is_empty(),"new village and authenticated life state load")
	if app.screen!="village": quit(1); return
	app.life.open_map()
	await capture("village-map-07")
	app.close_village_modal()
	expect(await walk(Vector2(0,5)),"walk out of plaza")
	expect(await walk(Vector2(-15,5)),"west path leaves old village boundary")
	expect(await walk(Vector2(-22,-2.8)),"reach raised farm by physical walking")
	expect(app.player.position.y>0.45,"farm terrace has real elevation")
	expect(app.life.closest().get("kind","")=="plot","nearby plot can be interacted with")
	app.life.open_plot(4)
	for b in app.village_modal.find_children("*","Button",true,false):
		if b.text.begins_with("순무 심기"): b.pressed.emit(); break
	for i in 50:
		if not app.life.state.plots[4].is_empty(): break
		await create_timer(.1).timeout
	expect(app.life.state.bag.turnip_seed==2,"plant button consumes one seed on server")
	await create_timer(.15).timeout
	for b in app.village_modal.find_children("*","Button",true,false):
		if b.text=="물뿌리개로 물주기": b.pressed.emit(); break
	for i in 50:
		if app.life.state.plots[4].get("watered",false): break
		await create_timer(.1).timeout
	expect(app.life.state.plots[4].get("watered",false),"water button starts real server growth")
	start_time=Time.get_ticks_msec()*0.001
	await capture("farm-growing-07")
	app.close_village_modal()
	await capture("farm-world-07")
	expect(await walk(Vector2(-16,3)),"return from farm to village path")
	expect(await walk(Vector2(-7,9)),"walk to lake approach")
	expect(await walk(Vector2(-7,14.4)),"walk onto lake jetty without falling")
	app.life.open_fishing("pond")
	await app.life.action("cast",{"spot":"pond"})
	app.life.open_fishing("pond")
	expect(app.life.state.bag.bait==4,"casting consumes one bait")
	while app.life.now()<app.life.state.fishing.bite_at+.15: await create_timer(.05).timeout
	await capture("fishing-bite-07")
	var e := InputEventKey.new()
	e.physical_keycode=KEY_E; e.pressed=true
	app._unhandled_input(e)
	for i in 50:
		if app.life.state.fishing==null: break
		await create_timer(.1).timeout
	expect(app.life.state.caught==1,"E reels in a fish during real bite window")
	app.close_village_modal()
	expect(await walk(Vector2(-7,9)),"return safely from jetty")
	expect(await walk(Vector2(0,9)),"reach central promenade")
	expect(await walk(Vector2(12,-5)),"reach west bridge approach")
	expect(await walk(Vector2(23,-5)),"cross physical river bridge")
	expect(await walk(Vector2(26,5)),"reach east herb garden")
	await app.life.interact()
	expect(app.life.state.bag.get("herb",0)==2,"gather east-bank herbs")
	await capture("river-garden-07")
	expect(await walk(Vector2(27,-27)),"climb sloped northern ridge")
	expect(app.player.position.y>2.8,"ridge has elevated walkable floor")
	await capture("hill-lookout-07")
	expect(await walk(Vector2(27,-5)),"descend ridge")
	expect(await walk(Vector2(27,18)),"follow east bank south")
	expect(await walk(Vector2(26,29)),"walk onto sea fishing boardwalk")
	var haeru: Node3D
	for villager in app.npcs:
		if villager.get_meta("role","")=="angler": haeru=villager
	expect(is_instance_valid(haeru),"Haeru fisherman is present at the beach")
	if is_instance_valid(haeru):
		app.talk_to(haeru)
		var portrait_found := false
		for view in app.village_modal.find_children("*","TextureRect",true,false):
			if view.texture is AtlasTexture: portrait_found=true
		expect(portrait_found,"Haeru conversation shows the supplied character design")
		await capture("haeru-dialogue")
		app.close_village_modal()
	app.life.open_fishing("sea")
	await app.life.action("cast",{"spot":"sea"})
	while app.life.now()<app.life.state.fishing.bite_at+.15: await create_timer(.05).timeout
	await app.life.reel()
	expect(app.life.state.caught==2,"sea fishing also produces an authenticated catch")
	app.close_village_modal()
	await capture("beach-fishing-07")
	expect(await walk(Vector2(27,18)),"return to southern bridge")
	expect(await walk(Vector2(12,18)),"cross second bridge")
	expect(await walk(Vector2(0,9)),"southern promenade is unobstructed")
	expect(await walk(Vector2(0,5)),"return through plaza")
	expect(await walk(Vector2(-15,5)),"return to west path")
	expect(await walk(Vector2(-22,-2.8)),"return to planted crop")
	while app.life.now()<float(app.life.state.plots[4].ready_at)+.1: await create_timer(.2).timeout
	await capture("farm-ripe-07")
	await app.life.action("harvest",{"plot":4})
	expect(app.life.state.bag.get("turnip",0)==2,"harvest after ninety real seconds yields two turnips")
	expect(Time.get_ticks_msec()*0.001-start_time>=89.5,"crop test uses real elapsed time")
	expect(await walk(Vector2(-17,0.9)),"reach seed stall")
	await app.life.action("sell",{"item":"turnip","quantity":2})
	expect(app.life.state.coins==18,"sell harvested crops for village-only coins")
	app.life.open_shop()
	await capture("village-shop-07")
	app.close_village_modal()
	expect(await walk(Vector2(-16,9)),"walk west orchard path")
	expect(await walk(Vector2(-24,15)),"reach apple gathering spot")
	await app.life.interact()
	expect(app.life.state.bag.get("apple",0)==2,"orchard yields apples")
	await capture("orchard-07")
	await app.logout()
	await app.authenticate(false,"http://127.0.0.1:8766",username,"qa-village-123","")
	expect(app.life.state.caught==2 and app.life.state.coins==18 and app.life.state.plots[4].is_empty(),"fish crop and wallet survive relogin")
	app.life.open_storage()
	await capture("village-storage-07")
	app.queue_free()
	await process_frame
	print("VILLAGE_LIFE_COMPLETE")
	quit(1 if failed else 0)
