extends CanvasLayer
## The social layer that outlives scenes: the always-on chat box (chat_box.gd), the 함께하기 drawer
## (K, social_window.gd) and social notices (friend requests, knocks, invitations) in the place's
## toast lane. One per signed-in session under tree.root, like CraftTracker: SocialHud.of(api)
## after signing in (null before), SocialHud.end(api) on signing out or a lost session, which
## clears the history so nothing leaks to the next account on this PC.
## A place (main.gd: village, survival; studio.gd: rooms) bind()s it with its toast lane and gives
## it every presence reply (ingest), so chat arrives in rooms and on expeditions too; it adds the
## chat cursor and the place to those polls (presence_extra). The server's features come from
## /health (SOCIAL_API.md 1): without "chat2" (the judges' server, 0.11.x) chat uses the old
## `messages` list, and the friends and online tabs stay hidden.
const RpgUi = preload("res://scripts/rpg_ui.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const Api = preload("res://scripts/api.gd")
const ChatBox = preload("res://scripts/chat_box.gd")
const SocialWindow = preload("res://scripts/social_window.gd")
const LAYER := 4
const MAX_LINES := 100
## Channels a line can come in on (server/chat.py), with their tag and colour in the log.
const CHANNELS := {"local":"마을", "party":"파티", "global":"전체", "whisper":"귓속말"}

static var hubs: Dictionary = {}
## The hub of the session being played (the last one made); null after signing out.
static var current: Node

var session := ""
var api: Node
var stopped := false
## /health: the social feature list, the chat length, the polling advice.
var features: Array = []
var health: Dictionary = {}
var health_ready := false
## The presence groups the server refused this session (the 422 rule): "chat2", "place".
var refused: Dictionary = {}
## The place now bound: the node (main.gd or studio.gd), its kind and its toast lane.
var place: Node
var place_kind := ""
var lane: Control
## Chat: lines (dictionaries, oldest first), the server cursor (-1: ask for history once),
## the newest legacy id seen (-1: seed silently first), the unread count.
var lines: Array = []
var cursor := -1
var legacy_seen := -1
var unread := 0
var last_whisper := ""
var muted_until := 0.0
## The last presence reply (party, invites, village, knocks) and its social block.
var overview: Dictionary = {}
var social_v := -1
var counts := {"requests":0, "knocks":0, "friends_online":0}
## The last /v1/social/people answer and when it came (seconds since start).
var people: Dictionary = {}
var people_time := -100.0
var people_pending := false
## Notices already shown (ids), so a poll does not say them again.
var noticed: Dictionary = {}
## UI: a full-rect root on this layer, the chat box, the drawer window while open.
var root_ui: Control
var chat: Control
var drawer: Dictionary = {}
var window: RefCounted
var hidden_by_window := false

## The hub of the session `network` (an api.gd) is signed in to; null before signing in.
static func of(network: Node) -> Node:
	if network == null or not is_instance_valid(network) or str(network.token).is_empty(): return null
	var key := str(network.base_url) + "|" + str(network.token)
	var found = hubs.get(key)
	if is_instance_valid(found) and not found.stopped:
		current = found
		return found
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null or tree.root == null: return null
	var hub: CanvasLayer = (load("res://scripts/social_hud.gd") as GDScript).new()
	hub.name = "SocialHud"
	hub.layer = LAYER
	hub.session = key
	# Its own connection, like CraftTracker (a place's api.gd goes with its scene); a test's
	# stand-in (tests/ui_stub_api.gd) is used as it is.
	if network.get_script() == Api:
		hub.api = Api.new()
		hub.api.base_url = network.base_url
		hub.api.token = network.token
		hub.add_child(hub.api)
	else: hub.api = network
	tree.root.add_child(hub)
	hubs[key] = hub
	current = hub
	return hub

## Signing out (or a lost session) ends the session's hub and its history (every hub without a
## network). Call it before the token is cleared.
static func end(network: Node = null) -> void:
	if network == null or not is_instance_valid(network) or str(network.token).is_empty():
		for hub in hubs.values():
			if is_instance_valid(hub): hub.stop()
		hubs.clear()
		current = null
		return
	var key := str(network.base_url) + "|" + str(network.token)
	var found = hubs.get(key)
	hubs.erase(key)
	if is_instance_valid(found): found.stop()

## Every live hub lets go of `node` (a place leaving: the title screen, a scene change).
static func release_place(node: Node) -> void:
	for hub in hubs.values():
		if is_instance_valid(hub): hub.unbind(node)

## A speech bubble over `actor` for a chat line: a short billboard label that floats up and fades.
## One per actor: a new line replaces the last.
static func bubble(actor: Node3D, text: String, height := 2.45) -> void:
	if not is_instance_valid(actor) or text.strip_edges().is_empty(): return
	var old := actor.get_node_or_null("ChatBubble")
	if old: old.free()
	var label := Label3D.new()
	label.name = "ChatBubble"
	label.text = text.left(40) + ("…" if text.length() > 40 else "")
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.fixed_size = false
	label.pixel_size = 0.0055
	label.font_size = 30
	label.outline_size = 10
	label.modulate = RpgUi.INK
	label.outline_modulate = Color(RpgUi.OUTLINE, 0.9)
	label.width = 360.0
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.position = Vector3(0, height, 0)
	label.render_priority = 3
	actor.add_child(label)
	var tween := label.create_tween()
	tween.tween_property(label, "position:y", height + 0.12, 0.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_interval(4.0)
	tween.tween_property(label, "modulate:a", 0.0, 0.5)
	tween.parallel().tween_property(label, "outline_modulate:a", 0.0, 0.5)
	tween.tween_callback(label.queue_free)

func stop() -> void:
	if stopped: return
	stopped = true
	RpgUi.unlisten_windows(_windows_changed)
	if not drawer.is_empty(): RpgUi.close_window(drawer, false)
	lines.clear()
	if current == self: current = null
	queue_free()

func _ready() -> void:
	root_ui = Control.new()
	root_ui.name = "Root"
	root_ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root_ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root_ui.theme = RpgUi.theme()
	add_child(root_ui)
	chat = ChatBox.new()
	chat.hub = self
	root_ui.add_child(chat)
	chat.visible = false
	window = SocialWindow.new(self)
	RpgUi.listen_windows(_windows_changed)
	read_health()

## Reads /health for the social features (at sign-in; again after a room return or a 422).
func read_health() -> void:
	var answer: Dictionary = await api.request("/health")
	if stopped or not answer.ok: return
	health = answer.data
	features = health.get("social_features", []) if health.get("social_features") is Array else []
	health_ready = true
	if is_instance_valid(chat): chat.refresh_channels()
	window.refresh()

func has(feature: String) -> bool:
	return feature in features and not refused.has(feature)

func chat2() -> bool:
	return has("chat2")

# ------------------------------------------------------------------ places

## A place shows the chat and the notices from now on. kind: "village", "survival" or "room".
func bind(node: Node, kind: String, toast_lane: Control) -> void:
	place = node
	place_kind = kind
	lane = toast_lane
	chat.place_for(kind)
	update_visibility()

## The place is going (scene change, title): the chat hides until the next one binds.
func unbind(node: Node) -> void:
	if place != node: return
	place = null
	place_kind = ""
	lane = null
	if not drawer.is_empty(): RpgUi.close_window(drawer, false)
	drawer = {}
	chat.release()
	update_visibility()

func update_visibility() -> void:
	var shown := is_instance_valid(place) and not hidden_by_window
	chat.visible = shown
	if not drawer.is_empty() and is_instance_valid(drawer.get("root")): (drawer.root as Control).visible = shown
	if not shown: chat.release()

## Window stack listener: a modal window or a dialogue hides the chat (and the drawer under it)
## until it closes; unread lines keep counting.
func _windows_changed(_count: int, _top_kind: String) -> void:
	var covered := false
	for w in RpgUi.windows():
		if bool(w.get("modal", false)): covered = true
	if covered == hidden_by_window: return
	hidden_by_window = covered
	update_visibility()

## The place's toast lane (a notice said while no place is bound is dropped: chat keeps it).
func notice(text: String, kind := "social", actions: Array = []) -> void:
	var target: Control = lane
	if is_instance_valid(place) and place.get("toast_lane") is Control and is_instance_valid(place.get("toast_lane")): target = place.get("toast_lane")
	if is_instance_valid(target): RpgUi.toast(target, text, kind, {"actions":actions} if not actions.is_empty() else {})

# ------------------------------------------------------------------ presence

## Fields to add to a presence poll: the chat cursor (chat2) and where the player is (place).
## place: "village", "home", "workshop", "room" or "expedition"; floor for the home.
func presence_extra(where := "", floor := -1) -> Dictionary:
	var extra := {}
	if chat2(): extra["since"] = maxi(cursor, 0)
	if has("place") and not where.is_empty():
		extra["place"] = where
		if floor >= 0: extra["floor"] = clampi(floor, 0, 9)
	return extra

## A presence poll was refused with 422: the groups the server named (fields) are dropped for this
## session and true is returned (poll again as it was); false when none of ours was named.
func presence_refused(response: Dictionary) -> bool:
	if int(response.get("status", 0)) != 422: return false
	var named: Array = response.get("fields", []) if response.get("fields") is Array else []
	var dropped := false
	for field in named:
		match str(field):
			"since": dropped = _refuse("chat2") or dropped
			"place", "floor": dropped = _refuse("place") or dropped
	if named.is_empty() and has("chat2"): dropped = _refuse("chat2")
	return dropped

func _refuse(group: String) -> bool:
	if refused.has(group) or not group in features: return false
	refused[group] = true
	return true

## Every presence reply of the place (village, room, expedition) comes here.
func ingest(reply: Dictionary) -> void:
	if stopped or reply.is_empty(): return
	overview = reply
	if reply.get("chat") is Dictionary: _ingest_chat(reply.chat)
	elif reply.get("messages") is Array: _ingest_legacy(reply.messages)
	if reply.get("social") is Dictionary: _ingest_social(reply.social)
	_ingest_invites(reply.get("invites", []) if reply.get("invites") is Array else [])
	_ingest_knocks(reply.get("knocks", []) if reply.get("knocks") is Array else [])
	chat.update_badge()
	window.refresh_overview()

func _ingest_chat(block: Dictionary) -> void:
	var history := bool(block.get("history", false))
	var fresh := []
	for entry in block.get("lines", []):
		if not entry is Dictionary: continue
		var id := int(entry.get("id", 0))
		if lines.any(func(l): return int(l.get("id", -1)) == id): continue
		# Our own line: the echo shown when it was sent takes the server's id and text.
		var echo = _echo_for(entry)
		if echo:
			echo.merge(entry, true)
			echo.erase("pending")
			continue
		fresh.append(entry)
	for id in block.get("removed", []):
		lines = lines.filter(func(l): return int(l.get("id", -1)) != int(id))
	if block.has("cursor"): cursor = int(block.cursor)
	fresh.sort_custom(func(a, b): return int(a.id) < int(b.id))
	for entry in fresh: _add_line(entry, not history)
	if not fresh.is_empty() or block.get("removed", []).size() > 0: chat.redraw()
	# More than 50 lines were waiting: the place's next poll brings the rest.

func _echo_for(entry: Dictionary):
	for line in lines:
		if line.get("pending", false) and str(line.get("request_id", "")) != "" and int(line.get("sent_id", -1)) == int(entry.get("id", -2)): return line
	return null

## The 0.11.x list (the last 20 lines of the room): the first reply only seeds what is old.
func _ingest_legacy(messages: Array) -> void:
	var newest := legacy_seen
	var seeding := legacy_seen < 0
	var fresh := false
	for entry in messages:
		if not entry is Dictionary: continue
		var id := int(entry.get("id", 0))
		newest = maxi(newest, id)
		if seeding or id <= legacy_seen: continue
		var echo = null
		for line in lines:
			if line.get("pending", false) and str(line.get("text", "")) == str(entry.get("text", "")): echo = line
		if echo:
			echo.merge(entry, true)
			echo.erase("pending")
			continue
		_add_line({"id":id, "channel":"local", "username":str(entry.get("username", "")), "text":str(entry.get("text", ""))}, true)
		fresh = true
	if seeding:
		for entry in messages:
			if entry is Dictionary: _add_line({"id":int(entry.get("id", 0)), "channel":"local", "username":str(entry.get("username", "")), "text":str(entry.get("text", ""))}, false)
		fresh = not messages.is_empty()
	legacy_seen = maxi(newest, 0)
	if fresh: chat.redraw()

func _add_line(entry: Dictionary, live: bool) -> void:
	lines.append(entry)
	while lines.size() > MAX_LINES: lines.pop_front()
	if not live: return
	var mine := str(entry.get("username", "")) == my_name()
	if str(entry.get("channel", "")) == "whisper" and not mine: last_whisper = str(entry.get("username", ""))
	if not mine and not chat.reading(): unread += 1
	# Someone else's live line: chat_in (a whisper its own), at most one per 400 ms (RpgUi SFX_GAP_MS)
	# when a poll brings several; history and this player's own lines stay silent (sending sounded).
	if not mine: RpgUi.sfx("whisper" if str(entry.get("channel", "")) == "whisper" else "chat_in", -11.0)
	if place and place.has_method("chat_bubble") and not str(entry.get("channel", "")) in ["global", "whisper"]:
		place.chat_bubble(str(entry.get("user_id", "")), str(entry.get("username", "")), str(entry.get("text", "")))

## A system line in the chat log (joins, visit ends, refusals): SOFT, never counted as unread.
func system_line(text: String) -> void:
	lines.append({"id":-1, "channel":"system", "text":text})
	while lines.size() > MAX_LINES: lines.pop_front()
	chat.redraw()

func _ingest_social(block: Dictionary) -> void:
	var before: int = counts.requests
	for key in counts.keys(): counts[key] = int(block.get(key, counts[key]))
	muted_until = float(block.get("muted_until", 0.0))
	var v := int(block.get("v", social_v))
	if v != social_v:
		social_v = v
		if window.is_open(): fetch_people()
	if counts.requests > before and health_ready:
		notice(tr("친구 신청이 왔어요"), "social", [{"label":tr("보기"), "call":func(): open_window("friends")}])

func _ingest_invites(invites: Array) -> void:
	for invitation in invites:
		if not invitation is Dictionary: continue
		var id := str(invitation.get("id", ""))
		if id.is_empty() or noticed.has("invite:" + id): continue
		noticed["invite:" + id] = true
		var village := str(invitation.get("kind", "")) == "village"
		var text := (tr("%s님이 마을로 초대했어요") if village else tr("%s님이 파티에 초대했어요")) % str(invitation.get("sender", ""))
		notice(text, "social", [{"label":tr("수락"), "call":func(): answer_invite(invitation, "accept")},
			{"label":tr("거절"), "call":func(): answer_invite(invitation, "decline")}])
		system_line(text)

func _ingest_knocks(knocks: Array) -> void:
	for knock in knocks:
		if not knock is Dictionary: continue
		var id := str(knock.get("id", ""))
		if id.is_empty() or noticed.has("knock:" + id): continue
		noticed["knock:" + id] = true
		var text := tr("%s님이 마을 문을 두드려요") % str(knock.get("sender", ""))
		notice(text, "social", [{"label":tr("들이기"), "call":func(): answer_invite({"id":id, "kind":"knock", "sender":knock.get("sender", "")}, "accept")},
			{"label":tr("거절"), "call":func(): answer_invite({"id":id, "kind":"knock"}, "decline")}])
		system_line(text)

func my_name() -> String:
	if is_instance_valid(place) and "me" in place and place.me is Dictionary:
		var name := str(place.me.get("username", ""))
		if not name.is_empty(): return name
	return str(overview.get("self_name", Engine.get_meta("social_username", "")))

# ------------------------------------------------------------------ chat

## Sends a chat line on `channel` ("local", "party", "global", "whisper" with `to`). Slash commands:
## /w 이름 내용 (whisper), /r 내용 (answer the last whisper), /p (party), /v (village), /g (everyone).
func send(text: String, channel := "local") -> void:
	text = text.strip_edges()
	if text.is_empty(): return
	var to := ""
	if text.begins_with("/"):
		var parts := text.split(" ", false, 2)
		match parts[0].to_lower():
			"/w", "/귓":
				if parts.size() < 3:
					system_line(tr("귓속말은 /w 이름 내용"))
					return
				channel = "whisper"; to = parts[1]; text = parts[2]
			"/r":
				if last_whisper.is_empty() or parts.size() < 2:
					system_line(tr("답할 귓속말이 없어요."))
					return
				channel = "whisper"; to = last_whisper; text = text.substr(3).strip_edges()
			"/p": channel = "party"; text = text.substr(3).strip_edges()
			"/v": channel = "local"; text = text.substr(3).strip_edges()
			"/g": channel = "global"; text = text.substr(3).strip_edges()
		if text.is_empty(): return
	if channel == "whisper" and to.is_empty(): to = chat.whisper_to
	var body := {"text":text.left(int(health.get("chat_max_length", 160)))}
	if chat2():
		body["channel"] = channel
		if channel == "whisper": body["to"] = to
	elif channel != "local" and channel != "party":
		system_line(tr("이 월드에서는 마을 대화만 할 수 있어요."))
		return
	var payload: Dictionary = api.mutation(body)
	var echo := {"id":-2, "channel":channel, "username":my_name(), "text":body.text, "pending":true, "request_id":payload.request_id}
	if channel == "whisper": echo["to_name"] = to
	lines.append(echo)
	chat.redraw()
	var answer: Dictionary = await api.post("/v1/social/messages", payload)
	if stopped: return
	if answer.ok:
		# The send sound once the server took the line (as the old social.gd send_message).
		RpgUi.sfx("chat_out", -6.0)
		echo["sent_id"] = int(answer.data.get("id", -2))
		echo["text"] = str(answer.data.get("text", echo.text))
		if answer.data.has("muted_until"): muted_until = float(answer.data.muted_until)
		# A line the server already delivered while the send was out.
		for line in lines:
			if line != echo and int(line.get("id", -1)) == int(echo.sent_id):
				lines.erase(echo)
				break
		chat.redraw()
		return
	lines.erase(echo)
	RpgUi.sfx("deny", -10.0)
	system_line(send_error(str(answer.get("error", ""))))

func send_error(code: String) -> String:
	return {
		"message_rate_limited":tr("조금 천천히 보내 주세요."),
		"message_repeated":tr("같은 말을 연달아 보낼 수 없어요."),
		"global_chat_slow":tr("전체 대화는 5초에 한 번 보낼 수 있어요."),
		"global_chat_busy":tr("전체 대화가 붐벼요. 잠시 뒤에 보내 주세요."),
		"global_chat_off":tr("이 월드는 전체 대화가 꺼져 있어요."),
		"chat_muted":tr("잠시 대화를 쉬어야 해요."),
		"message_blocked":tr("보낼 수 없는 말이 들어 있어요."),
		"not_in_party":tr("파티에 들어가 있지 않아요."),
		"whisper_target_unavailable":tr("귓속말을 받을 수 없는 상대예요. 접속 중인 친구에게만 보낼 수 있어요."),
		"chat_ip_limited":tr("지금은 보낼 수 없어요. 잠시 뒤에 다시 해 주세요."),
		"message_empty":tr("보낼 내용이 없어요."),
		"connection_failed":tr("연결이 끊겨서 보내지 못했어요."),
	}.get(code, tr("보내지 못했어요."))

# ------------------------------------------------------------------ people and actions

func open_window(tab := "") -> void:
	if not is_instance_valid(place) or hidden_by_window: return
	if drawer.is_empty() or not is_instance_valid(drawer.get("root")):
		drawer = RpgUi.drawer(root_ui, tr("함께하기"), {"side":"left", "width":340.0, "top":108.0, "action":"social", "id":"social_drawer",
			"on_close":close_window})
		window.build(drawer, tab)
		fetch_people()
	elif not tab.is_empty(): window.show_tab(tab)

func close_window() -> void:
	if not drawer.is_empty(): RpgUi.close_window(drawer)
	drawer = {}

func toggle_window() -> void:
	if window.is_open(): close_window()
	else: open_window()

func _process(_delta: float) -> void:
	if stopped or not window.is_open(): return
	var every := float((health.get("social_poll", {}) as Dictionary).get("people", 5.0)) if health.get("social_poll") is Dictionary else 5.0
	if Time.get_ticks_msec() * 0.001 - people_time > every: fetch_people()

func fetch_people() -> void:
	if people_pending or not has("people"): return
	people_pending = true
	people_time = Time.get_ticks_msec() * 0.001
	var answer: Dictionary = await api.request("/v1/social/people")
	people_pending = false
	if stopped or not answer.ok: return
	people = answer.data
	window.refresh()

## A mutation with the shared refusal texts; returns the answer.
func act(path: String, body := {}) -> Dictionary:
	var answer: Dictionary = await api.post(path, api.mutation(body))
	if stopped: return answer
	if not answer.ok: notice(act_error(str(answer.get("error", ""))), "warn")
	return answer

func act_error(code: String) -> String:
	return {
		"user_not_found":tr("그런 이름의 모험가가 없어요."),
		"friend_self":tr("나 자신에게는 신청할 수 없어요."),
		"user_blocked":tr("차단한 사람이에요. 차단을 풀고 다시 해 주세요."),
		"friend_requests_limited":tr("오늘은 친구 신청을 더 보낼 수 없어요."),
		"friend_requests_pending_full":tr("답을 기다리는 신청이 너무 많아요."),
		"friend_list_full":tr("친구가 가득 찼어요."),
		"request_unavailable":tr("이미 처리된 신청이에요."),
		"block_self":tr("나 자신은 차단할 수 없어요."),
		"block_list_full":tr("차단 목록이 가득 찼어요."),
		"report_self":tr("나 자신은 신고할 수 없어요."),
		"report_limited":tr("오늘은 신고를 더 할 수 없어요."),
		"visit_self":tr("내 마을이에요."),
		"host_offline":tr("지금 마을에 없어요."),
		"village_full":tr("마을이 가득 찼어요."),
		"knock_limited":tr("잠시 뒤에 다시 두드려 주세요."),
		"party_expedition_active":tr("탐험 중에는 할 수 없어요."),
		"party_full":tr("파티는 최대 3명이에요."),
		"already_in_party":tr("이미 파티에 있어요."),
		"party_leader_required":tr("파티장만 할 수 있어요."),
		"invite_target_unavailable":tr("초대할 수 없는 상대예요. 이름을 확인해 주세요."),
		"invitation_expired":tr("만료되었거나 이미 처리된 초대예요."),
		"return_home_before_inviting":tr("내 마을로 돌아간 뒤 초대해 주세요."),
		"people_rate_limited":tr("잠시 뒤에 다시 해 주세요."),
		"connection_failed":tr("연결이 끊겼어요."),
	}.get(code, tr("지금은 할 수 없어요."))

func request_friend(username := "", user_id := "") -> void:
	var body := {"username":username} if not username.is_empty() else {"user_id":user_id}
	var answer := await act("/v1/friends/requests", body)
	if not answer.ok: return
	# The outcome's own sound before its notice stands in for the toast's chime (RpgUi message kinds).
	match str(answer.data.get("state", "")):
		"accepted", "friends":
			RpgUi.sfx("friend", -6.0)
			notice(tr("친구가 되었어요!"), "success")
		_:
			RpgUi.sfx("chat_out", -6.0)
			notice(tr("친구 신청을 보냈어요"), "success")
	fetch_people()

func answer_request(id: String, decision: String) -> void:
	if (await act("/v1/friends/requests/%s/%s" % [id, decision])).ok:
		if decision == "accept":
			RpgUi.sfx("friend", -6.0)
			notice(tr("친구가 되었어요!"), "success")
		else: RpgUi.sfx("cancel", -8.0)
		fetch_people()

func remove_friend(user_id: String) -> void:
	if (await act("/v1/friends/remove", {"user_id":user_id})).ok: fetch_people()

func block(user_id: String, username: String) -> void:
	if (await act("/v1/social/blocks", {"user_id":user_id})).ok:
		notice(tr("%s님을 차단했어요") % username, "info")
		lines = lines.filter(func(l): return str(l.get("user_id", "")) != user_id)
		chat.redraw()
		fetch_people()

func unblock(user_id: String) -> void:
	if (await act("/v1/social/blocks/remove", {"user_id":user_id})).ok: fetch_people()

func report(user_id: String, username: String, reason := "abuse") -> void:
	var body := {"user_id":user_id, "reason":reason}
	for line in lines:
		if str(line.get("user_id", "")) == user_id and int(line.get("id", -1)) > 0: body["message_id"] = int(line.id)
	if (await act("/v1/social/report", body)).ok: notice(tr("%s님을 신고했어요. 운영자가 확인해요.") % username, "info")

func set_pref(key: String, value) -> void:
	var answer := await act("/v1/social/prefs", {key:value})
	if answer.ok:
		people["prefs"] = answer.data
		window.refresh()

## 놀러가기: walks straight in (drop-in friends), or knocks on the host's door.
func visit(user_id: String, username: String) -> void:
	if place_kind != "village":
		notice(tr("마을에서 놀러 갈 수 있어요."), "info")
		return
	var answer := await act("/v1/social/visit", {"user_id":user_id})
	if not answer.ok: return
	match str(answer.data.get("state", "")):
		"visiting":
			notice(tr("%s님의 마을로 가요") % username, "success")
			if place.has_method("follow_visit"): place.follow_visit()
		"asked": notice(tr("%s님의 마을 문을 두드렸어요") % username, "info")
		"host_cannot_answer": notice(tr("%s님의 게임은 아직 방문을 받을 수 없어요. 초대를 부탁해 보세요.") % username, "info")

func invite(username: String, kind := "village") -> void:
	if (await act("/v1/social/invites", {"username":username, "kind":kind})).ok:
		RpgUi.sfx("chat_out", -6.0)
		notice(tr("마을 초대를 보냈어요") if kind == "village" else tr("파티 초대를 보냈어요"), "success")

func answer_invite(invitation: Dictionary, decision: String) -> void:
	if is_instance_valid(place) and place.has_method("answer_social_invite"):
		await place.answer_social_invite(invitation, decision)
		return
	var answer := await act("/v1/social/invites/%s/%s" % [str(invitation.get("id", "")), decision])
	if answer.ok and decision == "accept" and str(invitation.get("kind", "")) == "village" and is_instance_valid(place) and place.has_method("leave"):
		# In a room: the village to walk out to is now the host's.
		place.leave()

func eject(user_id: String) -> void:
	if (await act("/v1/social/eject", {"user_id":user_id})).ok: fetch_people()

## The K key and Enter (focus the chat), heard after the place's own keys, so a place that uses
## them first (a dialogue's Enter) keeps them.
func _unhandled_key_input(event: InputEvent) -> void:
	if not is_instance_valid(place) or hidden_by_window or not chat.visible: return
	if not event is InputEventKey or not event.pressed or event.echo: return
	var focus := get_viewport().gui_get_focus_owner()
	if focus is LineEdit or focus is TextEdit: return
	var key := GameSettings.canonical_key(event)
	if key == GameSettings.default_key("social"):
		toggle_window()
		get_viewport().set_input_as_handled()
	elif key in [KEY_ENTER, KEY_KP_ENTER] and chat.can_focus():
		chat.focus()
		get_viewport().set_input_as_handled()
