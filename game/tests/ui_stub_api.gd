extends Node
## Offline stand-in for api.gd used by the UI gallery: replays recorded server
## replies (tests/fixtures/ui_gallery.json, see tools/make_ui_gallery_fixture.py)
## so every screen can be built and captured without opening a port.
var base_url := "http://gallery.invalid"
var token := "gallery"
var mode := "demo"
var data: Dictionary = {}

func request(path: String, payload: Dictionary = {}, method := HTTPClient.METHOD_GET, binary := false) -> Dictionary:
	await get_tree().process_frame
	if binary: return {"ok": false, "error": "object_not_found"}
	if path == "/v1/runs": return {"ok": true, "data": {"id": data.run.id}}
	if path.begins_with("/v1/runs/") or path.begins_with("/v1/coop/runs/"): return {"ok": true, "data": data.run}
	if data.has(path): return {"ok": true, "data": data[path]}
	return {"ok": false, "error": "connection_failed"}

func post(path: String, payload: Dictionary) -> Dictionary:
	return await request(path, payload, HTTPClient.METHOD_POST)

func mutation(extra: Dictionary = {}) -> Dictionary:
	return extra.merged({"request_id": "00000000-0000-4000-8000-000000000000"})
