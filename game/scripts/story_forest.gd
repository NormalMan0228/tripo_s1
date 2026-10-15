extends Node
## The opening chapter's epilogue (server/story.py EVENTS). A few seconds after 모카's gift scene,
## 다온 the postman comes running to the walker with news from the forest: something big moves
## beyond the stone gate. The tracker then leads there (story.gd "▸ 숲의 돌문으로 가기", guided
## across the islands like the chapter's other goals), and at the gate 'forest_gate' is recorded:
## the expedition is one E away. It bridges the gift to the survival part of the demo.
## Armed only by a gift scene this client played (story.gd finale): a chapter finished another way
## (tests, the operator) never brings a sudden dialogue. Each event is recorded once; a reset of the
## chapter clears them.
##   var forest := StoryForest.new(); story.add_child(forest); forest.story = story
##   forest.arm()          # story.gd finale
##   forest.tick(delta)    # story.gd _process, in the village with no window open
##   forest.active()       # 다온 told, the gate not reached yet (the tracker's line)
const Figure := preload("res://scripts/shadow_figure.gd")
const DayFolk := preload("res://scripts/day_folk.gd")
const Daylight := preload("res://scripts/daylight.gd")
const Residents := preload("res://scripts/residents.gd")
const Town := preload("res://scripts/town.gd")
const Roads := preload("res://scripts/roads.gd")
const Fx := preload("res://scripts/fx.gd")
const RpgUi := preload("res://scripts/rpg_ui.gd")

const RUNNER := "postman"
## Seconds of calm (no window open) after the gift scene before 다온 comes running.
const WAIT := 5.0
const FROM := 9.0
const STOP := 1.7
const SPEED := 3.6
const GATE_REACH := 4.0
const LINES := ["헉, 헉… 제작자님! 모카 씨 편지를 전하고 오는 길이었는데요…",
	"숲의 돌문 너머에서 이상한 소리가 나요. 쿵… 쿵… 뭔가 커다란 게 움직이는 것 같아요!",
	"방금 모카 씨를 도와준 제작자님이라면 뭔가 해낼 수 있을 거예요. 같이 가 봐 줄래요?"]

var story: Node
var armed := false
var wait := WAIT
var runner: Node3D
var running := false
var leaving := false
var gate_pending := false
## Seconds before the gate is reported again after a failed report.
var gate_wait := 0.0
## True while this node holds 다온's schedule (it releases only its own hold).
var held := false

func _exit_tree() -> void:
	if held: Residents.hold(RUNNER, false)

func arm() -> void:
	if told(): return
	armed = true
	wait = WAIT

func events() -> Array:
	var list = story.story.get("events", []) if is_instance_valid(story) else []
	return list if list is Array else []

func told() -> bool:
	return "forest_told" in events()

func active() -> bool:
	return told() and not "forest_gate" in events()

func tick(delta: float) -> void:
	if not is_instance_valid(story) or not is_instance_valid(story.app): return
	# The dialogue closed (a choice or Esc): 다온 runs on toward the forest.
	if is_instance_valid(runner) and not running and not leaving: leave(false)
	gate_wait = maxf(0.0, gate_wait-delta)
	if active() and not gate_pending and gate_wait <= 0.0 and story.walker_at().distance_to(Town.GATE) < GATE_REACH: reach_gate()
	if not armed or running or told() or story.step() != "done": return
	wait -= delta
	if wait <= 0.0: run_in()

## A starting point about FROM metres from the walker: a road if one is there (open ground), on
## level with the walker; else straight toward the forest gate.
func start_point(at: Vector2) -> Vector2:
	var ground := Town.height_at(at.x, at.y)
	var toward := (Town.GATE-at).normalized() if Town.GATE.distance_to(at) > 1.0 else Vector2(0, 1)
	var fallback := at+toward*FROM
	for i in 16:
		var dir := toward.rotated(TAU*float(i)/16.0*(1.0 if i % 2 == 0 else -1.0)*0.5)
		var p := at+dir*FROM
		if absf(Town.height_at(p.x, p.y)-ground) > 1.2: continue
		if Roads.on_road(p): return p
	return fallback

func run_in() -> void:
	var app: Node = story.app
	if not is_instance_valid(app.get("player")): return
	var figure = Figure.create_still(RUNNER)
	armed = false
	if figure == null: return
	running = true
	# The terrace guest is never 다온 (story.gd GUESTS), so this hold is ours alone.
	Residents.hold(RUNNER, true)
	held = true
	story.add_child(figure)
	var hour: float = story.hour()
	figure.set_day(DayFolk.is_day(RUNNER, hour), true)
	figure.set_night(Daylight.sample(hour).night)
	var at: Vector2 = story.walker_at()
	var start := start_point(at)
	var path := at-start
	var stop := start+path-path.normalized()*STOP
	figure.position = Town.point(start, 0.0)
	figure.face(atan2(path.x, path.y))
	runner = figure
	figure.pop("!", 1.8)
	figure.play_clip("run")
	var seconds := maxf(0.8, stop.distance_to(start)/SPEED)
	var run: Tween = figure.create_tween()
	run.tween_property(figure, "position", Town.point(stop, 0.0), seconds)
	run.parallel().tween_method(story.guest_step.bind(figure), 0.0, 1.0, seconds)
	await run.finished
	if not is_instance_valid(figure) or not is_instance_valid(app) or not is_instance_valid(app.get("player")):
		running = false
		return
	figure.play_clip("idle")
	# A window opened while he ran (the bag, a sign, a door): he waits until it closes.
	while is_instance_valid(app) and is_instance_valid(app.get("village_modal")) and is_instance_valid(figure):
		await get_tree().create_timer(0.25).timeout
	if not is_instance_valid(figure) or not is_instance_valid(app) or str(app.get("screen")) != "village":
		running = false
		return
	var look: Vector2 = story.walker_at()-Vector2(figure.position.x, figure.position.z)
	figure.face(atan2(look.x, look.y))
	app.player.face_point(figure.global_position)
	figure.pop("!", 1.4)
	Fx.burst(story, figure.global_position+Vector3(0, 1.9, 0), "sparkle", 8, Color(0,0,0,0), 0.35)
	# Recorded as he speaks: closing the box early still counts as told.
	story.post_event("forest_told")
	var lines: Array = LINES.map(func(line): return tr(line))
	app.open_dialogue(str(figure.title), portrait(figure), lines,
		[[tr("가 볼게요"), func(): leave(true)], [tr("조금 이따가"), func(): leave(false)]])
	running = false

func portrait(figure: Node3D) -> String:
	return ("res://assets/ui/day_%s.png" if bool(figure.day_target) else "res://assets/ui/shadow_%s.png") % RUNNER

## 다온 runs off toward the forest and is gone (back to his round); "가 볼게요" says where to go.
func leave(go: bool) -> void:
	if leaving or not is_instance_valid(runner): return
	leaving = true
	var figure := runner
	var from := Vector2(figure.position.x, figure.position.z)
	var dir := (Town.GATE-from).normalized() if Town.GATE.distance_to(from) > 1.0 else Vector2(0, 1)
	var end := from+dir*7.0
	figure.face(atan2(dir.x, dir.y))
	figure.play_clip("run")
	if go and is_instance_valid(story.app): story.app.message(tr("숲의 돌문으로! 금빛 길을 따라가요"))
	var run: Tween = figure.create_tween()
	run.tween_property(figure, "position", Town.point(end, 0.0), 2.0)
	await run.finished
	if is_instance_valid(figure):
		Fx.burst(story, figure.global_position+Vector3(0, 0.4, 0), "dust", 10, Color(0,0,0,0), 0.4)
		figure.queue_free()
	if held:
		Residents.hold(RUNNER, false)
		held = false
	runner = null
	leaving = false

## At the stone gate: recorded once; the expedition is one E away (main.gd open_expedition).
func reach_gate() -> void:
	gate_pending = true
	var result: Dictionary = await story.post_event("forest_gate")
	gate_pending = false
	if not result.ok: gate_wait = 5.0
	if not result.ok or not is_instance_valid(story) or not is_instance_valid(story.app): return
	story.app.message(tr("숲의 돌문 · E로 탐험을 떠나요"))
	RpgUi.sfx("confirm", -6.0)
	Fx.glow(story, Town.point(Town.GATE, 1.6), Color("ffd27a"), 2.2, 1.2)
