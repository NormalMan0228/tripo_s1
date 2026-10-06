extends Node3D
## Visual creature only; pursuit, wind-up, charge, damage and HP come from the server.
## Body: the Tripo monster GLB for kind/variant (monster.gd: res://assets/monsters/<kind>_<variant>.glb),
## else the legacy brute.glb (brute only), else a cheap procedural body. The variant is the map's
## creature variant sent by the server with every enemy (forest / quarry / frost); set `variant` before
## add_child or let the first snapshot provide it.
const A = preload("res://scripts/art.gd")
const Monster = preload("res://scripts/monster.gd")
const AUDIO_PATH := "res://scripts/creature_audio.gd"
const WINDUP_TEXT := {"brute": "내려찍기!", "wisp": "불꽃!", "boar": "돌진!", "shroom": "포자!"}
const HOVER := {"wisp": 0.3}
## Procedural fallback tint per map variant (the GLBs carry their own regional look).
const TINT := {"forest": [Color.WHITE, 0.0], "quarry": [Color("6b3a24"), 0.28], "frost": [Color("d8ecf7"), 0.38]}
const SPORE := {"forest": Color("c8e86a"), "quarry": Color("ff9a4a"), "frost": Color("b8e6ff")}
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
var variant := ""
var animator: AnimationPlayer
var clip := ""
var monster: Node3D  ## monster.gd instance when the Tripo GLB is used
var built := false
var dying := false
var hurt_left := 0.0
var ground_speed := 0.0
var last_snapshot_ms := -1
var last_snapshot_at := Vector3.ZERO
var idle_call := 0.0
var alerted := false
var audio: Script
var showcase := false  ## galleries drive monster clips directly; skips the phase -> clip mapping

func _ready() -> void:
	health=Label3D.new()
	health.font_size=28
	health.pixel_size=0.006
	health.billboard=BaseMaterial3D.BILLBOARD_ENABLED
	add_child(health)
	if ResourceLoader.exists(AUDIO_PATH): audio=load(AUDIO_PATH)
	idle_call=randf_range(3.0,7.0)
	if variant!="": build()

func build() -> void:
	if built: return
	built=true
	body=Node3D.new()
	add_child(body)
	var height := 1.4
	var creature := Monster.new()
	if creature.setup(kind,variant):
		monster=creature
		body.add_child(creature)
		animator=creature.player
		height=creature.height
	else:
		creature.free()
		match kind:
			"brute": build_brute()
			"wisp": build_wisp()
			"boar": build_boar()
			"shroom": build_shroom()
			_: build_wolf()
		height={"brute":2.4,"wisp":1.3,"boar":1.1,"shroom":1.0}.get(kind,1.3)
		var tint: Array=TINT.get(variant,TINT.forest)
		for mesh in body.find_children("*","MeshInstance3D",true,false):
			if mesh not in eyes and mesh.material_override is StandardMaterial3D:
				materials.append(mesh.material_override)
				if tint[1]>0: mesh.material_override.albedo_color=mesh.material_override.albedo_color.lerp(tint[0],tint[1])
	health.position.y=height+HOVER.get(kind,0.0)+0.45

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

func build_boar() -> void:
	A.sphere(body,Vector3(0,0.6,0),Vector3(1.0,0.85,1.3),Color("4b3a52"))
	A.sphere(body,Vector3(0,0.62,0.66),Vector3(0.62,0.58,0.5),Color("574561"))
	A.sphere(body,Vector3(0,0.55,0.95),Vector3(0.36,0.28,0.18),Color("b07a76"))
	for i in 5:
		var spike := A.cone(body,Vector3(0,1.0,-0.4+i*0.2),0.09,0.36,Color("3d5a3a"))
		spike.rotation.x=-0.25
	for side in [-1.0,1.0]:
		var tusk := A.cone(body,Vector3(side*0.16,0.5,1.0),0.04,0.22,Color("efe2c4"))
		tusk.rotation.x=-1.2
		var eye := A.sphere(body,Vector3(side*0.18,0.78,0.86),Vector3(0.1,0.08,0.06),Color("f4c074"))
		eye.material_override.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
		eyes.append(eye)
		for z in [-0.4,0.4]:
			var leg := Node3D.new()
			leg.position=Vector3(side*0.3,0.35,z)
			body.add_child(leg)
			A.cone(leg,Vector3(0,-0.15,0),0.11,0.34,Color("3b2d40"))
			legs.append(leg)

func build_shroom() -> void:
	A.sphere(body,Vector3(0,0.38,0),Vector3(0.55,0.62,0.5),Color("d9cde6"))
	A.sphere(body,Vector3(0,0.82,0),Vector3(1.0,0.5,1.0),Color("7a4d8f"))
	for i in 6:
		A.sphere(body,Vector3(sin(i*1.05)*0.34,0.98,cos(i*1.05)*0.34),Vector3(0.14,0.06,0.14),Color("e8f0b0"))
	for side in [-1.0,1.0]:
		var eye := A.sphere(body,Vector3(side*0.12,0.5,0.24),Vector3(0.09,0.12,0.05),Color("dff07a"))
		eye.material_override.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
		eyes.append(eye)
		var leg := Node3D.new()
		leg.position=Vector3(side*0.13,0.14,0)
		body.add_child(leg)
		A.sphere(leg,Vector3(0,-0.04,0.03),Vector3(0.16,0.12,0.2),Color("cbbfd8"))
		legs.append(leg)

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
	if dying: return
	if not built:
		if variant=="": variant=str(state.get("variant","forest"))
		build()
	target_position=Vector3(state.x,0,state.z)
	var now := Time.get_ticks_msec()
	if last_snapshot_ms>=0 and now>last_snapshot_ms:
		var seconds := (now-last_snapshot_ms)/1000.0
		ground_speed=lerpf(ground_speed,Vector2(target_position.x-last_snapshot_at.x,target_position.z-last_snapshot_at.z).length()/maxf(seconds,0.016),0.5)
	last_snapshot_ms=now
	last_snapshot_at=target_position
	var previous := phase
	phase=state.get("phase","chase")
	var aim := player_at
	if phase=="windup": aim=Vector3(state.get("target_x",player_at.x),0,state.get("target_z",player_at.z))
	var direction := aim-target_position
	# Follow the actual path while walking; committed attacks keep their announced aim.
	if phase not in ["windup","recover"] and position.distance_to(target_position)>0.06:
		direction=target_position-position
	if kind=="shroom" and phase=="windup": direction=player_at-target_position
	if Vector2(direction.x,direction.z).length()>0.001: target_angle=atan2(direction.x,direction.z)
	if not alerted:
		alerted=true
		voice("alert")
	if phase=="windup" and previous!="windup":
		voice("windup")
		if monster: monster.play("attack",0.08,1.0,true)
	if previous=="windup" and phase in ["recover","charge"]:
		voice("strike")
		if kind=="shroom": burst(SPORE.get(variant,SPORE.forest),Vector3(0,0.5,0),float(state.get("impact",2.0)),26)
	if state.hp<last_hp:
		flash=0.16
		hurt_left=0.0
		voice("hurt")
		if monster:
			monster.hit_flash()
			if phase not in ["windup","charge"]:
				monster.play("hurt",0.05,1.0,true)
				hurt_left=monster.length("hurt")
	last_hp=state.hp
	health.text=tr(WINDUP_TEXT.get(kind,"!")) if phase=="windup" else "%d / %d" % [state.hp,state.get("max_hp",45)]
	health.modulate=Color("f08d72") if phase=="windup" else Color("d4dcca")

## Plays the death clip (or a collapse for procedural bodies), sinks into the ground and frees itself.
func die() -> void:
	if dying: return
	dying=true
	if not built: build()
	voice("death")
	health.visible=false
	var wait := 0.5
	if monster:
		monster.play("death",0.08,1.0,true)
		wait=monster.length("death")+0.25
		monster.glow=1.4
	else:
		var fall := create_tween()
		fall.tween_property(body,"rotation:z",1.35,0.45).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_IN)
	burst(Color("2c2440"),Vector3(0,0.6,0),0.6,18)
	var tween := create_tween()
	tween.tween_interval(wait)
	tween.tween_callback(burst.bind(SPORE.get(variant,SPORE.forest),Vector3(0,0.3,0),0.5,14))
	tween.tween_property(body,"position:y",-0.9,0.9).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	tween.parallel().tween_property(body,"scale",Vector3(0.8,0.6,0.8),0.9)
	tween.tween_callback(queue_free)

func voice(event: String) -> void:
	if audio==null or not is_inside_tree(): return
	audio.call("play",self,kind,event,global_position,variant)

## Small one-shot mote burst (spore puff, death smoke). CPUParticles3D works on Compatibility.
func burst(color: Color, at: Vector3, radius: float, amount: int) -> void:
	if not is_inside_tree(): return
	var motes := CPUParticles3D.new()
	motes.one_shot=true
	motes.amount=amount
	motes.lifetime=0.9
	motes.explosiveness=0.9
	motes.emission_shape=CPUParticles3D.EMISSION_SHAPE_SPHERE
	motes.emission_sphere_radius=maxf(0.2,radius*0.35)
	motes.direction=Vector3.UP
	motes.spread=70
	motes.initial_velocity_min=radius*0.8
	motes.initial_velocity_max=radius*1.6
	motes.gravity=Vector3(0,-0.6,0)
	motes.scale_amount_min=0.6
	motes.scale_amount_max=1.2
	var mesh := SphereMesh.new()
	mesh.radius=0.07
	mesh.height=0.14
	mesh.radial_segments=6
	mesh.rings=3
	var material := StandardMaterial3D.new()
	material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color=color
	material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	mesh.material=material
	motes.mesh=mesh
	motes.color=color
	motes.position=position+at
	get_parent().add_child(motes)
	motes.emitting=true
	get_tree().create_timer(1.6).timeout.connect(motes.queue_free)

func _process(delta: float) -> void:
	if not built: return
	clock+=delta
	var moving := position.distance_to(target_position)>0.04
	if not dying:
		position=position.lerp(target_position,minf(1,delta*15))
		rotation.y=lerp_angle(rotation.y,target_angle,minf(1,delta*10))
	idle_call-=delta
	if idle_call<=0 and not dying:
		idle_call=randf_range(5.0,10.0)
		voice("idle")
	var crouch := phase=="windup"
	if monster:
		animate_monster(delta,moving)
		if HOVER.has(kind): body.position.y=HOVER[kind]+sin(clock*3)*0.08 if not dying else body.position.y
		return
	if animator:
		var desired := "slash" if phase in ["windup","recover"] and animator.has_animation("slash") else "walk" if moving else "idle"
		if clip!=desired and animator.has_animation(desired):
			clip=desired
			animator.play(clip,0.18)
			if clip=="slash": animator.seek(1.05,true)
		animator.speed_scale=1.0 if clip=="slash" else 0.75
	if dying: return
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

## Server phase -> clip: windup = attack (its strike lands when the wind-up ends), recover = finish the
## attack then idle (a charging boar is dazed), charge = fast run, chase/warded = idle/walk/run by speed.
func animate_monster(delta: float, moving: bool) -> void:
	hurt_left=maxf(0.0,hurt_left-delta)
	clip=monster.clip
	if dying or showcase: return
	# Eyes flare during the telegraph; a soft breathing glow otherwise keeps them readable at night.
	monster.glow=lerpf(monster.glow,2.2 if phase in ["windup","charge"] else 0.55+0.15*sin(clock*2.2),minf(1,delta*8))
	if phase=="windup":
		monster.play("attack",0.08)
	elif phase=="charge":
		monster.play("run",0.1,2.0)
	elif hurt_left>0:
		pass
	elif phase=="recover" and monster.clip=="attack" and not monster.finished():
		pass
	elif phase=="recover" and kind=="boar":
		monster.play("idle",0.2,0.5)
	else:
		monster.locomote(ground_speed if moving or ground_speed>0.12 else 0.0)
	clip=monster.clip
