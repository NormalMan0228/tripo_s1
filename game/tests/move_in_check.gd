extends SceneTree
## 단비's move-in (story 43/44, move_in.gd) on the QA server, with the residency fed to the module
## the way /v1/me would carry it (docs/design/MOVE_IN_API.md; the QA server has no moves yet):
##   no "residents" field -> nothing changes (also after the real /v1/me polls);
##   arriving -> the lot's sign says a neighbour is coming, no house;
##   home (news "moved_in") -> the house stands, her home is danbi_house, the arrival moment plays
##     once (sparkles + ribbon) and not again for the same answer or a fresh module (kept in user://);
##   away after a move-out -> no house, the sign says she has left, her old home again;
##   back (news "returned", 3 hearts) -> the house again, one warm greeting near her, once;
##   move letters read in the mailbox, older letters unchanged; a disabled answer restores the lot.
const Transition = preload("res://scripts/transition.gd")
const Town = preload("res://scripts/town.gd")
const Plots = preload("res://maps/archipelago/plots.gd")
const NpcGifts = preload("res://scripts/npc_gifts.gd")
const MoveIn = preload("res://scripts/move_in.gd")
var failed := false
var url := preload("res://tests/qa_server.gd").url()

func _initialize() -> void:
	call_deferred("run")
	create_timer(300).timeout.connect(func():
		push_error("Move-in check exceeded 300 seconds")
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

func village() -> Node:
	await wait_for(func() -> bool: return is_instance_valid(current_scene) and current_scene.get("screen") == "village" and Transition.instance != null and is_zero_approx(Transition.instance.veil.modulate.a), 90.0)
	return current_scene

## A /v1/me-shaped answer with one residency for 단비.
func me_with(state: String, extra := {}, news := []) -> Dictionary:
	var entry := {"npc":"shopkeeper", "state":state, "home":"danbi_house", "plot":"danbi_plot", "since":1800000000.0,
		"due_at":null, "moves":0, "legacy":false, "back":false, "hearts":0,
		"friendship":{"points":0, "gifts":0, "level":0, "next":40}, "memory":{"met":true, "first_met":1800000000.0, "last_met":null}}
	if state in ["arriving", "leaving"]: entry.due_at = 1800000090.0
	entry.merge(extra, true)
	var plot: String = {"away":"empty", "arriving":"building", "home":"built", "leaving":"built"}[state]
	return {"username":"tester", "residents":{"enabled":true, "host_id":"host-test", "version":1, "residents":[entry], "plots":{"danbi_plot":plot}, "news":news}}

func sign_text() -> String:
	var label := Plots.plot_info("danbi_plot").get("sign_label") as Label3D
	return label.text if label else str(Plots.sign_texts.get("danbi_plot", ""))

func bubble_with(town: Node, words: String) -> bool:
	# story.gd speech() panels (a second bubble on screen gets an auto name, so read story.bubbles).
	var seen: Array = []
	for entry in town.chapter().bubbles:
		if not is_instance_valid(entry.panel): continue
		for label in entry.panel.find_children("*", "Label", true, false):
			seen.append((label as Label).text)
			if (label as Label).text.contains(words): return true
	print("NOTE bubbles on screen: ", seen)
	return false

func run() -> void:
	MoveIn.save_path = "user://move_in_check_%d.cfg" % Time.get_ticks_usec()
	var api = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = url
	var login: Dictionary = await api.post("/v1/auth/register", {"username":"movein_"+str(Time.get_ticks_usec()%100000000), "password":"Move-in-check-pass-1"})
	expect(login.ok, "a fresh account")
	if not login.ok:
		quit(1)
		return
	Engine.set_meta("studio_session", {"token":login.data.token, "url":url, "room":"home"})
	change_scene_to_file("res://scenes/main.tscn")
	var town: Node = await village()
	var story: Node = town.chapter() if is_instance_valid(town) else null
	var mover: Node = story.move_in if story else null
	expect(is_instance_valid(mover), "the story module carries the move-in module")
	if not is_instance_valid(mover):
		quit(1)
		return

	# 1. Today's server: no "residents" in /v1/me -> nothing changes (also over a few real polls).
	var sign_before := sign_text()
	# The real server (moves off by default) sends {"enabled": false, ...}: the same as no field.
	var real_me = town.me.get("residents")
	expect(not town.me.has("residents") or (real_me is Dictionary and not bool(real_me.get("enabled", true))), "the QA server's /v1/me has no residents or moves switched off")
	mover.adopt_me({"username":"tester"})
	await create_timer(3.6).timeout
	expect(not Plots.is_built("danbi_plot") and sign_text() == sign_before and not MoveIn.touched and MoveIn.last_home.is_empty(),
		"without moves (no field, or real polls with enabled false) the lot, its sign and 단비's home stay as they were")
	# From here on the answers are fed by hand: the real polls (moves off) are unhooked.
	story.move_in = null
	expect(MoveIn.ENABLED, "the move-in switch is on")

	# 2. Arriving: the sign says a neighbour is coming, no house yet.
	mover.adopt_me(me_with("arriving"))
	expect(not Plots.is_built("danbi_plot") and sign_text() == tr(MoveIn.SIGN_SOON), "arriving: the sign says 곧 새 이웃이 이사 와요, no house")
	expect(MoveIn.last_home.is_empty(), "arriving: 단비's home is not moved yet")

	# 3. Moved in: the house, her home, the arrival moment once.
	var moved_in := me_with("home", {}, [{"id":"news-in-1", "npc":"shopkeeper", "kind":"moved_in", "at":1800000090.0, "letter_id":"l1", "returned_to_bag":[]}])
	mover.adopt_me(moved_in)
	expect(Plots.is_built("danbi_plot"), "moved in: the house stands on the lot")
	expect(sign_text() == tr(MoveIn.SIGN_HOME) or not Plots.plot_info("danbi_plot").get("sign_label"), "moved in: the sign reads 단비네 집")
	expect(MoveIn.last_home == "danbi_house", "moved in: 단비's home is danbi_house")
	if MoveIn.has_static("home_of"):
		expect(str(load("res://scripts/residents.gd").call("home_of", "shopkeeper")) == "danbi_house", "residents.gd agrees: home_of(shopkeeper) is danbi_house")
	else:
		print("NOTE residents.gd has no set_home/home_of yet: the call is skipped")
	expect(await wait_for(func() -> bool: return mover.celebrated == 1, 6.0), "the arrival moment plays")
	expect(town.ui.get_node_or_null("MoveInBanner") != null, "a ribbon tells 단비 moved in")
	expect(str(town.last_notice) == tr(MoveIn.TOAST_IN), "a toast says 단비 님이 이사 왔어요!")
	mover.adopt_me(moved_in)
	var fresh: Node = MoveIn.new()
	fresh.story = story
	story.add_child(fresh)
	fresh.adopt_me(moved_in)
	await create_timer(1.5).timeout
	expect(mover.celebrated == 1 and fresh.celebrated == 0 and fresh.pending_arrival.is_empty(), "the arrival moment plays once (not again for the same answer or a reloaded module)")
	fresh.queue_free()

	# 4. Moved out: no house, the sign says she left, her old home back.
	var out_news: Array = [{"id":"news-out-1", "npc":"shopkeeper", "kind":"moved_out", "at":1800000200.0, "letter_id":"l1b", "returned_to_bag":[]}]
	out_news.append_array(moved_in.residents.news)
	mover.adopt_me(me_with("away", {"moves":1}, out_news))
	expect(await wait_for(func() -> bool: return mover.farewells == 1, 6.0) and str(town.last_notice) == tr(MoveIn.TOAST_OUT), "moved out: a farewell toast once")
	expect(not Plots.is_built("danbi_plot"), "moved out: the house is gone, the lot is back")
	expect(sign_text() == tr(MoveIn.SIGN_AWAY), "moved out: the sign says 단비가 잠시 떠났어요")
	expect(MoveIn.last_home != "danbi_house", "moved out: 단비's home is her old one again")

	# 5. Back with 3 hearts: the house, the returning moment, one warm greeting near her.
	var back := me_with("home", {"moves":1, "back":true, "hearts":3}, [{"id":"news-back-1", "npc":"shopkeeper", "kind":"returned", "at":1800000300.0, "letter_id":"l2", "returned_to_bag":[]}])
	mover.adopt_me(back)
	expect(Plots.is_built("danbi_plot"), "back: the house stands again")
	expect(await wait_for(func() -> bool: return mover.celebrated == 2, 6.0), "back: the returning moment plays")
	expect(mover.greeted_back == 0, "back: no greeting while 단비 is not near")
	var danbi := Node3D.new()
	danbi.set_meta("cast", "shopkeeper")
	town.add_child(danbi)
	danbi.global_position = town.player.global_position+Vector3(1.2, 0, 0)
	town.npcs.append(danbi)
	expect(await wait_for(func() -> bool: return mover.greeted_back == 1, 6.0), "back: 단비 greets the walker when near")
	expect(bubble_with(town, tr(MoveIn.BACK_LINES[1])), "back: the greeting is the warm line for 2-3 hearts")
	mover.adopt_me(back)
	await create_timer(1.5).timeout
	expect(mover.greeted_back == 1, "back: the greeting comes once")
	town.npcs.erase(danbi)
	danbi.queue_free()

	# 6. Letters: move letters read sensibly, older letters as before.
	var page: Array = NpcGifts.letter_lines({"id":"l2", "npc":"shopkeeper", "name":"단비", "level":0, "read":false, "move":{"kind":"back", "npc":"shopkeeper"}})
	expect(page.size() == 1 and str(page[0]).contains(tr("단비")) and str(page[0]).contains(tr("다시 돌아왔어요! 그동안 보고 싶었어요. 집에 한번 들러 줘요.")), "a move letter reads as 단비's back-home letter")
	var real_letter: Array = load("res://scripts/npc_letters.gd").letter_lines({"id":"l3", "npc":"shopkeeper", "name":"단비", "level":0, "read":false,
		"event":{"type":"move_in", "payload":{"kind":"in", "home":"danbi_house", "plot":"danbi_plot", "moves":0}}})
	expect(real_letter.size() >= 1 and str(real_letter[0]).contains(tr("단비")), "a real-server move letter (event move_in) reads as 단비's letter")
	var old: Array = NpcGifts.letter_lines({"id":"l0", "npc":"farmer", "name":"보리", "level":2, "personality":"calm", "read":false})
	expect(old.size() >= 1 and str(old[0]).contains(NpcGifts.hearts(2)), "an older hearts letter reads as before")

	# 7. A disabled answer puts the lot back as the map shows it.
	mover.adopt_me({"residents":{"enabled":false, "host_id":"host-test", "residents":[], "plots":{"danbi_plot":"empty"}, "news":[]}})
	expect(not Plots.is_built("danbi_plot") and sign_text() == tr(str(Plots.PLOTS.danbi_plot.sign_text)) and not MoveIn.touched, "disabled: the lot and its sign are back to the map's own")

	DirAccess.remove_absolute(ProjectSettings.globalize_path(MoveIn.save_path))
	quit(1 if failed else 0)
