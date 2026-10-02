extends Window
## Local rehearsal of server-validated numeric behavior; never publishes an asset.
const Assembly=preload("res://scripts/asset_assembly.gd")
const Art=preload("res://scripts/art.gd")
const BuildMode=preload("res://scripts/build_mode.gd")
var item: Node3D
var camera: Camera3D
var status: Label
var payload: Dictionary
var world: Node3D

func show_plan(value: Dictionary) -> bool:
	payload=value
	title="설계 동작 미리보기 · 유료 생성 전" if BuildMode.developer() else "만들기 전, 미리 살펴보기"
	size=Vector2i(820,680);min_size=Vector2i(640,540)
	var background := ColorRect.new();background.color=Color("f6efdd");background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(background)
	var box := VBoxContainer.new();box.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);box.offset_left=14;box.offset_right=-14;box.offset_top=14;box.offset_bottom=-14;add_child(box)
	var font := SystemFont.new();font.font_names=PackedStringArray(["Malgun Gothic","sans-serif"]);box.add_theme_font_override("font",font)
	var paper_theme := Theme.new();paper_theme.default_font=font;paper_theme.default_font_size=15
	paper_theme.set_color("font_color","Label",Color("3c4736"));paper_theme.set_color("font_color","Button",Color("3c4736"))
	for state_name in ["normal","hover","pressed","focus"]:
		var style := StyleBoxFlat.new();style.bg_color=Color("cdddbb") if state_name!="normal" else Color("fff9ea")
		style.set_corner_radius_all(8);style.set_border_width_all(1);style.border_color=Color("b5ac90")
		style.content_margin_left=14;style.content_margin_right=14;style.content_margin_top=10;style.content_margin_bottom=10
		paper_theme.set_stylebox(state_name,"Button",style)
	box.theme=paper_theme
	var note := Label.new();note.text="도형으로 부품과 움직임만 확인합니다. 실제 Tripo 메시의 외형과 분리는 달라질 수 있습니다.\n이 창의 조작은 저장·과금되지 않습니다. 창을 닫은 뒤 비용을 확인하고 생성하세요."
	note.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;box.add_child(note)
	if not BuildMode.developer():note.text="제작 전, 간단한 모양으로 크기와 움직임을 살펴보세요.\n완성될 가구의 모습은 달라질 수 있어요. 여기서 사용해 보는 동작은 저장되지 않아요."
	var container := SubViewportContainer.new();container.stretch=true;container.size_flags_vertical=Control.SIZE_EXPAND_FILL;box.add_child(container)
	var view := SubViewport.new();view.size=Vector2i(820,500);view.own_world_3d=true;view.render_target_update_mode=SubViewport.UPDATE_ALWAYS;container.add_child(view)
	world=Node3D.new();view.add_child(world)
	var env := WorldEnvironment.new();env.environment=Environment.new();env.environment.background_mode=Environment.BG_COLOR;env.environment.background_color=Color("a8b7a0");env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.environment.ambient_light_energy=.65;world.add_child(env)
	var light := DirectionalLight3D.new();light.rotation_degrees=Vector3(-40,-30,0);world.add_child(light)
	Art.box(world,Vector3(0,-.06,0),Vector3(30,.1,30),Color("859a80"))
	camera=Camera3D.new();camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=3.4;camera.position=Vector3(3,2.6,4);world.add_child(camera);camera.look_at(Vector3(0,.7,0));camera.current=true
	container.gui_input.connect(func(event):
		if event is InputEventMouseMotion and event.button_mask&MOUSE_BUTTON_MASK_LEFT and is_instance_valid(item):item.rotation.y+=event.relative.x*.01
		if event is InputEventMouseButton and event.pressed:
			if event.button_index==MOUSE_BUTTON_WHEEL_UP:camera.size=maxf(1.5,camera.size-.2)
			if event.button_index==MOUSE_BUTTON_WHEEL_DOWN:camera.size=minf(6,camera.size+.2))
	var actions := HBoxContainer.new();box.add_child(actions)
	for pair in [["사용 / 클릭","click"],["가까이 가기","near"],["떠나기","leave"]]:
		var button := Button.new();button.text=pair[0];actions.add_child(button);button.pressed.connect(simulate.bind(pair[1]))
	var reset := Button.new();reset.text="처음 상태";actions.add_child(reset);reset.pressed.connect(rebuild)
	var close := Button.new();close.text="닫기";actions.add_child(close);close.pressed.connect(queue_free)
	status=Label.new();status.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;box.add_child(status)
	close_requested.connect(queue_free)
	return rebuild()

func rebuild() -> bool:
	if is_instance_valid(item):item.free()
	item=Assembly.new()
	var blobs := {}
	for id in payload.blobs:blobs[id]=Marshalls.base64_to_raw(payload.blobs[id])
	if not item.build(payload,blobs):item.free();status.text="설계를 표시하지 못했습니다.";return false
	world.add_child(item)
	status.text=("%d개 부품 · "%payload.plan.parts.size() if BuildMode.developer() else "")+"드래그로 회전 · 휠로 확대\n"+str(payload.plan.get("title","가구 미리보기"))
	return true

func simulate(event: String) -> void:
	if not is_instance_valid(item):return
	if event=="near":item.nearby=true
	if event=="leave":item.nearby=false
	var result: Dictionary=item.vm.run(event,{"dt":0,"time":item.elapsed,"near":int(item.nearby)})
	if result.ok:item.apply_commands(result.commands)
	if BuildMode.developer():status.text=("동작 확인 · "+event if result.ok else "동작 검증 실패")+"\n"+JSON.stringify(item.vm.state)
	else:status.text={"click":"가구를 사용해 봤어요.","near":"가까이 다가가 봤어요.","leave":"가구에서 떨어져 봤어요."}.get(event,"움직임을 살펴보세요.") if result.ok else "지금은 움직임을 확인할 수 없어요."
