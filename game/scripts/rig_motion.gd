extends RefCounted
## Crafted characters with a skeleton (task 67; the server side is server/rig_pipeline.py): the
## server only accepts a GLB whose weighted bones really move, and the manifest says so
## (provenance.rig: {moves, clips ["idle", "walk"], default_clip}). In the game the default clip
## loops, and once the object is shown its bones are checked for motion (rig_moving meta).
##   RigMotion.start(model_root, rig)      # after the GLB scene is built, before it enters the tree
##   await RigMotion.verify(assembly)      # once it is in the tree: true when bones move

## The animation players a built model carries (GLTFDocument makes one per scene with clips).
## Half the footprint a moving character keeps clear around its centre, as a share of its height:
## a walk on the spot swings the feet about a third of the height forward and back.
const STRIDE := 0.35

static func players(root: Node) -> Array[AnimationPlayer]:
	var found: Array[AnimationPlayer] = []
	if root == null: return found
	for node in root.find_children("*", "AnimationPlayer", true, false):
		found.append(node)
	return found

static func skeletons(root: Node) -> Array[Skeleton3D]:
	var found: Array[Skeleton3D] = []
	if root == null: return found
	for node in root.find_children("*", "Skeleton3D", true, false):
		found.append(node)
	return found

## Loops the clips and plays `rig.default_clip` ("idle") as soon as the model is in the tree.
## Returns the player that has it, or null (a model without that clip stays still). Placed crafts
## move on the spot: every clip's root (hips) keeps its first horizontal position (lock_in_place).
static func start(root: Node, rig: Dictionary) -> AnimationPlayer:
	var clip := str(rig.get("default_clip", "idle"))
	for player in players(root):
		if not player.has_animation(clip): continue
		var skeleton: Skeleton3D = skeletons(root)[0] if not skeletons(root).is_empty() else null
		for name in player.get_animation_list():
			var animation := player.get_animation(name)
			if animation == null: continue
			animation.loop_mode = Animation.LOOP_LINEAR
			lock_in_place(animation, skeleton)
		player.autoplay = clip
		if player.is_inside_tree(): player.play(clip)
		return player
	return null

## Walks on the spot: the root bone's (and a node's own) position tracks keep their first key's x and z;
## the up and down bob stays. The craft's own transform is never animated, so it keeps the spot and
## facing it was placed with. Tripo is already asked for clips in place (server/rig_rules.py
## animate_in_place); this holds any drift it leaves.
static func lock_in_place(animation: Animation, skeleton: Skeleton3D) -> void:
	var roots := {}
	if skeleton != null:
		for bone in skeleton.get_bone_count():
			if skeleton.get_bone_parent(bone) == -1: roots[skeleton.get_bone_name(bone)] = true
	for track in animation.get_track_count():
		var path := animation.track_get_path(track)
		var bone := str(path.get_concatenated_subnames())
		var is_root := bone.is_empty() or roots.has(bone)
		if not is_root: continue
		if animation.track_get_type(track) == Animation.TYPE_POSITION_3D and animation.track_get_key_count(track) > 0:
			var first: Vector3 = animation.track_get_key_value(track, 0)
			for key in animation.track_get_key_count(track):
				var at: Vector3 = animation.track_get_key_value(track, key)
				animation.track_set_key_value(track, key, Vector3(first.x, at.y, first.z))

## Plays `clip` ("idle", "walk") on the model's player; false when it has no such clip.
static func play(root: Node, clip: String) -> bool:
	for player in players(root):
		if player.has_animation(clip):
			player.play(clip)
			return true
	return false

## The bones' local poses, every skeleton in order.
static func pose(root: Node) -> Array:
	var values := []
	for skeleton in skeletons(root):
		for bone in skeleton.get_bone_count():
			values.append(skeleton.get_bone_pose(bone))
	return values

## Whether the bones move over `seconds` once shown (sets the root's "rig_moving" meta). A character
## that stays still says so in the log: the server's check passed, so the game's playback is at fault.
static func verify(root: Node, seconds := 0.5) -> bool:
	if root == null or not root.is_inside_tree(): return false
	var tree := root.get_tree()
	var before := pose(root)
	await tree.create_timer(seconds).timeout
	if not is_instance_valid(root) or not root.is_inside_tree(): return false
	var after := pose(root)
	var moving := false
	if before.size() == after.size():
		for i in before.size():
			var a: Transform3D = before[i]
			var b: Transform3D = after[i]
			if not a.is_equal_approx(b):
				moving = true
				break
	root.set_meta("rig_moving", moving)
	if not moving and not before.is_empty(): push_warning("Crafted character '%s': its bones did not move after %.1f s" % [root.name, seconds])
	return moving
