extends SceneTree
## Shape-fitted collision for crafted objects (craft_collision.gd, model_loader.add_collision):
## a walker fits under a table and between its legs, the legs and top still block, a shape
## edit (width, mirror) moves and scales the boxes, and real Tripo models build in a few
## milliseconds with a handful of boxes. No server needed.
##   godot --path game --script res://tests/craft_collision_check.gd
const Loader = preload("res://scripts/model_loader.gd")
const CraftCollision = preload("res://scripts/craft_collision.gd")
const ObjectTransform = preload("res://scripts/object_transform.gd")
var failures: Array[String] = []
var stage: Node3D

func check(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func _initialize() -> void: call_deferred("run")

## A crafted-looking model: root > ShapeFrame > mesh pieces, as model_loader builds it.
func model(pieces: Array) -> Node3D:
	var root := Node3D.new()
	var frame := Node3D.new()
	frame.name = "ShapeFrame"
	root.add_child(frame)
	var bounds := AABB()
	var first := true
	for piece in pieces:
		var box := BoxMesh.new()
		box.size = piece.size
		var mesh := MeshInstance3D.new()
		mesh.mesh = box
		mesh.position = piece.position + piece.size * 0.5
		mesh.set_meta("craft_surface", true)
		frame.add_child(mesh)
		bounds = piece if first else bounds.merge(piece)
		first = false
	root.set_meta("size", bounds.size)
	return root

func blocked(at: Vector3, radius := 0.05, height := 0.0) -> bool:
	var query := PhysicsShapeQueryParameters3D.new()
	if height > 0.0:
		var capsule := CapsuleShape3D.new()
		capsule.radius = radius
		capsule.height = height
		query.shape = capsule
	else:
		var sphere := SphereShape3D.new()
		sphere.radius = radius
		query.shape = sphere
	query.collision_mask = 16
	query.transform = Transform3D(Basis(), at)
	return not stage.get_world_3d().direct_space_state.intersect_shape(query, 1).is_empty()

func boxes_of(root: Node3D) -> int:
	var count := 0
	for body in root.get_children():
		if body is StaticBody3D: count += body.get_child_count()
	return count

func run() -> void:
	stage = Node3D.new()
	root.add_child(stage)

	# ------------------------------------------------------------ table: 1.2 x 0.75 x 0.8
	var legs := []
	for x in [0.0, 1.12]:
		for z in [0.0, 0.72]:
			legs.append(AABB(Vector3(x, 0, z), Vector3(0.08, 0.7, 0.08)))
	var table := model(legs + [AABB(Vector3(0, 0.7, 0), Vector3(1.2, 0.05, 0.8))])
	stage.add_child(table)
	var started := Time.get_ticks_usec()
	Loader.add_collision(table)
	print("table: %d boxes in %.1f ms" % [boxes_of(table), (Time.get_ticks_usec() - started) / 1000.0])
	await physics_frame
	await physics_frame
	check(boxes_of(table) >= 5 and boxes_of(table) <= 12, "table splits into top and legs (%d boxes)" % boxes_of(table))
	check(not blocked(Vector3(0.6, 0.3, 0.4), 0.22, 0.5), "a body fits under the table between its legs")
	check(blocked(Vector3(0.04, 0.3, 0.04)), "a leg blocks")
	check(blocked(Vector3(0.6, 0.72, 0.4)), "the top blocks")
	check(not blocked(Vector3(0.6, 0.9, 0.4)), "nothing above the top")

	# ------------------------------------------------------------ shape edit: wider + mirror
	ObjectTransform.apply(table, {"width": 150, "depth": 100, "height": 100, "scale": 100, "mirror": true})
	await physics_frame
	await physics_frame
	# x scales by -1.5: the leg at x≈0.04 moves to x≈-0.06 and the far leg to ≈ -1.74.
	check(blocked(Vector3(-1.74, 0.3, 0.04)), "a mirrored, widened leg blocks where it now stands")
	check(not blocked(Vector3(0.04, 0.3, 0.04 + 0.4)), "the old leg spot is free")
	check(not blocked(Vector3(-0.9, 0.3, 0.4), 0.22, 0.5), "still room under the widened table")

	# ------------------------------------------------------------ hollow crate: closed shell fills in
	var walls := [AABB(Vector3(0, 0, 0), Vector3(1, 0.04, 1)), AABB(Vector3(0, 0.96, 0), Vector3(1, 0.04, 1)),
		AABB(Vector3(0, 0, 0), Vector3(0.04, 1, 1)), AABB(Vector3(0.96, 0, 0), Vector3(0.04, 1, 1)),
		AABB(Vector3(0, 0, 0), Vector3(1, 1, 0.04)), AABB(Vector3(0, 0, 0.96), Vector3(1, 1, 0.04))]
	var crate := model(walls)
	crate.position = Vector3(4, 0, 0)
	stage.add_child(crate)
	Loader.add_collision(crate)
	await physics_frame
	await physics_frame
	check(boxes_of(crate) <= 3, "a closed crate fills into a few boxes (%d)" % boxes_of(crate))
	check(blocked(Vector3(4.5, 0.5, 0.5)), "the crate's inside is solid")

	# ------------------------------------------------------------ flat rug: a thin slab, no NaN
	var rug := Node3D.new()
	var plane := MeshInstance3D.new()
	plane.mesh = PlaneMesh.new()
	plane.set_meta("craft_surface", true)
	rug.add_child(plane)
	rug.set_meta("size", Vector3(2, 0, 2))
	rug.position = Vector3(8, 0, 0)
	stage.add_child(rug)
	Loader.add_collision(rug)
	await physics_frame
	await physics_frame
	var finite := true
	for body in rug.get_children():
		for shape in body.get_children():
			finite = finite and shape.position.is_finite() and (shape.shape as BoxShape3D).size.is_finite()
	check(boxes_of(rug) == 1 and finite and blocked(Vector3(8, 0.0, 0)), "a flat rug becomes one thin slab")

	# ------------------------------------------------------------ no mesh: the old single box
	var bare := Node3D.new()
	bare.set_meta("size", Vector3(0.5, 0.5, 0.5))
	bare.position = Vector3(-4, 0, 0)
	stage.add_child(bare)
	Loader.add_collision(bare)
	await physics_frame
	await physics_frame
	check(boxes_of(bare) == 1 and blocked(Vector3(-4, 0.25, 0)), "a model without triangles keeps one box")

	# ------------------------------------------------------------ real Tripo models
	for path in ["res://assets/sample_stool.glb", "res://tests/fixtures/tripo/tripo_pot.glb", "res://assets/shore_rowboat.glb"]:
		var real := Loader.load_sample(path)
		check(real != null, path.get_file() + " loads")
		if real == null: continue
		stage.add_child(real)
		real.position = Vector3(0, 0, 6)
		var points := CraftCollision.face_count(real)
		started = Time.get_ticks_usec()
		Loader.add_collision(real)
		var ms := (Time.get_ticks_usec() - started) / 1000.0
		var size: Vector3 = real.get_meta("size")
		print("%s: %d faces, size %s, %d boxes, %.1f ms" % [path.get_file(), points, str(size), boxes_of(real), ms])
		check(boxes_of(real) >= 1 and boxes_of(real) <= CraftCollision.MAX_BOXES, path.get_file() + ": box count within limit")
		check(ms < 60.0, path.get_file() + ": builds in under 60 ms (%.1f)" % ms)
		real.queue_free()
		await physics_frame

	print("craft collision: %s" % ("OK" if failures.is_empty() else "FAILED " + str(failures)))
	quit(0 if failures.is_empty() else 1)
