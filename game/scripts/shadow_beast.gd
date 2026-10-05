extends Node3D
## Visual creature only; pursuit, wind-up, damage and HP come from the server.
const A = preload("res://scripts/art.gd")
var target_position := Vector3.ZERO
var target_angle := 0.0
var phase := "chase"
var body: Node3D
var legs: Array[Node3D]=[]
var eyes: Array[MeshInstance3D]=[]
var health: Label3D
var materials: Array[StandardMaterial3D]=[]
var clock := 0.0
var last_hp := 45.0
var flash := 0.0
var kind := "wolf"
var animator: AnimationPlayer
var clip := ""

func _ready() -> void:
	body=Node3D.new()
	add_child(body)
	if kind=="brute":
		build_brute()
	elif kind=="wisp":
		build_wisp()
	else:
		build_wolf()
	health=Label3D.new()
	health.font_size=28
	health.pixel_size=0.006
	health.position.y=2.8 if kind=="brute" else 1.85
	health.billboard=BaseMaterial3D.BILLBOARD_ENABLED
	add_child(health)
	for mesh in body.find_children("*","MeshInstance3D",true,false):
		if mesh not in eyes and mesh.material_override is StandardMaterial3D: materials.append(mesh.material_override)

func build_wolf() -> void:
	A.sphere(body,Vector3(0,0.58,0),Vector3(0.78,0.65,1.2),Color("3c5056"))
	A.sphere(body,Vector3(0,0.77,0.35),Vector3(0.83,0.8,0.74),Color("465963"))
	A.sphere(body,Vector3(0,0.92,0.66),Vector3(0.6,0.61,0.62),Color("566775"))
	A.sphere(body,Vector3(0,0.78,0.93),Vector3(0.4,0.3,0.43),Color("82908d"))
	A.sphere(body,Vector3(0,0.83,1.1),Vector3(0.19,0.12,0.09),Color("263b44"))
	for side in [-1.0,1.0]:
		var ear := A.cone(body,Vector3(side*0.24,1.27,0.5),0.18,0.58,Color("394f5d"))
		ear.rotation.z=-side*0.2
		var eye := A.sphere(body,Vector3(side*0.21,1.0,0.9),Vector3(0.12,0.09,0.07),Color("f4c074"))
		eye.material_override.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
		eyes.append(eye)
		for z in [-0.37,0.32]:
			var leg := Node3D.new()
			leg.position=Vector3(side*0.29,0.52,z)
			body.add_child(leg)
			A.cone(leg,Vector3(0,-0.19,0),0.115,0.44,Color("3e5155"))
			A.sphere(leg,Vector3(0,-0.42,0.07),Vector3(0.25,0.14,0.3),Color("596a68"))
			legs.append(leg)
	var tail := A.cone(body,Vector3(0,0.67,-0.82),0.2,0.9,Color("52646b"))
	tail.rotation.x=-1.7

func build_brute() -> void:
	if ResourceLoader.exists("res://assets/brute.glb"):
		var hero := load("res://assets/brute.glb").instantiate() as Node3D
		body.add_child(hero)
		var meshes: Array[MeshInstance3D]=[]
		var loader=preload("res://scripts/model_loader.gd")
		loader._collect_meshes(hero,meshes)
		var bounds := AABB()
		var first := true
		for mesh in meshes:
			var b: AABB=loader._local_transform(mesh,hero)*mesh.get_aabb()
			bounds=b if first else bounds.merge(b)
			first=false
		hero.scale=Vector3.ONE*(2.4/maxf(bounds.size.y,0.1))
		hero.position=-Vector3(bounds.get_center().x,bounds.position.y,bounds.get_center().z)*hero.scale
		var players := hero.find_children("*","AnimationPlayer",true,false)
		if not players.is_empty():
			animator=players[0]
			for name in ["walk","idle"]:
				if animator.has_animation(name): animator.get_animation(name).loop_mode=Animation.LOOP_LINEAR
		return
	A.sphere(body,Vector3(0,1.1,0),Vector3(1.4,1.6,0.9),Color("657965"))
	A.sphere(body,Vector3(0,2.05,0.1),Vector3(0.85,0.8,0.8),Color("889080"))
	for side in [-1.0,1.0]:
		A.sphere(body,Vector3(side*0.9,1.2,0),Vector3(0.6,1.4,0.65),Color("526b55"))
		A.sphere(body,Vector3(side*0.4,0.35,0),Vector3(0.55,0.7,0.7),Color("687563"))

func build_wisp() -> void:
	var core := A.sphere(body,Vector3(0,1.05,0),Vector3(0.55,0.72,0.55),Color("ffca7e"))
	core.material_override.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	for side in [-1.0,1.0]:
		var eye := A.sphere(body,Vector3(side*0.13,1.14,0.25),Vector3(0.1,0.15,0.07),Color("563c65"))
		eyes.append(eye)
	for i in 5:
		var petal := A.cone(body,Vector3(sin(i*TAU/5)*0.36,0.9,cos(i*TAU/5)*0.36),0.16,0.75,Color("d67a72"))
		petal.rotation.z=sin(i*TAU/5)*0.5
	var light := OmniLight3D.new()
	light.position.y=1
	light.light_color=Color("ffae66")
	light.light_energy=0.7
	light.omni_range=2.5
	body.add_child(light)

func update_snapshot(state: Dictionary, player_at: Vector3) -> void:
	target_position=Vector3(state.x,0,state.z)
	phase=state.get("phase","chase")
	var aim := player_at
	if phase=="windup": aim=Vector3(state.get("target_x",player_at.x),0,state.get("target_z",player_at.z))
	var direction := aim-target_position
	# Follow the actual path while walking; committed attacks keep their announced aim.
	if phase not in ["windup","recover"] and position.distance_to(target_position)>0.06:
		direction=target_position-position
	if Vector2(direction.x,direction.z).length()>0.001: target_angle=atan2(direction.x,direction.z)
	if state.hp<last_hp: flash=0.16
	last_hp=state.hp
	health.text=(tr("내려찍기!") if kind=="brute" else tr("불꽃!") if kind=="wisp" else "!") if phase=="windup" else "%d / %d" % [state.hp,state.get("max_hp",45)]
	health.modulate=Color("f08d72") if phase=="windup" else Color("d4dcca")

func _process(delta: float) -> void:
	clock+=delta
	var moving := position.distance_to(target_position)>0.04
	position=position.lerp(target_position,minf(1,delta*15))
	rotation.y=lerp_angle(rotation.y,target_angle,minf(1,delta*10))
	var crouch := phase=="windup"
	if animator:
		var desired := "slash" if phase in ["windup","recover"] and animator.has_animation("slash") else "walk" if moving else "idle"
		if clip!=desired and animator.has_animation(desired):
			clip=desired
			animator.play(clip,0.18)
			if clip=="slash": animator.seek(1.05,true)
		animator.speed_scale=1.0 if clip=="slash" else 0.75
	var anticipation := Vector3(1.03,0.96,1.03) if kind=="brute" else Vector3(1.14,0.68,1.16)
	body.scale=body.scale.lerp(anticipation if crouch else Vector3.ONE,minf(1,delta*16))
	body.position.y=absf(sin(clock*10))*0.035 if moving and not crouch else sin(clock*2)*0.015
	if kind=="wisp": body.position.y=sin(clock*3)*0.16
	for i in legs.size():
		legs[i].rotation.x=sin(clock*11+float(i%3)*PI)*0.45 if moving and not crouch else 0
	for eye in eyes:
		eye.material_override.albedo_color=(Color("fff3cc") if crouch else Color("59395c")) if kind=="wisp" else (Color("ff795d") if crouch else Color("f4c074"))
	flash=maxf(0,flash-delta)
	for material in materials:
		material.emission_enabled=flash>0
		material.emission=Color("cf9c66")
		material.emission_energy_multiplier=0.8
