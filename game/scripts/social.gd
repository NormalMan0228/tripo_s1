extends Node
## Polling transport for a three-player test. Authority and membership stay on the server.
const AvatarLook = preload("res://scripts/avatar_look.gd")
## Other players' walk, drawn smoothly from the irregular replies (remote_motion.gd).
const RemoteMotion = preload("res://scripts/remote_motion.gd")
## RpgUi (rpg_ui.gd), for the arrival, refusal and invite-answer sounds.
const UiSound = preload("res://scripts/rpg_ui.gd")
## The chat box and the 함께하기 drawer live in the social layer that outlives scenes.
const SocialHud = preload("res://scripts/social_hud.gd")
## What each walker carries (presence `held`, held_items.gd).
const HeldItems = preload("res://scripts/held_items.gd")
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
## False until the first sync after a world change: the walkers already there arrive silently.
var peer_baseline := false
## When a join / leave chime last played (ms): a flickering connection chimes at most every 2 s.
var peer_sound_ms := -100000
var status_label: Label
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

## This session's social layer (chat, the 함께하기 drawer), or null without multiplayer.
func hub() -> Node:
	return SocialHud.of(app.api) if enabled and feature_enabled() else null

func install_hud(survival: bool) -> void:
	if not feature_enabled() or not enabled: return
	var layer := hub()
	# The HUD's toast lane is laid after this (a freed one from the last HUD would not pass): the
	# layer finds the place's current lane when it speaks.
	if layer: layer.bind(app, "survival" if survival else "village", app.toast_lane if is_instance_valid(app.toast_lane) else null)
	# The old social chip became the chat box's header (the 함께하기 key, K) everywhere. A shared
	# expedition keeps one small line under the day counter: who is along and their health.
	if not survival or not bool(app.run.get("coop", false)): return
	var RpgUi = preload("res://scripts/rpg_ui.gd")
	var plate := PanelContainer.new()
	plate.name = "CoopLine"
	var style: StyleBox = RpgUi.panel_style("pill")
	style.content_margin_left = 14
	style.content_margin_right = 14
	style.content_margin_top = 3
	style.content_margin_bottom = 3
	plate.add_theme_stylebox_override("panel", style)
	plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
	plate.position = Vector2(500, 64)
	plate.custom_minimum_size = Vector2(280, 0)
	app.ui.add_child(plate)
	status_label = RpgUi.label(plate, "", 12, RpgUi.SOFT)
	status_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	status_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	plate.size = Vector2(280, 24)
	RpgUi.pin(plate, 0.5, 0.0)
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

func reset_world() -> void:
	peers.clear()
	peer_baseline = false
	object_signature = ""

func reset_session() -> void:
	data.clear()
	reset_world()

func _process(delta: float) -> void:
	if not is_instance_valid(app): return
	for entry in peers.values():
		if not is_instance_valid(entry.node): continue
		entry.motion.update(delta)
		entry.motion.apply_to(entry.node)
		# Other players' footsteps: positional, on the other walkers' own voices and take bag
		# (world_audio.stride; about -8 dB under the hero's, fading with distance).
		var audio = app.get("world_audio")
		var place := str(app.get("screen"))
		if place in ["village","survival"] and is_instance_valid(audio) and audio.has_method("stride") and (entry.node as Node3D).is_inside_tree():
			var at: Vector3=(entry.node as Node3D).global_position
			# The ground under them, looked up four times a second (the road test walks every segment).
			if Time.get_ticks_msec()-int(entry.get("ground_at",-1000))>250:
				entry["ground_at"]=Time.get_ticks_msec()
				if place=="village": entry["ground"]="stone" if preload("res://scripts/roads.gd").on_road(Vector2(at.x,at.z)) else "grass"
				else: entry["ground"]=app.region_surface() if app.has_method("region_surface") else "grass"
			audio.stride(entry.audio_key,at,delta,str(entry.get("ground","grass")))
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

## The village seat's standing spot while this walker rests (rest_seat.stand_spot), else null.
func resting_spot():
	if not "seat" in app: return null
	var seat = app.get("seat")
	if not is_instance_valid(seat) or not seat.has_method("stand_spot"): return null
	return seat.stand_spot()

## This player's spot, its velocity and the moment (this game's clock) it was taken.
func spot(scene: String) -> Dictionary:
	var body := {"scene":scene}
	var walker = app.player
	if is_instance_valid(walker) and walker.is_inside_tree():
		var at: Vector3 = walker.position
		# Seated or lying, the body is lowered into the seat and presence carries no pose: others see
		# the walker standing where it stood before it sat down, not sunk into the bench.
		var resting = resting_spot()
		if resting is Vector3:
			at = (walker.get_parent() as Node3D).to_local(resting) if walker.get_parent() is Node3D else resting
		body.merge({"x":clampf(at.x, -100, 100), "z":clampf(at.z, -100, 100), "y":clampf(at.y, -20, 40),
			"yaw":wrapf(walker.visual.rotation.y if is_instance_valid(walker.visual) else 0.0, -PI, PI)})
		if rich_presence:
			var velocity: Vector3 = walker.get_real_velocity() if not resting is Vector3 else Vector3.ZERO
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
	var layer := hub()
	var body := spot("village" if app.screen == "village" else "away")
	# The chat cursor and the place ride along (social_hud.gd), so chat arrives with the walk.
	if layer: body.merge(layer.presence_extra("village" if app.screen == "village" else "expedition"))
	if app.screen == "village": body.merge(HeldItems.presence_extra(layer))
	# One kept-alive connection (api.post_kept): a new HTTPS connection per poll cost several round
	# trips each time and made the answers late and uneven.
	var response: Dictionary = await app.api.post_kept("/v1/social/presence", body, POLL_TIMEOUT)
	pending = false
	if token != app.api.token or epoch != app.world_epoch: return
	if not response.ok and int(response.get("status", 0)) == 422:
		if HeldItems.refused(response): return
		# The newest groups (chat cursor, place) go first, then the 0.11.4 walk fields.
		if layer and layer.presence_refused(response): return
		if rich_presence:
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
	# Chat lines go to the chat box, not the toast lane (social_hud.gd sounds each live line; its
	# invite and knock notices chime as social toasts).
	if layer: layer.ingest(data)
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

## A soft chime when another player arrives in this village or leaves it (one per poll, at most every
## 2 s; the walkers already there when this player arrives come in silently).
func peer_sounds(before: Array) -> void:
	var settled := peer_baseline
	peer_baseline = true
	if not settled or Time.get_ticks_msec() - peer_sound_ms < 2000: return
	var kind := ""
	if peers.keys().any(func(id): return not before.has(id)): kind = "join"
	elif before.any(func(id): return not peers.has(id)): kind = "leave"
	if kind.is_empty(): return
	peer_sound_ms = Time.get_ticks_msec()
	UiSound.sfx(kind, -6.0)

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
			peers[id] = {"node":actor, "label":nameplate, "motion":RemoteMotion.new(), "audio_key":"peer%d" % actor.get_instance_id()}
		peers[id].motion.push_record(record, target)
		AvatarLook.wear(peers[id].node, record.get("avatar", {}), version, true)
		peers[id].node.sprinting = bool(record.get("sprinting", false))
		HeldItems.show_on(peers[id].node, record.get("held", ""))
		peers[id].label.text = str(record.username)+( tr(" · 연결 끊김") if not record.get("online", true) else "")+(tr(" · 관전") if record.get("hp", 100) <= 0 else "")
		# The village's owner, seen by visitors: a crown over a gold name.
		var hosting: bool = app.screen == "village" and str(id) == str(data.get("host_id", "")) and str(id) != str(data.get("self_id", ""))
		peers[id].label.modulate = UiSound.HOVER if hosting else Color.WHITE
		SocialHud.host_crown(peers[id].node, hosting)
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
	# A social toast: its own glyph and chime (ui/toast_social) instead of the generic info one.
	app.message(visit_end_text(info), "social")
	var layer := hub()
	if layer: layer.system_line(visit_end_text(info))

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
		UiSound.sfx("deny", -7.0)
		var messages := {"host_offline":tr("초대한 친구가 지금 마을에 없어요."), "party_full":tr("파티는 최대 3명입니다."), "village_full":tr("마을은 주인을 포함해 최대 3명입니다."), "already_in_party":tr("이미 파티에 참여 중입니다."), "party_leader_required":tr("파티장만 할 수 있습니다."), "party_members_not_in_village":tr("모두 마을에 접속한 뒤 출발해 주세요."), "member_has_solo_expedition":tr("개인 생존 탐험을 마친 뒤 파티로 출발해 주세요."), "party_needs_two_players":tr("동료를 초대해 2명 이상 모여 주세요."), "party_expedition_active":tr("진행 중인 협동 탐험으로 돌아가 주세요."), "leave_expedition_first":tr("탐험에서 귀환한 뒤 파티를 나갈 수 있습니다."), "invite_target_unavailable":tr("가입한 사용자 이름을 확인해 주세요."), "invitation_expired":tr("만료되었거나 이미 처리된 초대입니다."), "message_rate_limited":tr("메시지는 1초 간격으로 보낼 수 있습니다.")}
		app.message(messages.get(result.error, app.error_message(result.error)))
	return result

## The 함께하기 drawer (K): friends, who is online, this village, the party (social_window.gd).
func open_menu() -> void:
	var layer := hub()
	if not layer:
		app.message(tr("이 월드에서는 아직 함께하기를 할 수 없어요."))
		return
	layer.open_window("village")

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
	var layer := hub()
	if layer: layer.ingest(data)
	# A knock let in, or a village invitation taken: the host's village is where this walker is now.
	if decision == "accept" and (invitation.kind == "village" or str(response.data.get("knock", "")) == "visiting"):
		data.erase("village")
		await poll()
		await app.enter_village()

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
	var layer := hub()
	if layer: await layer.send(value)
	elif not (await perform("/v1/social/messages", {"text":value})).ok: return
	# Without the social layer: the send sound once the server took the line.
	else: UiSound.sfx("chat_out", -4.0)
	await poll()

## A chat line said by someone in this village (or this walker): a bubble over their head.
func bubble(user_id: String, username: String, text: String) -> void:
	var actor: Node3D = null
	if peers.has(user_id) and is_instance_valid(peers[user_id].node): actor = peers[user_id].node
	elif is_instance_valid(app.player) and ((not user_id.is_empty() and user_id == str(data.get("self_id", ""))) or username == str(app.me.get("username", ""))): actor = app.player
	if actor: SocialHud.bubble(actor, text)
