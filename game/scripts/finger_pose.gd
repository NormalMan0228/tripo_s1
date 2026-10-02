extends SkeletonModifier3D
## Reuse only finger rotations from the reviewed hand-v4 clip, never facial tracks.
var samples: Array[Dictionary]=[]
var holding := false
var grip := 0.12

func configure(animator: AnimationPlayer) -> void:
	if not animator.has_animation("Hands_Open_Grasp"):return
	var clip: Animation=animator.get_animation("Hands_Open_Grasp")
	var skeleton := get_skeleton()
	for track in clip.get_track_count():
		if clip.track_get_type(track)!=Animation.TYPE_ROTATION_3D:continue
		var path := clip.track_get_path(track)
		if path.get_subname_count()!=1:continue
		var bone := str(path.get_subname(0))
		var finger := false
		for digit in ["Thumb_","Index_","Middle_","Ring_","Little_"]:
			if digit in bone:finger=true
		if not finger:continue
		var index := skeleton.find_bone(bone)
		if index<0:continue
		samples.append({"index":index,"right":bone.begins_with("R_"),"open":clip.rotation_track_interpolate(track,0.0),"closed":clip.rotation_track_interpolate(track,1.0)})

func _process_modification_with_delta(delta: float) -> void:
	grip=lerpf(grip,1.0 if holding else .12,1.0-exp(-10.0*delta))
	var skeleton := get_skeleton()
	if not skeleton:return
	for sample in samples:
		var from: Quaternion=sample.open
		skeleton.set_bone_pose_rotation(sample.index,from.slerp(sample.closed,grip if sample.right else .12))
