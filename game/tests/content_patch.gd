extends SceneTree
## Authenticated patch acceptance: authored NPC, player UI, placement/cancel and persistence.
var failures: Array[String]=[]
var app: Node
const Main=preload("res://scripts/main.gd")
func _initialize() -> void:call_deferred("run")
func expect(ok: bool,description: String) -> void:
	print(("PASS " if ok else "FAIL ")+description)
	if not ok:failures.append(description)
func capture(name: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args():return
	await process_frame;await RenderingServer.frame_post_draw
	var folder := ProjectSettings.globalize_path("res://../artifacts")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--artifacts="):folder=arg.trim_prefix("--artifacts=")
	expect(root.get_texture().get_image().save_png(folder.path_join(name+".png"))==OK,"capture "+name)
func run() -> void:
	app=Main.new();root.add_child(app);await process_frame
	await app.authenticate(true,"http://127.0.0.1:8766","content_"+str(Time.get_ticks_usec()),"content-patch-test-password","")
	expect(app.screen=="village","authenticated village opens")
	if app.screen!="village":quit(1);return
	expect(app.npcs.size()==5,"five village NPCs are available")
	await create_timer(.2).timeout
	var camera_forward: Vector3=app.camera.global_basis.z.normalized()
	var camera_stable := true
	var motion_start: Vector3=app.player.position
	# Start, turn and stop with real input. Pitch must not nod as tracking catches up.
	for action in ["move_right","move_back",""]:
		if not action.is_empty():Input.action_press(action)
		for frame in 18:
			await physics_frame
			camera_stable=camera_stable and camera_forward.dot(app.camera.global_basis.z.normalized())>.99999
		if not action.is_empty():Input.action_release(action)
	expect(app.player.position.distance_to(motion_start)>.6,"camera review uses physical player movement")
	expect(camera_stable,"camera keeps its viewing angle through starts turns and stops")
	await create_timer(.5).timeout
	print("CONTENT_RENDER_METRIC fps=",Engine.get_frames_per_second()," draw_calls=",Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
	await capture("content-village")
	var haeru: Node3D
	for npc in app.npcs:
		if npc.get_meta("role")=="angler":haeru=npc
		else:expect(npc.avatar.character=="explorer_b","consistent proportions for "+str(npc.get_meta("role")))
	expect(haeru!=null and haeru.avatar.character=="haeru","new concept-derived Haeru is integrated")
	if haeru:
		expect(haeru.hand_skeleton.get_bone_count()==41,"Haeru original skin rig retained")
		for clip in ["idle","walk","fishing","greet"]:expect(haeru.animation_player.has_animation(clip),"Haeru authored "+clip)
		# Teleport only for art inspection, not a navigation or gameplay claim.
		app.player.position=Vector3(29.4,.1,28.2);app.camera.size=8;app.follow_camera(1)
		await create_timer(.6).timeout
		await capture("content-haeru-fishing")
		app.talk_to(haeru);await create_timer(.85).timeout
		expect(haeru.current_clip=="greet","talking plays Haeru's original greeting")
		await capture("content-haeru-dialogue")
		app.close_village_modal();await create_timer(2.0).timeout
		expect(haeru.current_clip=="fishing","Haeru returns to fishing after greeting")
	var token: String=app.api.token
	app.queue_free();await process_frame
	Engine.set_meta("studio_session",{"token":token,"url":"http://127.0.0.1:8766","room":"home"})
	app=load("res://scenes/studio.tscn").instantiate();root.add_child(app);await create_timer(1.2).timeout
	expect(not app.room_root.find_children("AuthoredRoomShell","Node3D",true,false).is_empty(),"authored home interior loads")
	var tabs: TabContainer=app.find_children("*","TabContainer",true,false)[0]
	expect(tabs.is_tab_hidden(2) and tabs.is_tab_hidden(3) and tabs.is_tab_hidden(4),"player cannot see code/model/fitting tabs")
	app.message("model_download_failed")
	expect(not app.status_label.text.contains("model_download_failed"),"player failure text hides implementation codes")
	var queued: Dictionary=await app.api.post("/v1/studio/jobs",app.api.mutation({"prompt":"wooden chest"}))
	expect(queued.ok,"fixture furniture job queued without paid provider")
	if not queued.ok:quit(1);return
	var oid := ""
	for attempt in 80:
		var job: Dictionary=await app.api.request("/v1/studio/jobs/"+queued.data.id)
		if job.ok and job.data.state=="ready":oid=job.data.object_id;break
		await create_timer(.1).timeout
	expect(not oid.is_empty(),"fixture furniture finishes")
	await app.refresh()
	for i in app.data.objects.size():
		if app.data.objects[i].id==oid:await app.select_item(i);break
	expect(app.selected.get("id")==oid,"owned furniture selection loads")
	if app.selected.get("id")!=oid:quit(1);return
	expect(app.part_choice.get_item_text(1)=="본체" and app.part_choice.get_item_metadata(1)=="body","friendly part label retains the authorized part identifier")
	app.part_choice.select(2)
	await app.paint("#edbc63")
	expect(app.inspected.colors.get("lid")=="#edbc63" and app.inspected.colors.get("body")!="#edbc63","painting one translated part leaves the other part unchanged")
	app.part_choice.select(0)
	tabs.current_tab=1
	await app.begin_place();app.place_at=Vector3(0,.08,4);await process_frame
	expect(app.place_button.disabled and not app.placement_problem(app.place_at).is_empty(),"door obstruction disables place button")
	app.place_at=Vector3(-2,.08,-1);app.ghost.position=app.place_at
	app.rotate_placement(90);await process_frame
	expect(not app.place_button.disabled and app.placement_rotation==90,"valid cell and rotate control are available")
	await capture("content-placement")
	await app.commit_place()
	expect(app.placed.has(oid) and app.selected.rotation==90,"placement persisted by server")
	await app.begin_place()
	expect(not app.placed[oid].visible,"move hides old instance while previewing")
	app.cancel_placement();await process_frame
	expect(app.placed[oid].visible and not is_instance_valid(app.ghost) and not app.placement_mode,"cancel restores original without duplicate preview")
	await app.paint("#789887")
	expect(app.inspected.colors.get("lid")=="#789887","player palette persists both parts")
	await app.interact_selected();await create_timer(1.3).timeout
	expect(absf(app.placed[oid].pivots.lid.rotation_degrees.x)>70,"placed chest opens through authorized interaction")
	await capture("content-home-furniture")
	await app.change_room("workshop")
	expect(not app.placed.has(oid),"home furniture stays separate from workshop")
	await capture("content-workshop")
	await app.change_room("home")
	expect(app.placed.has(oid) and app.placed[oid].colors.get("lid")=="#789887","placement and paint survive room reentry")
	for i in app.data.objects.size():
		if app.data.objects[i].id==oid:await app.select_item(i);break
	await app.retrieve()
	expect(not app.placed.has(oid),"player can retrieve furniture")
	app.queue_free();await process_frame;await create_timer(.1).timeout
	Engine.remove_meta("studio_session")
	print("CONTENT_PATCH ",JSON.stringify({"ok":failures.is_empty(),"failures":failures,"paid_provider_calls":0}))
	quit(0 if failures.is_empty() else 1)
