extends RefCounted
## The 함께하기 drawer's content (social_hud.gd opens the drawer on K or the chat's people key):
## folder tabs 친구 / 접속 중 / 우리 마을 / 파티. 친구 and 접속 중 only when the server offers them
## (/health social_features "friends", "people"; never on the judges' server). Every tab is a
## form row that stays (a name field and its button) over a list rebuilt only when its data
## changed, so typing a name is not cleared by the 5-second refresh.
const RpgUi = preload("res://scripts/rpg_ui.gd")
const PLACES := {"village":"마을", "home":"집 안", "workshop":"공방", "room":"실내", "expedition":"탐험 중", "away":"다른 곳"}

var hub: Node
var w: Dictionary = {}
var tabs: HBoxContainer
var form: VBoxContainer
var list: VBoxContainer
var scroll: ScrollContainer
var current := ""
var signature := ""

func _init(owner: Node) -> void:
	hub = owner

func is_open() -> bool:
	var root = w.get("root")
	return root != null and is_instance_valid(root) and not (root as Control).get_meta("rpg_closing", false)

func entries() -> Array:
	var out := []
	if hub.has("friends"): out.append({"id":"friends", "label":tr("친구"), "badge":int(hub.counts.requests)})
	if hub.has("people"): out.append({"id":"online", "label":tr("접속 중")})
	out.append({"id":"village", "label":tr("우리 마을"), "badge":int(hub.counts.knocks)})
	out.append({"id":"party", "label":tr("파티")})
	return out

func build(drawer: Dictionary, tab := "") -> void:
	w = drawer
	var column: VBoxContainer = w.body
	tabs = RpgUi.tab_strip(column, entries(), show_tab)
	form = VBoxContainer.new()
	form.name = "Form"
	form.add_theme_constant_override("separation", 6)
	column.add_child(form)
	scroll = ScrollContainer.new()
	scroll.name = "Scroll"
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	# The drawer ends above the chat box (y 548 on the design canvas).
	scroll.custom_minimum_size = Vector2(0, 236)
	column.add_child(scroll)
	list = VBoxContainer.new()
	list.name = "List"
	list.add_theme_constant_override("separation", 6)
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(list)
	var first: String = tab if not tab.is_empty() else ("friends" if hub.has("friends") else "village")
	RpgUi.select_tab(tabs, first)

func show_tab(id: String) -> void:
	if not is_open(): return
	if str(tabs.get_meta("selected", "")) != id:
		RpgUi.select_tab(tabs, id)
		return
	current = id
	signature = ""
	for child in form.get_children():
		form.remove_child(child)
		child.queue_free()
	match id:
		"friends": name_form(tr("이름으로 친구 신청"), "add_friend", tr("친구 신청"), func(n): hub.request_friend(n))
		"village": name_form(tr("마을로 초대할 이름"), "invite", tr("마을 초대"), func(n): hub.invite(n, "village"))
		"party": name_form(tr("파티로 초대할 이름"), "party", tr("파티 초대"), func(n): hub.invite(n, "party"))
	refresh()

## The name field and its button at the top of a tab.
func name_form(placeholder: String, icon: String, tip: String, call: Callable) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	form.add_child(row)
	var name_field := RpgUi.field(row, placeholder, false, Callable(), false)
	name_field.theme_type_variation = "LineEdit"
	name_field.custom_minimum_size = Vector2(0, 36)
	name_field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_field.max_length = 24
	name_field.keep_editing_on_text_submit = false
	var send := func() -> void:
		var value := name_field.text.strip_edges()
		if value.is_empty(): return
		name_field.clear()
		name_field.release_focus()
		call.call(value)
	name_field.text_submitted.connect(func(_v): send.call())
	var go := Button.new()
	go.theme_type_variation = "PrimaryButton"
	go.focus_mode = Control.FOCUS_NONE
	go.custom_minimum_size = Vector2(40, 36)
	go.icon = RpgUi.icon_texture(icon)
	go.expand_icon = true
	go.add_theme_constant_override("icon_max_width", 24)
	RpgUi.name_tip(go, tip)
	go.pressed.connect(send)
	row.add_child(go)

func refresh() -> void:
	if not is_open() or current.is_empty(): return
	var data := {}
	match current:
		"friends": data = {"f":hub.people.get("friends", []), "r":hub.people.get("requests", {})}
		"online": data = {"o":hub.people.get("online", []), "n":hub.people.get("online_count", 0), "roster":hub.people.get("roster", "")}
		"village": data = {"m":hub.people.get("my_village", {}), "v":hub.overview.get("village", {}), "i":hub.overview.get("invites", []), "vis":hub.overview.get("visiting", false), "p":hub.people.get("prefs", {}), "k":hub.overview.get("knocks", [])}
		"party": data = {"p":hub.overview.get("party", {}), "r":hub.overview.get("pending_rewards", [])}
	var stamp := current + JSON.stringify(data)
	if stamp == signature: return
	signature = stamp
	# Out of the tree at once: rows rebuilt with the same names must not be renamed.
	for child in list.get_children():
		list.remove_child(child)
		child.queue_free()
	match current:
		"friends": friends_page()
		"online": online_page()
		"village": village_page()
		"party": party_page()

func refresh_overview() -> void:
	if current in ["village", "party"]: refresh()
	if is_open() and is_instance_valid(tabs):
		var buttons: Dictionary = tabs.get_meta("buttons", {})
		if buttons.has("friends"): RpgUi.badge(buttons.friends, int(hub.counts.requests))
		if buttons.has("village"): RpgUi.badge(buttons.village, int(hub.counts.knocks))

func caption(text: String) -> Label:
	var label := RpgUi.label(list, text, RpgUi.T_CAPTION, RpgUi.PAPER_MUTED, false)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return label

func section(text: String) -> void:
	var label := RpgUi.label(list, text, RpgUi.T_SECTION, RpgUi.PAPER_INK, false)
	label.add_theme_font_override("font", RpgUi.FONT_STRONG)
	RpgUi.divider(list, RpgUi.PAPER_LINE, 300)

## Where someone is, in a few words: their place, whose village and floor when known.
static func where_text(entry: Dictionary) -> String:
	var where: Dictionary = entry.get("where") if entry.get("where") is Dictionary else {}
	var place := str(where.get("place", entry.get("place", "")))
	var text: String = TranslationServer.translate(PLACES.get(place, ""))
	if not str(where.get("host_name", "")).is_empty() and place in ["village", "home"]:
		text = TranslationServer.translate("%s님의 마을") % str(where.host_name)
		if place == "home": text += " · " + TranslationServer.translate("집 %d층") % (int(where.get("floor", 0)) + 1)
	return text

static func seen_text(last_seen) -> String:
	if last_seen == null: return ""
	var days := int((Time.get_unix_time_from_system() - float(last_seen)) / 86400.0)
	if days <= 0: return TranslationServer.translate("오늘") if Time.get_unix_time_from_system() - float(last_seen) > 600 else TranslationServer.translate("방금")
	if days == 1: return TranslationServer.translate("어제")
	return TranslationServer.translate("%d일 전") % days

static func state_of(entry: Dictionary) -> String:
	if not bool(entry.get("online", true)): return "offline"
	var where: Dictionary = entry.get("where") if entry.get("where") is Dictionary else {}
	var place := str(where.get("place", entry.get("place", "village")))
	return "online" if place in ["village", "home"] else "away"

static func character(entry: Dictionary) -> String:
	var avatar: Dictionary = entry.get("avatar") if entry.get("avatar") is Dictionary else {}
	return str(avatar.get("character", "explorer_b"))

## The … menu next to a person: the rarer actions, kept off the row.
func more_menu(button: Button, items: Array) -> void:
	var menu := PopupMenu.new()
	button.add_child(menu)
	for i in items.size(): menu.add_item(str(items[i][0]), i)
	menu.id_pressed.connect(func(i: int) -> void: (items[i][1] as Callable).call())
	button.pressed.connect(func() -> void:
		menu.position = Vector2i(button.get_screen_position() + Vector2(0, button.size.y))
		menu.popup())

func friends_page() -> void:
	var requests: Dictionary = hub.people.get("requests", {}) if hub.people.get("requests") is Dictionary else {}
	var incoming: Array = requests.get("incoming", [])
	var outgoing: Array = requests.get("outgoing", [])
	if not incoming.is_empty():
		section(tr("받은 친구 신청"))
		for entry in incoming:
			RpgUi.person_row(list, {"username":entry.username, "character":"f1", "state":"online", "where":tr("친구가 되고 싶어 해요")}, [
				{"icon":"accept", "tip":tr("수락"), "call":func(): hub.answer_request(str(entry.id), "accept")},
				{"icon":"decline", "tip":tr("거절"), "call":func(): hub.answer_request(str(entry.id), "decline")}])
	var friends: Array = hub.people.get("friends", [])
	section(tr("친구 %d명") % friends.size())
	if friends.is_empty(): caption(tr("아직 친구가 없어요. 위에서 이름으로 신청해 보세요."))
	for entry in friends:
		var online := bool(entry.get("online", false))
		var where := where_text(entry) if online else seen_text(entry.get("last_seen"))
		var row := RpgUi.person_row(list, {"username":entry.username, "character":character(entry), "state":state_of(entry), "where":where}, [
			{"icon":"visit", "tip":tr("놀러가기") if bool(entry.get("drop_in", false)) else tr("놀러가기 (문 두드리기)"), "disabled":not online, "call":func(): hub.visit(str(entry.id), str(entry.username))},
			{"icon":"invite", "tip":tr("내 마을로 초대"), "disabled":not online, "call":func(): hub.invite(str(entry.username), "village")},
			{"icon":"whisper", "tip":tr("귓속말"), "disabled":not online, "call":func(): hub.chat.whisper(str(entry.username))},
			{"icon":"more", "tip":tr("더 보기")}])
		more_menu(row.get_node("Act_more"), [[tr("파티로 초대"), func(): hub.invite(str(entry.username), "party")],
			[tr("친구 끊기"), func(): hub.remove_friend(str(entry.id))],
			[tr("차단"), func(): hub.block(str(entry.id), str(entry.username))],
			[tr("신고"), func(): hub.report(str(entry.id), str(entry.username))]])
	if not outgoing.is_empty():
		section(tr("보낸 신청"))
		for entry in outgoing:
			RpgUi.person_row(list, {"username":entry.username, "character":"f1", "state":"offline", "where":tr("답을 기다려요")}, [
				{"icon":"decline", "tip":tr("신청 취소"), "call":func(): hub.answer_request(str(entry.id), "cancel")}])
	var blocked: Array = hub.people.get("blocked", [])
	if not blocked.is_empty():
		section(tr("차단한 사람"))
		for entry in blocked:
			RpgUi.person_row(list, {"username":entry.username, "character":"f1", "state":"offline", "where":""}, [
				{"icon":"lock", "tip":tr("차단 풀기"), "call":func(): hub.unblock(str(entry.id))}])

func online_page() -> void:
	var online: Array = hub.people.get("online", [])
	section(tr("지금 %d명 접속 중") % int(hub.people.get("online_count", online.size())))
	if str(hub.people.get("roster", "all")) == "off": caption(tr("이 월드는 접속자 목록을 보여 주지 않아요."))
	elif online.is_empty(): caption(tr("지금은 나 혼자예요."))
	for entry in online:
		var friend := bool(entry.get("friend", false))
		var actions := []
		if not friend: actions.append({"icon":"add_friend", "tip":tr("친구 신청"), "call":func(): hub.request_friend("", str(entry.id))})
		else: actions.append({"icon":"whisper", "tip":tr("귓속말"), "call":func(): hub.chat.whisper(str(entry.username))})
		actions.append({"icon":"more", "tip":tr("더 보기")})
		var row := RpgUi.person_row(list, {"username":entry.username, "character":character(entry), "state":state_of(entry), "where":where_text(entry)}, actions)
		more_menu(row.get_node("Act_more"), [[tr("놀러가기"), func(): hub.visit(str(entry.id), str(entry.username))],
			[tr("차단"), func(): hub.block(str(entry.id), str(entry.username))],
			[tr("신고"), func(): hub.report(str(entry.id), str(entry.username))]])

func village_page() -> void:
	var visiting := bool(hub.overview.get("visiting", false))
	if visiting:
		caption(tr("%s님의 마을에 놀러 와 있어요.") % str(hub.overview.get("host_name", "")))
		if hub.place_kind == "village" and hub.place.get("social"):
			var home := RpgUi.button(list, tr("내 마을로 돌아가기"), func(): hub.place.social.return_home(), "primary", "md")
			home.icon = RpgUi.icon_texture("home")
	var my: Dictionary = hub.people.get("my_village", {}) if hub.people.get("my_village") is Dictionary else {}
	var invites: Array = hub.overview.get("invites", []) if hub.overview.get("invites") is Array else []
	if not invites.is_empty():
		section(tr("받은 초대"))
		for invitation in invites:
			var village := str(invitation.get("kind", "")) == "village"
			RpgUi.person_row(list, {"username":invitation.get("sender", ""), "character":"f1", "state":"online", "where":tr("마을로 초대했어요") if village else tr("파티로 초대했어요")}, [
				{"icon":"accept", "tip":tr("수락"), "call":func(): hub.answer_invite(invitation, "accept")},
				{"icon":"decline", "tip":tr("거절"), "call":func(): hub.answer_invite(invitation, "decline")}])
	var knocks: Array = my.get("knocks", hub.overview.get("knocks", []))
	if knocks is Array and not knocks.is_empty():
		section(tr("문 두드리는 사람"))
		for knock in knocks:
			RpgUi.person_row(list, {"username":knock.get("username", knock.get("sender", "")), "character":"f1", "state":"online", "where":tr("놀러 오고 싶어 해요")}, [
				{"icon":"accept", "tip":tr("들이기"), "call":func(): hub.answer_invite({"id":knock.id, "kind":"knock"}, "accept")},
				{"icon":"decline", "tip":tr("거절"), "call":func(): hub.answer_invite({"id":knock.id, "kind":"knock"}, "decline")}])
	section(tr("마을에 있는 사람"))
	var people := []
	if not my.is_empty():
		var host: Dictionary = my.get("host", {})
		people.append({"id":str(host.get("id", "")), "username":str(host.get("username", "")), "online":bool(host.get("online", true)), "place":"village", "host":true})
		for guest in my.get("guests", []): people.append(guest)
	else:
		var village: Dictionary = hub.overview.get("village", {}) if hub.overview.get("village") is Dictionary else {}
		for player in village.get("players", []):
			people.append({"id":str(player.get("id", "")), "username":str(player.get("username", "")), "online":bool(player.get("online", true)), "place":"village", "host":str(player.get("id", "")) == str(hub.overview.get("host_id", ""))})
	var self_id := str(hub.overview.get("self_id", ""))
	var hosting := not visiting
	for person in people:
		var actions := []
		if hosting and not bool(person.get("host", false)) and str(person.get("id", "")) != self_id:
			actions.append({"icon":"leave", "tip":tr("방문 끝내기"), "call":func(): hub.eject(str(person.id))})
		var where := where_text(person)
		if bool(person.get("host", false)): where = tr("마을 주인")
		var row := RpgUi.person_row(list, {"username":person.username, "character":"f1", "state":"online" if bool(person.get("online", true)) else "offline", "where":where}, actions)
		if bool(person.get("host", false)):
			var crown := RpgUi.icon("crown", 20)
			crown.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			row.add_child(crown)
			row.move_child(crown, 2)
	if people.size() <= 1: caption(tr("아직 아무도 놀러 오지 않았어요. 위에서 이름으로 초대해 보세요."))
	var out: Array = my.get("invites_out", [])
	if out is Array and not out.is_empty():
		caption(tr("보낸 초대: %s") % ", ".join(PackedStringArray(out.map(func(i): return str(i.get("username", ""))))))
	if hub.has("friends"):
		section(tr("나의 공개 설정"))
		var prefs: Dictionary = hub.people.get("prefs", {}) if hub.people.get("prefs") is Dictionary else {}
		toggle(tr("접속 숨기기"), bool(prefs.get("appear_offline", false)), func(on): hub.set_pref("appear_offline", on))
		toggle(tr("친구는 문 두드리지 않고 들어오기"), str(prefs.get("drop_in", "off")) == "friends", func(on): hub.set_pref("drop_in", "friends" if on else "off"))
		toggle(tr("친구 신청 받기"), str(prefs.get("requests", "everyone")) == "everyone", func(on): hub.set_pref("requests", "everyone" if on else "nobody"))

func toggle(text: String, on: bool, call: Callable) -> void:
	var box := CheckBox.new()
	box.text = text
	box.button_pressed = on
	box.focus_mode = Control.FOCUS_NONE
	box.add_theme_color_override("font_color", RpgUi.PAPER_INK)
	box.toggled.connect(func(value: bool) -> void: call.call(value))
	list.add_child(box)

func party_page() -> void:
	var party: Dictionary = hub.overview.get("party") if hub.overview.get("party") is Dictionary else {}
	var main = hub.place if hub.place_kind in ["village", "survival"] else null
	if party.is_empty():
		caption(tr("파티를 만들면 함께 탐험을 떠날 수 있어요. 최대 3명."))
		var create := func() -> void:
			if (await hub.act("/v1/party")).ok: hub.notice(tr("파티를 만들었어요"), "success")
		RpgUi.button(list, tr("파티 만들기"), create, "primary", "md")
	else:
		section(tr("파티 %d/3명") % party.get("members", []).size())
		for member in party.get("members", []):
			var leader := str(member.get("id", "")) == str(party.get("leader_id", ""))
			var row := RpgUi.person_row(list, {"username":member.get("username", ""), "character":"f1", "state":"online" if bool(member.get("online", false)) else "offline", "where":tr("파티장") if leader else ""}, [])
			if leader:
				var crown := RpgUi.icon("crown", 20)
				crown.size_flags_vertical = Control.SIZE_SHRINK_CENTER
				row.add_child(crown)
		if party.get("run_id") != null and bool(party.get("can_join_run", false)) and main:
			RpgUi.button(list, tr("협동 탐험으로 돌아가기"), func(): main.start_run("forest", "standard", "", str(party.run_id)), "primary", "md")
		var leading := str(party.get("leader_id", "")) == str(hub.overview.get("self_id", ""))
		if leading and party.get("run_status") != "active":
			if hub.place_kind == "village" and main: start_row(main)
			else: caption(tr("마을에서 함께 출발할 수 있어요."))
		var quit := func() -> void:
			if (await hub.act("/v1/party/leave")).ok: hub.notice(tr("파티에서 나왔어요"), "info")
		var leave := RpgUi.button(list, tr("파티 나가기"), quit, "normal", "md")
		leave.icon = RpgUi.icon_texture("leave")
	for reward in hub.overview.get("pending_rewards", []):
		var claim := func() -> void:
			if (await hub.act("/v1/coop/runs/" + str(reward.id) + "/claim")).ok: hub.notice(tr("협동 탐험 보상을 받았어요"), "success")
		RpgUi.button(list, tr("협동 탐험 보상 받기"), claim, "gold", "md")

## The leader's start row: region and difficulty, then everyone in the party leaves together.
func start_row(main: Node) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	list.add_child(row)
	var region := OptionButton.new()
	# The maps in the expedition window's order (server catalog: the tutorial first), else the three.
	var maps: Array = []
	for entry in main.get("me").get("catalog", {}).get("maps", []):
		if entry is Dictionary: maps.append(entry)
	maps.sort_custom(func(a, b): return int(a.get("order", 0)) < int(b.get("order", 0)))
	if maps.is_empty(): maps = [{"id":"forest", "name":"솔바람 숲"}, {"id":"quarry", "name":"노을 채석장"}, {"id":"frost", "name":"서리빛 분지"}]
	for entry in maps: region.add_item(preload("res://scripts/i18n.gd").server(str(entry.get("name", entry.id))))
	region.focus_mode = Control.FOCUS_NONE
	row.add_child(region)
	var difficulty := OptionButton.new()
	for title in [tr("산책"), tr("탐험"), tr("개척")]: difficulty.add_item(title)
	difficulty.focus_mode = Control.FOCUS_NONE
	row.add_child(difficulty)
	var depart := func() -> void:
		var result: Dictionary = await hub.act("/v1/party/runs", {"map_id":str(maps[region.selected].id), "difficulty":["relaxed", "standard", "veteran"][difficulty.selected]})
		if result.ok:
			hub.close_window()
			await main.start_run("forest", "standard", "", str(result.data.id))
	var go := RpgUi.button(list, tr("파티 함께 출발"), depart, "gold", "md")
	go.icon = RpgUi.icon_texture("expedition")
