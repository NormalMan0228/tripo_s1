extends SceneTree
## The always-on chat box and the 함께하기 drawer (social_hud.gd, chat_box.gd, social_window.gd)
## against recorded replies (no port): history seeds the log silently, new lines append once
## (no replay), user text is not BBCode, Enter focuses / sends / gives the keys back (the walker
## stands still meanwhile), Esc lets go without the pause menu, a modal window hides the chat,
## K opens and closes the drawer with its tabs and rows, and signing out clears it all.
## Windowed runs also capture artifacts/chat-*.png:
##   godot --path game --script res://tests/chat_box_check.gd
const Main = preload("res://scripts/main.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const SocialHud = preload("res://scripts/social_hud.gd")
const PauseMenu = preload("res://scripts/pause_menu.gd")
var failures: Array[String] = []
var app: Node
var stub: Node
var sent: Array = []

class RecordingStub extends "res://tests/ui_stub_api.gd":
	var posts: Array = []
	func post(path: String, payload: Dictionary) -> Dictionary:
		posts.append([path, payload])
		return await request(path, payload, HTTPClient.METHOD_POST)

func expect(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("chat_box_check exceeded 240 seconds")
		quit(2))

func press(key: Key) -> void:
	for down in [true, false]:
		var event := InputEventKey.new()
		event.keycode = key
		event.physical_keycode = key
		event.pressed = down
		root.push_input(event)
		await process_frame
	await process_frame

func capture(name: String) -> void:
	for i in 6: await process_frame
	if DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/chat-%s.png" % name))
	print("SHOT chat-", name)

func line(id: int, username: String, text: String, channel := "local", extra := {}) -> Dictionary:
	return {"id":id, "channel":channel, "user_id":"u-" + username, "username":username, "text":text, "created":1781234567.0 + id}.merged(extra)

func run() -> void:
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	fixture["/health"]["social_features"] = ["chat2", "place", "people", "friends", "visit", "report"]
	fixture["/health"]["global_chat"] = true
	fixture["/health"]["chat_max_length"] = 160
	var people := {"v":3, "online_count":4, "roster":"all",
		"online":[{"id":"u-sora", "username":"sora", "avatar":{"character":"explorer"}, "friend":true, "place":"village", "where":{"place":"village", "host_name":"sora"}},
			{"id":"u-jun", "username":"jun", "avatar":{"character":"ranger"}, "friend":false, "place":"expedition"},
			{"id":"u-dan", "username":"dan", "avatar":{"character":"tinker"}, "friend":false, "place":"home"}],
		"my_village":{"host":{"id":"me", "username":"haneul", "online":true}, "visiting":false, "guest_limit":2,
			"guests":[{"id":"u-sora", "username":"sora", "online":true, "place":"home", "floor":1}], "invites_out":[], "knocks":[]},
		"friends":[{"id":"u-sora", "username":"sora", "avatar":{"character":"explorer"}, "online":true, "where":{"place":"village", "host_name":"haneul"}, "joinable":false, "drop_in":true},
			{"id":"u-mina", "username":"mina", "avatar":{"character":"ranger"}, "online":false, "last_seen":Time.get_unix_time_from_system() - 90000.0, "joinable":false}],
		"requests":{"incoming":[{"id":"r1", "user_id":"u-dan", "username":"dan"}], "outgoing":[]},
		"blocked":[], "prefs":{"appear_offline":false, "roster":"everyone", "requests":"everyone", "drop_in":"friends"}}
	fixture["/v1/social/people"] = people
	var presence := {"self_id":"me", "host_id":"me", "host_name":"haneul", "visiting":false, "party":null, "invites":[], "pending_rewards":[],
		"village":{"players":[{"id":"me", "username":"haneul", "x":0, "z":0}]},
		"chat":{"cursor":12, "history":true, "more":false, "removed":[], "lines":[line(10, "sora", "안녕! 오늘 낚시 어때?"), line(11, "jun", "[b]굵게[/b] 아니에요", "global"), line(12, "sora", "탐험 갈 사람", "party")]},
		"social":{"v":3, "requests":1, "knocks":0, "friends_online":1}}
	fixture["/v1/social/presence"] = presence
	fixture["/v1/social/messages"] = {"ok":true, "id":20, "channel":"local", "text":"반가워요"}
	app = Main.new()
	root.add_child(app)
	await create_timer(1.6).timeout
	app.api.queue_free()
	stub = RecordingStub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = true
	await app.enter_village()
	preload("res://scripts/transition.gd").of(self).fade_in()
	await create_timer(1.2).timeout
	var hub: Node = SocialHud.of(stub)
	expect(hub != null and hub.place == app and hub.chat.visible, "the village binds the chat box and shows it")
	await create_timer(0.6).timeout
	expect(hub.health_ready and hub.chat2(), "features read from /health (chat2)")
	# History seeds silently: three lines, nothing unread.
	var chat: Control = hub.chat
	var shown: String = chat.log_view.get_parsed_text()
	expect(hub.lines.filter(func(l): return int(l.get("id", 0)) >= 10).size() == 3 and hub.unread == 0, "history seeds the log without unread (%d lines, %d unread)" % [hub.lines.size(), hub.unread])
	expect(shown.contains("[b]굵게[/b]"), "user text is shown as typed, not as BBCode")
	expect(shown.contains("[전체]") and shown.contains("[파티]"), "global and party lines carry their tag")
	# The same reply again does not repeat the lines.
	hub.ingest(presence)
	expect(hub.lines.filter(func(l): return int(l.get("id", 0)) >= 10).size() == 3, "a repeated reply adds nothing (no replay)")
	# A new live line appends once.
	var live := presence.duplicate(true)
	live.chat = {"cursor":13, "history":false, "lines":[line(13, "mina", "나도 갈래!")], "removed":[]}
	hub.ingest(live)
	expect(hub.lines.back().get("text") == "나도 갈래!" and int(hub.cursor) == 13, "a live line appends and moves the cursor")
	expect(hub.presence_extra("village").get("since") == 13 and hub.presence_extra("village").get("place") == "village", "polls carry since and place")
	await capture("idle")
	# Enter focuses the field; the walker stands still while it has the keys.
	await press(KEY_ENTER)
	expect(chat.field.has_focus(), "Enter focuses the chat field")
	expect(not app.player.controls_enabled, "the walker stands still while typing")
	chat.field.text = "반가워요"
	await capture("focus")
	chat.field.text_submitted.emit("반가워요")
	await create_timer(0.4).timeout
	var posted: Array = stub.posts.filter(func(p): return p[0] == "/v1/social/messages")
	expect(posted.size() == 1 and posted[0][1].text == "반가워요" and posted[0][1].channel == "local", "Enter sends the line on the village channel (%s)" % [posted])
	expect(not chat.field.has_focus() and chat.field.text.is_empty(), "after sending the field is empty and lets go")
	expect(app.player.controls_enabled, "the walker can walk again")
	expect(hub.lines.any(func(l): return str(l.get("text", "")) == "반가워요"), "the sent line shows in the log")
	# Esc lets go of the field without opening the pause menu.
	await press(KEY_ENTER)
	await press(KEY_ESCAPE)
	await create_timer(0.2).timeout
	expect(not chat.field.has_focus() and not is_instance_valid(PauseMenu.current), "Esc lets go of the field; no pause menu")
	# Slash whisper.
	stub.posts.clear()
	hub.send("/w sora 몰래 할 말")
	await create_timer(0.3).timeout
	posted = stub.posts.filter(func(p): return p[0] == "/v1/social/messages")
	expect(posted.size() == 1 and posted[0][1].channel == "whisper" and posted[0][1].to == "sora" and posted[0][1].text == "몰래 할 말", "/w sends a whisper (%s)" % [posted])
	# Whisper requests (48): a whisper not allowed yet comes back as a request and the line goes
	# back into the field; a request to me is a toast with 수락 / 거절, and 수락 answers it.
	var sent_reply: Dictionary = stub.data["/v1/social/messages"]
	stub.data["/v1/social/messages"] = {"ok":true, "channel":"whisper", "state":"requested", "request":{"id":"w1", "to_id":"u-jun", "expires":0}}
	hub.send("/w jun 같이 낚시해요")
	await create_timer(0.3).timeout
	# The line waits as typed (/w 이름 …): Enter again on the village or global channel must not send it there.
	expect(str(hub.lines.back().get("channel")) == "system" and chat.field.text == "/w jun 같이 낚시해요" and not hub.lines.any(func(l): return str(l.get("text", "")) == "같이 낚시해요"),
		"a whisper not allowed yet becomes a request; the line waits in the field as typed (%s / field %s)" % [hub.lines.back().get("channel"), chat.field.text])
	chat.field.clear()
	hub.last_whisper = "jun"
	hub.send("/r 다시 말해요")
	await create_timer(0.3).timeout
	expect(chat.field.text == "/r 다시 말해요", "a /r that became a request waits as typed too (field %s)" % chat.field.text)
	stub.data["/v1/social/messages"] = sent_reply
	chat.field.clear()
	stub.data["/v1/social/whispers/requests"] = {"requests":[{"id":"w2", "sender_id":"u-dan", "recipient_id":"me", "state":"pending", "from_name":"dan", "to_name":"haneul"}]}
	stub.data["/v1/social/whispers/requests/w2/accept"] = {"ok":true, "state":"accepted", "expires":0}
	await hub.fetch_whispers()
	var asked := RpgUi.find_toast(app.toast_lane, app.tr("%s님이 귓속말을 나누고 싶어 해요") % "dan")
	expect(hub.whisper_api == 1 and asked != null, "a whisper request to me shows a toast with its answers")
	await hub.fetch_whispers()
	expect(RpgUi.toasts(app.toast_lane).filter(func(t): return str(t.get_meta("toast")).contains("dan")).size() == 1, "the same request is not shown twice")
	stub.posts.clear()
	await hub.answer_whisper("w2", "dan", true)
	expect(stub.posts.any(func(p): return p[0] == "/v1/social/whispers/requests/w2/accept") and chat.whisper_to == "dan", "수락 answers the request and turns the channel to them")
	chat.whisper_to = ""
	chat.refresh_channels()
	await capture("whisper")
	# A modal window hides the chat; closing it brings it back.
	app.life.open_map()
	await create_timer(0.3).timeout
	expect(not chat.visible, "a modal window hides the chat")
	app.close_village_modal()
	await create_timer(0.3).timeout
	expect(chat.visible, "the chat comes back when the window closes")
	# K: the 함께하기 drawer with its tabs; the people list fills the friends tab.
	await press(KEY_K)
	await create_timer(0.6).timeout
	var w: Dictionary = hub.drawer
	expect(not w.is_empty() and RpgUi.top_window().get("id") == "social_drawer", "K opens the 함께하기 drawer on the window stack")
	var tabs: Dictionary = hub.window.tabs.get_meta("buttons", {}) if is_instance_valid(hub.window.tabs) else {}
	expect(tabs.has("friends") and tabs.has("online") and tabs.has("village") and tabs.has("party"), "four tabs with friends and online (%s)" % [tabs.keys()])
	var rows: Array = hub.window.list.find_children("Person_*", "HBoxContainer", true, false)
	expect(rows.size() >= 3, "friends tab: request and friends rows (%d)" % rows.size())
	await capture("social-friends")
	RpgUi.select_tab(hub.window.tabs, "online")
	await create_timer(0.3).timeout
	var online_rows: Array = hub.window.list.find_children("Person_*", "HBoxContainer", true, false).filter(func(r): return not r.is_queued_for_deletion())
	expect(online_rows.size() == 3, "online tab: three people (%s)" % [online_rows.map(func(r): return r.name)])
	await capture("social-online")
	RpgUi.select_tab(hub.window.tabs, "village")
	await create_timer(0.3).timeout
	await capture("social-village")
	await press(KEY_K)
	await create_timer(0.4).timeout
	expect(hub.drawer.is_empty() and RpgUi.windows().is_empty(), "K closes the drawer")
	# The drawer also closes on Esc before the pause menu.
	hub.open_window()
	await create_timer(0.3).timeout
	await press(KEY_ESCAPE)
	await create_timer(0.3).timeout
	expect(hub.drawer.is_empty() and not is_instance_valid(PauseMenu.current), "Esc closes the drawer first")
	# Signing out ends the layer and its history.
	SocialHud.end(stub)
	await process_frame
	await process_frame
	expect(not is_instance_valid(hub) or hub.is_queued_for_deletion() or hub.stopped, "signing out ends the social layer")
	expect(SocialHud.hubs.is_empty(), "no hub is left for the next account")
	print("CHAT_BOX ", "PASS" if failures.is_empty() else "FAIL %d" % failures.size())
	quit(0 if failures.is_empty() else 1)
