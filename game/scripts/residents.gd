extends RefCounted
## Who lives where, and where everyone is at any hour. Pure data plus seeded
## daily plans, so the outdoor walkers, the interiors, the window lights and the
## door locks all agree without talking to each other. Every resident has a home
## building and their own bed in it; shop and special-building owners live in a
## back room of their workplace. Plans change a little every real day (seeded by
## resident and date), and night owls keep night hours.
##
## Places are building ids from TownLayout.DOORS ("01_cafe", ...) or "outside".
## Spots inside a building are furniture words the interiors map to real pieces:
##   bed table stove armchair sofa fireplace desk bookshelf piano sink window
##   counter telescope millstone garden_bed lens workbench
## Outside spots are keys the walkers map to positions (see OUTSIDE_SPOTS).

## kind: "cast" (named villagers, res://assets/npc/<id>.glb) or "shadow" (silhouette folk).
## sleep: "day" (sleeps at night), "early" (dawn fishers), "evening" (late lamplighter), "night".
## work: [{place, spot, activity, from, to}], local hours; place "outside" uses an outside spot.
const RESIDENTS := [
	{"id":"naru","kind":"cast","title":"나루 · 길잡이","home":"02_timber_house","sleep":"day",
		"work":[{"place":"outside","spot":"gate","activity":"guide","from":8.0,"to":18.0}]},
	{"id":"sora","kind":"cast","title":"소라 · 재단사","home":"11_purple_house","sleep":"day",
		"work":[{"place":"outside","spot":"square","activity":"tailor","from":9.0,"to":18.0}]},
	{"id":"moru","kind":"cast","title":"모루 · 야영 전문가","home":"16_blue_cottage","sleep":"day",
		"work":[{"place":"outside","spot":"camp","activity":"camp","from":8.0,"to":17.0}]},
	{"id":"haeru","kind":"cast","title":"해루 · 낚시꾼","home":"17_lighthouse","sleep":"early",
		"work":[{"place":"outside","spot":"lighthouse_pier","activity":"fish","from":5.5,"to":10.5},
			{"place":"outside","spot":"lighthouse_pier","activity":"fish","from":15.5,"to":19.0}]},
	{"id":"postman","kind":"shadow","home":"12_blue_house","sleep":"day",
		"work":[{"place":"outside","spot":"rounds","activity":"deliver","from":8.0,"to":16.0}]},
	{"id":"sweeper","kind":"shadow","home":"12_blue_house","sleep":"day",
		"work":[{"place":"outside","spot":"square","activity":"sweep","from":6.5,"to":11.0}]},
	{"id":"fisher","kind":"shadow","home":"06_orange_cottage","sleep":"early",
		"work":[{"place":"outside","spot":"lighthouse_pier","activity":"fish","from":5.0,"to":10.0},
			{"place":"outside","spot":"pond_pier","activity":"fish","from":16.0,"to":19.0}]},
	{"id":"kid","kind":"shadow","home":"06_orange_cottage","sleep":"day","bedtime":20.5,
		"work":[{"place":"outside","spot":"pond","activity":"play","from":9.0,"to":17.0}]},
	{"id":"farmer","kind":"shadow","home":"03_teal_cottage","sleep":"early",
		"work":[{"place":"03_teal_cottage","spot":"counter","activity":"shopkeep","from":8.5,"to":12.5},
			{"place":"outside","spot":"farm","activity":"farm","from":13.5,"to":17.5}]},
	{"id":"regular","kind":"shadow","home":"01_cafe","sleep":"day",
		"work":[{"place":"01_cafe","spot":"counter","activity":"barista","from":8.0,"to":20.0}]},
	{"id":"miller","kind":"shadow","home":"04_windmill","sleep":"early",
		"work":[{"place":"04_windmill","spot":"millstone","activity":"mill","from":7.0,"to":17.0}]},
	{"id":"stargazer","kind":"shadow","home":"05_observatory","sleep":"night",
		"work":[{"place":"05_observatory","spot":"telescope","activity":"stargaze","from":19.5,"to":28.0}]},
	{"id":"gardener","kind":"shadow","home":"07_greenhouse","sleep":"day",
		"work":[{"place":"07_greenhouse","spot":"garden_bed","activity":"tend","from":8.0,"to":17.0}]},
	{"id":"shopkeeper","kind":"shadow","home":"13_shop","sleep":"day",
		"work":[{"place":"13_shop","spot":"counter","activity":"shopkeep","from":9.0,"to":19.0}]},
	{"id":"scout","kind":"shadow","home":"02_timber_house","sleep":"day",
		"work":[{"place":"outside","spot":"camp","activity":"scout","from":9.0,"to":18.0}]},
	{"id":"lamplighter","kind":"shadow","home":"16_blue_cottage","sleep":"evening",
		"work":[{"place":"outside","spot":"lamps","activity":"light_lamps","from":17.0,"to":24.0}]},
	{"id":"gentleman","kind":"shadow","home":"11_purple_house","sleep":"day","work":[]},
	{"id":"poet","kind":"shadow","home":"11_purple_house","sleep":"day",
		"work":[{"place":"outside","spot":"gazebo","activity":"write","from":10.5,"to":16.5}]},
	{"id":"stroller","kind":"shadow","home":"17_lighthouse","sleep":"night",
		"work":[{"place":"outside","spot":"rounds","activity":"stroll","from":21.0,"to":28.5}]},
]

## Rough village positions for outside spots (x, z). Walkers wander near them.
const OUTSIDE_SPOTS := {
	"gate":Vector2(51,37),"square":Vector2(-30,35),"camp":Vector2(57,38),
	"lighthouse_pier":Vector2(1.5,78.5),"pond_pier":Vector2(-44,33),"pond":Vector2(-29,42),
	"farm":Vector2(-18.4,-31.5),"gazebo":Vector2(63,-25),"orchard":Vector2(-46,-33),
	"bridges":Vector2(24,30.5),"lamps":Vector2(-25.5,57.5),"rounds":Vector2(-33,37),
	"bench":Vector2(-24,36),"picnic":Vector2(65,29),"stage":Vector2(37,26),
}

## Opening hours for buildings people may visit while the owner is at work.
## A shop is open only while its owner is actually working at the counter.
const SHOPS := {"01_cafe":"regular","03_teal_cottage":"farmer","04_windmill":"miller",
	"05_observatory":"stargazer","07_greenhouse":"gardener","13_shop":"shopkeeper"}
## The player's own rooms: always open, nobody else lives there.
const PLAYER_ROOMS := ["home","workshop","09_town_hall","10_red_house"]

const HOME_ACTIVITIES := ["cook","eat","read","tidy","wash","fireplace","piano","chat"]
const ACTIVITY_SPOT := {"cook":"stove","eat":"table","read":"armchair","tidy":"bookshelf","wash":"sink",
	"fireplace":"fireplace","piano":"piano","chat":"sofa","sleep":"bed","shopkeep":"counter",
	"barista":"counter","tend":"garden_bed","mill":"millstone","stargaze":"telescope","visit":"table",
	"coffee":"table","browse":"counter","relax":"armchair"}
## Outside leisure spots; "stroll" (not in OUTSIDE_SPOTS) means wander the roads.
const LEISURE_OUTSIDE := ["stroll","bench","pond","orchard","gazebo","bridges","stage","picnic"]

static func resident(id: String) -> Dictionary:
	for entry in RESIDENTS:
		if entry.id == id: return entry
	return {}

## Ids of everyone whose bed is in this building.
static func residents_of(building: String) -> Array[String]:
	var out: Array[String] = []
	for entry in RESIDENTS:
		if entry.home == building: out.append(entry.id)
	return out

## Local clock: {"hour": 0..24 float, "day": days since 1970-01-01 (local date)}.
static func clock() -> Dictionary:
	var now := Time.get_datetime_dict_from_system()
	var day := int(Time.get_unix_time_from_datetime_dict({"year":now.year,"month":now.month,"day":now.day})/86400)
	return {"hour":now.hour+now.minute/60.0+now.second/3600.0,"day":day}

static func _rng(id: String, day: int) -> RandomNumberGenerator:
	var rng := RandomNumberGenerator.new()
	rng.seed = hash("%s:%d" % [id, day])
	return rng

## Wake time on a given day (local hours from that day's midnight).
static func wake_time(id: String, day: int) -> float:
	var rng := _rng(id, day)
	match str(resident(id).get("sleep","day")):
		"early": return rng.randf_range(4.3, 5.2)
		"evening": return rng.randf_range(9.0, 10.5)
		"night": return rng.randf_range(12.5, 14.0)
	return rng.randf_range(5.8, 7.6)

static func _bedtime(entry: Dictionary, rng: RandomNumberGenerator) -> float:
	if entry.has("bedtime"): return float(entry.bedtime)+rng.randf_range(-0.3, 0.4)
	match str(entry.get("sleep","day")):
		"early": return rng.randf_range(20.8, 21.8)
		"evening": return rng.randf_range(24.8, 26.0)
		"night": return rng.randf_range(28.6, 29.6)
	return rng.randf_range(21.8, 23.6)

## One day's plan from waking up until waking up again, as blocks
## {from, to, place, spot, activity, asleep} in hours from that day's midnight
## (so a block can run past 24). Work blocks come from RESIDENTS; the gaps are
## filled with seeded home time, meals and leisure.
## Plans are pure functions of (id, day), so they are built once and cached.
static var _plans := {}
static func plan(id: String, day: int) -> Array[Dictionary]:
	var key := "%s:%d" % [id, day]
	if not _plans.has(key):
		if _plans.size() > 400: _plans.clear()
		_plans[key] = _build_plan(id, day)
	return _plans[key]

static func _build_plan(id: String, day: int) -> Array[Dictionary]:
	var entry := resident(id)
	var blocks: Array[Dictionary] = []
	if entry.is_empty(): return blocks
	var rng := _rng(id, day*7+3)
	var wake := wake_time(id, day)
	var bed := _bedtime(entry, rng)
	var next_wake := wake_time(id, day+1)+24.0
	var home: String = entry.home
	var shifts: Array = []
	for shift in entry.work:
		# Work hours drift a little day to day, and some days start late.
		var start: float = float(shift.from)+rng.randf_range(-0.25, 0.35)
		var stop: float = float(shift.to)+rng.randf_range(-0.4, 0.3)
		# A shift may not start before waking or run into bedtime.
		start = maxf(start, wake+0.4)
		stop = minf(stop, bed-0.1)
		if stop > start+0.25: shifts.append({"place":shift.place,"spot":shift.spot,"activity":shift.activity,"from":start,"to":stop})
	shifts.sort_custom(func(a, b): return a.from < b.from)
	var t := wake
	# Morning at home first.
	var morning: float = minf(wake+rng.randf_range(0.6, 1.4), shifts[0].from if not shifts.is_empty() else bed)
	_add(blocks, t, morning, home, "", HOME_ACTIVITIES[rng.randi_range(0, 2)])
	t = morning
	for shift in shifts:
		if shift.from > t: _fill_free(blocks, entry, t, shift.from, rng)
		_add(blocks, maxf(t, shift.from), shift.to, shift.place, shift.spot, shift.activity)
		t = maxf(t, shift.to)
	if bed > t: _fill_free(blocks, entry, t, bed, rng)
	_add(blocks, maxf(t, bed), next_wake, home, "bed", "sleep")
	return blocks

## Free time: meals, a visit to the café or a friend, a stroll, or staying in.
static func _fill_free(blocks: Array[Dictionary], entry: Dictionary, from: float, to: float, rng: RandomNumberGenerator) -> void:
	var t := from
	while t < to-0.001:
		var length: float = minf(to-t, rng.randf_range(0.8, 2.2))
		# Never leave a sliver of time before the next fixed block.
		if to-(t+length) < 0.3: length = to-t
		var hour := fmod(t, 24.0)
		var roll := rng.randf()
		var meal: bool = (hour > 11.5 and hour < 13.5) or (hour > 17.5 and hour < 19.5)
		var night: bool = hour >= 21.0 or hour < 5.0
		var night_owl: bool = str(entry.get("sleep","")) in ["night","evening"]
		if meal and roll < 0.35 and _owner_working("01_cafe", t):
			_add(blocks, t, t+length, "01_cafe", "table", "coffee")
		elif meal and roll < 0.75:
			_add(blocks, t, t+length, entry.home, "", "eat")
		elif (not night or night_owl) and roll < 0.55:
			_add(blocks, t, t+length, "outside", LEISURE_OUTSIDE[rng.randi_range(0, LEISURE_OUTSIDE.size()-1)], "stroll")
		elif not night and roll < 0.68:
			# Pop into a shop that is open, or call on a neighbour who is up.
			var shop: String = SHOPS.keys()[rng.randi_range(0, SHOPS.size()-1)]
			if _owner_working(shop, t): _add(blocks, t, t+length, shop, "", "browse")
			else: _add(blocks, t, t+length, entry.home, "", HOME_ACTIVITIES[rng.randi_range(0, HOME_ACTIVITIES.size()-1)])
		elif not night and roll < 0.78:
			var friend: Dictionary = RESIDENTS[rng.randi_range(0, RESIDENTS.size()-1)]
			if friend.home != entry.home: _add(blocks, t, t+length, friend.home, "sofa", "visit")
			else: _add(blocks, t, t+length, entry.home, "", "chat")
		else:
			_add(blocks, t, t+length, entry.home, "", HOME_ACTIVITIES[rng.randi_range(0, HOME_ACTIVITIES.size()-1)])
		t += length

static func _add(blocks: Array[Dictionary], from: float, to: float, place: String, spot: String, activity: String) -> void:
	if to <= from+0.01: return
	if spot.is_empty() and place != "outside": spot = str(ACTIVITY_SPOT.get(activity, "table"))
	# Merge with the previous block when nothing changes.
	if not blocks.is_empty():
		var last: Dictionary = blocks[-1]
		if last.place == place and last.activity == activity and last.spot == spot and absf(last.to-from) < 0.02:
			last.to = to
			return
	blocks.append({"from":from,"to":to,"place":place,"spot":spot,"activity":activity,"asleep":activity == "sleep"})

## The owner's fixed shift only (no randomness), used while building other plans
## so a visit never points at a closed shop.
static func _owner_working(building: String, at: float) -> bool:
	var owner := resident(str(SHOPS.get(building, "")))
	if owner.is_empty(): return false
	var hour := fmod(at, 24.0)
	for shift in owner.work:
		if shift.place != building: continue
		var from: float = float(shift.from)
		var to: float = float(shift.to)
		if (hour >= from and hour < to) or (hour+24.0 >= from and hour+24.0 < to): return true
	return false

## Where a resident is right now: {place, spot, activity, asleep, from, to}.
## hour/day default to the local clock; pass the daylight override hour to test.
static func now(id: String, hour := -1.0, day := -1) -> Dictionary:
	var c := clock()
	if hour < 0.0: hour = c.hour
	if day < 0: day = c.day
	for block in plan(id, day):
		if hour >= block.from and hour < block.to: return block.merged({"id":id})
	for block in plan(id, day-1):
		if hour+24.0 >= block.from and hour+24.0 < block.to: return block.merged({"id":id})
	return {"id":id,"place":resident(id).get("home",""),"spot":"bed","activity":"sleep","asleep":true,"from":hour,"to":hour+1.0}

## Everyone inside a building at this hour (residents and visitors).
static func occupants(building: String, hour := -1.0, day := -1) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for entry in RESIDENTS:
		var state := now(entry.id, hour, day)
		if state.place == building: out.append(state)
	return out

## Who is out and about: [{id, spot, activity}] for the outdoor walkers.
static func outdoors(hour := -1.0, day := -1) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for entry in RESIDENTS:
		var state := now(entry.id, hour, day)
		if state.place == "outside": out.append(state)
	return out

## Lights and the door, as seen from outside:
## {lights_on, open (a shop at work), enterable, reason ("", "asleep", "away", "closed"),
##  message (Korean, already tr()'d), occupants}
## Cached per building and game minute: door prompts and window lights ask every
## frame / second, the answer only changes at block boundaries. Treat it as read-only.
static var _states := {}
static func building_state(building: String, hour := -1.0, day := -1) -> Dictionary:
	if hour < 0.0 or day < 0:
		var c := clock()
		if hour < 0.0: hour = c.hour
		if day < 0: day = c.day
	var key := "%s:%d:%d" % [building, day, int(hour*60.0)]
	if _states.has(key): return _states[key]
	if _states.size() > 600: _states.clear()
	var state := _building_state(building, hour, day)
	_states[key] = state
	return state

static func _building_state(building: String, hour: float, day: int) -> Dictionary:
	var state := {"lights_on":true,"open":false,"enterable":true,"reason":"","message":"","occupants":[]}
	if building in PLAYER_ROOMS: return state
	var inside := occupants(building, hour, day)
	state.occupants = inside
	var awake := inside.filter(func(o): return not o.asleep)
	var owner := str(SHOPS.get(building, ""))
	if not owner.is_empty():
		for o in inside:
			if o.id == owner and o.activity in ["shopkeep","barista","mill","stargaze","tend"]: state.open = true
	state.lights_on = not awake.is_empty()
	state.enterable = state.lights_on
	if state.enterable: return state
	if not inside.is_empty():
		state.reason = "asleep"
		state.message = TranslationServer.translate("불이 꺼져 있어요. 다들 곤히 자고 있나 봐요.")
	elif not owner.is_empty():
		state.reason = "closed"
		state.message = TranslationServer.translate("지금은 문을 닫았어요. 주인이 자리를 비웠나 봐요.")
	else:
		state.reason = "away"
		state.message = TranslationServer.translate("아무도 없는 것 같아요. 문이 잠겨 있어요.")
	return state
