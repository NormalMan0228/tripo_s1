extends SceneTree
## Offline transport-contract regression checks; no external server or credentials.
const Policy = preload("res://scripts/net/net_policy.gd")
var failed := 0
var passed := 0

class FixturePolicy extends "res://scripts/net/net_policy.gd":
	signal release_requests
	var replies: Array[Dictionary] = []
	var sent: Array[Dictionary] = []
	var hold_requests := false
	func _http_get(_api: Node, path: String, headers: PackedStringArray, _timeout: float, _limit: int, _gzip := true) -> Dictionary:
		sent.append({"path": path, "headers": headers})
		if hold_requests: await release_requests
		return replies.pop_front() if not replies.is_empty() else {"ok": false, "error": "connection_failed"}

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, description: String) -> void:
	if ok: passed += 1
	else: failed += 1
	print(("PASS " if ok else "FAIL ") + description)

func reply(code: int, bytes: PackedByteArray, headers := PackedStringArray()) -> Dictionary:
	return {"ok": true, "status": code, "bytes": bytes, "headers": headers}

func glb(size: int) -> PackedByteArray:
	var bytes := PackedByteArray()
	bytes.resize(size)
	bytes.fill(42)
	bytes[0] = 103; bytes[1] = 108; bytes[2] = 84; bytes[3] = 70
	bytes.encode_u32(4, 2)
	bytes.encode_u32(8, size)
	return bytes

func tag(bytes: PackedByteArray) -> String:
	var hash := HashingContext.new()
	hash.start(HashingContext.HASH_SHA256)
	hash.update(bytes)
	return "\"" + hash.finish().hex_encode() + "\""

func seed_partial(policy: Node, api: Node, path: String, bytes: PackedByteArray, etag: String) -> String:
	var route := path + "?lod=low&cache=1"
	var key: String = (policy.bind_session(api) + "\n" + route).sha256_text()
	DirAccess.make_dir_recursive_absolute(policy.cache_directory)
	var part: String = policy.cache_directory.path_join(key + ".part")
	var output := FileAccess.open(part, FileAccess.WRITE)
	output.store_buffer(bytes)
	output.close()
	output = FileAccess.open(part + ".json", FileAccess.WRITE)
	output.store_string(JSON.stringify({"etag": etag}))
	output.close()
	return part

func collect_download(policy: Node, api: Node, path: String, key: String, results: Dictionary) -> void:
	results[key] = await policy.download_model(api, path)

func concurrent_download_checks(api: Node, policy: Node, bytes: PackedByteArray) -> void:
	var api2 = load("res://scripts/api.gd").new()
	root.add_child(api2)
	api2.base_url = api.base_url
	api2.token = api.token
	api2.net_policy.free()
	var second := FixturePolicy.new()
	api2.add_child(second)
	api2.net_policy = second
	second.cache_directory = policy.cache_directory
	var third := FixturePolicy.new()
	root.add_child(third)
	third.cache_directory = policy.cache_directory
	var full := reply(200, bytes, PackedStringArray(["ETag: " + tag(bytes)]))
	var results := {}
	var route := "/v1/social/village/objects/concurrent/model"
	policy.hold_requests = true
	policy.replies.assign([full])
	second.replies = [full]
	collect_download(policy, api, route, "first", results)
	collect_download(second, api2, route, "second", results)
	await create_timer(0.03).timeout
	check(second.sent.is_empty(), "two API instances serialize writes to the same partial file")
	policy.release_requests.emit()
	await create_timer(0.03).timeout
	check(results.size() == 2 and results.first.ok and results.second.ok, "waiting API resumes after the shared file lock is released")
	results.clear()
	second.sent.clear()
	second.hold_requests = true
	policy.replies.assign([full])
	second.replies = [full, full]
	third.replies = [full]
	collect_download(policy, api, route + "1", "one", results)
	collect_download(second, api2, route + "2", "two", results)
	collect_download(second, api2, route + "3", "three", results)
	collect_download(third, api2, route + "4", "four", results)
	await create_timer(0.03).timeout
	var folder: String = Policy._cache_folder(policy.cache_directory)
	var active: Array = Policy._active_download_paths(folder)
	check(active.size() == 3 and third.sent.is_empty(), "the three-download limit is shared by every API in a folder")
	var protected: String = active[0]
	var output := FileAccess.open(protected, FileAccess.WRITE)
	output.store_buffer(bytes)
	output.close()
	var orphan := folder.path_join("capacity-check.part")
	output = FileAccess.open(orphan, FileAccess.WRITE)
	var excess := PackedByteArray()
	excess.resize(5 * 1024 * 1024)
	output.store_buffer(excess)
	output.close()
	Policy._prune_partials(folder, active)
	check(FileAccess.file_exists(protected) and not FileAccess.file_exists(orphan), "pruning protects other API owners and reserves all active transfers' disk space")
	policy.release_requests.emit()
	second.release_requests.emit()
	await create_timer(0.03).timeout
	check(results.size() == 4 and results.four.ok, "a fourth download waits for a slot instead of failing busy")
	policy.hold_requests = false
	second.hold_requests = false
	# Model an interrupted owner with a live registry entry, then actually free that node.
	var identity: String = policy.bind_session(api)
	var abandoned := folder.path_join((identity + "\n" + route + "?lod=low&cache=1").sha256_text() + ".part")
	var abandoned_ticket: int = await second._acquire_download_slot(api2, identity, folder, abandoned)
	second.free()
	third.replies = [full]
	var recovered: Dictionary = await third.download_model(api, route)
	check(abandoned_ticket > 0 and recovered.ok and Policy._active_download_paths(folder).is_empty(), "a freed weak owner cannot strand a file lock or download slot")
	# A waiter must cancel when its API session changes, without touching the fixture transport.
	var held: Dictionary = {}
	for i in 3:
		var part := folder.path_join("slot-%d.part" % i)
		held[part] = await policy._acquire_download_slot(api, identity, folder, part)
	results.clear()
	third.sent.clear()
	collect_download(third, api2, route, "cancelled", results)
	api2.token = "different-session"
	await create_timer(0.03).timeout
	check(results.has("cancelled") and results.cancelled.error == "session_changed" and third.sent.is_empty(), "a slot waiter cancels when its authentication session changes")
	for part in held: Policy._release_download_slot(str(part), int(held[part]))
	third.free()
	api2.free()

func run() -> void:
	var api = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = "http://127.0.0.1:1"
	api.token = "offline-test-token"
	api.net_policy.free()
	var policy := FixturePolicy.new()
	api.add_child(policy)
	api.net_policy = policy
	policy.cache_directory = ProjectSettings.globalize_path("res://").path_join("../.codex-lownet-cache")
	policy.bind_session(api)
	var json := '{"objects":[{"id":"one"}]}'.to_utf8_buffer()
	policy.replies = [reply(200, json, PackedStringArray(['ETag: W/"one"'])), reply(304, PackedByteArray())]
	var first: Dictionary = await api.request("/v1/studio")
	first.data.objects[0].id = "changed-by-caller"
	var second: Dictionary = await api.request("/v1/studio")
	check(second.ok and second.not_modified and second.data.objects[0].id == "one", "304 restores an isolated cached body")
	check(Policy.header(policy.sent[-1].headers, "if-none-match") == 'W/"one"', "conditional GET sends the saved ETag")
	api.token = "new-offline-session"
	policy.bind_session(api)
	check(policy._cache.is_empty(), "session change clears private JSON bodies")
	policy.replies = [reply(304, PackedByteArray()), reply(200, json)]
	var recovered: Dictionary = await api.request("/v1/studio")
	check(recovered.ok and not recovered.get("not_modified", false), "missing 304 body triggers one unconditional recovery GET")
	check(not Policy.handles_poll("/v1/studio", HTTPClient.METHOD_POST, false), "mutation POST never enters retry/cache policy")
	check(Policy.presence_interval(false, false) == 0.25 and Policy.presence_interval(true, false) == 1.0 and Policy.presence_interval(true, true) == 3.0, "active/idle/minimized presence intervals")
	var within_bounds := true
	for i in 100:
		var delay := policy.retry_delay(20, true)
		if delay <= 0 or delay > 5: within_bounds = false
	check(within_bounds, "presence retry stays below host expiry budget")
	policy.record(Policy.PRESENCE, {"ok": false, "error": "connection_failed"}, 10)
	policy.record(Policy.PRESENCE, {"ok": false, "error": "connection_failed"}, 10)
	check(policy._weak, "two transport failures show weak connection")
	for i in 3: policy.record(Policy.PRESENCE, {"ok": true}, 300)
	check(not policy._weak, "three healthy responses clear weak connection")
	var presence: Dictionary = policy._state(Policy.PRESENCE)
	presence.scene = "village"
	presence.started = Policy.now()
	policy._last_input = Policy.now() - 30
	policy._last_motion = Policy.now() - 30
	create_timer(0.02).timeout.connect(func(): policy._last_input = Policy.now())
	var woken: bool = await policy.before_presence(api, Policy.PRESENCE, {"scene": "village"})
	check(woken, "input wakes idle presence without a false connection error")
	presence.retry_at = Policy.now() + 0.2
	var retry_started := Policy.now()
	policy._last_input = Policy.now() - 30
	create_timer(0.02).timeout.connect(func(): policy._last_input = Policy.now())
	woken = await policy.before_presence(api, Policy.PRESENCE, {"scene": "village"})
	check(woken and Policy.now() - retry_started >= 0.18, "activity does not bypass error backoff")
	# Held gamepad input can have no new events; legacy presence can omit vx/vz entirely.
	policy._last_input = Policy.now() - 30
	policy._last_motion = Policy.now() - 30
	presence.started = Policy.now() - 0.3
	presence.retry_at = 0.0
	var motion_started := Policy.now()
	await policy.before_presence(api, Policy.PRESENCE, {"scene": "village", "vx": 2.0, "vz": 0.0, "x": 0.0, "z": 0.0})
	var velocity_kept_active := Policy.now() - motion_started < 0.2
	policy._last_motion = Policy.now() - 30
	presence.started = Policy.now() - 0.3
	motion_started = Policy.now()
	await policy.before_presence(api, Policy.PRESENCE, {"scene": "village", "x": 1.0, "z": 0.0})
	check(velocity_kept_active and Policy.now() - motion_started < 0.2 and Policy.now() - float(policy._last_input) >= 30, "held movement and position-only movement remain active without new input events")
	check(Policy.decode_json(json.compress(FileAccess.COMPRESSION_GZIP), PackedStringArray(["Content-Encoding: gzip"])) == json, "kept HTTPClient gzip decode")
	check(Policy.decode_json(json.compress(FileAccess.COMPRESSION_DEFLATE), PackedStringArray(["Content-Encoding: deflate"])) == json, "kept HTTPClient deflate decode")
	# Produced with Python gzip.compress(..., mtime=0) / zlib.compress, not Godot's encoder.
	var wire_json := '{"wire":"python-zlib"}'.to_utf8_buffer()
	check(Policy.decode_json(Marshalls.base64_to_raw("H4sIAAAAAAAC/6tWKs8sSlWyUiqoLMnIz9OtyslMUqoFANY7tmIWAAAA"), PackedStringArray(["Content-Encoding: gzip"])) == wire_json, "Python HTTP gzip wire fixture")
	check(Policy.decode_json(Marshalls.base64_to_raw("eJyrVirPLEpVslIqqCzJyM/TrcrJTFKqBQBaIQfy"), PackedStringArray(["Content-Encoding: deflate"])) == wire_json, "Python zlib-wrapped HTTP deflate wire fixture")
	check(Policy.parse_content_range("bytes 0-3/4").get("total") == 4 and Policy.parse_content_range("bytes 4-5/4").is_empty(), "Content-Range validation rejects invalid bounds")
	var bytes := glb(Policy.RANGE_BYTES + 32)
	var etag := tag(bytes)
	var path := "/v1/social/village/objects/test/model"
	var part := seed_partial(policy, api, path, bytes.slice(0, Policy.RANGE_BYTES), etag)
	policy.replies = [reply(206, bytes.slice(Policy.RANGE_BYTES), PackedStringArray(["ETag: " + etag, "Content-Range: bytes %d-%d/%d" % [Policy.RANGE_BYTES, bytes.size() - 1, bytes.size()]]))]
	var downloaded: Dictionary = await policy.download_model(api, path)
	check(downloaded.ok and downloaded.bytes == bytes, "interrupted GLB resumes from the durable complete chunk")
	check(Policy.header(policy.sent[-1].headers, "range").begins_with("bytes=524288-") and Policy.header(policy.sent[-1].headers, "if-range") == etag, "resume sends exact offset and strong If-Range")
	check(Policy.header(policy.sent[-1].headers, "accept-encoding") == "identity" and str(policy.sent[-1].path).ends_with("?lod=low&cache=1"), "other-player model requests low variant with uncompressed ranges")
	check(not FileAccess.file_exists(part), "successful import removes durable partial file")
	seed_partial(policy, api, path, bytes.slice(0, Policy.RANGE_BYTES), etag)
	var replacement := glb(64)
	policy.replies = [reply(200, replacement, PackedStringArray(["ETag: " + tag(replacement)]))]
	downloaded = await policy.download_model(api, path)
	check(downloaded.ok and downloaded.bytes == replacement, "If-Range mismatch 200 replaces rather than appends bytes")
	var corrupted := bytes.slice(0, Policy.RANGE_BYTES)
	corrupted[20] = 0
	seed_partial(policy, api, path, corrupted, etag)
	policy.replies = [reply(206, bytes.slice(Policy.RANGE_BYTES), PackedStringArray(["ETag: " + etag, "Content-Range: bytes %d-%d/%d" % [Policy.RANGE_BYTES, bytes.size() - 1, bytes.size()]]))]
	downloaded = await policy.download_model(api, path)
	check(not downloaded.ok and downloaded.error == "invalid_model", "strong SHA256 validator detects a corrupted cached chunk")
	seed_partial(policy, api, path, bytes.slice(0, Policy.RANGE_BYTES), etag)
	policy.replies = [reply(416, PackedByteArray())]
	downloaded = await policy.download_model(api, path)
	check(not downloaded.ok and not FileAccess.file_exists(part), "416 clears obsolete partial bytes")
	policy.replies = [reply(503, '{"code":"server_maintenance","detail":"maintenance"}'.to_utf8_buffer())]
	downloaded = await policy.download_model(api, path)
	check(not downloaded.ok and downloaded.error == "server_maintenance", "maintenance gate is preserved during a model download")
	policy.replies = [reply(206, replacement, PackedStringArray(["ETag: " + tag(replacement), "X-Asset-Lod: low", "Content-Range: bytes 0-63/64"]))]
	downloaded = await policy.download_model(api, "/v1/social/village/objects/test/parts/body")
	check(downloaded.ok and downloaded.lod == "low" and downloaded.etag == tag(replacement) and str(policy.sent[-1].path).ends_with("/parts/body?lod=low&cache=1"), "assembly parts preserve selected variant and SHA256 metadata")
	await concurrent_download_checks(api, policy, replacement)
	api.free()
	if passed + failed != 33:
		failed += 1
		print("FAIL incomplete regression run")
	print("NET_POLICY_RESULT passed=%d failed=%d" % [passed, failed])
	quit(1 if failed else 0)
