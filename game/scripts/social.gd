extends Node
## Polling transport for a three-player test. Authority and membership stay on the server.
const AvatarLook = preload("res://scripts/avatar_look.gd")
## Other players' walk, drawn smoothly from the irregular replies (remote_motion.gd).
const RemoteMotion = preload("res://scripts/remote_motion.gd")
## RpgUi (rpg_ui.gd), for the chat, invite and arrival sounds.
const UiSound = preload("res://scripts/rpg_ui.gd")
## The village shares this player's spot four times a second. On an expedition the run carries the
## party's spots, and while a screen loads a slower heartbeat still says this player is here: a
## host who goes quiet for long (server/multiplayer.py HOST_GONE_SECONDS) has left, and the guests
## are sent home.
const POLL_VILLAGE := 0.25
const POLL_AWAY := 2.0
const HEARTBEAT := 3.0
## A reply that does not come within this long is given up (the next poll goes out).
const POLL_TIMEOUT := 4.0
## The host's furniture is read through the guest routes (server/multiplayer.py).
const GUEST_OBJECTS = "/v1/social/village/objects/"
var app: Node3D
var enabled := false
var data: Dictionary = {}
var peers: Dictionary = {}
var timer := 0.0
var pending := false
var changing := false
var objects_pending := false
var object_signature := ""
var seen_message := 0
## Invites counted at the last poll (-1: none read yet), so only a new one chimes.
var seen_invites := -1
## False until the first sync after a world change: the walkers already there arrive silently.
var peer_baseline := false
var status_label: Label
var menu_messages: Label
var last_failure := 0.0
## The spot also carries the walker's velocity and this game's clock (multiplayer.py Presence);
## a server older than that refuses them (422), and the 0.11.4 fields are sent from then on.
var rich_presence := true

## Village visits and co-op are on whenever the server offers them. --no-multiplayer
## hides them for a solo client.
static func feature_enabled() -> bool:
	return not OS.get_cmdline_user_args().has("--no-multiplayer")

func visiting() -> bool:
	return enabled and bool(data.get("visiting", false))

func install_hud(survival: bool) -> void:
	if not feature_enabled() or not enabled: return
	# A compact social chip: two icon keys (함께하기 menu, quick greeting) and a status
	# line. Village: under the character frame. Survival: under the day counter.
	var RpgUi = preload("res://scripts/rpg_ui.gd")
	var plate := PanelContainer.new()
	plate.name = "SocialChip"
	var style: StyleBox = RpgUi.panel_style("pill")
	style.content_margin_left = 10
	style.content_margin_right = 16
	style.content_margin_top = 6
	style.content_margin_bottom = 6
	plate.add_theme_stylebox_override("panel", style)
	plate.position = Vector2(470, 74) if survival else Vector2(14, 108)
	app.ui.add_child(plate)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	plate.add_child(row)
	for spec in [["people", tr("함께하기"), open_menu], ["chat", tr("인사"), func(): send_message(tr("안녕하세요! 👋"))]]:
		var key := Button.new()
		key.custom_minimum_size = Vector2(42, 42)
		key.focus_mode = Control.FOCUS_NONE
		key.theme_type_variation = "HudSlot"
		key.icon = RpgUi.icon_texture(spec[0])
		key.expand_icon = true
		key.tooltip_text = spec[1]
		var action: Callable = spec[2]
		key.pressed.connect(func(): action.call())
		RpgUi.hover_motion(key, 1.1)
		row.add_child(key)
	status_label = RpgUi.label(row, tr("연결 상태 확인 중…"), 12, RpgUi.SOFT)
	status_label.custom_minimum_size.x = 150 if not survival else 220
	status_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if survival: RpgUi.pin(plate, 0.5, 0.0)
	update_status()

func update_status() -> void:
	if not enabled or not is_instance_valid(status_label): return
	var title: String = str(data.get("host_name", app.me.get("username", tr("나"))))+tr("님의 마을")
	var party: Dictionary = data.get("party") if data.get("party") is Dictionary else {}
	var invites: int = data.get("invites", []).size()
	status_label.text = title+(tr(" · 초대 %d개") % invites if invites > 0 else "")
	if not party.is_empty(): status_label.text += tr(" · 파티 %d/3명") % party.members.size()
	if app.screen == "survival" and app.run.get("coop", false):
		status_label.text = tr("협동 생존 · ")+", ".join(PackedStringArray(app.run.get("players", []).map(func(p): return "%s %d♥" % [p.username, p.hp])))
	if is_instance_valid(menu_messages):
		var lines := PackedStringArray()
		for entry in data.get("messages", []): lines.append(entry.username+": "+entry.text)
		menu_messages.text = tr("아직 대화가 없습니다.") if lines.is_empty() else "\n".join(lines)

func reset_world() -> void:
	peers.clear()
	peer_baseline = false
	object_signature = ""

func reset_session() -> void:
	data.clear()
	seen_message = 0
	seen_invites = -1
	reset_world()

func _process(delta: float) -> void:
	if not is_instance_valid(app): return
	for entry in peers.values():
		if not is_instance_valid(entry.node): continue
		entry.motion.update(delta)
		entry.motion.apply_to(entry.node)
	if not enabled or app.api.token.is_empty(): return
	var interval := 0.0
	match app.screen:
		"village": interval = POLL_VILLAGE
		"survival": interval = POLL_AWAY
		"loading": interval = HEARTBEAT
		_: return
	timer += delta
	# The next poll goes out on schedule, or as soon as a slow answer is in (a poll skipped while
	# one was under way halved the rate on a slow connection).
	if timer < interval or pending or changing: return
	timer = 0.0
	if app.screen == "loading": heartbeat()
	else: poll()

## This player's spot, its velocity and the moment (this game's clock) it was taken.
func spot(scene: String) -> Dictionary:
	var body := {"scene":scene}
	var walker = app.player
	if is_instance_valid(walker) and walker.is_inside_tree():
		body.merge({"x":clampf(walker.position.x, -100, 100), "z":clampf(walker.position.z, -100, 100), "y":clampf(walker.position.y, -20, 40),
			"yaw":wrapf(walker.visual.rotation.y if is_instance_valid(walker.visual) else 0.0, -PI, PI)})
		if rich_presence:
			var velocity: Vector3 = walker.get_real_velocity()
			body.merge({"vx":clampf(velocity.x, -30, 30), "vz":clampf(velocity.z, -30, 30)})
	if rich_presence: body.t = RemoteMotion.now()
	return body

## While a screen loads: only "still here" (the answer is not used; the next poll catches up).
func heartbeat() -> void:
	pending = true
	await app.api.post_kept("/v1/social/presence", {"scene":"away"}, POLL_TIMEOUT)
	pending = false

func poll() -> void:
	if pending or changing or not enabled or app.api.token.is_empty(): return
	pending = true
	var epoch: int = app.world_epoch
	var old_host: String = str(data.get("host_id", ""))
	var token: String = app.api.token
	# One kept-alive connection (api.post_kept): a new HTTPS connection per poll cost several round
	# trips each time and made the answers late and uneven.
	var response: Dictionary = await app.api.post_kept("/v1/social/presence", spot("village" if app.screen == "village" else "away"), POLL_TIMEOUT)
	pending = false
	if token != app.api.token or epoch != app.world_epoch: return
	if not response.ok and int(response.get("status", 0)) == 422 and rich_presence:
		rich_presence = false
		return
	if not response.ok:
		if Time.get_ticks_msec()*.001-last_failure > 10:
			last_failure = Time.get_ticks_msec()*.001
			app.message(tr("함께하기 연결을 확인 중입니다. 잠시 후 다시 시도합니다."))
		# Refused (signed out, no longer let in): the host's furniture goes. A dropped connection
		# keeps it; the next answer updates it in place.
		if visiting() and int(response.get("status", 0)) in [401, 403]:
			for id in app.loaded.keys(): app.drop_loaded(id)
			object_signature = ""
		return
	data = response.data
	# The host's residents' home versions (npc_gifts.gd), so a cached house stays current.
	preload("res://scripts/npc_gifts.gd").set_versions(data.get("npc_homes"), data.get("host_id", ""))
	update_status()
	# The first read after signing in is a backlog: shown, not sounded.
	var backlog := seen_message == 0
	var heard := false
	for entry in data.get("messages", []):
		if int(entry.id) > seen_message:
			seen_message = int(entry.id)
			if not backlog and not heard: heard = chat_sound(entry)
			app.message(entry.username+": "+entry.text)
	var invites: int = data.get("invites", []).size()
	if seen_invites >= 0 and invites > seen_invites: UiSound.sfx("friend", -4.0)
	seen_invites = invites
	if app.screen == "village":
		if not old_host.is_empty() and old_host != str(data.host_id):
			changing = true
			await app.enter_village()
			changing = false
			announce_visit_end()
			return
		announce_visit_end()
		if data.get("village") is Dictionary:
			var before := peers.keys()
			sync_peers(data.village.players)
			peer_sounds(before)
			if visiting():
				accept_crops()
				await refresh_guest_objects()
		var party: Dictionary = data.party if data.get("party") is Dictionary else {}
		if not app.busy and not changing and party.get("run_status") == "active" and party.get("can_join_run", false):
			changing = true
			await app.start_run("forest", "standard", "", str(party.run_id))
			changing = false

## The sound of one new chat line, played before its toast (it stands in for the toast chime): none
## for a history line (a replayed backlog) or this player's own line (sending already sounded).
func chat_sound(entry: Dictionary) -> bool:
	if bool(entry.get("history", false)): return false
	if str(entry.get("username", "")) == str(app.me.get("username", "")): return false
	var whisper := bool(entry.get("whisper", false)) or str(entry.get("kind", "")) == "whisper"
	UiSound.sfx("whisper" if whisper else "chat_in", -4.0)
	return true

## A soft chime when another player arrives in this village or leaves it.
func peer_sounds(before: Array) -> void:
	var settled := peer_baseline
	peer_baseline = true
	if not settled: return
	if peers.keys().any(func(id): return not before.has(id)): UiSound.sfx("join", -6.0)
	elif before.any(func(id): return not peers.has(id)): UiSound.sfx("leave", -6.0)

func accept_crops() -> void:
	if not data.get("village") is Dictionary: return
	var crops: Dictionary = data.village.crops
	app.life.state = {"version":crops.version, "plots":crops.plots, "server_time":crops.server_time, "coins":0, "bag":{}, "fishing":null}
	app.life.synced_at = Time.get_ticks_msec()*.001

## Other players in the village or the co-op expedition. Each record carries the player's saved
## look and its version (avatar_version): a body is built in that look, and rebuilt only when the
## version changes (a wardrobe save shows here within one poll, without re-entering).
func sync_peers(players: Array) -> void:
	var retained := {}
	var self_id := str(data.get("self_id", app.run.get("self_id", "")))
	for record in players:
		var id: String = record.id
		if id == self_id:
			# This account's own look, saved on another screen or device, reaches this walker too.
			if record.get("avatar") is Dictionary and record.has("avatar_version"):
				app.adopt_profile({"avatar":record.avatar, "version":int(record.avatar_version)}, true)
			continue
		if record.get("withdrawn", false): continue
		retained[id] = true
		var y = record.get("y")
		var target := Vector3(record.x, .03 if y == null else float(y), record.z)
		var version := int(record.get("avatar_version", -1))
		if not peers.has(id) or not is_instance_valid(peers[id].node):
			var actor := AvatarLook.walker(record.get("avatar", {}), version)
			actor.visual_only = true
			actor.controls_enabled = false
			actor.collision_layer = 0
			actor.collision_mask = 0
			actor.position = target
			app.world.add_child(actor)
			var nameplate := Label3D.new()
			nameplate.position.y = 2.05
			nameplate.font_size = 32
			nameplate.pixel_size = .006
			nameplate.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			preload("res://scripts/art.gd").plate_priority(nameplate)
			actor.add_child(nameplate)
			peers[id] = {"node":actor, "label":nameplate, "motion":RemoteMotion.new()}
		peers[id].motion.push_record(record, target)
		AvatarLook.wear(peers[id].node, record.get("avatar", {}), version, true)
		peers[id].node.sprinting = bool(record.get("sprinting", false))
		peers[id].label.text = str(record.username)+( tr(" · 연결 끊김") if not record.get("online", true) else "")+(tr(" · 관전") if record.get("hp", 100) <= 0 else "")
	for id in peers.keys():
		if not retained.has(id):
			if is_instance_valid(peers[id].node): peers[id].node.queue_free()
			peers.erase(id)

## The host's furniture during a visit follows the host's changes in place (main.sync_placed): only
## a new, removed or repainted object loads or frees a model. Moves, shape edits and interaction
## state update the loaded copy; the host walking up to or using furniture changes its runtime
## version every few moments, and reloading every model each time kept the village loading.
func refresh_guest_objects() -> void:
	if not visiting() or objects_pending or not data.get("village") is Dictionary: return
	var signature: String = str(data.host_id)+JSON.stringify(data.village.objects)
	if signature == object_signature: return
	objects_pending = true
	var epoch: int = app.world_epoch
	var host: String = data.host_id
	var complete: bool = await app.sync_placed(data.village.objects, GUEST_OBJECTS)
	objects_pending = false
	if epoch != app.world_epoch or host != str(data.get("host_id", "")): return
	if complete: object_signature = signature
	accept_crops()

## Why a visit ended, from the server (multiplayer.py visit_ended): said once, in this player's own
## village (the host's room may have sent the walker back already, studio.gd).
func announce_visit_end() -> void:
	var info = data.get("visit_ended")
	if not info is Dictionary or visiting(): return
	var key := str(info.get("at", ""))
	if str(Engine.get_meta("visit_notice_seen", "")) == key: return
	Engine.set_meta("visit_notice_seen", key)
	app.message(visit_end_text(info))

func visit_end_text(info: Dictionary) -> String:
	var host := str(info.get("host_name", ""))
	match str(info.get("reason", "")):
		"left": return tr("%s님이 마을을 떠나서 내 마을로 돌아왔어요.") % host
		"host_lost": return tr("%s님의 연결이 끊겨서 내 마을로 돌아왔어요.") % host
		"ended": return tr("%s님이 방문을 마쳐서 내 마을로 돌아왔어요.") % host
		"lost": return tr("연결이 끊겨서 %s님의 마을에서 내 마을로 돌아왔어요.") % host
	return tr("방문이 끝나서 내 마을로 돌아왔어요.")

## Closing the game (the window, or quitting from the menu: pause_menu.gd sends the same
## notification): the server hears it at once, so friends see this player leave now and guests in
## this village go home (multiplayer.py leave), instead of after the presence times out.
func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST and enabled and is_instance_valid(app) and not app.api.token.is_empty():
		app.api.farewell("/v1/social/offline")

func perform(path: String, payload: Dictionary = {}) -> Dictionary:
	var result: Dictionary = await app.api.post(path, app.api.mutation(payload))
	if not result.ok:
		UiSound.sfx("deny", -4.0)
		var messages := {"host_offline":tr("초대한 친구가 지금 마을에 없어요."), "party_full":tr("파티는 최대 3명입니다."), "village_full":tr("마을은 주인을 포함해 최대 3명입니다."), "already_in_party":tr("이미 파티에 참여 중입니다."), "party_leader_required":tr("파티장만 할 수 있습니다."), "party_members_not_in_village":tr("모두 마을에 접속한 뒤 출발해 주세요."), "member_has_solo_expedition":tr("개인 생존 탐험을 마친 뒤 파티로 출발해 주세요."), "party_needs_two_players":tr("동료를 초대해 2명 이상 모여 주세요."), "party_expedition_active":tr("진행 중인 협동 탐험으로 돌아가 주세요."), "leave_expedition_first":tr("탐험에서 귀환한 뒤 파티를 나갈 수 있습니다."), "invite_target_unavailable":tr("가입한 사용자 이름을 확인해 주세요."), "invitation_expired":tr("만료되었거나 이미 처리된 초대입니다."), "message_rate_limited":tr("메시지는 1초 간격으로 보낼 수 있습니다.")}
		app.message(messages.get(result.error, app.error_message(result.error)))
	return result

func open_menu() -> void:
	if not enabled:
		app.message(tr("이 월드에서는 아직 함께하기를 할 수 없어요."))
		return
	var response: Dictionary = await app.api.request("/v1/social")
	if not app.check(response): return
	data.merge(response.data, true)
	var box: VBoxContainer = app.modal_card(tr("함께하기 · 최대 3명"))
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(700, 400)
	box.add_child(scroll)
	var content := VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(content)
	app.text(content, tr("내 이름: ")+str(app.me.get("username", ""))+" · "+str(data.host_name)+tr("님의 마을"), 16)
	var invite_row := HBoxContainer.new()
	content.add_child(invite_row)
	var name_input := LineEdit.new()
	name_input.placeholder_text = tr("초대할 사용자 이름")
	name_input.max_length = 24
	name_input.custom_minimum_size.x = 220
	name_input.keep_editing_on_text_submit = true
	invite_row.add_child(name_input)
	app.button(invite_row, tr("내 마을로 초대"), func():
		var result: Dictionary = await perform("/v1/social/invites", {"username":name_input.text, "kind":"village"})
		if result.ok: invited(tr("마을 초대를 보냈습니다.")))
	app.button(invite_row, tr("파티로 초대"), func():
		var result: Dictionary = await perform("/v1/social/invites", {"username":name_input.text, "kind":"party"})
		if result.ok: invited(tr("파티 초대를 보냈습니다.")))
	for invitation in data.get("invites", []):
		var row := HBoxContainer.new()
		content.add_child(row)
		app.text(row, invitation.sender+" · "+(tr("마을 방문") if invitation.kind == "village" else tr("파티")), 14)
		app.button(row, tr("수락"), func(): answer(invitation, "accept"))
		app.button(row, tr("거절"), func(): answer(invitation, "decline"))
	var party: Dictionary = data.party if data.get("party") is Dictionary else {}
	if party.is_empty():
		app.button(content, tr("파티 만들기"), func():
			if (await perform("/v1/party")).ok: open_menu())
	else:
		for member in party.members:
			app.text(content, member.username+(tr(" · 파티장") if member.id == party.leader_id else "")+(tr(" · 접속 중") if member.online else tr(" · 연결 대기")), 14)
		if party.run_id != null and party.get("can_join_run", false):
			app.button(content, tr("협동 탐험으로 돌아가기"), func(): app.start_run("forest", "standard", "", str(party.run_id)))
		if str(party.leader_id) == str(data.self_id) and app.screen == "village" and party.run_status != "active":
			app.text(content, tr("모두 마을에 있을 때 함께 출발합니다. 체력·가방은 개인, 자원·적·모닥불은 공유합니다."), 13)
			var choices := HBoxContainer.new()
			content.add_child(choices)
			var region := OptionButton.new()
			for title in [tr("솔바람 숲"), tr("노을 채석장"), tr("서리빛 분지")]: region.add_item(title)
			choices.add_child(region)
			var difficulty := OptionButton.new()
			for title in [tr("산책"), tr("탐험"), tr("개척")]: difficulty.add_item(title)
			difficulty.select(0)
			choices.add_child(difficulty)
			app.button(choices, tr("파티 함께 출발"), func():
				var result: Dictionary = await perform("/v1/party/runs", {"map_id":["forest", "quarry", "frost"][region.selected], "difficulty":["relaxed", "standard", "veteran"][difficulty.selected]})
				if result.ok: await app.start_run("forest", "standard", "", str(result.data.id)))
		app.button(content, tr("파티 나가기"), func():
			if (await perform("/v1/party/leave")).ok: open_menu())
	if visiting():
		app.text(content, tr("방문 중에는 산책과 대화를 할 수 있습니다. 가구·텃밭 편집은 마을 주인만 할 수 있습니다."), 13)
		app.button(content, tr("내 마을로 돌아가기"), return_home)
	elif data.get("village") is Dictionary:
		for person in data.village.players:
			if person.id != data.self_id:
				app.button(content, person.username+tr(" 방문 종료"), func():
					if (await perform("/v1/social/eject", {"user_id":person.id})).ok: open_menu())
	for reward in data.get("pending_rewards", []):
		app.button(content, tr("완료한 협동 탐험 보상 받기"), func():
			if (await perform("/v1/coop/runs/"+reward.id+"/claim")).ok:
				app.message(tr("협동 탐험 보상을 받았습니다."))
				open_menu())
	app.text(content, tr("파티 대화") if not party.is_empty() else tr("마을 대화"), 17)
	menu_messages = app.text(content, "", 13)
	menu_messages.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	menu_messages.custom_minimum_size.x = 640
	var chat := LineEdit.new()
	chat.placeholder_text = tr("메시지를 입력하고 Enter")
	chat.max_length = 160
	# Enter sends and the field stays ready for the next line (Godot otherwise stops editing on
	# Enter: the next message, Korean IME included, did not type until the field was clicked again).
	chat.keep_editing_on_text_submit = true
	content.add_child(chat)
	chat.text_submitted.connect(func(value):
		send_message(value)
		chat.clear())
	app.button(content, tr("초대 확인하기"), open_menu)
	update_status()

## An invite went out: a send sound with its toast.
func invited(text: String) -> void:
	UiSound.sfx("chat_out", -4.0)
	app.message(text)

func answer(invitation: Dictionary, decision: String) -> void:
	if changing: return
	changing = true
	while pending: await get_tree().process_frame
	var response: Dictionary = await perform("/v1/social/invites/"+invitation.id+"/"+decision)
	if not response.ok:
		if response.get("status", 0) == 401:
			app.api.token = ""
			reset_session()
			app.build_world(false)
			app.login_ui()
			app.message(tr("세션이 만료되었습니다. 다시 로그인해 주세요."))
			return
		changing = false
		return
	data.merge(response.data, true)
	changing = false
	UiSound.sfx("friend" if decision == "accept" else "cancel", -4.0)
	app.close_village_modal()
	if invitation.kind == "village" and decision == "accept":
		data.erase("village")
		await poll()
		await app.enter_village()
	else: open_menu()

func return_home() -> void:
	if changing: return
	changing = true
	while pending: await get_tree().process_frame
	if not (await perform("/v1/social/home")).ok:
		changing = false
		return
	data.visiting = false
	data.host_id = data.self_id
	data.erase("village")
	app.close_village_modal()
	await app.enter_village()
	changing = false

func send_message(value: String) -> void:
	if not enabled or value.strip_edges().is_empty(): return
	if (await perform("/v1/social/messages", {"text":value})).ok:
		UiSound.sfx("chat_out", -4.0)
		await poll()
