extends SceneTree
## Run with tools/check_lownet_client.py; its fixture binds only 127.0.0.1.
var failures := 0
var passed := 0
func _initialize() -> void: call_deferred("run")
func check(ok: bool, message: String) -> void:
	if ok: passed += 1
	else: failures += 1
	print(("PASS " if ok else "FAIL ") + message)
func run() -> void:
	var port := OS.get_environment("LOWNET_TEST_PORT")
	if not port.is_valid_int(): quit(2); return
	var api = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = "http://127.0.0.1:" + port
	api.token = "local-fixture"
	var notices: Array[String] = []
	api.notice_seen.connect(func(value: String): notices.append(value))
	var first: Dictionary = await api.request("/v1/studio")
	check(first.ok and first.get("data", {}).get("wire") == "studio", "HTTPRequest automatically decodes gzip with a custom Accept-Encoding header")
	var cached: Dictionary = await api.request("/v1/studio")
	check(cached.ok and cached.get("not_modified", false) and cached.get("data") == first.get("data"), "real empty-body 304 restores the private JSON body")
	check(notices.size() == 2 and notices[-1] == "42", "304 still delivers the notice-version header")
	var presence: Dictionary = await api.post_kept("/v1/social/presence", {"scene": "village"})
	check(presence.ok and presence.get("data", {}).get("wire") == "presence", "HTTPClient preserves copied response headers for manual gzip decoding")
	presence = await api.post_kept("/v1/social/presence", {"scene": "village"})
	check(presence.ok and presence.get("data", {}).get("wire") == "presence", "second compressed presence succeeds on the kept connection")
	api.kept.close()
	api.free()
	print("NET_POLICY_HTTP_RESULT passed=%d failed=%d" % [passed, failures])
	quit(1 if failures else 0)
