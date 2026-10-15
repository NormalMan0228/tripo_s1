extends RefCounted
## The villagers who walk the shadow folk's rounds by day. Every shadow resident
## (residents.gd, shadow_folk.gd FOLK) is a full-colour villager while the sun is up
## and the near-black silhouette only after dark: the same home, schedule, route,
## job, build and gait (the Explorer B rig), another name, face colours and outfit.
## Each resident hands over at its own point of dusk and dawn (switch_point), so the
## village never changes all at once; shadow_figure.gd dissolves the two looks when
## the change happens in view and swaps them at once out of sight. Everything follows
## the player's local clock (daylight.gd), like the sky.
const Daylight = preload("res://scripts/daylight.gd")

## title "<name> · <job>"; coat, pants and boots recolour the rig's cloth; hair and
## skin its face; hat and bag colour the props; gear is what they wear by day
## (shadow_figure.gd add_gear: hats, bags, tools). The shadows' aprons stand off the
## body to read in silhouette, so the villagers leave them off.
const LOOKS := {
	"postman":{"title":"다온 · 우편배달부","coat":"#3d6ea8","pants":"#3a4150","boots":"#5c4030","hair":"#2b201b","skin":"#f0c6a2","hat":"#2c4f80","bag":"#8c5a32","gear":["cap","satchel"]},
	"fisher":{"title":"보람 · 낚시꾼","coat":"#5f8a6e","pants":"#4a4f45","boots":"#3f3a33","hair":"#5a3a26","skin":"#d9a47c","hat":"#c9b88a","bag":"#7a6a4a","gear":["bucket","rod"]},
	"farmer":{"title":"한결 · 농부","coat":"#c9783f","pants":"#4f6a8a","boots":"#6a4a2e","hair":"#3a2a20","skin":"#c88f63","hat":"#e2c47e","bag":"#8a6a40","gear":["straw","hoe"]},
	"sweeper":{"title":"미소 · 청소부","coat":"#d9b44a","pants":"#5a5f6e","boots":"#4d3b2f","hair":"#7a3f24","skin":"#f2cdb0","hat":"#c24a3a","bag":"#8a6a40","gear":["beanie","broom"]},
	"gentleman":{"title":"윤재 · 산책하는 신사","coat":"#6d5a8c","pants":"#3b3a44","boots":"#2e2a2a","hair":"#9a9590","skin":"#e8bd98","hat":"#55515c","bag":"#2f3550","gear":["fedora","umbrella"]},
	"stargazer":{"title":"하늘 · 별지기","coat":"#3c4f8f","pants":"#3a3f55","boots":"#3a3030","hair":"#1f1d22","skin":"#e9c09c","hat":"#2e3a6e","bag":"#d9a441","gear":["beret","scarf"]},
	"lamplighter":{"title":"노을 · 등불지기","coat":"#b8573f","pants":"#4a4038","boots":"#3d2f25","hair":"#a8642f","skin":"#efc2a0","hat":"#2f6b6a","bag":"#8a6a40","gear":["cap","lantern"]},
	"gardener":{"title":"초록 · 정원사","coat":"#6f9a4f","pants":"#6b5a44","boots":"#4a3a2a","hair":"#3a2a1f","skin":"#b97f55","hat":"#dcc27a","bag":"#9a7448","gear":["straw","satchel"]},
	"scout":{"title":"바우 · 탐험가","coat":"#8a7a45","pants":"#5b5444","boots":"#4a3424","hair":"#2a2018","skin":"#a8714a","hat":"#6b5a3a","bag":"#a0522d","gear":["fedora","backpack"]},
	"regular":{"title":"모카 · 카페 주인","coat":"#9a5b44","pants":"#3c3836","boots":"#3a2c24","hair":"#5c3a2a","skin":"#f3d0b4","hat":"#7a3b30","bag":"#d97a5a","gear":["scarf"]},
	"miller":{"title":"두레 · 방앗간지기","coat":"#c7a46a","pants":"#6a5a4a","boots":"#4a3a2c","hair":"#6e6660","skin":"#e3b38d","hat":"#f2eee6","bag":"#8a6a40","gear":["flourcap"]},
	"shopkeeper":{"title":"단비 · 잡화점 주인","coat":"#4f8a86","pants":"#45404a","boots":"#3a2e28","hair":"#2a1e1a","skin":"#efc8a8","hat":"#3a3a3a","bag":"#8a6a40","gear":["glasses"]},
	"kid":{"title":"콩이 · 꼬마","coat":"#e0a43a","pants":"#4a6fa5","boots":"#c0503a","hair":"#3b2a1f","skin":"#f2c8a6","hat":"#e05a4a","bag":"#8a6a40","gear":["cap"]},
	"stroller":{"title":"새벽 · 산책자","coat":"#4a6a8a","pants":"#3f4248","boots":"#30302e","hair":"#151418","skin":"#c99a74","hat":"#8a3a4a","bag":"#c9b27a","gear":["beanie","scarf"]},
	"poet":{"title":"가람 · 시인","coat":"#8a5a7a","pants":"#3e3a48","boots":"#3a2a2a","hair":"#4a2a1a","skin":"#efcaa8","hat":"#5a3a6a","bag":"#d9b46a","gear":["beret","scarf"]},
}
## Prop colours that do not change from villager to villager.
const WOOD := "#8b6a48"
const METAL := "#4b5157"
const PAPER := "#efe6d2"
const STRAW := "#dcc27a"
## Where each worn piece takes its colour from (LOOKS keys or a fixed colour above).
const GEAR_COLOUR := {"cap":"hat","fedora":"hat","tophat":"hat","bucket":"hat","beanie":"hat","beret":"hat","straw":"hat",
	"flourcap":"hat","satchel":"bag","backpack":"bag","scarf":"bag","apron":"apron","umbrella":"hat","rod":"wood",
	"broom":"wood","hoe":"wood","lantern":"metal","glasses":"metal"}

## First lines by day, in place of shadow_folk.gd's shadow greetings.
const GREETINGS := {
	"postman":["안녕하세요! 이 섬의 우편배달부 다온이에요.","다섯 섬을 다 돌다 보면 하루가 금방 가요. 다리 건너는 게 제일 즐겁죠."],
	"fisher":["…쉿. 물고기가 놀라요.","낚시꾼 보람이에요. 물때만 맞으면 오늘도 대어예요."],
	"farmer":["어이쿠, 반가워요. 농부 한결이에요.","그런데 아까부터 호미가 안 보이네… 어디 떨어뜨렸더라."],
	"sweeper":["쓱싹쓱싹… 광장 청소는 제 담당이에요.","미소예요. 깨끗한 길을 걸으면 기분도 반짝하죠."],
	"gentleman":["좋은 날씨군요. 윤재라고 합니다.","실례. 다리를 건너며 산책하던 중이었습니다."],
	"stargazer":["하암… 밤새 별을 보느라 졸려요.","별지기 하늘이에요. 해가 지면 천문대로 와요."],
	"lamplighter":["등불지기 노을이에요. 해 질 녘이면 바빠져요.","낮엔 등불을 닦고 심지를 손봐 둬요."],
	"gardener":["향초 냄새 좋죠? 정원사 초록이에요.","유리 온실 옆 향초밭은 제 자랑이에요."],
	"scout":["돌문 너머 숲에서 막 돌아왔어요. 탐험가 바우예요.","탐험을 떠날 생각이에요? 몇 가지 알려 줄까요?"],
	"regular":["카페 '빨간 지붕' 주인 모카예요. 풍차 언덕 하숙집에서 지내며 커피를 내려요.","오늘의 블렌드는 고소하고 향이 짙답니다."],
	"miller":["풍차 방앗간지기 두레예요. 풍차가 돌면 밀가루가 눈처럼 날려요.","풍차 옆 하숙집 다락방이 제 방이에요. 맷돌 소리가 거기까지 들려요."],
	"shopkeeper":["잡화점 주인 단비예요. 필요한 게 있으면 말해요.","가게 뒤쪽 방에서 살아요. 손님이 없으면 장부 정리를 하죠."],
	"kid":["헤헤, 깜짝 놀랐지? 나 콩이야!","나 술래잡기 엄청 잘한다? 따라올 수 있으면 따라와 봐!"],
	"stroller":["산책 중이에요. 새벽이라고 해요.","밤 산책을 더 좋아하지만, 낮의 바다도 예쁘네요."],
	"poet":["정자에 앉아 시를 짓던 참이에요. 시인 가람이에요.","한 수 들어 보실래요?"],
}
## Shadow folk lines that only a shadow would say -> what the daytime villager says.
const DAY_LINES := {
	"빗자루 소리 들려요? 그림자 빗자루는 아주 조용하답니다.":"빗자루 소리 들려요? 쓱싹 소리가 경쾌하죠.",
	"나 엄청 빠르지? 그림자는 숨도 안 차!":"나 엄청 빠르지? 숨이 하나도 안 차!",
	"일찍 일어난 그림자가 길을 먼저 걷는답니다.":"일찍 일어나면 길을 제일 먼저 걷는답니다.",
	"산책 중이에요. 그늘만 골라 걷는 중이죠.":"산책 중이에요. 햇볕이 따뜻해서 좋네요.",
	"노을 질 때 그림자가 제일 길어지거든요.":"노을 지는 바다가 제일 예쁘거든요.",
	"햇살이 길을 그리면, 나는 그 옆에 가만히 눕는다.":"햇살이 길을 그리면, 나는 그 길을 따라 걷는다.",
	"다섯 섬이 잠들 무렵, 나는 비로소 눈을 뜬다.":"다섯 섬이 눈을 뜰 무렵, 바다는 금빛으로 웃는다.",
	"…어때요? 그림자의 시라서 조금 어둡죠?":"…어때요? 오늘 아침에 쓴 시예요.",
	"…이건 비밀이에요. 그림자끼리만 아는 이야기.":"…이건 비밀이에요. 마을 사람들끼리만 아는 이야기.",
	"연못 부두 끝에 서 있으면 꼬마 그림자가 놀러 와요. 장난꾸러기예요.":"연못 부두 끝에 서 있으면 꼬마가 놀러 와요. 장난꾸러기예요.",
	"정원 언덕 정자에는 시를 쓰는 그림자가 자주 앉아 있죠.":"정원 언덕 정자에는 시인이 자주 앉아 있죠.",
	"꼬마 그림자는 밤이 되면 자러 가요. 낮에 광장에서 만나 봐요.":"꼬마는 밤이 되면 자러 가요. 낮에 광장에서 만나 봐요.",
	"햇살 텃밭 바로 위가 방앗간이에요. 농부 그림자가 자주 놀러 와요.":"햇살 텃밭 바로 위가 방앗간이에요. 농부가 자주 놀러 와요.",
	"카페 주인 그림자가 저녁마다 커피 한 잔 하러 와요. 제가 가는 날도 있고요.":"카페 주인이 저녁마다 커피 한 잔 하러 와요. 제가 가는 날도 있고요.",
	"수수께끼를 풀었어요! 그림자가 하얗게 웃어요.":"수수께끼를 풀었어요! 활짝 웃어 줘요.",
	"그림자는 칭찬할 때 이렇게 웃는답니다. 히히.":"칭찬할 땐 이렇게 웃는 거예요. 히히.",
	"다음에 다시 물어봐 줘요. 그림자는 기다리는 걸 잘하거든요.":"다음에 다시 물어봐 줘요. 기다리는 건 자신 있거든요.",
	"…놓치지 마세요. 그림자는 그늘에 잘 섞이거든요.":"…놓치지 마세요. 제 걸음이 꽤 빠르거든요.",
	"그림자의 쉼터":"작은 쉼터",
	"오늘은 배달할 편지가 없네요. 그림자 우체국도 쉬는 날이 있어요.":"오늘은 배달할 편지가 없네요. 우체국도 쉬는 날이 있어요.",
	"낚시꾼 그림자가 엄지를 치켜세웠어요":"낚시꾼이 엄지를 치켜세웠어요",
	"좋은 솜씨예요. 그림자 낚시회에 들어올래요? …농담이에요.":"좋은 솜씨예요. 마을 낚시회에 들어올래요? …농담이에요.",
	"호미를 주웠어요 · 농부 그림자에게 돌려주세요":"호미를 주웠어요 · 농부에게 돌려주세요",
	"농부 그림자가 하얗게 활짝 웃어요":"농부가 활짝 웃어요",
	"이걸로 오늘 순무 한 고랑 더 일구겠네요. 그림자 농사도 손이 많이 가거든요.":"이걸로 오늘 순무 한 고랑 더 일구겠네요. 농사는 손이 많이 가거든요.",
	"제가 직접 가면 다들 깜짝 놀라서요. %s 쪽에 있을 거예요.":"오늘은 배달할 곳이 많아서요. %s 쪽에 있을 거예요.",
	"%s에게 편지를 전했어요 · \"그림자 우체부가 보냈구나!\"":"%s에게 편지를 전했어요 · \"우체부가 보냈구나!\"",
	"그림자가 한참 기다리다 돌아갔어요":"한참 기다리다 돌아갔어요",
}

static func has_look(id: String) -> bool:
	return LOOKS.has(id)

## Night level (daylight.gd sample().night, 0 day .. 1 night) at which this resident
## changes: spread over 0.3..0.7, roughly a quarter of an hour either side of the
## middle of dusk and dawn, the same for the walker outside and the figure in a room.
static func switch_point(id: String) -> float:
	return 0.3+0.4*float(absi(hash(id)) % 1000)/999.0

## True while `id` wears its daytime look at `hour` (the player's local time).
static func is_day(id: String, hour: float) -> bool:
	if not LOOKS.has(id): return false
	return float(Daylight.sample(hour).night) < switch_point(id)

## "다온 · 우편배달부", translated.
static func title(id: String) -> String:
	return TranslationServer.translate(str(LOOKS.get(id, {}).get("title", "")))

## Colour of a look entry ("coat", "hat", ...) or of a fixed prop colour role.
static func colour(id: String, key: String) -> Color:
	match key:
		"wood": return Color(WOOD)
		"metal": return Color(METAL)
		"paper": return Color(PAPER)
		"straw": return Color(STRAW)
	var look: Dictionary = LOOKS.get(id, {})
	return Color(str(look.get(key, look.get("bag", WOOD))))

static func greeting(id: String) -> Array:
	var lines: Array = []
	for line in GREETINGS.get(id, ["안녕하세요!"]): lines.append(TranslationServer.translate(line))
	return lines

## A shadow folk line as the speaker says it: the daytime wording when `day`.
static func line(text: String, day: bool) -> String:
	return TranslationServer.translate(str(DAY_LINES.get(text, text)) if day else text)
