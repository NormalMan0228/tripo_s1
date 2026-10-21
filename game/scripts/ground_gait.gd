extends "res://scripts/locomotion_pose.gd"
## Contact IK for grounded residents and biped monsters, using their actual travel.
var facing_offset := 0.0
var drawn: Node3D
var animator: AnimationPlayer
var initialized := false
var previous_position := Vector3.INF
var measured_speed := 0.0

func setup(host: Node3D,model: Node3D,player: AnimationPlayer,forward := 1.0) -> void:
	actor=host;drawn=model;animator=player;forward_sign=forward;preserve_bend=true

func body_basis() -> Basis:return drawn.global_basis*Basis(Vector3.UP,facing_offset)
func motion_speed() -> float:return measured_speed
func motion_clip() -> String:return str(animator.assigned_animation)
func motion_phase() -> float:
	var clip := motion_clip()
	if not animator.has_animation(clip):return 0.0
	return fposmod(animator.current_animation_position/maxf(.001,animator.get_animation(clip).length),1.0)

func update_motion(delta: float) -> void:
	if not is_instance_valid(actor) or not actor.is_inside_tree():return
	if not initialized:
		configure(actor);initialized=true;previous_position=actor.global_position
	var at := actor.global_position
	var distance := Vector2(at.x-previous_position.x,at.z-previous_position.z).length()
	previous_position=at
	# Doors/teleports release contacts; they are not a running stride.
	if distance>maxf(1.0,delta*12.0):
		measured_speed=0.0
		for leg in legs:leg.contact=false
		return
	measured_speed=distance/maxf(delta,.001)

func playback_speed() -> float:
	var clip := motion_clip()
	if legs.size()!=2 or clip not in ["walk","run"]:return -1.0
	return animator.get_animation(clip).length/cycle_for_speed(measured_speed)
