extends RefCounted

static var cedar_crown_mesh: Mesh

static func material(color: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = 0.93
	return m

static func box(parent: Node3D, at: Vector3, size: Vector3, color: Color, solid := false) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	var shape := BoxMesh.new()
	shape.size = size
	mesh.mesh = shape
	mesh.position = at
	mesh.material_override = material(color)
	parent.add_child(mesh)
	if solid:
		var body := StaticBody3D.new()
		var col := CollisionShape3D.new()
		var bounds := BoxShape3D.new()
		bounds.size = size
		col.shape = bounds
		body.add_child(col)
		# Keep physics attached to the visual transform (fences and benches rotate).
		mesh.add_child(body)
	return mesh

static func sphere(parent: Node3D, at: Vector3, size: Vector3, color: Color) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	var ball := SphereMesh.new()
	ball.radius = 0.5
	ball.height = 1
	ball.radial_segments = 12
	ball.rings = 6
	mesh.mesh = ball
	mesh.scale = size
	mesh.position = at
	mesh.material_override = material(color)
	parent.add_child(mesh)
	return mesh

static func cone(parent: Node3D, at: Vector3, radius: float, height: float, color: Color) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	var cone_mesh := CylinderMesh.new()
	cone_mesh.top_radius = 0
	cone_mesh.bottom_radius = radius
	cone_mesh.height = height
	cone_mesh.radial_segments = 8
	mesh.mesh = cone_mesh
	mesh.position = at
	mesh.material_override = material(color)
	parent.add_child(mesh)
	return mesh

static func tree(parent: Node3D, at: Vector3, pine := false, solid := true) -> Node3D:
	var root := Node3D.new()
	parent.add_child(root)
	root.position = at
	var trunk := MeshInstance3D.new()
	var trunk_mesh := CylinderMesh.new()
	trunk_mesh.bottom_radius=0.24
	trunk_mesh.top_radius=0.12
	trunk_mesh.height=2.2
	trunk_mesh.radial_segments=7
	trunk.mesh=trunk_mesh
	trunk.position.y=1.1
	trunk.material_override=material(Color("776043"))
	root.add_child(trunk)
	if solid: box(root,Vector3(0,0.8,0),Vector3(0.35,1.6,0.35),Color("80654f"),true).visible=false
	for i in 3:
		var branch := box(root,Vector3(sin(i*2.1)*0.16,0.2,cos(i*2.1)*0.16),Vector3(0.17,0.45,0.18),Color("776043"))
		branch.rotation=Vector3(cos(i*2.1)*0.6,0,sin(i*2.1)*0.6)
	if pine:
		pine_crown(root,int((at.x+parent.position.x)*313+(at.z+parent.position.z)*677))
	else:
		for i in 6:
			var angle := i*2.4+at.x
			var leaf := sphere(root,Vector3(sin(angle)*0.58,2.35+sin(i*1.3)*0.35,cos(angle)*0.5),Vector3(1.7,1.45,1.7),Color("668d47").lightened(i*0.028))
			leaf.rotation.y=angle
			leaf.add_to_group("canopy")
		sphere(root,Vector3(0,3,0),Vector3(1.45,1.25,1.4),Color("91aa59")).add_to_group("canopy")
	return root

static func pine_crown(parent: Node3D, seed_value: int) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed=absi(seed_value)+71
	if cedar_crown_mesh==null:
		var source := preload("res://assets/storybook_cedar_crown_v1.glb").instantiate()
		cedar_crown_mesh=source.find_children("*","MeshInstance3D",true,false)[0].mesh
		source.free()
	var crown := MeshInstance3D.new()
	crown.mesh=cedar_crown_mesh
	crown.rotation.y=rng.randf()*TAU
	crown.scale=Vector3(1,rng.randf_range(.92,1.1),1)
	var leaves := material(Color("477661").lightened(rng.randf_range(0,0.08)))
	leaves.vertex_color_use_as_albedo=true
	leaves.cull_mode=BaseMaterial3D.CULL_DISABLED
	crown.material_override=leaves
	parent.add_child(crown)
	crown.add_to_group("canopy")

static func label3d(parent: Node3D, text: String, at: Vector3, color := Color("f5eed9")) -> Label3D:
	var l := Label3D.new()
	l.text = TranslationServer.translate(text)
	l.position = at
	l.pixel_size = 0.006
	l.font_size = 44
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.modulate = color
	l.outline_size = 7
	parent.add_child(l)
	return l

static func authored_prop(parent: Node3D, path: String, at: Vector3, span: float, height: float) -> bool:
	if not ResourceLoader.exists(path): return false
	var packed := load(path) as PackedScene
	if not packed: return false
	var model := packed.instantiate() as Node3D
	var loader = preload("res://scripts/model_loader.gd")
	var meshes: Array[MeshInstance3D]=[]
	loader._collect_meshes(model,meshes)
	var bounds := AABB()
	var first := true
	for instance in meshes:
		var b: AABB=loader._local_transform(instance,model)*instance.get_aabb()
		bounds=b if first else bounds.merge(b)
		first=false
	if bounds.size.y<=0.001 or maxf(bounds.size.x,bounds.size.z)<=0.001:
		model.free()
		return false
	var pivot := Node3D.new()
	parent.add_child(pivot)
	pivot.position=at
	pivot.scale=Vector3.ONE*minf(span/maxf(bounds.size.x,bounds.size.z),height/bounds.size.y)
	pivot.add_child(model)
	model.position-=Vector3(bounds.get_center().x,bounds.position.y,bounds.get_center().z)
	return true

static func village(parent: Node3D) -> void:
	box(parent,Vector3(0,-0.5,0),Vector3(26,1,26),Color("859b70"),true)
	box(parent,Vector3(0,-0.8,0),Vector3(27,0.5,27),Color("666e58"))
	box(parent,Vector3(0,0.015,0),Vector3(2.6,0.03,24),Color("d4c2a0"))
	box(parent,Vector3(0,0.025,-3),Vector3(20,0.03,2.2),Color("d4c2a0"))
	for i in 20:
		var z := -11.5+i*1.2
		for x in [-12.2,12.2]:
			box(parent,Vector3(x,0.5,z),Vector3(0.14,1,0.14),Color("d3bb92"))
	for x in [-12.2,12.2]: box(parent,Vector3(x,0.7,0),Vector3(0.1,0.14,24),Color("d3bb92"),true)
	for z in [-12.2,12.2]: box(parent,Vector3(0,0.5,z),Vector3(24,1,0.15),Color("9f9978"),true)
	if authored_prop(parent,"res://assets/workshop.glb",Vector3(-5,0,-5.5),4.8,4.2):
		box(parent,Vector3(-5,1.25,-5.5),Vector3(4.2,2.5,3.8),Color.WHITE,true).visible=false
	else:
		box(parent,Vector3(-5,1.25,-5.5),Vector3(3.8,2.5,3.2),Color("eddac0"),true)
		var roof := cone(parent,Vector3(-5,3.2,-5.5),3.1,1.6,Color("a65c4e"))
		roof.rotation_degrees.y = 22.5
		box(parent,Vector3(-5,0.9,-3.86),Vector3(0.8,1.8,0.1),Color("567b72"))
		for x in [-6.25,-3.75]:
			box(parent,Vector3(x,1.45,-3.83),Vector3(0.65,0.7,0.1),Color("a2c7c0"))
			box(parent,Vector3(x,1.45,-3.74),Vector3(0.06,0.7,0.05),Color("f9e8c9"))
		box(parent,Vector3(-5,0.1,-3.4),Vector3(2,0.2,0.8),Color("b19c82"))
	for p in [Vector3(-10,0,-9),Vector3(-9,0,5),Vector3(-7,0,9),Vector3(10,0,5),Vector3(7,0,10),Vector3(2,0,-10)]: tree(parent,p,false,false)
	for x in [6,8]: box(parent,Vector3(x,1.8,-5.5),Vector3(0.6,3.6,0.7),Color("627d7e"),true)
	box(parent,Vector3(7,3.55,-5.5),Vector3(3.2,0.5,1),Color("8fada4"))
	var gate := box(parent,Vector3(7,1.6,-5.5),Vector3(1.4,2.8,0.08),Color("82c1b4"))
	gate.material_override.emission_enabled = true
	gate.material_override.emission = Color("32776c")
	label3d(parent,TranslationServer.translate("일곱 밤의 숲"),Vector3(7,4.3,-5.5))
	label3d(parent,TranslationServer.translate("별씨 공방"),Vector3(-5,4.5,-5.5))
	for i in 28:
		var p := Vector3(sin(i*2.34)*10,0.06,cos(i*1.77)*10)
		if absf(p.x)<2 or (p.x< -2 and p.z< -2) or (p.x>5 and p.z< -3): continue
		sphere(parent,p,Vector3(0.16,0.18,0.16),Color("edcb79") if i%2==0 else Color("e6a796"))

static func forest(parent: Node3D) -> void:
	box(parent,Vector3(0,-0.4,0),Vector3(40,0.8,40),Color("687e67"),true)
	for i in 36:
		var angle := float(i)/36*TAU
		tree(parent,Vector3(cos(angle)*20,0,sin(angle)*20),true,false)
	for axis in [-19.0,19.0]:
		box(parent,Vector3(axis,0.6,0),Vector3(0.2,1.2,38),Color("526857"),true)
		box(parent,Vector3(0,0.6,axis),Vector3(38,1.2,0.2),Color("526857"),true)
	for i in 9:
		var a := float(i)/9*TAU
		sphere(parent,Vector3(cos(a)*0.75,0.15,sin(a)*0.75),Vector3(0.4,0.3,0.4),Color("8d9789"))
	box(parent,Vector3(0,0.15,0),Vector3(1.1,0.18,0.22),Color("7b5842"))
	box(parent,Vector3(0,0.22,0),Vector3(0.22,0.18,1.1),Color("7b5842"))
	label3d(parent,TranslationServer.translate("야영지 · F 모닥불"),Vector3(0,2,0))
