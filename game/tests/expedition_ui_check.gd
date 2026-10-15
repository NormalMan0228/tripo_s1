extends SceneTree
## The staged expedition's screens against recorded replies (no port): the map choice is a row of
## picture cards in catalog order (the tutorial first, with its 처음 ribbon; a crown where a boss
## waits), the tracker reads "스테이지 n/m" with the stage clock (∞ on the boss night) and falls back
## to the seven-day dots without stages, and the boss bar comes with run.boss, follows its health,
## pushes the toast lane down and leaves with the boss. Windowed runs capture artifacts/exp-*.png:
##   godot --path game --script res://tests/expedition_ui_check.gd
const Main = preload("res://scripts/main.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
var failures: Array[String] = []
var app: Node

func expect(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("expedition_ui_check exceeded 240 seconds")
		quit(2))

func capture(name: String) -> void:
	for i in 6: await process_frame
	if DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/exp-%s.png" % name))
	print("SHOT exp-", name)

func run() -> void:
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	var maps: Array = fixture["/v1/me"]["catalog"]["maps"]
	var order := {"forest":1, "quarry":2, "frost":3}
	var stages := {"forest":3, "quarry":5, "frost":7}
	for region in maps:
		region["order"] = order.get(region.id, 9)
		region["stages"] = stages.get(region.id, 3)
		region["has_boss"] = true
	var tutorial: Dictionary = maps[0].duplicate(true)
	tutorial.merge({"id":"tutorial", "name":"첫 탐험 연습", "description":"걷기, 채집, 모닥불을 차근차근 배워요.", "order":0, "stages":1, "has_boss":false, "tutorial":true}, true)
	maps.append(tutorial)
	app = Main.new()
	root.add_child(app)
	await create_timer(1.6).timeout
	app.api.queue_free()
	var stub := Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = false
	await app.enter_village()
	preload("res://scripts/transition.gd").of(self).fade_in()
	await create_timer(0.8).timeout
	# The map choice: picture cards in catalog order.
	app.chosen_map = "forest"
	await app.open_expedition()
	await create_timer(0.5).timeout
	var cards: Array = app.village_modal.find_children("Map_*", "Button", true, false)
	expect(cards.map(func(c): return c.get_meta("id")) == ["tutorial", "forest", "quarry", "frost"], "map cards in catalog order, tutorial first (%s)" % [cards.map(func(c): return c.get_meta("id"))])
	expect(cards.size() == 4 and cards.all(func(c): return c.find_children("*", "TextureRect", true, false).any(func(t): return t.texture != null)), "every card shows a painting")
	expect(cards.size() == 4 and cards[0].find_children("*", "Label", true, false).any(func(l): return l.text == tr("처음")), "the tutorial card wears its ribbon")
	var crowns := func(card: Control) -> int: return card.find_children("*", "TextureRect", true, false).filter(func(t): return t.texture != null and t.texture.resource_path.ends_with("crown.png")).size()
	expect(cards.size() == 4 and crowns.call(cards[0]) == 0 and crowns.call(cards[2]) == 1, "a crown where a boss waits, none on the tutorial")
	expect(cards.size() == 4 and cards[1].button_pressed, "the chosen map's card is pressed")
	if cards.size() == 4: cards[3].pressed.emit()
	await process_frame
	expect(app.chosen_map == "frost" and cards[3].button_pressed and not cards[1].button_pressed, "clicking a card picks that map")
	await capture("cards")
	app.close_village_modal()
	await create_timer(0.3).timeout
	# Into the field: the tracker and the boss bar.
	await app.start_run("forest", "standard")
	preload("res://scripts/transition.gd").of(self).fade_in()
	await create_timer(1.2).timeout
	expect(app.screen == "survival", "the expedition HUD is up")
	app.run["day"] = 3
	app.run.erase("stage")
	app.update_run()
	expect(app.day_track.text.begins_with("DAY 03"), "without stages the tracker keeps the seven-day dots (%s)" % app.day_track.text)
	app.run.merge({"stage":2, "stage_count":5, "stage_seconds":120, "stage_remaining":75, "boss_night":false, "boss":null}, true)
	app.update_run()
	expect(app.day_track.text == tr("스테이지 %d/%d") % [2, 5] + "   1:15", "stage line with its clock (%s)" % app.day_track.text)
	expect(not is_instance_valid(app.boss_panel), "no boss bar before the boss night")
	var lane_y: float = app.toast_lane.position.y
	app.run.merge({"stage":5, "stage_remaining":-1, "boss_night":true, "boss":{"id":"golem", "name":"이끼 골렘", "hp":900, "max_hp":1000}}, true)
	app.update_run()
	await process_frame
	expect(app.day_track.text.ends_with("∞"), "the boss night's clock reads ∞ (%s)" % app.day_track.text)
	expect(app.metrics.text == tr("우두머리의 밤"), "the status line names the boss night instead of a zero clock (%s)" % app.metrics.text)
	expect(is_instance_valid(app.boss_panel) and app.boss_meter.bar.value == 900 and app.boss_meter.bar.max_value == 1000, "the boss bar shows its health")
	expect(app.toast_lane.position.y > lane_y, "the toast lane steps down under the boss bar")
	app.run.boss.hp = 640
	app.update_run()
	await create_timer(0.3).timeout
	expect(app.boss_meter.bar.value == 640 and app.boss_meter.readout.text == "640 / 1000", "a hit lowers the bar and its numbers")
	await capture("boss")
	app.run.boss = null
	app.run.boss_night = false
	app.update_run()
	await process_frame
	expect(not is_instance_valid(app.boss_panel) and is_equal_approx(app.toast_lane.position.y, lane_y), "the bar leaves with the boss; the lane goes back")
	print("EXPEDITION_UI ", "PASS" if failures.is_empty() else "FAIL %d" % failures.size())
	quit(0 if failures.is_empty() else 1)
