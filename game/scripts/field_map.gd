extends Control
## Read-only view of the server snapshot. No position or game state is written here.
var snapshot: Dictionary = {}
var facing := Vector2(0,-1)
const INK := Color("41563e")

func _ready() -> void:
	custom_minimum_size=Vector2(214,174)
	mouse_filter=Control.MOUSE_FILTER_IGNORE

func map_point(x: float,z: float) -> Vector2:
	return Vector2(107+x*3.65,87+z*3.65)

func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO,size),Color("f5eddb"),true)
	draw_rect(Rect2(34,14,146,146),Color("dce4cf"),true)
	draw_rect(Rect2(34,14,146,146),Color("91a184"),false,1)
	for i in [-10,0,10]:
		draw_line(map_point(-20,i),map_point(20,i),Color("a5b69b",0.3))
		draw_line(map_point(i,-20),map_point(i,20),Color("a5b69b",0.3))
	var center := map_point(0,0)
	for hazard in snapshot.get("hazards",[]):
		draw_circle(map_point(hazard.x,hazard.z),hazard.radius*3.65,Color("9bcfdc") if hazard.kind=="ice" else Color("b96746"))
	for obstacle in snapshot.get("obstacles",[]): draw_circle(map_point(obstacle.x,obstacle.z),obstacle.radius*3.65,Color("87958e"))
	draw_circle(center,14.6,Color(0.94,0.61,0.25,0.30) if snapshot.get("warm",false) else Color(0.58,0.58,0.41,0.16))
	for item in snapshot.get("nodes",[]):
		if item.quantity<=0: continue
		var color: Color={"tree":Color("77956b"),"stone":Color("babcb5"),"berry":Color("e8a095"),"fiber":Color("b8c576")}.get(item.kind,INK)
		draw_circle(map_point(item.x,item.z),2,color)
	for enemy in snapshot.get("enemies",[]): draw_circle(map_point(enemy.x,enemy.z),3,Color("f77e68"))
	draw_colored_polygon(PackedVector2Array([center+Vector2(0,-5),center+Vector2(4,4),center+Vector2(-4,4)]),Color("edbf73"))
	var p := map_point(snapshot.get("x",0),snapshot.get("z",0))
	draw_circle(p,4,Color("354d4e"))
	draw_line(p,p+facing.normalized()*9,Color("354d4e"),2,true)
	draw_string(get_theme_default_font(),Vector2(102,12),"N",HORIZONTAL_ALIGNMENT_LEFT,-1,12,INK)
	draw_string(get_theme_default_font(),Vector2(8,170),"▲ 야영지    ● 나    ● 적",HORIZONTAL_ALIGNMENT_LEFT,-1,11,INK)

func update_state(state: Dictionary,direction: Vector2) -> void:
	snapshot=state
	facing=direction
	queue_redraw()
