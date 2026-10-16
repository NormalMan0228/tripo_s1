extends SceneTree
## 보니 and 솔's own models on their walkers (shadow_folk.gd DAY_MODELS, attach_day_model /
## drive_day_model), headless and without a server or a village:
##  - with res://assets/npc/<id>.glb: the model hangs under the walker's body, has idle/walk/work,
##    shows by day in place of the procedural figure (work clip at the work spot, walk while
##    walking, idle while talking) and hides again at night (figure back),
##  - without the file: nothing is attached and the procedural look stays.
## Godot --headless --path game --script res://tests/residents_model_check.gd
const Folk = preload("res://scripts/shadow_folk.gd")
const Figure = preload("res://scripts/shadow_figure.gd")
var failed := 0
var passed := 0

func _initialize() -> void:
	call_deferred("run")

func expect(value: bool, description: String) -> void:
	if value:
		passed += 1
		print("PASS ", description)
	else:
		failed += 1
		print("FAIL ", description)

func run() -> void:
	var folk: Node3D = Folk.new()
	root.add_child(folk)
	expect(Folk.DAY_MODELS.has("boni") and Folk.DAY_MODELS.has("sol"), "보니 and 솔 have model heights")
	for id in ["boni", "sol"]:
		var entry: Dictionary = {}
		for e in Folk.FOLK:
			if str(e.id) == id: entry = e
		var walker: CharacterBody3D = Figure.new()
		walker.configure(entry, folk, null)
		folk.add_child(walker)
		# No path graph here: the brain stays off.
		walker.set_physics_process(false)
		walker.dress()
		folk.attach_day_model(walker)
		var path := "res://assets/npc/%s.glb" % id
		if not ResourceLoader.exists(path) or not Folk.DAY_MODELS_ENABLED:
			print("SKIP ", id, " model file missing or switched off: procedural look")
			expect(not walker.has_meta("day_model") and walker.figure.visible, "%s keeps the procedural look without its model" % id)
			continue
		var model = walker.get_meta("day_model", null)
		var player = walker.get_meta("day_model_player", null)
		expect(is_instance_valid(model) and model.get_parent() == walker.visual, "%s model hangs under the walker's body" % id)
		if not is_instance_valid(model): continue
		expect(is_instance_valid(player) and player.has_animation("idle") and player.has_animation("walk") and player.has_animation("work"), "%s model has idle/walk/work" % id)
		var box := AABB()
		var first := true
		for node in model.find_children("*", "MeshInstance3D", true, false):
			var mesh := node as MeshInstance3D
			var local: AABB = walker.visual.global_transform.affine_inverse()*mesh.global_transform*mesh.get_aabb()
			box = local if first else box.merge(local)
			first = false
		expect(absf(box.size.y-float(Folk.DAY_MODELS[id])) < 0.08 and absf(box.position.y) < 0.08, "%s model stands %.2f m tall from %.2f (feet on the ground)" % [id, box.size.y, box.position.y])
		# Day, at the work spot.
		walker.visible = true
		walker.fade = 1.0
		walker.day_blend = 1.0
		walker.place = "outside"
		walker.activity = "craft" if id == "boni" else "garden"
		walker.state = "pause"
		walker.current_clip = Figure.IDLE
		folk.drive_day_model(walker, 0.1)
		expect(model.visible and not walker.figure.visible, "%s by day: model shown, procedural figure hidden" % id)
		expect(player.current_animation == "work", "%s works at her spot (%s)" % [id, player.current_animation])
		walker.current_clip = Figure.WALK
		folk.drive_day_model(walker, 0.1)
		expect(player.current_animation == "walk", "%s walks with the walk clip" % id)
		walker.current_clip = Figure.IDLE
		walker.state = "talk"
		folk.drive_day_model(walker, 0.1)
		expect(player.current_animation == "idle", "%s idles while talking" % id)
		# Night: the silhouette is back.
		walker.day_blend = 0.0
		folk.drive_day_model(walker, 0.1)
		expect(not model.visible and walker.figure.visible, "%s at night: silhouette back, model hidden" % id)
		# Through a door: hidden.
		walker.day_blend = 1.0
		walker.fade = 0.1
		folk.drive_day_model(walker, 0.1)
		expect(not model.visible, "%s fading through a door hides the model" % id)
	folk.leave()
	print("RESIDENTS_MODEL ", "FAIL" if failed else "OK", " pass=", passed, " fail=", failed)
	quit(1 if failed else 0)
