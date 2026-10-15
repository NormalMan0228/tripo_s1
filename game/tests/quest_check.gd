extends SceneTree
## Every resident's request (quests.gd words, server/quests.py rules) on the QA server, through the
## same conversation code the village and the rooms use (Quests.choice_for with a recording
## dialogue box): a new account finishes the opening chapter (the requests stay closed until
## 모카's letter is read), then each request is offered, taken, done the way a player does it
## (apples from trees, mushrooms, a sea fish, turnips grown, signposts, a new outfit, a gift, a
## lamp set out in the village) and handed over: the starseeds come once, the choice goes away,
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

func _initialize() -> void:
	call_deferred("run")
	create_timer(600).timeout.connect(func():
		push_error("Quest check exceeded 600 seconds")
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
	expect(ids.size() == 8 and ids == Quests.BOOK.keys(), "the server's requests and the client's words are the same eight (%s)" % ", ".join(ids))
	var catalog = JSON.parse_string(FileAccess.get_file_as_string("res://i18n/strings.json"))
	var untranslated: Array = []
	for id in Quests.BOOK:
		var book: Dictionary = Quests.BOOK[id]
		for key in ["title", "accepted", "remind", "goal"]:
			if not catalog.strings.has(str(book[key])): untranslated.append(book[key])
		for key in ["ask", "thanks"]:
			for line in book[key]:
				if not catalog.strings.has(str(line)): untranslated.append(line)
	expect(untranslated.is_empty(), "every request's words have English and Chinese (%s)" % str(untranslated))
	var total := 0
	for q in first.get("list", []): total += int(q.stars)
	expect(total >= 35 and total <= 60 and first.list.all(func(q): return int(q.stars) >= 5 and int(q.stars) <= 15), "rewards are 5-15 each, %d in all (about one craft)" % total)

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

	# A lamp for 노을 (the offline demo craft) and the turnips' seeds go in first (they take 90 s).
	var queued: Dictionary = await api.post("/v1/studio/jobs", api.mutation({"prompt":"등불", "geometry":"proxy", "designer":"fixture"}))
	var lamp_id := ""
	for i in 120:
		var job: Dictionary = await api.request("/v1/studio/jobs/"+str(queued.get("data", {}).get("id", "")))
		if job.ok and job.data.state == "awaiting_confirmation": await api.post("/v1/studio/jobs/%s/confirm" % job.data.id, api.mutation({"use_concept":false}))
		if job.ok and job.data.state == "ready":
			lamp_id = str(job.data.object_id)
			break
		await create_timer(0.5).timeout
	expect(not lamp_id.is_empty(), "a lamp was made")
	expect(not (await act("plant", {"plot":0, "item":"turnip"})).is_empty() and not (await act("water", {"plot":0})).is_empty(), "turnip seeds planted and watered")
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
				var bag: Array = (await api.request("/v1/me")).data.objects.filter(func(o): return str(o.state) == "inventory" and str(o.id) != lamp_id)
				var gift: Dictionary = await api.post("/v1/npcs/postman/gift", api.mutation({"object_id":bag[0].id, "version":bag[0].version}))
				expect(gift.ok, "daon_gift: a gift for 다온 (%s)" % str(bag[0].name))
			"hangyeol_turnips":
				# Sown before the first request; ripe 90 s after watering.
				var left := 92.0-(Time.get_ticks_msec()-sown)*0.001
				if left > 0.0:
					print("  turnips grow (%.0f s more)" % left)
					await create_timer(left).timeout
				expect(not (await act("harvest", {"plot":0})).is_empty(), "hangyeol_turnips: turnips harvested")
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
			expect(str(page[0]).contains(Quests.npc_name(npc)) and str(page[0]).contains(str(NpcGifts.QUEST_LETTERS[npc][0])), "%s: the letter reads in the mailbox" % id)
	expect(await shards() == start+paid and paid == total, "all eight paid %d starseeds in all" % paid)
	var ledger: Dictionary = await refresh()
	expect(ledger.list.all(func(q): return str(q.state) == "done"), "every request is done")
	print("QUEST_CHECK " + ("FAILED" if failed else "OK"))
	quit(1 if failed else 0)
