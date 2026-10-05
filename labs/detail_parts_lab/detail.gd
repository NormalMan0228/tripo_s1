extends Node3D
var model: Node3D
var animator: AnimationPlayer
var label: Label
var camera: Camera3D
var audit := OS.get_cmdline_user_args().has("--audit")
var output := ProjectSettings.globalize_path("res://../../artifacts/detail-map-20261003/character")
var video := OS.get_cmdline_user_args().has("--record")
var frame_count := 0
func _ready() -> void:
	var env := Environment.new();env.background_mode=Environment.BG_COLOR;env.background_color=Color("e0e9e2")
	env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.ambient_light_color=Color.WHITE;env.ambient_light_energy=.5;env.tonemap_mode=Environment.TONE_MAPPER_ACES
	var we := WorldEnvironment.new();we.environment=env;add_child(we)
	var sun := DirectionalLight3D.new();sun.rotation_degrees=Vector3(-30,-40,0);sun.light_energy=1.1;add_child(sun)
	camera=Camera3D.new();camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=1.48
	camera.position=Vector3(2.5,.78,1.6);add_child(camera);camera.look_at(Vector3(0,.5,0));camera.current=true
	var canvas := CanvasLayer.new();add_child(canvas)
	var panel := PanelContainer.new();panel.position=Vector2(24,22);canvas.add_child(panel)
	var style := StyleBoxFlat.new();style.bg_color=Color("f8f0df");style.set_corner_radius_all(12);style.content_margin_left=18;style.content_margin_top=12;style.content_margin_right=18;style.content_margin_bottom=12;panel.add_theme_stylebox_override("panel",style)
	var v := VBoxContainer.new();panel.add_child(v);label=Label.new();label.add_theme_color_override("font_color",Color("314b3b"));label.add_theme_font_size_override("font_size",23);v.add_child(label)
	var row := HBoxContainer.new();v.add_child(row)
	for pair in [["손 동작","hand"],["머리카락","hair"],["세부 분할","parts"]]:
		var button := Button.new();button.text=pair[0];button.pressed.connect(show_model.bind(pair[1]));row.add_child(button)
	show_model("hand")
	if audit:call_deferred("run_audit")
	if video:DirAccess.make_dir_recursive_absolute(output+"/hand-frames")

func show_model(kind: String) -> void:
	if is_instance_valid(model):model.queue_free()
	animator=null
	var path := "open_hand_rigged.glb" if kind=="hand" else ("bob-hair.glb" if kind=="hair" else "body-detailed-segment.glb")
	model=load("res://assets/"+path).instantiate();add_child(model)
	var box := AABB();var first := true
	for m in model.find_children("*","MeshInstance3D",true,false):
		var a: AABB=m.global_transform*m.get_aabb();box=a if first else box.merge(a);first=false
	model.position=-box.get_center()+Vector3(0,.5,0)
	var players=model.find_children("*","AnimationPlayer",true,false)
	if kind=="hand" and not players.is_empty():
		animator=players[0]
		animator.get_animation("hand_gentle_grasp").loop_mode=Animation.LOOP_LINEAR;animator.play("hand_gentle_grasp")
	label.text={"hand":"독립 손 부품 · 16본 · 2.4초 동작 시험","hair":"독립 머리카락 · 머리 맞춤 전","parts":"몸체 세부 분할 · 87개 조각"}[kind]

func run_audit() -> void:
	for i in 50:await get_tree().process_frame
	var skeleton: Skeleton3D=model.find_children("*","Skeleton3D",true,false)[0]
	var clip := animator.get_animation("hand_gentle_grasp");clip.loop_mode=Animation.LOOP_NONE
	animator.seek(0,true);await get_tree().process_frame
	var initial: Array=[]
	for i in skeleton.get_bone_count():initial.append(skeleton.get_bone_pose_rotation(i))
	animator.seek(clip.length,true);await get_tree().process_frame
	var gap := 0.0
	for i in skeleton.get_bone_count():gap=maxf(gap,rad_to_deg(initial[i].angle_to(skeleton.get_bone_pose_rotation(i))))
	var result := {"bones":skeleton.get_bone_count(),"clip_seconds":clip.length,"loop_endpoint_max_gap_deg":gap,"production_body_replaced":false}
	FileAccess.open(output+"/hand-godot-audit.json",FileAccess.WRITE).store_string(JSON.stringify(result,"\t"));print("HAND_GODOT_AUDIT ",JSON.stringify(result))
	animator.seek(1.2,true);animator.pause();await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(output+"/hand-godot.png")
	get_tree().quit(0 if gap<.05 and skeleton.get_bone_count()==16 else 1)

func _process(_delta: float) -> void:
	if video:
		await RenderingServer.frame_post_draw
		var image := get_viewport().get_texture().get_image()
		image.save_jpg(output+"/hand-frames/frame-%04d.jpg"%frame_count,.9);frame_count+=1
		if frame_count>=150:get_tree().quit()
