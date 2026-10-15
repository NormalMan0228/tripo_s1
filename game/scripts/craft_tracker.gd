extends Node
## The one craft follower of a signed-in session, shared by every place the craft window opens (the
## village and every room). It lives under the root, so a craft started in the village keeps being
## followed inside the home or a room and back again (a scene change frees the village or the room,
## not this). It polls with its own connection, keeps the craft's last state for the window wherever
## it reopens, and tells the player once that the picture (or quote) is ready and once that the
## object is done, through the place the player is in.
##   var tracker := CraftTracker.of(api)   # null before signing in
##   tracker.attach(self)                  # this place shows the toasts (see craft_window.gd)
## Created at run time, not as an autoload: patch builds cannot add autoloads (patch_boot.gd).
const Api = preload("res://scripts/api.gd")
const CraftWords = preload("res://scripts/craft_words.gd")
const Fx = preload("res://scripts/fx.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")

## The craft's state changed (each poll's answer; {} when it is gone or was cleared).
signal updated(job: Dictionary)
## /v1/studio answered (the window's options, the account's crafts).
signal info_changed(info: Dictionary)

## "unknown" is a submission the server could not confirm: it waits for an operator (who gives the
## starseeds back), so the craft stops being followed and the player can craft again.
const TERMINAL := ["ready", "failed", "cancelled", "unknown"]
## Polls back off from 2 s to this while the server cannot be reached.
const MAX_POLL_PAUSE := 30.0

## One tracker per session (world address + token): two players in one process (tests) keep theirs.
static var trackers := {}

var api: Node
var session := ""
## The craft under way ("" when none) and its last answer.
var job_id := ""
var job: Dictionary = {}
## The finished craft ("ready") until the player places it or starts a new one.
var done: Dictionary = {}
## The picture (or quote) already announced (announce_key), so it is said once.
var announced := ""
## Every announcement made, as "picture:<job>:<draws>" and "ended:<job>" (tests count them).
var told: Array[String] = []
## The last /v1/studio answer: the window opens on it at once and refreshes it behind.
var info: Dictionary = {}
var polling := false
var stopped := false
## The place the player is in (main.gd or studio.gd) and the craft window while it is open.
var host: Node
var window: Control
## Toasts said while no place was attached (the walk between the village and a room).
var waiting: Array[String] = []

## The tracker of the session `network` (an api.gd) is signed in to; null before signing in.
static func of(network: Node) -> Node:
	if network == null or not is_instance_valid(network) or str(network.token).is_empty(): return null
	var key := str(network.base_url) + "|" + str(network.token)
	var found = trackers.get(key)
	if is_instance_valid(found) and not found.stopped: return found
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null or tree.root == null: return null
	var tracker: Node = (load("res://scripts/craft_tracker.gd") as GDScript).new()
	tracker.name = "CraftTracker"
	tracker.session = key
	tracker.api = Api.new()
	tracker.api.base_url = network.base_url
	tracker.api.token = network.token
	tracker.add_child(tracker.api)
	# The version gate listens to the place's own connection: refusals heard here go there too.
	tracker.api.refused.connect(func(code: String, data: Dictionary) -> void: tracker._relay("refused", [code, data]))
	tracker.api.session_lost.connect(func(code: String) -> void:
		tracker._relay("session_lost", [code])
		tracker.stop())
	tree.root.add_child(tracker)
	trackers[key] = tracker
	return tracker

## Signing out (or a lost session) ends the session's tracker.
static func end(network: Node) -> void:
	if network == null or not is_instance_valid(network): return
	var key := str(network.base_url) + "|" + str(network.token)
	var found = trackers.get(key)
	trackers.erase(key)
	if is_instance_valid(found): found.stop()

func stop() -> void:
	if stopped: return
	stopped = true
	job_id = ""
	trackers.erase(session)
	queue_free()

## This place shows the toasts from now on; anything said on the way here is said now.
func attach(place: Node) -> void:
	host = place
	if place != null and place.has_method("craft_say"):
		for words in waiting: place.craft_say(words)
		waiting.clear()

func window_open() -> bool:
	return is_instance_valid(window) and window.is_inside_tree() and window.visible

## Follows the craft `id` (or the one already followed) until it needs the player or ends. Only one
## loop runs; a later call while it runs just switches the craft it asks about.
func follow(id := "") -> void:
	# A craft that ended this session is not followed again (a list read just before it ended).
	if told.has("ended:" + id): return
	if not id.is_empty() and id != job_id:
		job_id = id
		if str(job.get("id", "")) != id: job = {}
		done = {}
	if polling or job_id.is_empty() or stopped: return
	polling = true
	var failures := 0
	while not job_id.is_empty() and not stopped:
		var asked := job_id
		var reply: Dictionary = await api.request("/v1/studio/jobs/" + asked)
		if stopped: break
		if asked != job_id: continue
		if not reply.ok:
			var status := int(reply.get("status", 0))
			# A craft that is gone stops; a dropped connection or a busy server is asked again, slower each time.
			if status in [401, 404]:
				job_id = ""
				job = {}
				updated.emit({})
				break
			failures += 1
			await get_tree().create_timer(poll_pause(failures)).timeout
			continue
		failures = 0
		var value: Dictionary = reply.data
		take(value)
		if str(value.get("state", "")) == "awaiting_confirmation" or str(value.get("state", "")) in TERMINAL: break
		await get_tree().create_timer(2.0).timeout
	polling = false

## A new craft the server just accepted: followed from its first answer.
func start(value: Dictionary) -> void:
	done = {}
	job_id = str(value.get("id", ""))
	job = value
	updated.emit(value)
	follow()

## The player cancelled the craft (the starseeds came back).
func cancelled(id: String) -> void:
	if id != job_id and not job_id.is_empty(): return
	job_id = ""
	job = {"id": id, "state": "cancelled"}
	updated.emit(job)
	bag_changed()

## The finished craft was placed or cleared ("새로 만들기").
func clear_done() -> void:
	if done.is_empty(): return
	done = {}
	if job_id.is_empty():
		job = {}
		updated.emit({})

## Takes one answer about the craft: announces the picture or quote and the end once each.
func take(value: Dictionary) -> void:
	job = value
	var state := str(value.get("state", ""))
	if state == "awaiting_confirmation":
		var key := announce_key(value)
		if key != announced:
			announced = key
			told.append("picture:" + key)
			chime("twinkle")
			say(CraftWords.ready_words(value, not window_open()))
	elif state in TERMINAL:
		job_id = ""
		if state == "ready": done = value
		var id := str(value.get("id", ""))
		if not told.has("ended:" + id):
			told.append("ended:" + id)
			if state == "ready": chime("craft_done")
			elif state == "failed": chime("craft_fail")
			var words := CraftWords.ended_words(value, not window_open())
			if not words.is_empty(): say(words)
			bag_changed()
	updated.emit(value)

## Reads /v1/studio (the window's options and the account's crafts) and adopts it.
func fetch_info() -> Dictionary:
	var reply: Dictionary = await api.request("/v1/studio")
	if reply.ok and reply.data is Dictionary: adopt(reply.data)
	return info

## A /v1/studio answer from anywhere: kept for the window, and a craft still under way (started on
## another PC or before a relaunch) is followed again.
func adopt(value: Dictionary) -> void:
	info = value
	if job_id.is_empty():
		for entry in value.get("jobs", []):
			if not str(entry.get("state", "")) in TERMINAL:
				follow(str(entry.get("id", "")))
				break
	info_changed.emit(value)

func cap() -> int:
	return int(info.get("max_tripo_credits", 0))

## Seconds before asking again after `failures` failed polls in a row: 4, 8, 16, then 30.
static func poll_pause(failures: int) -> float:
	return minf(MAX_POLL_PAUSE, 2.0 * pow(2.0, failures))

## Names the picture (or quote) the player is told about once: the job and its draw count.
static func announce_key(value: Dictionary) -> String:
	return str(value.get("id", "")) + ":" + str(value.get("concept", {}).get("draws", 0))

## A short sound for a craft moment (the picture is ready, the object is done or failed): the
## craft_* kinds are RpgUi take families (ui/craft_done ...), the rest Fx sounds.
static func chime(kind: String) -> void:
	if DisplayServer.get_name() == "headless": return
	if kind.begins_with("craft_"): RpgUi.sfx(kind, -4.0)
	else: Fx.sound(null, kind, Vector3.INF, 1.0, 4.0)

## Says `words` in the open window (a note over the card) and as the place's toast; kept for the
## next place when the player is between the village and a room.
func say(words: String) -> void:
	if words.is_empty(): return
	if window_open() and window.has_method("note"): window.note(words)
	if _host_ready(): host.craft_say(words)
	elif not window_open():
		waiting.append(words)
		if waiting.size() > 4: waiting.pop_front()

## The place refreshes its wallet and bag (a craft started, ended or was cancelled).
func bag_changed() -> void:
	if _host_ready() and host.has_method("craft_bag_changed"): host.craft_bag_changed()

func _host_ready() -> bool:
	return is_instance_valid(host) and host.is_inside_tree() and not host.is_queued_for_deletion() and host.has_method("craft_say")

## Passes a refusal heard on this connection to the place's own (version_gate.gd watches that one).
func _relay(signal_name: String, values: Array) -> void:
	if not is_instance_valid(host): return
	var network = host.get("api")
	if network is Node and is_instance_valid(network) and network.has_signal(signal_name):
		network.callv("emit_signal", [signal_name] + values)
