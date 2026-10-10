extends CanvasLayer
## The game version and the server's notices, wherever the player is: the title, the village and
## expeditions (main.gd) and the rooms (studio.gd) each add one and hand it their api.gd.
## The server (server/client_policy.py) tells /health and /v1/client:
##   client.min     older games may not play (426 client_update_required): a blocking update window
##   client.latest  a newer game is out: a gentle top banner with a download button
##   notice         scheduled maintenance: a countdown banner from 30 minutes before (stronger in
##                  the last 5), then, while it runs (503 server_maintenance), a clean maintenance
##                  screen that retries by itself
## Each reply's X-Villagen-Notice-Version tells a running game that something changed; besides,
## it asks /v1/client about once a minute. Progress lives on the server, so nothing is lost.
## The state is static, so it follows the player between the village and the rooms.

## The blocking screen closed (maintenance over): the scene reloads what it shows.
signal resumed

const RpgUi = preload("res://scripts/rpg_ui.gd")
const Api = preload("res://scripts/api.gd")
const POLL_SECONDS := 60.0
const RETRY_SECONDS := 15.0
const WARN_SECONDS := 30 * 60
const URGENT_SECONDS := 5 * 60
const EMBER := Color("ff9b6a")

static var client := {}
static var notice := {}
static var notice_read := 0
static var seen_version := ""
static var host := ""
static var blocked := ""
static var dismissed := ""
static var checked_at := -100000

var api: Node
var probe: Node
var root: Control
var lane: VBoxContainer
var update_pill: PanelContainer
var maintenance_pill: PanelContainer
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
	var digits := version.strip_edges().trim_prefix("v").split("-")[0].split("+")[0]
	var out := []
	for part in digits.split("."):
		if not part.is_valid_int(): return []
		out.append(int(part))
	while out.size() < 4: out.append(0)
	return out

static func older(version: String, than: String) -> bool:
	var a := parse(version)
	var b := parse(than)
	if b.is_empty(): return false
	if a.is_empty(): return true
	for i in 4:
		if a[i] != b[i]: return a[i] < b[i]
	return false

static func needs_update() -> bool:
	return older(Api.client_version(), str(client.get("min", "")))

static func update_available() -> bool:
	return older(Api.client_version(), str(client.get("latest", "")))

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
	refresh()
	# A room or the village opening while the server is closed shows the screen again.
	if is_blocked(): _open_screen(blocked)

## Follows the scene's connection (server and session) and its replies.
func watch(scene_api: Node) -> void:
	api = scene_api
	if api.has_signal("notice_seen"): api.notice_seen.connect(_on_seen)
	if api.has_signal("refused"): api.refused.connect(_on_refused)
	if online(): host = api.base_url
	poll_wait = 3.0

func online() -> bool:
	return is_instance_valid(api) and not str(api.token).is_empty() and not str(api.base_url).is_empty()

## The world this game plays on (logged in) or would log in to (title).
func current_world() -> String:
	return str(api.base_url) if online() else host

## The title screen: what does this world say about this game? (No login needed.)
func check(world: String) -> void:
	world = world.strip_edges().trim_suffix("/")
	if world.is_empty(): return
	# The title menu and the login card both ask; once in a while is enough.
	if world == host and Time.get_ticks_msec() - checked_at < 20000: return
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
	elif needs_update(): reason = "client_update_required"
	_set_blocked(reason)
	refresh()
	return reason

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

func _on_refused(code: String, data: Dictionary) -> void:
	if code == "server_maintenance": _set_notice(data.get("notice"))
	elif data.get("client") is Dictionary: client = data.client
	_set_blocked(code)
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
	else: _open_screen(reason)

## Seconds until the notice starts / ends, counted down here since it was read.
func seconds_to_start() -> float:
	return float(notice.get("starts_in", 0)) - (Time.get_ticks_msec() - notice_read) / 1000.0

func seconds_to_end() -> float:
	return float(notice.get("ends_in", 0)) - (Time.get_ticks_msec() - notice_read) / 1000.0

func _process(delta: float) -> void:
	poll_wait -= delta
	if poll_wait <= 0.0:
		poll_wait = RETRY_SECONDS if is_blocked() else POLL_SECONDS
		if online() or (is_blocked() and not host.is_empty()): ask()
	if notice.is_empty(): return
	var left := seconds_to_start()
	var active := bool(notice.get("active", false))
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
	var show_update := update_available() and not needs_update() and dismissed != latest
	if show_update and is_instance_valid(update_pill) and update_pill.get_meta("version", "") != latest:
		update_pill.queue_free()
		update_pill = null
	if show_update and not is_instance_valid(update_pill): _build_update_pill(latest)
	elif not show_update and is_instance_valid(update_pill):
		update_pill.queue_free()
		update_pill = null
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
	var url := str(client.get("download_url", ""))
	if url.begins_with("https://"):
		var fetch := _button(row, tr("받기"), func(): open_download(), 92, true)
		fetch.custom_minimum_size.y = 38
		fetch.add_theme_font_size_override("font_size", 16)
	var close := Button.new()
	close.flat = true
	close.icon = load(RpgUi.painted("res://assets/ui/close.svg"))
	close.expand_icon = true
	close.custom_minimum_size = Vector2(30, 30)
	close.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	close.focus_mode = Control.FOCUS_NONE
	close.tooltip_text = tr("닫기")
	close.pressed.connect(func():
		dismissed = latest
		RpgUi.sfx("close")
		refresh())
	row.add_child(close)
	RpgUi.sfx("toast", -12.0)

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

# ------------------------------------------------------------------ blocking screens

func _open_screen(reason: String) -> void:
	_close_screen()
	screen_kind = reason
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
	var update := reason == "client_update_required"
	var ribbon := RpgUi.ribbon(column, tr("업데이트 필요") if update else tr("서버 점검 중"), not update, 24)
	ribbon.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	var badge := RpgUi.icon("res://assets/starseed.svg" if update else "res://assets/ui/gear.svg", 64)
	badge.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	column.add_child(badge)
	if not RpgUi.calm():
		badge.pivot_offset = Vector2(32, 32)
		var spin := badge.create_tween().set_loops()
		if update:
			spin.tween_property(badge, "scale", Vector2.ONE * 1.12, 0.8).set_trans(Tween.TRANS_SINE)
			spin.tween_property(badge, "scale", Vector2.ONE, 0.8).set_trans(Tween.TRANS_SINE)
		else: spin.tween_property(badge, "rotation", TAU, 6.0).from(0.0)
	screen_time = null
	if update:
		var versions := HBoxContainer.new()
		versions.alignment = BoxContainer.ALIGNMENT_CENTER
		versions.add_theme_constant_override("separation", 14)
		column.add_child(versions)
		RpgUi.numbers(RpgUi.label(versions, "v" + Api.client_version(), 22, Color(RpgUi.INK, .55)), 22)
		RpgUi.label(versions, "→", 24, RpgUi.GOLD)
		var target := str(client.get("latest", "")) if not older(str(client.get("latest", "")), str(client.get("min", ""))) else str(client.get("min", ""))
		RpgUi.numbers(RpgUi.label(versions, "v" + target, 28, RpgUi.GOLD), 28)
		_line(column, tr("새 버전을 받아야 계속할 수 있어요."), 17, RpgUi.INK)
	else:
		screen_time = RpgUi.label(column, _end_text(), 26, RpgUi.GOLD)
		screen_time.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		var about := str(notice.get("message", ""))
		if not about.is_empty(): _line(column, about, 16, RpgUi.INK)
	_line(column, tr("진행 상황은 서버에 안전하게 남아 있어요."), 14, Color(RpgUi.INK, .7))
	RpgUi.divider(column, Color(RpgUi.GOLD, .8))
	var first: Button
	if update:
		var url := str(client.get("download_url", ""))
		first = _button(column, tr("새 버전 받기"), func(): open_download(), 320, true)
		first.disabled = not url.begins_with("https://")
		if first.disabled: _line(column, tr("받는 곳은 운영자 공지를 확인해 주세요."), 13, Color(RpgUi.INK, .7))
	else:
		retry_button = _button(column, tr("다시 시도"), func(): retry(), 320, true)
		first = retry_button
	_button(column, tr("게임 종료"), func(): get_tree().quit(), 320, false)
	RpgUi.pop_in(card, 0.3)
	RpgUi.sfx("open")
	if not first.disabled: first.grab_focus.call_deferred()
	lane.visible = false

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
