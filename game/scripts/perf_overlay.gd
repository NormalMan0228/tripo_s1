extends CanvasLayer
## In-game performance overlay (F2, or Settings > 그래픽 > 성능 표시; off by default): a small
## translucent panel in the bottom-right corner with frame rate and frame times (average and the worst
## 1 %), process/physics time, memory and video memory, draw calls and triangles, node/object
## counts, the scene, the presence round trip and how many players / residents are nearby.
## The numbers refresh every REFRESH s. While hidden it does nothing at all (no process); while
## shown it records one frame time per frame and rebuilds its text twice a second (its own cost is
## printed on the last line, measured).
const RpgUi = preload("res://scripts/rpg_ui.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const TOGGLE_KEY := KEY_F2
const REFRESH := 0.5
## Frame times kept for the average and the worst 1 % (10 s at 60 fps).
const WINDOW := 600
const NEAR := 25.0
const PRESENCE := "/v1/social/presence"

var panel: PanelContainer
var label: Label
var times := PackedFloat32Array()
var cursor := 0
var filled := 0
var clock := 0.0
var cost_us := 0.0
## The frame it was made in: ImeCaret makes it on the first F2 and shows it, and that same key
## press then reaches this _input too (it hid it again at once).
var born_frame := -1

func _ready() -> void:
	layer = 120
	born_frame = Engine.get_process_frames()
	process_mode = Node.PROCESS_MODE_ALWAYS
	times.resize(WINDOW)
	panel = PanelContainer.new()
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var look := RpgUi.style(Color(RpgUi.NIGHT.r, RpgUi.NIGHT.g, RpgUi.NIGHT.b, 0.62), 8, Color(RpgUi.GOLD, 0.45), 1)
	look.content_margin_left = 10
	look.content_margin_right = 10
	look.content_margin_top = 6
	look.content_margin_bottom = 6
	panel.add_theme_stylebox_override("panel", look)
	# Bottom right: the minimap and the map card hold the top right in the village and on
	# expeditions; this corner is free everywhere (hotbar centre, chat bottom left).
	panel.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	panel.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	panel.grow_vertical = Control.GROW_DIRECTION_BEGIN
	panel.offset_left = -12
	panel.offset_right = -12
	panel.offset_top = -12
	panel.offset_bottom = -12
	add_child(panel)
	label = Label.new()
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_font_size_override("font_size", 13)
	label.add_theme_color_override("font_color", RpgUi.INK)
	label.add_theme_color_override("font_outline_color", RpgUi.OUTLINE)
	label.add_theme_constant_override("outline_size", 3)
	label.add_theme_constant_override("line_spacing", -2)
	panel.add_child(label)
	GameSettings.listen(_on_settings)
	show_overlay(bool(GameSettings.get_value("perf_overlay")))

func _exit_tree() -> void:
	GameSettings.unlisten(_on_settings)

func _on_settings(keys: Array[String]) -> void:
	if "perf_overlay" in keys: show_overlay(bool(GameSettings.get_value("perf_overlay")))

func show_overlay(value: bool) -> void:
	visible = value
	set_process(value)
	if value:
		filled = 0
		cursor = 0
		clock = REFRESH

func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == TOGGLE_KEY:
		if Engine.get_process_frames() == born_frame: return
		show_overlay(not visible)

func _process(delta: float) -> void:
	times[cursor] = delta
	cursor = (cursor+1) % WINDOW
	filled = mini(filled+1, WINDOW)
	clock += delta
	if clock < REFRESH: return
	clock = 0.0
	var started := Time.get_ticks_usec()
	label.text = describe()
	cost_us = lerpf(cost_us, float(Time.get_ticks_usec()-started), 0.5) if cost_us > 0.0 else float(Time.get_ticks_usec()-started)

## Average and worst-1 % frame time (ms) over the kept window.
func frame_stats() -> Vector2:
	if filled == 0: return Vector2.ZERO
	var kept := times.slice(0, filled) if filled < WINDOW else times.duplicate()
	var total := 0.0
	for t in kept: total += t
	kept.sort()
	var worst := kept.slice(kept.size()-maxi(1, kept.size()/100))
	var worst_total := 0.0
	for t in worst: worst_total += t
	return Vector2(total/kept.size(), worst_total/worst.size())*1000.0

func describe() -> String:
	var frames := frame_stats()
	var scene := get_tree().current_scene
	var lines := PackedStringArray()
	lines.append("FPS %d   %.1f ms  (1%% %.1f ms)" % [Engine.get_frames_per_second(), frames.x, frames.y])
	lines.append("CPU %.1f ms   물리 %.1f ms" % [Performance.get_monitor(Performance.TIME_PROCESS)*1000.0, Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)*1000.0])
	lines.append("메모리 %.0f MB   VRAM %.0f MB" % [Performance.get_monitor(Performance.MEMORY_STATIC)/1048576.0, Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED)/1048576.0])
	lines.append("드로우콜 %d   삼각형 %s" % [Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME), short(Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME))])
	lines.append("노드 %d   오브젝트 %d" % [Performance.get_monitor(Performance.OBJECT_NODE_COUNT), Performance.get_monitor(Performance.OBJECT_COUNT)])
	var where := str(scene.name) if scene else "-"
	if scene and scene.get("screen") is String: where += " · "+str(scene.get("screen"))
	lines.append("장면 "+where)
	var api = scene.get("api") if scene else null
	var trip = api.get("round_trip_ms") if is_instance_valid(api) else null
	var ms: int = int(trip.get(PRESENCE, -1)) if trip is Dictionary else -1
	lines.append("서버 응답 "+("%d ms" % ms if ms >= 0 else "-"))
	var counts := nearby(scene)
	lines.append("근처 플레이어 %d   주민 %d" % [counts.x, counts.y])
	lines.append("(표시 비용 %.2f ms · F2)" % (cost_us/1000.0))
	return "\n".join(lines)

static func short(value: float) -> String:
	if value >= 1000000.0: return "%.1fM" % (value/1000000.0)
	if value >= 1000.0: return "%.0fK" % (value/1000.0)
	return str(int(value))

## Other players drawn in this scene and residents/villagers within NEAR m of the walker.
func nearby(scene: Node) -> Vector2i:
	if scene == null: return Vector2i.ZERO
	var players := 0
	var social = scene.get("social")
	if is_instance_valid(social) and social.get("peers") is Dictionary: players = social.peers.size()
	elif scene.get("peers") is Dictionary: players = scene.peers.size()
	var hero = scene.get("player")
	if not hero is Node3D: hero = scene.get("hero")
	var residents := 0
	if hero is Node3D and (hero as Node3D).is_inside_tree():
		var at: Vector3 = (hero as Node3D).global_position
		for plate in get_tree().get_nodes_in_group("npc_nameplates"):
			var owner_node := (plate as Node).get_parent() as Node3D
			if owner_node and owner_node.is_visible_in_tree() and owner_node.global_position.distance_to(at) < NEAR: residents += 1
	return Vector2i(players, residents)
