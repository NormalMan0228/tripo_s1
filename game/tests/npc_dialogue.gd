extends SceneTree
## Talks to each cast NPC and captures the illustrated dialogue box.
const Main = preload("res://scripts/main.gd")
const Town = preload("res://scripts/town.gd")
var failed := false
func expect(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ")+label)
	if not value: failed = true
func shot(name: String) -> void:
	for i in 10: await process_frame
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/npc-"+name+".png"))
func _initialize() -> void:
	call_deferred("run")
	create_timer(150).timeout.connect(func(): quit(2))
func run() -> void:
	preload("res://scripts/npc.gd").pinned = true  # cast at their work spots whatever the clock
	var app = Main.new()
	root.add_child(app)
	await create_timer(1.2).timeout
	await app.authenticate(true,"http://127.0.0.1:8766","talk_"+str(Time.get_ticks_msec()),"Npc-dialogue-1","")
	await create_timer(1.0).timeout
	expect(app.npcs.size()==4,"four cast NPCs")
	for npc in app.npcs:
		expect(npc.get_script()==preload("res://scripts/npc.gd"),"cast model for "+str(npc.get_meta("cast")))
		var spot: Vector3=npc.position+Vector3(0,0,1.6)
		app.player.position=Town.point(Vector2(spot.x,spot.z),.3)
		app.camera_focus_ready=false
		for i in 30: await physics_frame
		expect(app.nearest_npc()==npc,"near "+str(npc.get_meta("cast")))
		app.talk_to(npc)
		await create_timer(1.8).timeout
		await shot(str(npc.get_meta("cast")))
		var advance: Callable=app.village_modal.get_meta("advance")
		for i in 6:
			advance.call()
			await create_timer(0.2).timeout
		await shot(str(npc.get_meta("cast"))+"-end")
		app.close_village_modal()
	quit(1 if failed else 0)
