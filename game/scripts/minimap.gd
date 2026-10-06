extends Control
## Corner minimap: the archipelago render around the walker with place markers.
## Settings: north-up (arrow turns) or rotating (map turns, arrow points up), and a
## 12/24-hour clock (game_settings.gd).
const Town = preload("res://scripts/town.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const TownMap = preload("res://scripts/town_map.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const CLOCK: Texture2D = preload("res://assets/ui/clock.svg")
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
	font = RpgUi.FONT_STRONG
	GameSettings.listen(func(_keys): queue_redraw())
	# Placed by absolute position in the right half of the 1280-wide layout: keep the
	# same gap to the right edge, so a larger interface scale does not push it off.
	var base_width := float(ProjectSettings.get_setting("display/window/size/viewport_width", 1280))
	if get_parent() is Control and anchor_left == 0.0 and anchor_right == 0.0 and position.x > base_width*0.5:
		var gap := base_width-(position.x+custom_minimum_size.x)
		var top := position.y
		set_anchors_preset(Control.PRESET_TOP_RIGHT)
		offset_left = -(custom_minimum_size.x+gap); offset_right = -gap
		offset_top = top; offset_bottom = top+custom_minimum_size.y

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
	# Walnut rim and a gold band: the same metalwork as the portrait ring.
	draw_circle(frame.get_center()+Vector2(0,4), 103, Color(0.06,0.04,0.02,.35))
	draw_circle(frame.get_center(), 101, Color("4a2f17"))
	draw_circle(frame.get_center(), 99, Color("d9a446"))
	draw_circle(frame.get_center(), 96.5, Color("f3d58f"))
	draw_circle(frame.get_center(), 94.5, Color("2f6f7c"))
	# Rotating map: the world turns by the walker's heading so the arrow points up.
	var turn := facing if GameSettings.minimap_rotates() else 0.0
	var text_scale := GameSettings.text_scale()
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
			uvs.append((centre+dir.rotated(turn)*span*.5)/Vector2(background.get_size()))
		draw_colored_polygon(points, Color.WHITE, uvs, background)
	var scale := 188.0/VIEW_METRES
	for place in Town.PLACES:
		var offset: Vector2 = ((place.at-player_at)*scale).rotated(-turn)
		if offset.length() > 86: continue
		draw_circle(frame.get_center()+offset, 5, Color("314c46"))
		draw_circle(frame.get_center()+offset, 3, Color("f3d98f"))
	var gate: Vector2 = ((Town.GATE-player_at)*scale).rotated(-turn)
	if gate.length() <= 86: draw_circle(frame.get_center()+gate, 5, Color("8a5fb0"))
	# Walker arrow points where the character faces.
	var tip := Vector2(0,-9).rotated(facing-turn)
	var left := Vector2(-6,6).rotated(facing-turn)
	var right := Vector2(6,6).rotated(facing-turn)
	draw_colored_polygon(PackedVector2Array([frame.get_center()+tip, frame.get_center()+left, frame.get_center()+right]), Color("fff4d6"))
	draw_polyline(PackedVector2Array([frame.get_center()+tip, frame.get_center()+left, frame.get_center()+right, frame.get_center()+tip]), Color("3b2d1c"), 1.5)
	# Inner shadow, highlight line and four gold studs on the rim.
	draw_arc(frame.get_center(), 92.5, 0, TAU, 64, Color(0,0,0,.3), 4, true)
	draw_arc(frame.get_center(), 97.8, 0, TAU, 96, Color("fff0b8"), 1.2, true)
	for i in 4:
		var a := TAU*i/4.0-PI*0.5
		var at := frame.get_center()+Vector2(cos(a),sin(a))*97.8
		var r := 6.5 if i==0 else 4.5
		draw_colored_polygon(PackedVector2Array([at+Vector2(0,-r),at+Vector2(r,0),at+Vector2(0,r),at+Vector2(-r,0)]), Color("3a2312"))
		draw_colored_polygon(PackedVector2Array([at+Vector2(0,-r+1.5),at+Vector2(r-1.5,0),at+Vector2(0,r-1.5),at+Vector2(-r+1.5,0)]), Color("ffe39a") if i==0 else Color("e9b552"))
	var north := frame.get_center()+Vector2(0,-84).rotated(-turn)
	draw_string_outline(font, north+Vector2(-5*text_scale, 4*text_scale), "N", HORIZONTAL_ALIGNMENT_LEFT, -1, roundi(13*text_scale), 4, Color("3a2312"))
	draw_string(font, north+Vector2(-5*text_scale, 4*text_scale), "N", HORIZONTAL_ALIGNMENT_LEFT, -1, roundi(13*text_scale), Color("fff4d6"))
	# The village clock follows the player's real local time (day/night cycle).
	var now := Time.get_datetime_dict_from_system()
	var clock := GameSettings.format_clock(int(now.hour), int(now.minute))
	var label := tr(area)+"  ·  "+clock
	var label_size := roundi(14*text_scale)
	var width := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, label_size).x
	var plate := RpgUi.panel_style("pill")
	var plate_height := 26.0+(label_size-14)
	draw_style_box(plate, Rect2(102-width*.5-30, 202, width+52, plate_height))
	draw_texture_rect(CLOCK, Rect2(102-width*.5-22, 205+(label_size-14)*0.5, 19, 19), false, Color.WHITE)
	draw_string(font, Vector2(102-width*.5+4, 220+(label_size-14)*0.5), label, HORIZONTAL_ALIGNMENT_LEFT, -1, label_size, Color("fff4d6"))
