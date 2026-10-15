extends SceneTree
## The demo's small rules, end to end on the QA server:
##   dialogue keys: E reads on; when the choices appear a key in the first moment never picks one
##   (reading on with E); then S/W (and the arrows) move the highlight and E, Space or Enter pick
##   the highlighted choice;
##   selling: apples from the orchard sold at the seed stall pay leaf coins and starseeds (a daily
##   allowance shown on the stall), the stars fly into the counter; the general store's window
##   (단비, shop_sell.gd) lists the bag and sells the same way.
## --capture saves artifacts/demo-keys-*.png.
const Main = preload("res://scripts/main.gd")
const Town = preload("res://scripts/town.gd")
const ShopSell = preload("res://scripts/shop_sell.gd")
const PASSWORD := "Demo-keys-pass-1"
var failed := false
var capture := "--capture" in OS.get_cmdline_user_args()
var shots := 0
var app: Node

func _initialize() -> void:
	call_deferred("run")
	create_timer(300).timeout.connect(func():
		push_error("demo_keys exceeded 300 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func wait_for(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec()+int(seconds*1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return condition.call()

func shot(name: String, settle := 0.6) -> void:
	if not capture: return
	await create_timer(settle).timeout
	await RenderingServer.frame_post_draw
	shots += 1
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/demo-keys-%02d-%s.png" % [shots, name]))

func key(code: Key) -> void:
	for pressed in [true, false]:
		var event := InputEventKey.new()
		event.keycode = code
		event.physical_keycode = code
		event.pressed = pressed
		root.push_input(event)
		await process_frame

func buttons() -> Array:
	var out: Array = []
	if not is_instance_valid(app.village_modal): return out
	for b in app.village_modal.find_children("*", "Button", true, false):
		if (b as Button).is_visible_in_tree() and not (b as Button).is_queued_for_deletion(): out.append(b)
	return out

func cast(id: String) -> Node3D:
	for npc in app.npcs:
		if is_instance_valid(npc) and str(npc.get_meta("cast", "")) == id: return npc
	return null

func teleport(at: Vector2) -> void:
	app.player.position = Town.point(at, 0.3)
	app.player.velocity = Vector3.ZERO
	app.follow_camera(1.0)
	for i in 6: await physics_frame

func run() -> void:
	preload("res://scripts/npc.gd").pinned = true
	app = Main.new()
	root.add_child(app)
	await create_timer(1.0).timeout
	var name := "keys_"+str(Time.get_ticks_msec()%1000000)
	await app.authenticate(true, preload("res://tests/qa_server.gd").url(), name, PASSWORD, "")
	expect(await wait_for(func() -> bool: return app.screen == "village" and is_instance_valid(app.player), 60.0), "the village")
	await create_timer(1.0).timeout

	# 1. Dialogue keys on a resident's talk (several pages, then choices).
	var npc := cast("sora")
	await teleport(Vector2(npc.position.x, npc.position.z)+Vector2(0, 1.6))
	app.close_village_modal()
	var lines: Array = ["첫 줄이에요.", "둘째 줄이에요.", "셋째 줄이에요."]
	var hits := [0, 0, 0]
	app.open_dialogue("소라 · 재단사", "sora", lines, [["하나", func(): hits[0] += 1], ["둘", func(): hits[1] += 1], ["셋", func(): hits[2] += 1]])
	expect(is_instance_valid(app.village_modal), "a dialogue opens")
	await shot("dialogue-page")
	# E finishes the typing, then turns the page, until the choices show.
	var presses := 0
	while buttons().is_empty() and presses < 12:
		await key(KEY_E)
		presses += 1
	expect(buttons().size() == 3, "E reads on to the choices (%d presses)" % presses)
	# The press right as they appear (reading on) picks nothing.
	await key(KEY_E)
	expect(hits == [0, 0, 0] and buttons().size() == 3, "a key in the choices' first moment picks nothing")
	await create_timer(0.45).timeout
	await process_frame
	var list := buttons()
	expect(root.gui_get_focus_owner() == list[0], "the first choice is highlighted")
	await key(KEY_S)
	expect(root.gui_get_focus_owner() == list[1], "S moves the highlight down")
	await key(KEY_DOWN)
	expect(root.gui_get_focus_owner() == list[2], "the down arrow too")
	await key(KEY_W)
	expect(root.gui_get_focus_owner() == list[1], "W moves it back up")
	await shot("dialogue-choice")
	await key(KEY_E)
	expect(hits == [0, 1, 0], "E picks the highlighted choice (%s)" % str(hits))
	expect(not is_instance_valid(app.village_modal) or buttons().is_empty(), "and the dialogue closes")
	# Space picks too (a second dialogue).
	app.open_dialogue("소라 · 재단사", "sora", ["한 줄."], [["좋아요", func(): hits[0] += 1], ["싫어요", func(): hits[2] += 1]])
	while buttons().is_empty() and presses < 30:
		await key(KEY_SPACE)
		presses += 1
	await create_timer(0.45).timeout
	await process_frame
	await key(KEY_SPACE)
	expect(hits == [1, 1, 0], "Space picks the highlighted choice")
	app.close_village_modal()

	# 2. Selling at the seed stall: apples from the orchard box, leaf coins and starseeds.
	var api: Node = app.api
	var state: Dictionary = (await api.request("/v1/homestead")).data
	var allowance: Dictionary = state.get("sell_stars", {})
	expect(int(allowance.get("cap", 0)) > 0 and int(allowance.get("today", -1)) == 0, "the stall's allowance comes with the life state %s" % str(allowance))
	var reply: Dictionary = await api.post("/v1/homestead", api.mutation({"action":"gather", "item":"apple", "version":int(state.version)}))
	expect(reply.ok and int(reply.data.bag.get("apple", 0)) >= 2, "apples from the orchard box")
	var apples := int(reply.data.bag.get("apple", 0))
	await app.life.refresh()
	var before := int(app.frame.stars.text)
	app.life.open_shop()
	await process_frame
	var sell: Button = null
	var line := ""
	for b in app.village_modal.find_children("*", "Button", true, false):
		if (b as Button).text.begins_with("사과"): sell = b
	for l in app.village_modal.find_children("*", "Label", true, false):
		if (l as Label).text.begins_with("오늘 별씨"): line = (l as Label).text
	expect(line != "", "the stall shows today's starseeds (%s)" % line)
	expect(sell != null and sell.text.contains("별씨 +"), "the apple button shows the starseeds it adds (%s)" % (sell.text if sell else ""))
	await shot("stall")
	sell.pressed.emit()
	expect(await wait_for(func() -> bool: return int(app.frame.stars.text) > before, 8.0), "stars fly into the counter (%d -> %s)" % [before, app.frame.stars.text])
	var after: Dictionary = (await api.request("/v1/homestead")).data
	var me: Dictionary = (await api.request("/v1/me")).data
	expect(int(after.bag.get("apple", 0)) == 0 and int(me.shards) == int(app.frame.stars.text), "apples sold, counter = server (%s)" % str(me.shards))
	expect(int(after.sell_stars.today) == apples*2/3, "today's starseeds: %d" % int(after.sell_stars.today))
	app.close_village_modal()

	# 3. The general store's window (단비): lists the bag and sells the same way.
	# A shell from the beach (a forage spot) gives the store something to buy.
	for node in ["shell_01", "shell_02", "shell_03"]:
		await create_timer(2.2).timeout
		var fresh: Dictionary = (await api.request("/v1/homestead")).data
		reply = await api.post("/v1/homestead", api.mutation({"action":"gather", "node":node, "version":int(fresh.version)}))
		if reply.ok: break
	expect(reply.ok, "a find from the beach for the store")
	var got := [{}]
	var window: Control = ShopSell.window(app.ui, api, func(data: Dictionary): got[0] = data)
	expect(await wait_for(func() -> bool:
		for l in window.find_children("*", "Label", true, false):
			if (l as Label).text.begins_with("잎전"): return true
		return false, 5.0), "the store window loads the bag")
	var store_buttons: Array = window.find_children("*", "Button", true, false)
	expect(not store_buttons.is_empty(), "the store lists something to sell (%d)" % store_buttons.size())
	await shot("store")
	if not store_buttons.is_empty():
		(store_buttons[0] as Button).pressed.emit()
		expect(await wait_for(func() -> bool: return not got[0].is_empty(), 5.0), "a sale at the store answers (%s)" % str(got[0].get("message", "")))
	window.queue_free()

	# 4. In the general store at noon: 단비 at the counter offers "물건 팔기" and sells there.
	for node in ["shell_04", "shell_05", "shell_06"]:
		await create_timer(2.2).timeout
		var fresh: Dictionary = (await api.request("/v1/homestead")).data
		reply = await api.post("/v1/homestead", api.mutation({"action":"gather", "node":node, "version":int(fresh.version)}))
		if reply.ok: break
	Engine.set_meta("interior_hour", 12.0)
	Engine.set_meta("studio_session", {"token":str(api.token), "url":preload("res://tests/qa_server.gd").url(), "room":"13_shop"})
	var room: Control = load("res://scenes/studio.tscn").instantiate()
	root.add_child(room)
	var present := await wait_for(func() -> bool: return room.npcs.has("shopkeeper") and str(room.npcs.shopkeeper.state.get("activity", "")) == "shopkeep", 40.0)
	expect(present, "단비 keeps the counter at noon")
	if present:
		room.open_talk("shopkeeper")
		var labels: Array = room.talk_choices.map(func(c): return str(c[0]))
		expect("물건 팔기" in labels, "her talk offers 물건 팔기 (%s)" % str(labels))
		room.run_choice("sell")
		var sells := [[]]
		expect(await wait_for(func() -> bool:
			if not is_instance_valid(room.talk_box): return false
			sells[0] = room.talk_box.find_children("*", "Button", true, false)
			return not sells[0].is_empty(), 6.0), "the selling window lists the bag")
		await shot("store-room", 0.8)
		var coins_before := int((await api.request("/v1/homestead")).data.get("coins", 0))
		if not sells[0].is_empty():
			(sells[0][0] as Button).pressed.emit()
			await create_timer(1.5).timeout
			var coins_after := int((await api.request("/v1/homestead")).data.get("coins", 0))
			expect(coins_after > coins_before, "a sale at the counter pays leaf coins (%d -> %d)" % [coins_before, coins_after])
		await key(KEY_E)
		expect(not is_instance_valid(room.talk_box), "E closes the selling window")
	Engine.remove_meta("interior_hour")
	room.queue_free()
	await create_timer(0.5).timeout
	print("DEMO_KEYS " + ("FAILED" if failed else "OK"))
	quit(1 if failed else 0)
