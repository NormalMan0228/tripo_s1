extends Node
## Keeps the walker in view: buildings, tree crowns and other tall props that
## stand between the follow camera and the walker fade to a soft see-through, the
## way top-down RPGs do. Buildings (dressed with building_exterior.gdshader) use the
## shader's screen-door `fade` uniform on their own materials; trees get translucent
## copies of their shared materials (depth still written, so only front faces show)
## until they are clear again. A village add-on (see main.gd VILLAGE_MODULES).
const ALPHA := 0.4
## Tree crowns are many overlapping blobs, so they need to go further to show the walker.
const PROP_ALPHA := 0.2
const FADE_SPEED := 6.0
const CHECK_EVERY := 0.08
## Tall environment props worth fading; flowers, fences and benches never hide anyone.
const PROPS := ["37_round_tree","38_conifer","39_palm","22_tent_orange","23_tent_green","28_beach_umbrella","30_cafe_umbrella"]
## Knees, chest and head. Something fades only when it hides at least two of
## them, so brushing past an eave or the edge of a crown leaves it solid.
const SAMPLES := [Vector3(0,.55,0),Vector3(0,1.1,0),Vector3(0,1.6,0)]
const HIDDEN_SAMPLES := 2

var app: Node
## Each: {root, alpha, building, box: AABB (root space), meshes, amount, target, copies}
var groups: Array[Dictionary] = []
## Building roots, for mapping a ray hit on a building's collision back to it.
var building_roots := {}
var wait := 0.0

func setup(main: Node) -> void:
	app = main
	var map: Node = app.town.map if is_instance_valid(app.town) else null
	if not is_instance_valid(map): return
	var buildings := map.get_node_or_null("Buildings")
	if buildings:
		for building in buildings.get_children():
			add_group(building, ALPHA)
			building_roots[building] = true
	var props := map.get_node_or_null("Environment")
	if props and "prop_nodes" in props:
		for prop in props.prop_nodes:
			if str(prop.get_meta("placement_spec",{}).get("id","")) in PROPS: add_group(prop, PROP_ALPHA)

func add_group(root: Node3D, alpha: float) -> void:
	var meshes: Array[MeshInstance3D] = []
	var box := AABB()
	var inverse := root.global_transform.affine_inverse()
	for node in root.find_children("*","MeshInstance3D",true,false):
		var mesh := node as MeshInstance3D
		if not mesh.visible or mesh.mesh == null: continue
		var local: AABB = inverse*mesh.global_transform*mesh.get_aabb()
		box = local if meshes.is_empty() else box.merge(local)
		meshes.append(mesh)
	if meshes.is_empty(): return
	# Crowns are round inside their box: trim it so its corners do not count.
	box = box.grow(-minf(box.size.x,box.size.z)*0.14)
	groups.append({"root":root,"alpha":alpha,"building":alpha == ALPHA,"box":box,"meshes":meshes,"amount":0.0,"target":0.0,"copies":[]})

func _process(delta: float) -> void:
	if not is_instance_valid(app) or not is_instance_valid(app.player) or not is_instance_valid(app.camera): return
	wait -= delta
	if wait <= 0.0:
		wait = CHECK_EVERY
		find_blockers()
	for group in groups:
		if group.amount == group.target: continue
		group.amount = move_toward(group.amount, group.target, FADE_SPEED*delta)
		apply(group)

func find_blockers() -> void:
	var toward: Vector3 = app.camera.global_transform.basis.z
	var feet: Vector3 = app.player.render_position() if app.player.has_method("render_position") else app.player.global_position
	# Buildings: rays toward the camera against their real collision shells.
	var covered := {}
	var space: PhysicsDirectSpaceState3D = app.player.get_world_3d().direct_space_state
	for sample in SAMPLES:
		var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(feet+sample, feet+sample+toward*60.0, 2))
		if hit.is_empty(): continue
		var node: Node = hit.collider
		while node != null and not building_roots.has(node): node = node.get_parent()
		if node != null: covered[node] = int(covered.get(node, 0))+1
	for group in groups:
		var root: Node3D = group.root
		if not is_instance_valid(root): continue
		if group.building:
			group.target = 1.0 if int(covered.get(root, 0)) >= HIDDEN_SAMPLES else 0.0
			continue
		var hits := 0
		# Cheap reject: only things on the camera side of the walker, close enough to matter.
		var offset := root.global_position-feet
		if offset.dot(toward) > -4.0 and Vector2(offset.x,offset.z).length() < 26.0:
			# Trees settle into the ground after loading, so read the transform each time.
			var inverse := root.global_transform.affine_inverse()
			for sample in SAMPLES:
				var from: Vector3 = inverse*(feet+sample)
				var to: Vector3 = inverse*(feet+sample+toward*60.0)
				if group.box.intersects_segment(from,to): hits += 1
		group.target = 1.0 if hits >= HIDDEN_SAMPLES else 0.0

## amount 0 = solid with the original shared materials, 1 = fully faded to ALPHA.
func apply(group: Dictionary) -> void:
	var dither := smoothstep(0.0, 1.0, group.amount)
	if group.amount <= 0.0:
		for entry in group.copies:
			if not is_instance_valid(entry.mesh): continue
			if entry.has("shader"): entry.shader.set_shader_parameter("fade", 0.0)
			else: entry.mesh.set_surface_override_material(entry.surface, entry.previous)
		group.copies = []
		return
	if group.copies.is_empty():
		for mesh: MeshInstance3D in group.meshes:
			if not is_instance_valid(mesh) or mesh.material_override != null: continue
			for surface in mesh.mesh.get_surface_count():
				var shaded := mesh.get_active_material(surface) as ShaderMaterial
				if shaded != null and fadeable(shaded):
					group.copies.append({"mesh":mesh,"surface":surface,"shader":shaded})
					continue
				var source := mesh.get_active_material(surface) as BaseMaterial3D
				if source == null: continue
				var copy := source.duplicate() as BaseMaterial3D
				copy.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
				copy.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_ALWAYS
				group.copies.append({"mesh":mesh,"surface":surface,"previous":mesh.get_surface_override_material(surface),"copy":copy,"alpha":source.albedo_color.a})
				mesh.set_surface_override_material(surface, copy)
	var alpha := lerpf(1.0, group.alpha, dither)
	for entry in group.copies:
		if entry.has("shader"): entry.shader.set_shader_parameter("fade", dither)
		else: entry.copy.albedo_color.a = entry.alpha*alpha

## Shader materials that know the screen-door `fade` uniform (building_exterior).
static var _fadeable := {}
static func fadeable(material: ShaderMaterial) -> bool:
	if material.shader == null: return false
	var key := material.shader.get_instance_id()
	if not _fadeable.has(key):
		_fadeable[key] = material.shader.get_shader_uniform_list().any(func(u): return u.name == "fade")
	return _fadeable[key]

func leave() -> void:
	for group in groups:
		group.amount = 0.0
		apply(group)
	groups.clear()
