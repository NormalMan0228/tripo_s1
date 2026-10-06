extends SceneTree
## Walk check for scripts/shadow_folk.gd on the real island village (town.gd builds
## the archipelago and roads). Simulates the shadows for several minutes by day and
## by night with the walker out of the way, then checks that every shadow:
##  - keeps moving (no stall longer than STALL_LIMIT s while it means to walk),
##  - never stands inside a building (layer 2 at chest height) or on a door pad,
##  - never drops below the shore line (TownLayout.SHORE_MIN_Y),
##  - spends most of its time on the roads / path network.
## Then: a shadow blocked by the walker gets past, every shadow answers E with a
## dialogue whose choices all run, the letter / hoe favours finish, and a
## "follow me" walk reaches its spot. Headless, fast with a fixed step:
##   Godot --headless --fixed-fps 60 --path game --script res://tests/shadow_folk_walk.gd -- [--minutes=5]
const Stub = preload("res://tests/shadow_folk_stub.gd")
const Folk = preload("res://scripts/shadow_folk.gd")
const Town = preload("res://scripts/town.gd")
const Roads = preload("res://scripts/roads.gd")
const STALL_LIMIT := 6.0
const SAMPLE := 0.5
var app: Node3D
var folk: Node3D
var failures: Array[String] = []
var stats: Dictionary = {}
var time := 0.0

func _initialize() -> void:
	call_deferred("run")

func fail(text: String) -> void:
	failures.append(text)
	print("FAIL ", text)

func run() -> void:
	var minutes := 5.0
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--minutes="): minutes = float(arg.trim_prefix("--minutes="))
	seed(20261006)
	var cam := Camera3D.new()
	root.add_child(cam)
	app = Stub.new()
	root.add_child(app)
	app.build(cam)
	for i in 8: await physics_frame
	app.spawn_villagers()
	folk = Folk.new()
	folk.persist = false
	app.add_child(folk)
	var started := Time.get_ticks_msec()
	folk.setup(app)
	print("SETUP_MS ", Time.get_ticks_msec()-started, " nodes=", folk.paths.points.size(), " edges=", folk.paths.edges().size(), " walkers=", folk.walkers.size(), " lanes_moved=", folk.lanes_moved)
	check_graph()
	for walker in folk.walkers:
		stats[walker.spec.id] = {"samples":0,"road":0,"network":0,"max_stall":0.0,"stall":0.0,"anchor":walker.xz(),"inside":0,"door":0,"low":0,"islands":{},"min_y":INF,"min_y_at":Vector2.ZERO,"present_s":0.0,"stall_at":Vector2.ZERO,"off":0.0,"off_at":Vector2.ZERO,"air":0,"lift":0.0,"lift_at":Vector2.ZERO}
	# Camera far away so every shadow runs its reduced animation rate too.
	cam.position = Vector3(-33, 30, 50)
	var half := minutes*30.0
	app.daylight.override_hour = 12.0
	folk.clock = 0.0
	await simulate(half, "day")
	app.daylight.override_hour = 22.0
	folk.clock = 0.0
	await simulate(half, "night")
	report()
	await blocking_test()
	await interaction_test()
	await favour_test()
	await follow_test()
	print("SHADOW_FOLK_WALK ", "FAIL " if not failures.is_empty() else "OK ", failures.size())
	for text in failures: print("  - ", text)
	quit(1 if not failures.is_empty() else 0)

func check_graph() -> void:
	var paths = folk.paths
	# Every node reachable from the town green: the islands are joined by bridges.
	var start: int = paths.nearest(Town.SPAWN)
	var seen := {start:true}
	var open: Array = [start]
	while not open.is_empty():
		var node: int = open.pop_back()
		for next in paths.links[node]:
			if not seen.has(next):
				seen[next] = true
				open.append(next)
	var lonely := 0
	for i in paths.points.size():
		if not seen.has(i) and not paths.links[i].is_empty(): lonely += 1
	print("GRAPH connected=", seen.size(), "/", paths.points.size(), " porches=", paths.faces.size(), " spots=", paths.spot_names.values())
	if lonely > 0: fail("%d path nodes are not connected to the town green" % lonely)
	for node in paths.points.size():
		for door in Town.DOORS:
			if paths.points[node].distance_to(door.at) < 2.0: fail("path node %d at %s sits on door pad %s" % [node, paths.points[node], door.id])

func simulate(seconds: float, label: String) -> void:
	var space: PhysicsDirectSpaceState3D = app.get_world_3d().direct_space_state
	var probe := SphereShape3D.new()
	probe.radius = 0.12
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = probe
	query.collision_mask = 2
	var steps := int(seconds*60.0)
	var sample_every := int(SAMPLE*60.0)
	var real := Time.get_ticks_msec()
	for step in steps:
		await physics_frame
		time += 1.0/60.0
		if step % sample_every != 0: continue
		for walker in folk.walkers:
			var s: Dictionary = stats[walker.spec.id]
			if not walker.present or walker.state == "hidden": continue
			# Walking in or out of a door is checked by tests/residents_walk.gd.
			if walker.state in ["door", "emerge", "vanish"] or walker.transit: continue
			s.present_s += SAMPLE
			s.samples += 1
			if walker.stay or walker.activity in ["deliver", "light_lamps"]: s.settled = true
			var at: Vector2 = walker.xz()
			if Roads.on_road(at): s.road += 1
			var off: float = folk.paths.distance_to_network(at)
			if off < 1.1: s.network += 1
			if off > s.off:
				s.off = off
				s.off_at = at
			s.islands[preload("res://scripts/minimap.gd").island_name(at)] = true
			if walker.position.y < s.min_y:
				s.min_y = walker.position.y
				s.min_y_at = at
			if walker.position.y < Town.SHORE_MIN_Y: s.low += 1
			for door in Town.DOORS:
				if at.distance_to(door.at) < 1.9: s.door += 1
			# Feet near the ground (or a deck): never floating or flung into the air.
			# A few rays under the capsule: pier decks are planks with gaps between them.
			var floor_y := -10.0
			for offset in [Vector3.ZERO, Vector3(0.14, 0, 0), Vector3(-0.14, 0, 0), Vector3(0, 0, 0.14), Vector3(0, 0, -0.14)]:
				var from: Vector3 = walker.position+offset+Vector3.UP*0.5
				var ground := space.intersect_ray(PhysicsRayQueryParameters3D.create(from, from+Vector3.DOWN*30.0, 1|2|8|16))
				if not ground.is_empty(): floor_y = maxf(floor_y, ground.position.y)
			var lift: float = walker.position.y-floor_y
			if lift > s.lift:
				s.lift = lift
				s.lift_at = at
			if lift > 1.2: s.air += 1
			query.transform = Transform3D(Basis.IDENTITY, walker.position+Vector3(0, 1.0*walker.height_scale, 0))
			var touching := space.intersect_shape(query, 1)
			if not touching.is_empty():
				s.inside += 1
				if s.inside % 20 == 1: print("INSIDE ", walker.spec.id, " at ", walker.position.snapped(Vector3.ONE*0.01), " hit ", touching[0].collider.get_parent().name, " state ", walker.state)
			# A stall: wants to walk (walk/lead, not yielding, greeting or waiting) but stays put.
			var wants: bool = walker.state in ["walk", "lead", "travel"] and walker.yield_time == 0.0 and walker.greet_left <= 0.0 and not walker.lead_waiting
			if wants and at.distance_to(s.anchor) < 0.3:
				s.stall += SAMPLE
				if s.stall > s.max_stall:
					s.max_stall = s.stall
					s.stall_at = at
			else:
				s.stall = 0.0
				s.anchor = at
	print("SIM ", label, " ", seconds, "s in ", Time.get_ticks_msec()-real, " ms")

func report() -> void:
	var total_samples := 0
	var total_road := 0
	var total_network := 0
	for walker in folk.walkers:
		var s: Dictionary = stats[walker.spec.id]
		var w: Dictionary = walker.stats
		var road := float(s.road)/maxf(1.0, s.samples)
		var network := float(s.network)/maxf(1.0, s.samples)
		total_samples += s.samples
		total_road += s.road
		total_network += s.network
		print("WALKER %-11s out=%5.0fs dist=%6.1fm nodes=%3d road=%3.0f%% path=%3.0f%% max_stall=%.1fs side=%d back=%d rejoin=%d slip=%d water=%d fast=%d inside=%d door=%d min_y=%.2f islands=%s" % [walker.spec.id, s.present_s, w.distance, w.arrivals, road*100.0, network*100.0, s.max_stall, w.sidesteps, w.reversals, w.rejoins, w.slips, w.water_resets, w.overspeed, s.inside, s.door, s.min_y, ",".join(PackedStringArray(s.islands.keys()))])
		print("    stall_at=%s off=%.1fm at %s min_y_at=%s max_lift=%.2fm at %s" % [s.stall_at, s.off, s.off_at, s.min_y_at, s.lift, s.lift_at])
		# residents.gd keeps some shadows indoors at both test hours (shop owners at work).
		if s.samples == 0:
			print("    (indoors at both hours by the schedule)")
			continue
		if s.max_stall > STALL_LIMIT: fail("%s stalled %.1f s" % [walker.spec.id, s.max_stall])
		if s.low > 0: fail("%s went below the shore line (%d samples)" % [walker.spec.id, s.low])
		if s.inside > 0: fail("%s overlapped a building %d times" % [walker.spec.id, s.inside])
		if s.door > 0: fail("%s stood on a door pad %d times" % [walker.spec.id, s.door])
		if s.air > 0: fail("%s was more than 1.2 m off the ground %d times" % [walker.spec.id, s.air])
		if network < 0.9: fail("%s spent only %.0f%% on the path network" % [walker.spec.id, network*100.0])
		# Settled workers (pier, gazebo) stay put; round stops hop while the walker is far.
		if s.get("settled", false): pass
		elif w.distance < s.present_s*0.25: fail("%s barely moved (%.1f m in %.0f s)" % [walker.spec.id, w.distance, s.present_s])
		if w.slips > 1: fail("%s needed %d slips" % [walker.spec.id, w.slips])
		if w.water_resets > 0: fail("%s stepped into the water %d times" % [walker.spec.id, w.water_resets])
		if w.overspeed > 30: fail("%s moved faster than twice its pace %d times" % [walker.spec.id, w.overspeed])
	print("TOTAL road=%.0f%% path=%.0f%%" % [100.0*total_road/maxf(1, total_samples), 100.0*total_network/maxf(1, total_samples)])
	if float(total_road)/maxf(1, total_samples) < 0.7: fail("shadows spent under 70% of their time on roads")

## A walker standing on the path: the shadow greets, waits, then steps around.
func blocking_test() -> void:
	app.daylight.override_hour = 12.0
	var subject: Node3D
	var best := 0.0
	for walker in folk.walkers:
		if not walker.present or walker.state != "walk": continue
		var left: float = walker.xz().distance_to(folk.paths.points[walker.target_node])
		if left > best:
			best = left; subject = walker
	if subject == null or best < 6.0:
		print("BLOCK skipped (no long walk in progress)")
		return
	var target: int = subject.target_node
	var ahead: Vector2 = subject.xz()+(folk.paths.points[target]-subject.xz()).normalized()*3.0
	app.player.position = Town.point(ahead, 0.05)
	var yields_before: int = subject.stats.yields
	var arrived := false
	for frame in 60*25:
		await physics_frame
		if subject.at_node == target or subject.xz().distance_to(folk.paths.points[target]) < 0.6:
			arrived = true
			break
	print("BLOCK ", subject.spec.id, " yields=", subject.stats.yields-yields_before, " greets=", subject.stats.greets, " passed=", arrived)
	if subject.stats.yields-yields_before < 1 and subject.stats.greets < 1: fail("blocked shadow never noticed the walker")
	if not arrived: fail("%s could not get past the walker" % subject.spec.id)
	app.player.position = Vector3(0, 30, -120)
	for frame in 30: await physics_frame

## E on every shadow opens a dialogue; every choice (and nested choice) runs.
func interaction_test() -> void:
	var opened := 0
	var checked := 0
	for hour in [12.0, 22.0]:
		app.daylight.override_hour = hour
		# Let the schedule settle: who is out comes out of its door and fades in.
		folk.clock = 0.0
		for i in 150: await physics_frame
		for walker in folk.walkers:
			if not walker.present or walker.place != "outside" or walker.fade < 0.6: continue
			checked += 1
			# Stand right on the shadow: another one may be just beside it.
			app.player.position = walker.position
			var entry: Dictionary = folk.closest(app.player.position)
			if entry.get("walker") != walker:
				fail("closest() missed %s (got %s)" % [walker.spec.id, entry])
				continue
			if not "와 대화" in str(entry.prompt): fail("odd prompt %s" % entry.prompt)
			var before: int = app.dialogues.size()
			folk.interact(entry)
			if app.dialogues.size() == before:
				fail("%s opened no dialogue" % walker.spec.id)
				continue
			opened += 1
			var dialogue: Dictionary = app.dialogues.back()
			if not ResourceLoader.exists(dialogue.cast): fail("portrait missing: %s" % dialogue.cast)
			run_choices(dialogue, 0)
			await physics_frame
	print("TALK checked=", checked, " opened=", opened, " dialogues=", app.dialogues.size(), " toasts=", app.messages.size())
	app.player.position = Vector3(0, 30, -120)

func run_choices(dialogue: Dictionary, depth: int) -> void:
	for choice in dialogue.choices:
		var action: Callable = choice[1]
		if not action.is_valid(): continue
		# The "follow me" walk is tested on its own.
		if str(choice[0]) in [TranslationServer.translate("따라간다")]: continue
		var before: int = app.dialogues.size()
		action.call()
		if depth < 2 and app.dialogues.size() > before: run_choices(app.dialogues.back(), depth+1)

func favour_test() -> void:
	# Letter: accept, then walk the walker to the addressee.
	var postman: Node3D = walker_named("postman")
	folk.errands.erase("letter")
	folk.done_today.clear()
	folk.letter(postman)
	if not folk.errands.has("letter"): fail("postman gave no letter")
	else:
		var target: Dictionary = folk.letter_target()
		app.player.position = Town.point(target.at+Vector2(1.5, 0), 0.05)
		for frame in 10: await process_frame
		if folk.errands.has("letter"): fail("letter was not delivered")
		print("LETTER delivered to ", target.title, ": ", app.messages.back())
	# Hoe: ask, find it, pick it up, hand it back.
	var farmer: Node3D = walker_named("farmer")
	farmer.set_present(true); farmer.fade = 1.0; farmer.visible = true
	folk.errands.erase("hoe")
	folk.ask_hoe(farmer)
	if not is_instance_valid(folk.dropped): fail("farmer dropped no hoe")
	else:
		var spot: Vector3 = folk.dropped.position
		var island: String = preload("res://scripts/minimap.gd").island_name(Vector2(spot.x, spot.z))
		app.player.position = spot+Vector3(0.6, 0, 0)
		var entry: Dictionary = folk.closest(app.player.position)
		if entry.get("item", "") != "hoe": fail("hoe not offered by closest(): %s" % entry)
		else: folk.interact(entry)
		if folk.errands.get("hoe", "") != "carried": fail("hoe not picked up")
		app.player.position = farmer.position+Vector3(1.0, 0, 0)
		folk.interact(folk.closest(app.player.position))
		if folk.done_today.get("farmer", "") == "": fail("hoe not returned")
		print("HOE found at ", Vector2(spot.x, spot.z), " (", island, ") ground_y=", snappedf(spot.y, 0.01), " returned=", folk.done_today.has("farmer"))
	# Fish: with and without a catch.
	app.life.state = {"bag":{"perch":1}}
	folk.show_fish(walker_named("fisher"))
	print("FISH ", app.dialogues.back().lines[0])
	app.player.position = Vector3(0, 30, -120)
	for frame in 30: await physics_frame

## The kid leads the walker to the pond pier; the walker trails 2 m behind.
func follow_test() -> void:
	app.daylight.override_hour = 12.0
	folk.clock = 0.0
	for i in 150: await physics_frame
	# The kid if it is out playing, else any shadow that is out and walking about.
	var kid: Node3D = walker_named("kid")
	if kid.place != "outside" or not kid.present or kid.fade < 0.9:
		for walker in folk.walkers:
			if walker.place == "outside" and walker.present and walker.fade >= 0.9 and not walker.stay and folk.pick_spot(walker) >= 0:
				kid = walker
				break
	print("FOLLOW leader ", kid.spec.id)
	app.player.position = kid.position+Vector3(1.0, 0, 0)
	folk.follow(kid)
	var go: Callable = app.dialogues.back().choices[0][1]
	go.call()
	if kid.state != "lead":
		fail("kid did not start leading (state %s)" % kid.state)
		return
	var length: float = folk.paths.route_length(kid.lead_route)
	var count: int = app.messages.size()
	var finished := false
	var waited := 0
	for frame in 60*150:
		await physics_frame
		# Trail the shadow, but lag far behind once to make it wait.
		var behind: Vector2 = kid.xz()-Vector2(sin(kid.visual.rotation.y), cos(kid.visual.rotation.y))*2.0
		if frame > 60*8 and frame < 60*14:
			if kid.lead_waiting: waited += 1
		else:
			app.player.position = Town.point(behind, 0.05)
		if frame == 60*8: app.player.position = Town.point(kid.xz()+Vector2(12, 0), 0.05)
		if app.messages.size() > count and "숨은 장소" in app.messages.back():
			finished = true
			break
	print("FOLLOW kid route=", snappedf(length, 0.1), "m finished=", finished, " waited_frames=", waited, " spot=", folk.paths.spot_names.get(kid.at_node, "?"), " msg=", app.messages.back())
	if not finished:
		print("    kid state=%s at=%s at_node=%d target=%d route=%s leader=%s place=%s" % [kid.state, kid.xz(), kid.at_node, kid.target_node, kid.lead_route, folk.leader == kid, kid.place])
		fail("follow-me walk never arrived")

func walker_named(id: String) -> Node3D:
	for walker in folk.walkers:
		if walker.spec.id == id: return walker
	return null
