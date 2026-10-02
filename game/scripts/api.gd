extends Node

var base_url := "http://127.0.0.1:8765"
var token := ""
var mode := "demo"

func _ready() -> void:
	# Release players use the online demo; editor and developer builds use local testing.
	if OS.has_feature("tripothon_player") and not OS.get_cmdline_user_args().has("--local-demo"):
		base_url = "https://34-28-65-113.sslip.io"

func request(path: String, payload: Dictionary = {}, method := HTTPClient.METHOD_GET, binary := false) -> Dictionary:
	var http := HTTPRequest.new()
	http.timeout = 12.0
	http.body_size_limit = 20 * 1024 * 1024
	# Redirects must never forward a session credential to another host.
	http.max_redirects = 0
	add_child(http)
	var headers := PackedStringArray(["Content-Type: application/json"])
	if not token.is_empty(): headers.append("Authorization: Bearer " + token)
	var error := http.request(base_url + path, headers, method, "" if method == HTTPClient.METHOD_GET else JSON.stringify(payload))
	if error != OK:
		http.queue_free()
		return {"ok": false, "error": "connection_failed"}
	var response: Array = await http.request_completed
	http.queue_free()
	if response[0] != HTTPRequest.RESULT_SUCCESS:
		return {"ok": false, "error": "connection_failed"}
	var code: int = response[1]
	var bytes: PackedByteArray = response[3]
	if binary and code == 200: return {"ok": true, "bytes": bytes}
	var data = JSON.parse_string(bytes.get_string_from_utf8())
	if not data is Dictionary: return {"ok":false,"error":"invalid_server_response"}
	if code >= 400: return {"ok":false,"error":str(data.get("detail","request_failed")),"status":code}
	return {"ok":true,"data":data}

func post(path: String, payload: Dictionary) -> Dictionary:
	return await request(path, payload, HTTPClient.METHOD_POST)

func mutation(extra: Dictionary = {}) -> Dictionary:
	var bytes := Crypto.new().generate_random_bytes(16)
	bytes[6] = (bytes[6] & 15) | 64
	bytes[8] = (bytes[8] & 63) | 128
	var s := bytes.hex_encode()
	var id := "%s-%s-%s-%s-%s" % [s.substr(0,8),s.substr(8,4),s.substr(12,4),s.substr(16,4),s.substr(20,12)]
	return extra.merged({"request_id":id})
