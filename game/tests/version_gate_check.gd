extends SceneTree
## The game version gate and maintenance notices (version_gate.gd) against a QA server whose policy
## file this test writes (server/client_policy.py reads it every couple of seconds):
## village banner for a newer game, the maintenance countdown (stronger in the last five minutes),
## the maintenance screen and its retry, the update window (426), the same screen following the
## player into a room and back, an expedition pausing under maintenance, and the title refusing
## a login when this game is too old.
##   TRIPOTHON_MODE=demo TRIPOTHON_DATA_DIR=artifacts/qa-version python -m uvicorn server.app:create_app --factory --port 8814
##   Godot --headless --path game --script res://tests/version_gate_check.gd -- --mute --qa --server=http://127.0.0.1:8814
## --policy=PATH names the server's <data>/client_policy.json (default artifacts/qa-version/).
## version_gate.gd, taken from the village's gate: loading it from this script before the main
## scene made the engine crash at exit (4.7.2).
var VersionGate: GDScript
var failed := false
var server := "http://127.0.0.1:8814"
var policy_path := ""
var resumed := 0
## --until=loaded|banner|countdown|maintenance|village|room|expedition stops after that part
## (quicker runs while working on one).
var until := ""

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ") + description)
	if not value: failed = true

func _initialize() -> void:
	call_deferred("run")

func capture(name: String) -> void:
	if DisplayServer.get_name() == "headless": return
	for i in 4: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/version-gate-" + name + ".png"))

func texts(node: Node) -> String:
	if not is_instance_valid(node): return ""
	var out := []
	for l in node.find_children("*", "Label", true, false): out.append(l.text)
	for b in node.find_children("*", "Button", true, false): out.append(b.text)
	return "\n".join(out)

func write_policy(data: Dictionary) -> void:
	var file := FileAccess.open(policy_path, FileAccess.WRITE)
	if file == null:
		expect(false, "the server's policy file can be written: " + policy_path + " (start the QA server with that data dir, or pass --policy=)")
		quit(1)
		return
	file.store_string(JSON.stringify(data))
	file.close()
	# The server looks at the file every two seconds.
	await create_timer(2.3).timeout

func now() -> int:
	return int(Time.get_unix_time_from_system())

## Any reply carries the notice version; a change makes the gate ask /v1/client.
func nudge(scene: Node) -> void:
	await scene.api.request("/v1/homestead")
	await create_timer(0.6).timeout

func gate_of(scene: Node) -> CanvasLayer:
	return scene.get("gate")

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=").trim_suffix("/")
		if arg.begins_with("--policy="): policy_path = arg.trim_prefix("--policy=")
		if arg.begins_with("--until="): until = arg.trim_prefix("--until=")
	if policy_path.is_empty(): policy_path = ProjectSettings.globalize_path("res://../artifacts/qa-version/client_policy.json")
	await write_policy({})
	var api = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = server
	var name := "gate_" + str(Time.get_ticks_usec())
	var password := "Gate-check-password-1"
	var login: Dictionary = await api.post("/v1/auth/register", {"username": name, "password": password})
	expect(login.ok, "a new account (no policy yet)")
	if not login.ok:
		quit(1)
		return
	Engine.set_meta("studio_session", {"token": login.data.token, "url": server, "room": "home"})
	change_scene_to_file("res://scenes/main.tscn")
	await create_timer(4.0).timeout
	var village: Node = current_scene
	expect(village.screen == "village", "village loaded")
	var gate := gate_of(village)
	expect(is_instance_valid(gate), "the village has a gate")
	VersionGate = gate.get_script()
	expect(not VersionGate.is_blocked(), "nothing blocked without a policy")
	expect(not is_instance_valid(gate.update_pill) and not is_instance_valid(gate.maintenance_pill), "no banners without a policy")

	if until == "loaded":
		await finish()
		return
	# A newer game is published: a gentle banner, play goes on.
	await write_policy({"latest_client_version": "99.0.0", "client_download_url": "https://example.com/villagen"})
	await nudge(village)
	expect(is_instance_valid(gate.update_pill) and gate.update_pill.visible, "new version banner in the village")
	expect("새 버전이 있어요" in texts(gate.update_pill) and "v99.0.0" in texts(gate.update_pill), "the banner names the new version")
	expect(not VersionGate.is_blocked() and village.world_movement_allowed(), "a newer version does not stop play")
	await capture("banner")

	if until == "banner":
		await finish()
		return
	# Maintenance in 45 minutes: nothing yet (the banner starts 30 minutes ahead).
	await write_policy({"latest_client_version": "99.0.0", "client_download_url": "https://example.com/villagen",
		"notice": {"id": "qa0", "starts_at": now() + 2700, "minutes": 10, "message": "QA 점검 안내"}})
	await nudge(village)
	expect(not VersionGate.notice.is_empty() and not is_instance_valid(gate.maintenance_pill), "no countdown 45 minutes ahead")
	# Maintenance in ten minutes: a countdown pill; in the last five it turns urgent.
	await write_policy({"latest_client_version": "99.0.0", "client_download_url": "https://example.com/villagen",
		"notice": {"id": "qa1", "starts_at": now() + 600, "minutes": 10, "message": "QA 점검 안내"}})
	await nudge(village)
	expect(is_instance_valid(gate.maintenance_pill), "maintenance countdown banner 10 minutes ahead")
	var shown: String = gate.maintenance_time.text if is_instance_valid(gate.maintenance_time) else ""
	expect(shown.begins_with("9:5") or shown == "10:00", "the countdown reads about ten minutes (" + shown + ")")
	expect(not gate.maintenance_urgent, "not urgent ten minutes ahead")
	expect("QA 점검 안내" in texts(gate.maintenance_pill), "the operator's message is shown")
	await write_policy({"latest_client_version": "99.0.0", "client_download_url": "https://example.com/villagen",
		"notice": {"id": "qa2", "starts_at": now() + 120, "minutes": 10, "message": "QA 점검 안내"}})
	await nudge(village)
	await process_frame
	expect(is_instance_valid(gate.maintenance_pill) and gate.maintenance_urgent, "urgent in the last five minutes")
	await capture("countdown")

	if until == "countdown":
		await finish()
		return
	# Maintenance starts: one clean screen, the world stops, nothing else talks.
	await write_policy({"notice": {"id": "qa3", "starts_at": now() - 5, "minutes": 10, "message": "QA 점검 중"}})
	await village.api.request("/v1/me")
	await process_frame
	expect(VersionGate.blocked == "server_maintenance", "a 503 opens the maintenance screen")
	expect(is_instance_valid(gate.screen) and "서버 점검 중" in texts(gate.screen) and "다시 시도" in texts(gate.screen), "maintenance screen with retry")
	expect("약 10분 뒤 끝나요" in texts(gate.screen) or "약 9분 뒤 끝나요" in texts(gate.screen), "it says when it ends")
	expect(not village.world_movement_allowed(), "the walker stops under the screen")
	village.message("this toast should not appear")
	expect(village.last_notice != "this toast should not appear", "scattered error toasts stay quiet")
	await capture("maintenance")
	# The player walks into a room meanwhile? The screen follows (static state), shown on arrival.
	gate.resumed.connect(func(): resumed += 1)
	await write_policy({})
	await gate.retry()
	expect(not VersionGate.is_blocked() and not is_instance_valid(gate.screen), "retry after maintenance reopens play")
	expect(resumed == 1, "the village reloads after maintenance")
	expect(village.world_movement_allowed(), "the walker moves again")

	if until == "maintenance":
		await finish()
		return
	# Too old for the server (426): the update window with the new version and a download button.
	await write_policy({"min_client_version": "99.0.0", "latest_client_version": "99.0.0", "client_download_url": "https://example.com/villagen"})
	var refused: Dictionary = await village.api.request("/v1/me")
	await process_frame
	expect(refused.get("error", "") == "client_update_required" and int(refused.get("status", 0)) == 426, "426 client_update_required")
	expect(VersionGate.blocked == "client_update_required", "update window opened")
	var window := texts(gate.screen)
	expect("업데이트 필요" in window and "v99.0.0" in window and "새 버전 받기" in window and "게임 종료" in window, "update window: version, download, quit")
	var download: Button = null
	for b in gate.screen.find_children("*", "Button", true, false):
		if b.text == "새 버전 받기": download = b
	expect(download != null and not download.disabled, "the download button is live")
	await capture("update")

	if until == "village":
		await finish()
		return
	# Into a room while the server is in maintenance: the room shows the same screen.
	await write_policy({})
	await gate.retry()
	expect(not VersionGate.is_blocked(), "minimum lifted")
	village.open_studio("home")
	await create_timer(3.0).timeout
	var home: Node = current_scene
	expect(home.get("room") == "home", "entered the home")
	var room_gate := gate_of(home)
	expect(is_instance_valid(room_gate), "the room has a gate")
	await write_policy({"notice": {"id": "qa4", "starts_at": now() - 5, "minutes": 3, "message": "방 점검"}})
	await home.api.request("/v1/studio")
	await process_frame
	expect(VersionGate.blocked == "server_maintenance" and is_instance_valid(room_gate.screen), "maintenance screen in the room")
	home.leave()
	await create_timer(4.0).timeout
	village = current_scene
	gate = gate_of(village)
	expect(village.has_method("tick_run") and is_instance_valid(gate.screen) and VersionGate.is_blocked(), "the screen follows the player back to the village")
	await write_policy({})
	await gate.retry()
	expect(not VersionGate.is_blocked(), "maintenance over")
	await create_timer(1.0).timeout

	if until == "room":
		await finish()
		return
	# An expedition pauses under maintenance and carries on afterwards.
	await village.start_run("forest", "standard")
	await create_timer(1.5).timeout
	expect(village.screen == "survival", "expedition started")
	await write_policy({"notice": {"id": "qa5", "starts_at": now() - 5, "minutes": 3, "message": "탐험 점검"}})
	var deadline := Time.get_ticks_msec() + 4000
	while Time.get_ticks_msec() < deadline and not VersionGate.is_blocked(): await create_timer(0.1).timeout
	expect(VersionGate.blocked == "server_maintenance", "the expedition's next input meets the maintenance screen")
	await create_timer(0.5).timeout
	expect(village.network_failures <= 1 and not village.ticking, "inputs stop while the screen is up")
	await capture("expedition")
	await write_policy({})
	await gate.retry()
	await create_timer(1.0).timeout
	expect(not VersionGate.is_blocked() and village.screen == "survival" and str(village.run.get("status", "")) == "active", "the expedition carries on")
	village.suspend_run()
	await create_timer(1.0).timeout

	if until == "expedition":
		await finish()
		return
	# The title: too old for this world, so login is refused with the update window.
	await write_policy({"min_client_version": "99.0.0", "client_download_url": "https://example.com/villagen"})
	await village.logout()
	await create_timer(0.5).timeout
	await gate.check(server)
	expect(village.screen == "login" and VersionGate.blocked == "client_update_required" and is_instance_valid(gate.screen), "update window over the title")
	await village.authenticate(false, server, name, password, "")
	expect(village.api.token.is_empty(), "login refused while this game is too old")
	await capture("title-update")
	# Only a newer game: the title shows the gentle banner and login works.
	await write_policy({"latest_client_version": "99.0.0", "client_download_url": "https://example.com/villagen"})
	await gate.ask(server)
	expect(not VersionGate.is_blocked() and is_instance_valid(gate.update_pill), "title banner for a newer game")
	await finish()

func finish() -> void:
	await write_policy({})
	VersionGate.reset()
	VersionGate = null
	print("VERSION_GATE ", JSON.stringify({"ok": not failed}))
	quit(1 if failed else 0)
