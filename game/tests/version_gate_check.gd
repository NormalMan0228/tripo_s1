extends SceneTree
## The game version gate and maintenance notices (version_gate.gd) against a QA server whose policy
## file this test writes (server/client_policy.py reads it every couple of seconds):
## village banner for a newer game, the maintenance countdown (stronger in the last five minutes),
## maintenance starting: the maintenance screen, the forced logout to the title (with the note and
## the expected end), the old session refused afterwards (session_reset) and a fresh sign-in; the
## update window (426) in a room, maintenance in a room (back to the title), an expedition under
## maintenance (logged out, the run waits on the server), the countdown on the title, an operator's
## logout-all, and the title refusing a login when this game is too old.
##   TRIPOTHON_MODE=demo TRIPOTHON_DATA_DIR=artifacts/qa-version python -m uvicorn server.app:create_app --factory --port 8814
##   Godot --headless --path game --script res://tests/version_gate_check.gd -- --mute --qa --server=http://127.0.0.1:8814
## --policy=PATH names the server's <data>/client_policy.json (default artifacts/qa-version/).
## version_gate.gd, taken from the village's gate: loading it from this script before the main
## scene made the engine crash at exit (4.7.2).
var VersionGate: GDScript
var failed := false
var server := preload("res://tests/qa_server.gd").url()  # tools/test.ps1 QA server
var policy_path := ""
var resumed := 0
var account := ""
var saved_world := ""
const I18n = preload("res://scripts/i18n.gd")
var password := "Gate-check-password-1"
## --until=loaded|banner|countdown|maintenance|room|expedition|title stops after that part.
var until := ""
## A connection of the test's own (no gate watches it) and what /v1/client served it last.
var looker: Node
var served := {}
## Every wait is for a state (a busy PC only makes it come later), bounded by these seconds.
const SCENE_SECONDS := 60.0
const STATE_SECONDS := 20.0

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ") + description)
	if not value: failed = true

func wait_until(condition: Callable, seconds := STATE_SECONDS) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await create_timer(0.1).timeout
	return condition.call()

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
	var written := Time.get_ticks_msec()
	# The server looks at the file every two seconds (server/client_policy.py CHECK_SECONDS): at least
	# that long (sessions_valid_after shows in no reply), and until /v1/client serves what it can show
	# of the file (a busy server, or a read of the half-written file, takes longer).
	while true:
		var reply: Dictionary = await looker.request("/v1/client")
		served = reply.get("data", {}) if reply.ok and reply.get("data") is Dictionary else {}
		if Time.get_ticks_msec() - written >= 2300 and serves(data): return
		if Time.get_ticks_msec() - written > STATE_SECONDS * 1000:
			expect(false, "the server serves the new policy within %d s (%s)" % [STATE_SECONDS, JSON.stringify(served)])
			return
		await create_timer(0.2).timeout

## Does the last /v1/client show the policy's versions, download page and notice?
func serves(data: Dictionary) -> bool:
	if not served.get("client") is Dictionary: return false
	var client: Dictionary = served.client
	for pair in [["min", "min_client_version"], ["latest", "latest_client_version"], ["download_url", "client_download_url"]]:
		if str(client.get(pair[0], "")) != str(data.get(pair[1], "")): return false
	var notice = served.get("notice")
	if data.get("notice") is Dictionary: return notice is Dictionary and str(notice.get("id", "")) == str(data.notice.get("id", ""))
	return notice == null

## The gate holds what the server serves now (client versions, the notice and whether it runs).
func gate_holds() -> bool:
	var notice = served.get("notice")
	var mine: Dictionary = VersionGate.notice
	var same: bool = mine.is_empty() if not notice is Dictionary else (str(mine.get("id", "")) == str(notice.get("id", "")) and bool(mine.get("active", false)) == bool(notice.get("active", false)))
	return same and VersionGate.client == served.get("client", {})

func now() -> int:
	return int(Time.get_unix_time_from_system())

## Any reply carries the notice version; a change makes the gate ask /v1/client. Until the gate holds
## what the server serves: a check already under way may bring the earlier answer, and then the next
## reply asks again.
func nudge(scene: Node) -> void:
	var deadline := Time.get_ticks_msec() + int(STATE_SECONDS * 1000)
	while not gate_holds() and Time.get_ticks_msec() < deadline:
		await scene.api.request("/v1/homestead")
		await wait_until(gate_holds, 1.0)
	await process_frame

## The title asks the server (as its menu and login card do) until the gate holds the answer: an ask
## for the same world already under way returns at once and may bring the earlier answer.
func ask_until_held(gate: Node) -> void:
	var deadline := Time.get_ticks_msec() + int(STATE_SECONDS * 1000)
	while true:
		await gate.ask(server)
		if gate_holds() or Time.get_ticks_msec() > deadline: return
		await create_timer(0.2).timeout

## The retry key until done() (a check already under way makes one press do nothing).
func retry_until(gate: Node, done: Callable) -> void:
	var deadline := Time.get_ticks_msec() + int(STATE_SECONDS * 1000)
	while true:
		await gate.retry()
		if done.call() or Time.get_ticks_msec() > deadline: return
		await create_timer(0.2).timeout

func gate_of(scene: Node) -> CanvasLayer:
	return scene.get("gate") if is_instance_valid(scene) else null

## Signs in (a fresh session) and opens the village the way a room hands over to it.
func enter_village() -> Node:
	var api = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = server
	var login: Dictionary = await api.post("/v1/auth/login", {"username": account, "password": password})
	api.queue_free()
	if not login.ok: return null
	Engine.set_meta("studio_session", {"token": login.data.token, "url": server, "room": "home"})
	change_scene_to_file("res://scenes/main.tscn")
	return await wait_for_village()

## The scene in front is the village, built, signed in and its walker free to move.
func village_ready() -> bool:
	var scene := current_scene
	if not is_instance_valid(scene) or not scene.has_method("tick_run") or scene.get("screen") != "village": return false
	return not str(scene.api.token).is_empty() and is_instance_valid(scene.get("player")) and bool(scene.player.controls_enabled)

func wait_for_village() -> Node:
	await wait_until(village_ready, SCENE_SECONDS)
	return current_scene

## The scene in front is the home (studio.gd), standing: its own frame work starts once the stage is built.
func home_ready() -> bool:
	var scene := current_scene
	return is_instance_valid(scene) and not scene.has_method("tick_run") and scene.get("room") == "home" and is_instance_valid(gate_of(scene)) and scene.is_processing()

## Waits until the scene in front is the title (main.gd on its login screen, no session).
func wait_for_title(seconds := SCENE_SECONDS) -> Node:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		var scene := current_scene
		if is_instance_valid(scene) and scene.has_method("tick_run") and scene.get("screen") == "login" and scene.api.token.is_empty():
			return scene
		await create_timer(0.1).timeout
	return current_scene

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=").trim_suffix("/")
		if arg.begins_with("--policy="): policy_path = arg.trim_prefix("--policy=")
		if arg.begins_with("--until="): until = arg.trim_prefix("--until=")
	# tools/test.ps1 starts its QA server with TRIPOTHON_DATA_DIR set, and this process inherits it.
	if policy_path.is_empty() and not OS.get_environment("TRIPOTHON_DATA_DIR").is_empty():
		policy_path = OS.get_environment("TRIPOTHON_DATA_DIR").path_join("client_policy.json")
	if policy_path.is_empty(): policy_path = ProjectSettings.globalize_path("res://../artifacts/qa-version/client_policy.json")
	# The title asks the remembered world (a real login remembers it); --qa keeps this in the QA settings.
	saved_world = str(I18n.setting("server", ""))
	I18n.remember("server", server)
	looker = load("res://scripts/api.gd").new()
	root.add_child(looker)
	looker.base_url = server
	await write_policy({})
	var api = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = server
	account = "gate_" + str(Time.get_ticks_usec())
	var login: Dictionary = await api.post("/v1/auth/register", {"username": account, "password": password})
	expect(login.ok, "a new account (no policy yet)")
	if not login.ok:
		quit(1)
		return
	api.queue_free()
	Engine.set_meta("studio_session", {"token": login.data.token, "url": server, "room": "home"})
	change_scene_to_file("res://scenes/main.tscn")
	var village: Node = await wait_for_village()
	expect(village.screen == "village", "village loaded")
	var gate := gate_of(village)
	expect(is_instance_valid(gate), "the village has a gate")
	VersionGate = gate.get_script()
	expect(not VersionGate.is_blocked(), "nothing blocked without a policy")
	expect(not is_instance_valid(gate.update_pill) and not is_instance_valid(gate.maintenance_pill), "no banners without a policy")

	if until == "loaded":
		await finish()
		return
	# A newer game is published: a gentle banner, play goes on (a source run; installed games update
	# at their title, tests/patch_update_check.gd).
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
	# The pill's clock (and its urgency) moves on the gate's next frame.
	await wait_until(func(): return is_instance_valid(gate.maintenance_pill) and gate.maintenance_urgent)
	expect(is_instance_valid(gate.maintenance_pill) and gate.maintenance_urgent, "urgent in the last five minutes")
	await capture("countdown")

	if until == "countdown":
		await finish()
		return
	# Maintenance starts: one clean screen, and the game leaves the world for the title.
	var old_token: String = village.api.token
	var started := now() - 5
	await write_policy({"notice": {"id": "qa3", "starts_at": started, "minutes": 10, "message": "QA 점검 중"}})
	await village.api.request("/v1/me")
	await process_frame
	expect(VersionGate.blocked == "server_maintenance", "a 503 opens the maintenance screen")
	expect(not village.world_movement_allowed(), "the walker stops under the screen")
	village.message("this toast should not appear")
	expect(village.last_notice != "this toast should not appear", "scattered error toasts stay quiet")
	var title := await wait_for_title()
	expect(title == village and village.screen == "login" and village.api.token.is_empty(), "maintenance logs the player out to the title")
	gate = gate_of(village)
	var window := texts(gate.screen)
	expect(is_instance_valid(gate.screen) and "서버 점검 중" in window and "다시 시도" in window, "maintenance screen with retry over the title")
	expect("약 10분 뒤 끝나요" in window or "약 9분 뒤 끝나요" in window, "it says when it ends")
	expect("끝나는 시각" in window and "(예상)" in window, "it shows the expected end time")
	expect("로그아웃했어요" in window and "다시 로그인" in window, "it says the player was logged out and signs in again afterwards")
	await capture("maintenance")
	gate.resumed.connect(func(): resumed += 1)
	# What ops/notice.sh cancel writes: the maintenance is gone, the sessions from before it stay over.
	await write_policy({"sessions_valid_after": started})
	await retry_until(gate, func(): return not VersionGate.is_blocked())
	expect(not VersionGate.is_blocked() and not is_instance_valid(gate.screen), "retry after maintenance closes the screen")
	expect(resumed == 1 and village.screen == "login", "the title stays: the player signs in again")
	expect(is_instance_valid(gate.note_pill) and "다시 로그인" in texts(gate.note_pill), "the title keeps the sign-in-again note")
	var stale = load("res://scripts/api.gd").new()
	root.add_child(stale)
	stale.base_url = server
	stale.token = old_token
	var refused_old: Dictionary = await stale.request("/v1/me")
	expect(int(refused_old.get("status", 0)) == 401 and str(refused_old.get("error", "")) == "session_reset", "the session from before the maintenance is over (401 session_reset)")
	stale.queue_free()

	if until == "maintenance":
		await finish()
		return
	# Signed in again, into a room: too old for the server (426) shows the update window there.
	village = await enter_village()
	expect(is_instance_valid(village) and village.screen == "village" and not village.api.token.is_empty(), "a fresh sign-in plays again")
	# The village gate drops the note at its first refresh while signed in (its first check, ~3 s).
	await wait_until(func(): return not is_instance_valid(gate_of(village).note_pill))
	expect(not is_instance_valid(gate_of(village).note_pill), "the note is gone once signed in")
	village.open_studio("home")
	await wait_until(home_ready, SCENE_SECONDS)
	var home: Node = current_scene
	expect(home.get("room") == "home", "entered the home")
	var room_gate := gate_of(home)
	expect(is_instance_valid(room_gate), "the room has a gate")
	await write_policy({"min_client_version": "99.0.0", "latest_client_version": "99.0.0", "client_download_url": "https://example.com/villagen"})
	var refused: Dictionary = await home.api.request("/v1/studio")
	await process_frame
	expect(refused.get("error", "") == "client_update_required" and int(refused.get("status", 0)) == 426, "426 client_update_required")
	expect(VersionGate.blocked == "client_update_required", "update window opened")
	window = texts(room_gate.screen)
	expect("업데이트 필요" in window and "v99.0.0" in window and "새 버전 받기" in window and "게임 종료" in window, "update window: version, download, quit")
	var download: Button = null
	for b in room_gate.screen.find_children("*", "Button", true, false):
		if b.text == "새 버전 받기": download = b
	expect(download != null and not download.disabled, "the download button is live")
	await capture("update")
	await write_policy({})
	await retry_until(room_gate, func(): return not VersionGate.is_blocked())
	expect(not VersionGate.is_blocked(), "minimum lifted")
	# Maintenance in the room: the screen, then back to the title (main.tscn) without a session.
	# What the room showed when it left for the title (the room's own calls may meet the 503 first,
	# while the policy is being read).
	var room_screen := []
	room_gate.logout_required.connect(func(_reason): room_screen.append(VersionGate.blocked == "server_maintenance" and is_instance_valid(room_gate.screen)))
	await write_policy({"notice": {"id": "qa4", "starts_at": now() - 5, "minutes": 3, "message": "방 점검"}})
	if is_instance_valid(home) and not str(home.api.token).is_empty(): await home.api.request("/v1/studio")
	await process_frame
	expect(not room_screen.is_empty() and room_screen[0], "maintenance screen in the room")
	title = await wait_for_title()
	expect(is_instance_valid(title) and title.has_method("tick_run") and title.screen == "login", "maintenance in a room returns to the title")
	expect(is_instance_valid(gate_of(title).screen) and VersionGate.is_blocked(), "the maintenance screen follows to the title")
	await write_policy({})
	await retry_until(gate_of(title), func(): return not VersionGate.is_blocked())
	expect(not VersionGate.is_blocked(), "maintenance over")

	if until == "room":
		await finish()
		return
	# An expedition under maintenance: logged out, and the run waits on the server for the next sign-in.
	village = await enter_village()
	# start_run does nothing while the village is still busy with something else.
	await wait_until(func(): return not village.busy)
	await village.start_run("forest", "standard")
	await wait_until(func(): return village.screen == "survival", SCENE_SECONDS)
	expect(village.screen == "survival", "expedition started")
	await write_policy({"notice": {"id": "qa5", "starts_at": now() - 5, "minutes": 3, "message": "탐험 점검"}})
	title = await wait_for_title()
	expect(title == village and village.screen == "login" and VersionGate.blocked == "server_maintenance", "the expedition's next input meets maintenance: back to the title")
	expect(village.run_id.is_empty() and not village.ticking, "inputs stop")
	await capture("expedition")
	await write_policy({})
	await retry_until(gate_of(village), func(): return not VersionGate.is_blocked())
	var checker = load("res://scripts/api.gd").new()
	root.add_child(checker)
	checker.base_url = server
	var again: Dictionary = await checker.post("/v1/auth/login", {"username": account, "password": password})
	checker.token = str(again.get("data", {}).get("token", ""))
	var me: Dictionary = await checker.request("/v1/me")
	expect(me.ok and me.data.get("active_run_summary") is Dictionary, "the expedition waits under 이어하기 after signing in again")
	checker.queue_free()

	if until == "expedition":
		await finish()
		return
	# The title counts down too (before anyone signs in).
	await write_policy({"notice": {"id": "qa6", "starts_at": now() + 600, "minutes": 5, "message": "타이틀 점검 안내"}})
	await ask_until_held(gate_of(village))
	expect(village.screen == "login" and is_instance_valid(gate_of(village).maintenance_pill), "countdown banner on the title")
	expect("타이틀 점검 안내" in texts(gate_of(village).maintenance_pill), "with the operator's message")
	await capture("title-countdown")
	# An operator's logout-all (no maintenance): the next reply sends the player to the title.
	await write_policy({})
	village = await enter_village()
	expect(is_instance_valid(village) and village.screen == "village", "signed in again")
	await write_policy({"sessions_valid_after": now() + 1})
	await village.api.request("/v1/me")
	title = await wait_for_title()
	expect(title == village and village.screen == "login", "session_reset returns to the title")
	expect(is_instance_valid(gate_of(village).note_pill) and "다시 로그인" in texts(gate_of(village).note_pill), "with a note to sign in again")

	if until == "title":
		await finish()
		return
	# The title: too old for this world, so login is refused with the update window.
	await write_policy({"min_client_version": "99.0.0", "client_download_url": "https://example.com/villagen"})
	gate = gate_of(village)
	await ask_until_held(gate)
	expect(village.screen == "login" and VersionGate.blocked == "client_update_required" and is_instance_valid(gate.screen), "update window over the title")
	await village.authenticate(false, server, account, password, "")
	expect(village.api.token.is_empty(), "login refused while this game is too old")
	await capture("title-update")
	# Only a newer game (a source run): the title shows the gentle banner and login works.
	await write_policy({"latest_client_version": "99.0.0", "client_download_url": "https://example.com/villagen"})
	await ask_until_held(gate)
	expect(not VersionGate.is_blocked() and is_instance_valid(gate.update_pill), "title banner for a newer game")
	await finish()

func finish() -> void:
	await write_policy({})
	VersionGate.reset()
	VersionGate.logout_note = ""
	VersionGate = null
	I18n.remember("server", saved_world)
	print("VERSION_GATE ", JSON.stringify({"ok": not failed}))
	quit(1 if failed else 0)
