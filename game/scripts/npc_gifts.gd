extends RefCounted
## Gifts to village residents (server/npc_homes.py). Talking to a resident who lives in a house
## offers "선물하기": a crafted piece from the bag goes to that resident, who later decorates
## their home with it (the server picks the moment and the spot, the same for every visitor).
##
## The conversation runs in whatever dialogue box the caller has: start() gets say(lines,
## choices) (choices are [label, Callable]) and done(reply) for the thank-you effect.
## Home layouts are cached by version in Engine metadata, so a house the village poll still
## reports at the same version opens without asking the server again.
const Residents = preload("res://scripts/residents.gd")
const Fx = preload("res://scripts/fx.gd")

## Residents who take gifts: everyone whose bed is in a house (the server's NPCS). Shop and
## workplace owners sleep in back rooms of working buildings and are left out for now.
const RECEIVERS := ["naru","scout","sora","gentleman","poet","moru","lamplighter","haeru","stroller","postman","sweeper","fisher","kid"]
## Reaction lines by the resident's personality (from the server) and how much they like it.
const LINES := {
	"cheerful":{"love":"우와, 이거 정말 내 취향이야! 고마워, 진짜로!","like":"헤헤, 예쁘다! 집 어디에 둘지 벌써 고민돼.",
		"thanks":"나한테 주는 거야? 고마워, 소중히 쓸게!","again":"오늘 또? 이러다 우리 집이 선물로 가득 차겠어!"},
	"calm":{"love":"…이건 정말 마음에 드네. 고마워, 오래 아낄게.","like":"좋은 물건이야. 집에 잘 어울리겠어.",
		"thanks":"고마워. 마음 써 줘서 기뻐.","again":"오늘만 벌써 몇 번째야? 고맙긴 한데, 너무 무리하진 마."},
	"elegant":{"love":"어머, 이렇게 근사한 걸! 제 방에 딱 어울리겠어요.","like":"안목이 좋으시네요. 정성껏 장식해 둘게요.",
		"thanks":"고마워요. 이런 선물은 언제나 반갑답니다.","again":"또 선물이요? 오늘은 제가 대접받는 날이네요."},
	"dreamy":{"love":"이건… 꿈에서 본 것 같아요. 시 한 편이 떠올라요.","like":"고마워요. 창가에 두면 햇빛이 머물다 갈 것 같아요.",
		"thanks":"선물이라니, 마음이 몽글몽글해져요.","again":"오늘은 선물이 별처럼 쏟아지네요."},
	"playful":{"love":"우와아! 이거 진짜 가져도 돼? 최고야!","like":"헤헤, 고마워! 내 보물 상자 옆에 둘래!",
		"thanks":"선물이다! 고마워, 고마워!","again":"또 줘? 헤헤, 오늘은 생일 같아!"},
}

## Letters at each new heart (1..4) by personality; the fourth comes with a return gift.
const LETTERS := {
	"cheerful":["안녕! 선물 정말 고마웠어. 집에 들어갈 때마다 그 생각이 나서 웃게 돼. 또 놀러 와!",
		"너랑 이야기하는 시간이 점점 기다려져. 다음에 만나면 내가 아는 지름길도 알려 줄게!",
		"우리 이제 진짜 친한 친구 맞지? 네가 준 선물들 덕분에 집이 훨씬 환해졌어.",
		"너는 내 가장 소중한 친구야! 고마운 마음을 담아 작은 선물을 같이 보내. 마음에 들면 좋겠다!"],
	"calm":["선물 고마워. 말로는 잘 못 했지만, 꽤 기뻤어. 잘 쓰고 있어.",
		"요즘 네가 지나가면 괜히 반가워. 언제든 쉬어 가.",
		"네 덕분에 집이 한결 아늑해졌어. 고맙다는 말, 이번엔 편지로 할게.",
		"오래 함께해 줘서 고마워. 내가 아끼는 걸 하나 보내. 너라면 잘 써 줄 거야."],
	"elegant":["보내 준 선물, 정성스럽게 장식해 두었어요. 안목이 정말 좋으시더군요.",
		"차 한 잔 함께하고 싶은 친구가 생겼네요. 바로 당신이에요.",
		"당신의 선물들이 제 방을 작은 전시회로 만들어 주었어요. 고마워요.",
		"소중한 친구에게 어울리는 답례를 고민하다 이걸 골랐어요. 곁에 두고 저를 떠올려 주세요."],
	"dreamy":["선물을 받은 날, 하늘이 조금 더 맑아 보였어요. 고마워요.",
		"당신 이야기를 시로 써 보려다 그만 잠들었어요. 꿈에서도 고마웠어요.",
		"창가에 둔 당신의 선물에 별빛이 내려앉아요. 매일 밤 인사해요.",
		"마음을 담은 작은 선물을 보내요. 달이 뜨는 밤마다 우리가 친구라는 걸 기억해 줘요."],
	"playful":["선물 고마워!!! 매일매일 가지고 놀고 있어! 헤헤.",
		"너 진짜 좋은 사람이야! 다음엔 같이 술래잡기 하자!",
		"너는 내 단짝이야! 비밀 기지도 보여 줄게. 아무한테도 말하면 안 돼!",
		"내 보물 중에 제일 좋은 걸 너한테 줄게! 소중히 해야 해, 약속!"],
}
## Storage-chest icons by item tag (the bag's own item pictures).
const TAG_ICONS := {"storage":"chest","clock":"clock","light":"lamp","plant":"seed","sea":"fish"}

static func t(text: String) -> String:
	return TranslationServer.translate(text)

static func can_receive(id: String) -> bool:
	return id in RECEIVERS

## The building a receiver lives in ("" for anyone else).
static func home_of(id: String) -> String:
	return str(Residents.resident(id).get("home","")) if can_receive(id) else ""

## True for a house whose residents decorate with gifts.
static func is_gift_home(building: String) -> bool:
	for id in RECEIVERS:
		if home_of(id)==building: return true
	return false

static func reaction(personality: String, mood: String, again: bool) -> String:
	var lines: Dictionary = LINES.get(personality,LINES.calm)
	return t(str(lines.get("again" if again else mood,lines.thanks)))

## "♥♥♡♡" for friendship levels 0..4.
static func hearts(level: int) -> String:
	return "♥".repeat(clampi(level,0,4))+"♡".repeat(4-clampi(level,0,4))

static func error_line(code: String) -> String:
	match code:
		"gift_own_village_only": return t("선물은 내 마을 주민에게만 줄 수 있어요.")
		"gift_needs_crafted_furniture": return t("공방에서 만든 가구만 선물할 수 있어요.")
		"object_not_found","object_not_in_inventory","stale_object_version": return t("그 가구는 지금 줄 수 없어요. 가방을 다시 확인해 주세요.")
	return t("지금은 선물을 받을 수 없대요.")

## The gift conversation: what is in the bag, the pick, the server's answer and the thanks.
static func start(api: Node, npc_id: String, say: Callable, done: Callable) -> void:
	var options: Dictionary = await api.request("/v1/npcs/%s/gift" % npc_id)
	if not options.ok:
		say.call([error_line(str(options.get("error","")))],[])
		return
	var data: Dictionary = options.data
	if not data.get("can_gift",false):
		say.call([error_line("gift_own_village_only")],[])
		return
	var items: Array = data.get("items",[])
	if items.is_empty():
		say.call([t("가방에 선물할 만한 가구가 없네요."),t("공방에서 만든 가구를 가져다주면 집에 예쁘게 놓아 둘게요!")],[])
		return
	# "Not now" comes first: dialogue focus starts on the first choice, so reading on with
	# Space or E never gives a piece away by accident.
	var choices: Array = [[t("다음에 줄게요"),Callable()]]
	for item in items.slice(0,6):
		var piece: Dictionary = item
		choices.append([str(piece.name),func(): give(api,npc_id,piece,say,done)])
	say.call([t("나한테 주는 거예요? 두근두근… 뭘까요?")],choices)

static func give(api: Node, npc_id: String, item: Dictionary, say: Callable, done: Callable) -> void:
	var result: Dictionary = await api.post("/v1/npcs/%s/gift" % npc_id,api.mutation({"object_id":item.id,"version":item.version}))
	if not result.ok:
		say.call([error_line(str(result.get("error","")))],[])
		return
	var reply: Dictionary = result.data
	if done.is_valid(): done.call(reply)
	say.call([reaction(str(reply.get("personality","calm")),str(reply.get("mood","thanks")),bool(reply.get("again",false))),
		t("곧 집 어딘가에 놓아 둘게요. 놀러 와서 찾아봐요!")],[[t("천만에요"),Callable()]])

## Hearts and petals over the resident, and a short chime.
static func thanks_effect(parent: Node3D, at: Vector3, app = null) -> void:
	Fx.bubble(parent,at+Vector3(0,2.15,0),"heart")
	Fx.burst(parent,at+Vector3(0,1.5,0),"petal",14,Color(0,0,0,0),0.35)
	Fx.burst(parent,at+Vector3(0,1.7,0),"sparkle",10,Color(0,0,0,0),0.3)
	if DisplayServer.get_name()!="headless": Fx.sound(app,"twinkle",at,1.15,-2.0)

## 모카's thank-you letter that closes the story chapter (server/story.py), for a seat or for decoration.
const STORY_LETTERS := {
	"seat":["제작자님에게. 테라스에 놓아 준 %s, 오늘 벌써 손님 셋이 앉아 쉬다 갔어.","네가 상상한 모습 그대로 우리 마을의 일부가 되었어. 앞으로도 잘 부탁해!"],
	"decor":["제작자님에게. 테라스에 놓아 준 %s, 지나가는 사람마다 걸음을 멈추고 구경해.","네가 상상한 모습 그대로 우리 마을의 일부가 되었어. 앞으로도 잘 부탁해!"],
}

## Thank-you letters for a finished request (server/quests.py, quests.gd), by resident.
const QUEST_LETTERS := {
	"regular":["제작자님에게. 네가 따 온 사과로 구운 파이, 손님들이 한 조각씩 더 달라고 해서 금방 동났어.","다음엔 너도 꼭 한 조각 먹으러 와. 제일 큰 걸로 남겨 둘게!"],
	"lamplighter":["제작자님에게. 네가 놓아 준 불빛이 밤마다 골목을 지켜 주고 있어요.","등불을 밝히다 그 앞을 지날 때면 꼭 인사해요. 고마워요!"],
}

## One letter as dialogue pages: who and how close, the words, and the present if any.
static func letter_lines(letter: Dictionary) -> Array:
	# A resident's move news (move_in.gd; marked by "move", its level is only for show).
	if letter.get("move") is Dictionary: return load("res://scripts/move_in.gd").letter_lines(letter)
	if letter.get("quest") is Dictionary:
		var words: Array = QUEST_LETTERS.get(str(letter.quest.get("npc", "")), ["고마워요! 덕분에 큰 힘이 됐어요."])
		var page := [t("✉ %s의 편지 · 부탁을 들어줘서") % t(str(letter.get("name","")))+"\n"+t(str(words[0]))]
		for line in words.slice(1): page.append(t(str(line)))
		return page
	if letter.get("story") is Dictionary:
		var about: Dictionary = letter.story
		var words: Array = STORY_LETTERS.seat if bool(about.get("sittable",false)) else STORY_LETTERS.decor
		var page := [t("✉ %s의 편지 · 마을의 첫 선물") % t(str(letter.get("name","")))+"\n"+t(str(words[0])) % str(about.get("object","")),t(str(words[1]))]
		var gift = letter.get("gift")
		if gift is Dictionary: page.append(t("편지와 함께 선물이 왔어요: %s. 가방을 확인해 보세요!") % str(gift.get("name","")))
		return page
	var pool: Array = LETTERS.get(str(letter.get("personality","calm")),LETTERS.calm)
	var level := clampi(int(letter.get("level",1)),1,4)
	var lines := [t("✉ %s의 편지 · %s") % [t(str(letter.get("name",""))),hearts(level)]+"\n"+t(str(pool[level-1]))]
	var present = letter.get("gift")
	if present is Dictionary: lines.append(t("편지와 함께 선물이 왔어요: %s. 가방을 확인해 보세요!") % str(present.get("name","")))
	return lines

## A toast for letters that came with a gift reply ("" when none).
static func letters_note(reply: Dictionary) -> String:
	var fresh: Array = reply.get("letters",[])
	if fresh.is_empty(): return ""
	var name := t(str(fresh[0].get("name","")))
	for letter in fresh:
		if letter.get("gift") is Dictionary: return t("%s에게서 편지와 답례 선물이 왔어요! 우편함을 열어 보세요.") % name
	return t("%s에게서 편지가 왔어요! 우편함을 열어 보세요.") % name

static func icon_for(tags: Array) -> String:
	for tag in tags:
		if TAG_ICONS.has(str(tag)): return "res://assets/items/%s.svg" % TAG_ICONS[str(tag)]
	return "res://assets/items/furniture.svg"

static func thanks_text(name: String, reply: Dictionary) -> String:
	var level := int(reply.get("friendship",{}).get("level",0))
	return t("%s에게 선물했어요 · 우정 %s") % [name,hearts(level)]

# ------------------------------------------------------------------ home versions and cache

## The latest home versions the village poll saw ({building: version}) and whose village they are.
static func set_versions(value, host) -> void:
	if value is Dictionary: Engine.set_meta("npc_home_versions",{"host":str(host),"homes":value})

static func version_of(home: String, host: String) -> int:
	var known: Dictionary = Engine.get_meta("npc_home_versions",{})
	if str(known.get("host",""))!=host: return -1
	return int(known.get("homes",{}).get(home,-1))

static func remember(home: String, data: Dictionary) -> void:
	var cache: Dictionary = Engine.get_meta("npc_home_cache",{})
	cache[home]=data
	Engine.set_meta("npc_home_cache",cache)

## A cached layout the village poll still reports current, or {}.
static func cached(home: String) -> Dictionary:
	var entry: Dictionary = Engine.get_meta("npc_home_cache",{}).get(home,{})
	if entry.is_empty() or int(entry.get("version",-2))!=version_of(home,str(entry.get("host_id",""))): return {}
	return entry
