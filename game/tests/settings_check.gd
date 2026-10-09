extends SceneTree
## Settings round trip (headless):
##   godot --headless --path game --script res://tests/settings_check.gd -- --qa
## Every setting survives save/load in the QA settings file, applying it changes the
## engine (bus volumes and mutes, MSAA, 3D scale, LOD threshold, frame cap, content
## scale, brightness, shadows of tracked lights), rebinding updates the InputMap and
## persists, defaults restore, and the settings and pause menus build every page.
## The QA file is restored afterwards.
## With --capture (windowed) it also saves artifacts/settings-<tab>.png and
## artifacts/settings-pause*.png for review.
const GameSettings = preload("res://scripts/game_settings.gd")
const SettingsMenu = preload("res://scripts/settings_menu.gd")
const PauseMenu = preload("res://scripts/pause_menu.gd")
const I18n = preload("res://scripts/i18n.gd")
const Daylight = preload("res://scripts/daylight.gd")

var failures := 0
var checks := 0

class FakeApp extends Node:
	var screen := "survival"
	var paused := false
	var run := {"status":"active"}
	var pending_action := "attack"
	var pending_target := "x"
	var coop_run := false
	var results_shown := false
	var player: Node = null
	var ui: Control = null
	var calls: Array = []
	func suspend_run() -> void: calls.append("suspend")
	func confirm_return() -> void: calls.append("return")
	func logout() -> void: calls.append("logout")

class FakeRoom extends Control:
	var left := false
	func leave() -> void: left = true

func check(ok: bool, what: String) -> void:
	checks += 1
	if ok: return
	failures += 1
	print("SETTINGS_FAIL ", what)

func _initialize() -> void:
	call_deferred("run")

func capture_mode() -> bool:
	return "--capture" in OS.get_cmdline_user_args()

func run() -> void:
	check("--qa" in OS.get_cmdline_user_args(), "run with -- --qa so the player's settings stay untouched")
	var path := I18n.settings_path()
	var backup := FileAccess.get_file_as_bytes(path) if FileAccess.file_exists(path) else PackedByteArray()
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	if capture_mode():
		await captures()
	else:
		check_project_defaults()
		GameSettings.reload_settings()
		GameSettings.apply_all(self)
		await process_frame
		await process_frame
		check(is_instance_valid(GameSettings.runtime) and GameSettings.runtime.is_inside_tree(), "runtime node joined the root")
		check_defaults()
		check_round_trip()
		await check_engine_state()
		check_audio()
		check_bindings()
		check_preview_and_reset()
		check_legacy()
		await check_interface()
		check_hooks()
		await check_menus()
		check(load("res://maps/archipelago/environment_layout.gd").can_instantiate(), "environment_layout.gd compiles")
	# Leave the QA file as it was.
	if backup.is_empty(): DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	else:
		var file := FileAccess.open(path, FileAccess.WRITE)
		file.store_buffer(backup)
		file.close()
	GameSettings.reload_settings()
	print("SETTINGS_DONE checks=%d failures=%d" % [checks, failures])
	quit(1 if failures else 0)

# ------------------------------------------------------------------ defaults
func check_project_defaults() -> void:
	# Before apply_input runs, InputMap holds exactly what project.godot declares.
	for entry in GameSettings.ACTIONS:
		var action: String = entry[0]
		check(InputMap.has_action(action), "project.godot declares %s" % action)
		var keys := []
		for event in InputMap.action_get_events(action):
			if event is InputEventKey: keys.append(event.physical_keycode)
		var wanted := (entry[2] as Array).filter(func(k): return k != KEY_NONE)
		check(keys == wanted, "%s project keys %s != defaults %s" % [action, keys, wanted])
	for name in ["Master","Music","SFX","Ambience","Voice","UI"]:
		var index := AudioServer.get_bus_index(name)
		check(index >= 0, "bus %s exists" % name)
		if index > 0: check(AudioServer.get_bus_send(index) == &"Master", "%s sends to Master" % name)

func check_defaults() -> void:
	for key in GameSettings.DEFAULTS:
		if key == "language": continue
		check(GameSettings.get_value(key) == GameSettings.DEFAULTS[key], "default %s" % key)
	check(GameSettings.get_value("preset") == "medium", "medium is the default preset")
	check(get_root().msaa_3d == Viewport.MSAA_2X, "default MSAA 2x")
	check(is_equal_approx(get_root().scaling_3d_scale, 1.0), "default 3D scale")
	check(is_equal_approx(get_root().content_scale_factor, 1.0), "default UI scale")

func other_value(key: String):
	var value = GameSettings.DEFAULTS[key]
	if GameSettings.CHOICES.has(key):
		for choice in GameSettings.CHOICES[key]:
			if choice[0] != value and not (key == "preset" and choice[0] == "custom"): return choice[0]
	if GameSettings.RANGES.has(key):
		var r: Array = GameSettings.RANGES[key]
		return r[0] if value != r[0] else r[1]
	if value is bool: return not value
	return value

func check_round_trip() -> void:
	for key in GameSettings.DEFAULTS:
		if key in ["language","preset","window_mode","mute_all","background_mute"]: continue
		var wanted = other_value(key)
		GameSettings.set_value(key, wanted)
		GameSettings.reload_settings()
		check(GameSettings.get_value(key) == wanted, "%s did not survive save/load (%s != %s)" % [key, GameSettings.get_value(key), wanted])
		GameSettings.set_value(key, GameSettings.DEFAULTS[key])
	# window_mode is saved but only applied with a real display.
	GameSettings.set_value("window_mode", "borderless")
	GameSettings.reload_settings()
	check(GameSettings.get_value("window_mode") == "borderless", "window_mode round trip")
	check(GameSettings.window_mode_for("fullscreen") == Window.MODE_EXCLUSIVE_FULLSCREEN and GameSettings.window_mode_for("borderless") == Window.MODE_FULLSCREEN, "window mode mapping")
	GameSettings.set_value("window_mode", "windowed")
	# Bad values in the file fall back to defaults or clamp.
	var config := ConfigFile.new()
	config.load(I18n.settings_path())
	config.set_value("graphics", "render_scale", 500)
	config.set_value("graphics", "shadows", "ultra")
	config.set_value("audio", "music", -20)
	config.save(I18n.settings_path())
	GameSettings.reload_settings()
	check(GameSettings.get_value("render_scale") == 100, "render_scale clamps")
	check(GameSettings.get_value("shadows") == "low", "unknown shadows falls back")
	check(GameSettings.get_value("music") == 0, "music clamps at 0")
	GameSettings.commit(GameSettings.defaults_for("graphics").merged(GameSettings.defaults_for("audio")))
	# Language goes through I18n's [game] key.
	GameSettings.set_value("language", "en")
	check(I18n.language() == "en" and TranslationServer.get_locale().begins_with("en"), "language saved through I18n")
	GameSettings.set_value("language", "ko")
	check(I18n.language() == "ko", "language back to ko")

func check_engine_state() -> void:
	var root := get_root()
	GameSettings.set_value("preset", "high")
	check(GameSettings.get_value("shadows") == "high" and GameSettings.get_value("msaa") == "4x" and GameSettings.get_value("view_detail") == "high", "high preset fills its values")
	check(root.msaa_3d == Viewport.MSAA_4X, "high preset MSAA 4x")
	check(is_equal_approx(root.mesh_lod_threshold, 1.0/1.6), "view detail high LOD threshold")
	GameSettings.set_value("preset", "low")
	check(root.msaa_3d == Viewport.MSAA_DISABLED and is_equal_approx(root.scaling_3d_scale, 0.8), "low preset MSAA off, 80% scale")
	GameSettings.set_value("shadows", "high")
	check(GameSettings.get_value("preset") == "custom", "changing a preset value makes it custom")
	GameSettings.set_value("render_scale", 65)
	check(is_equal_approx(root.scaling_3d_scale, 0.65), "render scale 65%")
	GameSettings.set_value("msaa", "2x")
	check(root.msaa_3d == Viewport.MSAA_2X, "MSAA 2x")
	GameSettings.set_value("fps_cap", 60)
	check(Engine.max_fps == 60, "frame cap 60")
	GameSettings.set_value("fps_cap", 0)
	check(Engine.max_fps == 0, "frame cap off")
	GameSettings.set_value("vsync", false)
	check(GameSettings.get_value("vsync") == false, "vsync saved")
	GameSettings.set_value("vsync", true)
	# A room's own SubViewport, container and sun.
	var container := SubViewportContainer.new()
	var view := SubViewport.new()
	container.add_child(view)
	root.add_child(container)
	var sun := DirectionalLight3D.new()
	view.add_child(sun)
	GameSettings.track_viewport(view, container)
	GameSettings.track_light(sun)
	GameSettings.set_value("msaa", "4x")
	check(view.msaa_3d == Viewport.MSAA_4X, "tracked viewport follows MSAA")
	GameSettings.set_value("shadows", "off")
	check(not sun.shadow_enabled, "tracked sun loses shadows when off")
	GameSettings.set_value("shadows", "low")
	check(sun.shadow_enabled and sun.directional_shadow_mode == DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS, "low shadows: two splits")
	GameSettings.set_value("shadows", "high")
	check(sun.directional_shadow_mode == DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS, "high shadows: four splits")
	GameSettings.set_value("brightness", 130)
	var material := container.material as ShaderMaterial
	check(material != null and is_equal_approx(float(material.get_shader_parameter("gamma")), GameSettings.gamma()) and GameSettings.gamma() > 1.0, "room brightness reaches the container")
	check(is_equal_approx(float(GameSettings.runtime.shade_material.get_shader_parameter("gamma")), GameSettings.gamma()), "village brightness pass gamma")
	# The full-screen pass only runs over the root's own 3D camera.
	var camera := Camera3D.new()
	var stage := Node3D.new()
	root.add_child(stage)
	stage.add_child(camera)
	camera.current = true
	GameSettings.runtime.update_brightness()
	check(GameSettings.runtime.shade.visible, "brightness pass on over a 3D view")
	GameSettings.set_value("brightness", 100)
	check(not GameSettings.runtime.shade.visible, "brightness pass off at 100%")
	stage.queue_free()
	container.queue_free()
	await process_frame
	GameSettings.commit(GameSettings.defaults_for("graphics"))
	check(GameSettings.get_value("preset") == "medium", "graphics defaults restore the medium preset")

func bus_db(name: String) -> float:
	return AudioServer.get_bus_volume_db(AudioServer.get_bus_index(name))

func bus_muted(name: String) -> bool:
	return AudioServer.is_bus_mute(AudioServer.get_bus_index(name))

func check_audio() -> void:
	var session_mute := "--mute" in OS.get_cmdline_user_args()
	for pair in GameSettings.BUSES:
		GameSettings.set_value(pair[1], 50)
		check(absf(bus_db(pair[0])-linear_to_db(0.25)) < 0.01, "%s at 50%% is %.2f dB" % [pair[0], bus_db(pair[0])])
		GameSettings.set_value(pair[1], 0)
		check(bus_muted(pair[0]), "%s mutes at 0" % pair[0])
		GameSettings.set_value(pair[1], 100)
		check(absf(bus_db(pair[0])) < 0.01 and (pair[0] == "Master" and session_mute or not bus_muted(pair[0])), "%s back to 0 dB" % pair[0])
	GameSettings.set_value("mute_all", true)
	check(bus_muted("Master"), "mute all mutes Master")
	GameSettings.set_value("mute_all", false)
	if not session_mute: check(not bus_muted("Master"), "unmute")
	# The M key path (sound.gd) flips the same saved setting.
	var sound: Node = load("res://scripts/sound.gd").new()
	get_root().add_child(sound)
	sound.toggle()
	check(GameSettings.get_value("mute_all") and sound.muted and bus_muted("Master"), "sound.toggle() mutes and saves")
	sound.toggle()
	check(not GameSettings.get_value("mute_all"), "sound.toggle() unmutes")
	check(sound.music[0].bus == &"Music" and sound.voices[0].bus == &"SFX", "sound.gd players on Music/SFX")
	# Clicks go through RpgUi.sfx (deduped per press), whose players sit on the UI bus.
	var rpg_ui: GDScript = load("res://scripts/rpg_ui.gd")
	rpg_ui._last_played.erase("click")
	var clicks_before: int = rpg_ui._voice
	sound.effect("click")
	# Headless runs skip UI sounds (the dummy audio driver never finishes them).
	var played := 0 if DisplayServer.get_name() == "headless" else 1
	check(rpg_ui._voice == clicks_before+played and AudioServer.get_bus_index("UI") >= 0, "click plays on UI")
	sound.effect("gather")
	check(sound.voices[(sound.voice_index+sound.voices.size()-1)%sound.voices.size()].bus == &"SFX", "gather plays on SFX")
	sound.free()
	# Background mute follows window focus.
	GameSettings.set_value("background_mute", true)
	GameSettings.runtime._notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	check(bus_muted("Master"), "muted in the background")
	GameSettings.runtime._notification(Node.NOTIFICATION_APPLICATION_FOCUS_IN)
	if not session_mute: check(not bus_muted("Master"), "sound back with focus")
	GameSettings.set_value("background_mute", false)
	GameSettings.runtime._notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	if not session_mute: check(not bus_muted("Master"), "background mute off keeps sound")
	GameSettings.runtime._notification(Node.NOTIFICATION_APPLICATION_FOCUS_IN)
	# Every other player in the game is on a named bus.
	var transition: CanvasLayer = load("res://scripts/transition.gd").new()
	check(transition.door.bus == &"SFX", "door sounds on SFX")
	transition.free()
	var life: Node = load("res://scripts/life_sfx.gd").new()
	get_root().add_child(life)
	check(life.voices[0].bus == &"SFX", "life sounds on SFX")
	life.free()
	var audio: Node = load("res://scripts/world_audio.gd").new()
	get_root().add_child(audio)
	audio.setup()
	check(audio.steps[0].bus == &"SFX" and audio.beds["coast"].bus == &"Ambience", "footsteps on SFX, beds on Ambience")
	audio.free()

func key_event(code: int) -> InputEventKey:
	var event := InputEventKey.new()
	event.physical_keycode = code
	event.pressed = true
	return event

func action_keys(action: String) -> Array:
	var out := []
	for event in InputMap.action_get_events(action):
		if event is InputEventKey: out.append(event.physical_keycode)
	return out

func check_bindings() -> void:
	check(GameSettings.canonical_key(key_event(KEY_E)) == KEY_E, "E is interact by default")
	check(GameSettings.canonical_key(key_event(KEY_F3)) == KEY_F3, "F3 passes through")
	check(GameSettings.canonical_key(key_event(KEY_UP)) == KEY_W, "arrow up is forward")
	var result := GameSettings.rebind("interact", 0, KEY_G)
	check(result.ok and str(result.swapped) == "", "rebind interact to G")
	check(action_keys("interact") == [KEY_G], "InputMap interact = G (%s)" % [action_keys("interact")])
	check(GameSettings.canonical_key(key_event(KEY_G)) == KEY_E, "G reports KEY_E")
	check(GameSettings.canonical_key(key_event(KEY_E)) == KEY_NONE, "E no longer interacts")
	check(GameSettings.key_label("interact") == "G", "prompt label G")
	result = GameSettings.rebind("eat", 0, KEY_G)
	check(result.ok and result.swapped == "interact", "conflict swaps with interact")
	check(GameSettings.binding("eat")[0] == KEY_G and GameSettings.binding("interact")[0] == KEY_Q, "swap gave interact eat's old Q")
	check(action_keys("eat") == [KEY_G] and action_keys("interact") == [KEY_Q], "InputMap after swap")
	result = GameSettings.rebind("attack", 0, KEY_ESCAPE)
	check(not result.ok and result.reason == "reserved", "Esc cannot be bound")
	GameSettings.rebind("run", 1, KEY_CTRL)
	GameSettings.reload_settings()
	GameSettings.apply_input()
	check(GameSettings.binding("run") == [KEY_SHIFT, KEY_CTRL] and action_keys("run") == [KEY_SHIFT, KEY_CTRL], "bindings persist")
	check(InputMap.action_get_events("move_left").any(func(e): return e is InputEventJoypadMotion), "left stick kept on move_left")
	GameSettings.reset_bindings()
	check(GameSettings.bindings == GameSettings.default_bindings(), "reset bindings")
	check(action_keys("interact") == [KEY_E] and action_keys("move_forward") == [KEY_W, KEY_UP], "InputMap defaults back")
	# Run: hold or toggle.
	Input.action_press("run")
	check(GameSettings.running(), "hold to run")
	Input.action_release("run")
	check(not GameSettings.running(), "release stops")
	GameSettings.set_value("run_mode", "toggle")
	GameSettings.runtime._input(key_event(KEY_SHIFT))
	check(GameSettings.running(), "toggle latches")
	GameSettings.runtime._input(key_event(KEY_SHIFT))
	check(not GameSettings.running(), "toggle unlatches")
	GameSettings.set_value("run_mode", "hold")

func check_preview_and_reset() -> void:
	GameSettings.set_value("music", 80)
	GameSettings.preview({"music": 20, "shadows": "off"})
	check(absf(bus_db("Music")-GameSettings.volume_db(20)) < 0.01, "preview moves the bus")
	check(GameSettings.get_value("shadows") != "off", "preview ignores non-live keys")
	GameSettings.reload_settings()
	check(GameSettings.get_value("music") == 80, "preview is not saved")
	GameSettings.preview({"music": 20})
	GameSettings.end_preview()
	check(absf(bus_db("Music")-GameSettings.volume_db(80)) < 0.01, "end_preview restores")
	for category in GameSettings.CATEGORIES:
		for key in GameSettings.CATEGORIES[category]:
			if key in ["language","preset","window_mode"]: continue
			GameSettings.set_value(key, other_value(key))
		GameSettings.commit(GameSettings.defaults_for(category))
		for key in GameSettings.defaults_for(category):
			check(GameSettings.get_value(key) == GameSettings.DEFAULTS[key], "%s reset to default" % key)

func check_legacy() -> void:
	var config := ConfigFile.new()
	config.load(I18n.settings_path())
	config.erase_section("graphics")
	config.set_value("game", "graphics", "low")
	config.save(I18n.settings_path())
	GameSettings.reload_settings()
	check(GameSettings.get_value("preset") == "low" and GameSettings.get_value("shadows") == "off", "old [game] graphics=low becomes the low preset")
	GameSettings.commit(GameSettings.defaults_for("graphics"))
	check(str(I18n.setting("graphics", "")) == "medium", "legacy key kept in step")

func check_interface() -> void:
	GameSettings.set_value("ui_scale", 120)
	check(is_equal_approx(get_root().content_scale_factor, 1.2), "UI scale 120%")
	GameSettings.set_value("ui_scale", 100)
	var holder := Control.new()
	get_root().add_child(holder)
	var sized := Label.new()
	sized.add_theme_font_size_override("font_size", 20)
	holder.add_child(sized)
	var plain := Label.new()
	holder.add_child(plain)
	await process_frame
	var base := plain.get_theme_font_size("font_size")
	GameSettings.set_value("large_text", true)
	check(sized.get_theme_font_size("font_size") == roundi(20*GameSettings.LARGE_TEXT_SCALE), "large text scales overrides")
	check(plain.get_theme_font_size("font_size") == roundi(base*GameSettings.LARGE_TEXT_SCALE), "large text scales theme sizes")
	var late := Label.new()
	late.add_theme_font_size_override("font_size", 30)
	holder.add_child(late)
	await process_frame
	check(late.get_theme_font_size("font_size") == roundi(30*GameSettings.LARGE_TEXT_SCALE), "labels added later are scaled")
	GameSettings.set_value("large_text", false)
	check(sized.get_theme_font_size("font_size") == 20 and not plain.has_theme_font_size_override("font_size"), "large text off restores sizes")
	# Nameplates hide through render layers (main.gd keeps toggling .visible by distance).
	var stage := Node3D.new()
	get_root().add_child(stage)
	var plate := Label3D.new()
	plate.add_to_group("npc_nameplates")
	stage.add_child(plate)
	GameSettings.set_value("nameplates", false)
	check(plate.layers == 0, "nameplate hidden")
	var later := Label3D.new()
	later.name = "NamePlate"
	stage.add_child(later)
	await process_frame
	check(later.layers == 0, "room NamePlate added later hidden")
	GameSettings.set_value("nameplates", true)
	check(plate.layers == 1 and later.layers == 1, "nameplates back")
	holder.queue_free()
	stage.queue_free()
	await process_frame

func check_hooks() -> void:
	check(is_equal_approx(GameSettings.typing_seconds(10), 0.28), "normal typing 0.028 s/char")
	GameSettings.set_value("text_speed", "instant")
	check(GameSettings.typing_seconds(40) == 0.0, "instant typing")
	GameSettings.set_value("text_speed", "slow")
	check(GameSettings.typing_seconds(40) > 1.6, "slow typing is longer")
	GameSettings.set_value("text_speed", "normal")
	check(GameSettings.zoom_step(MOUSE_BUTTON_WHEEL_UP) == -1.0 and GameSettings.zoom_step(MOUSE_BUTTON_WHEEL_DOWN) == 1.0, "wheel zoom default")
	GameSettings.set_value("zoom_invert", true)
	GameSettings.set_value("zoom_speed", 150)
	check(GameSettings.zoom_step(MOUSE_BUTTON_WHEEL_UP) == 1.5, "wheel inverted and faster")
	GameSettings.commit(GameSettings.defaults_for("controls"))
	TranslationServer.set_locale("ko")
	check(GameSettings.format_clock(13, 5) == "오후 1:05" and GameSettings.format_clock(0, 30) == "오전 12:30", "12-hour clock")
	GameSettings.set_value("clock_24h", true)
	check(GameSettings.format_clock(13, 5) == "13:05", "24-hour clock")
	GameSettings.set_value("clock_24h", false)
	check(GameSettings.particle_scale() == 1.0 and GameSettings.shake_scale() == 1.0 and GameSettings.flashes_allowed(), "full motion by default")
	GameSettings.set_value("reduce_shake", true)
	check(GameSettings.shake_scale() < 0.5 and not GameSettings.flashes_allowed(), "reduced shake")
	GameSettings.set_value("reduced_motion", true)
	check(GameSettings.particle_scale() < 0.5 and GameSettings.shake_scale() == 0.0, "reduced motion")
	GameSettings.commit({"reduce_shake": false, "reduced_motion": false})
	# Night grade switch reaches Daylight.apply.
	var env := Environment.new()
	var night := Daylight.sample(1.0)
	Daylight.apply(night, env, null)
	check(env.adjustment_enabled, "night grade on at 1 am")
	GameSettings.set_value("night_grade", false)
	var plain := Environment.new()
	Daylight.apply(night, plain, null)
	check(plain.adjustment_color_correction == null, "night grade off")
	GameSettings.set_value("night_grade", true)
	check(is_equal_approx(GameSettings.lod_multiplier(), 1.0), "medium view detail multiplier 1")

func check_menus() -> void:
	var holder := Control.new()
	holder.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	get_root().add_child(holder)
	var closed := [false]
	var menu = SettingsMenu.open(holder, func(): closed[0] = true)
	await process_frame
	for entry in SettingsMenu.TABS:
		menu.show_tab(entry[0])
		check(menu.rows.get_child_count() > 2, "tab %s has rows" % entry[0])
	menu.show_tab("audio")
	menu.set_draft("music", 30)
	check(absf(bus_db("Music")-GameSettings.volume_db(30)) < 0.01, "menu previews volume live")
	check(menu.dirty(), "menu draft dirty")
	menu.show_tab("controls")
	menu.start_capture("craft", 0)
	menu.finish_capture(KEY_J)
	check(menu.draft_bindings.craft[0] == KEY_J and GameSettings.binding("craft")[0] == KEY_C, "capture edits the draft only")
	menu.apply()
	check(GameSettings.get_value("music") == 30 and GameSettings.binding("craft")[0] == KEY_J, "apply commits")
	menu.reset_tab()
	menu.apply()
	check(GameSettings.binding("craft")[0] == KEY_C, "controls tab defaults")
	menu.show_tab("audio")
	menu.set_draft("music", 55)
	menu.close()
	await process_frame
	check(closed[0], "close callback")
	check(GameSettings.get_value("music") == 30 and absf(bus_db("Music")-GameSettings.volume_db(30)) < 0.01, "closing without apply restores")
	GameSettings.commit(GameSettings.defaults_for("audio"))
	# Pause menu: solo survival reuses app.paused; closing resumes.
	var app := FakeApp.new()
	get_root().add_child(app)
	var pause := PauseMenu.open(app)
	await process_frame
	check(PauseMenu.is_open() and app.paused and app.pending_action == "", "pause menu pauses solo survival")
	pause.show_controls()
	pause.show_settings()
	await process_frame
	check(is_instance_valid(pause.sub), "settings opens from pause")
	pause.sub.close()
	await process_frame
	check(pause.view == "main", "settings returns to the pause page")
	PauseMenu.close()
	await process_frame
	check(not PauseMenu.is_open() and not app.paused, "closing resumes")
	app.screen = "village"
	app.paused = false
	PauseMenu.open(app)
	await process_frame
	check(PauseMenu.is_open() and not app.paused, "village pause does not touch app.paused")
	app.screen = "survival"
	await process_frame
	await process_frame
	check(not PauseMenu.is_open(), "menu closes when the screen changes")
	var room := FakeRoom.new()
	get_root().add_child(room)
	check(PauseMenu.context_of(room) == "room", "studio context")
	PauseMenu.open(room)
	await process_frame
	PauseMenu.close()
	app.queue_free()
	room.queue_free()
	holder.queue_free()
	await process_frame

# ------------------------------------------------------------------ captures
func captures() -> void:
	var out := "res://../artifacts"
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--artifacts="): out = arg.trim_prefix("--artifacts=")
	var dir := ProjectSettings.globalize_path(out) if out.begins_with("res://") else out
	DirAccess.make_dir_recursive_absolute(dir)
	get_root().size = Vector2i(1280, 800)
	GameSettings.reload_settings()
	GameSettings.apply_all(self)
	var layer := CanvasLayer.new()
	get_root().add_child(layer)
	var ui := Control.new()
	ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	# The shared HUD theme when the UI kit provides one (main.gd applies it to its HUD).
	var kit: GDScript = load("res://scripts/rpg_ui.gd")
	if kit.get_script_method_list().any(func(m): return m.name == "theme"): ui.theme = kit.call("theme")
	else:
		var theme := Theme.new()
		var font := SystemFont.new()
		font.font_names = PackedStringArray(["Malgun Gothic","sans-serif"])
		theme.default_font = font
		ui.theme = theme
	layer.add_child(ui)
	var art := TextureRect.new()
	art.texture = load("res://assets/title_background.jpg")
	art.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	ui.add_child(art)
	var menu = SettingsMenu.open(ui)
	for entry in SettingsMenu.TABS:
		menu.show_tab(entry[0])
		if entry[0] == "controls":
			menu.start_capture("interact", 1)
		await settle()
		await shot(dir, "settings-%s" % entry[0])
	menu.show_tab("controls")
	menu.start_capture("interact", 0)
	menu.finish_capture(KEY_Q)
	await settle()
	await shot(dir, "settings-controls-conflict")
	# Largest interface scale and large text: the panel still fits the screen.
	GameSettings.commit({"ui_scale": 140, "large_text": true})
	menu.show_tab("accessibility")
	await settle()
	await shot(dir, "settings-accessibility-140")
	check(menu.panel.get_global_rect().end.x <= get_root().get_visible_rect().size.x + 1.0, "panel fits at 140%")
	GameSettings.commit({"ui_scale": 100, "large_text": false})
	menu.show_tab("audio")
	menu.set_draft("music", 40)
	menu.request_close()
	await settle()
	await shot(dir, "settings-unsaved")
	menu.close()
	var app := FakeApp.new()
	ui.add_child(app)
	app.ui = ui
	var pause := PauseMenu.open(app)
	await settle()
	await shot(dir, "settings-pause")
	pause.show_controls()
	await settle()
	await shot(dir, "settings-pause-controls")
	PauseMenu.close()
	app.queue_free()
	layer.queue_free()
	# The village's brightness pass over the root viewport's own 3D.
	var stage := Node3D.new()
	get_root().add_child(stage)
	var camera := Camera3D.new()
	camera.position = Vector3(0, 1.5, 5)
	stage.add_child(camera)
	camera.current = true
	var lamp := DirectionalLight3D.new()
	lamp.rotation_degrees = Vector3(-50, 30, 0)
	stage.add_child(lamp)
	for i in 5:
		var box := MeshInstance3D.new()
		box.mesh = BoxMesh.new()
		var paint := StandardMaterial3D.new()
		paint.albedo_color = Color.from_hsv(i/5.0, 0.6, 0.35)
		box.material_override = paint
		box.position = Vector3(i*1.4-2.8, 0.5, 0)
		stage.add_child(box)
	await settle()
	var before := await mean_luma()
	GameSettings.set_value("brightness", 145)
	await settle()
	var after := await mean_luma()
	await shot(dir, "settings-brightness-village")
	print("SETTINGS_BRIGHTNESS before=%.3f after=%.3f" % [before, after])
	check(after > before + 0.03, "brightness pass lifts the 3D picture (%.3f -> %.3f)" % [before, after])
	GameSettings.set_value("brightness", 100)
	stage.queue_free()
	await settle()
	# A public room without a server: its SubViewport, sun and prompts follow the settings.
	Engine.set_meta("studio_session", {"token":"","url":"http://127.0.0.1:9","room":"01_cafe"})
	var room: Control = load("res://scenes/studio.tscn").instantiate()
	get_root().add_child(room)
	for i in 100: await process_frame
	await shot(dir, "settings-room-default")
	GameSettings.commit({"brightness": 145, "nameplates": false, "prompts": false, "shadows": "off"})
	check(not room.sun.shadow_enabled and room.viewport.msaa_3d == get_root().msaa_3d, "room follows shadows/MSAA")
	await settle()
	await shot(dir, "settings-room-tuned")
	PauseMenu.open(room)
	await settle()
	await shot(dir, "settings-room-pause")
	PauseMenu.close()
	room.queue_free()
	await settle()

func mean_luma() -> float:
	await RenderingServer.frame_post_draw
	var image := get_root().get_texture().get_image()
	image.resize(64, 40)
	var total := 0.0
	for y in 40:
		for x in 64: total += image.get_pixel(x, y).get_luminance()
	return total/(64.0*40.0)

func settle() -> void:
	for i in 6: await process_frame

func shot(dir: String, name: String) -> void:
	await RenderingServer.frame_post_draw
	var image := get_root().get_texture().get_image()
	var file := dir.path_join(name + ".png")
	check(image != null and image.save_png(file) == OK, "saved " + file)
	print("SETTINGS_SHOT ", file)
