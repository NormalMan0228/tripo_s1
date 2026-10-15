extends SceneTree
## Tool effects land on the frame the tool meets its target (tool_contact.gd), on the real walker:
## the hoe's strike (village till), the axe's chop (expedition harvest), the watering can's pour.
## Prints when each moment came (ms after the swing started) and where the tip was, so a pose
## change (N6) can be checked; --capture (windowed) saves the hoe and can at their moments:
## artifacts/tool_contact.png.
const ToolContact := preload("res://scripts/tool_contact.gd")
const AvatarLook := preload("res://scripts/avatar_look.gd")
const Fx := preload("res://scripts/fx.gd")

var failures: Array[String] = []
var world: Node3D
var hero: CharacterBody3D
var shots: Array[Image] = []

func _initialize() -> void: call_deferred("run_test")

func check(ok: bool, what: String) -> void:
	print(("PASS " if ok else "FAIL ")+what)
	if not ok: failures.append(what)

func run_test() -> void:
	var capture := "--capture" in OS.get_cmdline_user_args()
	world = Node3D.new()
	root.add_child(world)
	hero = AvatarLook.walker({}, -1)
	hero.visual_only = true
	world.add_child(hero)
	if capture: stage()
	for i in 20: await process_frame
	await swing("hoe", "attack", Vector3(0, 0, -1.1), capture)
	await swing("axe", "gather", Vector3(0, 0.9, -1.0), false)
	# the watering can pours from its spout toward the bed
	hero.equip("watering_can")
	hero.face_point(Vector3(0, 0, -1.2))
	for i in 5: await process_frame
	hero.react("craft")
	var drops := [0]
	var first := [-1]
	var started := Time.get_ticks_msec()
	ToolContact.pour(hero, Vector3(0, 0.15, -1.2), func(from: Vector3, to: Vector3):
		drops[0] += 1
		if first[0] < 0: first[0] = Time.get_ticks_msec()-started
		Fx.pour(world, from, to, 3))
	await wait(0.6)
	if capture: shots.append(await shot())
	await wait(0.8)
	var tip := ToolContact.tip(hero)
	print("POUR first_drop_ms=%d drops=%d tip=%s" % [first[0], drops[0], str(tip)])
	check(drops[0] >= 5, "the can pours several times (%d)" % drops[0])
	check(first[0] >= 0 and first[0] <= 450, "the pour starts within 0.45 s (%d ms)" % first[0])
	if capture: save()
	print("TOOL_CONTACT %s failures=%d" % ["PASS" if failures.is_empty() else "FAIL", failures.size()])
	quit(0 if failures.is_empty() else 1)

func swing(tool: String, kind: String, target: Vector3, capture: bool) -> void:
	hero.equip(tool)
	hero.face_point(Vector3(target.x, 0, target.z))
	for i in 8: await process_frame
	var tip0 := ToolContact.tip(hero)
	check(tip0 != Vector3.INF, "%s: a tip is found (%s)" % [tool, str(tip0)])
	hero.react(kind)
	var started := Time.get_ticks_msec()
	var hit := [Vector3.INF, -1]
	ToolContact.strike(hero, target, func(p: Vector3):
		hit[0] = p
		hit[1] = Time.get_ticks_msec()-started
		Fx.burst(world, p, "dust", 10))
	while hit[1] < 0 and Time.get_ticks_msec()-started < 1500: await process_frame
	if capture and hit[1] >= 0: shots.append(await shot())
	print("STRIKE %s at_ms=%d point=%s tip_now=%s" % [tool, hit[1], str(hit[0]), str(ToolContact.tip(hero))])
	check(hit[1] >= 0 and hit[1] <= 750, "%s: the moment comes within the swing (%d ms)" % [tool, hit[1]])
	await wait(0.7)

func wait(seconds: float) -> void:
	var until := Time.get_ticks_msec()+int(seconds*1000.0)
	while Time.get_ticks_msec() < until: await process_frame

func stage() -> void:
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -30, 0)
	world.add_child(sun)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color("8fb3cf")
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color("c9d6e0")
	env.environment.ambient_light_energy = 0.6
	world.add_child(env)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(10, 10)
	ground.mesh = plane
	var m := StandardMaterial3D.new()
	m.albedo_color = Color("8d7152")
	ground.material_override = m
	world.add_child(ground)
	var cam := Camera3D.new()
	cam.fov = 40
	world.add_child(cam)
	# From the side, so the tool's path down to the ground reads.
	cam.look_at_from_position(Vector3(3.2, 1.3, -0.5), Vector3(0, 0.7, -0.6))
	cam.current = true

func shot() -> Image:
	await RenderingServer.frame_post_draw
	return root.get_texture().get_image()

func save() -> void:
	if shots.is_empty(): return
	var w := shots[0].get_width()
	var h := shots[0].get_height()
	var crop := Rect2i(w/5, 0, w*3/5, h)
	var sheet := Image.create(crop.size.x*shots.size(), h, false, shots[0].get_format())
	for i in shots.size(): sheet.blit_rect(shots[i], crop, Vector2i(crop.size.x*i, 0))
	var path := ProjectSettings.globalize_path("res://../artifacts/tool_contact.png")
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	print("SHEET ", sheet.save_png(path), " ", path)
