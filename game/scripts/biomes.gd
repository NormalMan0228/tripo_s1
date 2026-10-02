extends RefCounted
const A = preload("res://scripts/art.gd")
const L = preload("res://scripts/world_detail.gd")

static func build(parent: Node3D, state: Dictionary) -> void:
	var region: String=state.get("map_id","forest")
	L.forest(parent)
	if region=="forest": return
	var snow := region=="frost"
	for mesh in parent.find_children("*","MeshInstance3D",true,false):
		var mat: Material=mesh.material_override
		if mat is ShaderMaterial and mat.shader==preload("res://shaders/meadow.gdshader"):
			mat.set_shader_parameter("base_color",Color("a3c5ce") if snow else Color("957254"))
			mat.set_shader_parameter("light_color",Color("e4eee9") if snow else Color("cba47b"))
		if mesh.is_in_group("canopy") and mat is StandardMaterial3D:
			mat.albedo_color=Color("c2dcd4") if snow else Color("8b815a")
	for obstacle in state.get("obstacles",[]):
		var root := StaticBody3D.new()
		root.position=Vector3(obstacle.x,0,obstacle.z)
		parent.add_child(root)
		var shape := CollisionShape3D.new()
		var cylinder := CylinderShape3D.new()
		cylinder.radius=obstacle.radius
		cylinder.height=3
		shape.shape=cylinder
		shape.position.y=1.5
		root.add_child(shape)
		var outcrop=(load("res://assets/storybook_frost_outcrop_v1.glb" if snow else "res://assets/storybook_quarry_outcrop_v1.glb") as PackedScene).instantiate()
		outcrop.scale=Vector3(obstacle.radius,1.8,obstacle.radius);root.add_child(outcrop)
	for hazard in state.get("hazards",[]):
		var at := Vector3(hazard.x,0.035,hazard.z)
		var disk := L.cylinder(parent,at,hazard.radius,0.028,Color("9bcfdc") if snow else Color("602e27"),40)
		disk.material_override.roughness=0.18 if snow else 0.8
		for i in 7:
			var crack := A.box(parent,at+Vector3(sin(i*2.4)*hazard.radius*0.5,0.026,cos(i*2.4)*hazard.radius*0.5),Vector3(0.045,0.015,hazard.radius*0.7),Color("e9ffff") if snow else Color("ff9954"))
			crack.rotation.y=i*2.4
			crack.material_override.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
		A.label3d(parent,"얼음 · 이동 둔화" if snow else "열기 · 접근 주의",at+Vector3(0,0.45,0),Color("e5f6f4") if snow else Color("ffcb92"))
	if snow:
		var flakes := CPUParticles3D.new()
		flakes.amount=160
		flakes.lifetime=10
		flakes.emission_shape=CPUParticles3D.EMISSION_SHAPE_BOX
		flakes.emission_box_extents=Vector3(20,5,20)
		flakes.position.y=6
		flakes.direction=Vector3(0.3,-1,0.1)
		flakes.initial_velocity_min=0.5
		flakes.initial_velocity_max=0.9
		flakes.gravity=Vector3.ZERO
		flakes.scale_amount_min=0.025
		flakes.scale_amount_max=0.06
		flakes.mesh=SphereMesh.new()
		flakes.material_override=A.material(Color("effaff"))
		parent.add_child(flakes)
	else:
		for x in [-16.0,16.0]:
			for z in [-13.0,13.0]:
				# Landmarks sit beyond resource routes; these small mining props do not block.
				for dx in [-0.6,0.6]: A.box(parent,Vector3(x+dx,0.8,z),Vector3(0.16,1.6,0.16),Color("6d513f"))
				A.box(parent,Vector3(x,1.55,z),Vector3(1.6,0.2,0.22),Color("987250"))
				L.lantern(parent,Vector3(x,0,z),false)
