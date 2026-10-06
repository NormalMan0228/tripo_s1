extends Node3D
## Gather spots across the islands. Ids and kinds match server/homestead.py NODES;
## the server owns drops and respawn times, this node only draws and animates them.
## Spots were sampled by tests/life_place_nodes.gd: on solid ground, at least 0.9 m
## past a road edge, 4 m from doors, clear of buildings and props; shells on sand,
## mushrooms and twigs in tree shade.
const Art=preload("res://scripts/life_art.gd")
const Town=preload("res://scripts/town.gd")
const NODES := [
	["shell_01","shell",27.6,7.7],["shell_02","shell",-11.2,-56.3],["shell_03","shell",73.7,13.9],["shell_04","shell",39.1,65.5],
	["shell_05","shell",4.1,86.5],["shell_06","shell",40.1,10.5],["shell_07","shell",-8.4,-30.5],["shell_08","shell",10.6,-22.6],
	["shell_09","shell",-55.1,69.2],["shell_10","shell",29.1,-65.3],["shell_11","shell",-22.4,-63.6],["shell_12","shell",9.3,-40.9],
	["mushroom_01","mushroom",35.9,38.0],["mushroom_02","mushroom",47.4,20.1],["mushroom_03","mushroom",42.2,-59.2],["mushroom_04","mushroom",80.9,38.1],
	["mushroom_05","mushroom",61.8,-35.6],["mushroom_06","mushroom",-27.0,-45.4],["mushroom_07","mushroom",-26.8,46.3],["mushroom_08","mushroom",-40.6,-37.6],
	["branch_01","branch",-19.7,37.7],["branch_02","branch",27.2,37.8],["branch_03","branch",33.3,-36.7],["branch_04","branch",77.6,37.4],
	["branch_05","branch",-56.7,24.9],["branch_06","branch",-50.1,60.8],["branch_07","branch",63.9,57.6],["branch_08","branch",44.3,19.4],
	["branch_09","branch",-69.8,25.6],["branch_10","branch",-61.0,13.0],
	["rock_01","rock",-65.8,-49.6],["rock_02","rock",22.9,8.5],["rock_03","rock",-24.4,7.4],["rock_04","rock",-56.9,-23.0],
	["rock_05","rock",77.4,54.0],["rock_06","rock",23.9,-52.2],["rock_07","rock",-38.4,58.2],["rock_08","rock",30.4,42.9],
	["rock_09","rock",-23.6,58.1],["rock_10","rock",69.2,37.0],["rock_11","rock",51.5,23.1],["rock_12","rock",22.3,33.4],
	["flower_01","flower",82.4,-24.2],["flower_02","flower",39.7,-10.1],["flower_03","flower",-35.0,2.6],["flower_04","flower",79.0,45.4],
	["flower_05","flower",37.8,50.2],["flower_06","flower",-27.4,29.8],["flower_07","flower",-9.1,19.1],["flower_08","flower",77.9,29.2],
	["flower_09","flower",19.0,-15.4],["flower_10","flower",58.8,-33.9],["flower_11","flower",23.2,-43.2],["flower_12","flower",74.2,-17.0],
	["herb_01","herb",-16.7,8.5],["herb_02","herb",30.7,47.7],["herb_03","herb",-53.9,-27.6],["herb_04","herb",59.6,33.4],
	["herb_05","herb",-48.4,9.2],["herb_06","herb",-39.5,6.4],["herb_07","herb",-11.1,15.6],["herb_08","herb",-51.4,31.0],
]
const PROMPTS := {"rock":"돌 캐기","shell":"조개껍데기 줍기","flower":"들꽃 꺾기","mushroom":"버섯 따기","herb":"향초 뜯기","branch":"나뭇가지 줍기"}
const PARTICLES := {"rock":"dust","shell":"sand","flower":"petal","mushroom":"spore","herb":"leaf","branch":"leaf"}
const SOUNDS := {"rock":"dig_stone","shell":"shell","flower":"dig_grass","mushroom":"pop","herb":"dig_grass","branch":"chop_wood"}
const REACH := 1.45
var spots: Array=[]
var busy := ""
var lit := ""

func build() -> void:
	for row in NODES:
		var root := Node3D.new()
		root.name=row[0]
		add_child(root)
		root.position=Town.point(Vector2(row[2],row[3]),-0.02)
		root.rotation.y=float(row[0].hash()%628)/100.0
		var model: Node3D=Art.forage(row[1],row[0].hash())
		root.add_child(model)
		# Finds read at the default zoom: a touch larger than life, shells glint on the sand.
		root.scale=Vector3.ONE*(1.7 if row[1]=="rock" else 1.5)
		if row[1]=="shell": Art.sparkles(model,0.15).amount=2
		spots.append({"id":row[0],"kind":row[1],"at":Vector2(row[2],row[3]),"root":root,"model":model,"ready":true})

## Shows or regrows spots from the server's respawn table.
func sync(state: Dictionary, now: float) -> void:
	var waiting: Dictionary=state.get("nodes",{})
	for spot in spots:
		if spot.id==busy: continue
		var ready: bool=now>=float(waiting.get(spot.id,0))
		if ready==spot.ready: continue
		spot.ready=ready
		var model: Node3D=spot.model
		if ready:
			model.visible=true
			model.scale=Vector3.ONE*0.05
			var t := model.create_tween()
			t.tween_property(model,"scale",Vector3.ONE,0.55).set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)
		else:
			model.visible=false

func nearest(at: Vector2) -> Dictionary:
	var best := {}
	var gap := REACH
	for spot in spots:
		if not spot.ready: continue
		var d: float=at.distance_to(spot.at)
		if d<gap:
			gap=d
			best=spot
	return best

func prompt(spot: Dictionary) -> String: return tr(PROMPTS[spot.kind])

## The spot the walker would pick up breathes a little so it reads as usable.
func highlight(id: String) -> void:
	if lit!=id:
		for spot in spots:
			if spot.id==lit and spot.ready and spot.id!=busy: spot.model.scale=Vector3.ONE
		lit=id
	if id.is_empty() or id==busy: return
	for spot in spots:
		if spot.id==id and spot.ready: spot.model.scale=Vector3.ONE*(1.0+0.07*absf(sin(Time.get_ticks_msec()*0.004)))

## Wind-up before the server answers: squash, shake and a puff.
func anticipate(spot: Dictionary) -> void:
	busy=spot.id
	var model: Node3D=spot.model
	var t := model.create_tween()
	t.tween_property(model,"scale",Vector3(1.15,0.8,1.15),0.09)
	t.tween_property(model,"scale",Vector3(0.92,1.1,0.92),0.08)
	t.tween_property(model,"scale",Vector3.ONE,0.12)
	Art.burst(self,spot.root.position+Vector3(0,0.3,0),PARTICLES[spot.kind],10)

## Plays the pick-up once the server confirmed it; false shakes the spot back.
func finish(spot: Dictionary, ok: bool) -> void:
	busy=""
	var model: Node3D=spot.model
	if not ok:
		var t := model.create_tween()
		for i in 3: t.tween_property(model,"rotation:z",0.08*(1 if i%2==0 else -1),0.05)
		t.tween_property(model,"rotation:z",0.0,0.05)
		return
	spot.ready=false
	Art.burst(self,spot.root.position+Vector3(0,0.25,0),PARTICLES[spot.kind],16)
	var t := model.create_tween()
	t.tween_property(model,"scale",Vector3(1.25,0.3,1.25),0.12).set_ease(Tween.EASE_IN)
	t.tween_callback(func(): model.visible=false; model.scale=Vector3.ONE)
