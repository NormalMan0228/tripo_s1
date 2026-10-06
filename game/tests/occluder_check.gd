extends SceneTree
## Puts the walker behind the town hall and under a tree, and checks the occluder
## fade add-on turns exactly those see-through (captures before/after).
const Map = preload("res://maps/archipelago/archipelago.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const Player = preload("res://scripts/player.gd")
const Fade = preload("res://scripts/occluder_fade.gd")
var failed := false

class StubTown extends Node:
	var map: Node3D

class StubApp extends Node:
	var town: Node
	var camera: Camera3D
	var player: Node3D

func _initialize() -> void:
	call_deferred("run")

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func run() -> void:
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 10
	root.add_child(camera)
	camera.current = true
	var map := Map.new()
	root.add_child(map)
	map.build(camera)
	var e := WorldEnvironment.new()
	e.environment = Environment.new()
	e.environment.background_mode = Environment.BG_COLOR
	e.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	root.add_child(e)
	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = true
	root.add_child(sun)
	Map.apply_lighting(e.environment, sun)
	var walker := Player.new()
	walker.controls_enabled = false
	root.add_child(walker)
	walker.apply_avatar({})
	var app := StubApp.new()
	app.town = StubTown.new()
	app.town.map = map
	app.camera = camera
	app.player = walker
	root.add_child(app)
	for i in 8: await physics_frame
	# Dress the buildings like the game does, so their shader materials are faded.
	preload("res://scripts/building_dressing.gd").dress(map)
	var fade := Fade.new()
	root.add_child(fade)
	fade.setup(app)
	expect(fade.groups.size() > 40, "collected buildings and tall props (%d)" % fade.groups.size())
	# "door" stands on the town hall steps and "corner" beside its front corner: the
	# building barely overlaps the walker there and must stay solid.
	for spot in [["hall", Vector2(-33,15.6), "09_town_hall"], ["open", Vector2(-30,36), ""], ["door", Vector2(-33,28.6), ""],
			["corner", Vector2(-27.6,25.5), ""], ["tree", Vector2(-15.8,31.6), "38_conifer"]]:
		var at: Vector2 = spot[1]
		var hit := map.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(at.x,60,at.y),Vector3(at.x,-20,at.y),1))
		walker.global_position = hit.get("position", Vector3(at.x,2,at.y))
		var focus := walker.global_position+Profile.CAMERA_FOCUS_OFFSET
		camera.position = focus+Profile.CAMERA_OFFSET*Profile.CAMERA_PULLBACK
		camera.look_at(focus)
		for i in 40: await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/occluder-%s.png" % spot[0]))
		var faded: Array[String] = []
		for group in fade.groups:
			if group.amount > 0.5:
				var spec: Dictionary = group.root.get_meta("placement_spec", {})
				faded.append(str(spec.get("id", group.root.name)))
		print("FADED ", spot[0], " ", faded)
		if spot[2] == "": expect(faded.is_empty(), "nothing fades at %s" % spot[0])
		else: expect(spot[2] in faded, "%s fades when it hides the walker" % spot[2])
		if spot[2] == "09_town_hall":
			var dithered := false
			for group in fade.groups:
				if group.root.name == "09_town_hall":
					for entry in group.copies:
						if entry.has("shader") and float(entry.shader.get_shader_parameter("fade")) > 0.5: dithered = true
			expect(dithered, "the dressed town hall fades through its shader")
	fade.leave()
	quit(1 if failed else 0)
