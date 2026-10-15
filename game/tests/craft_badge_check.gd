extends SceneTree
## The HUD craft slot's badge (craft_badge.gd, task 17) on a hotbar like the village's: it appears on the
## craft slot only, stays one badge however often it is raised, and goes when cleared. No server needed.
## With --capture (a window) it saves artifacts/craft-badge.png.
const RpgUi = preload("res://scripts/rpg_ui.gd")
const CraftBadge = preload("res://scripts/craft_badge.gd")
var failed := false

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ") + description)
	if not value: failed = true

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var ui := Control.new()
	ui.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(ui)
	var back := ColorRect.new()
	back.color = Color("1d2a33")
	back.set_anchors_preset(Control.PRESET_FULL_RECT)
	ui.add_child(back)
	var none := func() -> void: pass
	RpgUi.hotbar(ui, [{"icon": "res://assets/ui/bag.svg", "action": "inventory", "label": "가방", "call": none},
		{"icon": "res://assets/ui/craft.svg", "action": "craft", "label": "제작", "call": none},
		{"icon": "res://assets/ui/map.svg", "action": "map", "label": "지도", "call": none}], 700, "")
	await process_frame
	var slots := CraftBadge.slots()
	expect(slots.size() == 1, "one craft slot found on the hotbar (%d)" % slots.size())
	expect(CraftBadge.show(true) == 1 and CraftBadge.show(true) == 1, "raising it twice puts one badge on it")
	var dots := 0
	for node in ui.find_children(CraftBadge.NAME, "", true, false): dots += 1
	expect(dots == 1, "only the craft slot wears it (%d)" % dots)
	if "--capture" in OS.get_cmdline_user_args():
		for i in 50: await process_frame
		await RenderingServer.frame_post_draw
		var shot := root.get_texture().get_image()
		var region := shot.get_region(Rect2i(440, 560, 400, 240))
		region.save_png(ProjectSettings.globalize_path("res://../artifacts/craft-badge.png"))
	CraftBadge.show(false)
	await process_frame
	var left := 0
	for node in ui.find_children(CraftBadge.NAME, "", true, false):
		if not node.is_queued_for_deletion(): left += 1
	expect(left == 0, "clearing takes it off")
	print("CRAFT_BADGE " + ("FAILED" if failed else "OK"))
	quit(1 if failed else 0)
