extends Control
## Corner minimap: the archipelago render around the walker with place markers.
const Town = preload("res://scripts/town.gd")
const TownMap = preload("res://scripts/town_map.gd")
const VIEW_METRES := 64.0
var background: Texture2D
var player_at := Vector2.ZERO
var facing := 0.0
var area := ""
var font: Font

func _ready() -> void:
	custom_minimum_size = Vector2(204, 228)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	if ResourceLoader.exists(TownMap.MAP_IMAGE): background = load(TownMap.MAP_IMAGE)
	font = get_theme_default_font()

var last_minute := -1
func follow(at: Vector2, heading: float) -> void:
	var minute: int = Time.get_datetime_dict_from_system().minute
	if at.distance_to(player_at) < 0.05 and absf(heading-facing) < 0.02 and minute==last_minute: return
	last_minute = minute
	player_at = at
	facing = heading
	var name := island_name(at)
	area = name
	queue_redraw()

static func island_name(at: Vector2) -> String:
	if at.y > 66: return TranslationServer.translate("등대섬")
	if at.x < -2 and at.y < -12: return TranslationServer.translate("풍차 들판")
	if at.x >= -2 and at.y < 2: return TranslationServer.translate("정원 언덕")
	if at.x >= 10: return TranslationServer.translate("캠프 초원")
	return TranslationServer.translate("물결빛 광장")

func _draw() -> void:
	var frame := Rect2(2, 2, 200, 200)
	var border := StyleBoxFlat.new()
	border.bg_color = Color("2f6f7c")
	border.set_corner_radius_all(100)
	border.set_border_width_all(4)
	border.border_color = Color("e9d29b")
	border.shadow_color = Color(0,0,0,.35)
	border.shadow_size = 8
	draw_style_box(border, frame)
	if background:
		var pixels_per_metre := background.get_width()/TownMap.MAP_RECT.size.x
		var centre := (player_at-TownMap.MAP_RECT.position)*pixels_per_metre
		var span := VIEW_METRES*pixels_per_metre
		# A circle of quads keeps the round frame without a shader.
		var points := PackedVector2Array()
		var uvs := PackedVector2Array()
		for i in 48:
			var a := TAU*i/48.0
			var dir := Vector2(cos(a), sin(a))
			points.append(frame.get_center()+dir*94.0)
			uvs.append((centre+dir*span*.5)/Vector2(background.get_size()))
		draw_colored_polygon(points, Color.WHITE, uvs, background)
	var scale := 188.0/VIEW_METRES
	for place in Town.PLACES:
		var offset: Vector2 = (place.at-player_at)*scale
		if offset.length() > 86: continue
		draw_circle(frame.get_center()+offset, 5, Color("314c46"))
		draw_circle(frame.get_center()+offset, 3, Color("f3d98f"))
	var gate: Vector2 = (Town.GATE-player_at)*scale
	if gate.length() <= 86: draw_circle(frame.get_center()+gate, 5, Color("8a5fb0"))
	# Walker arrow points where the character faces.
	var tip := Vector2(0,-9).rotated(facing)
	var left := Vector2(-6,6).rotated(facing)
	var right := Vector2(6,6).rotated(facing)
	draw_colored_polygon(PackedVector2Array([frame.get_center()+tip, frame.get_center()+left, frame.get_center()+right]), Color("fff4d6"))
	draw_polyline(PackedVector2Array([frame.get_center()+tip, frame.get_center()+left, frame.get_center()+right, frame.get_center()+tip]), Color("3b2d1c"), 1.5)
	draw_string(font, Vector2(frame.get_center().x-5, 22), "N", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color("fff4d6"))
	# The village clock follows the player's real local time (day/night cycle).
	var now := Time.get_datetime_dict_from_system()
	var hour: int = now.hour
	var clock := (tr("오전 %d:%02d") if hour<12 else tr("오후 %d:%02d")) % [12 if hour%12==0 else hour%12, now.minute]
	var label := tr(area)+"  ·  "+clock
	var width := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
	var plate := StyleBoxFlat.new()
	plate.bg_color = Color(0.13,0.16,0.17,.86)
	plate.set_corner_radius_all(9)
	plate.border_color = Color("e9d29b")
	plate.set_border_width_all(1)
	draw_style_box(plate, Rect2(102-width*.5-12, 204, width+24, 23))
	draw_string(font, Vector2(102-width*.5, 221), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color("fff4d6"))
