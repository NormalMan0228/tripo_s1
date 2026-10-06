extends RefCounted
## Procedural art for village life: soil beds, crops by growth stage, gather nodes,
## fish, ripple rings and particle bursts. Chunky low-poly shapes with soft colours
## that keep a clear silhouette from the follow camera (28 degrees, orthographic).

static var mats := {}
static var meshes := {}

static func mat(c: Color, rough := 0.85, emit := 0.0, unshaded := false) -> StandardMaterial3D:
	var key := "%s/%.2f/%.2f/%s" % [c.to_html(), rough, emit, unshaded]
	if mats.has(key): return mats[key]
	var m := StandardMaterial3D.new()
	m.albedo_color=c
	m.roughness=rough
	m.cull_mode=BaseMaterial3D.CULL_DISABLED
	if c.a<0.999: m.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	if emit>0:
		m.emission_enabled=true
		m.emission=c
		m.emission_energy_multiplier=emit
	if unshaded: m.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	mats[key]=m
	return m

static func mesh(kind: String) -> Mesh:
	if meshes.has(kind): return meshes[kind]
	var m: Mesh
	match kind:
		"ball":
			m=SphereMesh.new(); m.radius=0.5; m.height=1.0; m.radial_segments=14; m.rings=7
		"facet":
			m=SphereMesh.new(); m.radius=0.5; m.height=1.0; m.radial_segments=7; m.rings=4
		"dome":
			m=SphereMesh.new(); m.radius=0.5; m.height=0.5; m.is_hemisphere=true; m.radial_segments=14; m.rings=5
		"rod":
			m=CylinderMesh.new(); m.top_radius=0.5; m.bottom_radius=0.5; m.height=1.0; m.radial_segments=7; m.rings=1
		"cone":
			m=CylinderMesh.new(); m.top_radius=0.0; m.bottom_radius=0.5; m.height=1.0; m.radial_segments=10; m.rings=1
		"capsule":
			m=CapsuleMesh.new(); m.radius=0.5; m.height=2.0; m.radial_segments=10; m.rings=3
		"box":
			m=BoxMesh.new()
		"leaf": m=leaf_mesh(false)
		"frond": m=leaf_mesh(true)
		"ring": m=ring_mesh()
		"quad":
			m=QuadMesh.new(); m.size=Vector2(0.2,0.2)
		"petal":
			m=SphereMesh.new(); m.radius=0.5; m.height=1.0; m.radial_segments=8; m.rings=4
	meshes[kind]=m
	return m

## A leaf lying along +Z with a folded midrib and an upward curl at the tip.
static func leaf_mesh(thin: bool) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var steps := 7
	var rows: Array=[]
	for i in steps+1:
		var t := float(i)/steps
		var w := sin(PI*pow(t,0.8))*(0.16 if thin else 0.5)
		var y := t*t*0.35
		rows.append([Vector3(-w,y+w*0.25,t),Vector3(0,y,t),Vector3(w,y+w*0.25,t)])
	for i in steps:
		var a: Array=rows[i]
		var b: Array=rows[i+1]
		for side in 2:
			var p0: Vector3=a[side]; var p1: Vector3=a[side+1]; var q0: Vector3=b[side]; var q1: Vector3=b[side+1]
			for v in [p0,q0,p1,p1,q0,q1]:
				st.set_normal(Vector3.UP)
				st.add_vertex(v)
	st.generate_normals()
	return st.commit()

static func ring_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var n := 40
	for i in n:
		var a := TAU*i/n
		var b := TAU*(i+1)/n
		var o0 := Vector3(cos(a),0,sin(a)); var o1 := Vector3(cos(b),0,sin(b))
		for v in [o0*0.86,o0,o1*0.86,o1*0.86,o0,o1]:
			st.set_normal(Vector3.UP)
			st.add_vertex(v)
	return st.commit()

static func part(parent: Node3D, kind: String, at: Vector3, size: Vector3, color: Color, rot := Vector3.ZERO, rough := 0.85) -> MeshInstance3D:
	var m := MeshInstance3D.new()
	m.mesh=mesh(kind)
	m.position=at
	m.rotation=rot
	m.scale=size
	m.material_override=mat(color,rough)
	m.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if size.length()<0.25 else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	parent.add_child(m)
	return m

## Leaf rooted at `at`, pointing toward yaw, tipped up by pitch (radians from flat).
static func leaf(parent: Node3D, at: Vector3, yaw: float, pitch: float, length: float, color: Color, thin := false) -> MeshInstance3D:
	var m := part(parent,"frond" if thin else "leaf",at,Vector3.ONE*length,color)
	m.basis=Basis(Vector3.UP,yaw)*Basis(Vector3.RIGHT,-pitch)
	m.scale=Vector3.ONE*length
	return m

# ---------------------------------------------------------------- soil

static func bed(wet: bool) -> Node3D:
	var root := Node3D.new()
	var soil := Color("5c412d") if wet else Color("9b7650")
	var ridge := Color("4d3524") if wet else Color("8a6644")
	var rough := 0.42 if wet else 0.95
	part(root,"box",Vector3(0,0.02,0),Vector3(1.62,0.16,1.62),soil.darkened(0.08),Vector3.ZERO,rough)
	part(root,"box",Vector3(0,0.06,0),Vector3(1.5,0.16,1.5),soil,Vector3.ZERO,rough)
	for z in [-0.45,0.0,0.45]:
		part(root,"capsule",Vector3(0,0.15,z),Vector3(0.15,0.68,0.15),ridge,Vector3(0,0,PI/2),rough)
	if wet:
		for i in 3: part(root,"dome",Vector3(-0.5+i*0.45,0.13,0.22-i*0.2),Vector3(0.3,0.05,0.22),Color("3f2c1e"),Vector3.ZERO,0.25)
	return root

static func ghost(valid: bool) -> Node3D:
	var root := Node3D.new()
	var c := Color(0.55,0.95,0.55,0.9) if valid else Color(1.0,0.45,0.4,0.9)
	for i in 4:
		var bar := part(root,"box",Vector3.ZERO,Vector3(1.6,0.06,0.08),c)
		bar.material_override=mat(c,1.0,0.0,true)
		var side := i%2==1
		bar.position=Vector3((0.78 if i==1 else -0.78) if side else 0.0,0.08,0.0 if side else (0.78 if i==0 else -0.78))
		if side: bar.rotation.y=PI/2
	var fill := part(root,"box",Vector3(0,0.05,0),Vector3(1.5,0.02,1.5),Color(c,0.22))
	fill.material_override=mat(Color(c,0.22),1.0,0.0,true)
	return root

# ---------------------------------------------------------------- crops

## Bed layouts: plant offsets per crop.
const SPOTS := {"turnip":[Vector2(-0.38,-0.38),Vector2(0.38,-0.38),Vector2(-0.38,0.38),Vector2(0.38,0.38)],
	"carrot":[Vector2(-0.38,-0.38),Vector2(0.38,-0.38),Vector2(-0.38,0.38),Vector2(0.38,0.38)],
	"strawberry":[Vector2(-0.36,-0.3),Vector2(0.36,0.3)],"pumpkin":[Vector2(0,0)],"sunflower":[Vector2(-0.35,0.05),Vector2(0.35,-0.05)]}
const LEAF := {"turnip":Color("6aac5a"),"carrot":Color("4f9a48"),"pumpkin":Color("5f9c4a"),"strawberry":Color("4d8f45"),"sunflower":Color("5c9a3e")}

## stage: 1 seeds, 2 sprout, 3 leafy, 4 flowering, 5 ripe.
static func crop(kind: String, stage: int, seed_value: int) -> Node3D:
	var root := Node3D.new()
	var rng := RandomNumberGenerator.new()
	rng.seed=seed_value
	for spot in SPOTS.get(kind,SPOTS.turnip):
		var plant := Node3D.new()
		plant.position=Vector3(spot.x,0.14,spot.y)
		plant.rotation.y=rng.randf()*TAU
		plant.scale=Vector3.ONE*rng.randf_range(0.92,1.08)
		root.add_child(plant)
		if stage<=1:
			for i in 3: part(plant,"ball",Vector3(sin(i*2.1)*0.06,0.02,cos(i*2.1)*0.06),Vector3(0.05,0.035,0.05),Color("e8d39a"))
			continue
		if stage==2:
			for i in 2: leaf(plant,Vector3(0,0.06,0),i*PI+0.4,0.5,0.16,LEAF[kind].lightened(0.25))
			part(plant,"rod",Vector3(0,0.04,0),Vector3(0.02,0.1,0.02),LEAF[kind].lightened(0.2))
			continue
		match kind:
			"carrot": _carrot(plant,stage,rng)
			"pumpkin": _pumpkin(plant,stage,rng)
			"strawberry": _strawberry(plant,stage,rng)
			"sunflower": _sunflower(plant,stage,rng)
			_: _turnip(plant,stage,rng)
	return root

static func _turnip(p: Node3D, stage: int, rng: RandomNumberGenerator) -> void:
	var n := 5 if stage==3 else 7
	for i in n: leaf(p,Vector3(0,0.05,0),TAU*i/n+rng.randf()*0.4,0.75+rng.randf()*0.3,0.3 if stage==3 else 0.42,LEAF.turnip.lerp(Color("8cc070"),rng.randf()*0.4))
	if stage>=4:
		var s := 0.16 if stage==4 else 0.3
		part(p,"ball",Vector3(0,s*0.25,0),Vector3(s,s*0.9,s),Color("f1ece6"))
		part(p,"dome",Vector3(0,s*0.32,0),Vector3(s*1.02,s*0.9,s*1.02),Color("b05aa0"))

static func _carrot(p: Node3D, stage: int, rng: RandomNumberGenerator) -> void:
	var n := 6 if stage==3 else 9
	for i in n: leaf(p,Vector3(0,0.05,0),TAU*i/n+rng.randf()*0.3,1.0+rng.randf()*0.25,0.34 if stage==3 else 0.5,LEAF.carrot.lerp(Color("78b860"),rng.randf()*0.5),true)
	if stage>=4:
		var s := 0.12 if stage==4 else 0.2
		part(p,"cone",Vector3(0,-0.02,0),Vector3(s,s*1.2,s),Color("ee8a2f"),Vector3(PI,0,0))
		part(p,"dome",Vector3(0,0.0,0),Vector3(s,s*0.6,s),Color("f39a3c"))

static func _pumpkin(p: Node3D, stage: int, rng: RandomNumberGenerator) -> void:
	var n := 4 if stage==3 else 6
	for i in n:
		var a := TAU*i/n+rng.randf()*0.4
		part(p,"rod",Vector3(sin(a)*0.25,0.03,cos(a)*0.25),Vector3(0.025,0.5,0.025),Color("6d9a43"),Vector3(PI/2,a,0))
		leaf(p,Vector3(sin(a)*0.45,0.05,cos(a)*0.45),a,0.35,0.42 if stage==3 else 0.5,LEAF.pumpkin.lerp(Color("7fb35d"),rng.randf()*0.4))
	if stage==4:
		for i in 3:
			var a := TAU*i/3+0.5
			var f := Vector3(sin(a)*0.3,0.18,cos(a)*0.3)
			part(p,"cone",f,Vector3(0.14,0.16,0.14),Color("f7c843"),Vector3(PI,0,0))
	if stage>=5:
		var body := Node3D.new()
		body.position=Vector3(0,0.24,0)
		p.add_child(body)
		for i in 8:
			var a := TAU*i/8
			part(body,"ball",Vector3(sin(a)*0.15,0,cos(a)*0.15),Vector3(0.26,0.42,0.26),Color("e8862e").lerp(Color("f29a3a"),float(i%2)))
		part(body,"ball",Vector3.ZERO,Vector3(0.5,0.4,0.5),Color("e07f2a"))
		part(body,"rod",Vector3(0,0.24,0),Vector3(0.05,0.14,0.05),Color("6b5a2c"),Vector3(0.2,0,0.1))

static func _strawberry(p: Node3D, stage: int, rng: RandomNumberGenerator) -> void:
	var n := 6 if stage==3 else 8
	for i in n:
		var a := TAU*i/n+rng.randf()*0.3
		for j in 3: leaf(p,Vector3(sin(a)*0.06,0.08,cos(a)*0.06),a+(j-1)*0.45,0.45,0.2 if stage==3 else 0.24,LEAF.strawberry.lerp(Color("6eae55"),rng.randf()*0.4))
	if stage>=4:
		for i in 3:
			var a := TAU*i/3+0.3
			var at := Vector3(sin(a)*0.22,0.17,cos(a)*0.22)
			if stage==4 or i==0:
				for k in 5: part(p,"petal",at+Vector3(sin(k*1.256)*0.035,0,cos(k*1.256)*0.035),Vector3(0.05,0.015,0.05),Color("fbf6ee"))
				part(p,"ball",at+Vector3(0,0.01,0),Vector3(0.03,0.02,0.03),Color("f4cf3e"))
			else:
				part(p,"cone",at+Vector3(0,-0.02,0),Vector3(0.11,0.14,0.11),Color("e0333f"),Vector3(PI,0,0))
				part(p,"dome",at+Vector3(0,0.03,0),Vector3(0.1,0.06,0.1),Color("56a043"))
	if stage>=5:
		for i in 2: part(p,"cone",Vector3(sin(i*3.0+1.5)*0.2,0.1,cos(i*3.0+1.5)*0.2),Vector3(0.12,0.15,0.12),Color("ea3a45"),Vector3(PI,0,0))

static func _sunflower(p: Node3D, stage: int, rng: RandomNumberGenerator) -> void:
	var h := 0.45 if stage==3 else (1.05 if stage==4 else 1.3)
	part(p,"rod",Vector3(0,h*0.5,0),Vector3(0.05,h,0.05),Color("6a9c3c"))
	p.rotation.y=0
	for i in (3 if stage==3 else 5):
		var y := 0.12+i*h*0.18
		leaf(p,Vector3(0,y,0),i*2.4,0.25,0.3,LEAF.sunflower.lerp(Color("82b85a"),rng.randf()*0.4))
	if stage>=4:
		var head := Node3D.new()
		head.position=Vector3(0,h,0.03)
		head.rotation.x=0.55
		p.add_child(head)
		if stage==4:
			part(head,"ball",Vector3.ZERO,Vector3(0.16,0.12,0.16),Color("6e9d3f"))
			for k in 8: part(head,"petal",Vector3(sin(k*0.785)*0.08,0.04,cos(k*0.785)*0.08),Vector3(0.05,0.03,0.09),Color("f2cf45"),Vector3(0,k*0.785,0))
		else:
			for k in 14:
				var a := TAU*k/14
				part(head,"petal",Vector3(sin(a)*0.2,0,cos(a)*0.2),Vector3(0.1,0.03,0.2),Color("f6c531").lerp(Color("f9db5a"),float(k%2)),Vector3(0,a,0))
			part(head,"dome",Vector3(0,0.01,0),Vector3(0.28,0.12,0.28),Color("6a4325"))

## Gentle twinkles over a ripe bed.
static func sparkles(parent: Node3D, height: float) -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.amount=5
	p.lifetime=1.3
	p.mesh=mesh("quad")
	p.material_override=star_material()
	p.emission_shape=CPUParticles3D.EMISSION_SHAPE_BOX
	p.emission_box_extents=Vector3(0.65,0.1,0.65)
	p.position=Vector3(0,height,0)
	p.gravity=Vector3(0,0.35,0)
	p.initial_velocity_min=0.05
	p.initial_velocity_max=0.15
	p.scale_amount_min=0.5
	p.scale_amount_max=1.0
	var curve := Curve.new()
	curve.add_point(Vector2(0,0)); curve.add_point(Vector2(0.3,1)); curve.add_point(Vector2(1,0))
	p.scale_amount_curve=curve
	parent.add_child(p)
	return p

static var star: StandardMaterial3D
static func star_material() -> StandardMaterial3D:
	if star: return star
	var img := Image.create(32,32,false,Image.FORMAT_RGBA8)
	for y in 32:
		for x in 32:
			var d := Vector2(x-15.5,y-15.5)
			var v := clampf(1.0-(absf(d.x)*absf(d.y))/18.0-d.length()/20.0,0,1)
			img.set_pixel(x,y,Color(1,0.95,0.7,v))
	star=StandardMaterial3D.new()
	star.albedo_texture=ImageTexture.create_from_image(img)
	star.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	star.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	star.blend_mode=BaseMaterial3D.BLEND_MODE_ADD
	star.billboard_mode=BaseMaterial3D.BILLBOARD_PARTICLES
	star.albedo_color=Color(1,0.92,0.55)
	star.no_depth_test=false
	return star

# ---------------------------------------------------------------- gather nodes

const FLOWER_COLORS := [Color("f27fae"),Color("b98cf0"),Color("f7cf3a"),Color("f0705f"),Color("7fb6f2")]

static func forage(kind: String, seed_value: int) -> Node3D:
	var root := Node3D.new()
	var rng := RandomNumberGenerator.new()
	rng.seed=seed_value
	match kind:
		"rock":
			var grey := Color("9ea3a2").lerp(Color("b4ab9c"),rng.randf())
			part(root,"facet",Vector3(0,0.2,0),Vector3(0.78,0.52,0.66),grey,Vector3(0,rng.randf()*TAU,0.15))
			part(root,"facet",Vector3(0.36,0.1,0.18),Vector3(0.38,0.3,0.36),grey.darkened(0.1),Vector3(0.3,rng.randf()*TAU,0))
			part(root,"facet",Vector3(-0.3,0.08,0.24),Vector3(0.26,0.2,0.24),grey.lightened(0.08))
			if seed_value%3==0:
				for i in 3: part(root,"facet",Vector3(-0.15+i*0.14,0.43,0.1-i*0.05),Vector3(0.09,0.1,0.09),Color("d58a4a"),Vector3.ZERO,0.35)
			part(root,"dome",Vector3(-0.1,0.38,-0.05),Vector3(0.3,0.1,0.26),Color("7fa35c"))
		"shell":
			var tint: Color=[Color("f5c9b8"),Color("f7e2c4"),Color("e9b7c9")][seed_value%3]
			var fan := Node3D.new()
			fan.position=Vector3(0,0.05,0)
			fan.rotation=Vector3(-0.35,rng.randf()*TAU,0)
			root.add_child(fan)
			for i in 7:
				var a := -1.1+i*0.366
				part(fan,"capsule",Vector3(sin(a)*0.12,0,cos(a)*0.12),Vector3(0.085,0.13,0.06),tint.lerp(Color.WHITE,float(i%2)*0.35),Vector3(PI/2,a,0))
			part(fan,"box",Vector3(0,0,-0.03),Vector3(0.12,0.05,0.06),tint.darkened(0.15))
			part(root,"cone",Vector3(0.28,0.07,0.15),Vector3(0.14,0.3,0.14),Color("f0d2a8"),Vector3(0,0,PI/2.4))
			part(root,"ball",Vector3(0.2,0.07,0.15),Vector3(0.15,0.14,0.15),Color("e2b07f"))
		"flower":
			var c: Color=FLOWER_COLORS[seed_value%FLOWER_COLORS.size()]
			for i in 6:
				var at := Vector3(rng.randf_range(-0.28,0.28),0,rng.randf_range(-0.28,0.28))
				var h := rng.randf_range(0.32,0.55)
				part(root,"rod",at+Vector3(0,h*0.5,0),Vector3(0.025,h,0.025),Color("5f9c47"))
				leaf(root,at+Vector3(0,0.05,0),rng.randf()*TAU,0.6,0.16,Color("6aa54f"))
				var head := Node3D.new()
				head.position=at+Vector3(0,h,0)
				head.rotation.x=0.5
				root.add_child(head)
				for k in 5: part(head,"petal",Vector3(sin(k*1.256)*0.06,0,cos(k*1.256)*0.06),Vector3(0.075,0.025,0.11),c.lerp(Color.WHITE,rng.randf()*0.25),Vector3(0,k*1.256,0))
				part(head,"ball",Vector3(0,0.015,0),Vector3(0.05,0.035,0.05),Color("f6cf47"))
		"mushroom":
			var red := seed_value%2==0
			for i in 3:
				var at := Vector3(-0.2+i*0.2+rng.randf_range(-0.05,0.05),0,rng.randf_range(-0.15,0.15))
				var s: float=[0.32,0.22,0.16][i]
				part(root,"rod",at+Vector3(0,s*0.45,0),Vector3(s*0.32,s*0.9,s*0.32),Color("f3e8d2"))
				var cap := part(root,"dome",at+Vector3(0,s*0.82,0),Vector3(s*1.25,s*1.1,s*1.25),Color("d9473d") if red else Color("a8714a"),Vector3(rng.randf_range(-0.2,0.2),0,rng.randf_range(-0.2,0.2)))
				if red:
					for k in 4: part(cap,"ball",Vector3(sin(k*1.7)*0.3,0.3,cos(k*1.7)*0.3),Vector3(0.14,0.06,0.14),Color("fff7ec"))
			for i in 4: leaf(root,Vector3(rng.randf_range(-0.3,0.3),0.02,rng.randf_range(-0.3,0.3)),rng.randf()*TAU,0.2,0.18,Color("5d8a3e"))
		"herb":
			for i in 9:
				var a := TAU*i/9+rng.randf()*0.3
				leaf(root,Vector3(sin(a)*0.05,0.02,cos(a)*0.05),a,1.05+rng.randf()*0.2,rng.randf_range(0.38,0.5),Color("8ccf6c").lerp(Color("5fae5c"),rng.randf()),true)
			for i in 4:
				var at := Vector3(rng.randf_range(-0.15,0.15),rng.randf_range(0.36,0.48),rng.randf_range(-0.15,0.15))
				part(root,"ball",at,Vector3(0.06,0.06,0.06),Color("f4f1fb"))
		"branch":
			for i in 3:
				var len := rng.randf_range(0.7,1.0)
				var stick := part(root,"rod",Vector3(rng.randf_range(-0.1,0.1),0.05+i*0.05,rng.randf_range(-0.1,0.1)),Vector3(0.06,len,0.06),Color("8a6443").lerp(Color("a77d55"),rng.randf()),Vector3(PI/2,rng.randf()*TAU,0))
				part(stick,"rod",Vector3(0.0,0.2,0.0),Vector3(0.5,0.35,0.5),Color("7c5a3c"),Vector3(0,0,0.7))
			for i in 3: leaf(root,Vector3(rng.randf_range(-0.3,0.3),0.12,rng.randf_range(-0.3,0.3)),rng.randf()*TAU,0.15,0.16,Color("9bbf5c"))
	return root

# ---------------------------------------------------------------- fish

## Look of each fish: body, belly, accent, length:height, shape.
const FISH_LOOK := {
	"perch":[Color("7d9a4a"),Color("e9e2b8"),Color("3f5a2a"),2.6,"striped"],
	"crucian":[Color("9a8a5a"),Color("e2d9b4"),Color("6d5f3a"),2.2,"plain"],
	"carp":[Color("b08a4c"),Color("ead7a8"),Color("7a5a2e"),2.7,"plain"],
	"catfish":[Color("5a5650"),Color("c9c0aa"),Color("2f2c28"),3.6,"whisker"],
	"koi":[Color("f4f0e8"),Color("fff9f0"),Color("ec7a2a"),2.7,"spotted"],
	"mackerel":[Color("4d7f9a"),Color("eef3f2"),Color("1f3d55"),3.2,"striped"],
	"puffer":[Color("d7c27a"),Color("f6efd6"),Color("6b5a2a"),1.4,"puffer"],
	"squid":[Color("e3b5c9"),Color("f6e2ea"),Color("b5638a"),2.6,"squid"],
	"tuna":[Color("2f4f74"),Color("dfe6ea"),Color("f1c84a"),3.3,"plain"],
	"silverfish":[Color("c7ced6"),Color("f5f7f8"),Color("e58e8e"),2.4,"plain"],
	"sweetfish":[Color("a9b49a"),Color("f1efe3"),Color("e5c24a"),3.2,"plain"],
	"rainbow":[Color("8a9e86"),Color("f2e8e0"),Color("e3788a"),3.0,"rainbow"],
	"eel":[Color("4a5a3a"),Color("b9b58f"),Color("2f3a25"),7.0,"eel"],
	"trout":[Color("7f8a6a"),Color("efe7d2"),Color("3d4630"),3.0,"spotted"],
}

static func fish(kind: String, length := 0.6) -> Node3D:
	var look: Array=FISH_LOOK.get(kind,FISH_LOOK.perch)
	var root := Node3D.new()
	var body: Color=look[0]
	var belly: Color=look[1]
	var accent: Color=look[2]
	var ratio: float=look[3]
	var shape: String=look[4]
	var h := length/ratio
	if shape=="squid":
		part(root,"cone",Vector3(0,0,-length*0.15),Vector3(h*1.1,length*0.7,h*0.9),body,Vector3(-PI/2,0,0))
		for i in 6: part(root,"capsule",Vector3(-h*0.4+i*h*0.16,0,length*0.32),Vector3(0.05*length,0.18*length,0.05*length),accent,Vector3(PI/2+0.2*sin(i),0,0))
		for s in [-1,1]: part(root,"ball",Vector3(s*h*0.35,h*0.1,length*0.15),Vector3.ONE*h*0.25,Color("1c1c22"))
		return root
	part(root,"ball",Vector3.ZERO,Vector3(h*0.62,h,length*0.8),body,Vector3.ZERO,0.45)
	part(root,"ball",Vector3(0,-h*0.18,0.02),Vector3(h*0.56,h*0.7,length*0.7),belly,Vector3.ZERO,0.45)
	if shape!="eel":
		part(root,"cone",Vector3(0,0,-length*0.48),Vector3(h*0.12,h*0.55,h*0.9),body.darkened(0.12),Vector3(PI/2,0,0))
		part(root,"cone",Vector3(0,h*0.48,-length*0.05),Vector3(h*0.08,h*0.35,length*0.35),accent,Vector3(0,0,0))
	if shape=="puffer":
		for i in 10:
			var a := TAU*i/10
			part(root,"cone",Vector3(cos(a)*h*0.3,sin(a)*h*0.5,0),Vector3(0.03,0.08,0.03)*length*4,belly.darkened(0.2),Vector3(0,0,a-PI/2))
	if shape=="striped":
		for i in 4: part(root,"box",Vector3(0,h*0.15,-length*0.25+i*length*0.14),Vector3(h*0.64,h*0.6,length*0.04),accent)
	if shape in ["spotted"]:
		for i in 6: part(root,"ball",Vector3(h*0.3*(1 if i%2 else -1),h*(0.2-0.08*(i%3)),-length*0.2+i*length*0.08),Vector3.ONE*h*0.14,accent)
	if shape=="rainbow":
		part(root,"ball",Vector3(0,0,0),Vector3(h*0.64,h*0.25,length*0.7),accent)
	if shape=="whisker":
		for s in [-1,1]: part(root,"rod",Vector3(s*h*0.25,-h*0.1,length*0.45),Vector3(0.012,length*0.25,0.012),accent,Vector3(PI/2-0.4,0,s*0.6))
	for s in [-1,1]:
		part(root,"ball",Vector3(s*h*0.28,h*0.12,length*0.3),Vector3.ONE*h*0.2,Color.WHITE)
		part(root,"ball",Vector3(s*h*0.31,h*0.12,length*0.31),Vector3.ONE*h*0.12,Color("1c1c22"))
	return root

# ---------------------------------------------------------------- effects

## Flat ring that widens and fades on a water surface.
static func ripple(parent: Node3D, at: Vector3, radius := 0.9, time := 1.1, color := Color(1,1,1,0.7)) -> void:
	var ring := MeshInstance3D.new()
	ring.mesh=mesh("ring")
	var m := StandardMaterial3D.new()
	m.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	m.albedo_color=color
	m.cull_mode=BaseMaterial3D.CULL_DISABLED
	ring.material_override=m
	ring.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	ring.position=at+Vector3(0,0.03,0)
	ring.scale=Vector3.ONE*0.12
	parent.add_child(ring)
	var t := ring.create_tween().set_parallel(true)
	t.tween_property(ring,"scale",Vector3.ONE*radius,time).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_CUBIC)
	t.tween_property(m,"albedo_color:a",0.0,time).set_ease(Tween.EASE_IN)
	t.chain().tween_callback(ring.queue_free)

## One-shot particle puff: dust, dirt, splash, petals, leaves, sparks, seeds, drops.
static func burst(parent: Node3D, at: Vector3, kind: String, amount := 14) -> void:
	var p := CPUParticles3D.new()
	p.one_shot=true
	p.explosiveness=0.92
	p.amount=amount
	p.lifetime=0.9
	p.position=at
	var colors := {"dust":Color("cbb89a"),"dirt":Color("7a5638"),"splash":Color("e6f6ff"),"petal":Color("f6a8c8"),
		"leaf":Color("8fc46a"),"spark":Color("ffe48a"),"seed":Color("e5cf8e"),"drop":Color("8fd0f2"),"sand":Color("f0dcae"),"spore":Color("f4ead2")}
	var c: Color=colors.get(kind,Color.WHITE)
	var m := mat(c,0.6,0.6 if kind=="spark" else 0.0)
	p.mesh=mesh("facet" if kind in ["dirt","dust","sand","seed"] else ("petal" if kind in ["petal","leaf"] else "ball"))
	p.material_override=m
	p.direction=Vector3.UP
	p.spread=55 if kind!="drop" else 20
	p.initial_velocity_min=1.4
	p.initial_velocity_max=3.2 if kind!="spore" else 1.2
	p.gravity=Vector3(0,-9 if kind not in ["petal","leaf","spore","spark"] else -2.2,0)
	p.scale_amount_min=0.06
	p.scale_amount_max=0.13 if kind not in ["splash","drop"] else 0.1
	p.angular_velocity_min=-300
	p.angular_velocity_max=300
	if kind=="drop":
		p.direction=Vector3(0,-1,0)
		p.initial_velocity_min=0.5
		p.initial_velocity_max=1.2
		p.emission_shape=CPUParticles3D.EMISSION_SHAPE_BOX
		p.emission_box_extents=Vector3(0.5,0.05,0.5)
		p.explosiveness=0.2
		p.lifetime=0.5
	p.emitting=true
	parent.add_child(p)
	p.finished.connect(p.queue_free)
