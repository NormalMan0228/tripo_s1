extends RefCounted
## A glowing "!" on the HUD's craft slot (C, the village and every room) while a craft waits for the
## player: its picture or quote is ready, or it finished or failed while the window was closed. The
## session's CraftTracker raises and clears it (craft_tracker.gd needs_you); the toast and chime stay.
##   CraftBadge.show(true)   # every craft slot on screen gets the badge
##   CraftBadge.show(false)  # the craft window opened: gone everywhere
const RpgUi = preload("res://scripts/rpg_ui.gd")
const NAME := "CraftBadge"

## The HUD slots bound to the craft key (RpgUi.hotbar watch_key "craft").
static func slots() -> Array[Control]:
	var found: Array[Control] = []
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null: return found
	for node in tree.get_nodes_in_group(RpgUi.KEY_GROUP):
		if node is Button and str(node.get_meta("key_tip_action", "")) == "craft" and node.theme_type_variation == "HudSlot":
			found.append(node)
	return found

## Puts the badge on every craft slot (or takes it off); a slot that has it keeps it (no restart).
static func show(on: bool) -> int:
	var shown := 0
	for slot in slots():
		var dot: Control = slot.get_node_or_null(NAME)
		if not on:
			if dot != null: dot.queue_free()
			continue
		shown += 1
		if dot == null: _add(slot)
	return shown

static func _add(slot: Control) -> void:
	var dot := Label.new()
	dot.name = NAME
	dot.text = "!"
	dot.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	dot.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	dot.add_theme_font_override("font", RpgUi.FONT_BOLD)
	dot.add_theme_font_size_override("font_size", 13)
	dot.add_theme_color_override("font_color", Color.WHITE)
	var pill := StyleBoxFlat.new()
	pill.bg_color = RpgUi.ACCENT
	pill.set_corner_radius_all(10)
	pill.corner_detail = 8
	pill.border_color = RpgUi.AWAY
	pill.set_border_width_all(2)
	pill.shadow_color = Color(RpgUi.AWAY, 0.55)
	pill.shadow_size = 6
	dot.add_theme_stylebox_override("normal", pill)
	dot.custom_minimum_size = Vector2(20, 20)
	dot.size = dot.custom_minimum_size
	dot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	dot.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	dot.offset_left = -24; dot.offset_right = -4; dot.offset_top = -8; dot.offset_bottom = 12
	dot.pivot_offset = Vector2(10, 10)
	slot.add_child(dot)
	if RpgUi.calm(): return
	# Pops in, then breathes (scale and glow) until the window opens.
	dot.scale = Vector2.ONE * 0.2
	var arrive := dot.create_tween()
	arrive.tween_property(dot, "scale", Vector2.ONE, 0.32).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	var glow := dot.create_tween().set_loops()
	glow.tween_interval(0.35)
	glow.tween_property(dot, "modulate", Color(1.25, 1.2, 1.05), 0.7).set_trans(Tween.TRANS_SINE)
	glow.parallel().tween_property(dot, "scale", Vector2.ONE * 1.12, 0.7).set_trans(Tween.TRANS_SINE)
	glow.tween_property(dot, "modulate", Color.WHITE, 0.7).set_trans(Tween.TRANS_SINE)
	glow.parallel().tween_property(dot, "scale", Vector2.ONE, 0.7).set_trans(Tween.TRANS_SINE)
