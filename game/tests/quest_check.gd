extends SceneTree
## Every resident's request, all nineteen (quests.gd words, server/quests.py rules) on the QA server, through the
## same conversation code the village and the rooms use (Quests.choice_for with a recording
## dialogue box): a new account finishes the opening chapter (the requests stay closed until
## 모카's letter is read), then each request is offered, taken, done the way a player does it
## (apples, mushrooms, flowers, herbs, pinecones, sea and pond fish, turnips and carrots grown,
## signposts, the lookout, night errands by the player's clock, a new outfit, a gift, a message
## passed on, a teddy bear at home and then for 콩이, a lamp set out in the village) and handed over: the starseeds come once, the choice goes away,
## and 모카 and 노을 write their letters.
const Quests = preload("res://scripts/quests.gd")
const NpcGifts = preload("res://scripts/npc_gifts.gd")
const PASSWORD := "Quest-check-pass-1"
var failed := false
var url := preload("res://tests/qa_server.gd").url()
var api: Node
## The recording dialogue box: the last lines and choices said.
var box := {"lines":[], "choices":[], "count":0}
var effects: Array = []

## An api that records what the conversation would send (and answers no).
class SentApi extends Node:
	var token := ""
	var sent: Array = []
	func mutation(extra := {}) -> Dictionary:
		return extra.merged({"request_id":"recorded"})
	func post(path: String, payload: Dictionary) -> Dictionary:
		sent.append([path, payload])
		return {"ok":false, "error":"quests_locked", "data":{}}
	func request(_path: String) -> Dictionary:
		return {"ok":false, "error":"offline", "data":{}}

func _initialize() -> void:
	call_deferred("run")
	create_timer(900).timeout.connect(func():
		push_error("Quest check exceeded 900 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func wait_for(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec()+int(seconds*1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await create_timer(0.1).timeout
	return condition.call()

func say(lines: Array, choices: Array) -> void:
	box.lines = lines
	box.choices = choices
	box.count += 1

func done(kind: String, reply: Dictionary) -> void:
	effects.append([kind, reply])

## Presses the choice with this label (or whose label starts with it) and waits for the next words.
func press(label: String) -> bool:
	for choice in box.choices:
		if str(choice[0]) == label or str(choice[0]).begins_with(label):
			var before := int(box.count)
			var action: Callable = choice[1]
			if action.is_valid(): action.call()
			return await wait_for(func() -> bool: return int(box.count) > before, 10.0)
	print("  choices were: ", box.choices.map(func(c): return c[0]))
	return false

func refresh() -> Dictionary:
	var reply: Dictionary = await api.request("/v1/quests")
	if reply.ok: Quests.adopt_data(reply.data.get("quests"), str(api.token))
	return reply.data.get("quests", {}) if reply.ok else {}

func talk(npc: String) -> Array:
	await refresh()
	return Quests.choice_for(api, npc, say, done, false)

## Opens the resident's request choice (and presses it).
func open(npc: String, label: String) -> bool:
	var request: Array = await talk(npc)
	if request.is_empty() or not str(request[0]).begins_with(label):
		print("  ", npc, " offers ", request)
		return false
	var before := int(box.count)
	(request[1] as Callable).call()
	return await wait_for(func() -> bool: return int(box.count) > before, 10.0)

func life() -> Dictionary:
	var reply: Dictionary = await api.request("/v1/homestead")
	return reply.data if reply.ok else {}

func act(action: String, extra := {}) -> Dictionary:
	var state := await life()
	var reply: Dictionary = await api.post("/v1/homestead", api.mutation(extra.merged({"action":action, "version":int(state.get("version", 0))})))
	if not reply.ok: print("  homestead ", action, " ", extra, " -> ", reply.get("error", ""))
	return reply.data if reply.ok else {}

func bag_count(items: Array) -> int:
	var bag: Dictionary = (await life()).get("bag", {})
	var n := 0
	for item in items: n += int(bag.get(item, 0))
	return n

func craft(prompt: String) -> String:
	var queued: Dictionary = await api.post("/v1/studio/jobs", api.mutation({"prompt":prompt, "geometry":"proxy", "designer":"fixture"}))
	for i in 120:
		var job: Dictionary = await api.request("/v1/studio/jobs/"+str(queued.get("data", {}).get("id", "")))
		if job.ok and job.data.state == "awaiting_confirmation": await api.post("/v1/studio/jobs/%s/confirm" % job.data.id, api.mutation({"use_concept":false}))
		if job.ok and job.data.state == "ready": return str(job.data.object_id)
		await create_timer(0.5).timeout
	return ""

## One fish from this water (casts until one lands; buys bait when it runs out).
func catch_one(spot: String) -> bool:
	for attempt in 8:
		if int((await life()).get("bag", {}).get("bait", 0)) <= 0: await act("buy", {"item":"bait", "quantity":5})
		var before := int((await life()).get("caught", 0))
		var thrown := await act("cast", {"spot":spot})
		await create_timer(maxf(0.1, float(thrown.get("fishing", {}).get("bite_at", 0))-float(thrown.get("server_time", 0))+0.3)).timeout
		var hooked := await act("reel")
		if hooked.get("reward", {}).get("kind", "") != "hooked": continue
		await create_timer(float(hooked.get("fishing", {}).get("fight_min", 3.5))+0.4).timeout
		await act("reel", {"outcome":"landed"})
		if int((await life()).get("caught", 0)) > before: return true
	return false

## A request from a player whose own clock shows this hour now (the time zone header; the
## game's api always sends the real one).
func local_post(path: String, payload: Dictionary, hour: int) -> Dictionary:
	var utc := Time.get_datetime_dict_from_system(true)
	var shift := fposmod(float(hour)-(float(utc.hour)+float(utc.minute)/60.0), 24.0)
	if shift > 14.0: shift -= 24.0
	var http := HTTPRequest.new()
	root.add_child(http)
	var headers := PackedStringArray(["Content-Type: application/json", "Authorization: Bearer "+str(api.token),
		"X-Villagen-UTC-Offset: %d" % int(round(shift*60.0)), load("res://scripts/api.gd").version_header()])
	http.request(url+path, headers, HTTPClient.METHOD_POST, JSON.stringify(api.mutation(payload)))
	var response: Array = await http.request_completed
	http.queue_free()
	var data = JSON.parse_string((response[3] as PackedByteArray).get_string_from_utf8())
	var ok: bool = int(response[1]) < 400 and data is Dictionary
	return {"ok":ok, "data":data if data is Dictionary else {}, "error":"" if ok or not data is Dictionary else str(data.get("detail", ""))}

## /v1/me's brief updates the kept list (same catalog), and the night names of the shadow folk.
func brief_and_names(opened: Dictionary) -> void:
	var me: Dictionary = (await api.request("/v1/me")).data.get("quests", {})
	expect(not me.has("list") and me.get("states") is Array and str(me.get("catalog", "")) == str(opened.get("catalog", "")), "/v1/me carries only the states and the catalog digest")
	expect(Quests.adopt_data(me, str(api.token)) and Quests.listed(str(api.token)).size() == 19 and str(Quests.by_id(str(api.token), "moka_pie").get("npc", "")) == "regular" and int(Quests.by_id(str(api.token), "moka_pie").get("stars", 0)) == 8, "the brief updates the kept list, its residents kept")
	var stale := me.duplicate()
	stale["catalog"] = "another"
	expect(not Quests.adopt_data(stale, str(api.token)) and not Quests.adopt_data(me, "another-token"), "a brief with another catalog (or login) asks for the full list")
	# 하늘 and 새벽 by day; at night the shadow's role is named with them, as over their heads.
	expect(Quests.npc_name("stargazer", 12.0) == tr("하늘") and Quests.npc_name("stargazer", 22.0) == tr("하늘")+"("+tr("별지기")+")", "하늘 by day, 하늘(별지기) at night (%s)" % Quests.npc_name("stargazer", 22.0))
	expect(Quests.npc_name("stroller", 23.0) == tr("새벽")+"("+tr("밤 산책자")+")" and Quests.npc_name("sora", 23.0) == tr("소라"), "새벽(밤 산책자) at night; the cast keep their names")
	var stars: Dictionary = Quests.by_id(str(api.token), "haneul_stars")
	expect(Quests.goal_text(stars, 1, true, 22.0).contains(tr("하늘")+"("+tr("별지기")+")") and Quests.done_word(stars, 22.0).contains(tr("별지기")), "the tracker and the 'done' word name the night role")

## 하늘's request from inside her observatory: the yes carries the place (the server counts it at
## night); E through her talk never opens the request by itself.
func inside_the_observatory() -> void:
	expect(Quests.place_of_room("05_observatory") == "observatory" and Quests.place_of_room("13_shop") == "", "the observatory is the room of 하늘's request")
	var sent := SentApi.new()
	root.add_child(sent)
	sent.token = str(api.token)
	var choice: Array = Quests.choice_for(sent, "stargazer", say, done, false, Callable(), "observatory")
	var before := int(box.count)
	(choice[1] as Callable).call()
	await wait_for(func() -> bool: return int(box.count) > before, 5.0)
	expect(await press("맡겨 줘요") and not sent.sent.is_empty() and str(sent.sent.back()[1].get("place", "")) == "observatory", "taken inside the observatory: the yes says where (%s)" % str(sent.sent))
	var pie: Array = Quests.choice_for(sent, "regular", say, done, false, Callable(), "observatory")
	before = int(box.count)
	(pie[1] as Callable).call()
	await wait_for(func() -> bool: return int(box.count) > before, 5.0)
	expect(await press("맡겨 줘요") and not sent.sent.back()[1].has("place"), "another request's yes has no place")
	sent.queue_free()
	# The room itself at night: 하늘 at her telescope, the request on top, E reads on past it.
	Engine.set_meta("interior_hour", 22.0)
	Engine.set_meta("studio_session", {"token":str(api.token), "url":url, "room":"05_observatory"})
	var room: Control = load("res://scenes/studio.tscn").instantiate()
	root.add_child(room)
	var present := await wait_for(func() -> bool: return room.npcs.has("stargazer") and not room.npcs.stargazer.state.get("asleep", false), 40.0)
	expect(present, "하늘 is in the observatory at night")
	if present:
		room.open_talk("stargazer")
		var top: Array = room.talk_choices[0] if not room.talk_choices.is_empty() else []
		expect(top.size() == 3 and str(top[0]) == tr("✦ 부탁 들어주기") and str(top[2]) == "request", "her request is the first choice, marked as a request")
		var ask: Array = Quests.lines_of(Quests.by_id(str(api.token), "haneul_stars"), "ask")
		var asked := false
		for i in 30:
			if not is_instance_valid(room.talk_box): break
			if room.talk_lines == ask: asked = true
			room.advance_talk()
			await process_frame
		expect(not asked and str(Quests.by_id(str(api.token), "haneul_stars").state) == "available" and str((await talk("stargazer"))[0]) == "✦ 부탁 들어주기", "E through her talk picks her own choice, not the request")
		room.close_talk()
	Engine.remove_meta("interior_hour")
	room.queue_free()
	await create_timer(0.5).timeout

func shards() -> int:
	var me: Dictionary = await api.request("/v1/me")
	return int(me.data.shards) if me.ok else -1

func run() -> void:
	api = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = url
	var name := "quester_"+str(Time.get_ticks_msec()%1000000)
	var signup: Dictionary = await api.post("/v1/auth/register", {"username":name, "password":PASSWORD})
	expect(signup.ok, "a new account")
	if not signup.ok:
		quit(1)
		return
	api.token = signup.data.token

	# The definitions: the server's list and the client's words agree, every line is translated.
	var first := await refresh()
	var ids: Array = first.get("list", []).map(func(q): return str(q.id))
	expect(ids.size() == 19 and ids == Quests.BOOK.keys(), "the server's requests and the client's words are the same nineteen (%s)" % ", ".join(ids))
	var catalog = JSON.parse_string(FileAccess.get_file_as_string("res://i18n/strings.json"))
	var untranslated: Array = []
	for id in Quests.BOOK:
		var book: Dictionary = Quests.BOOK[id]
		for key in ["title", "accepted", "remind", "goal", "already"]:
			if book.has(key) and not catalog.strings.has(str(book[key])): untranslated.append(book[key])
		for key in ["ask", "thanks", "reply"]:
			for line in book.get(key, []):
				if not catalog.strings.has(str(line)): untranslated.append(line)
	expect(untranslated.is_empty(), "every request's words have English and Chinese (%s)" % str(untranslated))
	var total := 0
	for q in first.get("list", []): total += int(q.stars)
	expect(total >= 75 and total <= 85 and first.list.all(func(q): return int(q.stars) >= 3 and int(q.stars) <= 8), "rewards are 3-8 each, %d in all (about two cheap crafts)" % total)

	# Closed while the opening chapter runs, and after it until 모카's letter is read.
	expect(not first.get("unlocked", true) and (await talk("regular")).is_empty(), "no request while the chapter runs")
	await api.post("/v1/story/step", api.mutation({"action":"read_letter"}))
	await api.post("/v1/story/step", api.mutation({"action":"accept"}))
	var me: Dictionary = (await api.request("/v1/me")).data
	var chair: Dictionary = me.objects.filter(func(o): return str(o.name) == "환영의 나무 의자")[0]
	var chapter: Dictionary = await api.post("/v1/story/gift", api.mutation({"object_id":chair.id, "version":chair.version}))
	expect(chapter.ok, "the chapter's gift is given")
	expect(not (await refresh()).get("unlocked", true) and (await talk("naru")).is_empty(), "still closed while 모카's letter waits")
	await api.post("/v1/letters/read", api.mutation({"ids":[chapter.data.letters[0].id]}))
	var opened := await refresh()
	expect(opened.get("unlocked", false) and opened.list.all(func(q): return str(q.state) == "available"), "the letter read, every request is offered")
	await brief_and_names(opened)
	await inside_the_observatory()

	# A lamp for 노을 and a teddy bear for 콩이 (the offline demo crafts), and the turnips' and the
	# carrots' seeds go in first (they take 90 and 120 s).
	var lamp_id := await craft("등불")
	expect(not lamp_id.is_empty(), "a lamp was made")
	var toy_id := await craft("곰인형")
	expect(not toy_id.is_empty(), "a teddy bear was made")
	expect(not (await act("plant", {"plot":0, "item":"turnip"})).is_empty() and not (await act("water", {"plot":0})).is_empty(), "turnip seeds planted and watered")
	expect(not (await act("plant", {"plot":1, "item":"carrot"})).is_empty() and not (await act("water", {"plot":1})).is_empty(), "carrot seeds planted and watered")
	var sown := Time.get_ticks_msec()
	var start := await shards()

	var paid := 0
	for id in Quests.BOOK:
		var entry: Dictionary = Quests.by_id(str(api.token), id)
		var npc := str(entry.npc)
		var stars := int(entry.stars)
		# Offer: the request's words, "다음에요" first, "맡겨 줘요 · 별씨 +N".
		expect(await open(npc, "✦ 부탁 들어주기"), "%s: %s offers the request" % [id, Quests.npc_name(npc)])
		expect(box.lines == Quests.lines_of(entry, "ask") and str(box.choices[0][0]) == "다음에요", "%s: the request's words, 'not now' first" % id)
		expect(await press("맡겨 줘요 · 별씨 +%d" % stars), "%s: taken (맡겨 줘요 · 별씨 +%d)" % [id, stars])
		expect(effects.back()[0] == "accepted" and str(Quests.by_id(str(api.token), id).state) == "active", "%s: under way on the server" % id)
		# Not done yet: the resident reminds (and does not take it).
		expect(await open(npc, "부탁 이야기"), "%s: 부탁 이야기 while it is under way" % id)
		expect(str(box.lines[0]) == Quests.remind_text(entry, 0), "%s: the reminder says how far it is" % id)
		var before := await shards()
		var reply: Dictionary = await api.post("/v1/quests/%s/complete" % id, api.mutation())
		expect(not reply.ok and str(reply.error) == "quest_not_ready", "%s: the server refuses an early hand-over" % id)
		# Done the player's way.
		match id:
			"moka_pie":
				for tree in ["apple_tree_01", "apple_tree_02"]:
					var shaken := await act("shake", {"node":tree})
					for fruit in shaken.get("reward", {}).get("drops", []):
						if str(fruit) != "apple" or await bag_count(["apple"]) >= 3: continue
						await act("pickup", {"node":tree, "item":fruit})
					await create_timer(0.7).timeout
			"naru_islands":
				for island in ["square", "fields", "lighthouse"]:
					var seen: Dictionary = await api.post("/v1/quests/naru_islands/progress", api.mutation({"place":island}))
					expect(seen.ok, "naru_islands: the %s signpost counted" % island)
					await create_timer(3.2).timeout
			"sora_outfit":
				var look: Dictionary = (await api.request("/v1/me")).data.profile
				var avatar: Dictionary = look.avatar.duplicate()
				avatar["coat"] = "#3a6ea5"
				expect((await api.post("/v1/profile", api.mutation({"version":look.version, "avatar":avatar}))).ok, "sora_outfit: a new outfit saved")
			"moru_soup":
				for node in ["mushroom_01", "mushroom_02", "mushroom_03"]:
					if await bag_count(["mushroom", "gold_mushroom"]) >= 2: break
					await act("gather", {"node":node})
					await create_timer(0.7).timeout
			"haeru_fish":
				for attempt in 4:
					if await bag_count(["mackerel", "puffer", "squid", "tuna", "silverfish"]) >= 1: break
					var cast := await act("cast", {"spot":"sea"})
					var bite := float(cast.get("fishing", {}).get("bite_at", 0))-float(cast.get("server_time", 0))
					await create_timer(maxf(0.1, bite+0.3)).timeout
					var hooked := await act("reel")
					if hooked.get("reward", {}).get("kind", "") != "hooked": continue
					await create_timer(float(hooked.get("fishing", {}).get("fight_min", 3.5))+0.4).timeout
					await act("reel", {"outcome":"landed"})
			"daon_gift":
				var bag: Array = (await api.request("/v1/me")).data.objects.filter(func(o): return str(o.state) == "inventory" and not str(o.id) in [lamp_id, toy_id])
				var gift: Dictionary = await api.post("/v1/npcs/postman/gift", api.mutation({"object_id":bag[0].id, "version":bag[0].version}))
				expect(gift.ok, "daon_gift: a gift for 다온 (%s)" % str(bag[0].name))
			"hangyeol_turnips", "dure_carrots":
				# Sown before the first request; ripe 90 s (turnips) or 120 s (carrots) after watering.
				var plot := 0 if id == "hangyeol_turnips" else 1
				var left := (92.0 if plot == 0 else 122.0)-(Time.get_ticks_msec()-sown)*0.001
				if left > 0.0:
					print("  %s grow (%.0f s more)" % ["turnips" if plot == 0 else "carrots", left])
					await create_timer(left).timeout
				expect(not (await act("harvest", {"plot":plot})).is_empty(), "%s: harvested" % id)
			"boram_catch":
				# A pond fish and a sea fish are always two kinds.
				expect(await catch_one("pond") and await catch_one("sea"), "boram_catch: a pond fish and a sea fish caught")
			"miso_flowers":
				for node in ["flower_01", "flower_02", "flower_03", "flower_04"]:
					if await bag_count(["flower"]) >= 3: break
					await act("gather", {"node":node})
					await create_timer(0.7).timeout
			"yunjae_regards":
				# 가람's own talk offers to pass the regards on (before his own request).
				expect(await open("poet", "✦ 윤재의 안부 전하기"), "yunjae_regards: 가람 is offered 윤재's regards")
				expect(box.lines == Quests.lines_of(entry, "reply") and effects.back()[0] == "progress", "yunjae_regards: 가람 answers")
			"haneul_stars", "saebyeok_walk":
				var place := "observatory" if id == "haneul_stars" else "lighthouse_pier"
				var by_day := await local_post("/v1/quests/%s/progress" % id, {"place":place}, 13)
				expect(not by_day.ok and str(by_day.error) == "quest_not_night", "%s: by day it does not count" % id)
				var by_night := await local_post("/v1/quests/%s/progress" % id, {"place":place}, 22)
				expect(by_night.ok, "%s: at night it counts (%s)" % [id, str(by_night.error)])
			"chorok_herbs":
				await act("gather", {"item":"herb"})
				await create_timer(0.7).timeout
				for node in ["herb_01", "herb_02"]:
					if await bag_count(["herb"]) >= 3: break
					await act("gather", {"node":node})
					await create_timer(0.7).timeout
			"bau_pinecones":
				for tree in ["pine_tree_01", "pine_tree_02"]:
					var shaken := await act("shake", {"node":tree})
					for fruit in shaken.get("reward", {}).get("drops", []):
						if str(fruit) != "pinecone" or await bag_count(["pinecone"]) >= 3: continue
						await act("pickup", {"node":tree, "item":fruit})
					await create_timer(0.7).timeout
			"danbi_home":
				var bear: Dictionary = (await api.request("/v1/me")).data.objects.filter(func(o): return str(o.id) == toy_id)[0]
				var home: Dictionary = await api.post("/v1/objects/%s/placement" % toy_id, api.mutation({"version":bear.version, "room":"home", "x":1.0, "z":-1.0}))
				expect(home.ok, "danbi_home: the teddy bear is set down at home (%s)" % str(home.get("error", "")))
			"kongi_toy":
				var bear: Dictionary = (await api.request("/v1/me")).data.objects.filter(func(o): return str(o.id) == toy_id)[0]
				var back: Dictionary = await api.post("/v1/objects/%s/placement" % toy_id, api.mutation({"version":bear.version, "action":"retrieve"}))
				var given: Dictionary = await api.post("/v1/npcs/kid/gift", api.mutation({"object_id":toy_id, "version":int(back.get("data", {}).get("version", 0))}))
				expect(given.ok, "kongi_toy: the teddy bear for 콩이 (%s)" % str(given.get("error", "")))
			"garam_lookout":
				expect((await api.post("/v1/quests/garam_lookout/progress", api.mutation({"place":"lookout"}))).ok, "garam_lookout: the lookout counted")
			"noeul_light":
				var lamp: Dictionary = (await api.request("/v1/me")).data.objects.filter(func(o): return str(o.id) == lamp_id)[0]
				var placed: Dictionary = await api.post("/v1/objects/"+lamp_id, api.mutation({"version":lamp.version, "action":"place", "x":24.0, "z":18.0}))
				expect(placed.ok, "noeul_light: the lamp is set down in the village (%s)" % str(placed.get("error", "")))
		var now := await refresh()
		var ready: Dictionary = Quests.by_id(str(api.token), id)
		expect(str(ready.get("state", "")) == "ready", "%s: done the player's way (%d/%d)" % [id, int(ready.get("have", 0)), int(ready.get("need", 0))])
		# The hand-over: the thanks, the stars once.
		var label := "✦ 부탁한 것 건네기" if str(entry.kind) == "bring" else "✦ 부탁을 마쳤어요"
		expect(await open(npc, label), "%s: '%s'" % [id, label])
		expect(box.lines == Quests.lines_of(entry, "thanks"), "%s: the resident's thanks" % id)
		var last: Array = effects.back()
		expect(last[0] == "completed" and int(last[1].get("stars", -1)) == stars, "%s: the reward of %d starseeds" % [id, stars])
		var after := await shards()
		expect(after == before+stars and int(last[1].get("shards", -1)) == after, "%s: the counter goes up by %d, once" % [id, stars])
		paid += stars
		var again: Dictionary = await api.post("/v1/quests/%s/complete" % id, api.mutation())
		expect(not again.ok and str(again.error) == "quest_already_done" and await shards() == after, "%s: a second hand-over pays nothing" % id)
		expect((await talk(npc)).is_empty(), "%s: the resident has no request left" % id)
		var wants_letter := bool(entry.get("letter", false))
		var letters: Array = last[1].get("letters", [])
		expect(letters.size() == (1 if wants_letter else 0), "%s: %s" % [id, "a thank-you letter" if wants_letter else "no letter"])
		if wants_letter and not letters.is_empty():
			var page: Array = NpcGifts.letter_lines(letters[0])
			expect(str(page[0]).contains(Quests.npc_name(npc, 12.0)) and str(page[0]).contains(str(NpcGifts.QUEST_LETTERS[npc][0])), "%s: the letter reads in the mailbox" % id)
	expect(await shards() == start+paid and paid == total, "all nineteen paid %d starseeds in all" % paid)
	var ledger: Dictionary = await refresh()
	expect(ledger.list.all(func(q): return str(q.state) == "done"), "every request is done")
	print("QUEST_CHECK " + ("FAILED" if failed else "OK"))
	quit(1 if failed else 0)
