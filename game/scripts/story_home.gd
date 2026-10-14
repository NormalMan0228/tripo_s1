extends Node
## The opening story chapter "마을의 첫 선물" at home (server/story.py keeps the progress; the
## village side is story.gd). A new maker's first room is their own home, and a welcome letter
## lies on the desk by the front door: a soft glow, a slow bob and a few sparkles draw the eye,
## E opens it as a parchment card (the server marks it read), and the home's small objective card
## turns to "카페에 인사하러 가기" while the door shines. Walking out, the village guides the way.
## Only for the owner's own home; the letter stays on the desk (read) until the chapter is done.
##   var home := StoryHome.new(); room.add_child(home); home.setup(room)   # studio.gd, room "home"
##   home.use(record) -> bool     # studio.use_decor: true when E was the letter's
##   home.chip(record) -> String  # the key chip's words for the letter ("" for anything else)
const RpgUi = preload("res://scripts/rpg_ui.gd")
const Art = preload("res://scripts/art.gd")
const Fx = preload("res://scripts/fx.gd")
const Interiors = preload("res://scripts/interiors.gd")
const GameSettings = preload("res://scripts/game_settings.gd")

## The letter's words (Korean source; i18n strings.json has en/zh).
const TITLE := "이사 온 걸 환영해!"
const BODY := ["여기는 네 집이야.", "자유롭게 돌아다니며 네가 좋아하는 공간으로 꾸며 봐.",
	"실력 있는 제작자가 온다고 해서 다들 기대하고 있어.",
	"카페 주인이 새 의자를 기다리고 있대.", "산책하다 들러서 인사해 보는 건 어때?"]
const SIGNATURE := "— 물결빛 마을 사람들이"

var room: Node
var state: Dictionary = {}
var letter: Node3D
var envelope: Node3D
var glow: OmniLight3D
## A gold star bobbing over the unread letter, with a soft halo (commercial RPGs' quest mark).
var marker: Node3D
var paper_parts: Array = []
var record: Dictionary = {}
var card: PanelContainer
var card_lines: VBoxContainer
var reading: Control
var clock := 0.0
var sparkle_wait := 0.0

func setup(owner_room: Node) -> void:
	room = owner_room
	name = "StoryHome"
	var reply: Dictionary = await room.api.request("/v1/story")
	if not is_instance_valid(room) or not reply.ok or not reply.data.get("story") is Dictionary: return
	state = reply.data.story
	if str(state.get("step", "")) == "done": return
	place_letter()
	build_card()
	if unread():
		# One soft note on the way in; the glow does the rest.
		room.message(tr("책상 위에 편지가 놓여 있어요"))
		RpgUi.sfx("toast", -10.0)

## Leaving the room (or switching rooms): the letter, the card and its record go with it.
func _exit_tree() -> void:
	for node in [card, letter, reading]:
		if is_instance_valid(node): node.queue_free()
	if is_instance_valid(room) and not record.is_empty() and not room.decor_by_floor.is_empty(): room.decor_by_floor[0].erase(record)

func unread() -> bool:
	return str(state.get("step", "")) == "letter"

## The desk by the door on the ground floor (interiors.gd 10_red_house/0).
func desk() -> Dictionary:
	if room.decor_by_floor.is_empty(): return {}
	for entry in room.decor_by_floor[0]:
		if str(entry.get("kind", "")) == "desk": return entry
	return {}

## An envelope with a red seal on the desk, a warm light over it, and the record E finds.
func place_letter() -> void:
	var table := desk()
	if table.is_empty() or room.floor_roots.is_empty(): return
	var size: Vector3 = table.get("size", Vector3(1.3, 0.8, 0.65))
	var top: float = float(table.get("top", size.y))
	letter = Node3D.new()
	letter.name = "StoryLetter"
	room.floor_roots[0].add_child(letter)
	# Toward the room from the desk's middle, so the walker sees it from the door.
	var inward := Vector3(0, 0, 1).rotated(Vector3.UP, float(table.get("yaw", 0.0)))
	letter.position = Vector3(table.center.x, top+0.02, table.center.z)+inward*0.12
	letter.rotation.y = float(table.get("yaw", 0.0))+0.35
	envelope = Node3D.new()
	letter.add_child(envelope)
	paper_parts = [Art.box(envelope, Vector3(0, 0.014, 0), Vector3(0.4, 0.024, 0.28), Color("fbf3e0")),
		Art.box(envelope, Vector3(0, 0.028, -0.04), Vector3(0.28, 0.006, 0.14), Color("efdfbd"))]
	paper_parts[1].rotation.y = PI*0.25
	paper_parts.append(Art.sphere(envelope, Vector3(0, 0.034, 0.012), Vector3(0.085, 0.03, 0.085), Color("c0392b")))
	marker = Node3D.new()
	marker.position = Vector3(0, 0.78, 0)
	letter.add_child(marker)
	# A soft 0.75 m halo (48 px) behind an outlined star bubble about 0.45 m wide (64 px).
	for layer in [[Fx.tex("soft"), 0.0156, Color(1.0, 0.82, 0.42, 0.55)], [Fx.bubble_texture("star", Color("f0b429")), 0.007, Color.WHITE]]:
		var sprite := Sprite3D.new()
		sprite.texture = layer[0]
		sprite.pixel_size = float(layer[1])
		sprite.modulate = layer[2]
		sprite.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		sprite.shaded = false
		sprite.no_depth_test = true
		sprite.render_priority = 8
		marker.add_child(sprite)
	glow = OmniLight3D.new()
	glow.light_color = Color("ffd98a")
	glow.light_energy = 1.1
	glow.omni_range = 1.8
	glow.position = Vector3(0, 0.45, 0)
	glow.shadow_enabled = false
	letter.add_child(glow)
	record = {"kind":"story_letter", "node":letter, "center":Vector3(letter.position.x, 0, letter.position.z), "yaw":float(table.get("yaw", 0.0)),
		"mounted":false, "solid":false, "interactive":true, "glb":false, "size":Vector3(0.4, 0.06, 0.3),
		"half":Vector2(0.75, 0.55), "world_half":Vector2(0.75, 0.55), "top":top+0.06, "floor":0}
	room.decor_by_floor[0].append(record)
	if room.floor_index == 0: room.decor = room.decor_by_floor[0]
	shine(unread())

## Unread: it glows, bobs and wears the star; read: it lies still.
func shine(on: bool) -> void:
	if is_instance_valid(glow): glow.visible = on
	if is_instance_valid(marker): marker.visible = on
	for part in paper_parts:
		var material: StandardMaterial3D = part.material_override
		material.emission_enabled = on
		material.emission = material.albedo_color
		material.emission_energy_multiplier = 0.35
	if is_instance_valid(envelope) and not on: envelope.position.y = 0.0
	set_process(on)

func _process(delta: float) -> void:
	if not is_instance_valid(envelope): return
	clock += delta
	if not RpgUi.calm():
		envelope.position.y = 0.04+sin(clock*2.4)*0.025
		envelope.rotation.y = sin(clock*1.3)*0.08
	if is_instance_valid(glow): glow.light_energy = 0.9+sin(clock*3.1)*0.3
	if is_instance_valid(marker) and not RpgUi.calm():
		marker.position.y = 0.78+sin(clock*2.2)*0.06
		marker.scale = Vector3.ONE*(1.0+sin(clock*3.4)*0.08)
	sparkle_wait -= delta
	if sparkle_wait <= 0.0 and room.floor_index == 0:
		sparkle_wait = 1.6
		Fx.burst(letter, letter.global_position+Vector3(0, 0.25, 0), "sparkle", 4, Color(0,0,0,0), 0.22)

## E at the desk: the letter (studio.use_decor asks first).
func use(target: Dictionary) -> bool:
	if not is_instance_valid(letter) or target.is_empty(): return false
	if target != record and not (str(target.get("kind", "")) == "desk" and Vector3(target.center).distance_to(record.center) < 1.2): return false
	open_letter()
	return true

func chip(target: Dictionary) -> String:
	if not is_instance_valid(letter): return ""
	if target == record or (str(target.get("kind", "")) == "desk" and Vector3(target.center).distance_to(record.center) < 1.2): return tr("편지 읽기")
	return ""

## The letter as a parchment card that unfolds; E, Space, Enter, Esc or a click closes it.
func open_letter() -> void:
	room.close_talk()
	if is_instance_valid(room.hero): room.hero.face_point(letter.global_position)
	reading = Control.new()
	reading.name = "StoryLetterCard"
	reading.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	room.add_child(reading)
	var shade := ColorRect.new()
	shade.color = Color(0.03, 0.04, 0.05, 0.55)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.gui_input.connect(func(event): if event is InputEventMouseButton and event.pressed: room.close_talk())
	reading.add_child(shade)
	var middle := CenterContainer.new()
	middle.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	middle.mouse_filter = Control.MOUSE_FILTER_IGNORE
	reading.add_child(middle)
	var paper := PanelContainer.new()
	paper.add_theme_stylebox_override("panel", RpgUi.panel_style("paper", 34))
	paper.custom_minimum_size = Vector2(560, 0)
	middle.add_child(paper)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	paper.add_child(column)
	var seal := RpgUi.heading(column, "✉", 30, Color("c0392b"))
	seal.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var head := RpgUi.heading(column, tr(TITLE), 30)
	head.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	RpgUi.divider(column)
	for line in BODY:
		var words := RpgUi.caption(column, tr(line), 18, RpgUi.PAPER_INK)
		words.custom_minimum_size.x = 490
	var sign := RpgUi.caption(column, tr(SIGNATURE), 16, RpgUi.PAPER_MUTED)
	sign.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	var close := RpgUi.caption(column, tr("E · 편지 접기"), 13, RpgUi.PAPER_MUTED)
	close.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	# Unfolds from a thin strip, like opening a folded sheet.
	paper.pivot_offset = Vector2(280, 160)
	if not RpgUi.calm():
		paper.scale = Vector2(1.0, 0.08)
		paper.modulate.a = 0.0
		var unfold := paper.create_tween().set_parallel(true)
		unfold.tween_property(paper, "scale", Vector2.ONE, 0.42).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		unfold.tween_property(paper, "modulate:a", 1.0, 0.2)
	room.sfx_player.stream = Interiors.sfx("page")
	room.sfx_player.play()
	# The room's talk box is this card: E/Space/Enter/Esc close it (studio._unhandled_key_input).
	room.talk_box = reading
	room.talk_window = {}
	for item in [room.name_panel, room.hint_chip, room.hint_label, room.bubble]:
		if is_instance_valid(item): item.visible = false
	reading.tree_exited.connect(read_done)
	if unread():
		var reply: Dictionary = await room.api.post("/v1/story/step", room.api.mutation({"action":"read_letter"}))
		if reply.ok and reply.data.get("story") is Dictionary: state = reply.data.story

## Folded away: the next goal shows and the door shines.
func read_done() -> void:
	if not is_instance_valid(room) or room.is_queued_for_deletion(): return
	if is_instance_valid(room.name_panel): room.name_panel.visible = true
	shine(unread())
	update_card()
	if unread(): return
	if not bool(get_meta("told", false)):
		set_meta("told", true)
		room.message(tr("새 목표 · 카페 '빨간 지붕'에 인사하러 가기"))
		var door := Vector3(float(room.room_spec.get("door_x", 0.0)), 0.0, float(room.room_spec.size.y)*0.5)
		if room.floor_index == 0:
			Fx.glow(room.floor_roots[0], door+Vector3(0, 1.2, 0), Color("ffd27a"), 2.4, 2.4)
			Fx.burst(room.floor_roots[0], door+Vector3(0, 1.0, -0.3), "sparkle", 14, Color(0,0,0,0), 0.6)
		RpgUi.sfx("confirm", -6.0)

## The home's objective card, top right (the village's tracker look).
func build_card() -> void:
	card = PanelContainer.new()
	card.name = "StoryGoal"
	card.add_theme_stylebox_override("panel", RpgUi.panel_style("night", 14))
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.custom_minimum_size = Vector2(286, 0)
	room.add_child(card)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 6)
	card.add_child(column)
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 8)
	column.add_child(head)
	head.add_child(RpgUi.icon("res://assets/ui/book.svg", 22))
	RpgUi.label(head, tr("목표"), 15, RpgUi.GOLD)
	card_lines = VBoxContainer.new()
	card_lines.add_theme_constant_override("separation", 3)
	column.add_child(card_lines)
	update_card()
	RpgUi.pin(card, 1.0, 0.0, Vector2(1280.0-18.0-286.0, 18.0))
	if not RpgUi.calm(): RpgUi.slide_in(card, Vector2(30, 0))

func update_card() -> void:
	if not is_instance_valid(card_lines): return
	for child in card_lines.get_children(): child.queue_free()
	var lines: Array = [["▸ "+tr("책상 위 편지 읽기"), true], [tr("이삿날 아침, 편지가 와 있어요"), false]] if unread() \
		else [["▸ "+tr("카페 '빨간 지붕'에 인사하러 가기"), true], [tr("문을 나서면 길 안내가 시작돼요"), false]]
	if str(state.get("step", "")) == "craft":
		lines = [["▸ "+tr("C · 모카의 의자 만들기"), true], [tr("완성되면 모카에게 가져가기"), false]]
	for entry in lines:
		var words := RpgUi.label(card_lines, str(entry[0]), 14 if entry[1] else 13, RpgUi.INK if entry[1] else Color(RpgUi.INK, 0.72), bool(entry[1]))
		words.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		words.custom_minimum_size.x = 250
	if not RpgUi.calm() and is_inside_tree(): RpgUi.pop_in(card, 0.22, 0.96)
