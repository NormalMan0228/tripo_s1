extends SceneTree
## In-engine sound proof: records what the live village really plays, for Godot's Movie Maker
## (the AVI's audio track is the game's final mix). Enters the village offline (the UI gallery
## fixture, as toast_check does) and runs, each part a second apart:
##   a. the hero walks on grass ~5 s (movement keys), then on a stone road, a bridge deck (wood)
##      and a beach (sand), ~3 s each (main.gd's own footstep cadence and ground_surface()); the
##      stretches are searched at run time (clear of props, one surface all along);
##   b. back inland at the grass start: 12 hovers then 8 presses on real HUD buttons (their own
##      mouse_entered / button_down hooks: RpgUi.sfx "hover" / "click");
##   c. 10 fishing reel ticks at fishing.gd's cadence and pitch/level ramp (life.sfx.play("tick"));
##   d. 8 Fx.sound(app, "thud") one-shots (Fx.arrive's level), 0.45 s apart;
##   e. the ambience beds on the coast with a few spots (ambience_spots.fire, when it exists).
## Music is muted on its bus for the take (it would sit under everything); every other bus plays
## at its default level. A monitor watches every AudioStreamPlayer(2D/3D) in the tree and logs each
## playback start: frame, bus, the take (resource path, or "synth:<cache>/<key>" for streams made
## at runtime), pitch and level, plus the segment marks and the prompt chip's changes ("chip": it
## ticks softly as it appears; UI events carry its state). Written as JSON to --events=<file>.
## "frame" counts process frames from the start; in the movie (--fixed-fps 30, 48 kHz) a sound
## logged at frame f starts about f*1600 - 1300 samples in (measured on the clicks).
## --dump=<dir> also saves the runtime-synthesized streams that played (older builds) as WAV.
## Works on builds without the take banks too (missing members are probed with get()).
##   godot --path game --position 2880,314 --write-movie out.avi --fixed-fps 30 \
##         --script res://tests/sound_variety_capture.gd -- --qa --hour=11 --events=<file> [--dump=<dir>]
## Without --write-movie it simply plays the scenario (listen on the speakers).
const Main = preload("res://scripts/main.gd")
const I18n = preload("res://scripts/i18n.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
const Fx = preload("res://scripts/fx.gd")
const WorldAudio = preload("res://scripts/world_audio.gd")
const Roads = preload("res://scripts/roads.gd")
const LAYOUT := "res://maps/archipelago/environment_layout.json"
## Everything the walker collides with (player.gd collision_mask).
const BODY_MASK := 1|2|4|8|16|32

var app: Node3D
var frame := 0
var sim := 0.0
var players: Array = []
var state := {}
var events: Array = []
var marks: Array = []
var synth_names := {}
var dump_dir := ""
var events_path := ""
## The prompt chip (main.hint, RpgUi.prompt) as it changes: it ticks softly (RpgUi.sfx "hover",
## -14 dB) whenever it appears, so a quiet hover nobody scripted is attributed by this log.
var chip_log: Array = []
var chip_state := ""

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--events="): events_path = arg.trim_prefix("--events=")
		if arg.begins_with("--dump="): dump_dir = arg.trim_prefix("--dump=")
	node_added.connect(_on_node_added)
	process_frame.connect(_tick)
	call_deferred("run")
	create_timer(420).timeout.connect(func():
		push_error("sound_variety_capture exceeded 420 s")
		_write()
		quit(2))

func _on_node_added(node: Node) -> void:
	if node is AudioStreamPlayer or node is AudioStreamPlayer2D or node is AudioStreamPlayer3D: players.append(node)

func _tick() -> void:
	frame += 1
	sim += 1.0/30.0
	track_chip()
	poll()

func chip() -> Control:
	if not is_instance_valid(app): return null
	var hint = app.get("hint")
	return hint if hint is Control and is_instance_valid(hint) else null

func track_chip() -> void:
	var hint := chip()
	if hint == null: return
	var shown := hint.is_visible_in_tree()
	var text := str(hint.get_meta("prompt", "")) if shown else ""
	var now := "%s|%s" % [shown, text]
	if now == chip_state: return
	chip_state = now
	chip_log.append({"frame": frame, "t": snappedf(sim, 0.001), "visible": shown, "prompt": text})

## Logs every player that started since the last look (new stream, restarted, or newly playing).
func poll(seg := "") -> void:
	var alive: Array = []
	for p in players:
		if not is_instance_valid(p): continue
		alive.append(p)
		var playing: bool = p.playing
		var stream: AudioStream = p.stream
		var pos: float = p.get_playback_position() if playing else 0.0
		var key: int = p.get_instance_id()
		var before: Dictionary = state.get(key, {"playing": false, "stream": null, "pos": 0.0})
		var started: bool = playing and (not before.playing or stream != before.stream or pos + 0.02 < float(before.pos))
		state[key] = {"playing": playing, "stream": stream, "pos": pos}
		if not started: continue
		var entry := {"frame": frame, "t": snappedf(sim, 0.001), "take": _name(stream), "bus": str(p.bus),
			"node": str(p.get_parent().name) + "/" + str(p.name) if p.get_parent() else str(p.name),
			"pitch": snappedf(p.pitch_scale, 0.0001), "db": snappedf(p.volume_db, 0.01), "pos": snappedf(pos, 0.001)}
		if str(p.bus) == "UI" and chip() != null:
			track_chip()
			entry["chip"] = chip_state
		if not seg.is_empty(): entry["seg"] = seg
		elif str(p.bus) == "UI":
			# A UI sound nobody scripted: what the desktop pointer was over (it rests where it is).
			var over: Control = root.gui_get_hovered_control() if root.has_method("gui_get_hovered_control") else null
			entry["hovered"] = str(over.get_path()) if over != null else ""
			var window := Rect2i(DisplayServer.window_get_position(), DisplayServer.window_get_size())
			entry["pointer_in_window"] = window.has_point(DisplayServer.mouse_get_position())
		events.append(entry)
	players = alive

func _name(stream: AudioStream) -> String:
	if stream == null: return ""
	if not stream.resource_path.is_empty(): return stream.resource_path
	var id := stream.get_instance_id()
	if synth_names.has(id): return synth_names[id]
	var sources := {"world": WorldAudio.cache, "fx": Fx.streams}
	if is_instance_valid(app):
		var life = app.get("life")
		if life != null and life.get("sfx") != null: sources["life"] = life.sfx.get("streams")
		var sound = app.get("sound")
		if sound != null: sources["sound"] = sound.get("effects")
	for src in sources:
		var table = sources[src]
		if not table is Dictionary: continue
		for k in table:
			if table[k] == stream:
				synth_names[id] = "synth:%s/%s" % [src, k]
				if not dump_dir.is_empty() and stream is AudioStreamWAV:
					var file := dump_dir.path_join(("%s_%s.wav" % [src, k]).replace("/", "_"))
					(stream as AudioStreamWAV).save_to_wav(file)
				return synth_names[id]
	synth_names[id] = "synth:?%d" % id
	return synth_names[id]

func mark(name: String) -> void:
	marks.append({"name": name, "frame": frame, "t": snappedf(sim, 0.001)})
	print("MARK %s frame %d t %.2f" % [name, frame, sim])

func wait(seconds: float) -> void:
	await create_timer(seconds).timeout

# ------------------------------------------------------------------ ground search
## The surface main.gd's ground_surface() would give at `at` (top-down, with the body's mask: a
## roof, a trunk or a prop on top makes it "blocked"), and the ground height.
func probe(at: Vector2) -> Dictionary:
	var space: PhysicsDirectSpaceState3D = app.get_world_3d().direct_space_state
	var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(at.x, 60, at.y), Vector3(at.x, -20, at.y), BODY_MASK))
	if hit.is_empty(): return {"surface": "none", "y": 0.0}
	var body = hit.collider
	var y: float = hit.position.y
	if not body is CollisionObject3D: return {"surface": "blocked", "y": y}
	var layer: int = (body as CollisionObject3D).collision_layer
	if layer & 2: return {"surface": "wood", "y": y}
	if layer & 1 == 0: return {"surface": "blocked", "y": y}
	var owner_name := str(body.get_parent().name).to_lower() if body.get_parent() else ""
	if "rock" in owner_name: return {"surface": "rock", "y": y}
	if Roads.on_road(at): return {"surface": "stone", "y": y}
	if y < 0.8: return {"surface": "shallow", "y": y}
	if y < 1.55: return {"surface": "sand", "y": y}
	return {"surface": "grass", "y": y}

## A straight walk of `length` m from `start` along `dir` that stays on `surface` with room for
## the body on both sides and no step taller than 0.3 m.
func clear_line(start: Vector2, dir: Vector2, length: float, surface: String, margin := 0.45) -> bool:
	var side := Vector2(-dir.y, dir.x)
	var last := INF
	var n := int(length / 0.5)
	for i in n + 1:
		var at := start + dir * (0.5 * i)
		var mid := probe(at)
		if mid.surface != surface: return false
		if surface == "sand" and (mid.y < 0.95 or mid.y > 1.45): return false
		if surface == "grass" and mid.y < 1.75: return false
		if last != INF and absf(mid.y - last) > 0.3: return false
		last = mid.y
		for s in [-margin, margin]:
			var edge := probe(at + side * s)
			if edge.surface != surface or absf(edge.y - mid.y) > 0.3: return false
	return true

func find_line(surface: String, length: float, centre: Vector2, radius: float, step := 2.0) -> Dictionary:
	var dirs: Array = []
	for k in 8: dirs.append(Vector2.RIGHT.rotated(TAU * k / 8.0))
	var best := {}
	var best_d := INF
	var r := 0.0
	while r <= radius:
		var ring: Array = [centre] if r == 0.0 else []
		if r > 0.0:
			var count := int(ceil(TAU * r / step))
			for k in count: ring.append(centre + Vector2.RIGHT.rotated(TAU * k / count) * r)
		for start in ring:
			if probe(start).surface != surface: continue
			for dir in dirs:
				if clear_line(start, dir, length, surface):
					var d: float = (start as Vector2).distance_to(centre)
					if d < best_d:
						best_d = d
						best = {"start": start, "dir": dir}
			if not best.is_empty(): return best
		r += step
	return best

## A stretch along a road segment (stone) at least `length` m long, nearest the centre first.
func find_road(length: float, centre: Vector2) -> Dictionary:
	var found: Array = []
	for road in Roads.ROADS:
		var pts: Array = road[2]
		for i in pts.size() - 1:
			var a: Vector2 = pts[i]
			var b: Vector2 = pts[i + 1]
			var span := a.distance_to(b)
			if span < length + 1.0: continue
			var dir := (b - a) / span
			var start := a + dir * 0.5
			if clear_line(start, dir, length, "stone", 0.35): found.append({"start": start, "dir": dir, "d": start.distance_to(centre)})
	found.sort_custom(func(x, y): return x.d < y.d)
	return found[0] if not found.is_empty() else {}

## The middle of a bridge deck (wood): start a quarter in, walk towards the far bank.
func find_bridge(length: float) -> Dictionary:
	var layout = JSON.parse_string(FileAccess.get_file_as_string(LAYOUT))
	if not layout is Dictionary: return {}
	for spec in layout.get("bridges", []):
		var a := Vector2(spec.a[0], spec.a[1])
		var b := Vector2(spec.b[0], spec.b[1])
		var dir := (b - a).normalized()
		var start := a.lerp(b, 0.3)
		if a.distance_to(b) * 0.55 < length: continue
		if clear_line(start, dir, length, "wood", 0.3): return {"start": start, "dir": dir, "bridge": str(spec.id)}
	return {}

func place(at: Vector2) -> void:
	var y: float = probe(at).y
	app.player.global_position = Vector3(at.x, y + 0.15, at.y)
	app.player.velocity = Vector3.ZERO
	for i in 4: await physics_frame
	if app.has_method("follow_camera"): app.follow_camera(1.0)

func release_keys() -> void:
	for action in ["move_left", "move_right", "move_forward", "move_back", "run"]: Input.action_release(action)

## Holds the movement keys along `dir` (world x = right, z = back) for `seconds`.
func walk(dir: Vector2, seconds: float) -> void:
	release_keys()
	if dir.x > 0.01: Input.action_press("move_right", dir.x)
	if dir.x < -0.01: Input.action_press("move_left", -dir.x)
	if dir.y > 0.01: Input.action_press("move_back", dir.y)
	if dir.y < -0.01: Input.action_press("move_forward", -dir.y)
	await wait(seconds)
	release_keys()

func walk_segment(name: String, line: Dictionary, seconds: float) -> void:
	if line.is_empty():
		print("SKIP %s: no clear stretch found" % name)
		return
	await place(line.start)
	await wait(1.0)
	mark(name + "_start")
	await walk(line.dir, seconds)
	await wait(0.6)
	mark(name + "_end")
	print("WALK %s from %s along %s -> %s" % [name, line.start, line.dir, Vector2(app.player.position.x, app.player.position.z)])

# ------------------------------------------------------------------ scenario
func run() -> void:
	I18n.setup()
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	app = Main.new()
	root.add_child(app)
	await wait(1.6)
	app.api.queue_free()
	var stub := Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = false
	await app.enter_village()
	var music := AudioServer.get_bus_index("Music")
	if music >= 0: AudioServer.set_bus_mute(music, true)
	await wait(3.0)
	print("VILLAGE screen=%s at %s" % [app.screen, app.player.position])
	var home := Vector2(app.player.position.x, app.player.position.z)
	var lines := {
		"grass": find_line("grass", 14.5, home, 40.0),
		"stone": find_road(8.5, home),
		"wood": find_bridge(8.5),
		"sand": find_line("sand", 8.5, home, 90.0, 3.0),
	}
	for k in lines: print("LINE %s %s" % [k, lines[k]])
	await wait(1.0)
	mark("begin")
	# a. footsteps
	await walk_segment("a_grass", lines.grass, 5.0)
	await walk_segment("a_stone", lines.stone, 3.0)
	await walk_segment("a_wood", lines.wood, 3.0)
	await walk_segment("a_sand", lines.sand, 3.0)
	# b-d inland, back at the grass walk's start: the surf (and its wave crashes) would sit on top
	# of the quiet seconds the analysis takes the bed from.
	if not lines.grass.is_empty(): await place(lines.grass.start)
	await wait(2.5)
	# b. UI on real HUD buttons
	var hud: Array = app.ui.find_children("*", "BaseButton", true, false).filter(func(b):
		return b.is_visible_in_tree() and not b.disabled and b.mouse_entered.get_connections().size() > 0 and b.button_down.get_connections().size() == 1)
	print("HUD buttons with hover+press hooks: %d %s" % [hud.size(), hud.map(func(x): return x.tooltip_text.get_slice("  ", 0) if not x.tooltip_text.is_empty() else str(x.name))])
	if not hud.is_empty():
		mark("b_hover_start")
		for i in 12:
			var b: BaseButton = hud[i % hud.size()]
			if i > 0:
				var left_one: BaseButton = hud[(i - 1) % hud.size()]
				left_one.notification(Control.NOTIFICATION_MOUSE_EXIT)
				left_one.mouse_exited.emit()
			# The viewport sends these on a real pointer move; the button's own hooks (hover_motion:
			# lift tween + RpgUi.sfx("hover")) run from the signal.
			b.notification(Control.NOTIFICATION_MOUSE_ENTER)
			b.mouse_entered.emit()
			poll("b_hover")
			await wait(0.32)
		var last_one: BaseButton = hud[11 % hud.size()]
		last_one.notification(Control.NOTIFICATION_MOUSE_EXIT)
		last_one.mouse_exited.emit()
		mark("b_hover_end")
		await wait(1.0)
		mark("b_click_start")
		for i in 8:
			hud[(i * 3) % hud.size()].button_down.emit()
			poll("b_click")
			await wait(0.42)
		mark("b_click_end")
	await wait(1.0)
	# c. fishing reel ticks (fishing.gd: 0.075 s +-20 %, quicker, higher and louder as the line tightens)
	var sfx = app.life.get("sfx") if app.get("life") != null else null
	if sfx != null:
		mark("c_tick_start")
		for i in 10:
			var progress := i / 18.0
			sfx.play("tick", lerpf(0.93, 1.08, progress), -6 + 2.0 * progress + randf_range(-1.0, 1.0))
			poll("c_tick")
			await wait(0.075 * randf_range(0.8, 1.2) * (1.0 - 0.2 * progress))
		await wait(0.4)
		mark("c_tick_end")
	await wait(1.0)
	# d. eight thuds (Fx.arrive's level), pickup-spaced
	mark("d_thud_start")
	for i in 8:
		Fx.sound(app, "thud", Vector3.INF, 1.0, -2.0)
		poll("d_thud")
		await wait(0.45)
	await wait(0.3)
	mark("d_thud_end")
	await wait(1.0)
	# e. the beds on the shore, with a few spots on top
	if not lines.sand.is_empty(): await place(lines.sand.start)
	mark("e_ambience_start")
	await wait(2.0)
	var spots = app.world_audio.get("spots")
	for kind in ["bird", "wave_slap", "gull", "bird"]:
		if spots != null and spots.has_method("fire"):
			spots.fire(kind)
			poll("e_spot")
		await wait(1.4)
	await wait(1.5)
	mark("e_ambience_end")
	print("CAPTURE_DONE events=%d" % events.size())
	_write()
	app.queue_free()
	await wait(0.5)
	quit(0)

func _write() -> void:
	if events_path.is_empty(): return
	var file := FileAccess.open(events_path, FileAccess.WRITE)
	if file == null:
		push_error("cannot write " + events_path)
		return
	file.store_string(JSON.stringify({"events": events, "marks": marks, "chip": chip_log, "fps": 30}, " "))
	file.close()
