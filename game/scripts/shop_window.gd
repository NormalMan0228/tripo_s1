extends RefCounted
## The residents' shops (server/shops.py, docs/design/NPC_INTERACTIONS_KO.md): talking to a shop's
## resident adds "가게 보기", which opens a window to buy, sell and order its services with leaf
## coins (잎전), at the server's prices and daily stock, honouring open / closed_reason (단비's store
## opens once she has moved in, required_flag danbi_moved_in).
## Feature-detected: probe() asks each shop once per login; while the server has no /v1/shops
## (404) nothing changes: no new talk choice, and 단비's "물건 팔기" (shop_sell.gd) stays as it is.
## Selling here goes through the shop's /sell, never also /v1/homestead, so a sale pays once;
## both share the server's daily starseed allowance.
##
## Also the hook for the residents' extra talk choices (#81): room_choices() for studio.gd rooms and
## village_choices() for main.gd talks add the shop and the notice board's "전하기" (quest_board.gd).
const RpgUi = preload("res://scripts/rpg_ui.gd")
const Icon = preload("res://scripts/life_icon.gd")
const ShopSell = preload("res://scripts/shop_sell.gd")
const QuestsLib = preload("res://scripts/quests.gd")
const QuestBoard = preload("res://scripts/quest_board.gd")

## Which resident keeps which shop. 해루 shares the lighthouse pier with 보람's fish counter
## (the contract allows the pier's UI to be shared); 보람 himself mostly walks as a shadow.
const NPC_SHOPS := {"shopkeeper":"general_store", "farmer":"farm_stall", "regular":"cafe", "fisher":"fishing_shack", "haeru":"fishing_shack"}
const SHOP_IDS := ["general_store", "farm_stall", "cafe", "fishing_shack"]
## Shop names until the server's answer (the server's own name wins).
const NAMES := {"general_store":"단비의 잡화점", "farm_stall":"한결의 씨앗 가게", "cafe":"빨간 지붕", "fishing_shack":"보람의 생선 매입"}
const META := "shop_probe"
const STAR_ICON := "res://assets/starseed.svg"

static func t(text: String) -> String:
	return TranslationServer.translate(text)

# ------------------------------------------------------------------ feature detection

## {shop_id: true/false} for this login; a shop not in it is not known yet.
static func known(token: String) -> Dictionary:
	var kept: Dictionary = Engine.get_meta(META, {})
	return kept.get("shops", {}) if str(kept.get("token", "")) == token and not token.is_empty() else {}

static func has_shop(token: String, shop_id: String) -> bool:
	return bool(known(token).get(shop_id, false))

## Asks each shop once per login (GET /v1/shops/{id}); a 404 means the server has no shops.
static func probe(api: Node) -> void:
	if api == null or str(api.token).is_empty(): return
	var token := str(api.token)
	var kept: Dictionary = Engine.get_meta(META, {})
	if str(kept.get("token", "")) == token and (bool(kept.get("busy", false)) or kept.get("shops", {}).size() == SHOP_IDS.size()): return
	var shops: Dictionary = kept.get("shops", {}) if str(kept.get("token", "")) == token else {}
	Engine.set_meta(META, {"token":token, "shops":shops, "busy":true})
	for id in SHOP_IDS:
		if shops.has(id): continue
		var reply: Dictionary = await api.request("/v1/shops/%s" % id)
		if reply.ok: shops[id] = true
		elif int(reply.get("status", 0)) in [404, 405]:
			# No route at all: no shop will answer either.
			for other in SHOP_IDS:
				if not shops.has(other): shops[other] = false
			break
		# Anything else (offline, a hiccup) stays unknown: asked again next time.
	Engine.set_meta(META, {"token":token, "shops":shops, "busy":false})

## Test and tooling hook: what probe() would have found.
static func assume(token: String, shops: Dictionary) -> void:
	Engine.set_meta(META, {"token":token, "shops":shops, "busy":false})

# ------------------------------------------------------------------ talk choices (#81)

## Extra choices for a resident inside a building (studio.gd open_talk): [label, Callable] each.
static func room_choices(room: Node, id: String, state: Dictionary) -> Array:
	var out: Array = []
	if not is_instance_valid(room) or bool(room.get("visiting")) or room.get("api") == null or str(room.api.token).is_empty(): return out
	var api: Node = room.api
	var shop := str(NPC_SHOPS.get(id, ""))
	# 단비 trades at her counter only (as with "물건 팔기"); the others whenever they are up.
	var at_work := id != "shopkeeper" or str(state.get("activity", "")) == "shopkeep"
	if not shop.is_empty() and at_work and has_shop(str(api.token), shop): out.append([t("가게 보기"), func(): open_room(room, id, shop)])
	elif not shop.is_empty() and known(str(api.token)).is_empty(): probe(api)
	var board := QuestBoard.talk_choice(api, id, func(lines: Array, choices: Array): room.open_talk(id, lines, choices),
		func(_reply: Dictionary): if room.get("npcs") is Dictionary and room.npcs.has(id): room.pop_over(room.npcs[id], "♪"))
	if not board.is_empty(): out.append(board)
	return out

## Extra choices for a village talk (main.gd talk_to): [label, Callable] each.
static func village_choices(app: Node, npc: String, speaker: String, anchor: Node3D) -> Array:
	var out: Array = []
	if not is_instance_valid(app) or app.get("api") == null or str(app.api.token).is_empty(): return out
	if QuestBoard.visiting(app): return out
	var shop := str(NPC_SHOPS.get(npc, ""))
	if not shop.is_empty() and has_shop(str(app.api.token), shop):
		out.append([t("가게 보기") if npc != "haeru" else t("보람의 생선 매입 보기"), func(): open_village(app, shop, anchor)])
	var board := QuestBoard.talk_choice(app.api, npc, func(lines: Array, choices: Array): app.open_dialogue(speaker, npc, lines, choices),
		func(_reply: Dictionary): if is_instance_valid(anchor) and anchor.has_method("pop"): anchor.pop("♪", 1.6))
	if not board.is_empty(): out.append(board)
	return out

# ------------------------------------------------------------------ opening the window

## Inside a building: the shared window over the room; E or Esc closes it like the storage list.
static func open_room(room: Node, npc: String, shop_id: String) -> Dictionary:
	room.close_talk(false)
	RpgUi.sfx("open", -8.0)
	var w := RpgUi.window(room, t(NAMES.get(shop_id, "가게")), {"width":RpgUi.WINDOW_W.standard, "place":"centre", "scroll":true,
		"on_close":room.close_talk, "id":"shop_window", "sound":false})
	room.talk_box = w.root
	room.talk_window = {}
	room.talk_lines = []
	room.talk_choices = []
	room.show_hud(false)
	build(w.body, room.api, shop_id, {"title":w.title, "traded":func(reply: Dictionary):
		# The room's sale moment (studio.gd sold): a pop over the keeper, starseeds into the wallet line.
		if room.has_method("sold"): room.sold(npc, reply)})
	return w

## In the village: the shared parchment window (main.gd modal_card).
static func open_village(app: Node, shop_id: String, anchor: Node3D) -> void:
	var body: VBoxContainer = app.modal_card(t(NAMES.get(shop_id, "가게")))
	var title: Label = app.village_modal.find_child("Title", true, false) as Label if is_instance_valid(app.village_modal) else null
	build(body, app.api, shop_id, {"title":title, "traded":func(reply: Dictionary):
		if reply.has("version") and is_instance_valid(app.get("life")) and app.life.has_method("accept"): app.life.accept(reply)
		var stars := int(reply.get("stars", 0))
		if stars > 0 and is_instance_valid(anchor) and app.get("world") != null: QuestsLib.reward_burst(app, anchor.global_position, stars, false)
		if is_instance_valid(anchor) and anchor.has_method("pop"): anchor.pop("✦" if stars > 0 else "♪", 1.4)
		if reply.has("shards") and app.has_method("live_shards"): app.live_shards(int(reply.shards))
		RpgUi.hush_toast()
		app.message(str(reply.get("message", "")))})

# ------------------------------------------------------------------ the window's content

static func closed_line(reason: String) -> String:
	match reason:
		"danbi_not_moved_in": return t("단비가 아직 마을로 이사 오지 않았어요. 첫 이야기를 마치면 문을 열어요.")
	return t("지금은 문을 닫았어요.")

static func error_line(code: String) -> String:
	match code:
		"shop_closed", "danbi_not_moved_in": return closed_line("danbi_not_moved_in")
		"life_not_enough_coins": return t("잎전이 모자라요.")
		"insufficient_shards": return t("별씨가 모자라요.")
		"life_missing_items": return t("가방에 물건이 모자라요.")
		"life_invalid_item": return t("여기서는 다루지 않는 물건이에요.")
		"shop_item_unavailable": return t("오늘은 팔지 않는 물건이에요.")
		"shop_daily_limit": return t("오늘 몫은 다 팔렸어요. 내일 다시 와 주세요.")
		"life_order_completed": return t("오늘 배달은 벌써 마쳤어요.")
		"stale_life_version": return t("가방이 바뀌어서 다시 불러왔어요.")
		"sell_reward_limit": return t("오늘 판매로 받을 별씨를 다 받았어요. 내일 다시 팔아 주세요.")
	return t("지금은 거래할 수 없어요. 다시 해 볼게요.")

## The item's picture: the village-life icon for bag items, furniture art for decorations.
static func item_icon(entry: Dictionary, edge: float) -> Control:
	if str(entry.get("kind", "bag")) == "decoration":
		return RpgUi.icon("res://assets/items/lamp.svg" if "lamp" in str(entry.get("id", "")) else "res://assets/items/furniture.svg", edge)
	return Icon.make(str(entry.get("id", "")), edge)

## "3잎전" (+ "· 별씨 1" when a price has starseeds).
static func price_text(coins: int, shards: int) -> String:
	return t("%d잎전") % coins + (" · " + t("별씨 %d") % shards if shards > 0 else "")

## Fills `body` with the shop: wallet line, the closed notice, tabs 사기 / 팔기 / 주문, rows with
## icons, prices, today's stock and the action. hooks: title (Label renamed to the server's name),
## traded(reply) after each successful trade. Returns the state dictionary (tests read it).
static func build(body: VBoxContainer, api: Node, shop_id: String, hooks := {}) -> Dictionary:
	var state := {"shop":{}, "bag":{}, "tab":"", "busy":false, "shop_id":shop_id}
	var head := RpgUi.caption(body, t("가게를 여는 중…"), 13)
	head.name = "ShopHead"
	var notice := RpgUi.label(body, "", 15, RpgUi.ACCENT, false)
	notice.name = "ShopClosed"
	notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	notice.visible = false
	var tabs_holder := VBoxContainer.new()
	body.add_child(tabs_holder)
	var list := VBoxContainer.new()
	list.name = "ShopList"
	list.add_theme_constant_override("separation", 6)
	body.add_child(list)
	# Lambdas capture locals by value: the three steps reach each other through this dictionary.
	var fns := {}
	state["fns"] = fns
	fns.fill = func() -> void:
		if not is_instance_valid(list): return
		var shop: Dictionary = state.shop
		var bag: Dictionary = state.bag
		if hooks.get("title") is Label and is_instance_valid(hooks.title) and not str(shop.get("name", "")).is_empty(): hooks.title.text = t(str(shop.name))
		var open := bool(shop.get("open", false))
		var words := t("잎전 %d · 별씨 %d") % [int(shop.get("coins", 0)), int(shop.get("shards", 0))]
		var allowance := ShopSell.status_text(shop)
		var mood: Dictionary = shop.get("effects", {}).get("cafe_mood", {}) if shop.get("effects") is Dictionary else {}
		if not mood.is_empty():
			var minutes := ceili(maxf(0.0, float(mood.get("expires_at", 0)) - float(shop.get("server_time", 0))) / 60.0)
			words += "  ·  " + t("♨ 마음이 포근해요 · %d분") % minutes
		head.text = words + ("  ·  " + allowance if not allowance.is_empty() and not (shop.get("sell", []) as Array).is_empty() else "")
		notice.visible = not open
		notice.text = closed_line(str(shop.get("closed_reason", ""))) if not open else ""
		var pages: Array = []
		if not (shop.get("buy", []) as Array).is_empty(): pages.append({"id":"buy", "label":t("사기")})
		if not (shop.get("sell", []) as Array).is_empty(): pages.append({"id":"sell", "label":t("팔기")})
		if (shop.get("services", []) as Array).any(func(s): return str(s.get("kind", "")) != "sell"): pages.append({"id":"service", "label":t("주문")})
		var ids := pages.map(func(p): return p.id)
		if not str(state.tab) in ids: state.tab = ids[0] if not ids.is_empty() else ""
		var draw := func(page: String) -> void:
			state.tab = page
			for child in list.get_children():
				list.remove_child(child)
				child.queue_free()
			var rows := 0
			var coins := int(shop.get("coins", 0))
			if page == "buy":
				for entry in shop.get("buy", []):
					var item: Dictionary = entry
					var remaining = item.get("remaining")
					var price := int(item.get("coins", 0))
					var row := row_of(list, item, price_text(price, int(item.get("shards", 0))), remaining)
					var buy := RpgUi.button(row, t("사기"), func(): fns.act.call("buy", {"item":str(item.id), "quantity":1}), "gold", "sm")
					buy.name = "Buy_" + str(item.id)
					buy.custom_minimum_size.x = 84
					buy.disabled = not open or (remaining != null and int(remaining) <= 0) or coins < price or int(shop.get("shards", 0)) < int(item.get("shards", 0))
					rows += 1
			elif page == "sell":
				for entry in shop.get("sell", []):
					var item: Dictionary = entry
					var count := int(bag.get(str(item.id), 0))
					if count < 1: continue
					var amount := mini(count, 20)
					var paid := int(item.get("coins", 0)) * amount
					var row := row_of(list, item.merged({"name":"%s ×%d" % [t(str(item.get("name", item.id))), amount]}, true), t("+%d잎전") % paid, item.get("remaining"))
					ShopSell.star_badge(row, ShopSell.estimate(shop, paid))
					var sell := RpgUi.button(row, t("팔기"), func(): fns.act.call("sell", {"item":str(item.id), "quantity":amount}), "normal", "sm")
					sell.name = "Sell_" + str(item.id)
					sell.custom_minimum_size.x = 84
					sell.disabled = not open
					rows += 1
				if rows == 0: RpgUi.caption(list, t("팔 물건이 없어요. 사과를 따거나 낚시를 해 보세요."), 14)
			else:
				for entry in shop.get("services", []):
					var item: Dictionary = entry
					var kind := str(item.get("kind", ""))
					if kind == "sell": continue
					var remaining = item.get("remaining")
					var cost := ""
					var can := open and (remaining == null or int(remaining) > 0)
					if kind == "order":
						var need: Dictionary = item.get("items", {})
						var parts := PackedStringArray()
						for thing in need:
							parts.append("%s ×%d" % [t(str(state.get("names", {}).get(thing, thing))), int(need[thing])])
							if int(bag.get(str(thing), 0)) < int(need[thing]): can = false
						cost = t("%s → +%d잎전") % [", ".join(parts), int(item.get("coins_reward", 0))]
					else:
						cost = price_text(int(item.get("coins", 0)), int(item.get("shards", 0)))
						if coins < int(item.get("coins", 0)): can = false
					var row := row_of(list, item.merged({"kind":"service"}, true), cost, remaining)
					var order := RpgUi.button(row, t("배달하기") if kind == "order" else t("주문하기"), func(): fns.act.call("service", {"service":str(item.id)}), "gold", "sm")
					order.name = "Service_" + str(item.id)
					order.custom_minimum_size.x = 84
					order.disabled = not can
					rows += 1
		for child in tabs_holder.get_children():
			tabs_holder.remove_child(child)
			child.queue_free()
		if pages.size() > 1:
			var strip := RpgUi.tab_strip(tabs_holder, pages, draw)
			strip.name = "ShopTabs"
			RpgUi.select_tab(strip, str(state.tab))
		elif not pages.is_empty(): draw.call(str(state.tab))
	fns.load = func() -> void:
		var shop_reply: Dictionary = await api.request("/v1/shops/%s" % shop_id)
		if not is_instance_valid(list): return
		if not shop_reply.ok:
			head.text = t("가게 문이 잠겨 있어요. 잠시 뒤 다시 와 주세요.")
			return
		state.shop = shop_reply.data
		if not (state.shop.get("sell", []) as Array).is_empty() or (state.shop.get("services", []) as Array).any(func(s): return str(s.get("kind", "")) == "order"):
			var bag_reply: Dictionary = await api.request("/v1/homestead")
			if not is_instance_valid(list): return
			if bag_reply.ok:
				state.bag = bag_reply.data.get("bag", {})
				state.names = bag_reply.data.get("catalog", {}).get("names", {}) if bag_reply.data.get("catalog") is Dictionary else {}
		fns.fill.call()
	fns.act = func(action: String, extra: Dictionary) -> void:
		if state.busy: return
		state.busy = true
		var path := "/v1/shops/%s/%s" % [shop_id, action]
		var body_json: Dictionary = api.mutation(extra.merged({"version":int(state.shop.get("version", 0))}))
		state["last"] = {"path":path, "body":body_json}
		var reply: Dictionary = await QuestBoard.send(api, path, body_json)
		state.busy = false
		if not is_instance_valid(list): return
		if reply.ok:
			# Buying: the purchase chime; selling: the coins (shop_sell.gd's sound).
			RpgUi.sfx("coin_gain" if action == "sell" else "confirm", -5.0)
			var traded: Callable = hooks.get("traded", Callable())
			if traded.is_valid(): traded.call(reply.data)
			# The trade's reply is the bag and coins; the stock comes with the shop again.
			state.bag = reply.data.get("bag", state.bag)
			await fns.load.call()
			return
		RpgUi.sfx("deny", -8.0)
		var code := str(reply.get("error", ""))
		await fns.load.call()
		if is_instance_valid(head): head.text = error_line(code)
	fns.load.call()
	return state

## One shop row: picture, name and today's stock, the price; the caller adds the button.
static func row_of(list: VBoxContainer, item: Dictionary, price: String, remaining) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.name = "Row_" + str(item.get("id", ""))
	row.add_theme_constant_override("separation", 10)
	list.add_child(row)
	row.add_child(item_icon(item, 36) if str(item.get("kind", "")) != "service" else RpgUi.icon("res://assets/items/soup.svg", 36))
	var words := VBoxContainer.new()
	words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	words.add_theme_constant_override("separation", 0)
	row.add_child(words)
	RpgUi.label(words, t(str(item.get("name", item.get("id", "")))), 16, RpgUi.PAPER_INK, false).add_theme_font_override("font", RpgUi.FONT_STRONG)
	if remaining != null: RpgUi.caption(words, t("오늘 %d개 남음") % int(remaining) if int(remaining) > 0 else t("오늘은 다 팔렸어요"), 12)
	var cost := RpgUi.label(row, price, 15, RpgUi.LEAF, false)
	cost.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	return row
