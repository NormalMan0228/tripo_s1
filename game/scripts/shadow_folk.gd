extends Node3D
## Village add-on (main.gd VILLAGE_MODULES): the "shadow folk", plain silhouettes
## with white eyes in the style of a mystery cartoon's unnamed culprit, who live
## on all five islands. Most stroll the road network (shadow_paths.gd) and cross
## the bridges, a few keep to a favourite corner (pier, gazebo, orchard), some only
## come out at night. Each has a small role: rumours and hints about the islands,
## a riddle, a "follow me" walk to a quiet spot, or a little daily favour (deliver a
## letter, find a dropped hoe, show a fish). Everything here is client-side
## flavour: rewards are toasts and smiles, never items or coins.
const Paths = preload("res://scripts/shadow_paths.gd")
const Figure = preload("res://scripts/shadow_figure.gd")
const Daylight = preload("res://scripts/daylight.gd")
const I18n = preload("res://scripts/i18n.gd")
const Roads = preload("res://scripts/roads.gd")
const Town = preload("res://scripts/town.gd")
const Minimap = preload("res://scripts/minimap.gd")
const Residents = preload("res://scripts/residents.gd")
const LAYOUT := "res://maps/archipelago/environment_layout.json"
## Bridge deck centre lines (environment_layout.json), used if the manifest is missing.
const BRIDGES := [[Vector2(-11,-36),Vector2(15,-36)],[Vector2(57,-7),Vector2(57,14)],[Vector2(-9,27),Vector2(16,27)],[Vector2(-25,58),Vector2(2,73)]]
## Short off-road walks to quiet corners; the first point joins the road network.
const SPURS := [
	["pond_pier",[Vector2(-29,42),Vector2(-32.4,43.9),Vector2(-37.2,44.0)]],
	["lh_pier",[Vector2(3,77),Vector2(2.6,79.4),Vector2(0.2,80.3),Vector2(-4.0,82.8)]],
	["orchard",[Vector2(-46,-33),Vector2(-48.4,-38.4),Vector2(-49.4,-41.6)]],
]
## Road ends that are views rather than doors.
const VIEW_ENDS := {"gazebo":Vector2(68,-32)}
const SAVE_PATH := "user://shadow_folk.cfg"
const TALK_REACH := 2.2
## hours: "always", "day" (go home at dusk) or "night" (only after dark).
## radius 0 roams every island; otherwise the shadow stays near home.
const FOLK := [
	{"id":"postman","title":"수상한 그림자 · 우편배달부","home":Vector2(-33,37),"radius":0.0,"speed":1.45,"build":[1.0,1.0],"gear":["cap","satchel"],"hours":"always","bridge_bias":1.2,"tint":"8fb7d6"},
	{"id":"fisher","title":"수상한 그림자 · 낚시꾼","home":Vector2(3,77),"radius":13.0,"speed":1.05,"build":[1.04,1.18],"gear":["bucket","rod","lantern"],"hours":"always","spot_bias":1.4,"tint":"8ec5c8"},
	{"id":"farmer","title":"수상한 그림자 · 농부","home":Vector2(-16,-29.5),"radius":17.0,"speed":1.1,"build":[0.97,1.22],"gear":["straw","hoe"],"hours":"day","tint":"c9d39a"},
	{"id":"sweeper","title":"수상한 그림자 · 청소부","home":Vector2(-33,37),"radius":20.0,"speed":1.0,"build":[0.93,1.0],"gear":["beanie","broom"],"hours":"always","porch_bias":0.6,"tint":"d8c39e"},
	{"id":"gentleman","title":"수상한 그림자 · 우산 신사","home":Vector2(24,30.5),"radius":0.0,"speed":1.2,"build":[1.12,0.94],"gear":["tophat","umbrella"],"hours":"always","bridge_bias":1.0,"tint":"b6a6d6"},
	{"id":"stargazer","title":"수상한 그림자 · 별지기","home":Vector2(30,-31),"radius":15.0,"speed":1.0,"build":[1.03,1.0],"gear":["beret","scarf"],"hours":"night","tint":"7f8fd0","eyes":[0.035,0.022]},
	{"id":"lamplighter","title":"수상한 그림자 · 등불지기","home":Vector2(-25.5,57.5),"radius":30.0,"speed":1.15,"build":[1.0,1.02],"gear":["cap","lantern"],"hours":"always","lantern_always":false,"tint":"e5c48d"},
	{"id":"gardener","title":"수상한 그림자 · 정원사","home":Vector2(49.2,-15.6),"radius":18.0,"speed":1.05,"build":[0.9,1.12],"gear":["straw","satchel"],"hours":"always","tint":"a9d3a2"},
	{"id":"scout","title":"수상한 그림자 · 탐험가","home":Vector2(52,38.5),"radius":19.0,"speed":1.3,"build":[1.06,1.05],"gear":["fedora","backpack"],"hours":"always","tint":"d6b08e"},
	{"id":"regular","title":"수상한 그림자 · 카페 주인","home":Vector2(-46,-33),"radius":18.0,"speed":0.95,"build":[1.0,1.32],"gear":["scarf","apron"],"hours":"always","spot_bias":0.8,"tint":"e3a99a"},
	{"id":"miller","title":"수상한 그림자 · 방앗간지기","home":Vector2(-18.9,-38.0),"radius":16.0,"speed":1.05,"build":[1.06,1.2],"gear":["flourcap","apron"],"hours":"always","tint":"e8dcc0"},
	{"id":"shopkeeper","title":"수상한 그림자 · 잡화점 주인","home":Vector2(-18.0,32.5),"radius":16.0,"speed":1.0,"build":[0.98,1.08],"gear":["glasses","apron"],"hours":"always","tint":"b9d0c4","eyes":[0.03,0.022]},
	{"id":"kid","title":"수상한 그림자 · 꼬마","home":Vector2(-29,42),"radius":17.0,"speed":1.55,"build":[0.72,1.0],"gear":["cap"],"hours":"day","spot_bias":1.0,"tint":"f0d27e","eyes":[0.037,0.027],"eye_tilt":4.0,"always_grin":true},
	{"id":"stroller","title":"수상한 그림자 · 밤 산책자","home":Vector2(57,3.5),"radius":0.0,"speed":1.15,"build":[1.08,1.0],"gear":["fedora","lantern"],"hours":"night","bridge_bias":1.2,"tint":"8f9bd9"},
	{"id":"poet","title":"수상한 그림자 · 시인","home":Vector2(63,-25),"radius":13.0,"speed":0.9,"build":[1.05,0.95],"gear":["beret","scarf"],"hours":"always","spot_bias":1.5,"tint":"c7a6d9"},
]

## Outdoor work and leisure by residents.gd activity: the hand prop shown while the
## shadow pauses, how far it roams from its spot, and whether it stays put.
const TASKS := {"fish":"fish","sweep":"sweep","farm":"hoe","write":"write","deliver":"deliver","light_lamps":"lamp"}
const ROAM := {"sweep":13.0,"farm":9.0,"scout":15.0,"play":12.0,"stroll":11.0}
const STAY := ["fish","write"]
## The schedule only moves a shadow on screen near the walker; elsewhere it hops
## (still through its door) so a far-away village keeps time without walking it.
const NEAR := 28.0
## Profiling (tests): microseconds spent in this module and its walkers' physics.
static var profile := false
static var profile_us := 0
## Test log of appearances and disappearances: {id, kind, at, building, hour}.
var record_events := false
var events: Array = []

var app: Node
var paths: Paths
var walkers: Array = []
var villager_points: Array[Vector2] = []
var night := 0.0
var clock := 0.0
var hour := 12.0
var day := 0
var persist := true
var done_today: Dictionary = {}
## Favours in progress: "letter" -> villager cast, "hoe" -> "dropped"/"carried".
var errands: Dictionary = {}
var dropped: Node3D
var leader: Node3D
var lead_spot := -1
var lead_lost := 0.0
var step_turn := 0
## Directed edges whose lane had to move off the default keep-right line.
var lanes_moved := 0
## building id (and room) -> {"node": path node by the door, "step": door step, "title"}
var doors := {}
## outside spot -> path node
var spot_nodes := {}
## Round stops: [{"node", "at" (what to face), "building"}]
var door_stops: Array = []
var lamp_stops: Array = []

## Milliseconds spent building the path graph (roads, lanes, door and spot index).
var graph_ms := 0

func setup(main: Node) -> void:
	app = main
	var started := Time.get_ticks_msec()
	paths = Paths.new()
	paths.build(Roads.ROADS, bridge_lines(), Town.DOORS, SPURS)
	for key in VIEW_ENDS:
		var node := paths.nearest(VIEW_ENDS[key])
		if node >= 0 and paths.points[node].distance_to(VIEW_ENDS[key]) < 1.5 and paths.links[node].size() == 1:
			paths.kinds[node] = "spot"
			paths.spot_names[node] = key
	lanes_moved = paths.fit_lanes(get_world_3d().direct_space_state)
	index_places()
	graph_ms = Time.get_ticks_msec()-started
	update_villager_points()
	load_progress()
	read_clock()
	night = Daylight.sample(hour).night
	var used: Array[int] = []
	for entry in FOLK:
		var resident: Dictionary = Residents.resident(str(entry.id))
		if resident.is_empty() or resident.kind != "shadow": continue
		var walker: CharacterBody3D = Figure.new()
		walker.configure(entry, self, paths)
		add_child(walker)
		walker.dress()
		walker.min_ground_y = Town.SHORE_MIN_Y
		walker.set_night(night)
		walkers.append(walker)
		var block := Residents.now(str(entry.id), hour, day)
		walker.block_key = block_key(block)
		walker.place = block.place
		walker.activity = block.activity
		walker.spot = block.spot
		if block.place != "outside":
			walker.building = block.place
			hide_walker(walker)
			continue
		# Already out when the village loads: start at the activity, no door walk.
		configure_activity(walker)
		var start := activity_node(walker)
		if start < 0 or start in used:
			start = start_node(door_for(str(resident.home)).get("step", entry.home), used)
		used.append(start)
		var links: Array = paths.links[start]
		walker.place_at(start, links[randi() % links.size()] if not links.is_empty() and not walker.stay else -1)
		start_activity(walker)

## Door nodes, outside spots and round stops on the path graph.
func index_places() -> void:
	doors.clear()
	door_stops.clear()
	for door in Town.DOORS:
		var node := -1
		for porch in paths.faces:
			if paths.faces[porch].distance_to(door.at) < 0.5: node = porch
		if node < 0:
			var gap := INF
			for i in paths.points.size():
				if paths.links[i].is_empty() or paths.kinds[i] == "bridge": continue
				var d: float = paths.points[i].distance_to(door.at)
				if d < gap and d > 2.0:
					gap = d
					node = i
		var entry := {"node":node, "step":Vector2(door.at), "title":str(door.title), "id":str(door.id)}
		doors[str(door.id)] = entry
		doors[str(door.room)] = entry
		if not str(door.room) in ["home", "workshop"]: door_stops.append({"node":node, "at":Vector2(door.at), "building":str(door.id)})
	spot_nodes.clear()
	var named := {}
	for node in paths.spot_names: named[paths.spot_names[node]] = node
	for key in Residents.OUTSIDE_SPOTS:
		var alias: String = {"lighthouse_pier":"lh_pier", "pond_pier":"pond_pier", "orchard":"orchard", "gazebo":"gazebo"}.get(key, "")
		if named.has(alias): spot_nodes[key] = named[alias]
		else: spot_nodes[key] = start_node(Residents.OUTSIDE_SPOTS[key], [])
	lamp_stops.clear()
	if FileAccess.file_exists(LAYOUT):
		var manifest = JSON.parse_string(FileAccess.get_file_as_string(LAYOUT))
		if manifest is Dictionary and manifest.get("instances") is Array:
			var taken := {}
			for item in manifest.instances:
				if str(item.get("id", "")) != "27_lamp": continue
				var at := Vector2(float(item.position[0]), float(item.position[2]))
				var node := paths.nearest(at)
				if node < 0 or taken.has(node) or paths.points[node].distance_to(at) > 7.0: continue
				taken[node] = true
				lamp_stops.append({"node":node, "at":at, "building":""})

func door_for(building: String) -> Dictionary:
	return doors.get(building, {})

func bridge_lines() -> Array:
	if FileAccess.file_exists(LAYOUT):
		var manifest = JSON.parse_string(FileAccess.get_file_as_string(LAYOUT))
		if manifest is Dictionary and manifest.get("bridges") is Array and not manifest.bridges.is_empty():
			var lines: Array = []
			for bridge in manifest.bridges:
				lines.append([Vector2(bridge.a[0], bridge.a[1]), Vector2(bridge.b[0], bridge.b[1])])
			return lines
	return BRIDGES

## A road node near `home` that no other shadow starts on.
func start_node(home: Vector2, used: Array) -> int:
	var best := -1
	var gap := INF
	for i in paths.points.size():
		if i in used or paths.links[i].is_empty() or not paths.kinds[i] in ["road", "porch", "spot"]: continue
		var d := paths.points[i].distance_to(home)
		if d < gap:
			gap = d; best = i
	return best if best >= 0 else paths.nearest(home)

func current_hour() -> float:
	var daylight = app.get("daylight") if is_instance_valid(app) else null
	if is_instance_valid(daylight) and daylight.has_method("current_hour"): return daylight.current_hour()
	return Daylight.clock_hour()

func read_clock() -> void:
	hour = current_hour()
	day = int(Residents.clock().day)

## Out of doors right now by the schedule (the old "hours" field is gone).
func wants_out(entry: Dictionary) -> bool:
	return Residents.now(str(entry.id), hour, day).place == "outside"

func player_node() -> Node3D:
	var player = app.get("player") if is_instance_valid(app) else null
	return player if is_instance_valid(player) else null

func player_xz() -> Vector2:
	var player := player_node()
	if player == null: return Vector2(1e6, 1e6)
	return Vector2(player.global_position.x, player.global_position.z)

func near_player(at: Vector2) -> bool:
	return player_xz().distance_to(at) < NEAR

func _process(delta: float) -> void:
	if not is_instance_valid(app): return
	var started := Time.get_ticks_usec() if profile else 0
	clock -= delta
	if clock <= 0.0:
		clock = 1.0
		refresh_schedule()
	var camera = app.get("camera")
	var eye: Vector3 = camera.global_position if is_instance_valid(camera) and camera.is_inside_tree() else Vector3(player_xz().x, 10, player_xz().y)
	for walker in walkers:
		if not walker.present and walker.state == "hidden": continue
		var d: float = eye.distance_to(walker.global_position)
		walker.anim_stride = 1 if d < 26.0 else (3 if d < 50.0 else 8)
	# A closed conversation lets the shadow go back to what it was doing.
	var modal = app.get("village_modal")
	for walker in walkers:
		if walker.state == "talk" and not is_instance_valid(modal): walker.talk_left = minf(walker.talk_left, 1.2)
	update_errands(delta)
	if profile: profile_us += Time.get_ticks_usec()-started

## ------------------------------------------------------------------ schedule

func block_key(block: Dictionary) -> String:
	return "%s|%s|%s|%.2f" % [block.place, block.spot, block.activity, float(block.from)]

func update_villager_points() -> void:
	villager_points.clear()
	for npc in (app.get("npcs") if is_instance_valid(app) and app.get("npcs") != null else []):
		if is_instance_valid(npc) and npc.is_visible_in_tree(): villager_points.append(Vector2(npc.position.x, npc.position.z))

## Once a second: the clock, the night and every shadow's block in residents.gd.
func refresh_schedule() -> void:
	read_clock()
	night = Daylight.sample(hour).night
	update_villager_points()
	for walker in walkers:
		if walker.visible: walker.set_night(night)
		if walker == leader or walker.state == "talk": continue
		var block := Residents.now(str(walker.spec.id), hour, day)
		var key := block_key(block)
		if key != walker.block_key:
			walker.block_key = key
			adopt(walker, block)
		elif walker.transit and walker.state == "travel" and walker.travel_purpose == "door" and not near_player(walker.xz()) and not near_player(walker.door_point):
			# Walked out of the walker's sight on a long way in: finish at the door now,
			# so the plan (and the room inside) never waits on a long walk.
			go_in(walker, walker.door_building)
		elif walker.present and walker.task_shown == "fish" and randf() < 0.05:
			walker.cast_rod()
			if near_player(walker.xz()): walker.pop("~", 1.2)

## Follows a new block: out of a door, on to the next spot, or in through a door.
func adopt(walker: Node, block: Dictionary) -> void:
	var was_in: String = walker.building
	var hidden: bool = walker.state == "hidden"
	walker.place = block.place
	walker.activity = block.activity
	walker.spot = block.spot
	if block.place == "outside":
		walker.building = ""
		walker.transit = false
		configure_activity(walker)
		if hidden: come_out(walker, was_in if not was_in.is_empty() else home_of(walker))
		elif walker.state in ["vanish", "door"]:
			# Turned back on the door step: step out to the door's path node first.
			var door := door_for(walker.door_building)
			if not walker.present: walker.set_present(true)
			if door.is_empty() or int(door.node) < 0:
				go_to_activity(walker)
				return
			walker.at_node = int(door.node)
			walker.target_node = int(door.node)
			walker.door_point = paths.points[int(door.node)]
			walker.state = "emerge"
		else:
			# Moving on to the next outdoor block.
			if not walker.present: walker.set_present(true)
			go_to_activity(walker)
		return
	walker.task = ""
	walker.stay = false
	if hidden:
		# Between two buildings: walk it over only where the walker can see.
		var from_door := door_for(was_in)
		var to_door := door_for(block.place)
		walker.building = block.place
		if was_in != block.place and not from_door.is_empty() and not to_door.is_empty() and (near_player(from_door.step) or near_player(to_door.step)):
			walker.transit = true
			come_out(walker, was_in)
		return
	walker.building = block.place
	go_in(walker, block.place)

func home_of(walker: Node) -> String:
	return str(Residents.resident(str(walker.spec.id)).get("home", ""))

## Roam area, pace, prop and stay-put flag for the walker's outdoor activity.
func configure_activity(walker: Node) -> void:
	var activity: String = walker.activity
	walker.task = TASKS.get(activity, "")
	walker.stay = activity in STAY
	walker.pace = float(walker.spec.get("speed", 1.25))*(1.75 if activity == "play" else 1.0)
	var node := activity_node(walker)
	if node >= 0:
		walker.roam_center = paths.points[node]
		walker.roam_radius = float(ROAM.get(activity, ROAM.stroll))
	else:
		# "stroll" wanders the roads around wherever it is; "rounds" the whole network.
		walker.roam_center = walker.xz()
		walker.roam_radius = 0.0 if walker.spot == "rounds" else 26.0

func activity_node(walker: Node) -> int:
	if walker.spot in ["stroll", "rounds", "lamps"]: return -1
	return int(spot_nodes.get(walker.spot, -1))

## Fades in on the door step of `building` and steps out to its path node.
func come_out(walker: Node, building: String) -> void:
	var door := door_for(building)
	if door.is_empty() or int(door.node) < 0: door = door_for(home_of(walker))
	walker.set_present(true)
	walker.fade = 0.0
	walker.begin_emerge(door.step, int(door.node))
	walker.last_appear = door.step
	walker.appear_building = building
	log_event(walker, "appear", door.step, building)

## Called by the figure on the path node in front of the door.
func emerged(walker: Node) -> void:
	if walker.place == "outside":
		configure_activity(walker)
		go_to_activity(walker)
	else:
		go_in(walker, walker.building)

func go_to_activity(walker: Node) -> void:
	walker.travel_purpose = "activity"
	var goal := activity_node(walker)
	if walker.activity in ["deliver", "light_lamps"]:
		start_activity(walker)
		return
	if goal < 0:
		start_activity(walker)
		return
	if walker.at_node == goal and walker.xz().distance_to(paths.points[goal]) < 1.0:
		start_activity(walker)
		return
	if not near_player(walker.xz()) and not near_player(paths.points[goal]) and walker.state != "emerge":
		walker.place_at(goal, -1)
		start_activity(walker)
		return
	var route: Array[int] = paths.route(walker.at_node, goal)
	if route.is_empty():
		walker.place_at(goal, -1)
		start_activity(walker)
		return
	walker.begin_travel(route)

## At the spot: settle in (pier, gazebo), start a round, or roam the area.
func start_activity(walker: Node) -> void:
	walker.travel_purpose = ""
	match str(walker.activity):
		"deliver":
			next_stop(walker, door_stops)
			return
		"light_lamps":
			next_stop(walker, lamp_stops)
			return
	if walker.stay:
		var prev: int = walker.from_node
		if prev < 0 or prev == walker.at_node: prev = paths.links[walker.at_node][0] if not paths.links[walker.at_node].is_empty() else -1
		var view: Vector2 = paths.points[walker.at_node]-paths.points[prev] if prev >= 0 else Vector2(0, 1)
		walker.begin_pause(randf_range(25.0, 50.0), atan2(view.x, view.y))
		walker.look_clock = 1e6
		return
	walker.choose_next()

## The next door (postman) or lamp (lamplighter) on the round, nearest first.
func next_stop(walker: Node, stops: Array) -> void:
	if stops.is_empty():
		walker.choose_next()
		return
	if walker.stops.is_empty():
		walker.stops = range(stops.size())
		walker.stops.shuffle()
	var here: Vector2 = walker.xz()
	var best := 0
	for i in walker.stops.size():
		var a: Dictionary = stops[walker.stops[i]]
		var b: Dictionary = stops[walker.stops[best]]
		# Mostly the nearest one, sometimes a random pick for variety.
		if paths.points[a.node].distance_to(here) < paths.points[b.node].distance_to(here): best = i
	if randf() < 0.25: best = randi() % walker.stops.size()
	var stop: Dictionary = stops[walker.stops[best]]
	walker.stops.remove_at(best)
	walker.current_stop = stop
	walker.travel_purpose = "stop"
	var route: Array[int] = paths.route(walker.at_node, int(stop.node))
	if not near_player(walker.xz()) and not near_player(paths.points[stop.node]):
		walker.place_at(int(stop.node), -1)
		travel_arrived(walker)
		return
	if route.is_empty():
		walker.choose_next()
		return
	walker.begin_travel(route)

## Called by the figure at the end of a route.
func travel_arrived(walker: Node) -> void:
	match str(walker.travel_purpose):
		"door":
			walker.begin_door(walker.door_point)
		"activity":
			start_activity(walker)
		"stop":
			var stop: Dictionary = walker.current_stop
			var look: Vector2 = Vector2(stop.at)-walker.xz()
			walker.begin_pause(randf_range(3.0, 5.0), atan2(look.x, look.y))
			if walker.activity == "light_lamps":
				walker.smile(2.5)
				if near_player(walker.xz()): walker.pop("✦", 1.6)
			elif near_player(walker.xz()): walker.pop("✉", 1.6)
		_:
			walker.choose_next()

## A pause ran out; true when the schedule picked what comes next.
func pause_over(walker: Node) -> bool:
	if walker.place != "outside" or walker.transit: return false
	if walker.stay:
		walker.begin_pause(randf_range(25.0, 50.0), walker.face_yaw)
		walker.look_clock = 1e6
		return true
	if walker.travel_purpose == "stop":
		next_stop(walker, door_stops if walker.activity == "deliver" else lamp_stops)
		return true
	return false

## Roaming arrivals: sweepers and farmers stop to work, the kid keeps running.
func walker_arrived(walker: Node) -> bool:
	match str(walker.activity):
		"sweep", "farm":
			if randf() < 0.65:
				walker.begin_pause(randf_range(5.0, 11.0))
				return true
		"play":
			if randf() < 0.12:
				walker.begin_pause(randf_range(0.8, 1.6))
				if near_player(walker.xz()): walker.pop("♪", 1.0)
			else:
				walker.choose_next()
			return true
	return false

## Heads for the door of `building` and fades out on its step.
func go_in(walker: Node, building: String) -> void:
	var door := door_for(building)
	walker.transit = true
	walker.door_building = building
	walker.travel_purpose = "door"
	if door.is_empty() or int(door.node) < 0:
		vanish(walker, building)
		return
	walker.door_point = door.step
	if near_player(walker.xz()) or near_player(door.step):
		var route: Array[int] = paths.route(walker.at_node, int(door.node))
		if not route.is_empty():
			walker.begin_travel(route)
			return
	# Out of sight: hop to the step and fade there.
	walker.position = walker.step_point(door.step, int(door.node), 0.05)
	walker.ground_y = walker.position.y
	walker.velocity = Vector3.ZERO
	walker.just_placed = true
	walker.resting = false
	vanish(walker, building)

## Called by the figure on the door step.
func door_reached(walker: Node) -> void:
	vanish(walker, walker.door_building)

func vanish(walker: Node, building: String) -> void:
	walker.state = "vanish"
	walker.show_task("")
	walker.set_present(false)
	walker.last_vanish = walker.xz()
	walker.vanish_building = building
	log_event(walker, "vanish", walker.xz(), building)

func hide_walker(walker: Node) -> void:
	walker.present = false
	walker.fade = 0.0
	walker.visible = false
	walker.collision_layer = 0
	walker.collision_mask = 0
	walker.state = "hidden"
	walker.set_physics_process(false)

func log_event(walker: Node, kind: String, at: Vector2, building: String) -> void:
	if not record_events: return
	events.append({"id":str(walker.spec.id), "kind":kind, "at":at, "building":building, "hour":hour})
	if events.size() > 4000: events = events.slice(2000)

## ------------------------------------------------------------------ module API

func closest(at: Vector3) -> Dictionary:
	var here := Vector2(at.x, at.z)
	var best := {}
	var gap := TALK_REACH
	for walker in walkers:
		if not walker.present or walker.fade < 0.6: continue
		var d: float = here.distance_to(walker.xz())
		if d < gap:
			gap = d
			best = {"prompt":tr("%s와 대화") % walker.title, "distance":d, "walker":walker}
	if is_instance_valid(dropped) and errands.get("hoe", "") == "dropped":
		var d := here.distance_to(Vector2(dropped.position.x, dropped.position.z))
		if d < 1.7 and d < gap:
			best = {"prompt":tr("떨어진 호미 줍기"), "distance":d, "item":"hoe"}
	return best

func interact(entry: Dictionary) -> void:
	if entry.get("item", "") == "hoe":
		pick_up_hoe()
		return
	var walker = entry.get("walker")
	if is_instance_valid(walker): talk(walker)

func leave() -> void:
	for walker in walkers:
		if is_instance_valid(walker): walker.queue_free()
	walkers.clear()
	if is_instance_valid(dropped): dropped.queue_free()
	leader = null
	app = null

## ------------------------------------------------------------------ dialogue

func portrait(walker: Node) -> String:
	return "res://assets/ui/shadow_%s.png" % str(walker.spec.id)

func say(walker: Node, lines: Array, choices: Array = []) -> void:
	if not is_instance_valid(app): return
	if choices.is_empty(): choices = [[tr("고마워요"), Callable()]]
	var player := player_node()
	if is_instance_valid(walker):
		walker.talk_to_player(player.global_position if player else walker.global_position)
		if player and player.has_method("face_point"): player.face_point(walker.global_position)
	var text: Array[String] = []
	for line in lines: text.append(str(line))
	app.open_dialogue(str(walker.title), portrait(walker), text, choices)

func toast(text: String) -> void:
	if is_instance_valid(app) and app.has_method("message"): app.message(text)

func effect(kind: String) -> void:
	var sound = app.get("sound") if is_instance_valid(app) else null
	if is_instance_valid(sound) and sound.has_method("effect"): sound.effect(kind)

func float_text(text: String, at: Vector3, color := Color("d9d2ff")) -> void:
	if is_instance_valid(app) and app.has_method("floating_feedback"): app.floating_feedback(text, at, color)

func talk(walker: Node) -> void:
	var id := str(walker.spec.id)
	if walker == leader:
		# Mid-walk the shadow only waves the walker on.
		walker.pop("♪", 1.2)
		app.open_dialogue(str(walker.title), portrait(walker), [tr("이쪽이에요, 조금만 더 가면 돼요!")] as Array[String], [[tr("따라간다"), Callable()]])
		return
	var opening := greeting(id)
	if night >= 0.5 and NIGHT_OPENERS.has(id): opening[0] = tr(NIGHT_OPENERS[id])
	# What it is doing right now comes first; the introduction follows.
	var now_line := situation(walker)
	if not now_line.is_empty():
		opening.insert(0, now_line)
		if opening.size() > 2 and randf() < 0.5: opening.remove_at(1)
	if id == "farmer" and errands.get("hoe", "") == "carried":
		return_hoe(walker)
		return
	var choices: Array = []
	for action in actions(id):
		choices.append(action_choice(walker, str(action)))
	choices.append([tr("안녕"), Callable()])
	say(walker, opening, choices)

## What the shadow is up to, by residents.gd activity (and time of day for walks),
## one line picked at random so a second chat sounds different.
const DOING := {
	"fish":["오늘은 입질이 영 없네요… 그래도 찌 보는 맛이 있죠.","쉿, 방금 찌가 까딱했어요!","물때가 좋아요. 한 마리만 더 잡고 들어갈래요."],
	"sweep":["광장 쓸기 중이에요. 낙엽이 끝이 없네요.","쓱싹쓱싹… 오늘은 꽃잎이 많이 떨어졌어요.","빗자루 소리 들려요? 그림자 빗자루는 아주 조용하답니다."],
	"farm":["밭을 일구는 중이에요. 호미질 소리 들리죠?","오늘은 순무 고랑을 하나 더 내 볼까 해요.","흙냄새가 좋아요. 비가 오면 더 좋고요."],
	"deliver":["편지 배달 중이에요! 오늘은 우편물이 많네요.","다음 집 문 앞에 편지를 놓아야 해요. 똑똑!","가방이 가벼워질수록 발걸음도 가벼워져요."],
	"light_lamps":["가로등을 하나씩 살펴보는 중이에요. 불빛이 고르죠?","해가 지면 등불지기는 바빠져요.","이 등불은 어젯밤보다 조금 흐리네요. 닦아 줘야겠어요."],
	"write":["정자에서 시를 쓰는 중이에요. 오늘의 단어는 '그늘'.","방금 한 줄 떠올랐는데… 앗, 잊어버렸어요.","바람이 종이를 넘겨 주니 시가 절로 써져요."],
	"play":["헤헤, 연못 한 바퀴 더 뛰어야지!","술래잡기 할래? 내가 술래 안 할 거야!","나 엄청 빠르지? 그림자는 숨도 안 차!"],
	"scout":["캠프 둘레를 살피는 중이에요. 이상한 발자국은 없네요.","돌문 쪽 바람이 오늘은 조용해요.","텐트 줄을 다시 매던 참이에요."],
}
const STROLL := {
	"morning":["아침 산책이에요. 공기가 맑죠?","일찍 일어난 그림자가 길을 먼저 걷는답니다."],
	"afternoon":["오후 햇살이 좋아서 잠깐 나왔어요.","산책 중이에요. 그늘만 골라 걷는 중이죠."],
	"evening":["저녁 바람 쐬러 나왔어요.","노을 질 때 그림자가 제일 길어지거든요."],
	"night":["밤 산책이에요. 별이 잘 보여요.","이 시간엔 길이 조용해서 좋아요."],
}
const HEADING_HOME := ["이제 집에 들어가 볼게요. 쉴 시간이에요.","졸려서… 이만 들어가 잘게요.","집에 가는 길이에요. 내일 또 봐요."]
const HEADING_TO := ["%s에 가는 길이에요.","잠깐 %s에 들르려고요.","%s에서 약속이 있거든요."]

func time_band(at: float) -> String:
	if at < 5.0 or at >= 21.0: return "night"
	if at < 11.0: return "morning"
	if at < 17.0: return "afternoon"
	return "evening"

func situation(walker: Node) -> String:
	if walker.transit and not str(walker.building).is_empty():
		if walker.building == home_of(walker): return tr(HEADING_HOME[randi() % HEADING_HOME.size()])
		var title := str(door_for(walker.building).get("title", ""))
		if not title.is_empty(): return tr(HEADING_TO[randi() % HEADING_TO.size()]) % tr(title)
	var pool: Array = DOING.get(str(walker.activity), [])
	if pool.is_empty() and walker.activity == "stroll": pool = STROLL[time_band(hour)]
	return tr(pool[randi() % pool.size()]) if not pool.is_empty() else ""

## Night variants of each shadow's first line.
const NIGHT_OPENERS := {
	"postman":"밤 배달 중이에요. 쉿, 다들 자고 있거든요.",
	"fisher":"밤낚시는 찌가 안 보여서… 대신 그림자는 눈이 밝답니다.",
	"sweeper":"밤에는 낙엽 대신 별빛을 쓸어요. …농담이에요.",
	"gentleman":"달밤의 산책이란, 그림자에게는 최고의 사치죠.",
	"lamplighter":"해가 졌군요. 이 등불이 제 얼굴 대신이에요.",
	"scout":"밤의 캠프 초원은 조용해서 좋아요. 숲의 밤과는 딴판이죠.",
	"regular":"카페 문은 닫았어요. 내일 아침엔 따뜻한 커피를 내려 드릴게요.",
	"miller":"밤에는 풍차도 쉬어요. 바람만 혼자 놀다 가죠.",
	"shopkeeper":"가게는 닫았지만, 안경 너머로 별은 잘 보여요.",
	"gardener":"밤에는 향초 향이 더 짙어져요. 맡아 보세요.",
	"poet":"밤의 정자는 시가 저절로 써지는 곳이에요.",
}

func greeting(id: String) -> Array:
	match id:
		"postman": return [tr("…앗, 놀라셨죠? 이래 봬도 이 섬의 우편배달부랍니다."), tr("그림자라서 밤낮없이 다섯 섬을 다 돌아요. 다리 건너는 게 제일 즐겁죠.")]
		"fisher": return [tr("…쉿. 물고기가 놀라요."), tr("그림자는 물에 비치지 않아서 낚시에 유리하답니다.")]
		"farmer": return [tr("어이쿠, 그림자 농부요. 햇볕이 뜨거워도 저는 타지 않아요."), tr("그런데 아까부터 호미가 안 보이네… 어디 떨어뜨렸더라.")]
		"sweeper": return [tr("쓱싹쓱싹… 광장 청소는 제 담당이에요."), tr("그림자 빗자루는 소리가 안 나서 아무도 모른답니다.")]
		"gentleman": return [tr("…비는 안 오지만, 그림자에겐 햇빛이 조금 눈부셔서요."), tr("실례. 다리를 건너며 산책하던 중이었습니다.")]
		"stargazer": return [tr("밤에만 나와요. 별을 세는 게 일이거든요."), tr("그림자는 어둠 속에서 오히려 또렷해진답니다.")]
		"lamplighter": return [tr("등불지기예요. 길이 어두워지면 제가 먼저 걸어요."), tr("어두운 길이 무서우면 저를 따라와요.")]
		"gardener": return [tr("향초 냄새 좋죠? 그림자도 냄새는 맡아요."), tr("유리 온실 옆 향초밭은 제 자랑이에요.")]
		"scout": return [tr("돌문 너머 숲에서 막 돌아왔어요. 그림자라서 아무도 못 알아보더라고요."), tr("탐험을 떠날 생각이에요? 몇 가지 알려 줄까요?")]
		"regular": return [tr("카페 '빨간 지붕' 주인이에요. 뒷방에서 살면서 커피를 내려요."), tr("그림자 블렌드는 쓴맛 대신 향이 짙답니다.")]
		"miller": return [tr("풍차 방앗간지기예요. 풍차가 돌면 밀가루가 눈처럼 날려요."), tr("방앗간 위층 작은 방이 제 집이에요. 맷돌 소리가 자장가죠.")]
		"shopkeeper": return [tr("잡화점 주인이에요. 동그란 안경 너머로 다 보인답니다."), tr("가게 뒤쪽 방에서 살아요. 손님이 없으면 장부 정리를 하죠.")]
		"kid": return [tr("헤헤, 깜짝 놀랐지?"), tr("나 술래잡기 엄청 잘한다? 따라올 수 있으면 따라와 봐!")]
		"stroller": return [tr("밤 산책 중이에요. 이 시간엔 그림자들이 다 나와요."), tr("낮에는 나무 그늘 속에서 낮잠을 자요.")]
		"poet": return [tr("정자에 앉아 시를 짓던 참이에요. 그림자의 시는 행간이 길죠."), tr("한 수 들어 보실래요?")]
	return [tr("…")]

func actions(id: String) -> Array:
	match id:
		"postman": return ["letter", "rumour"]
		"fisher": return ["fish", "tips"]
		"farmer": return ["hoe", "tips"]
		"sweeper": return ["riddle", "rumour"]
		"gentleman": return ["riddle", "rumour"]
		"stargazer": return ["follow", "riddle"]
		"lamplighter": return ["follow", "rumour"]
		"gardener": return ["tips", "riddle"]
		"scout": return ["tips", "rumour"]
		"regular": return ["tips", "follow"]
		"miller": return ["tips", "riddle"]
		"shopkeeper": return ["tips", "rumour"]
		"kid": return ["follow", "riddle"]
		"stroller": return ["rumour", "follow"]
		"poet": return ["poem", "riddle"]
	return ["rumour"]

func action_choice(walker: Node, action: String) -> Array:
	var id := str(walker.spec.id)
	match action:
		"letter": return [tr("편지 배달 돕기"), func(): letter(walker)]
		"fish": return [tr("물고기 보여 주기"), func(): show_fish(walker)]
		"hoe": return [tr("호미 찾아 주기"), func(): ask_hoe(walker)]
		"riddle": return [tr("수수께끼 풀기"), func(): riddle(walker)]
		"follow": return [tr("따라가기"), func(): follow(walker)]
		"poem": return [tr("시 듣기"), func(): say(walker, [tr("햇살이 길을 그리면, 나는 그 옆에 가만히 눕는다."), tr("다섯 섬이 잠들 무렵, 나는 비로소 눈을 뜬다."), tr("…어때요? 그림자의 시라서 조금 어둡죠?")])]
		"tips":
			var label: String = {"fisher":tr("낚시 비결 듣기"),"farmer":tr("농사 비결 듣기"),"gardener":tr("정원 비결 듣기"),"scout":tr("탐험 요령 듣기"),"regular":tr("카페 이야기 듣기"),"miller":tr("방앗간 이야기 듣기"),"shopkeeper":tr("가게 이야기 듣기")}.get(id, tr("이야기 듣기"))
			return [label, func(): say(walker, tips(id))]
	return [tr("소문 듣기"), func(): rumour(walker)]

func tips(id: String) -> Array:
	match id:
		"fisher": return [tr("미끼를 달고 찌를 던진 뒤, 금빛 입질이 오면 망설이지 말고 당겨요."), tr("바다 쪽 등대 부두에서는 은빛 도미가 더 잘 잡혀요."), tr("마을 연못 낚시터는 물결빛 광장 남쪽, 나무 부두 끝이에요.")]
		"farmer": return [tr("햇살 텃밭은 바로 이 풍차 들판에 있어요. 씨앗을 심고 물을 한 번만 주면 돼요."), tr("마을을 떠나도, 게임을 꺼도 작물은 계속 자라요. 순무는 금방, 호박은 조금 더 걸려요."), tr("씨앗 노점 배달 게시판에 순무 두 개와 강농어 한 마리를 가져가면 식탁 배달을 할 수 있어요.")]
		"gardener": return [tr("정원 향초밭에서 향초를 거둘 수 있어요. 다시 자랄 때까지는 조금 기다려야 해요."), tr("길가 덤불을 뒤져 보면 향초가 숨어 있을 때도 있어요."), tr("둥근 나무를 흔들면 사과가 떨어져요. 뾰족한 나무는… 잎만 우수수.")]
		"scout": return [tr("캠프 초원의 돌문을 지나면 일곱 밤의 숲이 시작돼요."), tr("첫날엔 목재와 돌을 모아 도끼부터 만드세요. 밤에는 모닥불 곁을 지키고요."), tr("붉은 원이 보이면 바로 피해요. 일곱 밤을 버티면 새 물건을 만들 별씨를 받아요.")]
		"miller": return [tr("방앗간은 아침 일곱 시쯤 맷돌을 돌리기 시작해요. 저녁엔 문을 닫고요."), tr("바람이 센 날엔 풍차가 신나서 가루가 문밖까지 날려요."), tr("햇살 텃밭 바로 위가 방앗간이에요. 농부 그림자가 자주 놀러 와요.")]
		"shopkeeper": return [tr("잡화점은 아침 아홉 시쯤 열고 저녁 일곱 시쯤 닫아요."), tr("불이 꺼져 있으면 문을 두드려도 소용없어요. 다들 자거나 나갔거든요."), tr("카페 주인 그림자가 저녁마다 커피 한 잔 하러 와요. 제가 가는 날도 있고요.")]
		"regular": return [tr("카페는 아침 여덟 시쯤 열어요. 창문에 불이 켜져 있으면 들어와요."), tr("풍차 들판 서쪽 사과 과수원 상자에서 사과를 얻을 수 있어요."), tr("둥근 나무를 살살 흔들어도 사과가 떨어지죠. 저는 그 소리가 좋아요."), tr("과수원 오솔길 끝은 조용해서, 커피 생각날 때 가끔 가요. 같이 가 볼래요?")]
	return [tr("…")]

func rumour(walker: Node) -> void:
	var id := str(walker.spec.id)
	var pool: Array = []
	match id:
		"postman": pool = [tr("다리는 모두 네 개예요. 등대섬으로 가는 긴 다리에서 보는 노을이 제일이죠."), tr("카페 '빨간 지붕' 앞으로 편지가 제일 많이 와요. 단골이 많거든요."), tr("가로등은 가까이 가서 켜고 끌 수 있어요. 저는 밤마다 하나씩 살펴요.")]
		"sweeper": pool = [tr("별씨 공방에서는 숲에서 받은 별씨로 새 물건을 만들 수 있대요."), tr("재단사 소라에게 가면 옷 색과 모자를 바꿀 수 있어요."), tr("연못 부두 끝에 서 있으면 꼬마 그림자가 놀러 와요. 장난꾸러기예요.")]
		"gentleman": pool = [tr("돌문 너머 숲은 밤이 길어요. 모닥불 곁을 떠나지 마세요."), tr("정원 언덕 정자에는 시를 쓰는 그림자가 자주 앉아 있죠."), tr("다섯 섬은 모두 다리로 이어져 있어요. 어디든 걸어서 갈 수 있답니다.")]
		"lamplighter": pool = [tr("밤이 되면 가로등이 길을 따라 켜져요. 그림자들은 그 불빛 사이로 다니죠."), tr("등대 종을 울리면 마을 전체에 소리가 퍼져요."), tr("등대섬으로 가는 긴 다리는 밤에 별이 물에 비쳐서 예뻐요.")]
		"scout": pool = [tr("캠프 초원의 텐트를 들여다보면 침낭과 등불이 가지런히 놓여 있어요."), tr("모루 씨는 숲에서 밤을 버티는 법을 제일 잘 알아요."), tr("탐험 지도는 길잡이 나루가 펼쳐 준대요.")]
		"stroller": pool = [tr("별지기 그림자는 밤에만 천문대 근처에 나타나요."), tr("꼬마 그림자는 밤이 되면 자러 가요. 낮에 광장에서 만나 봐요."), tr("그림자들이 왜 여기 사냐고요? …섬이 너무 밝아서, 쉴 그늘이 필요했대요.")]
		_: pool = [tr("천문대 전망대에 오르면 다섯 섬과 다리가 한눈에 보여요."), tr("목조 주택 주인은 아직 한 번도 못 봤어요. 혹시 그림자일까요?")]
	var turn := int(walker.get_meta("rumour_turn", 0))
	walker.set_meta("rumour_turn", turn+1)
	say(walker, [pool[turn % pool.size()], tr("…이건 비밀이에요. 그림자끼리만 아는 이야기.")])

## ------------------------------------------------------------------ riddles

const RIDDLES := {
	"sweeper":["낮에는 늘 발밑에 붙어 다니다가, 해가 지면 사라지는 나는 누구일까요?",["바람","그림자","고양이"],1],
	"gentleman":["물 위를 걷게 해 주지만 발은 젖지 않게 해 주는 것은? 이 섬에만 네 개가 있어요.",["다리","배","구름"],0],
	"stargazer":["밤마다 바다에 길을 그려 주지만, 정작 자신은 한 발짝도 움직이지 않는 것은?",["달","가로등","등대"],2],
	"gardener":["물 위에 동동 떠서 기다리다가, '쏙' 들어가면 모두가 기뻐하는 것은?",["오리","낚시찌","나뭇잎"],1],
	"kid":["다리가 네 개인데 걷지 못하고, 앉으면 편한 것은?",["의자","강아지","탁자"],0],
	"poet":["보이지 않지만 풍차를 돌리고 나뭇잎을 흔드는 것은?",["물결","그림자","바람"],2],
	"miller":["하루 종일 돌고 도는데 제자리에 있고, 바람이 불면 더 신나는 것은?",["풍차","팽이","시계"],0],
}

func riddle(walker: Node) -> void:
	var entry: Array = RIDDLES.get(str(walker.spec.id), RIDDLES.sweeper)
	var choices: Array = []
	var answers: Array = entry[1]
	for i in answers.size():
		var correct: bool = i == int(entry[2])
		choices.append([tr(answers[i]), func(): answer(walker, correct)])
	say(walker, [tr("수수께끼 하나 낼게요."), tr(entry[0])], choices)

func answer(walker: Node, correct: bool) -> void:
	if correct:
		walker.smile(6.0)
		walker.pop("!", 1.6)
		effect("reward")
		toast(tr("수수께끼를 풀었어요! 그림자가 하얗게 웃어요."))
		say(walker, [tr("정답! …역시 눈썰미가 좋네요."), tr("그림자는 칭찬할 때 이렇게 웃는답니다. 히히.")])
	else:
		walker.pop("…", 1.4)
		say(walker, [tr("땡! 아쉽지만 아니에요."), tr("다음에 다시 물어봐 줘요. 그림자는 기다리는 걸 잘하거든요.")])

## ------------------------------------------------------------------ follow me

func follow(walker: Node) -> void:
	var spot := pick_spot(walker)
	if spot < 0:
		say(walker, [tr("음… 오늘은 보여 줄 곳이 떠오르지 않네요.")])
		return
	var route: Array[int] = paths.route(walker.at_node, spot)
	if route.is_empty():
		say(walker, [tr("음… 오늘은 보여 줄 곳이 떠오르지 않네요.")])
		return
	if is_instance_valid(leader) and leader != walker: leader.cancel_lead()
	leader = walker
	lead_spot = spot
	lead_lost = 0.0
	var go := func() -> void:
		if is_instance_valid(walker) and walker == leader:
			walker.end_talk()
			walker.begin_lead(route)
			walker.pop("♪", 1.4)
	say(walker, [tr("좋아요, 따라와요. 너무 멀어지면 기다릴게요."), tr("…놓치지 마세요. 그림자는 그늘에 잘 섞이거든요.")], [[tr("따라간다"), go]])

## Where each shadow likes to take the walker; otherwise the nearest quiet spot
## that is at least a short walk away.
func pick_spot(walker: Node) -> int:
	var wanted: String = {"kid":"pond_pier","regular":"orchard","lamplighter":"lh_pier","poet":"gazebo"}.get(str(walker.spec.id), "")
	if str(walker.spec.id) == "stargazer":
		for node in paths.faces:
			if paths.faces[node].distance_to(Vector2(30, -42.6)) < 0.5: return node
	var best := -1
	var best_length := INF
	for node in paths.spot_names:
		var route: Array[int] = paths.route(walker.at_node, node)
		if route.is_empty(): continue
		var length: float = paths.route_length(route)
		if paths.spot_names[node] == wanted: return node
		if length > 10.0 and length < best_length:
			best_length = length
			best = node
	return best

func lead_arrived(walker: Node) -> void:
	if walker != leader: return
	leader = null
	var name := spot_title(lead_spot)
	walker.smile(6.0)
	walker.pop("♪", 2.0)
	effect("reward")
	toast(tr("숨은 장소를 찾았어요 · %s") % name)
	float_text(tr("여기가 제 비밀 장소예요"), walker.global_position, Color("d9d2ff"))

func spot_title(node: int) -> String:
	var key: String = paths.spot_names.get(node, "")
	match key:
		"pond_pier": return tr("연못 부두 끝")
		"lh_pier": return tr("등대 부두 끝")
		"orchard": return tr("과수원 오솔길")
		"gazebo": return tr("정원 언덕 정자")
	if paths.faces.has(node): return tr("별빛 천문대 앞")
	return tr("그림자의 쉼터")

## ------------------------------------------------------------------ favours

func letter(walker: Node) -> void:
	if done_today.get("postman", "") == today():
		say(walker, [tr("오늘 편지는 벌써 다 배달했어요. 덕분이에요!"), tr("내일 또 부탁해도 될까요? …히히.")])
		return
	var target := letter_target()
	if target.is_empty():
		say(walker, [tr("오늘은 배달할 편지가 없네요. 그림자 우체국도 쉬는 날이 있어요.")])
		return
	var where: String = Minimap.island_name(target.at)
	if errands.get("letter", "") == target.cast:
		say(walker, [tr("%s에게 가는 편지, 잘 부탁해요.") % target.title, tr("%s 쪽에 있을 거예요.") % where])
		return
	errands["letter"] = target.cast
	effect("click")
	say(walker, [tr("이 편지, %s에게 전해 줄 수 있어요?") % target.title, tr("제가 직접 가면 다들 깜짝 놀라서요. %s 쪽에 있을 거예요.") % where],
		[[tr("맡겨 줘요"), func(): toast(tr("편지를 받았어요 · %s에게 전해 주세요") % target.title)]])

## Today's addressee among the named villagers.
func letter_target() -> Dictionary:
	var npcs: Array = []
	for npc in (app.get("npcs") if app.get("npcs") != null else []):
		if is_instance_valid(npc) and npc.visible: npcs.append(npc)
	if npcs.is_empty(): return {}
	var npc: Node3D = npcs[Time.get_date_dict_from_system().day % npcs.size()]
	var title := str(npc.get_meta("title", npc.name)).split(" · ")[0]
	return {"cast":str(npc.get_meta("cast", npc.name)), "title":title, "node":npc, "at":Vector2(npc.position.x, npc.position.z)}

func show_fish(walker: Node) -> void:
	var life = app.get("life")
	var bag: Dictionary = {}
	if is_instance_valid(life) and life.get("state") is Dictionary: bag = life.state.get("bag", {})
	var catch := ""
	for kind in ["silverfish", "perch"]:
		if int(bag.get(kind, 0)) > 0:
			catch = kind
			break
	if catch.is_empty():
		say(walker, [tr("아직 물고기가 없군요."), tr("등대 부두나 마을 연못에서 찌를 던져 봐요. 금빛 입질이 오면 바로!")])
		return
	var fish_name := tr("은빛 도미") if catch == "silverfish" else tr("강농어")
	walker.smile(6.0)
	effect("reward")
	if done_today.get("fisher", "") != today():
		mark_done("fisher")
		toast(tr("낚시꾼 그림자가 엄지를 치켜세웠어요"))
	say(walker, [tr("오오, %s! 비늘이 반짝반짝하네요.") % fish_name, tr("좋은 솜씨예요. 그림자 낚시회에 들어올래요? …농담이에요.")])

func ask_hoe(walker: Node) -> void:
	if done_today.get("farmer", "") == today():
		say(walker, [tr("호미 덕분에 오늘 밭일은 끝났어요. 고마워요!")])
		return
	if errands.get("hoe", "") == "dropped" and is_instance_valid(dropped):
		say(walker, [tr("이 근처 길가 어딘가에 떨어뜨린 것 같아요."), tr("반짝이는 게 보이면 그거예요!")])
		return
	var spot := hoe_spot(walker)
	drop_hoe(spot)
	errands["hoe"] = "dropped"
	say(walker, [tr("정말요? 고마워요!"), tr("이 근처 길가 어딘가에 떨어뜨린 것 같아요. 반짝이는 게 보이면 그거예요!")],
		[[tr("찾아볼게요"), func(): toast(tr("떨어진 호미를 찾아보세요 · %s 길가") % Minimap.island_name(Vector2(spot.x, spot.z)))]])

## A road-side point 9-22 m (along the roads) from the farmer, on his island.
func hoe_spot(walker: Node) -> Vector3:
	var options: Array[int] = []
	for node in paths.points.size():
		if paths.kinds[node] != "road" or paths.links[node].is_empty(): continue
		# Not at a bridge head: the banks there drop to the shore.
		if paths.links[node].any(func(next: int) -> bool: return paths.kinds[next] == "bridge"): continue
		var d: float = paths.points[node].distance_to(walker.xz())
		if d > 9.0 and d < 22.0 and paths.points[node].distance_to(walker.spec.home) < 20.0: options.append(node)
	var node: int = options[randi() % options.size()] if not options.is_empty() else walker.at_node
	var next: int = paths.links[node][0]
	var along: Vector2 = paths.points[next]-paths.points[node]
	var side := along.orthogonal().normalized()*0.9 if along.length() > 0.1 else Vector2.ZERO
	var p: Vector2 = paths.points[node]+along*0.3+side
	var y := Town.height_at(p.x, p.y)
	if y < Town.SHORE_MIN_Y+0.4:
		p = paths.points[node]
		y = Town.height_at(p.x, p.y)
	return Vector3(p.x, y, p.y)

func drop_hoe(at: Vector3) -> void:
	if is_instance_valid(dropped): dropped.queue_free()
	dropped = Node3D.new()
	dropped.name = "DroppedHoe"
	add_child(dropped)
	dropped.position = at+Vector3(0, 0.05, 0)
	var dark := ShaderMaterial.new()
	dark.shader = Figure.SILHOUETTE
	var stick := MeshInstance3D.new()
	var shaft := CylinderMesh.new()
	shaft.top_radius = 0.02; shaft.bottom_radius = 0.02; shaft.height = 1.1
	stick.mesh = shaft
	stick.rotation_degrees = Vector3(0, 30, 86)
	stick.position.y = 0.04
	stick.material_override = dark
	dropped.add_child(stick)
	var blade := MeshInstance3D.new()
	var plate := BoxMesh.new()
	plate.size = Vector3(0.14, 0.03, 0.18)
	blade.mesh = plate
	blade.position = Vector3(0.47, 0.06, -0.27)
	blade.material_override = dark
	dropped.add_child(blade)
	var sparkle := Label3D.new()
	sparkle.text = "✦"
	sparkle.font_size = 64
	sparkle.pixel_size = 0.006
	sparkle.modulate = Color("fff2b8")
	sparkle.outline_size = 0
	sparkle.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	sparkle.position.y = 0.55
	dropped.add_child(sparkle)
	var twinkle := sparkle.create_tween().set_loops()
	twinkle.tween_property(sparkle, "modulate:a", 0.25, 0.6)
	twinkle.tween_property(sparkle, "modulate:a", 1.0, 0.6)

func pick_up_hoe() -> void:
	if not is_instance_valid(dropped): return
	float_text(tr("호미를 주웠어요"), dropped.position, Color("f3e1af"))
	dropped.queue_free()
	dropped = null
	errands["hoe"] = "carried"
	effect("gather")
	toast(tr("호미를 주웠어요 · 농부 그림자에게 돌려주세요"))
	var player := player_node()
	if player and player.has_method("react"): player.react("gather")

func return_hoe(walker: Node) -> void:
	errands.erase("hoe")
	mark_done("farmer")
	walker.smile(8.0)
	walker.pop("!", 1.6)
	effect("reward")
	toast(tr("농부 그림자가 하얗게 활짝 웃어요"))
	say(walker, [tr("내 호미! 정말 고마워요."), tr("이걸로 오늘 순무 한 고랑 더 일구겠네요. 그림자 농사도 손이 많이 가거든요.")])

func update_errands(delta: float) -> void:
	var here := player_xz()
	if errands.has("letter"):
		var target := letter_target()
		if not target.is_empty() and target.cast == errands.letter and here.distance_to(target.at) < 3.0:
			errands.erase("letter")
			mark_done("postman")
			effect("reward")
			toast(tr("%s에게 편지를 전했어요 · \"그림자 우체부가 보냈구나!\"") % target.title)
			float_text(tr("편지 고마워요!"), target.node.global_position, Color("f5e5b7"))
	if is_instance_valid(leader):
		if here.distance_to(leader.xz()) > 25.0: lead_lost += delta
		else: lead_lost = 0.0
		if lead_lost > 20.0:
			leader.cancel_lead()
			leader.pop("…", 2.0)
			leader = null
			toast(tr("그림자가 한참 기다리다 돌아갔어요"))

func today() -> String:
	return Time.get_date_string_from_system()

## Progress lives in the settings file's [shadow_folk] section, which follows the account (cloud_prefs.gd).
func mark_done(id: String) -> void:
	done_today[id] = today()
	if not persist: return
	var file := ConfigFile.new()
	file.load(I18n.settings_path())
	for key in done_today: file.set_value("shadow_folk", key, done_today[key])
	file.save(I18n.settings_path())

func load_progress() -> void:
	done_today.clear()
	if not persist: return
	var file := ConfigFile.new()
	if file.load(I18n.settings_path()) == OK and file.has_section("shadow_folk"):
		for key in file.get_section_keys("shadow_folk"): done_today[key] = str(file.get_value("shadow_folk", key, ""))
	# Older builds kept it in its own file on this PC.
	var legacy := ConfigFile.new()
	if legacy.load(SAVE_PATH) == OK and legacy.has_section("done"):
		for key in legacy.get_section_keys("done"):
			if not done_today.has(key): done_today[key] = str(legacy.get_value("done", key, ""))

## Soft footsteps for the one shadow closest to the walker.
func footstep(walker: Node, speed: float) -> void:
	step_turn += 1
	var audio = app.get("world_audio") if is_instance_valid(app) else null
	if not is_instance_valid(audio) or not audio.has_method("footstep"): return
	var surface := "stone" if Roads.on_road(walker.xz()) else "grass"
	if paths.kinds[walker.at_node] == "bridge" or paths.kinds[walker.target_node] == "bridge": surface = "wood"
	audio.footstep(surface, speed*0.6)
