## The owner's front door, a small HUD card in their own home while friends can visit (multiplayer
## on; server/home_access.py): a padlock that keeps new guests out (POST /v1/home/lock; the ones
## inside stay) and who is inside, each with 내보내기 (POST /v1/home/eject: out at once, back no
## sooner than 10 minutes). The guest's side lives here too: show_refusal(), the card a guest sees
## when the home closes on them, before they walk out.
## studio.gd: attach(self) once the HUD stands, feed(self, reply) on every presence answer.
extends PanelContainer

const RpgUi = preload("res://scripts/rpg_ui.gd")
const DoorAudio = preload("res://scripts/door_audio.gd")
const AvatarLook = preload("res://scripts/avatar_look.gd")
const HomeDoor = preload("res://scripts/home_door.gd")
const SELF := "res://scripts/home_door_panel.gd"
const FOLD_ID := "home_door"
const LOCK_ICON := "res://assets/ui/icons/lock.png"
## The padlock art (128 px): the shackle is rows 0-45, the body from 46; opening swings the shackle
## about its right leg (x 89) and lifts it, as the painted open padlocks do.
const SHACKLE_ROWS := 46.0
const PIVOT_X := 89.0
const OPEN_ANGLE := 0.42
const OPEN_LIFT := 4.0
const PAD := 38.0
const WIDTH := 236.0
## Under the location card and the home's objective card, on the right edge (design canvas).
const TOP := 196.0
## A presence answer sent before a lock or a send-out landed still tells the old state: how long the
## change outranks them.
const SETTLE_MS := 2500
## How long a guest's card stays before they walk out.
const REFUSAL_HOLD := 1.8

var room: Node
var locked := false
var busy := false
var changed_ms := -100000
var pad: Control
var shackle: TextureRect
var lock_key: Button
var state_label: Label
var count_box: HBoxContainer
var count_label: Label
var list: VBoxContainer
var empty_label: Label
## Guest id -> their row; ids sent out lately (ticks), so a stale answer does not bring a row back.
var rows := {}
var sent_out := {}
var ask: Dictionary = {}

## The card for the owner in their own home with multiplayer on; null anywhere else.
static func attach(owner_room: Node) -> Node:
	if str(owner_room.get("room")) != "home" or not str(owner_room.get("visit_host")).is_empty() or not owner_room.get("social_session") or owner_room.get("public_room"): return null
	if not is_instance_valid(owner_room.get("api")) or str(owner_room.api.token).is_empty(): return null
	var hud = owner_room.get("hud")
	if not hud is Control or not is_instance_valid(hud) or hud.has_node("HomeDoorPanel"): return null
	var panel: Node = load(SELF).new()
	panel.room = owner_room
	hud.add_child(panel)
	panel.build()
	return panel

## Hands a presence answer to the room's card, when it has one.
static func feed(owner_room: Node, reply: Dictionary) -> void:
	var hud = owner_room.get("hud")
	var panel = hud.get_node_or_null("HomeDoorPanel") if hud is Control and is_instance_valid(hud) else null
	if panel: panel.ingest(reply)

func build() -> void:
	name = "HomeDoorPanel"
	# Only the keys take the mouse: a click on the glass walks the room as anywhere else.
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	theme = RpgUi.night_theme()
	add_theme_stylebox_override("panel", RpgUi.panel_style("night", 12))
	custom_minimum_size.x = WIDTH
	var column := _box(VBoxContainer.new(), 6)
	add_child(column)
	var head := _box(HBoxContainer.new(), 8)
	column.add_child(head)
	lock_key = Button.new()
	lock_key.name = "LockKey"
	lock_key.theme_type_variation = "GhostButton"
	lock_key.focus_mode = Control.FOCUS_NONE
	lock_key.custom_minimum_size = Vector2(PAD + 8, PAD + 8)
	lock_key.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	head.add_child(lock_key)
	pad = Control.new()
	pad.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pad.position = Vector2(4, 4)
	pad.size = Vector2(PAD, PAD)
	pad.pivot_offset = pad.size * 0.5
	lock_key.add_child(pad)
	var art: Texture2D = load(LOCK_ICON)
	var k := PAD / 128.0
	shackle = _piece(art, Rect2(0, 0, 128, SHACKLE_ROWS), k)
	shackle.name = "Shackle"
	shackle.pivot_offset = Vector2(PIVOT_X * k, SHACKLE_ROWS * k)
	var body := _piece(art, Rect2(0, SHACKLE_ROWS - 2.0, 128, 130.0 - SHACKLE_ROWS), k)
	body.name = "Body"
	body.position.y = (SHACKLE_ROWS - 2.0) * k
	# The padlock has its own snap and click (show_lock), not the button press.
	RpgUi.hover_motion(lock_key, 1.08, Vector2(0.5, 0.5), true, "")
	lock_key.pressed.connect(toggle_lock)
	var words := _box(VBoxContainer.new(), 0)
	words.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	# The words take the head's width, so the count sits by the fold key (fold_card's spacer).
	words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	words.size_flags_stretch_ratio = 20.0
	head.add_child(words)
	RpgUi.label(words, tr("현관문"), 15, RpgUi.GOLD)
	state_label = RpgUi.label(words, "", 13, RpgUi.LEAF_LIGHT)
	state_label.name = "State"
	# Folded, the head still tells how many are inside.
	count_box = _box(HBoxContainer.new(), 3)
	count_box.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	head.add_child(count_box)
	count_box.add_child(RpgUi.icon("res://assets/ui/icons/people.png", 20))
	count_label = RpgUi.numbers(RpgUi.label(count_box, "0", 14, RpgUi.INK), 14)
	RpgUi.name_tip(count_box, tr("손님"))
	var under := _box(VBoxContainer.new(), 6)
	column.add_child(under)
	RpgUi.divider(under, Color(RpgUi.GOLD, .45))
	list = _box(VBoxContainer.new(), 4)
	list.name = "Guests"
	under.add_child(list)
	empty_label = RpgUi.label(under, tr("손님이 없어요"), 13, Color(RpgUi.SOFT, .7), false)
	empty_label.name = "Empty"
	RpgUi.fold_card(self, head, under, FOLD_ID)
	show_lock(false, false)
	count_box.visible = false
	position = Vector2(RpgUi.CANVAS.x - 18.0 - WIDTH, TOP)
	RpgUi.pin(self, 1.0, 0.0)
	if not RpgUi.calm(): RpgUi.slide_in(self, Vector2(30, 0))

## A container that lets clicks fall through to the room.
func _box(c: BoxContainer, gap: int) -> BoxContainer:
	c.add_theme_constant_override("separation", gap)
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return c

## One part of the padlock art, drawn at k of its size inside the pad.
func _piece(art: Texture2D, region: Rect2, k: float) -> TextureRect:
	var part := AtlasTexture.new()
	part.atlas = art
	part.region = region
	var image := TextureRect.new()
	image.texture = part
	image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	image.stretch_mode = TextureRect.STRETCH_SCALE
	image.mouse_filter = Control.MOUSE_FILTER_IGNORE
	image.size = region.size * k
	pad.add_child(image)
	return image

## A presence answer: the lock as the server keeps it (unless a change of ours is settling) and the
## guests inside (space.players but the owner).
func ingest(reply: Dictionary) -> void:
	visible = str(room.get("room")) == "home"
	var door = reply.get("home")
	if door is Dictionary and bool(door.get("owner", false)) and not busy and Time.get_ticks_msec() - changed_ms > SETTLE_MS:
		if bool(door.get("locked", false)) != locked: show_lock(bool(door.locked), false)
	var space = reply.get("space")
	if not space is Dictionary: return
	var me := str(reply.get("self_id", ""))
	var guests := {}
	for record in space.get("players", []):
		var id := str(record.get("id", ""))
		if id == me or Time.get_ticks_msec() - int(sent_out.get(id, -100000)) < SETTLE_MS: continue
		guests[id] = record
	for id in rows.keys():
		if not guests.has(id): drop_row(id)
	for id in guests:
		if not rows.has(id): add_row(id, guests[id])
	show_count()

func show_count() -> void:
	count_label.text = str(rows.size())
	count_box.visible = not rows.is_empty()
	empty_label.visible = rows.is_empty()

## A guest's row: their face, their name and 내보내기. Fades in.
func add_row(id: String, record: Dictionary) -> void:
	var row := _box(HBoxContainer.new(), 8)
	var username := str(record.get("username", ""))
	row.name = "Guest_" + username.validate_node_name()
	list.add_child(row)
	RpgUi.avatar_thumb(row, str(AvatarLook.normalize(record.get("avatar", {})).get("character", "explorer")), 30.0)
	var who := RpgUi.label(row, username, 14, RpgUi.INK)
	who.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	who.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	who.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	who.clip_text = true
	var out := RpgUi.button(row, tr("내보내기"), func(): ask_eject(id, username), "danger", "sm")
	out.name = "Eject"
	out.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.set_meta("key", out)
	rows[id] = row
	if not RpgUi.calm():
		row.modulate.a = 0.0
		row.create_tween().tween_property(row, "modulate:a", 1.0, 0.25)

func drop_row(id: String) -> void:
	var row: Control = rows.get(id)
	rows.erase(id)
	if not is_instance_valid(row): return
	if RpgUi.calm(): row.queue_free(); return
	var tw := row.create_tween()
	tw.tween_property(row, "modulate:a", 0.0, 0.2)
	tw.tween_callback(row.queue_free)

## The padlock as `shut`: the shackle drops into the body (or swings up out of it), the state word
## turns, and with `animate` the padlock punches, tips and clicks.
func show_lock(shut: bool, animate: bool) -> void:
	locked = shut
	state_label.text = tr("잠금") if shut else tr("열림")
	state_label.add_theme_color_override("font_color", RpgUi.WARM if shut else RpgUi.LEAF_LIGHT)
	RpgUi.name_tip(lock_key, tr("잠금 풀기") if shut else tr("문 잠그기"))
	var lift := Vector2(0, 0 if shut else -OPEN_LIFT)
	var angle := 0.0 if shut else OPEN_ANGLE
	if not animate or RpgUi.calm() or not is_inside_tree():
		shackle.position = lift
		shackle.rotation = angle
		return
	var swing := shackle.create_tween().set_parallel(true).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	swing.tween_property(shackle, "position", lift, 0.22)
	swing.tween_property(shackle, "rotation", angle, 0.22)
	var punch := pad.create_tween()
	punch.tween_property(pad, "scale", Vector2.ONE * 1.22, 0.08)
	punch.tween_property(pad, "scale", Vector2.ONE, 0.24).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	var tip := pad.create_tween()
	tip.tween_property(pad, "rotation", -0.2 if shut else 0.2, 0.07)
	tip.tween_property(pad, "rotation", 0.0, 0.45).set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)
	RpgUi.pop_in(state_label, 0.2, 0.8)
	if shut:
		DoorAudio.play(room, "locked", "home", Vector3.INF, -2.0)
		RpgUi.sfx("snap", -6.0)
	else: RpgUi.sfx("unlock", -9.0)

## A refused change: the padlock shakes in place.
func rattle() -> void:
	RpgUi.sfx("deny", -6.0)
	if RpgUi.calm(): return
	var tw := pad.create_tween()
	for side in [0.16, -0.14, 0.1, -0.05, 0.0]: tw.tween_property(pad, "rotation", side, 0.05)

## The padlock key: one request at a time (the key waits, greyed, until the answer).
func toggle_lock() -> void:
	if busy: return
	busy = true
	lock_key.disabled = true
	pad.modulate.a = 0.6
	var answer: Dictionary = await room.api.post("/v1/home/lock", room.api.mutation({"locked": not locked}))
	if not is_inside_tree(): return
	busy = false
	lock_key.disabled = false
	pad.modulate.a = 1.0
	if not answer.ok:
		rattle()
		return
	changed_ms = Time.get_ticks_msec()
	show_lock(bool(answer.data.get("locked", not locked)), true)

## 내보내기 asks first: a small night card naming the guest (Esc or 취소 keeps them).
func ask_eject(id: String, username: String) -> void:
	if not ask.is_empty() and is_instance_valid(ask.root): RpgUi.close_window(ask, false, false)
	ask = RpgUi.window(room, tr("손님 내보내기"), {"kind":"night", "width":400, "place":"centre", "scroll":false,
		"id":"home_eject", "icon":"res://assets/ui/icons/leave.png"})
	var line := RpgUi.label(ask.body, tr("%s님을 집 밖으로 안내할까요?") % username, 16)
	line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	line.custom_minimum_size.x = 340
	var later := HBoxContainer.new()
	later.add_theme_constant_override("separation", 6)
	ask.body.add_child(later)
	later.add_child(RpgUi.icon("res://assets/ui/icons/clock.png", 18))
	RpgUi.label(later, tr("10분 동안 다시 들어올 수 없어요."), 13, RpgUi.SOFT, false)
	var keys := HBoxContainer.new()
	keys.alignment = BoxContainer.ALIGNMENT_END
	keys.add_theme_constant_override("separation", RpgUi.GAP)
	ask.body.add_child(keys)
	var w := ask
	var send := func() -> void:
		RpgUi.close_window(w, true, false)
		eject(id)
	RpgUi.button(keys, tr("취소"), func(): RpgUi.close_window(w), "night").name = "Cancel"
	RpgUi.button(keys, tr("내보내기"), send, "danger").name = "Confirm"

## Sends a guest out: their row leaves at once and the door shuts behind them.
func eject(id: String) -> void:
	var row: Control = rows.get(id)
	var key: Button = row.get_meta("key") if is_instance_valid(row) else null
	if key:
		if key.disabled: return
		key.disabled = true
	var answer: Dictionary = await room.api.post("/v1/home/eject", room.api.mutation({"user_id": id}))
	if not is_inside_tree(): return
	if not answer.ok:
		if is_instance_valid(key): key.disabled = false
		room.refuse(str(answer.get("error", "")))
		return
	sent_out[id] = Time.get_ticks_msec()
	drop_row(id)
	show_count()
	DoorAudio.door_close(room, "home", door_at(), 0.35)

## The room's front door in the world (for its sounds), else INF (flat).
func door_at() -> Vector3:
	var spec = room.get("room_spec")
	if not spec is Dictionary or not spec.has("size"): return Vector3.INF
	return Vector3(float(spec.get("door_x", 0.0)), 1.0, float(spec.size.y) * 0.5)

## A guest in a friend's home the door just closed on (studio.gd share_presence: the presence answer's
## home block not open): a short card says why, then the guest walks out (room.leave()). Once.
static func show_refusal(guest_room: Node, door, owner_name: String) -> void:
	if not is_instance_valid(guest_room) or guest_room.get_node_or_null("HomeRefusal") or guest_room.get("leaving"): return
	var reason := str(door.get("reason", "")) if door is Dictionary else ""
	var who := owner_name if not owner_name.is_empty() else guest_room.tr("친구")
	var line := HomeDoor.refusal(door)
	var art := "res://assets/ui/icons/lock.png"
	match reason:
		"ejected":
			line = guest_room.tr("%s님이 집 밖으로 안내했어요") % who
			art = "res://assets/ui/icons/leave.png"
		"owner_away":
			line = guest_room.tr("%s님이 집을 나가서 함께 나왔어요") % who
			art = "res://assets/ui/icons/leave.png"
	var w := RpgUi.window(guest_room, guest_room.tr("%s님의 집") % who, {"kind":"night", "width":440, "place":"centre",
		"scroll":false, "closable":false, "sound":false, "id":"home_refusal", "icon":"res://assets/ui/icons/home.png", "dim":0.55})
	var face := HBoxContainer.new()
	face.add_theme_constant_override("separation", 14)
	w.body.add_child(face)
	var mark := RpgUi.icon(art, 52)
	face.add_child(mark)
	var words := RpgUi.label(face, line, 18, RpgUi.INK)
	words.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	words.custom_minimum_size.x = 300
	words.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	words.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var minutes := HomeDoor.minutes_left(door) if reason == "ejected" else 0
	if minutes > 0:
		var later := HBoxContainer.new()
		later.add_theme_constant_override("separation", 6)
		later.alignment = BoxContainer.ALIGNMENT_END
		w.body.add_child(later)
		later.add_child(RpgUi.icon("res://assets/ui/icons/clock.png", 18))
		RpgUi.label(later, guest_room.tr("%d분 뒤에 다시 들어갈 수 있어요.") % minutes, 13, RpgUi.SOFT, false)
	RpgUi.sfx("leave", -4.0)
	# The mark steps toward the door while the card holds.
	if not RpgUi.calm():
		var step := mark.create_tween().set_loops(3)
		step.tween_property(mark, "position:x", 6.0, 0.22).set_trans(Tween.TRANS_SINE).as_relative()
		step.tween_property(mark, "position:x", -6.0, 0.22).set_trans(Tween.TRANS_SINE).as_relative()
	var held: WeakRef = weakref(guest_room)
	guest_room.get_tree().create_timer(REFUSAL_HOLD).timeout.connect(func():
		var node = held.get_ref()
		if node != null and is_instance_valid(node) and node.is_inside_tree(): node.leave())
