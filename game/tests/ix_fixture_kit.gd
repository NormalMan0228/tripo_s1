extends RefCounted
## Offline crafted objects for the ISS-1 checks and the lab: a real asset_assembly built from a plan
## whose parts are generated box/ellipsoid GLBs at their designed sizes (what the server's proxy
## geometry gives), so socket derivation, carriers and collision run exactly as in the game.
const Loader = preload("res://scripts/model_loader.gd")

static var glbs := {}

static func archetypes() -> Dictionary:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ix_archetypes.json"))
	var out := {}
	for arch in data.archetypes: out[arch.id] = arch
	return out

## A plain chair: a seat block of the given height with a back (multi-part, like the fixture chair).
static func box_chair(height: float, width := 0.5) -> Dictionary:
	return {"id": "box_chair_%d" % int(round(height * 100.0)), "rest": "sit", "parts": [
		{"id": "seat", "parent": "", "shape": "box", "size": [width, height, 0.48], "position": [0, height * 0.5, 0], "rotation": [0, 0, 0], "pivot": [0, 0, 0]},
		{"id": "back", "parent": "seat", "shape": "box", "size": [width, 0.5, 0.06], "position": [0, height * 0.5 + 0.25, -0.21], "rotation": [0, 0, 0], "pivot": [0, 0, 0]}]}

## A bed: a 0.45 m frame-and-mattress block with a headboard at -Z.
static func box_bed() -> Dictionary:
	return {"id": "box_bed", "rest": "lie", "parts": [
		{"id": "frame", "parent": "", "shape": "box", "size": [1.0, 0.45, 1.75], "position": [0, 0.225, 0], "rotation": [0, 0, 0], "pivot": [0, 0, 0]},
		{"id": "headboard", "parent": "frame", "shape": "box", "size": [1.0, 0.8, 0.06], "position": [0, 0.175, -0.845], "rotation": [0, 0, 0], "pivot": [0, 0, 0]}]}

static func build(arch: Dictionary, collision := true) -> Node3D:
	var parts: Array = []
	var blobs := {}
	for p in arch.parts:
		var q: Dictionary = p.duplicate(true)
		q["color"] = str(p.get("color", "#b8a07a"))
		parts.append(q)
		blobs[p.id] = glb_for(str(p.get("shape", "box")), Vector3(p.size[0], p.size[1], p.size[2]))
	var node = load("res://scripts/asset_assembly.gd").new()
	var ok: bool = node.build({"schema": 1, "plan": {"parts": parts}, "provenance": {"geometry": "proxy"}, "interaction": {"rest": arch.rest},
		"program": {"version": 1, "state": {}, "functions": {}, "events": {}}, "runtime": {}}, blobs)
	if not ok:
		node.free()
		return null
	node.name = str(arch.id)
	node.set_meta("fixture_id", arch.id)
	if collision: Loader.add_collision(node)
	return node

static func glb_for(shape: String, size: Vector3) -> PackedByteArray:
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
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	doc.append_from_scene(holder, state)
	glbs[key] = doc.generate_buffer(state)
	holder.free()
	return glbs[key]

## A floor (layer 1) under everything.
static func floor_body(parent: Node3D, size := 40.0) -> StaticBody3D:
	var body := StaticBody3D.new()
	parent.add_child(body)
	var shape := CollisionShape3D.new()
	body.add_child(shape)
	var box := BoxShape3D.new()
	box.size = Vector3(size, 0.2, size)
	shape.shape = box
	body.position.y = -0.1
	return body
