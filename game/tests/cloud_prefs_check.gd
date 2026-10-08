extends SceneTree
## Settings follow the account: the first login uploads this PC's settings, and a wiped PC gets them
## back on the next login (cloud_prefs.gd, /v1/prefs). Graphics stay with the PC.
const Main = preload("res://scripts/main.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const I18n = preload("res://scripts/i18n.gd")
var failed := false

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var cloud: Node = root.get_node("CloudPrefs")
	GameSettings.reload_settings()
	GameSettings.set_value("master", 40)
	GameSettings.set_value("shadows", "high")
	GameSettings.save()
	var app := Main.new()
	root.add_child(app)
	await create_timer(0.4).timeout
	await app.authenticate(true, "http://127.0.0.1:8766", "prefs_"+str(Time.get_ticks_msec()), "Prefs-check-password-1", "")
	var deadline := Time.get_ticks_msec() + 8000
	var stored := {}
	while Time.get_ticks_msec() < deadline:
		var reply: Dictionary = await app.api.request("/v1/prefs")
		if reply.ok and not reply.data.prefs.is_empty():
			stored = reply.data.prefs
			break
		await create_timer(0.3).timeout
	expect(int(stored.get("audio", {}).get("master", -1)) == 40, "first login uploaded this PC's sound settings")
	expect(not stored.has("graphics"), "graphics stay with the PC")
	# A wiped PC: default settings, then the same account logs in again.
	var config := ConfigFile.new()
	config.save(I18n.settings_path())
	GameSettings.reload_settings()
	expect(int(GameSettings.get_value("master")) == 100, "local settings wiped")
	await cloud.start(app.api.base_url, app.api.token)
	expect(int(GameSettings.get_value("master")) == 40, "sound settings came back from the account")
	expect(str(GameSettings.get_value("shadows")) != "high", "graphics did not come back (per PC)")
	# A change on this PC is sent back within a few seconds.
	GameSettings.set_value("music", 25)
	GameSettings.save()
	var sent := false
	deadline = Time.get_ticks_msec() + 8000
	while Time.get_ticks_msec() < deadline and not sent:
		await create_timer(0.5).timeout
		var reply: Dictionary = await app.api.request("/v1/prefs")
		sent = reply.ok and int(reply.data.prefs.get("audio", {}).get("music", -1)) == 25
	expect(sent, "a later change was saved to the account")
	cloud.stop()
	quit(1 if failed else 0)
