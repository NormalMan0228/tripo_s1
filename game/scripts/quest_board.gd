extends Node
## The village notice board's "오늘의 부탁" (server/quest_board.py, docs/design/QUEST_BOARD_API.md):
## five of the residents' requests are pinned each day (KST midnight); the player takes up to three,
## does them and hands them in at the board, and the resident writes a thank-you letter.
## Everything is feature-detected: while the server has no /v1/quest_board (404), the board stays
## the read-only notice it always was and no talk gets a new choice.
##
## The words come from quests.gd (BOOK titles, goals, reminders) and so do the effects (reward_burst
## stars over the walker, reward_fly into the counter, the quest sounds), so a board request feels
## like a resident's own.
##   QuestBoard.fetch(api)                 # the board ({} when the server has none), kept per login
##   QuestBoard.summary(board)             # one line for the notice board's page
##   QuestBoard.open(app, board[, api])    # the board window (rows: accept / 길 안내 / 완료하기)
##   QuestBoard.watch(field, app)          # the village side (this node): visits, ready moments, guide
##   QuestBoard.entered_room(room, id)     # a visit request whose place is a room (studio.gd)
##   QuestBoard.talk_choice(api, npc, say, done)  # "✦ 게시판 부탁 전하기" for a talk request
const QuestsLib := preload("res://scripts/quests.gd")
const RpgUi := preload("res://scripts/rpg_ui.gd")
const Fx := preload("res://scripts/fx.gd")
const Town := preload("res://scripts/town.gd")
const Guide := preload("res://scripts/guide.gd")
const NpcGifts := preload("res://scripts/npc_gifts.gd")

const STAR_ICON := "res://assets/starseed.svg"
## Release switch: false leaves the notice board read-only, no "전하기" talk choice and no village
## watcher, exactly as before the board (fetch() answers {} without asking the server).
const ENABLED := true
## Guide keys of a board request ("quest_board:<id>"); story.gd leaves keys it does not know alone.
const GUIDE_KEY := "quest_board:"
const META := "quest_board"
## Errors after which the board is read again (the day turned, the post is gone).
const REFETCH := ["quest_board_expired", "quest_not_found", "quest_board_not_offered", "quest_not_active", "quest_not_ready", "quest_already_done"]

static func t(text: String) -> String:
	return TranslationServer.translate(text)

# ------------------------------------------------------------------ the server's board (kept per login)

## The kept board for this login ({} when unknown or missing).
static func cached(token: String) -> Dictionary:
	var kept: Dictionary = Engine.get_meta(META, {})
	if token.is_empty() or str(kept.get("token", "")) != token: return {}
	return kept.get("board", {})

## False once the server answered 404 for this login (no board feature on it).
static func missing(token: String) -> bool:
	var kept: Dictionary = Engine.get_meta(META, {})
	return not token.is_empty() and str(kept.get("token", "")) == token and bool(kept.get("missing", false))

static func remember(board, token: String) -> void:
	if board is Dictionary and board.get("list") is Array: Engine.set_meta(META, {"token":token, "board":board})

## GET /v1/quest_board: the board, or {} when the server has none (404) or cannot be reached.
static func fetch(api: Node) -> Dictionary:
	if not ENABLED: return {}
	if api == null or str(api.token).is_empty(): return {}
	var token := str(api.token)
	if missing(token): return {}
	var reply: Dictionary = await api.request("/v1/quest_board")
	if reply.ok and reply.data.get("board") is Dictionary:
		remember(reply.data.board, token)
		return reply.data.board
	# No such route (an older server): remembered, so the village does not keep asking.
	if int(reply.get("status", 0)) in [404, 405]: Engine.set_meta(META, {"token":token, "missing":true})
	return {}

## A POST, sent again once with the same body (same request_id) when the answer was lost.
static func send(api: Node, path: String, body: Dictionary) -> Dictionary:
	var reply: Dictionary = await api.post(path, body)
	if not reply.ok and str(reply.get("error", "")) == "connection_failed": reply = await api.post(path, body)
	return reply

static func path_of(item: Dictionary, action: String, board: Dictionary) -> String:
	return "/v1/quest_board/%s/%s/%s" % [str(item.get("day", board.get("day", ""))).uri_encode(), str(item.get("id", "")).uri_encode(), action]

# ------------------------------------------------------------------ words

static func title_of(item: Dictionary) -> String:
	var title := QuestsLib.title_of(item)
	return title if not title.is_empty() else str(item.get("id", ""))

## The notice board page's line: how many are pinned and how many the player may still take.
static func summary(board: Dictionary) -> String:
	if not bool(board.get("unlocked", false)): return t("✦ 오늘의 부탁 · 마을 일을 먼저 마치면 받을 수 있어요")
	var limits: Dictionary = board.get("limits", {})
	return t("✦ 오늘의 부탁 %d개 · 받은 부탁 %d/%d · 끝낸 부탁 %d/%d") % [(board.get("list", []) as Array).size(),
		int(board.get("accepted", 0)), int(limits.get("accept", 3)), int(board.get("completed", 0)), int(limits.get("complete", 3))]

## The request's state now: the bag and the look count at once in the village (quests.gd have_of).
static func state_of(app: Node, item: Dictionary) -> String:
	var state := str(item.get("state", ""))
	if not state in ["active", "ready"]: return state
	return "ready" if have_of(app, item) >= int(item.get("need", 1)) else "active"

static func have_of(app: Node, item: Dictionary) -> int:
	var quests: Node = QuestsLib.village_of(app) if is_instance_valid(app) and app.has_method("chapter") else null
	if quests != null and quests.has_method("have_of"): return quests.have_of(item)
	return mini(int(item.get("have", 0)), int(item.get("need", 1)))

static func detail_of(app: Node, item: Dictionary, state: String) -> String:
	var who := QuestsLib.npc_name(str(item.get("npc", "")))
	match state:
		"available": return who + " · " + t("받으면 별씨를 받을 수 있어요")
		"active":
			if not QuestsLib.BOOK.has(str(item.get("id", ""))): return who + " · " + t("진행 중")
			return who + " · " + QuestsLib.goal_text(item, have_of(app, item), false)
		"ready": return who + " · " + t("다 됐어요! 게시판에서 완료하기")
		"done": return who + " · " + t("완료 · 감사 편지가 우편함에 왔어요")
		"locked": return who + " · " + t("아직 받을 수 없어요")
	return who

static func error_line(code: String) -> String:
	match code:
		"quest_board_daily_limit": return t("오늘은 더 받을 수 없어요 · 자정에 새 부탁이 붙어요")
		"quest_board_expired", "quest_board_not_offered", "quest_not_found": return t("게시물이 바뀌었어요. 새 부탁을 확인해 보세요.")
		"quests_locked": return t("아직 게시판 부탁을 받을 수 없어요. 마을 일을 먼저 마쳐 보세요.")
		"quest_own_village_only": return t("게시판 부탁은 내 마을에서만 할 수 있어요.")
		"quest_not_ready": return t("앗, 아직 다 되지 않았어요.")
		"quest_already_done": return t("이미 끝낸 부탁이에요.")
		"quest_not_night": return t("밤에만 할 수 있는 부탁이에요.")
		"quest_too_fast": return t("조금 천천히 둘러봐요.")
	return t("지금은 게시판을 쓸 수 없어요. 잠시 뒤 다시 해 보세요.")

# ------------------------------------------------------------------ the board window

static func visiting(app: Node) -> bool:
	return is_instance_valid(app) and app.get("social") != null and app.social.has_method("visiting") and app.social.visiting()

## The board window (a shared parchment window, main.gd modal_card): the day's posts, each with its
## resident, goal, reward and the one thing to do with it. Rebuilt in place after each answer.
static func open(app: Node, board: Dictionary, api: Node = null) -> Control:
	if not is_instance_valid(app) or not app.has_method("modal_card"): return null
	if api == null: api = app.api
	var body: VBoxContainer = app.modal_card(t("오늘의 부탁"))
	var modal: Control = app.village_modal
	modal.set_meta("quest_board", true)
	RpgUi.sfx("page", -10.0)
	var head := RpgUi.caption(body, "", 13)
	head.name = "BoardSummary"
	var list := VBoxContainer.new()
	list.name = "BoardList"
	list.add_theme_constant_override("separation", 4)
	body.add_child(list)
	var foot := RpgUi.caption(body, t("매일 자정에 새 부탁이 붙어요. 끝내지 못한 부탁은 자정에 내려가요."), 12)
	foot.name = "BoardFoot"
	var busy := [false]
	var state := {"board":board}
	var fill := func(again: Callable, popped: String) -> void:
		if not is_instance_valid(list): return
		var now: Dictionary = state.board
		head.text = summary(now)
		for child in list.get_children():
			list.remove_child(child)
			child.queue_free()
		var items: Array = now.get("list", [])
		if items.is_empty(): RpgUi.caption(list, t("오늘은 게시판이 비어 있어요."), 14)
		var away := visiting(app)
		var can_take := bool(now.get("unlocked", false)) and int(now.get("remaining_accepts", 0)) > 0 and not away
		for entry in items:
			var item: Dictionary = entry
			var id := str(item.get("id", ""))
			var shown_state := state_of(app, item)
			var line := HBoxContainer.new()
			line.name = "Board_" + id
			line.add_theme_constant_override("separation", 12)
			line.custom_minimum_size = Vector2(650, 48)
			list.add_child(line)
			var mark := RpgUi.label(line, {"ready":"?", "active":"▸", "available":"!", "done":"✓", "locked":"·"}.get(shown_state, "·"), 22,
				{"ready":Color("9fe3ff"), "available":Color("ffd84a"), "done":Color("a6d98a")}.get(shown_state, RpgUi.GOLD))
			mark.custom_minimum_size.x = 22
			mark.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			var words := VBoxContainer.new()
			words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			words.add_theme_constant_override("separation", 0)
			line.add_child(words)
			var title := RpgUi.label(words, title_of(item) + ("  ☾" if bool(item.get("night", false)) else ""), 17, RpgUi.PAPER_INK, false)
			title.add_theme_font_override("font", RpgUi.FONT_STRONG)
			RpgUi.caption(words, detail_of(app, item, shown_state), 13)
			var reward := HBoxContainer.new()
			reward.add_theme_constant_override("separation", 3)
			line.add_child(reward)
			reward.add_child(RpgUi.icon(STAR_ICON, 20))
			var stars := int(item.get("stars", 0))
			RpgUi.numbers(RpgUi.label(reward, ("+%d" % stars) if shown_state != "done" else "✓ %d" % stars, 16, Color("8a5a12"), false), 16).vertical_alignment = VERTICAL_ALIGNMENT_CENTER
			var button: Button = null
			match shown_state:
				"available":
					button = app.button(line, t("받기"), func():
						if busy[0]: return
						busy[0] = true
						await take(app, api, item, state, again)
						busy[0] = false, "gold")
					button.disabled = not can_take
				"active":
					button = app.button(line, t("길 안내"), func():
						app.close_village_modal()
						guide(app, item))
				"ready":
					button = app.button(line, t("완료하기"), func():
						if busy[0]: return
						busy[0] = true
						await finish(app, api, item, state, again)
						busy[0] = false, "gold")
					button.disabled = away
				_:
					var gap := Control.new()
					gap.custom_minimum_size.x = 96
					line.add_child(gap)
			if button != null:
				button.name = "BoardAction"
				button.custom_minimum_size.x = 96
			# The post just taken pops in place (the one effect of it inside the window).
			if id == popped: RpgUi.pop_in(line, 0.3, 0.85)
	fill.call(fill, "")
	return modal

## "받기": the server takes it; the row turns into a goal, a star pops over the walker.
static func take(app: Node, api: Node, item: Dictionary, state: Dictionary, again: Callable) -> void:
	var board: Dictionary = state.board
	var reply: Dictionary = await send(api, path_of(item, "accept", board), api.mutation({}))
	if not is_instance_valid(app): return
	if not reply.ok:
		await refused(app, api, str(reply.get("error", "")), state, again)
		return
	var fresh = reply.data.get("board")
	if fresh is Dictionary and fresh.get("list") is Array:
		state.board = fresh
		remember(fresh, str(api.token))
	var taken: Dictionary = reply.data.get("quest", item)
	# The accept fanfare stands in for the toast's chime.
	RpgUi.sfx("quest_accept", -6.0)
	RpgUi.hush_toast()
	app.message(t("새 게시판 부탁 · %s") % title_of(taken))
	if is_instance_valid(app.get("player")) and app.get("world") != null:
		Fx.bubble(app.world, app.player.global_position + Vector3(0, 2.2, 0), "star")
	again.call(again, str(taken.get("id", item.get("id", ""))))

## "완료하기": the hand-in. The window closes on the moment: the star burst over the walker, the
## stars flying into the counter, the toast, and the resident's letter note after it.
static func finish(app: Node, api: Node, item: Dictionary, state: Dictionary, again: Callable) -> void:
	var reply: Dictionary = await send(api, path_of(item, "complete", state.board), api.mutation({}))
	if not is_instance_valid(app): return
	if not reply.ok:
		await refused(app, api, str(reply.get("error", "")), state, again)
		return
	var data: Dictionary = reply.data
	var fresh = data.get("board")
	if fresh is Dictionary and fresh.get("list") is Array: remember(fresh, str(api.token))
	var stars := int(data.get("stars", 0))
	var total := int(data.get("shards", app.me.get("shards", 0) if app.get("me") is Dictionary else 0))
	if app.get("me") is Dictionary: app.me["shards"] = total
	if data.get("homestead") is Dictionary and data.homestead.has("version") and is_instance_valid(app.get("life")) and app.life.has_method("accept"): app.life.accept(data.homestead)
	app.close_village_modal(false)
	var at: Vector3 = app.player.global_position if is_instance_valid(app.get("player")) else Vector3.ZERO
	if app.get("world") != null: QuestsLib.reward_burst(app, at, stars, false)
	QuestsLib.reward_fly(app, at, stars, total)
	RpgUi.sfx("quest_complete", -6.0)
	RpgUi.hush_toast()
	app.message(t("게시판 부탁 완료 · %s · %s") % [title_of(item), QuestsLib.stars_text(stars)] if stars > 0 else t("게시판 부탁 완료 · %s") % title_of(item))
	var note := NpcGifts.letters_note(data)
	if not note.is_empty() and app.is_inside_tree(): app.get_tree().create_timer(3.2).timeout.connect(func(): if is_instance_valid(app): letter_arrived(app, note))

## A refusal: a deny note and why; the board is read again when it changed under the player.
static func refused(app: Node, api: Node, code: String, state: Dictionary, again: Callable) -> void:
	RpgUi.sfx("deny", -6.0)
	app.message(error_line(code), "warn")
	if code in REFETCH or code == "quest_board_daily_limit":
		var fresh := await fetch(api)
		if not fresh.is_empty() and is_instance_valid(app):
			state.board = fresh
			again.call(again, "")

## A field object's spot in the world ("mailbox", "notice"), Vector3.INF when there is none.
static func object_at(app: Node, id: String) -> Vector3:
	var quests: Node = QuestsLib.village_of(app) if is_instance_valid(app) and app.has_method("chapter") else null
	var field: Node = quests.story.field_module() if quests != null and quests.get("story") != null else null
	if field == null or not field.has_method("object"): return Vector3.INF
	var entry: Dictionary = field.object(id)
	return entry.root.global_position if entry.get("root") is Node3D and is_instance_valid(entry.root) and entry.root.is_inside_tree() else Vector3.INF

## The resident's letter is in the mailbox: the flap at the mailbox and the notify chime, then the note.
static func letter_arrived(app: Node, note: String) -> void:
	Fx.sound(app, "field/flap", object_at(app, "mailbox"), 1.0, -6.0)
	RpgUi.sfx("notify", -8.0)
	app.message(note)

# ------------------------------------------------------------------ the route guide

## Where a board request leads now ({"at","name","key"}), with the quests module's helpers; a ready
## request leads back to the notice board.
static func goal_of(app: Node, item: Dictionary) -> Dictionary:
	var quests: Node = QuestsLib.village_of(app)
	if quests == null: return {}
	var id := str(item.get("id", ""))
	var key := GUIDE_KEY + id
	var kind := str(item.get("kind", ""))
	if state_of(app, item) == "ready":
		var field: Node = quests.story.field_module() if quests.get("story") != null else null
		for entry in field.objects if field != null else []:
			if str(entry.kind) == "notice": return {"at":entry.at, "name":t("마을 게시판"), "key":key}
		return {}
	var place := str(QuestsLib.BOOK.get(id, {}).get("place", ""))
	if kind == "gift": return quests.npc_goal(str(item.get("to", item.get("npc", ""))), key)
	if kind == "talk":
		var places: Array = item.get("places", [])
		return quests.npc_goal(str(places[0]), key) if not places.is_empty() else {}
	if kind == "visit":
		for spot in quests.spots_of(item):
			if not str(spot.place) in item.get("visited", []): return {"at":spot.at, "name":str(spot.name), "key":key}
		for spot in item.get("places", []):
			var where := str(QuestsLib.VISIT_SPOTS.get(str(spot), ""))
			if where.begins_with("room:") and not str(spot) in item.get("visited", []):
				var door := Town.door_for(where.trim_prefix("room:"))
				if not door.is_empty(): return {"at":door.at, "name":t(door.title), "key":key}
		return {}
	if place.begins_with("npc:"): return quests.npc_goal(place.trim_prefix("npc:"), key)
	if place.begins_with("forage:"): return quests.forage_goal(place.trim_prefix("forage:"), key)
	if place.begins_with("tree:"): return quests.tree_goal(place.trim_prefix("tree:"), key)
	match place:
		"apple", "sea", "pond", "herb", "lookout", "farm":
			var spot := Guide.place(place)
			return {"at":spot.at, "name":t(spot.title), "key":key} if not spot.is_empty() else {}
		"home": return {"at":Town.HOME_DOOR, "name":t("나의 집"), "key":key}
		"": return quests.npc_goal(str(item.get("npc", "")), key)
	return {}

## "길 안내": the beacon to the goal (this island's signpost first when it is on another island);
## a goal with no place says what to do instead.
static func guide(app: Node, item: Dictionary) -> void:
	var goal := goal_of(app, item)
	var watcher := watcher_of(app)
	if goal.is_empty():
		app.message(t("빛나는 물건을 마을에 놓아 주세요 · I 가방 또는 C 공방") if str(item.get("kind", "")) == "light" else QuestsLib.remind_text(item, have_of(app, item)))
		return
	if watcher != null: watcher.follow = str(item.get("id", ""))
	aim(app, goal, false)

static func aim(app: Node, goal: Dictionary, quiet: bool) -> void:
	var story: Node = app.chapter() if app.has_method("chapter") else null
	var guide_node: Node = story.guide_node() if story != null else null
	if guide_node == null: return
	var here: String = story.island_of(story.walker_at())
	var there: String = story.island_of(goal.at)
	if here != there:
		var sign: Dictionary = story.signpost(here)
		if not sign.is_empty(): goal = {"at":sign.at, "name":t("이정표 · %s") % t(QuestsLib.ISLANDS.get(there, "")), "key":goal.key, "hop":there}
	guide_node.set_target(goal, quiet)

static func watcher_of(app: Node) -> Node:
	return app.get_meta("quest_board_watch") if is_instance_valid(app) and app.has_meta("quest_board_watch") and is_instance_valid(app.get_meta("quest_board_watch")) else null

# ------------------------------------------------------------------ rooms and talks

## A room was entered (studio.gd show_story): a board visit request whose place is this room counts.
static func entered_room(room: Node, room_id: String) -> void:
	if not ENABLED or not is_instance_valid(room) or room.get("api") == null or bool(room.get("visiting")): return
	var api: Node = room.api
	var board := cached(str(api.token))
	for entry in board.get("list", []):
		var item: Dictionary = entry
		if str(item.get("kind", "")) != "visit" or str(item.get("state", "")) != "active": continue
		if bool(item.get("night", false)) and not QuestsLib.night_now(): continue
		for place in item.get("places", []):
			if str(QuestsLib.VISIT_SPOTS.get(str(place), "")) != "room:" + room_id or str(place) in item.get("visited", []): continue
			var reply: Dictionary = await send(api, path_of(item, "progress", board), api.mutation({"place":str(place)}))
			if not reply.ok or not is_instance_valid(room): return
			remember(reply.data.get("board"), str(api.token))
			if str(reply.data.get("quest", {}).get("state", "")) == "ready" and room.has_method("message"):
				RpgUi.sfx("quest_ready", -6.0)
				room.message(t("게시판 부탁 다 됐어요! 게시판에서 완료하기"))
			return

## The talk choice for a board request that asks to pass a word to `npc` ([] when none):
## say(lines, choices) shows the resident's reply; done(reply) is the caller's pop.
static func talk_choice(api: Node, npc: String, say: Callable, done: Callable) -> Array:
	if not ENABLED or api == null: return []
	var board := cached(str(api.token))
	if not bool(board.get("unlocked", false)): return []
	for entry in board.get("list", []):
		var item: Dictionary = entry
		if str(item.get("kind", "")) != "talk" or str(item.get("state", "")) != "active": continue
		if not npc in item.get("places", []) or npc in item.get("visited", []): continue
		return [t("✦ 게시판 부탁 전하기"), func():
			var reply: Dictionary = await send(api, path_of(item, "progress", board), api.mutation({"place":npc}))
			if not reply.ok:
				say.call([error_line(str(reply.get("error", "")))], [])
				return
			remember(reply.data.get("board"), str(api.token))
			var words: Array = QuestsLib.BOOK.get(str(item.get("id", "")), {}).get("reply", ["전해 줘서 고마워요!"])
			if done.is_valid(): done.call(reply.data)
			say.call(words.map(func(line): return t(str(line))), [[t("게시판에 알릴게요"), Callable()]])]
	return []

# ------------------------------------------------------------------ the village (this node)

var app: Node
var tick := 0.0
var reporting := false
var report_after := 0.0
var refetching := false
## Last seen state per post (the "다 됐어요" moment) and the followed post's id.
var seen := {}
var follow := ""
var hooked: Node = null

## Starts the village side under the field objects (field_objects.gd setup).
static func watch(field: Node, main: Node) -> void:
	if not ENABLED or not is_instance_valid(main) or main.get("api") == null: return
	var node = load("res://scripts/quest_board.gd").new()
	node.name = "QuestBoardWatch"
	node.app = main
	main.set_meta("quest_board_watch", node)
	field.add_child(node)
	node.start()

func start() -> void:
	# load, not preload: shop_window.gd preloads this script.
	load("res://scripts/shop_window.gd").probe(app.api)
	if missing(token()): return
	var board := await fetch(app.api)
	for entry in board.get("list", []): seen[str(entry.get("id", ""))] = state_of(app, entry)

func token() -> String:
	return str(app.api.token) if is_instance_valid(app) and app.get("api") != null else ""

func _process(delta: float) -> void:
	tick -= delta
	if tick > 0.0: return
	tick = 1.0
	if not is_instance_valid(app) or str(app.get("screen")) != "village" or visiting(app): return
	var board := cached(token())
	if board.is_empty(): return
	# Midnight (KST) pins new posts: read them once the old ones expire.
	if float(board.get("resets_at", 0)) > 0.0 and Time.get_unix_time_from_system() > float(board.resets_at) + 2.0 and not refetching:
		refetching = true
		var old_day := str(board.get("day", ""))
		var fresh := await fetch(app.api)
		refetching = false
		if not fresh.is_empty() and str(fresh.get("day", "")) != old_day and is_instance_valid(app):
			Fx.sound(app, "field/pin", object_at(app, "notice"), 1.0, -6.0)
			app.message(t("마을 게시판에 새 부탁이 붙었어요"))
		return
	for entry in board.get("list", []):
		var id := str(entry.get("id", ""))
		var now := state_of(app, entry)
		if str(seen.get(id, "")) == "active" and now == "ready": became_ready(entry)
		seen[id] = now
	report_visits(board)
	steer(board)

## A board request is done: a word and a sparkle; the guide turns back to the board when it was on it.
func became_ready(item: Dictionary) -> void:
	RpgUi.sfx("quest_ready", -6.0)
	app.message(t("게시판 부탁 다 됐어요! 게시판에서 완료하기 · %s") % title_of(item))
	if is_instance_valid(app.get("player")):
		Fx.burst(app.world, app.player.global_position + Vector3(0, 1.8, 0), "sparkle", 12, Color(0,0,0,0), 0.35)
		Fx.bubble(app.world, app.player.global_position + Vector3(0, 2.2, 0), "star")
	if follow == str(item.get("id", "")):
		var goal := goal_of(app, item)
		if not goal.is_empty(): aim(app, goal, true)

## Standing at a board visit request's place (the lookout, the pier, a signpost) tells the server.
func report_visits(board: Dictionary) -> void:
	if reporting or Time.get_ticks_msec() * 0.001 < report_after: return
	var quests: Node = QuestsLib.village_of(app)
	if quests == null or quests.get("story") == null: return
	var here: Vector2 = quests.story.walker_at()
	for entry in board.get("list", []):
		var item: Dictionary = entry
		if str(item.get("kind", "")) != "visit" or str(item.get("state", "")) != "active": continue
		if bool(item.get("night", false)) and not QuestsLib.night_now(): continue
		for spot in quests.spots_of(item):
			if str(spot.place) in item.get("visited", []) or here.distance_to(spot.at) > float(spot.reach): continue
			reporting = true
			var reply: Dictionary = await send(app.api, path_of(item, "progress", board), app.api.mutation({"place":str(spot.place)}))
			reporting = false
			# The server wants three seconds between reports.
			report_after = Time.get_ticks_msec() * 0.001 + (3.2 if reply.ok else 6.0)
			if not reply.ok or not is_instance_valid(app): return
			remember(reply.data.get("board"), token())
			var now: Dictionary = reply.data.get("quest", {})
			if is_instance_valid(app.get("player")): Fx.burst(app.world, app.player.global_position + Vector3(0, 1.6, 0), "sparkle", 14, Color(0,0,0,0), 0.4)
			if str(now.get("state", "")) != "ready":
				RpgUi.sfx("star", -8.0)
				RpgUi.hush_toast()
				app.message(t("게시판 부탁 %d/%d · %s") % [int(now.get("have", 0)), int(now.get("need", 1)), str(spot.name)])
			return

## The followed request: after a signpost hop (the beacon reached this island's signpost: travel on)
## and when the beacon went out, the next leg is set again.
func steer(board: Dictionary) -> void:
	if follow.is_empty(): return
	var story: Node = app.chapter() if app.has_method("chapter") else null
	var guide_node: Node = story.guide_node() if story != null else null
	if guide_node == null: return
	if guide_node.has_signal("arrived") and hooked != guide_node:
		hooked = guide_node
		guide_node.arrived.connect(arrived)
	var item := {}
	for entry in board.get("list", []):
		if str(entry.get("id", "")) == follow: item = entry
	if item.is_empty() or not state_of(app, item) in ["active", "ready"]:
		follow = ""
		return
	# A beacon already lit (this request's or another's) or one the player put out stays as it is.
	if guide_node.active() or Guide.player_stopped: return
	var goal := goal_of(app, item)
	if goal.is_empty(): follow = ""
	elif story.walker_at().distance_to(goal.at) > 8.0: aim(app, goal, true)

## The beacon reached its spot: a signpost on the way travels to the goal's island.
func arrived(key: String) -> void:
	if not key.begins_with(GUIDE_KEY) or not is_instance_valid(app) or is_instance_valid(app.get("village_modal")): return
	var story: Node = app.chapter()
	var guide_node: Node = story.guide_node() if story != null else null
	if guide_node == null: return
	var there := str(guide_node.target.get("hop", ""))
	if there.is_empty(): return
	var here: String = story.island_of(story.walker_at())
	var sign: Dictionary = story.signpost(here)
	if not sign.is_empty() and here != there: story.field_module().use_signpost(sign, there)
