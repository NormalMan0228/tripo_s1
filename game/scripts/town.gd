extends Node3D
## The island village. The archipelago from labs/terrain_lab is the walkable map;
## this script places the village's interaction points onto its five islands.
## Server-side village rules do not depend on these positions (homestead.py).
const A=preload("res://scripts/art.gd")
const L=preload("res://scripts/world_detail.gd")
const Archipelago=preload("res://maps/archipelago/archipelago.gd")
const Fx=preload("res://scripts/fx.gd")
const TreeFruit=preload("res://scripts/tree_fruit.gd")
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
	{"id":"farm","title":"햇살 텃밭","at":Vector2(-18.4,-34.0),"kind":"farm"},
	{"id":"shop","title":"씨앗 노점 · 배달 게시판","at":Vector2(-32.4,-21.6),"kind":"shop"},
	{"id":"apple","title":"사과 과수원","at":Vector2(-50,-44),"kind":"gather"},
	{"id":"herb","title":"정원 향초밭","at":Vector2(42,-14),"kind":"gather"},
	{"id":"pond","title":"마을 연못 낚시터","at":Vector2(-32,44),"kind":"fish"},
	{"id":"sea","title":"등대 부두 낚시터","at":Vector2(-4,82.6),"kind":"fish"},
	{"id":"bell","title":"등대 종","at":Vector2(10.4,79.6),"kind":"bell"},
	{"id":"lookout","title":"천문대 전망대","at":Vector2(33.6,-41.2),"kind":"view"},
	{"id":"home","title":"나의 집","at":HOME_DOOR,"kind":"home"},
	{"id":"workshop","title":"별씨 공방","at":WORKSHOP_DOOR,"kind":"workshop"},
]
## Where each villager stands, by role.
const VILLAGERS := {"map":Vector2(51,37),"wardrobe":Vector2(-30,35),"guide":Vector2(57,38),"angler":Vector2(1.5,78.5)}
## Every building with a door (measured on top-down renders). "room" is the
## interior the door opens: home and workshop are the player's rooms, the rest
## are public interiors keyed by building id. Open structures (gazebo, stage,
## picnic shelter) have no door; players walk straight in.
const DOORS := [
	{"id":"01_cafe","room":"01_cafe","title":"카페 '빨간 지붕'","at":Vector2(-61.4,-32.8),"center":Vector2(-62,-38)},
	{"id":"02_timber_house","room":"02_timber_house","title":"목조 주택","at":Vector2(-40.8,-45.4),"center":Vector2(-42,-50)},
	{"id":"03_teal_cottage","room":"03_teal_cottage","title":"씨앗 가게","at":Vector2(-35.6,-23.2),"center":Vector2(-34,-28)},
	{"id":"04_windmill","room":"04_windmill","title":"풍차 방앗간","at":Vector2(-18.9,-41.0),"center":Vector2(-18,-44)},
	{"id":"05_observatory","room":"05_observatory","title":"별빛 천문대","at":Vector2(30,-42.6),"center":Vector2(30,-48)},
	{"id":"06_orange_cottage","room":"06_orange_cottage","title":"주황 지붕 오두막","at":Vector2(24,-25.0),"center":Vector2(24,-28)},
	{"id":"07_greenhouse","room":"07_greenhouse","title":"유리 온실","at":Vector2(49,-16.3),"center":Vector2(49,-20)},
	{"id":"09_town_hall","room":"workshop","title":"별씨 공방","at":WORKSHOP_DOOR,"center":Vector2(-33,22)},
	{"id":"10_red_house","room":"home","title":"나의 집","at":HOME_DOOR,"center":Vector2(-55,17)},
	{"id":"11_purple_house","room":"11_purple_house","title":"보라 지붕 집","at":Vector2(-65.5,35.6),"center":Vector2(-68,32)},
	{"id":"12_blue_house","room":"12_blue_house","title":"파란 집","at":Vector2(-69.6,48.8),"center":Vector2(-67,46)},
	{"id":"13_shop","room":"13_shop","title":"잡화점","at":Vector2(-17.9,29.9),"center":Vector2(-17,28)},
	{"id":"16_blue_cottage","room":"16_blue_cottage","title":"파란 지붕 오두막","at":Vector2(70.05,55.8),"center":Vector2(70,52)},
	{"id":"17_lighthouse","room":"17_lighthouse","title":"등대","at":Vector2(7,80.6),"center":Vector2(7,78)},
]

static func door_for(room: String) -> Dictionary:
	for door in DOORS:
		if door.room==room: return door
	return {}

## A step outside the door, where the walker reappears after leaving the room.
static func door_return(room: String) -> Vector3:
	var door := door_for(room)
	if door.is_empty(): return point(SPAWN,.3)
	var out: Vector2=(door.at-door.center).normalized()
	return point(door.at+out*1.2,.3)
## Fishing floats land on the pond and on the sea beside the lighthouse pier.
const CAST_POINTS := {"pond":Vector3(-39,1.2,44),"sea":Vector3(-8,0.05,86)}
## Field objects the walker can use with E: prop id -> [prompt, reach in metres].
const PROP_ACTIONS := {
	"26_bench":["벤치에 앉아 쉬기",1.7],"25_picnic_table":["피크닉 테이블에 앉기",1.9],"32_cafe_chair":["의자에 앉기",1.3],
	"31_cafe_table":["테이블 살펴보기",1.5],"33_signboard":["안내판 읽기",1.6],
	"37_round_tree":["나무 흔들기",2.2],"38_conifer":["나무 흔들기",2.0],"39_palm":["야자나무 흔들기",2.0],
	"40_shrub":["덤불 뒤져 보기",1.5],"41_planter":["화분에 물 주기",1.4],"42_white_flowers":["꽃향기 맡기",1.1],
	"43_yellow_flowers":["꽃향기 맡기",1.1],"44_pink_flowers":["꽃향기 맡기",1.1],"45_reeds":["갈대 흔들기",1.3],
	"21_boat":["작은 배 살펴보기",2.4],"24_firepit":["모닥불 쬐기",2.0],"22_tent_orange":["텐트 들여다보기",2.0],
	"23_tent_green":["텐트 들여다보기",2.0],"28_beach_umbrella":["파라솔 그늘에서 쉬기",1.8],"29_beach_lounger":["선베드에 누워 보기",1.6],
	"30_cafe_umbrella":["파라솔 그늘에서 쉬기",1.8],"36_speaker":["음악 틀기",1.5]}
var props: Array = []
var trees: Node3D
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
	# Paths are part of the kept map, so they are laid only once per session.
	if is_instance_valid(map) and map is Archipelago and not map.has_node("Roads"):
		var roads: Node3D=preload("res://scripts/roads.gd").new()
		roads.name="Roads"
		map.add_child(roads)
		roads.build(space,map.get_node_or_null("Environment"))
	index_props()
	var home := point(HOME_DOOR)
	A.label3d(self,tr("나의 집 · E 들어가기"),home+Vector3(0,3.4,0),Color("f5e5b7"))
	A.label3d(self,tr("별씨 공방 · E 들어가기"),point(WORKSHOP_DOOR)+Vector3(0,3.6,0),Color("fff1c8"))
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
		A.style_nameplate(label,20)
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
		labels.append(A.label3d(root,tr("%d · 빈 밭") % (i+1),Vector3(0,0.65,0),Color("f3e1af")))
		var crop := Node3D.new()
		root.add_child(crop)
		crops.append(crop)
	var scare := point(Vector2(-22,-33))
	A.box(self,scare+Vector3(0,1,0),Vector3(0.13,2,0.13),Color("977047"))
	A.box(self,scare+Vector3(0,1.6,0),Vector3(1.3,0.13,0.13),Color("977047"))
	A.sphere(self,scare+Vector3(0,1.95,0),Vector3(0.5,0.5,0.5),Color("ddb77d"))
	L.cylinder(self,scare+Vector3(0,2.15,0),0.43,0.13,Color("b8864e"))
	A.box(self,scare+Vector3(0,1.5,0),Vector3(0.55,0.6,0.3),Color("6f94a0"))
	A.label3d(self,tr("햇살 텃밭 · 씨앗을 심고 물을 주세요"),point(Vector2(-16,-33.5),3),Color("f2dfaa"))

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
		if plot.is_empty(): labels[i].text=tr("%d · E 심기") % (i+1)
		elif not plot.get("watered",false): labels[i].text=tr("E · 물주기")
		elif ready: labels[i].text=tr("E · 수확!")
		else: labels[i].text=tr("성장 중 · %d초") % maxi(0,int(ceil(float(plot.ready_at)-now)))
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

func index_props() -> void:
	props.clear()
	var layout := map.get_node_or_null("Environment") if is_instance_valid(map) else null
	if layout==null or not "prop_nodes" in layout: return
	for node in layout.prop_nodes:
		if not is_instance_valid(node): continue
		var spec: Dictionary=node.get_meta("placement_spec",{})
		if PROP_ACTIONS.has(spec.get("id","")):
			props.append({"node":node,"id":spec.id,"at":Vector2(node.global_position.x,node.global_position.z)})
	# Every field tree is its own server node with its own fruit (tree_fruit.gd).
	if not is_instance_valid(trees):
		trees=TreeFruit.new()
		trees.name="TreeFruit"
		add_child(trees)
	trees.build(layout.prop_nodes)

## Fallen fruit within reach comes first, then the nearest usable prop.
func nearest_prop(at: Vector2) -> Dictionary:
	if is_instance_valid(trees):
		var drop: Dictionary=trees.nearest_drop(at)
		if not drop.is_empty(): return {"id":"fruit","drop":drop,"at":Vector2(drop.pos.x,drop.pos.z)}
	var best := {}
	var best_gap := INF
	for entry in props:
		var gap: float=at.distance_to(entry.at)
		if gap<PROP_ACTIONS[entry.id][1] and gap<best_gap:
			best=entry
			best_gap=gap
	return best

func prop_prompt(entry: Dictionary) -> String:
	if entry.id=="fruit": return trees.prompt(entry.drop)
	return tr(PROP_ACTIONS[entry.id][0])

## Prop reactions show, they do not tell: a sway, a puff, a bubble, a sound and the
## walker's own gesture. Trees shake one by one (tree_fruit.gd); shrubs still give
## the shared herb gather. Words stay only where they carry information (signboard).
func use_prop(app: Node, entry: Dictionary) -> void:
	if entry.id=="fruit":
		if is_instance_valid(trees): trees.pick(entry.drop,true)
		return
	var node: Node3D=entry.node
	if not is_instance_valid(node): return
	var base: Vector3=node.global_position
	var player: Node3D=app.player
	var head: Vector3=player.global_position+Vector3(0,2.0,0)
	var away: Vector3=Vector3.UP.cross(Vector3(base.x-player.global_position.x,0,base.z-player.global_position.z).normalized())
	player.face_point(base)
	match entry.id:
		"37_round_tree","38_conifer","39_palm":
			trees.shake(app,node)
		"40_shrub":
			search_shrub(app,node,away)
		"42_white_flowers","43_yellow_flowers","44_pink_flowers":
			player.react("eat")
			var petal: Color={"42_white_flowers":Color("fbf7ee"),"43_yellow_flowers":Color("f7d65a"),"44_pink_flowers":Color("f6a8c8")}[entry.id]
			Fx.wobble(node,0.12,away,3,0.6)
			Fx.burst(self,base+Vector3(0,0.35,0),"petal",10,petal,0.3)
			Fx.burst(self,player.global_position+Vector3(0,1.6,0),"heart",3,Color(0,0,0,0),0.15)
			Fx.bubble(self,head,"heart")
			Fx.sound(app,"twinkle",base,1.0,-4.0)
		"45_reeds":
			Fx.wobble(node,0.2,away,5,0.9)
			Fx.burst(self,base+Vector3(0,0.9,0),"fluff",10,Color(0,0,0,0),0.4)
			Fx.sound(app,"leaves",base,1.35,-3.0)
			# Now and then something lives in there.
			if randf()<0.75: Fx.dragonfly(self,base+Vector3(0,0.8,0),Vector3(base.x-player.global_position.x,0,base.z-player.global_position.z))
		"41_planter":
			water_planter(app,node)
		"33_signboard":
			Fx.wobble(node,0.03,away,3,0.4)
			Fx.sound(app,"pluck",base,0.8,-6.0)
			var area: String=preload("res://scripts/minimap.gd").island_name(entry.at)
			Fx.title(app,base+Vector3(0,0.4,0),"「%s」" % tr(area),Color("f5e5b7"))
		"21_boat":
			# The layout bobs the boat in height and roll; a pitch rock reads as a nudge.
			var rock := node.create_tween()
			for i in 4: rock.tween_property(node,"rotation:x",0.07*(1.0 if i%2==0 else -1.0)*(1.0-i*0.22),0.22).set_trans(Tween.TRANS_SINE)
			rock.tween_property(node,"rotation:x",0.0,0.3).set_trans(Tween.TRANS_SINE)
			var water := Vector3(base.x,maxf(base.y,0.0)+0.2,base.z)
			for i in 3:
				get_tree().create_timer(i*0.35).timeout.connect(func(): Fx.ring(self,water,2.2+i*0.6,Color(0.9,0.97,1.0,0.6),1.2))
			Fx.burst(self,water+Vector3(0,0.2,0),"splash",10,Color(0,0,0,0),0.8)
			Fx.sound(app,"splash",base,0.85,-4.0)
		"24_firepit":
			player.react("craft")
			var fire := base+Vector3(0,0.45,0)
			Fx.glow(self,fire+Vector3(0,0.25,0),Color("ffae55"),2.4,1.8)
			Fx.stream(self,fire,"spark",1.6,9.0,Color(0,0,0,0),0.25)
			Fx.burst(self,fire+Vector3(0,0.5,0),"smoke",4,Color(0,0,0,0),0.2)
			Fx.bubble(self,head,"flame")
			Fx.sound(app,"crackle",base)
			app.sound.effect("fire")
		"22_tent_orange","23_tent_green":
			Fx.wobble(node,0.025,away,4,0.6)
			Fx.burst(self,base+Vector3(0,1.9,0.5),"zz",3,Color(0,0,0,0),0.2)
			Fx.bubble(self,base+Vector3(0,2.6,0.4),"zz")
			Fx.sound(app,"leaves",base,1.6,-8.0)
		"36_speaker":
			Fx.squash(node,0.08,0.3)
			Fx.stream(self,base+Vector3(0,1.0,0),"note",3.0,4.0,Color(0,0,0,0),0.25)
			for i in 3:
				get_tree().create_timer(i*0.5).timeout.connect(func():
					Fx.ring(self,base,1.8,Color(0.9,0.8,1.0,0.45),0.8)
					if is_instance_valid(node): Fx.squash(node,0.06,0.25))
			Fx.sound(app,"tune",base,1.0,-2.0)
		"28_beach_umbrella","30_cafe_umbrella":
			Fx.wobble(node,0.05,away,4,0.8)
			player.react("eat")
			Fx.burst(self,base+Vector3(0,2.3,0),"sparkle",5,Color(0,0,0,0),0.8)
			Fx.bubble(self,head,"sun")
			Fx.sound(app,"whoosh",base,1.2,-8.0)
		"29_beach_lounger":
			player.react("eat")
			Fx.burst(self,player.global_position+Vector3(0,1.7,0),"zz",3,Color(0,0,0,0),0.15)
			Fx.bubble(self,head,"sun")
			Fx.sound(app,"pluck",base,0.7,-8.0)
		"31_cafe_table":
			Fx.burst(self,base+Vector3(0,0.9,0),"steam",4,Color(0,0,0,0),0.15)
			Fx.bubble(self,head,"note")
			Fx.sound(app,"pluck",base,1.2,-8.0)
		_:
			# Benches, picnic tables and chairs: a stretch and a contented hum.
			player.react("eat")
			Fx.burst(self,player.global_position+Vector3(0,1.8,0),"note",3,Color(0,0,0,0),0.2)
			Fx.bubble(self,head,"heart")
			Fx.sound(app,"pluck",base,0.9,-8.0)

## A shrub rustles; when the shared herb patch is ripe the server gives herbs.
func search_shrub(app: Node, node: Node3D, away: Vector3) -> void:
	var base: Vector3=node.global_position
	app.player.react("gather")
	Fx.wobble(node,0.14,away,5,0.7)
	Fx.burst(self,base+Vector3(0,0.5,0),"leaf",10,Color(0,0,0,0),0.4)
	Fx.sound(app,"leaves",base,1.25,-3.0)
	var life: Node=app.life
	if not is_instance_valid(life) or not life.has_method("request") or not life.state is Dictionary or life.state.is_empty(): return
	if app.social.visiting() or life.now()<float(life.state.get("cooldowns",{}).get("herb",0)): return
	var data: Dictionary=await life.request("gather",{"item":"herb"})
	if data.is_empty() or not is_instance_valid(self): return
	var items: Dictionary=data.get("reward",{}).get("items",{})
	for item in items: Fx.item_pop(app,base+Vector3(0,0.6,0),item,int(items[item]))
	Fx.fly_to_bag(app,items,base+Vector3(0,0.6,0),0.2)
	if "sfx" in life and is_instance_valid(life.sfx): life.sfx.play("collect",1.05,-3)

func water_planter(app: Node, node: Node3D) -> void:
	var base: Vector3=node.global_position
	app.player.equip("watering_can")
	app.player.react("craft")
	for i in 3:
		get_tree().create_timer(i*0.16).timeout.connect(func(): Fx.burst(self,base+Vector3(0,1.0,0),"drop",10,Color(0,0,0,0),0.3))
	Fx.sound(app,"splash",base,1.4,-6.0)
	get_tree().create_timer(0.6).timeout.connect(func():
		Fx.burst(self,base+Vector3(0,0.6,0),"sparkle",7,Color(0,0,0,0),0.35)
		Fx.burst(self,base+Vector3(0,0.5,0),"leaf",4,Color("8fd46a"),0.2)
		if is_instance_valid(node): Fx.squash(node,0.08,0.35)
		Fx.sound(app,"twinkle",base,1.1,-5.0))
	await get_tree().create_timer(1.2).timeout
	if is_instance_valid(app) and is_instance_valid(app.player) and app.player.equipped=="watering_can": app.player.equip("")

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
		else:
			kept_map=map
			free_kept_with_tree()

## A kept map sits outside the scene tree while a room is open. If the game quits
## then (or mid-way through the switch), free it with the tree instead of leaking it.
static func free_kept_with_tree() -> void:
	var tree := Engine.get_main_loop() as SceneTree
	if tree==null or tree.root==null or tree.root.has_node("KeptTownMap"): return
	var holder := Node.new()
	holder.name="KeptTownMap"
	holder.tree_exiting.connect(func(): discard_kept())
	tree.root.add_child.call_deferred(holder)

func _exit_tree() -> void:
	space=null
