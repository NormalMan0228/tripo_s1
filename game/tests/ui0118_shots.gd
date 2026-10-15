extends SceneTree
## Windowed shots of the 0.11.8 UI work for the review sheet (docs/design/UI_0118_KO.md), against
## recorded replies (no port): artifacts/ui0118-*.png — the login's CapsLock line, the chat box with
## its title and unread pill, a whisper request toast. Headless runs only build the screens.
##   godot --path game --script res://tests/ui0118_shots.gd
const Main = preload("res://scripts/main.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const SocialHud = preload("res://scripts/social_hud.gd")
var failures: Array[String] = []
var app: Node

func expect(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func _initialize() -> void:
	call_deferred("run")
	create_timer(180).timeout.connect(func():
		push_error("ui0118_shots exceeded 180 seconds")
		quit(2))

func capture(name: String) -> void:
	for i in 6: await process_frame
	if DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/ui0118-%s.png" % name))
	print("SHOT ui0118-", name)

func line(id: int, who: String, text: String) -> Dictionary:
	return {"id":id, "user_id":"u-" + who, "username":who, "channel":"local", "text":text, "at":Time.get_unix_time_from_system()}

func run() -> void:
	app = Main.new()
	root.add_child(app)
	await create_timer(1.6).timeout
	# The login page: a capital typed without Shift shows the CapsLock line under the field.
	app.login_ui("login")
	await create_timer(0.6).timeout
	var fields: Array = app.ui.find_children("*", "LineEdit", true, false).filter(func(f): return f.secret)
	expect(not fields.is_empty(), "the login page has its password field")
	if not fields.is_empty():
		var password: LineEdit = fields[0]
		password.grab_focus()
		var key := InputEventKey.new()
		key.keycode = KEY_A
		key.unicode = "A".unicode_at(0)
		key.pressed = true
		password.gui_input.emit(key)
		await process_frame
		var hint: Label = password.get_parent().get_node_or_null("CapsHint")
		expect(hint != null and hint.visible, "a capital without Shift shows the CapsLock line")
	await capture("caps")
	# The village with the chat box: lines while folded light the unread pill.
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	var presence := {"self_id":"me", "host_id":"u-sora", "host_name":"sora", "visiting":false, "party":null, "invites":[], "pending_rewards":[],
		"village":{"players":[{"id":"me", "username":"haneul", "x":0, "z":0}]},
		"chat":{"cursor":12, "history":true, "more":false, "removed":[], "lines":[line(10, "sora", "어서 와요! 마을 구경하고 가요"), line(11, "jun", "광장에서 만나요")]},
		"social":{"v":3, "requests":0, "knocks":0, "friends_online":1}}
	fixture["/v1/social/presence"] = presence
	app.api.queue_free()
	var stub := Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = true
	await app.enter_village()
	preload("res://scripts/transition.gd").of(self).fade_in()
	await create_timer(1.4).timeout
	var hub: Node = SocialHud.of(stub)
	expect(hub != null, "the village binds the social layer")
	if hub == null:
		quit(1)
		return
	hub.ingest(presence)
	RpgUi.set_folds(["chat"], true, false)
	await create_timer(0.3).timeout
	var live := presence.duplicate(true)
	live.chat = {"cursor":14, "history":false, "removed":[], "lines":[line(13, "mina", "낚시 같이 갈 사람!"), line(14, "dan", "저요")]}
	hub.ingest(live)
	await create_timer(0.5).timeout
	expect(hub.unread == 2, "two lines while folded are unread (%d)" % hub.unread)
	await capture("chat_folded")
	RpgUi.set_folds(["chat"], false, false)
	await create_timer(0.4).timeout
	await capture("chat_open")
	# A whisper request to me: the toast with its answers.
	stub.data["/v1/social/whispers/requests"] = {"requests":[{"id":"w9", "sender_id":"u-dan", "recipient_id":"me", "state":"pending", "from_name":"dan", "to_name":"haneul"}]}
	await hub.fetch_whispers()
	await create_timer(0.5).timeout
	await capture("whisper")
	print("UI0118_SHOTS ", "PASS" if failures.is_empty() else "FAIL %d" % failures.size())
	SocialHud.end()
	quit(0 if failures.is_empty() else 1)
