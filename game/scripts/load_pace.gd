extends RefCounted
## Work done under the loading card, paced so the card keeps moving (transition.gd draws it).
## While the veil covers the screen, `await LoadPace.step()` between pieces of a long build hands
## the frame back once this frame has spent BUDGET_USEC on work. Resources the next place needs
## load on worker threads: want() them as early as possible, fetch() them where they are used.
## Builds say how far they are with done(), which fills the ring around the card's star seed.
## Uncovered (no veil: tools, a fade-free rebuild) or without a window (headless runs: no card to
## keep moving) nothing waits and builds run in one go, as before.

## Work per frame under the card (the card and the hidden world still draw after it).
const BUDGET_USEC := 9000
## Set (cover()) by transition.gd while the veil fully covers the screen.
static var covered := false
static var windowed := DisplayServer.get_name() != "headless"
## When this frame's processing began (transition.gd marks it on every process_frame and pumps).
static var frame_from := 0
## Paths waiting for a worker thread, the ones loading, and the loaded ones held until the build
## that wanted them ends. In the Compatibility renderer a finished load's textures and meshes reach
## the GPU on the main thread at the next frame, so many loads started together landed in one frame
## of seconds. A few at a time (max_loads, each one whole resource on its own worker) they spread
## over frames; with only one, the worker sat idle until the next frame started the next load
## (up to a frame between every two of ~100 resources).
static var queue: Array[String] = []
static var loading: Array[String] = []
static var held: Dictionary = {}
## --load-threads=N: loads in flight (default 2).
static var max_loads := _arg_int("--load-threads=", 2)
## The progress shown (0..1, < 0 for none) and the share of it the current stage reports into.
static var shown := -1.0
static var span := Vector2(0.0, 1.0)
## --log-load: pieces of work that held a frame past twice the budget, to find what still stutters.
static var log_slow := "--log-load" in OS.get_cmdline_user_args()
static var last_step := 0
static var last_what := ""
static var work_end := 0
## --load-phases: where the frames under the card went, in ms by phase (tests/loading_frames.gd
## reads and clears `phases` per change of place). Off, the checks below cost one bool each.
static var phases_on := "--load-phases" in OS.get_cmdline_user_args()
static var phases := {}
## This frame: paced work done so far (usec), and whether the build waited for a worker load.
static var frame_work := 0
static var frame_waited := false
## What a frame spent only waiting counts as (boot.gd: the game's scripts being read).
static var wait_phase := "waiting for file reads"
## The build released its loads (LoadPace.release): later frames under the card are its first renders.
static var built := false

## transition.gd at each process_frame: starts this frame's clock and the next threaded load. With
## --log-load a long frame under the card is printed with the share the paced work had in it.
static func frame_began() -> void:
	var now := Time.get_ticks_usec()
	if log_slow and covered and frame_from > 0 and now-frame_from > 50000:
		var work := maxi(work_end-frame_from, 0)
		print("LOAD_FRAME %6.1f ms: paced work %5.1f, other %6.1f (loading %s)" % [(now-frame_from)/1000.0, work/1000.0, (now-frame_from-work)/1000.0, ", ".join(loading.map(func(path): return path.get_file()))])
	if phases_on and covered and frame_from > 0: _account(now-frame_from)
	frame_from = now
	work_end = now
	frame_work = 0
	frame_waited = false
	pump()

## --log-load: prints how long since the last mark (the stages of a build).
static var last_mark := 0
static func mark(what: String) -> void:
	if not log_slow: return
	var now := Time.get_ticks_msec()
	if last_mark > 0: print("LOAD_MARK %6d ms %s" % [now-last_mark, what])
	last_mark = now

## Gives the frame back when this frame's work is over budget; a no-op while uncovered.
static func step(what := "") -> void:
	if not covered: return
	var now := Time.get_ticks_usec()
	if log_slow or phases_on:
		var chunk := now-maxi(last_step, frame_from)
		if log_slow and chunk > 2*BUDGET_USEC: print("LOAD_SLOW %6.1f ms after %s (before %s)" % [chunk/1000.0, last_what, what])
		if phases_on:
			add_phase(phase_of(last_what), chunk)
			frame_work += chunk
		last_what = what
		last_step = now
	if now-frame_from < BUDGET_USEC: return
	work_end = Time.get_ticks_usec()
	await (Engine.get_main_loop() as SceneTree).process_frame

## The veil fully covers the screen (or no longer does).
static func cover(on: bool) -> void:
	covered = on and windowed

## Queues these resources for the worker threads (missing, queued or loaded paths are skipped).
static func want(paths: Array) -> void:
	for path: String in paths:
		if path.is_empty() or pending(path) or held.has(path) or ResourceLoader.has_cached(path) or not ResourceLoader.exists(path): continue
		queue.append(path)
	pump()

## Queued or loading.
static func pending(path: String) -> bool:
	return not path.is_empty() and (loading.has(path) or queue.has(path))

static func _arg_int(prefix: String, fallback: int) -> int:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with(prefix): return maxi(1, arg.trim_prefix(prefix).to_int())
	return fallback

## Collects the finished loads and starts the next ones (every frame, from transition.gd).
static func pump() -> void:
	for path: String in loading.duplicate():
		var status := ResourceLoader.load_threaded_get_status(path)
		if status == ResourceLoader.THREAD_LOAD_IN_PROGRESS: continue
		var resource := ResourceLoader.load_threaded_get(path) if status == ResourceLoader.THREAD_LOAD_LOADED else null
		if resource != null: held[path] = resource
		loading.erase(path)
	while loading.size() < max_loads and not queue.is_empty():
		var path: String = queue.pop_front()
		if ResourceLoader.has_cached(path): continue
		# One worker for the whole resource: its textures (4096² BPTC, ~20 MB each with mipmaps) then
		# finish one by one and their GPU uploads land in different frames instead of the same one.
		if ResourceLoader.load_threaded_request(path, "", false) == OK: loading.append(path)

## The resource at `path`: covered, a queued one goes next and the card turns until it is in.
static func fetch(path: String) -> Resource:
	if covered and pending(path):
		if not loading.has(path):
			queue.erase(path)
			queue.push_front(path)
		while covered and pending(path):
			pump()
			if pending(path):
				frame_waited = true
				await (Engine.get_main_loop() as SceneTree).process_frame
				frame_waited = true
				last_step = Time.get_ticks_usec()
	return take(path)

## The resource at `path` now (waiting for it if it is the one loading).
static func take(path: String) -> Resource:
	var from := Time.get_ticks_usec() if phases_on else 0
	if loading.has(path):
		var resource := ResourceLoader.load_threaded_get(path)
		loading.erase(path)
		pump()
		if phases_on: _blocked(from)
		if resource != null:
			held[path] = resource
			return resource
	queue.erase(path)
	if held.has(path): return held[path]
	var loaded := load(path)
	if phases_on: _blocked(from)
	return loaded

## Waits until every queued load is in, reporting their share as progress (0..1 of the span).
static func settle() -> void:
	var total := queue.size()+loading.size()
	while covered and (not queue.is_empty() or not loading.is_empty()):
		pump()
		done(1.0-(queue.size()+loading.size())/maxf(total, 1.0))
		if not queue.is_empty() or not loading.is_empty():
			frame_waited = true
			await (Engine.get_main_loop() as SceneTree).process_frame
			frame_waited = true
			last_step = Time.get_ticks_usec()
	done(1.0)

## The build is done: drops the queued loads nobody fetched and the references held for it (the
## built nodes keep what they use). Loads still running are collected and let go at the next release.
static func release() -> void:
	queue.clear()
	held.clear()
	if phases_on:
		# The work since the last step belongs to it; frames after this are the place's first renders.
		var now := Time.get_ticks_usec()
		var chunk := now-maxi(last_step, frame_from)
		add_phase(phase_of(last_what), chunk)
		frame_work += chunk
		last_step = now
		last_what = "after build"
		built = true

## --load-phases: the phase a paced piece of work counts for.
static func phase_of(what: String) -> String:
	if what == "ground pads": return "pad levelling"
	if what == "after build": return "after build"
	if "collid" in what or "collision" in what or "rock wall" in what or "ramp" in what: return "collision"
	return "node assembly"

static func add_phase(name: String, usec: int) -> void:
	if usec > 0: phases[name] = phases.get(name, 0.0)+usec/1000.0

## A load the main thread waited for in one call (load_threaded_get of a running load, or load()).
static func _blocked(from: int) -> void:
	var spent := Time.get_ticks_usec()-from
	add_phase("file read (main thread)", spent)
	frame_work += spent
	last_step = Time.get_ticks_usec()

## One frame under the card (usec from its start to the next): the paced work in it is already
## counted; the rest is waiting for worker-thread file reads (a frame the build only waited in),
## the renderer's CPU time, or the engine's own work (resources reaching the GPU: in the
## Compatibility renderer a loaded texture or mesh is uploaded on the main thread; physics; sync).
static func _account(length: int) -> void:
	var rest := maxf(length-frame_work, 0.0)/1000.0
	var viewport := (Engine.get_main_loop() as SceneTree).root.get_viewport_rid()
	if not phases.has("_measuring"):
		RenderingServer.viewport_set_measure_render_time(viewport, true)
		phases["_measuring"] = true
	var render := minf(rest, RenderingServer.viewport_get_measured_render_time_cpu(viewport)+RenderingServer.get_frame_setup_time_cpu())
	phases["frames"] = phases.get("frames", 0)+1
	phases["longest frame"] = maxf(phases.get("longest frame", 0.0), length/1000.0)
	if built:
		add_phase("first render", length)
		return
	if frame_waited and frame_work < 1000:
		add_phase(wait_phase, int(rest*1000.0))
		return
	add_phase("render", int(render*1000.0))
	add_phase("GPU upload + engine", int((rest-render)*1000.0))

## --load-phases: this change of place's phases (ms) and a fresh count for the next one.
static func take_phases() -> Dictionary:
	var result := phases.duplicate()
	result.erase("_measuring")
	phases = {"_measuring": true} if phases.has("_measuring") else {}
	built = false
	last_what = ""
	return result

## Under the card, a trimesh collider for `mesh` as MeshInstance3D.create_trimesh_collision() makes
## it (a StaticBody3D "<mesh>_col" holding the shape, under the mesh), in pieces a frame apart:
## reading the faces, then the shape's BVH. The node gets the shape while it is still empty, so its
## debug sync (debug builds) has nothing to rebuild; in one go that held a frame 60-300 ms per big mesh.
## `faces`: 3 points a triangle, the mesh's own when empty. (Physics calls from worker threads are
## queued to the main thread, so threads would not take this work off it.)
static func collide(mesh: MeshInstance3D, faces := PackedVector3Array(), layer := 1, mask := 1) -> void:
	if faces.is_empty(): faces = mesh.mesh.get_faces()
	if faces.is_empty(): return
	await step("collider shape")
	if not is_instance_valid(mesh): return
	var shape := ConcavePolygonShape3D.new()
	var holder := CollisionShape3D.new()
	holder.shape = shape
	shape.set_faces(faces)
	var body := StaticBody3D.new()
	body.name = String(mesh.name)+"_col"
	body.collision_layer = layer
	body.collision_mask = mask
	body.add_child(holder, true)
	mesh.add_child(body, true)
	if mesh.owner != null:
		body.owner = mesh.owner
		holder.owner = mesh.owner
	await step("collider")

## A collider for `mesh` from precomputed faces (maps/archipelago/island_bake.gd: simplified and cut
## into chunks of a few thousand triangles): a StaticBody3D "<mesh>_col" with one shape per chunk,
## made a step apart (each a few ms instead of one 30-130 ms trimesh). `shapes` holds the shapes
## another instance of the same prop already made (shared, nothing to build); empty, they are made
## here and appended to it. `body`: the body to fill (the baked island keeps its bodies), else a new
## one under `mesh`. Uncovered it runs in one go.
static func collide_chunks(mesh: Node3D, chunks: Array, layer := 1, mask := 1, shapes: Array = [], body: StaticBody3D = null) -> void:
	if body == null:
		body = StaticBody3D.new()
		body.name = String(mesh.name)+"_col"
		body.collision_layer = layer
		body.collision_mask = mask
		mesh.add_child(body, true)
		if mesh.owner != null: body.owner = mesh.owner
	var make := shapes.is_empty()
	for index in chunks.size():
		var holder := CollisionShape3D.new()
		var shape: ConcavePolygonShape3D = ConcavePolygonShape3D.new() if make else shapes[index]
		holder.shape = shape
		if make:
			shape.set_faces(chunks[index])
			shapes.append(shape)
		body.add_child(holder, true)
		if mesh.owner != null: holder.owner = mesh.owner
		if make:
			await step("collider chunk")
			if not is_instance_valid(body): return

## Waits `count` physics steps with `node` in the tree. A map finishing itself a few steps after
## its build may be taken out of the tree meanwhile (kept for the next visit while a room is open);
## it then goes on once it is back instead of failing without a tree.
static func physics_frames(node: Node, count: int) -> void:
	var left := count
	while left > 0 or not node.is_inside_tree():
		if not node.is_inside_tree():
			await node.tree_entered
			continue
		await node.get_tree().physics_frame
		left -= 1

## This stage is `fraction` (0..1) done; shown within the current span, never going back.
static func done(fraction: float) -> void:
	if not covered: return
	shown = maxf(shown, span.x+(span.y-span.x)*clampf(fraction, 0.0, 1.0))

## Narrows the next done() reports to [from, to] of the current span; returns the span to restore.
static func narrow(from: float, to: float) -> Vector2:
	var previous := span
	var width := span.y-span.x
	span = Vector2(span.x+width*from, span.x+width*to)
	return previous

## A new loading card: no progress yet, the whole ring to fill.
static func reset() -> void:
	shown = -1.0
	span = Vector2(0.0, 1.0)
