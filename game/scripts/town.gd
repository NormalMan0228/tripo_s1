extends Node3D
## The island village. The archipelago from labs/terrain_lab is the walkable map;
## this script places the village's interaction points onto its five islands.
## Server-side village rules do not depend on these positions (homestead.py).
const A=preload("res://scripts/art.gd")
const L=preload("res://scripts/world_detail.gd")
const Archipelago=preload("res://maps/archipelago/archipelago.gd")
## Sea level guard for walkers: below this the body returns to its last ground.
const SHORE_MIN_Y := 0.45
## Town green on the south-west island. Players start here.
const SPAWN := Vector2(-33,37)
## Outdoor furniture keeps the server's village coordinates (|x|,|z| <= 11) around
## the town green; homestead.village_reserved uses the same origin.
const VILLAGE_ORIGIN := SPAWN
## 나의 집 is the red house; 별씨 공방 is the town hall. Door steps were measured on
## top-down renders (tests/archipelago_probe.gd --top), not derived from yaw.
const HOME_DOOR := Vector2(-54.2,21.6)
const HOME_RETURN_AT := Vector2(-54.0,22.8)
const WORKSHOP_DOOR := Vector2(-33.2,28.4)
const WORKSHOP_RETURN_AT := Vector2(-33.2,29.7)
## The expedition arch stands at the camp on the south-east island.
const GATE := Vector2(54,38)
## Six plots on the north-west meadow between the bench, the conifer and the beach.
const PLOTS=[Vector2(-17.5,-31),Vector2(-14.5,-31),Vector2(-11.5,-31),Vector2(-20.5,-27),Vector2(-17.5,-27),Vector2(-14.5,-27)]
const PLACES=[
	{"id":"farm","title":"햇살 텃밭","at":Vector2(-16,-29),"kind":"farm"},
	{"id":"shop","title":"씨앗 가게 · 배달 게시판","at":Vector2(-35.6,-23.2),"kind":"shop"},
	{"id":"apple","title":"사과 과수원","at":Vector2(-50,-44),"kind":"gather"},
	{"id":"herb","title":"정원 향초밭","at":Vector2(42,-14),"kind":"gather"},
	{"id":"pond","title":"마을 연못 낚시터","at":Vector2(-32,44),"kind":"fish"},
	{"id":"sea","title":"등대 부두 낚시터","at":Vector2(-4,82.6),"kind":"fish"},
	{"id":"bell","title":"별바람 등대","at":Vector2(7,81.6),"kind":"bell"},
	{"id":"lookout","title":"별빛 천문대 전망","at":Vector2(30,-41.7),"kind":"view"},
	{"id":"home","title":"나의 집","at":HOME_DOOR,"kind":"home"},
	{"id":"workshop","title":"별씨 공방","at":WORKSHOP_DOOR,"kind":"workshop"},
]
## Where each villager stands, by role.
const VILLAGERS := {"map":Vector2(51,37),"wardrobe":Vector2(-30,35),"guide":Vector2(57,38),"farmer":Vector2(-22.5,-30.5),"angler":Vector2(1.5,78.5)}
## Fishing floats land on the pond and on the sea beside the lighthouse pier.
const CAST_POINTS := {"pond":Vector3(-39,1.2,44),"sea":Vector3(-8,0.05,86)}
static var space: PhysicsDirectSpaceState3D
## The built map survives leaving the village (survival, studio rooms) so returning
## does not reload 1.8 GB of terrain, buildings and props.
static var kept_map: Node3D
var map: Node3D
var plots: Array[Node3D]=[]
var crops: Array[Node3D]=[]
var labels: Array[Label3D]=[]
var float_root: Node3D
var bobber: MeshInstance3D
var fishing_line: MeshInstance3D
var last_plot_signature := ""
var story_progress := 0
var camera: Camera3D

## Ground height from the map's colliders. Before the map exists it falls back to
## the islands' typical meadow height.
static func height_at(x: float,z: float) -> float:
	if space == null: return 2.3
	var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(x,60,z),Vector3(x,-20,z),Archipelago.WALK_MASK))
	return hit.position.y if not hit.is_empty() else 2.3

static func point(p: Vector2, offset := 0.0) -> Vector3: return Vector3(p.x,height_at(p.x,p.y)+offset,p.y)

## Server village coordinates (furniture) to the map, and back.
static func furniture_point(x: float,z: float) -> Vector3:
	return point(VILLAGE_ORIGIN+Vector2(x,z))
static func furniture_local(world: Vector3) -> Vector2:
	return Vector2(world.x,world.z)-VILLAGE_ORIGIN

func _ready() -> void:
	if is_instance_valid(kept_map):
		map=kept_map
		kept_map=null
		map.camera=camera
		add_child(map)
	elif Archipelago.available():
		map=Archipelago.new()
		map.name="Archipelago"
		add_child(map)
		map.build(camera)
	else:
		# A fresh clone has no map binaries (tools/port_archipelago_map.py copies them
		# from the lab). A flat meadow keeps the village playable until then.
		push_warning("Archipelago map assets are missing; run tools/port_archipelago_map.py")
		A.box(self,Vector3(0,1.3,20),Vector3(200,2,200),Color("8fb86a"),true)
	space=get_world_3d().direct_space_state
	var home := point(HOME_DOOR)
	A.label3d(self,"나의 집 · E 들어가기",home+Vector3(0,3.4,0),Color("f5e5b7"))
	A.label3d(self,"별씨 공방 · E 들어가기",point(WORKSHOP_DOOR)+Vector3(0,3.6,0),Color("fff1c8"))
	for i in mini(3,story_progress):
		var at := point(HOME_DOOR+Vector2(-2.2+i*1.6,1.6),.25)
		A.box(self,at,Vector3(.2,.5,.2),Color("846344"))
		A.sphere(self,at+Vector3(0,.32,0),Vector3.ONE*.28,[Color("eac77b"),Color("c5b5d6"),Color("8bcac2")][i])
		var glow := OmniLight3D.new();glow.position=at+Vector3(0,.4,0);glow.light_color=Color("edce8c");glow.light_energy=.35;glow.omni_range=2;add_child(glow)
	L.gate(self,point(GATE))
	build_farm()
	build_orchard()
	for place in PLACES:
		if place.id in ["farm","home","workshop"]: continue
		var label := A.label3d(self,place.title,point(place.at)+Vector3(0,2.9,0),Color("f5e5b7"))
		label.font_size=36
		label.no_depth_test=false
		label.add_to_group("place_nameplates")
	float_root=Node3D.new()
	add_child(float_root)
	bobber=A.sphere(float_root,Vector3.ZERO,Vector3(0.17,0.25,0.17),Color("e77f56"))
	float_root.visible=false
	fishing_line=MeshInstance3D.new()
	add_child(fishing_line)
	fishing_line.material_override=A.material(Color("e5d9b0"))

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
	var scare := point(Vector2(-22,-33))
	A.box(self,scare+Vector3(0,1,0),Vector3(0.13,2,0.13),Color("977047"))
	A.box(self,scare+Vector3(0,1.6,0),Vector3(1.3,0.13,0.13),Color("977047"))
	A.sphere(self,scare+Vector3(0,1.95,0),Vector3(0.5,0.5,0.5),Color("ddb77d"))
	L.cylinder(self,scare+Vector3(0,2.15,0),0.43,0.13,Color("b8864e"))
	A.box(self,scare+Vector3(0,1.5,0),Vector3(0.55,0.6,0.3),Color("6f94a0"))
	A.label3d(self,"햇살 텃밭 · 씨앗을 심고 물을 주세요",point(Vector2(-16,-33.5),3),Color("f2dfaa"))

func build_orchard() -> void:
	# Apples hang in a small crate beside the meadow trees; the herb bed sits by the greenhouse.
	var crate := point(PLACES[2].at)
	A.box(self,crate+Vector3(0,.25,0),Vector3(.9,.5,.6),Color("a37a50"))
	for i in 6: A.sphere(self,crate+Vector3(-.3+(i%3)*.3,.55,-.12+(i/3)*.24),Vector3.ONE*.22,Color("d66849"))
	for i in 15:
		var p: Vector2=PLACES[3].at+Vector2((i%5)*0.8-1.6,(i/5)*0.8-0.8)
		for j in 3:
			var leaf := A.sphere(self,point(p)+Vector3(sin(j*2)*0.17,0.28,cos(j*2)*0.17),Vector3(0.19,0.52,0.13),Color("78a887"))
			leaf.rotation.z=sin(j)*0.5

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

## Frees a kept map when the game is not travelling between village and rooms.
static func discard_kept() -> void:
	if is_instance_valid(kept_map): kept_map.free()
	kept_map=null

## Call before the village world is freed to keep the map for the next visit.
func release_map() -> void:
	if is_instance_valid(map) and map.get_parent()==self:
		remove_child(map)
		# Only one map is kept; extra clients in one process (tests) free theirs.
		if is_instance_valid(kept_map) and kept_map!=map: map.queue_free()
		else: kept_map=map

func _exit_tree() -> void:
	space=null
