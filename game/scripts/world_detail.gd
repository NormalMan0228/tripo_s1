extends RefCounted
## Decorative geometry never changes authoritative survival obstacles or resources.
const A = preload("res://scripts/art.gd")

static func cylinder(parent: Node3D, at: Vector3, radius: float, height: float, color: Color, sides := 12, top := -1.0) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.bottom_radius=radius
	mesh.top_radius=radius if top<0 else top
	mesh.height=height
	mesh.radial_segments=sides
	node.mesh=mesh
	node.material_override=A.material(color)
	node.position=at
	parent.add_child(node)
	return node

static func rock(parent: Node3D, at: Vector3, scale: Vector3, color: Color) -> MeshInstance3D:
	var node := A.sphere(parent,at,scale,color)
	var mesh := SphereMesh.new()
	mesh.radius=0.5
	mesh.height=1
	mesh.radial_segments=7
	mesh.rings=3
	node.mesh=mesh
	node.rotation=Vector3(0.16,at.x*2.0,0.1)
	return node

static func ground(parent: Node3D, forest: bool) -> void:
	var span := 40.0 if forest else 26.0
	# The playable floor stays flat; the sculpted shoreline lies outside it.
	var floor_mesh := A.box(parent,Vector3(0,-0.22,0),Vector3(span,0.44,span),Color.WHITE,true)
	floor_mesh.visible=false
	var mat := ShaderMaterial.new()
	mat.shader=preload("res://shaders/meadow.gdshader")
	mat.set_shader_parameter("base_color",Color("394d3b") if forest else Color("657c38"))
	mat.set_shader_parameter("light_color",Color("73844b") if forest else Color("a0ac62"))
	var radius := span*0.5+0.75
	var outline: Array[Vector3]=[]
	for i in 80:
		var angle := i*TAU/80
		var exponent := 0.16 if forest else 0.3
		var x := signf(cos(angle))*pow(absf(cos(angle)),exponent)
		var z := signf(sin(angle))*pow(absf(sin(angle)),exponent)
		outline.append(Vector3(x,0,z)*(radius+sin(angle*7)*0.17))
	var turf := SurfaceTool.new()
	turf.begin(Mesh.PRIMITIVE_TRIANGLES)
	var cliff := SurfaceTool.new()
	cliff.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in outline.size():
		var p := outline[i]
		var q := outline[(i+1)%outline.size()]
		for point in [Vector3.ZERO,q,p]: turf.add_vertex(point)
		var lower_p := p*1.04+Vector3(0,-1.25,0)
		var lower_q := q*1.04+Vector3(0,-1.25,0)
		for point in [p,q,lower_p,q,lower_q,lower_p]: cliff.add_vertex(point)
	turf.generate_normals()
	cliff.generate_normals()
	var turf_node := MeshInstance3D.new()
	turf_node.mesh=turf.commit()
	turf_node.material_override=mat
	parent.add_child(turf_node)
	var cliff_node := MeshInstance3D.new()
	cliff_node.mesh=cliff.commit()
	var cliff_mat := A.material(Color("a59470"))
	cliff_mat.cull_mode=BaseMaterial3D.CULL_DISABLED
	cliff_node.material_override=cliff_mat
	parent.add_child(cliff_node)
	var water := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size=Vector2(240,240)
	plane.subdivide_width=40
	plane.subdivide_depth=40
	water.mesh=plane
	water.position.y=-1.75
	var water_mat := water_material()
	water.material_override=water_mat
	parent.add_child(water)
	# Irregular shoreline stones obscure the square platform corners.
	var rng := RandomNumberGenerator.new()
	rng.seed=5106 if forest else 718
	for i in 80:
		var p := outline[i]*1.035
		p.y=-0.95
		rock(parent,p,Vector3(rng.randf_range(0.65,1.4),rng.randf_range(0.5,0.8),rng.randf_range(0.65,1.4)),Color("8f9376").lightened(rng.randf()*0.15))
	for z in [-span*0.5+0.6,span*0.5-0.6]:
		if not forest and z>0:
			# Keep a walkable opening to the harbor, with its own rails below.
			for segment in [Vector2(-13,-8.25),Vector2(-5.75,13)]:
				A.box(parent,Vector3((segment.x+segment.y)*0.5,1,z),Vector3(segment.y-segment.x,2,0.1),Color.WHITE,true).visible=false
			continue
		var wall := A.box(parent,Vector3(0,1,z),Vector3(span,2,0.1),Color.WHITE,true)
		wall.visible=false
	for x in [-span*0.5+0.6,span*0.5-0.6]:
		var wall := A.box(parent,Vector3(x,1,0),Vector3(0.1,2,span),Color.WHITE,true)
		wall.visible=false

static func water_material() -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader=preload("res://shaders/water.gdshader")
	return mat

static func path_strip(parent: Node3D, from: Vector2, to: Vector2, width: float) -> void:
	var length := from.distance_to(to)
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var side := (to-from).normalized().orthogonal()
	var segments := maxi(2,int(length*2))
	for i in segments:
		var t := float(i)/segments
		var u := float(i+1)/segments
		var p := from.lerp(to,t)+side*sin(t*PI)*0.25
		var q := from.lerp(to,u)+side*sin(u*PI)*0.25
		var w := width*0.5+sin(i*0.7)*0.055
		for point in [p-side*w,q-side*w,p+side*w,q-side*w,q+side*w,p+side*w]: surface.add_vertex(Vector3(point.x,0.022,point.y))
	surface.generate_normals()
	var node := MeshInstance3D.new()
	node.mesh=surface.commit()
	var mat := ShaderMaterial.new()
	mat.shader=preload("res://shaders/meadow.gdshader")
	mat.set_shader_parameter("base_color",Color("b19b7a"))
	mat.set_shader_parameter("light_color",Color("ceb68f"))
	node.material_override=mat
	parent.add_child(node)
	node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var rng := RandomNumberGenerator.new()
	rng.seed=int(length*234+from.x*53)
	var density := 0.4 if width<1 else 1.6
	for i in int(length*density):
		var p := from.lerp(to,(i+0.5)/(length*density))
		var offset := (to-from).normalized().orthogonal()*rng.randf_range(-width*0.38,width*0.38)
		var stone_color := Color("a6a185") if width<1 else Color("ddc9a4")
		var slab := cylinder(parent,Vector3(p.x+offset.x,0.031,p.y+offset.y),rng.randf_range(0.08,0.17) if width<1 else rng.randf_range(0.18,0.33),0.035,stone_color.darkened(rng.randf()*0.11),6)
		slab.scale.z=0.65
		slab.rotation.y=rng.randf()*TAU

static func fence(parent: Node3D, from: Vector3, to: Vector3) -> void:
	var count := maxi(2,int(from.distance_to(to)/0.8))
	for i in count+1:
		var p := from.lerp(to,float(i)/count)
		A.box(parent,p+Vector3(0,0.48,0),Vector3(0.11,0.94,0.11),Color("bd9972"))
		A.cone(parent,p+Vector3(0,1,0),0.085,0.14,Color("e1c299"))
	for height in [0.32,0.72]:
		var rail := A.box(parent,(from+to)*0.5+Vector3(0,height,0),Vector3(0.09,0.12,from.distance_to(to)),Color("d8b388"))
		rail.rotation.y=atan2(to.x-from.x,to.z-from.z)
	var barrier := A.box(parent,(from+to)*0.5+Vector3(0,0.5,0),Vector3(0.12,1,from.distance_to(to)),Color.WHITE,true)
	barrier.rotation.y=atan2(to.x-from.x,to.z-from.z)
	barrier.visible=false

static func bench(parent: Node3D, at: Vector3, angle := 0.0) -> void:
	var root := Node3D.new()
	parent.add_child(root)
	root.position=at
	root.rotation.y=angle
	A.box(root,Vector3(0,0.6,0),Vector3(1.55,1.2,0.7),Color.WHITE,true).visible=false
	for x in [-0.62,0.62]:
		for z in [-0.23,0.23]: A.box(root,Vector3(x,0.28,z),Vector3(0.09,0.56,0.1),Color("415a4d"))
		A.box(root,Vector3(x,0.75,0.3),Vector3(0.08,1.05,0.08),Color("415a4d"))
	for z in [-0.22,0.0,0.22]: A.box(root,Vector3(0,0.58,z),Vector3(1.55,0.08,0.19),Color("bb8556"))
	for y in [0.9,1.13]: A.box(root,Vector3(0,y,0.3),Vector3(1.55,0.17,0.08),Color("cea26c"))

static func lantern(parent: Node3D, at: Vector3, tall := true) -> void:
	var height := 1.85 if tall else 0.4
	if tall:
		cylinder(parent,at+Vector3(0,0.07,0),0.24,0.14,Color("707e6c"),8)
		cylinder(parent,at+Vector3(0,height*0.5,0),0.055,height,Color("384e4a"),8)
	var glass := A.box(parent,at+Vector3(0,height+0.2,0),Vector3(0.25,0.37,0.25),Color("ffdda1"))
	glass.material_override.emission_enabled=true
	glass.material_override.emission=Color("f4b56c")
	glass.material_override.emission_energy_multiplier=0.45
	for y in [height-0.02,height+0.42]: A.box(parent,at+Vector3(0,y,0),Vector3(0.37,0.06,0.37),Color("40544b"))
	A.cone(parent,at+Vector3(0,height+0.54,0),0.29,0.22,Color("455f58"))
	var light := OmniLight3D.new()
	light.position=at+Vector3(0,height+0.2,0)
	light.light_color=Color("ffcc8b")
	light.light_energy=0.6
	light.omni_range=3
	parent.add_child(light)

static func pot(parent: Node3D, at: Vector3, flower := true) -> void:
	cylinder(parent,at+Vector3(0,0.2,0),0.2,0.4,Color("b67857"),10,0.28)
	cylinder(parent,at+Vector3(0,0.41,0),0.29,0.09,Color("ce9369"),10)
	cylinder(parent,at+Vector3(0,0.455,0),0.235,0.012,Color("5e573c"),10)
	for i in 5:
		var offset := Vector3(sin(i*2.4)*0.17,0.65+sin(i)*0.1,cos(i*2.4)*0.17)
		var leaf := A.sphere(parent,at+offset,Vector3(0.14,0.42,0.13),Color("538b53"))
		leaf.rotation.z=sin(i)*0.6
		if flower: A.sphere(parent,at+offset+Vector3(0,0.18,0),Vector3.ONE*0.17,Color("f3cb73") if i%2 else Color("ec9c8f"))

static func scatter(parent: Node3D, forest: bool) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed=782 if forest else 383
	var mesh := SurfaceTool.new()
	mesh.begin(Mesh.PRIMITIVE_TRIANGLES)
	var span := 18.5 if forest else 12.5
	for i in (2300 if forest else 1800):
		var x := rng.randf_range(-span,span)
		var z := rng.randf_range(-span,span)
		if forest:
			if Vector2(x,z).length()<2.2: continue
		else:
			if absf(x)<1.5 or absf(z+2.4)<1.3 or Vector2(x,z+1).length()<3.2: continue
			if (x< -2 and z< -2) or (x>4.8 and z< -3): continue
		var height := rng.randf_range(0.09,0.29)
		var color := Color("778951").lerp(Color("b4b97d"),rng.randf()) if forest else Color("819843").lerp(Color("b7c372"),rng.randf())
		for blade in 3:
			var angle := rng.randf()*TAU
			var offset := Vector3(cos(angle)*0.045,0,sin(angle)*0.045)
			var base := Vector3(x,0.025,z)
			mesh.set_color(color)
			mesh.add_vertex(base-offset)
			mesh.add_vertex(base+offset)
			mesh.set_color(color.lightened(0.08))
			mesh.add_vertex(base+Vector3(offset.x*2,height,offset.z*2))
		if i%9==0:
			var center := Vector3(x,height*0.7,z)
			mesh.set_color(Color("f7df9b") if i%2 else Color("ecd5c0"))
			mesh.add_vertex(center+Vector3(-0.07,0,0))
			mesh.add_vertex(center+Vector3(0.07,0,0))
			mesh.add_vertex(center+Vector3(0,0.11,0.025))
	mesh.generate_normals()
	var instance := MeshInstance3D.new()
	instance.mesh=mesh.commit()
	var mat := ShaderMaterial.new()
	mat.shader=preload("res://shaders/foliage.gdshader")
	instance.material_override=mat
	instance.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(instance)

static func workshop(parent: Node3D) -> void:
	A.authored_prop(parent,"res://assets/workshop.glb",Vector3(-5,0,-5.5),4.8,4.2)
	A.box(parent,Vector3(-5,1.25,-5.5),Vector3(4.2,2.5,3.8),Color.WHITE,true).visible=false
	fence(parent,Vector3(-7.8,0,-7.7),Vector3(-7.8,0,-2.2))
	fence(parent,Vector3(-7.8,0,-7.7),Vector3(-2.3,0,-7.7))
	for p in [Vector3(-7.1,0,-2.8),Vector3(-3,0,-3),Vector3(-6.6,0,-2.5)]: pot(parent,p)
	bench(parent,Vector3(-7,0,-4),PI*0.5)
	lantern(parent,Vector3(-2.55,0,-3.1))
	# A useful-looking work table and painted samples explain the workshop visually.
	A.box(parent,Vector3(-3,0.8,-6.9),Vector3(1.45,0.12,0.62),Color("b58b58"))
	for x in [-3.6,-2.4]: A.box(parent,Vector3(x,0.4,-6.9),Vector3(0.1,0.8,0.4),Color("826449"))
	for i in 3: cylinder(parent,Vector3(-3.45+i*0.4,0.98,-6.9),0.12,0.25,[Color("d38367"),Color("dda94b"),Color("649f98")][i],10)
	A.label3d(parent,TranslationServer.translate("별씨 공방"),Vector3(-5,3.95,-5),Color("fff1c8"))

static func gate(parent: Node3D, origin := Vector3(7,0,-5.5)) -> void:
	var arch := preload("res://assets/departure_arch.glb").instantiate() as Node3D
	parent.add_child(arch);arch.position=origin
	var portal := MeshInstance3D.new()
	var plane := QuadMesh.new();plane.size=Vector2(1.94,3.26)
	portal.mesh=plane;portal.position=origin+Vector3(0,1.63,.035)
	portal.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(portal)
	var mat := ShaderMaterial.new()
	mat.shader=preload("res://shaders/portal.gdshader")
	portal.material_override=mat
	lantern(parent,origin+Vector3(-1.7,0,1.3),false)
	lantern(parent,origin+Vector3(1.7,0,1.3),false)
	A.label3d(parent,TranslationServer.translate("일곱 밤의 숲"),origin+Vector3(0,4.25,0),Color("f0e4bb")).font_size=30
	for i in 4: cylinder(parent,origin+Vector3(0,0.025,1+i*0.55),0.75,0.05,Color("aeb39a"),7).scale.z=0.38

static func village(parent: Node3D, expanded := false) -> void:
	if not expanded: ground(parent,false)
	if not expanded:
		path_strip(parent,Vector2(0,12),Vector2(0,-10),2.3)
		path_strip(parent,Vector2(-8,-2.4),Vector2(8,-2.4),1.85)
		path_strip(parent,Vector2(-5,-2.5),Vector2(-5,-4),1.8)
	cylinder(parent,Vector3(0,0.027,-1),3,0.045,Color("b7a37e"),48)
	cylinder(parent,Vector3(0,0.055,-1),2.7,0.045,Color("d9c4a0"),48)
	for i in 24:
		var angle := i*TAU/24
		var p := Vector3(cos(angle)*2.83,0.07,-1+sin(angle)*2.83)
		var stone := A.box(parent,p,Vector3(0.32,0.045,0.21),Color("e8d8b9"))
		stone.rotation.y=-angle
	workshop(parent)
	gate(parent)
	var rng := RandomNumberGenerator.new()
	rng.seed=519
	for i in (0 if expanded else 19):
		var p := Vector3(-11.5 if i%2==0 else 11.6,0,-10.5+(i/2)*2.6)
		p.x+=rng.randf_range(-0.4,0.4)
		A.tree(parent,p,false,true)
	if not expanded:
		for p in [Vector3(-10,0,-10),Vector3(-6,0,-11),Vector3(-2,0,-11),Vector3(3,0,-11),Vector3(9,0,-10)]: A.tree(parent,p,false,true)
	for i in 9:
		if expanded and i<4:continue # Keep the authored home and front path clear.
		var p := Vector3(-10.8,0.23,-10+i*2.6)
		rock(parent,p,Vector3(0.65,0.5,0.8),Color("909579"))
	for side in [-1.0,1.0]:
		if not expanded and side>0: fence(parent,Vector3(1.7,0,11.6),Vector3(9,0,11.6))
		elif not expanded:
			fence(parent,Vector3(-1.7,0,11.6),Vector3(-5.5,0,11.6))
			fence(parent,Vector3(-8.5,0,11.6),Vector3(-10,0,11.6))
		lantern(parent,Vector3(side*1.65,0,8.2))
		lantern(parent,Vector3(side*2.1,0,-1))
	# A harbor overlook beyond the decoration area gives the island a destination.
	for i in 12: A.box(parent,Vector3(-7,-0.06,12+i*0.34),Vector3(2.5,0.2,0.3),Color("ab8962").lightened((i%3)*0.03))
	A.box(parent,Vector3(-7,-0.12,13.8),Vector3(2.5,0.3,4.3),Color.WHITE,true).visible=false
	for x in [-8.25,-5.75]:
		fence(parent,Vector3(x,0,12),Vector3(x,0,15.8))
		A.box(parent,Vector3(x,0.8,14),Vector3(0.1,1.6,4),Color.WHITE,true).visible=false
	fence(parent,Vector3(-8.25,0,15.9),Vector3(-5.75,0,15.9))
	A.box(parent,Vector3(-7,0.8,15.9),Vector3(2.5,1.6,0.1),Color.WHITE,true).visible=false
	for x in [-8.35,-5.65]:
		for z in [12.2,14,15.7]: cylinder(parent,Vector3(x,-0.5,z),0.12,2.1,Color("735d43"),8)
	bench(parent,Vector3(-9.3,0,10.6),PI)
	if not expanded: path_strip(parent,Vector2(-7,9.4),Vector2(-7,12),1.6)
	if not expanded: A.label3d(parent,TranslationServer.translate("바람 선착장"),Vector3(-7,2.2,15.5),Color("ead9b2"))
	scatter(parent,false)
