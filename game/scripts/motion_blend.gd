extends SkeletonModifier3D
## Blend from the last displayed local pose, including an interrupted transition.
## Unlike an AnimationPlayer crossfade this also survives a completed source clip.
var elapsed := 1.0
var duration := 0.0
var source: Array[Transform3D]=[]
var shown: Array[Transform3D]=[]

static func install(animator: AnimationPlayer) -> SkeletonModifier3D:
	var existing=animator.get_meta("pose_transition") if animator.has_meta("pose_transition") else null
	if is_instance_valid(existing):return existing
	var root := animator.get_node_or_null(animator.root_node)
	if root==null:return null
	var rigs := root.find_children("*","Skeleton3D",true,false)
	if root is Skeleton3D:rigs.push_front(root)
	if rigs.is_empty():return null
	var modifier: SkeletonModifier3D=load("res://scripts/motion_blend.gd").new()
	modifier.name="MotionBlend";rigs[0].add_child(modifier);rigs[0].move_child(modifier,0)
	animator.set_meta("pose_transition",modifier)
	return modifier

static func play(animator: AnimationPlayer,clip: String,seconds := .22,start := 0.0) -> void:
	var modifier=install(animator)
	if modifier!=null and not animator.assigned_animation.is_empty():modifier.begin(seconds)
	animator.play(clip,0.0)
	if start>=0.0:animator.seek(start,true)

static func advance(animator: AnimationPlayer,delta: float) -> void:
	var clip := str(animator.assigned_animation)
	if animator.is_playing() and animator.has_animation(clip):
		var animation := animator.get_animation(clip)
		# Hold the visible end pose across a loop seam, then ease into its beginning.
		if animation.loop_mode==Animation.LOOP_LINEAR and animator.current_animation_position+delta*animator.speed_scale>=animation.length:
			var modifier=install(animator)
			if modifier!=null:modifier.begin(minf(.16,animation.length*.2))
	animator.advance(delta)

func begin(seconds: float) -> void:
	var skeleton := get_skeleton()
	if skeleton==null:return
	if elapsed<duration and shown.size()==skeleton.get_bone_count():
		source=shown.duplicate()
	else:
		source.clear()
		for bone in skeleton.get_bone_count():source.append(skeleton.get_bone_pose(bone))
	shown=source.duplicate();duration=maxf(.001,seconds);elapsed=0.0

func _process_modification_with_delta(delta: float) -> void:
	if elapsed>=duration:return
	var skeleton := get_skeleton()
	if skeleton==null or source.size()!=skeleton.get_bone_count():return
	# Zero first-frame weight prevents a seek from exposing one frame of the new pose.
	var weight := smoothstep(0.0,1.0,elapsed/duration)
	for bone in source.size():
		var target := skeleton.get_bone_pose(bone)
		var pose := source[bone].interpolate_with(target,weight)
		skeleton.set_bone_pose(bone,pose);shown[bone]=pose
	elapsed+=maxf(0.0,delta)
