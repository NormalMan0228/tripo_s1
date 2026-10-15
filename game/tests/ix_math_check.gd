extends SceneTree
## ISS-1 core (S-WP1): socket resolution under the object's turn, shape and mirror and under a moving
## part, the warp math and the clip-name grammar. Offline and headless, no server:
##   godot --headless --path game --script res://tests/ix_math_check.gd
const IxMath = preload("res://scripts/ix/ix_math.gd")
const Schema = preload("res://scripts/ix/ix_schema.gd")
const ObjectTransform = preload("res://scripts/object_transform.gd")

var failures: Array[String] = []
var passes := 0
var worst := {}

func check(value: bool, label: String) -> void:
	if value: passes += 1
	else:
		failures.append(label)
		print("FAIL ", label)

func note(key: String, value: float) -> void:
	worst[key] = maxf(float(worst.get(key, 0.0)), value)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	names()
	whole_carrier()
	part_carrier()
	repeats()
	round_trip()
	warps()
	procedural()
	legs()
	print("IX_MATH_CHECK ", JSON.stringify({"ok": failures.is_empty(), "passed": passes, "failures": failures, "worst": worst}))
	quit(0 if failures.is_empty() else 1)

func names() -> void:
	for good in ["sit_chair_enter_l90", "sit_chair_hold", "lie_bed_enter_headl", "sitg_any_exit", "use_counter_act_hr"]:
		check(Schema.valid_name(good), "name accepted: " + good)
	for bad in ["sit_loop", "sit_chair_cycle", "grip-col", "sit_chair_2", "sit_chair2", "Sit_chair_enter", "sit_chair_hold_col", "sit__x", "sit_a_b_c_d_e_f_g"]:
		check(not Schema.valid_name(bad), "name rejected: " + bad)
	var parsed := Schema.parse_clip("sit_chair_enter_l90")
	check(parsed.ok and parsed.family == "sit" and parsed.variant == "chair" and parsed.phase == "enter" and parsed.qualifiers == ["l90"], "clip name parses into family/variant/phase/qualifiers")
	check(not Schema.parse_clip("chair_sit_enter").ok, "an unknown family is refused")
	check(Schema.problems(Schema.normalize({"id": "seat_0", "type": "sit"})).is_empty(), "a normalised record has no problems")
	check(not Schema.problems({"id": "Seat 0", "type": "fly", "at": [0.9, 2, 0]}).is_empty(), "a broken record reports problems")

## A crafted object: root (placement yaw) / Whole / ShapeFrame (shape). A marker placed at the base point
## under the ShapeFrame must land where IxMath says the socket is, for every turn, shape and mirror.
func whole_carrier() -> void:
	var size := Vector3(0.6, 0.9, 0.55)
	var box := AABB(Vector3(-size.x * 0.5, 0, -size.z * 0.5), size)
	var rec := Schema.normalize({"id": "seat_0", "type": "sit", "at": [0.12, 0.5, 0.1], "off": [0.03, 0.0, 0.02], "yaw": 20,
		"params": {"width": 0.5, "depth": 0.45, "head": "l", "hand": "r"}})
	for yaw in [0.0, 37.0, 90.0, 217.0, 359.0]:
		for shape in [{"width": 50, "depth": 100, "height": 100}, {"width": 100, "depth": 100, "height": 100}, {"width": 200, "depth": 50, "height": 150},
				{"width": 100, "depth": 200, "height": 50}, {"width": 100, "depth": 100, "height": 100, "mirror": true}, {"width": 150, "depth": 80, "height": 200, "mirror": true}]:
			var root := Node3D.new()
			get_root().add_child(root)
			root.position = Vector3(3.5, 0.4, -2.0)
			root.rotation_degrees.y = yaw
			var whole := Node3D.new()
			whole.name = "Whole"
			root.add_child(whole)
			var frame := Node3D.new()
			frame.name = "ShapeFrame"
			whole.add_child(frame)
			# The model's own frame: scaled and offset like asset_assembly does it.
			frame.scale = Vector3.ONE * 0.8
			frame.position = Vector3(0.1, 0.0, -0.05) * 0.8
			root.set_meta("size", size)
			var p_b := IxMath.base_point(rec, box)
			var marker := Node3D.new()
			frame.add_child(marker)
			marker.position = frame.transform.affine_inverse() * p_b
			ObjectTransform.apply(root, shape)
			var k := ObjectTransform.factors(shape)
			var ctx := {"xform": whole.global_transform, "box": box, "k": k}
			var resolved := IxMath.resolve(rec, ctx)
			# The clearance offset is metres after the shape, its x on the mirrored side.
			var expected: Vector3 = marker.global_position + root.global_basis * Vector3(rec.off.x * (-1.0 if k.x < 0 else 1.0), rec.off.y, rec.off.z)
			var error: float = resolved.origin.distance_to(expected)
			note("whole_point_mm", error * 1000.0)
			check(error < 0.001, "whole carrier point at yaw %d shape %s (%.4f m)" % [yaw, str(shape), error])
			var b: Basis = resolved.basis
			check(absf(b.determinant() - 1.0) < 1e-4 and b.is_conformal() and absf(b.x.length() - 1.0) < 1e-4, "basis orthonormal det +1 at yaw %d %s" % [yaw, str(shape)])
			# Facing: the object's +Z turned by the socket yaw (mirrored when the object is).
			var local_yaw := deg_to_rad(20.0) * (-1.0 if k.x < 0 else 1.0)
			var want := (root.global_basis * Vector3(sin(local_yaw), 0, cos(local_yaw))).normalized()
			check(b.z.distance_to(want) < 1e-4, "socket faces object front + yaw at %d %s" % [yaw, str(shape)])
			var mirrored := bool(shape.get("mirror", false))
			check(resolved.mirror == mirrored and str(resolved.params.head) == ("r" if mirrored else "l") and str(resolved.params.hand) == ("l" if mirrored else "r") and resolved.id == "seat_0",
				"l/r swap and stable id under mirror=%s" % str(mirrored))
			check(absf(float(resolved.params.width) - 0.5 * absf(k.x)) < 1e-5 and absf(float(resolved.params.depth) - 0.45 * absf(k.z)) < 1e-5, "width/depth follow the shape")
			root.free()

## A part carrier: the seat of a multi-part craft on a pivot turned 20 degrees (a swinging plank).
## The socket at the top-front of the part box must sit on the fitted mesh's own top-front point.
func part_carrier() -> void:
	var assembly = load("res://scripts/asset_assembly.gd").new()
	var holder := Node3D.new()
	get_root().add_child(holder)
	holder.position = Vector3(0.4, 1.2, -0.3)
	holder.rotation_degrees = Vector3(0, 30, 0)
	var pivot := Node3D.new()
	holder.add_child(pivot)
	var normalization := Node3D.new()
	pivot.add_child(normalization)
	var mesh := MeshInstance3D.new()
	var cube := BoxMesh.new()
	cube.size = Vector3(2, 0.5, 1.2)
	mesh.mesh = cube
	normalization.add_child(mesh)
	var size := Vector3(0.62, 0.06, 0.3)
	var pivot_frac := Vector3(0, 0.5, 0)
	assembly.fit_part(normalization, mesh.get_aabb(), size, pivot_frac)
	pivot.rotation_degrees.x = 20.0
	var box := AABB((-pivot_frac - Vector3(0.5, 0.5, 0.5)) * size, size)
	var rec := Schema.normalize({"id": "seat_0", "type": "sit", "carrier": "plank", "at": [0.0, 1.0, 0.5]})
	var resolved := IxMath.resolve(rec, {"xform": pivot.global_transform, "box": box, "k": Vector3.ONE})
	var bounds := mesh.get_aabb()
	var top_front := mesh.global_transform * Vector3(bounds.get_center().x, bounds.end.y, bounds.end.z)
	var error: float = resolved.origin.distance_to(top_front)
	note("part_point_mm", error * 1000.0)
	check(error < 0.001, "part pivot (20 deg) socket on the fitted mesh (%.4f m)" % error)
	var b: Basis = resolved.basis
	check(absf(b.determinant() - 1.0) < 1e-4 and absf(b.y.dot(Vector3.UP) - 1.0) < 1e-5, "yaw-follow socket stays upright on a tilted pivot")
	var full := IxMath.socket_basis({"yaw": 0, "follow": "full"}, {"xform": pivot.global_transform})
	check(absf(full.determinant() - 1.0) < 1e-4 and full.y.dot(pivot.global_basis.y.normalized()) > 0.999, "full-follow socket tilts with the pivot")
	holder.free()
	assembly.free()

func repeats() -> void:
	var bench := Schema.normalize({"id": "seat_0", "type": "sit", "variant": "bench", "at": [0, 1, 0.0], "params": {"width": 1.5, "depth": 0.45},
		"repeat": {"axis": "x", "pitch": 0.55, "min_width": 0.45}})
	var two := IxMath.expand(bench, Vector3.ONE)
	check(two.size() == 2, "a 1.5 m bench gives 2 seats (%d)" % two.size())
	var five := IxMath.expand(bench, Vector3(2, 1, 1))
	check(five.size() == 5, "twice as wide gives 5 seats (%d)" % five.size())
	var box := AABB(Vector3(-0.75, 0, -0.225), Vector3(1.5, 0.45, 0.45))
	var plain := []
	for r in two: plain.append(IxMath.resolve(r, {"xform": Transform3D.IDENTITY, "box": box, "k": Vector3.ONE}))
	var flipped := []
	for r in IxMath.expand(bench, Vector3(-1, 1, 1)): flipped.append(IxMath.resolve(r, {"xform": Transform3D.IDENTITY, "box": box, "k": Vector3(-1, 1, 1)}))
	check(plain.size() == 2 and plain[0].id == "seat_0" and plain[0].origin.x < 0 and plain[1].origin.x > 0, "seat_0 is the -x end unmirrored")
	check(flipped.size() == 2 and flipped[0].id == "seat_0" and flipped[0].origin.x > 0 and absf(flipped[0].origin.x + plain[0].origin.x) < 1e-5, "mirrored, seat_0 keeps its id on the other side")
	check(IxMath.expand(bench, Vector3(0.25, 1, 1)).is_empty(), "too narrow for anyone: no seat")

func round_trip() -> void:
	var box := AABB(Vector3(-0.3, 0, -0.25), Vector3(0.6, 0.9, 0.5))
	var by_frac := Schema.normalize({"id": "a", "at": [0.25, 0.5, -0.2], "off": [0.0, 0.02, 0.05]})
	var point := IxMath.socket_point(by_frac, {"xform": Transform3D.IDENTITY, "box": box})
	var by_pos := Schema.normalize({"id": "a", "pos": [point.x, point.y, point.z]})
	var back := IxMath.socket_point(by_pos, {"xform": Transform3D.IDENTITY, "box": box})
	check(point.distance_to(back) < 1e-6 and point.distance_to(Vector3(0.15, 0.47, -0.05)) < 1e-5, "fractions + offset and metres round-trip (%s)" % str(point))

func warps() -> void:
	var a0 := Transform3D(Basis(Vector3.UP, 0.4), Vector3(1.0, 0.0, 2.0))
	var s := Transform3D(Basis(Vector3.UP, 0.4 + PI + 0.3), Vector3(1.2, 0.45, 2.6))
	var c := Transform3D(Basis(Vector3.UP, PI), Vector3(0.05, 0.45, 0.55))
	var res := IxMath.residual(a0, s, c)
	check(res.ok, "a small residual is inside the clamp (xz %.2f yaw %.2f)" % [res.xz, res.yaw])
	var tb := 0.1
	var tc := 0.7
	var curve := func(t: float) -> Transform3D: return Transform3D(Basis(Vector3.UP, 0.25 * t), Vector3(0, 0, 0.5 * t))
	var at_tb := IxMath.warped_root(a0, res.E, curve.call(tb), tb, tb, tc)
	check(at_tb.origin.distance_to((a0 * curve.call(tb)).origin) < 0.001, "Root(tb) = A0*R(tb)")
	for t in [0.7, 0.9, 1.2]:
		var root := IxMath.warped_root(a0, res.E, curve.call(t), t, tb, tc)
		var want: Transform3D = res.W0 * curve.call(t)
		check(root.origin.distance_to(want.origin) < 0.001 and root.basis.z.distance_to(want.basis.z) < 0.001, "Root(t>=tc) = W0*R(t) at %.1f" % t)
	# The socket_ref C, carried by the root at contact, lands on the socket (planar).
	var contact := IxMath.warped_root(a0, res.E, Transform3D.IDENTITY, tc, tb, tc) * c
	check(Vector2(contact.origin.x - s.origin.x, contact.origin.z - s.origin.z).length() < 0.001, "the clip's contact lands on the socket")
	var eps := 1e-4
	check(absf(IxMath.alpha(tb + eps, tb, tc) - IxMath.alpha(tb, tb, tc)) < 1e-6 and absf(IxMath.alpha(tc, tb, tc) - IxMath.alpha(tc - eps, tb, tc)) < 1e-6, "no velocity step at the warp window ends")
	var far := IxMath.residual(a0, Transform3D(Basis(Vector3.UP, 2.0), Vector3(3, 0, 3)), c)
	check(not far.ok and Vector2(far.clamped.origin.x, far.clamped.origin.z).length() <= IxMath.WARP_XZ + 1e-5, "a residual beyond the clamp is reported and clamped")
	var v := IxMath.vertical(0.56, 0.0, 0.45)
	check(v.ok and absf(v.dh - 0.11) < 1e-6, "vertical warp inside the limit")
	check(not IxMath.vertical(0.80, 0.0, 0.45).ok, "a seat far above the reference is out of the vertical warp")

## The procedural virtual clips: per 60 Hz tick the body moves <= 0.08 m for the lengths the driver uses.
func procedural() -> void:
	var a := Vector3(0, 0, 0.75)
	var h := Vector3(0.05, -0.47, -0.02)
	for seconds in [0.45, 0.5, 0.55, 0.7]:
		var ticks := int(ceil(seconds * 60.0))
		var last := IxMath.enter_curve(0.0, a, h)
		var biggest := 0.0
		for i in range(1, ticks + 1):
			var p := IxMath.enter_curve(float(i) / ticks, a, h)
			biggest = maxf(biggest, p.distance_to(last))
			last = p
		note("enter_step_m", biggest)
		check(biggest <= IxMath.STEP_LIMIT, "enter over %.2f s: %.3f m per tick" % [seconds, biggest])
		check(IxMath.enter_curve(1.0, a, h).distance_to(h) < 1e-6 and IxMath.exit_curve(1.0, h, a).distance_to(a) < 1e-6, "curves end exactly on their points")
	check(absf(IxMath.enter_weight(1.0) - 1.0) < 1e-6 and IxMath.exit_weight(1.0) < 1e-6 and IxMath.exit_weight(0.0) > 0.999, "pose weights run 0-1 and back")
	var yaw := 0.0
	for i in 30: yaw = IxMath.turn_toward(yaw, PI, IxMath.TURN_RATE, 1.0 / 60.0)
	check(absf(angle_difference(yaw, PI)) < 1e-4, "a half turn at 10 rad/s finishes in 0.3 s")
	check(IxMath.align_duration(1.2, PI) <= 0.4 and IxMath.align_duration(0.0, 0.0) >= 0.15, "align lasts 0.15-0.40 s")
	check(IxMath.sit_variant(0.30) == "sit_low" and IxMath.sit_variant(0.45) == "sit" and IxMath.sit_variant(0.72) == "perch" and IxMath.sit_variant(0.05) == "sit_ground", "seat height picks the variant")

func legs() -> void:
	var thigh := 0.38
	var shin := 0.43
	for target in [Vector2(0.36, 0.49), Vector2(0.30, 0.30), Vector2(0.10, 0.70)]:
		var angles := IxMath.leg_angles(thigh, shin, target.x, target.y)
		var knee := Vector2(sin(angles.x), -cos(angles.x)) * thigh
		var total := angles.x + angles.y
		var ankle := knee + Vector2(sin(total), -cos(total)) * shin
		var error := ankle.distance_to(Vector2(target.x, -target.y))
		note("leg_mm", error * 1000.0)
		check(error < 0.001 and angles.y <= 0.0 and knee.x > 0.0, "two-bone leg reaches %s with the knee in front (%.4f m)" % [str(target), error])
