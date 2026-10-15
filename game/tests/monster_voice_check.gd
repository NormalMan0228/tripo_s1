extends SceneTree
## Own monster voices (tools/sfx/gen_monsters.py) and their runtime wiring (headless):
##   godot --headless --path game --script res://tests/monster_voice_check.gd
## 1. Every staged species of server/catalog.py ENEMIES (read from the file, so a new species
##    fails here until it has sounds) has >= TAKES takes of each event, a boss (tier "boss") also
##    >= ROARS roars and >= INTROS intros; every take loads as an AudioStreamWAV.
## 2. Resolution: creature_audio.gd voice_name() picks the species' own family for every event
##    (charge / dazed through their FALLBACK events, roar / intro of a non-boss through alert), the
##    stand-in for a species without takes, the old aliases and "wolf" for unknown names; an own
##    pool holds only that species' takes (no region takes); size_pitch() lowers a stand-in for a
##    bigger species within SIZE_PITCH and leaves own voices alone.
## 3. Playback: an own voice plays its take with no region layer; a species without takes plays
##    the stand-in with its region layer; limits key on the resolved name.
## 4. shadow_beast.gd: a boss announces itself with its intro (flat, the 2D pool), roars on every
##    third wind-up and once as its health falls past half; a non-boss calls its own alert.
## Prints RESULT PASS|FAIL; exit code 1 on failure.
const CreatureAudio := preload("res://scripts/creature_audio.gd")
const SfxBank := preload("res://scripts/sfx_bank.gd")
const Beast := preload("res://scripts/shadow_beast.gd")
const EVENTS := ["idle", "alert", "windup", "strike", "hurt", "death"]
const TAKES := 4
const ROARS := 4
const INTROS := 3

var failures := 0
var lines := PackedStringArray()

func _initialize() -> void: call_deferred("run")

func check(ok: bool, what: String) -> void:
	if ok: return
	failures += 1
	lines.append("FAIL "+what)

func run() -> void:
	var started := Time.get_ticks_msec()
	var species := read_catalog()
	check(species.size() >= 29, "server/catalog.py: %d staged species found (want >= 29)" % species.size())
	check_takes(species)
	check_resolution(species)
	await check_playback()
	await check_beast()
	CreatureAudio.stop_all()
	SfxBank.clear()
	lines.append("RESULT %s (%d problems, %.1f s)" % ["PASS" if failures == 0 else "FAIL", failures, (Time.get_ticks_msec()-started)*0.001])
	print("\n".join(lines))
	quit(1 if failures > 0 else 0)

## {species: {"map", "tier", "stand_in"}} for every ENEMIES entry that belongs to a map.
func read_catalog() -> Dictionary:
	var out := {}
	var path := ProjectSettings.globalize_path("res://").path_join("../server/catalog.py")
	var text := FileAccess.get_file_as_string(path)
	check(not text.is_empty(), "cannot read "+path)
	var re := RegEx.new()
	re.compile("'(\\w+)':\\s*\\{'name':'[^']*','map':'(\\w+)','tier':'(\\w+)','stand_in':'(\\w+)'")
	for m in re.search_all(text):
		out[m.get_string(1)] = {"map": m.get_string(2), "tier": m.get_string(3), "stand_in": m.get_string(4)}
	return out

func check_takes(species: Dictionary) -> void:
	var files := 0
	var bosses := 0
	for sp in species:
		var events := EVENTS.duplicate()
		if species[sp].tier == "boss":
			bosses += 1
			events += ["roar", "intro"]
		for event in events:
			var base := "creatures/%s_%s" % [sp, event]
			var want: int = ROARS if event == "roar" else INTROS if event == "intro" else TAKES
			var paths := SfxBank.paths(base)
			check(paths.size() >= want, "%s has %d takes (want >= %d)" % [base, paths.size(), want])
			for path in paths:
				check(load(path) is AudioStreamWAV, path+" does not load as AudioStreamWAV")
				files += 1
	check(bosses == 3, "%d bosses in the catalog (want 3: treant, chimera, dragon)" % bosses)
	SfxBank.clear()
	lines.append("takes      %d species (%d bosses), %d files load" % [species.size(), bosses, files])

func check_resolution(species: Dictionary) -> void:
	for sp in species:
		var stand_in: String = species[sp].stand_in
		for event in EVENTS+CreatureAudio.EXTRA:
			var got := CreatureAudio.voice_name(sp, stand_in, event)
			check(got == sp, "voice_name(%s, %s, %s) = %s (want its own voice)" % [sp, stand_in, event, got])
		for event in EVENTS:
			var pool := CreatureAudio.pool_paths(sp, event, species[sp].map)
			var own := pool.size() > 0
			for path in pool: own = own and path.get_file().begins_with("%s_%s_" % [sp, event])
			check(own, "%s/%s pool is not only its own takes: %s" % [sp, event, pool])
		check(CreatureAudio.size_pitch(sp, 5.0) == 1.0, "%s: an own voice must not be pitched by size" % sp)
		if species[sp].tier != "boss":
			check(CreatureAudio.pool_paths(sp, "roar", "forest") == CreatureAudio.pool_paths(sp, "alert", "forest"), "%s roar falls back to its alert" % sp)
	check(CreatureAudio.pool_paths("centipede", "charge", "forest") == CreatureAudio.pool_paths("centipede", "windup", "forest"), "centipede charge = its own windup")
	check(CreatureAudio.pool_paths("mimic", "dazed", "quarry") == CreatureAudio.pool_paths("mimic", "hurt", "quarry"), "mimic dazed = its own hurt")
	# No takes: the stand-in, exactly as before (its region pool).
	check(CreatureAudio.voice_name("no_such_species", "brute", "idle") == "brute", "a species without takes uses its stand-in")
	check(CreatureAudio.voice_name("no_such_species", "", "idle") == "wolf", "an unknown species without stand-in is a wolf")
	check(CreatureAudio.voice_name("golem", "", "strike") == "brute" and CreatureAudio.voice_name("wolf", "", "idle") == "wolf", "aliases and base species")
	check(CreatureAudio.voice_name("boar", "boar", "charge") == "boar", "the boar keeps its charge")
	check(CreatureAudio.pool_paths("brute", "idle", "frost").size() >= 8, "stand-in pool keeps its region takes")
	var low := CreatureAudio.size_pitch("brute", 5.0)
	check(is_equal_approx(low, 1.0-CreatureAudio.SIZE_PITCH), "a 5 m species on the brute is pitched %.3f (want %.3f)" % [low, 1.0-CreatureAudio.SIZE_PITCH])
	check(CreatureAudio.size_pitch("brute", 2.8) < 1.0 and CreatureAudio.size_pitch("wolf", 1.0) > 1.0 and CreatureAudio.size_pitch("wolf", 0.0) == 1.0, "size pitch direction")
	lines.append("resolve    %d species x %d events resolve to their own voices" % [species.size(), (EVENTS+CreatureAudio.EXTRA).size()])

func make_app() -> Node3D:
	var script := GDScript.new()
	script.source_code = "extends Node3D\nvar player: Node3D\nvar run := {\"map_id\": \"quarry\"}\n"
	script.reload()
	var app: Node3D = script.new()
	root.add_child(app)
	var hero := Node3D.new()
	app.add_child(hero)
	app.player = hero
	return app

func layers_playing() -> int:
	return CreatureAudio.active("layer/")

func check_playback() -> void:
	var app := make_app()
	await process_frame
	CreatureAudio.stop_all()
	CreatureAudio.last_key.clear()
	check(CreatureAudio.play(app, "troll", "strike", Vector3(2, 0, 0), "forest", "brute", 2.8), "troll strike did not play")
	var take: String = CreatureAudio.last_take.get("troll_strike_forest", "")
	check(take.get_file().begins_with("troll_strike_"), "troll strike played %s" % take)
	await process_frame
	check(CreatureAudio.active("creature/troll/") == 1, "troll voice not tagged by its own name")
	check(layers_playing() == 0, "an own voice got a region layer")
	CreatureAudio.stop_all()
	var layered := 0
	for i in 12:
		CreatureAudio.last_key.clear()
		check(CreatureAudio.play(app, "no_such_species", "death", Vector3(-2, 0, 0), "quarry", "boar", 1.4), "stand-in death did not play")
		await process_frame
		layered += layers_playing()
		CreatureAudio.stop_all()
	var stand: String = CreatureAudio.last_take.get("boar_death_quarry", "")
	check(stand.get_file().begins_with("boar_death_"), "stand-in played %s" % stand)
	check(layered > 0, "the stand-in never got its region layer")
	# Limits key on the resolved name: three troll calls fill the troll, the brute is untouched.
	for event in ["alert", "strike", "death"]:
		CreatureAudio.last_key.clear()
		CreatureAudio.play(app, "troll", event, Vector3(1, 0, 1), "forest", "brute")
	CreatureAudio.last_key.clear()
	check(not CreatureAudio.play(app, "troll", "idle", Vector3(1, 0, 1), "forest", "brute"), "a fourth (idle) troll voice got through")
	check(CreatureAudio.play(app, "brute", "idle", Vector3(1, 0, 1), "forest"), "the brute was limited by the troll's voices")
	await process_frame
	check(CreatureAudio.active("creature/troll/") <= CreatureAudio.MAX_PER_SPECIES, "troll over its voice limit")
	lines.append("playback   own voice without layer, stand-in with layer (%d layers in 12 deaths), limits per name" % layered)
	CreatureAudio.stop_all()
	app.queue_free()
	await process_frame

func flat_playing(tag: String) -> bool:
	for entry in CreatureAudio.pool2d:
		if entry.node.playing and entry.tag == tag: return true
	return false

func check_beast() -> void:
	var app := make_app()
	var camera := Camera3D.new()
	app.add_child(camera)
	camera.current = true
	await process_frame
	CreatureAudio.stop_all()
	var beast: Node3D = Beast.new()
	beast.variant = "forest"
	beast.from_enemy({"id": "boss3", "kind": "brute", "species": "treant", "stand_in": "brute", "boss": true, "height": 5.0, "variant": "forest"})
	app.add_child(beast)
	beast.set_process(false)
	await process_frame
	var state := {"x": 3.0, "z": 0.0, "phase": "chase", "hp": 480.0, "max_hp": 480.0}
	beast.update_snapshot(state, Vector3.ZERO)
	await process_frame
	check(CreatureAudio.last_take.get("treant_intro_forest", "").get_file().begins_with("treant_intro_"), "the boss did not play its intro")
	check(flat_playing("creature/treant/intro"), "the intro is not flat (2D pool)")
	var calls := []
	for i in 3:
		CreatureAudio.stop_all()
		CreatureAudio.last_key.clear()
		beast.voice_at.clear()
		var before: String = CreatureAudio.last_take.get("treant_roar_forest", "")
		beast.update_snapshot(state.merged({"phase": "windup"}, true), Vector3.ZERO)
		calls.append("roar" if CreatureAudio.last_take.get("treant_roar_forest", "") != before else "windup")
		beast.update_snapshot(state.merged({"phase": "recover"}, true), Vector3.ZERO)
		beast.update_snapshot(state, Vector3.ZERO)
	check(calls == ["windup", "windup", "roar"], "boss wind-up calls %s (want windup, windup, roar)" % [calls])
	CreatureAudio.stop_all()
	CreatureAudio.last_key.clear()
	beast.voice_at.clear()
	var roars: String = CreatureAudio.last_take.get("treant_roar_forest", "")
	beast.update_snapshot(state.merged({"hp": 230.0}, true), Vector3.ZERO)
	check(CreatureAudio.last_take.get("treant_roar_forest", "") != roars, "no roar as the boss fell past half health")
	beast.voice_at.clear()
	CreatureAudio.last_key.clear()
	roars = CreatureAudio.last_take.get("treant_roar_forest", "")
	beast.update_snapshot(state.merged({"hp": 200.0}, true), Vector3.ZERO)
	check(CreatureAudio.last_take.get("treant_roar_forest", "") == roars, "the half-health roar repeated")
	beast.queue_free()
	# A staged non-boss announces itself with its own alert.
	CreatureAudio.stop_all()
	CreatureAudio.last_key.clear()
	CreatureAudio.alert_start = -10.0
	var goblin: Node3D = Beast.new()
	goblin.variant = "forest"
	goblin.from_enemy({"id": "e1_0", "kind": "wolf", "species": "goblin", "stand_in": "wolf", "variant": "forest"})
	app.add_child(goblin)
	goblin.set_process(false)
	await process_frame
	goblin.update_snapshot({"x": 2.0, "z": 1.0, "phase": "chase", "hp": 40.0, "max_hp": 40.0}, Vector3.ZERO)
	check(CreatureAudio.last_take.get("goblin_alert_forest", "").get_file().begins_with("goblin_alert_"), "the goblin did not call its own alert")
	lines.append("beast      boss intro flat, wind-ups %s, half-health roar once; goblin calls its own alert" % [calls])
	goblin.queue_free()
	CreatureAudio.stop_all()
	app.queue_free()
	await process_frame
	await process_frame
