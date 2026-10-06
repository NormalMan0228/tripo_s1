extends Node3D
## Draws every plot from server state (soil bed, crop growth stage, ripe sparkle)
## and checks where the hoe may break new ground. Rules mirror homestead.py:
## the meadow zone, the 1.8 m grid around the scarecrow, spacing and the cap.
const Art=preload("res://scripts/life_art.gd")
const Town=preload("res://scripts/town.gd")
const Roads=preload("res://scripts/roads.gd")
const GRID := 1.8
const ORIGIN := Vector2(-22,-33)
const ZONE := Rect2(-24.5,-40.5,9.0,11.5)
const STARTERS := 6
var beds: Array=[]
var ghost: Node3D
var ghost_valid := false

static func stage(plot: Dictionary, now: float) -> int:
	if not plot.get("crop"): return 0
	if not plot.get("watered",false): return 1
	var total := maxf(1.0,float(plot.ready_at)-float(plot.get("watered_at",float(plot.ready_at)-60)))
	var grown := 1.0-maxf(0,float(plot.ready_at)-now)/total
	if grown>=1.0: return 5
	return 2 if grown<0.25 else (3 if grown<0.6 else 4)

func sync(plots: Array, now: float) -> void:
	while beds.size()>plots.size():
		var gone: Dictionary=beds.pop_back()
		gone.root.queue_free()
	for i in plots.size():
		var plot: Dictionary=plots[i]
		var at := Vector2(float(plot.get("x",0)),float(plot.get("z",0)))
		if i>=beds.size():
			var root := Node3D.new()
			add_child(root)
			beds.append({"root":root,"at":Vector2.INF,"wet":null,"sig":""})
			root.scale=Vector3.ONE*0.2
			root.create_tween().tween_property(root,"scale",Vector3.ONE,0.4).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		var bed: Dictionary=beds[i]
		var root: Node3D=bed.root
		if bed.at!=at:
			bed.at=at
			root.position=Town.point(at,-0.06)
		var wet: bool=plot.get("watered",false) and stage(plot,now)<5
		if bed.wet!=wet:
			bed.wet=wet
			var old := root.get_node_or_null("Soil")
			if old: old.free()
			var soil := Art.bed(wet)
			soil.name="Soil"
			root.add_child(soil)
		var s := stage(plot,now)
		var sig := "%s/%d" % [plot.get("crop",""),s]
		if sig!=bed.sig:
			var grew: bool=not bed.sig.is_empty() and s>1 and sig.get_slice("/",0)==bed.sig.get_slice("/",0)
			bed.sig=sig
			var old := root.get_node_or_null("Crop")
			if old: old.free()
			var old_spark := root.get_node_or_null("Sparkle")
			if old_spark: old_spark.free()
			if s>0:
				var crop := Art.crop(str(plot.crop),s,i*97+int(plot.get("planted_at",0)))
				crop.name="Crop"
				root.add_child(crop)
				if grew:
					crop.scale=Vector3(0.7,0.4,0.7)
					crop.create_tween().tween_property(crop,"scale",Vector3.ONE,0.5).set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)
			if s==5:
				var spark := Art.sparkles(root,0.55 if plot.crop!="sunflower" else 1.2)
				spark.name="Sparkle"

func _process(_delta: float) -> void:
	var t := Time.get_ticks_msec()*0.001
	for bed in beds:
		var crop: Node3D=bed.root.get_node_or_null("Crop")
		if crop and bed.sig.ends_with("/5"): crop.position.y=absf(sin(t*2.2+bed.at.x))*0.035

func index_at(at: Vector2, reach := 1.05) -> int:
	var best := -1
	var gap := reach
	for i in beds.size():
		var d: float=maxf(absf(at.x-beds[i].at.x),absf(at.y-beds[i].at.y))
		if d<gap:
			gap=d
			best=i
	return best

static func snap(at: Vector2) -> Vector2:
	return ORIGIN+((at-ORIGIN)/GRID).round()*GRID

func in_zone(at: Vector2) -> bool: return ZONE.has_point(at)

## Why a hoe cannot break ground at `cell`, or "" when it can.
func till_problem(cell: Vector2, plots: Array, cap: int) -> String:
	if not ZONE.has_point(cell): return "zone"
	if plots.size()>=cap: return "cap"
	if cell.distance_to(ORIGIN)<1.0: return "scarecrow"
	for plot in plots:
		if maxf(absf(float(plot.x)-cell.x),absf(float(plot.z)-cell.y))<1.7: return "plot"
	for corner in [Vector2.ZERO,Vector2(0.75,0.75),Vector2(-0.75,0.75),Vector2(0.75,-0.75),Vector2(-0.75,-0.75)]:
		if Roads.on_road(cell+corner): return "road"
	for door in Town.DOORS:
		if cell.distance_to(door.at)<3.0: return "door"
	var space := get_world_3d().direct_space_state
	var heights: Array[float]=[]
	for corner in [Vector2.ZERO,Vector2(0.75,0.75),Vector2(-0.75,0.75),Vector2(0.75,-0.75),Vector2(-0.75,-0.75)]:
		var p: Vector2=cell+corner
		var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(p.x,60,p.y),Vector3(p.x,-20,p.y),1|2|8|16))
		if hit.is_empty() or not (hit.collider is CollisionObject3D and hit.collider.collision_layer&1): return "blocked"
		if hit.normal.y<0.9: return "slope"
		heights.append(hit.position.y)
	if heights.max()-heights.min()>0.4: return "slope"
	if heights.min()<1.0: return "water"
	var shape := BoxShape3D.new()
	shape.size=Vector3(1.5,1.4,1.5)
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape=shape
	q.collision_mask=2|8|16
	q.transform=Transform3D(Basis.IDENTITY,Vector3(cell.x,heights.max()+0.85,cell.y))
	return "" if space.intersect_shape(q,1).is_empty() else "blocked"

func show_ghost(cell: Vector2, valid: bool) -> void:
	if not is_instance_valid(ghost) or ghost_valid!=valid:
		if is_instance_valid(ghost): ghost.queue_free()
		ghost=Art.ghost(valid)
		ghost_valid=valid
		add_child(ghost)
	ghost.visible=true
	ghost.position=Town.point(cell,0.02)
	var pulse := 0.92+sin(Time.get_ticks_msec()*0.008)*0.06
	ghost.scale=Vector3(pulse,1,pulse)

func hide_ghost() -> void:
	if is_instance_valid(ghost): ghost.visible=false

## Crop jumps out of the bed, spins and shrinks toward the walker.
func harvest_pop(index: int, toward: Vector3) -> void:
	if index<0 or index>=beds.size(): return
	var root: Node3D=beds[index].root
	var crop: Node3D=root.get_node_or_null("Crop")
	if not crop: return
	crop.name="Popping"
	var spark := root.get_node_or_null("Sparkle")
	if spark: spark.queue_free()
	var from := crop.global_position
	crop.top_level=true
	crop.global_position=from
	Art.burst(self,root.position+Vector3(0,0.3,0),"spark",12)
	Art.burst(self,root.position+Vector3(0,0.2,0),"dirt",10)
	var t := crop.create_tween()
	t.tween_property(crop,"scale",Vector3(1.25,1.4,1.25),0.1)
	t.tween_method(func(v: float):
		var p := from.lerp(toward+Vector3(0,1.6,0),v)
		p.y+=sin(v*PI)*1.6
		crop.global_position=p
		crop.rotation.y=v*TAU*1.5
		crop.scale=Vector3.ONE*lerpf(1.3,0.35,v),0.0,1.0,0.55).set_ease(Tween.EASE_IN_OUT)
	t.tween_callback(crop.queue_free)
	beds[index].sig=""
