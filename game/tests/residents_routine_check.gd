extends SceneTree
## Daily routines (residents.gd #20) and the two new villagers (#83), headless and without a
## server: only Residents / DayFolk static functions.
##  - 보니 and 솔 exist with titles, looks, walkers (shadow_folk.gd FOLK) and a valid place for
##    every half hour over 7 consecutive days; 보니 works by 별씨 공방, 솔 in the greenhouse,
##  - routines differ across days for several residents, outings happen, Saturday has a market,
##  - a worker's day off closes their shop door with the day-off reason,
##  - set_home("shopkeeper", "danbi_house") opens 단비네 집 while she is home; clearing it
##    puts her back in 13_shop.
## Godot --headless --path game --script res://tests/residents_routine_check.gd
const Residents = preload("res://scripts/residents.gd")
const DayFolk = preload("res://scripts/day_folk.gd")
const Town = preload("res://scripts/town.gd")
var failed := 0
var passed := 0

func _initialize() -> void:
	call_deferred("run")

func expect(value: bool, description: String) -> void:
	if value:
		passed += 1
		print("PASS ", description)
	else:
		failed += 1
		print("FAIL ", description)

func run() -> void:
	var base: int = Residents.clock().day
	var buildings := {}
	for door in Town.DOORS: buildings[str(door.id)] = true
	buildings["danbi_house"] = true
	expect(Residents.weekday(0) == 4, "1970-01-01 is a Thursday (weekday 4)")
	check_new_villagers(base, buildings)
	check_variety(base)
	check_day_off(base)
	check_set_home(base)
	print("RESIDENTS_ROUTINE ", "FAIL" if failed else "OK", " pass=", passed, " fail=", failed)
	quit(1 if failed else 0)

func check_new_villagers(base: int, buildings: Dictionary) -> void:
	var folk: Array = (load("res://scripts/shadow_folk.gd") as GDScript).FOLK
	for pair in [["boni", "보니"], ["sol", "솔"]]:
		var id: String = pair[0]
		expect(not Residents.resident(id).is_empty(), "%s is a resident" % id)
		expect(DayFolk.title(id).begins_with(pair[1]) and DayFolk.title(id).contains(" · "), "%s has a title (%s)" % [id, DayFolk.title(id)])
		expect(DayFolk.has_look(id) and not DayFolk.opener(id, 9.0).is_empty(), "%s has a daytime look and time-of-day openers" % id)
		expect(folk.any(func(e): return str(e.id) == id), "%s walks the village (shadow_folk.gd FOLK)" % id)
		var bad := []
		for offset in 7:
			var day := base+offset
			var blocks := Residents.plan(id, day)
			for i in range(1, blocks.size()):
				if absf(blocks[i-1].to-blocks[i].from) > 0.02: bad.append("gap day+%d %.2f" % [offset, blocks[i].from])
			if blocks.is_empty() or blocks[-1].activity != "sleep": bad.append("day+%d does not end asleep" % offset)
			for step in 48:
				var state := Residents.now(id, step*0.5, day)
				var place := str(state.place)
				var ok: bool = buildings.has(place) or (place == "outside" and (Residents.OUTSIDE_SPOTS.has(str(state.spot)) or str(state.spot) in ["stroll", "rounds"]))
				if not ok: bad.append("day+%d %.1fh %s/%s" % [offset, step*0.5, place, state.spot])
		expect(bad.is_empty(), "%s has a valid place every half hour for 7 days %s" % [id, bad.slice(0, 4)])
	var boni_work := 0
	var sol_work := 0
	var workdays := 0
	for offset in 7:
		var day := base+offset
		if Residents.day_off("boni", day): expect(Residents.now("boni", 11.0, day).activity != "craft", "보니 rests on her day off (day+%d)" % offset)
		else:
			workdays += 1
			if Residents.now("boni", 11.0, day).spot == "workshop_yard": boni_work += 1
		if not Residents.day_off("sol", day) and Residents.now("sol", 10.0, day).place == "07_greenhouse": sol_work += 1
	expect(workdays == 6 and boni_work == workdays, "보니 is at 별씨 공방 at 11:00 on every workday (%d/%d)" % [boni_work, workdays])
	expect(sol_work == 6, "솔 tends the greenhouse at 10:00 on every workday (%d/6)" % sol_work)
	expect(Residents.day_off("sol", base) == Residents.day_off("gardener", base) and Residents.DAY_OFF_WITH.sol == "gardener", "솔 takes 초록's day off")
	expect(Residents.now("boni", 3.0, base).asleep and Residents.now("boni", 3.0, base).place == "04_windmill", "보니 sleeps at home at night")
	expect(Residents.now("sol", 3.0, base).asleep and Residents.now("sol", 3.0, base).place == "03_teal_cottage", "솔 sleeps at home at night")
	expect("boni" in Residents.residents_of("04_windmill") and "sol" in Residents.residents_of("03_teal_cottage"), "both have a bed in their home")
	var story_script := load("res://scripts/story.gd") as GDScript
	expect(not story_script.GREETINGS.has("boni") and not story_script.GREETINGS.has("sol") and not "boni" in story_script.GUESTS and not "sol" in story_script.GUESTS, "story greeters and guests unchanged")
	expect(not preload("res://scripts/npc_gifts.gd").can_receive("boni") and not preload("res://scripts/npc_gifts.gd").can_receive("sol"), "no gift homes for the new two yet")

func signature(id: String, day: int) -> String:
	var parts := PackedStringArray()
	for block in Residents.plan(id, day):
		if block.asleep: continue
		parts.append("%s/%s/%s@%d" % [block.place, block.spot, block.activity, int(block.from)])
	return "|".join(parts)

func check_variety(base: int) -> void:
	var varied := 0
	var events := {}
	var market := false
	for entry in Residents.RESIDENTS:
		var seen := {}
		for offset in 7:
			seen[signature(entry.id, base+offset)] = true
			for event in Residents.day_events(entry.id, base+offset):
				events[event] = int(events.get(event, 0))+1
				if event == "market": market = true
		if seen.size() >= 5: varied += 1
	print("VARIETY residents_with_5plus_routines=", varied, " events=", events)
	expect(varied >= 12, "routines differ across 7 days for many residents (%d with 5+ different days)" % varied)
	expect(events.size() >= 3, "several kinds of outings happen in a week %s" % [events])
	expect(market, "Saturday brings a market morning")
	# Deterministic: a fresh build gives the same plan (every client agrees).
	var before := signature("postman", base+2)
	Residents._plans.clear()
	expect(signature("postman", base+2) == before, "plans are deterministic per (resident, date)")

func check_day_off(base: int) -> void:
	for owner_pair in [["shopkeeper", "13_shop"], ["regular", "01_cafe"], ["gardener", "07_greenhouse"]]:
		var owner: String = owner_pair[0]
		var shop: String = owner_pair[1]
		var off_day := -1
		var work_day := -1
		for offset in 7:
			if Residents.day_off(owner, base+offset): off_day = base+offset
			elif work_day < 0 and Residents.weekday(base+offset) != 0: work_day = base+offset
		expect(off_day >= 0, "%s has a day off within a week" % owner)
		if off_day < 0: continue
		var shut: Dictionary = Residents.building_state(shop, 12.0, off_day)
		expect(not shut.enterable and str(shut.reason) == "closed" and bool(shut.day_off) and not str(shut.message).is_empty() and not shut.open,
			"%s is shut with the day-off message on %s's day off (%s)" % [shop, owner, shut.message])
		var open: Dictionary = Residents.building_state(shop, 12.0, work_day)
		expect(open.open and open.enterable, "%s is open at noon on a workday" % shop)
		var visitors := 0
		for step in range(12, 44):
			for o in Residents.occupants(shop, step*0.5, off_day):
				if o.activity in ["browse", "coffee"]: visitors += 1
		expect(visitors == 0, "nobody shops at %s on its day off" % shop)

func check_set_home(base: int) -> void:
	Residents.set_home("shopkeeper", "danbi_house")
	expect(Residents.home_of("shopkeeper") == "danbi_house" and "shopkeeper" in Residents.residents_of("danbi_house"), "set_home moves 단비 into danbi_house")
	expect(Residents.now("shopkeeper", 3.0, base).place == "danbi_house" and Residents.now("shopkeeper", 3.0, base).asleep, "단비 sleeps in danbi_house")
	var home_hour := -1.0
	for step in range(24, 92):
		var h := step*0.25
		var state := Residents.now("shopkeeper", h, base)
		if state.place == "danbi_house" and not state.asleep:
			home_hour = h
			break
	expect(home_hour >= 0.0, "단비 spends awake time at danbi_house")
	if home_hour >= 0.0:
		var house: Dictionary = Residents.building_state("danbi_house", home_hour, base)
		expect(house.enterable and house.lights_on, "danbi_house is enterable while 단비 is home (%.2fh)" % home_hour)
	expect(not Residents.building_state("danbi_house", 3.0, base).enterable, "danbi_house is dark while she sleeps")
	var in_shop := Residents.occupants("13_shop", 3.0, base).any(func(o): return o.id == "shopkeeper")
	expect(not in_shop, "13_shop no longer has her bed")
	Residents.set_home("shopkeeper", "")
	expect(Residents.home_of("shopkeeper") == "13_shop", "clearing restores 13_shop")
	expect(Residents.now("shopkeeper", 3.0, base).place == "13_shop", "단비 sleeps in 13_shop again")
	if home_hour >= 0.0:
		var empty: Dictionary = Residents.building_state("danbi_house", home_hour, base)
		expect(not empty.enterable and str(empty.reason) == "away", "danbi_house is locked again once she moved back")
