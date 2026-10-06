extends SceneTree
## Opens every interior in turn without a server (empty token), walks the hero a
## little, uses a piece of furniture and saves a capture of every floor, plus
## sitting/lying and morning/dusk/night captures and a contact sheet, to
## artifacts/. Run WITHOUT --headless so the captures render:
##   Godot --path game -s res://tests/interior_tour.gd [-- --room=01_cafe]
const Interiors = preload("res://scripts/interiors.gd")
const ROOMS := ["home","workshop","01_cafe","02_timber_house","03_teal_cottage","04_windmill","05_observatory","06_orange_cottage","07_greenhouse","11_purple_house","12_blue_house","13_shop","16_blue_cottage","17_lighthouse"]
const SHOWCASE := ["piano","map_table","telescope","lighthouse_lens","fireplace","cooking_stove","bed","bathtub","gear_wheel","bookshelf","cafe_counter","shop_counter","millstone","seedling_bench","kitchen_counter","workbench","wall_clock"]
var failures: Array[String] = []
var out_dir := ""
var shots: Array[Image] = []

func _initialize() -> void:
	call_deferred("run")
	create_timer(600).timeout.connect(func():
		push_error("Interior tour exceeded 600 seconds")
		quit(2))

func check(value: bool, description: String) -> void:
	if not value:
		failures.append(description)
		print("FAIL ",description)

func hold(action: String, seconds: float) -> void:
	Input.action_press(action)
	await create_timer(seconds).timeout
	Input.action_release(action)

func capture(name: String, wait := 0.8) -> void:
	await create_timer(wait).timeout
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	image.convert(Image.FORMAT_RGBA8)
	image.save_png(out_dir.path_join(name+".png"))
	shots.append(image)

func open(id: String) -> Control:
	Engine.set_meta("studio_session",{"token":"","url":"http://127.0.0.1:9","room":id})
	var app: Control = load("res://scenes/studio.tscn").instantiate()
	root.add_child(app)
	await create_timer(0.9).timeout
	return app

func close(app: Control) -> void:
	app.queue_free()
	await process_frame
	await process_frame

## Uses the most characteristic piece on the current floor so the capture shows a bubble.
func showcase(app: Control) -> String:
	for kind in SHOWCASE:
		for record in app.decor:
			if record.kind == kind and record.interactive and not record.has("link"):
				app.hero.position = approach(app, record)
				app.hero.facing = (record.center-app.hero.position).normalized()
				app.use_decor(record)
				return kind
	return ""

## A free spot in front of a piece, used to stand the walker beside it.
func approach(app: Control, record: Dictionary) -> Vector3:
	var front := Vector3(0,0,1).rotated(Vector3.UP,float(record.yaw))
	for distance in [0.7,0.9,1.1,1.4]:
		var at: Vector3 = record.center+front*(float(record.half.y)+distance)
		at.y = 0
		if app.can_stand(at): return at
	return app.hero.position

func run() -> void:
	var only := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--room="): only = arg.trim_prefix("--room=")
	out_dir = ProjectSettings.globalize_path("res://").path_join("../artifacts").simplify_path()
	DirAccess.make_dir_recursive_absolute(out_dir)
	Engine.set_meta("interior_hour",13.0)
	var summary: Array = []
	if "--stairs-fx" in OS.get_cmdline_user_args():
		await stairs_and_effects()
		print("INTERIOR_TOUR ",JSON.stringify({"ok":failures.is_empty(),"failures":failures,"rooms":0}))
		quit(0 if failures.is_empty() else 1)
		return
	if "--residents" in OS.get_cmdline_user_args():
		await residents_captures()
		var sheet_only := Image.create_empty(400*4,250*int(ceil(shots.size()/4.0)),false,Image.FORMAT_RGBA8)
		for i in shots.size():
			var small: Image = shots[i].duplicate()
			small.resize(400,250,Image.INTERPOLATE_BILINEAR)
			sheet_only.blit_rect(small,Rect2i(0,0,400,250),Vector2i((i%4)*400,int(i/4)*250))
		sheet_only.save_png(out_dir.path_join("interior-res-sheet.png"))
		print("INTERIOR_TOUR ",JSON.stringify({"ok":failures.is_empty(),"failures":failures,"rooms":0}))
		quit(0 if failures.is_empty() else 1)
		return
	for id in ROOMS:
		if not only.is_empty() and id != only: continue
		var app := await open(id)
		var building: Dictionary = app.building_spec
		var spec: Dictionary = app.room_spec
		var size: Vector2 = spec.size
		check(app.room == id, id+" opens the requested room")
		check(app.camera.projection == Camera3D.PROJECTION_PERSPECTIVE and app.camera.fov >= 38 and app.camera.fov <= 42, id+" perspective camera")
		check(app.camera.position.z > size.y*0.5, id+" camera stands in front of the open front edge")
		check(is_instance_valid(app.hero), id+" hero present")
		var limits := Interiors.walk_limits(spec)
		check(Interiors.at_door(spec,Vector3(limits.door_x,0,limits.door_front)) and not Interiors.at_door(spec,Interiors.spawn_point(spec)), id+" door edge leaves, spawn does not")
		check(not app.movement_blocked(Interiors.spawn_point(spec)), id+" spawn is clear")
		if Interiors.is_private(id):
			check(size.x >= 9 and size.y >= 9, id+" keeps the whole [-4,4] server square inside")
			check(app.dock_toggle.visible and app.dock_panel.visible == (id == "workshop"), id+" keeps the editing dock behind its drawer button")
			app.set_dock_open(true)
			check(app.dock_panel.visible, id+" drawer opens")
			app.set_dock_open(id == "workshop")
			check(not app.placement_problem(Vector3(0,0,4)).is_empty(), id+" door strip rejected")
			check(not app.placement_problem(Vector3(4.5,0,0)).is_empty(), id+" outside server bounds rejected")
			for spot in [Vector3(-2,0,-1),Vector3(2,0,-1),Vector3(1.5,0,-1.5)]:
				if id == "workshop" and spot.x < -1.8: continue
				check(app.placement_problem(spot).is_empty(), id+" central cell %s stays free" % str(spot))
		else:
			check(not app.dock_panel.visible and not app.dock_toggle.visible, id+" hides the editing dock")
			check(app.title_label.text == app.tr(str(spec.name)), id+" shows the building name")
			check(not app.placement_problem(Vector3.ZERO).is_empty(), id+" refuses placement")
		var start: Vector3 = app.hero.position
		await hold("move_left",0.4)
		await hold("move_forward",0.5)
		await hold("move_right",0.7)
		await hold("move_back",0.25)
		check(app.hero.position.distance_to(start) > 0.4, id+" hero walks")
		check(Interiors.walkable(spec,app.hero.position), id+" hero stays on the floor")
		check(not app.leaving, id+" walking around does not leave")
		var floors: Array = building.floors
		var rooms := 0
		for index in floors.size():
			if index > 0:
				app.set_floor(index)
				app.hero.position = first_arrival(floors, index, app)
				app.update_camera(0.0,true)
			rooms += floors[index].rooms.size()
			var effects: int = app.stage.get_child_count()
			var shown := showcase(app)
			check(not app.last_used.is_empty() and (app.bubble.visible or is_instance_valid(app.talk_box) or app.stage.get_child_count() > effects or app.resting != ""), "%s floor %d furniture answers (%s)" % [id,index,shown])
			await capture("interior-%s" % id if index == 0 else "interior-%s-f%d" % [id,index])
			app.bubble.visible = false
		var kinds: Array = []
		var glb := 0
		for list in app.decor_by_floor:
			for record in list:
				if not kinds.has(record.kind): kinds.append(record.kind)
				if record.glb: glb += 1
		summary.append({"id":id,"floors":floors.size(),"rooms":rooms,"size":[size.x,size.y],"furniture":kinds.size(),"glb_pieces":glb})
		print("ROOM ",JSON.stringify(summary[-1]))
		await close(app)
	if only.is_empty() or only == "01_cafe": await extras()
	if not shots.is_empty():
		var thumb := Vector2i(400,250)
		var columns := 5
		var rows := int(ceil(shots.size()/float(columns)))
		var sheet := Image.create_empty(thumb.x*columns,thumb.y*rows,false,Image.FORMAT_RGBA8)
		sheet.fill(Color("1b1714"))
		for i in shots.size():
			var small: Image = shots[i].duplicate()
			small.resize(thumb.x,thumb.y,Image.INTERPOLATE_BILINEAR)
			sheet.blit_rect(small,Rect2i(Vector2i.ZERO,thumb),Vector2i((i%columns)*thumb.x,int(i/columns)*thumb.y))
		sheet.save_png(out_dir.path_join("interior-sheet.png" if only.is_empty() else "interior-sheet-%s.png" % only))
	# Walking out through the doorway leaves the room (stopped before the village loads).
	Engine.set_meta("interior_hour",13.0)
	var exit_room := await open("13_shop" if only.is_empty() else only)
	exit_room.hero.position = Interiors.spawn_point(exit_room.room_spec)+Vector3(0.35,0,0)
	Input.action_press("move_back")
	for i in 60:
		await create_timer(0.05).timeout
		if exit_room.leaving: break
	Input.action_release("move_back")
	check(exit_room.leaving, "walking into the front door leaves the room")
	var z0: float = exit_room.hero.position.z
	await create_timer(0.25).timeout
	check(exit_room.hero.position.z > z0+0.2 and exit_room.hero.external_velocity.length() > 1.0, "the walker keeps walking out through the doorway while the screen fades")
	Engine.remove_meta("interior_hour")
	print("INTERIOR_TOUR ",JSON.stringify({"ok":failures.is_empty(),"failures":failures,"rooms":summary.size()}))
	quit(0 if failures.is_empty() else 1)

func first_arrival(floors: Array, index: int, app: Control) -> Vector3:
	for f in floors:
		for entry in f.furniture:
			if entry.has("link") and int(entry.link.to) == index: return entry.link.arrive
	return Interiors.spawn_point(app.room_spec)

## Sitting, lying and the same room at morning, dusk and night.
func extras() -> void:
	var cafe := await open("01_cafe")
	for record in cafe.decor:
		if record.kind == "wooden_chair" and not record.has("occupant"):
			cafe.hero.position = approach(cafe, record)
			cafe.use_decor(record)
			break
	check(cafe.resting == "sit", "the walker sits on a cafe chair")
	await capture("interior-sit")
	cafe.stand_up()
	check(cafe.resting.is_empty() and cafe.hero.position.y == 0.0, "standing up puts the walker back on the floor")
	for hour in [[7.2,"morning"],[18.6,"dusk"],[22.5,"night"]]:
		cafe.hour_override = hour[0]
		cafe.apply_daylight(true)
		await capture("interior-time-%s" % hour[1])
	await close(cafe)
	Engine.set_meta("interior_hour",13.0)
	var home := await open("home")
	home.set_floor(1)
	for record in home.decor:
		if record.kind == "bed":
			home.hero.position = approach(home, record)
			home.use_decor(record)
			break
	home.update_camera(0.0,true)
	check(home.resting == "lie", "the walker lies on the attic bed")
	await capture("interior-lie")
	await close(home)

## Residents at telling hours: the busy café, a miller at work, sleepers in bed.
func residents_captures() -> void:
	Engine.set_meta("interior_day",preload("res://scripts/residents.gd").clock().day)
	for shot in [["01_cafe",19.0,"talk"],["04_windmill",12.5,""],["07_greenhouse",12.5,""],["13_shop",12.5,""],["05_observatory",22.5,""],
			["17_lighthouse",12.5,""],["02_timber_house",22.5,"bed"],["11_purple_house",3.0,"bed"],["06_orange_cottage",19.0,""],["16_blue_cottage",7.5,""]]:
		Engine.set_meta("interior_hour",shot[1])
		var app := await open(shot[0])
		var focus := ""
		for who in app.npcs:
			var entry: Dictionary = app.npcs[who]
			if shot[2] == "bed" and entry.pose == "lie": focus = who;break
			if shot[2] != "bed" and not entry.state.asleep: focus = who
		if not focus.is_empty():
			var entry: Dictionary = app.npcs[focus]
			app.set_floor(int(entry.floor))
			var target: Dictionary = entry.talk if entry.pose == "stand" else entry.record
			app.hero.position = approach(app, target)
			app.hero.facing = (target.center-app.hero.position).normalized()
			app.update_camera(0.0,true)
			if shot[2] == "talk": app.use_decor(target)
		await create_timer(1.0).timeout
		await capture("interior-res-%s-%02d" % [shot[0],int(shot[1])])
		print("RES ",shot[0]," ",shot[1]," ",app.npcs.keys()," focus=",focus)
		await close(app)
	Engine.remove_meta("interior_hour")
	Engine.remove_meta("interior_day")

## A climb caught mid-way (and the step off at the top), plus furniture effects.
func stairs_and_effects() -> void:
	Engine.set_meta("interior_hour",13.0)
	Engine.set_meta("interior_day",preload("res://scripts/residents.gd").clock().day)
	for shot in [["home",0],["17_lighthouse",0],["05_observatory",0],["04_windmill",0],["11_purple_house",1]]:
		var app := await open(shot[0])
		app.set_floor(int(shot[1]))
		for record in app.decor:
			if not record.has("link"): continue
			app.hero.position = approach(app,record)
			app.update_camera(0.0,true)
			await create_timer(0.3).timeout
			app.travel(record)
			await create_timer(1.0).timeout
			check(app.travelling and app.hero.position.y != 0.0, "%s: walker is on the stair mid-climb" % shot[0])
			await capture("interior-stair-%s" % shot[0],0.05)
			for i in 80:
				await create_timer(0.05).timeout
				if app.floor_index != int(shot[1]): break
			await capture("interior-stair-%s-arrive" % shot[0],0.35)
			break
		await close(app)
	for shot in [["home",0,"cooking_stove"],["home",0,"kitchen_counter"],["01_cafe",0,"piano"],["17_lighthouse",2,"lighthouse_lens"],["16_blue_cottage",0,"fireplace"],
			["02_timber_house",0,"bookshelf"],["07_greenhouse",0,"potted_plant"],["home",1,"chest"],["13_shop",0,"shop_counter"],["home",0,"wall_clock"]]:
		var app := await open(shot[0])
		app.set_floor(int(shot[1]))
		for record in app.decor:
			if record.kind != shot[2] or record.has("occupant"): continue
			# Stand beside the piece (not in front of it) so the effect is in view.
			var side := Vector3(1,0,0).rotated(Vector3.UP,float(record.yaw))
			var front := Vector3(0,0,1).rotated(Vector3.UP,float(record.yaw))
			var spot: Vector3 = approach(app,record)
			for lateral in [1.0,-1.0,1.3,-1.3]:
				var at: Vector3 = record.center+front*(float(record.half.y)+0.55)+side*(float(record.half.x)+0.15)*lateral
				at.y = 0
				if app.can_stand(at): spot = at;break
			app.hero.position = spot
			app.hero.facing = (record.center-app.hero.position).normalized()
			app.update_camera(0.0,true)
			await create_timer(0.4).timeout
			app.use_decor(record)
			await capture("interior-fx-%s" % shot[2],0.35)
			break
		await close(app)
	Engine.remove_meta("interior_hour")
	Engine.remove_meta("interior_day")
