extends SceneTree
## Which colliders make the walker's move_and_slide slow at a village spot (perf_scenes found
## 16 ms ticks by the pond): the real game screen against recorded replies, then every collision
## shape within RADIUS of --at=x,z with its type, face count and owner, and the time of a probe
## test_move there.   godot --headless --path game --script res://tests/collider_probe.gd -- --qa --at=-36.3,45.3
const Main = preload("res://scripts/main.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
const I18n = preload("res://scripts/i18n.gd")
const RADIUS := 4.0

func _initialize() -> void: call_deferred("run")

func run() -> void:
	I18n.setup()
	var at := Vector2(-36.3, 45.3)
	for item in OS.get_cmdline_user_args():
		if item.begins_with("--at="):
			var parts := item.trim_prefix("--at=").split(",")
			at = Vector2(float(parts[0]), float(parts[1]))
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	fixture["/v1/social/presence"] = {"self_id":"me", "host_id":"me", "host_name":"haneul", "visiting":false, "party":null, "invites":[],
		"pending_rewards":[], "village":{"players":[{"id":"me", "username":"haneul", "x":0, "z":0}]}, "messages":[]}
	var app = Main.new()
	root.add_child(app)
	await create_timer(1.6).timeout
	app.api.queue_free()
	var stub = Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	await app.enter_village()
	await create_timer(3.0).timeout
	var player: CharacterBody3D = app.player
	var space := player.get_world_3d().direct_space_state
	var ball := SphereShape3D.new()
	ball.radius = RADIUS
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = ball
	query.collision_mask = player.collision_mask
	var ground: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(at.x, 60, at.y), Vector3(at.x, -20, at.y), 1|2))
	var y: float = ground.position.y if not ground.is_empty() else 1.0
	query.transform = Transform3D(Basis.IDENTITY, Vector3(at.x, y+1.0, at.y))
	var seen := {}
	for hit in space.intersect_shape(query, 64):
		var body := hit.collider as CollisionObject3D
		if body == null or seen.has(body.get_instance_id()): continue
		seen[body.get_instance_id()] = true
		for owner_id in body.get_shape_owners():
			for i in body.shape_owner_get_shape_count(owner_id):
				var shape := body.shape_owner_get_shape(owner_id, i)
				var faces := 0
				if shape is ConcavePolygonShape3D: faces = (shape as ConcavePolygonShape3D).get_faces().size()/3
				elif shape is ConvexPolygonShape3D: faces = (shape as ConvexPolygonShape3D).points.size()
				elif shape is HeightMapShape3D: faces = (shape as HeightMapShape3D).map_width*(shape as HeightMapShape3D).map_depth
				print("COLLIDER %s layer=%d %s faces/points=%d path=%s" % [body.name, body.collision_layer, shape.get_class(), faces, str(body.get_path()).right(90)])
	# The walker's own cost right there.
	player.global_position = Vector3(at.x, y+0.1, at.y)
	await physics_frame
	var started := Time.get_ticks_usec()
	for i in 20: player.test_move(player.global_transform, Vector3(0.05, 0, 0.05))
	print("TEST_MOVE_US %.0f per call" % ((Time.get_ticks_usec()-started)/20.0))
	# Walk into the spot from each side with each layer left out: what makes move_and_slide slow.
	var mask: int = player.collision_mask
	player.controls_enabled = false
	player.set_physics_process(false)
	for drop in [0, 1, 2, 4, 8, 16, 32]:
		player.collision_mask = mask & ~drop
		var worst := 0.0
		var total := 0.0
		for side in 8:
			var dir := Vector2.from_angle(TAU*side/8.0)
			player.global_position = Vector3(at.x, y+0.1, at.y)-Vector3(dir.x, 0, dir.y)*0.8
			for i in 30:
				player.velocity = Vector3(dir.x*2.8, -1.0, dir.y*2.8)
				var t0 := Time.get_ticks_usec()
				player.move_and_slide()
				var used := (Time.get_ticks_usec()-t0)/1000.0
				total += used
				worst = maxf(worst, used)
		print("SLIDE drop_layer=%d avg=%.2f ms worst=%.2f ms" % [drop, total/240.0, worst])
	player.collision_mask = mask
	quit(0)
