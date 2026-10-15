extends SceneTree
## Door hooks (maps/archipelago/building_doors.gd, interiors.gd front_door) on the map built both ways:
## the baked island and the runtime build (generated data off for the island). Headless:
##   Godot --headless --path game --script res://tests/building_doors_check.gd
##  - door_leaves.json has a door for every Town.DOORS entry, each with its leaf and opening resources
##    (run tools/door_leaves.gd after a door, a building model or its placement changes);
##  - every enabled door (BuildingDoors.ENABLED / ALL_DOORS) is on its building: Buildings/<id>/DoorFrame
##    with DoorLeaf (the hinge, unturned while closed, a solid leaf THICKNESS deep under it) and
##    DoorOpening (inner_light);
##    near the door point, facing out of the door, nothing of it collides; set_door_open swings the
##    hinge outward about +Y (0 closed .. 1 OPEN_DEGREES) and back; the leaf took the building's
##    exterior material (dressing restyle); both builds put the doors at the same place;
##  - the room behind an enabled door has that very leaf as its FrontDoor (same mesh, same size),
##    which set_front_door_open turns 0 .. 108 degrees, 108 by default; other rooms keep theirs.
## Prints BUILDING_DOORS_CHECK {...}.
const Map = preload("res://maps/archipelago/archipelago.gd")
const IslandBake = preload("res://maps/archipelago/island_bake.gd")
const Dressing = preload("res://scripts/building_dressing.gd")
const Doors = preload("res://maps/archipelago/building_doors.gd")
const Town = preload("res://scripts/town.gd")
const Interiors = preload("res://scripts/interiors.gd")
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var report := {}
	var table := Doors.table()
	for door: Dictionary in Town.DOORS:
		var entry: Dictionary = table.get(String(door.id), {})
		var leaf_path := String(entry.get("mesh", "")) if not entry.has("leaves") else String(entry.leaves[0].get("mesh", "")) if not (entry.leaves as Array).is_empty() else ""
		if entry.is_empty() or not ResourceLoader.exists(leaf_path) or not ResourceLoader.exists(String(entry.get("opening", ""))):
			failures.append("%s: no door in door_leaves.json (run tools/door_leaves.gd)" % door.id)
	var enabled: Array = Town.DOORS.map(func(d): return String(d.id)).filter(func(id): return Doors.enabled(id))
	report["enabled"] = enabled
	var places := {}
	for label in ["island", "runtime"]:
		IslandBake.island_disabled = label == "runtime"
		var map := await build()
		Dressing.dress(map)
		places[label] = check_map(map, label, enabled, report)
		map.get_parent().queue_free()
		await process_frame
	IslandBake.island_disabled = false
	for id in places.island:
		if places.runtime.has(id) and (places.island[id] as Transform3D).origin.distance_to((places.runtime[id] as Transform3D).origin) > 0.001:
			failures.append("%s: the island and the runtime build place the door differently" % id)
	check_interiors(enabled, report)
	report["failures"] = failures
	report["passed"] = failures.is_empty()
	print("BUILDING_DOORS_CHECK ", JSON.stringify(report))
	quit(0 if failures.is_empty() else 1)

func build() -> Node3D:
	var viewport := SubViewport.new()
	viewport.own_world_3d = true
	viewport.size = Vector2i(64, 64)
	root.add_child(viewport)
	var camera := Camera3D.new()
	viewport.add_child(camera)
	var map: Node3D = Map.new()
	map.name = "Archipelago"
	viewport.add_child(map)
	await map.build(camera)
	for i in 6: await physics_frame
	return map

func check_map(map: Node3D, label: String, enabled: Array, report: Dictionary) -> Dictionary:
	var places := {}
	var ids := Doors.door_ids()
	report[label+"_doors"] = ids.size()
	for door: Dictionary in Town.DOORS:
		var id := String(door.id)
		if not enabled.has(id):
			if ids.has(id): failures.append("%s %s: installed but not enabled" % [label, id])
			continue
		var hinge := Doors.door_leaf(id)
		var opening := Doors.door_opening(id)
		if hinge == null or opening == null:
			failures.append("%s %s: DoorLeaf or DoorOpening missing" % [label, id])
			continue
		if String(hinge.get_parent().get_parent().name) != id or String(hinge.name) != "DoorLeaf" or hinge.transform != Transform3D(Basis.IDENTITY, hinge.position): failures.append("%s %s: leaf not at Buildings/<id>/DoorFrame/DoorLeaf, unturned" % [label, id])
		places[id] = hinge.global_transform
		var leaf := hinge.get_node("Mesh") as MeshInstance3D
		var box := leaf.mesh.get_aabb()
		var size := Doors.leaf_size(id)
		var leaves := Doors.leaf_entries(id)
		if not leaves.is_empty(): size = Vector3(float(leaves[0].width), float(leaves[0].height), size.z)
		var inward: bool = String(Doors.table()[id].get("opens", "out")) == "in"
		# The leaf reaches from its hinge across the doorway: along -x when hung on its right edge.
		var reach := size.x if not leaves.is_empty() and String(leaves[0].get("hinge", "right")) == "left" else -size.x
		report[label+"_"+id] = {"leaf_aabb": [snappedf(box.size.x, .01), snappedf(box.size.y, .01), snappedf(box.size.z, .01)], "surfaces": leaf.mesh.get_surface_count()}
		if box.size.z < size.z*0.9: failures.append("%s %s: the leaf is not solid (%.3f m deep)" % [label, id, box.size.z])
		if absf(box.size.x-size.x) > 0.1 or absf(box.size.y-size.y) > 0.1: failures.append("%s %s: leaf size %s, door %s" % [label, id, box.size, size])
		# The leaf took the building's exterior material (restyled with it).
		var restyled := true
		for s in leaf.mesh.get_surface_count():
			# The exterior shader, or for a door's own glass parts the dressing's lit pane material.
			# (A cut door's back, edges and handle keep their own plain colour materials.)
			var drawn := leaf.get_surface_override_material(s)
			var own := leaf.mesh.surface_get_material(s) as StandardMaterial3D
			if not (drawn is ShaderMaterial or (drawn is StandardMaterial3D and (drawn as StandardMaterial3D).emission_enabled) or (drawn == null and own != null and own.albedo_texture == null)): restyled = false
		if not restyled: failures.append("%s %s: the leaf is not drawn with the building's exterior material" % [label, id])
		var at: Vector2 = door.at
		var out: Vector2 = (at-Vector2(door.center)).normalized()
		var middle := hinge.global_transform*Vector3(reach*0.5, 1.0, 0)
		var facing := hinge.global_basis.z
		if Vector2(middle.x, middle.z).distance_to(at) > 4.0: failures.append("%s %s: door %.1f m from the door point" % [label, id, Vector2(middle.x, middle.z).distance_to(at)])
		if Vector2(facing.x, facing.z).normalized().dot(out) < 0.5: failures.append("%s %s: the door does not face out" % [label, id])
		var material := opening.material_override as ShaderMaterial
		if material == null or not material.shader.code.contains("inner_light"): failures.append("%s %s: opening without inner_light" % [label, id])
		var closed_far := (hinge.global_transform*Vector3(reach, 1.0, 0))
		Doors.set_door_open(id, 1.0)
		var open_far := (hinge.global_transform*Vector3(reach, 1.0, 0))
		var swing := Vector2(open_far.x-closed_far.x, open_far.z-closed_far.z)
		if absf(absf(hinge.rotation_degrees.y)-Doors.OPEN_DEGREES) > 0.01 or (swing.dot(out) <= 0.0) != inward: failures.append("%s %s: did not open %s" % [label, id, "inward" if inward else "outward"])
		Doors.set_door_open(id, 0.5)
		if absf(Doors.door_open(id)-0.5) > 0.001: failures.append("%s %s: amount not kept" % [label, id])
		Doors.set_door_open(id, 0.0)
		if absf(hinge.rotation.y) > 0.0001: failures.append("%s %s: did not close" % [label, id])
		for node in [hinge, opening]:
			if not (node as Node).find_children("*", "CollisionObject3D", true, false).is_empty(): failures.append("%s %s: the door collides" % [label, id])
	return places

func check_interiors(enabled: Array, report: Dictionary) -> void:
	for door: Dictionary in Town.DOORS:
		var room := String(door.room)
		if not Interiors.has_interior(room): continue
		var spec: Dictionary = Interiors.spec(room).floors[0]
		var holder := Node3D.new()
		root.add_child(holder)
		Interiors.front(holder, spec)
		var hinge := Interiors.front_door(holder)
		if hinge == null:
			failures.append("%s: no FrontDoor" % room)
			holder.free()
			continue
		if absf(absf(hinge.rotation_degrees.y)-Interiors.FRONT_DOOR_OPEN_DEGREES) > 0.01: failures.append("%s: FrontDoor is not open 108 degrees by default" % room)
		Interiors.set_front_door_open(holder, 0.0)
		if absf(hinge.rotation.y) > 0.0001: failures.append("%s: FrontDoor did not close" % room)
		Interiors.set_front_door_open(holder, 1.0)
		var leaf := hinge.get_node_or_null("Mesh") as MeshInstance3D
		if enabled.has(String(door.id)):
			if leaf == null or leaf.mesh != Doors.leaf_mesh(String(door.id)): failures.append("%s: FrontDoor is not the building's door leaf" % room)
			else:
				report["interior_"+room] = {"hinge_x": snappedf(hinge.position.x, .01), "door_width": Doors.leaf_size(String(door.id)).x,
					"doorway_width": Interiors.DOOR_HALF*2, "fits": Doors.leaf_size(String(door.id)).x <= Interiors.DOOR_HALF*2+0.01}
		elif leaf != null: failures.append("%s: FrontDoor took a leaf though the door is not enabled" % room)
		holder.free()
