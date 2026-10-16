extends SceneTree
## Tool directions while used (the user: "도구 방향이 자연스럽게"): for each item and use, the hand
## socket's path through the real gesture (player.react -> action_pose.gd) is recorded once, then every
## turn of the item in the hand (30 degree steps on x, y, z) is scored against what the use should look
## like at its strike frame, and the best turn is printed as the json's "use" (or "rot" for a carry).
## Criteria in character space (forward = player.facing, up, from the feet):
##   hoe/attack       blade tip in front (>= 0.45 m) and low (<= 0.35 m), blade edge (+Z) down
##   watering_can/craft  spout ahead of the hand and below it (tilted to pour), spout (+X) forward
##   axe, pickaxe/gather blade tip in front (>= 0.4 m) at 0.6..1.3 m, edge (+X) forward
##   spear/attack     point in front (>= 0.6 m) at 0.7..1.4 m, shaft forward
##   rod/hold         rod forward and up; lantern/hold hangs down; umbrella/hold up; broom/hold bristles down
## Always: the tool never passes through the torso, and the tip never goes behind the back.
##   Godot --headless --path game --script res://tests/tool_use_solve.gd
const EquipSockets = preload("res://scripts/equip_sockets.gd")
const PlayerBody = preload("res://scripts/player.gd")
const STEP := 30
var player: CharacterBody3D

func _initialize() -> void:
	call_deferred("run")
	create_timer(200).timeout.connect(func(): quit(2))

func run() -> void:
	var floor := StaticBody3D.new()
	root.add_child(floor)
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(20, 0.2, 20)
	shape.shape = box
	floor.add_child(shape)
	floor.position.y = -0.1
	player = PlayerBody.new()
	player.controls_enabled = false
	root.add_child(player)
	for i in 30: await physics_frame
	var jobs := [["hoe", "attack"], ["watering_can", "craft"], ["axe", "gather"], ["pickaxe", "gather"], ["spear", "attack"],
		["rod", "hold"], ["lantern", "hold"], ["umbrella", "hold"], ["broom", "hold"]]
	var out := {}
	for job in jobs:
		var item: String = job[0]
		var kind: String = job[1]
		player.equip("")
		for i in 20: await physics_frame
		player.equip(item)
		for i in 20: await physics_frame
		var hold: Node3D = player.socket(str(EquipSockets.item(item).get("hold", "hand_r")))
		var path: Array[Transform3D] = []
		if kind == "hold":
			path.append(hold.global_transform)
		else:
			player.react(kind)
			for i in 30:
				await physics_frame
				path.append(hold.global_transform)
		var best := solve(item, kind, path)
		out[item] = best
		print("SOLVE %s/%s rot=%s score=%.3f %s" % [item, kind, str(best.rot), best.score, best.why])
	print("TOOL_USE_SOLVE ", JSON.stringify(out))
	quit(0)

## Character frame at the feet: forward (facing), up, right.
func frame() -> Dictionary:
	var f: Vector3 = player.facing
	f.y = 0
	f = f.normalized() if f.length() > 0.01 else Vector3.FORWARD
	return {"o":player.global_position, "f":f, "u":Vector3.UP, "r":f.cross(Vector3.UP).normalized()}

func local(c: Dictionary, p: Vector3) -> Vector3:
	var d: Vector3 = p-c.o
	return Vector3(d.dot(c.r), d.dot(c.u), d.dot(c.f))

func solve(item: String, kind: String, path: Array[Transform3D]) -> Dictionary:
	var record := EquipSockets.item(item)
	var tip_a: Array = record.get("tip", [0, 1, 0])
	var tip := Vector3(tip_a[0], tip_a[1], tip_a[2])
	var c := frame()
	var best := {"score":INF}
	for ax in range(0, 360, STEP):
		for ay in range(0, 360, STEP):
			for az in range(0, 360, STEP):
				var rot := [ax, ay, az]
				var rec := record.duplicate()
				rec["rot"] = rot
				var place := EquipSockets.placement(rec)
				var score := 0.0
				var why := ""
				# Through the torso / behind the back, on every frame.
				for hand in path:
					var item_x := hand*place
					for k in 7:
						var p := local(c, item_x*(tip*k/6.0))
						if p.y > 0.55 and p.y < 1.45 and Vector2(p.x, p.z).length() < 0.17: score += 1.0
					if local(c, item_x*tip).z < -0.15: score += 1.0
				# The strike frame: the hand farthest from rest (largest gesture), or the carry.
				var strike: Transform3D = path[0]
				var widest := -1.0
				for hand in path:
					var away := hand.origin.distance_to(path[0].origin)
					if away > widest:
						widest = away
						strike = hand
				var at := strike*place
				var t := local(c, at*tip)
				var g := local(c, at.origin)
				var dir_x: Vector3 = (at.basis*Vector3.RIGHT).normalized()
				var dir_y: Vector3 = (at.basis*Vector3.UP).normalized()
				var dir_z: Vector3 = (at.basis*Vector3.BACK).normalized()
				var fwd: Vector3 = c.f
				match item:
					"hoe":
						score += maxf(0.0, 0.45-t.z)+maxf(0.0, t.y-0.35)+maxf(0.0, 0.7-dir_z.dot(Vector3.DOWN))
					"watering_can":
						score += maxf(0.0, (g.z+0.12)-t.z)+maxf(0.0, t.y-(g.y-0.05))+maxf(0.0, 0.5-dir_x.dot(fwd))
					"axe", "pickaxe":
						score += maxf(0.0, 0.4-t.z)+maxf(0.0, 0.6-t.y)+maxf(0.0, t.y-1.3)+maxf(0.0, 0.7-dir_x.dot(fwd))
					"spear":
						score += maxf(0.0, 0.6-t.z)+maxf(0.0, 0.7-t.y)+maxf(0.0, t.y-1.4)+maxf(0.0, 0.7-dir_y.dot(fwd))
					"rod":
						score += maxf(0.0, 0.5-dir_y.dot(fwd))+maxf(0.0, 0.3-dir_y.dot(Vector3.UP))
					"lantern":
						score += maxf(0.0, 0.95-(-dir_y).dot(Vector3.DOWN))
					"umbrella":
						score += maxf(0.0, 0.9-dir_y.dot(Vector3.UP))
					"broom":
						score += maxf(0.0, 0.6-dir_y.dot(Vector3.DOWN))
				# Prefer the turn closest to the authored grip when scores tie.
				score += (absf(wrapf(ax, -180, 180))+absf(wrapf(ay, -180, 180))+absf(wrapf(az, -180, 180)))*0.00001
				if score < float(best.score):
					why = "tip=%s grip=%s" % [str(t.snapped(Vector3.ONE*0.01)), str(g.snapped(Vector3.ONE*0.01))]
					best = {"score":score, "rot":rot, "why":why}
	return best
