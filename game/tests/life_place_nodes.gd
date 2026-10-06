extends SceneTree
## Authoring tool: samples gather-node spots on the archipelago (off roads, doors,
## buildings and props; shells on sand, mushrooms and twigs in tree shade) and
## prints the table pasted into scripts/forage.gd.
const Map = preload("res://maps/archipelago/archipelago.gd")
const Town = preload("res://scripts/town.gd")
const Roads = preload("res://scripts/roads.gd")
const COUNTS := {"rock":12,"shell":12,"flower":12,"mushroom":8,"herb":8,"branch":10}
var space: PhysicsDirectSpaceState3D
var trees: Array[Vector2]=[]

func _initialize() -> void: call_deferred("run")

func ground(p: Vector2, mask := 1) -> Dictionary:
	return space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(p.x,60,p.y),Vector3(p.x,-20,p.y),mask))

func road_gap(p: Vector2) -> float:
	var best := INF
	for road in Roads.ROADS:
		var pts: Array=road[2]
		for i in pts.size()-1:
			best=minf(best,Geometry2D.get_closest_point_to_segment(p,pts[i],pts[i+1]).distance_to(p)-float(road[1])*0.5)
	return best

func clear(p: Vector2, y: float) -> bool:
	var shape := SphereShape3D.new()
	shape.radius=0.9
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape=shape
	q.collision_mask=2|8|16
	q.transform=Transform3D(Basis.IDENTITY,Vector3(p.x,y+1.0,p.y))
	return space.intersect_shape(q,1).is_empty()

func near_water(p: Vector2) -> bool:
	for i in 12:
		var d := Vector2.from_angle(i*TAU/12)*3.5
		var hit := ground(p+d)
		if hit.is_empty() or hit.position.y<-0.05: return true
	return false

func ok(kind: String, p: Vector2, taken: Array) -> bool:
	var hit := ground(p)
	if hit.is_empty(): return false
	var top := ground(p,1|2|8)
	if top.is_empty() or top.position.y>hit.position.y+0.05: return false
	if hit.normal.y<0.88: return false
	var y: float=hit.position.y
	if kind=="shell":
		if y<0.15 or y>1.0 or not near_water(p): return false
	elif y<1.3: return false
	if road_gap(p)<0.9: return false
	for door in Town.DOORS:
		if p.distance_to(door.at)<4.0: return false
	for place in Town.PLACES:
		if p.distance_to(place.at)<3.0: return false
	for key in Town.VILLAGERS:
		if p.distance_to(Town.VILLAGERS[key])<3.0: return false
	if p.distance_to(Town.SPAWN)<6 or p.distance_to(Town.GATE)<5: return false
	if p.x>-30 and p.x<-14 and p.y>-42 and p.y<-25.5: return false # farm meadow
	for key in Map.OPEN_STRUCTURES:
		if p.distance_to(Map.OPEN_STRUCTURES[key][0])<float(Map.OPEN_STRUCTURES[key][1])+2: return false
	if not clear(p,y): return false
	if kind in ["mushroom","branch"]:
		var shade := false
		for t in trees:
			var gap := p.distance_to(t)
			if gap>1.6 and gap<(2.8 if kind=="mushroom" else 3.6): shade=true
		if not shade: return false
	for other in taken:
		var gap: float=p.distance_to(other[1])
		if gap<3.0 or (other[0]==kind and gap<9.0): return false
	return true

func run() -> void:
	var camera := Camera3D.new(); root.add_child(camera)
	var map: Node3D = Map.new(); root.add_child(map); map.build(camera)
	for i in 6: await physics_frame
	space=map.get_world_3d().direct_space_state
	var roads: Node3D=Roads.new(); map.add_child(roads); roads.build(space,map.get_node("Environment"))
	for i in 3: await physics_frame
	for node in map.get_node("Environment").prop_nodes:
		if is_instance_valid(node) and node.get_meta("placement_spec",{}).get("id","") in ["37_round_tree","38_conifer"]:
			trees.append(Vector2(node.global_position.x,node.global_position.z))
	var rng := RandomNumberGenerator.new()
	rng.seed=20261006
	var taken: Array=[]
	for kind in ["shell","mushroom","branch","rock","flower","herb"]:
		var made := 0
		var tries := 0
		while made<COUNTS[kind] and tries<40000:
			tries+=1
			var p := Vector2(rng.randf_range(-85,85),rng.randf_range(-70,92))
			if kind in ["mushroom","branch"] and rng.randf()<0.9 and not trees.is_empty():
				p=trees[rng.randi()%trees.size()]+Vector2.from_angle(rng.randf()*TAU)*rng.randf_range(1.7,3.4)
			p=p.snapped(Vector2(0.1,0.1))
			if ok(kind,p,taken):
				made+=1
				taken.append([kind,p])
				print("NODE [\"%s_%02d\",\"%s\",%.1f,%.1f]," % [kind,made,kind,p.x,p.y])
		print("KIND ",kind," ",made," tries ",tries)
	quit()
