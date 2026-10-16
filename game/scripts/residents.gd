extends RefCounted
## Who lives where, and where everyone is at any hour. Pure data plus seeded
## daily plans, so the outdoor walkers, the interiors, the window lights and the
## door locks all agree without talking to each other. Every resident has a home
## building and their own bed in it. The café, seed-shop and mill owners share
## 풍차 언덕 하숙집 (18_meadow_house); the other shop and special-building owners
## still live in a back room of their workplace (TODO MAP 40: stargazer, gardener;
## the shopkeeper 단비 moves to her plot house with the story, plots.gd, via set_home()).
## Plans change every real day (seeded by resident and local date, so every client
## agrees): working hours drift, each worker has a weekly day off (their shop stays
## shut with a "쉬는 날" message), weekdays differ (Sunday lie-in and late opening,
## Friday's late café, Saturday's market morning on the square) and some days bring a
## small outing (picnic, fishing trip, a visit to a friend's house). Night owls keep
## night hours.
##
## Places are building ids from TownLayout.DOORS ("01_cafe", ...) or "outside".
## Spots inside a building are furniture words the interiors map to real pieces:
##   bed table stove armchair sofa fireplace desk bookshelf piano sink window
##   counter telescope millstone garden_bed lens workbench
## Outside spots are keys the walkers map to positions (see OUTSIDE_SPOTS).

## kind: "cast" (named villagers, res://assets/npc/<id>.glb) or "shadow" (silhouette folk).
## sleep: "day" (sleeps at night), "early" (dawn fishers), "evening" (late lamplighter), "night".
## work: [{place, spot, activity, from, to}], local hours; place "outside" uses an outside spot.
## unwind (optional): [{place, spot, activity}] one of which follows the last shift for an hour or so.
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
	{"id":"farmer","kind":"shadow","home":"18_meadow_house","sleep":"early",
		"work":[{"place":"03_teal_cottage","spot":"counter","activity":"shopkeep","from":8.5,"to":12.5},
			{"place":"outside","spot":"farm","activity":"farm","from":13.5,"to":17.5}]},
	{"id":"regular","kind":"shadow","home":"18_meadow_house","sleep":"day",
		"work":[{"place":"01_cafe","spot":"counter","activity":"barista","from":8.0,"to":20.0}]},
	{"id":"miller","kind":"shadow","home":"18_meadow_house","sleep":"early",
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
	# 보니 · 공방 제작 담당: works in front of 별씨 공방 (the player's workshop, town.gd WORKSHOP_DOOR),
	# unwinds at the café or on a walk after work, sleeps in the windmill's attic room.
	{"id":"boni","kind":"shadow","home":"04_windmill","sleep":"day",
		"work":[{"place":"outside","spot":"workshop_yard","activity":"craft","from":9.0,"to":12.5},
			{"place":"outside","spot":"workshop_yard","activity":"craft","from":13.5,"to":19.0}],
		"unwind":[{"place":"01_cafe","spot":"table","activity":"coffee"},{"place":"outside","spot":"bench","activity":"stroll"}]},
	# 솔 · 꼬마 정원사: 초록's apprentice; mornings in the greenhouse with her, afternoons in the
	# herb beds outside; lives above the seed shop. Takes 초록's day off with her (DAY_OFF_WITH).
	{"id":"sol","kind":"shadow","home":"03_teal_cottage","sleep":"day",
		"work":[{"place":"07_greenhouse","spot":"garden_bed","activity":"tend","from":8.0,"to":12.0},
			{"place":"outside","spot":"herb_garden","activity":"garden","from":13.0,"to":17.0}]},
]

## Rough village positions for outside spots (x, z). Walkers wander near them.
const OUTSIDE_SPOTS := {
	"gate":Vector2(51,37),"square":Vector2(-30,35),"camp":Vector2(57,38),
	"lighthouse_pier":Vector2(1.5,78.5),"pond_pier":Vector2(-44,33),"pond":Vector2(-29,42),
	"farm":Vector2(-18.4,-31.5),"gazebo":Vector2(63,-25),"orchard":Vector2(-46,-33),
	"bridges":Vector2(24,30.5),"lamps":Vector2(-25.5,57.5),"rounds":Vector2(-33,37),
	"bench":Vector2(-24,36),"picnic":Vector2(65,29),"stage":Vector2(37,26),
	"workshop_yard":Vector2(-33.1,34.0),"herb_garden":Vector2(44,-13),
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

## Weekly day off (weekday(): 0 Sunday .. 6 Saturday). Shop owners are spread over the week so
## the village never shuts all at once; other workers get a day from hash(id). Nobody off:
## the cast (their services stay put), the kid, and the lamp and night walkers.
const DAY_OFF := {"regular":1,"shopkeeper":3,"farmer":2,"miller":4,"gardener":1,"stargazer":2,"boni":2}
## Apprentices rest with their master.
const DAY_OFF_WITH := {"sol":"gardener"}
const NO_DAY_OFF := ["kid","lamplighter","stroller"]
## Saturday morning the square fills up (market); residents free that morning may drop by,
## and the easy-going outdoor jobs (MARKET_LATE) start at 11 that day so they can go too.
const MARKET_DAY := 6
const MARKET_LATE := ["play","write","scout"]
## Small outings that may fill a free stretch: event -> windows [from, to], place, spot,
## activity. Only existing activities and spots, so walkers and rooms need nothing new.
const OUTINGS := {
	"picnic":{"windows":[[11.5,14.0]],"place":"outside","spot":"picnic","activity":"stroll"},
	"fishing":{"windows":[[6.5,8.6],[16.0,18.5]],"place":"outside","spot":"pond_pier","activity":"fish"},
	"visit":{"windows":[[14.5,17.0],[18.5,20.6]],"place":"friend","spot":"sofa","activity":"visit"},
}

static func resident(id: String) -> Dictionary:
	for entry in RESIDENTS:
		if entry.id == id: return entry
	return {}

## Where residents live when it differs from RESIDENTS (story move-ins, #43): id -> room.
static var homes := {}

## Moves a resident into `room` (an interiors.gd room such as "danbi_house", a plot house
## from plots.gd) or, with room "", back to their RESIDENTS home. Plans, beds
## (residents_of), the interiors and building_state() all follow at once, so the new
## house lights up and opens while its resident is home and awake. Per session (static):
## story code sets it for whichever village is shown.
##   Residents.set_home("shopkeeper", "danbi_house")   단비 sleeps and spends home time there
##   Residents.set_home("shopkeeper", "")              back to the back room of 13_shop
static func set_home(id: String, room: String) -> void:
	if room.is_empty(): homes.erase(id)
	else: homes[id] = room
	_plans.clear()
	_states.clear()

## The building or room `id` lives in now (set_home() wins over RESIDENTS), "" if unknown.
static func home_of(id: String) -> String:
	return str(homes.get(id, resident(id).get("home", "")))

## Ids of everyone whose bed is in this building.
static func residents_of(building: String) -> Array[String]:
	var out: Array[String] = []
	for entry in RESIDENTS:
		if home_of(entry.id) == building: out.append(entry.id)
	return out

## Local clock: {"hour": 0..24 float, "day": days since 1970-01-01 (local date)}.
static func clock() -> Dictionary:
	var now := Time.get_datetime_dict_from_system()
	var day := int(Time.get_unix_time_from_datetime_dict({"year":now.year,"month":now.month,"day":now.day})/86400)
	return {"hour":now.hour+now.minute/60.0+now.second/3600.0,"day":day}

## Day of the week for a clock() day: 0 Sunday .. 6 Saturday (1970-01-01 was a Thursday).
static func weekday(day: int) -> int:
	return posmod(day+4, 7)

## True on `id`'s weekly day off (only residents with work have one).
static func day_off(id: String, day: int) -> bool:
	var key := str(DAY_OFF_WITH.get(id, id))
	var entry := resident(key)
	if entry.is_empty() or entry.work.is_empty() or str(entry.kind) == "cast" or key in NO_DAY_OFF: return false
	return weekday(day) == int(DAY_OFF.get(key, absi(hash(key+":off")) % 7))

## The day's work before any jitter: none on a day off, an hour's later start on Sunday
## for day workers, the café open an hour longer on Friday, market-morning jobs from 11 on
## Saturday.
static func _fixed_shifts(entry: Dictionary, day: int) -> Array:
	var out: Array = []
	if day_off(str(entry.id), day): return out
	var wd := weekday(day)
	var day_sleeper: bool = str(entry.get("sleep","day")) in ["day","early"]
	for shift in entry.work:
		var from := float(shift.from)
		var to := float(shift.to)
		if wd == 0 and day_sleeper and from < 12.0 and to-from > 3.0: from += 1.0
		if wd == 5 and shift.activity == "barista": to += 1.0
		if wd == MARKET_DAY and shift.activity in MARKET_LATE and from < 11.0: from = 11.0
		out.append({"place":shift.place,"spot":shift.spot,"activity":shift.activity,"from":from,"to":to})
	return out

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
	# A Sunday lie-in for everyone on day hours.
	return rng.randf_range(5.8, 7.6)+(0.7 if weekday(day) == 0 else 0.0)

static func _bedtime(entry: Dictionary, rng: RandomNumberGenerator) -> float:
	if entry.has("bedtime"): return float(entry.bedtime)+rng.randf_range(-0.3, 0.4)
	match str(entry.get("sleep","day")):
		"early": return rng.randf_range(20.8, 21.8)
		"evening": return rng.randf_range(24.8, 26.0)
		"night": return rng.randf_range(28.6, 29.6)
	return rng.randf_range(21.8, 23.6)

## One day's plan from waking up until waking up again, as blocks
## {from, to, place, spot, activity, asleep, event} in hours from that day's midnight
## (so a block can run past 24). Work comes from RESIDENTS (_fixed_shifts: day off,
## weekday hours), then the day's outings (_outings), and the gaps are filled with seeded
## home time, meals and leisure. event is "" or the outing ("market", "picnic",
## "fishing", "visit", "unwind").
## Plans are pure functions of (id, day, set_home), so they are built once and cached.
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
	var home := home_of(id)
	var shifts: Array = []
	for shift in _fixed_shifts(entry, day):
		# Work hours drift a little day to day, and some days start late.
		var start: float = float(shift.from)+rng.randf_range(-0.25, 0.35)
		var stop: float = float(shift.to)+rng.randf_range(-0.4, 0.3)
		# A shift may not start before waking or run into bedtime.
		start = maxf(start, wake+0.4)
		stop = minf(stop, bed-0.1)
		if stop > start+0.25:
			shift.from = start
			shift.to = stop
			shifts.append(shift)
	# The day's outings go in free stretches (their own seed: work and sleep stay as they were).
	shifts.append_array(_outings(entry, day, wake, bed, shifts))
	shifts.sort_custom(func(a, b): return a.from < b.from)
	var t := wake
	# Morning at home first.
	var morning: float = minf(wake+rng.randf_range(0.6, 1.4), shifts[0].from if not shifts.is_empty() else bed)
	_add(blocks, t, morning, home, "", HOME_ACTIVITIES[rng.randi_range(0, 2)])
	t = morning
	for shift in shifts:
		if shift.from > t: _fill_free(blocks, entry, t, shift.from, rng, day)
		_add(blocks, maxf(t, shift.from), shift.to, shift.place, shift.spot, shift.activity, str(shift.get("event", "")))
		t = maxf(t, shift.to)
	# Some unwind somewhere after work (보니: the café while it is open, else a bench).
	if entry.has("unwind") and not shifts.is_empty() and bed > t+1.2:
		var options: Array = entry.unwind.filter(func(o): return o.place != "01_cafe" or _owner_working("01_cafe", t+0.2, day))
		if not options.is_empty():
			var pick: Dictionary = options[rng.randi_range(0, options.size()-1)]
			var stop := minf(t+rng.randf_range(1.0, 1.6), bed)
			_add(blocks, t, stop, pick.place, pick.spot, pick.activity, "unwind")
			t = stop
	if bed > t: _fill_free(blocks, entry, t, bed, rng, day)
	_add(blocks, maxf(t, bed), next_wake, home, "bed", "sleep")
	return blocks

## The outings in a resident's day, as fixed blocks: Saturday's market morning on the
## square for those free then, and on a day off (two) or about one ordinary day in three
## (one) a picnic, a fishing trip or a visit to a friend's house, in the first window
## that fits between waking, work and bed. Deterministic per (resident, day).
static func _outings(entry: Dictionary, day: int, wake: float, bed: float, shifts: Array) -> Array:
	var out: Array = []
	var id := str(entry.id)
	if str(entry.get("sleep","")) in ["night","evening"]: return out
	var rng := _rng(id, day*31+11)
	var taken := shifts.duplicate()
	# The kid never misses the market.
	if weekday(day) == MARKET_DAY and rng.randf() < (1.0 if id == "kid" else 0.7):
		var start := 8.4+rng.randf_range(0.0, 0.4)
		var market := {"place":"outside","spot":"square","activity":"stroll","from":start,"to":start+rng.randf_range(1.0, 1.6),"event":"market"}
		if _fits(market, wake, bed, taken):
			out.append(market)
			taken.append(market)
	var off := day_off(id, day)
	if not off and rng.randf() > 0.33: return out
	var kinds: Array = OUTINGS.keys()
	# A seeded shuffle (Array.shuffle() would use the global generator).
	for i in range(kinds.size()-1, 0, -1):
		var j := rng.randi_range(0, i)
		var swap = kinds[i]
		kinds[i] = kinds[j]
		kinds[j] = swap
	var wanted := 2 if off else 1
	for kind in kinds:
		if wanted <= 0: break
		var spec: Dictionary = OUTINGS[kind]
		for window in spec.windows:
			var length := rng.randf_range(1.2, 2.2)
			var from: float = float(window[0])+rng.randf_range(0.0, maxf(0.0, float(window[1])-float(window[0])-length))
			var place := str(spec.place)
			if place == "friend": place = _friend_home(entry, rng)
			if place.is_empty(): break
			var block := {"place":place,"spot":spec.spot,"activity":spec.activity,"from":from,"to":from+length,"event":kind}
			if _fits(block, wake, bed, taken):
				out.append(block)
				taken.append(block)
				wanted -= 1
				break
	return out

## Awake, before bed and clear of every fixed block by a little.
static func _fits(block: Dictionary, wake: float, bed: float, taken: Array) -> bool:
	if block.from < wake+0.8 or block.to > bed-0.4: return false
	for other in taken:
		if block.from < float(other.to)+0.3 and block.to > float(other.from)-0.3: return false
	return true

## A friend's house to call on: someone else's dwelling (not a shop, not the visitor's own).
static func _friend_home(entry: Dictionary, rng: RandomNumberGenerator) -> String:
	var own := home_of(str(entry.id))
	for _attempt in 4:
		var friend: Dictionary = RESIDENTS[rng.randi_range(0, RESIDENTS.size()-1)]
		var house := home_of(str(friend.id))
		if house != own and not SHOPS.has(house): return house
	return ""

## Free time: meals, a visit to the café or a friend, a stroll, or staying in.
static func _fill_free(blocks: Array[Dictionary], entry: Dictionary, from: float, to: float, rng: RandomNumberGenerator, day: int) -> void:
	var t := from
	var home := home_of(str(entry.id))
	while t < to-0.001:
		var length: float = minf(to-t, rng.randf_range(0.8, 2.2))
		# Never leave a sliver of time before the next fixed block.
		if to-(t+length) < 0.3: length = to-t
		var hour := fmod(t, 24.0)
		var roll := rng.randf()
		var meal: bool = (hour > 11.5 and hour < 13.5) or (hour > 17.5 and hour < 19.5)
		var night: bool = hour >= 21.0 or hour < 5.0
		var night_owl: bool = str(entry.get("sleep","")) in ["night","evening"]
		if meal and roll < 0.35 and _owner_working("01_cafe", t, day):
			_add(blocks, t, t+length, "01_cafe", "table", "coffee")
		elif meal and roll < 0.75:
			_add(blocks, t, t+length, home, "", "eat")
		elif (not night or night_owl) and roll < 0.55:
			_add(blocks, t, t+length, "outside", LEISURE_OUTSIDE[rng.randi_range(0, LEISURE_OUTSIDE.size()-1)], "stroll")
		elif not night and roll < 0.68:
			# Pop into a shop that is open, or call on a neighbour who is up.
			var shop: String = SHOPS.keys()[rng.randi_range(0, SHOPS.size()-1)]
			if _owner_working(shop, t, day): _add(blocks, t, t+length, shop, "", "browse")
			else: _add(blocks, t, t+length, home, "", HOME_ACTIVITIES[rng.randi_range(0, HOME_ACTIVITIES.size()-1)])
		elif not night and roll < 0.78:
			var friend: Dictionary = RESIDENTS[rng.randi_range(0, RESIDENTS.size()-1)]
			var house := home_of(str(friend.id))
			# Never into a shop on its closed hours (a day off keeps it shut).
			if house != home and (not SHOPS.has(house) or _owner_working(house, t, day)): _add(blocks, t, t+length, house, "sofa", "visit")
			else: _add(blocks, t, t+length, home, "", "chat")
		else:
			_add(blocks, t, t+length, home, "", HOME_ACTIVITIES[rng.randi_range(0, HOME_ACTIVITIES.size()-1)])
		t += length

static func _add(blocks: Array[Dictionary], from: float, to: float, place: String, spot: String, activity: String, event := "") -> void:
	if to <= from+0.01: return
	if spot.is_empty() and place != "outside": spot = str(ACTIVITY_SPOT.get(activity, "table"))
	# Merge with the previous block when nothing changes.
	if not blocks.is_empty():
		var last: Dictionary = blocks[-1]
		if last.place == place and last.activity == activity and last.spot == spot and last.event == event and absf(last.to-from) < 0.02:
			last.to = to
			return
	blocks.append({"from":from,"to":to,"place":place,"spot":spot,"activity":activity,"asleep":activity == "sleep","event":event})

## The owner's fixed shift only (no jitter, but with the day off and weekday hours), used
## while building other plans so a visit never points at a closed shop.
static func _owner_working(building: String, at: float, day: int) -> bool:
	var owner := resident(str(SHOPS.get(building, "")))
	if owner.is_empty(): return false
	var hour := fmod(at, 24.0)
	for shift in _fixed_shifts(owner, day):
		if shift.place != building: continue
		var from: float = float(shift.from)
		var to: float = float(shift.to)
		if (hour >= from and hour < to) or (hour+24.0 >= from and hour+24.0 < to): return true
	return false

## Residents the story chapter keeps out of their plan (story.gd: 모카 waits on the café terrace
## as the story's own figure, a passer-by sits on the terrace's new chair). Their place is "story":
## no building has them inside and their walker steps out of sight, so nobody is seen twice.
static var held := {}

## Takes `id` out of (on) or gives it back to (off) its daily plan.
static func hold(id: String, on: bool) -> void:
	if on == held.has(id): return
	if on: held[id] = {"place":"story","spot":"","activity":"story","asleep":false,"event":""}
	else: held.erase(id)
	_states.clear()

## Where a resident is right now: {place, spot, activity, asleep, from, to, event}.
## hour/day default to the local clock; pass the daylight override hour to test.
static func now(id: String, hour := -1.0, day := -1) -> Dictionary:
	var c := clock()
	if hour < 0.0: hour = c.hour
	if day < 0: day = c.day
	if held.has(id): return held[id].merged({"id":id,"from":hour,"to":hour+1.0})
	for block in plan(id, day):
		if hour >= block.from and hour < block.to: return block.merged({"id":id})
	for block in plan(id, day-1):
		if hour+24.0 >= block.from and hour+24.0 < block.to: return block.merged({"id":id})
	return {"id":id,"place":home_of(id),"spot":"bed","activity":"sleep","asleep":true,"from":hour,"to":hour+1.0,"event":""}

## The outings in a resident's day ("market", "picnic", "fishing", "visit", "unwind"), in order.
static func day_events(id: String, day: int) -> Array[String]:
	var out: Array[String] = []
	for block in plan(id, day):
		var event := str(block.get("event", ""))
		if not event.is_empty() and not event in out: out.append(event)
	return out

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
##  message (Korean, already tr()'d), occupants, day_off (the owner's weekly day off)}
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
	var state := {"lights_on":true,"open":false,"enterable":true,"reason":"","message":"","occupants":[],"day_off":false}
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
	# The owner's weekly day off: the shop stays shut and its front dark through the day, even
	# with them home in the back room (dark windows always mean a locked door).
	if not owner.is_empty() and not state.open and day_off(owner, day) and hour >= 6.0 and hour < 22.0:
		state.lights_on = false
		state.enterable = false
		state.reason = "closed"
		state.day_off = true
		state.message = TranslationServer.translate("오늘은 쉬는 날이라 문을 닫았어요. 내일 다시 와 주세요.")
		return state
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
