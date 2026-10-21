extends SceneTree
const Player=preload("res://scripts/player.gd")
const Npc=preload("res://scripts/npc.gd")
const Roster=preload("res://scripts/character_roster.gd")
const Look=preload("res://scripts/avatar_look.gd")
const Materials=preload("res://scripts/actor_materials.gd")
const Lod=preload("res://scripts/anim_lod.gd")
const Art=preload("res://scripts/art.gd")
const REQUIRED := ["greet","agree","bow","relax","look_around","fold_arms","wait","punch","chop","dig","hurt","cheer","clap"]
var checks := 0
var failures := 0
var stage: Node3D
var report := {}
var camera: Camera3D
var folder := ""
func _initialize() -> void: call_deferred("run")
func check(ok: bool, text: String) -> void:
	checks+=1
	if not ok: failures+=1
	print(("PASS " if ok else "FAIL ")+text)
func hero(id: String) -> CharacterBody3D:
	var body := Player.new();body.avatar=Roster.PRESETS[id].duplicate();body.avatar.character=id;body.avatar.backpack=false;body.visual_only=true;body.controls_enabled=false
	stage.add_child(body);body.set_physics_process(false);body.set_process(false)
	return body
func step(body: Node, seconds := .016667) -> void: body._physics_process(seconds)
func capture(name: String) -> void:
	if DisplayServer.get_name()=="headless": return
	await process_frame;await process_frame;await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(folder.path_join(name+".png"))
func clear_stage() -> void:
	for child in stage.get_children():
		if child is CharacterBody3D or child is Label3D or child.get_script()==Npc: child.queue_free()
	await process_frame;await process_frame
func run() -> void:
	folder=ProjectSettings.globalize_path("res://../artifacts")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--artifacts="): folder=arg.trim_prefix("--artifacts=")
	root.size=Vector2i(1440,1000)
	for child in root.get_children():
		if child is CanvasLayer: child.visible=false
	stage=Node3D.new();root.add_child(stage)
	var env := WorldEnvironment.new();env.environment=Environment.new();stage.add_child(env)
	env.environment.background_mode=Environment.BG_COLOR;env.environment.background_color=Color("dce4da")
	env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.environment.ambient_light_energy=.65
	var sun := DirectionalLight3D.new();stage.add_child(sun);sun.rotation_degrees=Vector3(-40,-35,0)
	camera=Camera3D.new();stage.add_child(camera);camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=9.5
	camera.position=Vector3(0,7,14);camera.look_at(Vector3(0,.8,-3));camera.current=true
	for id in Roster.IDS:
		var body := hero(id)
		for clip in REQUIRED: check(body.animation_player.has_animation(clip),id+" clip/"+clip)
		body.equip("axe");body.react("attack");step(body)
		check(body.current_clip=="slash",id+" axe attack uses slash")
		body.react("gather");step(body)
		check(body.current_clip=="chop",id+" tree gather uses chop")
		body.equip("");body.react("attack");step(body)
		check(body.current_clip=="punch",id+" bare attack uses punch")
		body.action_until=0;body.action_kind="";body.equip("spear");body.react("attack");step(body)
		check(body.action_pose.kind=="thrust",id+" spear uses forward thrust")
		body.react("hurt");step(body);body.react("attack")
		check(body.action_clip=="hurt" and body.action_kind=="hurt",id+" hit reaction takes priority")
		body.action_until=0;body.idle_seconds=3.0;body.external_velocity=Vector2.ZERO;step(body)
		check(body.current_clip in ["relax","look_around","fold_arms","wait"],id+" idle personality")
		body.external_velocity=Vector2(2.5,0);step(body)
		check(body.current_clip=="walk",id+" motion interrupts idle")
		body.external_velocity=Vector2.ZERO;body.action_until=0;body.equip("")
		body.react("greet");body.external_velocity=Vector2(2.5,0);step(body)
		check(body.current_clip=="walk",id+" movement cancels greeting")
		var rig: Skeleton3D=body.hand_skeleton
		var left: int=rig.find_bone("L_Upperarm");var right: int=rig.find_bone("R_Upperarm")
		var hip: int=rig.find_bone("Hip")
		var rest_width := (rig.global_transform*rig.get_bone_global_rest(left).origin).distance_to(rig.global_transform*rig.get_bone_global_rest(right).origin)
		for clip in REQUIRED:
			var narrow := INF;var hip_low := INF
			body.animation_player.play(clip,0)
			for sample in 24:
				body.animation_player.seek(body.animation_player.get_animation(clip).length*sample/24.0,true)
				var a: Vector3=rig.global_transform*rig.get_bone_global_pose(left).origin
				var b: Vector3=rig.global_transform*rig.get_bone_global_pose(right).origin
				narrow=minf(narrow,a.distance_to(b))
				hip_low=minf(hip_low,(rig.global_transform*rig.get_bone_global_pose(hip).origin).y)
			check(narrow>maxf(.15,rest_width*.65) and (id!="m2" or narrow>.27),id+" shoulders remain open/"+clip+" %.3f/rest %.3f"%[narrow,rest_width])
			if clip=="hurt": check(hip_low>.55,id+" standing hit reaction does not fall/sit")
		body.queue_free();await process_frame;await process_frame
	# A material variant is shared by equal looks, while a colour edit makes only that variant.
	var first := hero("m4");var second := hero("m4")
	var meshes_a: Array = first.visual.find_children("*","MeshInstance3D",true,false)
	var meshes_b: Array = second.visual.find_children("*","MeshInstance3D",true,false)
	check(meshes_a[0].get_surface_override_material(0)==meshes_b[0].get_surface_override_material(0),"equal looks share the same material")
	var skin: ShaderMaterial=meshes_a[0].get_surface_override_material(1)
	var coat: ShaderMaterial=meshes_a[0].get_surface_override_material(2)
	check(float(skin.get_shader_parameter("metallic_factor"))==0.0 and float(coat.get_shader_parameter("metallic_factor"))>.5,"skin and smith plate have different PBR properties")
	check(Materials.hits>0 and Materials.cache.size()<=Materials.LIMIT,"bounded material cache has real reuse")
	report.material_cache={"hits":Materials.hits,"misses":Materials.misses,"entries":Materials.cache.size()}
	await clear_stage()
	for id in ["naru","sora","moru","haeru"]:
		var npc := Npc.new();stage.add_child(npc);npc.setup(id,0.0);npc.set_process(false)
		for clip in REQUIRED:check(npc.anim_player.has_animation(clip),id+" clip/"+clip)
		var motion: Node=npc.motion
		motion.activity="tailor" if id=="sora" else "camp" if id=="moru" else "fish" if id=="haeru" else "guide"
		motion._process(.05)
		var before: String=npc.anim_player.current_animation
		var box := Control.new();root.add_child(box);npc.begin_talk(box);npc._process(.05)
		check(npc.anim_player.current_animation=="greet",id+" conversation interrupts work with greeting")
		motion.greeting_left=0.0;npc._process(.05)
		check(npc.anim_player.current_animation=="agree",id+" conversation gestures")
		box.queue_free();await process_frame;npc._process(.05)
		check(not motion.talking and npc.anim_player.current_animation==before,id+" closing conversation restores job")
		motion.posture="lie";motion._process(.05)
		var count: int=motion.advances
		for i in 10:motion._process(.05)
		check(motion.advances==count,id+" lying holds still")
		npc.queue_free();await process_frame;await process_frame
	# A fixed crowd: half off-screen. Count actual AnimationPlayer.advance calls,
	# not an inferred gameplay FPS improvement.
	var crowd: Array[Node] = []
	for index in 20:
		var npc := Npc.new();stage.add_child(npc);npc.setup("naru",0.0);npc.set_process(false)
		npc.position=Vector3((index%5-2)*1.7,0,-float(index/5)*2.2) if index<10 else Vector3(150+index*2,0,0)
		crowd.append(npc.motion)
	var baseline := 0;var optimized := 0
	var reads_before := Lod.plane_reads
	for enabled in [false,true]:
		for motion in crowd:motion.disabled_lod=not enabled;motion.advances=0;motion.frames=0;motion.clock=0.0
		for frame in 120:
			for motion in crowd:motion._process(1.0/60.0)
		var count := 0
		for motion in crowd:count+=motion.advances
		if enabled:optimized=count
		else:baseline=count
	check(optimized<baseline and baseline==2400,"off-screen crowd evaluates fewer animation frames")
	check(Lod.plane_reads-reads_before<=1,"camera frustum read once for the frame")
	report.crowd={"baseline_advances":baseline,"optimized_advances":optimized,"plane_reads":Lod.plane_reads-reads_before}
	var hidden= crowd[0];hidden.model.visible=false;var count: int=hidden.advances
	for i in 30:hidden._process(1.0/60.0)
	check(hidden.advances==count,"hidden model performs no animation advances")
	await clear_stage()
	# Real materials and imported clips in a small review scene.
	var actors: Array = []
	for index in 8:
		var id: String=Roster.IDS[index];var body := hero(id)
		body.position=Vector3((index%4-1.5)*2.2,0,-float(index/4)*3.0)
		body.visual.rotation.y=PI
		var clip: String=["greet","chop","punch","hurt","relax","fold_arms","clap","cheer"][index]
		if clip=="chop":body.equip("axe")
		body.animation_player.play(clip,0);body.animation_player.seek(body.animation_player.get_animation(clip).length*.35,true)
		actors.append({"body":body,"animator":body.animation_player,"clip":clip})
		var label := Art.label3d(stage,id+" / "+clip,body.position+Vector3(0,2.1,0),Color("263e37"));label.font_size=38;label.pixel_size=.006
	for index in 4:
		var id: String=["naru","sora","moru","haeru"][index]
		var npc := Npc.new();stage.add_child(npc);npc.setup(id,PI);npc.set_process(false)
		npc.position=Vector3((index-1.5)*2.2,0,-6);npc.rotation.y=0.0
		var clip: String=["greet","agree","fold_arms","wait"][index]
		npc.anim_player.play(clip,0);npc.anim_player.seek(npc.anim_player.get_animation(clip).length*.35,true)
		actors.append({"body":npc,"animator":npc.anim_player,"clip":clip})
		var label := Art.label3d(stage,id+" / "+clip,npc.position+Vector3(0,2.1,0),Color("263e37"));label.font_size=38;label.pixel_size=.006
	await capture("context-characters-materials")
	if DisplayServer.get_name()!="headless":
		for frame in 16:
			for record in actors:
				var player: AnimationPlayer=record.animator
				player.seek(player.get_animation(record.clip).length*(.1+.7*frame/16.0),true)
			await capture("context-preview-%02d"%frame)
	report.checks=checks;report.failures=failures
	FileAccess.open(folder.path_join("context-motion-results.json"),FileAccess.WRITE).store_string(JSON.stringify(report,"\t"))
	print("CONTEXT_MOTION_DONE checks=%d failures=%d"%[checks,failures]);quit(1 if failures else 0)
