extends SceneTree
## A crafted character's GLB from a real Tripo run (task 67d): built the way the game builds crafts,
## its idle loops and its bones move, walk plays, and (with --capture) frames of both are saved.
##   godot --path game --script res://tests/rig_file_check.gd -- --glb=C:/path/part-whole.glb [--capture --out=C:/dir]
const Assembly = preload("res://scripts/asset_assembly.gd")
const RigMotion = preload("res://scripts/rig_motion.gd")
var failed := false

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ") + description)
	if not value: failed = true

func _initialize() -> void:
	call_deferred("run")

func arg(name: String, fallback := "") -> String:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--" + name + "="): return a.trim_prefix("--" + name + "=")
	return fallback

func shot(out: String, name: String) -> void:
	if out.is_empty() or DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out.path_join("rig67d-" + name + ".png"))

func run() -> void:
	var blob := FileAccess.get_file_as_bytes(arg("glb"))
	expect(blob.size() > 1000, "the GLB was read (%d bytes)" % blob.size())
	var manifest := {"schema": 1, "plan": {"title": "robot", "category": "character", "parts": [{"id": "whole", "parent": "", "prompt": "robot",
		"shape": "box", "size": [0.8, 1.6, 0.5], "position": [0, 0.8, 0], "rotation": [0, 0, 0], "pivot": [0, 0, 0], "color": "#c9a46e"}]},
		"program": {"version": 1, "state": {}, "functions": {}, "events": {}},
		"provenance": {"geometry": "tripo", "size_m": 1.6, "rig": {"moves": true, "clips": ["idle", "walk"], "default_clip": "idle"}},
		"runtime": {"state": {}, "colors": {}, "version": 1}}
	var character: Node3D = Assembly.new()
	expect(character.build(manifest, {"whole": blob}), "the real rigged GLB builds as a craft")
	var players := RigMotion.players(character)
	var skeletons := RigMotion.skeletons(character)
	expect(not players.is_empty() and players[0].has_animation("idle") and players[0].has_animation("walk"), "it carries idle and walk (%s)" % [players[0].get_animation_list() if not players.is_empty() else []])
	expect(not skeletons.is_empty() and skeletons[0].get_bone_count() > 10, "it has a full skeleton (%d bones)" % [skeletons[0].get_bone_count() if not skeletons.is_empty() else 0])
	# A stage to look at it: light, a floor and an orthographic camera framing its size.
	var stage := Node3D.new()
	root.add_child(stage)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-50, -35, 0)
	stage.add_child(light)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color("e9e2d2")
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.75, 0.75, 0.75)
	stage.add_child(env)
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	stage.add_child(camera)
	camera.position = Vector3(2, 1.4, 3)
	stage.add_child(character)
	preload("res://scripts/preview_frame.gd").fit(camera, character.get_meta("size", Vector3.ONE))
	camera.current = true
	await create_timer(0.8).timeout
	expect(character.get_meta("rig_moving", false) == true and players[0].current_animation == "idle", "shown, idle loops and the bones move")
	var out := arg("out")
	await shot(out, "idle-a")
	await create_timer(0.5).timeout
	await shot(out, "idle-b")
	expect(RigMotion.play(character, "walk"), "walk plays")
	var before := RigMotion.pose(character)
	await create_timer(0.35).timeout
	expect(before != RigMotion.pose(character), "walking moves the bones")
	await shot(out, "walk-a")
	await create_timer(0.35).timeout
	await shot(out, "walk-b")
	print("RIG_FILE " + ("FAILED" if failed else "OK"))
	quit(1 if failed else 0)
