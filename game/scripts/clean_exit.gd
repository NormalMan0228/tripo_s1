extends Node
## Engine shutdown hygiene (autoload). It is deleted with the tree when the game quits (window closed,
## 게임 종료, a test's quit()), after every node has left the tree, and then:
## - empties GameSettings' static listener list: a lambda still held there crashed the engine on exit
##   (access violation 0xC0000005), see game_settings.gd listen();
## - lets the audio thread drop the sounds that stopped as their players left the tree. It releases a
##   stopped playback only on its next mix or two; one it still held when the engine shut the audio
##   server down was leaked ("4 ObjectDB instances were leaked", "1 resources still in use at exit":
##   the room's Ogg music, or whatever else was playing at quit);
## - drops the take cache of sfx_bank.gd (static, like the listener list) so no sound stream is
##   still held when the engine checks for resources in use at exit;
## - collects the ambience beds world_audio.gd still reads on worker threads (world_audio release()):
##   a threaded load nobody collected is leaked by the engine ("1 ObjectDB instance was leaked").
const SETTINGS := "res://scripts/game_settings.gd"
const SFX_BANK := "res://scripts/sfx_bank.gd"
const WORLD_AUDIO := "res://scripts/world_audio.gd"

func _notification(what: int) -> void:
	_notification_close(what)
	if what != NOTIFICATION_PREDELETE: return
	if ResourceLoader.has_cached(SETTINGS): load(SETTINGS).listeners.clear()
	if ResourceLoader.has_cached(SFX_BANK): load(SFX_BANK).clear()
	if ResourceLoader.has_cached(WORLD_AUDIO): load(WORLD_AUDIO).release()
	let_audio_release()

## Waits until two audio mixes have started after the players stopped: the first drops their
## playbacks, the second starts only once the first has finished. The time since the last mix falls
## back when one starts. About 20 ms with a sound card, up to ~190 ms with the headless dummy driver
## (one mix per 93 ms), never more than a quarter second.
static func let_audio_release() -> void:
	var mixes := 0
	var last := AudioServer.get_time_since_last_mix()
	var deadline := Time.get_ticks_msec() + 250
	while mixes < 2 and Time.get_ticks_msec() < deadline:
		OS.delay_msec(2)
		var since := AudioServer.get_time_since_last_mix()
		if since < last: mixes += 1
		last = since

# ------------------------------------------------------------------ the fade out (item 57)

## The game goes dark before it closes (게임 종료 in the menus, the title's 종료, the window's X),
## like every other scene change. The window's X waits here instead of closing at once: the close
## notice still reaches every node first (friends see this player leave, social.gd / studio.gd),
## then the screen fades and the game quits. Never more than QUIT_WAIT s, whatever the fade does.
const QUIT_FADE := 0.4
const QUIT_WAIT := 0.8
var quitting := false

func _ready() -> void:
	get_tree().set_auto_accept_quit(false)

func _notification_close(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST: fade_and_quit()

## Fades the screen and quits (once). Headless runs and tests quit at once.
func fade_and_quit() -> void:
	if quitting: return
	quitting = true
	var tree := get_tree()
	if DisplayServer.get_name() == "headless":
		tree.quit()
		return
	tree.create_timer(QUIT_WAIT, true, false, true).timeout.connect(tree.quit)
	var veil = load("res://scripts/transition.gd").of(tree)
	if veil != null: await veil.fade_out(QUIT_FADE)
	tree.quit()

## For buttons: the close notice to every node, then the fade (falls back to quitting at once).
static func request_quit(tree: SceneTree) -> void:
	tree.root.propagate_notification(NOTIFICATION_WM_CLOSE_REQUEST)
	var exit := tree.root.get_node_or_null("CleanExit")
	if exit == null: tree.quit()
