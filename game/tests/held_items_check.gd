extends SceneTree
## Carrying (#64, held_items.gd + held_pose.gd) on the shipped Player, offline: every item is taken
## out, the walker idles, walks and runs while each frame's hand-to-handle distance and the item's
## step relative to the body are measured (no pops); a tool out hides the item and putting the tool
## away brings it back; a rebuilt look keeps it; another walker shows a presence id (unknown ids
## draw empty-handed); the presence field follows /health presence_held. Windowed (--capture) it
## also saves artifacts/held_items.png: every item, idle and mid-walk, front three-quarter view.
##   godot --path game --script res://tests/held_items_check.gd [-- --capture]
const HeldItems = preload("res://scripts/held_items.gd")
const Art = preload("res://scripts/art.gd")

var failures: Array[String] = []
var passes := 0
var player: CharacterBody3D
var camera: Camera3D
var holder: Node
## Per-frame samples while measuring (filled in the skeleton's update, the final pose).
var measuring := false
var worst_grip := 0.0
var worst_step := 0.0
var worst_palm_step := 0.0
var last_model := Vector3.INF
var last_palm := Vector3.INF
var samples := 0
var tiles: Array = []

func check(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ") + label)
	if value: passes += 1
	else: failures.append(label)

func _initialize() -> void:
	call_deferred("run")

func capturing() -> bool:
	return "--capture" in OS.get_cmdline_user_args() and DisplayServer.get_name() != "headless"

func run() -> void:
	var stage := Node3D.new()
	root.add_child(stage)
	var floor := StaticBody3D.new()
	stage.add_child(floor)
	var shape := CollisionShape3D.new()
	floor.add_child(shape)
	var box := BoxShape3D.new()
	box.size = Vector3(400, 0.2, 400)
	shape.shape = box
	floor.position.y = -0.1
	Art.box(stage, Vector3(0, -0.1, 0), Vector3(400, 0.2, 400), Color("7d9a63"))
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color("a9c6cf")
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color.WHITE
	env.environment.ambient_light_energy = 0.7
	stage.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-45, 30, 0)
	sun.light_energy = 0.9
	sun.shadow_enabled = true
	stage.add_child(sun)
	camera = Camera3D.new()
	camera.fov = 32
	stage.add_child(camera)
	camera.current = true
	player = load("res://scripts/player.gd").new()
	stage.add_child(player)
	for i in 4: await physics_frame
	await process_frame
	HeldItems.adopt(null, player)
	holder = player.get_node_or_null("Held")
	check(holder != null, "the hero has a holder node")
	player.hand_skeleton.skeleton_updated.connect(_sampled)
	var pose: SkeletonModifier3D = player.hand_skeleton.get_node_or_null("HeldPose")
	check(pose != null and pose.get_index() < player.locomotion_pose.get_index(), "the held arm layer runs before locomotion_pose's limiter")
	if pose and pose.ready_for(player.hand_skeleton):
		var palm: Vector3 = pose.cfg.r.palm0
		var to_visual: Transform3D = player.visual.global_transform.affine_inverse() * player.hand_skeleton.global_transform
		print("INFO arm length %.3f m, rest palm (visual frame) %s" % [float(pose.cfg.arm), str((to_visual.basis * palm).normalized())])
	var bag := {"flower": 2, "apple": 3, "koi": 1}
	for item in HeldItems.ORDER:
		await one_item(item, bag)
	await tool_toggle()
	await look_rebuild()
	await remote_walker(stage)
	presence_rules()
	check(not HeldItems.allowed("bouquet", {}) and HeldItems.allowed("bouquet", {"sunflower": 1}) and HeldItems.allowed("umbrella", {}), "bag rules: a bouquet needs flowers, an umbrella nothing")
	check(HeldItems.pick_id("fish", {"perch": 1, "koi": 1}) == "fish_koi", "the fish shown off is the best one in the bag")
	if capturing(): save_sheet()
	print("SUMMARY held_items_check %d passed, %d failed" % [passes, failures.size()])
	for f in failures: print("FAILED: " + f)
	quit(1 if failures.size() > 0 else 0)

## Final-pose samples (the skeleton's update): hand-to-handle distance and how far the item and
## the right palm moved relative to the body since the last tick.
func _sampled() -> void:
	if not measuring or not is_instance_valid(holder) or not holder.shown: return
	var pose: SkeletonModifier3D = holder.pose
	if pose == null or pose.weight < 0.999: return
	samples += 1
	for side in holder.grip_error():
		worst_grip = maxf(worst_grip, float(holder.grip_error()[side]))
	var at: Vector3 = holder.model.position
	var palm: Vector3 = pose.palm_point(player.hand_skeleton, "r")
	if last_model.is_finite(): worst_step = maxf(worst_step, at.distance_to(last_model))
	if last_palm.is_finite(): worst_palm_step = maxf(worst_palm_step, palm.distance_to(last_palm))
	last_model = at
	last_palm = palm

func reset_metrics() -> void:
	worst_grip = 0.0
	worst_step = 0.0
	worst_palm_step = 0.0
	last_model = Vector3.INF
	last_palm = Vector3.INF
	samples = 0

func frames(n: int) -> void:
	for i in n:
		await physics_frame
		await process_frame
		frame_camera()

func frame_camera() -> void:
	var at := player.global_position
	camera.global_position = at + Vector3(1.9, 1.75, 3.5)
	camera.look_at(at + Vector3(0, 1.2, 0), Vector3.UP)

func walk(direction: String, run_fast: bool, n: int) -> void:
	player.sprinting = run_fast
	Input.action_press(direction)
	await frames(n)
	Input.action_release(direction)
	player.sprinting = false

func one_item(item: String, bag: Dictionary) -> void:
	HeldItems.hold(HeldItems.pick_id(item, bag))
	await frames(4)
	check(holder.model.scale.x < 0.9, "%s: pops in from small (scale %.2f), the placement keeps the tween's scale" % [item, holder.model.scale.x])
	await frames(26)
	check(holder.shown and is_instance_valid(holder.model) and holder.model.visible, "%s: taken out and shown" % item)
	check(HeldItems.CATALOG[item].socket in preload("res://scripts/ix/ix_schema.gd").CHARACTER_SOCKETS, "%s: sits on an ISS-1 character socket (%s)" % [item, HeldItems.CATALOG[item].socket])
	reset_metrics()
	measuring = true
	await frames(30)
	await walk("move_back", false, 90)
	await walk("move_right", true, 90)
	await walk("move_left", false, 60)
	await frames(30)
	measuring = false
	print("INFO %s: %d samples, grip %.3f m, item step %.3f m, palm step %.3f m" % [item, samples, worst_grip, worst_step, worst_palm_step])
	check(samples > 200, "%s: measured the walk (%d samples)" % [item, samples])
	check(worst_grip < 0.05, "%s: hands stay on the handles (worst %.3f m)" % [item, worst_grip])
	check(worst_step < 0.09, "%s: no pop, the item never jumps against the body (worst %.3f m a tick)" % [item, worst_step])
	if capturing():
		await face_camera()
		await shot(item + " idle")
		Input.action_press("move_back")
		await frames(50)
		await shot(item + " walk")
		Input.action_release("move_back")
		await frames(20)

func face_camera() -> void:
	player.face_point(player.global_position + Vector3(0.55, 0, 1.0))
	await frames(40)

func shot(label: String) -> void:
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	var w := image.get_width()
	var h := image.get_height()
	var crop := Rect2i(int(w * 0.5 - h * 0.34), 0, int(h * 0.68), h)
	var tile := image.get_region(crop)
	tile.resize(256, 376, Image.INTERPOLATE_BILINEAR)
	tiles.append(tile)
	print("INFO captured " + label)

func save_sheet() -> void:
	if tiles.is_empty(): return
	var columns := 4
	var rows := int(ceil(tiles.size() / float(columns)))
	var sheet := Image.create(256 * columns, 376 * rows, false, Image.FORMAT_RGBA8)
	sheet.fill(Color("1d2b30"))
	for i in tiles.size():
		var tile: Image = tiles[i]
		tile.convert(Image.FORMAT_RGBA8)
		sheet.blit_rect(tile, Rect2i(Vector2i.ZERO, tile.get_size()), Vector2i((i % columns) * 256, int(i / columns) * 376))
	var path := ProjectSettings.globalize_path("res://../artifacts/held_items.png")
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	sheet.save_png(path)
	print("INFO saved " + path)

func tool_toggle() -> void:
	HeldItems.hold("lantern")
	await frames(30)
	player.equip("watering_can")
	await frames(30)
	check(not holder.shown and holder.pose.weight == 0.0, "a tool out puts the carried thing away and frees the arm")
	await frames(10)
	check(not holder.model.visible, "the put-away item is hidden")
	player.equip("")
	await frames(30)
	check(holder.shown and holder.model.visible and holder.pose.weight >= 0.999, "putting the tool away brings it back")
	check(player.finger_pose.holding, "the right hand closes on the lantern again")
	HeldItems.hold("basket")
	await frames(30)
	check(player.finger_pose.holding_left, "a two-hand carry closes the left hand too")
	HeldItems.hold("")
	await frames(30)
	check(not holder.shown and holder.pose.weight == 0.0 and not player.finger_pose.holding and not player.finger_pose.holding_left, "putting it away releases both hands")
	check(HeldItems.hero_showing() == "", "nothing reported while empty-handed")

func look_rebuild() -> void:
	HeldItems.hold("umbrella")
	await frames(20)
	var look: Dictionary = player.avatar.duplicate(true)
	look["coat"] = "#5a7fb8"
	player.apply_avatar(look)
	await frames(30)
	if not player.hand_skeleton.skeleton_updated.is_connected(_sampled): player.hand_skeleton.skeleton_updated.connect(_sampled)
	check(holder.shown and is_instance_valid(holder.model) and holder.model.get_parent() == player.visual, "a new look keeps the umbrella in hand")
	reset_metrics()
	measuring = true
	await frames(30)
	measuring = false
	check(samples > 10 and worst_grip < 0.05, "after the rebuild the hand still holds it (%.3f m)" % worst_grip)
	check(HeldItems.hero_showing() == "umbrella", "the hero reports what it shows")

func remote_walker(stage: Node3D) -> void:
	var other: CharacterBody3D = load("res://scripts/player.gd").new()
	other.visual_only = true
	other.controls_enabled = false
	other.position = Vector3(3, 0, 0)
	stage.add_child(other)
	await frames(6)
	HeldItems.show_on(other, "fish_koi")
	await frames(20)
	var h := other.get_node_or_null("Held")
	check(h != null and h.shown and h.id == "fish_koi", "another player's presence id is drawn (fish_koi)")
	HeldItems.show_on(other, "rocket_launcher")
	await frames(20)
	check(h.id == "" and not h.shown, "an unknown id draws empty-handed")
	HeldItems.show_on(other, null)
	check(h.id == "", "no held field: empty hands")
	other.queue_free()

func presence_rules() -> void:
	var script := GDScript.new()
	script.source_code = "extends Node\nvar health := {}\n"
	script.reload()
	var hub: Node = script.new()
	root.add_child(hub)
	check(HeldItems.presence_extra(hub).is_empty(), "no presence_held in /health: held is not sent")
	hub.health = {"presence_held": 1}
	check(HeldItems.presence_extra(hub).get("held", "x") == "umbrella", "presence_held 1: held is sent")
	check(HeldItems.refused({"status": 422, "fields": ["held"]}) and HeldItems.presence_extra(hub).is_empty(), "a 422 naming held stops sending it")
	HeldItems.held_refused = false
	check(HeldItems.presence_extra(null).is_empty(), "no social layer: nothing sent")
	hub.queue_free()
