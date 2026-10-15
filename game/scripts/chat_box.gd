extends Control
## The always-on chat box, bottom left in every place (social_hud.gd owns it): a header (the
## 함께하기 key with its badge, the 채팅창 title, the channel chip, the unread pill, the fold key),
## the log, and the field.
## Enter focuses the field (social_hud.gd hears it after the place's keys), Enter sends and gives
## the keys back to walking, an empty Enter or Esc just gives them back, and a click in the world
## does too (and is used up, so it does not click furniture). The Korean IME commits its last
## syllable before the line is read (one frame). While the field has focus the walker stands
## still, and its movement keys are released when it lets go (no key stuck down).
## Quiet for 8 s, the log's glass fades out and the text after it; a new line, the mouse or the
## field brings it back. U folds it to the header like the other HUD panels (fold id "chat").
## Sound: a soft tab as the field takes the keys and another as the player hands them back (empty
## Enter, Esc, a click in the world); a line sent is heard as chat_out (social_hud.gd send), not the
## tab; a window or a fold taking the keys away is heard as itself. The 함께하기 key's press is the
## drawer's own slide (no click before it).
const RpgUi = preload("res://scripts/rpg_ui.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const WIDTH := 328.0
const HEIGHT := 226.0
const IDLE := 8.0
const TEXT_LINGER := 4.0
const MOVE_ACTIONS := ["move_forward", "move_back", "move_left", "move_right", "run"]
const CROWN := "res://assets/ui/icons/crown.png"
const CHANNEL_NAMES := {"local":"마을", "party":"파티", "global":"전체", "whisper":"귓속말"}
const CHANNEL_COLOURS := {"local":RpgUi.INK, "party":RpgUi.TEAL, "global":RpgUi.CHAT_GLOBAL, "whisper":RpgUi.CHAT_WHISPER, "system":RpgUi.SOFT}

var hub: Node
var glass: PanelContainer
var log_view: RichTextLabel
var field: LineEdit
var people_key: Button
var channel_key: Button
var fold_key: Button
var body: VBoxContainer
var unread_pill: Label
var title: Label
## The channel a line goes out on, and the whisper partner when it is "whisper".
var channel := "local"
var whisper_to := ""
var idle := 0.0
var folded := false
var bottom := 786.0

func _ready() -> void:
	name = "ChatBox"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size = Vector2(WIDTH, HEIGHT)
	size = custom_minimum_size
	glass = PanelContainer.new()
	glass.name = "Glass"
	var style := RpgUi.panel_style("night_plain")
	style.content_margin_left = 10
	style.content_margin_right = 10
	style.content_margin_top = 8
	style.content_margin_bottom = 8
	glass.add_theme_stylebox_override("panel", style)
	glass.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	# The glass ends a click (62): the log's links still answer first, nothing goes to the world.
	glass.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(glass)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 6)
	glass.add_child(column)
	var head := HBoxContainer.new()
	head.name = "Head"
	head.add_theme_constant_override("separation", 6)
	column.add_child(head)
	people_key = Button.new()
	people_key.name = "People"
	people_key.theme_type_variation = "HudSlot"
	people_key.custom_minimum_size = Vector2(34, 34)
	people_key.focus_mode = Control.FOCUS_NONE
	people_key.icon = RpgUi.icon_texture("people")
	people_key.expand_icon = true
	RpgUi.name_tip(people_key, tr("함께하기"), RpgUi.key_text("social"))
	people_key.pressed.connect(func(): hub.toggle_window())
	RpgUi.hover_motion(people_key, 1.1, Vector2(0.5, 0.5), true, "")
	head.add_child(people_key)
	title = RpgUi.label(head, tr("채팅창"), 14, RpgUi.GOLD)
	title.name = "Title"
	title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	channel_key = Button.new()
	channel_key.name = "Channel"
	channel_key.theme_type_variation = "GhostButton"
	channel_key.focus_mode = Control.FOCUS_NONE
	channel_key.custom_minimum_size = Vector2(0, 30)
	channel_key.add_theme_font_size_override("font_size", 13)
	channel_key.tooltip_text = tr("보낼 곳 바꾸기")
	channel_key.pressed.connect(next_channel)
	head.add_child(channel_key)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	head.add_child(spacer)
	# New lines while folded or faded: a gold pill that hops when the count grows.
	var pill := PanelContainer.new()
	pill.name = "UnreadPill"
	var pill_style := StyleBoxFlat.new()
	pill_style.bg_color = RpgUi.GOLD
	pill_style.set_corner_radius_all(11)
	pill_style.content_margin_left = 8
	pill_style.content_margin_right = 8
	pill_style.content_margin_top = 1
	pill_style.content_margin_bottom = 1
	pill.add_theme_stylebox_override("panel", pill_style)
	pill.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	pill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pill.visible = false
	head.add_child(pill)
	unread_pill = RpgUi.label(pill, "", 12, RpgUi.PAPER_INK, false)
	unread_pill.name = "Unread"
	fold_key = RpgUi.fold_toggle(head, "chat", Vector2.DOWN, 26.0)
	body = VBoxContainer.new()
	body.name = "Body"
	body.add_theme_constant_override("separation", 6)
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(body)
	log_view = RichTextLabel.new()
	log_view.name = "Log"
	log_view.bbcode_enabled = true
	log_view.scroll_following = true
	log_view.selection_enabled = false
	log_view.fit_content = false
	log_view.size_flags_vertical = Control.SIZE_EXPAND_FILL
	log_view.add_theme_font_override("normal_font", RpgUi.FONT_BODY)
	log_view.add_theme_font_override("bold_font", RpgUi.FONT_STRONG)
	log_view.add_theme_font_size_override("normal_font_size", 14)
	log_view.add_theme_font_size_override("bold_font_size", 14)
	log_view.add_theme_color_override("default_color", RpgUi.INK)
	log_view.add_theme_constant_override("outline_size", 4)
	log_view.add_theme_color_override("font_outline_color", Color(RpgUi.OUTLINE, 0.85))
	log_view.meta_clicked.connect(_link)
	log_view.mouse_filter = Control.MOUSE_FILTER_PASS
	body.add_child(log_view)
	field = RpgUi.field(body, tr("Enter 로 대화"))
	field.name = "Field"
	field.custom_minimum_size = Vector2(0, 36)
	field.add_theme_font_size_override("font_size", 14)
	field.keep_editing_on_text_submit = false
	field.max_length = 160
	field.focus_mode = Control.FOCUS_CLICK
	field.text_submitted.connect(_submitted)
	field.gui_input.connect(_field_key)
	field.focus_entered.connect(_took_keys)
	field.focus_exited.connect(_gave_keys)
	RpgUi.foldable(self, "chat", _fold)
	mouse_entered.connect(wake)
	glass.mouse_entered.connect(wake)
	refresh_channels()
	place_for("village")
	visibility_changed.connect(_sync_processing)
	_sync_processing()

func _sync_processing() -> void:
	# Hidden chat already freezes its idle clock; skip its empty frame callback too.
	set_process(is_visible_in_tree())

## The same bottom-left spot in every place (village, rooms and expeditions keep their hotbars at the
## bottom centre, U-WP-10/11); `kind` stays for a place that needs its own.
func place_for(kind: String) -> void:
	bottom = {}.get(kind, 786.0)
	position = Vector2(14, bottom - HEIGHT)
	size = Vector2(WIDTH, HEIGHT)
	RpgUi.pin(self, 0.0, 1.0)
	wake()

func _fold(shut: bool, _animate: bool) -> void:
	folded = shut
	body.visible = not shut
	glass.offset_top = HEIGHT - 50.0 if shut else 0.0
	if shut: release()
	update_badge()
	wake()

## True while the player can see new lines (open, shown, not faded out).
func reading() -> bool:
	return is_visible_in_tree() and not folded

func can_focus() -> bool:
	if not is_visible_in_tree() or folded or not is_instance_valid(hub.place): return false
	var place: Node = hub.place
	if "preview" in place and is_instance_valid(place.get("preview")): return false
	if "placement_mode" in place and bool(place.get("placement_mode")): return false
	if "village_modal" in place and is_instance_valid(place.get("village_modal")): return false
	if "talk_box" in place and is_instance_valid(place.get("talk_box")): return false
	return not RpgUi.modal_open()

func focus() -> void:
	if not can_focus(): return
	field.grab_focus()
	field.edit()
	wake()

## Gives the keys back; sound: the player's own letting go (a soft tab), not a window or a fold.
func release(sound := false) -> void:
	if not is_instance_valid(field) or not field.has_focus(): return
	field.release_focus()
	if sound: RpgUi.sfx("tab", -16.0)

## Enter in the field: wait one frame so the IME's last syllable is in, send, give the keys back
## (a line going out is heard as chat_out, social_hud.gd send; an empty Enter as the tab).
func _submitted(_value: String) -> void:
	await get_tree().process_frame
	var line := field.text
	field.clear()
	var sending := not line.strip_edges().is_empty()
	release(not sending)
	if sending: hub.send(line, channel)

func _field_key(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		field.clear()
		release(true)
		field.accept_event()

## A click anywhere outside the box while typing gives the keys back and is used up.
func _input(event: InputEvent) -> void:
	if not is_instance_valid(field) or not field.has_focus(): return
	if event is InputEventMouseButton and event.pressed and not get_global_rect().has_point(get_global_mouse_position()):
		release(true)
		get_viewport().set_input_as_handled()

func _took_keys() -> void:
	RpgUi.sfx("tab", -14.0)
	wake()
	var place: Node = hub.place if is_instance_valid(hub.place) else null
	if place and "player" in place and is_instance_valid(place.get("player")): place.player.controls_enabled = false

func _gave_keys() -> void:
	# Letters typed for the line pressed W/A/S/D too: let go of them so the walker does not start.
	for action in MOVE_ACTIONS:
		if InputMap.has_action(action): Input.action_release(action)
	var place: Node = hub.place if is_instance_valid(hub.place) else null
	if place and "player" in place and is_instance_valid(place.get("player")) and place.has_method("world_movement_allowed"):
		place.player.controls_enabled = place.world_movement_allowed()
	idle = 0.0

# ------------------------------------------------------------------ channels

func channels() -> Array:
	var out := ["local"]
	var party = hub.overview.get("party") if is_instance_valid(hub) else null
	if party is Dictionary and not party.is_empty(): out.append("party")
	if is_instance_valid(hub) and hub.chat2() and bool(hub.health.get("global_chat", false)): out.append("global")
	if not whisper_to.is_empty(): out.append("whisper")
	return out

func next_channel() -> void:
	var list := channels()
	channel = list[(list.find(channel) + 1) % list.size()]
	refresh_channels()
	RpgUi.sfx("click", -12.0)

func refresh_channels() -> void:
	if not is_instance_valid(channel_key): return
	if not channel in channels(): channel = "local"
	var label: String = tr(CHANNEL_NAMES.get(channel, "마을"))
	if channel == "whisper": label = tr("귓속말 · %s") % whisper_to
	channel_key.text = "▸ " + label
	channel_key.add_theme_color_override("font_color", CHANNEL_COLOURS.get(channel, RpgUi.INK))

## Whisper to `username`: the channel turns to them and the field opens.
func whisper(username: String) -> void:
	whisper_to = username
	channel = "whisper"
	refresh_channels()
	focus()

# ------------------------------------------------------------------ log

func redraw() -> void:
	if not is_instance_valid(log_view) or not is_instance_valid(hub): return
	var out := PackedStringArray()
	var me: String = hub.my_name()
	for line in hub.lines:
		out.append(format(line, me))
	log_view.text = "\n".join(out)
	refresh_channels()
	update_badge()
	wake()

## One line in BBCode, user text escaped: [tag] name: text, coloured by channel.
func format(line: Dictionary, me: String) -> String:
	var kind := str(line.get("channel", "local"))
	var text := escape(str(line.get("text", "")))
	if kind == "system": return "[color=#%s]· %s[/color]" % [RpgUi.SOFT.to_html(false), text]
	var who := str(line.get("username", ""))
	var name_colour: Color = RpgUi.HOVER if who == me else RpgUi.GOLD
	var tag := ""
	if kind in ["party", "global"]: tag = "[%s] " % tr(CHANNEL_NAMES[kind])
	if kind == "whisper":
		var to := str(line.get("to_name", ""))
		tag = (tr("[→%s] ") % to) if who == me else tr("[귓] ")
	tag = escape(tag)
	var colour: Color = CHANNEL_COLOURS.get(kind, RpgUi.INK)
	var pending := " …" if line.get("pending", false) else ""
	var name_part := "[url=who:%s][b][color=#%s]%s[/color][/b][/url]" % [escape(who).uri_encode(), name_colour.to_html(false), escape(who)]
	# The owner of the village (or home) being visited speaks under a crown in the place's chat.
	var host := str(hub.overview.get("host_id", ""))
	if kind == "local" and not host.is_empty() and str(line.get("user_id", "")) == host:
		name_part = "[img=16x16]%s[/img]" % CROWN + name_part
	return "[color=#%s]%s%s: %s%s[/color]" % [colour.to_html(false), tag, name_part, text, pending]

static func escape(value: String) -> String:
	return value.replace("[", "[lb]")

## A name in the log: whisper to them.
func _link(meta) -> void:
	var value := str(meta)
	if value.begins_with("who:"):
		var who := value.substr(4).uri_decode()
		if not who.is_empty() and who != hub.my_name(): whisper(who)

func update_badge() -> void:
	if not is_instance_valid(people_key) or not is_instance_valid(hub): return
	var invites: Array = hub.overview.get("invites", []) if hub.overview.get("invites") is Array else []
	RpgUi.badge(people_key, int(hub.counts.requests) + int(hub.counts.knocks) + invites.size())
	if reading(): hub.unread = 0
	var pill: Control = unread_pill.get_parent()
	var text := tr("새 대화 %d") % hub.unread
	if hub.unread > 0 and (not pill.visible or unread_pill.text != text): _hop(pill)
	pill.visible = hub.unread > 0
	unread_pill.text = text

func _hop(pill: Control) -> void:
	if RpgUi.calm(): return
	await get_tree().process_frame
	if not is_instance_valid(pill): return
	pill.pivot_offset = pill.size * 0.5
	var tween := pill.create_tween()
	tween.tween_property(pill, "scale", Vector2(1.18, 1.18), 0.09).set_trans(Tween.TRANS_SINE)
	tween.tween_property(pill, "scale", Vector2.ONE, 0.18).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)

# ------------------------------------------------------------------ fade

func wake() -> void:
	idle = 0.0
	if is_instance_valid(glass):
		glass.self_modulate.a = 1.0
		body.modulate.a = 1.0

func _process(delta: float) -> void:
	if not is_visible_in_tree(): return
	if field.has_focus() or get_global_rect().has_point(get_global_mouse_position()):
		if idle > 0.0: wake()
		return
	idle += delta
	if RpgUi.calm(): return
	if idle > IDLE:
		var t := clampf((idle - IDLE) / 0.6, 0.0, 1.0)
		glass.self_modulate.a = lerpf(1.0, 0.0, t)
		body.modulate.a = lerpf(1.0, 0.55, t)
	if idle > IDLE + TEXT_LINGER:
		var t := clampf((idle - IDLE - TEXT_LINGER) / 0.8, 0.0, 1.0)
		body.modulate.a = lerpf(0.55, 0.0, t)
