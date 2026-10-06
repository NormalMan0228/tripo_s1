extends RefCounted
## Player settings: the single source of truth for graphics, sound, controls,
## gameplay and accessibility. Everything here is static, so any script can
##   const GameSettings = preload("res://scripts/game_settings.gd")
## and read a value (GameSettings.get_value("music"), or a typed helper below).
##
## Storage: the same ConfigFile as I18n (I18n.settings_path(): user://settings.cfg,
## or user://settings_qa.cfg when --qa is on the command line), one section per
## category ([graphics] [audio] [controls] [gameplay] [accessibility] [input]).
## The language stays in [game] language and goes through I18n.set_language().
##
## Change flow: set_value()/commit() validate, save, apply to the engine and then
## call every listen() callback with the changed keys. preview() applies values
## without saving (the settings menu's live sliders); end_preview() puts the saved
## values back. apply_all(tree) applies everything once at startup.
##
## ---------------------------------------------------------------------------
## AUDIO BUSES (res://default_bus_layout.tres). Every AudioStreamPlayer, 2D or 3D
## must set .bus to one of these (use the BUS_* constants); the player keeps its own
## volume_db for the mix and the bus carries the player's volume slider:
##   BUS_MUSIC    &"Music"     background music and stingers            (sound.gd)
##   BUS_SFX      &"SFX"       world and gameplay sounds: footsteps, doors, tools,
##                             furniture, farming, combat hits, monster attacks,
##                             growls and other creature noises
##   BUS_AMBIENCE &"Ambience"  looping beds: birds, insects, coast, wind, rooms
##   BUS_VOICE    &"Voice"     spoken lines and dialogue blips of characters
##   BUS_UI       &"UI"        menu clicks, confirmations, error beeps, toasts
## All five send to Master (master volume, mute all, mute in background).
## ---------------------------------------------------------------------------
##
## Hooks other scripts read (cheap, safe every frame):
##   shadow_quality() "off"/"low"/"high"      lod_multiplier()  prop LOD distance
##   night_grade()     bool                   typing_seconds(chars) dialogue typewriter
##   show_nameplates() / show_prompts()       minimap_rotates() / format_clock(h, m)
##   show_route_guide() route guide trail
##   shake_scale()     0..1 camera shake      particle_scale()  0..1 particle counts
##   flashes_allowed() bool                   reduced_motion()  bool
##   zoom_step(wheel_button) signed zoom      running()         run key held/toggled
##   key_label(action) "E"                    canonical_key(event) rebinding-aware key
##   track_viewport(sub_viewport, container)  track_light(sun)  for scenes that render
##                                            3D in their own SubViewport (studio.gd)
const I18n = preload("res://scripts/i18n.gd")

const BUS_MUSIC := &"Music"
const BUS_SFX := &"SFX"
const BUS_AMBIENCE := &"Ambience"
const BUS_VOICE := &"Voice"
const BUS_UI := &"UI"
const BUSES := [["Master","master"],["Music","music"],["SFX","sfx"],["Ambience","ambience"],["Voice","voice"],["UI","ui"]]

const CATEGORIES := {
	"graphics": ["preset","window_mode","render_scale","vsync","fps_cap","shadows","msaa","view_detail","night_grade","brightness"],
	"audio": ["master","music","sfx","ambience","voice","ui","mute_all","background_mute"],
	"controls": ["zoom_speed","run_mode","zoom_invert"],
	"gameplay": ["language","text_speed","nameplates","prompts","route_guide","minimap_rotate","clock_24h","reduce_shake"],
	"accessibility": ["ui_scale","large_text","reduced_motion"],
}
const DEFAULTS := {
	"preset": "medium", "window_mode": "windowed", "render_scale": 100, "vsync": true, "fps_cap": 0,
	"shadows": "low", "msaa": "2x", "view_detail": "medium", "night_grade": true, "brightness": 100,
	"master": 100, "music": 100, "sfx": 100, "ambience": 100, "voice": 100, "ui": 100,
	"mute_all": false, "background_mute": false,
	"zoom_speed": 100, "run_mode": "hold", "zoom_invert": false,
	"language": "ko", "text_speed": "normal", "nameplates": true, "prompts": true, "route_guide": true,
	"minimap_rotate": false, "clock_24h": false, "reduce_shake": false,
	"ui_scale": 100, "large_text": false, "reduced_motion": false,
}
## Option keys: [value, Korean label] pairs (labels go through tr()).
const CHOICES := {
	"preset": [["high","높음"],["medium","보통"],["low","낮음"],["custom","사용자 지정"]],
	"window_mode": [["windowed","창 모드"],["fullscreen","전체 화면"],["borderless","테두리 없는 전체 화면"]],
	"fps_cap": [[30,"30"],[60,"60"],[120,"120"],[144,"144"],[0,"무제한"]],
	"shadows": [["off","끄기"],["low","낮음"],["high","높음"]],
	"msaa": [["off","끄기"],["2x","2x"],["4x","4x"]],
	"view_detail": [["low","낮음"],["medium","보통"],["high","높음"]],
	"text_speed": [["slow","느리게"],["normal","보통"],["fast","빠르게"],["instant","즉시"]],
	"run_mode": [["hold","누르고 있기"],["toggle","눌러서 전환"]],
	"language": [["ko","한국어"],["en","English"],["zh","中文"]],
}
## Slider keys: [min, max, step], shown as percentages.
const RANGES := {
	"render_scale": [50,100,5], "brightness": [50,150,5],
	"master": [0,100,1], "music": [0,100,1], "sfx": [0,100,1], "ambience": [0,100,1], "voice": [0,100,1], "ui": [0,100,1],
	"zoom_speed": [25,200,5], "ui_scale": [80,140,5],
}
## What each graphics preset sets; touching one of these keys makes the preset "custom".
const PRESETS := {
	"high": {"shadows":"high","msaa":"4x","render_scale":100,"view_detail":"high"},
	"medium": {"shadows":"low","msaa":"2x","render_scale":100,"view_detail":"medium"},
	"low": {"shadows":"off","msaa":"off","render_scale":80,"view_detail":"low"},
}
## Keys whose change is cheap enough to show while a slider moves.
const LIVE_KEYS := ["master","music","sfx","ambience","voice","ui","mute_all","brightness","ui_scale","large_text"]
const LOD_MULTIPLIERS := {"low":0.7,"medium":1.0,"high":1.6}
## Seconds per character of the dialogue typewriter (0 = whole line at once).
const TEXT_SPEEDS := {"slow":0.045,"normal":0.028,"fast":0.014,"instant":0.0}
const LARGE_TEXT_SCALE := 1.18

## Rebindable gameplay actions: [action, Korean label, default keys (primary, secondary)].
## project.godot declares the same actions with these keys (tests/settings_check.gd
## keeps them in step) plus left-stick motion on the four move actions.
const ACTIONS := [
	["move_forward","앞으로 이동",[KEY_W,KEY_UP]],
	["move_back","뒤로 이동",[KEY_S,KEY_DOWN]],
	["move_left","왼쪽으로 이동",[KEY_A,KEY_LEFT]],
	["move_right","오른쪽으로 이동",[KEY_D,KEY_RIGHT]],
	["run","달리기",[KEY_SHIFT,KEY_NONE]],
	["interact","상호작용 · 채집",[KEY_E,KEY_NONE]],
	["attack","공격",[KEY_SPACE,KEY_NONE]],
	["eat","먹기",[KEY_Q,KEY_NONE]],
	["campfire","모닥불 피우기",[KEY_F,KEY_NONE]],
	["heal","붕대 감기",[KEY_H,KEY_NONE]],
	["inventory","가방",[KEY_I,KEY_NONE]],
	["map","지도",[KEY_TAB,KEY_NONE]],
	["storage","보관함",[KEY_B,KEY_NONE]],
	["craft","제작",[KEY_C,KEY_NONE]],
	["wardrobe","옷장",[KEY_O,KEY_NONE]],
	["rotate","가구 돌리기",[KEY_R,KEY_NONE]],
	["toggle_sound","소리 켜기/끄기",[KEY_M,KEY_NONE]],
	["toggle_hud","HUD 접기/펼치기",[KEY_U,KEY_NONE]],
]
## Keys that cannot be bound (Esc opens the pause menu and cancels a rebind; F3/F9 are tools).
const RESERVED_KEYS := [KEY_ESCAPE,KEY_F3,KEY_F9,KEY_ENTER,KEY_KP_ENTER]

const BRIGHTNESS_SHADER := """
shader_type canvas_item;
render_mode unshaded;
uniform sampler2D screen_texture : hint_screen_texture, filter_nearest;
uniform float gamma = 1.0;
void fragment() {
	vec3 c = textureLod(screen_texture, SCREEN_UV, 0.0).rgb;
	COLOR = vec4(pow(max(c, vec3(0.0)), vec3(1.0 / gamma)), 1.0);
}
"""
## Same curve for a SubViewportContainer's own picture (rooms render in a SubViewport).
const CONTAINER_SHADER := """
shader_type canvas_item;
uniform float gamma = 1.0;
void fragment() {
	COLOR.rgb = pow(max(COLOR.rgb, vec3(0.0)), vec3(1.0 / gamma));
}
"""

static var values: Dictionary = {}
static var bindings: Dictionary = {}
static var loaded := false
## Values shown by preview() on top of the saved ones (menu live sliders).
static var previewing: Dictionary = {}
static var listeners: Array[Callable] = []
## physical keycode -> action, rebuilt from the bindings.
static var key_owner: Dictionary = {}
static var default_keys: Dictionary = {}
static var tracked_viewports: Array = []
static var tracked_lights: Array = []
static var runtime: Node
static var focus_lost := false
static var run_latched := false
static var container_material: ShaderMaterial

# ------------------------------------------------------------------ load / save
static func ensure_loaded() -> void:
	if loaded: return
	loaded = true
	values = DEFAULTS.duplicate()
	bindings = default_bindings()
	var config := ConfigFile.new()
	config.load(I18n.settings_path())
	for category in CATEGORIES:
		for key in CATEGORIES[category]:
			if key == "language": continue
			if config.has_section_key(category, key):
				values[key] = _validate(key, config.get_value(category, key))
	values["language"] = I18n.language()
	# Before this file, the title screen kept a single [game] graphics level.
	if not config.has_section_key("graphics", "preset") and config.has_section_key("game", "graphics"):
		var legacy := str(config.get_value("game", "graphics"))
		if PRESETS.has(legacy):
			values.preset = legacy
			values.merge(PRESETS[legacy], true)
	if config.has_section("input"):
		for entry in ACTIONS:
			if config.has_section_key("input", entry[0]):
				var stored = config.get_value("input", entry[0])
				if stored is Array or stored is PackedInt32Array:
					var keys := [int(stored[0]) if stored.size() > 0 else KEY_NONE, int(stored[1]) if stored.size() > 1 else KEY_NONE]
					bindings[entry[0]] = keys
	_rebuild_key_owner()

static func save() -> void:
	ensure_loaded()
	var config := ConfigFile.new()
	config.load(I18n.settings_path())
	for category in CATEGORIES:
		for key in CATEGORIES[category]:
			if key == "language": continue
			config.set_value(category, key, values[key])
	for entry in ACTIONS:
		config.set_value("input", entry[0], bindings[entry[0]])
	# Older builds read [game] graphics; keep it in step with the preset.
	config.set_value("game", "graphics", values.preset if PRESETS.has(values.preset) else "medium")
	config.save(I18n.settings_path())

## Forget the cached values (tests re-read the file after writing it).
static func reload_settings() -> void:
	loaded = false
	previewing.clear()
	ensure_loaded()

static func get_value(key: String) -> Variant:
	ensure_loaded()
	if previewing.has(key): return previewing[key]
	return values.get(key, DEFAULTS.get(key))

static func category_of(key: String) -> String:
	for category in CATEGORIES:
		if key in CATEGORIES[category]: return category
	return ""

static func defaults_for(category: String) -> Dictionary:
	var out := {}
	for key in CATEGORIES.get(category, []):
		if key == "language": continue
		out[key] = DEFAULTS[key]
	return out

static func snapshot() -> Dictionary:
	ensure_loaded()
	return values.duplicate()

## Sets one value, saves and applies it.
static func set_value(key: String, value) -> void:
	commit({key: value})

## Saves and applies several values (and optionally the key bindings) at once.
static func commit(changes: Dictionary, new_bindings: Dictionary = {}) -> void:
	ensure_loaded()
	previewing.clear()
	var changed: Array[String] = []
	var incoming := changes.duplicate()
	if incoming.has("preset") and PRESETS.has(str(incoming.preset)) and str(incoming.preset) != str(values.preset):
		incoming.merge(PRESETS[str(incoming.preset)], true)
	for key in incoming:
		if not DEFAULTS.has(key): continue
		var value = _validate(key, incoming[key])
		if key == "language":
			if value != values.language:
				I18n.set_language(value)
				values.language = value
				changed.append(key)
			continue
		if value != values.get(key):
			values[key] = value
			changed.append(key)
	var preset := derive_preset(values)
	if preset != values.preset:
		values.preset = preset
		if not "preset" in changed: changed.append("preset")
	if not new_bindings.is_empty():
		for entry in ACTIONS:
			if new_bindings.has(entry[0]) and new_bindings[entry[0]] != bindings[entry[0]]:
				bindings[entry[0]] = (new_bindings[entry[0]] as Array).duplicate()
				if not "bindings" in changed: changed.append("bindings")
	save()
	if changed.is_empty(): return
	_apply_changed(changed)
	_notify(changed)

## Shows values without saving them (only LIVE_KEYS are cheap enough).
static func preview(changes: Dictionary) -> void:
	ensure_loaded()
	var touched: Array[String] = []
	for key in changes:
		if not key in LIVE_KEYS: continue
		previewing[key] = _validate(key, changes[key])
		touched.append(key)
	if not touched.is_empty(): _apply_changed(touched)

static func end_preview() -> void:
	if previewing.is_empty(): return
	var touched: Array[String] = []
	for key in previewing: touched.append(str(key))
	previewing.clear()
	_apply_changed(touched)

## callback(keys: Array[String]) after each commit. Callables of freed objects drop out.
static func listen(callback: Callable) -> void:
	if not callback in listeners: listeners.append(callback)

static func unlisten(callback: Callable) -> void:
	listeners.erase(callback)

static func _notify(keys: Array[String]) -> void:
	for callback in listeners.duplicate():
		if callback.is_valid(): callback.call(keys)
		else: listeners.erase(callback)

## The preset whose values the table matches, else "custom".
static func derive_preset(table: Dictionary) -> String:
	for name in ["high","medium","low"]:
		var matches := true
		for key in PRESETS[name]:
			if table.get(key) != PRESETS[name][key]: matches = false
		if matches: return name
	return "custom"

static func _validate(key: String, value) -> Variant:
	var fallback = DEFAULTS.get(key)
	if CHOICES.has(key):
		for choice in CHOICES[key]:
			if typeof(fallback) == TYPE_INT and (value is int or value is float or (value is String and value.is_valid_int())) and int(value) == int(choice[0]): return choice[0]
			if str(choice[0]) == str(value): return choice[0]
		return fallback
	if RANGES.has(key):
		var r: Array = RANGES[key]
		var number := float(value) if (value is int or value is float or (value is String and value.is_valid_float())) else float(fallback)
		return int(clampf(snappedf(number, float(r[2])), float(r[0]), float(r[1])))
	if fallback is bool:
		if value is bool: return value
		if value is String: return value.to_lower() in ["true","1","yes","on"]
		return bool(value)
	return value

# ------------------------------------------------------------------ apply
## Applies every setting to the engine. Call once at startup (and it is safe again).
static func apply_all(tree: SceneTree = null) -> void:
	ensure_loaded()
	if tree == null: tree = Engine.get_main_loop() as SceneTree
	_ensure_runtime(tree)
	apply_graphics(tree)
	apply_audio()
	apply_input()
	apply_interface(tree)
	# The language lives in [game] language and I18n.set_language() can change it without this cache.
	values.language = I18n.language()
	if TranslationServer.get_locale().substr(0,2) != str(values.language): TranslationServer.set_locale(str(values.language))

static func _apply_changed(keys: Array[String]) -> void:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null: return
	var render := false
	var display := false
	for key in keys:
		match key:
			"brightness": _apply_brightness()
			"window_mode", "vsync", "fps_cap": display = true
			"preset", "shadows", "msaa", "render_scale", "view_detail": render = true
			"ui_scale": tree.root.content_scale_factor = float(get_value("ui_scale"))/100.0
			"large_text": if is_instance_valid(runtime): runtime.refresh_text()
			"nameplates": if is_instance_valid(runtime): runtime.refresh_plates()
			"bindings": apply_input()
			"run_mode": run_latched = false
			"night_grade":
				var daylight := tree.current_scene.get_node_or_null("Daylight") if tree.current_scene else null
				if daylight and daylight.has_method("refresh") and daylight.get("environment") != null: daylight.refresh(true)
		if category_of(key) == "audio":
			apply_audio()
	if render: _apply_render(tree)
	if display: _apply_display(tree)

static func apply_graphics(tree: SceneTree) -> void:
	_apply_render(tree)
	_apply_display(tree)
	_apply_brightness()

static func _apply_render(tree: SceneTree) -> void:
	_apply_viewport(tree.root)
	for weak in tracked_viewports.duplicate():
		var vp = weak.get_ref()
		if vp == null: tracked_viewports.erase(weak)
		else: _apply_viewport(vp)
	for weak in tracked_lights.duplicate():
		var light = weak.get_ref()
		if light == null: tracked_lights.erase(weak)
		else: _apply_light(light)

static func _apply_display(tree: SceneTree) -> void:
	Engine.max_fps = int(get_value("fps_cap"))
	if DisplayServer.get_name() == "headless": return
	var vsync := DisplayServer.VSYNC_ENABLED if get_value("vsync") else DisplayServer.VSYNC_DISABLED
	if DisplayServer.window_get_vsync_mode() != vsync: DisplayServer.window_set_vsync_mode(vsync)
	var root := tree.root
	var wanted := window_mode_for(str(get_value("window_mode")))
	if root.mode != wanted and not (wanted == Window.MODE_WINDOWED and root.mode in [Window.MODE_MAXIMIZED, Window.MODE_MINIMIZED]):
		root.mode = wanted

static func window_mode_for(name: String) -> Window.Mode:
	match name:
		"fullscreen": return Window.MODE_EXCLUSIVE_FULLSCREEN
		"borderless": return Window.MODE_FULLSCREEN
	return Window.MODE_WINDOWED

static func _apply_viewport(vp: Viewport) -> void:
	vp.msaa_3d = {"off":Viewport.MSAA_DISABLED,"2x":Viewport.MSAA_2X,"4x":Viewport.MSAA_4X}.get(str(get_value("msaa")), Viewport.MSAA_2X)
	vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_BILINEAR
	vp.scaling_3d_scale = float(get_value("render_scale"))/100.0
	vp.mesh_lod_threshold = 1.0/lod_multiplier()

static func _apply_light(light: DirectionalLight3D) -> void:
	var quality := shadow_quality()
	light.shadow_enabled = quality != "off"
	light.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS if quality == "high" else DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS

## Rooms render 3D in their own SubViewport: register it (and the container that
## shows it, for brightness) so graphics settings reach it too.
static func track_viewport(vp: Viewport, container: CanvasItem = null) -> void:
	ensure_loaded()
	if not tracked_viewports.any(func(w): return w.get_ref() == vp): tracked_viewports.append(weakref(vp))
	_apply_viewport(vp)
	if container:
		if container_material == null:
			var shader := Shader.new()
			shader.code = CONTAINER_SHADER
			container_material = ShaderMaterial.new()
			container_material.shader = shader
		container.material = container_material
		_apply_brightness()

## A scene's own sun (rooms): shadows on/off and split count follow the setting.
## The village sun is fitted by main.gd itself (fit_shadow_to_camera).
static func track_light(light: DirectionalLight3D) -> void:
	ensure_loaded()
	if not tracked_lights.any(func(w): return w.get_ref() == light): tracked_lights.append(weakref(light))
	_apply_light(light)

static func gamma() -> float:
	return pow(2.0, (float(get_value("brightness"))-100.0)/100.0)

static func _apply_brightness() -> void:
	if container_material: container_material.set_shader_parameter("gamma", gamma())
	if is_instance_valid(runtime): runtime.update_brightness()

static func volume_db(percent: float) -> float:
	# Squared taper: half the slider is about -12 dB, which sounds like half as loud.
	var linear := clampf(percent/100.0, 0.0, 1.0)
	return -80.0 if linear <= 0.0 else linear_to_db(linear*linear)

## True while sound is off for the session (--mute in tests) or by the player.
static func muted() -> bool:
	return bool(get_value("mute_all")) or "--mute" in OS.get_cmdline_user_args()

static func apply_audio() -> void:
	for pair in BUSES:
		var index := AudioServer.get_bus_index(pair[0])
		if index < 0: continue
		var level := float(get_value(pair[1]))
		AudioServer.set_bus_volume_db(index, volume_db(level))
		var silent := level <= 0.0
		if pair[0] == "Master": silent = silent or muted() or (bool(get_value("background_mute")) and focus_lost)
		AudioServer.set_bus_mute(index, silent)

static func apply_interface(tree: SceneTree) -> void:
	tree.root.content_scale_factor = float(get_value("ui_scale"))/100.0
	if is_instance_valid(runtime) and runtime.is_inside_tree():
		runtime.refresh_text()
		runtime.refresh_plates()

# ------------------------------------------------------------------ input
static func default_bindings() -> Dictionary:
	var out := {}
	for entry in ACTIONS: out[entry[0]] = (entry[2] as Array).duplicate()
	return out

static func action_label(action: String) -> String:
	for entry in ACTIONS:
		if entry[0] == action: return entry[1]
	return action

static func binding(action: String) -> Array:
	ensure_loaded()
	return bindings.get(action, [KEY_NONE, KEY_NONE])

## Rebinds slot (0 primary, 1 secondary) of action inside a bindings dictionary (the
## menu's draft or the live one). A key used elsewhere is swapped: the other action
## takes this slot's previous key. Returns {"ok", "swapped": action or "", "reason"}.
static func rebind_in(table: Dictionary, action: String, slot: int, key: int) -> Dictionary:
	if key in RESERVED_KEYS: return {"ok":false,"swapped":"","reason":"reserved"}
	if not table.has(action): return {"ok":false,"swapped":"","reason":"unknown"}
	var previous: int = table[action][slot]
	if previous == key: return {"ok":true,"swapped":"","reason":""}
	var swapped := ""
	if key != KEY_NONE:
		for other in table:
			for i in 2:
				if (other != action or i != slot) and int(table[other][i]) == key:
					table[other][i] = previous
					if other != action: swapped = other
	table[action][slot] = key
	return {"ok":true,"swapped":swapped,"reason":""}

static func rebind(action: String, slot: int, key: int) -> Dictionary:
	ensure_loaded()
	var table := bindings.duplicate(true)
	var result := rebind_in(table, action, slot, key)
	if result.ok: commit({}, table)
	return result

static func reset_bindings() -> void:
	commit({}, default_bindings())

static func apply_input() -> void:
	ensure_loaded()
	for entry in ACTIONS:
		var action: String = entry[0]
		if not InputMap.has_action(action): InputMap.add_action(action, 0.25 if action.begins_with("move_") else 0.5)
		for event in InputMap.action_get_events(action):
			if event is InputEventKey: InputMap.action_erase_event(action, event)
		for key in bindings[action]:
			if int(key) == KEY_NONE: continue
			var event := InputEventKey.new()
			event.physical_keycode = int(key)
			InputMap.action_add_event(action, event)
	_rebuild_key_owner()

static func _rebuild_key_owner() -> void:
	key_owner.clear()
	default_keys.clear()
	for entry in ACTIONS:
		for key in entry[2]:
			if int(key) != KEY_NONE: default_keys[int(key)] = entry[0]
		for key in bindings.get(entry[0], []):
			if int(key) != KEY_NONE: key_owner[int(key)] = entry[0]

## The key code main.gd/studio.gd should act on for a key event, honouring rebinding:
## a key bound to an action reports that action's default key (rebinding Interact to
## G makes G report KEY_E), a default key that was moved away reports KEY_NONE, and
## every other key (Esc, Enter, digits, F-keys) reports itself.
static func canonical_key(event: InputEvent) -> int:
	if not event is InputEventKey: return KEY_NONE
	ensure_loaded()
	var key: int = event.physical_keycode if event.physical_keycode != KEY_NONE else event.keycode
	if key_owner.has(key):
		for entry in ACTIONS:
			if entry[0] == key_owner[key]: return int(entry[2][0])
	if default_keys.has(key): return KEY_NONE
	return key

## Short name of the action's primary key for prompts and guides ("E", "Space").
static func key_label(action: String) -> String:
	var keys := binding(action)
	var key: int = keys[0] if int(keys[0]) != KEY_NONE else int(keys[1])
	return key_name(key)

static func key_name(key: int) -> String:
	if key == KEY_NONE: return "—"
	var shown := key
	if DisplayServer.get_name() != "headless":
		var mapped := DisplayServer.keyboard_get_keycode_from_physical(key)
		if mapped != KEY_NONE: shown = mapped
	var text := OS.get_keycode_string(shown)
	return text if not text.is_empty() else OS.get_keycode_string(key)

## The run key, held or latched (run_mode "toggle").
static func running() -> bool:
	if str(get_value("run_mode")) == "toggle": return run_latched
	return Input.is_action_pressed("run")

# ------------------------------------------------------------------ hooks
static func shadow_quality() -> String:
	return str(get_value("shadows"))

static func lod_multiplier() -> float:
	return float(LOD_MULTIPLIERS.get(str(get_value("view_detail")), 1.0))

static func night_grade() -> bool:
	return bool(get_value("night_grade"))

## Duration of the typewriter for a line of chars characters (0 = show at once).
static func typing_seconds(chars: int) -> float:
	var rate: float = TEXT_SPEEDS.get(str(get_value("text_speed")), 0.028)
	if rate <= 0.0: return 0.0
	var scale := rate/0.028
	return clampf(chars*rate, 0.25*scale, 1.6*scale)

static func show_nameplates() -> bool:
	return bool(get_value("nameplates"))

static func show_prompts() -> bool:
	return bool(get_value("prompts"))

## Route guide trail and pillar (guide.gd); the minimap flag shows either way.
static func show_route_guide() -> bool:
	return bool(get_value("route_guide"))

static func minimap_rotates() -> bool:
	return bool(get_value("minimap_rotate"))

static func clock_24h() -> bool:
	return bool(get_value("clock_24h"))

static func format_clock(hour: int, minute: int) -> String:
	if clock_24h(): return "%02d:%02d" % [hour, minute]
	var source := "오전 %d:%02d" if hour < 12 else "오후 %d:%02d"
	return TranslationServer.translate(source) % [12 if hour%12 == 0 else hour%12, minute]

static func reduced_motion() -> bool:
	return bool(get_value("reduced_motion"))

## Multiplier for camera shake / screen kick amplitudes.
static func shake_scale() -> float:
	if reduced_motion(): return 0.0
	return 0.25 if bool(get_value("reduce_shake")) else 1.0

## Multiplier for particle counts (Fx.burst/gust/stream).
static func particle_scale() -> float:
	return 0.35 if reduced_motion() else 1.0

## Full-screen flashes (photo flash, hit flashes).
static func flashes_allowed() -> bool:
	return not reduced_motion() and not bool(get_value("reduce_shake"))

## Signed change of the follow camera's orthographic size for one wheel notch.
static func zoom_step(button_index: int) -> float:
	var direction := -1.0 if button_index == MOUSE_BUTTON_WHEEL_UP else 1.0
	if bool(get_value("zoom_invert")): direction = -direction
	return direction*float(get_value("zoom_speed"))/100.0

static func text_scale() -> float:
	return LARGE_TEXT_SCALE if bool(get_value("large_text")) else 1.0

# ------------------------------------------------------------------ runtime node
static func _ensure_runtime(tree: SceneTree) -> void:
	if is_instance_valid(runtime): return
	runtime = Runtime.new()
	runtime.name = "GameSettingsRuntime"
	if tree.root.is_inside_tree() and not tree.root.is_ancestor_of(runtime):
		tree.root.add_child.call_deferred(runtime)

## Lives under the tree root across scene changes: the brightness pass over the
## village's 3D, focus-out muting, the run toggle, larger text and nameplate hiding.
class Runtime extends CanvasLayer:
	const NAMEPLATE_GROUPS := ["npc_nameplates","place_nameplates"]
	var shade: ColorRect
	var shade_material: ShaderMaterial
	var camera_check := 0.0

	func _init() -> void:
		# Above the 3D picture and below every HUD layer (main.gd's UI is layer 1).
		layer = -1
		process_mode = Node.PROCESS_MODE_ALWAYS
		var shader := Shader.new()
		shader.code = BRIGHTNESS_SHADER
		shade_material = ShaderMaterial.new()
		shade_material.shader = shader
		shade = ColorRect.new()
		shade.name = "Brightness"
		shade.material = shade_material
		shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
		shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		shade.visible = false
		add_child(shade)

	func _ready() -> void:
		get_tree().node_added.connect(_on_node_added)
		update_brightness()
		refresh_text()
		refresh_plates()

	func _exit_tree() -> void:
		if get_tree() and get_tree().node_added.is_connected(_on_node_added): get_tree().node_added.disconnect(_on_node_added)

	func update_brightness() -> void:
		var g: float = _settings().gamma()
		shade_material.set_shader_parameter("gamma", g)
		# Only the root viewport's own 3D needs the pass; rooms use their container.
		var root_3d := is_inside_tree() and get_viewport().get_camera_3d() != null
		shade.visible = absf(g-1.0) > 0.001 and root_3d

	func _process(delta: float) -> void:
		camera_check += delta
		if camera_check > 0.5:
			camera_check = 0.0
			update_brightness()

	func _notification(what: int) -> void:
		var script := _settings()
		if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
			script.focus_lost = true
			script.apply_audio()
		elif what == NOTIFICATION_APPLICATION_FOCUS_IN:
			script.focus_lost = false
			script.apply_audio()

	func _input(event: InputEvent) -> void:
		var script := _settings()
		if str(script.get_value("run_mode")) != "toggle": return
		if event is InputEventKey and event.pressed and not event.echo and event.is_action("run"):
			var focus := get_viewport().gui_get_focus_owner()
			if focus is LineEdit or focus is TextEdit: return
			script.run_latched = not script.run_latched

	func _settings() -> GDScript:
		return load("res://scripts/game_settings.gd")

	# Larger text: every Control's font sizes scale by LARGE_TEXT_SCALE; the original
	# sizes are kept in a meta so turning it off restores them exactly.
	func refresh_text() -> void:
		if not is_inside_tree(): return
		for node in get_tree().root.find_children("*", "Control", true, false): _scale_text(node)

	func refresh_plates() -> void:
		if not is_inside_tree(): return
		for group in NAMEPLATE_GROUPS:
			for node in get_tree().get_nodes_in_group(group): _plate(node)
		for node in get_tree().root.find_children("NamePlate", "Label3D", true, false): _plate(node)

	func _on_node_added(node: Node) -> void:
		if node is Control:
			if node.has_meta("settings_font") or _settings().text_scale() != 1.0: _scale_text.call_deferred(node)
		elif node is Label3D and not _settings().show_nameplates(): _plate.call_deferred(node)

	func _plate(node) -> void:
		if not is_instance_valid(node) or not node is Label3D: return
		if not (node.name == "NamePlate" or NAMEPLATE_GROUPS.any(func(g): return node.is_in_group(g))): return
		var shown: bool = _settings().show_nameplates()
		if not node.has_meta("settings_layers"): node.set_meta("settings_layers", node.layers)
		# Hidden through the render layers, so scripts that toggle .visible by
		# distance keep working and the label simply stays unseen.
		node.layers = int(node.get_meta("settings_layers")) if shown else 0

	func _scale_text(node) -> void:
		if not is_instance_valid(node) or not node is Control or not node.is_inside_tree(): return
		var factor: float = _settings().text_scale()
		var names := ["normal_font_size","bold_font_size","italics_font_size","bold_italics_font_size","mono_font_size"] if node is RichTextLabel else ["font_size"]
		var original: Dictionary = node.get_meta("settings_font", {})
		if factor == 1.0 and original.is_empty(): return
		for item in names:
			if not original.has(item):
				if not node.has_theme_font_size(item): continue
				original[item] = node.get_theme_font_size(item) if node.has_theme_font_size_override(item) else -node.get_theme_font_size(item)
			var base: int = absi(int(original[item]))
			if factor == 1.0:
				if int(original[item]) > 0: node.add_theme_font_size_override(item, base)
				else: node.remove_theme_font_size_override(item)
			else:
				node.add_theme_font_size_override(item, roundi(base*factor))
		if factor == 1.0: node.remove_meta("settings_font")
		else: node.set_meta("settings_font", original)
