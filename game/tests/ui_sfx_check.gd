extends SceneTree
## UI take families (tools/sfx/gen_ui.py -> assets/sfx/ui), checked after the import:
##   godot --headless --path game --script res://tests/ui_sfx_check.gd
## 1. Every kind RpgUi.sfx() plays has all its takes: the bare original (the six first kinds) plus
##    <kind>_1 .. <kind>_N, contiguous, nothing past N.
## 2. Each take loads as an AudioStream and stays short (UI sounds: at most 1.5 s).
## 3. The shuffle bag never plays one take twice in a row on a real family.
## 4. RpgUi.sfx() stays harmless headless: any kind (known, unknown, empty) returns at once, no
##    player host is made and the play counter does not move.
## Prints RESULT PASS|FAIL; exit code 1 on failure.
const SfxBank = preload("res://scripts/sfx_bank.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const ROOT := "res://assets/sfx/ui/"
## kind: [has a bare original ui/<kind>.wav, numbered takes] (gen_ui.py FAMILIES)
const KINDS := {"hover": [true, 14], "click": [true, 12], "open": [true, 8], "close": [true, 8],
	"toast": [true, 10], "confirm": [true, 8], "deny": [false, 8], "tab": [false, 8], "select": [false, 8],
	"slider": [false, 12], "drawer_open": [false, 6], "drawer_close": [false, 6], "count": [false, 10],
	"coin_gain": [false, 6], "chat_in": [false, 8], "chat_out": [false, 6], "whisper": [false, 4],
	"friend": [false, 4], "join": [false, 4], "leave": [false, 4], "notify": [false, 6],
	"toast_success": [false, 6], "toast_warn": [false, 6], "toast_error": [false, 6],
	"toast_social": [false, 6], "quest_accept": [false, 5], "quest_ready": [false, 4],
	"quest_complete": [false, 5], "star": [false, 8], "unlock": [false, 4], "rotate": [false, 12],
	"snap": [false, 10], "place": [false, 8], "lift": [false, 6], "cancel": [false, 6], "valid": [false, 4],
	"invalid": [false, 4], "paint": [false, 8], "brush": [false, 12], "fill": [false, 4], "undo": [false, 6],
	"redo": [false, 6], "layer": [false, 6], "swatch": [false, 6], "key_capture": [false, 4],
	"save": [false, 5], "craft_submit": [false, 4], "craft_step": [false, 6], "craft_done": [false, 4],
	"craft_fail": [false, 4], "page": [false, 8], "choice": [false, 6]}

var failures := 0
var lines := PackedStringArray()

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, what: String) -> void:
	if ok: return
	failures += 1
	lines.append("FAIL "+what)

func run() -> void:
	SfxBank.clear()
	var takes := 0
	for kind in KINDS:
		var spec: Array = KINDS[kind]
		var want := PackedStringArray()
		if spec[0]: want.append(ROOT+kind+".wav")
		for n in range(1, int(spec[1])+1): want.append("%s%s_%d.wav" % [ROOT, kind, n])
		var found := SfxBank.paths("ui/"+kind)
		check(found == want, "ui/%s: %d takes found, %d expected (run the importer?)" % [kind, found.size(), want.size()])
		check(not ResourceLoader.exists("%s%s_%d.wav" % [ROOT, kind, int(spec[1])+1]), "ui/%s: a take past %d" % [kind, int(spec[1])])
		for path in found:
			var stream := SfxBank.stream(path)
			check(stream != null, "%s does not load" % path)
			if stream != null:
				takes += 1
				check(stream.get_length() > 0.02 and stream.get_length() <= 1.5, "%s length %.2f s" % [path, stream.get_length()])
	var last := ""
	var repeats := 0
	for i in 60:
		var path := SfxBank.pick_path("ui/toast_error")
		if path == last: repeats += 1
		last = path
	check(repeats == 0, "ui/toast_error repeated a take back to back %d times" % repeats)
	var before: int = RpgUi._voice
	for kind in ["hover", "toast_error", "__no_such_kind__", ""]: RpgUi.sfx(kind, -6.0)
	check(RpgUi._voice == before, "RpgUi.sfx played headless")
	check(root.get_node_or_null("RpgUiSounds") == null, "RpgUi.sfx made its player host headless")
	SfxBank.clear()
	for line in lines: print(line)
	print("ui takes loaded: %d (%d kinds)" % [takes, KINDS.size()])
	print("RESULT %s" % ("PASS" if failures == 0 else "FAIL"))
	quit(0 if failures == 0 else 1)
