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

# ------------------------------------------------------------------ names on hover

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
	var stars := numbers(label(coins, "0", 17, Color("ffe08a")), 17)
	stars.custom_minimum_size.x = 34
	name_tip(stars, star_name)
	var gap := Control.new(); gap.custom_minimum_size.x = 6; gap.mouse_filter = Control.MOUSE_FILTER_IGNORE; coins.add_child(gap)
	coins.add_child(name_tip(icon("res://assets/ui/leaf.svg", 22), leaf_name))
	var leaves := numbers(label(coins, "0", 17, Color("c8ec9f")), 17)
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

## Square slots with an icon, a key cap and a caption on a glass tray. With a
## fold_id a chevron key at the tray's right end slides it below the screen.
static func hotbar(ui: Control, slots: Array, y: float, fold_id := "") -> HBoxContainer:
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
		name_tip(b, slot.label, str(slot.get("key", "")))
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
	if not fold_id.is_empty(): fold_dock(ui, fold_id, [tray, bar], 640.0 + width * 0.5, y + 6 + (SLOT + 8) * 0.5)
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
	tooltip_theme(t)
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
		standee.offset_left = STANDEE_RECT.position.x; standee.offset_right = STANDEE_RECT.end.x
		standee.offset_top = STANDEE_RECT.position.y; standee.offset_bottom = STANDEE_RECT.end.y
		standee.pivot_offset = Vector2(STANDEE_RECT.size.x * 0.5, STANDEE_RECT.size.y)
		standee.mouse_filter = Control.MOUSE_FILTER_IGNORE
		standee.set_meta("portrait", portrait)
		standee.set_meta("mood", "neutral")
		root.add_child(standee)
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
	return {"root":root, "shade":shade, "box":box, "body":body, "more":more, "choices":choices, "card":card, "plate":plate, "standee":standee}

## Where the standee stands on the 1280x800 canvas (bottom-left anchored offsets):
## its lower part sits behind the text box, which hides the waist crop.
const STANDEE_RECT := Rect2(28, -26 - 560, 420, 560)

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
