extends Node
## Settings follow the account, online-game style: after login the account's settings are read from the
## server (/v1/prefs) and written into this PC's settings file, and later changes are sent back, so a
## fresh install (or wiped data) on any PC plays with the same sound, keys, gameplay options, HUD folds
## and shadow-folk progress. Graphics/display, the last server and the remembered username stay with
## the PC. Autoloaded; main.gd calls start() once a login has a token.
## Scripts are loaded when needed, not held by this autoload: keeping RpgUi (themes, fonts) alive in an
## autoload made the engine crash while shutting down (4.7.2, access violation at exit).
const I18N_PATH := "res://scripts/i18n.gd"
const SYNCED := ["audio", "controls", "gameplay", "accessibility", "input", "hud", "shadow_folk"]
## [game] keys that follow the account; server, username and the legacy graphics level do not.
const SYNCED_GAME_KEYS := ["language"]
const CHECK_SECONDS := 2.0

var url := ""
var token := ""
var sent := ""
var wait := 0.0
var busy := false

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS

## Reads the account's settings; a first login uploads this PC's settings instead.
func start(base_url: String, session_token: String) -> void:
	url = base_url
	token = session_token
	sent = ""
	var reply := await _call(HTTPClient.METHOD_GET, {})
	if reply.is_empty() or token != session_token: return
	var prefs = reply.get("prefs", {})
	if prefs is Dictionary and not prefs.is_empty(): apply(prefs)
	else: await push()
	sent = JSON.stringify(snapshot())

func stop() -> void:
	url = ""
	token = ""

## This PC's account-wide settings, as sections of simple values.
func snapshot() -> Dictionary:
	var config := ConfigFile.new()
	config.load(load(I18N_PATH).settings_path())
	var out := {}
	for section in SYNCED:
		if not config.has_section(section): continue
		var values := {}
		for key in config.get_section_keys(section): values[key] = config.get_value(section, key)
		out[section] = values
	var game := {}
	for key in SYNCED_GAME_KEYS:
		if config.has_section_key("game", key): game[key] = config.get_value("game", key)
	if not game.is_empty(): out["game"] = game
	return out

## Writes the account's settings into this PC's file and applies them now.
func apply(prefs: Dictionary) -> void:
	var I18n: GDScript = load(I18N_PATH)
	var GameSettings: GDScript = load("res://scripts/game_settings.gd")
	var config := ConfigFile.new()
	config.load(I18n.settings_path())
	var language_before := str(config.get_value("game", "language", ""))
	for section in SYNCED:
		if not prefs.has(section) or not prefs[section] is Dictionary: continue
		if config.has_section(section): config.erase_section(section)
		for key in prefs[section]: config.set_value(section, key, prefs[section][key])
	var game = prefs.get("game", {})
	if game is Dictionary:
		for key in SYNCED_GAME_KEYS:
			if game.has(key): config.set_value("game", key, game[key])
	config.save(I18n.settings_path())
	GameSettings.reload_settings()
	var language := str(config.get_value("game", "language", ""))
	if language != language_before and not language.is_empty(): I18n.set_language(language)
	GameSettings.apply_all(get_tree())
	load("res://scripts/rpg_ui.gd").reload_folds()

func push() -> void:
	busy = true
	var current := snapshot()
	var reply := await _call(HTTPClient.METHOD_POST, {"prefs": current})
	if not reply.is_empty(): sent = JSON.stringify(current)
	busy = false

func _process(delta: float) -> void:
	if token.is_empty() or busy: return
	wait -= delta
	if wait > 0.0: return
	wait = CHECK_SECONDS
	if JSON.stringify(snapshot()) != sent: push()

func _call(method: int, body: Dictionary) -> Dictionary:
	var http := HTTPRequest.new()
	http.timeout = 10.0
	http.max_redirects = 0
	add_child(http)
	var headers := PackedStringArray(["Content-Type: application/json", "Authorization: Bearer " + token])
	if method == HTTPClient.METHOD_POST: body["request_id"] = _uuid()
	var error := http.request(url + "/v1/prefs", headers, method, JSON.stringify(body) if method == HTTPClient.METHOD_POST else "")
	if error != OK:
		http.queue_free()
		return {}
	var response: Array = await http.request_completed
	http.queue_free()
	if response[0] != HTTPRequest.RESULT_SUCCESS or response[1] != 200: return {}
	var data = JSON.parse_string((response[3] as PackedByteArray).get_string_from_utf8())
	return data if data is Dictionary else {}

func _uuid() -> String:
	var bytes := Crypto.new().generate_random_bytes(16)
	bytes[6] = (bytes[6] & 15) | 64
	bytes[8] = (bytes[8] & 63) | 128
	var s := bytes.hex_encode()
	return "%s-%s-%s-%s-%s" % [s.substr(0, 8), s.substr(8, 4), s.substr(12, 4), s.substr(16, 4), s.substr(20, 12)]
