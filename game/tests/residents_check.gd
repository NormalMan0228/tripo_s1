extends SceneTree
## Prints every resident's plan for today and the lights/door state of each
## building through the day, and checks the plans are gap-free and sane.
const Residents = preload("res://scripts/residents.gd")
const TownLayout = preload("res://scripts/town.gd")
var failed := false

func _initialize() -> void:
	call_deferred("run")

func expect(value: bool, description: String) -> void:
	if not value:
		failed = true
		print("FAIL ", description)

func run() -> void:
	var day: int = Residents.clock().day
	# Two weeks of plans must all be gap-free; today's are printed.
	for later in range(1, 14):
		for entry in Residents.RESIDENTS:
			var later_blocks := Residents.plan(entry.id, day+later)
			for i in range(1, later_blocks.size()):
				expect(absf(later_blocks[i-1].to-later_blocks[i].from) < 0.02, "%s day+%d has no gaps" % [entry.id, later])
			expect(not later_blocks.is_empty() and later_blocks[-1].activity == "sleep", "%s day+%d ends asleep" % [entry.id, later])
	for entry in Residents.RESIDENTS:
		var blocks := Residents.plan(entry.id, day)
		var line := PackedStringArray()
		for i in blocks.size():
			var b: Dictionary = blocks[i]
			line.append("%05.2f-%05.2f %s/%s/%s" % [b.from, b.to, b.place, b.spot, b.activity])
			if i > 0: expect(absf(blocks[i-1].to-b.from) < 0.02, "%s plan has no gaps at %.2f" % [entry.id, b.from])
		expect(not blocks.is_empty() and blocks[-1].activity == "sleep", "%s ends the day asleep" % entry.id)
		var home_known := false
		for door in TownLayout.DOORS:
			if door.room == entry.home: home_known = true
		expect(home_known, "%s lives in a real building" % entry.id)
		print("PLAN ", entry.id, " ", " | ".join(line))
	for hour in [2.0, 6.5, 9.0, 12.5, 15.0, 19.0, 21.5, 23.5]:
		var lit := PackedStringArray()
		var outside := Residents.outdoors(hour, day).size()
		for door in TownLayout.DOORS:
			var state := Residents.building_state(door.room, hour, day)
			lit.append("%s:%s%s" % [door.room.substr(0, 6), "on" if state.lights_on else "off", "/open" if state.open else ""])
		print("HOUR %05.2f outside=%d %s" % [hour, outside, " ".join(lit)])
	print("RESIDENTS_CHECK ", "FAIL" if failed else "OK")
	quit(1 if failed else 0)
