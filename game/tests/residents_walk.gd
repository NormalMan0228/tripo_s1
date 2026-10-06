extends SceneTree
## A whole village day for the outdoor residents (scripts/shadow_folk.gd driven by
## scripts/residents.gd), at high time scale on the real islands. Asserts:
##  - the shadows the module keeps "outside" are exactly Residents.outdoors(),
##  - nobody visible outdoors is asleep (beyond a short fade), and every walk in or
##    out ends within TRANSIT_LIMIT,
##  - every appearance is on the door step of the building the shadow left and every
##    disappearance on the door step of the building it enters,
##  - outdoor walkers keep moving, stay on the path network, out of the water and
##    out of the buildings (as tests/shadow_folk_walk.gd),
##  - at night the lights-off buildings are exactly the locked ones,
##  - the schedule + walkers stay inside the CPU budget (profile counters).
## Headless, fixed step:
##   Godot --headless --fixed-fps 60 --path game --script res://tests/residents_walk.gd -- [--seconds-per-hour=12] [--from=0] [--to=24] [--near]
## --near parks the walker by the town green so the door walks run on screen.
## With a window and --capture it also writes artifacts/residents-{day,dusk,night}.png.
const Stub = preload("res://tests/shadow_folk_stub.gd")
const Folk = preload("res://scripts/shadow_folk.gd")
const Figure = preload("res://scripts/shadow_figure.gd")
const Residents = preload("res://scripts/residents.gd")
const Town = preload("res://scripts/town.gd")
const Daylight = preload("res://scripts/daylight.gd")
const STALL_LIMIT := 6.0
## Simulated seconds; the walk itself is real-time (about 1 m/s), only the clock is fast.
const TRANSIT_LIMIT := 240.0
var app: Node3D
var folk: Node3D
var failures: Array[String] = []
var counts := {}

func _initialize() -> void:
	call_deferred("run")

func fail(text: String) -> void:
	if counts.get(text, 0) == 0: print("FAIL ", text)
	counts[text] = counts.get(text, 0)+1
	if counts[text] == 1: failures.append(text)

func run() -> void:
	var per_hour := 12.0
	var from := 0.0
	var to := 24.0
	var near := "--near" in OS.get_cmdline_user_args()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--seconds-per-hour="): per_hour = float(arg.trim_prefix("--seconds-per-hour="))
		if arg.begins_with("--from="): from = float(arg.trim_prefix("--from="))
		if arg.begins_with("--to="): to = float(arg.trim_prefix("--to="))
	seed(20261006)
	var cam := Camera3D.new()
	root.add_child(cam)
	app = Stub.new()
	root.add_child(app)
	app.build(cam)
	for i in 8: await physics_frame
	app.spawn_villagers()
	app.daylight.override_hour = from
	# The walker off the road by the town green (near) or far out at sea.
	var park := Vector2(-36.5, 30.5) if near else Vector2(0, -120)
	app.player.position = Town.point(park, 0.1) if near else Vector3(0, 30, -120)
	cam.position = Vector3(-33, 30, 50)
	folk = Folk.new()
	folk.persist = false
	folk.record_events = true
	app.add_child(folk)
	var started := Time.get_ticks_msec()
	folk.setup(app)
	print("GRAPH_MS ", folk.graph_ms, " (budget 150)")
	if folk.graph_ms > 150: fail("path graph took %d ms" % folk.graph_ms)
	print("SETUP_MS ", Time.get_ticks_msec()-started, " nodes=", folk.paths.points.size(), " walkers=", folk.walkers.size(), " lamps=", folk.lamp_stops.size(), " doors=", folk.door_stops.size())
	check_lights()
	await simulate(from, to, per_hour)
	print("RESIDENTS_WALK ", "FAIL " if not failures.is_empty() else "OK ", failures.size())
	for text in failures: print("  - ", text, " x", counts[text])
	if "--capture" in OS.get_cmdline_user_args() and DisplayServer.get_name() != "headless": await capture()
	quit(1 if not failures.is_empty() else 0)

## Lights off <=> locked, for every building and hour of the night.
func check_lights() -> void:
	var day: int = Residents.clock().day
	var locked_at_night := 0
	for step in 48:
		var h := step*0.5
		if Daylight.sample(h).night < 0.5: continue
		for door in Town.DOORS:
			var state := Residents.building_state(door.room, h, day)
			if state.lights_on != state.enterable: fail("%s at %.1f: lights_on=%s but enterable=%s" % [door.room, h, state.lights_on, state.enterable])
			if not state.enterable:
				locked_at_night += 1
				if str(state.message).is_empty(): fail("%s locked without a message" % door.room)
			if door.room in Residents.PLAYER_ROOMS and not state.enterable: fail("player room %s locked" % door.room)
	print("LIGHTS night samples locked=", locked_at_night)

func simulate(from: float, to: float, per_hour: float) -> void:
	var space: PhysicsDirectSpaceState3D = app.get_world_3d().direct_space_state
	var probe := SphereShape3D.new()
	probe.radius = 0.12
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = probe
	query.collision_mask = 2
	var frames := int((to-from)*per_hour*60.0)
	var stats := {}
	for walker in folk.walkers:
		stats[walker.spec.id] = {"stall":0.0, "max_stall":0.0, "anchor":walker.xz(), "transit":0.0, "max_transit":0.0, "transit_anchor":Vector2.ZERO, "transit_still":0.0, "asleep_seen":0.0, "out_s":0.0, "dist0":walker.stats.distance, "samples":0, "network":0}
	var real := Time.get_ticks_msec()
	Folk.profile = true
	Figure.profile = true
	Folk.profile_us = 0
	Figure.profile_us = 0
	var max_out := 0
	var max_present := 0
	var mismatches := 0
	var last_check_clock := -1.0
	var hour_frames := {}
	for frame in frames:
		app.daylight.override_hour = fposmod(from+frame/(per_hour*60.0), 24.0)
		await physics_frame
		# Right after each schedule tick: the module's outdoor set equals the plan's.
		if folk.clock > last_check_clock and folk.clock > 0.98:
			var planned := {}
			for state in Residents.outdoors(folk.hour, folk.day):
				if Residents.resident(state.id).kind == "shadow": planned[state.id] = true
			var mine := {}
			for walker in folk.walkers:
				if walker.place == "outside": mine[walker.spec.id] = true
			if planned.keys().size() != mine.keys().size() or not planned.keys().all(func(k): return mine.has(k)):
				mismatches += 1
				fail("outdoor set differs from Residents.outdoors() at %.2f h" % folk.hour)
			max_out = maxi(max_out, mine.size())
		last_check_clock = folk.clock
		if frame % 30 != 0: continue
		var present := 0
		for walker in folk.walkers:
			var s: Dictionary = stats[walker.spec.id]
			if not walker.visible:
				s.transit = 0.0
				s.stall = 0.0
				continue
			present += 1
			var state: String = walker.state
			var at: Vector2 = walker.xz()
			var block := Residents.now(walker.spec.id, folk.hour, folk.day)
			var doorway: bool = state in ["door", "emerge", "vanish"] or walker.transit
			if walker.place != "outside" or doorway:
				s.transit += 0.5
				s.max_transit = maxf(s.max_transit, s.transit)
				# A long way home in the walker's sight is fine; standing still on it is not.
				if s.transit <= 0.5 or at.distance_to(s.transit_anchor) > 1.0:
					s.transit_anchor = at
					s.transit_still = 0.0
				else:
					s.transit_still += 0.5
				if s.transit_still > 15.0: fail("%s stuck on its way through a door (state %s at %s)" % [walker.spec.id, state, at])
				if s.transit > TRANSIT_LIMIT: fail("%s took over %.0f s to get through a door" % [walker.spec.id, TRANSIT_LIMIT])
			else:
				s.transit = 0.0
				s.out_s += 0.5
			if block.asleep and walker.fade > 0.05:
				s.asleep_seen += 0.5
				if s.asleep_seen > 3.0 and not doorway: fail("%s outdoors while asleep at %.2f h" % [walker.spec.id, folk.hour])
			else:
				s.asleep_seen = 0.0
			if walker.position.y < Town.SHORE_MIN_Y: fail("%s below the shore line at %s" % [walker.spec.id, at])
			if doorway: continue
			# Walking quality, as tests/shadow_folk_walk.gd.
			s.samples += 1
			var off: float = folk.paths.distance_to_network(at)
			if off < 1.6: s.network += 1
			elif off > s.get("off", 0.0):
				s.off = off
				s.off_at = "%s state=%s activity=%s" % [at, state, walker.activity]
			for door in Town.DOORS:
				if at.distance_to(door.at) < 1.6: fail("%s on the %s door pad while not using it" % [walker.spec.id, door.id])
			query.transform = Transform3D(Basis.IDENTITY, walker.position+Vector3(0, 1.0*walker.height_scale, 0))
			if not space.intersect_shape(query, 1).is_empty(): fail("%s overlaps a building at %s" % [walker.spec.id, at])
			var wants: bool = state in ["walk", "travel"] and walker.yield_time == 0.0 and walker.greet_left <= 0.0
			if wants and at.distance_to(s.anchor) < 0.3:
				s.stall += 0.5
				s.max_stall = maxf(s.max_stall, s.stall)
				if s.stall > STALL_LIMIT: fail("%s stalled %.1f s at %s" % [walker.spec.id, s.stall, at])
			else:
				s.stall = 0.0
				s.anchor = at
		max_present = maxi(max_present, present)
		var hour_slot := int(app.daylight.override_hour)
		hour_frames[hour_slot] = maxi(hour_frames.get(hour_slot, 0), present)
	var physics_frames := frames
	Folk.profile = false
	Figure.profile = false
	var total_ms := float(Folk.profile_us+Figure.profile_us)/1000.0
	print("SIM %.1f-%.1f h at %.0f s/h: %d frames in %d ms" % [from, to, per_hour, frames, Time.get_ticks_msec()-real])
	print("PERF module=%.3f ms/frame walkers=%.3f ms/frame total=%.3f ms/frame max_outside=%d max_visible=%d" % [Folk.profile_us/1000.0/physics_frames, Figure.profile_us/1000.0/physics_frames, total_ms/physics_frames, max_out, max_present])
	print("VISIBLE_BY_HOUR ", hour_frames)
	if total_ms/physics_frames > 0.6: fail("schedule + walkers cost %.3f ms/frame (budget 0.6)" % (total_ms/physics_frames))
	# Door events: every appearance / disappearance on the right door step.
	var appear := 0
	var vanish := 0
	for event in folk.events:
		var door: Dictionary = folk.door_for(event.building)
		if door.is_empty():
			fail("%s %s without a door (%s)" % [event.id, event.kind, event.building])
			continue
		var gap: float = Vector2(event.at).distance_to(door.step)
		if event.kind == "appear":
			appear += 1
			if gap > 1.0: fail("%s appeared %.1f m from the %s door" % [event.id, gap, event.building])
		else:
			vanish += 1
			if gap > 2.6: fail("%s vanished %.1f m from the %s door" % [event.id, gap, event.building])
	# Each disappearance is into a building the plan had the shadow in, or heading for.
	for event in folk.events:
		if event.kind != "vanish": continue
		var at_hour := Residents.now(event.id, event.hour, folk.day)
		var before := Residents.now(event.id, fposmod(event.hour+0.08, 24.0), folk.day)
		if at_hour.place != event.building and before.place != event.building: fail("%s went into %s but its plan says %s" % [event.id, event.building, at_hour.place])
	print("DOORS appear=", appear, " vanish=", vanish)
	for walker in folk.walkers:
		var s: Dictionary = stats[walker.spec.id]
		var network: float = float(s.network)/maxf(1.0, s.samples)
		print("WALKER %-11s out=%5.0fs dist=%6.1fm path=%3.0f%% max_stall=%.1fs max_transit=%.1fs slips=%d water=%d" % [walker.spec.id, s.out_s, walker.stats.distance-s.dist0, network*100.0, s.max_stall, s.max_transit, walker.stats.slips, walker.stats.water_resets])
		if s.has("off_at"): print("    furthest off the paths %.1f m at %s" % [s.off, s.off_at])
		if s.samples > 20 and network < 0.85: fail("%s spent only %.0f%% on the path network" % [walker.spec.id, network*100.0])
		if walker.stats.water_resets > 0: fail("%s stepped into the water %d times" % [walker.spec.id, walker.stats.water_resets])
	print("MISMATCH ticks=", mismatches)

## Day, dusk and night views of the town green with the window lights.
func capture() -> void:
	var map: Node3D = app.town.map
	var world := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	world.environment = env
	root.add_child(world)
	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = true
	root.add_child(sun)
	Town.Archipelago.apply_lighting(env, sun)
	app.daylight.attach(env, sun, map)
	var dressing: Node3D = preload("res://scripts/building_dressing.gd").new()
	app.add_child(dressing)
	dressing.setup(app)
	var camera: Camera3D = app.camera
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 34.0
	camera.far = 400.0
	camera.current = true
	for view in [["day", 12.5, Vector2(-36, 34)], ["dusk", 19.2, Vector2(-36, 34)], ["night", 22.5, Vector2(-50, 38)]]:
		app.daylight.override_hour = view[1]
		app.daylight.refresh(true)
		folk.clock = 0.0
		var focus := Town.point(view[2], 0.0)
		camera.position = focus+Vector3(0, 32, 32)
		camera.look_at(focus)
		for i in 90: await physics_frame
		dressing._until = 0.0
		for i in 10: await process_frame
		await RenderingServer.frame_post_draw
		var out := ProjectSettings.globalize_path("res://../artifacts/residents-%s.png" % view[0])
		root.get_texture().get_image().save_png(out)
		var visible: Array = folk.walkers.filter(func(w): return w.visible).map(func(w): return w.spec.id)
		print("CAPTURE ", out, " hour=", view[1], " out=", visible)
