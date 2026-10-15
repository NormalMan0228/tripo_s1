extends SceneTree
## The first look (31, character_select.gd) over the title, windowed: artifacts/char-select-*.png.
## Picks a card and checks the wardrobe editor follows; 모험 시작 hands back the look.
##   godot --path game --script res://tests/char_select_shot.gd
const Main = preload("res://scripts/main.gd")
const CharacterSelect = preload("res://scripts/character_select.gd")
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
	app.login_ui("menu")
	await create_timer(1.0).timeout
	var picker := CharacterSelect.new()
	picker.avatar = {"character":"explorer_b"}
	app.ui.add_child(picker)
	await create_timer(1.2).timeout
	await capture("first")
	picker.pick("ranger")
	await create_timer(0.8).timeout
	expect(picker.editor.avatar.character == "ranger", "a card dresses the editor as that traveller")
	await capture("ranger")
	var got := [null]
	picker.done.connect(func(look): got[0] = look)
	picker.find_child("Start", true, false).pressed.emit()
	await create_timer(0.3).timeout
	expect(got[0] is Dictionary and got[0].character == "ranger", "모험 시작 hands back the chosen look")
	print("CHAR_SELECT ", "PASS" if failures.is_empty() else "FAIL %d" % failures.size())
	quit(0 if failures.is_empty() else 1)
