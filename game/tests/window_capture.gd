extends SceneTree
## Captures for the window sky gradient (scripts/window_sky.gd): exterior glass (building_exterior
## .gdshader) and interior window views (interiors.gd WINDOW_SHADER). Needs a window. Images go to
## --out=DIR (default artifacts/mapdoor/windows), named "<label>_..." (--label=NAME, default "cap").
##   (default)   the village from the game's camera at buildings with many windows, at noon, sunset
##               and night (time held still); needs a QA server (--server=URL).
##   --interior  rooms opened without a server (like interior_tour.gd) at noon, sunset and night,
##               a camera square in front of a window ("<label>_in_<room>_h<hour>.png").
## Prints WINDOW_CAPTURE {...}.
const Town = preload("res://scripts/town.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const Dressing = preload("res://scripts/building_dressing.gd")
const HOURS := [12.0, 18.6, 22.0]
var BUILDINGS := ["01_cafe", "12_blue_house", "11_purple_house", "16_blue_cottage", "07_greenhouse", "10_red_house"]
var ROOMS := ["home", "17_lighthouse", "12_blue_house"]
var app: Node
var out_dir := "res://../artifacts/mapdoor/windows/"
var label := "cap"
var report := {"shots": 0}
var hours: Array = HOURS

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="): out_dir = arg.trim_prefix("--out=").trim_suffix("/")+"/"
		if arg.begins_with("--label="): label = arg.trim_prefix("--label=")
		if arg.begins_with("--buildings="): BUILDINGS = Array(arg.trim_prefix("--buildings=").split(","))
		if arg.begins_with("--rooms="): ROOMS = Array(arg.trim_prefix("--rooms=").split(","))
		if arg.begins_with("--hours="): hours = Array(arg.trim_prefix("--hours=").split(",")).map(func(h): return float(h))
	call_deferred("run")

func run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_dir))
	if "--interior" in OS.get_cmdline_user_args(): await interiors()
	else: await exterior()
	print("WINDOW_CAPTURE ", JSON.stringify(report))
	quit(0)

func exterior() -> void:
	if not await enter_village():
		quit(1)
		return
	app.player.process_mode = Node.PROCESS_MODE_DISABLED
	Engine.time_scale = 0.0
	var props: Node = app.town.map.get_node_or_null("Environment")
	if props:
		props.floating_boats.clear()
		props.visible = false
	app.warming = true
	for hour in HOURS:
		app.daylight.override_hour = hour
		app.daylight.refresh(true)
		Dressing.update(app.town.map, hour)
		for i in 4: await process_frame
		for id in BUILDINGS:
			var door := Town.DOORS.filter(func(d): return d.id == id)[0] as Dictionary
			facade(door)
			# Before: the building's own glass as painted (the whole-pane glass hidden); after: with it.
			var glass: Node3D = app.town.map.get_node_or_null("Buildings/%s/WindowGlass" % id)
			if glass:
				glass.visible = false
				await shot("%s_out_%s_h%s_before.png" % [label, id, str(hour)])
				glass.visible = true
			await shot("%s_out_%s_h%s.png" % [label, id, str(hour)])
	Engine.time_scale = 1.0

func interiors() -> void:
	for room in ROOMS:
		for hour in hours:
			Engine.set_meta("interior_hour", hour)
			Engine.set_meta("studio_session", {"token":"", "url":"http://127.0.0.1:9", "room":room})
			var studio: Control = load("res://scenes/studio.tscn").instantiate()
			root.add_child(studio)
			await create_timer(1.6).timeout
			# The room as the game shows it (its own camera; walker and HUD hidden): every window view
			# in sight, the ones that float off the walls included.
			if "hero" in studio and is_instance_valid(studio.hero): studio.hero.visible = false
			for layer in studio.find_children("*", "CanvasLayer", true, false): layer.visible = false
			await shot("%s_room_%s_h%s.png" % [label, room, str(hour)])
			var view := first_view(studio)
			if view:
				var camera := Camera3D.new()
				view.get_parent().add_child(camera)
				var normal := view.global_basis.z.normalized()
				camera.global_position = view.global_position+normal*1.6
				camera.look_at(view.global_position, Vector3.UP)
				camera.fov = 55.0
				camera.current = true
				await shot("%s_in_%s_h%s.png" % [label, room, str(hour)])
			else: print("NO_WINDOW ", room)
			studio.queue_free()
			for i in 3: await process_frame
	Engine.remove_meta("interior_hour")

func first_view(studio: Node) -> Node3D:
	for view in get_nodes_in_group("window_view"):
		if studio.is_ancestor_of(view) and (view as Node3D).is_visible_in_tree(): return view
	return null

func enter_village() -> bool:
	var api = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = preload("res://tests/qa_server.gd").url()
	var login: Dictionary = await api.post("/v1/auth/register", {"username":"windows_"+str(Time.get_ticks_usec()), "password":"Window-capture-password-1"})
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

## The building's door side square on, the whole facade in view.
func facade(door: Dictionary) -> void:
	var at: Vector2 = door.at
	var out: Vector2 = (at-Vector2(door.center)).normalized()
	var focus: Vector3 = Town.point(at, 2.6)
	app.camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	app.camera.size = 10.0
	app.camera.position = focus+Vector3(out.x, 0, out.y)*14.0+Vector3(0, 6.0, 0)
	app.camera.look_at(focus)

func place(at: Vector2, zoom: float) -> void:
	var focus: Vector3 = Town.point(at, 0.1)+Profile.CAMERA_FOCUS_OFFSET+Vector3(0, 2.0, 0)
	app.camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	app.camera_focus = focus
	app.camera_focus_ready = true
	app.camera_zoom_active = false
	app.camera.size = zoom
	app.camera.position = focus+Profile.CAMERA_OFFSET*Profile.CAMERA_PULLBACK
	app.camera.look_at(focus)

func shot(file: String) -> void:
	for i in 6: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path(out_dir+file))
	report.shots += 1
