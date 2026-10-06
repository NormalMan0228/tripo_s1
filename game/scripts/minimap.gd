extends Control
## Corner minimap: the archipelago render around the walker with place markers.
## Settings: north-up (arrow turns) or rotating (map turns, arrow points up), and a
## 12/24-hour clock (game_settings.gd). Folding (RpgUi fold id "minimap", the
## chevron key beside the chip) rolls the map away and keeps only the place · clock
## chip, moved up into the corner.
const Town = preload("res://scripts/town.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const TownMap = preload("res://scripts/town_map.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const CLOCK: Texture2D = preload("res://assets/ui/clock.svg")
## Painted walnut-and-gold ring (tools/build_ui_kit.py): a 512 px texture whose opening
## has radius 180 and whose rim reaches 226; drawn at RING_SCALE around the map disc.
const RING_PATH := "res://assets/ui/frames/minimap_ring.png"
const RING_SCALE := 0.46
const MAP_RADIUS := 84.0
const VIEW_METRES := 64.0
## Chip top while open (under the map) and folded (the map's place).
const CHIP_OPEN_Y := 202.0
const CHIP_FOLDED_Y := 2.0
## How far the pieces below the map move up while it is folded.
const FOLD_LIFT := CHIP_OPEN_Y - CHIP_FOLDED_Y
var background: Texture2D
var player_at := Vector2.ZERO
var facing := 0.0
var area := ""
var font: Font
## 0 open .. 1 folded (chip only).
var fold := 0.0
var disc: Control
var key: Button
var fold_tween: Tween
## Route guide (guide.gd sets these): the route walker -> goal, the goal (INF: none),
## and the layer over the ring that carries the rim arrow.
var guide_route := PackedVector2Array()
var guide_target := Vector2.INF
var guide_layer: Control

func _ready() -> void:
	custom_minimum_size = Vector2(204, 228)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	if ResourceLoader.exists(TownMap.MAP_IMAGE): background = load(TownMap.MAP_IMAGE)
	font = RpgUi.FONT_STRONG
	GameSettings.listen(func(_keys): refresh())
	# Placed by absolute position in the right half of the 1280-wide layout: keep the
	# same gap to the right edge, so a larger interface scale does not push it off.
	var base_width := float(ProjectSettings.get_setting("display/window/size/viewport_width", 1280))
	if get_parent() is Control and anchor_left == 0.0 and anchor_right == 0.0 and position.x > base_width*0.5:
		var gap := base_width-(position.x+custom_minimum_size.x)
		var top := position.y
		set_anchors_preset(Control.PRESET_TOP_RIGHT)
		offset_left = -(custom_minimum_size.x+gap); offset_right = -gap
		offset_top = top; offset_bottom = top+custom_minimum_size.y
	# The round map draws on its own layer (behind the chip) so it can fade and shrink.
	disc = Control.new()
	disc.name = "Disc"
	disc.size = Vector2(204, 204)
	disc.pivot_offset = Vector2(102, 0)
	disc.mouse_filter = Control.MOUSE_FILTER_IGNORE
	disc.show_behind_parent = true
	disc.draw.connect(_draw_map)
	add_child(disc)
	# The painted ring is its own item over the map (drawing it inside _draw_map came out
	# as a white square in the Compatibility renderer); it fades and shrinks with the disc.
	if ResourceLoader.exists(RING_PATH):
		var ring := TextureRect.new()
		ring.name = "Ring"
		ring.texture = load(RING_PATH)
		ring.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		ring.stretch_mode = TextureRect.STRETCH_SCALE
		ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
		ring.size = ring.texture.get_size()*RING_SCALE
		ring.position = Vector2(102, 102)-ring.size*0.5
		disc.add_child(ring)
	# Hovering the round map names it (see _has_point).
	RpgUi.name_tip(self, tr("미니맵"), "Tab")
	key = RpgUi.fold_toggle(self, "minimap", Vector2.UP)
	RpgUi.foldable(self, "minimap", fold_to)

func refresh() -> void:
	if not is_instance_valid(disc): return
	queue_redraw()
	if disc.visible: disc.queue_redraw()
	if disc.visible and is_instance_valid(guide_layer): guide_layer.queue_redraw()
	place_key()

func fold_to(shut: bool, animate: bool) -> void:
	if fold_tween and fold_tween.is_valid(): fold_tween.kill()
	if animate and is_inside_tree():
		fold_tween = create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		fold_tween.tween_method(set_fold, fold, 1.0 if shut else 0.0, RpgUi.FOLD_TIME)
	else: set_fold(1.0 if shut else 0.0)

func set_fold(t: float) -> void:
	fold = t
	disc.visible = t < 1.0
	disc.modulate.a = 1.0-t
	disc.scale = Vector2.ONE*lerpf(1.0, 0.82, t)
	refresh()

## Only the open round map takes the mouse (for its name); the chip and the corners
## around the disc stay click-through.
func _has_point(point: Vector2) -> bool:
	return is_instance_valid(disc) and disc.visible and fold < 0.5 and point.distance_to(Vector2(102, 102)) <= 104.0

var last_minute := -1
func follow(at: Vector2, heading: float) -> void:
	var minute: int = Time.get_datetime_dict_from_system().minute
	if at.distance_to(player_at) < 0.05 and absf(heading-facing) < 0.02 and minute==last_minute: return
	last_minute = minute
	player_at = at
	facing = heading
	var name := island_name(at)
	area = name
	refresh()

static func island_name(at: Vector2) -> String:
	if at.y > 66: return TranslationServer.translate("등대섬")
	if at.x < -2 and at.y < -12: return TranslationServer.translate("풍차 들판")
	if at.x >= -2 and at.y < 2: return TranslationServer.translate("정원 언덕")
	if at.x >= 10: return TranslationServer.translate("캠프 초원")
	return TranslationServer.translate("물결빛 광장")

func _draw_map() -> void:
	var frame := Rect2(2, 2, 200, 200)
	var ring := ResourceLoader.exists(RING_PATH)
	var radius := MAP_RADIUS if ring else 94.5
	disc.draw_circle(frame.get_center()+Vector2(0,5), 106 if ring else 103, Color(0.06,0.04,0.02,.35))
	if not ring:
		# Code-drawn walnut rim and gold band when the painted ring is missing.
		disc.draw_circle(frame.get_center(), 101, Color("4a2f17"))
		disc.draw_circle(frame.get_center(), 99, Color("d9a446"))
		disc.draw_circle(frame.get_center(), 96.5, Color("f3d58f"))
	disc.draw_circle(frame.get_center(), radius+1.0, Color("2f6f7c"))
	# Rotating map: the world turns by the walker's heading so the arrow points up.
	var turn := facing if GameSettings.minimap_rotates() else 0.0
	var text_scale := GameSettings.text_scale()
	if background:
		var pixels_per_metre := background.get_width()/TownMap.MAP_RECT.size.x
		var centre := (player_at-TownMap.MAP_RECT.position)*pixels_per_metre
		# Same metres per pixel as the 94 px disc: a smaller disc shows a smaller area.
		var span := VIEW_METRES*pixels_per_metre*(radius/94.0)
		# A circle of quads keeps the round frame without a shader.
		var points := PackedVector2Array()
		var uvs := PackedVector2Array()
		for i in 48:
			var a := TAU*i/48.0
			var dir := Vector2(cos(a), sin(a))
			points.append(frame.get_center()+dir*radius)
			uvs.append((centre+dir.rotated(turn)*span*.5)/Vector2(background.get_size()))
		disc.draw_colored_polygon(points, Color.WHITE, uvs, background)
	var scale := 188.0/VIEW_METRES
	for place in Town.PLACES:
		var offset: Vector2 = ((place.at-player_at)*scale).rotated(-turn)
		if offset.length() > radius-8.0: continue
		disc.draw_circle(frame.get_center()+offset, 5, Color("314c46"))
		disc.draw_circle(frame.get_center()+offset, 3, Color("f3d98f"))
	var gate: Vector2 = ((Town.GATE-player_at)*scale).rotated(-turn)
	if gate.length() <= radius-8.0: disc.draw_circle(frame.get_center()+gate, 5, Color("8a5fb0"))
	if guide_target != Vector2.INF: _draw_guide(frame.get_center(), scale, turn, radius)
	# Walker arrow points where the character faces.
	var tip := Vector2(0,-9).rotated(facing-turn)
	var left := Vector2(-6,6).rotated(facing-turn)
	var right := Vector2(6,6).rotated(facing-turn)
	disc.draw_colored_polygon(PackedVector2Array([frame.get_center()+tip, frame.get_center()+left, frame.get_center()+right]), Color("fff4d6"))
	disc.draw_polyline(PackedVector2Array([frame.get_center()+tip, frame.get_center()+left, frame.get_center()+right, frame.get_center()+tip]), Color("3b2d1c"), 1.5)
	# Inner shadow, then (without the painted Ring child) the code-drawn line and studs.
	disc.draw_arc(frame.get_center(), radius-2.0, 0, TAU, 64, Color(0,0,0,.3), 4, true)
	if not ring:
		disc.draw_arc(frame.get_center(), 97.8, 0, TAU, 96, Color("fff0b8"), 1.2, true)
		for i in 4:
			var a := TAU*i/4.0-PI*0.5
			var at := frame.get_center()+Vector2(cos(a),sin(a))*97.8
			var r := 6.5 if i==0 else 4.5
			disc.draw_colored_polygon(PackedVector2Array([at+Vector2(0,-r),at+Vector2(r,0),at+Vector2(0,r),at+Vector2(-r,0)]), Color("3a2312"))
			disc.draw_colored_polygon(PackedVector2Array([at+Vector2(0,-r+1.5),at+Vector2(r-1.5,0),at+Vector2(0,r-1.5),at+Vector2(-r+1.5,0)]), Color("ffe39a") if i==0 else Color("e9b552"))
	var north := frame.get_center()+Vector2(0,-(radius-11.0)).rotated(-turn)
	disc.draw_string_outline(font, north+Vector2(-5*text_scale, 4*text_scale), "N", HORIZONTAL_ALIGNMENT_LEFT, -1, roundi(13*text_scale), 4, Color("3a2312"))
	disc.draw_string(font, north+Vector2(-5*text_scale, 4*text_scale), "N", HORIZONTAL_ALIGNMENT_LEFT, -1, roundi(13*text_scale), Color("fff4d6"))

## Route guide: guide.gd hands over the route and the goal (Vector2.INF clears them).
func show_guide(route: PackedVector2Array, goal: Vector2) -> void:
	guide_route = route
	guide_target = goal
	if not is_instance_valid(guide_layer) and is_instance_valid(disc):
		# Over the painted ring, so the rim arrow can sit on it.
		guide_layer = Control.new()
		guide_layer.name = "GuideRim"
		guide_layer.size = disc.size
		guide_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
		guide_layer.draw.connect(_draw_guide_rim)
		disc.add_child(guide_layer)
	refresh()

## The road route as gold dots and a flag at the goal, inside the disc.
func _draw_guide(centre: Vector2, scale: float, turn: float, radius: float) -> void:
	var limit := radius-4.0
	# Dots counted from the goal end stay put on the map while the walker moves.
	var carry := 0.0
	for i in range(guide_route.size()-2, -1, -1):
		var a: Vector2 = ((guide_route[i+1]-player_at)*scale).rotated(-turn)
		var b: Vector2 = ((guide_route[i]-player_at)*scale).rotated(-turn)
		var length := a.distance_to(b)
		if length < 0.01: continue
		if Geometry2D.get_closest_point_to_segment(Vector2.ZERO, a, b).length() > limit:
			carry = fposmod(carry-length, 7.0)
			continue
		var t := carry
		while t < length:
			var p := a.lerp(b, t/length)
			if p.length() < limit and p.length() > 8.0:
				disc.draw_circle(centre+p, 2.9, Color(0.23, 0.13, 0.03, 0.75))
				disc.draw_circle(centre+p, 1.9, Color("ffe08a"))
			t += 7.0
		carry = t-length
	var goal: Vector2 = ((guide_target-player_at)*scale).rotated(-turn)
	if goal.length() > radius-10.0: return
	var at := centre+goal
	disc.draw_circle(at, 4.0, Color(0.23, 0.13, 0.03, 0.55))
	disc.draw_line(at, at+Vector2(0, -15), Color("3a2312"), 2.6)
	var flag := PackedVector2Array([at+Vector2(0.5, -15.5), at+Vector2(11, -11.5), at+Vector2(0.5, -7.5)])
	disc.draw_colored_polygon(flag, Color("ffd257"))
	disc.draw_polyline(PackedVector2Array([flag[0], flag[1], flag[2]]), Color("3a2312"), 1.4)
	disc.draw_circle(at, 2.2, Color("ffd257"))

## A gold arrowhead on the ring toward a goal beyond the disc.
func _draw_guide_rim() -> void:
	if guide_target == Vector2.INF: return
	var radius := MAP_RADIUS if ResourceLoader.exists(RING_PATH) else 94.5
	var turn := facing if GameSettings.minimap_rotates() else 0.0
	var goal: Vector2 = ((guide_target-player_at)*(188.0/VIEW_METRES)).rotated(-turn)
	if goal.length() <= radius-10.0: return
	var out := goal.normalized()
	var side := out.orthogonal()
	var centre := Vector2(102, 102)
	var tip := centre+out*(radius+19.0)
	var base := centre+out*(radius+3.0)
	var head := PackedVector2Array([tip, base+side*9.5, base-side*9.5])
	guide_layer.draw_colored_polygon(PackedVector2Array([tip+out*2.0, base+side*12.0-out*1.5, base-side*12.0-out*1.5]), Color(0.18, 0.1, 0.02, 0.85))
	guide_layer.draw_colored_polygon(head, Color("ffd257"))
	guide_layer.draw_line(base+out*3.0, tip-out*3.0, Color("fff3c4"), 1.6)

## The village clock follows the player's real local time (day/night cycle).
func chip_text() -> String:
	var now := Time.get_datetime_dict_from_system()
	return tr(area)+"  ·  "+GameSettings.format_clock(int(now.hour), int(now.minute))

## The place · clock chip: centred under the map, or in its place while folded. A
## long name (English, large text) grows it leftwards so it stays off the screen edge.
func chip_rect() -> Rect2:
	var label_size := roundi(14*GameSettings.text_scale())
	var width := font.get_string_size(chip_text(), HORIZONTAL_ALIGNMENT_LEFT, -1, label_size).x
	return Rect2(minf(102-width*.5-30, 204-(width+52)), lerpf(CHIP_OPEN_Y, CHIP_FOLDED_Y, fold), width+52, 26.0+(label_size-14))

## The fold key rides at the chip's left end.
func place_key() -> void:
	if not is_instance_valid(key) or font == null: return
	var chip := chip_rect()
	key.position = Vector2(chip.position.x-key.size.x-6, chip.get_center().y-key.size.y*0.5)

func _draw() -> void:
	var label_size := roundi(14*GameSettings.text_scale())
	var chip := chip_rect()
	draw_style_box(RpgUi.panel_style("pill"), chip)
	draw_texture_rect(CLOCK, Rect2(chip.position.x+8, chip.position.y+3+(label_size-14)*0.5, 19, 19), false, Color.WHITE)
	draw_string(font, Vector2(chip.position.x+34, chip.position.y+18+(label_size-14)*0.5), chip_text(), HORIZONTAL_ALIGNMENT_LEFT, -1, label_size, Color("fff4d6"))
