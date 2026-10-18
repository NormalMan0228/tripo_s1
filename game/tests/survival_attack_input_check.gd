extends SceneTree
## Observe real expedition intents. Stale Input action state alone must never arm a held attack.
const Main = preload("res://scripts/main.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const PauseMenu = preload("res://scripts/pause_menu.gd")
const SocialHud = preload("res://scripts/social_hud.gd")
var failures := 0
var checks := 0
var app: Node

class Probe extends Main:
	var attacks := 0
	var harvests := 0
	func intent(action: String, target := "") -> void:
		if action == "attack": attacks += 1
		if action == "harvest": harvests += 1
		super.intent(action,target)

func check(ok: bool, what: String) -> void:
	checks += 1
	print(("PASS " if ok else "FAIL ")+what)
	if not ok: failures += 1

func _initialize() -> void:
	call_deferred("run")

func wait(seconds: float) -> void:
	await create_timer(seconds).timeout

func press(code: int, down: bool, echo := false) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.physical_keycode = code
	event.pressed = down
	event.echo = echo
	Input.parse_input_event(event)
	await process_frame

func wait_ready() -> void:
	var veil = preload("res://scripts/transition.gd").of(self)
	for i in 250:
		if veil.veil.mouse_filter == Control.MOUSE_FILTER_IGNORE and not app.busy: return
		await wait(.05)
	check(false,"loading completes")

func stale_input(what: String) -> void:
	# An orphan action flag: no physical key-down was delivered to gameplay.
	Input.action_press("attack")
	var before: int = app.attacks
	await wait(1.1)
	check(app.attacks == before,what)
	Input.action_release("attack")
	await wait(.6)

func run() -> void:
	var server := "http://127.0.0.1:8766"
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server=arg.trim_prefix("--server=")
	preload("res://scripts/i18n.gd").remember("server",server)
	app = Probe.new()
	root.add_child(app)
	for i in 600:
		if app.title_page == "menu": break
		await wait(.1)
	await app.authenticate(true,server,"attack_"+str(Time.get_ticks_msec()),"Attack-qa-password123","")
	await app.start_run("forest","standard")
	await wait_ready()
	check(app.screen == "survival","real expedition starts")
	if app.screen != "survival": quit(1); return
	await stale_input("idle orphan attack flag does not start automatic attacks")
	var before: int = app.attacks
	await press(KEY_SPACE,true)
	await wait(1.1)
	check(app.attacks >= before+2,"a real held attack still repeats")
	await press(KEY_SPACE,false)
	await wait(.6)
	before=app.attacks
	await wait(1.1)
	check(app.attacks == before,"releasing attack stops repeats")
	var chat = SocialHud.of(app.api).chat
	chat.focus()
	await process_frame
	check(chat.field.has_focus(),"chat takes keyboard focus")
	await press(KEY_SPACE,true)
	await wait(.1)
	chat.release()
	await wait(.1)
	before=app.attacks
	await wait(1.1)
	check(app.attacks == before,"space typed in chat cannot arm gameplay attack")
	await press(KEY_SPACE,false)
	await press(KEY_SPACE,true)
	await wait(.1)
	chat.focus()
	await wait(.1)
	chat.release()
	before=app.attacks
	await wait(1.1)
	check(app.attacks == before,"chat interruption cancels an earlier held attack")
	await press(KEY_SPACE,false)
	await press(KEY_SPACE,true)
	await wait(.1)
	var menu = PauseMenu.open(app)
	await wait(.1)
	menu.show_settings()
	await wait(.1)
	menu.sub.close()
	await wait(.1)
	PauseMenu.close()
	await wait(.1)
	before=app.attacks
	await wait(1.1)
	check(app.attacks == before,"settings interruption requires a fresh attack press")
	await press(KEY_SPACE,false)
	await press(KEY_SPACE,true)
	await wait(.1)
	app.notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	await wait(.1)
	before=app.attacks
	await wait(.6)
	check(app.attacks == before,"focus loss stops repeating attack")
	app.notification(Node.NOTIFICATION_APPLICATION_FOCUS_IN)
	await wait(1.1)
	check(app.attacks == before,"returning to the window does not restart held attack")
	await press(KEY_SPACE,true,true)
	await wait(.6)
	check(app.attacks == before,"OS key-repeat echoes cannot rearm attack")
	await press(KEY_SPACE,false)
	before=app.attacks
	await press(KEY_SPACE,true)
	await press(KEY_SPACE,false)
	await wait(.6)
	check(app.attacks == before+1,"fresh short attack tap works exactly once")
	await stale_input("after a real attack, orphan action state still cannot rearm it")
	check(Time.get_ticks_msec()*.001 >= app.player.action_until,"one-shot attack clip expires without new input")
	if is_instance_valid(app.player.action_pose):
		check(app.player.action_pose.elapsed >= app.player.action_pose.duration,"attack pose settles without new input")
	GameSettings.rebind("attack",0,KEY_J)
	before=app.attacks
	await press(KEY_J,true)
	await wait(1.1)
	check(app.attacks >= before+2,"rebound attack key still holds and repeats")
	await press(KEY_J,false)
	await wait(.6)
	before=app.attacks
	await press(KEY_SPACE,true)
	await press(KEY_SPACE,false)
	await wait(.6)
	check(app.attacks == before,"old attack binding no longer attacks")
	GameSettings.rebind("attack",0,KEY_SPACE)
	before=app.harvests
	await press(KEY_E,true)
	await wait(1.1)
	check(app.harvests >= before+2,"held harvest input still repeats")
	await press(KEY_E,false)
	await wait(.6)
	before=app.harvests
	await wait(.6)
	check(app.harvests == before,"releasing harvest stops repeats")
	app.queue_free()
	await process_frame
	print("SURVIVAL_ATTACK_INPUT_DONE checks=%d failures=%d" % [checks,failures])
	quit(1 if failures else 0)
