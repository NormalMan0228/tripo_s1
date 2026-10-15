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
## Design tokens (docs/design/UI_UNIFICATION.md 1.1). Every other script takes its colours,
## type sizes and spacing from here; tests/ui_consistency_check.gd lints literal colours.
## Hover / focus text on night glass and the star-seed count.
const HOVER := Color("ffe08a")
## Party, whisper and the teal ribbon.
const TEAL := Color("70afa3")
## Ornamented dividers on parchment.
const PAPER_LINE := Color("c9a46a")
## Presence dots.
const ONLINE := Color("8fd16a")
const AWAY := Color("e9b552")
## The amber of meter fills, slider tracks and map markers (the same hue as AWAY).
const AMBER := Color("e9b552")
const OFFLINE := Color(1,1,1,.35)
## Chat channels other than the village (INK) and the party (TEAL).
const CHAT_GLOBAL := Color("c9b8ff")
const CHAT_WHISPER := Color("f0a8c8")
## The window shade: a radial fall from SHADE_IN at the centre to SHADE_OUT at the corners.
const SHADE_IN := Color(0.03,0.05,0.06,.55)
const SHADE_OUT := Color(0.02,0.03,0.04,.86)
## Dialogue choices take E/Space/Enter only this long after they appear (reading on never picks).
const CHOICE_KEY_DELAY_MS := 300
## Leaf-coin count and warm alert text on night glass.
const LEAF_LIGHT := Color("c8ec9f")
const WARM := Color("ffd9a0")
## Type scale (sizes; fonts and colours per role in TYPE and text_style()). Paper titles are
## PAPER_INK without an outline; night titles GOLD with one.
const T_WINDOW := 26
const T_SECTION := 17
const T_BODY := 15
const T_CAPTION := 13
const T_SMALL := 12
## Sizes on the 1280x800 design canvas.
const BTN_SM := 32
const BTN_MD := 40
const BTN_LG := 44
const BTN_MENU := 52
const SLOT := 70
const KEY := 22
const CLOSE := 34
const PAD := 16
const GAP_S := 8
const GAP := 10
const GAP_L := 12
const WINDOW_TOP := 92
const WINDOW_W := {"small":560, "standard":760, "wide":1040}
const DRAWER_W := 308

const GameSettings = preload("res://scripts/game_settings.gd")
const FONT_BODY: Font = preload("res://assets/fonts/ui_body.tres")
const FONT_STRONG: Font = preload("res://assets/fonts/ui_strong.tres")
const FONT_BOLD: Font = preload("res://assets/fonts/ui_bold.tres")
const FONT_DISPLAY: Font = preload("res://assets/fonts/ui_display.tres")
## Tabular figures so counters and timers do not jitter while they change.
const FONT_NUMBERS: Font = preload("res://assets/fonts/ui_numbers.tres")

## name: [texture margins, expand margins, content margins] at 2x (from frames.json).
const FRAMES := {
	"panel_paper":[[76, 48, 70, 72],[12, 8, 12, 16],[52, 24, 46, 40]],
	"panel_night":[[73, 76, 72, 65],[12, 8, 12, 16],[47, 50, 46, 31]],
	"panel_night_plain":[[73, 76, 72, 65],[12, 8, 12, 16],[47, 50, 46, 31]],
	"panel_paper_plain":[[76, 48, 70, 72],[12, 8, 12, 16],[52, 24, 46, 40]],
	"pill_night":[[60, 35, 60, 40],[8, 5, 8, 10],[26, 9, 26, 9]],
	"pill_paper":[[42, 35, 42, 40],[8, 5, 8, 10],[22, 9, 22, 9]],
	"tooltip":[[46, 26, 46, 30],[6, 4, 6, 8],[22, 9, 22, 9]],
	"btn_paper_normal":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 9, 18, 13]],
	"btn_paper_hover":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 9, 18, 13]],
	"btn_paper_pressed":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 12, 18, 10]],
	"btn_paper_disabled":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 9, 18, 13]],
	"btn_green_normal":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 9, 18, 13]],
	"btn_green_hover":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 9, 18, 13]],
	"btn_green_pressed":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 12, 18, 10]],
	"btn_green_disabled":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 9, 18, 13]],
	"btn_gold_normal":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 9, 18, 13]],
	"btn_gold_hover":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 9, 18, 13]],
	"btn_gold_pressed":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 12, 18, 10]],
	"btn_gold_disabled":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 9, 18, 13]],
	"btn_night_normal":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 9, 18, 13]],
	"btn_night_hover":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 9, 18, 13]],
	"btn_night_pressed":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 12, 18, 10]],
	"btn_night_disabled":[[36, 28, 36, 35],[6, 4, 6, 9],[18, 9, 18, 13]],
	"focus":[[28, 28, 28, 28],[6, 6, 6, 6],[]],
	"slot_night":[[34, 33, 34, 37],[4, 3, 4, 7],[10, 10, 10, 10]],
	"slot_night_hover":[[34, 33, 34, 37],[4, 3, 4, 7],[10, 10, 10, 10]],
	"slot_night_pressed":[[34, 33, 34, 37],[4, 3, 4, 7],[10, 10, 10, 10]],
	"slot_night_primary":[[34, 33, 34, 37],[4, 3, 4, 7],[10, 10, 10, 10]],
	"slot_paper":[[34, 33, 34, 37],[4, 3, 4, 7],[10, 10, 10, 10]],
	"slot_paper_hover":[[34, 33, 34, 37],[4, 3, 4, 7],[10, 10, 10, 10]],
	"slot_paper_empty":[[34, 33, 34, 37],[4, 3, 4, 7],[10, 10, 10, 10]],
	"field_paper":[[22, 22, 22, 22],[0, 0, 0, 0],[14, 9, 14, 9]],
	"field_paper_focus":[[22, 22, 22, 22],[0, 0, 0, 0],[14, 9, 14, 9]],
	"field_night":[[22, 22, 22, 22],[0, 0, 0, 0],[14, 9, 14, 9]],
	"field_night_focus":[[22, 22, 22, 22],[0, 0, 0, 0],[14, 9, 14, 9]],
	"bar_bg":[[16, 12, 16, 12],[0, 0, 0, 0],[]],
	"bar_fill":[[16, 12, 16, 12],[0, 0, 0, 0],[]],
	"ribbon":[[83, 26, 83, 30],[6, 4, 6, 8],[71, 8, 71, 12]],
	"ribbon_teal":[[83, 26, 83, 30],[6, 4, 6, 8],[71, 8, 71, 12]],
	"keycap":[[14, 14, 14, 16],[0, 0, 0, 0],[6, 1, 6, 3]],
	"portrait_ring":[[0, 0, 0, 0],[0, 0, 0, 0],[]],
	"check_off":[[0, 0, 0, 0],[0, 0, 0, 0],[]],
	"check_on":[[0, 0, 0, 0],[0, 0, 0, 0],[]],
	"radio_off":[[0, 0, 0, 0],[0, 0, 0, 0],[]],
	"radio_on":[[0, 0, 0, 0],[0, 0, 0, 0],[]],
	"slider_grabber":[[0, 0, 0, 0],[0, 0, 0, 0],[]],
	"slider_grabber_hover":[[0, 0, 0, 0],[0, 0, 0, 0],[]],
	"arrow_down":[[0, 0, 0, 0],[0, 0, 0, 0],[]],
	"arrow_down_light":[[0, 0, 0, 0],[0, 0, 0, 0],[]],
	"scroll_grabber":[[10, 10, 10, 10],[0, 0, 0, 0],[]],
	"scroll_grabber_hover":[[10, 10, 10, 10],[0, 0, 0, 0],[]],
	"scroll_track":[[10, 10, 10, 10],[0, 0, 0, 0],[]],
	"card_frame":[[42, 38, 42, 50],[12, 8, 12, 20],[]],
	"dialogue_box":[[78, 67, 77, 77],[12, 8, 12, 16],[56, 49, 55, 51]],
	"bar_fill_red":[[16, 12, 16, 12],[0, 0, 0, 0],[]],
	"bar_fill_green":[[16, 12, 16, 12],[0, 0, 0, 0],[]],
	"bar_fill_gold":[[16, 12, 16, 12],[0, 0, 0, 0],[]],
	# UI kit 2 (tools/build_ui_kit2.py, frames_v2.json): title plate, banners, folder tabs, big menu buttons.
	"title_plate_crest":[[0, 0, 0, 0],[0, 0, 0, 0],[]],
	"title_plate":[[72, 26, 72, 32],[10, 6, 10, 12],[68, 14, 68, 14]],
	"banner_red":[[101, 36, 101, 42],[10, 6, 10, 12],[73, 22, 73, 30]],
	"banner_teal":[[101, 36, 101, 42],[10, 6, 10, 12],[73, 22, 73, 30]],
	"tab_on":[[38, 28, 38, 18],[6, 4, 6, 6],[22, 12, 22, 10]],
	"tab_off":[[38, 28, 38, 18],[6, 4, 6, 6],[22, 12, 22, 10]],
	"tab_disabled":[[38, 28, 38, 18],[6, 4, 6, 6],[22, 12, 22, 10]],
	"btn_menu_gold_normal":[[62, 36, 62, 42],[10, 6, 10, 12],[30, 18, 30, 22]],
	"btn_menu_gold_hover":[[62, 36, 62, 42],[10, 6, 10, 12],[30, 18, 30, 22]],
	"btn_menu_gold_pressed":[[62, 36, 62, 42],[10, 6, 10, 12],[30, 18, 30, 22]],
	"btn_menu_gold_disabled":[[62, 36, 62, 42],[10, 6, 10, 12],[30, 18, 30, 22]],
	"btn_menu_night_normal":[[62, 36, 62, 42],[10, 6, 10, 12],[30, 18, 30, 22]],
	"btn_menu_night_hover":[[62, 36, 62, 42],[10, 6, 10, 12],[30, 18, 30, 22]],
	"btn_menu_night_pressed":[[62, 36, 62, 42],[10, 6, 10, 12],[30, 18, 30, 22]],
	"btn_menu_night_disabled":[[62, 36, 62, 42],[10, 6, 10, 12],[30, 18, 30, 22]],
	"divider_leaf":[[0, 0, 0, 0],[0, 0, 0, 0],[]],
	"corner_tl":[[0, 0, 0, 0],[0, 0, 0, 0],[]],
	"corner_tr":[[0, 0, 0, 0],[0, 0, 0, 0],[]],
	"corner_bl":[[0, 0, 0, 0],[0, 0, 0, 0],[]],
	"corner_br":[[0, 0, 0, 0],[0, 0, 0, 0],[]],
}
## Design canvas the HUD is laid out on; pin() keeps pieces on their edge when the
## interface scale (GameSettings ui_scale) shrinks the logical canvas.
const CANVAS := Vector2(1280, 800)

static var _textures := {}
static var _theme: Theme
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
	var path := painted(name if name.begins_with("res://") else "res://assets/ui/%s.svg" % name)
	return load(path) if ResourceLoader.exists(path) else null

## The painted icon (assets/ui/icons/<name>.png, tools/build_ui_kit.py) that replaces an
## SVG icon of the same name; other paths are returned unchanged.
static func painted(path: String) -> String:
	var painted_path := "res://assets/ui/icons/%s.png" % path.get_file().get_basename()
	return painted_path if ResourceLoader.exists(painted_path) else path

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
	_extra_buttons(t, false)
	_kit2_buttons(t, false)
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
	tooltip_theme(t)
	# Meters, sliders and scroll bars.
	t.set_stylebox("background", "ProgressBar", frame("bar_bg"))
	t.set_stylebox("fill", "ProgressBar", frame("bar_fill", AMBER))
	t.set_color("font_color", "ProgressBar", INK)
	var track := frame("bar_bg")
	track.set_content_margin_all(3)
	for type in ["HSlider","VSlider"]:
		t.set_stylebox("slider", type, track)
		t.set_stylebox("grabber_area", type, frame("bar_fill", AMBER))
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

# ------------------------------------------------------------------ names on hover

## The quick paint palette of the bag, the same in the village and in rooms (swatch()).
const PALETTE := ["#f6eee0","#edbc63","#d98477","#70afa3","#7c9ec6"]

## Paint swatches' names (translated where shown).
const COLOR_NAMES := {"#f6eee0":"상아색","#edbc63":"꿀색","#d98477":"산호색","#70afa3":"청록색","#7c9ec6":"하늘색",
	"#f1dfb8":"크림색","#dfa958":"황토색","#789887":"세이지색","#bd7f75":"장밋빛 갈색","#7d9ca3":"안개 파랑",
	"#30595b":"짙은 청록","#774f3d":"밤색","#d5a250":"겨자색","#c47b50":"구리색","#ab789f":"연보라","#e6dfce":"모래색","#526552":"이끼색","#6889a1":"청회색",
	"#f0cdb1":"밝은 복숭아빛","#e4b587":"살구빛","#bc865c":"황갈색","#895b43":"갈색","#604431":"짙은 갈색"}
## What each fold key does, per fold id: [while open, while folded].
const FOLD_TIPS := {"objective":["목표 접기","목표 펼치기"],"survival_objective":["목표 접기","목표 펼치기"],"minimap":["미니맵 접기","미니맵 펼치기"],
	"hotbar":["퀵슬롯 접기","퀵슬롯 펼치기"],"profile":["프로필 접기","프로필 펼치기"],"toolbar":["도구 막대 접기","도구 막대 펼치기"]}

## Hover names: a night pill (the painted "tooltip" frame) with cream outlined text.
## Used by theme(), night_theme() and the studio's theme.
static func tooltip_theme(t: Theme) -> void:
	var pill := frame("tooltip")
	# Room for the laurel ends; one line of text sits centred on the pill.
	pill.content_margin_left = 21
	pill.content_margin_right = 21
	pill.content_margin_top = 5
	pill.content_margin_bottom = 6
	t.set_stylebox("panel", "TooltipPanel", pill)
	t.set_font("font", "TooltipLabel", FONT_STRONG)
	t.set_font_size("font_size", "TooltipLabel", 14)
	t.set_color("font_color", "TooltipLabel", INK)
	t.set_color("font_outline_color", "TooltipLabel", OUTLINE)
	t.set_constant("outline_size", "TooltipLabel", 4)
	t.set_color("font_shadow_color", "TooltipLabel", Color(0,0,0,0))

## Names a picture-only control on hover (name, then "  ·  " and its key). A picture that
## ignores the mouse starts passing it so the hover reaches it; only call this on
## informational pictures, not on art lying over clickable things. Returns c.
static func name_tip(c: Control, name: String, key := "") -> Control:
	c.tooltip_text = name if key.is_empty() else name + "  ·  " + key
	if c.mouse_filter == Control.MOUSE_FILTER_IGNORE: c.mouse_filter = Control.MOUSE_FILTER_PASS
	return c

## A paint colour's name ("#d98477" -> 산호색); the code itself when unnamed.
static func color_name(hex: String) -> String:
	var key := ("#" + hex.trim_prefix("#")).to_lower()
	return TranslationServer.translate(COLOR_NAMES[key]) if COLOR_NAMES.has(key) else key

## The fold key's name for a panel: "목표 접기" open, "목표 펼치기" folded.
static func fold_tip(id: String, shut: bool) -> String:
	var pair: Array = FOLD_TIPS.get(id, ["접기", "펼치기"])
	return TranslationServer.translate(pair[1] if shut else pair[0])

# ------------------------------------------------------------------ sound

## Soft UI sounds on the "UI" bus (Master until that bus exists). A kind is a take family,
## ui/<kind>.wav plus ui/<kind>_<n>.wav (tools/sfx/gen_ui.py), played through a no-repeat shuffle
## bag (sfx_bank.gd) with +-4 % pitch and +-1 dB jitter. A kind with no takes (not imported yet)
## falls back to a related kind below; an unknown kind stays silent. A message kind (deny, chat_in,
## toast_error ...) played right before a message also stands in for the generic toast chime that
## message raises in the same moment (main.gd message()): that chime is deduped like a repeat.
## Kinds: hover chip (the prompt chip tick; hover takes, its own gate) click open close toast confirm deny tab select slider drawer_open drawer_close
## count coin_gain chat_in chat_out whisper friend join leave notify toast_success toast_warn
## toast_error toast_social quest_accept quest_ready quest_complete star unlock rotate snap place
## lift cancel valid invalid paint brush fill undo redo layer swatch key_capture save
## craft_submit craft_step craft_done craft_fail page choice.
## A fanfare kind (quest_accept, quest_ready, quest_complete, unlock, save, craft_done) likewise covers a
## generic confirm raised in the same moment (the route guide's beacon set by a request taken).
## Kinds that come in bursts keep a longer gap than the 60 ms every kind has (SFX_GAP_MS).
static func sfx(kind: String, volume_db := -4.0) -> void:
	if not _sfx_gate(kind, int(SFX_GAP_MS.get(kind, 60))): return
	var family := sfx_family(kind)
	if family.is_empty(): return
	_sfx_play(SfxBank.pick_path("ui/" + family), volume_db, SfxBank.pitch(0.04))

const SfxBank = preload("res://scripts/sfx_bank.gd")
## A kind with no takes (not imported yet) plays this related kind instead (up to three hops).
const SFX_FALLBACK := {"chip": "hover", "deny": "close", "tab": "click", "select": "click", "slider": "hover", "drawer_open": "open",
	"drawer_close": "close", "count": "hover", "coin_gain": "toast", "chat_in": "toast", "chat_out": "click",
	"whisper": "chat_in", "friend": "toast", "join": "open", "leave": "close", "notify": "toast",
	"toast_success": "confirm", "toast_warn": "toast", "toast_error": "deny", "toast_social": "chat_in",
	"quest_accept": "confirm", "quest_ready": "toast", "quest_complete": "confirm", "star": "toast",
	"unlock": "confirm", "rotate": "slider", "snap": "slider", "place": "click", "lift": "click",
	"cancel": "close", "valid": "hover", "invalid": "deny", "paint": "click", "fill": "click", "undo": "click",
	"redo": "click", "layer": "click", "swatch": "hover", "key_capture": "click", "save": "confirm",
	"craft_submit": "confirm", "craft_step": "toast", "craft_done": "confirm", "craft_fail": "deny",
	"page": "click", "choice": "click"}
## Message kinds: each stands in for the generic toast chime of a message raised in the same moment.
const SFX_FOR_TOAST := ["deny", "coin_gain", "chat_in", "chat_out", "whisper", "friend", "join", "leave", "notify",
	"toast_success", "toast_warn", "toast_error", "toast_social", "quest_accept", "quest_ready", "quest_complete",
	"unlock", "save", "craft_submit", "craft_done", "craft_fail", "invalid", "cancel", "paint", "place", "lift"]
## Fanfare kinds: each covers a generic confirm raised in the same moment.
const SFX_FANFARE := ["quest_accept", "quest_ready", "quest_complete", "unlock", "save", "craft_done"]
## Least time (ms) between two plays of a kind that can come in bursts: currency count ticks, notify
## chimes (badges, "!" marks, invites), chat lines arriving poll after poll.
const SFX_GAP_MS := {"count": 80, "notify": 400, "chat_in": 400, "whisper": 400}

## The take family a kind plays ("" when neither it nor its fallbacks have takes yet).
static func sfx_family(kind: String) -> String:
	var family := kind
	for _hop in 3:
		if family.is_empty() or SfxBank.has("ui/" + family): break
		family = str(SFX_FALLBACK.get(family, ""))
	return family if not family.is_empty() and SfxBank.has("ui/" + family) else ""

## One take of a kind (its path) for a ladder of notes (sfx_note); "" when the kind has none.
static func sfx_take(kind: String) -> String:
	var family := sfx_family(kind)
	return SfxBank.pick_path("ui/" + family) if not family.is_empty() else ""

## One note of a ladder: `take` (sfx_take, the same take for every note so the steps stay in tune)
## raised by `semitones`, without the pitch jitter (star landings climb a scale). Notes keep their own
## short gap (25 ms), so quick steps all sound.
static func sfx_note(kind: String, take: String, semitones: float, volume_db := -4.0) -> void:
	if take.is_empty() or not _sfx_gate(kind + "#note", 25): return
	_sfx_play(take, volume_db, pow(2.0, semitones / 12.0))

## The next toast chime in this moment stays silent (a replayed chat backlog, a line this player just
## sent, a reward whose flying stars carry the sound): it is deduped like a repeat.
static func hush_toast() -> void:
	_last_played["toast"] = Time.get_ticks_msec()

## Whether a kind may play now (and marks it played): never headless, hover at most every 45 ms, each
## kind at most every `gap` ms. A message kind marks the toast chime as covered even when its own gap
## holds it back; a fanfare kind marks the generic confirm.
static func _sfx_gate(kind: String, gap: int) -> bool:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null or tree.root == null: return false
	# Headless runs (tests, tools) have a dummy audio driver that never finishes a playback, so a
	# sound played just before quitting stayed referenced at exit ("resources still in use").
	if DisplayServer.get_name() == "headless": return false
	var now := Time.get_ticks_msec()
	if kind in SFX_FOR_TOAST: _last_played["toast"] = now
	if kind in SFX_FANFARE: _last_played["#fanfare"] = now
	if kind == "confirm" and now - int(_last_played.get("#fanfare", -100000)) < 150: return false
	if kind == "hover":
		if now - _last_hover < 45: return false
		_last_hover = now
	# One press can reach both a button hook and an older sound.effect("click").
	if now - int(_last_played.get(kind, -100000)) < gap: return false
	_last_played[kind] = now
	return true

## Plays one take on the shared UI players (made once, under the tree's root).
static func _sfx_play(path: String, volume_db: float, pitch: float) -> void:
	if path.is_empty(): return
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null or tree.root == null: return
	var host := tree.root.get_node_or_null("RpgUiSounds")
	if host == null and tree.root.has_meta("rpg_ui_sounds"):
		# A host made earlier this frame is still waiting for its deferred add: use it, not a second.
		# (has_meta first: get_meta with a null default reports an error when the key is missing.)
		var waiting = tree.root.get_meta("rpg_ui_sounds")
		if is_instance_valid(waiting) and not (waiting as Node).is_queued_for_deletion(): host = waiting
	var fresh := host == null
	if fresh:
		host = Node.new()
		host.name = "RpgUiSounds"
		host.process_mode = Node.PROCESS_MODE_ALWAYS
		for i in 6: host.add_child(AudioStreamPlayer.new())
		tree.root.add_child.call_deferred(host)
		tree.root.set_meta("rpg_ui_sounds", host)
	# Take paths come from sfx_bank (cached strings, cleared by CleanExit); the loaded streams live
	# on the host node, freed with the tree; a static stream cache kept them alive past exit
	# ("resources still in use").
	var sounds: Dictionary = host.get_meta("sounds", {})
	if not sounds.has(path):
		sounds[path] = load(path) if ResourceLoader.exists(path) else null
		host.set_meta("sounds", sounds)
	if sounds[path] == null: return
	# A free player first (a fanfare is not cut by the next hover tick), else the oldest in turn.
	var count := host.get_child_count()
	var voice: AudioStreamPlayer = host.get_child(_voice % count)
	for k in count:
		var free_one: AudioStreamPlayer = host.get_child((_voice + k) % count)
		if not free_one.playing:
			voice = free_one
			break
	_voice += 1
	voice.bus = "UI" if AudioServer.get_bus_index("UI") != -1 else "Master"
	voice.stream = sounds[path]
	voice.volume_db = volume_db + SfxBank.db(1.0)
	voice.pitch_scale = pitch
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
	# Held weakly: a view replaced in the same frame (a window opened on a known state and changed
	# at once) is gone before the deferred start.
	var held: WeakRef = weakref(c)
	var start := func() -> void:
		var node: Control = held.get_ref()
		if node == null or not node.is_inside_tree(): return
		node.pivot_offset = node.size * 0.5
		var tw := node.create_tween().set_parallel(true)
		tw.tween_property(node, "scale", Vector2.ONE, duration).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		tw.tween_property(node, "modulate:a", 1.0, duration * 0.7).set_trans(Tween.TRANS_SINE)
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

## Hover lift + brightness and the soft hover tick; a press sound on press (`press`, at `press_db`:
## click, or a kind of its own: a dialogue choice, a swatch, a danger button's deny; "" for none,
## when what the press opens has its own sound: a drawer's slide).
static func hover_motion(c: Control, lift := 1.05, pivot := Vector2(0.5, 0.5), sounds := true, press := "click", press_db := -4.0) -> void:
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
	if sounds and c is BaseButton and not press.is_empty(): (c as BaseButton).button_down.connect(func(): sfx(press, press_db))

## Counts a number label up (or down) to value with a small pulse. A change of a count already shown
## ticks softly as the digits roll (at most ~12 a second) and a gain ends on a coin jingle; the first
## fill of a label, and a count restarted by clearing its count_target (quests.gd reward_fly, whose
## flying stars carry the sound), stay silent.
static func count_to(l: Label, value: int, duration := -1.0) -> void:
	if not is_instance_valid(l): return
	var heard := l.has_meta("count_target")
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
	var gain := value > from
	var roll := func(v: float) -> void:
		var shown := str(int(round(v)))
		if heard and shown != l.text: sfx("count", -16.0 if gain else -19.0)
		l.text = shown
	tw.tween_method(roll, float(from), float(value), seconds).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	# A count cut short by a newer one (killed) never finishes: only the last gain jingles.
	if heard and gain: tw.finished.connect(func(): sfx("coin_gain", -12.0))
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

## Type roles: [font, size]. Colours depend on the surface (text_style()).
const TYPE := {"window":[FONT_DISPLAY, T_WINDOW], "section":[FONT_STRONG, T_SECTION], "body":[FONT_BODY, T_BODY],
	"caption":[FONT_BODY, T_CAPTION], "small":[FONT_BODY, T_SMALL]}

## Gives a label one of the type roles on parchment ("paper") or night glass ("night"):
## window titles are PAPER_INK on paper and GOLD with an outline on night; captions are
## PAPER_MUTED / SOFT; the rest PAPER_INK / INK. Returns l.
static func text_style(l: Label, role := "body", kind := "paper") -> Label:
	var spec: Array = TYPE.get(role, TYPE.body)
	var night := kind != "paper"
	l.add_theme_font_override("font", spec[0])
	l.add_theme_font_size_override("font_size", spec[1])
	var color := PAPER_INK
	if role == "caption": color = SOFT if night else PAPER_MUTED
	elif night: color = GOLD if role == "window" else INK
	l.add_theme_color_override("font_color", color)
	if night and role == "window":
		l.add_theme_color_override("font_outline_color", OUTLINE)
		l.add_theme_constant_override("outline_size", 5)
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
static func divider(parent: Node, color := PAPER_LINE, width := 0.0) -> Control:
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

## A little keyboard key cap ("E", "Tab", "Esc"). `key` may be an action id ("inventory"): the cap
## then shows that action's key and relabels itself when the bindings change.
static func keycap(parent: Node, key: String, size := 12) -> Label:
	var cap := Label.new()
	cap.text = key_text(key)
	cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cap.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	cap.custom_minimum_size = Vector2(KEY, KEY)
	cap.add_theme_font_override("font", FONT_BOLD)
	cap.add_theme_font_size_override("font_size", size)
	cap.add_theme_color_override("font_color", Color("3a2614"))
	cap.add_theme_stylebox_override("normal", frame("keycap"))
	cap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if is_action(key): watch_key(cap, key)
	parent.add_child(cap)
	return cap

# ------------------------------------------------------------------ keys

## True for a GameSettings action id ("inventory", "interact"), false for a literal key ("Esc").
static func is_action(id: String) -> bool:
	for entry in GameSettings.ACTIONS:
		if entry[0] == id: return true
	return false

## The key to show for an action id (its current primary binding: "I", or "J" after a rebind);
## a literal key ("Esc", "Enter", "1-9", "F9") passes through.
static func key_text(action_or_key: String) -> String:
	return GameSettings.key_label(action_or_key) if is_action(action_or_key) else action_or_key

## Controls that show an action's key join this group; KeyWatch relabels them on a rebind.
const KEY_GROUP := &"rpg_action_key"

## Makes c follow the key of `action`: a Label shows key_text(action); with `tip_name` the control's
## tooltip reads "<tip_name>  ·  <key>" (name_tip). Relabelled whenever the bindings change.
static func watch_key(c: Control, action: String, tip_name := "") -> void:
	if tip_name.is_empty(): c.set_meta("key_action", action)
	else:
		c.set_meta("key_tip_action", action)
		c.set_meta("key_tip_name", tip_name)
	c.add_to_group(KEY_GROUP)
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null or tree.root == null: return
	# The one watcher: kept here from the moment it is queued, so the other calls in the same frame
	# (a hotbar's slots and caps) find it before the deferred add has run.
	if is_instance_valid(_key_watch) and not _key_watch.is_queued_for_deletion(): return
	if tree.root.has_node("RpgUiKeys"):
		_key_watch = tree.root.get_node("RpgUiKeys")
		return
	var watch := KeyWatch.new()
	watch.name = "RpgUiKeys"
	_key_watch = watch
	tree.root.add_child.call_deferred(watch)

## The key watcher (queued or under the root), so watch_key makes exactly one.
static var _key_watch: Node

## Relabels every key cap and key tooltip in the tree (KeyWatch calls it after a rebind).
static func relabel_keys() -> void:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null: return
	for node in tree.get_nodes_in_group(KEY_GROUP):
		if node.has_meta("key_action") and node is Label:
			(node as Label).text = key_text(str(node.get_meta("key_action")))
		if node.has_meta("key_tip_action") and node is Control:
			name_tip(node, str(node.get_meta("key_tip_name")), key_text(str(node.get_meta("key_tip_action"))))

## One listener for all key caps: GameSettings.listen wants a plain method (no lambdas, see there).
class KeyWatch extends Node:
	func _enter_tree() -> void:
		GameSettings.listen(_on_settings)
	func _exit_tree() -> void:
		GameSettings.unlisten(_on_settings)
	func _on_settings(keys: Array[String]) -> void:
		if "bindings" in keys: load("res://scripts/rpg_ui.gd").relabel_keys()

## "[key] text": a key cap and its words ("[I] 가방"). kind "night" (cream, outlined) or "paper".
static func key_hint(parent: Node, action_or_key: String, text: String, kind := "night") -> HBoxContainer:
	var row := HBoxContainer.new()
	row.name = "KeyHint"
	row.add_theme_constant_override("separation", 6)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(row)
	var cap := keycap(row, action_or_key, 12)
	cap.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var words := label(row, text, 14, INK, true) if kind == "night" else caption(row, text, 14, PAPER_INK)
	words.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	row.set_meta("words", words)
	return row

## The one close key: a flat 34 px painted "close" icon that lifts on hover, named "닫기 · Esc" (or
## "닫기 · <the key that opened the window>" for an action, kept in step with rebinding).
static func close_key(parent: Node, callback: Callable, action := "") -> Button:
	var b := Button.new()
	b.name = "Close"
	b.icon = icon_texture("close")
	b.expand_icon = true
	b.flat = true
	b.custom_minimum_size = Vector2(CLOSE, CLOSE)
	b.focus_mode = Control.FOCUS_NONE
	b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	b.set_meta("rpg_close", true)
	# A flat button still keeps its theme box's content margins, which shrank the icon to ~18 px.
	var bare := StyleBoxEmpty.new()
	bare.set_content_margin_all(2)
	for state in ["normal","hover","pressed","hover_pressed","disabled","focus"]: b.add_theme_stylebox_override(state, bare)
	var named := TranslationServer.translate("닫기")
	if is_action(action):
		name_tip(b, named, key_text(action))
		watch_key(b, action, named)
	else: name_tip(b, named, "Esc" if action.is_empty() else action)
	hover_motion(b, 1.12)
	b.pressed.connect(func(): if callback.is_valid(): callback.call())
	parent.add_child(b)
	return b

const BUTTON_VARIANTS := {"normal":"", "primary":"PrimaryButton", "gold":"GoldButton", "night":"NightButton", "danger":"DangerButton", "ghost":"GhostButton"}
const BUTTON_SIZES := {"sm":[BTN_SM, 13], "md":[BTN_MD, 15], "lg":[BTN_LG, 16], "menu":[BTN_MENU, 19]}

## A text button in one of the shared looks: variant normal | primary | gold | night | danger |
## ghost, size sm (32) | md (40) | lg (44) | menu (52). Hover lift with the hover and click sounds;
## keyboard / pad focus only in menus (`menu`), never on the HUD.
static func button(parent: Node, text: String, callback: Callable, variant := "normal", size := "md", menu := false) -> Button:
	var b := Button.new()
	b.text = text
	b.theme_type_variation = BUTTON_VARIANTS.get(variant, "")
	var spec: Array = BUTTON_SIZES.get(size, BUTTON_SIZES.md)
	b.custom_minimum_size.y = spec[0]
	b.add_theme_font_size_override("font_size", spec[1])
	if size == "menu": b.add_theme_font_override("font", FONT_STRONG)
	b.focus_mode = Control.FOCUS_ALL if menu else Control.FOCUS_NONE
	# A danger button (delete, leave, discard) answers with the low deny note instead of the click.
	if variant == "danger": hover_motion(b, 1.03, Vector2(0.5, 0.5), true, "deny", -6.0)
	else: hover_motion(b, 1.03)
	b.pressed.connect(func(): if callback.is_valid(): callback.call())
	parent.add_child(b)
	return b

## The danger (red-tinted) and ghost (text-only until hovered) button looks for a theme.
static func _extra_buttons(t: Theme, night: bool) -> void:
	var base := "btn_night" if night else "btn_paper"
	t.set_type_variation("DangerButton", "Button")
	for state in ["normal","hover","pressed","disabled"]:
		t.set_stylebox(state, "DangerButton", frame(base + "_" + state, Color(1.0, .74, .68)))
	t.set_stylebox("hover_pressed", "DangerButton", frame(base + "_pressed", Color(1.0, .74, .68)))
	t.set_stylebox("focus", "DangerButton", frame("focus"))
	var danger_ink := INK if night else ACCENT
	for item in ["font_color","font_hover_color","font_pressed_color","font_focus_color","font_hover_pressed_color"]:
		t.set_color(item, "DangerButton", danger_ink)
	t.set_color("font_disabled_color", "DangerButton", Color(danger_ink, .5))
	t.set_type_variation("GhostButton", "Button")
	var bare := StyleBoxEmpty.new()
	bare.content_margin_left = 12; bare.content_margin_right = 12; bare.content_margin_top = 6; bare.content_margin_bottom = 6
	for state in ["normal","disabled"]: t.set_stylebox(state, "GhostButton", bare)
	t.set_stylebox("hover", "GhostButton", frame(base + "_hover", Color(1,1,1,.55)))
	t.set_stylebox("pressed", "GhostButton", frame(base + "_pressed", Color(1,1,1,.7)))
	t.set_stylebox("hover_pressed", "GhostButton", frame(base + "_pressed", Color(1,1,1,.7)))
	t.set_stylebox("focus", "GhostButton", frame("focus"))
	var ink := INK if night else PAPER_INK
	for item in ["font_color","font_pressed_color","font_focus_color"]: t.set_color(item, "GhostButton", ink)
	for item in ["font_hover_color","font_hover_pressed_color"]: t.set_color(item, "GhostButton", HOVER if night else ACCENT)
	t.set_color("font_disabled_color", "GhostButton", Color(ink, .45))

## UI kit 2 variations: "MenuGoldButton" / "MenuNightButton" (the big painted plates of the title and
## big actions) and "TabButton" (folder tabs: tab_off, tab_on when pressed, tab_disabled).
static func _kit2_buttons(t: Theme, night: bool) -> void:
	for pair in [["MenuGoldButton", "btn_menu_gold", PAPER_INK], ["MenuNightButton", "btn_menu_night", INK]]:
		t.set_type_variation(pair[0], "Button")
		_buttons(t, pair[0], pair[1], pair[2], pair[0] == "MenuNightButton")
		t.set_font("font", pair[0], FONT_STRONG)
		t.set_font_size("font_size", pair[0], 19)
		t.set_color("font_hover_color", pair[0], HOVER if pair[0] == "MenuNightButton" else ACCENT)
	t.set_type_variation("TabButton", "Button")
	t.set_stylebox("normal", "TabButton", frame("tab_off"))
	t.set_stylebox("hover", "TabButton", frame("tab_off", Color(1.08, 1.06, 1.0)))
	t.set_stylebox("pressed", "TabButton", frame("tab_on"))
	t.set_stylebox("hover_pressed", "TabButton", frame("tab_on"))
	t.set_stylebox("disabled", "TabButton", frame("tab_disabled"))
	t.set_stylebox("focus", "TabButton", StyleBoxEmpty.new())
	for item in ["font_color", "font_hover_color", "font_focus_color"]: t.set_color(item, "TabButton", PAPER_MUTED)
	for item in ["font_pressed_color", "font_hover_pressed_color"]: t.set_color(item, "TabButton", PAPER_INK)
	t.set_color("font_disabled_color", "TabButton", Color(PAPER_MUTED, .5))
	t.set_font("font", "TabButton", FONT_STRONG)
	t.set_font_size("font_size", "TabButton", 15)

## A row of folder tabs (one ButtonGroup). entries: [{id, label, icon?, badge?}]; on_select(id) is
## called when a tab is picked (by click or select_tab). The strip keeps meta "selected" (the id now
## shown); step_tab moves it (PageUp/PageDown).
static func tab_strip(parent: Node, entries: Array, on_select: Callable, kind := "paper") -> HBoxContainer:
	var strip := HBoxContainer.new()
	strip.name = "Tabs"
	strip.add_theme_constant_override("separation", 2)
	parent.add_child(strip)
	var group := ButtonGroup.new()
	var buttons := {}
	for entry in entries:
		var b := Button.new()
		var id := str(entry.get("id", ""))
		b.name = "Tab_" + id
		b.text = str(entry.get("label", ""))
		b.toggle_mode = true
		b.button_group = group
		b.focus_mode = Control.FOCUS_NONE
		b.theme_type_variation = "TabButton"
		b.custom_minimum_size = Vector2(0, 32)
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		if kind == "night":
			b.self_modulate = Color(0.86, 0.9, 0.95)
			# The cool tint dims the muted ink too much on glass: unpicked tabs read in full ink.
			for item in ["font_color", "font_hover_color", "font_focus_color"]: b.add_theme_color_override(item, PAPER_INK)
		if not str(entry.get("icon", "")).is_empty():
			b.icon = icon_texture(str(entry.icon))
			b.expand_icon = true
			b.add_theme_constant_override("icon_max_width", 20)
		strip.add_child(b)
		if int(entry.get("badge", 0)) > 0: badge(b, int(entry.badge))
		buttons[id] = b
		b.toggled.connect(func(on: bool) -> void:
			if not on: return
			# A change of tab on a shown strip gives the tab tick; the strip's first pick (as its
			# window is built, under that window's open sound) and a hidden strip stay silent.
			var heard := strip.has_meta("selected") and strip.is_visible_in_tree()
			strip.set_meta("selected", id)
			if heard: sfx("tab", -8.0)
			if on_select.is_valid(): on_select.call(id))
	strip.set_meta("buttons", buttons)
	return strip

## Picks tab `id` on a tab_strip (no-op for an unknown id).
static func select_tab(strip: Control, id: String) -> void:
	if not is_instance_valid(strip) or not strip.has_meta("buttons"): return
	var buttons: Dictionary = strip.get_meta("buttons")
	if buttons.has(id) and is_instance_valid(buttons[id]): (buttons[id] as Button).button_pressed = true

## Moves the strip's selection by `step` visible, enabled tabs (wrapping), for PageUp/PageDown.
static func step_tab(strip: Control, step: int) -> void:
	if not is_instance_valid(strip) or not strip.has_meta("buttons"): return
	var buttons: Dictionary = strip.get_meta("buttons")
	var ids: Array = buttons.keys().filter(func(k) -> bool: return is_instance_valid(buttons[k]) and (buttons[k] as Button).visible and not (buttons[k] as Button).disabled)
	if ids.is_empty(): return
	var at := ids.find(str(strip.get_meta("selected", ids[0])))
	select_tab(strip, str(ids[posmod(at + step, ids.size())]))

## A small round presence dot: "online" (ONLINE), "away" (AWAY: a room, the workshop or an
## expedition) or "offline" (OFFLINE).
static func status_dot(parent: Node, state: String, size := 10.0) -> Panel:
	var dot := Panel.new()
	dot.name = "Status"
	var disc := StyleBoxFlat.new()
	disc.bg_color = {"online": ONLINE, "away": AWAY}.get(state, OFFLINE)
	disc.set_corner_radius_all(int(size))
	disc.corner_detail = 8
	disc.border_color = Color(OUTLINE, 0.8)
	disc.set_border_width_all(1)
	disc.anti_aliasing = true
	dot.add_theme_stylebox_override("panel", disc)
	dot.custom_minimum_size = Vector2(size, size)
	dot.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	dot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(dot)
	return dot

## A round portrait of a player's character (assets/ui/portrait_<character>.png, the explorer
## when unknown) in the portrait ring, `size` px.
static func avatar_thumb(parent: Node, character: String, size := 36.0) -> Control:
	var holder := Control.new()
	holder.name = "Avatar"
	holder.custom_minimum_size = Vector2(size, size)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(holder)
	var medal := PanelContainer.new()
	var disc := StyleBoxFlat.new()
	disc.bg_color = Color("f5e6c4")
	disc.set_corner_radius_all(int(size))
	disc.corner_detail = 12
	medal.add_theme_stylebox_override("panel", disc)
	medal.clip_children = CanvasItem.CLIP_CHILDREN_AND_DRAW
	medal.position = Vector2(size * 0.08, size * 0.08)
	medal.size = Vector2(size * 0.84, size * 0.84)
	medal.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(medal)
	var path := "res://assets/ui/portrait_%s.png" % character
	if not ResourceLoader.exists(path): path = "res://assets/ui/portrait_explorer.png"
	medal.add_child(icon(path, size * 0.84))
	var ring := TextureRect.new()
	ring.texture = half("portrait_ring")
	ring.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	ring.stretch_mode = TextureRect.STRETCH_SCALE
	ring.size = Vector2(size, size)
	ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(ring)
	return holder

## One person in a social list: portrait, status dot, name (T_BODY) and a caption (where they are,
## when they were last seen), then icon buttons. p: {username, character, state ("online" | "away" |
## "offline"), where}. actions: [{icon, tip, call, disabled?}] (an icon name from assets/ui/icons).
static func person_row(parent: Node, p: Dictionary, actions: Array) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.name = "Person_" + str(p.get("username", ""))
	row.add_theme_constant_override("separation", GAP_S)
	parent.add_child(row)
	avatar_thumb(row, str(p.get("character", "explorer")), 38.0)
	status_dot(row, str(p.get("state", "offline")))
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 0)
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(column)
	var name_label := label(column, str(p.get("username", "")), T_BODY, PAPER_INK, false)
	name_label.add_theme_font_override("font", FONT_STRONG)
	name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	if not str(p.get("where", "")).is_empty():
		var where := label(column, str(p.where), T_SMALL, PAPER_MUTED, false)
		where.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	for action in actions:
		var b := Button.new()
		b.name = "Act_" + str(action.get("icon", ""))
		b.theme_type_variation = "GhostButton"
		b.focus_mode = Control.FOCUS_NONE
		b.custom_minimum_size = Vector2(BTN_SM, BTN_SM)
		b.icon = icon_texture(str(action.get("icon", "")))
		b.expand_icon = true
		b.add_theme_constant_override("icon_max_width", 24)
		b.disabled = bool(action.get("disabled", false))
		name_tip(b, str(action.get("tip", "")))
		var call: Callable = action.get("call", Callable())
		if call.is_valid(): b.pressed.connect(call)
		# hover_motion gives the press its click (button_down): no second click on release.
		hover_motion(b, 1.1)
		row.add_child(b)
	return row

## A count pill (ACCENT) on the top-right corner of a slot or button; hidden at 0. Calling it
## again on the same parent updates the same pill; a count that grows there (a new letter, invite or
## request) gives a soft notify chime, the first fill does not.
static func badge(parent: Control, count: int) -> Label:
	var pill: Label = parent.get_node_or_null("Badge")
	if pill != null and count > int(pill.get_meta("count", 0)) and parent.is_visible_in_tree(): sfx("notify", -12.0)
	if pill == null:
		pill = Label.new()
		pill.name = "Badge"
		pill.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		pill.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		pill.add_theme_font_override("font", FONT_BOLD)
		pill.add_theme_font_size_override("font_size", 11)
		pill.add_theme_color_override("font_color", INK)
		var dot := StyleBoxFlat.new()
		dot.bg_color = ACCENT
		dot.set_corner_radius_all(9)
		dot.corner_detail = 8
		dot.border_color = Color(OUTLINE, .6)
		dot.set_border_width_all(1)
		dot.content_margin_left = 5; dot.content_margin_right = 5
		pill.add_theme_stylebox_override("normal", dot)
		pill.custom_minimum_size = Vector2(18, 18)
		pill.mouse_filter = Control.MOUSE_FILTER_IGNORE
		pill.set_anchors_preset(Control.PRESET_TOP_RIGHT)
		pill.offset_left = -12; pill.offset_right = 6; pill.offset_top = -6; pill.offset_bottom = 12
		pill.grow_horizontal = Control.GROW_DIRECTION_BOTH
		parent.add_child(pill)
	pill.text = str(count) if count < 100 else "99+"
	pill.visible = count > 0
	pill.set_meta("count", count)
	return pill

## A round paint swatch ("#d98477") that lifts on hover; a gold rim marks the chosen one. Named
## by its colour on hover.
static func swatch(parent: Node, hex: String, selected: bool, callback: Callable) -> Button:
	var b := Button.new()
	b.custom_minimum_size = Vector2(CLOSE, CLOSE)
	b.focus_mode = Control.FOCUS_NONE
	b.set_meta("hex", hex)
	var colour := Color(hex)
	for state in ["normal","hover","pressed"]:
		var dot := StyleBoxFlat.new()
		dot.bg_color = colour
		dot.set_corner_radius_all(17)
		dot.corner_detail = 12
		var lit: bool = state != "normal" or selected
		dot.set_border_width_all(3 if lit else 2)
		dot.border_color = HOVER if lit else Color("6e4b2c")
		dot.shadow_color = Color(0,0,0,.25)
		dot.shadow_size = 3
		dot.shadow_offset = Vector2(0,2)
		b.add_theme_stylebox_override(state, dot)
	name_tip(b, color_name(hex))
	hover_motion(b, 1.15, Vector2(0.5, 0.5), true, "swatch")
	b.pressed.connect(func(): if callback.is_valid(): callback.call())
	parent.add_child(b)
	return b

static func icon(path: String, size: float) -> TextureRect:
	var image := TextureRect.new()
	image.texture = load(painted(path))
	image.custom_minimum_size = Vector2(size,size)
	image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	image.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	image.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return image

## Icon + label + bar for HP/hunger/stamina style meters on night glass.
static func meter(parent: Node, title: String, color: Color, icon_name := "") -> Dictionary:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	name_tip(row, title)
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
## With a fold_id a chevron badge on the medal folds the plate down to the medal.
static func player_frame(ui: Control, portrait: String, fold_id := "") -> Dictionary:
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
	var face := name_tip(icon(portrait, 60), TranslationServer.translate("내 캐릭터"))
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
	# The two currencies show only a picture and a number: each names itself on hover.
	var star_name := TranslationServer.translate("별씨")
	var leaf_name := TranslationServer.translate("잎전")
	coins.add_child(name_tip(icon("res://assets/starseed.svg", 24), star_name))
	var stars := numbers(label(coins, "0", 17, HOVER), 17)
	stars.custom_minimum_size.x = 34
	name_tip(stars, star_name)
	var gap := Control.new(); gap.custom_minimum_size.x = 6; gap.mouse_filter = Control.MOUSE_FILTER_IGNORE; coins.add_child(gap)
	coins.add_child(name_tip(icon("res://assets/ui/leaf.svg", 22), leaf_name))
	var leaves := numbers(label(coins, "0", 17, LEAF_LIGHT), 17)
	leaves.custom_minimum_size.x = 34
	name_tip(leaves, leaf_name)
	var status := label(column, "", 12, SOFT)
	status.visible = false
	if not fold_id.is_empty():
		# Folded: the name/coins column rolls into the medal and the plate fades away.
		fold_toggle(holder, fold_id, Vector2.LEFT).position = Vector2(50, 48)
		var clip := fold_clip(column, false)
		foldable(clip, fold_id, func(shut: bool, animate: bool):
			roll(clip, shell, shut, animate, false)
			var tw := _fold_tween(shell, "plate_tween", animate)
			if tw: tw.tween_property(shell, "self_modulate:a", 0.0 if shut else 1.0, FOLD_TIME)
			else: shell.self_modulate.a = 0.0 if shut else 1.0)
	return {"panel":shell, "name":name, "stars":stars, "leaves":leaves, "status":status, "column":column, "portrait":face}

## Square slots with an icon, a key cap and a caption on a glass tray. A slot spec is
## {icon, label, call, action ("inventory" or a literal key like "F9"), primary, press, press_db}; an
## action's key cap and its "name  ·  key" tooltip follow rebinding. press: the slot's press sound
## (hover_motion: "click" by default, "select" for a pick, "" when what it opens slides in with its
## own sound, as the bag's drawer), at press_db (-4). With a
## fold_id a chevron key at the tray's right end slides it below the screen.
static func hotbar(ui: Control, slots: Array, y: float, fold_id := "") -> HBoxContainer:
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
		# "action": an action id ("inventory") or a literal key ("F9"); "key" is the older name.
		var key_id := str(slot.get("action", slot.get("key", "")))
		name_tip(b, slot.label, key_text(key_id))
		if is_action(key_id): watch_key(b, key_id, slot.label)
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
		if not key_id.is_empty():
			var cap := keycap(b, key_id, 11)
			cap.position = Vector2(-7,-9)
		b.pressed.connect(slot.call)
		hover_motion(b, 1.08, Vector2(0.5, 1.0), true, str(slot.get("press", "click")), float(slot.get("press_db", -4.0)))
		bar.add_child(b)
	bar.set_meta("tray", tray)
	bar.set_meta("tray_top", y + 6)
	if not fold_id.is_empty(): bar.set_meta("fold_key", fold_dock(ui, fold_id, [tray, bar], 640.0 + width * 0.5, y + 6 + (SLOT + 8) * 0.5))
	# The strip spans the canvas: a new UI scale resizes it, and the dock is laid out again.
	bar.resized.connect(func(): _lay_dock(bar))
	_lay_dock(bar)
	return bar

## Shows or hides one hotbar slot (a room a visitor only looks around has no bag); the tray fits
## the slots left.
static func show_slot(slot: Control, shown: bool) -> void:
	slot.visible = shown
	var bar := slot.get_parent() as Control
	if bar and bar.has_meta("tray"): _lay_dock(bar)

## The bottom-left corner is the chat box's (chat_box.gd: x 14 to 342 on the design canvas, at the
## foot of every place). Pieces centred at the screen's foot (the hotbar, the prompt chip) move right
## just enough to clear it when the canvas narrows (UI scale above 100 %), never past the right edge.
const CHAT_CORNER := 350.0

## How far a piece `width` wide, centred at the foot of a canvas `canvas_width` wide, moves right to
## clear the chat corner, keeping `right_room` free at the right edge.
static func corner_shift(width: float, canvas_width: float, right_room := 14.0) -> float:
	var left := (canvas_width - width) * 0.5
	return clampf(CHAT_CORNER - left, 0.0, maxf(0.0, canvas_width - right_room - left - width))

## Lays a hotbar out for its shown slots and the canvas: the tray fits the visible slots, centred at
## the screen's foot (moved right only to clear the chat corner), and the fold key sits at its right
## end. Only x is set here, so a folded dock stays folded.
static func _lay_dock(bar: Control) -> void:
	if not is_instance_valid(bar) or not bar.has_meta("tray") or bar.get_meta("laying", false): return
	var tray: Control = bar.get_meta("tray")
	var host := bar.get_parent() as Control
	if not is_instance_valid(tray) or host == null: return
	bar.set_meta("laying", true)
	var count := 0
	for child in bar.get_children():
		if child is Control and (child as Control).visible: count += 1
	var width := maxf(count, 1) * (SLOT + GAP) - GAP + 36.0
	var canvas_width := host.size.x if host.size.x > 0.0 else CANVAS.x
	var key: Control = bar.get_meta("fold_key") if bar.has_meta("fold_key") and is_instance_valid(bar.get_meta("fold_key")) else null
	var shift := corner_shift(width, canvas_width, 14.0 + (36.0 if key else 0.0))
	tray.custom_minimum_size.x = width
	tray.offset_left = -width * 0.5 + shift
	tray.offset_right = width * 0.5 + shift
	bar.offset_left = shift
	bar.offset_right = shift
	if key:
		var side := maxf(key.custom_minimum_size.x, 28.0)
		key.offset_left = width * 0.5 + shift + 8.0
		key.offset_right = key.offset_left + side
	bar.set_meta("laying", false)

# ------------------------------------------------------------------ toasts

## How long a toast stays: plain ones, and ones that carry action buttons.
const TOAST_SECONDS := 4.5
const TOAST_ACTION_SECONDS := 12.0
const TOAST_MAX := 3
## The same text again keeps its toast up longer only within this many seconds of its first showing:
## a line repeated by a refresh loop (every reply says it again) still leaves on time.
const TOAST_REFRESH_WINDOW := 2.0
## Chimes asked for so far (tests: the field's toasts stay silent).
static var toast_chimes := 0
## Each kind its own glyph: error and warn are painted badges ("!" in lacquer red, an amber
## triangle), never the close key's art (tools/build_ui_icons.py --painted).
const TOAST_ICONS := {"info":"res://assets/starseed.svg", "success":"res://assets/ui/leaf.svg", "warn":"res://assets/ui/icons/warn.png",
	"error":"res://assets/ui/icons/alert.png", "social":"res://assets/ui/people.svg"}
## How long an evicted toast (the oldest, when a 4th arrives) takes to fade, and a slot to close.
const TOAST_EVICT_SECONDS := 0.15
## The side columns a top toast keeps clear of on a narrow canvas (frame or status card on the left,
## minimap, map or location card on the right: each about 290 px from its edge).
const TOAST_SIDE := 300.0
const TOAST_COLLAPSE_SECONDS := 0.15

## The shared toast lane: a full-width column whose toasts stack centred from `y` on the design
## canvas (top lane), or upward ending at `y` + 44 when y is in the lower half (the field's lane).
## width > 0 gives every toast that width (the village's 520 px pills); 0 fits each to its text up
## to max_width. opts.grow = "up" pins the lane's foot at `y` from the host's top and stacks
## upward from there (notes just above a card that starts at y + a gap); the oldest leave while
## the stack would rise past the host's top. opts.max caps the toasts shown at once (TOAST_MAX).
static func toast_lane(host: Control, y := 94.0, width := 0.0, max_width := 640.0, opts := {}) -> VBoxContainer:
	var lane := VBoxContainer.new()
	lane.name = "ToastLane"
	lane.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	lane.mouse_filter = Control.MOUSE_FILTER_IGNORE
	lane.add_theme_constant_override("separation", 6)
	if str(opts.get("grow", "")) == "up":
		lane.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
		lane.offset_top = 0.0
		lane.offset_bottom = y
		lane.grow_vertical = Control.GROW_DIRECTION_BEGIN
		lane.alignment = BoxContainer.ALIGNMENT_END
		# The room above the foot is y: once laid out, the oldest leave while the rest would not fit
		# (a note that wraps to two lines takes the room of two).
		lane.sort_children.connect(func() -> void:
			var shown := toasts(lane)
			var tall := -float(lane.get_theme_constant("separation"))
			for item in shown: tall += (item as Control).size.y + float(lane.get_theme_constant("separation"))
			while shown.size() > 1 and tall > y:
				var oldest: Control = shown.pop_front()
				tall -= oldest.size.y + float(lane.get_theme_constant("separation"))
				dismiss_toast(oldest, TOAST_EVICT_SECONDS))
	else:
		var top := y < CANVAS.y * 0.5
		# A top lane shares its band with the side columns (frame, minimap, map and status cards).
		if top: lane.set_meta("clear_sides", true)
		lane.alignment = BoxContainer.ALIGNMENT_BEGIN if top else BoxContainer.ALIGNMENT_END
		if top: lane.offset_top = y
		else: lane.offset_bottom = -(CANVAS.y - y - 44.0)
	lane.set_meta("width", width)
	lane.set_meta("max_width", max_width)
	lane.set_meta("max", maxi(1, int(opts.get("max", TOAST_MAX))))
	lane.theme = night_theme()
	host.add_child(lane)
	return lane

## The toasts on a lane, oldest first (those already leaving are not counted).
static func toasts(lane: Control) -> Array:
	var out := []
	if not is_instance_valid(lane): return out
	for child in lane.get_children():
		if child.has_meta("toast") and not child.get_meta("leaving", false): out.append(child)
	return out

## The toast on the lane that shows this text, or null.
static func find_toast(lane: Control, text: String) -> Control:
	for item in toasts(lane):
		if str(item.get_meta("toast")) == text: return item
	return null

## A short line in a night pill with a kind icon (info: the star-seed glint, success, warn, error,
## social), popping in with a soft chime. It leaves after 4.5 s (12 s with action buttons:
## opts.actions = [{label, call}], pressing one runs it and dismisses the toast). At most three
## stack on a lane (the lane's max; the oldest fades out quickly, then its slot closes); the same
## text while it is still shown refreshes that toast instead of stacking. opts.sound = false keeps
## it silent (the field, a window's own notes); it is silent with reduced motion too. Returns the
## toast.
static func toast(lane: Control, text: String, kind := "info", opts := {}) -> Control:
	if not is_instance_valid(lane) or text.is_empty(): return null
	var same := find_toast(lane, text)
	if same:
		if Time.get_ticks_msec() * 0.001 - float(same.get_meta("born", 0.0)) < TOAST_REFRESH_WINDOW: _toast_timer(same)
		if not calm():
			same.pivot_offset = Vector2(same.size.x * 0.5, 0)
			var pulse := same.create_tween().set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
			pulse.tween_property(same, "scale", Vector2.ONE * 1.04, 0.08)
			pulse.tween_property(same, "scale", Vector2.ONE, 0.18)
		return same
	var standing := toasts(lane)
	while standing.size() >= int(lane.get_meta("max", TOAST_MAX)):
		dismiss_toast(standing.pop_front(), TOAST_EVICT_SECONDS)
	var pill := PanelContainer.new()
	pill.name = "Toast"
	pill.set_meta("toast", text)
	pill.set_meta("kind", kind)
	pill.add_theme_stylebox_override("panel", panel_style("pill"))
	pill.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	var actions: Array = opts.get("actions", [])
	pill.mouse_filter = Control.MOUSE_FILTER_STOP if not actions.is_empty() else Control.MOUSE_FILTER_IGNORE
	var width: float = float(lane.get_meta("width", 0.0))
	var widest := width if width > 0.0 else float(lane.get_meta("max_width", 640.0))
	# On a narrowed canvas (UI scale above 100 %) a top toast stays between the side columns.
	if lane.get_meta("clear_sides", false) and lane.size.x > 0.0: widest = minf(widest, maxf(lane.size.x - 2.0 * TOAST_SIDE, 260.0))
	if width > 0.0:
		width = widest
		pill.custom_minimum_size.x = width
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pill.add_child(row)
	var glint := icon(str(TOAST_ICONS.get(kind, TOAST_ICONS.info)), 24)
	glint.name = "Kind"
	glint.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(glint)
	var words := label(row, text, T_BODY, INK)
	words.name = "Text"
	words.add_theme_font_override("font", FONT_STRONG)
	words.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	words.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var room := widest - 96.0
	if width > 0.0: words.custom_minimum_size.x = room
	else: words.custom_minimum_size.x = minf(room, FONT_STRONG.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, T_BODY).x + 4.0)
	words.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	for entry in actions:
		var run: Callable = entry.get("call", Callable())
		var act := func() -> void:
			if run.is_valid(): run.call()
			dismiss_toast(pill)
		var key := button(row, str(entry.get("label", "")), act, "night", "sm")
		key.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	lane.add_child(pill)
	pill.set_meta("life", TOAST_ACTION_SECONDS if not actions.is_empty() else float(opts.get("seconds", TOAST_SECONDS)))
	pill.set_meta("born", Time.get_ticks_msec() * 0.001)
	_toast_timer(pill)
	if not calm():
		pill.modulate.a = 0.0
		pill.scale = Vector2(0.92, 0.92)
		var held: WeakRef = weakref(pill)
		var start := func() -> void:
			var node: Control = held.get_ref()
			if node == null or not node.is_inside_tree() or node.get_meta("leaving", false): return
			node.pivot_offset = Vector2(node.size.x * 0.5, 0)
			var tw := node.create_tween().set_parallel(true).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
			tw.tween_property(node, "scale", Vector2.ONE, 0.3)
			tw.tween_property(node, "modulate:a", 1.0, 0.2)
			node.set_meta("pop", tw)
		start.call_deferred()
		if bool(opts.get("sound", true)):
			toast_chimes += 1
			_toast_chime(kind)
	return pill

## A new toast's chime by its kind: info the plain toast chime, success / warn / error / social their
## own. A message kind played just before (SFX_FOR_TOAST: deny, chat_in, quest_accept ...) or
## hush_toast() stands in for it, as it does for the plain chime.
static func _toast_chime(kind: String) -> void:
	const KINDS := {"success": "toast_success", "warn": "toast_warn", "error": "toast_error", "social": "toast_social"}
	var sound := str(KINDS.get(kind, "toast"))
	if sound != "toast" and Time.get_ticks_msec() - int(_last_played.get("toast", -100000)) < 60: return
	sfx(sound, -12.0)

## (Re)starts a toast's stay, then fades it out and frees it.
static func _toast_timer(pill: Control) -> void:
	if pill.has_meta("timer"):
		var old: Tween = pill.get_meta("timer")
		if old and old.is_valid(): old.kill()
	if not pill.is_inside_tree(): return
	var tw := pill.create_tween()
	tw.tween_interval(float(pill.get_meta("life", TOAST_SECONDS)))
	tw.tween_callback(func(): dismiss_toast(pill))
	pill.set_meta("timer", tw)

## Fades a toast out (it keeps its slot meanwhile, no longer counted), then closes its slot so the
## toasts around it glide together, and frees it. With reduced motion it goes at once.
static func dismiss_toast(pill: Control, seconds := 0.3) -> void:
	if not is_instance_valid(pill) or pill.get_meta("leaving", false): return
	pill.set_meta("leaving", true)
	if pill.has_meta("timer"):
		var old: Tween = pill.get_meta("timer")
		if old and old.is_valid(): old.kill()
	if pill.has_meta("pop"):
		var pop: Tween = pill.get_meta("pop")
		if pop and pop.is_valid(): pop.kill()
	if calm() or not pill.is_inside_tree():
		if pill.get_parent(): pill.get_parent().remove_child(pill)
		pill.queue_free()
		return
	var tw := pill.create_tween()
	tw.tween_property(pill, "modulate:a", 0.0, seconds).set_trans(Tween.TRANS_SINE)
	tw.tween_callback(func(): _collapse_toast(pill))

## The empty slot of a faded toast shrinks to nothing, then the toast is freed.
static func _collapse_toast(pill: Control) -> void:
	if not is_instance_valid(pill): return
	var tall := pill.size.y
	for child in pill.get_children(): if child is CanvasItem: (child as CanvasItem).visible = false
	pill.add_theme_stylebox_override("panel", StyleBoxEmpty.new())
	pill.custom_minimum_size = Vector2(0.0, tall)
	var tw := pill.create_tween()
	tw.tween_property(pill, "custom_minimum_size:y", 0.0, TOAST_COLLAPSE_SECONDS).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	tw.tween_callback(pill.queue_free)

## Clears a lane at once (a place that says "nothing to show").
static func clear_toasts(lane: Control) -> void:
	for item in toasts(lane):
		item.set_meta("leaving", true)
		item.queue_free()

## Least time (ms) between two of the prompt chip's appearance ticks.
const PROMPT_TICK_MS := 800

## Floating interaction chip above the hotbar; hidden while empty. The leading
## "E  " of the text is drawn as a key cap.
static func prompt(ui: Control, y: float) -> Label:
	var pill := Label.new()
	pill.name = "Prompt"
	# Left: the words start after the key cap (fit_prompt makes the chip exactly as wide as both).
	pill.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
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
	# Gentle breathing so the chip reads as "you can act here". When the place shows it (its own
	# visible turning on, not the HUD around it coming back after a talk) a very soft hover tick, at
	# most once in PROMPT_TICK_MS while walking past a row of props.
	pill.visibility_changed.connect(func():
		var toggled: bool = pill.visible != bool(pill.get_meta("own_shown", false))
		pill.set_meta("own_shown", pill.visible)
		if pill.visible and pill.is_inside_tree():
			pill.modulate.a = 0.0
			pill.create_tween().tween_property(pill, "modulate:a", 1.0, 0.15)
			var now := Time.get_ticks_msec()
			if toggled and pill.is_visible_in_tree() and now - int(pill.get_meta("tick_at", -100000)) > PROMPT_TICK_MS:
				pill.set_meta("tick_at", now)
				sfx("chip", -14.0))
	ui.add_child(pill)
	pin(pill, 0.5, 1.0)
	# A new UI scale narrows the canvas and moves the chip: it keeps clear of the chat corner.
	pill.item_rect_changed.connect(fit_prompt.bind(pill))
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
		if box: box.content_margin_left = 16.0 + cap_width + 8.0 if cap.visible else 22.0
		cap.position = Vector2(16, (chip.size.y - 24.0) * 0.5)
	fit_prompt(chip)

## Fits a prompt chip to its key cap and words, centred where it is pinned (a Label centres its
## text on its whole width, not after the cap, so the chip is made exactly as wide as it needs).
static func fit_prompt(chip: Label) -> void:
	if not is_instance_valid(chip) or chip.get_meta("fitting", false): return
	chip.set_meta("fitting", true)
	var width := chip.get_combined_minimum_size().x
	if is_equal_approx(chip.anchor_left, 0.5):
		var parent := chip.get_parent() as Control
		var shift := corner_shift(width, parent.size.x) if parent and parent.size.x > 0.0 else 0.0
		chip.offset_left = -width * 0.5 + shift
		chip.offset_right = width * 0.5 + shift
	else:
		chip.size = Vector2(width, chip.size.y)
		chip.position.x = CANVAS.x * 0.5 - width * 0.5
	chip.set_meta("fitting", false)

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

# ------------------------------------------------------------------ folding

## HUD panels fold to a compact form (a header row, a chip, a handle tab) and
## remember it per panel id ("objective", "minimap", "hotbar", "profile",
## "survival_objective", "toolbar") in [hud] of the settings file. Pieces register
## with foldable(id, apply); set_folded(), a panel's chevron key and the HUD key
## (toggle_all_folds) drive every piece of that id. Instant with reduced motion.
const FOLD_TIME := 0.22
const FOLD_GROUP := &"hud_fold"
static var _folds := {}
static var _folds_loaded := false

static func folded(id: String) -> bool:
	if not _folds_loaded:
		_folds_loaded = true
		var config := ConfigFile.new()
		if config.load(GameSettings.I18n.settings_path()) == OK and config.has_section("hud"):
			for key in config.get_section_keys("hud"): _folds[key] = bool(config.get_value("hud", key, false))
	return bool(_folds.get(id, false))

## Forget the cached fold states (tests re-read the settings file).
static func reload_folds() -> void:
	_folds.clear()
	_folds_loaded = false

static func set_folded(id: String, shut: bool, animate := true) -> void:
	set_folds([id], shut, animate)

## Folds or unfolds every piece registered under ids and saves the choice.
static func set_folds(ids: Array, shut: bool, animate := true) -> void:
	folded("")
	for id in ids: _folds[id] = shut
	var config := ConfigFile.new()
	config.load(GameSettings.I18n.settings_path())
	for id in _folds: config.set_value("hud", id, _folds[id])
	config.save(GameSettings.I18n.settings_path())
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null: return
	for host in tree.get_nodes_in_group(FOLD_GROUP):
		for entry in host.get_meta("folds", []):
			if entry[0] in ids: (entry[1] as Callable).call(shut, animate and not calm())

static func toggle_fold(id: String) -> void:
	var shut := not folded(id)
	set_folded(id, shut)
	sfx("close" if shut else "open", -8.0)

## The HUD key: folds every panel on screen, or unfolds them all when all are
## folded. Returns true when the panels are now folded.
static func toggle_all_folds() -> bool:
	var ids := fold_ids()
	if ids.is_empty(): return false
	var shut := ids.any(func(id): return not folded(id))
	set_folds(ids, shut)
	sfx("close" if shut else "open", -8.0)
	return shut

## Fold ids of the pieces currently in the tree.
static func fold_ids() -> Array:
	var ids := []
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null: return ids
	for host in tree.get_nodes_in_group(FOLD_GROUP):
		for entry in host.get_meta("folds", []):
			if not ids.has(entry[0]): ids.append(entry[0])
	return ids

## Registers a piece under a fold id. apply(folded, animate) moves it between its
## open and folded looks; it runs once now, unanimated, with the saved state.
static func foldable(host: Node, id: String, apply: Callable) -> void:
	var entries: Array = host.get_meta("folds", [])
	entries.append([id, apply])
	host.set_meta("folds", entries)
	host.add_to_group(FOLD_GROUP)
	apply.call(folded(id), false)

## Replaces the fold tween in a node's slot; null when the change should be instant.
static func _fold_tween(c: Node, slot := "fold_tween", animate := true) -> Tween:
	if c.has_meta(slot):
		var old: Tween = c.get_meta(slot)
		if old and old.is_valid(): old.kill()
		c.remove_meta(slot)
	if not animate or not c.is_inside_tree(): return null
	var tw := c.create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	c.set_meta(slot, tw)
	return tw

## The white chevron (pointing up) centred in a key; rotate it to point elsewhere.
static func _chevron(host: Control, inset: Vector4) -> TextureRect:
	var art := TextureRect.new()
	art.name = "Chevron"
	art.texture = icon_texture("chevron")
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	art.set_anchors_preset(Control.PRESET_FULL_RECT)
	art.offset_left = inset.x; art.offset_top = inset.y; art.offset_right = -inset.z; art.offset_bottom = -inset.w
	art.modulate = INK
	art.resized.connect(func(): art.pivot_offset = art.size * 0.5)
	host.add_child(art)
	return art

## A small night key whose chevron points where its panel goes: `toward` while open
## (folding), the opposite way while folded. Pressing it toggles fold id.
static func fold_toggle(parent: Node, id: String, toward := Vector2.UP, side := 28.0) -> Button:
	var key := Button.new()
	key.name = "Fold"
	key.custom_minimum_size = Vector2(side, side)
	key.size = key.custom_minimum_size
	key.focus_mode = Control.FOCUS_NONE
	for state in ["normal","hover","pressed","disabled"]: key.add_theme_stylebox_override(state, frame("btn_night_" + state))
	key.add_theme_stylebox_override("hover_pressed", frame("btn_night_pressed"))
	key.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	var art := _chevron(key, Vector4(5, 4, 5, 6))
	key.pressed.connect(func(): toggle_fold(id))
	hover_motion(key, 1.12, Vector2(0.5, 0.5), false)
	key.mouse_entered.connect(func(): sfx("hover"))
	parent.add_child(key)
	foldable(key, id, func(shut: bool, animate: bool):
		key.tooltip_text = fold_tip(id, shut)
		var angle := (-toward if shut else toward).angle() + PI * 0.5
		var tw := _fold_tween(art, "fold_tween", animate)
		if tw: tw.tween_property(art, "rotation", angle, FOLD_TIME)
		else: art.rotation = angle)
	return key

## Moves body into a clipping holder that rolls shut along one axis (height when
## vertical). Open, the holder takes the body's minimum size, so the card around it
## still follows the body's text as it changes.
static func fold_clip(body: Control, vertical := true) -> Control:
	var clip := Control.new()
	clip.name = "FoldClip"
	clip.clip_contents = true
	clip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	clip.size_flags_horizontal = body.size_flags_horizontal
	clip.size_flags_vertical = body.size_flags_vertical
	clip.set_meta("open", 1.0)
	var parent := body.get_parent()
	if parent:
		var at := body.get_index()
		parent.remove_child(body)
		parent.add_child(clip)
		parent.move_child(clip, at)
	clip.add_child(body)
	body.set_anchors_preset(Control.PRESET_TOP_WIDE if vertical else Control.PRESET_LEFT_WIDE)
	body.offset_left = 0; body.offset_top = 0; body.offset_right = 0; body.offset_bottom = 0
	var fit := func() -> void:
		if not is_instance_valid(clip) or not is_instance_valid(body): return
		var need := body.get_combined_minimum_size()
		var open: float = clip.get_meta("open", 1.0)
		clip.custom_minimum_size = Vector2(need.x, need.y * open) if vertical else Vector2(need.x * open, need.y)
	clip.set_meta("fit", fit)
	body.minimum_size_changed.connect(fit)
	fit.call()
	return clip

## Rolls a fold_clip() shut or open; `card` (the panel around it) shrinks with it.
static func roll(clip: Control, card: Control, shut: bool, animate: bool, vertical := true) -> void:
	var body := clip.get_child(0) as Control
	var fit: Callable = clip.get_meta("fit")
	var step := func(t: float) -> void:
		if not is_instance_valid(clip): return
		clip.set_meta("open", t)
		fit.call()
		if is_instance_valid(body): body.modulate.a = t
		if is_instance_valid(card): _snug(card, vertical)
	if not shut: clip.visible = true
	var tw := _fold_tween(clip, "fold_tween", animate)
	if tw: tw.tween_method(step, float(clip.get_meta("open", 1.0)), 0.0 if shut else 1.0, FOLD_TIME)
	else: step.call(0.0 if shut else 1.0)
	if shut:
		var done := func() -> void:
			if not is_instance_valid(clip): return
			clip.visible = false
			if is_instance_valid(card): _snug(card, vertical)
		if tw: tw.tween_callback(done)
		else: done.call()

## Lets a card shrink back to its content along one axis (containers only grow by
## themselves), keeping its pinned edge in place.
static func _snug(card: Control, vertical := true) -> void:
	var need := card.get_combined_minimum_size()
	if vertical:
		if card.grow_vertical == Control.GROW_DIRECTION_BEGIN: card.offset_top = card.offset_bottom - need.y
		else: card.offset_bottom = card.offset_top + need.y
	elif card.grow_horizontal == Control.GROW_DIRECTION_BEGIN: card.offset_left = card.offset_right - need.x
	else: card.offset_right = card.offset_left + need.x

## A HUD card that folds to its header row: `body` (everything under `head`) rolls
## up into a clip, the card shrinks to the header, and a chevron key closes the
## header row. Returns the key.
static func fold_card(card: Control, head: HBoxContainer, body: Control, id: String) -> Button:
	for part in head.get_children():
		if part is Label: (part as Label).vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	head.add_child(spacer)
	var key := fold_toggle(head, id, Vector2.UP)
	key.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var clip := fold_clip(body)
	# Shorter text lets the card shrink again (a container only grows by itself).
	body.minimum_size_changed.connect(func(): if is_instance_valid(card) and clip.visible: _snug(card))
	foldable(clip, id, func(shut: bool, animate: bool): roll(clip, card, shut, animate))
	return key

## Slides a piece by `offset` as its id folds. mode "hide": fades out and hides when
## folded; "show": the reverse (a handle shown only while folded); "move": stays
## visible and only moves (its visibility belongs to someone else).
static func fold_shift(c: Control, id: String, offset: Vector2, mode := "hide") -> void:
	var alpha := c.modulate.a
	c.set_meta("fold_at", 0.0)
	var place := func(t: float) -> void:
		if not is_instance_valid(c): return
		var by: Vector2 = offset * (t - float(c.get_meta("fold_at", 0.0)))
		c.set_meta("fold_at", t)
		c.offset_left += by.x; c.offset_right += by.x
		c.offset_top += by.y; c.offset_bottom += by.y
		if mode != "move": c.modulate.a = alpha * (1.0 - t)
	foldable(c, id, func(shut: bool, animate: bool):
		var target := (1.0 if shut else 0.0) if mode != "show" else (0.0 if shut else 1.0)
		var away := mode != "move" and target > 0.0
		if mode != "move" and not away: c.visible = true
		var tw := _fold_tween(c, "fold_tween", animate)
		if tw: tw.tween_method(place, float(c.get_meta("fold_at", 0.0)), target, FOLD_TIME)
		else: place.call(target)
		if away:
			if tw: tw.tween_callback(func(): if is_instance_valid(c): c.visible = false)
			else: c.visible = false)

## Bottom docks (slot hotbar, field toolbar): a chevron key beside the dock's right
## edge (`right`, centred on `mid` of the design canvas) slides `parts` below the
## screen; folded, a small handle tab with an up chevron waits at the bottom centre.
static func fold_dock(ui: Control, id: String, parts: Array, right: float, mid: float) -> Button:
	var key := fold_toggle(ui, id, Vector2.DOWN)
	key.position = Vector2(right + 8.0, mid - 14.0)
	pin(key, 0.5, 1.0)
	var handle := Button.new()
	handle.name = "FoldHandle"
	handle.focus_mode = Control.FOCUS_NONE
	handle.tooltip_text = fold_tip(id, true)
	for state in ["normal","hover","pressed","hover_pressed","disabled"]: handle.add_theme_stylebox_override(state, frame("pill_night"))
	handle.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	handle.custom_minimum_size = Vector2(76, 36)
	handle.size = handle.custom_minimum_size
	handle.position = Vector2(CANVAS.x * 0.5 - 38.0, CANVAS.y - 46.0)
	_chevron(handle, Vector4(8, 7, 8, 9))
	handle.pressed.connect(func(): toggle_fold(id))
	hover_motion(handle, 1.08, Vector2(0.5, 1.0), false)
	handle.mouse_entered.connect(func(): sfx("hover"))
	ui.add_child(handle)
	pin(handle, 0.5, 1.0)
	for part in parts + [key]: fold_shift(part, id, Vector2(0, 130))
	fold_shift(handle, id, Vector2(0, 60), "show")
	return key

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
	t.set_color("font_hover_color","Button",HOVER)
	t.set_color("font_disabled_color","Button",Color(INK,.45))
	t.set_stylebox("focus","Button",frame("focus"))
	for spec in [["GoldButton","btn_gold",PAPER_INK,false],["PrimaryButton","btn_green",INK,true],["NightButton","btn_night",INK,true]]:
		t.set_type_variation(spec[0],"Button")
		_buttons(t,spec[0],spec[1],spec[2],spec[3])
	t.set_color("font_hover_color","NightButton",HOVER)
	_extra_buttons(t,true)
	_kit2_buttons(t,true)
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
	_night_coverage(t)
	tooltip_theme(t)
	_night_theme=t
	return t

## The control types the parchment theme styles, in night glass, so a night panel inside a
## paper root (or the reverse) never shows the other surface's lists, tabs, menus or scroll
## wells (tests/ui_consistency_check.gd keeps both themes covering NIGHT_TYPES).
const THEMED_TYPES := ["Label","Button","LineEdit","TextEdit","CheckBox","CheckButton","ItemList","TabBar","TabContainer",
	"OptionButton","PopupMenu","ScrollContainer","VScrollBar","HScrollBar","HSlider","VSlider","ProgressBar","TooltipPanel","TooltipLabel"]

static func _night_coverage(t: Theme) -> void:
	# Lists: a night well; the picked row glows gold, the hovered one lifts a little.
	var well := frame("field_night")
	well.set_content_margin_all(8)
	t.set_stylebox("panel", "ItemList", well)
	t.set_stylebox("focus", "ItemList", StyleBoxEmpty.new())
	var picked := StyleBoxFlat.new()
	picked.bg_color = Color(GOLD, .28)
	picked.set_corner_radius_all(8)
	picked.border_color = Color(GOLD, .7)
	picked.set_border_width_all(1)
	var hovered := StyleBoxFlat.new()
	hovered.bg_color = Color(1,1,1,.1)
	hovered.set_corner_radius_all(8)
	for item in ["selected","selected_focus"]: t.set_stylebox(item, "ItemList", picked)
	t.set_stylebox("hovered", "ItemList", hovered)
	t.set_stylebox("cursor", "ItemList", StyleBoxEmpty.new())
	t.set_stylebox("cursor_unfocused", "ItemList", StyleBoxEmpty.new())
	for item in ["font_color","font_hovered_color"]: t.set_color(item, "ItemList", INK)
	t.set_color("font_selected_color", "ItemList", HOVER)
	t.set_constant("v_separation", "ItemList", 6)
	# Drop-down menus: plain night glass.
	var menu := frame("panel_night_plain")
	menu.set_content_margin_all(10)
	t.set_stylebox("panel", "PopupMenu", menu)
	t.set_stylebox("hover", "PopupMenu", picked)
	for item in ["font_color","font_accelerator_color"]: t.set_color(item, "PopupMenu", INK)
	t.set_color("font_hover_color", "PopupMenu", HOVER)
	t.set_color("font_disabled_color", "PopupMenu", Color(INK,.45))
	t.set_constant("v_separation", "PopupMenu", 8)
	t.set_icon("arrow", "OptionButton", half("arrow_down_light"))
	t.set_constant("arrow_margin", "OptionButton", 12)
	# Tabs: night keys, the chosen one gold.
	for type in ["TabBar","TabContainer"]:
		t.set_stylebox("tab_selected", type, frame("btn_gold_normal"))
		t.set_stylebox("tab_hovered", type, frame("btn_night_hover"))
		t.set_stylebox("tab_unselected", type, frame("btn_night_normal"))
		t.set_color("font_selected_color", type, PAPER_INK)
		t.set_color("font_unselected_color", type, INK)
		t.set_color("font_hovered_color", type, HOVER)
	t.set_stylebox("panel", "TabContainer", frame("panel_night_plain"))
	# Scrolling, sliders and meters share the parchment pieces (they read on both surfaces).
	t.set_stylebox("panel", "ScrollContainer", StyleBoxEmpty.new())
	for type in ["VScrollBar","HScrollBar"]:
		t.set_stylebox("scroll", type, frame("scroll_track"))
		t.set_stylebox("scroll_focus", type, frame("scroll_track"))
		t.set_stylebox("grabber", type, frame("scroll_grabber"))
		t.set_stylebox("grabber_highlight", type, frame("scroll_grabber_hover"))
		t.set_stylebox("grabber_pressed", type, frame("scroll_grabber_hover"))
	var track := frame("bar_bg")
	track.set_content_margin_all(3)
	for type in ["HSlider","VSlider"]:
		t.set_stylebox("slider", type, track)
		t.set_stylebox("grabber_area", type, frame("bar_fill", AMBER))
		t.set_stylebox("grabber_area_highlight", type, frame("bar_fill", Color("f3c96a")))
		t.set_icon("grabber", type, half("slider_grabber"))
		t.set_icon("grabber_highlight", type, half("slider_grabber_hover"))
		# Keyboard / pad focus (the settings sliders): the same bright edge as the buttons.
		t.set_stylebox("focus", type, frame("focus"))
	t.set_stylebox("background", "ProgressBar", frame("bar_bg"))
	t.set_stylebox("fill", "ProgressBar", frame("bar_fill", AMBER))
	t.set_color("font_color", "ProgressBar", INK)
	t.set_icon("checked", "CheckBox", half("check_on"))
	t.set_icon("unchecked", "CheckBox", half("check_off"))
	t.set_icon("radio_checked", "CheckBox", half("radio_on"))
	t.set_icon("radio_unchecked", "CheckBox", half("radio_off"))

# ------------------------------------------------------------------ windows

## The window stack: instance ids of open window and drawer roots, bottom to top. Each root holds
## its description in meta "rpg_window". Only ids live here (no callables, no nodes), so nothing
## stale outlives a scene; entries whose root is gone are pruned on every read.
static var _stack: Array[int] = []
## Called with (open_count, top_kind) whenever the stack changes ("" when empty). Plain methods
## only (listen_windows), like GameSettings.listen: a lambda held in a static list can crash the
## engine on exit.
static var window_listeners: Array[Callable] = []

## A shared screen shade: the radial fall from SHADE_IN to SHADE_OUT (dim > 0 darkens it evenly to
## that opacity, the blocked-client look), full-rect under `parent`, fading in over 0.2 s.
static func shade(parent: Control, dim := 0.0) -> TextureRect:
	var veil := TextureRect.new()
	veil.name = "Shade"
	var fall := GradientTexture2D.new()
	fall.fill = GradientTexture2D.FILL_RADIAL
	fall.fill_from = Vector2(0.5, 0.45)
	fall.fill_to = Vector2(1.1, 1.1)
	fall.gradient = Gradient.new()
	if dim > 0.0: fall.gradient.colors = PackedColorArray([Color(SHADE_IN, dim * 0.85), Color(SHADE_OUT, dim)])
	else: fall.gradient.colors = PackedColorArray([SHADE_IN, SHADE_OUT])
	veil.texture = fall
	veil.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	veil.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	parent.add_child(veil)
	if not calm():
		veil.modulate.a = 0.0
		veil.create_tween().tween_property(veil, "modulate:a", 1.0, 0.2)
	return veil

## One window: title (T_WINDOW), optional head controls, the close key, a rule, then the body.
## opts: kind "paper" | "night"; width (WINDOW_W.standard); place "top" (y WINDOW_TOP) | "centre" |
## "bottom" (above the hotbar); modal (true: a shade, shared with a modal window already open on the
## same host or on a host around it, and the world under it takes no clicks); action (the
## GameSettings action that opens it: the close key is named with its key; "" names Esc); icon (a
## picture before the title); on_close (what the close key does; default close_window); scroll
## (true: the body scrolls once the card would pass the screen's foot); id; dim (shade opacity for a
## darker shade); closable (false: no close key, and Esc routing leaves it open: a blocking screen);
## sound (false: no open sound, for a page swapped in place or a window whose opening is heard in
## the world: a chest's creak).
## Returns {root, shade, card, head, title, body, close, id, action, kind, modal}; free it with
## close_window(w). Opens with pop_in and the open sound and joins the window stack.
static func window(host: Control, title: String, opts := {}) -> Dictionary:
	var kind := str(opts.get("kind", "paper"))
	var width := float(opts.get("width", WINDOW_W.standard))
	var place := str(opts.get("place", "top"))
	var modal := bool(opts.get("modal", true))
	var action := str(opts.get("action", ""))
	var id := str(opts.get("id", ""))
	var root := Control.new()
	root.name = id.to_pascal_case() if not id.is_empty() else "Window"
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_STOP if modal else Control.MOUSE_FILTER_IGNORE
	# Paper windows look the same in every place (a room's own theme is night glass).
	root.theme = theme()
	host.add_child(root)
	var veil: TextureRect = null
	if modal:
		var under := _modal_shade(host)
		veil = under if under else shade(root, float(opts.get("dim", 0.0)))
	var card := PanelContainer.new()
	card.name = "Card"
	card.custom_minimum_size.x = width
	card.add_theme_stylebox_override("panel", panel_style("night" if kind == "night" else "paper"))
	if kind == "night": card.theme = night_theme()
	root.add_child(card)
	_place_card(card, width, place)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", GAP_S)
	card.add_child(column)
	var head := HBoxContainer.new()
	head.name = "Head"
	head.add_theme_constant_override("separation", GAP)
	column.add_child(head)
	if not str(opts.get("icon", "")).is_empty():
		var art := icon(str(opts.icon), 30)
		art.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		head.add_child(art)
	var heading_label := Label.new()
	heading_label.name = "Title"
	heading_label.text = title
	text_style(heading_label, "window", kind)
	heading_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	heading_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	head.add_child(heading_label)
	var closable := bool(opts.get("closable", true))
	var w := {"root":root, "shade":veil, "card":card, "head":head, "title":heading_label, "body":column, "close":null,
		"id":id, "action":action, "kind":kind, "modal":modal, "closable":closable}
	var on_close: Callable = opts.get("on_close", Callable())
	var shut := func() -> void:
		if on_close.is_valid(): on_close.call()
		else: close_window(w)
	if closable: w["close"] = close_key(head, shut, action)
	divider(column, PAPER_LINE if kind != "night" else Color(GOLD, .55))
	if bool(opts.get("scroll", true)):
		var scroll := ScrollContainer.new()
		scroll.name = "Scroll"
		scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
		column.add_child(scroll)
		var body := VBoxContainer.new()
		body.name = "Body"
		body.add_theme_constant_override("separation", GAP_S)
		body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		scroll.add_child(body)
		var top: float = float(WINDOW_TOP) if place == "top" else 40.0
		var fit := func() -> void:
			if not is_instance_valid(body) or not body.is_inside_tree(): return
			var room := maxf(200.0, body.get_viewport().get_visible_rect().size.y - top - 140.0)
			scroll.custom_minimum_size.y = minf(body.get_combined_minimum_size().y, room)
		body.minimum_size_changed.connect(fit)
		w["body"] = body
	_push_window(root, w)
	pop_in(card)
	if bool(opts.get("sound", true)): sfx("open", -8.0)
	return w

## Card placement on the design canvas: top centre at WINDOW_TOP growing down, the screen's centre,
## or bottom centre above the hotbar growing up.
static func _place_card(card: Control, width: float, place: String) -> void:
	match place:
		"centre", "center":
			card.anchor_left = 0.5; card.anchor_right = 0.5; card.anchor_top = 0.5; card.anchor_bottom = 0.5
			card.offset_left = -width * 0.5; card.offset_right = width * 0.5
			card.offset_top = 0; card.offset_bottom = 0
			card.grow_horizontal = Control.GROW_DIRECTION_BOTH
			card.grow_vertical = Control.GROW_DIRECTION_BOTH
		"bottom":
			card.anchor_left = 0.5; card.anchor_right = 0.5; card.anchor_top = 1.0; card.anchor_bottom = 1.0
			card.offset_left = -width * 0.5; card.offset_right = width * 0.5
			card.offset_top = -(CANVAS.y - 690.0); card.offset_bottom = -(CANVAS.y - 690.0)
			card.grow_horizontal = Control.GROW_DIRECTION_BOTH
			card.grow_vertical = Control.GROW_DIRECTION_BEGIN
		_:
			card.position = Vector2(CANVAS.x * 0.5 - width * 0.5, WINDOW_TOP)
			pin(card, 0.5, 0.0)

## A non-modal side panel in the window family (the bag, the social drawer). opts: side "right" |
## "left"; width (DRAWER_W); top (20); kind; action ("inventory"); on_close; id. It slides in from
## its side; no shade, the world stays live. Returns the same keys as window().
static func drawer(host: Control, title: String, opts := {}) -> Dictionary:
	var side := str(opts.get("side", "right"))
	var width := float(opts.get("width", DRAWER_W))
	var top := float(opts.get("top", 20.0))
	var kind := str(opts.get("kind", "paper"))
	var action := str(opts.get("action", "inventory"))
	var id := str(opts.get("id", ""))
	var root := Control.new()
	root.name = id.to_pascal_case() if not id.is_empty() else "Drawer"
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = theme()
	host.add_child(root)
	var card := PanelContainer.new()
	card.name = "Card"
	card.custom_minimum_size.x = width
	card.add_theme_stylebox_override("panel", panel_style("night" if kind == "night" else "paper"))
	if kind == "night": card.theme = night_theme()
	root.add_child(card)
	var left := side == "left"
	card.position = Vector2(14.0 if left else CANVAS.x - 24.0 - width, top)
	pin(card, 0.0 if left else 1.0, 0.0)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", GAP_S)
	card.add_child(column)
	var head := HBoxContainer.new()
	head.name = "Head"
	head.add_theme_constant_override("separation", GAP_S)
	column.add_child(head)
	if not str(opts.get("icon", "")).is_empty():
		var art := icon(str(opts.icon), 30)
		art.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		head.add_child(art)
	var heading_label := Label.new()
	heading_label.name = "Title"
	heading_label.text = title
	text_style(heading_label, "window", kind)
	heading_label.add_theme_font_size_override("font_size", 22)
	heading_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	heading_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	head.add_child(heading_label)
	var w := {"root":root, "shade":null, "card":card, "head":head, "title":heading_label, "body":column, "close":null,
		"id":id, "action":action, "kind":"drawer", "surface":kind, "modal":false, "side":side}
	var on_close: Callable = opts.get("on_close", Callable())
	var shut := func() -> void:
		if on_close.is_valid(): on_close.call()
		else: close_window(w)
	w["close"] = close_key(head, shut, action)
	divider(column, PAPER_LINE if kind != "night" else Color(GOLD, .55))
	if bool(opts.get("hidden", false)):
		# Kept: closed until show_drawer opens it; it leaves the stack whenever it is hidden.
		root.visible = false
		root.set_meta("rpg_window", w)
		var kept := root.get_instance_id()
		root.tree_exiting.connect(func(): _forget_window(kept))
		return w
	_push_window(root, w)
	slide_in(card, Vector2(-40.0 if left else 40.0, 0.0))
	sfx("drawer_open", -10.0)
	return w

## Opens or closes a kept drawer (drawer(opts.hidden)): shown, it joins the window stack on top and
## slides in from its side with the drawer's open slide (drawer_open, as drawer()); hidden, it leaves
## the stack with its close slide (drawer_close, as close_window). No-op when unchanged.
static func show_drawer(w: Dictionary, shown: bool, animate := true) -> void:
	var root: Control = w.get("root") if is_instance_valid(w.get("root")) else null
	if root == null: return
	var id := root.get_instance_id()
	if root.visible == shown and (id in _stack) == shown: return
	root.visible = shown
	var card: Control = w.get("card") if is_instance_valid(w.get("card")) else null
	if shown:
		if not id in _stack: _stack.append(id)
		_windows_changed()
		if card: _slide_card(card, (-40.0 if str(w.get("side", "right")) == "left" else 40.0) if animate else 0.0)
		if animate: sfx("drawer_open", -10.0)
	else:
		if card: _slide_card(card, 0.0)
		_forget_window(id)
		if animate: sfx("drawer_close", -10.0)

## Slides a pinned card in by its offsets from `dx` away (0: straight to its place). A slide cut
## short by a quick close and reopen starts again from the card's resting offsets, so it never
## drifts.
static func _slide_card(card: Control, dx: float) -> void:
	var rest: Vector2 = card.get_meta("rest_x", Vector2(card.offset_left, card.offset_right))
	card.set_meta("rest_x", rest)
	var old = card.get_meta("slide") if card.has_meta("slide") else null
	if old is Tween and (old as Tween).is_valid(): (old as Tween).kill()
	card.offset_left = rest.x
	card.offset_right = rest.y
	card.modulate.a = 1.0
	if is_zero_approx(dx) or calm() or not card.is_inside_tree(): return
	card.offset_left = rest.x + dx
	card.offset_right = rest.y + dx
	card.modulate.a = 0.0
	var tw := card.create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.tween_property(card, "offset_left", rest.x, 0.28)
	tw.tween_property(card, "offset_right", rest.y, 0.28)
	tw.tween_property(card, "modulate:a", 1.0, 0.22)
	card.set_meta("slide", tw)

## Closes a window or drawer: leaves the stack, plays the close sound (a drawer its own slide) and
## frees it (a short fade first when animate; at once otherwise, so callers that test is_instance_valid
## see it gone). sound false: a window swapped for the next page or refreshed in place (the new one's
## open, or what replaced it, is the one sound), or one whose outcome has its own sound.
static func close_window(w: Dictionary, animate := true, sound := true) -> void:
	var root: Control = w.get("root") if w.has("root") and is_instance_valid(w.get("root")) else null
	if root == null: return
	if root.get_meta("rpg_closing", false): return
	root.set_meta("rpg_closing", true)
	_forget_window(root.get_instance_id())
	_hand_over_shade(root, w)
	if sound: sfx("drawer_close" if str(w.get("kind", "")) == "drawer" else "close", -10.0)
	if animate and not calm() and root.is_inside_tree():
		root.mouse_filter = Control.MOUSE_FILTER_IGNORE
		for child in root.get_children(): if child is Control: (child as Control).mouse_filter = Control.MOUSE_FILTER_IGNORE
		var tw := root.create_tween()
		tw.tween_property(root, "modulate:a", 0.0, 0.12).set_trans(Tween.TRANS_SINE)
		tw.tween_callback(root.queue_free)
	else:
		if root.get_parent(): root.get_parent().remove_child(root)
		root.queue_free()

## A modal shade shared with other windows lives under the window that made it: when that one
## closes first, the shade moves to the lowest window still sharing it (under its card), so the
## others keep their backdrop and no description points at a freed shade.
static func _hand_over_shade(root: Control, w: Dictionary) -> void:
	var veil = w.get("shade")
	if not is_instance_valid(veil) or not (veil is TextureRect) or (veil as Node).get_parent() != root: return
	for other in windows():
		var keep: Control = other.get("root")
		var theirs = other.get("shade")
		if not is_instance_valid(theirs) or theirs != veil or not is_instance_valid(keep): continue
		(veil as Node).reparent(keep, false)
		keep.move_child(veil, 0)
		return

## The open windows and drawers, bottom to top (their descriptions).
static func windows() -> Array:
	var out := []
	var kept: Array[int] = []
	for id in _stack:
		var node := instance_from_id(id) as Control
		if node == null or not is_instance_valid(node) or node.is_queued_for_deletion() or node.get_meta("rpg_closing", false): continue
		kept.append(id)
		out.append(node.get_meta("rpg_window", {}))
	_stack = kept
	return out

## The topmost open window or drawer ({} when none): Esc routing and chat suppression read it.
static func top_window() -> Dictionary:
	var open := windows()
	return open.back() if not open.is_empty() else {}

## True when `key` (GameSettings.canonical_key of the event) is the key that opened window `w`:
## the same key closes it (I, C, Tab, B, O...). Windows without an action close on Esc only.
static func closes_window(w: Dictionary, key: int) -> bool:
	var action := str(w.get("action", ""))
	return not action.is_empty() and key != KEY_NONE and key == GameSettings.default_key(action)

## Closes window `w` (the top of the stack when empty) the way its close key does, so the owner's
## clean-up (on_close) runs. False when nothing could be closed (no window, a dialogue, or a
## blocking screen without a close key).
static func close_top(w := {}) -> bool:
	if w.is_empty(): w = top_window()
	if w.is_empty() or not bool(w.get("closable", true)): return false
	var close = w.get("close")
	if close is BaseButton and is_instance_valid(close):
		(close as BaseButton).pressed.emit()
		return true
	if str(w.get("kind", "")) == "dialogue": return false
	close_window(w)
	return true

## The open modal windows (not drawers) on the stack.
static func modal_open() -> bool:
	return windows().any(func(w): return bool(w.get("modal", false)))

## Adds a listener (a plain method) for stack changes: callback(open_count, top_kind).
static func listen_windows(callback: Callable) -> void:
	if callback.is_custom():
		push_error("RpgUi.listen_windows wants a plain method, not a lambda or bound callable: %s" % callback)
		return
	if not callback in window_listeners: window_listeners.append(callback)

static func unlisten_windows(callback: Callable) -> void:
	window_listeners.erase(callback)

## Puts any root (a window, a drawer, later the dialogue) on the stack with its description.
static func _push_window(root: Control, w: Dictionary) -> void:
	root.set_meta("rpg_window", w)
	var id := root.get_instance_id()
	if not id in _stack: _stack.append(id)
	root.tree_exiting.connect(func(): _forget_window(id))
	_windows_changed()

static func _forget_window(id: int) -> void:
	if not id in _stack: return
	_stack.erase(id)
	_windows_changed()

static func _windows_changed() -> void:
	var open := windows()
	var top_kind := str((open.back() as Dictionary).get("kind", "")) if not open.is_empty() else ""
	for callback in window_listeners.duplicate():
		if callback.is_valid(): callback.call(open.size(), top_kind)
		else: window_listeners.erase(callback)

## The shade of a modal window already open on this host, or on a host around it (settings opened
## from the pause menu lives inside the pause layer), so a window opened from another reuses it.
static func _modal_shade(host: Control) -> TextureRect:
	for w in windows():
		var root: Control = w.get("root")
		var veil = w.get("shade")
		if not bool(w.get("modal", false)) or not is_instance_valid(root) or not is_instance_valid(veil) or not (veil is TextureRect): continue
		var under := root.get_parent()
		if under == host or (under != null and under.is_ancestor_of(host)): return veil
	return null

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
	# A background-free illustration (assets/.../standee/<name>.png) stands behind the
	# box's left end; without one the painted card frame is used.
	var standee_file := standee_path(portrait)
	var has_card := standee_file.is_empty() and not portrait.is_empty() and ResourceLoader.exists(portrait)
	var standee: TextureRect = null
	if not standee_file.is_empty():
		standee = TextureRect.new()
		standee.name = "Standee"
		standee.texture = load(standee_file)
		standee.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		standee.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		standee.anchor_left = 0.0; standee.anchor_right = 0.0; standee.anchor_top = 1.0; standee.anchor_bottom = 1.0
		standee.mouse_filter = Control.MOUSE_FILTER_IGNORE
		standee.set_meta("portrait", portrait)
		standee.set_meta("mood", "neutral")
		root.add_child(standee)
		fit_standee(standee)
		var keep := standee
		root.resized.connect(func(): if is_instance_valid(keep): fit_standee(keep))
	# The text box: bottom, full width inside safe margins.
	var box := PanelContainer.new()
	box.name = "Box"
	# The painted dialogue box (tools/build_ui_kit.py), or the night panel without it.
	var style := frame("dialogue_box") if ResourceLoader.exists("res://assets/ui/frames/dialogue_box.png") else panel_style("night")
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
	# Gold crest on the box's top edge, centred.
	if ResourceLoader.exists("res://assets/ui/frames/window_crest.png"):
		var crest := TextureRect.new()
		crest.name = "Crest"
		crest.texture = half("window_crest")
		crest.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var crest_size := crest.texture.get_size()
		crest.anchor_left = 0.5; crest.anchor_right = 0.5; crest.anchor_top = 1.0; crest.anchor_bottom = 1.0
		crest.offset_left = -crest_size.x * 0.5; crest.offset_right = crest_size.x * 0.5
		crest.offset_top = -224 - crest_size.y + 3; crest.offset_bottom = -224 + 3
		root.add_child(crest)
		box.visibility_changed.connect(func(): if is_instance_valid(crest): crest.visible = box.visible)
		if not calm():
			crest.modulate.a = 0.0
			crest.create_tween().tween_property(crest, "modulate:a", 1.0, 0.2).set_delay(0.18)
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
	if standee:
		box.get_theme_stylebox("panel").content_margin_left = STANDEE_RECT.end.x - 64.0 + 18.0
	# Speaker ribbon: tied under the card, next to the standee, or on the box's top-left edge.
	var plate := ribbon(root, speaker, true, 21)
	plate.name = "Plate"
	plate.anchor_left = 0.0; plate.anchor_right = 0.0; plate.anchor_top = 1.0; plate.anchor_bottom = 1.0
	var plate_width: float = maxf(plate.get_combined_minimum_size().x, 210.0 if has_card else 0.0)
	var plate_x := 92.0 + 135.0 - plate_width * 0.5 if has_card else (STANDEE_RECT.end.x + 6.0 if standee else 92.0)
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
	# The key that reads on, beside the chevron (follows a rebound Interact key).
	var read_on := keycap(more, "interact", 11)
	read_on.position = Vector2(-30, -1)
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
	if standee and not calm():
		standee.modulate.a = 0.0
		var enter := standee.create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		enter.tween_property(standee, "offset_left", standee.offset_left, 0.36).from(standee.offset_left - 54)
		enter.tween_property(standee, "offset_right", standee.offset_right, 0.36).from(standee.offset_right - 54)
		enter.tween_property(standee, "modulate:a", 1.0, 0.28)
		# Breathing: a slow, barely visible rise of the shoulders.
		var breathe := standee.create_tween().set_loops()
		breathe.tween_property(standee, "scale", Vector2(1.0, 1.007), 1.6).set_trans(Tween.TRANS_SINE)
		breathe.tween_property(standee, "scale", Vector2.ONE, 1.6).set_trans(Tween.TRANS_SINE)
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
	var d := {"root":root, "shade":shade, "box":box, "body":body, "more":more, "choices":choices, "card":card, "plate":plate, "standee":standee}
	# On the window stack as a modal "dialogue": the chat box and toasts step aside while it talks.
	_push_window(root, {"root":root, "shade":shade, "close":null, "id":"dialogue", "action":"", "kind":"dialogue", "modal":true})
	return d

## Where the standee stands on the 1280x800 canvas (bottom-left anchored offsets):
## its lower part sits behind the text box, which hides the waist crop.
const STANDEE_RECT := Rect2(28, -26 - 560, 420, 560)
## The text box's top edge, as an offset from the bottom of the screen.
const DIALOGUE_BOX_TOP := -224.0
## Space kept above a standee's head when the screen is short.
const STANDEE_HEADROOM := 10.0
## Picture path -> the part that is not transparent (Rect2i), measured once.
static var _standee_used: Dictionary = {}

## Stands the illustration on the text box with only its cut-off bottom tucked
## behind it: the lowest 30 % of a waist-up picture (cast villagers, 3:4) or 15 %
## of a squarer head-and-shoulders one (the shadow folk), so a face never sits
## behind the box. When a large interface scale leaves too little room above the
## box, the picture shrinks until the top of the head clears the screen edge.
static func fit_standee(standee: TextureRect) -> void:
	var texture := standee.texture
	if texture == null or not standee.is_inside_tree(): return
	var picture := texture.get_size()
	var head := float(standee_used(texture).position.y)
	var tuck := 0.15 if picture.x/picture.y >= 0.8 else 0.3
	var scale := minf(STANDEE_RECT.size.x/picture.x, STANDEE_RECT.size.y/picture.y)
	var room := standee.get_viewport_rect().size.y+DIALOGUE_BOX_TOP-STANDEE_HEADROOM
	var reach := picture.y*(1.0-tuck)-head
	if reach > 0.0: scale = minf(scale, room/reach)
	var drawn := picture*scale
	var bottom := DIALOGUE_BOX_TOP+drawn.y*tuck
	var left := STANDEE_RECT.position.x+(STANDEE_RECT.size.x-drawn.x)*0.5
	standee.offset_left = left; standee.offset_right = left+drawn.x
	standee.offset_top = bottom-drawn.y; standee.offset_bottom = bottom
	standee.pivot_offset = Vector2(drawn.x*0.5, drawn.y)
	standee.remove_meta("rest_y")

static func standee_used(texture: Texture2D) -> Rect2i:
	var key := texture.resource_path
	if key.is_empty() or not _standee_used.has(key):
		var image := texture.get_image()
		var used := image.get_used_rect() if image else Rect2i(Vector2i.ZERO, Vector2i(texture.get_size()))
		if key.is_empty(): return used
		_standee_used[key] = used
	return _standee_used[key]

## The background-free illustration for a portrait (<dir>/standee/<name>[_mood].png),
## falling back to the neutral one; empty when none was made.
static func standee_path(portrait: String, mood := "neutral") -> String:
	if portrait.is_empty(): return ""
	var base := portrait.get_base_dir().path_join("standee").path_join(portrait.get_file().get_basename())
	if mood != "neutral" and ResourceLoader.exists(base + "_" + mood + ".png"): return base + "_" + mood + ".png"
	return base + ".png" if ResourceLoader.exists(base + ".png") else ""

## The face a line calls for: questions look curious/surprised, exclamations happy.
static func line_mood(line: String) -> String:
	var text := line.strip_edges()
	if text.ends_with("?") or text.ends_with("？") or text.contains("?!") or text.contains("？！"): return "curious"
	for mark in ["!", "！", "♪", "하하", "헤헤", "ㅎㅎ", "哈哈"]:
		if text.contains(mark): return "happy"
	return "neutral"

## Call when a dialogue line starts: the standee changes expression with a small hop.
static func dialogue_line(d: Dictionary, line: String) -> void:
	var standee: TextureRect = d.get("standee")
	if not is_instance_valid(standee): return
	var mood := line_mood(line)
	var path := standee_path(str(standee.get_meta("portrait", "")), mood)
	if path.is_empty() or standee.get_meta("mood", "") == mood: return
	standee.set_meta("mood", mood)
	standee.texture = load(path)
	if calm(): return
	var rest: float = standee.get_meta("rest_y", standee.position.y)
	standee.set_meta("rest_y", rest)
	var hop := standee.create_tween().set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	hop.tween_property(standee, "position:y", rest - (9.0 if mood == "happy" else 5.0), 0.09)
	hop.tween_property(standee, "position:y", rest, 0.16).set_ease(Tween.EASE_IN)

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
		b.add_theme_color_override("font_hover_color", HOVER)
		b.add_theme_color_override("font_focus_color", HOVER)
		for state in ["normal","hover","pressed","disabled"]:
			var box := frame("btn_night_" + state)
			box.content_margin_left = 50
			b.add_theme_stylebox_override(state, box)
		b.add_theme_stylebox_override("hover_pressed", frame("btn_night_pressed"))
		b.add_theme_stylebox_override("focus", frame("focus"))
		for item in ["font_color","font_pressed_color","font_hover_pressed_color"]: b.add_theme_color_override(item, INK)
		var cap := keycap(b, str(index), 12)
		cap.position = Vector2(14, 12)
		# One pick per list: a second press (E and a click together) never runs a choice twice.
		b.pressed.connect(func():
			if d.get("picked", false): return
			d.picked = true
			if action.is_valid(): action.call())
		# Keys on the focused choice: W/S or the arrows move, E, Space or Enter picks, 1-9 pick
		# directly. A key that lands right as the list appears (reading on with E) is ignored.
		b.gui_input.connect(func(event):
			if not event is InputEventKey or not event.pressed: return
			var key := GameSettings.canonical_key(event)
			if key in [KEY_W, KEY_S, KEY_UP, KEY_DOWN]:
				b.accept_event()
				var at := made.find(b) + (-1 if key in [KEY_W, KEY_UP] else 1)
				(made[wrapi(at, 0, made.size())] as Button).grab_focus()
				return
			if event.echo: return
			if key in [KEY_E, KEY_SPACE, KEY_ENTER, KEY_KP_ENTER]:
				b.accept_event()
				# The last line still typing: the key shows it whole (and the guard starts again).
				if dialogue_typing(d): dialogue_skip(d)
				elif dialogue_ready(d):
					# A key pick has no button_down (hover_motion's press note): the choice note here.
					if not d.get("picked", false): sfx("choice")
					b.pressed.emit()
			elif event.keycode >= KEY_1 and event.keycode <= KEY_9:
				var pick: int = event.keycode - KEY_1
				if pick < made.size():
					b.accept_event()
					if not d.get("picked", false): sfx("choice")
					(made[pick] as Button).pressed.emit())
		b.focus_entered.connect(func(): sfx("hover"))
		hover_motion(b, 1.03, Vector2(0.5, 0.5), true, "choice")
		list.add_child(b)
		made.append(b)
		if not calm():
			b.modulate.a = 0.0
			b.create_tween().tween_property(b, "modulate:a", 1.0, 0.18).set_delay(0.05 * index)
	if not made.is_empty(): (made[0] as Button).grab_focus.call_deferred(true)
	d.more.visible = false
	d.picked = false
	d.choices_at = Time.get_ticks_msec()
	return made

## Types the dialogue's current line out over `seconds` (the body's text is already set).
static func dialogue_type(d: Dictionary, seconds: float) -> void:
	var body: Label = d.body
	if d.get("typing") is Tween and (d.typing as Tween).is_valid(): (d.typing as Tween).kill()
	body.visible_ratio = 0.0
	var typing := body.create_tween()
	typing.tween_property(body, "visible_ratio", 1.0, seconds)
	d.typing = typing

static func dialogue_typing(d: Dictionary) -> bool:
	return is_instance_valid(d.get("body")) and (d.body as Label).visible_ratio < 1.0

## The whole line at once (a key while it types), with a very soft page flick (a page turn proper is
## -8 dB). Choices already up wait their guard again.
static func dialogue_skip(d: Dictionary) -> void:
	if d.get("typing") is Tween and (d.typing as Tween).is_valid(): (d.typing as Tween).kill()
	if is_instance_valid(d.get("body")):
		if (d.body as Label).visible_ratio < 1.0: sfx("page", -15.0)
		(d.body as Label).visible_ratio = 1.0
	if d.has("choices_at"): d.choices_at = Time.get_ticks_msec()

## True once the choices have been up long enough for a key to mean "pick this" (not the
## tail of reading on with E or Space).
static func dialogue_ready(d: Dictionary) -> bool:
	return d.has("choices_at") and Time.get_ticks_msec() - int(d.choices_at) >= CHOICE_KEY_DELAY_MS

## E, Space or Enter on the last page when no choice holds the focus (a click elsewhere took
## it): picks the highlighted choice, or the first. False when there is nothing to pick.
static func dialogue_pick(d: Dictionary) -> bool:
	if dialogue_typing(d):
		dialogue_skip(d)
		return true
	if not is_instance_valid(d.get("choices")) or not dialogue_ready(d): return false
	var buttons := (d.choices as Node).get_children().filter(func(child): return child is Button and not child.is_queued_for_deletion())
	if buttons.is_empty(): return false
	var chosen: Button = buttons[0]
	for button in buttons:
		if (button as Button).has_focus(): chosen = button
	# Picked by key (no button_down): the choice note a click on it gives.
	if not d.get("picked", false): sfx("choice")
	chosen.pressed.emit()
	return true

## Shows or hides the "more" chevron (pages left to read).
static func dialogue_more(d: Dictionary, waiting: bool) -> void:
	if is_instance_valid(d.more): d.more.visible = waiting
	if waiting and is_instance_valid(d.choices):
		for child in d.choices.get_children(): child.queue_free()

## Large title-menu button: night glass with a gold edge that warms on hover.
static func menu_button(parent: Node, value: String, callback: Callable, width := 300.0, variant := "NightButton") -> Button:
	var b := Button.new()
	b.text = value
	b.custom_minimum_size = Vector2(width, BTN_MENU)
	b.focus_mode = Control.FOCUS_NONE
	b.theme_type_variation = variant
	b.add_theme_font_override("font", FONT_STRONG)
	b.add_theme_font_size_override("font_size", 19)
	# The UI kit 2 plates ("MenuGoldButton", "MenuNightButton") bring their own hover ink.
	if variant == "NightButton":
		b.add_theme_color_override("font_hover_color", HOVER)
		b.add_theme_color_override("font_focus_color", HOVER)
	b.pressed.connect(callback)
	hover_motion(b, 1.03)
	parent.add_child(b)
	return b

## Text field matching the night title card. A Latin field (a password is always one; ids and
## addresses ask for it) takes keyboard letters only: ImeCaret keeps the Korean IME off while it is
## edited, and Hangul that still arrives becomes the keys that typed it ('안녕' -> 'dkssud');
## `dropped` is called when that happened, so the page can say the keyboard was in Hangul mode.
static func field(parent: Node, placeholder: String, secret := false, dropped := Callable(), latin := false) -> LineEdit:
	var line := LineEdit.new()
	line.placeholder_text = placeholder
	line.secret = secret
	if secret or latin:
		line.set_meta("latin", true)
		line.text_changed.connect(func(value: String):
			if latin_only(line, value) and dropped.is_valid(): dropped.call())
	line.custom_minimum_size = Vector2(340, 44)
	line.theme_type_variation = "NightField"
	line.add_theme_font_size_override("font_size", 16)
	# Enter must not end typing (Godot's default): a failed login or an early Enter left the
	# field focused but deaf until it was clicked again.
	line.keep_editing_on_text_submit = true
	parent.add_child(line)
	if secret or latin: caps_hint(parent, line)
	return line

## CapsLock as last seen in a Latin field: -1 unknown, 0 off, 1 on. Godot cannot read the lock
## itself, so a letter tells it: upper case without Shift (or lower case with it) means the lock
## is on. The CapsLock key flips a known state.
static var caps_lock := -1

static func caps_seen(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo: return
	if event.keycode == KEY_CAPSLOCK:
		if caps_lock != -1: caps_lock = 1 - caps_lock
		return
	var ch := String.chr(event.unicode) if event.unicode > 0 else ""
	if ch.length() != 1 or ch.to_upper() == ch.to_lower(): return
	caps_lock = 1 if (ch == ch.to_upper()) != event.shift_pressed else 0

## A quiet line under a Latin field that says CapsLock is on while the field is being typed in.
static func caps_hint(parent: Node, line: LineEdit) -> Label:
	var hint := label(parent, "⇪ " + TranslationServer.translate("CapsLock이 켜져 있어요"), 13, Color("ffd9a0"))
	hint.name = "CapsHint"
	hint.visible = false
	var refresh := func(): hint.visible = line.has_focus() and caps_lock == 1
	line.gui_input.connect(func(event):
		caps_seen(event)
		refresh.call())
	line.focus_entered.connect(refresh)
	line.focus_exited.connect(refresh)
	return hint

## Hangul typed on a Korean 2-set keyboard back to the keys pressed, everything else outside
## printable ASCII taken out; true when the field had to change. Shift is not known for plain
## letters (the IME does not say), so only the doubled consonants and two vowels come back upper case.
static func latin_only(line: LineEdit, value: String) -> bool:
	var kept := hangul_keys(value)
	if kept == value: return false
	var caret := line.caret_column + (kept.length() - value.length())
	line.text = kept
	line.caret_column = clampi(caret, 0, kept.length())
	return true

const HANGUL_LEADS := ["r","R","s","e","E","f","a","q","Q","t","T","d","w","W","c","z","x","v","g"]
const HANGUL_VOWELS := ["k","o","i","O","j","p","u","P","h","hk","ho","hl","y","n","nj","np","nl","b","m","ml","l"]
const HANGUL_TAILS := ["","r","R","rt","s","sw","sg","e","f","fr","fa","fq","ft","fx","fv","fg","a","q","qt","t","T","d","w","c","z","x","v","g"]
## Compatibility jamo U+3131..U+3163 (what the IME shows for a lone letter).
const HANGUL_JAMO := ["r","R","rt","s","sw","sg","e","E","f","fr","fa","fq","ft","fx","fv","fg","a","q","Q","qt","t","T","d","w","W","c","z","x","v","g",
	"k","o","i","O","j","p","u","P","h","hk","ho","hl","y","n","nj","np","nl","b","m","ml","l"]

static func hangul_keys(value: String) -> String:
	var out := ""
	for ch in value:
		var code := ch.unicode_at(0)
		if code >= 0x20 and code < 0x7F: out += ch
		elif code >= 0xAC00 and code <= 0xD7A3:
			var index := code - 0xAC00
			out += HANGUL_LEADS[index / 588] + HANGUL_VOWELS[(index % 588) / 28] + HANGUL_TAILS[index % 28]
		elif code >= 0x3131 and code <= 0x3163: out += HANGUL_JAMO[code - 0x3131]
	return out
