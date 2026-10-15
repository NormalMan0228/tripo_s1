extends RefCounted
## Selling finds pays leaf coins and, up to a daily allowance, starseeds (server: homestead 'sell'
## plus app.py's sell_stars: one starseed per N coins of sales, at most `cap` a day).
## The village's seed stall (village_life.gd open_shop) shows the allowance with these helpers;
## 단비 at the general store's counter (studio.gd, room 13_shop) opens the window below.
##   ShopSell.status_text(state)           # "오늘 별씨 3/15 · 3잎전마다 1개"
##   ShopSell.estimate(state, coins)       # starseeds a sale of that many coins would add now
##   ShopSell.window(parent, api, sold)    # the night card; sold(reply) after each sale
const RpgUi = preload("res://scripts/rpg_ui.gd")
const Icon = preload("res://scripts/life_icon.gd")

const STAR_ICON := "res://assets/starseed.svg"

static func t(text: String) -> String:
	return TranslationServer.translate(text)

static func allowance(state: Dictionary) -> Dictionary:
	var stars = state.get("sell_stars", {})
	return stars if stars is Dictionary else {}

## Starseeds a sale worth `coins` leaf coins would add today (0 when off or at the cap).
static func estimate(state: Dictionary, coins: int) -> int:
	var a := allowance(state)
	var cap := int(a.get("cap", 0))
	var per := maxi(1, int(a.get("coins_per_star", 3)))
	if cap <= 0: return 0
	return clampi((int(a.get("carry", 0)) + coins) / per, 0, maxi(0, cap - int(a.get("today", 0))))

static func status_text(state: Dictionary) -> String:
	var a := allowance(state)
	var cap := int(a.get("cap", 0))
	if cap <= 0: return ""
	if int(a.get("today", 0)) >= cap: return t("오늘 받을 별씨를 다 받았어요 · 내일 다시")
	return t("오늘 별씨 %d/%d · %d잎전어치마다 1개") % [int(a.get("today", 0)), cap, int(a.get("coins_per_star", 3))]

## A star icon + "+N" for a sell button, or nothing.
static func star_badge(parent: Control, stars: int) -> void:
	if stars <= 0: return
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_theme_constant_override("separation", 2)
	row.add_child(RpgUi.icon(STAR_ICON, 20))
	RpgUi.label(row, "+%d" % stars, 15, RpgUi.HOVER)
	parent.add_child(row)

## The general store's selling window (rooms): a night card listing the bag's sellable finds,
## each with its price and the starseeds it adds. Selling keeps the card open and refreshed.
static func window(parent: Node, api: Node, sold: Callable) -> Control:
	var root := Control.new()
	root.name = "ShopSell"
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	parent.add_child(root)
	var shade := ColorRect.new()
	shade.color = Color(0, 0, 0, 0.35)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(shade)
	var middle := CenterContainer.new()
	middle.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	middle.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(middle)
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", RpgUi.panel_style("night", 22))
	card.custom_minimum_size = Vector2(560, 0)
	middle.add_child(card)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	card.add_child(column)
	RpgUi.label(column, t("단비의 잡화점 · 물건 팔기"), 22, RpgUi.GOLD)
	var head := RpgUi.label(column, t("가방을 살펴보는 중…"), 14, RpgUi.SOFT)
	var list := VBoxContainer.new()
	list.add_theme_constant_override("separation", 6)
	column.add_child(list)
	RpgUi.label(column, t("E · Esc 닫기"), 12, RpgUi.SOFT)
	RpgUi.pop_in(card)
	var busy := [false]
	var fill := func(state: Dictionary, again: Callable) -> void:
		if not is_instance_valid(list): return
		for child in list.get_children(): child.queue_free()
		var words := t("잎전 %d") % int(state.get("coins", 0))
		var allowance_words := status_text(state)
		head.text = words + ("  ·  " + allowance_words if not allowance_words.is_empty() else "")
		var catalog: Dictionary = state.get("catalog", {})
		var prices: Dictionary = catalog.get("prices", {})
		var names: Dictionary = catalog.get("names", {})
		var bag: Dictionary = state.get("bag", {})
		var shown := 0
		var first: Button = null
		for item in prices:
			var count := int(bag.get(item, 0))
			if count < 1: continue
			shown += 1
			if shown > 8: break
			var amount := mini(count, 20)
			var coins := int(prices[item]) * amount
			var row := HBoxContainer.new()
			row.add_theme_constant_override("separation", 10)
			list.add_child(row)
			row.add_child(Icon.make(str(item), 36))
			var name_label := RpgUi.label(row, "%s ×%d" % [t(str(names.get(item, item))), amount], 16)
			name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			RpgUi.label(row, t("+%d잎전") % coins, 15, RpgUi.LEAF_LIGHT)
			star_badge(row, estimate(state, coins))
			var sell := Button.new()
			sell.text = t("팔기")
			sell.custom_minimum_size = Vector2(84, 38)
			sell.theme_type_variation = "NightButton"
			sell.pressed.connect(func():
				if busy[0]: return
				busy[0] = true
				var reply: Dictionary = await api.post("/v1/homestead", api.mutation({"action":"sell", "item":item, "quantity":amount, "version":int(state.get("version", 0))}))
				busy[0] = false
				if not is_instance_valid(root): return
				if reply.ok:
					RpgUi.sfx("confirm", -4.0)
					if sold.is_valid(): sold.call(reply.data)
					again.call(reply.data, again)
				else:
					head.text = t("지금은 팔 수 없어요. 다시 해 볼게요.")
					var fresh: Dictionary = await api.request("/v1/homestead")
					if is_instance_valid(root) and fresh.ok: again.call(fresh.data, again))
			row.add_child(sell)
			if first == null: first = sell
		if shown == 0: RpgUi.label(list, t("팔 물건이 없어요. 사과를 따거나 낚시를 해 보세요."), 15, RpgUi.SOFT)
		if first != null: first.grab_focus.call_deferred()
	var load := func() -> void:
		var loaded: Dictionary = await api.request("/v1/homestead")
		if not is_instance_valid(root): return
		if loaded.ok: fill.call(loaded.data, fill)
		else: head.text = t("가방을 불러오지 못했어요.")
	load.call()
	return root
