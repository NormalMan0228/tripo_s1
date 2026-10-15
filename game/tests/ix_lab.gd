extends SceneTree
## ISS-1 interaction lab (S-WP5). Every case runs the whole cycle on the shipped Player through the
## rest_seat facade (walk up, align, sit or lie down, hold, get up) and is measured: contact error in
## HOLD, the biggest body / visual-yaw / joint step per tick, seconds from E to seated, the exit
## spot's clearance. Cases: box seats 0.30/0.45/0.72 at yaw 0/90/217 from three directions, room
## kinds (chair, sofa, bed), crafted fixtures (rocking chair rocking, bed, bench, sofa), the chair at
## 50/200 % width and mirrored, and the map's bench, café chair, picnic table and lounger.
##   headless: godot --headless --path game --script res://tests/ix_lab.gd       -> artifacts/ix/lab.json
##   windowed: godot --path game --script res://tests/ix_lab.gd -- --capture     -> + artifacts/ix/ix_sheet.jpg
## The windowed run captures only the sheet cases (crafted chair, bed, village bench), 4 frames for
## sitting down and 4 for getting up, as one contact sheet.
const Kit = preload("res://tests/ix_fixture_kit.gd")
const IxRig = preload("res://scripts/ix/ix_rig.gd")
const IxMath = preload("res://scripts/ix/ix_math.gd")
const IxSources = preload("res://scripts/ix/ix_sources.gd")
const Driver = preload("res://scripts/ix/ix_driver.gd")
const ObjectTransform = preload("res://scripts/object_transform.gd")
const Interiors = preload("res://scripts/interiors.gd")
const CraftCollision = preload("res://scripts/craft_collision.gd")
const PROPS := {"26_bench": "res://maps/archipelago/assets/environment/bench.glb", "32_cafe_chair": "res://maps/archipelago/assets/environment/cafe_chair.glb",
	"25_picnic_table": "res://maps/archipelago/assets/environment/picnic_table.glb", "29_beach_lounger": "res://maps/archipelago/assets/environment/beach_lounger.glb"}
const THUMB := Vector2i(300, 200)

var capture := false
var stage: Node3D
var player: CharacterBody3D
var seat: Node
var camera: Camera3D
var caption: Label
var results: Array = []
var joint_step := 0.0
var last_rot := {}
var contact := Vector3.ZERO
var hips := Vector3.ZERO
var frames: Array = []

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	capture = "--capture" in OS.get_cmdline_user_args()
	build_stage()
	for i in 6: await physics_frame
	player.locomotion_pose.modification_processed.connect(_sampled)
	var arch := Kit.archetypes()
	if capture:
		await sheet_case("crafted chair · 의자", place(Kit.build(arch.seat), Vector3.ZERO, 25.0), "sit")
		await sheet_case("crafted bed · 침대", place(Kit.build(arch.bed), Vector3.ZERO, -20.0), "lie")
		var bench := prop("26_bench")
		if bench != null: await sheet_case("village bench · 마을 벤치", place(bench, Vector3.ZERO, 30.0), "sit")
		save_sheet()
	else:
		for height in [0.30, 0.45, 0.72]:
			for yaw in [0.0, 90.0, 217.0]:
				for dir in [[1.2, 0.0], [0.6, 1.1], [-0.4, 1.3]]:
					var node := place(Kit.build(Kit.box_chair(height)), Vector3.ZERO, yaw)
					await measure("box_%02d_yaw%d_dir%d" % [int(height * 100), int(yaw), results.size() % 3], node, "sit", dir)
		for kind in ["wooden_chair", "sofa", "bed"]:
			var record := Interiors.place(stage, {"kind": kind, "at": Vector3.ZERO, "yaw": 15.0}, Interiors.spec("home").floors[0], 0)
			await measure("room_" + kind, record.node, "lie" if kind == "bed" else "sit", [1.3, 0.3], record)
		for id in ["rocking_chair", "bed", "bench", "sofa"]:
			await measure("craft_" + id, place(Kit.build(arch[id]), Vector3.ZERO, 40.0), str(arch[id].rest), [1.2, 0.3], {}, id == "rocking_chair")
		for shape in [{"width": 50}, {"width": 200}, {"mirror": true}, {"height": 150, "depth": 120}]:
			var node := place(Kit.build(arch.seat), Vector3.ZERO, 60.0)
			ObjectTransform.apply(node, shape)
			await measure("shape_" + str(shape).replace(" ", "").replace("\"", ""), node, "sit", [1.2, 0.2])
		for id in PROPS:
			var node := prop(id)
			if node == null: continue
			await measure("prop_" + id, place(node, Vector3.ZERO, 10.0), "lie" if id == "29_beach_lounger" else "sit", [1.4, 0.5] if id != "25_picnic_table" else [0.2, 1.6])
	var ok := results.all(func(r): return bool(r.ok))
	var out := ProjectSettings.globalize_path("res://../artifacts/ix")
	DirAccess.make_dir_recursive_absolute(out)
	if not capture:
		var f := FileAccess.open(out.path_join("lab.json"), FileAccess.WRITE)
		f.store_string(JSON.stringify({"ok": ok, "cases": results}, " "))
		f.close()
	var worst := {"contact_cm": 0.0, "step_m": 0.0, "yaw_rad": 0.0, "joint_deg": 0.0, "seconds": 0.0}
	for r in results:
		for key in worst: worst[key] = maxf(float(worst[key]), float(r.get(key, 0.0)))
	print("IX_LAB ", JSON.stringify({"ok": ok, "cases": results.size(), "failed": results.filter(func(r): return not r.ok).map(func(r): return [r.case, r.why]), "worst": worst}))
	quit(0 if ok else 1)

func build_stage() -> void:
	stage = Node3D.new()
	root.add_child(stage)
	var environment := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("cfe3e8")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("dfe8ea")
	env.ambient_light_energy = 0.7
	environment.environment = env
	stage.add_child(environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-55, 35, 0)
	sun.light_energy = 1.1
	sun.shadow_enabled = true
	stage.add_child(sun)
	Kit.floor_body(stage)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(30, 30)
	ground.mesh = plane
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color("a9c49a")
	ground.material_override = mat
	stage.add_child(ground)
	camera = Camera3D.new()
	camera.fov = 38.0
	stage.add_child(camera)
	camera.current = true
	player = load("res://scripts/player.gd").new()
	stage.add_child(player)
	seat = load("res://scripts/rest_seat.gd").new()
	stage.add_child(seat)
	seat.keep_height = true
	seat.hero = player
	if capture:
		var layer := CanvasLayer.new()
		stage.add_child(layer)
		caption = Label.new()
		caption.position = Vector2(14, 10)
		caption.add_theme_font_size_override("font_size", 64)
		caption.add_theme_color_override("font_color", Color("1f2a30"))
		caption.add_theme_color_override("font_outline_color", Color(1, 1, 1, 0.9))
		caption.add_theme_constant_override("outline_size", 14)
		layer.add_child(caption)

func place(node: Node3D, at: Vector3, yaw: float) -> Node3D:
	stage.add_child(node)
	node.position = at
	node.rotation_degrees.y = yaw
	return node

## A map prop as the village places it: its placement spec (for the socket data) and collision.
func prop(id: String) -> Node3D:
	if not ResourceLoader.exists(PROPS[id]): return null
	var node := (load(PROPS[id]) as PackedScene).instantiate() as Node3D
	node.set_meta("placement_spec", {"id": id})
	var body := StaticBody3D.new()
	body.collision_layer = 8
	for b in CraftCollision.boxes_for(node):
		var shape := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = b.size
		shape.shape = box
		shape.position = b.get_center()
		body.add_child(shape)
	node.add_child(body)
	return node

## Starts the walker beside the thing (dir: [metres in front, metres to the side] in its frame).
func stand_near(node: Node3D, dir: Array) -> void:
	var front := IxMath.dir_of(node.global_rotation.y)
	var side := front.cross(Vector3.UP)
	var at: Vector3 = node.global_position + front * float(dir[0]) + side * float(dir[1])
	player.global_position = Vector3(at.x, 0.02, at.z)
	player.velocity = Vector3.ZERO
	player.facing = (node.global_position - at).normalized().rotated(Vector3.UP, 1.1)
	for i in 10: await physics_frame

func measure(label: String, node: Node3D, hint: String, dir: Array, record := {}, rock := false) -> void:
	await stand_near(node, dir)
	var row := {"case": label, "ok": false, "why": ""}
	joint_step = 0.0
	last_rot.clear()
	var started := Time.get_ticks_msec()
	if record.is_empty(): seat.crafted(node, hint)
	elif hint == "lie": seat.lie(record)
	else: seat.sit(record)
	var d: Node = seat.driver
	if not is_instance_valid(d) or not d.busy():
		row.why = "no start (%s)" % (d.why if is_instance_valid(d) else "")
		await finish_case(row, node)
		return
	var step := 0.0
	var turn := 0.0
	var last_pos: Vector3 = player.global_position
	var last_yaw: float = player.visual.rotation.y
	var seated := -1.0
	var worst_contact := 0.0
	var t := 0.0
	while t < 9.0:
		await physics_frame
		t += 1.0 / 60.0
		step = maxf(step, player.global_position.distance_to(last_pos))
		turn = maxf(turn, absf(angle_difference(last_yaw, player.visual.rotation.y)))
		last_pos = player.global_position
		last_yaw = player.visual.rotation.y
		if d.state == Driver.HOLD:
			if seated < 0.0: seated = (Time.get_ticks_msec() - started) / 1000.0
			if rock: node.whole_root.rotation.x = 0.12 * sin(t * 4.0)
			var point := IxSources.point_now(d.entry)
			var measured: Vector3 = (hips - Vector3(0, IxRig.LIE_LIFT, 0)) if d.kind == "lie" else contact
			if t - seated > 0.1: worst_contact = maxf(worst_contact, measured.distance_to(point))
			if seated > 0.0 and (Time.get_ticks_msec() - started) / 1000.0 > seated + 0.6:
				if rock: node.whole_root.rotation.x = 0.0
				seat.stand()
		if seated > 0.0 and not d.busy(): break
	row.merge({"seconds": seated, "contact_cm": worst_contact * 100.0, "step_m": maxf(step, d.max_step), "yaw_rad": turn, "joint_deg": joint_step,
		"type": str(d.socket.get("type", "")), "variant": d.variant, "height": snappedf(float(d.socket.get("height", 0.0)), 0.001), "source": str(d.socket.get("source", "")),
		"phases": d.phases, "exit_free": d.spot_free(player.global_position), "exit_off_m": Vector2(player.global_position.x - d.exit_point.x, player.global_position.z - d.exit_point.z).length()})
	var why: Array = []
	if seated < 0.0: why.append("never seated " + str(d.phases))
	if d.busy(): why.append("still busy")
	if worst_contact > 0.03: why.append("contact")
	if row.step_m > 0.08: why.append("step")
	if turn > 0.35: why.append("yaw")
	if joint_step >= 25.0: why.append("joint")
	if not row.exit_free: why.append("exit overlaps")
	row.ok = why.is_empty()
	row.why = ", ".join(why)
	await finish_case(row, node)

func finish_case(row: Dictionary, node: Node3D) -> void:
	if is_instance_valid(seat.driver) and seat.driver.busy(): seat.driver.abort("lab")
	results.append(row)
	print("CASE ", JSON.stringify(row))
	if is_instance_valid(node): node.queue_free()
	player.global_position = Vector3(6, 0.02, 6)
	for i in 8: await physics_frame

## A windowed case for the contact sheet: four frames sitting down, four getting up.
func sheet_case(title: String, node: Node3D, hint: String) -> void:
	await stand_near(node, [1.25, 0.55])
	var row: Array = []
	seat.crafted(node, hint)
	var d: Node = seat.driver
	# Looking at the seat from its front (where the user's chest faces), a little to the side.
	var front: Vector3 = d.socket.basis.z if d.busy() else IxMath.dir_of(node.global_rotation.y)
	var side := front.cross(Vector3.UP)
	var focus: Vector3 = (d.socket.origin if d.busy() else node.global_position) + Vector3(0, 0.15, 0)
	camera.global_position = focus + front * 2.9 + side * 1.6 + Vector3(0, 1.5, 0)
	camera.look_at(focus + Vector3(0, 0.1, 0))
	var shots := {}
	var t := 0.0
	var stood_at := -1.0
	while t < 9.0:
		await physics_frame
		t += 1.0 / 60.0
		var tag := ""
		match d.state:
			Driver.APPROACH:
				if not shots.has("a") and d.state_time > 0.15: tag = "a"
			Driver.ALIGN:
				if not shots.has("b") and d.state_time > 0.12: tag = "b"
			Driver.ENTER:
				if not shots.has("c") and d.state_time > (0.65 if d.kind == "lie" else 0.25): tag = "c"
			Driver.HOLD:
				if not shots.has("d") and d.state_time > 0.35: tag = "d"
				elif shots.has("d") and d.state_time > 0.8: seat.stand()
			Driver.EXIT:
				if not shots.has("e") and d.state_time > 0.08: tag = "e"
				elif not shots.has("f") and d.state_time > (0.5 if d.kind == "lie" else 0.2): tag = "f"
				elif not shots.has("g") and d.state_time > (0.75 if d.kind == "lie" else 0.36): tag = "g"
			Driver.IDLE:
				if shots.has("d"):
					if stood_at < 0.0: stood_at = t
					if not shots.has("h") and t - stood_at > 0.3: tag = "h"
		if tag.is_empty(): continue
		var names := {"a": "걸어가기", "b": "돌아서기", "c": "앉는 중" if d.kind != "lie" else "눕는 중", "d": "앉음" if d.kind != "lie" else "누움",
			"e": "일어나기 시작", "f": "일어나는 중", "g": "발 딛기", "h": "서기"}
		caption.text = "%s · %s" % [title, names[tag]]
		await RenderingServer.frame_post_draw
		var image := root.get_texture().get_image()
		image.resize(THUMB.x, THUMB.y, Image.INTERPOLATE_BILINEAR)
		shots[tag] = image
		if shots.size() == 8: break
	for tag in ["a", "b", "c", "d", "e", "f", "g", "h"]: row.append(shots.get(tag))
	frames.append(row)
	if d.busy(): d.abort("lab")
	node.queue_free()
	for i in 10: await physics_frame

func save_sheet() -> void:
	var sheet := Image.create(THUMB.x * 8, THUMB.y * frames.size(), false, Image.FORMAT_RGB8)
	sheet.fill(Color("f4f1ea"))
	for y in frames.size():
		for x in 8:
			var shot = frames[y][x]
			if shot == null: continue
			var img: Image = shot
			img.convert(Image.FORMAT_RGB8)
			sheet.blit_rect(img, Rect2i(Vector2i.ZERO, THUMB), Vector2i(x * THUMB.x, y * THUMB.y))
	var path := ProjectSettings.globalize_path("res://../artifacts/ix/ix_sheet.jpg")
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	sheet.save_jpg(path, 0.82)
	print("IX_SHEET ", path, " ", FileAccess.get_file_as_bytes(path).size())

func _sampled() -> void:
	var skel: Skeleton3D = player.hand_skeleton
	if not is_instance_valid(skel): return
	contact = IxRig.socket_global(skel, "seat_contact", player.visual).origin
	hips = skel.global_transform * skel.get_bone_global_pose(IxRig.bone(skel, "Hips")).origin
	if not is_instance_valid(seat.driver) or not seat.driver.busy():
		last_rot.clear()
		return
	for i in skel.get_bone_count():
		if skel.get_bone_name(i).begins_with("Face_"): continue
		var q := skel.get_bone_pose_rotation(i)
		if last_rot.has(i): joint_step = maxf(joint_step, rad_to_deg((last_rot[i] as Quaternion).angle_to(q)))
		last_rot[i] = q
