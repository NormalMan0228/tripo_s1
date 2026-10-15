extends Node

var base_url := "http://127.0.0.1:8765"
## This game runs the living-objects VM (offset_x/offset_z, the local clock input): the server sends
## crafted programs as they are, not the reduced copies released games get (server/interactions.py).
const VM_HEADER := "X-Villagen-VM: 2"
var token := ""
var mode := "demo"

## Every reply carries the server's notice version (X-Villagen-Notice-Version): it changes when a
## maintenance is scheduled or starts, or a newer game is published (version_gate.gd then asks
## /v1/client what changed).
signal notice_seen(version: String)
## 426 client_update_required (this game is too old) or 503 server_maintenance: version_gate.gd
## shows one clean screen instead of each caller's error.
signal refused(code: String, data: Dictionary)
const GATE_CODES := ["client_update_required", "server_maintenance"]
## 401 for a session the server no longer knows (session_reset: it ended every older session at a
## maintenance; session_expired): version_gate.gd returns the game to its title.
signal session_lost(code: String)
const SESSION_CODES := ["session_reset", "session_expired"]

## The login screen chooses the server; there is no offline or bundled sample play.

func request(path: String, payload: Dictionary = {}, method := HTTPClient.METHOD_GET, binary := false, timeout := 12.0) -> Dictionary:
	var http := HTTPRequest.new()
	# Large uploads (a painted texture) pass a longer timeout.
	http.timeout = timeout
	http.body_size_limit = 20 * 1024 * 1024
	# Redirects must never forward a session credential to another host.
	http.max_redirects = 0
	add_child(http)
	var headers := PackedStringArray(["Content-Type: application/json"])
	if not token.is_empty(): headers.append("Authorization: Bearer " + token)
	headers.append(time_zone_header())
	headers.append(version_header())
	headers.append(VM_HEADER)
	var error := http.request(base_url + path, headers, method, "" if method == HTTPClient.METHOD_GET else JSON.stringify(payload))
	if error != OK:
		http.queue_free()
		return {"ok": false, "error": "connection_failed"}
	var response: Array = await http.request_completed
	http.queue_free()
	if response[0] != HTTPRequest.RESULT_SUCCESS:
		return {"ok": false, "error": "connection_failed"}
	var code: int = response[1]
	_seen(response[2])
	var bytes: PackedByteArray = response[3]
	if binary and code == 200: return {"ok": true, "bytes": bytes}
	var data = parse_body(bytes)
	if not data is Dictionary: return {"ok":false,"error":"invalid_server_response"}
	if code >= 400: return _failure(code, data)
	return {"ok":true,"data":data}

## A reply's JSON body, or null. Quietly: something else answering on the world's address (a web page,
## a proxy's error page) is "invalid_server_response", not an engine error in the log.
static func parse_body(bytes: PackedByteArray) -> Variant:
	var json := JSON.new()
	return json.data if json.parse(bytes.get_string_from_utf8()) == OK else null

func post(path: String, payload: Dictionary) -> Dictionary:
	return await request(path, payload, HTTPClient.METHOD_POST)

## The expedition sends its input ten times a second and the village shares presence four times a
## second. A new HTTPRequest per call opens a fresh TCP + TLS connection every time (several round
## trips to an online world), so these calls share one kept-alive connection. Falls back to a
## normal request when the channel cannot even send (busy, cannot connect); once a request went
## out, a failure is reported as is. timeout: seconds before an unanswered request is given up.
var kept: HTTPClient
var kept_origin := ""
var kept_used := 0
var kept_busy := false

func post_kept(path: String, payload: Dictionary, timeout := 12.0) -> Dictionary:
	if kept_busy: return await request(path, payload, HTTPClient.METHOD_POST, false, timeout)
	kept_busy = true
	var result := await _kept_request(path, JSON.stringify(payload), timeout)
	kept_busy = false
	if result.is_empty(): return await request(path, payload, HTTPClient.METHOD_POST, false, timeout)
	return result

## The server's host, port, TLS and path prefix, from base_url.
func _origin() -> Dictionary:
	var https := base_url.begins_with("https://")
	var rest := base_url.trim_prefix("https://").trim_prefix("http://")
	var slash := rest.find("/")
	var host_port := rest.substr(0, slash) if slash >= 0 else rest
	var origin := {"https":https, "prefix":rest.substr(slash) if slash >= 0 else "", "host":host_port, "port":443 if https else 80}
	var colon := host_port.rfind(":")
	if colon > 0 and host_port.substr(colon + 1).is_valid_int():
		origin.host = host_port.substr(0, colon)
		origin.port = int(host_port.substr(colon + 1))
	return origin

func _headers() -> PackedStringArray:
	var headers := PackedStringArray(["Content-Type: application/json"])
	if not token.is_empty(): headers.append("Authorization: Bearer " + token)
	headers.append(time_zone_header())
	headers.append(version_header())
	headers.append(VM_HEADER)
	return headers

## The kept connection is open to this server and was used recently (servers drop idle keep-alive
## connections, uvicorn after 5 s).
func _kept_ready() -> bool:
	return kept != null and kept.get_status() == HTTPClient.STATUS_CONNECTED and kept_origin == base_url and Time.get_ticks_msec() - kept_used <= 4000

func _kept_request(path: String, body: String, timeout := 12.0) -> Dictionary:
	var origin := _origin()
	if kept == null: kept = HTTPClient.new()
	kept.poll()
	if not _kept_ready():
		kept.close()
		kept_origin = base_url
		if kept.connect_to_host(origin.host, origin.port, TLSOptions.client() if origin.https else null) != OK: return {}
		var connect_deadline := Time.get_ticks_msec() + 8000
		while kept.get_status() in [HTTPClient.STATUS_RESOLVING, HTTPClient.STATUS_CONNECTING]:
			kept.poll()
			if Time.get_ticks_msec() > connect_deadline: break
			await get_tree().process_frame
		if kept.get_status() != HTTPClient.STATUS_CONNECTED:
			kept.close()
			return {}
	if kept.request(HTTPClient.METHOD_POST, origin.prefix + path, _headers(), body) != OK:
		kept.close()
		return {}
	kept_used = Time.get_ticks_msec()
	var deadline := Time.get_ticks_msec() + int(timeout * 1000)
	while kept.get_status() == HTTPClient.STATUS_REQUESTING:
		kept.poll()
		if Time.get_ticks_msec() > deadline: break
		if kept.get_status() == HTTPClient.STATUS_REQUESTING: await get_tree().process_frame
	if not kept.has_response():
		kept.close()
		return {"ok": false, "error": "connection_failed"}
	var code := kept.get_response_code()
	_seen(kept.get_response_headers())
	var bytes := PackedByteArray()
	while kept.get_status() == HTTPClient.STATUS_BODY:
		kept.poll()
		var chunk := kept.read_response_body_chunk()
		if chunk.is_empty():
			if Time.get_ticks_msec() > deadline:
				kept.close()
				return {"ok": false, "error": "connection_failed"}
			await get_tree().process_frame
		else: bytes.append_array(chunk)
		if bytes.size() > 20 * 1024 * 1024:
			kept.close()
			return {"ok": false, "error": "connection_failed"}
	kept_used = Time.get_ticks_msec()
	var data = parse_body(bytes)
	if not data is Dictionary: return {"ok":false,"error":"invalid_server_response"}
	if code >= 400: return _failure(code, data)
	return {"ok":true,"data":data}

## The game is closing: one last POST (the social offline call), sent at once and waited for at
## most budget_ms, since nothing runs after this. Uses the kept connection when it is open and
## free, otherwise a short-lived one.
func farewell(path: String, budget_ms := 700) -> void:
	if token.is_empty(): return
	var deadline := Time.get_ticks_msec() + budget_ms
	var origin := _origin()
	var client: HTTPClient = kept if not kept_busy and _kept_ready() else null
	if client == null:
		client = HTTPClient.new()
		if client.connect_to_host(origin.host, origin.port, TLSOptions.client() if origin.https else null) != OK: return
		while client.get_status() in [HTTPClient.STATUS_RESOLVING, HTTPClient.STATUS_CONNECTING] and Time.get_ticks_msec() < deadline:
			client.poll()
			OS.delay_msec(5)
		if client.get_status() != HTTPClient.STATUS_CONNECTED:
			client.close()
			return
	if client.request(HTTPClient.METHOD_POST, origin.prefix + path, _headers(), "{}") == OK:
		while client.get_status() == HTTPClient.STATUS_REQUESTING and Time.get_ticks_msec() < deadline:
			client.poll()
			OS.delay_msec(5)
	client.close()

## An error reply. Maintenance and too-old-game replies carry their code in "code" (their detail is
## a Korean sentence for released games, which only print it).
func _failure(code: int, data: Dictionary) -> Dictionary:
	var reason := str(data.get("code", ""))
	if reason in GATE_CODES and code in [426, 503]:
		refused.emit(reason, data)
		return {"ok":false,"error":reason,"status":code,"data":data}
	var detail := str(data.get("detail","request_failed"))
	if code == 401 and detail in SESSION_CODES and not token.is_empty(): session_lost.emit(detail)
	var out := {"ok":false,"error":detail,"status":code}
	# A refused presence poll names the fields the server did not take (SOCIAL_API.md 2.2).
	if data.get("fields") is Array: out["fields"] = data.fields
	return out

func _seen(headers: PackedStringArray) -> void:
	for line in headers:
		if line.to_lower().begins_with("x-villagen-notice-version:"):
			notice_seen.emit(line.substr(line.find(":") + 1).strip_edges())
			return

func mutation(extra: Dictionary = {}) -> Dictionary:
	var bytes := Crypto.new().generate_random_bytes(16)
	bytes[6] = (bytes[6] & 15) | 64
	bytes[8] = (bytes[8] & 63) | 128
	var s := bytes.hex_encode()
	var id := "%s-%s-%s-%s-%s" % [s.substr(0,8),s.substr(8,4),s.substr(12,4),s.substr(16,4),s.substr(20,12)]
	return extra.merged({"request_id":id})

## The player's own time zone, so the server's day and night (night fish, the daily order) follow
## where they play (server/homestead.py UTC_OFFSET). Minutes from UTC, daylight saving included
## (Godot's time zone bias leaves it out on Windows).
static func utc_offset_minutes() -> int:
	var local := Time.get_unix_time_from_datetime_dict(Time.get_datetime_dict_from_system(false))
	var utc := Time.get_unix_time_from_datetime_dict(Time.get_datetime_dict_from_system(true))
	return int(round((local - utc) / 900.0)) * 15

static func time_zone_header() -> String:
	return "X-Villagen-UTC-Offset: %d" % utc_offset_minutes()

## This game's release (config/version). Servers with a minimum version refuse older games
## (server/client_policy.py); released games up to 0.11.2 send nothing.
static func client_version() -> String:
	return str(ProjectSettings.get_setting("application/config/version", "0"))

static func version_header() -> String:
	return "X-Villagen-Version: " + client_version()
