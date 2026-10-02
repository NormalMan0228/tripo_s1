extends Node3D
## Authored Explorer B: original face/hand-v4 mesh, existing hand and body clips.
var actor: Node3D
var animator: AnimationPlayer
var active := ""
var body_skeleton: Skeleton3D
var wardrobe := false

func _ready() -> void:
	actor=(load("res://assets/explorer_b_wardrobe.glb" if wardrobe else "res://assets/explorer_b_reference.glb") as PackedScene).instantiate()
	actor.rotation.y=-PI*.5
	add_child(actor)
	var skeletons := actor.find_children("*","Skeleton3D",true,false)
	if skeletons.is_empty():return
	body_skeleton=skeletons[0]
	var animations := actor.find_children("*","AnimationPlayer",true,false)
	if animations.is_empty():return
	animator=animations[0]
	var reference := (load("res://assets/explorer_b_motion.glb") as PackedScene).instantiate()
	var sources := reference.find_children("*","AnimationPlayer",true,false)
	if not sources.is_empty():
		var library := AnimationLibrary.new()
		for source_name in sources[0].get_animation_list():
			if source_name=="RESET":continue
			var clip: Animation=sources[0].get_animation(source_name).duplicate(true)
			var animator_root: Node=animator.get_node(animator.root_node)
			for track in range(clip.get_track_count()-1,-1,-1):
				var path := clip.track_get_path(track)
				if path.get_subname_count()!=1:
					clip.remove_track(track);continue
				var bone := str(path.get_subname(0))
				if body_skeleton.find_bone(bone)<0:
					clip.remove_track(track);continue
				clip.track_set_path(track,NodePath(str(animator_root.get_path_to(body_skeleton))+":"+bone))
			clip.loop_mode=Animation.LOOP_LINEAR
			library.add_animation(source_name,clip)
		animator.add_animation_library("movement",library)
	reference.free()
	set_walking(false)

func set_walking(walking: bool) -> void:
	if not is_instance_valid(animator):return
	var target := "movement/B_TrailWalk" if walking else "movement/B_Scout"
	if target==active:return
	if animator.has_animation(target):
		animator.play(target,0.18);active=target

func show_hands() -> void:
	if is_instance_valid(animator) and animator.has_animation("Hands_Open_Grasp"):
		animator.play("Hands_Open_Grasp",0.2);active="Hands_Open_Grasp"
