extends SceneTree
## Game patches (patcher.gd, patch_boot.gd and version_gate.gd's update screen) against a QA server
## and a patch host this test runs itself (a small HTTP server with byte ranges, like S3):
## what each patch list means (patch, installer, not uploaded yet, already current, unsafe file
## names), a damaged download thrown away, the installer screen for a release that needs it, the
## "being prepared" screen, then the launch of an older installed game: the title asks the server
## first, downloads the patch (cut once on the way and resumed), checks it, records it and restarts;
## the restart (simulated: patch_boot.gd loads the pack, as the first autoload does at launch) runs
## the new version, whose title then opens normally. Last, patch_boot.gd's guards: a patch that never
## reached the title three launches in a row is set aside, and one for another install is removed.
##   TRIPOTHON_MODE=demo TRIPOTHON_DATA_DIR=artifacts/qa-patch python -m uvicorn server.app:create_app --factory --port 8818
##   Godot --headless --path game --script res://tests/patch_update_check.gd -- --mute --qa --server=http://127.0.0.1:8818 --policy=<data>/client_policy.json
const I18n = preload("res://scripts/i18n.gd")
const TARGET := "99.0.1"

var failed := false
var server := "http://127.0.0.1:8766"  # tools/test.ps1 QA server
var policy_path := ""
var saved_world := ""
var Patcher: GDScript
var PatchBoot: GDScript
var VersionGate: GDScript
var host := FakeHost.new()
var restarted := 0
var base := ""

## A tiny HTTP/1.1 file server on 127.0.0.1: GET with "Range: bytes=N-" (206), 404 otherwise.
## cut_after[path] sends the headers and only that many body bytes once, then hangs up.
class FakeHost extends RefCounted:
	var server := TCPServer.new()
	var peers: Array = []
	var files := {}
	var cut_after := {}
	var log: Array = []
	## Bytes sent per connection and frame (a slow line shows the progress bar at work).
	var pace := 1 << 20

	func start(port: int) -> bool:
		return server.listen(port, "127.0.0.1") == OK

	func poll() -> void:
		while server.is_connection_available():
			peers.append({"peer": server.take_connection(), "in": PackedByteArray(), "out": PackedByteArray(), "answered": false, "linger": 0})
		for c in peers.duplicate():
			var peer: StreamPeerTCP = c.peer
			peer.poll()
			if peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
				peers.erase(c)
				continue
			if not c.answered:
				var waiting := peer.get_available_bytes()
				if waiting > 0: c["in"].append_array(peer.get_data(waiting)[1])
				var text: String = c["in"].get_string_from_ascii()
				if text.find("\r\n\r\n") >= 0:
					c.answered = true
					c.out = _answer(text)
			if not c.out.is_empty():
				var sent: Array = peer.put_partial_data(c.out.slice(0, pace))
				if sent[0] == OK and sent[1] > 0: c.out = c.out.slice(sent[1])
			elif c.answered:
				c.linger += 1
				if c.linger > 3:
					peer.disconnect_from_host()
					peers.erase(c)

	func _answer(text: String) -> PackedByteArray:
		var lines := text.split("\r\n")
		var path := lines[0].split(" ")[1] if lines[0].split(" ").size() > 1 else "/"
		var from := -1
		for line in lines:
			if line.to_lower().begins_with("range: bytes="): from = int(line.split("=")[1].split("-")[0])
		log.append({"path": path, "range": from})
		if not files.has(path):
			return "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".to_ascii_buffer()
		var body: PackedByteArray = files[path]
		var start := 0
		var status := "200 OK"
		if from > 0 and from < body.size():
			start = from
			status = "206 Partial Content"
		var part := body.slice(start)
		var head := "HTTP/1.1 %s\r\nContent-Length: %d\r\nContent-Type: application/octet-stream\r\nConnection: close\r\n" % [status, part.size()]
		if start > 0: head += "Content-Range: bytes %d-%d/%d\r\n" % [start, body.size() - 1, body.size()]
		var out := (head + "\r\n").to_ascii_buffer()
		if cut_after.has(path):
			part = part.slice(0, int(cut_after[path]))
			cut_after.erase(path)
		out.append_array(part)
		return out

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ") + description)
	if not value: failed = true

func _initialize() -> void:
	call_deferred("run")

func texts(node: Node) -> String:
	if not is_instance_valid(node): return ""
	var out := []
	for l in node.find_children("*", "Label", true, false): out.append(l.text)
	for b in node.find_children("*", "Button", true, false): out.append(b.text)
	return "\n".join(out)

func write_policy(data: Dictionary) -> void:
	var file := FileAccess.open(policy_path, FileAccess.WRITE)
	if file == null:
		expect(false, "the server's policy file can be written: " + policy_path)
		quit(1)
		return
	file.store_string(JSON.stringify(data))
	file.close()
	await create_timer(2.3).timeout

func sha256(bytes: PackedByteArray) -> String:
	var hashing := HashingContext.new()
	hashing.start(HashingContext.HASH_SHA256)
	hashing.update(bytes)
	return hashing.finish().hex_encode()

## The patch pack: a probe text and some filler (so the download takes a few steps).
func build_pack(dir: String) -> PackedByteArray:
	DirAccess.make_dir_recursive_absolute(dir)
	var probe := FileAccess.open(dir.path_join("probe.txt"), FileAccess.WRITE)
	probe.store_string("patched to " + TARGET)
	probe.close()
	var filler := FileAccess.open(dir.path_join("filler.bin"), FileAccess.WRITE)
	var noise := RandomNumberGenerator.new()
	noise.seed = 7
	var bytes := PackedByteArray()
	bytes.resize(600 * 1024)
	for i in bytes.size(): bytes[i] = noise.randi() & 255
	filler.store_buffer(bytes)
	filler.close()
	var packer := PCKPacker.new()
	packer.pck_start(dir.path_join("patch.pck"))
	packer.add_file("res://qa_patch_probe.txt", dir.path_join("probe.txt"))
	packer.add_file("res://qa_patch_filler.bin", dir.path_join("filler.bin"))
	packer.flush()
	return FileAccess.get_file_as_bytes(dir.path_join("patch.pck"))

func list_with(entry: Dictionary, latest := TARGET) -> PackedByteArray:
	return JSON.stringify({"format": 1, "edition": "qa", "latest": latest, "bases": {base: entry}}).to_utf8_buffer()

## Opens the title the way the game starts (no session): main.gd checks the version before its menu.
func launch(settle := 1.0) -> Node:
	if VersionGate: VersionGate.reset()
	change_scene_to_file("res://scenes/main.tscn")
	await create_timer(settle).timeout
	return current_scene

func wait_until(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await create_timer(0.1).timeout
	return condition.call()

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=").trim_suffix("/")
		if arg.begins_with("--policy="): policy_path = arg.trim_prefix("--policy=")
	# tools/test.ps1 starts its QA server with TRIPOTHON_DATA_DIR set, and this process inherits it.
	if policy_path.is_empty() and not OS.get_environment("TRIPOTHON_DATA_DIR").is_empty():
		policy_path = OS.get_environment("TRIPOTHON_DATA_DIR").path_join("client_policy.json")
	if policy_path.is_empty(): policy_path = ProjectSettings.globalize_path("res://../artifacts/qa-patch/client_policy.json")
	Patcher = load("res://scripts/patcher.gd")
	PatchBoot = load("res://scripts/patch_boot.gd")
	base = PatchBoot.base_version
	expect(not base.is_empty() and Patcher.older(base, TARGET), "the installed version (%s) is older than the release under test" % base)
	var work := "user://qa_patch_%d" % (Time.get_ticks_usec() % 1000000000)
	Patcher.dir = work.path_join("patches")
	Patcher.pretend_installed = true
	Patcher.restart_hook = func(): restarted += 1
	saved_world = str(I18n.setting("server", ""))
	I18n.remember("server", server)
	var port := 0
	for attempt in 20:
		var candidate := 18800 + randi() % 900
		if host.start(candidate):
			port = candidate
			break
	expect(port > 0, "the patch host listens")
	process_frame.connect(host.poll)
	var pack := build_pack(work.path_join("source"))
	var pack_path := "/school/patches/%s_to_%s.pck" % [base, TARGET]
	var list_url := "http://127.0.0.1:%d/school/patches.json" % port
	host.files[pack_path] = pack
	var good := {"file": "patches/%s_to_%s.pck" % [base, TARGET], "size": pack.size(), "sha256": sha256(pack)}

	# ---------------------------------------------------------------- what a patch list means
	var step: Dictionary = Patcher.plan(JSON.parse_string(list_with(good).get_string_from_utf8()), list_url, base, base, TARGET)
	expect(step.action == "patch" and step.url == "http://127.0.0.1:%d/school/patches/%s_to_%s.pck" % [port, base, TARGET] and int(step.size) == pack.size(), "a patch for this installed version: download it")
	step = Patcher.plan({"format": 1, "latest": base, "bases": {}}, list_url, base, base, TARGET)
	expect(step.action == "wait", "the server names a newer game than the list: wait for its upload")
	step = Patcher.plan({"format": 1, "latest": base, "bases": {}}, list_url, base, base, base)
	expect(step.action == "none", "already current")
	step = Patcher.plan({"format": 1, "latest": TARGET, "bases": {"0.0.1": good}}, list_url, base, base, TARGET)
	expect(step.action == "reinstall" and step.reason == "no_patch_for_base", "no patch for this version: the installer")
	step = Patcher.plan({"format": 1, "latest": TARGET, "bases": {base: {"requires_reinstall": true, "reason": "engine"}}}, list_url, base, base, TARGET)
	expect(step.action == "reinstall" and step.reason == "engine", "a release that changes the engine: the installer")
	for bad in ["../evil.pck", "/abs/evil.pck", "https://elsewhere/evil.pck", "patches/evil.exe", "patches\\evil.pck"]:
		step = Patcher.plan({"format": 1, "latest": TARGET, "bases": {base: {"file": bad, "size": 10, "sha256": good.sha256}}}, list_url, base, base, TARGET)
		expect(step.action == "reinstall" and step.reason == "bad_list", "an unsafe file name is refused: " + bad)
	expect(Patcher.manifest_address({"patch_manifest_url": "http://evil.example/patches.json"}).is_empty() and Patcher.manifest_address({"patch_manifest_url": list_url}) == list_url, "patch lists only over https (or this PC)")

	# ---------------------------------------------------------------- a damaged download
	var fetcher = Patcher.new()
	root.add_child(fetcher)
	var damaged: Dictionary = Patcher.plan(JSON.parse_string(list_with(good.merged({"sha256": "0".repeat(64)}, true)).get_string_from_utf8()), list_url, base, base, TARGET)
	var problem: String = await fetcher.install(damaged)
	expect(problem == "checksum", "a download that does not match its SHA-256 is refused (%s)" % problem)
	expect(not FileAccess.file_exists(Patcher.dir.path_join("state.json")) and DirAccess.get_files_at(Patcher.dir).is_empty(), "nothing of it is kept")
	fetcher.queue_free()

	# ---------------------------------------------------------------- the title, release needs the installer
	await write_policy({"latest_client_version": TARGET, "client_download_url": "https://example.com/villagen/index.html", "client_patch_url": list_url})
	host.files["/school/patches.json"] = list_with({"requires_reinstall": true, "reason": "engine"})
	var title := await launch()
	VersionGate = title.gate.get_script()
	await wait_until(func(): return title.gate.patch_step == "installer", 10.0)
	var window := texts(title.gate.screen)
	expect(VersionGate.blocked == "client_update_required" and "업데이트 필요" in window and "새로 설치해야" in window and "새 버전 받기" in window, "a release that needs the installer: the installer screen")
	# The list does not have the announced version yet: the screen waits and checks again.
	host.files["/school/patches.json"] = list_with(good, base)
	title = await launch()
	await wait_until(func(): return title.gate.patch_step == "waiting", 10.0)
	expect("준비하고 있어요" in texts(title.gate.screen) and "다시 시도" in texts(title.gate.screen), "a patch not uploaded yet: 'being prepared', retried by itself")

	# ---------------------------------------------------------------- the launch: patch, resume, verify, restart
	host.files["/school/patches.json"] = list_with(good)
	host.cut_after[pack_path] = 200 * 1024
	host.log.clear()
	host.pace = 8 * 1024
	title = await launch(0.05)
	var seen_progress := false
	var deadline := Time.get_ticks_msec() + 40000
	while restarted == 0 and Time.get_ticks_msec() < deadline:
		if is_instance_valid(title.gate.patch_readout) and " / " in title.gate.patch_readout.text and title.gate.patch_step == "downloading": seen_progress = true
		await process_frame
	expect(title.screen == "login" and title.title_page != "", "the title came up under the update screen")
	expect(seen_progress, "download progress shown (MB of MB)")
	expect(restarted == 1, "the patch was downloaded, checked and the game restarts")
	expect("업데이트 완료" in texts(title.gate.screen), "'업데이트 완료! 게임을 다시 시작해요.' before the restart")
	var ranges := host.log.filter(func(r): return r.path == pack_path)
	expect(ranges.size() >= 2 and ranges[0].range == -1 and int(ranges[-1].range) == 200 * 1024, "the cut download resumed from where it stopped (%s)" % [ranges])
	var state: Dictionary = PatchBoot.read_state(Patcher.dir)
	expect(state.get("base") == base and state.get("version") == TARGET and int(state.get("size", 0)) == pack.size() and state.get("sha256") == good.sha256 and int(state.get("boots", -1)) == 0, "the verified patch is recorded for the next launch")
	expect(FileAccess.get_sha256(Patcher.dir.path_join(str(state.get("file", "")))) == good.sha256 and not FileAccess.file_exists(Patcher.dir.path_join(str(state.get("file", "")) + ".part")), "the pack is complete and nothing partial is left")

	# ---------------------------------------------------------------- after the restart
	VersionGate.reset()
	expect(PatchBoot.boot(Patcher.dir), "at launch the first autoload loads the patch")
	expect(FileAccess.get_file_as_string("res://qa_patch_probe.txt") == "patched to " + TARGET, "files come from the patch")
	expect(str(ProjectSettings.get_setting("application/config/version")) == TARGET and load("res://scripts/api.gd").client_version() == TARGET, "the game now reports the new version")
	expect(int(PatchBoot.read_state(Patcher.dir).get("boots", 0)) == 1, "this launch is counted until the title")
	title = await launch()
	await wait_until(func(): return title.get("title_page") == "menu", 15.0)
	expect(title.title_page == "menu" and not VersionGate.is_blocked() and not is_instance_valid(title.gate.update_pill), "the new version's title opens normally")
	await create_timer(0.5).timeout
	expect(int(PatchBoot.read_state(Patcher.dir).get("boots", -1)) == 0, "reaching the title confirms the patch")

	# ---------------------------------------------------------------- patch_boot.gd's guards
	var record: Dictionary = PatchBoot.read_state(Patcher.dir)
	record.boots = 3
	PatchBoot.write_state(Patcher.dir, record)
	expect(not PatchBoot.boot(Patcher.dir) and PatchBoot.problem == "crashed" and bool(PatchBoot.read_state(Patcher.dir).get("disabled", false)), "a patch that never reached the title three times is set aside")
	step = Patcher.plan(JSON.parse_string(list_with(good).get_string_from_utf8()), list_url, base, base, TARGET)
	expect(step.action == "reinstall" and step.reason == "patch_failed", "then the installer is offered instead of the same patch")
	record.boots = 0
	record.erase("disabled")
	record.base = "0.0.1"
	PatchBoot.write_state(Patcher.dir, record)
	expect(not PatchBoot.boot(Patcher.dir) and PatchBoot.problem == "other_base", "a patch for another installed version is not loaded")
	expect(PatchBoot.read_state(Patcher.dir).is_empty() and not FileAccess.file_exists(Patcher.dir.path_join(str(record.file))), "and is removed")
	await finish(work)

func finish(work: String) -> void:
	await write_policy({})
	process_frame.disconnect(host.poll)
	ProjectSettings.set_setting("application/config/version", base)
	PatchBoot.problem = ""
	Patcher.pretend_installed = false
	Patcher.restart_hook = Callable()
	Patcher.dir = PatchBoot.DIR
	if VersionGate:
		VersionGate.reset()
		VersionGate = null
	I18n.remember("server", saved_world)
	for folder in [work.path_join("patches"), work.path_join("source"), work]:
		for name in DirAccess.get_files_at(folder): DirAccess.remove_absolute(folder.path_join(name))
		DirAccess.remove_absolute(folder)
	print("PATCH_UPDATE ", JSON.stringify({"ok": not failed}))
	quit(1 if failed else 0)
