extends SceneTree
const Map = preload("res://maps/archipelago/archipelago.gd")
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var cam := Camera3D.new(); root.add_child(cam)
	var map := Map.new(); root.add_child(map); map.build(cam)
	for i in 6: await physics_frame
	var space := map.get_world_3d().direct_space_state
	for spec in [["gazebo",Vector3(71,0,-36),4.2],["stage",Vector3(37,0,26),6.0],["picnic",Vector3(65,0,29),5.0]]:
		var c: Vector3 = spec[1]
		var ground: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(c.x,40,c.z+spec[2]+2),Vector3(c.x,-5,c.z+spec[2]+2),1))
		var g: float = ground.position.y
		var floor_hit: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(c.x,g+2.2,c.z),Vector3(c.x,g-1,c.z),2))
		var floor_y: float = floor_hit.position.y if not floor_hit.is_empty() else g
		var open := []
		for a in range(0,360,10):
			var dir := Vector3(sin(deg_to_rad(a)),0,cos(deg_to_rad(a)))
			var y := floor_y+0.7
			var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(c+dir*(spec[2]+1.5)+Vector3(0,y,0),c+Vector3(0,y,0),2))
			var reach: float = 0.0 if hit.is_empty() else Vector2(hit.position.x-c.x,hit.position.z-c.z).length()
			if reach < spec[2]*0.45: open.append(a)
		print("SCAN ",spec[0]," ground=",snappedf(g,0.01)," floor=",snappedf(floor_y,0.01)," open_angles=",open)
	quit()
