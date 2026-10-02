extends SceneTree
const Player=preload("res://scripts/player.gd")
const Art=preload("res://scripts/art.gd")
var failed := false
var actors: Array=[]
func _initialize() -> void: call_deferred("run_test")
func expect(value: bool,label: String) -> void:
	print(("PASS " if value else "FAIL ")+label)
	failed=failed or not value
func capture(label: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/"+label+".png"))
func run_test() -> void:
	var world := Node3D.new()
	root.add_child(world)
	Art.box(world,Vector3(0,-0.2,0),Vector3(20,0.4,12),Color("53675d"),true)
	var env := WorldEnvironment.new()
	env.environment=Environment.new()
	env.environment.background_mode=Environment.BG_COLOR
	env.environment.background_color=Color("223b42")
	env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color=Color.WHITE
	env.environment.ambient_light_energy=0.6
	world.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees=Vector3(-40,-25,0)
	sun.light_energy=0.65
	world.add_child(sun)
	var camera := Camera3D.new()
	camera.projection=Camera3D.PROJECTION_ORTHOGONAL
	camera.size=4.1
	world.add_child(camera)
	camera.position=Vector3(0,3.1,8)
	camera.look_at(Vector3(0,1,0))
	var ids := ["explorer","ranger","tinker"]
	for i in 3:
		var p := Player.new()
		p.controls_enabled=false
		p.avatar={"character":ids[i],"headwear":"none","backpack":false}
		world.add_child(p)
		p.position.x=(i-1)*2.3
		p.facing=Vector3(0,0,1)
		actors.append(p)
		Art.label3d(world,["루 · 탐험가","미라 · 숲지기","테오 · 정비사"][i],Vector3(p.position.x,2.1,0),Color("f2dbab"))
	await create_timer(0.4).timeout
	for p in actors:
		expect(is_instance_valid(p.animation_player),p.avatar.character+" imported animated rig")
		for clip in ["idle","walk","run","slash"]: expect(p.animation_player.has_animation(clip),p.avatar.character+" "+clip)
		var surfaces := 0
		for mesh in p.visual.find_children("*","MeshInstance3D",true,false): surfaces+=mesh.mesh.get_surface_count()
		expect(surfaces>=6,p.avatar.character+" distinct weighted body surfaces")
		p.equip("axe")
	await capture("characters-idle")
	for p in actors: p.external_motion=Vector2(0,1)
	await create_timer(0.5).timeout
	for p in actors:
		var hand: Transform3D=p.hand_skeleton.global_transform*p.hand_skeleton.get_bone_global_pose(p.hand_index)
		expect(p.equipment.global_position.distance_to(hand.origin)<0.05,p.avatar.character+" tool follows hand")
		expect(p.current_clip=="walk",p.avatar.character+" walking")
	await capture("characters-walk")
	for p in actors: p.sprinting=true
	await create_timer(0.4).timeout
	for p in actors: expect(p.current_clip=="run",p.avatar.character+" separate run clip")
	await capture("characters-run")
	for p in actors:
		p.external_motion=Vector2.ZERO
		p.sprinting=false
		p.set_meta("hand_before_attack",p.hand_skeleton.get_bone_global_pose(p.hand_index).origin)
		p.react("attack")
	await create_timer(0.18).timeout
	for p in actors:
		expect(p.current_clip=="slash",p.avatar.character+" imported attack clip")
		expect(p.hand_skeleton.get_bone_global_pose(p.hand_index).origin.distance_to(p.get_meta("hand_before_attack"))>0.1,p.avatar.character+" strike uses moving section, not idle handle")
	await capture("characters-attack")
	await create_timer(0.17).timeout
	await capture("characters-strike")
	await create_timer(0.9).timeout
	for p in actors:
		expect(p.current_clip=="idle",p.avatar.character+" attack blends back")
		p.apply_avatar({"character":p.avatar.character,"hair":"#a64e2c","coat":"#6889a1","pants":"#774f3d","boots":"#30595b","skin":"#bc865c","headwear":"cap","backpack":true})
	await create_timer(0.4).timeout
	await capture("characters-customized")
	for p in actors:
		p.facing=Vector3(0,0,-1)
	await create_timer(0.5).timeout
	await capture("characters-back")
	for p in actors:
		var value: Dictionary=p.avatar.duplicate(true)
		value.backpack=false
		p.apply_avatar(value)
	await create_timer(0.4).timeout
	await capture("characters-back-no-pack")
	world.queue_free()
	await process_frame
	print("EXPANDED_MOTION_COMPLETE")
	quit(1 if failed else 0)
