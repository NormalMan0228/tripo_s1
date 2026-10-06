extends SceneTree
const Beast=preload("res://scripts/shadow_beast.gd")
const A=preload("res://scripts/art.gd")
var failed := false
func _initialize() -> void: call_deferred("go")
func go() -> void:
	var world := Node3D.new()
	root.add_child(world)
	A.box(world,Vector3(0,-0.1,0),Vector3(16,0.2,9),Color("344d4d"))
	var env := WorldEnvironment.new()
	env.environment=Environment.new()
	env.environment.background_mode=Environment.BG_COLOR
	env.environment.background_color=Color("182d35")
	env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color=Color.WHITE
	env.environment.ambient_light_energy=0.7
	world.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees=Vector3(-45,-20,0)
	sun.light_energy=0.8
	world.add_child(sun)
	var camera := Camera3D.new()
	camera.projection=Camera3D.PROJECTION_ORTHOGONAL
	camera.size=5
	world.add_child(camera)
	camera.position=Vector3(0,3.5,8)
	camera.look_at(Vector3(0,1.1,0))
	var creatures: Array=[]
	for i in 3:
		var beast := Beast.new()
		beast.kind=["wolf","brute","wisp"][i]
		world.add_child(beast)
		beast.position.x=(i-1)*2.7
		beast.update_snapshot({"x":beast.position.x,"z":0,"hp":45,"max_hp":45,"phase":"chase"},Vector3(beast.position.x,0,3))
		creatures.append(beast)
		A.label3d(world,["그림자 늑대","이끼 수호자","불씨 도깨비"][i],Vector3(beast.position.x,3.1,0),Color("e5c890"))
	await create_timer(0.4).timeout
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/monsters.png"))
	for beast in creatures:
		beast.update_snapshot({"x":beast.position.x,"z":0,"hp":40,"max_hp":45,"phase":"windup","target_x":beast.position.x,"target_z":1.5},Vector3(beast.position.x,0,3))
	await create_timer(0.75).timeout
	# Tripo monster GLB plays "attack"; the legacy brute.glb fallback plays "slash".
	if creatures[1].animator==null or creatures[1].clip!=("attack" if creatures[1].monster else "slash"): failed=true
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/monsters-windup.png"))
	world.queue_free()
	await process_frame
	print("MONSTER_GALLERY_COMPLETE ",not failed)
	quit(1 if failed else 0)
