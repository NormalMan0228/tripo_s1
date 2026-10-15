extends SceneTree
## ISS-1 socket sources (S-WP3), offline: every resting archetype's offline fixture (tests/fixtures/
## ix_archetypes.json, from tools/export_ix_fixtures.py) is built as a real crafted assembly from
## generated box/ellipsoid parts, and its derived sockets must have the expected type, count and
## height (snapped onto the mesh); moving parts carry their seat; a one-piece bed snaps to its real
## top and degrades to a seat when shrunk; a rug gives sit_ground; every room seat kind is valid.
##   godot --headless --path game --script res://tests/ix_sources_check.gd
const Sources = preload("res://scripts/ix/ix_sources.gd")
const IxMath = preload("res://scripts/ix/ix_math.gd")
const Loader = preload("res://scripts/model_loader.gd")
const ObjectTransform = preload("res://scripts/object_transform.gd")
const Interiors = preload("res://scripts/interiors.gd")

## id -> [type, count (-1: any), plan-space top (m), tolerance]
const EXPECT := {
	"rocking_chair": ["sit", 1, 0.49, 0.02], "seat": ["sit", 1, 0.48, 0.02], "sofa": ["sit", 2, 0.45, 0.02], "bench": ["sit", 2, 0.46, 0.02],
	"armchair": ["sit", 1, 0.45, 0.02], "throne": ["sit", 1, 0.50, 0.02], "beanbag": ["sit", 1, 0.60, 0.05], "swing": ["sit", 1, 0.58, 0.02],
	"hammock": ["lie", 2, 1.0, 0.05], "sunbed": ["lie", 2, 0.35, 0.02], "bathtub": ["lie", 2, 0.555, 0.02], "toilet": ["sit", 1, 0.46, 0.02],
	"rug": ["sit_ground", 1, 0.024, 0.02], "seesaw": ["sit", -1, 0.48, 0.02], "rocking_horse": ["perch", 1, 0.725, 0.02]}
const BACK_AT_MINUS_Z := ["rocking_chair", "seat", "sofa", "armchair", "throne", "bench", "toilet"]

var failures: Array[String] = []
var passes := 0
var report := {}
var glbs := {}

func check(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ") + label)
	if value: passes += 1
	else: failures.append(label)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var stage := Node3D.new()
	root.add_child(stage)
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ix_archetypes.json"))
	var seen := {}
	var x := 0.0
	for arch in data.archetypes:
		seen[arch.id] = true
		var node := build(arch)
		check(node != null, "%s builds as an assembly" % arch.id)
		if node == null: continue
		stage.add_child(node)
		node.position = Vector3(x, 0.3, -2.0)
		node.rotation_degrees.y = 25.0
		x += 4.0
		var factor: float = (ObjectTransform.frame_of(node) as Node3D).scale.x
		var started := Time.get_ticks_usec()
		var entries := Sources.for_crafted(node, str(arch.rest))
		var ms := (Time.get_ticks_usec() - started) / 1000.0
		var resolved := Sources.resolve_all(entries)
		var want: Array = EXPECT.get(arch.id, [])
		var types := {}
		for r in resolved: types[r.type] = int(types.get(r.type, 0)) + 1
		var summary := {"types": types, "ms": ms, "heights": resolved.map(func(r): return snappedf(r.height, 0.001)), "factor": factor,
			"yaws": resolved.map(func(r): return snappedf(rad_to_deg(angle_difference(deg_to_rad(25.0), r.yaw)), 1.0)), "sources": resolved.map(func(r): return r.source)}
		report[arch.id] = summary
		if want.is_empty(): continue
		var of_type := resolved.filter(func(r): return r.type == want[0])
		check(not of_type.is_empty(), "%s offers %s (%s)" % [arch.id, want[0], str(types)])
		if of_type.is_empty(): continue
		if int(want[1]) >= 0: check(of_type.size() == int(want[1]), "%s has %d %s socket(s) (%d)" % [arch.id, want[1], want[0], of_type.size()])
		var top: float = float(want[2]) * factor
		var worst := 0.0
		for r in of_type: worst = maxf(worst, absf(float(r.height) - top))
		check(worst <= float(want[3]), "%s height on its real top (%.3f vs %.3f m)" % [arch.id, of_type[0].height, top])
		if arch.id in BACK_AT_MINUS_Z:
			var front_ok := true
			for r in of_type: front_ok = front_ok and absf(angle_difference(deg_to_rad(25.0), float(r.yaw))) < 0.05
			check(front_ok, "%s: back at -Z, so the seat faces +Z" % arch.id)
		if arch.id == "rocking_chair": carried(node, "seat", entries, func(): node.whole_root.rotation.x = 0.15)
		if arch.id == "swing": carried(node, "plank", entries, func(): node.pivots["ropes"].rotation.x = 0.35)
		if arch.id == "sunbed": check(float(of_type[0].params.get("recline_deg", 0.0)) > 10.0, "the sunbed reclines (%.0f deg)" % float(of_type[0].params.get("recline_deg", 0.0)))
	for id in EXPECT: check(seen.has(id), "fixture %s is exported" % id)
	await one_piece_bed(stage)
	rooms(stage)
	print("IX_SOURCES_CHECK ", JSON.stringify({"ok": failures.is_empty(), "passed": passes, "failures": failures, "report": report}))
	stage.queue_free()
	await process_frame
	quit(0 if failures.is_empty() else 1)

## A seat on a moving part rides it: the socket keeps its place on the part while the part moves.
func carried(node: Node3D, part: String, entries: Array, move: Callable) -> void:
	var entry: Dictionary = {}
	for e in entries:
		if e.carrier == node.pivots.get(part): entry = e
	check(not entry.is_empty(), "%s: the seat is carried by the %s pivot" % [node.get_meta("fixture_id", ""), part])
	if entry.is_empty(): return
	var pivot: Node3D = node.pivots[part]
	var before := Sources.point_now(entry)
	var local_before := pivot.global_transform.affine_inverse() * before
	move.call()
	var after := Sources.point_now(entry)
	var local_after := pivot.global_transform.affine_inverse() * after
	check(before.distance_to(after) > 0.01 and local_before.distance_to(local_after) < 0.001, "%s: moving the part moves the socket with it (%.2f m)" % [part, before.distance_to(after)])

## One mesh, no designed parts: collision boxes find the bed, the mesh gives the real top; shrunk to
## half it is too short to lie on and offers a seat on its edge instead.
func one_piece_bed(stage: Node3D) -> void:
	var mesh_root := Node3D.new()
	for spec in [[Vector3(2.0, 0.5, 0.9), Vector3(0, 0.25, 0)], [Vector3(0.08, 1.0, 0.9), Vector3(-0.96, 0.5, 0)]]:
		var m := MeshInstance3D.new()
		var b := BoxMesh.new()
		b.size = spec[0]
		m.mesh = b
		m.position = spec[1]
		mesh_root.add_child(m)
	var bytes := glb_of(mesh_root)
	var parts := [{"id": "whole", "parent": "", "size": [2.0, 1.0, 0.9], "position": [0, 0.5, 0], "rotation": [0, 0, 0], "pivot": [0, 0, 0], "color": "#c8b090"}]
	var node = load("res://scripts/asset_assembly.gd").new()
	var ok: bool = node.build({"schema": 1, "plan": {"parts": parts}, "provenance": {"geometry": "proxy"}, "interaction": {"rest": "lie"},
		"program": {"version": 1, "state": {}, "functions": {}, "events": {}}, "runtime": {}}, {"whole": bytes})
	check(ok and node.one_piece, "a one-piece bed builds")
	if not ok: return
	stage.add_child(node)
	node.position = Vector3(-6, 0.0, 3)
	Loader.add_collision(node)
	var factor: float = (ObjectTransform.frame_of(node) as Node3D).scale.x
	var lie := Sources.resolve_all(Sources.for_crafted(node, "lie"), ["lie"])
	report["one_piece_bed"] = {"lie": lie.size(), "heights": lie.map(func(r): return r.height), "factor": factor}
	check(not lie.is_empty() and absf(float(lie[0].height) - 0.5 * factor) < 0.02, "a one-piece bed lies on its real top (%s vs %.3f)" % [str(lie.map(func(r): return snappedf(r.height, 0.001))), 0.5 * factor])
	if not lie.is_empty(): check(str(lie[0].params.head) in ["l", "r"] and float(lie[0].params.length) >= 1.3, "the headboard end is the head (%s)" % str(lie[0].params))
	ObjectTransform.apply(node, {"scale": 50})
	var shrunk := Sources.resolve_all(Sources.for_crafted(node, "lie"))
	var kinds := shrunk.map(func(r): return r.type)
	report["one_piece_bed_50"] = {"types": kinds}
	check(not kinds.has("lie") and (kinds.has("sit") or kinds.has("sit_ground")), "shrunk to 50 %% it degrades to a seat (%s)" % str(kinds))
	await process_frame

## The room seat kinds (real models where the game has them) all give valid sockets.
func rooms(stage: Node3D) -> void:
	var s: Dictionary = Interiors.spec("home").floors[0]
	var i := 0
	for kind in ["wooden_chair", "armchair", "sofa", "bench", "bed"]:
		var record := Interiors.place(stage, {"kind": kind, "at": Vector3(i * 3.0 - 6.0, 0, 6.0), "yaw": 30.0 * i}, s, i)
		i += 1
		var resolved := Sources.resolve_all(Sources.for_room(record))
		var valid := resolved.filter(func(r): return r.valid)
		report["room_" + kind] = {"count": resolved.size(), "valid": valid.size(), "heights": resolved.map(func(r): return snappedf(r.height, 0.001)), "why": resolved.map(func(r): return r.why)}
		check(not valid.is_empty(), "room %s gives valid sockets (%s)" % [kind, str(report["room_" + kind])])
		if kind == "sofa": check(resolved.size() >= 2, "a sofa seats more than one")
		if kind == "bed": check(not resolved.filter(func(r): return r.type == "lie" and r.valid).is_empty(), "a room bed can be lain on")
		check(Sources.for_room(record) == Sources.for_room(record), "room sockets are cached on the piece")

func build(arch: Dictionary) -> Node3D:
	var parts: Array = []
	var blobs := {}
	for p in arch.parts:
		var q: Dictionary = p.duplicate(true)
		q["color"] = "#b0a080"
		parts.append(q)
		blobs[p.id] = glb_for(str(p.get("shape", "box")), Vector3(p.size[0], p.size[1], p.size[2]))
	var node = load("res://scripts/asset_assembly.gd").new()
	var ok: bool = node.build({"schema": 1, "plan": {"parts": parts}, "provenance": {"geometry": "proxy"}, "interaction": {"rest": arch.rest},
		"program": {"version": 1, "state": {}, "functions": {}, "events": {}}, "runtime": {}}, blobs)
	if not ok:
		node.free()
		return null
	node.set_meta("fixture_id", arch.id)
	return node

## A proxy part like the server's: a box or an ellipsoid at the designed size.
func glb_for(shape: String, size: Vector3) -> PackedByteArray:
	var key := shape + str(size)
	if glbs.has(key): return glbs[key]
	var holder := Node3D.new()
	var m := MeshInstance3D.new()
	if shape == "ellipsoid":
		var sphere := SphereMesh.new()
		sphere.radius = 0.5
		sphere.height = 1.0
		m.mesh = sphere
	else:
		m.mesh = BoxMesh.new()
	m.scale = size
	holder.add_child(m)
	glbs[key] = glb_of(holder)
	return glbs[key]

func glb_of(scene: Node3D) -> PackedByteArray:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	doc.append_from_scene(scene, state)
	var bytes := doc.generate_buffer(state)
	scene.free()
	return bytes
