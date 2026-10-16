extends RefCounted
## When the tool in the hero's hand actually meets its target, so effects land on that frame
## whatever the use pose is (N6 sets the poses; nothing here assumes their timing):
##   ToolContact.tip(player) -> Vector3
##       The held tool's working end in world space: its "tip" meta (or the rod's "line_tip"),
##       else the corner of its meshes farthest from the grip. Vector3.INF with no tool.
##   ToolContact.strike(player, target, on_hit: Callable(point: Vector3), window := 0.7)
##       Follows the tip each frame and calls on_hit once, at the tip, when it comes down to the
##       ground at the target (or swings closest past it). Falls back to the target when the
##       window runs out or no tool is held, so the effect is never lost.
##   ToolContact.pour(player, target, on_drop: Callable(from: Vector3, to: Vector3), seconds := 0.9)
##       While the tool's tip hangs below its grip (the can tipped toward the bed), calls on_drop
##       about every 0.09 s with the spout and the target, for at most `seconds`.
## Each frame step is capped at 1/30 s, so a hitch does not skip the moment.
const STEP_CAP := 1.0/30.0

static func tip(player) -> Vector3:
	if player == null or not is_instance_valid(player): return Vector3.INF
	var tool = player.get("tool_node")
	if not (tool is Node3D) or not is_instance_valid(tool) or not tool.is_inside_tree(): return Vector3.INF
	var local: Vector3
	if tool.has_meta("tip"): local = tool.get_meta("tip")
	elif tool.has_meta("line_tip"): local = tool.get_meta("line_tip")
	elif tool.has_meta("tool_tip_cache"): local = tool.get_meta("tool_tip_cache")
	else:
		local = Vector3.ZERO
		var far := -1.0
		for mesh in tool.find_children("*", "MeshInstance3D", true, false):
			var box: AABB = (mesh as MeshInstance3D).get_aabb()
			var to_tool: Transform3D = tool.global_transform.affine_inverse()*mesh.global_transform
			for i in 8:
				var p: Vector3 = to_tool*box.get_endpoint(i)
				if p.length() > far:
					far = p.length()
					local = p
		tool.set_meta("tool_tip_cache", local)
	var pivot = tool.get_node_or_null("RodPivot")
	return (pivot as Node3D).to_global(local) if pivot is Node3D else tool.to_global(local)

static func _floor(player) -> float:
	return player.global_position.y if player is Node3D and is_instance_valid(player) else 0.0

static func _grip(player) -> Vector3:
	var tool = player.get("tool_node")
	return tool.global_position if tool is Node3D and is_instance_valid(tool) else player.global_position+Vector3(0, 1.0, 0)

static func strike(player, target: Vector3, on_hit: Callable, window := 0.7) -> void:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null: return
	var state := {"t": 0.0, "last": Time.get_ticks_usec(), "high": -INF, "prev": Vector3.INF, "far": 0.0, "near": INF, "near_at": Vector3.INF, "done": false}
	var finish := func(at: Vector3) -> void:
		if state.done: return
		state.done = true
		if tree.process_frame.is_connected(state.cb): tree.process_frame.disconnect(state.cb)
		on_hit.call(at)
	var tick := func() -> void:
		if state.done: return
		var now := Time.get_ticks_usec()
		state.t += minf((now-int(state.last))/1000000.0, STEP_CAP)
		state.last = now
		var p := tip(player)
		if p == Vector3.INF:
			if state.t >= 0.16: finish.call(target)
			return
		state.high = maxf(state.high, p.y)
		var flat := Vector2(p.x-target.x, p.z-target.z).length()
		var d := p.distance_to(target)
		state.far = maxf(state.far, d)
		# Down to the target's height near it, after the swing lifted the tip above it: the blade bites.
		if state.high > target.y+0.3 and p.y <= target.y+0.18 and flat < 1.2:
			finish.call(Vector3(p.x, target.y, p.z))
			return
		# Came down at least 0.25 m and turned back up (the lowest point of a ground swing).
		var prev: Vector3 = state.prev
		if prev != Vector3.INF and target.y < 0.3+_floor(player) and state.high-prev.y > 0.25 and p.y > prev.y+0.005:
			finish.call(Vector3(prev.x, target.y, prev.z) if flat < 1.6 else target)
			return
		# A raised target (a trunk, a rock face): the moment the tip passes closest to it, once it
		# had swung at least 0.2 m nearer than where it started.
		if d < state.near:
			state.near = d
			state.near_at = p
		elif target.y >= 0.3+_floor(player) and state.far-state.near > 0.2 and d > state.near+0.03 and state.near < 1.1:
			finish.call(state.near_at)
			return
		state.prev = p
		if state.t >= window: finish.call(target)
	state.cb = tick
	tree.process_frame.connect(tick)

static func pour(player, target: Vector3, on_drop: Callable, seconds := 0.9) -> void:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null: return
	var state := {"t": 0.0, "last": Time.get_ticks_usec(), "pouring": 0.0, "since": 1.0}
	var tick := func() -> void:
		var now := Time.get_ticks_usec()
		var dt := minf((now-int(state.last))/1000000.0, STEP_CAP)
		state.last = now
		state.t += dt
		var spout := tip(player)
		var tipped := spout != Vector3.INF and spout.y < _grip(player).y-0.04
		# Without a tool, or a pose that never tips the can, it still pours after a short lift.
		if spout == Vector3.INF or (not tipped and state.t > 0.35):
			tipped = true
			if spout == Vector3.INF: spout = target+Vector3(0, 0.9, 0)
		if tipped:
			state.pouring += dt
			state.since += dt
			if state.since >= 0.09:
				state.since = 0.0
				on_drop.call(spout, target)
		if state.pouring >= seconds or state.t >= seconds+0.8:
			tree.process_frame.disconnect(state.cb)
	state.cb = tick
	tree.process_frame.connect(tick)
