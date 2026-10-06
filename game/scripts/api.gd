extends Node

var base_url := "http://127.0.0.1:8765"
var token := ""
var mode := "demo"

## The login screen chooses the server; there is no offline or bundled sample play.

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

## The expedition sends its input ten times a second. A new HTTPRequest per call opens a fresh
## TCP + TLS connection every time (several round trips to an online world), so these calls
## share one kept-alive connection. Falls back to a normal request when the channel cannot
## even send (busy, cannot connect); once a request went out, a failure is reported as is.
var kept: HTTPClient
var kept_origin := ""
var kept_used := 0
var kept_busy := false

func post_kept(path: String, payload: Dictionary) -> Dictionary:
	if kept_busy: return await post(path, payload)
	kept_busy = true
	var result := await _kept_request(path, JSON.stringify(payload))
	kept_busy = false
	if result.is_empty(): return await post(path, payload)
	return result

func _kept_request(path: String, body: String) -> Dictionary:
	var https := base_url.begins_with("https://")
	var rest := base_url.trim_prefix("https://").trim_prefix("http://")
	var slash := rest.find("/")
	var prefix := rest.substr(slash) if slash >= 0 else ""
	var host_port := rest.substr(0, slash) if slash >= 0 else rest
	var host := host_port
	var port := 443 if https else 80
	var colon := host_port.rfind(":")
	if colon > 0 and host_port.substr(colon + 1).is_valid_int():
		host = host_port.substr(0, colon)
		port = int(host_port.substr(colon + 1))
	if kept == null: kept = HTTPClient.new()
	kept.poll()
	# Servers drop idle keep-alive connections (uvicorn after 5 s): reconnect after a pause.
	if kept.get_status() != HTTPClient.STATUS_CONNECTED or kept_origin != base_url or Time.get_ticks_msec() - kept_used > 4000:
		kept.close()
		kept_origin = base_url
		if kept.connect_to_host(host, port, TLSOptions.client() if https else null) != OK: return {}
		var connect_deadline := Time.get_ticks_msec() + 8000
		while kept.get_status() in [HTTPClient.STATUS_RESOLVING, HTTPClient.STATUS_CONNECTING]:
			kept.poll()
			if Time.get_ticks_msec() > connect_deadline: break
			await get_tree().process_frame
		if kept.get_status() != HTTPClient.STATUS_CONNECTED:
			kept.close()
			return {}
	var headers := PackedStringArray(["Content-Type: application/json"])
	if not token.is_empty(): headers.append("Authorization: Bearer " + token)
	if kept.request(HTTPClient.METHOD_POST, prefix + path, headers, body) != OK:
		kept.close()
		return {}
	kept_used = Time.get_ticks_msec()
	var deadline := Time.get_ticks_msec() + 12000
	while kept.get_status() == HTTPClient.STATUS_REQUESTING:
		kept.poll()
		if Time.get_ticks_msec() > deadline: break
		if kept.get_status() == HTTPClient.STATUS_REQUESTING: await get_tree().process_frame
	if not kept.has_response():
		kept.close()
		return {"ok": false, "error": "connection_failed"}
	var code := kept.get_response_code()
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
	var data = JSON.parse_string(bytes.get_string_from_utf8())
	if not data is Dictionary: return {"ok":false,"error":"invalid_server_response"}
	if code >= 400: return {"ok":false,"error":str(data.get("detail","request_failed")),"status":code}
	return {"ok":true,"data":data}

func mutation(extra: Dictionary = {}) -> Dictionary:
	var bytes := Crypto.new().generate_random_bytes(16)
	bytes[6] = (bytes[6] & 15) | 64
	bytes[8] = (bytes[8] & 63) | 128
	var s := bytes.hex_encode()
	var id := "%s-%s-%s-%s-%s" % [s.substr(0,8),s.substr(8,4),s.substr(12,4),s.substr(16,4),s.substr(20,12)]
	return extra.merged({"request_id":id})
