extends SceneTree
## Equip sockets (scripts/equip_sockets.gd, assets/equip/equip_sockets.json) on the real player:
##  - every socket exists on the explorer_b rig, and the residents' rig answers the same names;
##  - every item in the json goes on its hold socket, and on its stow socket when put down;
##  - grip contact: around the grip the item's handle surrounds the palm centre (the hand neither
##    passes through a thick part nor floats beside it): the handle's axis is within AXIS_OFF of the
##    socket origin and its radius between R_MIN and R_MAX;
##  - no jumps: the item is watched (tests/motion_watch.gd) through take -> put down -> take -> swing;
##  - estimate_grip() on the authored tool models finds the handle end they are held by;
##  - with a window: artifacts/equip-sockets-sheet.png (per item: hand close-up, stowed view).
##   Godot --path game --script res://tests/equip_sockets_check.gd [--position X,Y]  (or --headless)
const EquipSockets = preload("res://scripts/equip_sockets.gd")
const MotionWatch = preload("res://tests/motion_watch.gd")
const PlayerBody = preload("res://scripts/player.gd")
const Figure = preload("res://scripts/shadow_figure.gd")
const AXIS_OFF := 0.03
const R_MIN := 0.006
const R_MAX := 0.06
const CELL := 260
var failures := 0
var player: CharacterBody3D
var camera: Camera3D

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func(): quit(2))

func expect(value: bool, text: String) -> void:
	print(("PASS " if value else "FAIL ")+text)
	if not value: failures += 1

func frames(n: int) -> void:
	for i in n: await process_frame

func run() -> void:
	var stage := Node3D.new()
	root.add_child(stage)
	var floor := StaticBody3D.new()
	stage.add_child(floor)
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(20, 0.2, 20)
	shape.shape = box
	floor.add_child(shape)
	floor.position.y = -0.1
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-45, 150, 0)
	stage.add_child(sun)
	var sky := WorldEnvironment.new()
	sky.environment = Environment.new()
	sky.environment.background_mode = Environment.BG_COLOR
	sky.environment.background_color = Color("2a3338")
	sky.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	sky.environment.ambient_light_color = Color("c9d2d6")
	stage.add_child(sky)
	camera = Camera3D.new()
	camera.fov = 35
	stage.add_child(camera)
	camera.current = true
	player = PlayerBody.new()
	player.controls_enabled = false
	stage.add_child(player)
	await frames(10)
	expect(player.uses_sockets(), "player rig uses sockets (%s)" % EquipSockets.rig_of(player.hand_skeleton))
	for name in EquipSockets.NAMES:
		expect(player.socket(name) != null, "player socket %s" % name)
	# The residents' wardrobe rig answers the same names.
	var figure = Figure.create_still("farmer")
	if figure:
		stage.add_child(figure)
		figure.position = Vector3(3, 0, 0)
		await frames(3)
		for name in EquipSockets.NAMES:
			expect(figure.socket(name) != null, "resident socket %s" % name)
	var items: Dictionary = EquipSockets.data().get("items", {})
	var sheet := Image.create(CELL*2, CELL*items.size(), false, Image.FORMAT_RGBA8)
	sheet.fill(Color("1b2124"))
	var row := 0
	for item in items:
		var record: Dictionary = items[item]
		player.equip(item)
		await frames(20)
		var hold: Node3D = player.socket(str(record.hold))
		expect(is_instance_valid(player.tool_node) and player.tool_node.get_parent() == hold, "%s held on %s" % [item, record.hold])
		contact(item, player.tool_node, hold)
		await shoot(sheet, Vector2i(0, row), hold, item+" · "+str(record.hold))
		player.equip("")
		await frames(int(PlayerBody.SOCKET_MOVE*60)+12)
		var stow := str(record.get("stow", ""))
		if not stow.is_empty():
			var node: Node3D = player.stowed.get(item)
			expect(is_instance_valid(node) and node.get_parent() == player.socket(stow), "%s stowed on %s" % [item, stow])
			await shoot(sheet, Vector2i(1, row), player.socket(stow), item+" · "+stow, true)
		else:
			expect(not player.stowed.has(item), "%s put away (no stow socket)" % item)
		row += 1
	await transitions()
	estimates()
	if DisplayServer.get_name() != "headless":
		var out := ProjectSettings.globalize_path("res://../artifacts")
		DirAccess.make_dir_recursive_absolute(out)
		sheet.save_png(out.path_join("equip-sockets-sheet.png"))
		print("CAPTURE ", out.path_join("equip-sockets-sheet.png"))
	print("EQUIP_SOCKETS_CHECK ", "FAIL" if failures > 0 else "PASS", " failures=", failures)
	quit(1 if failures > 0 else 0)

## The handle at the palm, in the hold socket's frame (metres): every mesh part that crosses the
## socket's y = 0 plane within 4 cm. Detailed meshes give their vertices there; primitive parts (boxes,
## cylinders: vertices only at their ends) give their bounds. The slimmest crossing part is the handle.
func contact(item: String, node: Node3D, hold: Node3D) -> void:
	if not bool(EquipSockets.item(item).get("handle", true)):
		print("  GRIP %s skipped (no handle in the data)" % item)
		return
	var into := hold.global_transform.affine_inverse()
	var best := {}
	for mesh_node in node.find_children("*", "MeshInstance3D", true, false):
		var mesh := (mesh_node as MeshInstance3D).mesh
		if mesh == null: continue
		var to_socket := into*(mesh_node as MeshInstance3D).global_transform
		var near := PackedVector2Array()
		var vertices := PackedVector3Array()
		for s in mesh.get_surface_count(): vertices.append_array(mesh.surface_get_arrays(s)[Mesh.ARRAY_VERTEX])
		if vertices.size() >= 64:
			for v in vertices:
				var p := to_socket*v
				if absf(p.y) < 0.04: near.append(Vector2(p.x, p.z))
		else:
			var box := to_socket*mesh.get_aabb()
			if box.position.y <= 0.04 and box.end.y >= -0.04:
				near.append(Vector2(box.position.x, box.position.z))
				near.append(Vector2(box.end.x, box.end.z))
		if near.is_empty(): continue
		var low := near[0]
		var high := near[0]
		for q in near:
			low = Vector2(minf(low.x, q.x), minf(low.y, q.y))
			high = Vector2(maxf(high.x, q.x), maxf(high.y, q.y))
		var radius := maxf(high.x-low.x, high.y-low.y)*0.5
		if best.is_empty() or radius < float(best.radius): best = {"radius":radius, "centre":(low+high)*0.5}
	if best.is_empty():
		expect(false, "%s: no item surface at the grip (the hand holds air)" % item)
		return
	var centre: Vector2 = best.centre
	var radius: float = best.radius
	print("  GRIP %s axis_off=%.3f m radius=%.3f m" % [item, centre.length(), radius])
	expect(centre.length() <= AXIS_OFF+radius*0.5, "%s: handle axis %.3f m from the palm centre" % [item, centre.length()])
	expect(radius >= R_MIN and radius <= R_MAX, "%s: handle radius %.3f m is graspable" % [item, radius])

## Close-up of a socket into the sheet cell (col, row).
func shoot(sheet: Image, cell: Vector2i, socket: Node3D, label: String, from_back := false) -> void:
	if DisplayServer.get_name() == "headless": return
	var at := socket.global_position
	var facing: Vector3 = -player.visual.global_basis.z if not from_back else player.visual.global_basis.z
	camera.global_position = at+facing*1.1+Vector3(0, 0.25, 0)+player.visual.global_basis.x*0.35
	camera.look_at(at)
	await frames(3)
	await RenderingServer.frame_post_draw
	var shot := root.get_texture().get_image()
	var side := mini(shot.get_width(), shot.get_height())
	var crop := shot.get_region(Rect2i((shot.get_width()-side)/2, (shot.get_height()-side)/2, side, side))
	crop.resize(CELL, CELL)
	sheet.blit_rect(crop, Rect2i(0, 0, CELL, CELL), Vector2i(cell.x*CELL, cell.y*CELL))
	print("  SHOT ", label)

## Take -> put down -> take -> swing for each stowable item: the drawn item never jumps.
func transitions() -> void:
	var watch := MotionWatch.new(null)
	var ticks := Engine.get_physics_frames()
	for item in ["axe", "rod", "hoe"]:
		player.equip(item)
		await frames(2)
		var node: Node3D = player.tool_node
		# Jumps only: the hand's pose itself steps with the 60 Hz physics animation.
		watch.add("item_"+item, node, {"speed": 10.0, "vertical": 8.0, "walking": func(): return false})
		for step in ["put", "take", "swing", "put"]:
			match step:
				"put": player.equip("")
				"take": player.equip(item)
				"swing": player.react("attack")
			for i in 30:
				await process_frame
				var now := Engine.get_physics_frames()
				if now != ticks:
					watch.tick(now-ticks)
					ticks = now
				watch.frame(root.get_process_delta_time())
	var result := watch.report()
	MotionWatch.print_report("equip", result)
	expect(result.pass, "items never jump between hand and stow socket")

## The rule (equip_sockets.gd estimate_grip) on the authored tools: their handles are at the low end
## of Y (the game holds them there); tools/equip_grip_estimate.py --selftest covers the shapes.
func estimates() -> void:
	for pair in [["axe", "res://assets/authored_axe_v1.glb"], ["spear", "res://assets/authored_spear_v1.glb"], ["rod", "res://assets/fishing_rod.glb"]]:
		if not ResourceLoader.exists(pair[1]): continue
		var node := (load(pair[1]) as PackedScene).instantiate() as Node3D
		root.add_child(node)
		var guess := EquipSockets.estimate_grip(node)
		node.queue_free()
		print("  ESTIMATE %s %s" % [pair[0], JSON.stringify(guess)])
		expect(not guess.is_empty() and guess.axis == "y" and guess.handle_end == "low", "%s: estimate finds the handle at the low end of Y (%s)" % [pair[0], guess.get("rule", "-")])
