extends Control
const Town=preload("res://scripts/town.gd")
var player_at := Vector2.ZERO
var destination := Vector2.ZERO
var has_destination := false
func _ready() -> void:
	custom_minimum_size=Vector2(365,345)
	mouse_filter=Control.MOUSE_FILTER_IGNORE
func p(v: Vector2) -> Vector2: return Vector2(182,171)+v*4.5
func _draw() -> void:
	draw_rect(Rect2(0,0,365,345),Color("426f72"))
	draw_rect(Rect2(p(Vector2(-36,-34)),Vector2(72,68)*4.5),Color("81975e"))
	draw_rect(Rect2(p(Vector2(-36,-34)),Vector2(72,16)*4.5),Color("a2af91"))
	draw_rect(Rect2(p(Vector2(-36,24)),Vector2(72,10)*4.5),Color("d0bb89"))
	draw_rect(Rect2(p(Vector2(-13,12)),Vector2(11,12)*4.5),Color("60989d"))
	for z in range(-34,34): draw_line(p(Vector2(Town.river_x(z),z)),p(Vector2(Town.river_x(z+1),z+1)),Color("60989d"),20)
	for z in [-5,18]: draw_line(p(Vector2(Town.river_x(z)-4,z)),p(Vector2(Town.river_x(z)+4,z)),Color("e5cfaa"),12)
	draw_line(p(Vector2(0,-29)),p(Vector2(0,11)),Color("d3c29a"),7)
	draw_line(p(Vector2(-22,2)),p(Vector2(13,-4)),Color("d3c29a"),7)
	draw_line(p(Vector2(27,-24)),p(Vector2(27,29)),Color("d3c29a"),7)
	for plot in Town.PLOTS: draw_rect(Rect2(p(plot)-Vector2(5,4),Vector2(10,8)),Color("835e44"))
	for i in Town.PLACES.size():
		var at := p(Town.PLACES[i].at)
		draw_circle(at,9,Color("314c46"))
		draw_string(get_theme_default_font(),at+Vector2(-4,5),str(i+1),HORIZONTAL_ALIGNMENT_LEFT,-1,13,Color("f3e7bd"))
	if has_destination:
		draw_line(p(player_at),p(destination),Color("f0d67f"),1.5,true)
		draw_arc(p(destination),13,0,TAU,32,Color("ffe393"),2)
	draw_circle(p(player_at),5,Color("fff6d8"))
	draw_string(get_theme_default_font(),Vector2(12,18),"N ↑     ● 현재 위치",HORIZONTAL_ALIGNMENT_LEFT,-1,12,Color("f3ead1"))
