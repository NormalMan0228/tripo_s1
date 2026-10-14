extends CanvasLayer
## The game version and the server's notices, wherever the player is: the title, the village and
## expeditions (main.gd) and the rooms (studio.gd) each add one and hand it their api.gd.
## The server (server/client_policy.py) tells /health and /v1/client:
##   client.min     older games may not play (426 client_update_required): the update screen
##   client.latest  a newer game is out. An installed game (an export) at the title must update
##                  first: it downloads the patch (patcher.gd) and restarts, or, when the release
##                  needs the installer, opens the download page. While playing, a top banner says
##                  the update happens at the next return to the title. Source runs only show the
##                  banner with a download button.
##   client.patch_manifest_url  the patch list (patches.json)
##   notice         scheduled maintenance: a countdown banner from 30 minutes before (stronger in
##                  the last 5) on every screen. When it starts (503 server_maintenance), a signed-in
##                  game saves its settings, logs out (logout_required: the scene returns to the
##                  title) and shows the maintenance screen with the expected end; it retries by
##                  itself and the player signs in again afterwards.
## A 401 session_reset (the server ended every older session: maintenance, logout-all) also returns
## to the title, with a note asking to sign in again.
## Each reply's X-Villagen-Notice-Version tells a running game that something changed; besides,
## it asks /v1/client about once a minute (the title too). Progress lives on the server.
## The state is static, so it follows the player between the village and the rooms.

## The blocking screen closed (maintenance over): the scene reloads what it shows.
signal resumed
## The player must leave the world now (maintenance began, or the server ended the session): the
## scene clears its session and shows the title. reason: "maintenance" | "session_reset" | "session_expired".
signal logout_required(reason: String)

const RpgUi = preload("res://scripts/rpg_ui.gd")
const Api = preload("res://scripts/api.gd")
const Patcher = preload("res://scripts/patcher.gd")
const POLL_SECONDS := 60.0
const RETRY_SECONDS := 15.0
const WAIT_SECONDS := 45.0
const WARN_SECONDS := 30 * 60
const URGENT_SECONDS := 5 * 60
## Settings are sent this long before maintenance starts (the server refuses everything after).
const SAVE_SECONDS := 20.0
const EMBER := Color("ff9b6a")

static var client := {}
static var notice := {}
static var notice_read := 0
static var seen_version := ""
static var host := ""
static var blocked := ""
static var dismissed := ""
static var checked_at := -100000
## Why the game just left the world (shown on the title until the next sign-in).
static var logout_note := ""
## The maintenance whose settings were already sent.
static var saved_for := ""

var api: Node
var probe: Node
var patcher: Node
var root: Control
var lane: VBoxContainer
var update_pill: PanelContainer
var maintenance_pill: PanelContainer
var note_pill: PanelContainer
var maintenance_time: Label
var maintenance_urgent := false
var screen: Control
var screen_kind := ""
var screen_time: Label
var retry_button: Button
var poll_wait := POLL_SECONDS
## The world being asked right now ("" when none).
var asking := ""
var start_checked := false
## The update screen: "checking", "downloading", "verifying", "restarting", "failed", "waiting", "installer".
var patch_step := ""
var patch_status: Label
var patch_bar: ProgressBar
var patch_readout: Label
var patch_buttons: VBoxContainer
var patch_wait := 0.0

static func is_blocked() -> bool:
	return not blocked.is_empty()

## A new session or another world: forget what the last server said.
static func reset() -> void:
	checked_at = -100000
	client = {}
	notice = {}
	seen_version = ""
	host = ""
	blocked = ""

## Numeric release order: 0.11.10 is newer than 0.11.9; a suffix (-school) is ignored.
static func parse(version: String) -> Array:
	return Patcher._numbers(version)

static func older(version: String, than: String) -> bool:
	return Patcher.older(version, than)

static func needs_update() -> bool:
	return older(Api.client_version(), str(client.get("min", "")))

static func update_available() -> bool:
	return older(Api.client_version(), str(client.get("latest", "")))

## Must this game update before it may go on? Too old for the server, or (an installed game at the
## title) any newer release: the update happens right away, never as an option.
static func must_update(at_title: bool) -> bool:
	return needs_update() or (at_title and update_available() and Patcher.installed_game())

## The version the server wants: the latest, or the minimum when that is higher.
static func wanted_version() -> String:
	var latest := str(client.get("latest", ""))
	var lowest := str(client.get("min", ""))
	return lowest if older(latest, lowest) else latest

func _ready() -> void:
	layer = 90
	name = "VersionGate"
	process_mode = Node.PROCESS_MODE_ALWAYS
	root = Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = RpgUi.night_theme()
	add_child(root)
	lane = VBoxContainer.new()
	lane.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	lane.grow_horizontal = Control.GROW_DIRECTION_BOTH
	lane.offset_top = 10
	lane.alignment = BoxContainer.ALIGNMENT_BEGIN
	lane.add_theme_constant_override("separation", 6)
	lane.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(lane)
	probe = Api.new()
	add_child(probe)
	probe.refused.connect(_on_refused)
	patcher = Patcher.new()
	add_child(patcher)
	patcher.progressed.connect(_on_progress)
	refresh()
	# A room or the village opening while the server is closed shows the screen again.
	if is_blocked(): _open_screen(blocked)

## Follows the scene's connection (server and session) and its replies.
func watch(scene_api: Node) -> void:
	api = scene_api
	if api.has_signal("notice_seen"): api.notice_seen.connect(_on_seen)
	if api.has_signal("refused"): api.refused.connect(_on_refused.bind(api))
	if api.has_signal("session_lost"): api.session_lost.connect(_on_session_lost)
	if online(): host = api.base_url
	poll_wait = 3.0
	# A room that opened while the maintenance already runs (the walk was under way): leave it too.
	if blocked == "server_maintenance": _leave_world.call_deferred()

func online() -> bool:
	return is_instance_valid(api) and not str(api.token).is_empty() and not str(api.base_url).is_empty()

## The world this game plays on (logged in) or would log in to (title).
func current_world() -> String:
	return str(api.base_url) if online() else host

## The title screen: what does this world say about this game? (No login needed.)
func check(world: String) -> void:
	world = world.strip_edges().trim_suffix("/")
	if world.is_empty(): return
	# The title menu and the login card both ask; once in a while is enough. Back at the title after
	# playing, an update announced meanwhile is due now.
	if world == host and Time.get_ticks_msec() - checked_at < 20000:
		_enforce()
		return
	adopt(world)
	checked_at = Time.get_ticks_msec()
	await ask(world)

## Another world than the one last asked: start from nothing.
func adopt(world: String) -> void:
	if world == host: return
	reset()
	_close_screen()
	host = world
	refresh()

## Applies /health or /v1/client and returns the reason this game may not go on ("" when it may).
func apply(data: Dictionary) -> String:
	var policy = data.get("client", {})
	client = policy if policy is Dictionary else {}
	_set_notice(data.get("notice"))
	if data.has("notice_version"): seen_version = str(data.notice_version)
	var reason := ""
	if bool(notice.get("active", false)): reason = "server_maintenance"
	elif must_update(not online()): reason = "client_update_required"
	_set_blocked(reason)
	refresh()
	return reason

## Back at the title with what the server said earlier: an update that waited for the title starts.
func _enforce() -> void:
	if not is_blocked() and must_update(not online()): _set_blocked("client_update_required")
	refresh()

func ask(world := "") -> void:
	var target := world if not world.is_empty() else current_world()
	if target.is_empty() or asking == target: return
	asking = target
	probe.base_url = target
	var reply: Dictionary = await probe.request("/v1/client", {}, HTTPClient.METHOD_GET, false, 8.0)
	if asking == target: asking = ""
	# The player picked another world meanwhile: this answer is not about it.
	if not is_inside_tree() or target != current_world(): return
	if reply.ok: apply(reply.data)
	# A server without notices (older than this feature): nothing to show.
	elif int(reply.get("status", 0)) == 404: apply({})

func _on_seen(version: String) -> void:
	if version == seen_version: return
	seen_version = version
	ask.call_deferred()

func _on_refused(code: String, data: Dictionary, source: Node = null) -> void:
	# A reply that arrives after the logout from a world the title is not looking at: not ours now.
	if source != null and source == api and not online() and str(api.base_url) != host: return
	if code == "server_maintenance": _set_notice(data.get("notice"))
	elif data.get("client") is Dictionary: client = data.client
	_set_blocked(code)
	if code == "server_maintenance": _leave_world()
	refresh()

## The server no longer knows this session: back to the title to sign in again.
func _on_session_lost(code: String) -> void:
	if not online(): return
	logout_note = tr("서버가 모두를 로그아웃시켰어요. 다시 로그인해 주세요.") if code == "session_reset" else tr("접속이 끝났어요. 다시 로그인해 주세요.")
	logout_required.emit(code)
	refresh()

func _set_notice(value) -> void:
	notice = value if value is Dictionary else {}
	notice_read = Time.get_ticks_msec()
	start_checked = false

func _set_blocked(reason: String) -> void:
	if reason == blocked and (reason.is_empty() or is_instance_valid(screen)): return
	var was := blocked
	blocked = reason
	if reason.is_empty():
		_close_screen()
		if not was.is_empty(): resumed.emit()
	else:
		if reason == "server_maintenance" and online(): logout_note = _maintenance_note()
		_open_screen(reason)
		if reason == "server_maintenance": _leave_world()

func _maintenance_note() -> String:
	return tr("서버 점검이 시작되어 로그아웃했어요. 점검이 끝나면 다시 로그인해 주세요.")

## Maintenance began while signed in: what can be kept is kept, then the scene logs out (the scene
## clears its token right away, so this happens once).
func _leave_world() -> void:
	if not online(): return
	_save_local()
	# A screen built before the note (another scene's gate) is built again with it.
	var rebuild := logout_note != _maintenance_note() and is_instance_valid(screen) and screen_kind == "server_maintenance"
	logout_note = _maintenance_note()
	logout_required.emit("maintenance")
	if rebuild: _open_screen(screen_kind)

## Progress lives on the server; the account's settings (sound, keys, HUD) are sent while it listens.
func _save_local() -> void:
	var cloud := get_node_or_null("/root/CloudPrefs")
	if cloud and cloud.has_method("push") and not str(cloud.get("token")).is_empty() and not bool(cloud.get("busy")): cloud.push()

## Seconds until the notice starts / ends, counted down here since it was read.
func seconds_to_start() -> float:
	return float(notice.get("starts_in", 0)) - (Time.get_ticks_msec() - notice_read) / 1000.0

func seconds_to_end() -> float:
	return float(notice.get("ends_in", 0)) - (Time.get_ticks_msec() - notice_read) / 1000.0

func _process(delta: float) -> void:
	poll_wait -= delta
	if poll_wait <= 0.0:
		poll_wait = RETRY_SECONDS if is_blocked() else POLL_SECONDS
		# The title and login screens ask too: a maintenance notice posted while a player waits there
		# (before signing in) shows its countdown instead of surprising them after login. An update
		# screen at work does not need the server meanwhile.
		var patching := blocked == "client_update_required" and patch_step in ["checking", "downloading", "verifying", "restarting"]
		if (online() or not host.is_empty()) and not patching: ask()
	if patch_step == "waiting":
		patch_wait -= delta
		if patch_wait <= 0.0: _run_patch()
	if notice.is_empty(): return
	var left := seconds_to_start()
	var active := bool(notice.get("active", false))
	if not active and left <= SAVE_SECONDS and online() and saved_for != str(notice.get("id", "")):
		saved_for = str(notice.get("id", ""))
		_save_local()
	if not active and left <= 0.0 and not start_checked:
		# Maintenance is starting now: ask, and the maintenance screen takes over.
		start_checked = true
		ask()
	# Thirty minutes before: the countdown banner appears.
	if not active and left <= WARN_SECONDS and not is_instance_valid(maintenance_pill): refresh()
	if is_instance_valid(maintenance_pill): _tick_pill(left)
	if is_instance_valid(screen_time) and screen_kind == "server_maintenance": screen_time.text = _end_text()

## Stops keys reaching the world under the blocking screen (its own buttons still work).
func _shortcut_input(event: InputEvent) -> void:
	if is_blocked() and (event is InputEventKey or event is InputEventJoypadButton): get_viewport().set_input_as_handled()

# ------------------------------------------------------------------ banners

func refresh() -> void:
	if not is_instance_valid(lane): return
	var warn: bool = not notice.is_empty() and not bool(notice.get("active", false)) and seconds_to_start() <= WARN_SECONDS
	if warn and not is_instance_valid(maintenance_pill): _build_maintenance_pill()
	elif not warn and is_instance_valid(maintenance_pill):
		maintenance_pill.queue_free()
		maintenance_pill = null
	var latest := str(client.get("latest", ""))
	var show_update := update_available() and not must_update(not online()) and dismissed != latest
	if show_update and is_instance_valid(update_pill) and update_pill.get_meta("version", "") != latest:
		update_pill.queue_free()
		update_pill = null
	if show_update and not is_instance_valid(update_pill): _build_update_pill(latest)
	elif not show_update and is_instance_valid(update_pill):
		update_pill.queue_free()
		update_pill = null
	# The sign-in-again note stays on the title until the player is back in.
	if online(): logout_note = ""
	var note := not logout_note.is_empty()
	if note and (not is_instance_valid(note_pill) or note_pill.get_meta("text", "") != logout_note):
		if is_instance_valid(note_pill): note_pill.queue_free()
		_build_note_pill(logout_note)
	elif not note and is_instance_valid(note_pill):
		note_pill.queue_free()
		note_pill = null
	lane.visible = not is_blocked()

func _pill() -> HBoxContainer:
	var pill := PanelContainer.new()
	pill.add_theme_stylebox_override("panel", RpgUi.panel_style("pill"))
	pill.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	pill.mouse_filter = Control.MOUSE_FILTER_PASS
	lane.add_child(pill)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	pill.add_child(row)
	# Scale and fade only: the lane (a container) places the pills, so position must stay its own.
	RpgUi.pop_in(pill, 0.3, 0.88)
	return row

func _close_button(row: HBoxContainer, on_close: Callable) -> void:
	var close := Button.new()
	close.flat = true
	close.icon = load(RpgUi.painted("res://assets/ui/close.svg"))
	close.expand_icon = true
	close.custom_minimum_size = Vector2(30, 30)
	close.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	close.focus_mode = Control.FOCUS_NONE
	close.tooltip_text = tr("닫기")
	close.pressed.connect(func():
		on_close.call()
		RpgUi.sfx("close")
		refresh())
	row.add_child(close)

func _build_update_pill(latest: String) -> void:
	var row := _pill()
	update_pill = row.get_parent()
	update_pill.set_meta("version", latest)
	var glint := RpgUi.icon("res://assets/starseed.svg", 26)
	glint.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(glint)
	var title := RpgUi.label(row, tr("새 버전이 있어요"), 16, RpgUi.GOLD)
	title.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var number := RpgUi.numbers(RpgUi.label(row, "v" + latest, 16, RpgUi.INK), 16)
	number.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	if Patcher.installed_game():
		# An installed game updates itself at the title: nothing to download by hand.
		var later := RpgUi.label(row, tr("타이틀로 돌아가면 업데이트해요"), 14, Color(RpgUi.INK, .8))
		later.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	else:
		var url := str(client.get("download_url", ""))
		if url.begins_with("https://"):
			var fetch := _button(row, tr("받기"), func(): open_download(), 92, true)
			fetch.custom_minimum_size.y = 38
			fetch.add_theme_font_size_override("font_size", 16)
	_close_button(row, func(): dismissed = latest)
	RpgUi.sfx("toast", -12.0)

func _build_note_pill(text: String) -> void:
	var row := _pill()
	note_pill = row.get_parent()
	note_pill.set_meta("text", text)
	lane.move_child(note_pill, 0)
	var badge := RpgUi.icon("res://assets/ui/gear.svg", 24)
	badge.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(badge)
	var words := RpgUi.label(row, text, 15, RpgUi.INK)
	words.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_close_button(row, func(): logout_note = "")

func _build_maintenance_pill() -> void:
	var row := _pill()
	maintenance_pill = row.get_parent()
	# Maintenance matters more than a new version: it goes on top.
	lane.move_child(maintenance_pill, 0)
	maintenance_urgent = false
	var clock := RpgUi.icon("res://assets/ui/clock.svg", 26)
	clock.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(clock)
	var words := VBoxContainer.new()
	words.add_theme_constant_override("separation", 0)
	row.add_child(words)
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 8)
	words.add_child(line)
	RpgUi.label(line, tr("서버 점검까지"), 16, RpgUi.GOLD)
	maintenance_time = RpgUi.numbers(RpgUi.label(line, "", 18, RpgUi.INK), 18)
	var about := str(notice.get("message", ""))
	if not about.is_empty():
		var detail := RpgUi.label(words, about, 13, Color(RpgUi.INK, .8))
		detail.custom_minimum_size.x = 260
		detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_tick_pill(seconds_to_start())

func _tick_pill(left: float) -> void:
	var text := _clock(left)
	if maintenance_time.text != text: maintenance_time.text = text
	var urgent := left <= URGENT_SECONDS
	if urgent == maintenance_urgent: return
	maintenance_urgent = urgent
	# The last five minutes: an ember glow and a slow pulse that is hard to miss.
	maintenance_time.add_theme_color_override("font_color", EMBER if urgent else RpgUi.INK)
	maintenance_pill.self_modulate = Color(1.0, .78, .66) if urgent else Color.WHITE
	if urgent:
		RpgUi.sfx("toast", -6.0)
		if not RpgUi.calm():
			maintenance_pill.pivot_offset = maintenance_pill.size * 0.5
			var pulse := maintenance_pill.create_tween().set_loops()
			pulse.tween_property(maintenance_pill, "scale", Vector2.ONE * 1.06, 0.5).set_trans(Tween.TRANS_SINE)
			pulse.tween_property(maintenance_pill, "scale", Vector2.ONE, 0.7).set_trans(Tween.TRANS_SINE)

static func _clock(seconds: float) -> String:
	var whole := maxi(0, ceili(seconds))
	if whole >= 3600: return "%d:%02d:%02d" % [whole / 3600, (whole / 60) % 60, whole % 60]
	return "%d:%02d" % [whole / 60, whole % 60]

func _end_text() -> String:
	var left := seconds_to_end()
	if left <= 30.0: return tr("곧 끝나요")
	return tr("약 %d분 뒤 끝나요") % ceili(left / 60.0)

## The expected end on the player's own clock ("" when unknown).
func _end_clock() -> String:
	var ends := int(notice.get("ends_at", 0))
	if ends <= 0: return ""
	var local := Time.get_datetime_dict_from_unix_time(ends + Api.utc_offset_minutes() * 60)
	return tr("끝나는 시각 %02d:%02d (예상)") % [local.hour, local.minute]

# ------------------------------------------------------------------ blocking screens

## The dimmed frame and card every blocking screen uses; returns the card's column.
func _frame() -> VBoxContainer:
	_close_screen()
	screen = Control.new()
	screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	screen.mouse_filter = Control.MOUSE_FILTER_STOP
	root.add_child(screen)
	var dim := ColorRect.new()
	dim.color = Color(0.02, 0.03, 0.04, 0.8)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	screen.add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	screen.add_child(center)
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", RpgUi.panel_style("night"))
	card.custom_minimum_size.x = 470
	center.add_child(card)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	column.alignment = BoxContainer.ALIGNMENT_CENTER
	card.add_child(column)
	RpgUi.pop_in(card, 0.3)
	lane.visible = false
	return column

func _badge(column: VBoxContainer, path: String, spin: bool) -> void:
	var badge := RpgUi.icon(path, 64)
	badge.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	column.add_child(badge)
	if RpgUi.calm(): return
	badge.pivot_offset = Vector2(32, 32)
	var motion := badge.create_tween().set_loops()
	if spin: motion.tween_property(badge, "rotation", TAU, 6.0).from(0.0)
	else:
		motion.tween_property(badge, "scale", Vector2.ONE * 1.12, 0.8).set_trans(Tween.TRANS_SINE)
		motion.tween_property(badge, "scale", Vector2.ONE, 0.8).set_trans(Tween.TRANS_SINE)

func _versions(column: VBoxContainer) -> void:
	var versions := HBoxContainer.new()
	versions.alignment = BoxContainer.ALIGNMENT_CENTER
	versions.add_theme_constant_override("separation", 14)
	column.add_child(versions)
	RpgUi.numbers(RpgUi.label(versions, "v" + Api.client_version(), 22, Color(RpgUi.INK, .55)), 22)
	RpgUi.label(versions, "→", 24, RpgUi.GOLD)
	RpgUi.numbers(RpgUi.label(versions, "v" + wanted_version(), 28, RpgUi.GOLD), 28)

func _open_screen(reason: String) -> void:
	if reason == "client_update_required" and Patcher.installed_game() and not Patcher.manifest_address(client).is_empty():
		_open_patch_screen()
		return
	if reason == "client_update_required":
		_open_installer_screen("")
		return
	var column := _frame()
	screen_kind = reason
	RpgUi.ribbon(column, tr("서버 점검 중"), true, 24).size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_badge(column, "res://assets/ui/gear.svg", true)
	screen_time = RpgUi.label(column, _end_text(), 26, RpgUi.GOLD)
	screen_time.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var ends := _end_clock()
	if not ends.is_empty(): _line(column, ends, 15, Color(RpgUi.INK, .8))
	var about := str(notice.get("message", ""))
	if not about.is_empty(): _line(column, about, 16, RpgUi.INK)
	if not logout_note.is_empty(): _line(column, logout_note, 15, RpgUi.GOLD)
	_line(column, tr("진행 상황은 서버에 안전하게 남아 있어요."), 14, Color(RpgUi.INK, .7))
	RpgUi.divider(column, Color(RpgUi.GOLD, .8))
	retry_button = _button(column, tr("다시 시도"), func(): retry(), 320, true)
	_button(column, tr("게임 종료"), func(): get_tree().quit(), 320, false)
	RpgUi.sfx("open")
	retry_button.grab_focus.call_deferred()

## No patch can do it: the installer page (the address comes from the server).
func _open_installer_screen(why: String) -> void:
	var column := _frame()
	screen_kind = "client_update_required"
	patch_step = "installer"
	RpgUi.ribbon(column, tr("업데이트 필요"), false, 24).size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_badge(column, "res://assets/starseed.svg", false)
	_versions(column)
	_line(column, tr("새 버전을 받아야 계속할 수 있어요."), 17, RpgUi.INK)
	if not why.is_empty(): _line(column, why, 15, RpgUi.GOLD)
	_line(column, tr("진행 상황은 서버에 안전하게 남아 있어요."), 14, Color(RpgUi.INK, .7))
	RpgUi.divider(column, Color(RpgUi.GOLD, .8))
	var url := str(client.get("download_url", ""))
	var first := _button(column, tr("새 버전 받기"), func(): open_download(), 320, true)
	first.disabled = not url.begins_with("https://")
	if first.disabled: _line(column, tr("받는 곳은 운영자 공지를 확인해 주세요."), 13, Color(RpgUi.INK, .7))
	_button(column, tr("게임 종료"), func(): get_tree().quit(), 320, false)
	RpgUi.sfx("open")
	if not first.disabled: first.grab_focus.call_deferred()

## The installed game patches itself: list, download with progress, check, restart.
func _open_patch_screen() -> void:
	var column := _frame()
	screen_kind = "client_update_required"
	RpgUi.ribbon(column, tr("업데이트"), false, 24).size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_badge(column, "res://assets/starseed.svg", false)
	_versions(column)
	patch_status = _line(column, "", 17, RpgUi.INK)
	var meter := VBoxContainer.new()
	meter.add_theme_constant_override("separation", 4)
	meter.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	column.add_child(meter)
	patch_bar = ProgressBar.new()
	patch_bar.custom_minimum_size = Vector2(400, 16)
	patch_bar.show_percentage = false
	patch_bar.add_theme_stylebox_override("background", RpgUi.frame("bar_bg"))
	patch_bar.add_theme_stylebox_override("fill", RpgUi.frame("bar_fill", RpgUi.GOLD))
	meter.add_child(patch_bar)
	patch_readout = RpgUi.numbers(RpgUi.label(meter, "", 14, Color(RpgUi.INK, .8)), 14)
	patch_readout.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_line(column, tr("진행 상황은 서버에 안전하게 남아 있어요."), 14, Color(RpgUi.INK, .7))
	RpgUi.divider(column, Color(RpgUi.GOLD, .8))
	patch_buttons = VBoxContainer.new()
	patch_buttons.add_theme_constant_override("separation", 10)
	column.add_child(patch_buttons)
	RpgUi.sfx("open")
	patch_step = ""
	_run_patch()

func _patch_show(step: String, text: String, bar := -1.0) -> void:
	patch_step = step
	if not is_instance_valid(patch_status): return
	patch_status.text = text
	patch_bar.indeterminate = bar < 0.0 and step in ["checking", "verifying"]
	if bar >= 0.0: patch_bar.value = bar * 100.0
	patch_bar.get_parent().visible = step in ["checking", "downloading", "verifying", "restarting"]
	for child in patch_buttons.get_children(): child.queue_free()
	if step in ["failed", "waiting"]:
		var again := _button(patch_buttons, tr("다시 시도"), func(): _run_patch(), 320, true)
		again.grab_focus.call_deferred()
		if step == "failed" and str(client.get("download_url", "")).begins_with("https://"):
			_button(patch_buttons, tr("설치 파일 받기"), func(): open_download(), 320, false)
	if step != "restarting": _button(patch_buttons, tr("게임 종료"), func(): get_tree().quit(), 320, false)

func _run_patch() -> void:
	if patch_step in ["checking", "downloading", "verifying", "restarting"] or not is_instance_valid(patch_status): return
	var opened := screen
	_patch_show("checking", tr("새 버전을 확인하고 있어요…"))
	var url := Patcher.manifest_address(client)
	var manifest: Dictionary = await patcher.fetch_manifest(url)
	if screen != opened or not is_instance_valid(opened): return
	if manifest.has("error"):
		_patch_show("failed", tr("업데이트 정보를 받지 못했어요. 인터넷 연결을 확인하고 다시 시도해 주세요."))
		return
	var step := Patcher.plan(manifest, url, Patcher.base_version(), Api.client_version(), wanted_version())
	match str(step.action):
		"none":
			# Already current after all (the server lowered its versions meanwhile).
			patch_step = ""
			_set_blocked("")
			return
		"wait":
			patch_wait = WAIT_SECONDS
			_patch_show("waiting", tr("새 버전을 준비하고 있어요. 잠시 뒤 다시 확인할게요."))
			return
		"reinstall":
			var why := tr("이번 업데이트는 게임을 새로 설치해야 해요.")
			if str(step.reason) == "no_patch_for_base": why = tr("이 버전은 너무 오래되어 게임을 새로 설치해야 해요.")
			elif str(step.reason) == "patch_failed": why = tr("패치가 이 PC에서 실행되지 않았어요. 게임을 새로 설치해 주세요.")
			_open_installer_screen(why)
			return
	_patch_show("downloading", tr("패치를 받고 있어요"), 0.0)
	_on_progress(0, int(step.size))
	var problem: String = await patcher.install(step)
	if screen != opened or not is_instance_valid(opened): return
	if not problem.is_empty():
		var text := tr("받은 파일이 손상되었어요. 다시 시도해 주세요.") if problem == "checksum" else tr("패치를 받다가 멈췄어요. 다시 시도하면 이어서 받아요.")
		_patch_show("failed", text)
		return
	_patch_show("restarting", tr("업데이트 완료! 게임을 다시 시작해요."), 1.0)
	RpgUi.sfx("confirm")
	await get_tree().create_timer(1.2).timeout
	if screen == opened: Patcher.restart(get_tree())

func _on_progress(done: int, total: int) -> void:
	if not is_instance_valid(patch_bar) or total <= 0: return
	if patch_step == "downloading" and done >= total:
		patch_step = "verifying"
		patch_status.text = tr("받은 파일을 확인하고 있어요…")
	patch_bar.indeterminate = false
	patch_bar.value = 100.0 * done / total
	patch_readout.text = "%s / %s" % [_megabytes(done), _megabytes(total)]

static func _megabytes(bytes: int) -> String:
	return "%.1f MB" % (bytes / 1048576.0)

func _line(parent: Node, value: String, size: int, color: Color) -> Label:
	var l := RpgUi.label(parent, value, size, color)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.custom_minimum_size.x = 400
	return l

func _button(parent: Node, value: String, callback: Callable, width: float, gold: bool) -> Button:
	var b := RpgUi.menu_button(parent, value, callback, width)
	b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	b.focus_mode = Control.FOCUS_ALL
	if gold:
		b.theme_type_variation = "GoldButton"
		b.add_theme_color_override("font_hover_color", RpgUi.PAPER_INK)
		b.add_theme_color_override("font_focus_color", RpgUi.PAPER_INK)
	return b

func _close_screen() -> void:
	if is_instance_valid(screen): screen.queue_free()
	screen = null
	screen_kind = ""
	screen_time = null
	retry_button = null
	patch_status = null
	patch_bar = null
	patch_readout = null
	patch_buttons = null
	patch_step = ""
	if is_instance_valid(lane): lane.visible = true

func retry() -> void:
	if not asking.is_empty(): return
	if is_instance_valid(retry_button):
		retry_button.disabled = true
		retry_button.text = tr("확인하는 중…")
	await ask()
	if is_instance_valid(retry_button):
		retry_button.disabled = false
		retry_button.text = tr("다시 시도")
		if is_blocked():
			# Still closed: a small shake says "not yet".
			var at := retry_button.position
			var shake := retry_button.create_tween()
			for dx in [-6.0, 5.0, -3.0, 0.0]: shake.tween_property(retry_button, "position:x", at.x + dx, 0.05)

func open_download() -> void:
	var url := str(client.get("download_url", ""))
	# Only web pages: the address comes from the server, and shell_open would also run programs.
	if url.begins_with("https://"):
		RpgUi.sfx("confirm")
		OS.shell_open(url)
