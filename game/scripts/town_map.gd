extends Control
## Tab map of the island village. The background is a top-down render of the
## archipelago (game/tests/archipelago_probe.gd --topdown) covering MAP_RECT.
const Town=preload("res://scripts/town.gd")
const MAP_IMAGE := "res://assets/archipelago_map.png"
const MAP_RECT := Rect2(-87.5,-80,180,180)
const DRAW := Rect2(28,18,309,309)
## Route guide (guide.gd): a click on a numbered place, the forest gate or open ground
## asks for a pin there (id: place id, "gate", or "" for a spot); hovering a marker
## names it. The guided route draws as gold dots and the goal as a dropping pin.
signal picked(at: Vector2, id: String)
var player_at := Vector2.ZERO
var destination := Vector2.ZERO
var has_destination := false
var background: Texture2D
var route := PackedVector2Array()
var hover := ""
## Seconds (ticks) when the last pin dropped, for its bounce and ripple.
var pin_time := -100.0
func _ready() -> void:
	custom_minimum_size=Vector2(365,345)
	mouse_filter=Control.MOUSE_FILTER_STOP
	if ResourceLoader.exists(MAP_IMAGE): background=load(MAP_IMAGE)
func p(v: Vector2) -> Vector2: return DRAW.position+(v-MAP_RECT.position)/MAP_RECT.size*DRAW.size
func world(at: Vector2) -> Vector2: return MAP_RECT.position+(at-DRAW.position)/DRAW.size*MAP_RECT.size
## Place id (or "gate") under a map point, "" for none.
func marker_at(at: Vector2) -> String:
	for place in Town.PLACES:
		if at.distance_to(p(place.at))<11.0: return str(place.id)
	if at.distance_to(p(Town.GATE))<11.0: return "gate"
	return ""
func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		var id := marker_at(event.position)
		if id!=hover:
			hover=id
			mouse_default_cursor_shape=Control.CURSOR_POINTING_HAND if not id.is_empty() else Control.CURSOR_ARROW
			if not id.is_empty(): preload("res://scripts/rpg_ui.gd").sfx("hover")
			queue_redraw()
	elif event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_LEFT and DRAW.has_point(event.position):
		accept_event()
		var id := marker_at(event.position)
		var at: Vector2=Town.GATE if id=="gate" else (world(event.position) if id.is_empty() else Vector2.ZERO)
		for place in Town.PLACES:
			if place.id==id: at=place.at
		picked.emit(at,id)
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
	if has_destination and route.size()>1:
		# Gold dots along the guided roads, counted from the goal so they hold still.
		var carry := 0.0
		for i in range(route.size()-2,-1,-1):
			var a := p(route[i+1])
			var b := p(route[i])
			var length := a.distance_to(b)
			var t := carry
			while t<length:
				var dot := a.lerp(b,t/length)
				draw_circle(dot,2.6,Color(0.24,0.14,0.04,0.75))
				draw_circle(dot,1.7,Color("ffd866"))
				t+=6.0
			carry=t-length
	elif has_destination:
		draw_line(p(player_at),p(destination),Color("f0d67f"),1.5,true)
	if has_destination: draw_pin(p(destination))
	draw_circle(p(player_at),7,Color("405653"))
	draw_circle(p(player_at),4.5,Color("fff6d8"))
	if not hover.is_empty():
		var at := p(Town.GATE) if hover=="gate" else Vector2.ZERO
		var title := tr("숲")
		for place in Town.PLACES:
			if place.id==hover:
				at=p(place.at)
				title=tr(place.title)
		draw_arc(at,11,0,TAU,32,Color("ffe393"),2.5,true)
		var font := get_theme_default_font()
		var width := font.get_string_size(title,HORIZONTAL_ALIGNMENT_LEFT,-1,13).x
		var tag := Rect2(clampf(at.x-width*0.5-7,DRAW.position.x,DRAW.end.x-width-14),at.y-36,width+14,21)
		var plate := StyleBoxFlat.new()
		plate.bg_color=Color(0.16,0.12,0.08,0.88)
		plate.set_corner_radius_all(8)
		draw_style_box(plate,tag)
		draw_string(font,tag.position+Vector2(7,15),title,HORIZONTAL_ALIGNMENT_LEFT,-1,13,Color("fff0c8"))
	draw_rect(Rect2(32,22,146,23),Color("eee0c5"))
	draw_string(get_theme_default_font(),Vector2(37,38),tr("N ↑     ● 현재 위치"),HORIZONTAL_ALIGNMENT_LEFT,-1,12,Color("405653"))

## A gold map pin that drops in with a bounce and keeps a slow ripple at its foot.
func draw_pin(at: Vector2) -> void:
	var calm: bool=preload("res://scripts/game_settings.gd").reduced_motion()
	var since := Time.get_ticks_msec()*0.001-pin_time
	var drop := 0.0 if calm or since>0.5 else -26.0*pow(1.0-since/0.5,2.0)*absf(cos(since*9.0))
	var ripple := fposmod(since,1.6)/1.6 if not calm else 0.45
	draw_arc(at,4.0+ripple*15.0,0,TAU,32,Color(1.0,0.86,0.4,0.85*(1.0-ripple)),2.0,true)
	draw_circle(at,3.0,Color(0.23,0.13,0.03,0.5))
	var head := at+Vector2(0,-17+drop)
	draw_colored_polygon(PackedVector2Array([head+Vector2(-7,2),head+Vector2(7,2),at+Vector2(0,drop)]),Color("3a2312"))
	draw_circle(head,8.5,Color("3a2312"))
	draw_colored_polygon(PackedVector2Array([head+Vector2(-5.4,2.5),head+Vector2(5.4,2.5),at+Vector2(0,drop-2.2)]),Color("ffc94d"))
	draw_circle(head,7.0,Color("ffc94d"))
	draw_circle(head,2.8,Color("fff4cf"))
