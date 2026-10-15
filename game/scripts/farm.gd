extends Node3D
## Draws every plot from the server's farm state (docs/design/FARM_API.md): the soil bed (wet
## while the water lasts, soaked and glossy right after watering), the crop's growth stage, a
## water-drop bubble and a slight droop over thirsty crops (half-speed growth until watered) and
## a golden halo with twinkles over ripe crops. A stage reached while the walker is near pops
## with leaves (and sparkles when ripe). Rules mirror homestead.py: the meadow zone, the 1.8 m
## grid around the scarecrow, spacing and the cap.
const Art=preload("res://scripts/life_art.gd")
const Fx=preload("res://scripts/fx.gd")
const Town=preload("res://scripts/town.gd")
const Roads=preload("res://scripts/roads.gd")
const GRID := 1.8
const ORIGIN := Vector2(-22,-33)
const ZONE := Rect2(-24.5,-40.5,9.0,11.5)
const STARTERS := 6
## Fresh water soaks the bed (puddles, gloss) and settles to WET_FLOOR over this many seconds;
## the soil stays that damp until the server's water runs out at the player's midnight.
const DRY_SECONDS := 40.0
const WET_FLOOR := 0.62
## Growth pops, thirsty bubbles and their sounds only play within this distance of the walker.
const NEAR := 14.0
## Seconds between "water me" bubbles over one thirsty bed.
const THIRST_EVERY := 3.6
## A crop reached a new stage while the walker was near (village_life plays its sound).
signal grew(index: int, stage: int)
## catalog.crops from the server (village_life sets it): stage_seconds split "growing" in two.
static var crops: Dictionary={}
var beds: Array=[]
var ghost: Node3D
var ghost_valid := false
## The walker's position (village_life sets it every frame); INF = nobody to show effects to.
var viewer := Vector3.INF

## The look of a bed: 0 empty, 1 seed, 2 sprout, 3 leafy, 4 budding, 5 ripe. Read from the
## server's plot (stage_index 0-3 of seed/sprout/growing/ripe, ready, progress); "growing" shows
## leafy for its first half and budding for the second (the crop's stage_seconds).
static func stage(plot: Dictionary, _now := 0.0) -> int:
	if not plot.get("crop"): return 0
	if plot.get("ready",false) or str(plot.get("stage",""))=="ripe": return 5
	var index := int(plot.get("stage_index",2 if plot.get("watered",false) else 0))
	if index<2: return index+1
	if index>=3: return 5
	var rule: Dictionary=crops.get(str(plot.crop),{})
	var times: Dictionary=rule.get("stage_seconds",{})
	var total := float(rule.get("seconds",0))
	var mid := 0.77
	if total>0 and times.has("growing"):
		mid=(float(times.get("seed",0))+float(times.get("sprout",0))+float(times.growing)*0.5)/total
	return 4 if float(plot.get("progress",0))>=mid else 3

## Planted, not ripe and without water: it grows at the server's half speed until watered.
static func thirsty(plot: Dictionary) -> bool:
	return not str(plot.get("crop","")).is_empty() and stage(plot)<5 and not plot.get("watered",false)

## How wet the soil looks (0 dry .. 1 just watered): soaked right after watering, damp while
## the water lasts, dry once it runs out (or on an empty bed).
static func wetness(plot: Dictionary, now: float) -> float:
	if not plot.get("crop") or not plot.get("watered",false): return 0.0
	var at := float(plot.get("watered_at",now-DRY_SECONDS))
	return maxf(WET_FLOOR,clampf(1.0-(now-at)/DRY_SECONDS,0.0,1.0))

func near(bed: Dictionary) -> bool:
	return viewer!=Vector3.INF and Vector2(viewer.x,viewer.z).distance_to(bed.at)<NEAR

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
			var soil := Art.soil_bed()
			soil.name="Soil"
			root.add_child(soil)
			beds.append({"root":root,"soil":soil,"at":Vector2.INF,"sig":"","wet":0.0,"shown":0.0,"thirst":randf()*THIRST_EVERY})
			root.scale=Vector3.ONE*0.2
			root.create_tween().tween_property(root,"scale",Vector3.ONE,0.4).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		var bed: Dictionary=beds[i]
		var root: Node3D=bed.root
		if bed.at!=at:
			bed.at=at
			root.position=Town.point(at,-0.06)
		bed.wet=wetness(plot,now)
		bed.thirsty=thirsty(plot)
		var s := stage(plot,now)
		var sig := "%s/%d" % [plot.get("crop",""),s]
		if sig!=bed.sig:
			var grew_now: bool=not bed.sig.is_empty() and s>1 and sig.get_slice("/",0)==bed.sig.get_slice("/",0)
			bed.sig=sig
			bed.stage=s
			for old_name in ["Crop","Sparkle","Halo"]:
				var old := root.get_node_or_null(old_name)
				if old: old.free()
			if s>0:
				var crop := Art.crop(str(plot.crop),s,i*97+int(plot.get("planted_at",0)))
				crop.name="Crop"
				root.add_child(crop)
				if grew_now:
					crop.scale=Vector3(0.7,0.4,0.7)
					crop.create_tween().tween_property(crop,"scale",Vector3.ONE,0.5).set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)
					if near(bed): grow_pop(i,s)
			if s==5:
				var spark := Art.sparkles(root,Art.crop_height(str(plot.crop))*0.8+0.3)
				spark.name="Sparkle"
				var halo := Art.halo()
				halo.name="Halo"
				root.add_child(halo)

## Leaves and a soft ring when a crop moves up a stage; sparkles, a glow and a golden ring when
## it turns ripe.
func grow_pop(index: int, s: int) -> void:
	var bed: Dictionary=beds[index]
	var root: Node3D=bed.root
	var top: Vector3=root.global_position+Vector3(0,0.35+0.25*(s-2),0)
	Fx.burst(self,top,"leaf",7 if s<5 else 5,Color(0,0,0,0),0.4)
	Fx.ring(self,root.global_position+Vector3(0,0.12,0),0.95,Color(0.78,1.0,0.6,0.55),0.7)
	if s==5:
		Fx.burst(self,top+Vector3(0,0.2,0),"sparkle",14,Color(0,0,0,0),0.5)
		Fx.glow(self,top,Color("ffd860"),1.5,1.1)
		Fx.ring(self,root.global_position+Vector3(0,0.14,0),1.25,Color(1.0,0.86,0.4,0.75),0.9)
	grew.emit(index,s)

func _process(delta: float) -> void:
	var t := Time.get_ticks_msec()*0.001
	for i in beds.size():
		var bed: Dictionary=beds[i]
		var root: Node3D=bed.root
		# Water soaks in quickly (a darkening spread) and dries slowly (server time drives it).
		var shown: float=bed.shown
		shown=move_toward(shown,bed.wet,delta*1.6) if bed.wet>shown else bed.wet
		if absf(shown-bed.shown)>0.002 or shown==0.0 and bed.shown!=0.0:
			bed.shown=shown
			Art.set_wet(bed.soil,shown)
		var s: int=bed.get("stage",0)
		var crop: Node3D=root.get_node_or_null("Crop")
		if bed.get("thirsty",false):
			# Without water: a small drop bubble now and then, and the plant droops a little.
			if crop: crop.rotation=Vector3(0.09+sin(t*1.3+bed.at.y)*0.02,0,0)
			bed.thirst-=delta
			if bed.thirst<=0.0:
				bed.thirst=THIRST_EVERY+randf()*0.8
				if near(bed): Fx.bubble(self,root.global_position+Vector3(0,0.75+0.2*maxi(0,s-2),0),"drop")
		elif s==5:
			if crop: crop.position.y=absf(sin(t*2.2+bed.at.x))*0.035
			var halo: Node3D=root.get_node_or_null("Halo")
			if halo:
				var pulse := 0.5+0.5*sin(t*2.4+bed.at.x*1.3)
				halo.scale=Vector3.ONE*(0.9+0.12*pulse)
				halo.position.y=0.17+0.01*pulse
		elif crop:
			# Watered crops stand up (seeds lie still) and sway a touch in the breeze.
			crop.rotation=Vector3(0,0,sin(t*1.1+bed.at.x*0.7)*0.025) if s>=2 else Vector3.ZERO

## Water poured on bed `index`: a splash, a ring of wet soil and the soil darkening at once.
func watered(index: int) -> void:
	if index<0 or index>=beds.size(): return
	var bed: Dictionary=beds[index]
	var root: Node3D=bed.root
	Fx.burst(self,root.global_position+Vector3(0,0.2,0),"splash",12,Color(0,0,0,0),0.55)
	Fx.ring(self,root.global_position+Vector3(0,0.12,0),1.1,Color(0.62,0.85,1.0,0.7),0.8)
	bed.thirst=THIRST_EVERY*2
	bed.thirsty=false
	bed.wet=1.0
	var crop: Node3D=root.get_node_or_null("Crop")
	if crop: Fx.squash(crop,0.2,0.35)

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
	for old_name in ["Sparkle","Halo"]:
		var old := root.get_node_or_null(old_name)
		if old: old.queue_free()
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
