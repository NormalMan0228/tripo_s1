extends SceneTree
## Room figures from shadow_figure.gd create_still(): every shadow resident gets a
## dressed figure with no collider; stand / sit / sit_ground / lie poses, clips,
## night, smile and pop all run. With a window (no --headless) it also writes
## artifacts/shadow-still-poses.png (one row per pose) to eyeball the poses.
##   Godot --path game --script res://tests/shadow_still_check.gd
const Figure = preload("res://scripts/shadow_figure.gd")
const Residents = preload("res://scripts/residents.gd")
var failed := false

func expect(value: bool, text: String) -> void:
	if not value:
		failed = true
		print("FAIL ", text)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var stage := Node3D.new()
	root.add_child(stage)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 30, 0)
	stage.add_child(sun)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color("c9c3b5")
	env.environment.ambient_light_color = Color(0.8, 0.8, 0.8)
	stage.add_child(env)
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(30, 30)
	floor_mesh.mesh = plane
	stage.add_child(floor_mesh)
	# Simple seat and bed blocks to read the poses against.
	for i in 4:
		var seat := MeshInstance3D.new()
		var box := BoxMesh.new()
		box.size = Vector3(0.5, 0.45, 0.5)
		seat.mesh = box
		seat.position = Vector3(-3.0+i*2.0, 0.225, 0.0)
		stage.add_child(seat)
		var bed := MeshInstance3D.new()
		var mattress := BoxMesh.new()
		mattress.size = Vector3(1.0, 0.5, 2.1)
		bed.mesh = mattress
		bed.position = Vector3(-3.0+i*2.0, 0.25, -3.2)
		stage.add_child(bed)
	expect(Figure.create_still("naru") == null, "cast ids return null")
	expect(Figure.create_still("nobody") == null, "unknown ids return null")
	var made := 0
	var ids: Array[String] = []
	for entry in Residents.RESIDENTS:
		if entry.kind == "shadow": ids.append(entry.id)
	var shown: Array = []
	var started := Time.get_ticks_usec()
	for id in ids:
		var who: Node3D = Figure.create_still(id)
		expect(who != null, "still figure for %s" % id)
		if who == null: continue
		stage.add_child(who)
		made += 1
		expect(who.find_children("*", "CollisionShape3D", true, false).is_empty(), "%s has no collider" % id)
		expect(who.collision_layer == 0 and not who.is_physics_processing(), "%s runs no physics" % id)
		expect(is_instance_valid(who.animator), "%s has an animator" % id)
		who.position = Vector3(0, -50, 0)
		who.visible = false
		shown.append(who)
	print("STILL made=", made, " in ", (Time.get_ticks_usec()-started)/1000, " ms")
	# Four on show: stand, sit on the box, sit on the floor, lie on the bed.
	var poses := ["stand", "sit", "sit_ground", "lie"]
	var picks := ["miller", "shopkeeper", "poet", "regular"]
	for i in 4:
		var who: Node3D
		for figure in shown:
			if figure.spec.id == picks[i]: who = figure
		who.visible = true
		who.set_pose(poses[i])
		match poses[i]:
			"stand": who.position = Vector3(-3.0, 0, 1.2)
			"sit": who.position = Vector3(-1.0, 0.45, 0.0)
			"sit_ground": who.position = Vector3(1.0, 0.0, 1.0)
			"lie": who.position = Vector3(3.0, 0.5, -3.2)
		who.face(0.0 if poses[i] != "lie" else PI)
		who.play_clip("idle")
		who.set_night(0.2)
		if poses[i] == "sit_ground": who.task = "write"
		if poses[i] == "stand":
			who.smile(30.0)
			who.pop("♪", 30.0)
	for figure in shown: if not figure.visible: figure.position = Vector3(0, -50, 0)
	var camera := Camera3D.new()
	camera.position = Vector3(0.5, 3.4, 7.2)
	stage.add_child(camera)
	camera.look_at(Vector3(0.5, 0.6, -1.0))
	camera.current = true
	for i in 30: await process_frame
	# Hidden figures must not animate.
	var hidden_frame: int = shown[shown.size()-1].anim_frame if not shown[shown.size()-1].visible else -1
	for i in 10: await process_frame
	if hidden_frame >= 0: expect(shown[shown.size()-1].anim_frame == hidden_frame, "hidden still does not animate")
	for figure in shown:
		if figure.visible:
			expect(figure.anim_frame > 0, "%s animates while visible" % figure.spec.id)
	# The seated hips sit on the origin; the lying body is centred on it and below 0.7 m.
	for figure in shown:
		if not figure.visible: continue
		var head: int = figure.skeleton.find_bone("Head")
		var head_y: float = (figure.skeleton.global_transform*figure.skeleton.get_bone_global_pose(head).origin).y
		print("POSE ", figure.spec.id, " ", figure.pose, " head_y=", snappedf(head_y, 0.01), " origin_y=", figure.position.y)
		if figure.pose == "lie": expect(head_y < figure.position.y+0.5, "lying head stays low")
		if figure.pose == "sit": expect(head_y > figure.position.y+0.3 and head_y < figure.position.y+1.0, "seated head height")
	if DisplayServer.get_name() != "headless":
		# Close three-quarter views of each pose.
		var index := 0
		for figure in shown:
			if not figure.visible: continue
			var at: Vector3 = figure.position
			camera.position = at+Vector3(1.6, 1.3, 2.2)
			camera.look_at(at+Vector3(0, 0.4 if figure.pose != "stand" else 0.9, 0))
			for i in 3: await process_frame
			await RenderingServer.frame_post_draw
			var out := ProjectSettings.globalize_path("res://../artifacts/shadow-still-%s.png" % figure.pose)
			root.get_texture().get_image().save_png(out)
			print("CAPTURE ", out)
			index += 1
	# Cost: 15 visible figures stepping their clips.
	for figure in shown:
		figure.visible = true
	var total := 0.0
	for i in 60:
		await process_frame
		total += Performance.get_monitor(Performance.TIME_PROCESS)
	print("STILL_TIME_PROCESS_MS per frame (15 visible, whole tree) ", snappedf(total/60.0*1000.0, 0.001))
	print("SHADOW_STILL_CHECK ", "FAIL" if failed else "OK")
	quit(1 if failed else 0)
