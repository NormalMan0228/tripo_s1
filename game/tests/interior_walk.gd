extends SceneTree
## Walkability of every interior (no server, works headless):
##  - every room of every floor is reachable from the door / stair arrival,
##  - the walker is actually driven (same movement code as WASD) to every
##    interactable piece and every stair without getting stuck,
##  - every piece is usable from where it can be reached (E picks it and it answers),
##  - every stair arrives on a free, connected spot of its target floor,
##  - every room has at least 8 things to use.
##   Godot --headless --path game -s res://tests/interior_walk.gd [-- --room=01_cafe]
const Interiors = preload("res://scripts/interiors.gd")
const ROOMS := ["home","workshop","01_cafe","02_timber_house","03_teal_cottage","04_windmill","05_observatory","06_orange_cottage","07_greenhouse","11_purple_house","12_blue_house","13_shop","16_blue_cottage","17_lighthouse"]
const CELL := 0.2
const STEP := 1.0/60.0
var failures: Array[String] = []
var report: Array = []
var resident_report: Array = []
const Residents = preload("res://scripts/residents.gd")

func _initialize() -> void:
	call_deferred("run")
	create_timer(900).timeout.connect(func():
		push_error("Interior walk exceeded 900 seconds")
		quit(2))

func check(value: bool, description: String) -> void:
	if not value:
		failures.append(description)
		print("FAIL ",description)

func run() -> void:
	var only := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--room="): only = arg.trim_prefix("--room=")
	Engine.set_meta("interior_hour",13.0)
	for id in ROOMS:
		if not only.is_empty() and id != only: continue
		Engine.set_meta("studio_session",{"token":"","url":"http://127.0.0.1:9","room":id})
		var app: Control = load("res://scenes/studio.tscn").instantiate()
		root.add_child(app)
		await create_timer(0.3).timeout
		app.set_process(false)
		app.travel_enabled = false
		var floors: Array = app.building_spec.floors
		for index in floors.size():
			app.set_floor(index)
			var start := Interiors.spawn_point(app.room_spec) if index == 0 else arrival_to(floors,index)
			check(app.can_stand(start), "%s floor %d: start %s is free" % [id,index,str(start)])
			await walk_floor(app,id,index,start)
		app.queue_free()
		await process_frame
	await check_residents(only)
	Engine.remove_meta("interior_hour")
	Engine.remove_meta("interior_day")
	print("INTERIOR_WALK ",JSON.stringify({"ok":failures.is_empty(),"failures":failures,"rooms":report,"residents":resident_report}))
	quit(0 if failures.is_empty() else 1)

func arrival_to(floors: Array, index: int) -> Vector3:
	for f in floors:
		for entry in f.furniture:
			if entry.has("link") and int(entry.link.to) == index: return entry.link.arrive
	return Vector3.ZERO

func key(cell: Vector2i) -> int:
	return (cell.x+200)*1000+(cell.y+200)

func to_world(cell: Vector2i) -> Vector3:
	return Vector3(cell.x*CELL,0,cell.y*CELL)

## Breadth-first flood over free cells from the start; returns {key: previous key}.
func flood(app: Control, start: Vector3) -> Dictionary:
	var first := Vector2i(roundi(start.x/CELL),roundi(start.z/CELL))
	var came := {key(first):-1}
	var cells := {key(first):first}
	var queue: Array[Vector2i] = [first]
	var size: Vector2 = app.room_spec.size
	while not queue.is_empty():
		var cell: Vector2i = queue.pop_front()
		for offset in [Vector2i(1,0),Vector2i(-1,0),Vector2i(0,1),Vector2i(0,-1)]:
			var next: Vector2i = cell+offset
			if absf(next.x*CELL)>size.x*0.5 or absf(next.y*CELL)>size.y*0.5: continue
			var k := key(next)
			if came.has(k): continue
			if not app.can_stand(to_world(next)): continue
			came[k] = key(cell)
			cells[k] = next
			queue.append(next)
	return {"came":came,"cells":cells,"first":key(first)}

func path_to(graph: Dictionary, target: int) -> Array[Vector3]:
	var points: Array[Vector3] = []
	var k := target
	while k != -1:
		points.push_front(to_world(graph.cells[k]))
		k = graph.came[k]
	return points

## Drives the walker along a path with the studio's own movement code.
func drive(app: Control, points: Array[Vector3]) -> bool:
	for point in points:
		var best := INF
		var idle := 0
		for i in 400:
			var offset: Vector3 = point-app.hero.position
			offset.y = 0
			if offset.length() < 0.06: break
			app.move_hero(offset,STEP)
			var left: float = (point-app.hero.position).length()
			if left < best-0.004:
				best = left
				idle = 0
			else:
				idle += 1
				if idle > 40: return false
		var rest: Vector3 = point-app.hero.position
		rest.y = 0
		if rest.length() > 0.08: return false
	return true

func walk_floor(app: Control, id: String, index: int, start: Vector3) -> void:
	app.hero.position = start
	var graph := flood(app,start)
	var spec: Dictionary = app.room_spec
	var label := "%s floor %d" % [id,index]
	# Every room on this floor can be reached.
	for r in spec.rooms.size():
		var room: Dictionary = spec.rooms[r]
		var reached := false
		for k in graph.cells:
			var at := to_world(graph.cells[k])
			if at.x > float(room.x0)+0.3 and at.x < float(room.x1)-0.3:
				reached = true
				break
		check(reached, "%s: room %s is reachable" % [label,room.name])
	var counts := {}
	for r in spec.rooms.size(): counts[r] = 0
	for record in app.decor:
		if not record.interactive: continue
		counts[Interiors.room_at(spec,float(record.center.x))] += 1
		# Find a reachable cell from which E picks exactly this piece.
		var target := -1
		var best_gap := INF
		for k in graph.cells:
			var at := to_world(graph.cells[k])
			var local: Vector3 = (at-record.center).rotated(Vector3.UP,-float(record.yaw))
			var half: Vector2 = record.half
			var gap := Vector2(maxf(0.0,absf(local.x)-half.x),maxf(0.0,absf(local.z)-half.y)).length()
			if gap >= (1.35 if record.mounted else 0.85)-0.1 or gap >= best_gap: continue
			app.hero.position = at
			app.hero.facing = (record.center-at).normalized()
			if not listed(app,record): continue
			best_gap = gap
			target = k
		if target < 0:
			check(false, "%s: %s at %s cannot be reached and used" % [label,record.kind,str(record.center)])
			continue
		app.hero.position = start
		var moved := drive(app,path_to(graph,target))
		check(moved, "%s: walker got stuck walking to %s" % [label,record.kind])
		if not moved: continue
		app.hero.facing = (record.center-app.hero.position).normalized()
		check(listed(app,record), "%s: E beside %s reaches it (at %s, aimed %s)" % [label,record.kind,str(app.hero.position),str(to_world(graph.cells[target]))])
		app.bubble.visible = false
		var stage_children: int = app.stage.get_child_count()
		app.use_decor(record)
		check(app.last_used == record and ((app.bubble.visible and not app.bubble_label.text.is_empty()) or is_instance_valid(app.talk_box) or app.stage.get_child_count() > stage_children or record.has("link") or app.resting != ""), "%s: %s answers" % [label,record.kind])
		app.close_talk()
		if not app.resting.is_empty(): app.stand_up()
		check(app.resting.is_empty() and app.hero.position.y == 0.0, "%s: back on the floor after %s" % [label,record.kind])
		if record.has("link"):
			var link: Dictionary = record.link
			var here: int = app.floor_index
			app.travel_enabled = true
			var climb := await climb_watch(app,record)
			app.travel_enabled = false
			check(climb.done, "%s: %s climb finishes (took %.1f s)" % [label,record.kind,float(climb.seconds)])
			check(int(climb.stalls) == 0, "%s: %s climb never stalls (%d still frames)" % [label,record.kind,int(climb.stalls)])
			check(int(climb.slides) == 0, "%s: %s climb never walks in place (%d frames)" % [label,record.kind,int(climb.slides)])
			check(float(climb.rise) > 0.6, "%s: %s visibly climbs or descends (%.2f m)" % [label,record.kind,float(climb.rise)])
			check(app.floor_index == int(link.to) and app.hero.position.distance_to(link.arrive) < 0.01 and app.hero.position.y == 0.0, "%s: %s leads to floor %d" % [label,record.kind,int(link.to)])
			check(app.can_stand(link.arrive), "%s: %s arrival is free" % [label,record.kind])
			app.set_floor(here)
		app.hero.position = start
	for r in counts:
		check(int(counts[r]) >= 8, "%s: room %s has only %d things to use" % [label,spec.rooms[r].name,int(counts[r])])
		report.append({"room":"%s/%d/%s" % [id,index,spec.rooms[r].name],"usable":counts[r]})

## Within reach of E (first press, or a later press on the same spot).
func listed(app: Control, record: Dictionary) -> bool:
	for entry in app.decor_candidates():
		if entry.record == record: return true
	return false

## Residents at several hours: the right people are inside, every resident has a
## bed at home, sleepers lie in their own bed, everyone answers E, and nobody
## blocks the way between rooms and stairs.
func check_residents(only: String) -> void:
	var day: int = Residents.clock().day
	Engine.set_meta("interior_day",day)
	for id in ROOMS:
		if Interiors.is_private(id) or (not only.is_empty() and id != only): continue
		for hour in [3.0,7.5,12.5,19.0,22.5]:
			Engine.set_meta("interior_hour",hour)
			Engine.set_meta("studio_session",{"token":"","url":"http://127.0.0.1:9","room":id})
			var app: Control = load("res://scenes/studio.tscn").instantiate()
			root.add_child(app)
			await create_timer(0.2).timeout
			app.set_process(false)
			app.travel_enabled = false
			var label := "%s at %.1f h" % [id,hour]
			var expected: Array = []
			for occupant in Residents.occupants(id,hour,day): expected.append(str(occupant.id))
			var actual: Array = app.npcs.keys()
			expected.sort();actual.sort()
			check(expected == actual, "%s: inside %s, expected %s" % [label,str(actual),str(expected)])
			for resident in Residents.residents_of(id):
				var has_bed := false
				for list in app.decor_by_floor:
					for record in list:
						if record.kind == "bed" and str(record.get("owner","")) == resident: has_bed = true
				check(has_bed, "%s: %s has a bed at home" % [label,resident])
			for who in app.npcs:
				var entry: Dictionary = app.npcs[who]
				if entry.state.asleep:
					check(entry.pose == "lie" and str(entry.record.get("kind","")) == "bed" and str(entry.record.get("owner","")) == who, "%s: %s sleeps in their own bed" % [label,who])
				app.set_floor(int(entry.floor))
				var target: Dictionary = entry.talk if entry.pose == "stand" else entry.record
				app.bubble.visible = false
				app.use_decor(target)
				if entry.state.asleep: check(app.bubble.visible and not is_instance_valid(app.talk_box), "%s: sleeping %s only murmurs" % [label,who])
				else: check(is_instance_valid(app.talk_box), "%s: %s talks" % [label,who])
				app.close_talk()
			# Standing residents never cut a floor in two.
			for index in app.building_spec.floors.size():
				app.set_floor(index)
				var start := Interiors.spawn_point(app.room_spec) if index == 0 else arrival_to(app.building_spec.floors,index)
				var graph := flood(app,start)
				for room in app.room_spec.rooms:
					var reached := false
					for k in graph.cells:
						var at := to_world(graph.cells[k])
						if at.x > float(room.x0)+0.3 and at.x < float(room.x1)-0.3: reached = true;break
					check(reached, "%s floor %d: %s still reachable with residents inside" % [label,index,room.name])
			resident_report.append("%s %02d:%02d %s" % [id,int(hour),int(fmod(hour,1.0)*60),",".join(actual)])
			app.queue_free()
			await process_frame

## Runs an animated climb and watches every frame: the walker must keep moving
## (except under the black fade) and the walk clip must never run in place.
func climb_watch(app: Control, record: Dictionary) -> Dictionary:
	var result := {"done":false,"stalls":0,"slides":0,"rise":0.0,"seconds":0.0}
	var started := Time.get_ticks_msec()
	app.travel(record)
	var last: Vector3 = app.hero.position
	var still := 0
	var lowest := 0.0
	var highest := 0.0
	for frame in 900:
		await process_frame
		var now: Vector3 = app.hero.position
		highest = maxf(highest,now.y)
		lowest = minf(lowest,now.y)
		var moved := now.distance_to(last)
		var veil = root.get_node_or_null("Transition")
		var dark: bool = veil != null and veil.veil.modulate.a > 0.6
		if moved < 0.0005 and app.travelling and not dark: still += 1
		else:
			result.stalls = maxi(int(result.stalls),still-8) if still > 8 else int(result.stalls)
			still = 0
		var horizontal := Vector2(now.x-last.x,now.z-last.z).length()
		if app.travelling and not dark and app.hero.external_velocity.length() > 0.1 and horizontal < 0.0002:
			result.slides += 1
		last = now
		if not app.travelling:
			result.done = true
			break
	result.rise = highest-lowest
	result.seconds = (Time.get_ticks_msec()-started)/1000.0
	return result
