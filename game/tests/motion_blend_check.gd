extends SceneTree
const Blend=preload("res://scripts/motion_blend.gd")
const Monster=preload("res://scripts/monster.gd")
const Npc=preload("res://scripts/npc.gd")
var failures := 0
var checks := 0
func _initialize() -> void:call_deferred("run")
func check(ok: bool,label: String) -> void:
	checks+=1
	if not ok:failures+=1
	print(("PASS " if ok else "FAIL ")+label)
func pose(rig: Skeleton3D) -> Array[Quaternion]:
	var result: Array[Quaternion]=[]
	for i in rig.get_bone_count():result.append(rig.get_bone_pose_rotation(i))
	return result
func gap(a: Array[Quaternion],b: Array[Quaternion]) -> float:
	var result := 0.0
	for i in a.size():result=maxf(result,a[i].angle_to(b[i]))
	return result
func transitions(ap: AnimationPlayer,label: String) -> void:
	var idle := "idle" if ap.has_animation("idle") else "relax"
	var modifier=Blend.install(ap)
	var rig: Skeleton3D=modifier.get_skeleton()
	ap.play("attack" if ap.has_animation("attack") else "greet",0)
	ap.advance(ap.get_animation(ap.assigned_animation).length+0.1)
	var before := pose(rig)
	Blend.play(ap,"walk",.24,0)
	modifier._process_modification_with_delta(1.0/60)
	check(gap(before,pose(rig))<.002,label+" finished action keeps its end pose at transition start")
	for i in 7:
		Blend.advance(ap,1.0/60);modifier._process_modification_with_delta(1.0/60)
	before=pose(rig)
	Blend.play(ap,idle,.24,0)
	modifier._process_modification_with_delta(1.0/60)
	check(gap(before,pose(rig))<.002,label+" interrupted blend keeps displayed pose")
	for i in 20:
		Blend.advance(ap,1.0/60);modifier._process_modification_with_delta(1.0/60)
	ap.seek(ap.get_animation(idle).length-.005,true);before=pose(rig)
	Blend.advance(ap,.016667);modifier._process_modification_with_delta(.016667)
	check(gap(before,pose(rig))<.002,label+" loop seam retains prior pose")
	modifier.elapsed=modifier.duration
func update_gait(body: Node3D,ap: AnimationPlayer,gait: SkeletonModifier3D) -> void:
	if gait.has_method("update_motion"):gait.update_motion(1.0/60)
	else:
		body.current_clip=str(ap.assigned_animation)
		body.locomotion_velocity=Vector2(0,-1.2) if body.current_clip=="walk" else Vector2.ZERO
		body.gait_phase=fposmod(ap.current_animation_position/maxf(.001,ap.get_animation(ap.assigned_animation).length),1.0)
func contacts(body: Node3D,ap: AnimationPlayer,gait: SkeletonModifier3D,heading: Vector3,label: String) -> void:
	update_gait(body,ap,gait)
	check(gait.legs.size()==2,label+" detects two legs")
	ap.play("walk",0);ap.seek(0,true)
	var maximum := 0.0;var total := 0.0;var samples := 0
	for i in 180:
		body.position+=heading*1.2/60
		update_gait(body,ap,gait)
		ap.speed_scale=gait.playback_speed() if gait.has_method("playback_speed") else ap.get_animation("walk").length/gait.cycle_for_speed(1.2)
		Blend.advance(ap,1.0/60)
		if not gait.has_method("update_motion"):update_gait(body,ap,gait)
		var modifier=Blend.install(ap);modifier._process_modification_with_delta(1.0/60)
		gait._process_modification_with_delta(1.0/60)
		if i>30:
			maximum=maxf(maximum,gait.contact_error);total+=gait.contact_error;samples+=1
	check(maximum<.15 and total/maxi(1,samples)<.06,label+" planted foot error max=%.3fm mean=%.3fm"%[maximum,total/maxi(1,samples)])
	ap.play("idle" if ap.has_animation("idle") else "relax",0);ap.advance(.016667);update_gait(body,ap,gait);gait._process_modification_with_delta(1.0/60)
	check(gait.blend>.5 and gait.blend<1.0,label+" foot correction fades on stop")
func run() -> void:
	for pair in [["werewolf","forest"],["ice_shardling","frost"],["lizardman","quarry"]]:
		var body=Monster.new();check(body.setup(pair[0],pair[1]),pair[0]+" loads");root.add_child(body);body.set_process(false)
		transitions(body.player,pair[0]);contacts(body,body.player,body.foot_gait,Vector3.BACK,pair[0])
		body.play("walk",.2,1,true);body.player.seek(body.length("walk")*.37,true)
		body.play("run");check(absf(body.player.current_animation_position/body.length("run")-.37)<.001,pair[0]+" walk/run phase preserved")
		body.play("attack",.2,1,true);body.player.advance(body.length("attack")+.1);body.play("attack")
		check(not body.player.is_playing(),pair[0]+" finished attack does not retrigger")
		body.free()
	var npc=Npc.new();root.add_child(npc);npc.setup("sora",0);npc.set_process(false)
	transitions(npc.anim_player,"sora")
	contacts(npc,npc.anim_player,npc.motion.gait,npc.motion.gait.body_basis().z.normalized(),"sora")
	npc.free()
	for id in preload("res://scripts/character_roster.gd").IDS:
		var hero=preload("res://scripts/player.gd").new();hero.avatar={"character":id};hero.visual_only=true;hero.controls_enabled=false
		root.add_child(hero);hero.set_process(false);hero.set_physics_process(false)
		transitions(hero.animation_player,id)
		contacts(hero,hero.animation_player,hero.locomotion_pose,-hero.visual.global_basis.z.normalized(),id)
		hero.free()
	print("MOTION_BLEND_DONE checks=%d failures=%d"%[checks,failures]);quit(1 if failures else 0)
