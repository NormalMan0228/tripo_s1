extends Node3D
## Art slice only. No provider credentials, generation calls, or production economy.
var actor: CharacterBody3D
var camera: Camera3D
var hud: CanvasLayer
var location_label: Label
var prompt: Label
var notification: Label
var dev: Label
var modal: PanelContainer
var modal_text: Label
var fade: ColorRect
var transitioning := false
var world_art: Node3D
var inside := false
var return_position := Vector3.ZERO
var crops := 0
var apples := 0
var fish := 0
var time_of_day := 0.0
var fishing_rod: Node3D
var fishing_line: ImmediateMesh
var bobber: MeshInstance3D
var points: Array[Dictionary]=[
	{"id":"home","pos":Vector3(-9,0,1.65),"verb":"집에 들어가기","name":"작은 탐험가의 집"},
	{"id":"studio","pos":Vector3(9,0,1.65),"verb":"작업실에 들어가기","name":"마을 작업실"},
	{"id":"market","pos":Vector3(-6,0,7.1),"verb":"가게 둘러보기","name":"작은 장터"},
	{"id":"garden","pos":Vector3(7.4,0,8.5),"verb":"채소 수확하기","name":"공동 텃밭"},
	{"id":"orchard","pos":Vector3(-5,0,-15.5),"verb":"사과 따기","name":"강 너머 과수원"},
	{"id":"fish","pos":Vector3(4,0,-5.7),"verb":"물가에서 낚시하기","name":"잔잔한 개울"},
	{"id":"haeru","pos":Vector3(6.1,0,-5.2),"verb":"해루와 이야기하기","name":"낚시꾼 해루"},
	{"id":"well","pos":Vector3(0,0,5.25),"verb":"우물 살펴보기","name":"마을 광장"}
]
var closest := ""
var audit := OS.get_cmdline_user_args().has("--audit")
var capture := OS.get_cmdline_user_args().has("--capture")
var recording := OS.get_cmdline_user_args().has("--record")
var closeup_tour := OS.get_cmdline_user_args().has("--closeup-tour")
var closeup := closeup_tour or OS.get_cmdline_user_args().has("--closeup")
var exterior_camera_size := 6.5 if closeup else 12.5
var recording_limit := 1500 if closeup_tour else 420
var video_frames := 0
var output := ProjectSettings.globalize_path("res://../../artifacts/detail-map-20261003/playtest"+("/closeup" if closeup else ""))
var last_camera_rotation := Vector3.ZERO
var max_camera_rotation_delta := 0.0
var max_step := 0.0
var last_actor := Vector3.ZERO
var monitoring := false
var physics_last_actor := Vector3.ZERO
var reset_step := true

func _ready() -> void:
	# Update attached props after AnimationPlayer/Skeleton3D have evaluated the pose.
	process_priority=50
	DirAccess.make_dir_recursive_absolute(output)
	if recording:DirAccess.make_dir_recursive_absolute(output+"/map-frames")
	var env := Environment.new()
	env.background_mode=Environment.BG_SKY
	var sky := Sky.new();var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color=Color("a2c4cc");sky_mat.sky_horizon_color=Color("dde5d7")
	sky_mat.ground_bottom_color=Color("7f9274");sky_mat.ground_horizon_color=Color("dde5d7")
	sky.sky_material=sky_mat;env.sky=sky
	env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.ambient_light_color=Color("e7eddb");env.ambient_light_energy=.45
	env.tonemap_mode=Environment.TONE_MAPPER_ACES;env.ssao_enabled=true;env.ssao_radius=1.0;env.ssao_intensity=1.1
	env.fog_enabled=true;env.fog_light_color=Color("cbded2");env.fog_density=.005
	var environment := WorldEnvironment.new();environment.environment=env;add_child(environment)
	var sun := DirectionalLight3D.new();sun.light_color=Color("fff0cc");sun.light_energy=1.2
	sun.rotation_degrees=Vector3(-52,-28,0);sun.shadow_enabled=true;sun.directional_shadow_max_distance=70;add_child(sun)
	world_art=load("res://assets/village.glb").instantiate();add_child(world_art)
	var fisherman: Node3D=load("res://assets/haeru_v1.glb").instantiate();add_child(fisherman)
	fisherman.position=Vector3(6.1,0,-5.2);fisherman.scale=Vector3.ONE*1.7;fisherman.rotation.y=PI*.5
	var players=fisherman.find_children("*","AnimationPlayer",true,false)
	if not players.is_empty():
		var anim: AnimationPlayer=players[0]
		if anim.has_animation("fishing"):
			anim.get_animation("fishing").loop_mode=Animation.LOOP_LINEAR;anim.play("fishing")
	attach_fishing_rod.call_deferred(fisherman)
	for m in world_art.find_children("*","MeshInstance3D",true,false):
		for i in m.mesh.get_surface_count():
			var material=m.mesh.surface_get_material(i)
			if material and "River turquoise" in material.resource_name:
				var shader := Shader.new();shader.code="shader_type spatial; render_mode cull_disabled; void fragment(){float r=sin(UV.x*160.0+TIME*.7)*sin(UV.y*90.0-TIME*.6);ALBEDO=mix(vec3(.12,.38,.38),vec3(.25,.56,.53),r*.17+.55);ROUGHNESS=.28;METALLIC=.08;}"
				var sm := ShaderMaterial.new();sm.shader=shader;m.set_surface_override_material(i,sm)
	box_collision(Vector3(0,-.26,5.6),Vector3(44,.5,22.8))
	box_collision(Vector3(0,-.26,-13.6),Vector3(44,.5,8.8))
	for p in [Vector3(-9,1.6,-1),Vector3(9,1.6,-1)]:box_collision(p,Vector3(5.0,3.2,4.7))
	for p in [Vector3(10,1.6,-14),Vector3(-13,1.6,-14)]:box_collision(p,Vector3(4.9,3.2,3.85))
	for p in [Vector3(0,.7,4),Vector3(-6,.7,6)]:box_collision(p,Vector3(1.55,1.4,1.55))
	box_collision(Vector3(6.1,.7,-5.2),Vector3(.5,1.4,.5))
	for x in [5.8,7.4,9.0]:
		for z in [8.5,10.1]:box_collision(Vector3(x,.16,z),Vector3(1.4,.32,1.35))
	for p in [Vector3(0,1,18),Vector3(0,1,-18),Vector3(-21,1,0),Vector3(21,1,0)]:box_collision(p,Vector3(44,3,1) if p.x==0 else Vector3(1,3,40))
	# Banks block the river except the ramped bridge opening.
	for x in [-11.75,11.75]:
		for z in [-6.25,-9.75]:box_collision(Vector3(x,.3,z),Vector3(20.1,1.0,.18))
	bridge_collision()
	var interior: Node3D=load("res://assets/cottage_interior.glb").instantiate();interior.position.x=100;add_child(interior)
	box_collision(Vector3(100,-.1,0),Vector3(7,.2,6.5))
	for p in [Vector3(96.5,1.5,0),Vector3(103.5,1.5,0)]:box_collision(p,Vector3(.25,3,6.5))
	box_collision(Vector3(100,1.5,-3.25),Vector3(7,3,.25));box_collision(Vector3(100,.45,-1),Vector3(1.7,.9,1.1))
	box_collision(Vector3(102.45,.45,-.4),Vector3(1.5,.9,2.7))
	actor=preload("res://actor.gd").new();add_child(actor);actor.position=Vector3(0,.1,9.2);actor.mode="play"
	camera=Camera3D.new();camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=exterior_camera_size
	camera.rotation_degrees=Vector3(-32,0,0);camera.position=actor.position+Vector3(0,12,19.2);camera.far=160;add_child(camera);camera.current=true
	make_hud();last_camera_rotation=camera.rotation;last_actor=actor.position
	if closeup_tour:call_deferred("record_closeup_tour")
	elif audit or capture:call_deferred("playtest")

func attach_fishing_rod(fisherman: Node3D) -> void:
	await get_tree().process_frame
	var skeletons := fisherman.find_children("*","Skeleton3D",true,false)
	if skeletons.is_empty():return
	var skeleton: Skeleton3D=skeletons[0]
	var hand := skeleton.find_bone("R_Hand")
	if hand<0:return
	var attachment := BoneAttachment3D.new();attachment.bone_name="R_Hand";skeleton.add_child(attachment)
	fishing_rod=Node3D.new();attachment.add_child(fishing_rod);fishing_rod.position=Vector3(0,.045,0)
	var grip := skeleton.global_transform*skeleton.get_bone_global_pose(hand)
	fishing_rod.basis=grip.basis.inverse()*Basis(Vector3.UP,fisherman.global_rotation.y)*Basis(Vector3.RIGHT,-.35)
	fishing_rod.add_child(load("res://assets/fishing_rod.glb").instantiate())
	fishing_line=ImmediateMesh.new();var line_view := MeshInstance3D.new();line_view.mesh=fishing_line
	var line_material := StandardMaterial3D.new();line_material.albedo_color=Color("615943");line_material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;line_view.material_override=line_material;add_child(line_view)
	bobber=MeshInstance3D.new();var sphere := SphereMesh.new();sphere.radius=.07;sphere.height=.14;bobber.mesh=sphere
	var paint := StandardMaterial3D.new();paint.albedo_color=Color("e88745");bobber.material_override=paint;bobber.position=Vector3(6.1,.12,-8.6);add_child(bobber)
	RenderingServer.frame_pre_draw.connect(update_fishing_line)

func update_fishing_line() -> void:
	if not is_instance_valid(fishing_rod) or not fishing_line:return
	fishing_rod.global_basis=Basis(Vector3.RIGHT,-.65+sin(time_of_day*.6)*.045)
	fishing_rod.force_update_transform()
	bobber.position.y=.12+sin(time_of_day*2)*.025
	fishing_line.clear_surfaces();fishing_line.surface_begin(Mesh.PRIMITIVE_LINES)
	fishing_line.surface_add_vertex(fishing_rod.to_global(Vector3(0,1.63,0)))
	fishing_line.surface_add_vertex(bobber.position);fishing_line.surface_end()

func box_collision(pos: Vector3,size: Vector3) -> void:
	var body := StaticBody3D.new();var col := CollisionShape3D.new();var shape := BoxShape3D.new()
	shape.size=size;col.shape=shape;body.position=pos;body.add_child(col);add_child(body)

func bridge_collision() -> void:
	var vertices := PackedVector3Array()
	var zs := [-10.3,-9.7,-8.0,-6.3,-5.7];var ys := [0.0,.16,.4,.16,0.0]
	for i in 4:
		var a := Vector3(-1.57,ys[i],zs[i]);var b := Vector3(1.57,ys[i],zs[i]);var c := Vector3(-1.57,ys[i+1],zs[i+1]);var d := Vector3(1.57,ys[i+1],zs[i+1])
		vertices.append_array([a,c,b,b,c,d])
	var shape := ConcavePolygonShape3D.new();shape.set_faces(vertices);shape.backface_collision=true
	var body := StaticBody3D.new();var col := CollisionShape3D.new();col.shape=shape;body.add_child(col);add_child(body)

func panel(color: Color=Color("f7eed9")) -> StyleBoxFlat:
	var style := StyleBoxFlat.new();style.bg_color=color
	style.set_corner_radius_all(16);style.content_margin_left=22;style.content_margin_right=22;style.content_margin_top=14;style.content_margin_bottom=14
	style.shadow_color=Color(0,0,0,.14);style.shadow_size=8;return style

func make_hud() -> void:
	hud=CanvasLayer.new();add_child(hud)
	var top := PanelContainer.new();top.position=Vector2(30,26);top.add_theme_stylebox_override("panel",panel());hud.add_child(top)
	var v := VBoxContainer.new();top.add_child(v)
	location_label=Label.new();location_label.text="바람개울 마을";location_label.add_theme_font_size_override("font_size",26);location_label.add_theme_color_override("font_color",Color("364b3c"));v.add_child(location_label)
	var subtitle := Label.new();subtitle.text="맑은 오후  ·  천천히 둘러보세요";subtitle.add_theme_color_override("font_color",Color("71816a"));v.add_child(subtitle)
	var bottom := PanelContainer.new();bottom.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT);bottom.offset_left=30;bottom.offset_top=-116;bottom.add_theme_stylebox_override("panel",panel(Color("ffffffdc")));hud.add_child(bottom)
	var b := VBoxContainer.new();bottom.add_child(b)
	prompt=Label.new();prompt.text="WASD 이동   ·   Shift 달리기   ·   E 상호작용";prompt.add_theme_color_override("font_color",Color("3c5140"));prompt.add_theme_font_size_override("font_size",20);b.add_child(prompt)
	notification=Label.new();notification.text="텃밭, 장터, 과수원과 집을 둘러보세요.";notification.add_theme_color_override("font_color",Color("687d67"));b.add_child(notification)
	dev=Label.new();dev.position=Vector2(970,26);dev.add_theme_font_size_override("font_size",16);dev.visible=false;hud.add_child(dev)
	modal=PanelContainer.new();modal.position=Vector2(420,260);modal.custom_minimum_size=Vector2(600,210);modal.add_theme_stylebox_override("panel",panel());modal.visible=false;hud.add_child(modal)
	var content := VBoxContainer.new();content.add_theme_constant_override("separation",18);modal.add_child(content)
	modal_text=Label.new();modal_text.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;modal_text.custom_minimum_size=Vector2(550,100);modal_text.add_theme_color_override("font_color",Color("354b3b"));modal_text.add_theme_font_size_override("font_size",23);content.add_child(modal_text)
	var close := Button.new();close.text="계속 둘러보기";close.pressed.connect(close_modal);content.add_child(close)
	fade=ColorRect.new();fade.color=Color(0,0,0,0);fade.mouse_filter=Control.MOUSE_FILTER_IGNORE;fade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);hud.add_child(fade)

func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.physical_keycode==KEY_F3:dev.visible=not dev.visible
		if event.physical_keycode==KEY_E:
			if modal.visible:close_modal()
			else:interact(closest)
		if event.physical_keycode==KEY_ESCAPE:close_modal()

func close_modal() -> void:
	modal.visible=false;actor.mode="play"

func _process(delta: float) -> void:
	time_of_day+=delta
	# Camera orientation never follows animation sway or character turning.
	var target := Vector3(clampf(actor.position.x,-14,14),12,clampf(actor.position.z,-12,5.5)+19.2)
	if closeup:target=Vector3(actor.position.x,12,actor.position.z+19.2)
	if inside:target=Vector3(100+(actor.position.x-100)*.2,12,19.2+.3)
	camera.position=camera.position.lerp(target,1-exp(-5*delta))
	if monitoring:
		max_camera_rotation_delta=maxf(max_camera_rotation_delta,camera.rotation.distance_to(last_camera_rotation))
	last_camera_rotation=camera.rotation;last_actor=actor.position
	closest="";var distance := 2.15
	if inside:
		if actor.position.distance_to(Vector3(100,0,2.7))<2.3:closest="exit"
	else:
		for point in points:
			var d: float=actor.position.distance_to(point.pos)
			if d<distance:closest=point.id;distance=d
	var verb := ""
	if closest=="exit":verb="마을로 나가기"
	else:
		for point in points:
			if point.id==closest:verb=point.verb
	prompt.text="E  ·  "+verb if not verb.is_empty() else "WASD 이동   ·   Shift 달리기   ·   E 상호작용"
	location_label.text="작은 탐험가의 집" if inside else ("강 너머 과수원" if actor.position.z< -10 else "바람개울 마을")
	dev.text="ART LAB · F3\nFPS %d\n위치 %.1f, %.1f\n속도 %.2f m/s · %s\n주기 %.2f /s · 위상 %.2f\n채소 %d · 사과 %d · 물고기 %d\n실험용 로컬 상태"%[Engine.get_frames_per_second(),actor.position.x,actor.position.z,actor.speed,actor.clip,actor.playback_rate,actor.phase,crops,apples,fish]
	if recording and video_frames<recording_limit:
		await RenderingServer.frame_post_draw
		if not recording:return
		get_viewport().get_texture().get_image().save_jpg(output+"/map-frames/frame-%04d.jpg"%video_frames,.90);video_frames+=1

func _physics_process(_delta: float) -> void:
	if not is_instance_valid(actor):return
	if monitoring:
		if not reset_step:max_step=maxf(max_step,actor.position.distance_to(physics_last_actor))
		reset_step=false
	else:reset_step=true
	physics_last_actor=actor.position

func interact(id: String) -> void:
	if transitioning:return
	match id:
		"home","studio":
			transitioning=true;actor.mode="review";await fade_scene(1)
			return_position=actor.position;inside=true;actor.position=Vector3(100,.1,2.4);actor.velocity=Vector3.ZERO
			camera.size=6.5 if closeup else 7.5;camera.position=Vector3(100,12,19.5);notification.text="E로 출입구를 이용해 마을로 돌아갈 수 있어요."
			await fade_scene(0);transitioning=false;actor.mode="play"
		"exit":
			transitioning=true;actor.mode="review";await fade_scene(1)
			inside=false;actor.position=return_position+Vector3(0,.05,.45);actor.velocity=Vector3.ZERO;camera.size=exterior_camera_size;camera.position=Vector3(actor.position.x,12,actor.position.z+19.2)
			await fade_scene(0);transitioning=false;actor.mode="play"
		"garden":crops+=1;show_message("공동 텃밭\n싱싱한 채소를 수확했어요.  채소 %d개"%crops)
		"orchard":apples+=1;show_message("강 너머 과수원\n잘 익은 사과를 땄어요.  사과 %d개"%apples)
		"fish":fish+=1;show_message("잔잔한 개울\n작은 물고기가 찾아왔어요.  물고기 %d마리"%fish)
		"haeru":show_message("해루 · 낚시꾼\n오늘 물때가 좋아요.\n다리를 건너면 과수원도 둘러볼 수 있어요.")
		"market":show_message("작은 장터\n오늘의 채소와 손으로 만든 물건들이 모였어요.\n장터를 둘러보고 물가에서도 쉬어 가세요.")
		"well":show_message("마을 광장\n장터에서 텃밭으로, 다리를 건너 과수원으로.\n푸른 지붕의 집은 안으로 들어갈 수 있어요.")

func show_message(text: String) -> void:
	modal_text.text=text;modal.visible=true;actor.mode="review"

func fade_scene(alpha: float) -> void:
	var tween := create_tween();tween.tween_property(fade,"color:a",alpha,.17)
	await tween.finished

func frames(n: int) -> void:
	for i in n:await get_tree().physics_frame

func snapshot(name: String) -> void:
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(output+"/"+name+".png")

func drive_to(target: Vector2,run := false,limit := 600) -> bool:
	actor.scripted_running=run
	for i in limit:
		var offset := target-Vector2(actor.position.x,actor.position.z)
		if offset.length()<.18:
			actor.scripted_input=Vector2.ZERO;await frames(20);return true
		actor.scripted_input=offset.normalized()
		await get_tree().physics_frame
	actor.scripted_input=Vector2.ZERO;return false

func playtest() -> void:
	await frames(100);actor.scripted_control=true
	if capture:
		await snapshot("village-start")
		set_process(false);var old_pos := camera.position;var old_size := camera.size
		camera.size=42;camera.position=Vector3(0,24,38.4);hud.visible=false
		await snapshot("village-overview");camera.position=old_pos;camera.size=old_size;hud.visible=true;set_process(true)
	monitoring=true
	await drive_to(Vector2(2.6,9.2))
	await drive_to(Vector2(2.6,2.5))
	await drive_to(Vector2(2.6,-4.5),true)
	await frames(35)
	var stop_speed: float=actor.speed
	if capture:await snapshot("village-square")
	await drive_to(Vector2(0,-4.5))
	var bridge_reached: bool=await drive_to(Vector2(0,-12.5))
	if capture:await snapshot("orchard-bridge")
	# The playable walkthrough ends here. Automated wall/door probes reposition
	# the actor deliberately and must not appear as locomotion in the video.
	var continuous_video_frames: int=maxi(video_frames-1,0)
	recording=false
	# Collision probe approaches the wall from a clear street.
	monitoring=false;actor.position=Vector3(9,.05,4);actor.velocity=Vector3.ZERO;await frames(5)
	monitoring=true;actor.scripted_input=Vector2(0,-1);await frames(145);actor.scripted_input=Vector2.ZERO;await frames(20)
	var wall_blocked: bool=actor.position.z>.94
	monitoring=false;actor.position=Vector3(-9,.05,1.7);await frames(5);interact("home");await frames(70)
	var entered: bool=inside and actor.position.x>95
	if capture:await snapshot("cottage-interior")
	interact("exit");await frames(25);var returned: bool=not inside and actor.position.x<0
	interact("garden");close_modal();interact("orchard");close_modal();interact("fish");close_modal()
	var result := {"bridge_crossed":bridge_reached,"house_wall_blocks":wall_blocked,"building_entry":entered,"building_return":returned,"interaction_counters":crops==1 and apples==1 and fish==1,"stop_speed_m_s":stop_speed,"camera_rotation_delta_rad":max_camera_rotation_delta,"max_continuous_step_m":max_step,"walk_m_s":actor.WALK_SPEED,"run_m_s":actor.RUN_SPEED,"deliberate_door_scene_switches_excluded":true}
	result["video_continuous_frames"]=continuous_video_frames
	var file := FileAccess.open(output+"/playtest.json",FileAccess.WRITE);file.store_string(JSON.stringify(result,"\t"));file.close();print("VILLAGE_PLAYTEST ",JSON.stringify(result))
	if audit:get_tree().quit(0 if bridge_reached and wall_blocked and entered and returned and crops==1 and max_camera_rotation_delta<.0001 and max_step<.11 else 1)
	else:actor.scripted_control=false;actor.position=Vector3(0,.05,9.2);actor.velocity=Vector3.ZERO

func record_closeup_tour() -> void:
	# Drive the real motor, collision and interaction code; no position cuts.
	actor.scripted_control=true;actor.visual.rotation.y=PI
	await frames(60)
	if capture:await snapshot("closeup-start")
	monitoring=true
	var reached: Array[bool]=[]
	reached.append(await drive_to(Vector2(2.6,9.2)))
	reached.append(await drive_to(Vector2(2.6,2.5)))
	reached.append(await drive_to(Vector2(2.6,-4.5),true))
	reached.append(await drive_to(Vector2(5.25,-4.5)))
	var npc_in_range: bool=closest=="haeru"
	if capture:await snapshot("closeup-npc")
	interact(closest);await frames(100);close_modal()
	# Returning south also shows the face and the front of the walking pose.
	reached.append(await drive_to(Vector2(5.25,2.5)))
	reached.append(await drive_to(Vector2(9,2.5),true))
	reached.append(await drive_to(Vector2(9,1.7)))
	var door_in_range: bool=closest=="studio"
	monitoring=false;interact(closest);await frames(65)
	var entered: bool=inside
	monitoring=true
	reached.append(await drive_to(Vector2(100,1.2)))
	reached.append(await drive_to(Vector2(99.1,1.2)))
	if capture:await snapshot("closeup-interior")
	await frames(45)
	reached.append(await drive_to(Vector2(100,2.4)))
	var exit_in_range: bool=closest=="exit"
	monitoring=false;interact(closest);await frames(65)
	var returned: bool=not inside
	actor.scripted_input=Vector2.ZERO;await frames(45)
	recording=false;await RenderingServer.frame_post_draw
	var passed := not reached.has(false) and npc_in_range and door_in_range and exit_in_range and entered and returned and max_step<.11 and max_camera_rotation_delta<.0001
	var result := {"passed":passed,"route_reached":not reached.has(false),"npc_interaction_in_range":npc_in_range,"building_entry":entered,"building_return":returned,"door_interaction_in_range":door_in_range,"exit_interaction_in_range":exit_in_range,"camera_size_m":exterior_camera_size,"original_camera_size_m":12.5,"camera_rotation_delta_rad":max_camera_rotation_delta,"max_continuous_step_m":max_step,"frames":video_frames,"fps":30,"seconds":video_frames/30.0,"scripted_input_real_gameplay":true,"only_scene_transitions_reposition_actor":true}
	FileAccess.open(output+"/closeup-audit.json",FileAccess.WRITE).store_string(JSON.stringify(result,"\t"))
	print("CLOSEUP_TOUR ",JSON.stringify(result))
	get_tree().quit(0 if passed else 1)
