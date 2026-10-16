extends Node
## LOWNET: per-session transport policy. Mutation POSTs are never retried here.
signal weak_changed(weak: bool)

const PRESENCE := "/v1/social/presence"
const MAX_JSON_BYTES := 20 * 1024 * 1024
const MAX_CACHE_BYTES := 8 * 1024 * 1024
const MAX_MODEL_BYTES := 20 * 1024 * 1024 # model_loader.gd's current import limit.
const RANGE_BYTES := 512 * 1024
const IDLE_AFTER := 15.0
var _session := ""
var _channels: Dictionary = {}
var _cache: Dictionary = {}
var _cache_bytes := 0
var _last_input := 0.0
var _last_motion := -100.0
var _rng := RandomNumberGenerator.new()
var _weak := false
var _badge: Label
var cache_directory := "user://lownet"
## All API instances share the disk directory. Weak owners cannot strand a slot on scene exit.
static var _download_locks: Dictionary = {}
static var _download_ticket := 0

static func install(api: Node) -> Node:
	var policy = load("res://scripts/net/net_policy.gd").new()
	api.add_child(policy)
	return policy

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_rng.randomize()
	_last_input = now()
	if DisplayServer.get_name() == "headless": return
	var layer := CanvasLayer.new()
	layer.layer = 95
	add_child(layer)
	_badge = Label.new()
	_badge.text = tr("연결이 약해요 · 다시 연결 중")
	_badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_badge.add_theme_color_override("font_color", Color("ffe2a6"))
	_badge.add_theme_color_override("font_shadow_color", Color("262119"))
	_badge.add_theme_constant_override("shadow_offset_x", 1)
	_badge.add_theme_constant_override("shadow_offset_y", 1)
	layer.add_child(_badge)
	_badge.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	_badge.offset_left = -292
	_badge.offset_right = -12
	_badge.offset_top = 12
	_badge.offset_bottom = 40
	_badge.visible = false

static func now() -> float:
	return Time.get_ticks_msec() * 0.001

func _input(event: InputEvent) -> void:
	if event is InputEventKey or event is InputEventMouseButton or event is InputEventMouseMotion or event is InputEventJoypadButton or event is InputEventJoypadMotion:
		_last_input = now()

func bind_session(api: Node) -> String:
	var identity: String = str(api.base_url) + "\n" + str(api.token)
	if identity != _session:
		_session = identity
		_channels.clear()
		_cache.clear()
		_cache_bytes = 0
		_last_motion = now()
		_set_weak(false)
	return identity

func _state(channel: String) -> Dictionary:
	if not _channels.has(channel):
		if _channels.size() >= 128: _channels.erase(_channels.keys()[0])
		_channels[channel] = {"failures": 0, "slow": 0, "healthy": 0, "weak": false, "retry_at": 0.0, "started": -100.0, "finished": 0.0, "scene": ""}
	return _channels[channel]

static func presence_interval(idle: bool, minimized: bool) -> float:
	return 3.0 if minimized else (1.0 if idle else 0.25)

func retry_delay(failures: int, presence := false) -> float:
	var cap := 5.0 if presence else 30.0
	return minf(cap, pow(2.0, mini(maxi(failures - 1, 0), 6)) * _rng.randf_range(0.75, 1.25))

## Wait before the existing kept-alive call; pending remains true in the scene's caller.
## A scene change is sent immediately. No presence is replayed automatically.
func before_presence(api: Node, path: String, payload: Dictionary) -> bool:
	if path != PRESENCE: return true
	var identity := bind_session(api)
	var state := _state(PRESENCE)
	var requested_at := now()
	var scene := str(payload.get("scene", ""))
	var moved_scene := scene != str(state.scene)
	# A held gamepad stick need not emit new input events. Observe the actual walk too.
	var velocity := Vector2(float(payload.get("vx", 0.0)), float(payload.get("vz", 0.0)))
	var moving := velocity.is_finite() and velocity.length_squared() > 0.0004
	if payload.has("x") and payload.has("z"):
		var position := Vector2(float(payload.x), float(payload.z))
		if position.is_finite():
			if not moved_scene and state.get("position") is Vector2:
				moving = moving or position.distance_squared_to(state.position) > 0.0001
			state.position = position
	if moving: _last_motion = requested_at
	while not moved_scene:
		var minimized := DisplayServer.get_name() != "headless" and DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_MINIMIZED
		var interval := presence_interval(now() - maxf(_last_input, _last_motion) >= IDLE_AFTER, minimized)
		var until := maxf(float(state.started) + interval, float(state.retry_at))
		if now() >= until: break
		await get_tree().create_timer(minf(0.1, until - now()), true).timeout
		if identity != str(api.base_url) + "\n" + str(api.token): return false
		# Wake without reporting a false connection error. The next poll captures the new walk.
		if _last_input > requested_at and now() >= float(state.retry_at): break
	state.started = now()
	state.scene = scene
	return true

func kept_fallback(api: Node, path: String, payload: Dictionary, timeout: float) -> Dictionary:
	var started := Time.get_ticks_msec()
	var result: Dictionary = await api.request(path, payload, HTTPClient.METHOD_POST, false, timeout)
	if path == PRESENCE: record(path, result, Time.get_ticks_msec() - started)
	return result

func record(path: String, result: Dictionary, elapsed_ms: int) -> void:
	var state := _state(path)
	state.finished = now()
	var status := int(result.get("status", 0))
	var transient := str(result.get("error", "")) == "connection_failed" or status in [408, 429, 500, 502, 503, 504]
	if transient:
		state.failures = int(state.failures) + 1
		state.healthy = 0
		state.retry_at = now() + retry_delay(int(state.failures), path == PRESENCE)
		if int(state.failures) >= 2: state.weak = true
	elif bool(result.get("ok", false)):
		state.failures = 0
		state.retry_at = 0.0
		state.slow = int(state.slow) + 1 if elapsed_ms >= 1800 else 0
		state.healthy = int(state.healthy) + 1 if elapsed_ms < 1800 else 0
		if int(state.slow) >= 3: state.weak = true
		if int(state.healthy) >= 3: state.weak = false
	var any_weak := false
	for entry in _channels.values():
		if bool(entry.weak) and now() - float(entry.finished) < 60.0: any_weak = true
	_set_weak(any_weak)

func _set_weak(value: bool) -> void:
	if _weak == value: return
	_weak = value
	if is_instance_valid(_badge): _badge.visible = value
	weak_changed.emit(value)

static func handles_poll(path: String, method: int, binary: bool) -> bool:
	if binary or method != HTTPClient.METHOD_GET: return false
	var route := path.get_slice("?", 0)
	return route in ["/v1/social", "/v1/social/people", "/v1/social/whispers/requests", "/v1/studio", "/v1/studio/library"] or route.begins_with("/v1/studio/jobs/") or route.begins_with("/v1/generations/")

static func header(headers: PackedStringArray, name: String) -> String:
	for line in headers:
		if line.get_slice(":", 0).strip_edges().to_lower() == name.to_lower():
			return line.substr(line.find(":") + 1).strip_edges()
	return ""

static func decode_json(bytes: PackedByteArray, headers: PackedStringArray) -> PackedByteArray:
	match header(headers, "content-encoding").to_lower():
		"gzip": return bytes.decompress_dynamic(MAX_JSON_BYTES, FileAccess.COMPRESSION_GZIP)
		"deflate": return bytes.decompress_dynamic(MAX_JSON_BYTES, FileAccess.COMPRESSION_DEFLATE)
	return bytes

func poll_json(api: Node, path: String, timeout: float) -> Dictionary:
	var identity := bind_session(api)
	var state := _state(path)
	while now() < float(state.retry_at):
		await get_tree().create_timer(minf(0.1, float(state.retry_at) - now()), true).timeout
		if identity != str(api.base_url) + "\n" + str(api.token): return {"ok": false, "error": "session_changed"}
	var started := Time.get_ticks_msec()
	var headers: PackedStringArray = api._headers()
	# HTTPRequest decompresses gzip/deflate itself. HTTPClient uses decode_json instead.
	headers.append("X-Villagen-Cache: 1")
	if _cache.has(path): headers.append("If-None-Match: " + str(_cache[path].etag))
	var response := await _http_get(api, path, headers, timeout, MAX_JSON_BYTES)
	if identity != str(api.base_url) + "\n" + str(api.token): return {"ok": false, "error": "session_changed"}
	var result := consume_json(api, path, response)
	# A 304 without a matching body is not valid data: recover once without a validator.
	if str(result.get("error", "")) == "cache_miss":
		response = await _http_get(api, path, api._headers(), timeout, MAX_JSON_BYTES)
		if identity != str(api.base_url) + "\n" + str(api.token): return {"ok": false, "error": "session_changed"}
		result = consume_json(api, path, response)
	record(path, result, Time.get_ticks_msec() - started)
	if response.get("headers") is PackedStringArray and int(response.get("status", 0)) in [429, 503]:
		var retry_after := header(response.headers, "retry-after")
		if retry_after.is_valid_int(): state.retry_at = maxf(float(state.retry_at), now() + maxi(0, int(retry_after)))
	return result

func consume_json(api: Node, path: String, response: Dictionary) -> Dictionary:
	if not response.ok: return response
	var code := int(response.status)
	api._seen(response.headers)
	if code == 304:
		if not _cache.has(path): return {"ok": false, "error": "cache_miss"}
		return {"ok": true, "data": _cache[path].data.duplicate(true), "not_modified": true}
	var data = api.parse_body(response.bytes)
	if not data is Dictionary: return {"ok": false, "error": "invalid_server_response", "status": code}
	if code >= 400: return api._failure(code, data)
	if code != 200: return {"ok": false, "error": "invalid_server_response", "status": code}
	if _cache.has(path):
		_cache_bytes -= int(_cache[path].size)
		_cache.erase(path)
	var etag := header(response.headers, "etag")
	var size: int = response.bytes.size()
	if not etag.is_empty() and size <= MAX_CACHE_BYTES:
		while not _cache.is_empty() and (_cache.size() >= 16 or _cache_bytes + size > MAX_CACHE_BYTES):
			var oldest = _cache.keys()[0]
			_cache_bytes -= int(_cache[oldest].size)
			_cache.erase(oldest)
		_cache[path] = {"etag": etag, "data": data.duplicate(true), "size": size}
		_cache_bytes += size
	return {"ok": true, "data": data}

func _http_get(api: Node, path: String, headers: PackedStringArray, timeout: float, limit: int, gzip := true) -> Dictionary:
	var http := HTTPRequest.new()
	http.timeout = timeout
	http.body_size_limit = limit
	http.max_redirects = 0
	http.accept_gzip = gzip
	add_child(http)
	if http.request(str(api.base_url) + path, headers) != OK:
		http.queue_free()
		return {"ok": false, "error": "connection_failed"}
	var response: Array = await http.request_completed
	http.queue_free()
	if int(response[0]) != HTTPRequest.RESULT_SUCCESS: return {"ok": false, "error": "connection_failed"}
	return {"ok": true, "status": int(response[1]), "headers": response[2], "bytes": response[3]}

## Optional model hook: ranges use an exact strong validator and keep only complete chunks.
## The caller keeps a placeholder until completion, and never falls back to 48 MiB silently.
func download_model(api: Node, path: String, other_player := true) -> Dictionary:
	var identity := bind_session(api)
	var folder := _cache_folder(cache_directory)
	var route := path + ("&" if path.contains("?") else "?") + ("lod=low&cache=1" if other_player else "cache=1")
	var part := folder.path_join((identity + "\n" + route).sha256_text() + ".part")
	var ticket := await _acquire_download_slot(api, identity, folder, part)
	if ticket == 0: return {"ok": false, "error": "session_changed"}
	var result := await _download_model(api, path, other_player, folder)
	_release_download_slot(part, ticket)
	return result

static func _cache_folder(path: String) -> String:
	var folder := ProjectSettings.globalize_path(path).replace("\\", "/").simplify_path().trim_suffix("/")
	return folder.to_lower() if OS.get_name() == "Windows" else folder

static func _clean_download_locks() -> void:
	for part in _download_locks.keys():
		var owner = _download_locks[part].owner.get_ref()
		if not is_instance_valid(owner) or not owner.is_inside_tree(): _download_locks.erase(part)

static func _active_download_paths(folder: String) -> Array:
	_clean_download_locks()
	var active: Array = []
	for part in _download_locks:
		if str(_download_locks[part].folder) == folder: active.append(part)
	return active

func _acquire_download_slot(api: Node, identity: String, folder: String, part: String) -> int:
	while is_inside_tree() and is_instance_valid(api):
		if identity != str(api.base_url) + "\n" + str(api.token): return 0
		var active := _active_download_paths(folder)
		if not _download_locks.has(part) and active.size() < 3:
			_download_ticket += 1
			_download_locks[part] = {"owner": weakref(self), "folder": folder, "ticket": _download_ticket}
			return _download_ticket
		await get_tree().process_frame
	return 0

static func _release_download_slot(part: String, ticket: int) -> void:
	if _download_locks.has(part) and int(_download_locks[part].ticket) == ticket:
		_download_locks.erase(part)

func _download_model(api: Node, path: String, other_player: bool, folder: String) -> Dictionary:
	var identity := bind_session(api)
	var route := path + ("&" if path.contains("?") else "?") + ("lod=low&cache=1" if other_player else "cache=1")
	var key := (identity + "\n" + route).sha256_text()
	if DirAccess.make_dir_recursive_absolute(folder) != OK: return {"ok": false, "error": "cache_unavailable"}
	# Reserve space for every API instance's active transfer in this same directory.
	_prune_partials(folder, _active_download_paths(folder))
	var part := folder + "/" + key + ".part"
	var meta_path := part + ".json"
	var meta = JSON.parse_string(FileAccess.get_file_as_string(meta_path)) if FileAccess.file_exists(meta_path) else null
	var etag := str(meta.get("etag", "")) if meta is Dictionary else ""
	var offset := 0
	if FileAccess.file_exists(part) and etag.begins_with("\""):
		var existing := FileAccess.open(part, FileAccess.READ)
		if existing: offset = existing.get_length()
	var failures := 0
	while offset < MAX_MODEL_BYTES:
		if not is_inside_tree() or not is_instance_valid(api): return {"ok": false, "error": "session_changed"}
		if identity != str(api.base_url) + "\n" + str(api.token): return {"ok": false, "error": "session_changed"}
		var headers: PackedStringArray = api._headers()
		# No compressed ranges: offsets always refer to the original GLB representation.
		headers = _without_header(headers, "accept-encoding")
		headers.append("Accept-Encoding: identity")
		headers.append("Range: bytes=%d-%d" % [offset, mini(offset + RANGE_BYTES, MAX_MODEL_BYTES) - 1])
		if offset > 0: headers.append("If-Range: " + etag)
		var response := await _http_get(api, route, headers, 20.0, MAX_MODEL_BYTES, false)
		if not is_inside_tree() or not is_instance_valid(api): return {"ok": false, "error": "session_changed"}
		if identity != str(api.base_url) + "\n" + str(api.token): return {"ok": false, "error": "session_changed"}
		if response.ok:
			api._seen(response.headers)
			if int(response.status) == 503:
				var gate_data = api.parse_body(response.bytes)
				if gate_data is Dictionary and str(gate_data.get("code", "")) == "server_maintenance": return api._failure(503, gate_data)
		if not response.ok or int(response.get("status", 0)) in [408, 429, 500, 502, 503, 504]:
			failures += 1
			if failures >= 3: return {"ok": false, "error": "connection_failed"}
			var delay := retry_delay(failures)
			var retry_after := header(response.get("headers", PackedStringArray()), "retry-after")
			if retry_after.is_valid_int(): delay = maxf(delay, maxi(0, int(retry_after)))
			await get_tree().create_timer(delay, true).timeout
			continue
		failures = 0
		var code := int(response.status)
		if code >= 400 and code != 416:
			var error_data = api.parse_body(response.bytes)
			return api._failure(code, error_data) if error_data is Dictionary else {"ok": false, "error": "model_download_failed", "status": code}
		if code == 200:
			# If-Range mismatch / older server ignoring Range: replace, never append.
			var complete: PackedByteArray = response.bytes
			if complete.size() > MAX_MODEL_BYTES or not _valid_glb(complete) or not _matches_etag(complete, header(response.headers, "etag")): return {"ok": false, "error": "invalid_model"}
			_remove_partial(part, meta_path)
			return {"ok": true, "bytes": complete, "etag": header(response.headers, "etag"), "lod": header(response.headers, "x-asset-lod")}
		if code == 416:
			_remove_partial(part, meta_path)
			return {"ok": false, "error": "range_changed"} # Next explicit call starts at zero.
		if code != 206: return {"ok": false, "error": "model_download_failed", "status": code}
		var bounds := parse_content_range(header(response.headers, "content-range"))
		var next_etag := header(response.headers, "etag")
		var chunk: PackedByteArray = response.bytes
		if bounds.is_empty() or int(bounds.start) != offset or int(bounds.end) - offset + 1 != chunk.size() or int(bounds.total) > MAX_MODEL_BYTES or chunk.size() > RANGE_BYTES or not next_etag.begins_with("\""):
			return {"ok": false, "error": "invalid_range"}
		if offset > 0 and next_etag != etag:
			_remove_partial(part, meta_path)
			return {"ok": false, "error": "range_changed"}
		etag = next_etag
		var output := FileAccess.open(part, FileAccess.READ_WRITE if offset > 0 else FileAccess.WRITE)
		if output == null: return {"ok": false, "error": "cache_unavailable"}
		output.seek(offset)
		output.store_buffer(chunk)
		output.flush()
		if output.get_error() != OK: return {"ok": false, "error": "cache_unavailable"}
		output.close()
		var metadata := FileAccess.open(meta_path, FileAccess.WRITE)
		if metadata == null: return {"ok": false, "error": "cache_unavailable"}
		metadata.store_string(JSON.stringify({"etag": etag}))
		metadata.close()
		offset += chunk.size()
		if offset == int(bounds.total):
			var complete := FileAccess.get_file_as_bytes(part)
			_remove_partial(part, meta_path)
			return {"ok": true, "bytes": complete, "etag": etag, "lod": header(response.headers, "x-asset-lod")} if _valid_glb(complete) and _matches_etag(complete, etag) else {"ok": false, "error": "invalid_model"}
	return {"ok": false, "error": "model_too_large"}

static func parse_content_range(value: String) -> Dictionary:
	var regex := RegEx.new()
	regex.compile("^bytes ([0-9]+)-([0-9]+)/([0-9]+)$")
	var found := regex.search(value)
	if found == null: return {}
	var start := int(found.get_string(1))
	var end := int(found.get_string(2))
	var total := int(found.get_string(3))
	return {"start": start, "end": end, "total": total} if start <= end and end < total else {}

static func _valid_glb(bytes: PackedByteArray) -> bool:
	return bytes.size() >= 12 and bytes.slice(0, 4).get_string_from_ascii() == "glTF" and bytes.decode_u32(4) == 2 and bytes.decode_u32(8) == bytes.size()

static func _matches_etag(bytes: PackedByteArray, etag: String) -> bool:
	# This server's strong asset validators are SHA256 of the entire representation.
	if etag.length() != 66 or not etag.begins_with("\"") or not etag.ends_with("\""): return true
	var digest := HashingContext.new()
	digest.start(HashingContext.HASH_SHA256)
	digest.update(bytes)
	return digest.finish().hex_encode() == etag.substr(1, 64)

static func _without_header(headers: PackedStringArray, name: String) -> PackedStringArray:
	var filtered := PackedStringArray()
	for line in headers:
		if line.get_slice(":", 0).to_lower() != name: filtered.append(line)
	return filtered

static func _prune_partials(folder: String, active: Array) -> void:
	# Partial chunks expire after one day. A bounded directory also handles abandoned sessions.
	var entries: Array[Dictionary] = []
	var total := 0
	for name in DirAccess.get_files_at(folder):
		if name.ends_with(".part.json") and not FileAccess.file_exists(folder.path_join(name.trim_suffix(".json"))):
			DirAccess.remove_absolute(folder.path_join(name))
		if not name.ends_with(".part"): continue
		var path := folder.path_join(name)
		var file := FileAccess.open(path, FileAccess.READ)
		if file == null: continue
		var size := file.get_length()
		file.close()
		var modified := FileAccess.get_modified_time(path)
		entries.append({"path": path, "size": size, "modified": modified})
		total += size
	entries.sort_custom(func(a: Dictionary, b: Dictionary): return int(a.modified) < int(b.modified))
	for entry in entries:
		if str(entry.path) in active: continue
		if total > maxi(0, 64 * 1024 * 1024 - MAX_MODEL_BYTES * active.size()) or Time.get_unix_time_from_system() - int(entry.modified) > 86400:
			_remove_partial(str(entry.path), str(entry.path) + ".json")
			total -= int(entry.size)

static func _remove_partial(part: String, meta_path: String) -> void:
	if FileAccess.file_exists(part): DirAccess.remove_absolute(part)
	if FileAccess.file_exists(meta_path): DirAccess.remove_absolute(meta_path)
