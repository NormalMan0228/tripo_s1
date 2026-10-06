extends SceneTree
const Map = preload("res://maps/archipelago/archipelago.gd")
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var cam := Camera3D.new(); root.add_child(cam)
	var map := Map.new(); root.add_child(map); map.build(cam)
	for i in 8: await physics_frame
	var space := map.get_world_3d().direct_space_state
	var a := Vector2(-15.5,36.2); var b := Vector2(-10.3,27)
	for i in 16:
		var p := a.lerp(b, i/15.0)
		var g: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(p.x,40,p.y),Vector3(p.x,-5,p.y),1))
		var shape := SphereShape3D.new(); shape.radius = 0.9
		var q := PhysicsShapeQueryParameters3D.new(); q.shape = shape; q.collision_mask = 1|2|8
		q.transform = Transform3D(Basis.IDENTITY, g.position+Vector3(0,1.1,0))
		var names := []
		for r in space.intersect_shape(q, 6):
			var c: Node = r.collider
			names.append(str(c.get_parent().get_parent().name if c.get_parent() and c.get_parent().get_parent() else c.name)+"/"+str(c.get_parent().name))
		print("AT ",p," y=",snappedf(g.position.y,0.01)," ",names)
	quit()
