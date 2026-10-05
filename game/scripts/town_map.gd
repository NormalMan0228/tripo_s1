extends Control
## Tab map of the island village. The background is a top-down render of the
## archipelago (game/tests/archipelago_probe.gd --topdown) covering MAP_RECT.
const Town=preload("res://scripts/town.gd")
const MAP_IMAGE := "res://assets/archipelago_map.png"
const MAP_RECT := Rect2(-87.5,-80,180,180)
const DRAW := Rect2(28,18,309,309)
var player_at := Vector2.ZERO
var destination := Vector2.ZERO
var has_destination := false
var background: Texture2D
func _ready() -> void:
	custom_minimum_size=Vector2(365,345)
	mouse_filter=Control.MOUSE_FILTER_IGNORE
	if ResourceLoader.exists(MAP_IMAGE): background=load(MAP_IMAGE)
func p(v: Vector2) -> Vector2: return DRAW.position+(v-MAP_RECT.position)/MAP_RECT.size*DRAW.size
func _draw() -> void:
	var frame := StyleBoxFlat.new()
	frame.bg_color=Color("eee0c5")
	frame.set_corner_radius_all(12)
	draw_style_box(frame,Rect2(0,0,365,345))
	if background: draw_texture_rect(background,DRAW,false)
	else: draw_rect(DRAW,Color("5fb8c9"))
	for plot in Town.PLOTS: draw_rect(Rect2(p(plot)-Vector2(2,2),Vector2(4,4)),Color("835e44"))
	for i in Town.PLACES.size():
		var at := p(Town.PLACES[i].at)
		draw_circle(at,8,Color("314c46"))
		draw_string(get_theme_default_font(),at+Vector2(-4 if i<9 else -7,4),str(i+1),HORIZONTAL_ALIGNMENT_LEFT,-1,11,Color("f3e7bd"))
	var gate := p(Town.GATE)
	draw_circle(gate,8,Color("7b5a8f"))
	draw_string(get_theme_default_font(),gate+Vector2(-5,4),tr("숲"),HORIZONTAL_ALIGNMENT_LEFT,-1,10,Color("f3e7bd"))
	if has_destination:
		draw_line(p(player_at),p(destination),Color("f0d67f"),1.5,true)
		draw_arc(p(destination),12,0,TAU,32,Color("ffe393"),2)
	draw_circle(p(player_at),7,Color("405653"))
	draw_circle(p(player_at),4.5,Color("fff6d8"))
	draw_rect(Rect2(32,22,146,23),Color("eee0c5"))
	draw_string(get_theme_default_font(),Vector2(37,38),tr("N ↑     ● 현재 위치"),HORIZONTAL_ALIGNMENT_LEFT,-1,12,Color("405653"))
