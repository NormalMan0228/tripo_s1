extends Node
## The first node of main.tscn. The game's main script (main.gd) and everything it preloads took
## seconds to load before anything was drawn: the window stayed black. At the game's start this node
## draws the loading card first, reads main.gd on a worker thread while the card turns, then opens
## main.tscn again: with main.gd now in memory, this node hands its parent (the scene's root) the main
## script right away and goes, and the root runs main.gd's _ready as the game always did.
## Coming back from a room, after a logout, in tests and headless runs main.gd is already in memory
## (or there is no window to draw on): the root gets it at once, as before.
## (The main scene and the autoloads in project.godot stay as they are: a patch cannot change them.)
const MAIN := "res://scripts/main.gd"
const SCENE := "res://scenes/main.tscn"
const Transition = preload("res://scripts/transition.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const I18n = preload("res://scripts/i18n.gd")
## The main script read on the worker thread, held until main.tscn opens again.
static var loaded: Script
static var started := 0

func _enter_tree() -> void:
	var host := get_parent()
	if host.get_script() != null: return
	if ResourceLoader.has_cached(MAIN) or Engine.has_meta("studio_session") or DisplayServer.get_name() == "headless":
		# The root becomes the game; its _ready (main.gd's) comes after this node's.
		host.set_script(load(MAIN))
		loaded = null
		queue_free()
		return
	set_process(false)

func _ready() -> void:
	if is_queued_for_deletion(): return
	if "--log-load" in OS.get_cmdline_user_args(): print("BOOT first node ready %d ms after the engine started" % Time.get_ticks_msec())
	# Window mode, language and UI scale before the first frame, so the card is drawn as the game will be.
	I18n.setup()
	GameSettings.apply_all(get_tree())
	var veil := Transition.of(get_tree())
	veil.loading("", "start")
	veil.cover()
	started = Time.get_ticks_msec()
	if "--log-load" in OS.get_cmdline_user_args(): print("BOOT card dressed %d ms after the engine started" % started)
	if ResourceLoader.load_threaded_request(MAIN, "", false) != OK:
		_open(load(MAIN))
		return
	set_process(true)

func _process(_delta: float) -> void:
	if ResourceLoader.load_threaded_get_status(MAIN) == ResourceLoader.THREAD_LOAD_IN_PROGRESS: return
	set_process(false)
	var script := ResourceLoader.load_threaded_get(MAIN) as Script
	if "--log-load" in OS.get_cmdline_user_args(): print("BOOT main.gd read in %d ms (from %d ms)" % [Time.get_ticks_msec()-started, started])
	_open(script if script != null else load(MAIN))

func _open(script: Script) -> void:
	loaded = script
	get_tree().change_scene_to_file(SCENE)
