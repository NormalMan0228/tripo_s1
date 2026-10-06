extends RefCounted
## The game's UI kit: bundled fonts, 9-slice frames (parchment, night glass, wood
## buttons, slots, ribbons), the shared Theme, a matching icon set, soft UI sounds
## and small motions. Player-facing HUD pieces (character frame, slot hotbar, the
## interaction prompt, title-menu buttons) are built here too. Text is passed
## through tr() by the callers.
##
## Frames are drawn at 2x by tools/build_ui_frames.py and shown at 1x through an
## ImageTexture size override, so they stay crisp when the 1280x800 canvas is
## stretched to a larger window.
const INK := Color("fff4d6")
const GOLD := Color("e9d29b")
const NIGHT := Color(0.11,0.14,0.15,0.86)
## Text on parchment cards.
const PAPER_INK := Color("3c2e1e")
const PAPER_MUTED := Color("7a6446")
const ACCENT := Color("b0452f")
const LEAF := Color("4a7536")
const SOFT := Color("d8e3d4")
const OUTLINE := Color(0.07,0.05,0.03,0.92)

const GameSettings = preload("res://scripts/game_settings.gd")
const FONT_BODY: Font = preload("res://assets/fonts/ui_body.tres")
const FONT_STRONG: Font = preload("res://assets/fonts/ui_strong.tres")
const FONT_BOLD: Font = preload("res://assets/fonts/ui_bold.tres")
const FONT_DISPLAY: Font = preload("res://assets/fonts/ui_display.tres")
## Tabular figures so counters and timers do not jitter while they change.
const FONT_NUMBERS: Font = preload("res://assets/fonts/ui_numbers.tres")

## name: [texture margins, expand margins, content margins] at 2x (from frames.json).
const FRAMES := {
	"panel_paper":[[54, 50, 54, 62],[14, 10, 14, 22],[26, 22, 26, 22]],
	"panel_night":[[54, 50, 54, 62],[14, 10, 14, 22],[26, 22, 26, 22]],
	"panel_night_plain":[[54, 50, 54, 62],[14, 10, 14, 22],[26, 22, 26, 22]],
	"panel_paper_plain":[[54, 50, 54, 62],[14, 10, 14, 22],[26, 22, 26, 22]],
	"pill_night":[[37, 33, 37, 37],[8, 6, 8, 12],[22, 9, 22, 9]],
	"pill_paper":[[37, 33, 37, 37],[8, 6, 8, 12],[22, 9, 22, 9]],
	"tooltip":[[29, 25, 29, 29],[8, 6, 8, 12],[22, 9, 22, 9]],
	"btn_paper_normal":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 7, 16, 15]],
	"btn_paper_hover":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 7, 16, 15]],
	"btn_paper_pressed":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 9, 16, 9]],
	"btn_paper_disabled":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 7, 16, 15]],
	"btn_green_normal":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 7, 16, 15]],
	"btn_green_hover":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 7, 16, 15]],
	"btn_green_pressed":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 9, 16, 9]],
	"btn_green_disabled":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 7, 16, 15]],
	"btn_gold_normal":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 7, 16, 15]],
	"btn_gold_hover":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 7, 16, 15]],
	"btn_gold_pressed":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 9, 16, 9]],
	"btn_gold_disabled":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 7, 16, 15]],
	"btn_night_normal":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 7, 16, 15]],
	"btn_night_hover":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 7, 16, 15]],
	"btn_night_pressed":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 9, 16, 9]],
	"btn_night_disabled":[[28, 26, 28, 30],[6, 6, 6, 6],[16, 7, 16, 15]],
	"focus":[[28, 28, 28, 28],[6, 6, 6, 6],[]],
	"slot_night":[[32, 32, 32, 32],[4, 4, 4, 4],[8, 8, 8, 8]],
	"slot_night_hover":[[32, 32, 32, 32],[4, 4, 4, 4],[8, 8, 8, 8]],
	"slot_night_pressed":[[32, 32, 32, 32],[4, 4, 4, 4],[8, 8, 8, 8]],
	"slot_night_primary":[[32, 32, 32, 32],[4, 4, 4, 4],[8, 8, 8, 8]],
	"slot_paper":[[32, 32, 32, 32],[4, 4, 4, 4],[8, 8, 8, 8]],
	"slot_paper_hover":[[32, 32, 32, 32],[4, 4, 4, 4],[8, 8, 8, 8]],
	"slot_paper_empty":[[32, 32, 32, 32],[4, 4, 4, 4],[8, 8, 8, 8]],
	"field_paper":[[20, 20, 20, 20],[4, 4, 4, 4],[14, 9, 14, 9]],
	"field_paper_focus":[[20, 20, 20, 20],[4, 4, 4, 4],[14, 9, 14, 9]],
	"field_night":[[20, 20, 20, 20],[4, 4, 4, 4],[14, 9, 14, 9]],
	"field_night_focus":[[20, 20, 20, 20],[4, 4, 4, 4],[14, 9, 14, 9]],
	"bar_bg":[[16, 16, 16, 16],[0, 0, 0, 0],[]],
	"bar_fill":[[16, 16, 16, 16],[0, 0, 0, 0],[]],
	"ribbon":[[52, 30, 52, 30],[0, 0, 0, 0],[48, 6, 48, 10]],
	"ribbon_teal":[[52, 30, 52, 30],[0, 0, 0, 0],[48, 6, 48, 10]],
	"keycap":[[14, 14, 14, 16],[1, 1, 1, 1],[6, 1, 6, 3]],
	"scroll_grabber":[[10, 10, 10, 10],[0, 0, 0, 0],[]],
	"scroll_grabber_hover":[[10, 10, 10, 10],[0, 0, 0, 0],[]],
	"scroll_track":[[10, 10, 10, 10],[0, 0, 0, 0],[]],
	"card_frame":[[42, 38, 42, 50],[12, 8, 12, 20],[]],
}
## Design canvas the HUD is laid out on; pin() keeps pieces on their edge when the
## interface scale (GameSettings ui_scale) shrinks the logical canvas.
const CANVAS := Vector2(1280, 800)

static var _textures := {}
static var _theme: Theme
static var _sounds := {}
static var _voice := 0
static var _last_hover := 0
static var _last_played := {}
static var _night_theme: Theme

# ------------------------------------------------------------------ resources

## A 2x PNG from assets/ui/frames shown at 1x (plain texture when nothing draws).
static func half(name: String) -> Texture2D:
	if _textures.has(name): return _textures[name]
	var source: Texture2D = load("res://assets/ui/frames/%s.png" % name)
	var texture: Texture2D = source
	if source and DisplayServer.get_name() != "headless":
		var image := source.get_image()
		if image:
			var scaled := ImageTexture.create_from_image(image)
			scaled.set_size_override(Vector2i(image.get_width()/2, image.get_height()/2))
			texture = scaled
	_textures[name] = texture
	return texture

## A 9-slice frame. Each call returns a fresh box, so callers may adjust margins.
static func frame(name: String, tint := Color.WHITE) -> StyleBoxTexture:
	var spec: Array = FRAMES.get(name, [[0,0,0,0],[0,0,0,0],[]])
	var box := StyleBoxTexture.new()
	box.texture = half(name)
	var sides := [SIDE_LEFT, SIDE_TOP, SIDE_RIGHT, SIDE_BOTTOM]
	for i in 4:
		box.set_texture_margin(sides[i], spec[0][i]*0.5)
		box.set_expand_margin(sides[i], spec[1][i]*0.5)
		if not spec[2].is_empty(): box.set_content_margin(sides[i], spec[2][i]*0.5)
	box.modulate_color = tint
	return box

## Panel looks: "paper" (cards and windows), "night" (HUD glass with gold studs),
## "night_plain", "paper_plain", "pill" (toasts, chips), "pill_paper".
static func panel_style(kind := "night", padding := -1.0) -> StyleBoxTexture:
	var names := {"paper":"panel_paper","night":"panel_night","night_plain":"panel_night_plain","paper_plain":"panel_paper_plain","pill":"pill_night","pill_paper":"pill_paper"}
	var box := frame(names.get(kind, "panel_night"))
	if padding >= 0.0: box.set_content_margin_all(padding)
	return box

static func icon_texture(name: String) -> Texture2D:
	var path := name if name.begins_with("res://") else "res://assets/ui/%s.svg" % name
	return load(path) if ResourceLoader.exists(path) else null

## Flat box kept for older callers (studio, settings); softer shadow, AA corners.
static func style(fill: Color, radius := 14, border := GOLD, width := 2) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = fill
	box.set_corner_radius_all(radius)
	box.corner_detail = 10
	box.set_border_width_all(width)
	box.border_color = border
	box.shadow_color = Color(0.05,0.03,0.01,.32)
	box.shadow_size = 10
	box.shadow_offset = Vector2(0,4)
	box.anti_aliasing = true
	box.content_margin_left = 12
	box.content_margin_right = 12
	box.content_margin_top = 8
	box.content_margin_bottom = 8
	return box

# ------------------------------------------------------------------ theme

static func _buttons(t: Theme, type: String, base: String, font: Color, outline := false) -> void:
	for state in ["normal","hover","pressed","disabled"]:
		t.set_stylebox(state, type, frame(base+"_"+state))
	t.set_stylebox("hover_pressed", type, frame(base+"_pressed"))
	t.set_stylebox("focus", type, frame("focus"))
	for item in ["font_color","font_hover_color","font_pressed_color","font_focus_color","font_hover_pressed_color"]:
		t.set_color(item, type, font)
	t.set_color("font_disabled_color", type, Color(font, 0.55))
	t.set_color("icon_normal_color", type, Color.WHITE)
	if outline:
		t.set_color("font_outline_color", type, Color(OUTLINE, 0.75))
		t.set_constant("outline_size", type, 3)

## The shared theme: Main's HUD root, the studio and every panel under them use it.
static func theme() -> Theme:
	if _theme: return _theme
	var t := Theme.new()
	t.default_font = FONT_BODY
	t.default_font_size = 15
	t.set_color("font_color", "Label", PAPER_INK)
	t.set_constant("line_spacing", "Label", 3)
	# Buttons: parchment keys by default, then leaf-green, gold and night variants.
	_buttons(t, "Button", "btn_paper", PAPER_INK)
	t.set_font("font", "Button", FONT_STRONG)
	t.set_constant("h_separation", "Button", 8)
	for spec in [["PrimaryButton","btn_green",INK,true],["GoldButton","btn_gold",PAPER_INK,false],["NightButton","btn_night",INK,true]]:
		t.set_type_variation(spec[0], "Button")
		_buttons(t, spec[0], spec[1], spec[2], spec[3])
	t.set_type_variation("ChoiceButton", "Button")
	t.set_stylebox("pressed", "ChoiceButton", frame("btn_gold_normal"))
	t.set_stylebox("hover_pressed", "ChoiceButton", frame("btn_gold_hover"))
	t.set_type_variation("SlotButton", "Button")
	for state in ["normal","disabled"]: t.set_stylebox(state, "SlotButton", frame("slot_paper" if state=="normal" else "slot_paper_empty"))
	for state in ["hover","pressed","hover_pressed"]: t.set_stylebox(state, "SlotButton", frame("slot_paper_hover"))
	t.set_stylebox("focus", "SlotButton", StyleBoxEmpty.new())
	t.set_type_variation("HudSlot", "Button")
	t.set_stylebox("normal", "HudSlot", frame("slot_night"))
	t.set_stylebox("hover", "HudSlot", frame("slot_night_hover"))
	t.set_stylebox("pressed", "HudSlot", frame("slot_night_pressed"))
	t.set_stylebox("hover_pressed", "HudSlot", frame("slot_night_pressed"))
	t.set_stylebox("disabled", "HudSlot", frame("slot_night", Color(1,1,1,.55)))
	t.set_stylebox("focus", "HudSlot", StyleBoxEmpty.new())
	for item in ["font_color","font_hover_color","font_pressed_color","font_hover_pressed_color","font_focus_color"]: t.set_color(item, "HudSlot", INK)
	# Check boxes, radios and toggles draw only their icon and text.
	for type in ["CheckBox","CheckButton"]:
		for state in ["normal","pressed","hover","hover_pressed","disabled","focus"]: t.set_stylebox(state, type, StyleBoxEmpty.new())
		for item in ["font_color","font_hover_color","font_pressed_color","font_hover_pressed_color","font_focus_color"]: t.set_color(item, type, PAPER_INK)
	t.set_icon("checked", "CheckBox", half("check_on"))
	t.set_icon("unchecked", "CheckBox", half("check_off"))
	t.set_icon("radio_checked", "CheckBox", half("radio_on"))
	t.set_icon("radio_unchecked", "CheckBox", half("radio_off"))
	t.set_icon("arrow", "OptionButton", half("arrow_down"))
	t.set_constant("arrow_margin", "OptionButton", 12)
	# Text entry: an inset parchment well that glows gold on focus.
	for type in ["LineEdit","TextEdit"]:
		t.set_stylebox("normal", type, frame("field_paper"))
		t.set_stylebox("read_only", type, frame("field_paper"))
		t.set_stylebox("focus", type, frame("field_paper_focus"))
		t.set_color("font_color", type, PAPER_INK)
		t.set_color("font_placeholder_color", type, Color(PAPER_INK, .42))
		t.set_color("caret_color", type, PAPER_INK)
		t.set_color("selection_color", type, Color("f0c75e", .55))
		t.set_color("font_selected_color", type, PAPER_INK)
	t.set_type_variation("NightField", "LineEdit")
	t.set_stylebox("normal", "NightField", frame("field_night"))
	t.set_stylebox("focus", "NightField", frame("field_night_focus"))
	t.set_color("font_color", "NightField", INK)
	t.set_color("caret_color", "NightField", GOLD)
	t.set_color("font_placeholder_color", "NightField", Color(1,1,1,.42))
	# Lists and menus.
	var well := frame("field_paper")
	well.set_content_margin_all(8)
	t.set_stylebox("panel", "ItemList", well)
	t.set_stylebox("focus", "ItemList", StyleBoxEmpty.new())
	var picked := StyleBoxFlat.new()
	picked.bg_color = Color("f0c75e", .45)
	picked.set_corner_radius_all(8)
	picked.border_color = Color("c9a25a")
	picked.set_border_width_all(1)
	var hovered := StyleBoxFlat.new()
	hovered.bg_color = Color(1,1,1,.4)
	hovered.set_corner_radius_all(8)
	for item in ["selected","selected_focus"]: t.set_stylebox(item, "ItemList", picked)
	t.set_stylebox("hovered", "ItemList", hovered)
	t.set_stylebox("cursor", "ItemList", StyleBoxEmpty.new())
	t.set_stylebox("cursor_unfocused", "ItemList", StyleBoxEmpty.new())
	for item in ["font_color","font_selected_color","font_hovered_color"]: t.set_color(item, "ItemList", PAPER_INK)
	t.set_constant("v_separation", "ItemList", 6)
	var menu := frame("panel_paper_plain")
	menu.set_content_margin_all(10)
	t.set_stylebox("panel", "PopupMenu", menu)
	t.set_stylebox("hover", "PopupMenu", picked)
	for item in ["font_color","font_hover_color","font_accelerator_color"]: t.set_color(item, "PopupMenu", PAPER_INK)
	t.set_color("font_disabled_color", "PopupMenu", Color(PAPER_INK,.45))
	t.set_constant("v_separation", "PopupMenu", 8)
	t.set_stylebox("panel", "TooltipPanel", frame("tooltip"))
	t.set_color("font_color", "TooltipLabel", INK)
	t.set_font_size("font_size", "TooltipLabel", 13)
	# Meters, sliders and scroll bars.
	t.set_stylebox("background", "ProgressBar", frame("bar_bg"))
	t.set_stylebox("fill", "ProgressBar", frame("bar_fill", Color("e9b552")))
	t.set_color("font_color", "ProgressBar", INK)
	var track := frame("bar_bg")
	track.set_content_margin_all(3)
	for type in ["HSlider","VSlider"]:
		t.set_stylebox("slider", type, track)
		t.set_stylebox("grabber_area", type, frame("bar_fill", Color("e9b552")))
		t.set_stylebox("grabber_area_highlight", type, frame("bar_fill", Color("f3c96a")))
		t.set_icon("grabber", type, half("slider_grabber"))
		t.set_icon("grabber_highlight", type, half("slider_grabber_hover"))
	for type in ["VScrollBar","HScrollBar"]:
		t.set_stylebox("scroll", type, frame("scroll_track"))
		t.set_stylebox("scroll_focus", type, frame("scroll_track"))
		t.set_stylebox("grabber", type, frame("scroll_grabber"))
		t.set_stylebox("grabber_highlight", type, frame("scroll_grabber_hover"))
		t.set_stylebox("grabber_pressed", type, frame("scroll_grabber_hover"))
	t.set_stylebox("panel", "ScrollContainer", StyleBoxEmpty.new())
	# Containers, tabs and dialogs.
	t.set_stylebox("panel", "PanelContainer", frame("panel_paper_plain"))
	t.set_stylebox("panel", "Panel", frame("panel_paper_plain"))
	t.set_stylebox("tab_selected", "TabBar", frame("btn_gold_normal"))
	t.set_stylebox("tab_hovered", "TabBar", frame("btn_paper_hover"))
	t.set_stylebox("tab_unselected", "TabBar", frame("btn_paper_normal"))
	t.set_stylebox("tab_selected", "TabContainer", frame("btn_gold_normal"))
	t.set_stylebox("tab_hovered", "TabContainer", frame("btn_paper_hover"))
	t.set_stylebox("tab_unselected", "TabContainer", frame("btn_paper_normal"))
	t.set_stylebox("panel", "TabContainer", frame("panel_paper_plain"))
	for item in ["font_selected_color","font_unselected_color","font_hovered_color"]:
		t.set_color(item, "TabBar", PAPER_INK)
		t.set_color(item, "TabContainer", PAPER_INK)
	var dialog := frame("panel_paper_plain")
	dialog.set_content_margin_all(18)
	t.set_stylebox("panel", "AcceptDialog", dialog)
	var border := frame("panel_paper")
	border.expand_margin_top += 30
	t.set_stylebox("embedded_border", "Window", border)
	t.set_stylebox("embedded_unfocused_border", "Window", border)
	t.set_font("title_font", "Window", FONT_DISPLAY)
	t.set_font_size("title_font_size", "Window", 20)
	t.set_color("title_color", "Window", PAPER_INK)
	t.set_constant("title_height", "Window", 30)
	# Label variations used across screens.
	t.set_type_variation("HudLabel", "Label")
	t.set_color("font_color", "HudLabel", INK)
	t.set_color("font_outline_color", "HudLabel", OUTLINE)
	t.set_constant("outline_size", "HudLabel", 4)
	t.set_type_variation("HeaderLabel", "Label")
	t.set_font("font", "HeaderLabel", FONT_DISPLAY)
	t.set_font_size("font_size", "HeaderLabel", 26)
	t.set_color("font_color", "HeaderLabel", PAPER_INK)
	t.set_type_variation("CaptionLabel", "Label")
	t.set_font_size("font_size", "CaptionLabel", 13)
	t.set_color("font_color", "CaptionLabel", PAPER_MUTED)
	_theme = t
	return t

# ------------------------------------------------------------------ sound

## Soft UI sounds on the "UI" bus (Master until that bus exists).
static func sfx(kind: String, volume_db := -4.0) -> void:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null or tree.root == null: return
	if kind == "hover":
		if Time.get_ticks_msec() - _last_hover < 45: return
		_last_hover = Time.get_ticks_msec()
	# One press can reach both a button hook and an older sound.effect("click").
	if Time.get_ticks_msec() - int(_last_played.get(kind, -1000)) < 60: return
	_last_played[kind] = Time.get_ticks_msec()
	if not _sounds.has(kind):
		var path := "res://assets/sfx/ui/%s.wav" % kind
		_sounds[kind] = load(path) if ResourceLoader.exists(path) else null
	if _sounds[kind] == null: return
	var host := tree.root.get_node_or_null("RpgUiSounds")
	var fresh := host == null
	if fresh:
		host = Node.new()
		host.name = "RpgUiSounds"
		host.process_mode = Node.PROCESS_MODE_ALWAYS
		for i in 4: host.add_child(AudioStreamPlayer.new())
		tree.root.add_child.call_deferred(host)
	var voice: AudioStreamPlayer = host.get_child(_voice % host.get_child_count())
	_voice += 1
	voice.bus = "UI" if AudioServer.get_bus_index("UI") != -1 else "Master"
	voice.stream = _sounds[kind]
	voice.volume_db = volume_db
	voice.pitch_scale = randf_range(0.97, 1.03)
	if fresh or not voice.is_inside_tree(): voice.play.call_deferred()
	else: voice.play()

# ------------------------------------------------------------------ motion

## Fade + gentle overshoot scale for windows and cards.
static func calm() -> bool:
	return GameSettings.reduced_motion()

static func pop_in(c: Control, duration := 0.24, from_scale := 0.94) -> void:
	if calm(): return
	c.modulate.a = 0.0
	c.scale = Vector2.ONE * from_scale
	var start := func() -> void:
		if not is_instance_valid(c) or not c.is_inside_tree(): return
		c.pivot_offset = c.size * 0.5
		var tw := c.create_tween().set_parallel(true)
		tw.tween_property(c, "scale", Vector2.ONE, duration).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		tw.tween_property(c, "modulate:a", 1.0, duration * 0.7).set_trans(Tween.TRANS_SINE)
	start.call_deferred()

## Slide from an offset while fading in (toasts, drawers).
static func slide_in(c: Control, offset: Vector2, duration := 0.28) -> void:
	if calm(): return
	var home := c.position
	c.position = home + offset
	c.modulate.a = 0.0
	var tw := c.create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.tween_property(c, "position", home, duration)
	tw.tween_property(c, "modulate:a", 1.0, duration * 0.8)

static func fade(c: CanvasItem, to := 0.0, duration := 0.18) -> Tween:
	var tw := c.create_tween()
	tw.tween_property(c, "modulate:a", to, duration).set_trans(Tween.TRANS_SINE)
	return tw

## Hover lift + brightness and the soft hover tick; click sound on press.
static func hover_motion(c: Control, lift := 1.05, pivot := Vector2(0.5, 0.5), sounds := true) -> void:
	var to := func(target: float, bright: float) -> void:
		if not is_instance_valid(c) or calm(): return
		c.pivot_offset = c.size * pivot
		var tw := c.create_tween().set_parallel(true).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		tw.tween_property(c, "scale", Vector2.ONE * target, 0.16)
		tw.tween_property(c, "self_modulate", Color(bright, bright, bright), 0.12)
	c.mouse_entered.connect(func():
		if c is BaseButton and (c as BaseButton).disabled: return
		to.call(lift, 1.08)
		if sounds: sfx("hover"))
	c.mouse_exited.connect(func(): to.call(1.0, 1.0))
	if sounds and c is BaseButton: (c as BaseButton).button_down.connect(func(): sfx("click"))

## Counts a number label up (or down) to value with a small pulse.
static func count_to(l: Label, value: int, duration := -1.0) -> void:
	if not is_instance_valid(l): return
	var target_now: int = l.get_meta("count_target", -2147483648)
	if target_now == value: return
	l.set_meta("count_target", value)
	var from := int(l.text) if l.text.is_valid_int() else value
	if from == value or not l.is_inside_tree():
		l.text = str(value)
		return
	if l.has_meta("count_tween"):
		var old: Tween = l.get_meta("count_tween")
		if old and old.is_valid(): old.kill()
	var seconds := duration if duration > 0.0 else clampf(absf(value - from) * 0.02, 0.3, 0.9)
	var tw := l.create_tween()
	tw.tween_method(func(v: float): l.text = str(int(round(v))), float(from), float(value), seconds).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	l.set_meta("count_tween", tw)
	l.pivot_offset = l.size * 0.5
	var pulse := l.create_tween()
	pulse.tween_property(l, "scale", Vector2.ONE * 1.18, 0.12).set_trans(Tween.TRANS_SINE)
	pulse.tween_property(l, "scale", Vector2.ONE, 0.3).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)

# ------------------------------------------------------------------ text

static func label(parent: Node, value: String, size := 15, color := INK, outline := true) -> Label:
	var l := Label.new()
	l.text = value
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	if size >= 22: l.add_theme_font_override("font", FONT_DISPLAY)
	elif outline: l.add_theme_font_override("font", FONT_STRONG)
	if outline:
		l.add_theme_color_override("font_outline_color", OUTLINE)
		l.add_theme_constant_override("outline_size", 5 if size >= 22 else 4)
		l.add_theme_color_override("font_shadow_color", Color(0,0,0,.28))
		l.add_theme_constant_override("shadow_offset_y", 2)
		l.add_theme_constant_override("shadow_offset_x", 0)
	parent.add_child(l)
	return l

## Display-font header (Jua) for cards and windows.
static func heading(parent: Node, value: String, size := 26, color := PAPER_INK) -> Label:
	var l := Label.new()
	l.text = value
	l.add_theme_font_override("font", FONT_DISPLAY)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	parent.add_child(l)
	return l

## Small muted caption on parchment.
static func caption(parent: Node, value: String, size := 13, color := PAPER_MUTED) -> Label:
	var l := Label.new()
	l.text = value
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	if not parent is HBoxContainer: l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	parent.add_child(l)
	return l

## Tabular bold numbers with an outline (wallet, timers, meters).
static func numbers(l: Label, size := 16) -> Label:
	l.add_theme_font_override("font", FONT_NUMBERS)
	l.add_theme_font_size_override("font_size", size)
	return l

## A ribbon banner carrying a title (modal headers, results).
static func ribbon(parent: Node, value: String, teal := false, size := 22) -> PanelContainer:
	var band := PanelContainer.new()
	band.add_theme_stylebox_override("panel", frame("ribbon_teal" if teal else "ribbon"))
	band.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var l := Label.new()
	l.text = value
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.add_theme_font_override("font", FONT_DISPLAY)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", INK)
	l.add_theme_color_override("font_outline_color", Color("4a1f10") if not teal else Color("102826"))
	l.add_theme_constant_override("outline_size", 4)
	band.add_child(l)
	parent.add_child(band)
	return band

## Thin ornamented rule with a centred diamond.
static func divider(parent: Node, color := Color("c9a46a"), width := 0.0) -> Control:
	var line := Control.new()
	line.custom_minimum_size = Vector2(width, 12)
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	line.draw.connect(func():
		var w := line.size.x
		var y := line.size.y * 0.5
		var c := w * 0.5
		line.draw_line(Vector2(4, y), Vector2(c - 13, y), Color(color, .7), 1.5, true)
		line.draw_line(Vector2(c + 13, y), Vector2(w - 4, y), Color(color, .7), 1.5, true)
		line.draw_colored_polygon(PackedVector2Array([Vector2(c, y - 5), Vector2(c + 5, y), Vector2(c, y + 5), Vector2(c - 5, y)]), color)
		line.draw_circle(Vector2(c - 10, y), 1.7, color)
		line.draw_circle(Vector2(c + 10, y), 1.7, color))
	line.resized.connect(line.queue_redraw)
	parent.add_child(line)
	return line

## A little keyboard key cap ("E", "Tab", "Esc").
static func keycap(parent: Node, key: String, size := 12) -> Label:
	var cap := Label.new()
	cap.text = key
	cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cap.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	cap.custom_minimum_size = Vector2(22, 22)
	cap.add_theme_font_override("font", FONT_BOLD)
	cap.add_theme_font_size_override("font_size", size)
	cap.add_theme_color_override("font_color", Color("3a2614"))
	cap.add_theme_stylebox_override("normal", frame("keycap"))
	cap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(cap)
	return cap

static func icon(path: String, size: float) -> TextureRect:
	var image := TextureRect.new()
	image.texture = load(path)
	image.custom_minimum_size = Vector2(size,size)
	image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	image.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	image.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return image

## Icon + label + bar for HP/hunger/stamina style meters on night glass.
static func meter(parent: Node, title: String, color: Color, icon_name := "") -> Dictionary:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	parent.add_child(row)
	if not icon_name.is_empty() and icon_texture(icon_name):
		var art := icon(icon_texture(icon_name).resource_path, 24)
		row.add_child(art)
	var column := VBoxContainer.new()
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.add_theme_constant_override("separation", 2)
	row.add_child(column)
	var header := HBoxContainer.new()
	column.add_child(header)
	var name_label := label(header, title, 12, SOFT)
	name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var value_label := numbers(label(header, "100 / 100", 12, INK), 12)
	var bar := ProgressBar.new()
	bar.custom_minimum_size.y = 12
	bar.show_percentage = false
	bar.add_theme_stylebox_override("background", frame("bar_bg"))
	bar.add_theme_stylebox_override("fill", frame("bar_fill", color))
	column.add_child(bar)
	return {"bar":bar, "readout":value_label, "name":name_label}

# ------------------------------------------------------------------ HUD pieces

## Portrait medallion, name and the two currencies. Returns the labels to update.
static func player_frame(ui: Control, portrait: String) -> Dictionary:
	var shell := PanelContainer.new()
	shell.position = Vector2(14,12)
	var plate := panel_style("pill")
	plate.content_margin_left = 10
	plate.content_margin_right = 22
	plate.content_margin_top = 8
	plate.content_margin_bottom = 8
	shell.add_theme_stylebox_override("panel", plate)
	ui.add_child(shell)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	shell.add_child(row)
	var holder := Control.new()
	holder.custom_minimum_size = Vector2(72,72)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(holder)
	var medal := PanelContainer.new()
	var disc := StyleBoxFlat.new()
	disc.bg_color = Color("f5e6c4")
	disc.set_corner_radius_all(40)
	disc.corner_detail = 16
	medal.add_theme_stylebox_override("panel", disc)
	medal.clip_children = CanvasItem.CLIP_CHILDREN_AND_DRAW
	medal.position = Vector2(6,6)
	medal.size = Vector2(60,60)
	medal.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(medal)
	var face := icon(portrait, 60)
	medal.add_child(face)
	var ring := TextureRect.new()
	ring.texture = half("portrait_ring")
	ring.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	ring.stretch_mode = TextureRect.STRETCH_SCALE
	ring.position = Vector2(-3,-3)
	ring.size = Vector2(78,78)
	ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(ring)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 2)
	column.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_child(column)
	var name := label(column, "", 20)
	name.add_theme_font_override("font", FONT_DISPLAY)
	var coins := HBoxContainer.new()
	coins.add_theme_constant_override("separation", 5)
	column.add_child(coins)
	coins.add_child(icon("res://assets/starseed.svg", 24))
	var stars := numbers(label(coins, "0", 17, Color("ffe08a")), 17)
	stars.custom_minimum_size.x = 34
	stars.tooltip_text = TranslationServer.translate("별씨")
	var gap := Control.new(); gap.custom_minimum_size.x = 6; coins.add_child(gap)
	coins.add_child(icon("res://assets/ui/leaf.svg", 22))
	var leaves := numbers(label(coins, "0", 17, Color("c8ec9f")), 17)
	leaves.custom_minimum_size.x = 34
	var status := label(column, "", 12, SOFT)
	status.visible = false
	return {"panel":shell, "name":name, "stars":stars, "leaves":leaves, "status":status, "column":column, "portrait":face}

## Square slots with an icon, a key cap and a caption on a glass tray.
static func hotbar(ui: Control, slots: Array, y: float) -> HBoxContainer:
	const SLOT := 70.0
	const GAP := 10.0
	var tray := PanelContainer.new()
	var tray_style := panel_style("pill")
	tray_style.set_content_margin_all(0)
	tray.add_theme_stylebox_override("panel", tray_style)
	var width := slots.size() * (SLOT + GAP) - GAP + 36.0
	tray.position = Vector2(640.0 - width * 0.5, y + 6)
	tray.size = Vector2(width, SLOT + 8)
	tray.custom_minimum_size = tray.size
	tray.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tray.modulate = Color(1,1,1,.92)
	ui.add_child(tray)
	pin(tray, 0.5, 1.0)
	var bar := HBoxContainer.new()
	bar.add_theme_constant_override("separation", int(GAP))
	bar.alignment = BoxContainer.ALIGNMENT_CENTER
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(bar)
	# Bottom-wide strip: the slots stay centred at the screen's foot at any UI scale.
	bar.anchor_left = 0.0; bar.anchor_right = 1.0; bar.anchor_top = 1.0; bar.anchor_bottom = 1.0
	bar.offset_left = 0; bar.offset_right = 0; bar.offset_top = y - CANVAS.y; bar.offset_bottom = y - CANVAS.y + 96
	# The tray follows the bar's visibility (conversations hide the HUD).
	bar.visibility_changed.connect(func(): if is_instance_valid(tray): tray.visible = bar.visible)
	for slot in slots:
		var b := Button.new()
		b.custom_minimum_size = Vector2(SLOT, SLOT)
		b.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
		b.focus_mode = Control.FOCUS_NONE
		b.tooltip_text = slot.label
		b.theme_type_variation = "HudSlot"
		if slot.get("primary", false):
			b.add_theme_stylebox_override("normal", frame("slot_night_primary"))
		var stack := VBoxContainer.new()
		stack.alignment = BoxContainer.ALIGNMENT_CENTER
		stack.mouse_filter = Control.MOUSE_FILTER_IGNORE
		stack.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		stack.add_theme_constant_override("separation", -1)
		b.add_child(stack)
		var art := icon(slot.icon, 36)
		art.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		stack.add_child(art)
		var caption_label := label(stack, slot.label, 12)
		caption_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		caption_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		if not String(slot.get("key","")).is_empty():
			var cap := keycap(b, slot.key, 11)
			cap.position = Vector2(-7,-9)
		b.pressed.connect(slot.call)
		hover_motion(b, 1.08, Vector2(0.5, 1.0))
		bar.add_child(b)
	return bar

## Floating interaction chip above the hotbar; hidden while empty. The leading
## "E  " of the text is drawn as a key cap.
static func prompt(ui: Control, y: float) -> Label:
	var pill := Label.new()
	pill.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	pill.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	pill.add_theme_font_override("font", FONT_STRONG)
	pill.add_theme_font_size_override("font_size", 16)
	pill.add_theme_color_override("font_color", INK)
	var chip := panel_style("pill")
	chip.content_margin_left = 22
	chip.content_margin_right = 22
	pill.add_theme_stylebox_override("normal", chip)
	pill.position = Vector2(440, y)
	pill.size = Vector2(400, 42)
	pill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pill.visible = false
	pill.set_meta("prompt", "")
	var cap := keycap(pill, "E", 13)
	cap.name = "Key"
	cap.position = Vector2(14, 9)
	cap.visible = false
	# Gentle breathing so the chip reads as "you can act here".
	pill.visibility_changed.connect(func():
		if pill.visible and pill.is_inside_tree():
			pill.modulate.a = 0.0
			pill.create_tween().tween_property(pill, "modulate:a", 1.0, 0.15))
	ui.add_child(pill)
	pin(pill, 0.5, 1.0)
	return pill

## Sets a prompt chip's text. A leading key label ("E", "F", "Space", "LMB"…)
## followed by two spaces is drawn as a key cap instead of text.
static func set_prompt(chip: Label, value: String) -> void:
	var cap: Label = chip.get_node_or_null("Key")
	var key := ""
	var rest := value
	var split := value.find("  ")
	if split > 0 and split <= 12 and not value.substr(0, split).contains(" "):
		key = value.substr(0, split)
		rest = value.substr(split + 2).strip_edges()
	chip.set_meta("prompt", value)
	chip.text = rest
	var box := chip.get_theme_stylebox("normal") as StyleBoxTexture
	if cap:
		cap.visible = not key.is_empty()
		cap.text = key
		cap.size = Vector2.ZERO
		var cap_width: float = maxf(cap.get_combined_minimum_size().x, 22.0)
		if box: box.content_margin_left = 22.0 + (cap_width + 10.0 if cap.visible else 0.0)
		cap.position = Vector2(16, (chip.size.y - 24.0) * 0.5)

## Pins a control laid out on the 1280x800 design canvas to an edge or centre
## (h/v: 0 = left/top, 0.5 = centre, 1 = right/bottom) so it stays put at any UI scale.
static func pin(c: Control, h := 0.0, v := 0.0, design_at := Vector2(-1, -1)) -> Control:
	var at := c.position if design_at.x < 0.0 else design_at
	var size := c.size
	if size == Vector2.ZERO: size = c.get_combined_minimum_size()
	c.anchor_left = h
	c.anchor_right = h
	c.anchor_top = v
	c.anchor_bottom = v
	c.offset_left = at.x - h * CANVAS.x
	c.offset_right = c.offset_left + size.x
	c.offset_top = at.y - v * CANVAS.y
	c.offset_bottom = c.offset_top + size.y
	c.grow_horizontal = Control.GROW_DIRECTION_BEGIN if h >= 1.0 else (Control.GROW_DIRECTION_BOTH if h > 0.0 else Control.GROW_DIRECTION_END)
	c.grow_vertical = Control.GROW_DIRECTION_BEGIN if v >= 1.0 else (Control.GROW_DIRECTION_BOTH if v > 0.0 else Control.GROW_DIRECTION_END)
	# Offset setters skip unchanged values, which can leave the cached rect from an
	# intermediate anchor step; nudge once so the final layout is recomputed.
	var top := c.offset_top
	c.offset_top = top + 1.0
	c.offset_top = top
	return c

## Overrides for controls on night glass: cream text with an outline, night keys.
static func night_theme() -> Theme:
	if _night_theme: return _night_theme
	var t := Theme.new()
	t.set_color("font_color","Label",INK)
	t.set_color("font_outline_color","Label",Color(OUTLINE,.8))
	t.set_constant("outline_size","Label",3)
	for state in ["normal","hover","pressed","disabled"]: t.set_stylebox(state,"Button",frame("btn_night_"+state))
	t.set_stylebox("hover_pressed","Button",frame("btn_night_pressed"))
	for item in ["font_color","font_pressed_color","font_hover_pressed_color","font_focus_color"]: t.set_color(item,"Button",INK)
	t.set_color("font_hover_color","Button",Color("ffe08a"))
	t.set_color("font_disabled_color","Button",Color(INK,.45))
	for spec in [["GoldButton","btn_gold",PAPER_INK,false],["PrimaryButton","btn_green",INK,true],["NightButton","btn_night",INK,true]]:
		t.set_type_variation(spec[0],"Button")
		_buttons(t,spec[0],spec[1],spec[2],spec[3])
	t.set_color("font_hover_color","NightButton",Color("ffe08a"))
	t.set_type_variation("HudSlot","Button")
	for state in ["normal","hover","pressed","hover_pressed","disabled"]:
		t.set_stylebox(state,"HudSlot",frame({"normal":"slot_night","hover":"slot_night_hover","pressed":"slot_night_pressed","hover_pressed":"slot_night_pressed","disabled":"slot_night"}[state]))
	t.set_stylebox("focus","HudSlot",StyleBoxEmpty.new())
	t.set_type_variation("SlotButton","Button")
	t.set_stylebox("normal","SlotButton",frame("slot_night"))
	t.set_stylebox("disabled","SlotButton",frame("slot_night",Color(1,1,1,.6)))
	for state in ["hover","pressed","hover_pressed"]: t.set_stylebox(state,"SlotButton",frame("slot_night_hover"))
	for type in ["CheckBox","CheckButton"]:
		for item in ["font_color","font_hover_color","font_pressed_color","font_hover_pressed_color","font_focus_color"]: t.set_color(item,type,INK)
	for type in ["LineEdit","TextEdit"]:
		t.set_stylebox("normal",type,frame("field_night"))
		t.set_stylebox("focus",type,frame("field_night_focus"))
		t.set_color("font_color",type,INK)
		t.set_color("caret_color",type,GOLD)
		t.set_color("font_placeholder_color",type,Color(1,1,1,.42))
	_night_theme=t
	return t

# ------------------------------------------------------------------ dialogue

## The RPG / visual-novel dialogue window shared by the village and the rooms.
## An illustrated portrait card in an ornate frame stands over the left of a wide
## night-glass box; the speaker's ribbon is tied to the card's foot. Returns
## {root, shade, box, body, more, choices, card, plate}. `parent` gets the window as
## a full-rect child; free `root` (or its parent) to close it.
static func dialogue(parent: Control, speaker: String, portrait := "") -> Dictionary:
	var root := Control.new()
	root.name = "Dialogue"
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(root)
	var shade := TextureRect.new()
	var fade := GradientTexture2D.new()
	fade.fill_from = Vector2(0, 0); fade.fill_to = Vector2(0, 1)
	fade.gradient = Gradient.new()
	fade.gradient.colors = PackedColorArray([Color(0.02,0.03,0.04,0.0), Color(0.02,0.03,0.04,0.2), Color(0.02,0.03,0.04,0.7)])
	fade.gradient.offsets = PackedFloat32Array([0.0, 0.45, 1.0])
	shade.texture = fade
	shade.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(shade)
	var has_card := not portrait.is_empty() and ResourceLoader.exists(portrait)
	# The text box: bottom, full width inside safe margins.
	var box := PanelContainer.new()
	box.name = "Box"
	var style := panel_style("night")
	style.content_margin_left = 52
	style.content_margin_right = 52
	style.content_margin_top = 46
	style.content_margin_bottom = 26
	box.add_theme_stylebox_override("panel", style)
	box.theme = night_theme()
	box.anchor_left = 0.0; box.anchor_right = 1.0; box.anchor_top = 1.0; box.anchor_bottom = 1.0
	box.offset_left = 64; box.offset_right = -64; box.offset_top = -224; box.offset_bottom = -26
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(box)
	var body := Label.new()
	body.name = "Body"
	body.add_theme_font_override("font", FONT_BODY)
	body.add_theme_font_size_override("font_size", 23)
	body.add_theme_constant_override("line_spacing", 9)
	body.add_theme_color_override("font_color", INK)
	body.add_theme_constant_override("outline_size", 0)
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.vertical_alignment = VERTICAL_ALIGNMENT_TOP
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(body)
	# Portrait card standing on the box's top-left.
	var card: Control = null
	if has_card:
		card = Control.new()
		card.name = "Card"
		card.anchor_left = 0.0; card.anchor_right = 0.0; card.anchor_top = 1.0; card.anchor_bottom = 1.0
		card.offset_left = 92; card.offset_right = 92 + 270; card.offset_top = -224 - 300; card.offset_bottom = -224 + 24
		card.mouse_filter = Control.MOUSE_FILTER_IGNORE
		root.add_child(card)
		var art := TextureRect.new()
		art.texture = load(portrait)
		art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		art.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		art.offset_left = 8; art.offset_top = 8; art.offset_right = -8; art.offset_bottom = -8
		art.mouse_filter = Control.MOUSE_FILTER_IGNORE
		card.add_child(art)
		var rim := Panel.new()
		rim.add_theme_stylebox_override("panel", frame("card_frame"))
		rim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		rim.mouse_filter = Control.MOUSE_FILTER_IGNORE
		card.add_child(rim)
		box.get_theme_stylebox("panel").content_margin_top = 52
	# Speaker ribbon: tied under the card, or on the box's top-left edge.
	var plate := ribbon(root, speaker, true, 21)
	plate.name = "Plate"
	plate.anchor_left = 0.0; plate.anchor_right = 0.0; plate.anchor_top = 1.0; plate.anchor_bottom = 1.0
	var plate_width: float = maxf(plate.get_combined_minimum_size().x, 210.0 if has_card else 0.0)
	var plate_x := 92.0 + 135.0 - plate_width * 0.5 if has_card else 92.0
	plate.offset_left = plate_x; plate.offset_right = plate_x + plate_width
	plate.offset_top = -224 - 22; plate.offset_bottom = -224 + 20
	# Advance indicator: a gold chevron bobbing at the box's bottom-right.
	var more := Label.new()
	more.name = "More"
	more.text = "▼"
	more.add_theme_font_size_override("font_size", 16)
	more.add_theme_color_override("font_color", GOLD)
	more.add_theme_color_override("font_outline_color", OUTLINE)
	more.add_theme_constant_override("outline_size", 4)
	more.anchor_left = 1.0; more.anchor_right = 1.0; more.anchor_top = 1.0; more.anchor_bottom = 1.0
	more.offset_left = -116; more.offset_right = -96; more.offset_top = -66; more.offset_bottom = -44
	more.mouse_filter = Control.MOUSE_FILTER_IGNORE
	more.visible = false
	root.add_child(more)
	if not calm():
		var bob := more.create_tween().set_loops()
		bob.tween_property(more, "offset_top", -60.0, 0.45).set_trans(Tween.TRANS_SINE)
		bob.tween_property(more, "offset_top", -66.0, 0.45).set_trans(Tween.TRANS_SINE)
	# Choices: a vertical list above the box's right side.
	var choices := VBoxContainer.new()
	choices.name = "Choices"
	choices.add_theme_constant_override("separation", 8)
	choices.alignment = BoxContainer.ALIGNMENT_END
	choices.anchor_left = 1.0; choices.anchor_right = 1.0; choices.anchor_top = 1.0; choices.anchor_bottom = 1.0
	choices.offset_left = -64 - 360; choices.offset_right = -84; choices.offset_top = -224 - 260; choices.offset_bottom = -224 - 16
	choices.grow_vertical = Control.GROW_DIRECTION_BEGIN
	choices.theme = night_theme()
	root.add_child(choices)
	# Entrance: card slides in from the left, box rises, ribbon pops.
	if not calm():
		if card:
			card.modulate.a = 0.0
			var tw := card.create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
			tw.tween_property(card, "offset_left", card.offset_left, 0.34).from(card.offset_left - 46)
			tw.tween_property(card, "offset_right", card.offset_right, 0.34).from(card.offset_right - 46)
			tw.tween_property(card, "modulate:a", 1.0, 0.26)
		box.modulate.a = 0.0
		var rise := box.create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		rise.tween_property(box, "offset_top", box.offset_top, 0.28).from(box.offset_top + 28)
		rise.tween_property(box, "offset_bottom", box.offset_bottom, 0.28).from(box.offset_bottom + 28)
		rise.tween_property(box, "modulate:a", 1.0, 0.22)
		plate.modulate.a = 0.0
		plate.create_tween().tween_property(plate, "modulate:a", 1.0, 0.2).set_delay(0.12)
	sfx("open", -10.0)
	return {"root":root, "shade":shade, "box":box, "body":body, "more":more, "choices":choices, "card":card, "plate":plate}

## Fills the dialogue's choice list: entries are [text, Callable]. Keyboard / pad
## focus starts on the first; number keys 1-9 pick directly. Returns the buttons.
static func dialogue_choices(d: Dictionary, entries: Array) -> Array:
	var list: VBoxContainer = d.choices
	for child in list.get_children(): child.queue_free()
	var made := []
	var index := 0
	for entry in entries:
		index += 1
		var action: Callable = entry[1]
		var b := Button.new()
		b.text = str(entry[0])
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.custom_minimum_size = Vector2(0, 46)
		b.focus_mode = Control.FOCUS_ALL
		b.theme_type_variation = "NightButton"
		b.add_theme_font_override("font", FONT_STRONG)
		b.add_theme_font_size_override("font_size", 17)
		b.add_theme_color_override("font_hover_color", Color("ffe08a"))
		b.add_theme_color_override("font_focus_color", Color("ffe08a"))
		for state in ["normal","hover","pressed","disabled"]:
			var box := frame("btn_night_" + state)
			box.content_margin_left = 50
			b.add_theme_stylebox_override(state, box)
		b.add_theme_stylebox_override("hover_pressed", frame("btn_night_pressed"))
		b.add_theme_stylebox_override("focus", frame("focus"))
		for item in ["font_color","font_pressed_color","font_hover_pressed_color"]: b.add_theme_color_override(item, INK)
		var cap := keycap(b, str(index), 12)
		cap.position = Vector2(14, 12)
		b.pressed.connect(func(): if action.is_valid(): action.call())
		b.gui_input.connect(func(event):
			if event is InputEventKey and event.pressed and not event.echo and event.keycode >= KEY_1 and event.keycode <= KEY_9:
				var pick: int = event.keycode - KEY_1
				if pick < made.size():
					b.accept_event()
					(made[pick] as Button).pressed.emit())
		b.focus_entered.connect(func(): sfx("hover"))
		hover_motion(b, 1.03)
		list.add_child(b)
		made.append(b)
		if not calm():
			b.modulate.a = 0.0
			b.create_tween().tween_property(b, "modulate:a", 1.0, 0.18).set_delay(0.05 * index)
	if not made.is_empty(): (made[0] as Button).grab_focus.call_deferred()
	d.more.visible = false
	return made

## Shows or hides the "more" chevron (pages left to read).
static func dialogue_more(d: Dictionary, waiting: bool) -> void:
	if is_instance_valid(d.more): d.more.visible = waiting
	if waiting and is_instance_valid(d.choices):
		for child in d.choices.get_children(): child.queue_free()

## Large title-menu button: night glass with a gold edge that warms on hover.
static func menu_button(parent: Node, value: String, callback: Callable, width := 300.0) -> Button:
	var b := Button.new()
	b.text = value
	b.custom_minimum_size = Vector2(width, 52)
	b.focus_mode = Control.FOCUS_NONE
	b.theme_type_variation = "NightButton"
	b.add_theme_font_override("font", FONT_STRONG)
	b.add_theme_font_size_override("font_size", 19)
	b.add_theme_color_override("font_hover_color", Color("ffe08a"))
	b.add_theme_color_override("font_focus_color", Color("ffe08a"))
	b.pressed.connect(callback)
	hover_motion(b, 1.03)
	parent.add_child(b)
	return b

## Text field matching the night title card.
static func field(parent: Node, placeholder: String, secret := false) -> LineEdit:
	var line := LineEdit.new()
	line.placeholder_text = placeholder
	line.secret = secret
	line.custom_minimum_size = Vector2(340, 44)
	line.theme_type_variation = "NightField"
	line.add_theme_font_size_override("font_size", 16)
	parent.add_child(line)
	return line
