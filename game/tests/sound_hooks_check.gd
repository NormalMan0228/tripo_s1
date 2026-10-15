extends SceneTree
## The sound hooks other sessions build on, headless, after the import:
##   godot --headless --path game --script res://tests/sound_hooks_check.gd
## 1. world_audio.gd `stepped`: footstep, remote_step, land and splash each emit one info with the
##    surface the sound used (unknown surfaces as grass), its SURFACE_FX, who, kind, gait and where;
##    a remote walker past REMOTE_AUDIBLE m emits nothing; SURFACE_FX covers every surface.
## 2. door_audio.gd: every kind finds a take (the room's own open/close, the new doors/locked and
##    doors/swing families); play() is flat without a position and positional with one, silent
##    past AUDIBLE m, once per GAP_MS at the same door; unknown kinds and hosts outside the tree
##    play nothing; door_close() lands its close after `seconds`.
## Prints RESULT PASS|FAIL; exit code 1 on failure.
const SfxBank = preload("res://scripts/sfx_bank.gd")
const WorldAudio = preload("res://scripts/world_audio.gd")
const DoorAudio = preload("res://scripts/door_audio.gd")

var failures := 0
var lines := PackedStringArray()
var heard: Array = []

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, what: String) -> void:
	if ok: return
	failures += 1
	lines.append("FAIL " + what)

func run() -> void:
	var started := Time.get_ticks_msec()
	SfxBank.clear()
	SfxBank.set_seed(99)
	var stage := Node3D.new()
	root.add_child(stage)
	var camera := Camera3D.new()
	stage.add_child(camera)
	camera.current = true
	await check_steps(stage)
	await check_doors(stage)
	stop_all(stage)
	stage.free()
	SfxBank.clear()
	lines.append("RESULT %s (%d problems, %.1f s)" % ["PASS" if failures == 0 else "FAIL", failures, (Time.get_ticks_msec() - started) * 0.001])
	print("\n".join(lines))
	quit(1 if failures > 0 else 0)

func check_steps(stage: Node3D) -> void:
	for surface in WorldAudio.SURFACES:
		check(WorldAudio.SURFACE_FX.has(surface), "SURFACE_FX has no entry for " + surface)
	var audio: Node = WorldAudio.new()
	stage.add_child(audio)
	audio.setup()
	audio.stepped.connect(func(info: Dictionary): heard.append(info))
	audio.footstep("snow", 3.0)
	check(heard.size() == 1, "footstep emitted %d infos" % heard.size())
	if heard.size() == 1:
		var info: Dictionary = heard[0]
		check(info.kind == "step" and info.who == "hero" and info.surface == "snow" and info.fx == "snow", "hero step info %s" % info)
		check(info.gait == "walk" and int(info.foot) in [0, 1], "hero gait/foot %s" % info)
	heard.clear()
	audio.footstep("lava", 4.8)
	check(heard.size() == 1 and heard[0].surface == "grass" and heard[0].fx == "grass" and heard[0].gait == "run", "unknown surface plays as grass %s" % [heard])
	heard.clear()
	audio.remote_step(Vector3(3, 0, 0), "shallow", 2.0)
	check(heard.size() == 1 and heard[0].who == "remote" and heard[0].fx == "splash" and heard[0].at == Vector3(3, 0, 0), "remote step info %s" % [heard])
	heard.clear()
	audio.remote_step(Vector3(WorldAudio.REMOTE_AUDIBLE + 10.0, 0, 0), "sand", 2.0)
	check(heard.is_empty(), "a far remote walker emitted %s" % [heard])
	audio.land(7.0, "sand")
	check(heard.size() == 1 and heard[0].kind == "land" and heard[0].fx == "dust", "land info %s" % [heard])
	heard.clear()
	audio.splash(1.0)
	check(heard.size() == 1 and heard[0].kind == "splash" and heard[0].surface == "shallow" and is_equal_approx(float(heard[0].size), 1.0), "splash info %s" % [heard])
	heard.clear()
	audio.stride("walker", Vector3.ZERO, 0.1, "leaves")
	for i in 12: audio.stride("walker", Vector3(0.2 * (i + 1), 0, 0), 0.1, "leaves")
	check(not heard.is_empty() and heard.all(func(info): return info.fx == "leaves" and info.who == "remote"), "stride steps %s" % [heard])
	await process_frame
	stop_all(audio)
	audio.free()

func check_doors(stage: Node3D) -> void:
	for kind in DoorAudio.KINDS:
		check(DoorAudio.stream(kind, "home") != null, "no take for door kind " + kind)
	check(SfxBank.count("doors/locked") >= 4 and SfxBank.count("doors/swing") >= 4, "door extras not imported (%d locked, %d swing)" % [SfxBank.count("doors/locked"), SfxBank.count("doors/swing")])
	check(DoorAudio.stream("open", "") != null and DoorAudio.stream("close", "no_such_room") != null, "generic door fallback")
	check(not DoorAudio.play(stage, "bang", "home"), "unknown kind played")
	var loose := Node3D.new()
	check(not DoorAudio.play(loose, "open", "home"), "a host outside the tree played")
	loose.free()
	check(DoorAudio.play(stage, "open", "home"), "flat open did not play")
	check(not DoorAudio.play(stage, "open", "home"), "the same door played twice within GAP_MS")
	var pool := stage.get_node_or_null(DoorAudio.POOL)
	check(pool != null and pool.get_child_count() == DoorAudio.VOICES * 2, "voice pool")
	check(playing(pool, false) == 1 and playing(pool, true) == 0, "flat open is not on a flat voice")
	check(DoorAudio.play(stage, "knock", "01_cafe", Vector3(4, 0, 0)), "positional knock did not play")
	check(playing(pool, true) == 1, "positional knock is not on a 3D voice")
	check(not DoorAudio.play(stage, "locked", "home", Vector3(DoorAudio.AUDIBLE + 5.0, 0, 0)), "a far door played")
	check(DoorAudio.play(stage, "locked", "home", Vector3(0, 0, 6)), "locked did not play")
	check(DoorAudio.door_open(stage, "13_shop", Vector3(2, 0, 2), 1.2), "door_open did not play")
	var before := playing(pool, true)
	check(DoorAudio.door_close(stage, "13_shop", Vector3(-2, 0, 2), 0.3), "door_close did not schedule")
	await create_timer(0.45).timeout
	check(playing(pool, true) >= mini(before + 1, DoorAudio.VOICES), "door_close never landed its close (%d -> %d)" % [before, playing(pool, true)])

func playing(pool: Node, positional: bool) -> int:
	var count := 0
	if pool == null: return 0
	for child in pool.get_children():
		if (child is AudioStreamPlayer3D) == positional and child.get("playing"): count += 1
	return count

## Headless playback never finishes (dummy driver): release every stream before quitting.
func stop_all(node: Node) -> void:
	for child in node.find_children("*", "", true, false):
		if child is AudioStreamPlayer or child is AudioStreamPlayer3D:
			child.stop()
			child.stream = null
