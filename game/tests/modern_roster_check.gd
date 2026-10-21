extends SceneTree
const Roster=preload("res://scripts/character_roster.gd")
const Look=preload("res://scripts/avatar_look.gd")
const Player=preload("res://scripts/player.gd")
const Select=preload("res://scripts/character_select.gd")
const Wardrobe=preload("res://scripts/wardrobe.gd")
var checks := 0
var failures := 0
func _initialize() -> void:call_deferred("run")
func check(ok: bool, words: String) -> void:
	checks+=1
	if not ok:failures+=1
	print(("PASS " if ok else "FAIL ")+words)
func run() -> void:
	check(Roster.IDS.size()==8 and Select.CARDS.size()==8,"exactly eight playable characters")
	for retired in ["explorer","ranger","tinker","haeru_v1","explorer_b_reference"]:
		check(not ResourceLoader.exists("res://assets/"+retired+".glb"),"retired model absent/"+retired)
	check(not ResourceLoader.exists("res://scripts/style_character.gd"),"retired player builder absent")
	for old in Roster.LEGACY:
		var look := Look.normalize({"character":old,"coat":"#123456","backpack":false})
		check(look.character==Roster.LEGACY[old] and look.coat=="#123456","saved look migrates without losing colours/"+old)
		var actor := Player.new();actor.avatar={"character":old,"backpack":false};root.add_child(actor)
		actor.set_physics_process(false)
		check(actor.avatar.character==Roster.LEGACY[old] and Look.applied(actor).model==Roster.LEGACY[old],"direct/presence body uses current model/"+old)
		if DisplayServer.get_name()!="headless":await RenderingServer.frame_post_draw
		actor.queue_free();await process_frame;await process_frame
	for v2 in [false,true]:
		var picker := Select.new();picker.avatar={"character":"explorer"};picker.v2=v2;root.add_child(picker)
		if DisplayServer.get_name()!="headless":await RenderingServer.frame_post_draw
		check(picker.cards.size()==8 and picker.editor.avatar.character in Roster.IDS,"modern selector even with old saved id/server")
		for id in Roster.IDS:
			picker.pick(id,false)
			await process_frame;await process_frame
			check(picker.editor.avatar.character==id and Look.applied(picker.editor.actor).model==id,"preview uses its own model/"+id)
			check(ResourceLoader.exists(Roster.portrait_path(id)),"modern social portrait/"+id)
		picker.queue_free();await process_frame;await process_frame
	var actor := Player.new();actor.avatar={"character":"m2","backpack":false};actor.visual_only=true;actor.controls_enabled=false;root.add_child(actor)
	actor.set_physics_process(false)
	var animator: AnimationPlayer=actor.animation_player
	animator.callback_mode_process=AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	var rig: Skeleton3D=actor.hand_skeleton
	var left: int=rig.find_bone("L_Upperarm");var right: int=rig.find_bone("R_Upperarm")
	for clip in ["idle","walk","run","slash"]:
		check(animator.has_animation(clip),"m2 clip/"+clip)
		var minimum := INF;var maximum := 0.0
		animator.play(clip,0)
		for sample in 48:
			animator.seek(animator.get_animation(clip).length*sample/48.0,true)
			var a: Vector3=rig.global_transform*rig.get_bone_global_pose(left).origin
			var b: Vector3=rig.global_transform*rig.get_bone_global_pose(right).origin
			var width: float=a.distance_to(b)
			minimum=minf(minimum,width);maximum=maxf(maximum,width)
		check(minimum>.27 and maximum<.55,"m2 shoulders do not collapse/%s [%.3f, %.3f]"%[clip,minimum,maximum])
	if DisplayServer.get_name()!="headless":await RenderingServer.frame_post_draw
	actor.queue_free();await process_frame;await process_frame
	print("MODERN_ROSTER_DONE checks=%d failures=%d"%[checks,failures]);quit(1 if failures else 0)
