extends Node
## Engine shutdown hygiene (autoload). It is deleted with the tree when the game quits (window closed,
## 게임 종료, a test's quit()), after every node has left the tree, and then:
## - empties GameSettings' static listener list: a lambda still held there crashed the engine on exit
##   (access violation 0xC0000005), see game_settings.gd listen();
## - lets the audio thread drop the sounds that stopped as their players left the tree. It releases a
##   stopped playback only on its next mix or two; one it still held when the engine shut the audio
##   server down was leaked ("4 ObjectDB instances were leaked", "1 resources still in use at exit":
##   the room's Ogg music, or whatever else was playing at quit).
const SETTINGS := "res://scripts/game_settings.gd"

func _notification(what: int) -> void:
	if what != NOTIFICATION_PREDELETE: return
	if ResourceLoader.has_cached(SETTINGS): load(SETTINGS).listeners.clear()
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
