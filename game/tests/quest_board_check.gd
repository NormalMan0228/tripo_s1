extends SceneTree
## The notice board's "오늘의 부탁", the residents' event letters and the shops' window (#26, #81):
##   A. on the current QA server (no /v1/quest_board, no /v1/shops): the board stays read-only, the
##      mailbox opens, the shops are found missing and no talk gets a new choice;
##   B. with stubbed replies injected into the modules: the board's rows, "받기" posting the right
##      URL with a request_id, "완료하기" flying the stars into the counter, the accept limit, the
##      talk request's "전하기", event letters' words, a closed shop's reason with its buttons off,
##      an open shop's buy posting its version, and "가게 보기" once the shop is known.
const Main = preload("res://scripts/main.gd")
const QuestBoard = preload("res://scripts/quest_board.gd")
const ShopWindow = preload("res://scripts/shop_window.gd")
const NpcLetters = preload("res://scripts/npc_letters.gd")
const NpcGifts = preload("res://scripts/npc_gifts.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const Town = preload("res://scripts/town.gd")
const PASSWORD := "Board-check-pass-1"
var failed := false
var app: Node

## A stand-in for api.gd: canned replies by "GET /path" / "POST /path", every call recorded.
class StubApi extends Node:
	var token := ""
	var replies := {}
	var calls: Array = []
	var ids := 0
	func request(path: String, payload: Dictionary = {}, method := HTTPClient.METHOD_GET, _binary := false, _timeout := 12.0) -> Dictionary:
		await get_tree().process_frame
		var key := ("POST " if method == HTTPClient.METHOD_POST else "GET ") + path
		calls.append({"key":key, "body":payload})
		return replies.get(key, {"ok":false, "error":"Not Found", "status":404})
	func post(path: String, payload: Dictionary) -> Dictionary:
		return await request(path, payload, HTTPClient.METHOD_POST)
	func mutation(extra: Dictionary = {}) -> Dictionary:
		ids += 1
		return extra.merged({"request_id":"00000000-0000-4000-8000-%012d" % ids})
	func called(key: String) -> Dictionary:
		for call in calls:
			if call.key == key: return call
		return {}

func _initialize() -> void:
	call_deferred("run")
	create_timer(300).timeout.connect(func():
		push_error("Quest board check exceeded 300 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ") + description)
	if not value: failed = true

func wait_for(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return condition.call()

func texts(node: Node) -> String:
	var out := ""
	if not is_instance_valid(node): return out
	for label in node.find_children("*", "Label", true, false): out += (label as Label).text + "\n"
	return out

func buttons(node: Node) -> Array:
	var out: Array = []
	if not is_instance_valid(node): return out
	for b in node.find_children("*", "Button", true, false):
		if (b as Button).is_visible_in_tree(): out.append((b as Button).text.strip_edges())
	return out

## The open dialogue's choices once its last page shows.
func choices(seconds := 8.0) -> Array:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		var shown := buttons(app.village_modal)
		if not shown.is_empty(): return shown
		if is_instance_valid(app.village_modal) and app.village_modal.has_meta("advance"): app.village_modal.get_meta("advance").call()
		await create_timer(0.2).timeout
	return []

func field() -> Node:
	for module in app.modules:
		if is_instance_valid(module) and module.has_method("use_notice"): return module
	return null

func cast(id: String) -> Node3D:
	for npc in app.npcs:
		if is_instance_valid(npc) and str(npc.get_meta("cast", "")) == id: return npc
	return null

func row_button(row_name: String) -> Button:
	if not is_instance_valid(app.village_modal): return null
	var row: Node = app.village_modal.find_child(row_name, true, false)
	return row.find_child("BoardAction", true, false) as Button if row else null

func post(id: String, state: String, extra := {}) -> Dictionary:
	return {"id":id, "day":"2027-02-01", "stars":5, "need":1, "have":0, "state":state}.merged(extra, true)

func board_of(list: Array, extra := {}) -> Dictionary:
	return {"day":"2027-02-01", "timezone":"Asia/Seoul", "resets_at":Time.get_unix_time_from_system() + 3600, "unlocked":true,
		"limits":{"accept":3, "complete":3}, "accepted":1, "completed":1, "remaining_accepts":2, "remaining_completions":2, "list":list}.merged(extra, true)

func run() -> void:
	preload("res://scripts/npc.gd").pinned = true
	app = Main.new()
	root.add_child(app)
	await create_timer(1.0).timeout
	await app.authenticate(true, preload("res://tests/qa_server.gd").url(), "board_" + str(Time.get_ticks_msec() % 1000000), PASSWORD, "")
	expect(await wait_for(func() -> bool: return app.screen == "village" and field() != null, 60.0), "the village with its field objects")
	var token := str(app.api.token)

	# A. The current server: no board, no shops; everything as before.
	var none := await QuestBoard.fetch(app.api)
	expect(none.is_empty() and QuestBoard.missing(token), "no /v1/quest_board: the board is found missing")
	await field().use_notice(field().object("notice"))
	var shown := await choices()
	expect("게시판 닫기" in shown and not "✦ 오늘의 부탁" in shown, "the notice board stays read-only (%s)" % str(shown))
	expect(not texts(app.village_modal).contains("오늘의 부탁"), "no board line on the notice page")
	app.close_village_modal()
	await ShopWindow.probe(app.api)
	var probed := ShopWindow.known(token)
	expect(probed.size() == 4 and probed.values().all(func(v): return v == false), "no /v1/shops: every shop found missing (%s)" % str(probed))
	expect(ShopWindow.village_choices(app, "haeru", "해루", cast("haeru")).is_empty(), "no new choices for 해루")
	app.talk_to(cast("haeru"))
	shown = await choices()
	expect(not shown.is_empty() and not "보람의 생선 매입 보기" in shown and not "가게 보기" in shown, "해루's talk is unchanged (%s)" % str(shown))
	app.close_village_modal()
	field().use_mailbox(field().object("mailbox"))
	shown = await choices()
	expect("우편함 닫기" in shown, "the mailbox opens as before")
	app.close_village_modal()

	# B1. Event letters.
	var day := NpcLetters.letter_lines({"npc":"naru", "name":"나루", "level":0, "read":false, "gift":null,
		"event":{"type":"resident_day", "key":"2027-01-09", "payload":{"date":"2027-01-09", "occasion":"village_anniversary"}}})
	expect(day.size() >= 2 and str(day[0]).contains("나루") and str(day[0]).contains("기념일"), "an anniversary letter names its sender and occasion")
	var thanks := NpcLetters.letter_lines({"npc":"regular", "name":"모카", "level":0, "quest":{"npc":"regular"},
		"event":{"type":"request_done", "key":"2027-02-01:moka_pie", "payload":{"quest_id":"moka_pie", "day":"2027-02-01"}}})
	expect(str(thanks[0]).contains("게시판 부탁") and str(thanks[0]).contains("모카의 사과 파이"), "a board thank-you letter names the request")
	var heart := {"npc":"naru", "name":"나루", "personality":"cheerful", "level":2}
	expect(NpcLetters.letter_lines(heart) == NpcGifts.letter_lines(heart), "letters without an event keep their old words")

	# B2. The board window with stubbed replies.
	var stub := StubApi.new()
	stub.token = token
	root.add_child(stub)
	var talk_post := post("yunjae_regards", "ready", {"npc":"gentleman", "kind":"talk", "have":1, "places":["poet"], "visited":["poet"]})
	var board := board_of([post("naru_islands", "available", {"npc":"naru", "kind":"visit", "need":3, "places":["square", "fields", "garden"]}),
		talk_post, post("sora_outfit", "done", {"npc":"sora", "kind":"outfit"}), post("moru_soup", "locked", {"npc":"moru", "kind":"bring", "need":2, "items":["mushroom"]})])
	var taken := board.duplicate(true)
	taken.list[0].state = "active"
	taken.accepted = 2
	taken.remaining_accepts = 1
	stub.replies["POST /v1/quest_board/2027-02-01/naru_islands/accept"] = {"ok":true, "data":{"quest":taken.list[0], "board":taken}}
	QuestBoard.open(app, board, stub)
	var page := texts(app.village_modal)
	expect(page.contains("나루의 섬 한 바퀴") and page.contains("윤재의 안부 전하기") and page.contains("소라의 새 옷 맞춤"), "the board lists today's posts by their titles")
	expect(page.contains("받은 부탁 1/3") and page.contains("다 됐어요! 게시판에서 완료하기"), "the summary and a ready post's word")
	var accept := row_button("Board_naru_islands")
	expect(accept != null and accept.text == "받기" and not accept.disabled, "an open post has 받기")
	expect(row_button("Board_yunjae_regards") != null and row_button("Board_yunjae_regards").text == "완료하기", "a ready post has 완료하기")
	expect(row_button("Board_sora_outfit") == null and row_button("Board_moru_soup") == null, "done and locked posts have no button")
	accept.pressed.emit()
	expect(await wait_for(func() -> bool: return not stub.called("POST /v1/quest_board/2027-02-01/naru_islands/accept").is_empty(), 5.0), "받기 posts /v1/quest_board/{day}/{id}/accept")
	var body: Dictionary = stub.called("POST /v1/quest_board/2027-02-01/naru_islands/accept").get("body", {})
	expect(str(body.get("request_id", "")).length() == 36, "with a request_id")
	expect(await wait_for(func() -> bool: return row_button("Board_naru_islands") != null and row_button("Board_naru_islands").text == "길 안내", 5.0), "the taken post turns into 길 안내")
	expect(QuestBoard.cached(token).get("accepted", 0) == 2, "the board's reply is kept")
	# The hand-in: stars burst and fly into the counter.
	var before := int(app.me.get("shards", 0))
	var after := taken.duplicate(true)
	after.list[1].state = "done"
	after.completed = 2
	stub.replies["POST /v1/quest_board/2027-02-01/yunjae_regards/complete"] = {"ok":true, "data":{"quest":after.list[1], "board":after, "stars":5, "shards":before + 5,
		"letters":[{"id":"x", "npc":"gentleman", "name":"윤재", "level":0, "read":false, "gift":null}]}}
	row_button("Board_yunjae_regards").pressed.emit()
	expect(await wait_for(func() -> bool: return not stub.called("POST /v1/quest_board/2027-02-01/yunjae_regards/complete").is_empty(), 5.0), "완료하기 posts .../complete")
	expect(await wait_for(func() -> bool: return not is_instance_valid(app.village_modal), 5.0), "the board closes on the hand-in")
	expect(int(app.me.get("shards", 0)) == before + 5, "the balance takes the server's total")
	expect(await wait_for(func() -> bool: return int(app.frame.stars.text) == before + 5, 6.0), "the stars fly into the counter (%s)" % app.frame.stars.text)
	# No accepts left: 받기 is off.
	var full := board_of([post("naru_islands", "available", {"npc":"naru", "kind":"visit", "need":3})], {"remaining_accepts":0, "accepted":3})
	QuestBoard.open(app, full, stub)
	expect(row_button("Board_naru_islands") != null and row_button("Board_naru_islands").disabled, "with no accepts left 받기 is off")
	app.close_village_modal()
	# A talk request's word passed on.
	var talking := board_of([post("yunjae_regards", "active", {"npc":"gentleman", "kind":"talk", "places":["poet"], "visited":[]})])
	QuestBoard.remember(talking, token)
	var said := []
	var choice := QuestBoard.talk_choice(stub, "poet", func(lines: Array, _c: Array): said.append_array(lines), Callable())
	expect(choice.size() == 2 and str(choice[0]) == "✦ 게시판 부탁 전하기", "가람 gets 전하기 for the talk request")
	expect(QuestBoard.talk_choice(stub, "naru", Callable(), Callable()).is_empty(), "nobody else does")
	stub.replies["POST /v1/quest_board/2027-02-01/yunjae_regards/progress"] = {"ok":true, "data":{"quest":post("yunjae_regards", "ready"), "board":talking}}
	choice[1].call()
	expect(await wait_for(func() -> bool: return not said.is_empty(), 5.0) and str(stub.called("POST /v1/quest_board/2027-02-01/yunjae_regards/progress").body.get("place", "")) == "poet", "전하기 posts progress with the resident as the place")

	# B3. Shops.
	var bag := {"ok":true, "data":{"bag":{"apple":2, "turnip_seed":0}, "catalog":{"names":{"apple":"사과", "turnip":"순무", "perch":"강농어"}}}}
	stub.replies["GET /v1/homestead"] = bag
	stub.replies["GET /v1/shops/general_store"] = {"ok":true, "data":{"id":"general_store", "name":"단비의 잡화점", "open":false, "closed_reason":"danbi_not_moved_in",
		"required_flag":"danbi_moved_in", "coins":50, "shards":3, "version":4, "sell_stars":{}, "effects":{},
		"buy":[{"id":"turnip_seed", "name":"순무 씨앗", "coins":2, "shards":0, "kind":"bag", "daily_limit":null, "remaining":null}],
		"sell":[{"id":"apple", "name":"사과", "coins":2, "shards":0, "remaining":null}], "services":[]}}
	var w := RpgUi.window(app.ui, "가게", {"place":"centre", "id":"shop_check"})
	var closed := ShopWindow.build(w.body, stub, "general_store", {"title":w.title})
	expect(await wait_for(func() -> bool: return not closed.shop.is_empty() and w.body.find_child("Buy_turnip_seed", true, false) != null, 5.0), "a shop window fills from /v1/shops/{id}")
	var reason := w.body.find_child("ShopClosed", true, false) as Label
	expect(reason != null and reason.visible and reason.text.contains("이사"), "a closed shop shows its reason")
	expect((w.body.find_child("Buy_turnip_seed", true, false) as Button).disabled, "and its buttons are off")
	expect(w.title.text == "단비의 잡화점", "the window takes the server's shop name")
	RpgUi.close_window(w, false, false)
	stub.replies["GET /v1/shops/farm_stall"] = {"ok":true, "data":{"id":"farm_stall", "name":"한결의 씨앗 가게", "open":true, "closed_reason":null, "coins":50, "shards":3, "version":4,
		"sell_stars":{"cap":15, "today":0, "coins_per_star":3, "carry":0}, "effects":{},
		"buy":[{"id":"turnip_seed", "name":"순무 씨앗", "coins":2, "shards":0, "kind":"bag", "daily_limit":null, "remaining":null}],
		"sell":[{"id":"apple", "name":"사과", "coins":2, "shards":0, "remaining":null}],
		"services":[{"id":"daily_order", "name":"마을 식탁 배달", "kind":"order", "items":{"turnip":2, "perch":1}, "coins_reward":20, "daily_limit":1, "remaining":1}]}}
	stub.replies["POST /v1/shops/farm_stall/buy"] = {"ok":true, "data":{"version":5, "coins":48, "bag":{"apple":2, "turnip_seed":1}, "message":"순무 씨앗 1개를 샀어요.", "stars":0, "shards":3}}
	var traded := []
	var w2 := RpgUi.window(app.ui, "가게", {"place":"centre", "id":"shop_check2"})
	var open := ShopWindow.build(w2.body, stub, "farm_stall", {"traded":func(reply: Dictionary): traded.append(reply)})
	expect(await wait_for(func() -> bool: return w2.body.find_child("Buy_turnip_seed", true, false) != null, 5.0), "an open shop's rows")
	expect(not (w2.body.find_child("ShopClosed", true, false) as Label).visible, "no closed notice")
	expect(w2.body.find_child("ShopTabs", true, false) != null, "사기 / 팔기 / 주문 tabs")
	var buy := w2.body.find_child("Buy_turnip_seed", true, false) as Button
	expect(not buy.disabled, "buy is on")
	buy.pressed.emit()
	expect(await wait_for(func() -> bool: return not traded.is_empty(), 5.0), "a purchase reaches the caller's hook")
	var sent: Dictionary = stub.called("POST /v1/shops/farm_stall/buy").get("body", {})
	expect(str(sent.get("item", "")) == "turnip_seed" and int(sent.get("quantity", 0)) == 1 and int(sent.get("version", -1)) == 4 and str(sent.get("request_id", "")).length() == 36,
		"buy posts /v1/shops/farm_stall/buy with the item, quantity, version and request_id (%s)" % str(sent))
	expect(stub.called("POST /v1/homestead").is_empty(), "nothing is sold or bought through /v1/homestead as well")
	RpgUi.close_window(w2, false, false)
	# Known shops add 가게 보기.
	ShopWindow.assume(token, {"general_store":true, "farm_stall":true, "cafe":true, "fishing_shack":true})
	var extras := ShopWindow.village_choices(app, "haeru", "해루", cast("haeru"))
	expect(extras.size() == 1 and str(extras[0][0]) == "보람의 생선 매입 보기", "with the shops known 해루 offers the fish counter")
	ShopWindow.assume(token, {"general_store":false, "farm_stall":false, "cafe":false, "fishing_shack":false})
	stub.queue_free()
	print("QUEST_BOARD_CHECK " + ("FAILED" if failed else "OK"))
	await app.logout()
	quit(1 if failed else 0)
