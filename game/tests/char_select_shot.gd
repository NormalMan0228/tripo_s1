extends SceneTree
## The first look (31, character_select.gd) over the title, windowed: artifacts/char-select-*.png.
## Picks a card and checks the wardrobe editor follows; 모험 시작 hands back the look.
##   godot --path game --script res://tests/char_select_shot.gd
const Main = preload("res://scripts/main.gd")
const CharacterSelect = preload("res://scripts/character_select.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
var failures: Array[String] = []

func expect(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func _initialize() -> void:
	call_deferred("run")
	create_timer(120).timeout.connect(func(): quit(2))

func capture(name: String) -> void:
	for i in 8: await process_frame
	if DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/char-select-%s.png" % name))
	print("SHOT char-select-", name)

func run() -> void:
	var app := Main.new()
	root.add_child(app)
	await create_timer(3.0).timeout
	# A plain title behind: the version check against the online world and the menu step aside.
	if "gate" in app and is_instance_valid(app.gate): app.gate.visible = false
	for child in app.ui.get_children(): child.queue_free()
	var art := TextureRect.new()
	art.texture = load("res://assets/title_golden.jpg")
	art.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	app.ui.add_child(art)
	preload("res://scripts/transition.gd").of(self).fade_in()
	await create_timer(1.2).timeout
	var picker := CharacterSelect.new()
	picker.avatar = {"character":"explorer"}
	app.ui.add_child(picker)
	await create_timer(1.2).timeout
	var panel: Control = picker.get_child(1)
	expect(Rect2(Vector2.ZERO, Vector2(1280, 800)).encloses(panel.get_global_rect()), "the card fits the screen (%s)" % panel.get_global_rect())
	await capture("first")
	expect(picker.chosen == "m1" and picker.cards["m2"].disabled, "the 남 tab opens on 모험가; characters without a model are locked (준비 중)")
	await capture("male")
	RpgUi.select_tab(picker.find_child("SexTabs", true, false), "f")
	picker.pick("f1")
	await create_timer(0.8).timeout
	expect(picker.editor.avatar.character == "explorer_b", "여 모험가 dresses the editor in its stand-in model")
	await capture("female")
	var got := [null]
	picker.done.connect(func(look): got[0] = look)
	picker.find_child("Start", true, false).pressed.emit()
	await create_timer(0.3).timeout
	expect(got[0] is Dictionary and got[0].character == "explorer_b", "모험 시작 hands back the chosen look")
	print("CHAR_SELECT ", "PASS" if failures.is_empty() else "FAIL %d" % failures.size())
	quit(0 if failures.is_empty() else 1)
