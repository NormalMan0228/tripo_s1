extends SceneTree
## Headless checks for the world-presentation pass (no server):
##  - stairs: a room's stair climb plays the walk clip, never a gliding idle pose.
##   Godot --headless --path game --script res://tests/world_polish_check.gd [-- --only=stairs]
var failures: Array[String] = []
var only := ""

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--only="): only = arg.trim_prefix("--only=")
	call_deferred("run")
	create_timer(300).timeout.connect(func():
		push_error("world_polish_check exceeded 300 seconds")
		quit(2))

func check(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failures.append(description)

func wants(name: String) -> bool:
	return only.is_empty() or only == name

func run() -> void:
	if wants("stairs"): await stairs()
	print("WORLD_POLISH ", JSON.stringify({"ok":failures.is_empty(), "failures":failures}))
	quit(0 if failures.is_empty() else 1)

## Climbs a straight staircase and the lighthouse's spiral: while the walker is on
## the stair (above the floor) the walk clip runs and the body reports motion.
func stairs() -> void:
	Engine.set_meta("interior_hour", 13.0)
	for room in ["home", "17_lighthouse"]:
		Engine.set_meta("studio_session", {"token":"", "url":"http://127.0.0.1:9", "room":room})
		var studio: Control = load("res://scenes/studio.tscn").instantiate()
		root.add_child(studio)
		await create_timer(0.8).timeout
		var record: Dictionary = {}
		for item in studio.decor:
			if item.has("link"):
				record = item
				break
		check(not record.is_empty(), "%s has a stair" % room)
		if record.is_empty(): continue
		var front := Vector3(0, 0, 1).rotated(Vector3.UP, float(record.yaw))
		for distance in [0.7, 0.9, 1.1, 1.4]:
			var at: Vector3 = record.center+front*(float(record.half.y)+distance)
			at.y = 0
			if studio.can_stand(at):
				studio.hero.position = at
				break
		await create_timer(0.3).timeout
		studio.travel(record)
		var climbing := 0
		var walking := 0
		for i in 120:
			await physics_frame
			if studio.floor_index != 0 or not studio.travelling: break
			if studio.hero.position.y > 0.05:
				climbing += 1
				if studio.hero.current_clip == "walk" and studio.hero.locomotion_velocity.length() > 0.5: walking += 1
		check(climbing > 20, "%s: the walker climbs the %s (%d frames)" % [room, record.kind, climbing])
		check(walking >= climbing*0.9, "%s: the walk clip runs on the %s (%d of %d frames)" % [room, record.kind, walking, climbing])
		studio.queue_free()
		await process_frame
		await process_frame
	Engine.remove_meta("interior_hour")
