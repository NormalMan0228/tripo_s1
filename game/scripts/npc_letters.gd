extends RefCounted
## Letters in the mailbox, with the residents' event letters (server/npc_letters.py,
## docs/design/NPC_LETTERS_API.md): a letter with an `event` is worded by its event.type
## (a board request done, a resident's village anniversary, moving in or out); every other
## letter (hearts, the story letter, a resident request's thanks) keeps npc_gifts.gd's words.
## The mailbox (field_objects.gd use_mailbox) reads letters through letter_lines().
## Player-to-player letters are not part of this yet.
const NpcGifts = preload("res://scripts/npc_gifts.gd")
const QuestsLib = preload("res://scripts/quests.gd")

## Words per event type: the heading after the sender's name, then the pages.
const EVENTS := {
	"request_done":{"head":"게시판 부탁을 들어줘서",
		"lines":["게시판에 붙여 둔 부탁, 정말 들어줄 줄은 몰랐어요. 덕분에 하루가 한결 가벼워졌어요.","다음에 게시판에서 또 만나요. 고마워요!"]},
	"resident_day":{"head":"마을 기념일",
		"lines":["오늘은 내가 이 마을에 처음 온 날이에요. 같이 축하해 줄 이웃이 있다니 참 기뻐요.","오늘 하루, 마을 어디서든 마주치면 꼭 인사해 줘요!"]},
	"move_in":{"head":"이사 왔어요",
		"lines":["새 집으로 이사 왔어요! 짐 정리가 끝나면 꼭 놀러 와 주세요.","앞으로 이웃으로 잘 부탁해요."]},
	"move_out":{"head":"잘 있어요",
		"lines":["정든 마을을 잠시 떠나게 됐어요. 함께한 날들, 오래 기억할게요.","언젠가 다시 만나요. 건강해요!"]},
}
const OTHER := {"head":"마을 소식", "lines":["마을 소식을 전해요. 늘 고마워요!"]}

static func t(text: String) -> String:
	return TranslationServer.translate(text)

## True for a letter the event table words (it has an event block from the server).
static func is_event(letter: Dictionary) -> bool:
	return letter.get("event") is Dictionary and not str(letter.event.get("type", "")).is_empty()

## One letter as dialogue pages ("✉ 나루의 편지 · 마을 기념일\n…").
static func letter_lines(letter: Dictionary) -> Array:
	if not is_event(letter): return NpcGifts.letter_lines(letter)
	var event: Dictionary = letter.event
	var kind := str(event.get("type", ""))
	var words: Dictionary = EVENTS.get(kind, OTHER)
	var sender := t(str(letter.get("name", "")))
	var head: String = t("✉ %s의 편지 · %s") % [sender, t(str(words.head))]
	var body: Array = words.lines
	# A board request's thanks names the request (the residents' own book words, quests.gd).
	if kind == "request_done":
		var payload = event.get("payload")
		var id := str(payload.get("quest_id", "")) if payload is Dictionary else ""
		var title := t(str(QuestsLib.BOOK.get(id, {}).get("title", "")))
		if not title.is_empty(): head += "\n" + t("「%s」") % title
		# 모카 and 노을 write their own thanks for their requests (npc_gifts.gd QUEST_LETTERS).
		var npc := str(letter.get("npc", ""))
		if NpcGifts.QUEST_LETTERS.has(npc): body = NpcGifts.QUEST_LETTERS[npc]
	var pages := [head + "\n" + t(str(body[0]))]
	for line in body.slice(1): pages.append(t(str(line)))
	var gift = letter.get("gift")
	if gift is Dictionary: pages.append(t("편지와 함께 선물이 왔어요: %s. 가방을 확인해 보세요!") % str(gift.get("name", "")))
	return pages
