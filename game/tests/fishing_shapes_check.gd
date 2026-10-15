extends SceneTree
## Reel fight meter shapes (fishing.gd): difficulty 1 fights on the lane, 2 on the upright gauge,
## 3+ on the ring. Each
## shape and difficulty runs seeded auto_reel fights through step() and must land almost every
## fish within a sane time (never before the server's fight_min); the ring's wrap-around gap and
## auto_reel direction are checked at the seam; then one real fight per shape runs through
## start_fight()/update() against a stub life (sfx, HUD, the reel request) until it lands.
## Windowed runs also save the meters mid-fight: artifacts/fishing_ring.png, fishing_gauge.png,
## fishing_lane.png.
##   godot --path game --script res://tests/fishing_shapes_check.gd
##   (or tools/test.ps1 -SkipServerTests -ClientScript fishing_shapes_check [-Capture])
const Fishing = preload("res://scripts/fishing.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const FIGHT_MIN := {1:2.0,2:2.2,3:2.6,4:3.0,5:3.4}
var failures: Array[String] = []

class Sfx extends Node:
	var played := {}
	func play(sound: String, _pitch := 1.0, _db := 0.0) -> void:
		played[sound] = int(played.get(sound, 0)) + 1

class Life extends Node:
	var sfx := Sfx.new()
	var state := {"bag":{"bait":3}, "fishing":null, "catalog":{}}
	var last_reward := {}
	var requests: Array = []
	var layer: CanvasLayer
	func now() -> float: return Time.get_ticks_msec() * 0.001
	func request(kind: String, extra: Dictionary = {}) -> Dictionary:
		requests.append([kind, extra])
		await get_tree().process_frame
		return {}
	func claim_hud(node: Control) -> void: layer.add_child(node)
	func deny() -> void: pass
	func fly_items(_items: Dictionary, _from: Vector3, _delay := 0.0) -> void: pass

class App extends Node:
	var world := Node3D.new()
	var player: Node = null
	var town: Node = null
	var messages: Array = []
	func message(text: String) -> void: messages.append(text)
	func close_village_modal() -> void: pass

func expect(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func _initialize() -> void:
	call_deferred("run")
	create_timer(180).timeout.connect(func():
		push_error("fishing_shapes_check exceeded 180 seconds")
		quit(2))

func fish_for(difficulty: int, shadow := "small") -> Dictionary:
	return {"difficulty":difficulty, "fight_min":FIGHT_MIN[difficulty], "shadow":shadow}

## Seeded auto_reel fights straight through step(): [landed, mean seconds, shortest, wrapped].
func simulate(difficulty: int, fights: int) -> Array:
	var f: Node = Fishing.new()
	f.auto_reel = true
	seed(4100 + difficulty)
	var landed := 0
	var total := 0.0
	var shortest := 99.0
	var wrapped := false
	for n in fights:
		f.setup_fight(fish_for(difficulty, "large" if n % 2 else "small"))
		var t := 0.0
		while t < 45.0:
			t += 1.0 / 60.0
			f.fight_time = t
			f.step(1.0 / 60.0, false)
			if f.fish_x < 0.0 or f.fish_x > 1.0: wrapped = true
			if f.progress >= 1.0 and t >= f.fight_min + 0.2:
				landed += 1
				total += t
				shortest = minf(shortest, t)
				break
			if f.progress <= 0.0: break
	f.free()
	return [landed, total / maxf(1, landed), shortest, wrapped]

func run() -> void:
	# Shape per difficulty (the client only knows difficulty + shadow at the hook).
	var shapes := []
	for d in range(1, 6): shapes.append(Fishing.shape_for(d))
	expect(shapes == ["lane","gauge","ring","ring","ring"], "difficulty 1 lane, 2 gauge, 3-5 ring: %s" % [shapes])
	var probe: Node = Fishing.new()
	probe.setup_fight(fish_for(3))
	var w3: float = probe.zone_w
	probe.setup_fight(fish_for(5))
	expect(probe.meter_shape == "ring" and probe.zone_w < w3, "harder ring fish get a narrower arc (%.3f < %.3f)" % [probe.zone_w, w3])
	# The ring measures the short way round: a fish just past the top seam is ahead of a zone
	# just before it, and auto_reel holds to turn the arc clockwise after it.
	probe.zone_v = 0.0
	probe.zone_x = 0.95 - probe.zone_w * 0.5
	probe.fish_x = 1.03
	expect(absf(probe.fish_gap() - 0.08) < 0.001, "ring gap wraps across the seam (%.3f)" % probe.fish_gap())
	expect(probe.auto_hold(), "auto_reel holds when the fish is ahead clockwise across the seam")
	probe.fish_x = 0.03 + 7.0
	expect(absf(probe.fish_gap() - 0.08) < 0.001, "ring gap ignores whole turns")
	probe.fish_x = 0.86
	expect(not probe.auto_hold(), "auto_reel lets go when the fish is behind (anticlockwise)")
	probe.fish_x = 0.95 + 0.6
	expect(probe.fish_gap() < 0.0 and probe.fish_gap() > -0.5, "more than half a turn ahead counts as behind (%.3f)" % probe.fish_gap())
	probe.setup_fight(fish_for(1))
	probe.zone_x = 0.3
	probe.fish_x = 0.9
	expect(probe.meter_shape == "lane" and probe.auto_hold(), "lane auto_reel still holds toward a fish on the right")
	probe.free()
	# Seeded auto_reel fights per difficulty: land nearly all, never before the server's minimum.
	for d in range(1, 6):
		var r := simulate(d, 24)
		print("SIM d%d %s landed %d/24 mean %.1fs shortest %.1fs" % [d, Fishing.shape_for(d), r[0], r[1], r[2]])
		expect(r[0] >= 21, "auto_reel lands d%d (%s) at least 21/24 (%d)" % [d, Fishing.shape_for(d), r[0]])
		expect(r[1] < 16.0, "d%d mean landing time is sane (%.1f s)" % [d, r[1]])
		expect(r[2] >= FIGHT_MIN[d] + 0.2, "d%d never lands before fight_min (%.1f s)" % [d, r[2]])
		if Fishing.shape_for(d) == "ring": expect(r[3], "d%d ring fish swims across the seam" % d)
	await live_fights()
	print("FISHING_SHAPES %s (%d failures)" % ["PASS" if failures.is_empty() else "FAIL", failures.size()])
	quit(0 if failures.is_empty() else 1)

## One real fight per shape through start_fight()/update() with the meter on screen.
func live_fights() -> void:
	var windowed := DisplayServer.get_name() != "headless"
	# A daylight backdrop so the captures read like the game (any title art that is present).
	var backdrop := TextureRect.new()
	for art in ["res://assets/title_morning.jpg", "res://assets/title_golden.jpg"]:
		if ResourceLoader.exists(art):
			backdrop.texture = load(art)
			break
	backdrop.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	backdrop.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	backdrop.modulate = Color(0.78, 0.8, 0.85)
	root.add_child(backdrop)
	var life := Life.new()
	var app := App.new()
	root.add_child(life)
	root.add_child(app)
	life.add_child(life.sfx)
	app.add_child(app.world)
	life.layer = CanvasLayer.new()
	root.add_child(life.layer)
	for d in [1, 2, 4]:
		var f: Node = Fishing.new()
		f.life = life
		f.app = app
		root.add_child(f)
		f.build_hud()
		f.phase = "ready"
		f.auto_reel = true
		seed(77 + d)
		life.requests.clear()
		f.start_fight(fish_for(d, "large"))
		var shape: String = f.meter_shape
		expect(f.phase == "fight" and is_instance_valid(f.meter), "d%d %s fight starts with its meter" % [d, shape])
		if shape == "gauge":
			var upright := tr("%s·Space·클릭을 누르고 있으면 칸이 위로, 떼면 아래로") % RpgUi.key_text("interact")
			expect(f.meter.size == Fishing.GAUGE_SIZE and f.keys.text == upright, "gauge meter stands upright with its hint: " + f.keys.text)
		if shape == "ring":
			expect(f.meter.size == Vector2(Fishing.RING_SIZE, Fishing.RING_SIZE), "ring meter is square")
			var hint := tr("%s·Space·클릭을 누르고 있으면 초록 호가 시계 방향으로, 떼면 반대로") % RpgUi.key_text("interact")
			expect(f.keys.text == hint, "ring fight hint explains the clockwise reel: " + f.keys.text)
		var shot := false
		var t := 0.0
		while f.phase == "fight" and t < 45.0:
			await process_frame
			t += 1.0 / 60.0
			f.update(1.0 / 60.0)
			var moving: bool = f.progress > 0.55 and absf(f.zone_v) > 0.2
			if windowed and not shot and f.phase == "fight" and t > 1.6 and f.zone_inside and (moving or f.progress > 0.85):
				shot = true
				await RenderingServer.frame_post_draw
				var file := "fishing_%s.png" % shape
				root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/" + file))
				print("SHOT ", file)
		for i in 4: await process_frame
		expect(life.requests.size() > 0 and life.requests[0] == ["reel", {"outcome":"landed"}], "d%d %s fight lands and asks the server (%.1f s)" % [d, shape, t])
		expect(int(life.sfx.played.get("tick", 0)) > 0, "reel ticks still play while holding")
		if windowed: expect(shot, "d%d %s meter captured mid-fight" % [d, shape])
		f.end()
		if is_instance_valid(f.hud): f.hud.queue_free()
		for c in life.layer.get_children(): c.queue_free()
		f.queue_free()
		await process_frame
