extends SceneTree
## In the real village craft window: does anything take focus away from the text field while the
## player types, and do committed syllables (what an IME delivers) pile up in order?
const Main = preload("res://scripts/main.gd")
var app: Node3D
var focus_log: PackedStringArray = []

func _initialize() -> void:
	call_deferred("run")

func type_text(field: Control, value: String) -> void:
	for ch in value:
		for pressed in [true, false]:
			var key := InputEventKey.new()
			key.pressed = pressed
			key.unicode = ch.unicode_at(0) if pressed else 0
			key.keycode = KEY_NONE
			Input.parse_input_event(key)
			await process_frame
		await process_frame

func run() -> void:
	app = Main.new()
	root.add_child(app)
	await create_timer(0.4).timeout
	await app.authenticate(true, "http://127.0.0.1:8766", "ime_"+str(Time.get_ticks_msec()), "Ime-check-password-1", "")
	root.gui_focus_changed.connect(func(c: Control) -> void: focus_log.append("%d %s" % [Time.get_ticks_msec(), c.get_path() if c else "null"]))
	app.me["studio_tripo_enabled"] = true
	await app.open_craft()
	var fields: Array = app.craft_box.find_children("*", "LineEdit", true, false)
	var field: LineEdit = fields[0] if not fields.is_empty() else null
	if field == null: print("IME_GAME no field"); quit(1); return
	field.grab_focus()
	focus_log.clear()
	var started := Time.get_ticks_msec()
	while Time.get_ticks_msec() - started < 3000: await process_frame
	var lost := focus_log.size()
	var owner := root.gui_get_focus_owner()
	await type_text(field, "한글 입력")
	print("IME_GAME focus_changes_while_idle=%d owner_is_field=%s text='%s' focus_log=%s" % [lost, owner == field, field.text, focus_log])
	quit(0)
