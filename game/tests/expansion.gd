extends SceneTree
const Main=preload("res://scripts/main.gd")
var app: Node3D
var failed := false
func _initialize() -> void: call_deferred("run_test")
func expect(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ")+label)
	failed=failed or not value
func capture(label: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	await process_frame
	await RenderingServer.frame_post_draw
	var path := ProjectSettings.globalize_path("res://../artifacts/"+label+".png")
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--artifacts="): path=argument.trim_prefix("--artifacts=").path_join(label+".png")
	if root.get_texture().get_image().save_png(path)!=OK: failed=true
func run_test() -> void:
	app=Main.new()
	root.add_child(app)
	await process_frame
	var username := "expand_"+str(Time.get_unix_time_from_system()).replace(".","_")
	await app.authenticate(true,"http://127.0.0.1:8766",username,"Qa-expansion-123","")
	expect(app.screen=="village","village loads on protocol 6")
	if app.screen!="village": quit(1); return
	# main.gd CAST: Naru, Sora, Moru, Haeru (the shadow folk are a separate module).
	expect(app.npcs.size()==4 and app.npcs.any(func(n): return n.get_meta("role","")=="angler"),"four villagers spawned including the angler")
	app.player.position=app.npcs[1].position+Vector3(0,0,1.5)
	expect(app.nearest_npc()==app.npcs[1],"proximity chooses tailor")
	app.talk_to(app.npcs[1])
	await create_timer(0.2).timeout
	expect(is_instance_valid(app.village_modal) and not app.player.controls_enabled,"dialogue stops movement")
	await capture("npc-dialogue")
	app.open_wardrobe()
	await create_timer(0.3).timeout
	await capture("wardrobe")
	for b in app.village_modal.find_children("*","Button",true,false):
		if b.has_meta("character") and b.get_meta("character")=="ranger": b.pressed.emit()
	for b in app.village_modal.find_children("*","Button",true,false):
		if b.get_meta("part","")=="coat" and b.get_meta("color","")=="#ab789f": b.pressed.emit()
	await create_timer(0.2).timeout
	await capture("wardrobe-customized")
	for b in app.village_modal.find_children("*","Button",true,false):
		if b.text=="이 모습으로 저장": b.pressed.emit()
	for i in 40:
		if not is_instance_valid(app.village_modal): break
		await create_timer(0.1).timeout
	expect(not is_instance_valid(app.village_modal) and app.me.profile.version==1,"wardrobe buttons save authenticated profile")
	await app.refresh_inventory()
	expect(app.player.avatar.character=="ranger" and app.player.avatar.coat=="#ab789f","saved appearance applied to player")
	app.open_expedition()
	await capture("expedition-selection")
	app.close_village_modal()
	for region in ["forest","quarry","frost"]:
		await app.start_run(region,"veteran")
		expect(app.run.map_id==region and app.run.difficulty=="veteran","server selected "+region+" veteran")
		expect(app.player.avatar.character=="ranger","appearance follows expedition")
		await create_timer(0.5).timeout
		await capture("region-"+region)
		# Authored layouts (server/survival_maps.py): quarry 3 ember fissures, frost 4 ice circles, solid landmarks + camp kit.
		var hazard_kind: String = {"forest":"","quarry":"ember","frost":"ice"}[region]
		expect(app.run.obstacles.size()>=15 and app.run.hazards.all(func(h): return h.kind==hazard_kind) and (app.run.hazards.size()>=3)==(region!="forest"),"region hazards and obstacles received")
		await app.leave_run()
	await app.logout()
	await app.authenticate(false,"http://127.0.0.1:8766",username,"Qa-expansion-123","")
	expect(app.player.avatar.character=="ranger" and app.me.profile.version==1,"avatar persists across session replacement")
	app.queue_free()
	await process_frame
	# Let the last door/UI sound finish: quitting mid-sound leaks the engine's playback at exit.
	await create_timer(1.0).timeout
	print("EXPANSION_COMPLETE")
	quit(1 if failed else 0)
