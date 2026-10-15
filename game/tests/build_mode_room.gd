extends SceneTree
## Room build mode end to end on a QA server: two pieces placed 1.3 m apart in the home (the old
## two-cell rule refused that), the right-click menu over a placed piece, 돌리기, 넣기 and
## 물건 통과 (V) letting the walker stand inside a piece.
##   godot --path game --script res://tests/build_mode_room.gd -- --server=http://127.0.0.1:8813 [--capture]
const RoomBuild = preload("res://scripts/build/room_build.gd")
var failures: Array[String]=[]
var studio

func check(value: bool,message: String) -> void:
	print(("PASS " if value else "FAIL ")+message)
	if not value:failures.append(message)

func _initialize() -> void:call_deferred("run")

func capture(name: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	await create_timer(0.5).timeout
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://../artifacts/"+name)

func obj(id: String) -> Dictionary:
	for o in studio.data.get("objects",[]):
		if str(o.id)==id: return o
	return {}

func place(id: String, at: Vector3) -> bool:
	for i in studio.data.objects.size():
		if str(studio.data.objects[i].id)==id: await studio.select_item(i)
	await studio.begin_place()
	if not is_instance_valid(studio.ghost): print("NO GHOST");return false
	studio.place_at=at;studio.ghost.position=at
	print("SPOT ",at," problem='",studio.placement_problem(at),"'")
	await studio.commit_place()
	await create_timer(0.4).timeout
	return str(obj(id).get("state",""))=="placed"

func run() -> void:
	var server: String=preload("res://tests/qa_server.gd").url()
	var api=load("res://scripts/api.gd").new();root.add_child(api);api.base_url=server
	var reply: Dictionary=await api.post("/v1/auth/register",{"username":"buildroom_"+str(Time.get_ticks_msec()),"password":"Local-build-qa-password1","invitation":""})
	check(reply.ok,"a fresh account")
	if not reply.ok: quit(1);return
	api.token=reply.data.token
	var ids: Array=[]
	for prompt in ["wooden table","small stool"]:
		var queued: Dictionary=await api.post("/v1/studio/jobs",api.mutation({"prompt":prompt,"geometry":"proxy","designer":"fixture"}))
		if not queued.ok: print("CRAFT REFUSED ",queued.error);continue
		for _i in 40:
			var job: Dictionary=await api.request("/v1/studio/jobs/"+queued.data.id)
			if job.ok and job.data.state=="ready": ids.append(str(job.data.object_id));break
			await create_timer(0.5).timeout
	check(ids.size()==2,"two crafted pieces")
	if ids.size()<2: quit(1);return
	Engine.set_meta("studio_session",{"token":api.token,"url":server,"room":"home"})
	studio=load("res://scenes/studio.tscn").instantiate();root.add_child(studio)
	for _i in 40:
		if not studio.data.is_empty() and is_instance_valid(studio.hero): break
		await create_timer(0.25).timeout
	await create_timer(1.0).timeout
	check(await place(ids[0],Vector3(-2.0,0.08,-1.5)),"the table stands in the home")
	check(await place(ids[1],Vector3(-0.7,0.08,-1.5)),"a stool 1.3 m away is allowed (old rule: two cells)")
	var table: String=ids[0]
	var item: Node3D=studio.placed.get(table)
	if not is_instance_valid(item): quit(1);return
	var ratio: Vector2=Vector2(studio.viewport.size)/studio.view_container.size.max(Vector2.ONE)
	var size: Vector3=item.get_meta("size",Vector3.ONE)
	var screen: Vector2=studio.camera.unproject_position(item.global_position+Vector3(0,size.y*0.5,0))/ratio
	check(RoomBuild.pick(studio,screen)==table,"right click finds the table")
	RoomBuild.right_click(studio,screen)
	await create_timer(0.4).timeout
	var menu: Control=studio.view_container.get_node_or_null("PlacedMenu")
	check(is_instance_valid(menu),"the placed menu opens over the room view")
	await capture("build-room-menu.png")
	if is_instance_valid(menu):
		var before := int(obj(table).rotation)
		(menu.find_child("Turn",true,false) as Button).pressed.emit()
		await create_timer(1.5).timeout
		check(int(obj(table).rotation)==(before+90)%360,"돌리기 turns the table 90°")
	# 물건 통과: standing inside the table is blocked, then allowed.
	RoomBuild.PassThrough.persist=false
	RoomBuild.PassThrough._loaded=true
	RoomBuild.PassThrough.on=false
	check(studio.movement_blocked(item.position),"the table blocks the walker")
	RoomBuild.toggle_pass(studio)
	check(not studio.movement_blocked(item.position),"V: the walker may pass through it")
	RoomBuild.toggle_pass(studio)
	# 넣기.
	RoomBuild.right_click(studio,screen)
	await create_timer(0.4).timeout
	menu=studio.view_container.get_node_or_null("PlacedMenu")
	if is_instance_valid(menu): (menu.find_child("Store",true,false) as Button).pressed.emit()
	await create_timer(2.5).timeout
	check(str(obj(table).get("state",""))=="inventory","넣기 takes the table back to the bag")
	check(not studio.placed.has(table),"…and it leaves the room")
	await surfaces(ids)
	print("BUILD_MODE_ROOM ",JSON.stringify({"ok":failures.is_empty(),"failures":failures}))
	quit(0 if failures.is_empty() else 1)

## Walls, ceiling and stacks (items 70, 74): the ghost on each surface, the server's pose back.
func ghost_for(id: String) -> bool:
	for i in studio.data.objects.size():
		if str(studio.data.objects[i].id)==id: await studio.select_item(i)
	await studio.begin_place()
	return is_instance_valid(studio.ghost)

func surfaces(ids: Array) -> void:
	await stack(ids[0],ids[1])
	await hang()

## A second home (demo accounts can craft two pieces): a frame on the wall and a lamp on the ceiling.
func hang() -> void:
	var BuildRules = RoomBuild.BuildRules
	var server: String=preload("res://tests/qa_server.gd").url()
	var api=load("res://scripts/api.gd").new();root.add_child(api);api.base_url=server
	var reply: Dictionary=await api.post("/v1/auth/register",{"username":"buildwall_"+str(Time.get_ticks_msec()),"password":"Local-build-qa-password1","invitation":""})
	if not reply.ok: check(false,"a second account");return
	api.token=reply.data.token
	var made: Array=[]
	for prompt in ["picture frame","hanging lamp"]:
		var queued: Dictionary=await api.post("/v1/studio/jobs",api.mutation({"prompt":prompt,"geometry":"proxy","designer":"fixture"}))
		if not queued.ok: print("CRAFT REFUSED ",queued.error);continue
		for _i in 40:
			var job: Dictionary=await api.request("/v1/studio/jobs/"+queued.data.id)
			if job.ok and job.data.state=="ready": made.append(str(job.data.object_id));break
			await create_timer(0.5).timeout
	check(made.size()==2,"a frame and a lamp")
	if made.size()<2: return
	studio.queue_free()
	await create_timer(0.3).timeout
	Engine.set_meta("studio_session",{"token":api.token,"url":server,"room":"home"})
	studio=load("res://scenes/studio.tscn").instantiate();root.add_child(studio)
	for _i in 40:
		if not studio.data.is_empty() and is_instance_valid(studio.hero): break
		await create_timer(0.25).timeout
	await create_timer(1.0).timeout
	var frame: String=made[0]
	var lamp: String=made[1]
	var ratio: Vector2=Vector2(studio.viewport.size)/studio.view_container.size.max(Vector2.ONE)
	if await ghost_for(frame):
		var fsize: Vector3=studio.ghost.get_meta("size",Vector3.ONE)
		print("FRAME size=",fsize," wall_ok='",BuildRules.wall_problem(fsize),"'")
		var row: Control=studio.get_meta("surface_row")
		var wall_button: Button=row.get_node("Surface_wall")
		check(wall_button.disabled==not BuildRules.wall_problem(fsize).is_empty(),"the wall button follows the piece's shape")
		if not wall_button.disabled:
			RoomBuild.choose_mode(studio,"wall")
			RoomBuild.follow(studio,studio.camera.unproject_position(Vector3(-3.2,1.8,-4.95))/ratio)
			RoomBuild.follow(studio,studio.camera.unproject_position(Vector3(-1.05,2.0,-4.95))/ratio)
			check(not studio.placement_problem(studio.place_at).is_empty(),"over the back window is refused: '%s'" % studio.placement_problem(studio.place_at))
			# Over one of the room's own wall pieces on the back wall (shelf, clock...).
			var fixture := {}
			for record in studio.decor:
				if record.get("mounted",false) and is_instance_valid(record.get("node")) and float(record.center.z)<-4.0: fixture=record;break
			if not fixture.is_empty():
				var middle: Vector3=Vector3(fixture.center.x,(fixture.node as Node3D).global_position.y+Vector3(fixture.get("size",Vector3.ONE)).y*0.5,-4.95)
				RoomBuild.follow(studio,studio.camera.unproject_position(middle)/ratio)
				check(not studio.placement_problem(studio.place_at).is_empty(),"over the room's %s is refused: '%s'" % [str(fixture.get("kind","")),studio.placement_problem(studio.place_at)])
			RoomBuild.follow(studio,studio.camera.unproject_position(Vector3(-4.95,1.8,0.9))/ratio)
			check(RoomBuild.surface(studio)=="wall" and str(studio.ghost.get_meta("build_wall",""))=="left" and studio.placement_rotation==90,"the ghost hangs on the left wall, facing in")
			check(studio.placement_problem(studio.place_at).is_empty(),"the wall spot is free: '%s'" % studio.placement_problem(studio.place_at))
			await studio.commit_place()
			await create_timer(0.5).timeout
			var o := obj(frame)
			check(str(o.get("surface",""))=="wall" and float(o.get("y",0))>0.5,"the server keeps the frame on the wall (y=%s)" % str(o.get("y")))
			check(is_instance_valid(studio.placed.get(frame)) and studio.placed[frame].position.y>0.5,"the frame shows up on the wall")
		else: studio.cancel_placement()
	if await ghost_for(lamp):
		var lsize: Vector3=studio.ghost.get_meta("size",Vector3.ONE)
		var reason: String=BuildRules.ceiling_problem(lsize,BuildRules.words_for(studio.selected,studio.ghost))
		print("LAMP size=",lsize," ceiling_ok='",reason,"'")
		if reason.is_empty():
			RoomBuild.choose_mode(studio,"ceiling")
			RoomBuild.follow(studio,studio.camera.unproject_position(Vector3(-1.5,0.07,1.0))/ratio)
			check(RoomBuild.surface(studio)=="ceiling","the ghost hangs from the ceiling")
			await studio.commit_place()
			await create_timer(0.5).timeout
			var o := obj(lamp)
			check(str(o.get("surface",""))=="ceiling","the server keeps the lamp on the ceiling")
			check(studio.placed.has(lamp) and studio.placed[lamp].position.y+lsize.y>2.9,"the lamp hangs near the ceiling")
			check(not studio.movement_blocked(Vector3(float(o.x),0,float(o.z))),"walking under a hanging lamp is free")
		else: studio.cancel_placement()
	RoomBuild.RpgUi.clear_toasts(studio.toast_lane)
	await capture("build-room-hang.png")

func stack(table: String, stool: String) -> void:
	var BuildRules = RoomBuild.BuildRules
	check(await place(table,Vector3(1.5,0.08,-2.0)),"the table stands again")
	var under: Node3D=studio.placed.get(table)
	if not is_instance_valid(under): return
	var ratio: Vector2=Vector2(studio.viewport.size)/studio.view_container.size.max(Vector2.ONE)
	if await ghost_for(stool):
		var ssize: Vector3=studio.ghost.get_meta("size",Vector3.ONE)
		RoomBuild.choose_mode(studio,"floor")
		var on_top: bool=RoomBuild.follow(studio,studio.camera.unproject_position(under.global_position+Vector3(0,under.get_meta("size",Vector3.ONE).y,0))/ratio)
		check(on_top and RoomBuild.surface(studio)=="top","pointing at the table's top puts the ghost on it")
		var problem: String=studio.placement_problem(studio.place_at)
		print("STOOL size=",ssize," on table problem='",problem,"'")
		if problem.is_empty():
			await studio.commit_place()
			await create_timer(0.5).timeout
			check(str(obj(stool).get("surface",""))=="top" and str(obj(stool).get("parent",""))==table,"the server keeps the stool on the table")
		else:
			check(not BuildRules.stack_problem(ssize,under.get_meta("size",Vector3.ONE),1).is_empty(),"a refused stack says why")
			studio.cancel_placement()
		await capture("build-room-stack.png")
