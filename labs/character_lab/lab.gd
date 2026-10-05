extends Node3D
## Standalone local art review. No account, DB, LLM or generation endpoints.
const Actor=preload("res://actor.gd")
var actor: CharacterBody3D
var camera: Camera3D
var sun: DirectionalLight3D
var info: Label
var mode_label: Label
var yaw := 0.0
var pitch := .10
var distance := 3.6
var focus_y := 1.02
var camera_mode := "body"
var dragging := false
var dusk := false
var clay := false
var playback := true
var elapsed := 0.0
var acceptance := false
var capture_dir := ""
var capture_phase := 0

func mat(color: String,rough := .85) -> StandardMaterial3D:
	var m := StandardMaterial3D.new();m.albedo_color=Color(color);m.roughness=rough;return m

func box(at: Vector3,size: Vector3,color: String,solid := false) -> MeshInstance3D:
	var instance := MeshInstance3D.new();var mesh := BoxMesh.new();mesh.size=size
	instance.mesh=mesh;instance.material_override=mat(color);instance.position=at;add_child(instance)
	if solid:
		var body := StaticBody3D.new();var shape := CollisionShape3D.new();var bounds := BoxShape3D.new()
		bounds.size=size;shape.shape=bounds;body.add_child(shape);instance.add_child(body)
	return instance

func cylinder(at: Vector3,radius: float,height: float,color: String) -> MeshInstance3D:
	var instance := MeshInstance3D.new();var mesh := CylinderMesh.new()
	mesh.top_radius=radius;mesh.bottom_radius=radius;mesh.height=height;mesh.radial_segments=48
	instance.mesh=mesh;instance.material_override=mat(color);instance.position=at;add_child(instance);return instance

func label3(text: String,at: Vector3) -> void:
	var node := Label3D.new();node.text=text;node.position=at;node.pixel_size=.003
	node.font_size=38;node.modulate=Color("40544f");node.outline_modulate=Color("fff6e7")
	node.billboard=BaseMaterial3D.BILLBOARD_ENABLED;add_child(node)
	var font := SystemFont.new();font.font_names=PackedStringArray(["Malgun Gothic"]);node.font=font

func _ready() -> void:
	DisplayServer.window_set_title("Tripothon · B형 탐험가 제작실 V5")
	for argument in OS.get_cmdline_user_args():
		if argument=="--acceptance":acceptance=true
		if argument.begins_with("--capture="):capture_dir=argument.trim_prefix("--capture=")
	var world := WorldEnvironment.new();world.environment=Environment.new();add_child(world)
	world.environment.background_mode=Environment.BG_COLOR;world.environment.background_color=Color("cbdcd5")
	world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	world.environment.ambient_light_color=Color("eee6d5");world.environment.ambient_light_energy=.35
	world.environment.tonemap_mode=Environment.TONE_MAPPER_ACES
	world.environment.ssao_enabled=true
	world.environment.ssao_radius=.5;world.environment.ssao_intensity=.65
	sun=DirectionalLight3D.new();sun.rotation_degrees=Vector3(-38,-30,0)
	sun.light_energy=.65;sun.light_color=Color("fff0d9");sun.shadow_enabled=true
	sun.directional_shadow_max_distance=36;sun.shadow_blur=1.5;add_child(sun)
	var fill := DirectionalLight3D.new();fill.rotation_degrees=Vector3(-20,145,0)
	fill.light_color=Color("d7e3ff");fill.light_energy=.12;add_child(fill)
	box(Vector3(0,-.15,0),Vector3(26,.3,24),"a2b896",true)
	box(Vector3(0,-.01,0),Vector3(9,.03,10),"e4d9bf")
	for x in range(-4,5):
		box(Vector3(x,.009,0),Vector3(.012,.007,10),"c9bba1")
	for z in range(-5,6):
		box(Vector3(0,.009,z),Vector3(9,.007,.012),"c9bba1")
	# A walking loop, wall, 15-degree ramp and four shallow steps.
	box(Vector3(0,-.005,-7),Vector3(19,.04,2),"cbbc9c")
	box(Vector3(-8,-.005,-2),Vector3(2,.04,12),"cbbc9c")
	box(Vector3(8,-.005,-2),Vector3(2,.04,12),"cbbc9c")
	var ramp := box(Vector3(7,.51,-2),Vector3(2,.15,4),"c8b491",true)
	ramp.rotation.x=deg_to_rad(15)
	box(Vector3(7,1.03,-4.3),Vector3(2,.2,1.8),"c8b491",true)
	for i in 4:
		var height := float(4-i)*.2
		box(Vector3(7,height*.5,-5.5-float(i)*.45),Vector3(2,height,.45),"bfa789",true)
	box(Vector3(-7,1.0,-6),Vector3(2,2,.35),"9fae99",true)
	# Proportion reference doorway, metre marker and restrained planting.
	for x in [-1.0,1.0]:box(Vector3(x,1.2,-4.3),Vector3(.12,2.4,.18),"9e8261",true)
	box(Vector3(0,2.4,-4.3),Vector3(2.12,.12,.18),"9e8261")
	label3("2.4m",Vector3(0,2.68,-4.3))
	for x in [-10.0,10.0]:
		for z in [-8.0,-2.0,4.0]:
			cylinder(Vector3(x,.22,z),.65,.44,"b29b78")
			for n in 5:
				var leaf := MeshInstance3D.new();var sphere := SphereMesh.new()
				sphere.radius=.38;sphere.height=.76;sphere.radial_segments=20;sphere.rings=12
				leaf.mesh=sphere;leaf.material_override=mat("688b60")
				leaf.position=Vector3(x+sin(n*2.4)*.3,.6+float(n)*.09,z+cos(n*2.4)*.3)
				leaf.scale=Vector3(.7,.85,.7);add_child(leaf)
	for x in [-3.4,3.4]:
		box(Vector3(x,.46,-3.5),Vector3(1.8,.12,.65),"a88860",true)
		for side in [-.65,.65]:box(Vector3(x+side,.22,-3.5),Vector3(.12,.44,.5),"6c796a",true)
	actor=Actor.new();actor.position=Vector3(0,.05,0);add_child(actor)
	camera=Camera3D.new();camera.current=true;camera.fov=32;camera.near=.03;camera.far=80;add_child(camera)
	build_ui();set_view("body")
	if acceptance:call_deferred("run_acceptance")

func panel_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new();style.bg_color=Color("fbf4e7")
	style.corner_radius_top_left=18;style.corner_radius_top_right=18
	style.corner_radius_bottom_left=18;style.corner_radius_bottom_right=18
	style.content_margin_left=22;style.content_margin_right=22
	style.content_margin_top=18;style.content_margin_bottom=18;return style

func add_button(row: HBoxContainer,text: String,callback: Callable) -> void:
	var button := Button.new();button.text=text;button.custom_minimum_size=Vector2(94,40)
	button.pressed.connect(callback);row.add_child(button)

func build_ui() -> void:
	var canvas := CanvasLayer.new();add_child(canvas)
	var control := Control.new();control.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	control.mouse_filter=Control.MOUSE_FILTER_IGNORE;canvas.add_child(control)
	var theme := Theme.new();var font := SystemFont.new();font.font_names=PackedStringArray(["Malgun Gothic"])
	theme.default_font=font;theme.default_font_size=16
	theme.set_color("font_color","Label",Color("354b43"))
	theme.set_color("font_color","Button",Color("354b43"))
	for state in ["normal","hover","pressed","focus"]:
		var style := panel_style();style.bg_color=Color("e7dcc4" if state=="pressed" else "f3ebdc")
		style.content_margin_left=12;style.content_margin_right=12
		style.content_margin_top=7;style.content_margin_bottom=7
		theme.set_stylebox(state,"Button",style)
	control.theme=theme
	var panel := PanelContainer.new();panel.position=Vector2(22,22);panel.add_theme_stylebox_override("panel",panel_style());control.add_child(panel)
	var column := VBoxContainer.new();column.add_theme_constant_override("separation",12);panel.add_child(column)
	var title := Label.new();title.text="B형 탐험가 · 제작 테스트 V5";title.add_theme_font_size_override("font_size",23);column.add_child(title)
	var subtitle := Label.new();subtitle.text="신규 몸체 + 보강한 기존 손 · Blender 전용 동작";column.add_child(subtitle)
	var views := HBoxContainer.new();column.add_child(views)
	for pair in [["전신","body"],["얼굴","face"],["손","hands"],["맵 이동","play"]]:
		add_button(views,pair[0],set_view.bind(pair[1]))
	var actions := HBoxContainer.new();column.add_child(actions)
	for pair in [["대기","idle"],["걷기","walk"],["달리기","run"],["손 동작","hands"],["팔 뻗기","reach"]]:
		add_button(actions,pair[0],set_motion.bind(pair[1]))
	var settings := HBoxContainer.new();column.add_child(settings)
	add_button(settings,"재질 / 무채색",toggle_clay)
	add_button(settings,"낮 / 저녁",toggle_light)
	add_button(settings,"재생 / 정지",toggle_pause)
	add_button(settings,"위치 초기화",reset_actor)
	mode_label=Label.new();column.add_child(mode_label)
	info=Label.new();column.add_child(info)
	var hint := Label.new();hint.text="우클릭 드래그: 회전   휠: 확대\n맵 이동: WASD · Shift 달리기 · Space 점프\nEsc: 전신 검수";column.add_child(hint)

func set_motion(value: String) -> void:
	actor.display_motion=value;actor.mode="review"
	if camera_mode=="play":set_view("body")
	actor.play_motion(value);actor.animator.active=true;playback=true

func set_view(value: String) -> void:
	camera_mode=value;actor.mode="play" if value=="play" else "review"
	actor.velocity=Vector3.ZERO
	if value=="play":distance=12.0;focus_y=.8;yaw=0;pitch=.47
	elif value=="face":distance=1.0;focus_y=1.49;yaw=0;pitch=.03
	elif value=="hands":
		distance=1.8;focus_y=1.00;yaw=-.42;pitch=.10;set_motion("hands")
	else:distance=4.6;focus_y=.95;yaw=0;pitch=.10
	if value!="play":actor.visual.rotation.y=PI
	mode_label.text="자유 이동" if value=="play" else "관찰 모드 · "+value

func toggle_clay() -> void:clay=not clay;actor.set_clay(clay)
func toggle_pause() -> void:playback=not playback;actor.animator.active=playback
func toggle_light() -> void:
	dusk=not dusk;sun.light_color=Color("ffbe83" if dusk else "fff0d9")
	sun.rotation_degrees.x=-18 if dusk else -38;sun.light_energy=.50 if dusk else .65
func reset_actor() -> void:
	actor.position=Vector3(0,.1,0);actor.velocity=Vector3.ZERO
	actor.display_motion="idle";actor.play_motion("idle");set_view("body")

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index==MOUSE_BUTTON_RIGHT:dragging=event.pressed
		if event.pressed and event.button_index==MOUSE_BUTTON_WHEEL_UP:distance=maxf(.55,distance*.9)
		if event.pressed and event.button_index==MOUSE_BUTTON_WHEEL_DOWN:distance=minf(22,distance*1.1)
	if event is InputEventMouseMotion and dragging:
		yaw-=event.relative.x*.008;pitch=clampf(pitch+event.relative.y*.005,-.25,1.0)
	if event is InputEventKey and event.pressed and event.keycode==KEY_ESCAPE:set_view("body")

func _process(delta: float) -> void:
	elapsed+=delta
	# Reserve the left side for controls, keeping close views unobstructed.
	var side_shift := distance*.12 if camera_mode!="play" else 0.0
	var target: Vector3=actor.global_position+Vector3(-cos(yaw)*side_shift,focus_y,sin(yaw)*side_shift)
	var offset := Vector3(sin(yaw)*cos(pitch),sin(pitch),cos(yaw)*cos(pitch))*distance
	camera.position=target+offset;camera.look_at(target)
	info.text="%.2f m/s · %s · %d bones"%[actor.speed,actor.clip,actor.skeleton.get_bone_count()]
	if not capture_dir.is_empty() and not acceptance and elapsed>1.5+capture_phase*1.5:
		call_deferred("capture_review")

func capture_review() -> void:
	var phase := capture_phase;capture_phase+=1
	if phase>3:return
	var names := ["body","face","hands","play"]
	set_view(names[phase]);await get_tree().create_timer(.8).timeout;await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(capture_dir.path_join("godot-"+names[phase]+".png"))
	if phase==3:get_tree().quit()

func run_acceptance() -> void:
	await get_tree().create_timer(.4).timeout
	var clips_ok := true
	for name in ["idle","walk","run","hands","reach"]:
		clips_ok=clips_ok and actor.animator.has_animation(name)
	var start: Vector3=actor.position
	actor.mode="play"
	var event := InputEventKey.new();event.physical_keycode=KEY_D;event.pressed=true;Input.parse_input_event(event)
	await get_tree().create_timer(.8).timeout
	event=InputEventKey.new();event.physical_keycode=KEY_D;event.pressed=false;Input.parse_input_event(event)
	var moved: float=actor.position.distance_to(start)
	await get_tree().create_timer(.2).timeout
	var stopped: bool=actor.clip=="idle" and actor.speed<.01
	set_view("hands");await get_tree().create_timer(.2).timeout
	var hand_clip: bool=actor.clip=="hands"
	var bones_ok: bool=actor.skeleton.get_bone_count()==71
	for side in ["L","R"]:
		for digit in ["Thumb","Index","Middle","Ring","Little"]:
			for i in range(1,4):bones_ok=bones_ok and actor.skeleton.find_bone(side+"_"+digit+"_%02d"%i)>=0
	# The wall must stop actual displacement and return locomotion to idle.
	actor.position=Vector3(-7,.1,-4);actor.mode="play"
	event=InputEventKey.new();event.physical_keycode=KEY_W;event.pressed=true;Input.parse_input_event(event)
	await get_tree().create_timer(1.1).timeout
	var wall_ok: bool=actor.position.z> -5.7 and actor.speed<.05 and actor.clip=="idle"
	event=InputEventKey.new();event.physical_keycode=KEY_W;event.pressed=false;Input.parse_input_event(event)
	# Ascend the ramp continuously from its bottom without jumping.
	actor.position=Vector3(7,.1,.35)
	event=InputEventKey.new();event.physical_keycode=KEY_W;event.pressed=true;Input.parse_input_event(event)
	await get_tree().create_timer(1.4).timeout
	var ramp_height: float=actor.position.y
	var ramp_ok: bool=ramp_height>.60 and ramp_height<1.5
	event=InputEventKey.new();event.physical_keycode=KEY_W;event.pressed=false;Input.parse_input_event(event)
	set_view("body")
	toggle_clay();var clay_ok: bool=actor.original_materials[0][0].material_override!=null;toggle_clay()
	var result := {"clips":clips_ok,"movement_m":moved,"stop_idle":stopped,"hands_clip":hand_clip,"clay":clay_ok,"bones":actor.skeleton.get_bone_count(),"finger_bones":bones_ok,"wall_stop":wall_ok,"ramp":ramp_ok,"ramp_height":ramp_height,"provider_calls":0}
	print("CHARACTER_LAB_ACCEPTANCE ",JSON.stringify(result))
	if not capture_dir.is_empty():
		reset_actor();await get_tree().process_frame;await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(capture_dir.path_join("godot-acceptance.png"))
	get_tree().quit(0 if clips_ok and moved>1.8 and moved<2.6 and stopped and hand_clip and clay_ok and bones_ok and wall_ok and ramp_ok else 1)
