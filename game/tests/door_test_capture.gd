extends SceneTree
## Door test captures at noon (maps/archipelago/building_doors.gd, interiors.gd front()). Needs a window.
## Images go to --out=DIR (default artifacts/mapdoor/door_test), named "<label>_..." (--label=NAME).
##   (default)   village doors close up from in front (QA server: --server=URL): EXTERIOR ids; a door
##               with a leaf also half open, open and a thickness close-up from its hinge side, and
##               closed against the building without it ("..._plain.png": the pixels that differ are
##               reported as closed_changed_pixels_<id>).
##   --before    every door as one picture, as the game has it (run with --no-doors: the doors as
##               they were before building_doors.gd).
##   --interior  the rooms of INTERIOR without a server, looking at the front door from inside; a room
##               whose FrontDoor is a leaf from its building also closed and half open, and a close-up.
## Prints DOOR_TEST_CAPTURE {...}.
const Town = preload("res://scripts/town.gd")
const Doors = preload("res://maps/archipelago/building_doors.gd")
const Interiors = preload("res://scripts/interiors.gd")
const Dressing = preload("res://scripts/building_dressing.gd")
var EXTERIOR := ["10_red_house", "01_cafe", "11_purple_house"]
var INTERIOR := ["home", "01_cafe", "11_purple_house"]
var app: Node
var out_dir := "res://../artifacts/mapdoor/door_test/"
var label := "cap"
var report := {"shots": []}

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="): out_dir = arg.trim_prefix("--out=").trim_suffix("/")+"/"
		if arg.begins_with("--label="): label = arg.trim_prefix("--label=")
		if arg.begins_with("--doors="): EXTERIOR = Array(arg.trim_prefix("--doors=").split(","))
		if arg.begins_with("--rooms="): INTERIOR = Array(arg.trim_prefix("--rooms=").split(","))
	call_deferred("run")

func run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_dir))
	if "--interior" in OS.get_cmdline_user_args(): await interiors()
	else: await exterior()
	print("DOOR_TEST_CAPTURE ", JSON.stringify(report))
	quit(0)

func exterior() -> void:
	if not await enter_village():
		quit(1)
		return
	app.player.process_mode = Node.PROCESS_MODE_DISABLED
	Engine.time_scale = 0.0
	var props: Node = app.town.map.get_node_or_null("Environment")
	if props: props.floating_boats.clear()
	app.warming = true
	app.daylight.override_hour = 12.0
	app.daylight.refresh(true)
	Dressing.update(app.town.map, 12.0)
	for i in 4: await process_frame
	# Trees and bushes in front of a door would hide it: the props stay out of these pictures.
	if props: props.visible = false
	for id in EXTERIOR:
		var door := Town.DOORS.filter(func(d): return d.id == id)[0] as Dictionary
		var leaf := Doors.door_leaf(id)
		look_at_door(door, 3.6, 0.0)
		if leaf == null or "--before" in OS.get_cmdline_user_args():
			await shot("%s_ext_%s.png" % [label, id])
			continue
		# Closed, against the building without its door nodes (the painted door as it was).
		Doors.set_door_open(id, 0.0)
		var opening := Doors.door_opening(id)
		leaf.visible = false
		opening.visible = false
		var plain := await shot("%s_ext_%s_plain.png" % [label, id])
		leaf.visible = true
		opening.visible = true
		for amount in [0.0, 0.5, 1.0]:
			Doors.set_door_open(id, amount)
			var image := await shot("%s_ext_%s_%s.png" % [label, id, ["closed", "half", "open"][int(amount*2)]])
			if amount == 0.0: report["closed_changed_pixels_"+id] = differ(plain, image)
		# Thickness: the leaf half open, close on its free edge from the side it swings to.
		Doors.set_door_open(id, 0.5)
		var size := Doors.leaf_size(id)
		var edge: Vector3 = leaf.global_transform*Vector3(-size.x, 1.2, -size.z*0.5)
		var across: Vector3 = (leaf.get_parent() as Node3D).global_basis.x
		app.camera.size = 1.3
		app.camera.position = edge-across*3.5+(leaf.get_parent() as Node3D).global_basis.z*6.0+Vector3(0, 2.0, 0)
		app.camera.look_at(edge)
		await shot("%s_ext_%s_thickness.png" % [label, id])
		Doors.set_door_open(id, 0.0)
	if props: props.visible = true
	Engine.time_scale = 1.0

## The camera square in front of the door (yaw_degrees turns it round the door), looking a little down.
func look_at_door(door: Dictionary, size: float, yaw_degrees: float) -> void:
	var at: Vector2 = door.at
	var out: Vector2 = (at-Vector2(door.center)).normalized().rotated(deg_to_rad(yaw_degrees))
	var leaf := Doors.door_leaf(String(door.id))
	var focus: Vector3 = Town.point(at, 1.2)
	if leaf: focus = leaf.global_transform*Vector3(-Doors.leaf_size(String(door.id)).x*0.5, 1.1, 0)
	app.camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	app.camera.size = size
	app.camera.position = focus+Vector3(out.x, 0, out.y)*10.0+Vector3(0, 3.0, 0)
	app.camera.look_at(focus)

func interiors() -> void:
	for room in INTERIOR:
		Engine.set_meta("interior_hour", 12.0)
		Engine.set_meta("studio_session", {"token":"", "url":"http://127.0.0.1:9", "room":room})
		var studio: Control = load("res://scenes/studio.tscn").instantiate()
		root.add_child(studio)
		await create_timer(2.0).timeout
		if "hero" in studio and is_instance_valid(studio.hero): studio.hero.visible = false
		for layer in studio.find_children("*", "CanvasLayer", true, false): layer.visible = false
		var hinge: Node3D = null
		for node in studio.find_children("FrontDoor", "Node3D", true, false):
			if (node as Node3D).is_visible_in_tree(): hinge = node
		if hinge == null:
			print("NO_FRONT_DOOR ", room)
		else:
			var floor_root := hinge.get_parent() as Node3D
			var camera := Camera3D.new()
			floor_root.add_child(camera)
			camera.fov = 50.0
			camera.current = true
			if hinge.has_meta("door_leaf"):
				for amount in [0.0, 0.5, 1.0]:
					Interiors.set_front_door_open(floor_root, amount)
					aim(camera, hinge, Vector3(1.4, 2.4, 3.6))
					await shot("%s_int_%s_%s.png" % [label, room, ["closed", "half", "open"][int(amount*2)]])
				Interiors.set_front_door_open(floor_root, 0.5)
				aim(camera, hinge, Vector3(1.6, 1.5, 1.4))
				await shot("%s_int_%s_thickness.png" % [label, room])
				# The closed door between the camera and the walker fades (door_fade.gd).
				if "hero" in studio and is_instance_valid(studio.hero):
					Interiors.set_front_door_open(floor_root, 0.0)
					aim(camera, hinge, Vector3(1.4, 2.4, 3.6))
					studio.hero.visible = true
					studio.hero.global_position = floor_root.to_global(hinge.position+Vector3(-Interiors.DOOR_HALF, 0.0, -1.3))
					await create_timer(0.8).timeout
					await shot("%s_int_%s_fade.png" % [label, room])
					studio.hero.visible = false
				Interiors.set_front_door_open(floor_root, 1.0)
			else:
				aim(camera, hinge, Vector3(1.4, 2.4, 3.6))
				await shot("%s_int_%s.png" % [label, room])
		studio.queue_free()
		for i in 3: await process_frame
	Engine.remove_meta("interior_hour")

## The camera at `offset` from the doorway's middle (room space: the doorway lies along -x of the hinge,
## the room towards -z, the camera's side of the room +z), looking at it.
func aim(camera: Camera3D, hinge: Node3D, offset: Vector3) -> void:
	var middle: Vector3 = hinge.position+Vector3(-Interiors.DOOR_HALF, 1.0, -0.3)
	camera.position = middle+offset
	camera.look_at(hinge.get_parent().to_global(middle), Vector3.UP)

func enter_village() -> bool:
	var api = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = preload("res://tests/qa_server.gd").url()
	var login: Dictionary = await api.post("/v1/auth/register", {"username":"doortest_"+str(Time.get_ticks_usec()), "password":"Door-test-password-1"})
	if not login.ok:
		print("LOGIN_FAILED")
		return false
	Engine.set_meta("studio_session", {"token":login.data.token, "url":api.base_url, "room":"home"})
	change_scene_to_file("res://scenes/main.tscn")
	var deadline := Time.get_ticks_msec()+90000
	while Time.get_ticks_msec() < deadline and not (is_instance_valid(current_scene) and current_scene.get("screen") == "village" and is_instance_valid(current_scene.get("player"))):
		await process_frame
	app = current_scene
	if not is_instance_valid(app) or app.get("screen") != "village": return false
	await create_timer(4.0).timeout
	for layer in app.find_children("*", "CanvasLayer", true, false): layer.visible = false
	for control in app.get_children():
		if control is Control: control.visible = false
	app.player.visible = false
	return true

func shot(file: String) -> Image:
	for i in 6: await process_frame
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	image.save_png(ProjectSettings.globalize_path(out_dir+file))
	report.shots.append(file)
	return image

## Pixels whose colour differs by more than 2/255 in any channel.
static func differ(a: Image, b: Image) -> int:
	if a.get_size() != b.get_size(): return -1
	var data_a := a.get_data()
	var data_b := b.get_data()
	var step := 4 if a.get_format() == Image.FORMAT_RGBA8 else 3
	var count := 0
	for i in range(0, data_a.size(), step):
		if absi(data_a[i]-data_b[i]) > 2 or absi(data_a[i+1]-data_b[i+1]) > 2 or absi(data_a[i+2]-data_b[i+2]) > 2: count += 1
	return count
