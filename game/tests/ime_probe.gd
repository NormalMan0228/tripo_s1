extends SceneTree
## IME check: a bare LineEdit and TextEdit (engine defaults) next to the game's styled ones.
## Type Korean (and Chinese) into each; every change is logged with the field's whole text, so
## "each new syllable replaces the last" shows up as a text that never grows. Writes the log to
## artifacts/ime-probe.txt when the window closes. Launch: tools/ime_probe.cmd
const RpgUi = preload("res://scripts/rpg_ui.gd")
var log_lines: PackedStringArray = []
var view: Label

func _initialize() -> void:
	var panel := VBoxContainer.new()
	panel.position = Vector2(24, 24)
	panel.custom_minimum_size = Vector2(760, 0)
	panel.add_theme_constant_override("separation", 10)
	root.add_child(panel)
	var title := Label.new()
	title.text = "IME 확인: 각 칸에 '한글 입력 테스트'와 '中文输入测试'를 쳐 보세요. 끝나면 창을 닫으세요."
	panel.add_child(title)
	for spec in [["기본 LineEdit", false, false], ["기본 TextEdit", true, false], ["게임 스타일 LineEdit", false, true], ["게임 스타일 TextEdit", true, true]]:
		var name: String = spec[0]
		var label := Label.new(); label.text = name; panel.add_child(label)
		var field: Control = TextEdit.new() if spec[1] else LineEdit.new()
		field.custom_minimum_size = Vector2(740, 70 if spec[1] else 40)
		if spec[2]: field.theme = RpgUi.theme()
		panel.add_child(field)
		field.text_changed.connect(func(_a = null) -> void: _note(name, field))
	view = Label.new(); view.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART; view.custom_minimum_size = Vector2(740, 200)
	panel.add_child(view)

func _note(name: String, field: Control) -> void:
	var line := "%s | %s | len=%d" % [name, field.text, field.text.length()]
	log_lines.append(line)
	var tail := log_lines.slice(maxi(0, log_lines.size() - 8))
	view.text = "\n".join(tail)

func _finalize() -> void:
	var file := FileAccess.open(ProjectSettings.globalize_path("res://../artifacts/ime-probe.txt"), FileAccess.WRITE)
	if file: file.store_string("\n".join(log_lines) + "\n")
