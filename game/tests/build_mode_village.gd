extends SceneTree
## Village build mode end to end on a QA server: two crafted pieces 1.2 m apart (the old uniform
## 2×2 cells refused that), the right-click menu over a placed piece, 돌리기 (90° on the server),
## a lamp put on top of the table (item 74), 넣기 taking the table and the lamp on it back to the
## bag, 물건 통과 (V) and the door kept clear (item 76).
##   godot --path game --script res://tests/build_mode_village.gd -- --server=http://127.0.0.1:8813 [--capture]
const Town = preload("res://scripts/town.gd")
const VillageBuild = preload("res://scripts/build/village_build.gd")
var failures: Array[String]=[]
var app

func check(value: bool,message: String) -> void:
	print(("PASS " if value else "FAIL ")+message)
	if not value:failures.append(message)

func _initialize() -> void:call_deferred("run")

func capture(name: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	await create_timer(0.5).timeout
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://../artifacts/"+name)

func craft(prompt: String) -> String:
	var queued: Dictionary=await app.api.post("/v1/studio/jobs",app.api.mutation({"prompt":prompt,"geometry":"proxy","designer":"fixture"}))
	if not queued.ok: return ""
	for _i in 40:
		var job: Dictionary=await app.api.request("/v1/studio/jobs/"+queued.data.id)
		if job.ok and job.data.state=="ready": return str(job.data.object_id)
		await create_timer(0.5).timeout
	return ""

func obj(id: String) -> Dictionary:
	for o in app.me.objects:
		if str(o.id)==id: return o
	return {}

func select(id: String) -> void:
	for i in app.me.objects.size():
		if str(app.me.objects[i].id)==id: app.select_object(i)
	await create_timer(0.6).timeout

## begin_place waits out a refresh in flight (it returns at once while one runs).
func ghost_up() -> bool:
	for _i in 20:
		if not app.busy and not app.refreshing:
			await app.begin_place()
			if is_instance_valid(app.preview): return true
		await create_timer(0.3).timeout
	print("NO PREVIEW busy=",app.busy," refreshing=",app.refreshing)
	return false

func place_at(id: String, x: float, z: float) -> bool:
	await select(id)
	print("PLACE ",id," state=",obj(id).get("state")," selected=",app.selected.get("id")," busy=",app.busy," refreshing=",app.refreshing)
	if not await ghost_up(): return false
	app.preview_follow=false
	app.preview.position=Town.furniture_point(x,z)
	print("SPOT ",Vector2(x,z)," problem='",app.placement_problem(),"'")
	await app.place_preview()
	await create_timer(0.3).timeout
	return str(obj(id).get("state",""))=="placed"

func run() -> void:
	app=load("res://scripts/main.gd").new();root.add_child(app);await process_frame
	await create_timer(0.4).timeout
	await app.authenticate(true,preload("res://tests/qa_server.gd").url(),"buildmode_"+str(Time.get_ticks_msec()),"Local-build-qa-password1","")
	for _i in 40:
		if app.screen=="village":break
		await create_timer(0.25).timeout
	if app.screen!="village":print("FAIL login screen=",app.screen);quit(1);return
	var table := await craft("wooden table")
	var lamp := await craft("small flower lamp")
	check(not table.is_empty() and not lamp.is_empty(),"two crafted pieces")
	if table.is_empty() or lamp.is_empty(): quit(1);return
	await app.refresh_inventory()
	# Size-based spacing (item 25): close neighbours are fine when their boxes do not meet.
	# A meadow spot off the roads, clear of buildings, near the arrival.
	var spot := Vector2.INF
	await select(table)
	if not await ghost_up(): quit(1);return
	app.preview_follow=false
	for offset in [Vector2(-8,-4),Vector2(-6,6),Vector2(6,-6),Vector2(8,6),Vector2(-10,2),Vector2(10,-2),Vector2(4,10),Vector2(-4,-10)]:
		var here: Vector2=Town.furniture_local(app.player.position)+offset
		app.preview.position=Town.furniture_point(here.x,here.y)
		var lamp_side: Vector2=here+Vector2(1.6,0)
		var problem: String=app.placement_problem()
		app.preview.position=Town.furniture_point(lamp_side.x,lamp_side.y)
		var side_problem: String=app.placement_problem()
		print("TRY ",here," ",problem," | ",side_problem)
		if problem.is_empty() and side_problem.is_empty(): spot=here;break
	app.cancel_preview()
	check(spot!=Vector2.INF,"a free meadow spot near the arrival")
	if spot==Vector2.INF: quit(1);return
	check(await place_at(table,spot.x,spot.y),"the table stands in the village")
	var tsize: Vector3=app.loaded[table].get_meta("size",Vector3.ONE)
	var lsize: Vector3=app.loaded.get(lamp,app.inspect_model).get_meta("size",Vector3.ONE) if is_instance_valid(app.inspect_model) else Vector3.ONE
	print("SIZES table=",tsize," lamp=",lsize)
	var gap := tsize.x*0.5+0.6
	check(await place_at(lamp,spot.x+gap,spot.y),"a lamp %.2f m from the table's centre is allowed (old rule: 2 m)" % gap)
	# The menu over the table.
	app.player.position=Town.furniture_point(spot.x-2.5,spot.y+1.5)
	await create_timer(0.5).timeout
	if not app.loaded.has(table): quit(1);return
	var item: Node3D=app.loaded[table]
	var screen: Vector2=app.camera.unproject_position(item.global_position+Vector3(0,tsize.y*0.5,0))
	check(VillageBuild.pick(app,screen)==table,"right click finds the table under the pointer")
	VillageBuild.right_click(app,screen)
	await create_timer(0.4).timeout
	var menu: Control=app.ui.get_node_or_null("PlacedMenu")
	check(is_instance_valid(menu) and menu.find_children("*","Button",true,false).size()==4,"the placed menu opens with four entries")
	await capture("build-menu.png")
	# 돌리기: 90° more on the server.
	var before := int(obj(table).rotation)
	(menu.find_child("Turn",true,false) as Button).pressed.emit()
	await create_timer(1.5).timeout
	check(int(obj(table).rotation)==(before+90)%360,"돌리기 turns the table 90° (%d -> %d)" % [before,int(obj(table).rotation)])
	# The lamp onto the table's top.
	await select(lamp)
	if not await ghost_up(): quit(1);return
	app.preview_follow=false
	var body: CollisionObject3D=null
	for child in app.loaded[table].get_children():
		if child is CollisionObject3D: body=child
	var top_point: Vector3=app.loaded[table].global_position+Vector3(0.0,tsize.y+0.5,0.0)
	var hit: Dictionary=app.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(top_point,top_point-Vector3(0,2,0),VillageBuild.CRAFTED))
	check(not hit.is_empty() and hit.collider==body,"a ray down meets the table's top")
	if not hit.is_empty():
		VillageBuild.follow(app,hit)
		check(VillageBuild.stacking(app),"the ghost sits on the table")
		check(app.placement_problem().is_empty(),"the table's top is free: '%s'" % app.placement_problem())
		await app.place_preview()
		await create_timer(0.6).timeout
		var placed_lamp := obj(lamp)
		check(str(placed_lamp.get("surface",""))=="top" and str(placed_lamp.get("parent",""))==table,"the server keeps the lamp on the table")
		check(is_instance_valid(app.loaded.get(lamp)) and app.loaded[lamp].global_position.y>app.loaded[table].global_position.y+tsize.y*0.5,"the lamp stands up on the table top")
		await capture("build-stacked.png")
	# Ways kept open: in front of a door.
	await select(lamp)
	app.cancel_preview()
	# 물건 통과.
	var mask_before: int=app.player.collision_mask
	VillageBuild.toggle_pass(app)
	check(not (app.player.collision_mask&16) and mask_before&16,"V: the walker passes through crafted pieces")
	VillageBuild.toggle_pass(app)
	check(app.player.collision_mask&16,"V again: crafted pieces block again")
	await capture("build-pass.png")
	# 넣기: the table and the lamp on it go back to the bag.
	VillageBuild.right_click(app,app.camera.unproject_position(app.loaded[table].global_position+Vector3(0,tsize.y*0.3,0)))
	await create_timer(0.3).timeout
	menu=app.ui.get_node_or_null("PlacedMenu")
	if is_instance_valid(menu): (menu.find_child("Store",true,false) as Button).pressed.emit()
	await create_timer(2.0).timeout
	check(str(obj(table).state)=="inventory","넣기 takes the table back to the bag")
	check(str(obj(lamp).state)=="inventory","…and the lamp that stood on it")
	check(not app.loaded.has(table) and not app.loaded.has(lamp),"both are gone from the village")
	# A door: nothing may stand in front of it.
	await select(table)
	if await ghost_up():
		app.preview_follow=false
		var door: Vector2=Town.DOORS[8].at
		app.preview.position=Vector3(door.x,Town.height_at(door.x,door.y),door.y)
		check(not app.placement_problem().is_empty(),"in front of a door is refused: '%s'" % app.placement_problem())
		app.cancel_preview()
	print("BUILD_MODE_VILLAGE ",JSON.stringify({"ok":failures.is_empty(),"failures":failures}))
	quit(0 if failures.is_empty() else 1)
