extends Control
## Independent comparison of video-derived animation; no provider/network calls.
const SOURCES := ["seedance2", "pixverse6", "kling3"]
const LABELS := ["Seedance 2.0", "PixVerse V6", "Kling V3"]
var players: Array[AnimationPlayer] = []
var cameras: Array[Camera3D] = []
var roots: Array[Node3D] = []
var skeletons: Array[Skeleton3D] = []
var transition_poses: Array = []
var transition_alpha := 1.0
var time := 0.0
var playing := true
var loops := false
var timeline: HSlider
var clock: Label
var capture_dir := ""
var record := false
var record_frame := 0
var capture_index := 0
var changing_slider := false
var duration := 5.0
var clip_names: Array[String] = []
var captions: Array[Label] = []
var capturing := false
var initial_view := "side"
var captures := [.0,.6,1.0,1.6,2.2,3.0,3.8,4.6,5.0]

func material(color: String) -> StandardMaterial3D:
	var m := StandardMaterial3D.new();m.albedo_color=Color(color);m.roughness=.85;return m

func button(parent: Node,text: String,callback: Callable) -> void:
	var b := Button.new();b.text=text;b.custom_minimum_size=Vector2(130,38)
	b.pressed.connect(callback);parent.add_child(b)

func _ready() -> void:
	DisplayServer.window_set_title("Tripothon · 영상 기반 애니메이션 3종 비교")
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--capture="):capture_dir=argument.trim_prefix("--capture=")
		if argument=="--record":record=true
		if argument=="--loops":loops=true
		if argument.begins_with("--view="):initial_view=argument.trim_prefix("--view=")
	if not capture_dir.is_empty():DirAccess.make_dir_recursive_absolute(capture_dir)
	if record:DirAccess.make_dir_recursive_absolute(capture_dir.path_join("frames"))
	var background := ColorRect.new();background.color=Color("f5f1e7")
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(background)
	var font := SystemFont.new();font.font_names=PackedStringArray(["Malgun Gothic"])
	var theme := Theme.new();theme.default_font=font;theme.default_font_size=18
	theme.set_color("font_color","Label",Color("304840"));self.theme=theme
	var outer := MarginContainer.new();outer.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for key in ["margin_left","margin_right","margin_top","margin_bottom"]:outer.add_theme_constant_override(key,20)
	add_child(outer);var column := VBoxContainer.new();column.add_theme_constant_override("separation",12);outer.add_child(column)
	var title := Label.new();title.text="같은 B형 탐험가 · 영상에서 추출한 서로 다른 애니메이션"
	title.add_theme_font_size_override("font_size",27);column.add_child(title)
	var subtitle := Label.new();subtitle.text="관절 추적 → 흔들림·관절 한계 보정 → Blender 키프레임 → 실제 Godot 재생";column.add_child(subtitle)
	var row := HBoxContainer.new();row.add_theme_constant_override("separation",14)
	row.size_flags_vertical=Control.SIZE_EXPAND_FILL;column.add_child(row)
	var packed := load("res://assets/explorer_video_motions.glb") as PackedScene
	for index in 3:
		var cell := VBoxContainer.new();cell.size_flags_horizontal=Control.SIZE_EXPAND_FILL;row.add_child(cell)
		var name_label := Label.new();name_label.text=LABELS[index];name_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
		name_label.add_theme_font_size_override("font_size",22);cell.add_child(name_label)
		var viewport_container := SubViewportContainer.new();viewport_container.stretch=true
		viewport_container.size_flags_vertical=Control.SIZE_EXPAND_FILL;viewport_container.size_flags_horizontal=Control.SIZE_EXPAND_FILL
		cell.add_child(viewport_container)
		var viewport := SubViewport.new();viewport.size=Vector2i(450,640);viewport.own_world_3d=true
		viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS;viewport.msaa_3d=Viewport.MSAA_4X;viewport_container.add_child(viewport)
		var stage := Node3D.new();viewport.add_child(stage)
		var environment := WorldEnvironment.new();environment.environment=Environment.new();stage.add_child(environment)
		environment.environment.background_mode=Environment.BG_COLOR;environment.environment.background_color=Color("d3dbd1")
		environment.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
		environment.environment.ambient_light_color=Color("f1e5d1");environment.environment.ambient_light_energy=.38
		environment.environment.tonemap_mode=Environment.TONE_MAPPER_ACES
		var light := DirectionalLight3D.new();light.rotation_degrees=Vector3(-38,-36,0)
		light.light_color=Color("fff0db");light.light_energy=.75;light.shadow_enabled=true;stage.add_child(light)
		var fill := DirectionalLight3D.new();fill.rotation_degrees=Vector3(-15,130,0)
		fill.light_energy=.15;fill.light_color=Color("cedded");stage.add_child(fill)
		var floor_mesh := MeshInstance3D.new();var box := BoxMesh.new();box.size=Vector3(16,.04,16)
		floor_mesh.mesh=box;floor_mesh.position.y=-.023;floor_mesh.material_override=material("cbbfa5");stage.add_child(floor_mesh)
		for x in range(-6,7):
			var stripe := MeshInstance3D.new();var line := BoxMesh.new();line.size=Vector3(.006,.002,8)
			stripe.mesh=line;stripe.position=Vector3(float(x)*.25,0,0)
			stripe.material_override=material("b5ab96");stage.add_child(stripe)
		var model := packed.instantiate() as Node3D;model.scale=Vector3.ONE*1.7;stage.add_child(model);roots.append(model)
		var player := model.find_children("*","AnimationPlayer",true,false)[0] as AnimationPlayer
		skeletons.append(model.find_children("*","Skeleton3D",true,false)[0] as Skeleton3D)
		player.callback_mode_process=AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL;players.append(player)
		var camera := Camera3D.new();camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=2.18
		camera.near=.02;camera.far=40;stage.add_child(camera);camera.current=true;cameras.append(camera)
		var caption := Label.new();caption.text=SOURCES[index]+"_sequence · 60fps 베이크";caption.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;cell.add_child(caption)
		captions.append(caption)
	var controls := HBoxContainer.new();controls.add_theme_constant_override("separation",10);column.add_child(controls)
	button(controls,"재생 / 정지",func(): playing=not playing)
	button(controls,"처음부터",func(): time=0.0;playing=true)
	button(controls,"영상 전체 / 루프",toggle_mode)
	button(controls,"옆면",set_view.bind("side"));button(controls,"정면",set_view.bind("front"));button(controls,"뒷면",set_view.bind("back"))
	clock=Label.new();controls.add_child(clock)
	timeline=HSlider.new();timeline.min_value=0;timeline.max_value=5;timeline.step=.01;column.add_child(timeline)
	timeline.value_changed.connect(func(value: float): if not changing_slider: time=value;playing=false;apply_time())
	var note := Label.new();note.text="영상의 숨겨진 깊이는 추정·보정했습니다. 손가락·표정 추출은 포함하지 않습니다. 게임 원본 교체 없이 별도 검수합니다."
	note.add_theme_font_size_override("font_size",14);column.add_child(note)
	set_view(initial_view);select_clips();apply_time()

func select_clips() -> void:
	duration=0.0
	clip_names.clear()
	for index in 3:
		var clip: String=SOURCES[index]+("_loop" if loops else "_sequence")
		assert(players[index].has_animation(clip),"Missing exported video clip: "+clip)
		players[index].get_animation(clip).loop_mode=Animation.LOOP_NONE
		clip_names.append(clip)
		captions[index].text=clip+" · 60fps 베이크"
		players[index].play(clip);duration=maxf(duration,players[index].get_animation(clip).length)
	time=0.0;timeline.max_value=duration

func toggle_mode() -> void:
	transition_poses.clear()
	for skeleton in skeletons:
		var poses: Array=[]
		for bone in skeleton.get_bone_count():
			poses.append([skeleton.get_bone_pose_position(bone),skeleton.get_bone_pose_rotation(bone),skeleton.get_bone_pose_scale(bone)])
		transition_poses.append(poses)
	loops=not loops;select_clips();playing=true
	transition_alpha=0.0

func set_view(view: String) -> void:
	for camera in cameras:
		camera.position=Vector3(0,.93,4.0) if view=="side" else (Vector3(4,.93,0) if view=="front" else Vector3(-4,.93,0))
		camera.look_at(Vector3(0,.86,0),Vector3.UP)

func apply_time() -> void:
	for index in players.size():
		var player: AnimationPlayer=players[index]
		var clip_duration: float=player.get_animation(clip_names[index]).length
		if player.current_animation.is_empty():player.play(clip_names[index])
		player.seek(fposmod(time,clip_duration) if loops else minf(time,clip_duration-.00001),true)
		player.advance(0)
		if transition_alpha<1.0 and index<transition_poses.size():
			var skeleton: Skeleton3D=skeletons[index]
			var weight := smoothstep(0.0,1.0,transition_alpha)
			for bone in skeleton.get_bone_count():
				var old: Array=transition_poses[index][bone]
				skeleton.set_bone_pose_position(bone,old[0].lerp(skeleton.get_bone_pose_position(bone),weight))
				skeleton.set_bone_pose_rotation(bone,old[1].slerp(skeleton.get_bone_pose_rotation(bone),weight))
				skeleton.set_bone_pose_scale(bone,old[2].lerp(skeleton.get_bone_pose_scale(bone),weight))
	var display_time: float=fposmod(time,duration) if loops else time
	changing_slider=true;timeline.value=display_time;changing_slider=false
	clock.text="%.2f / %.2f초"%[display_time,duration]

func _process(delta: float) -> void:
	if capturing:return
	transition_alpha=minf(1.0,transition_alpha+delta/.24)
	if playing:time=minf(time+delta,duration)
	if time>=duration:
		if loops:time=0
		else:playing=false
	apply_time()
	if not capture_dir.is_empty():
		capturing=true
		if record:time=float(record_frame)/30.0 if loops else minf(float(record_frame)/30.0,duration);apply_time()
		await RenderingServer.frame_post_draw
		if record:
			get_viewport().get_texture().get_image().save_jpg(capture_dir.path_join("frames/frame-%04d.jpg"%record_frame),.94)
			record_frame+=1
			if record_frame>150:get_tree().quit()
		elif capture_index<captures.size() and time>=captures[capture_index]:
			get_viewport().get_texture().get_image().save_png(capture_dir.path_join("godot-%02d.png"%capture_index));capture_index+=1
			if capture_index>=captures.size():get_tree().quit()
		capturing=false
