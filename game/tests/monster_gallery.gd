extends SceneTree
## Windowed monster gallery: all 15 survival monsters (rows = forest / quarry / frost, columns = species)
## under a night sky with the game's 45-degree orthographic camera, playing every clip in turn
## (idle, walk, run, attack, hurt, death, roar), then a short turntable. Afterwards it drives one beast
## through server snapshots (chase -> windup -> strike -> hurt -> die) and checks the clip mapping plus
## the procedural fallback.
## Run:  Godot --path game --script res://tests/monster_gallery.gd            (loops until closed)
##       Godot --path game --script res://tests/monster_gallery.gd -- --capture  (PNGs to artifacts/monsters, quits)
const Beast = preload("res://scripts/shadow_beast.gd")
const A = preload("res://scripts/art.gd")
const SPECIES := ["wolf", "boar", "brute", "wisp", "shroom"]
const NAMES := {"wolf": "그림자 늑대", "boar": "가시 멧돼지", "brute": "이끼 수호자", "wisp": "불씨 도깨비", "shroom": "버섯 망령"}
const VARIANTS := ["forest", "quarry", "frost"]
const CLIPS := ["idle", "walk", "run", "attack", "hurt", "death", "roar"]
var capture := false
var failures: Array[String] = []
var world: Node3D
var beasts: Array = []

func _initialize() -> void:
	capture = "--capture" in OS.get_cmdline_user_args()
	call_deferred("go")

func shot(name: String) -> void:
	if not capture: return
	await RenderingServer.frame_post_draw
	var dir := ProjectSettings.globalize_path("res://../artifacts/monsters")
	DirAccess.make_dir_recursive_absolute(dir)
	root.get_texture().get_image().save_png(dir + "/gallery_" + name + ".png")

func go() -> void:
	root.size = Vector2i(1600, 900)
	world = Node3D.new()
	root.add_child(world)
	var ground := A.box(world, Vector3(0, -0.1, 0), Vector3(30, 0.2, 18), Color("2d3d38"))
	ground.name = "Ground"
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color("0f1a24")
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color("7f8fb8")
	env.environment.ambient_light_energy = 0.45
	world.add_child(env)
	var moon := DirectionalLight3D.new()
	moon.rotation_degrees = Vector3(-50, -25, 0)
	moon.light_color = Color("b9c8ff")
	moon.light_energy = 0.55
	moon.shadow_enabled = true
	world.add_child(moon)
	var fire := OmniLight3D.new()
	fire.position = Vector3(0, 1.2, 6.5)
	fire.light_color = Color("ffb36b")
	fire.light_energy = 1.2
	fire.omni_range = 12
	world.add_child(fire)
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 13
	world.add_child(camera)
	camera.position = Vector3(0, 13, 13)
	camera.look_at(Vector3(0, 0.8, 0.5))
	# 1.7 m villager-height reference pole beside the grid.
	A.box(world, Vector3(-9.4, 0.85, 4.2), Vector3(0.12, 1.7, 0.12), Color("e8d9a8"))
	A.label3d(world, "1.7 m", Vector3(-9.4, 2.0, 4.2), Color("e8d9a8"))
	for row in VARIANTS.size():
		for column in SPECIES.size():
			var beast := Beast.new()
			beast.kind = SPECIES[column]
			beast.variant = VARIANTS[row]
			world.add_child(beast)
			var at := Vector3((column - 2) * 3.6, 0, (row - 1) * 4.2)
			beast.position = at
			beast.update_snapshot({"x": at.x, "z": at.z, "hp": 40, "max_hp": 40, "phase": "chase", "variant": VARIANTS[row]}, at + Vector3(0, 0, 5))
			beast.target_angle = 0.0
			beast.showcase = true
			beast.health.text = "%s · %s" % [NAMES[beast.kind], VARIANTS[row]]
			beasts.append(beast)
			if beast.monster == null: failures.append("%s_%s uses the fallback body" % [beast.kind, VARIANTS[row]])
	await create_timer(0.6).timeout
	await shot("idle")
	while true:
		for clip in CLIPS:
			var longest := 0.0
			for beast in beasts:
				if beast.monster and beast.monster.has(clip):
					beast.monster.play(clip, 0.12, 1.0, true)
					longest = maxf(longest, beast.monster.length(clip))
			if longest == 0.0: continue
			await create_timer(minf(longest, 3.0) * 0.55).timeout
			await shot(clip)
			await create_timer(minf(longest, 3.0) * 0.45 + 0.4).timeout
		for beast in beasts:
			if beast.monster: beast.monster.play("idle", 0.2)
		for step in 4:
			for beast in beasts: beast.rotation.y = step * PI / 2
			await create_timer(0.35).timeout
			await shot("turntable_%d" % (step * 90))
		for beast in beasts: beast.rotation.y = 0
		if capture: break
	await behaviour_check()
	for failure in failures: print("MONSTER_GALLERY_FAIL ", failure)
	print("MONSTER_GALLERY_COMPLETE ", failures.is_empty())
	quit(0 if failures.is_empty() else 1)

## Drive one beast with fake server snapshots and check which clip shadow_beast.gd chooses.
func behaviour_check() -> void:
	for beast in beasts: beast.queue_free()
	beasts.clear()
	await process_frame
	var beast := Beast.new()
	beast.kind = "boar"
	world.add_child(beast)
	var player := Vector3(0, 0, 6)
	var state := {"x": -4.0, "z": 0.0, "hp": 60, "max_hp": 60, "phase": "chase", "variant": "quarry", "impact": 1.1}
	beast.update_snapshot(state, player)
	if beast.monster == null or beast.variant != "quarry": failures.append("variant from snapshot not used")
	for i in 12:  # 0.9 m per 0.1 s = 9 m/s would be absurd; 0.11 m per 0.1 s = walking pace
		state.x += 0.11
		beast.update_snapshot(state, player)
		await create_timer(0.1).timeout
	if beast.clip != "walk": failures.append("boar walking pace played %s" % beast.clip)
	state.phase = "windup"
	state.target_x = 0.0
	state.target_z = 6.0
	beast.update_snapshot(state, player)
	await create_timer(0.3).timeout
	if beast.clip != "attack": failures.append("windup played %s" % beast.clip)
	state.phase = "charge"
	for i in 6:
		state.z += 0.7
		beast.update_snapshot(state, player)
		await create_timer(0.1).timeout
	if beast.clip != "run": failures.append("charge played %s" % beast.clip)
	state.phase = "recover"
	state.hp = 35
	beast.update_snapshot(state, player)
	await create_timer(0.1).timeout
	if beast.clip != "hurt": failures.append("hp drop played %s" % beast.clip)
	await shot("behaviour_hurt")
	beast.die()
	await create_timer(0.4).timeout
	if beast.clip != "death" and beast.monster and beast.monster.clip != "death": failures.append("die() did not play death")
	await create_timer(2.6).timeout
	if is_instance_valid(beast): failures.append("dead beast was not freed")
	var fallback := Beast.new()
	fallback.kind = "ghost"
	fallback.variant = "frost"
	world.add_child(fallback)
	fallback.update_snapshot({"x": 0.0, "z": 0.0, "hp": 10, "max_hp": 10}, player)
	if fallback.monster != null or fallback.body.get_child_count() == 0: failures.append("procedural fallback missing")
	fallback.queue_free()
