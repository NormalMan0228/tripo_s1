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
## Paths waiting for a worker thread, the one loading, and the loaded ones held until the build
## that wanted them ends. One load runs at a time: in the Compatibility renderer a finished load's
## textures and meshes reach the GPU on the main thread at the next frame, so loads started
## together landed in one frame of seconds; one by one they spread over frames of a few ms.
static var queue: Array[String] = []
static var running := ""
static var held: Dictionary = {}
## The progress shown (0..1, < 0 for none) and the share of it the current stage reports into.
static var shown := -1.0
static var span := Vector2(0.0, 1.0)
## --log-load: pieces of work that held a frame past twice the budget, to find what still stutters.
static var log_slow := "--log-load" in OS.get_cmdline_user_args()
static var last_step := 0
static var last_what := ""
static var work_end := 0

## transition.gd at each process_frame: starts this frame's clock and the next threaded load. With
## --log-load a long frame under the card is printed with the share the paced work had in it.
static func frame_began() -> void:
	var now := Time.get_ticks_usec()
	if log_slow and covered and frame_from > 0 and now-frame_from > 50000:
		var work := maxi(work_end-frame_from, 0)
		print("LOAD_FRAME %6.1f ms: paced work %5.1f, other %6.1f (loading %s)" % [(now-frame_from)/1000.0, work/1000.0, (now-frame_from-work)/1000.0, running.get_file()])
	frame_from = now
	work_end = now
	pump()

## Gives the frame back when this frame's work is over budget; a no-op while uncovered.
static func step(what := "") -> void:
	if not covered: return
	var now := Time.get_ticks_usec()
	if log_slow:
		var chunk := now-maxi(last_step, frame_from)
		if chunk > 2*BUDGET_USEC: print("LOAD_SLOW %6.1f ms after %s (before %s)" % [chunk/1000.0, last_what, what])
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
	return not path.is_empty() and (path == running or queue.has(path))

## Collects the finished load and starts the next one (every frame, from transition.gd).
static func pump() -> void:
	if not running.is_empty():
		var status := ResourceLoader.load_threaded_get_status(running)
		if status == ResourceLoader.THREAD_LOAD_IN_PROGRESS: return
		var resource := ResourceLoader.load_threaded_get(running) if status == ResourceLoader.THREAD_LOAD_LOADED else null
		if resource != null: held[running] = resource
		running = ""
	while running.is_empty() and not queue.is_empty():
		var path: String = queue.pop_front()
		if ResourceLoader.has_cached(path): continue
		# One worker for the whole resource: its textures (4096² BPTC, ~20 MB each with mipmaps) then
		# finish one by one and their GPU uploads land in different frames instead of the same one.
		if ResourceLoader.load_threaded_request(path, "", false) == OK: running = path

## The resource at `path`: covered, a queued one goes next and the card turns until it is in.
static func fetch(path: String) -> Resource:
	if covered and pending(path):
		if path != running:
			queue.erase(path)
			queue.push_front(path)
		while covered and pending(path):
			pump()
			if pending(path): await (Engine.get_main_loop() as SceneTree).process_frame
	return take(path)

## The resource at `path` now (waiting for it if it is the one loading).
static func take(path: String) -> Resource:
	if path == running:
		var resource := ResourceLoader.load_threaded_get(path)
		running = ""
		pump()
		if resource != null:
			held[path] = resource
			return resource
	queue.erase(path)
	if held.has(path): return held[path]
	return load(path)

## Waits until every queued load is in, reporting their share as progress (0..1 of the span).
static func settle() -> void:
	var total := queue.size()+(0 if running.is_empty() else 1)
	while covered and (not queue.is_empty() or not running.is_empty()):
		pump()
		done(1.0-(queue.size()+(0 if running.is_empty() else 1))/maxf(total, 1.0))
		if not queue.is_empty() or not running.is_empty(): await (Engine.get_main_loop() as SceneTree).process_frame
	done(1.0)

## The build is done: drops the queued loads nobody fetched and the references held for it (the
## built nodes keep what they use). A load still running is collected and let go at the next release.
static func release() -> void:
	queue.clear()
	held.clear()

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
