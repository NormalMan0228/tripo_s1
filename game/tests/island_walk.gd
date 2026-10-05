extends SceneTree
## Walks the player across the island village with real movement input: town green,
## workshop and home doors, the rope bridge to the camp island and the expedition gate.
## Checks the sea guard, door prompts and that the follow camera keeps the walker framed.
const Main = preload("res://scripts/main.gd")
const Town = preload("res://scripts/town.gd")
var failed := false
var app: Node3D
var test_url := "http://127.0.0.1:8766"
var lowest := INF

func _initialize() -> void:
	call_deferred("run_test")
	create_timer(300).timeout.connect(func():
		push_error("Island walk exceeded 300 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed=true

func capture(name: String) -> void:
	print("CAMERA ",name," size=",app.camera.size," at=",app.player.position)
	if "--capture" not in OS.get_cmdline_user_args(): return
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/island-walk-"+name+".png"))

func release() -> void:
	for action in ["move_left","move_right","move_forward","move_back"]: Input.action_release(action)

## Steers with the same actions the keyboard uses; the camera never rotates, so
## screen directions are world X/Z.
func walk(points: Array, label: String) -> bool:
	var player: CharacterBody3D = app.player
	for target: Vector2 in points:
		var start := Time.get_ticks_msec()
		var limit := Vector2(player.position.x,player.position.z).distance_to(target)/4.5*1000.0*2.5+3000.0
		var last_progress := Time.get_ticks_msec()
		var best := INF
		while true:
			var here := Vector2(player.position.x,player.position.z)
			var gap := target-here
			if gap.length()<0.5: break
			if gap.length()<best-0.05:
				best=gap.length()
				last_progress=Time.get_ticks_msec()
			if Time.get_ticks_msec()-start>limit or Time.get_ticks_msec()-last_progress>2500:
				release()
				print("STUCK ",label," at ",here," toward ",target)
				return false
			var d := gap.normalized()
			release()
			if d.x>0.05: Input.action_press("move_right",d.x)
			if d.x< -0.05: Input.action_press("move_left",-d.x)
			if d.y>0.05: Input.action_press("move_back",d.y)
			if d.y< -0.05: Input.action_press("move_forward",-d.y)
			lowest=minf(lowest,player.position.y)
			await physics_frame
	release()
	for i in 10: await physics_frame
	return true

func framed() -> bool:
	var at: Vector2 = app.camera.unproject_position(app.player.position+Vector3(0,1,0))
	var size: Vector2 = root.get_visible_rect().size
	return Rect2(size*0.3,size*0.4).has_point(at)

func run_test() -> void:
	app=Main.new()
	root.add_child(app)
	await process_frame
	var started := Time.get_ticks_msec()
	await app.authenticate(true,test_url,"walk_"+str(Time.get_unix_time_from_system()).replace(".","_"),"qa-local-password-123","")
	expect(app.screen=="village","island village opened")
	print("VILLAGE_READY_MS ",Time.get_ticks_msec()-started)
	if app.screen!="village":
		quit(1)
		return
	app.player.sprinting=true
	for i in 40: await physics_frame
	expect(app.player.is_on_floor(),"walker stands on the town green")
	expect(Vector2(app.player.position.x,app.player.position.z).distance_to(Town.SPAWN)<1.0,"spawned on the town green")
	expect(absf(app.camera.size-preload("res://scripts/controller_profile.gd").VILLAGE_CAMERA_DEFAULT)<0.01,"village camera starts zoomed in")
	await capture("spawn")
	expect(await walk([Vector2(-33,31),Town.WORKSHOP_DOOR],"workshop"),"walked to the workshop door")
	expect(app.life.closest().get("id","")=="workshop","workshop prompt at its door")
	expect(framed(),"camera keeps the walker framed")
	await capture("workshop")
	expect(await walk([Vector2(-33,31),Vector2(-42,33),Vector2(-50,26),Town.HOME_DOOR],"home"),"walked to the home door")
	expect(app.life.closest().get("id","")=="home","home prompt at its door")
	await capture("home")
	# Bridges are entered along their centre line; the rail end posts stand at the deck edges.
	expect(await walk([Vector2(-42,33),Vector2(-28,35),Vector2(-20,34),Vector2(-12,33),Vector2(-12,27)],"bridge approach"),"walked to the rope bridge")
	expect(await walk([Vector2(4,27)],"bridge middle"),"walked onto the rope bridge")
	expect(app.player.position.y>0.9,"bridge deck holds the walker above the water")
	await capture("bridge")
	expect(await walk([Vector2(18,27),Vector2(22,31),Vector2(30,34),Vector2(45,36),Town.GATE+Vector2(0,1.5)],"camp"),"crossed to the camp island")
	expect(app.near(Town.GATE,3),"expedition gate within reach")
	await capture("gate")
	# Walking straight out to sea stops at the shore.
	await walk([Vector2(54,52)],"beach")
	var ok := await walk([Vector2(54,75)],"sea")
	expect(not ok,"the sea does not let the walker through")
	expect(app.player.position.y>=Town.SHORE_MIN_Y-0.05,"walker stays on dry land")
	expect(lowest>=Town.SHORE_MIN_Y-0.05,"walker never sank below the shore line (lowest %.2f)"%lowest)
	await capture("shore")
	quit(1 if failed else 0)
