## A friend's home opens only while its owner is inside (server/home_access.py,
## docs/contracts/SERVER_CONTRACTS_KO.md): the line shown when the door stays shut, and the village's
## answer at that door (refuse_at_door: the latch rattles and a padlock pops over the player).
extends RefCounted

const DoorAudio = preload("res://scripts/door_audio.gd")
const LOCK_ICON := "res://assets/ui/icons/lock.png"
const SHUT := {"owner_away": "아무도 없는 것 같아요. 문이 잠겨 있어요.", "locked": "문이 잠겨 있어요.",
	"ejected": "지금은 이 집에 들어갈 수 없어요."}
## The word under the padlock over the player's head ("ejected" shows the minutes left instead).
const TAG := {"owner_away": "부재중", "locked": "잠김"}
## How long the padlock stays over the player's head after its pop and rattle.
const POP_HOLD := 1.5

## The translated line for a presence reply's home block that is not open; "" while it is open or missing.
static func refusal(door) -> String:
	if not door is Dictionary or bool(door.get("open", true)): return ""
	return TranslationServer.translate(SHUT.get(str(door.get("reason", "")), SHUT.ejected))

## Minutes until a guest sent out may come back (`until` on the server's clock; now: the server's
## time when a reply told it, else this machine's), at least 1; 0 when the block has no `until`.
static func minutes_left(door, now := -1.0) -> int:
	if not door is Dictionary or float(door.get("until", 0.0)) <= 0.0: return 0
	if now <= 0.0: now = Time.get_unix_time_from_system()
	return maxi(1, ceili((float(door.until) - now) / 60.0))

## The village at a shut friend's door (main.gd open_studio): the line (the minutes left for a guest
## sent out), the latch rattling, and a padlock popping over the player's head with a short tag
## (부재중, 잠김, or the minutes). place: the village main (refuse(), player); reply: its last
## presence answer (the home block, and the server's time with the village's crops).
static func refuse_at_door(place: Node, reply: Dictionary) -> void:
	var door = reply.get("home")
	var village = reply.get("village")
	var crops = village.get("crops") if village is Dictionary else null
	var now := float(crops.get("server_time", -1.0)) if crops is Dictionary else -1.0
	var line := refusal(door)
	if line.is_empty(): return
	var reason := str(door.get("reason", ""))
	var minutes := minutes_left(door, now) if reason == "ejected" else 0
	if minutes > 0: line = place.tr("%d분 뒤에 다시 들어갈 수 있어요.") % minutes
	place.refuse(line)
	DoorAudio.play(place, "locked", "home")
	var hero = place.get("player")
	if hero is Node3D and is_instance_valid(hero) and hero.is_inside_tree():
		pop_lock(hero, place.tr("%d분") % minutes if minutes > 0 else TranslationServer.translate(TAG.get(reason, TAG.locked)))

## A padlock over a walker's head, screen-sized like the name tags: pops in, rattles against its
## latch, rises a little and fades. One at a time per walker.
static func pop_lock(hero: Node3D, tag: String) -> Node3D:
	var old := hero.get_node_or_null("DoorLockPop")
	if old: old.free()
	var pop := Node3D.new()
	pop.name = "DoorLockPop"
	pop.position = Vector3(0, 2.6, 0)
	hero.add_child(pop)
	var lock := Sprite3D.new()
	lock.name = "Lock"
	lock.texture = load(LOCK_ICON)
	lock.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lock.fixed_size = true
	lock.pixel_size = 0.00078
	lock.no_depth_test = true
	lock.render_priority = 12
	pop.add_child(lock)
	var words := Label3D.new()
	words.name = "Tag"
	words.text = tag
	words.font = load("res://assets/fonts/ui_bold.tres")
	words.font_size = 22
	words.pixel_size = 0.0021
	words.fixed_size = true
	words.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	words.no_depth_test = true
	words.modulate = Color("ffd9a0")
	words.outline_size = 8
	words.outline_modulate = Color(0.1, 0.07, 0.05, 0.92)
	words.offset = Vector2(0, -40)
	words.render_priority = 13
	words.outline_render_priority = 12
	pop.add_child(words)
	pop.scale = Vector3.ONE * 0.2
	var tw := pop.create_tween()
	tw.tween_property(pop, "scale", Vector3.ONE, 0.24).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	# The rattle: the padlock knocks side to side against its latch.
	for side in [7.0, -6.0, 4.0, -2.0, 0.0]: tw.tween_property(lock, "offset:x", side, 0.05)
	tw.tween_interval(POP_HOLD)
	tw.set_parallel(true)
	tw.tween_property(pop, "position:y", 2.85, 0.4).set_trans(Tween.TRANS_SINE)
	tw.tween_property(lock, "modulate:a", 0.0, 0.4)
	tw.tween_property(words, "modulate:a", 0.0, 0.4)
	tw.tween_property(words, "outline_modulate:a", 0.0, 0.4)
	tw.chain().tween_callback(pop.queue_free)
	return pop
