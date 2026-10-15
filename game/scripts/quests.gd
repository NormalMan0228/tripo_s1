extends Node3D
## Residents' requests (부탁), one per resident the player knows (server/quests.py keeps the rules,
## the progress and the starseed rewards; this script has the words and the village's side).
## They open once the opening chapter (story.gd) is over and 모카's letter is read, or at once for
## an account without the chapter, so the demo chapter is never crowded.
##
## Conversations: every dialogue box that shows a resident (main.gd talk_to for the cast,
## shadow_folk.gd for the walkers, studio.gd inside buildings) asks choice()/room_choice() for the
## resident's request: "✦ 부탁 들어주기" (offer -> "맡겨 줘요"), "부탁 이야기" (how far it is),
## "✦ 부탁한 것 건네기" (the hand-over: the resident's thanks, a star burst, stars flying into
## the counter as it ticks up; 모카 and 노을 also write a letter to the mailbox).
## The village (this node, a child of story.gd): the objective tracker's lines (one request at a
## time plus a count of the others, guide.gd turns them into rows), the route guide's goals (the
## place to go, then the resident; another island leads to this island's signpost first), "!" and
## "?" over residents with a request waiting or ready, the signpost reports of 나루's request and
## the request book (부탁 수첩, the tracker's last line).
const Town := preload("res://scripts/town.gd")
const Residents := preload("res://scripts/residents.gd")
const DayFolk := preload("res://scripts/day_folk.gd")
const Fx := preload("res://scripts/fx.gd")
const RpgUi := preload("res://scripts/rpg_ui.gd")
const Guide := preload("res://scripts/guide.gd")
const Farm := preload("res://scripts/farm.gd")
const NpcGifts := preload("res://scripts/npc_gifts.gd")
const Daylight := preload("res://scripts/daylight.gd")
const Interiors := preload("res://scripts/interiors.gd")

## Guide keys: "story_quest:<id>" (a request's goal) and the book's line (story.gd routes "story_*").
const KEY := "story_quest:"
const BOOK_KEY := "story_quest_book"
const STAR_ICON := "res://assets/starseed.svg"
## Island names (field_objects.gd ISLANDS) and where 모카 waits while the chapter holds her (story.gd).
const ISLANDS := {"square":"물결빛 광장","fields":"풍차 들판","garden":"정원 언덕","camp":"캠프 초원","lighthouse":"등대섬"}
const MOKA_AT := Vector2(-59.6, -29.9)
## The words of each request (Korean source; translated where shown).
##   ask: the request; accepted: the answer to "맡겨 줘요"; remind: how far it is (%d/%d when it
##   counts); already: the answer when it is done the moment it is taken (taken at its place);
##   thanks: the hand-over; goal: the tracker line (%d/%d when it counts); place: where
##   the guide leads before it is done ("" for the resident, "-" for nowhere, a Town place id,
##   "farm", "forage:<kind>", "tree:<kind>", "signpost", "home", "npc:<id>", "visit" for the
##   request's places); deliver/reply: a message passed to another resident (talk requests).
const BOOK := {
	"moka_pie":{"title":"모카의 사과 파이", "place":"apple",
		"ask":["테라스에 오는 손님들께 갓 구운 사과 파이를 대접하고 싶어.", "풍차 들판 서쪽 과수원에서 사과 세 개만 따다 줄래? 둥근 나무를 살살 흔들어도 떨어져."],
		"accepted":"고마워! 오븐은 미리 데워 둘게.",
		"remind":"사과는 과수원 상자나 둥근 나무에서 얻을 수 있어. 지금 %d/%d개야.",
		"thanks":["우와, 빨갛게 잘 익었다! 오늘 오후엔 테라스에 파이 냄새가 퍼지겠어.", "고마워. 작은 보답이야, 받아 줘!"],
		"goal":"사과 %d/%d개 모으기"},
	"naru_islands":{"title":"나루의 섬 한 바퀴", "place":"signpost",
		"ask":["길잡이의 첫 수업! 이 마을은 다섯 섬이 다리로 이어져 있어.", "서로 다른 섬 세 곳의 이정표를 찾아가 봐. 이정표에서는 다른 섬으로 바로 갈 수도 있어!"],
		"accepted":"좋아, 출발! 이정표는 섬마다 길가에 서 있어.",
		"remind":"이정표를 %d/%d곳 찾았네. 금빛 길을 따라가 봐!",
		"thanks":["벌써 세 섬이나! 이제 어디든 혼자 다닐 수 있겠다.", "길잡이 수업 통과! 이건 수업료… 가 아니라 장학금이야."],
		"goal":"이정표 %d/%d곳 찾아가기"},
	"sora_outfit":{"title":"소라의 새 옷 맞춤", "place":"",
		"ask":["어머, 이사 오느라 옷이 먼지투성이네요.", "제 옷장에서 마음에 드는 새 차림으로 갈아입어 볼래요? 색 하나만 바꿔도 기분이 달라져요."],
		"accepted":"좋아요! 옷장은 언제든 열어 드릴게요.",
		"remind":"옷장에서 새 차림을 골라 저장해 보세요. 저한테 말하면 옷장을 열어 드려요.",
		"thanks":["정말 잘 어울려요! 섬 바람이랑 색이 딱 맞네요.", "제 옷을 입어 준 첫 손님이에요. 고마워요!"],
		"goal":"옷장에서 새 차림 갈아입기"},
	"moru_soup":{"title":"모루의 야영 수프", "place":"forage:mushroom",
		"ask":["숲에서 밤을 버티려면 따뜻한 수프가 최고야.", "숲 그늘에서 버섯 두 개만 모아 와 줄래? 나무 밑 그늘진 곳에 잘 자라."],
		"accepted":"고마워. 냄비는 내가 올려 둘게.",
		"remind":"버섯은 숲 그늘에 숨어 있어. 지금 %d/%d개.",
		"thanks":["좋은 버섯이네. 오늘 밤 수프는 특별하겠어.", "고맙다. 숲에 갈 때 든든할 거야."],
		"goal":"숲 버섯 %d/%d개 모으기"},
	"haeru_fish":{"title":"해루의 바다 저녁상", "place":"sea",
		"ask":["오늘 저녁은 바다 생선구이를 하고 싶은데, 제 낚싯대가 영 시원찮네요.", "등대 부두에서 바다 물고기 한 마리만 낚아 와 줄래요? 어떤 물고기든 좋아요!"],
		"accepted":"고마워요! 숯불은 제가 피워 둘게요.",
		"remind":"등대 부두 낚시터에서 바다 쪽으로 찌를 던져 봐요. 지금 %d/%d마리예요.",
		"thanks":["우와, 싱싱하다! 오늘 저녁은 잔치예요.", "고마워요. 다음엔 같이 낚시해요!"],
		"goal":"바다 물고기 %d/%d마리 낚기"},
	"daon_gift":{"title":"다온의 마음 배달", "place":"",
		"ask":["선물은 말 없는 편지 같아요. 받는 사람 얼굴이 환해지거든요.", "마을 주민 누구에게든 선물을 하나 건네 볼래요? 저한테 줘도 좋고요!"],
		"accepted":"좋아요! 이야기하다 '선물하기'를 고르면 돼요.",
		"remind":"주민과 이야기하다 '선물하기'를 골라 보세요. 가방의 물건을 건넬 수 있어요.",
		"thanks":["들었어요! 선물 받은 주민이 하루 종일 웃고 다니던데요.", "마음 배달 성공! 우편배달부가 드리는 작은 답례예요."],
		"goal":"주민에게 선물 %d/%d번 하기"},
	"hangyeol_turnips":{"title":"한결의 첫 수확", "place":"farm",
		"ask":["햇살 텃밭 흙이 올해 유난히 좋아요.", "순무 씨앗을 심고 물 한 번만 주면 금방 자라요. 순무 두 개만 나눠 줄래요? 새 흙 맛을 보고 싶거든요."],
		"accepted":"고마워요! 씨앗은 가방에 있을 거예요.",
		"remind":"씨앗을 심고 물을 주면 돼요. 지금 순무 %d/%d개예요.",
		"thanks":["오, 알이 꽉 찼네요! 첫 수확 솜씨가 보통이 아닌데요.", "고마워요. 농부의 감사 인사예요."],
		"goal":"순무 %d/%d개 수확하기"},
	"noeul_light":{"title":"노을의 골목 불빛", "place":"-",
		"ask":["밤마다 등불을 밝히지만, 등불이 닿지 않는 어두운 골목이 있어요.", "빛나는 물건 하나를 마을에 놓아 줄래요? 램프든 촛불이든, 직접 만든 거라면 더 좋고요."],
		"accepted":"고마워요. 밤에 그 불빛을 보러 갈게요.",
		"remind":"가방(I)에서 빛나는 물건을 꺼내 마을에 놓아 보세요. 없다면 공방(C)에서 만들 수 있어요.",
		"thanks":["어젯밤 그 불빛 덕분에 골목이 환했어요. 그림자들도 길을 잃지 않았대요.", "등불지기가 드리는 작은 답례예요. 고마워요."],
		"goal":"빛나는 물건 마을에 놓기"},
	"boram_catch":{"title":"보람의 낚시 도감", "place":"pond",
		"ask":["…쉿. 물고기가 놀라요.", "낚시꾼이라면 도감부터 채워야죠. 서로 다른 물고기 두 종류를 낚아 볼래요? 연못이든 바다든 좋아요."],
		"accepted":"좋아요. 찌가 쏙 들어가면 망설이지 말고 당겨요.",
		"remind":"다른 종류를 %d/%d가지 낚았네요. 연못과 바다는 사는 물고기가 달라요.",
		"thanks":["두 종류나! 도감이 금방 두꺼워지겠어요.", "낚시꾼끼리 주고받는 작은 선물이에요."],
		"goal":"서로 다른 물고기 %d/%d종 낚기"},
	"miso_flowers":{"title":"미소의 광장 꽃장식", "place":"forage:flower",
		"ask":["쓱싹쓱싹… 광장은 깨끗한데, 뭔가 허전하지 않아요?", "길가에 핀 들꽃 세 송이만 꺾어다 줄래요? 벤치 옆에 꽂아 두면 다들 웃을 거예요."],
		"accepted":"고마워요! 꽃병은 제가 찾아 둘게요.",
		"remind":"들꽃은 섬 곳곳 풀숲에 피어 있어요. 지금 %d/%d송이.",
		"thanks":["와, 향기 좋다! 광장이 반짝반짝해졌어요.", "청소부의 작은 답례예요. 고마워요!"],
		"goal":"들꽃 %d/%d송이 모으기"},
	"yunjae_regards":{"title":"윤재의 안부 전하기", "place":"npc:poet",
		"ask":["실례지만, 부탁 하나 드려도 되겠습니까?", "정원 언덕의 시인 가람 씨에게 제 안부를 전해 주시겠습니까? 지난번 시가 무척 좋았다고요."],
		"accepted":"감사합니다. 가람 씨는 낮에 정원 언덕 정자에 자주 앉아 있지요.",
		"remind":"가람 씨를 만나면 제 안부를 전해 주십시오. 낮에는 정원 언덕 정자에 자주 계십니다.",
		"thanks":["가람 씨가 그렇게 말했습니까? 허허, 오늘 산책은 유난히 즐겁겠군요.", "작은 답례입니다. 받아 주십시오."],
		"goal":"가람에게 윤재의 안부 전하기",
		"deliver":"✦ 윤재의 안부 전하기",
		"reply":["윤재 씨가요? 그 시를 기억해 주셨다니… 고맙다고 꼭 전해 주세요."]},
	"haneul_stars":{"title":"하늘의 밤하늘 관측", "place":"visit",
		"ask":["하암… 낮에는 졸려도, 밤이 되면 눈이 반짝 떠져요.", "해가 진 뒤에 별빛 천문대로 놀러 와요. 망원경으로 보는 별은 정말 달라요."],
		"accepted":"기다릴게요. 저녁 일곱 시가 지나면 천문대 불이 켜져요.",
		"already":"어머, 벌써 천문대에 와 있었네요! 오늘 밤 별이 참 잘 보여요.",
		"remind":"해가 진 뒤(저녁 7시~새벽 6시)에 별빛 천문대 안으로 들어와 봐요.",
		"thanks":["와 줬군요! 오늘 밤 고래자리가 유난히 또렷해요.", "별지기의 작은 선물이에요. 좋은 꿈 꿔요."],
		"goal":"밤에 별빛 천문대 들어가 보기"},
	"chorok_herbs":{"title":"초록의 향초 주머니", "place":"herb",
		"ask":["향초 냄새 좋죠? 말린 향초로 주머니를 만들고 있어요.", "향초 세 줌만 모아 줄래요? 정원 향초밭이나 길가 덤불에서 찾을 수 있어요."],
		"accepted":"고마워요! 주머니 끈은 제가 묶어 둘게요.",
		"remind":"향초는 정원 향초밭이나 덤불 속에 있어요. 지금 %d/%d줌.",
		"thanks":["음, 향이 진하다! 향초 주머니가 금방 완성되겠어요.", "정원사의 답례예요. 고마워요!"],
		"goal":"향초 %d/%d줌 모으기"},
	"bau_pinecones":{"title":"바우의 캠프 불쏘시개", "place":"tree:pine",
		"ask":["돌문 너머 숲은 밤이 길어요. 불을 빨리 붙이려면 불쏘시개가 필요하죠.", "뾰족한 나무를 흔들면 솔방울이 떨어져요. 세 개만 주워 와 줄래요?"],
		"accepted":"고마워요! 마른 솔방울일수록 잘 타요.",
		"remind":"뾰족한 나무를 흔들어 보세요. 솔방울 %d/%d개.",
		"thanks":["좋아요, 바싹 말랐네요! 다음 탐험은 든든하겠어요.", "탐험가의 답례예요. 숲에서 조심해요!"],
		"goal":"솔방울 %d/%d개 줍기"},
	"dure_carrots":{"title":"두레의 당근 케이크", "place":"farm",
		"ask":["풍차가 돌면 밀가루가 눈처럼 날려요. 오늘은 그 밀가루로 케이크를 구울 거예요.", "텃밭에서 당근 두 개만 길러 줄래요? 당근 씨앗은 가방에 있을 거예요."],
		"accepted":"고마워요! 반죽은 미리 해 둘게요.",
		"remind":"당근 씨앗을 심고 물을 주면 돼요. 지금 %d/%d개.",
		"thanks":["와, 주황빛이 예쁘다! 케이크가 폭신하게 나오겠어요.", "방앗간의 답례예요. 고소한 냄새 맡으러 또 와요."],
		"goal":"당근 %d/%d개 수확하기"},
	"danbi_home":{"title":"단비의 집들이 점검", "place":"home",
		"ask":["이사 오고 나서 집은 좀 꾸몄어요? 잡화점 주인은 그게 제일 궁금하답니다.", "가방에 있는 물건 하나를 집 안에 놓아 보세요. 놓을 자리를 고르는 게 꾸미기의 시작이에요."],
		"accepted":"좋아요! 집에 들어가서 가방(I)을 열면 돼요.",
		"remind":"나의 집에 들어가 가방(I)에서 물건 하나를 골라 놓아 보세요.",
		"thanks":["어머, 벌써 집다운 집이 됐네요! 안목이 좋은데요.", "단골 손님께 드리는 작은 선물이에요."],
		"goal":"나의 집에 물건 하나 놓기"},
	"kongi_toy":{"title":"콩이의 보물 상자", "place":"",
		"ask":["헤헤, 내 보물 상자 보여 줄까? …아직 텅 비었어.", "장난감이나 동물 모양 물건을 하나 선물해 줄래? 만들어 줘도 좋아!"],
		"accepted":"약속이다! 손가락 걸었어!",
		"remind":"장난감이나 동물 모양 물건을 선물해 줘! 공방(C)에서 만들어도 돼.",
		"thanks":["우와아! 이거 내 보물 1호야!", "고마워! 이건 내가 아끼던 별씨야. 나눠 줄게!"],
		"goal":"콩이에게 장난감 선물하기"},
	"saebyeok_walk":{"title":"새벽의 밤바다 산책", "place":"visit",
		"ask":["밤 산책 중이에요. 이 시간엔 바다가 별을 비춰요.", "해가 진 뒤에 등대 부두 끝까지 걸어가 봐요. 물에 비친 별이 길처럼 이어져요."],
		"accepted":"좋아요. 밤바람이 차니까 따뜻하게 입어요.",
		"remind":"해가 진 뒤(저녁 7시~새벽 6시)에 등대 부두 끝까지 걸어가 봐요.",
		"thanks":["봤어요? 물 위의 별길. 우리만 아는 비밀 산책로예요.", "밤 산책 친구에게 주는 작은 선물이에요."],
		"goal":"밤에 등대 부두 끝까지 걷기"},
	"garam_lookout":{"title":"가람의 첫 줄", "place":"visit",
		"ask":["정자에 앉아 시를 짓던 참이에요. 그런데 오늘은 첫 줄이 안 떠오르네요.", "천문대 전망대에 올라 다섯 섬을 내려다보고 와 줄래요? 당신이 본 풍경이 제 첫 줄이 될 거예요."],
		"accepted":"고마워요. 전망대는 별빛 천문대 바로 옆이에요.",
		"remind":"천문대 전망대에 올라 다섯 섬을 내려다봐 주세요.",
		"thanks":["\"다리 넷이 다섯 섬을 꿰어 놓은 실 같았다\"… 첫 줄이 생겼어요!", "고마워요. 시인의 작은 답례예요."],
		"goal":"천문대 전망대에서 다섯 섬 내려다보기"},
}
## Where a visit request's places are: a Town place, or a room (entered, studio.gd).
const VISIT_SPOTS := {"lookout":"place:lookout", "lighthouse_pier":"place:sea", "observatory":"room:05_observatory"}

static func t(text: String) -> String:
	return TranslationServer.translate(text)

# ------------------------------------------------------------------ the server's list (shared)

## The last list the server sent for this login (Engine metadata: it outlives rooms and the field).
## A full list (/v1/quests, the requests' replies) is kept with its catalog digest; /v1/me's brief
## ({unlocked, catalog, states}) updates the kept list's states when the digest is the same.
## False when nothing could be taken (a brief without a matching full list: ask /v1/quests).
static func adopt_data(value, token: String) -> bool:
	if not value is Dictionary: return false
	if value.get("list") is Array:
		Engine.set_meta("quest_state", {"token":token, "unlocked":bool(value.get("unlocked", false)), "catalog":str(value.get("catalog", "")), "list":value.list})
		return true
	if not value.get("states") is Array: return false
	var kept := known(token)
	if kept.is_empty() or str(kept.get("catalog", "")) != str(value.get("catalog", "")): return false
	var live := {}
	for item in value.states:
		if item is Dictionary: live[str(item.get("id", ""))] = item
	var merged: Array = []
	for item in kept.get("list", []):
		var now: Dictionary = (item as Dictionary).duplicate()
		var fresh: Dictionary = live.get(str(now.get("id", "")), {})
		if not fresh.is_empty():
			now["state"] = str(fresh.get("state", now.get("state", "")))
			now["have"] = int(fresh.get("have", 0))
			if now.has("visited") or fresh.has("visited"): now["visited"] = fresh.get("visited", [])
		merged.append(now)
	Engine.set_meta("quest_state", {"token":token, "unlocked":bool(value.get("unlocked", false)), "catalog":str(kept.catalog), "list":merged})
	return true

static func known(token: String) -> Dictionary:
	var kept: Dictionary = Engine.get_meta("quest_state", {})
	return kept if str(kept.get("token", "")) == token and not token.is_empty() else {}

static func listed(token: String) -> Array:
	return known(token).get("list", [])

static func open_for(token: String) -> bool:
	return bool(known(token).get("unlocked", false))

static func entry_for(token: String, npc: String) -> Dictionary:
	if not open_for(token): return {}
	for entry in listed(token):
		if str(entry.get("npc", "")) == npc and BOOK.has(str(entry.get("id", ""))): return entry
	return {}

static func by_id(token: String, id: String) -> Dictionary:
	for entry in listed(token):
		if str(entry.get("id", "")) == id: return entry
	return {}

## "모카", "나루": the resident's name without the job. At night the day villagers walk as
## shadows named by their role ("수상한 그림자 · 별지기"): "하늘(별지기)" then, so the name on
## the tracker matches the one over their head. hour: the village's (-1: the player's clock).
static func npc_name(npc: String, hour := -1.0) -> String:
	if not DayFolk.has_look(npc): return t(str(Residents.resident(npc).get("title", npc))).split(" · ")[0]
	var name := DayFolk.title(npc).split(" · ")[0]
	var at := hour if hour >= 0.0 else Daylight.clock_hour()
	if DayFolk.is_day(npc, at): return name
	return "%s(%s)" % [name, Interiors.short_name(npc, at)]

static func title_of(entry: Dictionary) -> String:
	return t(str(BOOK.get(str(entry.get("id", "")), {}).get("title", "")))

static func counts(entry: Dictionary) -> bool:
	return "%d" in str(BOOK.get(str(entry.get("id", "")), {}).get("goal", ""))

## The tracker's goal for a request: how far it is, or whom to tell.
static func goal_text(entry: Dictionary, have: int, ready: bool, hour := -1.0) -> String:
	if ready:
		return (t("다 모았어요! %s에게 가져가기") if str(entry.get("kind", "")) == "bring" else t("다 됐어요! %s에게 알리기")) % npc_name(str(entry.npc), hour)
	var goal := t(str(BOOK[str(entry.id)].goal))
	return goal % [have, int(entry.get("need", 1))] if counts(entry) else goal

static func stars_text(stars: int) -> String:
	return t("별씨 +%d") % stars

## The resident's reminder, with how far it is when it counts.
static func remind_text(entry: Dictionary, have: int) -> String:
	var line := t(str(BOOK.get(str(entry.get("id", "")), {}).get("remind", "")))
	return line % [have, int(entry.get("need", 1))] if "%d" in line else line

# ------------------------------------------------------------------ conversations

## The request choice for a talk with `npc` in the village (main.gd, shadow_folk.gd), or [].
static func choice(app: Node, npc: String, speaker: String, portrait: String, anchor: Node3D) -> Array:
	if not is_instance_valid(app) or app.get("social") == null or app.social.visiting() or str(app.api.token).is_empty(): return []
	var say := func(lines: Array, choices: Array) -> void:
		if not is_instance_valid(app): return
		if is_instance_valid(anchor) and anchor.has_method("talk_to_player") and is_instance_valid(app.get("player")): anchor.talk_to_player(app.player.global_position)
		app.open_dialogue(speaker, portrait, lines, choices if not choices.is_empty() else [[t("알겠어요"), Callable()]])
	var done := func(kind: String, reply: Dictionary) -> void: village_done(app, anchor, kind, reply)
	# The village knows the bag and the look a moment before the server's next answer.
	var here: Node = village_of(app)
	return choice_for(app.api, npc, say, done, true, Callable(here, "state_of") if here else Callable())

## The same inside a building (studio.gd open_talk), in that room's dialogue box. A request taken
## in the room it asks for (하늘's observatory) counts the room at once.
static func room_choice(room: Node, id: String) -> Array:
	if not is_instance_valid(room) or str(room.api.token).is_empty(): return []
	var say := func(lines: Array, choices: Array) -> void:
		if is_instance_valid(room) and room.is_inside_tree() and room.npcs.has(id): room.open_talk(id, lines, choices)
	var done := func(kind: String, reply: Dictionary) -> void: room_done(room, id, kind, reply)
	return choice_for(room.api, id, say, done, false, Callable(), place_of_room(str(room.get("room"))))

## The visit place a room is ("observatory" for 05_observatory), or "".
static func place_of_room(room_id: String) -> String:
	for place in VISIT_SPOTS:
		if str(VISIT_SPOTS[place]) == "room:"+room_id: return str(place)
	return ""

## say(lines, choices) opens the caller's dialogue box; done(kind, reply) plays its effects
## ("accepted", "completed", "guide", "wardrobe"); here: the visit place the player stands at.
static func choice_for(api: Node, npc: String, say: Callable, done: Callable, village: bool, judge := Callable(), here := "") -> Array:
	# A message another resident asked to pass on to this one comes first (윤재's regards to 가람).
	if open_for(str(api.token)):
		for item in listed(str(api.token)):
			var book: Dictionary = BOOK.get(str(item.get("id", "")), {})
			if str(item.get("kind", "")) == "talk" and str(item.get("state", "")) == "active" and npc in item.get("places", []) \
					and not npc in item.get("visited", []) and book.has("deliver"):
				return [t(str(book.deliver)), func(): deliver(api, item, npc, say, done)]
	var entry := entry_for(str(api.token), npc)
	if entry.is_empty(): return []
	match str(judge.call(entry) if judge.is_valid() else entry.get("state", "")):
		"available": return [t("✦ 부탁 들어주기"), func(): offer(api, entry, say, done, here)]
		"active": return [t("부탁 이야기"), func(): remind(api, str(entry.id), say, done, village)]
		"ready": return [t("✦ 부탁한 것 건네기") if str(entry.kind) == "bring" else t("✦ 부탁을 마쳤어요"), func(): hand_over(api, str(entry.id), say, done)]
	return []

## The message passed on: the server counts it, the resident answers.
static func deliver(api: Node, item: Dictionary, npc: String, say: Callable, done: Callable) -> void:
	var id := str(item.id)
	var result: Dictionary = await api.post("/v1/quests/%s/progress" % id, api.mutation({"place":npc}))
	if not result.ok:
		say.call([error_line(str(result.get("error", "")))], [])
		return
	adopt_data(result.data.get("quests"), str(api.token))
	say.call(lines_of(item, "reply"), [[t("전해 드릴게요"), Callable()]])
	if done.is_valid(): done.call("progress", result.data)

static func lines_of(entry: Dictionary, key: String) -> Array:
	var out: Array = []
	for line in BOOK[str(entry.id)].get(key, []): out.append(t(str(line)))
	return out

static func offer(api: Node, entry: Dictionary, say: Callable, done: Callable, here := "") -> void:
	var stars := int(entry.get("stars", 0))
	var yes := t("맡겨 줘요 · 별씨 +%d") % stars if stars > 0 else t("맡겨 줘요")
	# Taken where it asks to go: the server counts the place with the yes (night errands at night).
	var at := here if str(entry.get("kind", "")) == "visit" and here in entry.get("places", []) else ""
	# "Not now" first: reading on with Space or E never takes a request by accident.
	say.call(lines_of(entry, "ask"), [[t("다음에요"), Callable()], [yes, func(): accept(api, str(entry.id), say, done, at)]])

static func accept(api: Node, id: String, say: Callable, done: Callable, at := "") -> void:
	var result: Dictionary = await api.post("/v1/quests/%s/accept" % id, api.mutation({"place":at} if not at.is_empty() else {}))
	if not result.ok:
		say.call([error_line(str(result.get("error", "")))], [])
		return
	adopt_data(result.data.get("quests"), str(api.token))
	var entry: Dictionary = result.data.get("quest", {})
	if done.is_valid(): done.call("accepted", result.data)
	# Already done (the apples were in the bag): the hand-over is the next choice.
	if str(entry.get("state", "")) == "ready":
		var lines: Array = [t(str(BOOK[id].already))] if BOOK[id].has("already") else [t(str(BOOK[id].accepted)), t("어머, 벌써 준비가 됐네?")]
		say.call(lines, [[t("✦ 지금 건네기"), func(): hand_over(api, id, say, done)], [t("다녀올게요"), Callable()]])
		return
	say.call([t(str(BOOK[id].accepted))], [[t("다녀올게요"), Callable()]])

## How far it is (asked fresh: the bag may have changed a moment ago); done goes to the hand-over.
static func remind(api: Node, id: String, say: Callable, done: Callable, village: bool) -> void:
	var fresh: Dictionary = await api.request("/v1/quests")
	if fresh.ok: adopt_data(fresh.data.get("quests"), str(api.token))
	var entry := by_id(str(api.token), id)
	if entry.is_empty(): return
	if str(entry.get("state", "")) == "ready":
		hand_over(api, id, say, done)
		return
	var line := remind_text(entry, int(entry.get("have", 0)))
	var choices: Array = [[t("다녀올게요"), Callable()]]
	if village:
		if id == "sora_outfit": choices.push_front([t("옷장 열기"), func(): done.call("wardrobe", {"quest":entry})])
		elif str(BOOK[id].place) != "-": choices.append([t("길 안내 받기"), func(): done.call("guide", {"quest":entry})])
	say.call([line], choices)

static func hand_over(api: Node, id: String, say: Callable, done: Callable) -> void:
	var result: Dictionary = await api.post("/v1/quests/%s/complete" % id, api.mutation())
	if not result.ok:
		var code := str(result.get("error", ""))
		if code == "quest_not_ready":
			var fresh: Dictionary = await api.request("/v1/quests")
			if fresh.ok: adopt_data(fresh.data.get("quests"), str(api.token))
		say.call([error_line(code)], [])
		return
	adopt_data(result.data.get("quests"), str(api.token))
	var entry: Dictionary = result.data.get("quest", {})
	say.call(lines_of(entry, "thanks"), [[t("천만에요"), Callable()]])
	# The thanks are open: the effects start over them and finish once they close.
	if done.is_valid(): done.call("completed", result.data)

static func error_line(code: String) -> String:
	match code:
		"quest_own_village_only": return t("부탁은 내 마을 주민의 것만 들어줄 수 있어요.")
		"quest_not_ready": return t("앗, 아직 다 되지 않았나 봐요. 조금만 더 부탁해요!")
		"quest_already_done": return t("그 부탁은 벌써 들어줬어요. 정말 고마워요!")
		"quests_locked": return t("지금은 부탁할 게 없대요. 마을 일을 먼저 마쳐 보세요.")
	return t("지금은 부탁을 들을 수 없대요. 잠시 뒤 다시 말을 걸어 주세요.")

# ------------------------------------------------------------------ effects

## The village's side of a conversation: a pop over the resident, the toast, the guide, and at the
## hand-over the star burst and the stars flying into the counter.
static func village_done(app: Node, anchor: Node3D, kind: String, reply: Dictionary) -> void:
	if not is_instance_valid(app): return
	var entry: Dictionary = reply.get("quest", {})
	var here: Node = village_of(app)
	match kind:
		"accepted":
			if is_instance_valid(anchor) and anchor.has_method("pop"): anchor.pop("!", 1.6)
			if is_instance_valid(anchor): Fx.bubble(app.world, anchor.global_position+Vector3(0, 2.3, 0), "star")
			RpgUi.sfx("confirm", -6.0)
			app.message(t("새 부탁 · %s") % title_of(entry))
			if here: here.accepted(entry)
		"guide":
			if here: here.guide_to(str(entry.get("id", "")), false)
		"wardrobe":
			if app.has_method("open_wardrobe"): app.open_wardrobe()
		"progress":
			# A message passed on: the request is done (its moment and the way back follow).
			if is_instance_valid(anchor) and anchor.has_method("pop"): anchor.pop("♪", 1.6)
			if here: here.adopt(reply.get("quests"))
		"completed":
			var at: Vector3 = anchor.global_position if is_instance_valid(anchor) else app.player.global_position
			if is_instance_valid(anchor):
				if anchor.has_method("pop"): anchor.pop("♥", 2.0)
				if anchor.has_method("smile"): anchor.smile(4.0)
			var stars := int(reply.get("stars", 0))
			var total := int(reply.get("shards", app.me.get("shards", 0)))
			# Known now, so the village's polls see no change to refresh for.
			if app.me is Dictionary: app.me["shards"] = total
			reward_burst(app, at, stars)
			# The bag's items went to the resident: the village life takes the server's new state.
			if reply.get("homestead") is Dictionary and is_instance_valid(app.get("life")) and app.life.has_method("accept"): app.life.accept(reply.homestead)
			if here: here.completed(entry)
			# Conversations hide the HUD: the stars fly into the counter once the thanks close.
			await after_dialogue(app)
			if not is_instance_valid(app): return
			reward_fly(app, at, stars, total)
			app.message(t("부탁 완료 · %s · %s") % [title_of(entry), stars_text(stars)] if stars > 0 else t("부탁 완료 · %s") % title_of(entry))
			var note := NpcGifts.letters_note(reply)
			if not note.is_empty(): app.get_tree().create_timer(3.2).timeout.connect(func(): if is_instance_valid(app): app.message(note))

## "다 모았어요! 모카에게 가져가 보세요" / "다 됐어요! 윤재에게 알려 주세요".
static func done_word(entry: Dictionary, hour := -1.0) -> String:
	return (t("다 모았어요! %s에게 가져가 보세요") if str(entry.get("kind", "")) == "bring" else t("다 됐어요! %s에게 알려 주세요")) % npc_name(str(entry.get("npc", "")), hour)

## A room's own clock (studio.gd resident_clock), else the player's.
static func room_hour(room: Node) -> float:
	return float(room.resident_clock().hour) if is_instance_valid(room) and room.has_method("resident_clock") else -1.0

## A room was entered (studio.gd show_story): a visit request whose place is this room counts
## (night requests only while it is night by the player's clock, as the server checks).
static func entered_room(room: Node, room_id: String) -> void:
	if not is_instance_valid(room) or str(room.api.token).is_empty() or bool(room.get("visiting")): return
	var api: Node = room.api
	for item in listed(str(api.token)):
		if str(item.get("kind", "")) != "visit" or str(item.get("state", "")) != "active": continue
		for place in item.get("places", []):
			if str(VISIT_SPOTS.get(str(place), "")) != "room:"+room_id or str(place) in item.get("visited", []): continue
			if bool(item.get("night", false)) and not night_now(): continue
			var result: Dictionary = await api.post("/v1/quests/%s/progress" % str(item.id), api.mutation({"place":str(place)}))
			if not result.ok or not is_instance_valid(room): return
			adopt_data(result.data.get("quests"), str(api.token))
			var now: Dictionary = result.data.get("quest", {})
			if str(now.get("state", "")) == "ready" and room.has_method("message"): room.message(done_word(now, room_hour(room)))
			return

## Night by the player's own clock (server/homestead.py night: before 6 or from 19).
static func night_now() -> bool:
	var hour := int(Time.get_datetime_dict_from_system().hour)
	return hour < 6 or hour >= 19

## Inside a building: the room's own pop, sparkles over the resident and its wallet line.
static func room_done(room: Node, id: String, kind: String, reply: Dictionary) -> void:
	if not is_instance_valid(room) or not room.npcs.has(id): return
	var resident: Dictionary = room.npcs[id]
	var entry: Dictionary = reply.get("quest", {})
	if kind == "accepted":
		room.pop_over(resident, "!")
		room.message(t("새 부탁 · %s") % title_of(entry))
	elif kind == "progress":
		room.pop_over(resident, "♪")
		if str(entry.get("state", "")) == "ready": room.message(done_word(entry, room_hour(room)))
	elif kind == "completed":
		var stars := int(reply.get("stars", 0))
		var at: Vector3 = resident.holder.global_position
		room.pop_over(resident, "✦")
		Fx.burst(room.stage, at+Vector3(0, 1.5, 0), "sparkle", 22, Color(0,0,0,0), 0.5)
		Fx.glow(room.stage, at+Vector3(0, 1.3, 0), Color("ffd27a"), 2.0, 1.2)
		if is_instance_valid(room.get("wallet")): room.wallet.text = t("별씨 %d") % int(reply.get("shards", 0))
		# The room's character frame counts the reward up too.
		if reply.has("shards") and room.has_method("show_stars"): room.show_stars(int(reply.shards))
		room.message(t("부탁 완료 · %s · %s") % [title_of(entry), stars_text(stars)] if stars > 0 else t("부탁 완료 · %s") % title_of(entry))
		var note := NpcGifts.letters_note(reply)
		if not note.is_empty(): room.create_tween().tween_callback(func(): room.message(note)).set_delay(3.0)

## The moment of the hand-over, over the thanks: sparkles, a glow and a ring at the resident and
## a "+N" starseed rising over them.
static func reward_burst(app: Node, at: Vector3, stars: int) -> void:
	var world: Node3D = app.world
	Fx.burst(world, at+Vector3(0, 1.6, 0), "sparkle", 24, Color(0,0,0,0), 0.55)
	Fx.glow(world, at+Vector3(0, 1.4, 0), Color("ffd27a"), 2.4, 1.3)
	Fx.ring(world, at+Vector3(0, 0.05, 0), 1.8, Color(1.0, 0.88, 0.5, 0.8), 0.9)
	RpgUi.sfx("confirm", -2.0)
	if DisplayServer.get_name() != "headless": Fx.sound(app, "twinkle", at, 1.2, -1.0)
	if stars <= 0 or not is_instance_valid(app.get("camera")) or not is_instance_valid(app.get("ui")): return
	var from: Vector2 = app.camera.unproject_position(at+Vector3(0, 1.9, 0))
	var badge := HBoxContainer.new()
	badge.name = "QuestStars"
	badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	badge.add_theme_constant_override("separation", 3)
	badge.add_child(RpgUi.icon(STAR_ICON, 38))
	RpgUi.numbers(RpgUi.label(badge, "+%d" % stars, 28, RpgUi.HOVER), 28)
	app.ui.add_child(badge)
	badge.size = badge.get_combined_minimum_size()
	badge.position = from-badge.size*0.5
	badge.pivot_offset = badge.size*0.5
	badge.scale = Vector2.ONE*0.3
	var pop := badge.create_tween()
	pop.tween_property(badge, "scale", Vector2.ONE*1.15, 0.22).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	pop.parallel().tween_property(badge, "position:y", badge.position.y-46, 1.0).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	pop.tween_interval(1.2)
	pop.tween_property(badge, "modulate:a", 0.0, 0.35)
	pop.tween_callback(badge.queue_free)

## Until the open conversation closes (conversations hide the HUD, the counter with it).
static func after_dialogue(app: Node) -> void:
	for i in 1200:
		if not is_instance_valid(app) or not is_instance_valid(app.get("village_modal")): return
		await app.get_tree().create_timer(0.1).timeout

## Stars fly from the resident into the HUD counter, which ticks up from the old count as they land.
static func reward_fly(app: Node, at: Vector3, stars: int, total: int) -> void:
	if app.me is Dictionary: app.me["shards"] = total
	var counter: Label = app.frame.get("stars") if app.get("frame") is Dictionary else null
	if stars <= 0 or not is_instance_valid(counter) or not is_instance_valid(app.get("camera")) or not is_instance_valid(app.get("ui")):
		if is_instance_valid(counter): RpgUi.count_to(counter, total)
		return
	# A refresh may have shown the new count already: the stars bring it.
	if counter.has_meta("count_tween") and counter.get_meta("count_tween") is Tween and (counter.get_meta("count_tween") as Tween).is_valid(): (counter.get_meta("count_tween") as Tween).kill()
	if counter.has_meta("count_target"): counter.remove_meta("count_target")
	counter.text = str(total-stars)
	var from: Vector2 = app.camera.unproject_position(at+Vector3(0, 1.9, 0))
	var goal: Vector2 = counter.get_global_rect().get_center() if counter.is_visible_in_tree() else Vector2(120, 60)
	var flying := mini(stars, 8)
	var landed := [0]
	for k in flying:
		var star := RpgUi.icon(STAR_ICON, 30)
		star.name = "QuestStar"
		star.mouse_filter = Control.MOUSE_FILTER_IGNORE
		star.pivot_offset = Vector2(15, 15)
		star.position = from-Vector2(15, 15)
		star.scale = Vector2.ZERO
		app.ui.add_child(star)
		var rise := from-Vector2(15, 15)+Vector2(randf_range(-60, 60), -60-randf_range(0, 40))
		var t := star.create_tween()
		t.tween_interval(0.1+k*0.07)
		t.tween_property(star, "scale", Vector2.ONE*1.2, 0.16).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		t.parallel().tween_property(star, "position", rise, 0.3).set_ease(Tween.EASE_OUT)
		t.tween_property(star, "position", goal-Vector2(15, 15), 0.55).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
		t.parallel().tween_property(star, "scale", Vector2.ONE*0.6, 0.55)
		t.tween_callback(func():
			star.queue_free()
			landed[0] += 1
			if landed[0] == 1 and is_instance_valid(counter): RpgUi.count_to(counter, total, 0.25+0.07*flying)
			if is_instance_valid(counter):
				counter.pivot_offset = counter.size*0.5
				var bump := counter.create_tween()
				bump.tween_property(counter, "scale", Vector2.ONE*1.22, 0.06)
				bump.tween_property(counter, "scale", Vector2.ONE, 0.12)
			if DisplayServer.get_name() != "headless": Fx.sound(app, "pluck", Vector3.INF, 1.5+0.06*landed[0], -10.0))

## This module in the village (null in rooms or while loading).
static func village_of(app: Node) -> Node:
	var story: Node = app.chapter() if is_instance_valid(app) and app.has_method("chapter") else null
	return story.get("quests") if story != null else null

# ------------------------------------------------------------------ the village (this node)

var app: Node
## story.gd, which owns this node (its route guide helpers and the island hop).
var story: Node
var tick := 0.0
var mark_wait := 0.0
## Shown on the tracker (the player's pick in the book, else the newest one under way).
var focus := ""
## The tracker's lines -> guide keys (story_line_key asks).
var line_keys := {}
## Last seen state per request (for the "다 됐어요" moment) and whether the server said the
## requests were open (1), closed (0) or has not said yet this login (-1).
var seen := {}
var was_open := -1
## A full list asked for (/v1/me's brief did not match the kept one).
var fetching := false
## The guided request (its legs across islands follow on).
var followed := ""
## Signposts reported (island -> true) and the time of the last report.
var reporting := false
var report_after := 0.0
## "!" and "?" over residents: instance id of the resident -> its Label3D.
var marks := {}

func setup(main: Node, owner_story: Node) -> void:
	app = main
	story = owner_story
	name = "Quests"
	if app.get("me") is Dictionary and app.me.get("quests") is Dictionary: adopt(app.me.quests)
	else: remember_states()

func leave() -> void:
	clear_marks()

func _exit_tree() -> void:
	clear_marks()

func token() -> String:
	return str(app.api.token) if is_instance_valid(app) and app.get("api") != null else ""

func shown() -> bool:
	return is_instance_valid(app) and open_for(token()) and not story.visiting()

func entries() -> Array:
	return listed(token())

func entry(id: String) -> Dictionary:
	return by_id(token(), id)

## The server's list (/v1/me and the requests' replies): the moments it brings.
func adopt(data) -> void:
	if not adopt_data(data, token()):
		if data is Dictionary and data.get("states") is Array: fetch_full()
		return
	var open := 1 if open_for(token()) else 0
	# The chair was ordered (or the chapter ended) while this login saw them closed: the requests open (not on
	# every login of an open account, and not when nobody has a request left).
	if was_open == 0 and open == 1 and not story.visiting() and entries().any(func(item): return str(item.get("state", "")) == "available"):
		get_tree().create_timer(1.2).timeout.connect(func(): if is_instance_valid(app): app.message(tr("마을 주민들이 부탁을 기다리고 있어요 · 머리 위 ! 를 찾아보세요")))
	was_open = open
	for item in entries():
		var id := str(item.get("id", ""))
		var now := state_of(item)
		if str(seen.get(id, "")) == "active" and now == "ready": became_ready(item)
		seen[id] = now
	mark_wait = 0.0

## The full list, once, when /v1/me's brief has nothing to update (a new login, a request taken
## or handed over elsewhere).
func fetch_full() -> void:
	if fetching or not is_instance_valid(app) or token().is_empty(): return
	fetching = true
	var asked := token()
	var result: Dictionary = await app.api.request("/v1/quests")
	fetching = false
	if result.ok and is_instance_valid(app) and token() == asked and result.data.get("quests") is Dictionary: adopt(result.data.quests)

## What this login already knew (a village rebuilt after a room): nothing known yet is -1, so the
## first answer of a login never reads as "just opened".
func remember_states() -> void:
	was_open = -1 if known(token()).is_empty() else (1 if open_for(token()) else 0)
	for item in entries(): seen[str(item.get("id", ""))] = state_of(item)

## The bag's count right now (the village life's state), else the server's.
func have_of(item: Dictionary) -> int:
	var have := int(item.get("have", 0))
	if str(item.get("kind", "")) == "bring" and is_instance_valid(app.get("life")) and app.life.get("state") is Dictionary and not app.life.state.is_empty():
		var bag: Dictionary = app.life.state.get("bag", {})
		var count := 0
		for kind in item.get("items", []): count += int(bag.get(str(kind), 0))
		have = count
	if str(item.get("kind", "")) == "outfit" and app.get("me") is Dictionary and int(app.me.get("profile", {}).get("version", 0)) > int(item.get("since", 1 << 30)):
		have = 1
	# New kinds in the fish book since the request (the server's baseline comes with it).
	if str(item.get("kind", "")) == "catch" and item.get("since") is Dictionary and is_instance_valid(app.get("life")) and app.life.get("state") is Dictionary:
		var book: Dictionary = app.life.state.get("collection", {})
		var before: Dictionary = item.since
		var kinds := 0
		for fish in book:
			if int(book[fish]) > int(before.get(fish, 0)): kinds += 1
		have = maxi(have, kinds)
	return mini(have, int(item.get("need", 1)))

func state_of(item: Dictionary) -> String:
	var state := str(item.get("state", ""))
	if state in ["active", "ready"]: return "ready" if have_of(item) >= int(item.get("need", 1)) else "active"
	return state

func under_way() -> Array:
	return entries().filter(func(item): return state_of(item) in ["active", "ready"])

func focused() -> Dictionary:
	var open := under_way()
	if open.is_empty(): return {}
	for item in open:
		if str(item.id) == focus: return item
	# A request that is done first, else the newest one taken.
	for item in open:
		if state_of(item) == "ready": return item
	var best: Dictionary = open[0]
	for item in open:
		if float(item.get("accepted", 0)) > float(best.get("accepted", 0)): best = item
	return best

# ------------------------------------------------------------------ tracker and guide

## The tracker's text with the requests on top: the shown request's goal ("▸ ", a guide row), its
## title and reward, and a line for the others (the book).
func objective(base: String) -> String:
	line_keys.clear()
	if not shown(): return base
	var open := under_way()
	var waiting := entries().filter(func(item): return str(item.get("state", "")) == "available").size()
	var out := PackedStringArray()
	if not open.is_empty():
		var item := focused()
		var ready := state_of(item) == "ready"
		var goal := goal_text(item, have_of(item), ready, story.hour())
		line_keys[goal] = KEY+str(item.id)
		out.append("▸ "+goal)
		var stars := int(item.get("stars", 0))
		out.append(title_of(item)+(" · "+stars_text(stars) if stars > 0 else ""))
	var book := ""
	if open.size() > 1: book = tr("✦ 다른 부탁 %d개 · 수첩 보기") % (open.size()-1)
	elif waiting > 0: book = (tr("✦ 새 부탁 %d개 · 수첩 보기") if not open.is_empty() else tr("✦ 주민들의 부탁 %d개 · 수첩 보기")) % waiting
	if not book.is_empty():
		line_keys[book] = BOOK_KEY
		out.append(book)
	if out.is_empty(): return base
	return "\n".join(out)+("\n"+base if not base.is_empty() else "")

func line_key(line: String) -> String:
	return str(line_keys.get(line, ""))

## Where a request leads now ({"at", "name", "key"} before the island hop, story.gd story_goal).
func raw_goal(key: String) -> Dictionary:
	var id := key.trim_prefix(KEY)
	var item := entry(id)
	if item.is_empty() or not BOOK.has(id) or not state_of(item) in ["active", "ready", "available"]: return {}
	var place := str(BOOK[id].place)
	# Not taken yet (the book's "찾아가기"), done, or done by talking: the resident.
	if state_of(item) != "active" or place.is_empty() or (str(item.kind) == "gift" and not item.has("to")): return npc_goal(str(item.npc), key)
	if str(item.kind) == "gift": return npc_goal(str(item.to), key)
	if place.begins_with("npc:"): return npc_goal(place.trim_prefix("npc:"), key)
	if place.begins_with("forage:"): return forage_goal(place.trim_prefix("forage:"), key)
	if place.begins_with("tree:"): return tree_goal(place.trim_prefix("tree:"), key)
	match place:
		"apple", "sea", "pond", "herb", "lookout":
			var spot := Guide.place(place)
			return {"at":spot.at, "name":tr(spot.title), "key":key} if not spot.is_empty() else {}
		"home":
			return {"at":Town.HOME_DOOR, "name":tr("나의 집"), "key":key}
		"visit":
			for spot in item.get("places", []):
				if str(spot) in item.get("visited", []): continue
				var where := str(VISIT_SPOTS.get(str(spot), ""))
				if where.begins_with("place:"):
					var known_place := Guide.place(where.trim_prefix("place:"))
					if not known_place.is_empty(): return {"at":known_place.at, "name":tr(known_place.title), "key":key}
				elif where.begins_with("room:"):
					var door := Town.door_for(where.trim_prefix("room:"))
					if not door.is_empty(): return {"at":door.at, "name":tr(door.title), "key":key}
			return {}
		"farm":
			var farm := Guide.place("farm")
			var best: Vector2 = farm.at
			var life = app.get("life")
			if is_instance_valid(life) and life.state is Dictionary and life.state.get("plots") is Array:
				var gap := INF
				for plot in life.state.plots:
					if Farm.stage(plot, life.now()) != 5: continue
					var p := Vector2(float(plot.x), float(plot.z))
					if p.distance_to(story.walker_at()) < gap:
						gap = p.distance_to(story.walker_at())
						best = p
			return {"at":best, "name":tr(farm.title), "key":key}

		"signpost":
			var visited: Array = item.get("visited", [])
			var here: String = story.island_of(story.walker_at())
			var options: Array = []
			for island in item.get("places", []):
				if str(island) in visited: continue
				var sign: Dictionary = story.signpost(str(island))
				if not sign.is_empty(): options.append(sign)
			if options.is_empty(): return {}
			var best: Dictionary = options[0]
			for sign in options:
				# This island's own signpost first, else the nearest.
				if str(sign.spec.get("island", "")) == here: best = sign; break
				if Vector2(sign.at).distance_to(story.walker_at()) < Vector2(best.at).distance_to(story.walker_at()): best = sign
			return {"at":best.at, "name":tr("이정표 · %s") % tr(ISLANDS.get(str(best.spec.get("island", "")), "")), "key":key}
	return {}

## The nearest ready forage spot of a kind (forage.gd: mushroom, flower, herb, shell...).
func forage_goal(kind: String, key: String) -> Dictionary:
	var life = app.get("life")
	if not is_instance_valid(life) or not is_instance_valid(life.get("forage")): return {}
	var best := {}
	var gap := INF
	for spot in life.forage.spots:
		if not spot.ready or spot.kind != kind: continue
		var d: float = Vector2(spot.at).distance_to(story.walker_at())
		if d < gap:
			gap = d
			best = spot
	var names := {"mushroom":"숲 그늘 버섯", "flower":"길가 들꽃"}
	return {"at":best.at, "name":tr(str(names.get(kind, "채집"))), "key":key} if not best.is_empty() else {}

## The nearest field tree of a kind with fruit to shake (tree_fruit.gd via town.gd).
func tree_goal(kind: String, key: String) -> Dictionary:
	var town = app.get("town")
	var trees = town.get("trees") if is_instance_valid(town) else null
	if not is_instance_valid(trees): return {}
	var best := {}
	var gap := INF
	for tree in trees.trees:
		if str(tree.kind) != kind or (trees.has_method("server_ready") and not trees.server_ready(tree)): continue
		var d: float = Vector2(tree.at).distance_to(story.walker_at())
		if d < gap:
			gap = d
			best = tree
	return {"at":best.at, "name":tr("뾰족한 나무 · 솔방울"), "key":key} if not best.is_empty() else {}

## Where a resident is now: their walker or cast villager in view, their spot outside, or the door
## of the building they are in.
func npc_goal(npc: String, key: String) -> Dictionary:
	var name := npc_name(npc, story.hour())
	for module in app.get("modules") if app.get("modules") != null else []:
		if not is_instance_valid(module) or not "walkers" in module: continue
		for walker in module.walkers:
			if str(walker.spec.id) == npc and walker.present: return {"at":walker.xz(), "name":name, "key":key}
	for villager in app.get("npcs") if app.get("npcs") != null else []:
		if is_instance_valid(villager) and villager.visible and str(villager.get_meta("cast", "")) == npc:
			return {"at":Vector2(villager.position.x, villager.position.z), "name":name, "key":key}
	var block := Residents.now(npc, story.hour())
	var place := str(block.get("place", ""))
	if place == "story": return {"at":MOKA_AT, "name":name, "key":key}
	if place == "outside":
		var spot: Vector2 = Residents.OUTSIDE_SPOTS.get(str(block.get("spot", "")), Residents.OUTSIDE_SPOTS.square)
		return {"at":spot, "name":name, "key":key}
	var door := Town.door_for(place)
	if door.is_empty(): return {}
	return {"at":door.at, "name":tr("%s · %s") % [name, tr(door.title)], "key":key}

## A click on a request's row that is not a place, or on the book's line.
func row(key: String) -> bool:
	if key == BOOK_KEY:
		open_book()
		return true
	var id := key.trim_prefix(KEY)
	var item := entry(id)
	if not item.is_empty() and raw_goal(key).is_empty():
		app.message(tr("빛나는 물건을 마을에 놓아 주세요 · I 가방 또는 C 공방") if str(item.kind) == "light" else remind_text(item, have_of(item)))
		return true
	return false

func guide_to(id: String, quiet: bool) -> void:
	var guide: Node = story.guide_node()
	if guide == null: return
	focus = id
	var goal: Dictionary = story.story_goal(KEY+id)
	if goal.is_empty():
		row(KEY+id)
		return
	followed = KEY+id
	if story.walker_at().distance_to(goal.at) > 4.0: guide.set_target(goal, quiet)

## Taken: shown on the tracker, and the way to it guided.
func accepted(item: Dictionary) -> void:
	focus = str(item.get("id", ""))
	seen[focus] = state_of(entry(focus))
	if not Guide.player_stopped: guide_to(focus, false)

## Done: off the tracker and the guide.
func completed(item: Dictionary) -> void:
	var id := str(item.get("id", ""))
	seen[id] = "done"
	if focus == id: focus = ""
	if followed == KEY+id: followed = ""
	var guide: Node = story.guide_node()
	if guide != null and guide.active() and str(guide.target.get("key", "")) == KEY+id: guide.stop(false)
	mark_wait = 0.0

## The moment a request is done: a word, a sparkle, and the way back to the resident.
func became_ready(item: Dictionary) -> void:
	if not shown() or str(app.get("screen")) != "village": return
	var who := npc_name(str(item.npc), story.hour())
	app.message((tr("다 모았어요! %s에게 가져가 보세요") if str(item.kind) == "bring" else tr("다 됐어요! %s에게 알려 주세요")) % who)
	if is_instance_valid(app.get("player")):
		Fx.burst(app.world, app.player.global_position+Vector3(0, 1.8, 0), "sparkle", 12, Color(0,0,0,0), 0.35)
		Fx.bubble(app.world, app.player.global_position+Vector3(0, 2.2, 0), "star")
	RpgUi.sfx("confirm", -6.0)
	var id := str(item.id)
	if focus.is_empty() or focus == id or followed == KEY+id:
		focus = id
		if not Guide.player_stopped: guide_to(id, false)

func arrived(key: String) -> void:
	# At the resident (or the place): the leg is over; a signpost on the way goes on (story.gd).
	var goal := raw_goal(key)
	if goal.is_empty() or story.island_of(story.walker_at()) == story.island_of(goal.at): followed = ""

## The guided request's goal follows its resident, and its next leg after a signpost.
func steer() -> void:
	var guide: Node = story.guide_node()
	if guide == null or str(app.get("screen")) != "village": return
	# Arriving at a signpost on the way opens its travel choices (story.gd arrived), with or
	# without a chapter.
	if guide.has_signal("arrived") and not guide.arrived.is_connected(story.arrived):
		story.guide_hooked = true
		guide.arrived.connect(story.arrived)
	var key := str(guide.target.get("key", "")) if guide.active() else ""
	if key.begins_with(KEY):
		followed = key
		var goal: Dictionary = story.story_goal(key)
		if goal.is_empty():
			guide.stop(false)
			followed = ""
		elif Vector2(goal.at).distance_to(guide.target.at) > 3.0: guide.set_target(goal, true)
		return
	if followed.is_empty() or guide.active() or Guide.player_stopped: return
	var next: Dictionary = story.story_goal(followed)
	if next.is_empty(): followed = ""
	elif story.walker_at().distance_to(next.at) > 8.0: guide.set_target(next, true)

# ------------------------------------------------------------------ frame

func _process(delta: float) -> void:
	if not is_instance_valid(app) or not is_instance_valid(app.get("player")) or str(app.get("screen")) != "village": return
	tick -= delta
	if tick > 0.0: return
	tick = 0.25
	if not shown():
		if not marks.is_empty(): clear_marks()
		return
	# The bag and the look change between the server's answers: the moment shows at once.
	for item in entries():
		var id := str(item.get("id", ""))
		var now := state_of(item)
		if str(seen.get(id, "")) == "active" and now == "ready": became_ready(item)
		seen[id] = now
	steer()
	report_signposts()
	mark_wait -= 0.25
	if mark_wait <= 0.0:
		mark_wait = 0.5
		update_marks()

## 나루's request: standing at a signpost of an island not counted yet tells the server.
func report_signposts() -> void:
	if reporting or Time.get_ticks_msec()*0.001 < report_after: return
	var here: Vector2 = story.walker_at()
	for item in entries():
		if str(item.get("kind", "")) != "visit" or str(item.get("state", "")) != "active": continue
		# Night errands count only at night by the player's clock (the server checks the same).
		if bool(item.get("night", false)) and not night_now(): continue
		for spot in spots_of(item):
			if str(spot.place) in item.get("visited", []) or here.distance_to(spot.at) > float(spot.reach): continue
			reporting = true
			var result: Dictionary = await app.api.post("/v1/quests/%s/progress" % str(item.id), app.api.mutation({"place":str(spot.place)}))
			reporting = false
			report_after = Time.get_ticks_msec()*0.001+(1.0 if result.ok else 4.0)
			if not result.ok or not is_instance_valid(app): return
			adopt(result.data.get("quests"))
			var now: Dictionary = result.data.get("quest", {})
			var lift: Vector3 = spot.root.global_position if spot.get("root") is Node3D and is_instance_valid(spot.root) else Town.point(spot.at, 0.0)
			Fx.burst(self, lift+Vector3(0, 1.6, 0), "sparkle", 14, Color(0,0,0,0), 0.4)
			Fx.glow(self, lift+Vector3(0, 1.4, 0), RpgUi.HOVER, 1.8, 1.0)
			RpgUi.sfx("confirm", -8.0)
			if str(now.get("state", "")) != "ready":
				app.message(tr("이정표 %d/%d · %s") % [int(now.get("have", 0)), int(now.get("need", 3)), str(spot.name)])
			return

## Where a visit request's places stand in the village: the islands' signposts (나루), the lookout,
## the lighthouse pier (rooms are counted on entry, entered_room).
func spots_of(item: Dictionary) -> Array:
	var out: Array = []
	var field: Node = story.field_module()
	for place in item.get("places", []):
		if str(place) in ISLANDS:
			var sign: Dictionary = story.signpost(str(place)) if field != null else {}
			if not sign.is_empty(): out.append({"place":place, "at":sign.at, "reach":6.0, "root":sign.root, "name":tr(ISLANDS[str(place)])})
			continue
		var where := str(VISIT_SPOTS.get(str(place), ""))
		if where.begins_with("place:"):
			var known_place := Guide.place(where.trim_prefix("place:"))
			if not known_place.is_empty(): out.append({"place":place, "at":known_place.at, "reach":5.0, "name":tr(known_place.title)})
	return out
## "!" over a resident with a request to give, "?" over one waiting for the result.
func update_marks() -> void:
	var want := {}
	for item in entries():
		var state := state_of(item)
		if state == "available": want[str(item.npc)] = "!"
		elif state == "ready": want[str(item.npc)] = "?"
	var bodies := {}
	for module in app.get("modules") if app.get("modules") != null else []:
		if not is_instance_valid(module) or not "walkers" in module: continue
		for walker in module.walkers:
			var id := str(walker.spec.id)
			if want.has(id) and walker.present and walker.visible: bodies[walker.get_instance_id()] = [walker, want[id]]
	for villager in app.get("npcs") if app.get("npcs") != null else []:
		var id := str(villager.get_meta("cast", "")) if is_instance_valid(villager) else ""
		if want.has(id) and villager.visible: bodies[villager.get_instance_id()] = [villager, want[id]]
	# 모카 on the café terrace while the chapter's scene plays is the story's own figure.
	for key in marks.keys():
		var label: Label3D = marks[key]
		if not bodies.has(key) or not is_instance_valid(label):
			if is_instance_valid(label): label.queue_free()
			marks.erase(key)
	for key in bodies:
		var body: Node3D = bodies[key][0]
		var symbol: String = bodies[key][1]
		var label: Label3D = marks.get(key)
		if not is_instance_valid(label):
			label = mark_label()
			body.add_child(label)
			marks[key] = label
		if label.text != symbol:
			label.text = symbol
			label.modulate = Color("ffd84a") if symbol == "!" else Color("9fe3ff")

func mark_label() -> Label3D:
	var label := Label3D.new()
	label.name = "QuestMark"
	label.font = RpgUi.FONT_DISPLAY
	label.font_size = 120
	label.pixel_size = 0.0045
	label.outline_size = 26
	label.outline_modulate = Color(0.24, 0.13, 0.03, 0.95)
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.position = Vector3(0, 2.55, 0)
	label.double_sided = true
	if not RpgUi.calm():
		var bob := label.create_tween().set_loops()
		bob.tween_property(label, "position:y", 2.7, 0.6).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
		bob.tween_property(label, "position:y", 2.55, 0.6).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	return label

func clear_marks() -> void:
	for key in marks:
		if is_instance_valid(marks[key]): marks[key].queue_free()
	marks.clear()

# ------------------------------------------------------------------ the request book

## 부탁 수첩: every request, how far it is, its reward, and a way to it.
func open_book() -> void:
	if not is_instance_valid(app) or not app.has_method("modal_card"): return
	var v: VBoxContainer = app.modal_card(tr("부탁 수첩"))
	RpgUi.caption(v, tr("마을 주민들의 작은 부탁이에요. 들어주면 별씨를 받아요."), 13)
	# Nineteen rows: the list scrolls inside the window (the wheel or the bar).
	var scroll := ScrollContainer.new()
	scroll.name = "QuestBookScroll"
	scroll.custom_minimum_size = Vector2(680, 470)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	v.add_child(scroll)
	var list := VBoxContainer.new()
	list.add_theme_constant_override("separation", 4)
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(list)
	# Done first, then under way, new, finished; the residents' order within each.
	var order := {"ready":0, "active":1, "available":2, "done":3, "locked":4}
	var items: Array = []
	for index in entries().size(): items.append([int(order.get(state_of(entries()[index]), 5)), index, entries()[index]])
	items.sort_custom(func(a, b): return int(a[0]) < int(b[0]) or (int(a[0]) == int(b[0]) and int(a[1]) < int(b[1])))
	items = items.map(func(entry): return entry[2])
	for item in items:
		if not BOOK.has(str(item.get("id", ""))): continue
		var state := state_of(item)
		var line := HBoxContainer.new()
		line.name = "Quest_"+str(item.id)
		line.add_theme_constant_override("separation", 12)
		line.custom_minimum_size = Vector2(650, 46)
		list.add_child(line)
		var mark := RpgUi.label(line, {"ready":"?", "active":"▸", "available":"!", "done":"✓"}.get(state, "·"), 22,
			{"ready":Color("9fe3ff"), "available":Color("ffd84a"), "done":Color("a6d98a")}.get(state, RpgUi.GOLD))
		mark.custom_minimum_size.x = 22
		mark.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		var words := VBoxContainer.new()
		words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		words.add_theme_constant_override("separation", 0)
		line.add_child(words)
		var head := RpgUi.label(words, title_of(item), 17, RpgUi.PAPER_INK, false)
		head.add_theme_font_override("font", RpgUi.FONT_STRONG)
		var detail := npc_name(str(item.npc), story.hour())+" · "
		match state:
			"ready": detail += goal_text(item, have_of(item), true, story.hour())
			"active": detail += goal_text(item, have_of(item), false, story.hour())
			"available": detail += tr("새 부탁 · 이야기를 걸어 보세요")
			"done": detail += tr("완료")
		RpgUi.caption(words, detail, 13)
		var stars := int(item.get("stars", 0))
		var reward := HBoxContainer.new()
		reward.add_theme_constant_override("separation", 3)
		line.add_child(reward)
		reward.add_child(RpgUi.icon(STAR_ICON, 20))
		var amount := RpgUi.numbers(RpgUi.label(reward, ("+%d" % stars) if state != "done" else "✓ %d" % stars, 16, Color("8a5a12"), false), 16)
		amount.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		var id := str(item.id)
		if state in ["active", "ready"]:
			app.button(line, tr("길 안내"), func():
				app.close_village_modal()
				guide_to(id, false), "gold" if state == "ready" else "default").custom_minimum_size.x = 96
		elif state == "available":
			app.button(line, tr("찾아가기"), func():
				app.close_village_modal()
				guide_to(id, false)).custom_minimum_size.x = 96
		else:
			var gap := Control.new()
			gap.custom_minimum_size.x = 96
			line.add_child(gap)
