extends SceneTree
## Films the walker through a door round trip (village -> home -> village) with the
## fade veil hidden, cropping frames around the walker into one sheet, and logs the
## knee angles so a folded leg during the switch shows up as numbers too.
var frames: Array[Image] = []
var labels: Array[String] = []
var worst := {}

func _initialize() -> void:
	call_deferred("run")

func walker() -> Node3D:
	var scene := current_scene
	if scene == null: return null
	if "player" in scene and is_instance_valid(scene.player): return scene.player
	if "hero" in scene and is_instance_valid(scene.hero): return scene.hero
	return null

func knee_bend(body: Node3D) -> float:
	var skeleton: Skeleton3D = body.get("hand_skeleton") if "hand_skeleton" in body else null
	if not is_instance_valid(skeleton): return -1.0
	var most := 0.0
	for side in ["L","R"]:
		var hip := skeleton.find_bone(side+"_Thigh")
		var knee := skeleton.find_bone(side+"_Calf")
		var foot := skeleton.find_bone(side+"_Foot")
		if mini(hip,mini(knee,foot)) < 0: continue
		var a := skeleton.get_bone_global_pose(hip).origin
		var b := skeleton.get_bone_global_pose(knee).origin
		var c := skeleton.get_bone_global_pose(foot).origin
		most = maxf(most, rad_to_deg(PI-(a-b).angle_to(c-b)))
	return most

func grab(tag: String, count: int) -> void:
	for i in count:
		await process_frame
		await RenderingServer.frame_post_draw
		var body := walker()
		if body == null: continue
		var view: Camera3D = current_scene.camera if "camera" in current_scene and current_scene.camera is Camera3D and is_instance_valid(current_scene.camera) else root.get_camera_3d()
		if view == null: continue
		var bend := knee_bend(body)
		var name := "%s%d" % [tag, i]
		if bend > float(worst.get("bend", -1.0)): worst = {"bend": bend, "at": name}
		var centre := view.unproject_position(body.global_position+Vector3(0,0.9,0))
		var image := view.get_viewport().get_texture().get_image()
		var box := Rect2i(int(centre.x)-90, int(centre.y)-130, 180, 220)
		box = box.intersection(Rect2i(Vector2i.ZERO, image.get_size()))
		if box.size.x < 20 or box.size.y < 20: continue
		frames.append(image.get_region(box))
		labels.append("%s %.0f" % [name, bend])
		print("FRAME ", name, " knee=", snappedf(bend, 0.1), " pos=", body.global_position.snapped(Vector3.ONE*0.01))

func run() -> void:
	Transition_hide()
	if "--start" in OS.get_cmdline_user_args():
		# The real start: the title scene logs in, which now opens the home room.
		change_scene_to_file("res://scenes/main.tscn")
		await create_timer(2.0).timeout
		current_scene.authenticate(true, "http://127.0.0.1:8766", "start_"+str(Time.get_ticks_usec()), "Start-frames-password-1", "")
		await grab("start", 90)
		await create_timer(1.0).timeout
		await grab("settled", 6)
		sheet()
		print("WORST_KNEE ", JSON.stringify(worst))
		quit(0)
		return
	var api = load("res://scripts/api.gd").new(); root.add_child(api); api.base_url = "http://127.0.0.1:8766"
	var login: Dictionary = await api.post("/v1/auth/register", {"username":"door_"+str(Time.get_ticks_usec()), "password":"Door-frames-password-1"})
	if not login.ok: print("LOGIN_FAILED"); quit(1); return
	Engine.set_meta("studio_session", {"token":login.data.token, "url":api.base_url, "room":"home"})
	change_scene_to_file("res://scenes/main.tscn")
	await grab("in", 14)
	await create_timer(2.5).timeout
	await grab("idle", 2)
	current_scene.open_studio("home")
	await grab("out", 48)
	await create_timer(1.5).timeout
	await grab("room", 4)
	# Walk out through the doorway the way a player does.
	Input.action_press("move_back")
	await grab("walk", 60)
	Input.action_release("move_back")
	await grab("back", 30)
	sheet()
	print("WORST_KNEE ", JSON.stringify(worst))
	quit(0)

func Transition_hide() -> void:
	var veil = load("res://scripts/transition.gd").of(self)
	veil.visible = false

func sheet() -> void:
	if frames.is_empty(): return
	var columns := 16
	var rows := int(ceil(frames.size()/float(columns)))
	var out := Image.create(180*columns, 220*rows, false, Image.FORMAT_RGBA8)
	for i in frames.size():
		var frame := frames[i]
		frame.convert(Image.FORMAT_RGBA8)
		out.blit_rect(frame, Rect2i(Vector2i.ZERO, frame.get_size()), Vector2i((i%columns)*180, (i/columns)*220))
	out.save_png(ProjectSettings.globalize_path("res://../artifacts/transition-frames.png"))
	FileAccess.open(ProjectSettings.globalize_path("res://../artifacts/transition-frames.txt"), FileAccess.WRITE).store_string("\n".join(labels))
