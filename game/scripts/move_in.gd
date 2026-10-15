extends Node3D
## Residents moving in and out (story 43 and 44, server contract docs/design/MOVE_IN_API.md):
## 단비 (resident "shopkeeper") moves into the empty lot "danbi_plot" after the forest rescue,
## may leave later and come back. This module shows the village the server describes:
##   - the lot's sign says what is coming ("곧 새 이웃이 이사 와요"), the house stands once she
##     lives there (Plots.set_plot_built) and goes again when she has moved out;
##   - her home becomes "danbi_house" (Residents.set_home, when residents.gd has it);
##   - the first time this client sees her arrive (a "moved_in"/"returned" news entry), the lot
##     sparkles and a ribbon says so, once per account (kept in user://, by news id);
##   - back after a move-out, her next greeting near the walker is a warm, hearts-aware line, once.
## Feature-detected: a /v1/me without "residents" (a server without moves) changes nothing.
## While visiting, the host's residency is asked for once (GET /v1/village/residency); with no
## answer the lot shows its default again if this session changed it.
##   var move_in := MoveIn.new(); story.add_child(move_in); move_in.story = story; move_in.start()
##   move_in.adopt_me(me)              # story.gd adopt_residents, with every /v1/me answer
##   MoveIn.letter_lines(letter)       # npc_gifts.gd, for letters carrying "move"
const Plots := preload("res://maps/archipelago/plots.gd")
const Residents := preload("res://scripts/residents.gd")
const NpcGifts := preload("res://scripts/npc_gifts.gd")
const Fx := preload("res://scripts/fx.gd")
const RpgUi := preload("res://scripts/rpg_ui.gd")

const NPC := "shopkeeper"
const PLOT := "danbi_plot"
## Her home before the moves (residents.gd's shop), used when nothing else is known.
const OLD_HOME := "13_shop"
const SIGN_SOON := "곧 새 이웃이 이사 와요"
const SIGN_AWAY := "단비가 잠시 떠났어요"
const SIGN_HOME := "단비네 집"
const ARRIVALS := ["moved_in", "returned"]
## Her greeting when she is back, warmer with more hearts (0-1, 2-3, 4+).
const BACK_LINES := ["다시 왔어요! 그동안 잘 지냈어요?",
	"다시 왔어요! 그동안 잘 지냈어요? 정말 보고 싶었어요.",
	"다시 왔어요! 그동안 잘 지냈어요? 제일 먼저 당신 얼굴이 떠올랐어요!"]
const GREET_REACH := 4.0
## Where the once-per-account moments are remembered (a test points it elsewhere).
static var save_path := "user://move_in_seen.cfg"
## Plots and Residents are static (per session), so what this module changed is too.
static var touched := false
static var home_override := false
static var original_home := ""
## The home last asked for (tests read it whether or not residents.gd has set_home yet).
static var last_home := ""

var story: Node
## The residency last shown ({} before any).
var data: Dictionary = {}
var host := ""
## A news entry to celebrate when the village is calm, and a greeting waiting for 단비.
var pending_arrival: Dictionary = {}
var pending_back: Dictionary = {}
## How many arrival moments and back greetings this module played (tests).
var celebrated := 0
var greeted_back := 0
var wait := 0.0
var seen: ConfigFile

func _ready() -> void:
	set_process(false)

func app() -> Node:
	return story.app if is_instance_valid(story) else null

## story.gd setup: the own village takes the last /v1/me, a visit asks for the host's residency.
func start() -> void:
	var main := app()
	if main == null or str(main.api.token).is_empty(): return
	if story.visiting():
		var reply: Dictionary = await main.api.request("/v1/village/residency")
		if not is_inside_tree(): return
		if reply.ok and reply.data is Dictionary and reply.data.has("residents"): apply(reply.data, false)
		elif touched: restore()
		return
	if main.get("me") is Dictionary: adopt_me(main.me)

## A /v1/me answer (own village; the field is always the account's own village).
func adopt_me(me) -> void:
	if not me is Dictionary or not me.has("residents") or not is_instance_valid(story) or story.visiting(): return
	apply(me.residents, true)

## Shows one residency answer: the lot, the sign, her home, and (own village) the moments.
func apply(residency, own: bool) -> void:
	if not residency is Dictionary: return
	if not bool(residency.get("enabled", false)):
		if touched: restore()
		return
	var entry := resident(residency)
	if entry.is_empty(): return
	data = residency
	host = str(residency.get("host_id", ""))
	touched = true
	var state := str(entry.get("state", ""))
	var plots = residency.get("plots", {})
	var plot_state := str(plots.get(PLOT, "")) if plots is Dictionary else ""
	var lives := state in ["home", "leaving"] or plot_state == "built"
	if Plots.is_built(PLOT) != lives: Plots.set_plot_built(PLOT, lives)
	var sign := SIGN_HOME if lives else (SIGN_AWAY if state == "away" and int(entry.get("moves", 0)) > 0 else SIGN_SOON)
	if str(Plots.sign_texts.get(PLOT, "")) != sign: Plots.set_sign_text(PLOT, sign)
	var home := str(entry.get("home", ""))
	set_home(home if lives and not home.is_empty() else "")
	if not own: return
	# The arrival moment: the newest unseen move-in news while she lives here (older ones just count as seen).
	var news = residency.get("news", [])
	for item in (news if news is Array else []):
		if not item is Dictionary or str(item.get("npc", "")) != NPC or not str(item.get("kind", "")) in ARRIVALS: continue
		var key := "news_"+str(item.get("id", ""))
		if was_seen(key) or str(pending_arrival.get("id", "")) == str(item.get("id", "")): continue
		if lives and pending_arrival.is_empty(): pending_arrival = item
		elif not lives: mark(key)
	# Back after a move-out: one warm greeting per return (moves counts the move-outs).
	if bool(entry.get("back", false)) and state == "home":
		var back_key := "back_%d" % int(entry.get("moves", 0))
		if not was_seen(back_key):
			var friendship = entry.get("friendship")
			var level := int(entry.get("hearts", 0))
			if not entry.has("hearts") and friendship is Dictionary: level = int(friendship.get("level", 0))
			pending_back = {"key":back_key, "hearts":level}
	else:
		pending_back = {}
	set_process(not pending_arrival.is_empty() or not pending_back.is_empty())

func resident(residency: Dictionary) -> Dictionary:
	var list = residency.get("residents", [])
	for item in (list if list is Array else []):
		if item is Dictionary and str(item.get("npc", "")) == NPC: return item
	return {}

## Back to what the map shows by itself: no house, the lot's own sign, her old home.
func restore() -> void:
	if Plots.is_built(PLOT): Plots.set_plot_built(PLOT, false)
	Plots.set_sign_text(PLOT, str(Plots.PLOTS[PLOT].get("sign_text", SIGN_SOON)))
	set_home("")
	touched = false
	data = {}

## Her home: `room`, or "" for the one she had before (only if this module changed it).
static func set_home(room: String) -> void:
	if room.is_empty():
		if not home_override: return
		home_override = false
		last_home = original_home if not original_home.is_empty() else OLD_HOME
		# "" drops the override in residents.gd (her listed home again).
		if has_static("set_home"): residents().call("set_home", NPC, "")
		return
	# Every /v1/me poll says the same: only a change re-plans her day.
	if home_override and room == last_home: return
	if not home_override:
		original_home = str(residents().call("home_of", NPC)) if has_static("home_of") else OLD_HOME
		home_override = true
	last_home = room
	if has_static("set_home"): residents().call("set_home", NPC, room)

## residents.gd as a plain object (its methods are called by name: they may not exist yet).
static func residents() -> Object:
	var script: Object = Residents
	return script

## residents.gd may or may not have the method yet (another change adds set_home/home_of).
static func has_static(method: String) -> bool:
	for entry in residents().get_script_method_list():
		if str(entry.get("name", "")) == method: return true
	return false

# ------------------------------------------------------------------ once-per-account memory

func memory() -> ConfigFile:
	if seen == null:
		seen = ConfigFile.new()
		seen.load(save_path)
	return seen

func section() -> String:
	return host if not host.is_empty() else "local"

func was_seen(key: String) -> bool:
	return bool(memory().get_value(section(), key, false))

func mark(key: String) -> void:
	memory().set_value(section(), key, true)
	memory().save(save_path)

# ------------------------------------------------------------------ the moments

## A few times a second while a moment waits: the village open, no window, not visiting.
func _process(delta: float) -> void:
	wait -= delta
	if wait > 0.0: return
	wait = 0.25
	var main := app()
	if main == null or story.visiting() or main.get("screen") != "village" or is_instance_valid(main.get("village_modal")): return
	if not pending_arrival.is_empty():
		celebrate(pending_arrival)
		pending_arrival = {}
	elif not pending_back.is_empty():
		greet_back()
	set_process(not pending_arrival.is_empty() or not pending_back.is_empty())

## Sparkles and a warm glow at the house, a ribbon on the screen, the house's name over the door.
func celebrate(news: Dictionary) -> void:
	mark("news_"+str(news.get("id", "")))
	celebrated += 1
	var info := Plots.plot_info(PLOT)
	var at: Vector3 = info.get("center", Vector3.ZERO)
	Fx.glow(self, at+Vector3(0, 0.6, 0), Color("ffd27a"), 6.0, 2.2)
	Fx.ring(self, at+Vector3(0, 0.1, 0), 4.5, Color(1.0, 0.9, 0.6, 0.8), 1.2)
	Fx.burst(self, at+Vector3(0, 2.0, 0), "sparkle", 28, Color(0,0,0,0), 3.0)
	Fx.burst(self, at+Vector3(0, 3.2, 0), "heart", 8, Color(0,0,0,0), 1.2)
	Fx.title(app(), info.get("door_at", at)+Vector3(0, 2.6, 0), tr(SIGN_HOME), Color("ffe08a"))
	var back := str(news.get("kind", "")) == "returned"
	banner(tr("새 이웃") if not back else tr("반가운 얼굴"), tr("단비가 이사 왔어요") if not back else tr("단비가 다시 돌아왔어요"))

## The move ribbon (like story.gd banner, without the chapter's line).
func banner(title: String, line: String) -> void:
	var main := app()
	if main == null or not is_instance_valid(main.get("ui")): return
	var old: Node = main.ui.get_node_or_null("MoveInBanner")
	if old: old.queue_free()
	var holder := Control.new()
	holder.name = "MoveInBanner"
	holder.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	main.ui.add_child(holder)
	var column := VBoxContainer.new()
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_theme_constant_override("separation", 6)
	holder.add_child(column)
	var stars := RpgUi.label(column, "✦  ⌂  ✦", 18, RpgUi.GOLD)
	stars.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var band := RpgUi.ribbon(column, title, true, 30)
	band.custom_minimum_size.x = 380
	var words := RpgUi.label(column, line, 18, Color("fff3cf"))
	words.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.reset_size()
	var size := column.get_combined_minimum_size()
	column.position = Vector2((RpgUi.CANVAS.x-size.x)*0.5, 132.0)
	column.size = size
	column.pivot_offset = size*0.5
	RpgUi.pop_in(column, 0.4, 0.7)
	RpgUi.sfx("confirm", -2.0)
	if DisplayServer.get_name() != "headless": Fx.sound(main, "tune", Vector3.INF, 1.15, 2.0)
	var fade := holder.create_tween()
	fade.tween_interval(4.0)
	fade.tween_property(holder, "modulate:a", 0.0, 0.8)
	fade.tween_callback(holder.queue_free)

## 단비 near the walker (her walker or a placed figure): the warm greeting, hearts rising.
func greet_back() -> void:
	var figure := find_danbi()
	if figure == null: return
	var level := int(pending_back.get("hearts", 0))
	var line := tr(BACK_LINES[0 if level < 2 else (1 if level < 4 else 2)])
	mark(str(pending_back.key))
	pending_back = {}
	greeted_back += 1
	var main := app()
	if figure.has_method("talk_to_player"): figure.talk_to_player(main.player.global_position)
	elif figure.has_method("face_point"): figure.face_point(main.player.position)
	if figure.has_method("smile"): figure.smile(3.5)
	story.speech(figure, 2.35, line+("  "+NpcGifts.hearts(level) if level > 0 else ""), 4.0)
	Fx.bubble(self, figure.global_position+Vector3(0, 2.9, 0), "heart")
	Fx.burst(self, figure.global_position+Vector3(0, 2.2, 0), "heart", 4+clampi(level, 0, 4)*2, Color(0,0,0,0), 0.5)

func find_danbi() -> Node3D:
	var main := app()
	var here: Vector2 = story.walker_at()
	for module in main.get("modules"):
		if not is_instance_valid(module) or not "walkers" in module: continue
		for walker in module.walkers:
			if str(walker.spec.id) != NPC or not walker.present or float(walker.fade) < 0.6: continue
			if here.distance_to(walker.xz()) < GREET_REACH: return walker
	for npc in main.get("npcs"):
		if not is_instance_valid(npc) or not npc.is_visible_in_tree() or str(npc.get_meta("cast", "")) != NPC: continue
		if here.distance_to(Vector2(npc.position.x, npc.position.z)) < GREET_REACH: return npc
	return null

# ------------------------------------------------------------------ move letters

## A move letter's page in the mailbox ("move": {"kind": in/out/back}); [] if it is not one.
static func letter_lines(letter: Dictionary) -> Array:
	var move = letter.get("move")
	if not move is Dictionary: return []
	var who := NpcGifts.t(str(letter.get("name", "단비")))
	var words: Array = {"in":["이사 왔어요", "오늘부터 이웃이 됐어요! 빈 집터에 작은 집을 지었어요. 언제든 놀러 와요."],
		"out":["잠시 떠나요", "잠시 마을을 떠나게 됐어요. 그동안 정말 고마웠어요. 꼭 다시 올게요."],
		"back":["다시 왔어요", "다시 돌아왔어요! 그동안 보고 싶었어요. 집에 한번 들러 줘요."]}.get(str(move.get("kind", "")), ["이사 소식", "이사 소식을 전해요."])
	return [NpcGifts.t("✉ %s의 편지 · %s") % [who, NpcGifts.t(words[0])]+"\n"+NpcGifts.t(words[1])]
