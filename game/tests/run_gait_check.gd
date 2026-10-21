extends SceneTree
const Player=preload("res://scripts/player.gd")
const Roster=preload("res://scripts/character_roster.gd")
var failed := 0
func _initialize() -> void:call_deferred("run")
func check(ok: bool,label: String) -> void:
	if not ok:failed+=1
	print(("PASS " if ok else "FAIL ")+label)
func run() -> void:
	for id in Roster.IDS:
		var body=Player.new();body.avatar={"character":id};body.visual_only=true;body.controls_enabled=false;root.add_child(body);body.set_process(false);body.set_physics_process(false)
		body.external_velocity=Vector2(0,-4.5);body.sprinting=true;body._physics_process(1.0/60)
		var ap: AnimationPlayer=body.animation_player;var gait=body.locomotion_pose;var rig: Skeleton3D=body.hand_skeleton
		check(body.current_clip=="run" and absf(ap.speed_scale-1.0)<.001,id+" run retains native speed")
		var error := 0.0
		for frame in 180:
			body._physics_process(1.0/60)
			var before: Array[Transform3D]=[]
			for i in rig.get_bone_count():before.append(rig.get_bone_pose(i))
			gait._process_modification_with_delta(1.0/60)
			for i in rig.get_bone_count():
				error=maxf(error,before[i].basis.get_rotation_quaternion().angle_to(rig.get_bone_pose_rotation(i)))
		check(error<.001,id+" running preserves source leg and body trajectories")
		var blend=ap.get_meta("pose_transition")
		ap.seek(ap.get_animation("run").length-.001,true)
		preload("res://scripts/motion_blend.gd").advance(ap,1.0/60)
		check(blend.duration<=.0451,id+" loop seam cannot hold a foot for 0.16s")
		body.free()
	print("RUN_GAIT_DONE checks=24 failures=",failed);quit(1 if failed else 0)
