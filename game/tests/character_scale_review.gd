extends SceneTree
## Public asset scale review: no server or provider calls.
const Player=preload("res://scripts/player.gd")
const Loader=preload("res://scripts/model_loader.gd")
const Art=preload("res://scripts/art.gd")
var failures: Array[String]=[]
func _initialize() -> void:call_deferred("review")
func review() -> void:
	var stage := Node3D.new();root.add_child(stage)
	var environment := WorldEnvironment.new();stage.add_child(environment);environment.environment=Environment.new()
	environment.environment.background_mode=Environment.BG_COLOR;environment.environment.background_color=Color("d2dacd")
	environment.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;environment.environment.ambient_light_energy=.6
	var sun := DirectionalLight3D.new();stage.add_child(sun);sun.rotation_degrees=Vector3(-45,-25,0);sun.light_energy=.8;sun.shadow_enabled=true
	Art.box(stage,Vector3(0,-.06,0),Vector3(14,.1,7),Color("b9c4b0"))
	# One metre floor ticks and a 2.4 m doorway show the common spatial scale.
	for x in range(-6,7):Art.box(stage,Vector3(x,0,.5),Vector3(.015,.015,5),Color("8c9c86"))
	for z in range(-2,4):Art.box(stage,Vector3(0,0,z),Vector3(13,.015,.015),Color("8c9c86"))
	for x in [-.6,.6]:Art.box(stage,Vector3(x,1.2,-1.8),Vector3(.08,2.4,.12),Color("84694e"))
	Art.box(stage,Vector3(0,2.4,-1.8),Vector3(1.28,.1,.12),Color("84694e"))
	var report: Array[Dictionary]=[]
	var identifiers := ["explorer_b","explorer","ranger","tinker","haeru"]
	var names := ["여행자 B","루","미라","테오","해루"]
	for i in identifiers.size():
		var actor := Player.new();actor.avatar={"character":identifiers[i],"backpack":false};actor.controls_enabled=false;actor.visual_only=true
		stage.add_child(actor);actor.position=Vector3((i-2)*2.0,.03,0)
		actor.set_physics_process(false)
		actor.ambient_clip="idle";actor.visual.rotation.y=PI
		if actor.animation_player and actor.animation_player.has_animation("idle"):actor.animation_player.play("idle")
		await process_frame
		var meshes: Array[MeshInstance3D]=[];Loader._collect_meshes(actor.visual,meshes)
		var bounds := AABB();var first := true
		for mesh in meshes:
			var local: AABB=Loader._local_transform(mesh,actor)*mesh.get_aabb()
			bounds=local if first else bounds.merge(local);first=false
		var height := bounds.size.y
		var ok := height>=1.6 and height<=1.85
		print(("PASS " if ok else "FAIL ")+identifiers[i]+" mesh height "+str(height))
		if not ok:failures.append(identifiers[i])
		report.append({"character":identifiers[i],"height_m":height,"width_m":bounds.size.x,"bones":actor.hand_skeleton.get_bone_count() if actor.hand_skeleton else 0})
		var label := Label3D.new();stage.add_child(label);label.text=names[i]+"\n%.2f m"%height
		var font := SystemFont.new();font.font_names=PackedStringArray(["Malgun Gothic","sans-serif"]);label.font=font
		label.font_size=32;label.pixel_size=.004;label.position=actor.position+Vector3(0,2.05,0);label.billboard=BaseMaterial3D.BILLBOARD_ENABLED;label.no_depth_test=true
	var camera := Camera3D.new();stage.add_child(camera);camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=5.8;camera.current=true
	camera.position=Vector3(0,3.6,10);camera.look_at(Vector3(0,1,0))
	var layer := CanvasLayer.new();root.add_child(layer)
	var title := Label.new();layer.add_child(title);title.position=Vector2(28,25);title.text="캐릭터 크기 기준 · 1m 격자 / 2.4m 문틀";title.add_theme_font_size_override("font_size",24)
	title.add_theme_color_override("font_color",Color("3d4b39"))
	await create_timer(.4).timeout;await RenderingServer.frame_post_draw
	var folder := ProjectSettings.globalize_path("res://../artifacts")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--artifacts="):folder=arg.trim_prefix("--artifacts=")
	root.get_texture().get_image().save_png(folder.path_join("character-scale-review.png"))
	print("CHARACTER_SCALE ",JSON.stringify({"ok":failures.is_empty(),"assets":report,"paid_calls":0}))
	stage.queue_free();layer.queue_free();await process_frame;await process_frame;quit(0 if failures.is_empty() else 1)
