extends SceneTree
## Measure the current eight avatars and both resident builders in rendered world metres.
const Roster = preload("res://scripts/character_roster.gd")
const Player = preload("res://scripts/player.gd")
const Npc = preload("res://scripts/npc.gd")
const Folk = preload("res://scripts/shadow_folk.gd")
const Figure = preload("res://scripts/shadow_figure.gd")
const Interiors = preload("res://scripts/interiors.gd")
const Beast = preload("res://scripts/shadow_beast.gd")
const Art = preload("res://scripts/art.gd")
const Wardrobe = preload("res://scripts/wardrobe.gd")
var checks := 0
var failures := 0
var report: Array = []
var stage: Node3D
var folder := ""
var gallery: Array[Node3D] = []
var camera: Camera3D

func _initialize() -> void: call_deferred("run")

func check(ok: bool, words: String) -> void:
	checks += 1
	if not ok: failures += 1
	print(("PASS " if ok else "FAIL ")+words)

func bounds(node: Node3D, relative: Node3D, body_only := false) -> AABB:
	var result := AABB()
	var first := true
	var meshes: Array = node.find_children("*", "MeshInstance3D", true, false)
	if node is MeshInstance3D: meshes.append(node)
	for mesh in meshes:
		if mesh.mesh == null: continue
		if body_only and not mesh.mesh is ArrayMesh: continue
		var box: AABB = relative.global_transform.affine_inverse()*mesh.global_transform*mesh.get_aabb()
		result = box if first else result.merge(box)
		first = false
	return result

func measured(node: Node3D, relative: Node3D, expected: float, id: String) -> void:
	var box := bounds(node,relative,id.begins_with("resident/body/"))
	if DisplayServer.get_name()!="headless":
		await RenderingServer.frame_post_draw
		var drawn := AABB();var first := true
		for mesh in node.find_children("*","MeshInstance3D",true,false):
			if id.begins_with("resident/body/") and not mesh.mesh is ArrayMesh:continue
			var mesh_box: AABB=mesh.bake_mesh_from_current_skeleton_pose().get_aabb() if mesh.skin else mesh.get_aabb()
			var local: AABB=relative.global_transform.affine_inverse()*mesh.global_transform*mesh_box
			drawn=local if first else drawn.merge(local);first=false
		box=drawn
		check(absf(box.size.y-expected)<.12,"drawn human/%s height %.3f expected %.2f"%[id,box.size.y,expected])
	else:
		check(box.size.y>0,"rest body available/"+id)
	check(absf(box.position.y)<.04, "%s feet %.3f" % [id,box.position.y])
	report.append({"id":id,"height":box.size.y,"feet":box.position.y,"rendered":DisplayServer.get_name()!="headless"})

func show_actor(actor: Node3D, words: String) -> void:
	var i := gallery.size()
	actor.position=Vector3((i%7-3)*2.3,0,-floorf(i/7.0)*3.7)
	gallery.append(actor)
	for own_label in actor.find_children("*","Label3D",true,false): own_label.visible=false
	var label := Art.label3d(stage, words, actor.position+Vector3(0,2.2,0),Color("263e37"))
	label.font_size=48; label.pixel_size=.006
	actor.set_meta("scale_label",label)

func capture(name: String, rows: int) -> void:
	if DisplayServer.get_name()=="headless": return
	camera.size=11.0
	camera.position=Vector3(0,8,15)
	camera.look_at(Vector3(0,1,-(rows-1)*1.85))
	await create_timer(.35).timeout
	await RenderingServer.frame_post_draw
	check(root.get_texture().get_image().save_png(folder.path_join("actor-scale-"+name+".png"))==OK,"capture "+name)

func clear_gallery() -> void:
	for actor in gallery:
		var label=actor.get_meta("scale_label",null)
		if is_instance_valid(label): label.queue_free()
		actor.queue_free()
	gallery.clear()
	await process_frame
	await process_frame

func run() -> void:
	folder=ProjectSettings.globalize_path("res://../artifacts")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--artifacts="): folder=arg.trim_prefix("--artifacts=")
	stage=Node3D.new(); root.add_child(stage)
	var environment := WorldEnvironment.new(); stage.add_child(environment)
	environment.environment=Environment.new()
	environment.environment.background_mode=Environment.BG_COLOR
	environment.environment.background_color=Color("d2dacd")
	environment.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_energy=.65
	var sun := DirectionalLight3D.new();stage.add_child(sun);sun.rotation_degrees=Vector3(-45,-25,0)
	Art.box(stage,Vector3(0,-.06,-4),Vector3(18,.1,18),Color("b9c4b0"))
	for x in range(-9,10):Art.box(stage,Vector3(x,0,-4),Vector3(.012,.012,18),Color("8c9c86"))
	camera=Camera3D.new();stage.add_child(camera);camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.current=true
	for id in Roster.IDS:
		var actor := Player.new();actor.avatar={"character":id,"backpack":false};actor.controls_enabled=false;actor.visual_only=true
		stage.add_child(actor); actor.set_physics_process(false);actor.visual.visible=true;actor.visual.rotation.y=PI
		await measured(actor.visual,actor,1.75,"player/"+id)
		if actor.animation_player and actor.animation_player.has_animation("idle"):
			actor.animation_player.play("idle");actor.animation_player.advance(0)
		show_actor(actor,id)
	await capture("players",2)
	await clear_gallery()
	# Rebuilding the avatar must fit again, with no scale accumulating across changes.
	var changing := Player.new(); changing.avatar={"character":"m1","backpack":false};stage.add_child(changing)
	changing.set_physics_process(false)
	# Let the renderer register the initial material before replacing that body.
	if DisplayServer.get_name()!="headless": await RenderingServer.frame_post_draw
	for id in ["m1","m2","f4","m1","f4"]:
		changing.apply_avatar({"character":id,"backpack":false})
		await process_frame;await process_frame
		await measured(changing.visual,changing,1.75,"changed/"+id)
	changing.queue_free();await process_frame;await process_frame
	var preview := Wardrobe.new();preview.avatar={"character":"m1","backpack":false};root.add_child(preview)
	if DisplayServer.get_name()!="headless": await RenderingServer.frame_post_draw
	for id in ["m1","m2","f1","f4"]:
		preview.avatar.character=id;preview.refresh()
		await process_frame;await process_frame
		await measured(preview.actor.visual,preview.actor,1.75,"wardrobe/"+id)
	preview.queue_free();await process_frame
	for id in ["naru","sora","moru","haeru","boni","sol"]:
		if not Npc.available(id):continue
		var actor := Npc.new();stage.add_child(actor);actor.setup(id,0)
		await measured(actor.model,actor,1.3 if id=="sol" else 1.75,"npc/"+id)
		show_actor(actor,id)
	var folk := Folk.new();stage.add_child(folk)
	for entry in Folk.FOLK:
		var id := str(entry.id)
		var expected := 1.3 if id in ["kid","sol"] else 1.75
		var actor: Node3D = Figure.create_still(id);stage.add_child(actor)
		# The procedural body is measured before hats and hand props: tall hats do not shrink people.
		await measured(actor.figure.get_child(0),actor,expected,"resident/body/"+id)
		Interiors.wear_day_model(actor,id)
		if actor.has_meta("day_model"):
			await measured(actor.get_meta("day_model"),actor,expected,"resident/indoor/"+id)
		var outdoor: Node3D=Figure.create_still(id);stage.add_child(outdoor)
		folk.attach_day_model(outdoor)
		if outdoor.has_meta("day_model"):
			await measured(outdoor.get_meta("day_model"),outdoor,expected,"resident/outdoor/"+id)
		outdoor.queue_free()
		actor.set_day(true,true)
		show_actor(actor,id)
	await capture("residents",4)
	await clear_gallery();folk.queue_free();await process_frame
	for id in ["fallback_adult","sol"]:
		var actor := Interiors.stand_in_figure(id);stage.add_child(actor)
		await measured(actor,stage,1.3 if id=="sol" else 1.75,"room fallback/"+id)
		actor.queue_free();await process_frame
	# Every shipped species/region model goes through the encounter builder, not only the five stand-ins.
	var species := {}
	var tested_models := {}
	for file in DirAccess.get_files_at("res://assets/monsters"):
		var asset := file.trim_suffix(".remap").trim_suffix(".import")
		if asset.ends_with(".glb"):
			var id := asset.trim_suffix(".glb")
			if tested_models.has(id):continue
			var split := id.rfind("_")
			var animal := id.substr(0,split)
			var variant := id.substr(split+1)
			if variant not in ["forest","quarry","frost"]:continue
			tested_models[id]=true
			species[animal]=true
			var beast := Beast.new();beast.variant=variant
			beast.from_enemy({"species":animal,"stand_in":animal,"height":9.0,"boss":false})
			stage.add_child(beast)
			check(is_instance_valid(beast.monster) and beast.monster.height*beast.monster.scale.y<=1.901,"regular cap/"+id)
			check(beast.scale.is_equal_approx(Vector3.ONE),"unscaled encounter root/"+id)
			if DisplayServer.get_name()!="headless":
				# Skinned source vertices can be in bind space. Bake the displayed pose before
				# measuring; transforming the raw mesh AABB can falsely report a giant creature.
				await RenderingServer.frame_post_draw
				var drawn := AABB(); var first := true
				for mesh in beast.monster.model.find_children("*","MeshInstance3D",true,false):
					var baked: ArrayMesh=mesh.bake_mesh_from_current_skeleton_pose()
					var box: AABB=beast.global_transform.affine_inverse()*mesh.global_transform*baked.get_aabb()
					drawn=box if first else drawn.merge(box);first=false
				# An idle pose can raise the head/arms beyond the model's rest height.
				check(drawn.size.y<=2.25,"drawn regular body/"+id+" %.3f"%drawn.size.y)
			beast.queue_free();await process_frame
	check(species.size()>=34,"all shipped monster species enumerated")
	for is_boss in [false,true]:
		for kind in ["missing_qa_species"]:
			var beast := Beast.new();beast.kind=kind;beast.species=kind;beast.size_hint=7;beast.boss=is_boss
			# Build with no regional GLB to exercise the procedural fallback explicitly.
			stage.add_child(beast);beast.build();beast.set_process(false)
			check(not is_instance_valid(beast.monster),"procedural fallback selected")
			var box := bounds(beast.body,beast)
			check(box.size.y>=3.49 if is_boss else box.size.y<=1.901,"fallback size/%s/boss=%s (%.3f)"%[kind,is_boss,box.size.y])
			check(beast.scale.is_equal_approx(Vector3.ONE),"fallback root/"+kind)
			check(beast.health.position.y>box.end.y,"health above fallback/"+kind)
			var before: Vector3=beast.body.get_parent().scale
			beast.phase="windup";beast._process(.1)
			check(beast.body.get_parent().scale.is_equal_approx(before),"fallback crouch retains size")
			beast.phase="chase";beast._process(.2)
			check(beast.body.get_parent().scale.is_equal_approx(before),"fallback recovery retains size")
			beast.queue_free();await process_frame
	for i in 6:
		var beast := Beast.new();beast.variant="forest"
		var animal: String=["wolf","goblin","troll","skeleton","treant","dragon"][i]
		beast.from_enemy({"species":animal,"stand_in":"brute","height":5.0 if i>=4 else 3.0,"boss":i>=4})
		stage.add_child(beast);beast.set_process(false)
		check(beast.monster.height*beast.monster.scale.y>=3.5 if i>=4 else beast.monster.height*beast.monster.scale.y<=1.901,"gallery size/"+animal)
		show_actor(beast,animal+(" / BOSS" if i>=4 else ""))
		var label: Label3D=beast.get_meta("scale_label")
		if i>=4:label.position.y=5.5
	await capture("monsters",1)
	await clear_gallery()
	var result := {"checks":checks,"failures":failures,"species":species.size(),"measurements":report}
	var output := FileAccess.open(folder.path_join("actor-scale-results.json"),FileAccess.WRITE)
	output.store_string(JSON.stringify(result,"\t"));output.close()
	print("ACTOR_SCALE_DONE checks=%d failures=%d species=%d"%[checks,failures,species.size()])
	stage.queue_free();await process_frame;await process_frame
	quit(1 if failures else 0)
