extends Node3D
## A continuous walkable landscape with sloped terraces, river bridges and a lake.
const A=preload("res://scripts/art.gd")
const L=preload("res://scripts/world_detail.gd")
const HOME_POSITION=Vector3(-10.8,0,-7)
const HOME_DOOR=Vector3(-10.8,0,-4.2)
const HOME_RETURN=Vector3(-10.8,.1,-3.7)
const PLOTS=[Vector2(-25,-8),Vector2(-22,-8),Vector2(-19,-8),Vector2(-25,-4),Vector2(-22,-4),Vector2(-19,-4)]
const PLACES=[
	{"id":"farm","title":"햇살 텃밭","at":Vector2(-22,-6),"kind":"farm"},
	{"id":"shop","title":"씨앗 가게 · 배달 게시판","at":Vector2(-17,0),"kind":"shop"},
	{"id":"apple","title":"사과 과수원","at":Vector2(-24,15),"kind":"gather"},
	{"id":"herb","title":"강가 향초밭","at":Vector2(26,5),"kind":"gather"},
	{"id":"pond","title":"바람 호수 낚시터","at":Vector2(-7,14.5),"kind":"fish"},
	{"id":"sea","title":"조개빛 해변 낚시터","at":Vector2(26,29),"kind":"fish"},
	{"id":"bell","title":"별바람 언덕 종탑","at":Vector2(0,-27),"kind":"bell"},
	{"id":"lookout","title":"소나무 전망대","at":Vector2(27,-27),"kind":"view"},
	{"id":"home","title":"나의 집","at":Vector2(-10.8,-4.2),"kind":"home"},
	{"id":"workshop","title":"별씨 공방","at":Vector2(-5,-2.6),"kind":"workshop"},
]
var plots: Array[Node3D]=[]
var crops: Array[Node3D]=[]
var labels: Array[Label3D]=[]
var windmill: Node3D
var float_root: Node3D
var bobber: MeshInstance3D
var fishing_line: MeshInstance3D
var last_plot_signature := ""
var story_progress := 0

static func river_x(z: float) -> float: return 17.0+sin(z*0.13)*1.3
static func height_at(x: float,z: float) -> float:
	var hill := smoothstep(16.0,25.0,-z)*3.0
	var terrace := smoothstep(12.0,18.0,-x)*0.55*(1.0-smoothstep(8.0,12.0,z))
	var h := hill+terrace
	var river := absf(x-river_x(z))
	if river<3.0: h=lerpf(-1.55,h,smoothstep(1.8,3.0,river))
	if x> -13 and x< -2 and z>12 and z<24:
		var edge := minf(minf(x+13,-2-x),minf(z-12,24-z))
		h=lerpf(h,-1.5,smoothstep(0,1.2,edge))
	return h

static func point(p: Vector2, offset := 0.0) -> Vector3: return Vector3(p.x,height_at(p.x,p.y)+offset,p.y)

func _ready() -> void:
	build_ground()
	L.village(self,true)
	if A.authored_prop(self,"res://assets/storybook_home_v1.glb",HOME_POSITION,5.7,5.0):
		A.box(self,HOME_POSITION+Vector3(0,1.4,0),Vector3(4.6,2.8,3.8),Color.WHITE,true).visible=false
		A.label3d(self,"나의 집 · E 들어가기",HOME_DOOR+Vector3(0,3.3,-.6),Color("f5e5b7"))
	path(Vector2(HOME_DOOR.x,HOME_DOOR.z),Vector2(HOME_DOOR.x,-2.4),1.8)
	path(Vector2(-16,-2.4),Vector2(-8,-2.4),1.8)
	for i in mini(3,story_progress):
		var at := HOME_POSITION+Vector3(-1.8+i*1.8,.25,2.15)
		A.box(self,at,Vector3(.2,.5,.2),Color("846344"))
		A.sphere(self,at+Vector3(0,.32,0),Vector3.ONE*.28,[Color("eac77b"),Color("c5b5d6"),Color("8bcac2")][i])
		var glow := OmniLight3D.new();glow.position=at+Vector3(0,.4,0);glow.light_color=Color("edce8c");glow.light_energy=.35;glow.omni_range=2;add_child(glow)
	path(Vector2(0,12),Vector2(0,-10),2.3)
	path(Vector2(-8,-2.4),Vector2(8,-2.4),1.85)
	path(Vector2(-5,-2.5),Vector2(-5,-4),1.8)
	path(Vector2(-7,9.4),Vector2(-7,12),1.6)
	for route in [[Vector2(0,2),Vector2(-16,2)],[Vector2(-16,2),Vector2(-16,-12)],
		[Vector2(-16,-6),Vector2(-26,-6)],
		[Vector2(-17,2),Vector2(-24,18)],[Vector2(0,-10),Vector2(0,-28)],
		[Vector2(8,-2.4),Vector2(14,-5)],[Vector2(20,-5),Vector2(29,-5)],
		[Vector2(27,-5),Vector2(27,-29)],[Vector2(0,9),Vector2(14,18)],
		[Vector2(20,18),Vector2(27,29)],[Vector2(27,-5),Vector2(27,23)]]:
		path(route[0],route[1],2.1)
	for z in [-5.0,18.0]: bridge(z)
	build_farm()
	build_orchard()
	build_beach()
	build_hill()
	meadow_details()
	for place in PLACES:
		if place.id in ["farm","home","workshop"]: continue
		var p: Vector3=point(place.at)
		if place.id=="pond": p.y=0.05
		var label := A.label3d(self,place.title,p+Vector3(0,2.9,0),Color("f5e5b7"))
		label.font_size=36
		label.no_depth_test=false
	var rng := RandomNumberGenerator.new()
	rng.seed=7719
	for i in 125:
		var p := Vector2(rng.randf_range(-34,34),rng.randf_range(-32,24))
		if absf(p.x)<13 and absf(p.y)<17: continue
		if absf(p.x-river_x(p.y))<4: continue
		if height_at(p.x,p.y)<0: continue
		if p.x< -14 and p.y> -13 and p.y<21: continue
		if absf(p.x)<3 or absf(p.x-27)<3 or absf(p.y+5)<2.6 or absf(p.y-18)<2.6: continue
		var tree := A.tree(self,point(p),p.y< -16,true)
		tree.scale*=rng.randf_range(0.8,1.3)
	for p in [Vector2(-13,2),Vector2(-16,11),Vector2(0,-16),Vector2(23,-5),Vector2(25,18),Vector2(9,14)]: L.lantern(self,point(p))
	L.bench(self,point(Vector2(29,-29)),0)
	L.bench(self,point(Vector2(-28,18)),PI*0.5)
	A.label3d(self,"← 텃밭 / 과수원      언덕 ↑      강변 / 해변 →",Vector3(0,2.3,6),Color("eadfbd")).font_size=24
	float_root=Node3D.new()
	add_child(float_root)
	bobber=A.sphere(float_root,Vector3.ZERO,Vector3(0.17,0.25,0.17),Color("e77f56"))
	float_root.visible=false
	fishing_line=MeshInstance3D.new()
	add_child(fishing_line)
	fishing_line.material_override=A.material(Color("e5d9b0"))

func build_ground() -> void:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for x in range(-36,36):
		for z in range(-34,34):
			for p in [Vector2(x,z),Vector2(x+1,z),Vector2(x,z+1),Vector2(x+1,z),Vector2(x+1,z+1),Vector2(x,z+1)]:
				var h := height_at(p.x,p.y)
				var color := Color("819851")
				if p.y>24: color=Color("d7c28c")
				elif h>1.4: color=Color("91a582")
				elif p.x< -13: color=Color("9dac60")
				elif p.x>20: color=Color("6f9976")
				if h< -0.2: color=Color("acac80")
				color=color.lightened((sin(p.x*0.65)*cos(p.y*0.52)+1)*0.028)
				st.set_color(color)
				st.add_vertex(Vector3(p.x,h,p.y))
	st.generate_normals()
	var ground := MeshInstance3D.new()
	ground.mesh=st.commit()
	var mat := ShaderMaterial.new()
	mat.shader=preload("res://shaders/town_ground.gdshader")
	ground.material_override=mat
	add_child(ground)
	ground.create_trimesh_collision()
	var sea := A.box(self,Vector3(0,-1.85,0),Vector3(240,0.04,240),Color.WHITE)
	sea.material_override=L.water_material()
	# Separate water surfaces allow raised northern terrain without floating river water.
	for z in range(-34,34):
		var water := A.box(self,Vector3(river_x(z+0.5),-0.52,z+0.5),Vector3(4.5,0.025,1.15),Color.WHITE)
		water.material_override=L.water_material()
		if absf(z+0.5+5)<2 or absf(z+0.5-18)<2: continue
		for side in [-1,1]:
			A.box(self,Vector3(river_x(z+0.5)+side*2.7,height_at(river_x(z+0.5)+side*3,z)+0.7,z+0.5),Vector3(0.1,3,1.12),Color.WHITE,true).visible=false
	var lake := A.box(self,Vector3(-7.5,-0.5,18),Vector3(10,0.03,11),Color.WHITE)
	lake.material_override=L.water_material()
	for p in [Vector3(-13,0.6,18),Vector3(-2,0.6,18)]: A.box(self,p,Vector3(0.1,2,12),Color.WHITE,true).visible=false
	A.box(self,Vector3(-7.5,0.6,24),Vector3(11,2,0.1),Color.WHITE,true).visible=false
	for p in [Vector3(-10.7,0.6,12),Vector3(-3.8,0.6,12)]: A.box(self,p,Vector3(4,2,0.1),Color.WHITE,true).visible=false
	for x in [-35.5,35.5]: A.box(self,Vector3(x,2,0),Vector3(0.1,12,68),Color.WHITE,true).visible=false
	for z in [-33.5,33.5]: A.box(self,Vector3(0,2,z),Vector3(72,12,0.1),Color.WHITE,true).visible=false
	for i in 100:
		var p := Vector2(-35.4+i%50*1.44,-33.7 if i<50 else 33.7)
		L.rock(self,point(p,-0.6),Vector3(1.6,1.5,1.5),Color("9fa48b"))
	for i in 90:
		var p := Vector2(-35.6 if i<45 else 35.6,-32+i%45*1.5)
		L.rock(self,point(p,-0.6),Vector3(1.5,1.5,1.7),Color("9fa48b"))

func path(from: Vector2,to: Vector2,width: float) -> void:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var side := (to-from).normalized().orthogonal()*width*0.5
	var steps := maxi(2,int(from.distance_to(to)*2))
	for i in steps:
		var p := from.lerp(to,float(i)/steps)
		var q := from.lerp(to,float(i+1)/steps)
		for v in [p-side,p+side,q-side,q-side,p+side,q+side]: st.add_vertex(point(v,0.035))
	st.generate_normals()
	var node := MeshInstance3D.new()
	node.mesh=st.commit()
	var mat := A.material(Color("c5b68b"))
	mat.cull_mode=BaseMaterial3D.CULL_DISABLED
	node.material_override=mat
	node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
	# Small, irregular stone inlays break up long flat ribbons without adding
	# hundreds of separate draw calls or changing the authoritative paths.
	var count := maxi(1,int(from.distance_to(to)*1.05))
	var stones := MultiMesh.new()
	var stone_mesh := SphereMesh.new()
	stone_mesh.radius=0.5
	stone_mesh.height=1
	stone_mesh.radial_segments=8
	stone_mesh.rings=4
	stones.mesh=stone_mesh
	stones.transform_format=MultiMesh.TRANSFORM_3D
	stones.use_colors=true
	stones.instance_count=count
	var rng := RandomNumberGenerator.new()
	rng.seed=abs(int(from.x*911+from.y*433+to.x*127+to.y*619))
	var direction := (to-from).normalized()
	var cross := direction.orthogonal()
	for i in count:
		var t := (i+0.45+rng.randf_range(-0.3,0.3))/count
		var here := from.lerp(to,clampf(t,0.0,1.0))+cross*rng.randf_range(-width*0.39,width*0.39)
		var basis := Basis(Vector3.UP,rng.randf_range(-0.34,0.34)).scaled(Vector3(rng.randf_range(0.40,0.70),0.045,rng.randf_range(0.34,0.61)))
		stones.set_instance_transform(i,Transform3D(basis,point(here,0.039)))
		stones.set_instance_color(i,[Color("c4b898"),Color("afa68e"),Color("d3c8a8")][i%3])
	var inlays := MultiMeshInstance3D.new()
	inlays.multimesh=stones
	var stone_material := A.material(Color.WHITE)
	stone_material.vertex_color_use_as_albedo=true
	inlays.material_override=stone_material
	inlays.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(inlays)

func bridge(z: float) -> void:
	var x := river_x(z)
	for i in 20: A.box(self,Vector3(x-3.8+i*0.4,-0.06,z),Vector3(0.37,0.12,3.6),Color("bc9b70"),true)
	for side in [-1,1]:
		L.fence(self,Vector3(x-4,0,z+side*1.85),Vector3(x+4,0,z+side*1.85))
		L.lantern(self,Vector3(x-4.3,0,z+side*1.9),false)

func build_farm() -> void:
	for i in PLOTS.size():
		var root := Node3D.new()
		add_child(root)
		root.position=point(PLOTS[i],0.03)
		plots.append(root)
		A.box(root,Vector3(0,0.01,0),Vector3(2.2,0.09,2.0),Color("76563e"))
		for z in [-0.7,-0.25,0.2,0.65]: A.box(root,Vector3(0,0.08,z),Vector3(2,0.08,0.16),Color("916548"))
		for x in [-1.15,1.15]: A.box(root,Vector3(x,0.1,0),Vector3(0.1,0.2,2.2),Color("bd9b6e"))
		labels.append(A.label3d(root,"%d · 빈 밭" % (i+1),Vector3(0,0.65,0),Color("f3e1af")))
		var crop := Node3D.new()
		root.add_child(crop)
		crops.append(crop)
	for pair in [[Vector2(-27,-11),Vector2(-16,-11)],[Vector2(-27,-11),Vector2(-27,-1)]]:
		L.fence(self,point(pair[0]),point(pair[1]))
	var scare := point(Vector2(-26,-10))
	A.box(self,scare+Vector3(0,1,0),Vector3(0.13,2,0.13),Color("977047"))
	A.box(self,scare+Vector3(0,1.6,0),Vector3(1.3,0.13,0.13),Color("977047"))
	A.sphere(self,scare+Vector3(0,1.95,0),Vector3(0.5,0.5,0.5),Color("ddb77d"))
	L.cylinder(self,scare+Vector3(0,2.15,0),0.43,0.13,Color("b8864e"))
	A.box(self,scare+Vector3(0,1.5,0),Vector3(0.55,0.6,0.3),Color("6f94a0"))
	if not A.authored_prop(self,"res://assets/seed_shop.glb",point(Vector2(-13.8,-2.0)),4.7,4.4):
		var stall := Node3D.new()
		add_child(stall)
		stall.position=point(Vector2(-17,-0.9))
		A.box(stall,Vector3(0,0.7,0),Vector3(2.7,1.4,1.2),Color("c39262"),true)
		for x in [-1.3,1.3]: A.box(stall,Vector3(x,1.5,0),Vector3(0.1,3,0.12),Color("876643"))
		for i in 7: A.box(stall,Vector3(-1.5+i*0.5,2.8,0),Vector3(0.5,0.18,2.1),Color("e6d3a0") if i%2 else Color("759479"))
		for i in 4: L.pot(stall,Vector3(-0.9+i*0.6,1.4,0),false)
	A.label3d(self,"햇살 텃밭 · 씨앗을 심고 물을 주세요",point(Vector2(-22,-11),3),Color("f2dfaa"))
	var mill := point(Vector2(-30,-9))
	L.cylinder(self,mill+Vector3(0,1.5,0),1.1,3,Color("d5c79d"),10,0.75)
	A.cone(self,mill+Vector3(0,3.6,0),1.3,1.2,Color("738d79"))
	windmill=Node3D.new()
	add_child(windmill)
	windmill.position=mill+Vector3(0,3,-1.15)
	for i in 4:
		var vane := Node3D.new()
		windmill.add_child(vane)
		vane.rotation.z=i*PI*0.5
		A.box(vane,Vector3(0,1.25,0),Vector3(0.42,2.3,0.08),Color("e9dfbc"))

func build_orchard() -> void:
	for p in [Vector2(-25,13),Vector2(-28,9),Vector2(-21,10),Vector2(-29,16),Vector2(-20,17)]:
		var root := A.tree(self,point(p),false,true)
		for i in 6: A.sphere(root,Vector3(sin(i*2.1)*0.9,2.1+sin(i)*0.3,cos(i*2.1)*0.9),Vector3.ONE*0.26,Color("d66849"))
	for i in 15:
		var p := Vector2(24+(i%5)*0.8,3+(i/5)*0.8)
		for j in 3:
			var leaf := A.sphere(self,point(p)+Vector3(sin(j*2)*0.17,0.28,cos(j*2)*0.17),Vector3(0.19,0.52,0.13),Color("78a887"))
			leaf.rotation.z=sin(j)*0.5

func build_beach() -> void:
	A.authored_prop(self,"res://assets/fishing_shack.glb",point(Vector2(31.5,22.3)),4.2,4.4)
	# Walkable boardwalk ends at a visibly railed ocean casting point.
	for i in 11: A.box(self,Vector3(26,-0.08,27+i*0.48),Vector3(2.6,0.16,0.45),Color("c4a883"),true)
	for x in [24.6,27.4]: L.fence(self,Vector3(x,0,27),Vector3(x,0,32))
	L.fence(self,Vector3(24.6,0,32),Vector3(27.4,0,32))
	for i in 24:
		var p := Vector2(-31+(i*7)%62,26+(i%4)*1.5)
		if absf(p.x-26)<2 or absf(p.x-river_x(p.y))<4: continue
		L.rock(self,point(p,0.08),Vector3(0.28,0.13,0.22),Color("f4ddbd"))
	L.bench(self,Vector3(30,0,28),-PI*0.5)

func build_hill() -> void:
	var p := point(Vector2(0,-28))
	L.cylinder(self,p,2.5,0.12,Color("b7bfa0"),32)
	for x in [-0.8,0.8]: A.box(self,p+Vector3(x,1.6,0),Vector3(0.19,3.2,0.2),Color("ad8961"),true)
	A.box(self,p+Vector3(0,3,0),Vector3(2.1,0.2,0.3),Color("ad8961"))
	L.cylinder(self,p+Vector3(0,2.25,0),0.44,0.7,Color("c9ab63"),12,0.23)
	A.box(self,p+Vector3(0,1.4,0),Vector3(0.035,1.1,0.035),Color("e0c99c"))
	L.bench(self,point(Vector2(-4,-28)),0)
	var deck := point(Vector2(27,-28))
	var deck_mesh := A.box(self,deck+Vector3(0,-0.01,0),Vector3(7,0.08,5),Color("aaa484"))
	deck_mesh.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	L.fence(self,point(Vector2(24,-30)),point(Vector2(30,-30)))

func update_plots(state: Dictionary, now: float) -> void:
	var signature := JSON.stringify(state.get("plots",[]))
	for i in plots.size():
		var plot: Dictionary=state.get("plots",[{},{},{},{},{},{}])[i]
		var ready: bool=not plot.is_empty() and plot.get("watered",false) and now>=float(plot.get("ready_at",0))
		if plot.is_empty(): labels[i].text="%d · E 심기" % (i+1)
		elif not plot.get("watered",false): labels[i].text="E · 물주기"
		elif ready: labels[i].text="E · 수확!"
		else: labels[i].text="성장 중 · %d초" % maxi(0,int(ceil(float(plot.ready_at)-now)))
		if signature!=last_plot_signature or crops[i].get_meta("ripe",false)!=ready:
			for child in crops[i].get_children():
				crops[i].remove_child(child)
				child.queue_free()
			crops[i].set_meta("ripe",ready)
			if plot.is_empty(): continue
			for j in 4:
				var p := Vector3(-0.55+(j%2)*1.1,0.12,-0.5+(j/2)*1.0)
				if ready: A.sphere(crops[i],p+Vector3(0,0.2,0),Vector3(0.57,0.42,0.5),Color("e0cea5") if plot.crop=="turnip" else Color("df9846"))
				for k in 3:
					var leaf := A.sphere(crops[i],p+Vector3(sin(k*2.1)*0.1,0.3,cos(k*2.1)*0.1),Vector3(0.17,0.5 if ready else 0.25,0.12),Color("67a565"))
					leaf.rotation.z=sin(k)*0.6
	last_plot_signature=signature

func update_fishing(active: bool,at: Vector3,bite: bool,hand: Vector3) -> void:
	float_root.visible=active
	fishing_line.visible=active
	if not active: return
	float_root.position=at+Vector3(0,sin(Time.get_ticks_msec()*0.006)*(0.13 if bite else 0.025),0)
	bobber.material_override.albedo_color=Color("ffe074") if bite else Color("e77f56")
	var im := ImmediateMesh.new()
	im.surface_begin(Mesh.PRIMITIVE_LINES)
	im.surface_add_vertex(hand)
	im.surface_add_vertex(float_root.position)
	im.surface_end()
	fishing_line.mesh=im

func _process(delta: float) -> void:
	if is_instance_valid(windmill): windmill.rotation.z+=delta*0.25

func meadow_details() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed=70718
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in 4100:
		var p := Vector2(rng.randf_range(-34,34),rng.randf_range(-32,24))
		if height_at(p.x,p.y)<0: continue
		if absf(p.x)<13 and absf(p.y)<17: continue
		if p.x>23 and p.x<31 and p.y< -25: continue
		if p.x< -14 and p.x> -28 and p.y<2 and p.y> -12: continue
		if absf(p.x)<2 or absf(p.x-27)<2 or absf(p.y+5)<2 or absf(p.y-18)<2: continue
		var base := point(p,0.03)
		for j in 3:
			var angle := rng.randf()*TAU
			var offset := Vector3(cos(angle),0,sin(angle))*0.055
			st.set_color(Color("759655").lerp(Color("baca89"),rng.randf()))
			st.add_vertex(base-offset)
			st.add_vertex(base+offset)
			st.add_vertex(base+Vector3(offset.x,rng.randf_range(0.12,0.35),offset.z))
		if i%8==0:
			st.set_color(Color("e9cc8f") if i%3 else Color("d8b2c7"))
			for v in [Vector3(-0.075,0.18,0),Vector3(0.075,0.18,0),Vector3(0,0.32,0.015)]: st.add_vertex(base+v)
	st.generate_normals()
	var node := MeshInstance3D.new()
	node.mesh=st.commit()
	var mat := ShaderMaterial.new()
	mat.shader=preload("res://shaders/foliage.gdshader")
	node.material_override=mat
	node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
	for z in range(-31,32,2):
		if abs(z+5)<3 or abs(z-18)<3: continue
		for side in [-1,1]:
			var p := Vector2(river_x(z)+side*3.2,z)
			L.rock(self,point(p,0.02),Vector3(0.55,0.38,0.75),Color("9fae90"))
