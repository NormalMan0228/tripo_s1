extends Node
## Downloads and checks game patches; version_gate.gd shows it on its update screen.
##
## A release is a full install (Villagen_School_Setup.exe: Villagen.exe + Villagen.pck) or a patch
## built against an installed version (tools/publish_school_build.py patch). Patches are cumulative:
## for each installed version still supported, the patch list holds one pack that turns it into the
## newest release, so a game is always one download away from the latest version.
##
## The patch list (patches.json) lives beside the download page; the server names it in /v1/client
## (client.patch_manifest_url, server/client_policy.py):
##   {"format": 1, "latest": "0.11.6", "bases": {
##      "0.11.4": {"file": "patches/0.11.4_to_0.11.6.pck", "size": 123, "sha256": "..."},
##      "0.11.3": {"requires_reinstall": true, "reason": "engine"}}}
## The game downloads its base's pack into user://patches (resuming a cut download), checks size and
## SHA-256, records it in state.json and restarts; patch_boot.gd then loads it before anything else.

const PatchBoot = preload("res://scripts/patch_boot.gd")
const MANIFEST_LIMIT := 256 * 1024
const STALL_SECONDS := 25.0
const ATTEMPTS := 3

## Where patches go (tests use their own folder).
static var dir := PatchBoot.DIR
## Tests act as an installed game from source.
static var pretend_installed := false
## Tests replace the restart (it would end the test run).
static var restart_hook := Callable()

## The progress of the running download (bytes).
signal progressed(done: int, total: int)

var busy := false

## An installed game (an export): it can patch itself, and must be current to play.
static func installed_game() -> bool:
	return pretend_installed or OS.has_feature("template")

static func base_version() -> String:
	return PatchBoot.base_version if not PatchBoot.base_version.is_empty() else str(ProjectSettings.get_setting("application/config/version", "0"))

## The patch list address the server named: https, or this PC for QA runs.
static func manifest_address(client: Dictionary) -> String:
	var url := str(client.get("patch_manifest_url", "")).strip_edges()
	if url.length() > 300: return ""
	if url.begins_with("https://") or url.begins_with("http://127.0.0.1:") or url.begins_with("http://localhost:"): return url
	return ""

## Numeric version order (0.11.10 after 0.11.9); a suffix is ignored. Unreadable counts as oldest.
static func older(version: String, than: String) -> bool:
	var a := _numbers(version)
	var b := _numbers(than)
	if b.is_empty(): return false
	if a.is_empty(): return true
	for i in 4:
		if a[i] != b[i]: return a[i] < b[i]
	return false

static func _numbers(version: String) -> Array:
	var digits := version.strip_edges().trim_prefix("v").split("-")[0].split("+")[0]
	var out := []
	for part in digits.split("."):
		if not part.is_valid_int(): return []
		out.append(int(part))
	while out.size() < 4: out.append(0)
	return out

## What this game should do with the patch list:
##   {"action": "patch", "version", "url", "size", "sha256", "file"}
##   {"action": "reinstall", "reason"}   no patch for this installed version (or it needs the installer)
##   {"action": "wait"}                  the server announced a version the list does not have yet
##   {"action": "none"}                  already the newest
static func plan(manifest: Dictionary, manifest_url: String, base: String, current: String, wanted := "") -> Dictionary:
	var latest := str(manifest.get("latest", ""))
	if int(manifest.get("format", 0)) != 1 or _numbers(latest).is_empty(): return {"action": "reinstall", "reason": "bad_list"}
	if not older(current, latest):
		# The server already names a newer game than the list: its patch is still being uploaded.
		return {"action": "wait", "reason": "not_ready"} if not wanted.is_empty() and older(current, wanted) else {"action": "none"}
	var bases = manifest.get("bases", {})
	var entry = bases.get(base) if bases is Dictionary else null
	if not entry is Dictionary: return {"action": "reinstall", "reason": "no_patch_for_base"}
	if bool(entry.get("requires_reinstall", false)): return {"action": "reinstall", "reason": str(entry.get("reason", "reinstall_required"))}
	if PatchBoot.problem == "crashed" and str(PatchBoot.read_state(dir).get("version", "")) == latest:
		return {"action": "reinstall", "reason": "patch_failed"}
	var file := str(entry.get("file", ""))
	var sha := str(entry.get("sha256", "")).to_lower()
	var size := int(entry.get("size", 0))
	var safe := RegEx.create_from_string("^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*\\.pck$")
	if safe.search(file) == null or ".." in file or size <= 0 or sha.length() != 64 or not sha.is_valid_hex_number():
		return {"action": "reinstall", "reason": "bad_list"}
	return {"action": "patch", "version": latest, "url": manifest_url.get_base_dir() + "/" + file, "size": size, "sha256": sha,
		"file": "%s_to_%s.pck" % [base.validate_filename(), latest.validate_filename()]}

## patches.json, or {"error": ...}.
func fetch_manifest(url: String) -> Dictionary:
	var http := HTTPRequest.new()
	http.timeout = 12.0
	http.body_size_limit = MANIFEST_LIMIT
	http.max_redirects = 0
	add_child(http)
	if http.request(url, PackedStringArray(["Cache-Control: no-cache"])) != OK:
		http.queue_free()
		return {"error": "connection_failed"}
	var response: Array = await http.request_completed
	http.queue_free()
	if response[0] != HTTPRequest.RESULT_SUCCESS: return {"error": "connection_failed"}
	if response[1] != 200: return {"error": "http_%d" % response[1]}
	var data = JSON.parse_string((response[3] as PackedByteArray).get_string_from_utf8())
	return data if data is Dictionary else {"error": "bad_list"}

## Downloads the plan's pack, checks it and records it for the next start. "" when ready, else why not.
func install(step: Dictionary) -> String:
	if busy: return "busy"
	busy = true
	DirAccess.make_dir_recursive_absolute(dir)
	var part := dir.path_join(str(step.file) + ".part")
	var target := dir.path_join(str(step.file))
	var problem := ""
	for attempt in ATTEMPTS:
		problem = await _fetch(str(step.url), part, int(step.size))
		if problem.is_empty():
			if FileAccess.get_sha256(part) == str(step.sha256): break
			# Damaged on the way (or a stale part from another list): start over.
			problem = "checksum"
			DirAccess.remove_absolute(part)
		elif problem.begins_with("http_4"): break
	if not problem.is_empty():
		busy = false
		return problem
	# Only now does the pack replace anything: the game keeps running its current version until then.
	for old in DirAccess.get_files_at(dir):
		if old.ends_with(".pck") and old != str(step.file): DirAccess.remove_absolute(dir.path_join(old))
	DirAccess.remove_absolute(target)
	if DirAccess.rename_absolute(part, target) != OK:
		busy = false
		return "write_failed"
	PatchBoot.write_state(dir, {"base": base_version(), "version": str(step.version), "file": str(step.file),
		"size": int(step.size), "sha256": str(step.sha256), "boots": 0})
	busy = false
	return ""

## One HTTP GET into part, continuing after the bytes already there (Range). "" when complete.
func _fetch(url: String, part: String, size: int) -> String:
	var have := 0
	if FileAccess.file_exists(part):
		var existing := FileAccess.open(part, FileAccess.READ)
		if existing: have = existing.get_length()
		existing = null
	if have > size:
		DirAccess.remove_absolute(part)
		have = 0
	if have == size: return ""
	var tls := url.begins_with("https://")
	var rest := url.trim_prefix("https://").trim_prefix("http://")
	var slash := rest.find("/")
	if slash < 0: return "bad_address"
	var host_port := rest.substr(0, slash)
	var path := rest.substr(slash)
	var host := host_port
	var port := 443 if tls else 80
	var colon := host_port.rfind(":")
	if colon > 0 and host_port.substr(colon + 1).is_valid_int():
		host = host_port.substr(0, colon)
		port = int(host_port.substr(colon + 1))
	var http := HTTPClient.new()
	if http.connect_to_host(host, port, TLSOptions.client() if tls else null) != OK: return "connection_failed"
	var deadline := Time.get_ticks_msec() + 15000
	while http.get_status() in [HTTPClient.STATUS_RESOLVING, HTTPClient.STATUS_CONNECTING]:
		http.poll()
		if Time.get_ticks_msec() > deadline: return "connection_failed"
		await get_tree().process_frame
	if http.get_status() != HTTPClient.STATUS_CONNECTED: return "connection_failed"
	var headers := PackedStringArray(["User-Agent: Villagen-Patcher", "Accept: */*"])
	if have > 0: headers.append("Range: bytes=%d-" % have)
	if http.request(HTTPClient.METHOD_GET, path, headers) != OK: return "connection_failed"
	deadline = Time.get_ticks_msec() + 20000
	while http.get_status() == HTTPClient.STATUS_REQUESTING:
		http.poll()
		if Time.get_ticks_msec() > deadline: return "connection_failed"
		await get_tree().process_frame
	if not http.has_response(): return "connection_failed"
	var code := http.get_response_code()
	var file: FileAccess
	if code == 206 and have > 0:
		file = FileAccess.open(part, FileAccess.READ_WRITE)
		if file: file.seek_end()
	elif code == 200:
		# The server sent the whole file (no range support, or nothing was there yet).
		have = 0
		file = FileAccess.open(part, FileAccess.WRITE)
	elif code == 416:
		DirAccess.remove_absolute(part)
		return "range"
	else:
		http.close()
		return "http_%d" % code
	if file == null:
		http.close()
		return "write_failed"
	progressed.emit(have, size)
	var quiet_since := Time.get_ticks_msec()
	while http.get_status() == HTTPClient.STATUS_BODY:
		http.poll()
		# The connection may end here (a cut download): what came so far stays for the next try.
		if http.get_status() != HTTPClient.STATUS_BODY: break
		var chunk := http.read_response_body_chunk()
		if chunk.is_empty():
			if Time.get_ticks_msec() - quiet_since > STALL_SECONDS * 1000.0: break
			await get_tree().process_frame
			continue
		quiet_since = Time.get_ticks_msec()
		file.store_buffer(chunk)
		have += chunk.size()
		if have > size:
			file.close()
			http.close()
			DirAccess.remove_absolute(part)
			return "too_big"
		progressed.emit(have, size)
	file.close()
	http.close()
	return "" if have == size else "cut"

## Restarts the game so patch_boot.gd loads the new pack before anything else.
static func restart(tree: SceneTree) -> void:
	if restart_hook.is_valid():
		restart_hook.call()
		return
	var args := OS.get_cmdline_args()
	# Engine options are not among the arguments: a headless QA run restarts headless.
	if DisplayServer.get_name() == "headless" and not args.has("--headless"): args.insert(0, "--headless")
	var extra := OS.get_cmdline_user_args()
	if not extra.is_empty():
		args.append("--")
		args.append_array(extra)
	OS.set_restart_on_exit(true, args)
	tree.quit()
