extends Node
## One animation clock per resident, shared outdoors and in rooms. Hidden models
## do no animation work; the same frame's camera planes are cached by AnimLod.
const Motions=preload("res://scripts/context_motions.gd")
const Lod=preload("res://scripts/anim_lod.gd")
var actor: Node3D
var model: Node3D
var animator: AnimationPlayer
var actor_id := ""
var activity := "idle"
var posture := "stand"
var moving := false
var walk_speed := 1.0
var talking := false
var greeting_left := 0.0
var clock := 0.0
var frames := 0
var advances := 0
var skipped := 0
var disabled_lod := false
var focus: Node3D
var gait: SkeletonModifier3D
var current_clip := ""

func setup(body: Node3D, drawn: Node3D, player: AnimationPlayer, id: String) -> void:
	name="ContextMotion";actor=body;model=drawn;animator=player;actor_id=id
	Motions.configure(animator)
	animator.callback_mode_process=AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	var blend=preload("res://scripts/motion_blend.gd").install(animator)
	if blend!=null:
		gait=preload("res://scripts/ground_gait.gd").new()
		blend.get_parent().add_child(gait)
		gait.setup(actor,model,animator,1.0)
		gait.facing_offset=0.0 if id in ["boni","sol"] else PI/2

func set_talking(active: bool) -> void:
	if active and not talking: greet()
	if not active and talking: greeting_left=0.0
	talking=active

func greet() -> void:
	if posture=="stand" and animator.has_animation("greet"): greeting_left=2.0

func selected_clip() -> String:
	if posture!="stand": return Motions.fallback(animator,"idle")
	if moving: return Motions.fallback(animator,"walk")
	if greeting_left>0.0: return Motions.fallback(animator,"greet")
	if talking: return Motions.fallback(animator,"agree")
	return Motions.resident(animator,actor_id,activity)

func _process(delta: float) -> void:
	if not is_instance_valid(actor) or not is_instance_valid(model) or not is_instance_valid(animator): return
	if not model.is_visible_in_tree(): clock=0.0;skipped+=1;return
	greeting_left=maxf(0.0,greeting_left-delta)
	var clip := selected_clip()
	if clip.is_empty(): return
	var changed := current_clip!=clip
	if changed:
		preload("res://scripts/motion_blend.gd").play(animator,clip,.24)
		current_clip=clip
		if clip in ["relax","look_around","fold_arms","wait","work","dig"]:
			# A stable per-resident offset avoids synchronized crowd motion.
			animator.seek(fposmod(float(actor_id.hash()%1009)/1009.0,1.0)*animator.get_animation(clip).length,false)
	# Agree repeats softly only while a conversation is open. Work resumes on close.
	elif (not animator.is_playing() or (animator.get_animation(clip).loop_mode==Animation.LOOP_NONE and animator.current_animation_position>=animator.get_animation(clip).length-.18*animator.speed_scale)) and talking:
		preload("res://scripts/motion_blend.gd").play(animator,clip,.24)
		current_clip=clip
	animator.speed_scale=walk_speed if moving else (1.765 if clip=="greet" else .8 if clip=="agree" else 1.0)
	if is_instance_valid(gait):
		gait.update_motion(delta)
		if moving:
			var rate: float=gait.playback_speed()
			if rate>0.0:animator.speed_scale=rate
	clock+=delta;frames+=1
	var at := actor.global_position
	var target := focus.global_position if is_instance_valid(focus) else at
	var stride: int=1 if disabled_lod else Lod.stride(Lod.planes(get_viewport().get_camera_3d()),at,target)
	if frames%stride!=0 and not changed: skipped+=1;return
	# A sleeping/lying model holds its pose instead of breathing through the bed.
	if posture=="lie" and not changed: clock=0.0;skipped+=1;return
	preload("res://scripts/motion_blend.gd").advance(animator,clock);clock=0.0;advances+=1
