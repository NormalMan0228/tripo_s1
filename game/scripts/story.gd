extends Node3D
## The opening story chapter "마을의 첫 선물" in the village, a village module (main.gd
## VILLAGE_MODULES). A workshop maker has just moved to the island: a letter on the desk at home
## (story_home.gd) sends them to say hello at the café '빨간 지붕', residents met on the way
## greet the newcomer once each, 모카 the café owner asks for a chair (its look left to the
## player), the player crafts with the ordinary craft window, and whatever they bring is set out
## on the café terrace for good: a seat gets its first guest, anything else becomes decoration.
## A thank-you letter with a small present waits in the mailbox.
## server/story.py keeps the progress per player (so does the terrace, an outdoor home of 모카's
## in npc_homes); this module draws it:
##   * the objective tracker's lines (main.gd objective) and their goals for the route guide
##     (guide.gd asks story_line_key / story_goal); a goal on another island leads to this
##     island's signpost first, which opens with the goal's island on top;
##   * 모카 waiting on the terrace (a still shadow_figure: the villager by day, her shadow after
##     dark) while the chapter needs her; residents.gd holds her plan, so her walker and the café
##     interior never show her twice; her words open by themselves when the walker arrives;
##   * greetings: a short speech bubble and a heart over each resident the first time the walker
##     comes near (once each, kept on the server);
##   * the gift: the piece appears on the terrace at once, 모카 is delighted, a
##     passer-by walks over and sits on a seat, and a ribbon closes the chapter.
## Everyone (the owner and visitors) sees the terrace's piece; a seat has someone resting on it
## when the walker comes by in the daytime. Visitors see no chapter of their own here.
const Town := preload("res://scripts/town.gd")
const Residents := preload("res://scripts/residents.gd")
const DayFolk := preload("res://scripts/day_folk.gd")
const Daylight := preload("res://scripts/daylight.gd")
const Figure := preload("res://scripts/shadow_figure.gd")
const Fx := preload("res://scripts/fx.gd")
const RpgUi := preload("res://scripts/rpg_ui.gd")
const NpcGifts := preload("res://scripts/npc_gifts.gd")
const I18n := preload("res://scripts/i18n.gd")
const Loader := preload("res://scripts/model_loader.gd")
const VoiceBabble := preload("res://scripts/voice_babble.gd")
const Guide := preload("res://scripts/guide.gd")
const IxSources := preload("res://scripts/ix/ix_sources.gd")
const IxDriver := preload("res://scripts/ix/ix_driver.gd")
const Roads := preload("res://scripts/roads.gd")

## 모카 · 카페 주인 (day_folk.gd, shadow_folk.gd 'regular').
const MOKA := "regular"
const TERRACE_HOME := "cafe_terrace"
## The terrace slot (server/npc_homes.py OUTDOOR_SLOTS): the café's front lawn beside its tables,
## seen from the road, clear of the door apron; south-west of 모카, so the walker who comes from
## the road to her never stands on it.
const TERRACE := Vector2(-60.2, -27.6)
## Where 모카 waits, turned toward the road and the camera.
const MOKA_AT := Vector2(-59.6, -29.9)
const MOKA_LOOK := Vector2(0.6, 1.0)
## Where the first guest comes from (across the lawn, south-east of the terrace).
const GUEST_FROM := Vector2(-55.6, -24.6)
## The guest's footfalls walking in (as the room residents', studio.gd RESIDENT_STEP_DB), and the beat
## between sitting down (the seat's contact) and the guest's ♪ with 모카's reply.
const GUEST_STEP_DB := -11.0
const GUEST_SETTLE := 0.4
const STEPS := ["letter", "cafe", "craft", "done"]
const ISLANDS := {"square":"물결빛 광장","fields":"풍차 들판","garden":"정원 언덕","camp":"캠프 초원","lighthouse":"등대섬"}
## Figures stand while the walker is this close to the terrace.
const NEAR := 52.0
const TALK_REACH := 2.4
## 모카 speaks by herself this close (once per visit and per new piece).
const ARRIVE := 3.4
const GREET_REACH := 4.6
const GREET_GAP := 3.0
## Residents who may sit on the terrace's seat (shadow folk with a daytime look).
## (Not 다온 the postman: he runs up after the gift with the forest news, story_forest.gd.)
const GUESTS := ["gentleman", "stroller", "poet", "sweeper", "gardener", "miller", "shopkeeper", "kid"]
## Each resident's first words to the newcomer, in their own voice (shadow_folk.gd, day_folk.gd).
const GREETINGS := {"naru":"새로 온 제작자구나! 반가워!", "sora":"어머, 새로 이사 온 분이죠? 반가워요!",
	"moru":"새 이웃이군. 마을에 온 걸 환영해.", "haeru":"어서 와요! 이사 온 걸 환영해요.",
	"postman":"새로 온 제작자님! 편지 배달은 저한테 맡겨요.", "fisher":"…반가워요. 마을 생활, 금방 익숙해질 거예요.",
	"farmer":"어이쿠, 새 이웃이네! 반가워요.", "sweeper":"어서 와요! 길은 제가 늘 깨끗하게 해 둘게요.",
	"gentleman":"반갑습니다. 솜씨 좋은 제작자가 왔다고 들었지요.", "stargazer":"새로 온 사람이구나. 밤하늘 보러 놀러 와.",
	"lamplighter":"환영해요! 밤길은 제가 밝혀 둘게요.", "gardener":"새 이웃이 왔네요! 꽃이 필요하면 말해요.",
	"scout":"새로 온 제작자구나! 반가워!", "miller":"어서 와요. 갓 빻은 밀가루 냄새, 좋죠?",
	"shopkeeper":"어서 오세요, 새 이웃님! 가게에도 들러요.", "kid":"우와, 새 이웃이다! 반가워!",
	"stroller":"반가워요. 이 섬은 산책하기 참 좋아요.", "poet":"새 이웃이라니, 시 한 줄이 떠오르네요."}

## The live module (tests and tools).
static var current: Node
## The residents' requests once the chapter is over (quests.gd, a child of this module): their
## tracker lines and guide goals go through this module's ("story_quest:*", "story_quest_book").
const Quests := preload("res://scripts/quests.gd")
## The epilogue after the gift: 다온 runs up with news from the forest (story_forest.gd).
const StoryForest := preload("res://scripts/story_forest.gd")
## Residents moving in and out (단비 and her lot, move_in.gd; /v1/me "residents" when the server has it).
const MoveIn := preload("res://scripts/move_in.gd")

var app: Node
var quests: Node
var forest: Node
var move_in: Node
## server/story.py public() for this account ({} without the chapter or while visiting).
var story: Dictionary = {}
var busy := false
var moka: Node3D
var moka_yaw := 0.0
var guest: Node3D
var guest_id := ""
var guest_seated := false
var piece: Node3D
var piece_item: Dictionary = {}
var piece_seat := false
var terrace_version := -2
var terrace_pending := false
## Greeted this visit (the server's list comes with the chapter).
var greeted_here: Array = []
var greet_wait := 0.0
var bubbles: Array = []
var tick := 0.0
var welcomed := false
var offered := ""
## The gift scene is running or just ran: 모카 stays out until the walker leaves the terrace.
var reveal := false
var finale_reply: Dictionary = {}
var guided_key := ""
var guide_hooked := false
## The finished craft already pointed at 모카 (its object id), and the one finished before she asked.
var told_done := ""
var done_before := ""
## The player asked the guide for the mailbox (a click on its line): it follows across islands too.
var mailbox_asked := false
var banner_node: Control

func setup(main: Node) -> void:
	app = main
	name = "Story"
	current = self
	# The village is built before /v1/me answers: the chapter last seen this session holds 모카 at
	# once (so her walker never shows), the answer replaces it (main.gd refresh_inventory).
	var known = app.get("me").get("story") if app.get("me") is Dictionary else null
	var kept: Dictionary = Engine.get_meta("story_state", {})
	if known == null and str(kept.get("token", "")) == str(app.api.token): known = kept.get("story")
	# Signed out (the title's village): no chapter.
	if str(app.api.token).is_empty(): known = null
	adopt(known)
	quests = Quests.new()
	add_child(quests)
	quests.setup(main, self)
	forest = StoryForest.new()
	forest.name = "StoryForest"
	forest.story = self
	add_child(forest)
	move_in = MoveIn.new()
	move_in.name = "MoveIn"
	move_in.story = self
	add_child(move_in)
	move_in.start()

## The residents' requests from the server (main.gd, with /v1/me).
func adopt_quests(data) -> void:
	if is_instance_valid(quests): quests.adopt(data)

## The whole /v1/me answer (main.gd): residents' moves, when the server sends them (move_in.gd).
func adopt_residents(me) -> void:
	if is_instance_valid(move_in): move_in.adopt_me(me)

func leave() -> void:
	if is_instance_valid(quests): quests.leave()
	for entry in bubbles:
		if is_instance_valid(entry.panel): entry.panel.queue_free()
	bubbles.clear()
	if is_instance_valid(banner_node): banner_node.queue_free()
	release_guest()
	if current == self: current = null

func _exit_tree() -> void:
	if current == self: leave()

func visiting() -> bool:
	return is_instance_valid(app) and app.get("social") != null and app.social.visiting()

func step() -> String:
	return str(story.get("step", ""))

## The chapter is under way (not finished) for this player in their own village.
func waiting() -> bool:
	return step() in ["letter", "cafe", "craft"]

## The server's chapter: kept unless it is older than what this game already knows (a slow poll).
func adopt(data) -> void:
	var fresh: Dictionary = data if data is Dictionary and not visiting() else {}
	if not fresh.is_empty() and not story.is_empty() and int(fresh.get("run", 0)) == int(story.get("run", 0)) \
		and STEPS.find(str(fresh.get("step", ""))) < STEPS.find(step()):
		return
	if int(fresh.get("run", 0)) != int(story.get("run", 0)):
		welcomed = false
		offered = ""
		greeted_here.clear()
	if str(fresh.get("step", "")) == "craft" and step() != "craft":
		# A craft that ended before 모카 asked is not hers (the server's list knows; this is the
		# tracker's word in the moment between a craft's end and the next answer).
		var follower := tracker()
		done_before = str(follower.done.get("object_id", "")) if follower != null else ""
	story = fresh
	if is_instance_valid(app) and not visiting(): Engine.set_meta("story_state", {"token":str(app.api.token), "story":story})
	hold_moka()

func hold_moka() -> void:
	Residents.hold(MOKA, waiting() or reveal)

# ------------------------------------------------------------------ objective and route guide

## The tracker's text with the chapter's lines ("▸ " lines are goals; the guide turns them into rows).
## The residents' requests (quests.gd) sit above the base once the chapter is over.
func objective(base: String) -> String:
	# The requests' own lines (they open once the chair is ordered) for the wait below.
	var requests: String = quests.objective("") if is_instance_valid(quests) else ""
	if is_instance_valid(quests): base = quests.objective(base)
	if story.is_empty(): return base
	match step():
		"letter": return "▸ "+tr("나의 집 · 책상 위 편지 읽기")+"\n"+tr("이삿날 아침, 편지가 와 있어요")
		"cafe": return "▸ "+tr("카페 '빨간 지붕'에 인사하러 가기")+"\n"+tr("모카가 기다리고 있어요")
		"craft":
			if has_made(): return "▸ "+tr("완성! 모카에게 가져가기")+"\n"+tr("카페 '빨간 지붕' 테라스")
			if confirming(): return "▸ "+tr("그림이 나왔어요 · C로 확인하기")+"\n"+tr("마음에 들면 제작을 맡겨요")
			# While it is made: what the wait can hold (starseeds from chests, the shop and requests).
			if crafting(): return "▸ "+tr("제작 중 · 완성되면 모카에게 가져가기")+"\n"+tr("기다리는 동안 · 보물상자 · 사과 팔기 · 주민 부탁")+("\n"+requests if not requests.is_empty() else "")
			if stalled(): return "▸ "+tr("제작이 멈췄어요 · C로 다시 만들기")+"\n"+tr("어떤 모습이든 네 상상대로")
			return "▸ "+tr("%s · 모카의 의자 만들기") % preload("res://scripts/rpg_ui.gd").key_text("craft")+"\n"+tr("어떤 모습이든 네 상상대로")
		"done":
			# 다온's news first (the way on to the forest), then 모카's letter at the mailbox.
			var lines := PackedStringArray()
			if is_instance_valid(forest) and forest.active():
				lines.append("▸ "+tr("숲의 돌문으로 가기"))
				lines.append(tr("다온: 돌문 너머에서 이상한 소리가 나요"))
			if not bool(story.get("letter", {}).get("read", true)):
				lines.append("✦ "+tr("마을의 첫 선물 · 완료"))
				lines.append("▸ "+tr("우편함에서 모카의 편지 읽기"))
			if not lines.is_empty(): return "\n".join(lines)+("\n"+base if not base.is_empty() else "")
	return base

## The village's first toast while the chapter runs ("" for the usual welcome).
func welcome() -> String:
	if visiting(): return ""
	match step():
		"letter": return tr("집 책상 위에 편지가 와 있어요")
		"cafe": return tr("금빛 길을 따라 카페 '빨간 지붕'으로 가 보세요")
		"craft":
			if has_made(): return tr("만든 물건을 모카에게 가져가 보세요")
			if crafting(): return tr("공방에서 만드는 중이에요 · 완성되면 알려 드릴게요")
			return tr("C를 눌러 모카의 의자를 만들어 보세요")
	return ""

func tracker() -> Node:
	return app.craft_tracker() if is_instance_valid(app) and app.has_method("craft_tracker") else null

## A piece made since 모카 asked (the server's list, or the craft that just finished).
func has_made() -> bool:
	if not story.get("made", []).is_empty(): return true
	var follower := tracker()
	return follower != null and not follower.done.is_empty() and str(follower.done.get("object_id", "")) != done_before

func crafting() -> bool:
	var follower := tracker()
	if follower != null and not str(follower.job_id).is_empty(): return true
	return bool(story.get("crafting", false)) and (follower == null or not str(follower.job.get("state", "")) in ["failed", "cancelled", "unknown"])

## The craft's picture (or quote) waits for the player's yes in the craft window.
func confirming() -> bool:
	var follower := tracker()
	return follower != null and not str(follower.job_id).is_empty() and str(follower.job.get("state", "")) == "awaiting_confirmation"

## The last craft failed or was cancelled (nothing made since).
func stalled() -> bool:
	var follower := tracker()
	return follower != null and str(follower.job.get("state", "")) in ["failed", "cancelled", "unknown"]

## guide.gd: the goal key of a tracker line, "" when it is not the chapter's.
func story_line_key(line: String) -> String:
	var request: String = quests.line_key(line) if is_instance_valid(quests) else ""
	if not request.is_empty(): return request
	for entry in [["나의 집 · 책상 위 편지 읽기", "story_home"], ["카페 '빨간 지붕'에 인사하러 가기", "story_cafe"],
			["완성! 모카에게 가져가기", "story_cafe"], ["C · 모카의 의자 만들기", "story_craft"],
			["제작이 멈췄어요 · C로 다시 만들기", "story_craft"], ["그림이 나왔어요 · C로 확인하기", "story_craft"],
			["우편함에서 모카의 편지 읽기", "story_mailbox"], ["숲의 돌문으로 가기", "story_forest"]]:
		if line == tr(entry[0]): return entry[1]
	return ""

## guide.gd: where a chapter goal is ({"at", "name", "key"}); from another island the way starts
## at this island's signpost.
func story_goal(key: String) -> Dictionary:
	var goal := {}
	if key.begins_with(Quests.KEY) or key == Quests.BOOK_KEY:
		goal = quests.raw_goal(key) if is_instance_valid(quests) else {}
		if goal.is_empty(): return {}
		key = "quest"
	match key:
		"quest": pass
		"story_home": goal = {"at":Town.HOME_DOOR, "name":tr("나의 집 · 책상 위 편지"), "key":key}
		"story_cafe": goal = {"at":MOKA_AT+Vector2(1.3, 0.3), "name":tr("카페 '빨간 지붕' · 모카"), "key":key}
		"story_mailbox":
			var box := field_entry("mailbox")
			goal = {"at":box.get("at", Vector2(-51.3, 22.6)), "name":tr("나의 우편함"), "key":key}
		"story_forest": goal = {"at":Town.GATE, "name":tr("숲의 돌문"), "key":key}
		_: return {}
	var here := island_of(walker_at())
	var there := island_of(goal.at)
	if here != there:
		var sign := signpost(here)
		if not sign.is_empty():
			return {"at":sign.at, "name":tr("이정표 · %s(으)로") % tr(ISLANDS[there]), "key":str(goal.key)}
	return goal

## guide.gd: a click on a chapter row that is not a place (the craft line opens the craft window).
func story_row(key: String) -> bool:
	if (key.begins_with(Quests.KEY) or key == Quests.BOOK_KEY) and is_instance_valid(quests): return quests.row(key)
	if key != "story_craft" or not is_instance_valid(app): return false
	app.open_craft()
	return true

static func island_of(at: Vector2) -> String:
	return Guide.island_key(at)

func walker_at() -> Vector2:
	var body = app.get("player") if is_instance_valid(app) else null
	return Vector2(body.global_position.x, body.global_position.z) if is_instance_valid(body) else TERRACE

func guide_node() -> Node:
	for module in app.get("modules") if is_instance_valid(app) and app.get("modules") != null else []:
		if is_instance_valid(module) and module.has_method("guide_to"): return module
	return null

func field_module() -> Node:
	for module in app.get("modules") if is_instance_valid(app) and app.get("modules") != null else []:
		if is_instance_valid(module) and module.has_method("use_signpost"): return module
	return null

func field_entry(kind: String, island := "") -> Dictionary:
	var field := field_module()
	if field == null: return {}
	for entry in field.objects:
		if entry.kind == kind and (island.is_empty() or str(entry.spec.get("island", "")) == island): return entry
	return {}

func signpost(island: String) -> Dictionary:
	return field_entry("signpost", island)

## The first chapter goal on the tracker ("" for none).
func current_key() -> String:
	for line in objective("").split("\n"):
		if line.begins_with("▸ "):
			var key := story_line_key(line.trim_prefix("▸ "))
			if key in ["story_home", "story_cafe", "story_mailbox", "story_forest"]: return key
	return ""

## A new chapter goal is guided at once (unless the player turned the guide off); a guided one
## follows the walker across islands (signpost first, then the place).
func steer_guide() -> void:
	var guide := guide_node()
	if guide == null or str(app.get("screen")) != "village": return
	if not guide_hooked and guide.has_signal("arrived"):
		guide_hooked = true
		guide.arrived.connect(arrived)
	var key := current_key()
	var guided := str(guide.target.get("key", "")) if guide.active() else ""
	# A goal the chapter no longer has (it moved on, or it is done) stops being guided (the
	# residents' requests guide their own, quests.gd).
	if guided.begins_with("story_") and not guided.begins_with(Quests.KEY) and guided != key: guide.stop(false)
	# The mailbox line is guided only when the player asks (a click): the gift scene stays calm.
	if key == "story_mailbox":
		guided_key = key
		if guided == key: mailbox_asked = true
		if not mailbox_asked or Guide.player_stopped or guide.active(): return
		var post := story_goal(key)
		if not post.is_empty() and walker_at().distance_to(post.at) > 8.0: guide.set_target(post, true)
		return
	if key != guided_key:
		guided_key = key
		if key.is_empty() or Guide.player_stopped: return
		var goal := story_goal(key)
		if not goal.is_empty() and walker_at().distance_to(goal.at) > 6.0: guide.set_target(goal, false)
		return
	if key.is_empty() or Guide.player_stopped: return
	var goal := story_goal(key)
	if goal.is_empty(): return
	if not guide.active():
		# Arrived at a signpost and crossed (or walked away): on to the next leg; never again
		# for the spot the walker stands at.
		if walker_at().distance_to(goal.at) > 8.0: guide.set_target(goal, true)
		return
	if str(guide.target.get("key", "")) == key and Vector2(goal.at).distance_to(guide.target.at) > 3.0: guide.set_target(goal, true)

## At a signpost on the way: its travel choices open with the goal's island on top.
func arrived(key: String) -> void:
	if not key.begins_with("story_") or not is_instance_valid(app) or is_instance_valid(app.get("village_modal")): return
	var goal: Vector2 = {"story_home":Town.HOME_DOOR, "story_cafe":MOKA_AT, "story_forest":Town.GATE}.get(key, Vector2.INF)
	if key == "story_mailbox": goal = field_entry("mailbox").get("at", Vector2(-51.3, 22.6))
	if key.begins_with(Quests.KEY) and is_instance_valid(quests):
		quests.arrived(key)
		goal = quests.raw_goal(key).get("at", Vector2.INF)
	if goal == Vector2.INF: return
	var here := island_of(walker_at())
	var sign := signpost(here)
	if here == island_of(goal) or sign.is_empty(): return
	field_module().use_signpost(sign, island_of(goal))

# ------------------------------------------------------------------ frame

func _process(delta: float) -> void:
	if not is_instance_valid(app) or not is_instance_valid(app.get("player")): return
	update_bubbles(delta)
	tick -= delta
	if tick <= 0.0:
		tick = 0.25
		update_figures()
		if not story.is_empty() and not visiting(): steer_guide()
		if reveal and walker_at().distance_to(TERRACE) > 34.0 and finale_reply.is_empty():
			# The walker went on: 모카 goes back to her day.
			reveal = false
			hold_moka()
		if str(app.get("screen")) == "village" and not terrace_pending and (terrace_version == -2 or NpcGifts.version_of(TERRACE_HOME, host_id()) > terrace_version): refresh_terrace()
	if is_instance_valid(moka): turn_moka(delta)
	if str(app.get("screen")) != "village" or is_instance_valid(app.get("village_modal")):
		return
	if not finale_reply.is_empty():
		var reply := finale_reply
		finale_reply = {}
		finale(reply)
		return
	if busy or story.is_empty() or visiting(): return
	if step() == "craft": tell_done()
	if step() == "done" and is_instance_valid(forest): forest.tick(delta)
	if waiting():
		greet_wait -= delta
		if greet_wait <= 0.0: greet_nearby()
		arrive_at_moka()

func hour() -> float:
	var daylight = app.get("daylight")
	return daylight.current_hour() if is_instance_valid(daylight) and daylight.has_method("current_hour") else Daylight.clock_hour()

func host_id() -> String:
	if visiting(): return str(app.social.data.get("host_id", ""))
	return str(app.get("me").get("npc_homes_host", "")) if app.get("me") is Dictionary else ""

## 모카 and the terrace's guest stand while the walker is near; their look follows the hour.
func update_figures() -> void:
	var close := walker_at().distance_to(TERRACE) < NEAR
	var want_moka := close and (waiting() or reveal) and not visiting()
	if want_moka and not is_instance_valid(moka): spawn_moka()
	elif not want_moka and is_instance_valid(moka):
		moka.queue_free()
		moka = null
	var now := hour()
	var night: float = Daylight.sample(now).night
	if is_instance_valid(moka):
		var day := DayFolk.is_day(MOKA, now)
		if day != bool(moka.day_target): moka.set_day(day)
		moka.set_night(night)
	# A seat on the terrace has someone resting on it in the daytime (the first guest any time).
	var want_guest := close and piece_seat and is_instance_valid(piece) and (guest_seated or (now >= 7.0 and now < 21.5))
	if want_guest and not is_instance_valid(guest) and not reveal: seat_guest(false)
	elif not want_guest and is_instance_valid(guest) and not reveal: release_guest()
	if is_instance_valid(guest):
		var day := DayFolk.is_day(guest_id, now)
		if day != bool(guest.day_target): guest.set_day(day)
		guest.set_night(night)

func spawn_moka() -> void:
	var figure = Figure.create_still(MOKA)
	if figure == null: return
	add_child(figure)
	figure.position = Town.point(MOKA_AT, 0.0)
	moka_yaw = atan2(MOKA_LOOK.x, MOKA_LOOK.y)
	figure.face(moka_yaw)
	figure.set_day(DayFolk.is_day(MOKA, hour()), true)
	figure.set_night(Daylight.sample(hour()).night)
	figure.play_clip("idle")
	moka = figure

## 모카 turns toward the walker when it comes close, back to the road when it leaves.
func turn_moka(delta: float) -> void:
	var to := walker_at()-MOKA_AT
	var goal := atan2(to.x, to.y) if to.length() < 7.0 else atan2(MOKA_LOOK.x, MOKA_LOOK.y)
	var next := lerp_angle(moka_yaw, goal, minf(1.0, delta*4.0))
	if absf(angle_difference(next, moka_yaw)) > 0.002:
		moka_yaw = next
		moka.face(moka_yaw)

func moka_title() -> String:
	return str(moka.title) if is_instance_valid(moka) else DayFolk.title(MOKA)

## The dialogue box's picture path (by day a path with no picture that still picks her voice).
func moka_portrait() -> String:
	var day := DayFolk.is_day(MOKA, hour()) if not is_instance_valid(moka) else bool(moka.day_target)
	return ("res://assets/ui/day_%s.png" if day else "res://assets/ui/shadow_%s.png") % MOKA

# ------------------------------------------------------------------ module API (E)

func closest(at: Vector3) -> Dictionary:
	if not is_instance_valid(moka) or busy: return {}
	var d := Vector2(at.x, at.z).distance_to(MOKA_AT)
	if d >= TALK_REACH: return {}
	return {"prompt":I18n.talk_to(moka_title()), "distance":d, "story":"moka"}

func interact(entry: Dictionary) -> void:
	if str(entry.get("story", "")) == "moka": talk_moka()

## A craft finished during the chapter: after the craft's own word, where to take it.
func tell_done() -> void:
	var follower := tracker()
	if follower == null or follower.done.is_empty(): return
	var id := str(follower.done.get("object_id", ""))
	if id.is_empty() or id == told_done or id == done_before: return
	told_done = id
	get_tree().create_timer(2.8).timeout.connect(func():
		if is_instance_valid(app) and step() == "craft": app.message(tr("완성! 금빛 길을 따라 모카에게 가져가 보세요")))

## 모카's words open by themselves when the walker reaches her (once per visit; once per new piece).
func arrive_at_moka() -> void:
	if not is_instance_valid(moka) or walker_at().distance_to(MOKA_AT) > ARRIVE: return
	if step() in ["letter", "cafe"] and not welcomed:
		welcomed = true
		talk_moka()
	elif step() == "craft" and has_made():
		var made := ",".join(story.get("made", []).map(func(item): return str(item.id)))
		if made.is_empty() and tracker() != null: made = str(tracker().done.get("object_id", ""))
		if made != offered:
			offered = made
			talk_moka()

# ------------------------------------------------------------------ 모카's words

func say(lines: Array, choices: Array) -> void:
	if is_instance_valid(app.get("player")) and is_instance_valid(moka): app.player.face_point(moka.global_position)
	if is_instance_valid(moka): moka.smile(3.0)
	app.open_dialogue(moka_title(), moka_portrait(), lines, choices)

func talk_moka() -> void:
	if busy or not is_instance_valid(app) or is_instance_valid(app.get("village_modal")): return
	busy = true
	# The newest word first: what was made since she asked, and whether a craft is under way.
	var reply: Dictionary = await app.api.request("/v1/story")
	busy = false
	if reply.ok: adopt(reply.data.get("story"))
	if not is_instance_valid(app) or is_instance_valid(app.get("village_modal")): return
	match step():
		"letter", "cafe":
			say([tr("어서 와! 네가 새로 이사 온 제작자구나. 나는 카페 '빨간 지붕'의 모카야."),
				tr("실력 있는 제작자가 온다고 해서 마을이 온통 들떠 있었어."),
				tr("부탁이 하나 있어. 산책하다 쉬어 갈 손님을 위해 의자 하나가 필요해."),
				tr("어떤 모습이면 좋을지는 네게 맡길게. 네가 상상한 그대로면 돼!")],
				[[tr("좋아요, 만들어 올게요"), accept.bind(false)], [tr("지금 바로 만들기 · C"), accept.bind(true)]])
		"craft":
			var made: Array = story.get("made", [])
			if not made.is_empty():
				var choices: Array = [[tr("조금 있다가요"), Callable()]]
				for item in made.slice(0, 3): choices.append([tr("%s 건네기") % str(item.name), give.bind(item)])
				choices.append([tr("다른 물건 고르기"), pick_from_bag])
				say([tr("와, 혹시 그거…! 나를 위해 만들어 온 거야?")], choices)
			elif crafting():
				say([tr("벌써 만드는 중이구나! 완성되면 들고 와 줘."), tr("그동안 마을 구경도 하고 와. 다들 너를 기다렸거든.")],
					[[tr("다녀올게요"), Callable()], [tr("가방에서 고르기"), pick_from_bag]])
			else:
				say([tr("의자는 천천히 만들어도 괜찮아. 어떤 모습일지 벌써 궁금한걸!")],
					[[tr("공방 열기 · C"), open_craft], [tr("가방에서 고르기"), pick_from_bag], [tr("다녀올게요"), Callable()]])
		"done":
			say([tr("네가 만든 선물 덕분에 테라스가 한결 따뜻해졌어. 정말 고마워!")], [[tr("천만에요"), Callable()]])

func open_craft() -> void:
	if is_instance_valid(app): app.open_craft()

## 모카 asked: the goal turns to the craft (and the craft window may open at once).
func accept(open_window: bool) -> void:
	var result: Dictionary = await post_step("accept")
	if not result.get("ok", false):
		# A refusal: the soft deny in place of the toast chime (main.gd refuse()).
		var busy_line := tr("지금은 부탁을 들을 수 없대요. 잠시 뒤 다시 말을 걸어 주세요.")
		if app.has_method("refuse"): app.refuse(busy_line)
		else: app.message(busy_line)
		return
	if is_instance_valid(moka):
		moka.pop("♪", 1.8)
		Fx.bubble(self, moka.global_position+Vector3(0, 2.3, 0), "heart")
	# The chapter's new goal sounds like any resident's request taken (quests.gd): the quest_accept
	# fanfare, which also stands in for the toast chime and the guide's confirm.
	RpgUi.sfx("quest_accept", -6.0)
	app.message(tr("새 목표 · 모카의 의자 만들기"))
	if open_window: app.open_craft()

## The epilogue's events (server/story.py EVENTS: forest_told, forest_gate), once each.
func post_event(event: String) -> Dictionary:
	var result: Dictionary = await app.api.post("/v1/story/step", app.api.mutation({"action":"event", "event":event}))
	if result.ok and result.data.get("story") is Dictionary: adopt(result.data.story)
	return result

func post_step(action: String, npc := "") -> Dictionary:
	var body := {"action":action}
	if not npc.is_empty(): body["npc"] = npc
	var result: Dictionary = await app.api.post("/v1/story/step", app.api.mutation(body))
	if result.ok and result.data.get("story") is Dictionary: adopt(result.data.story)
	return result

## Any piece in the bag (or set down in the village) may be given: the chapter never stalls.
func pick_from_bag() -> void:
	await app.refresh_inventory()
	if not is_instance_valid(app): return
	var items: Array = app.me.get("objects", []).filter(func(item): return str(item.state) in ["inventory", "placed"])
	items.reverse()
	if items.is_empty():
		say([tr("가방이 비어 있네. 공방에서 하나 만들어 와 줄래?")], [[tr("공방 열기 · C"), open_craft], [tr("다녀올게요"), Callable()]])
		return
	var choices: Array = [[tr("조금 있다가요"), Callable()]]
	for item in items.slice(0, 6): choices.append([str(item.name), give.bind(item)])
	say([tr("어떤 걸 건네줄래?")], choices)

func give(item: Dictionary) -> void:
	if busy: return
	busy = true
	var result: Dictionary = await app.api.post("/v1/story/gift", app.api.mutation({"object_id":str(item.id), "version":int(item.version)}))
	if not is_instance_valid(app): return
	if not result.ok:
		busy = false
		await app.refresh_inventory()
		var words := tr("앗, 그 물건은 지금 건넬 수 없나 봐. 가방을 다시 확인해 줄래?")
		if str(result.get("error", "")) == "gift_own_village_only": words = tr("선물은 내 마을에서 건네줄 수 있어요.")
		say([words], [[tr("알겠어요"), Callable()]])
		return
	var reply: Dictionary = result.data
	reveal = true
	adopt(reply.get("story"))
	hold_moka()
	# 모카 is delighted at once; the piece appears on the terrace as soon as its model is in.
	if is_instance_valid(moka):
		NpcGifts.thanks_effect(self, moka.global_position, app)
		moka.pop("♥", 2.0)
		moka.smile(5.0)
	piece_seat = bool(reply.get("sittable", false))
	if reply.get("placed") is Dictionary:
		terrace_version = int(reply.get("home_version", terrace_version))
		await show_piece(reply.placed, true)
		piece_seat = bool(reply.get("sittable", false))
	app.refresh_inventory()
	await get_tree().create_timer(0.9).timeout
	busy = false
	if not is_instance_valid(app): return
	var title := str(reply.get("name", ""))
	var lines: Array = [tr("고마워! 딱 내가 바라던 의자야. 테라스에 바로 놓을게."), tr("산책하던 손님들이 정말 좋아하겠다!")] if piece_seat \
		else [tr("이건… 의자는 아니지만 정말 멋진걸!"), tr("테라스에 장식으로 두면 지나가는 손님마다 걸음을 멈추겠어.")]
	finale_reply = {}
	say(lines, [[tr("다행이에요"), Callable()]])
	# The rest plays once the words close (any way they close).
	finale_reply = reply.merged({"name":title})

## After 모카's words: the first guest sits down (a seat), the ribbon closes the chapter and the
## mailbox's letter is mentioned.
func finale(reply: Dictionary) -> void:
	if piece_seat:
		await seat_guest(true)
	elif is_instance_valid(piece):
		Fx.burst(self, piece.global_position+Vector3(0, 0.8, 0), "sparkle", 18, Color(0,0,0,0), 0.7)
		Fx.glow(self, piece.global_position+Vector3(0, 0.6, 0), Color("ffd27a"), 2.2, 1.4)
	if not is_instance_valid(app): return
	# The guest's "♪" and 모카's word first, then the ribbon, then the letter's note.
	await get_tree().create_timer(2.2 if piece_seat else 0.6).timeout
	if not is_instance_valid(app): return
	banner(tr("마을의 첫 선물"), tr("내가 상상한 %s, 이제 마을의 일부예요") % str(reply.get("name", "")))
	var note := NpcGifts.letters_note(reply)
	if not note.is_empty():
		get_tree().create_timer(5.6).timeout.connect(func(): if is_instance_valid(app): app.message(note))
	# A few calm seconds later 다온 comes running with news from the forest (story_forest.gd).
	if is_instance_valid(forest): forest.arm()

# ------------------------------------------------------------------ the terrace

## The terrace's piece as the server has it (the owner's own, or the host's during a visit).
func refresh_terrace() -> void:
	if terrace_pending or not is_instance_valid(app) or str(app.api.token).is_empty(): return
	terrace_pending = true
	var reply: Dictionary = await app.api.request("/v1/social/npc-homes/%s" % TERRACE_HOME)
	terrace_pending = false
	if not is_instance_valid(app): return
	if not reply.ok:
		# Asked once (a server without the terrace answers 404): again only when its version moves.
		terrace_version = maxi(terrace_version, -1)
		return
	terrace_version = int(reply.data.get("version", 0))
	var items: Array = reply.data.get("items", [])
	if items.is_empty():
		clear_piece()
		return
	var item: Dictionary = items[0]
	if str(piece_item.get("id", "")) == str(item.id) and is_instance_valid(piece): return
	await show_piece(item, false)
	if is_instance_valid(piece):
		piece_seat = bool(story.get("gift", {}).get("sittable", false)) if step() == "done" and str(story.get("gift", {}).get("id", "")) == str(item.id) \
			else seat_like(piece, str(item.get("name", "")))

## A seat by its interaction or by its name (a visitor does not know the host's chapter).
static func seat_like(node: Node, title: String) -> bool:
	if node.has_method("use_interaction") and str(node.get("rest")) == "sit": return true
	var low := title.to_lower()
	for word in ["의자", "소파", "벤치", "스툴", "걸상", "chair", "sofa", "bench", "stool", "seat"]:
		if low.contains(word): return true
	return false

func clear_piece() -> void:
	if is_instance_valid(piece): piece.queue_free()
	piece = null
	piece_item = {}
	piece_seat = false
	release_guest()

func show_piece(item: Dictionary, fresh: bool) -> void:
	var node: Node3D = await app.load_object(item, "/v1/social/village/objects/")
	if not is_instance_valid(app) or not is_inside_tree():
		if is_instance_valid(node): node.queue_free()
		return
	if node == null: return
	clear_piece()
	add_child(node)
	# Straight on the grass (the round plank deck under it was removed, user 2026-10-16).
	node.position = Town.point(Vector2(float(item.get("x", TERRACE.x)), float(item.get("z", TERRACE.y))), 0.0)
	node.rotation_degrees.y = float(item.get("rotation", 0))
	Loader.add_collision(node)
	piece = node
	piece_item = item
	if fresh: Fx.arrive(self, node, app, true)

## A resident sits on the terrace's seat: walking over from the café road the first time,
## already resting on later visits. Their plan is held meanwhile (residents.gd).
func seat_guest(walk_in: bool) -> void:
	if not is_instance_valid(piece): return
	release_guest()
	var walkers: Array = []
	for module in app.get("modules"):
		if is_instance_valid(module) and "walkers" in module: walkers = module.walkers
	var start := int(hour()) % GUESTS.size()
	var pick := ""
	for i in GUESTS.size():
		var id: String = GUESTS[(start+i) % GUESTS.size()]
		var shown := false
		for walker in walkers:
			if str(walker.spec.id) == id and walker.present and walker.xz().distance_to(walker_at()) < 40.0: shown = true
		if not shown:
			pick = id
			break
	if pick.is_empty(): pick = GUESTS[start]
	var figure = Figure.create_still(pick)
	if figure == null: return
	guest_id = pick
	Residents.hold(pick, true)
	add_child(figure)
	figure.set_day(DayFolk.is_day(pick, hour()), true)
	figure.set_night(Daylight.sample(hour()).night)
	guest = figure
	var size: Vector3 = piece.get_meta("size", Vector3(0.6, 0.9, 0.6))
	var front := Vector3(0, 0, 1).rotated(Vector3.UP, piece.rotation.y)
	var seat_at := piece.global_position+front*0.05+Vector3(0, clampf(size.y*0.5, 0.38, 0.62), 0)
	var yaw := piece.rotation.y
	var stop := piece.global_position+front*0.62
	# The chair's own seat socket (ISS-1, derived from its real shape): where the hips go, which way
	# the guest faces and where it stands before sitting. The old box formula stays the fallback.
	var socket := guest_socket()
	if not socket.is_empty():
		seat_at = socket.origin
		yaw = float(socket.yaw)
		if not (socket.approach as Array).is_empty(): stop = socket.approach[0].pos
		IxDriver.claims[IxDriver.key_of(piece, socket)] = figure.get_instance_id()
	if walk_in:
		var from := Town.point(GUEST_FROM, 0.0)
		stop.y = Town.height_at(stop.x, stop.z)
		figure.position = from
		var path := stop-from
		figure.face(atan2(path.x, path.z))
		figure.play_clip("walk")
		var seconds := maxf(1.0, Vector2(path.x, path.z).length()/1.25)
		var walk: Tween = figure.create_tween()
		walk.tween_property(figure, "position", stop, seconds)
		# Its footfalls along the way, as every other walker's (world_audio.stride).
		walk.parallel().tween_method(guest_step.bind(figure), 0.0, 1.0, seconds)
		await walk.finished
		if not is_instance_valid(figure) or not is_instance_valid(piece): return
		figure.play_clip("idle")
		figure.face(yaw+PI)
		await get_tree().create_timer(0.35).timeout
		if not is_instance_valid(figure): return
	figure.position = seat_at
	figure.face(yaw)
	figure.set_pose("sit")
	guest_seated = true
	if walk_in:
		# The weight lands on the player's piece: its contact as any seat in the village (main.gd
		# seat_sound, by the seat's material), then a beat later the guest's ♪ and 모카's reply.
		if is_instance_valid(app) and app.has_method("seat_sound"):
			var material := IxDriver.seat_material(socket) if not socket.is_empty() else "wood"
			app.seat_sound("settle", {"at":figure.global_position, "material":material, "kind":"sit"})
		await get_tree().create_timer(GUEST_SETTLE).timeout
		if not is_instance_valid(figure): return
		figure.pop("♪", 2.0)
		figure.smile(4.0)
		Fx.burst(self, seat_at+Vector3(0, 0.6, 0), "petal", 10, Color(0,0,0,0), 0.4)
		if is_instance_valid(moka):
			moka.pop("!", 1.4)
			speech(moka, 2.35, tr("벌써 첫 손님이네!"), 3.0)

## One frame of the guest walking in: its footfalls on the other walkers' voices (world_audio.stride),
## soft, on the café road's stone or on the grass.
func guest_step(_progress: float, figure: Node3D) -> void:
	if not is_instance_valid(figure) or not is_instance_valid(app): return
	var audio = app.get("world_audio")
	if not is_instance_valid(audio) or not audio.has_method("stride"): return
	var at := figure.global_position
	audio.stride("story_guest", at, get_process_delta_time(), "stone" if Roads.on_road(Vector2(at.x, at.z)) else "grass", false, GUEST_STEP_DB)

## The terrace piece's best seat socket, or {} when it has none (the box formula is used then).
func guest_socket() -> Dictionary:
	if not is_instance_valid(piece): return {}
	for resolved in IxSources.resolve_all(IxSources.for_node(piece, "sit"), ["sit", "perch"]):
		if resolved.valid: return resolved
	return {}

func release_guest() -> void:
	if is_instance_valid(guest):
		for key in IxDriver.claims.keys():
			if int(IxDriver.claims[key]) == guest.get_instance_id(): IxDriver.claims.erase(key)
	if is_instance_valid(guest): guest.queue_free()
	guest = null
	guest_seated = false
	if not guest_id.is_empty(): Residents.hold(guest_id, false)
	guest_id = ""

# ------------------------------------------------------------------ greetings

## The nearest resident the walker has not been greeted by says hello (once each, kept).
func greet_nearby() -> void:
	greet_wait = 0.3
	var here := walker_at()
	var greeted: Array = story.get("greeted", [])
	var best: Node3D
	var best_id := ""
	var gap := GREET_REACH
	for module in app.get("modules"):
		if not is_instance_valid(module) or not "walkers" in module: continue
		for walker in module.walkers:
			var id := str(walker.spec.id)
			# Only the residents the server knows as greeters (보니, 솔 and later arrivals are not).
			if id == MOKA or not GREETINGS.has(id) or id in greeted or id in greeted_here or not walker.present or float(walker.fade) < 0.6 or walker.state == "talk": continue
			var d: float = here.distance_to(walker.xz())
			if d < gap:
				gap = d
				best = walker
				best_id = id
	for npc in app.get("npcs"):
		if not is_instance_valid(npc) or not npc.is_visible_in_tree(): continue
		var id := str(npc.get_meta("cast", ""))
		if id.is_empty() or id in greeted or id in greeted_here: continue
		var d := here.distance_to(Vector2(npc.position.x, npc.position.z))
		if d < gap:
			gap = d
			best = npc
			best_id = id
	if best == null: return
	greet_wait = GREET_GAP
	greeted_here.append(best_id)
	if best.has_method("talk_to_player"): best.talk_to_player(app.player.global_position)
	elif best.has_method("face_point"): best.face_point(app.player.position)
	if best.has_method("smile"): best.smile(3.0)
	var line := tr(str(GREETINGS.get(best_id, "새로 온 제작자구나! 반가워!")))
	speech(best, 2.35, line, 3.2)
	Fx.bubble(self, best.global_position+Vector3(0, 2.9, 0), "heart")
	if DisplayServer.get_name() != "headless":
		var voice := ("res://assets/ui/day_%s.png" if bool(best.get("day_target")) else "res://assets/ui/shadow_%s.png") % best_id if best.has_method("talk_to_player") else best_id
		# A greeting bark first (once per voice per 30 s); the babble waits a moment for it.
		VoiceBabble.greet(app, voice)
		VoiceBabble.speak(app, voice, line)
	post_step("greet", best_id)

## A short speech bubble over someone's head, for a few seconds (2D, follows the 3D point).
func speech(anchor: Node3D, lift: float, text: String, seconds := 3.0) -> void:
	if not is_instance_valid(app) or not is_instance_valid(app.get("ui")): return
	var panel := PanelContainer.new()
	panel.name = "StoryBubble"
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.bg_color = Color("fffaf0", 0.97)
	style.set_corner_radius_all(14)
	style.set_border_width_all(2)
	style.border_color = Color("c9b48a")
	style.content_margin_left = 14
	style.content_margin_right = 14
	style.content_margin_top = 7
	style.content_margin_bottom = 8
	style.shadow_color = Color(0, 0, 0, 0.18)
	style.shadow_size = 5
	style.shadow_offset = Vector2(0, 3)
	panel.add_theme_stylebox_override("panel", style)
	var label := Label.new()
	label.text = text
	label.add_theme_font_override("font", RpgUi.FONT_STRONG)
	label.add_theme_font_size_override("font_size", 16)
	label.add_theme_color_override("font_color", Color("4a3b2b"))
	panel.add_child(label)
	var tail := Polygon2D.new()
	tail.name = "Tail"
	tail.color = Color("fffaf0")
	tail.polygon = PackedVector2Array([Vector2(-8, 0), Vector2(8, 0), Vector2(0, 10)])
	panel.add_child(tail)
	panel.modulate.a = 0.0
	app.ui.add_child(panel)
	bubbles.append({"panel":panel, "anchor":anchor, "lift":lift, "left":seconds, "age":0.0})

func update_bubbles(delta: float) -> void:
	if bubbles.is_empty(): return
	var camera: Camera3D = app.get("camera")
	var hidden: bool = is_instance_valid(app.get("village_modal"))
	for entry in bubbles.duplicate():
		var panel: PanelContainer = entry.panel
		entry.age += delta
		entry.left -= delta
		if entry.left <= 0.0 or not is_instance_valid(panel) or not is_instance_valid(entry.anchor) or not is_instance_valid(camera):
			if is_instance_valid(panel): panel.queue_free()
			bubbles.erase(entry)
			continue
		var at: Vector3 = entry.anchor.global_position+Vector3(0, float(entry.lift), 0)
		panel.visible = not hidden and not camera.is_position_behind(at)
		panel.reset_size()
		var point := camera.unproject_position(at)
		panel.position = point-Vector2(panel.size.x*0.5, panel.size.y+10.0)
		panel.pivot_offset = Vector2(panel.size.x*0.5, panel.size.y)
		var tail := panel.get_node_or_null("Tail") as Polygon2D
		if tail: tail.position = Vector2(panel.size.x*0.5, panel.size.y-1.0)
		var grow := minf(1.0, float(entry.age)*7.0)
		panel.scale = Vector2.ONE*(1.0 if RpgUi.calm() else lerpf(0.6, 1.0, grow))
		panel.modulate.a = minf(1.0, float(entry.age)*8.0)*minf(1.0, float(entry.left)*3.0)

# ------------------------------------------------------------------ the chapter's ribbon

func banner(title: String, line: String) -> void:
	if not is_instance_valid(app) or not is_instance_valid(app.get("ui")): return
	if is_instance_valid(banner_node): banner_node.queue_free()
	var holder := Control.new()
	holder.name = "StoryBanner"
	holder.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	app.ui.add_child(holder)
	banner_node = holder
	var column := VBoxContainer.new()
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.alignment = BoxContainer.ALIGNMENT_CENTER
	column.add_theme_constant_override("separation", 6)
	holder.add_child(column)
	var stars := RpgUi.label(column, "✦  ✦  ✦", 18, RpgUi.GOLD)
	stars.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var band := RpgUi.ribbon(column, title, false, 34)
	band.custom_minimum_size.x = 420
	var words := RpgUi.label(column, line, 18, Color("fff3cf"))
	words.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var chapter := RpgUi.label(column, tr("첫 번째 이야기 완료"), 14, RpgUi.GOLD)
	chapter.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.reset_size()
	var size := column.get_combined_minimum_size()
	column.position = Vector2((RpgUi.CANVAS.x-size.x)*0.5, 132.0)
	column.size = size
	column.pivot_offset = size*0.5
	RpgUi.pop_in(column, 0.4, 0.7)
	RpgUi.sfx("confirm", -2.0)
	if DisplayServer.get_name() != "headless": Fx.sound(app, "tune", Vector3.INF, 1.0, 2.0)
	if is_instance_valid(piece): Fx.burst(self, piece.global_position+Vector3(0, 1.0, 0), "sparkle", 20, Color(0,0,0,0), 0.8)
	var fade := holder.create_tween()
	fade.tween_interval(4.6)
	fade.tween_property(holder, "modulate:a", 0.0, 0.8)
	fade.tween_callback(holder.queue_free)
