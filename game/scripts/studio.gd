extends Control
const Api=preload("res://scripts/api.gd")
const Assembly=preload("res://scripts/asset_assembly.gd")
const Loader=preload("res://scripts/model_loader.gd")
const Art=preload("res://scripts/art.gd")
const BuildMode=preload("res://scripts/build_mode.gd")
var api: Node
var viewport: SubViewport
var view_container: SubViewportContainer
var stage: Node3D
var furniture: Node3D
var room_root: Node3D
var camera: Camera3D
var hero: Node3D
var inventory: ItemList
var title_label: Label
var status_label: Label
var wallet: Label
var detail: Label
var room_capacity: Label
var prompt: TextEdit
var surface_mode: OptionButton
var motion: OptionButton
var designer: OptionButton
var geometry: OptionButton
var models: OptionButton
var efforts: OptionButton
var part_choice: OptionButton
var generation_button: Button
var file_dialog: FileDialog
var image_label: Label
var code_view: CodeEdit
var data: Dictionary={}
var selected: Dictionary={}
var placed: Dictionary={}
var inspected: Node3D
var ghost: Node3D
var room := "workshop"
var placement_mode := false
var placement_rotation := 0
var place_at := Vector3.ZERO
var pending := false
var epoch := 0
var selection_epoch := 0
var placement_epoch := 0
var job_id := ""
var poll_time := 0.0
var polling := false
var refreshing := false
var auth_time := 0.0
var image_data := ""
var orbit := 0.0
var proximity_time := 0.0
var proximity_pending := false
var placement_marker: MeshInstance3D
var quote_panel: VBoxContainer
var quote_label: Label
var provider_price: Label
var preview_stage: Node3D
var preview_camera: Camera3D
var generated_functions: OptionButton
var function_args: LineEdit
var function_fields: Array[SpinBox]=[]
var function_fields_box: VBoxContainer
var function_fields_scroll: ScrollContainer
var function_signature: Label
var raw_args_toggle: CheckButton
var function_result: Label
var mesh_models: OptionButton
var refine_reference: CheckButton
var binding_part: OptionButton
var binding_fields: Dictionary={}
var binding_hint: Label
var binding_dirty := false
var history_list: ItemList
var history_detail: Label
var history_selected := ""
var live_defaults_applied := false

func _ready() -> void:
	api=Api.new();add_child(api)
	if Engine.has_meta("studio_session"):
		var session: Dictionary=Engine.get_meta("studio_session")
		api.token=session.token;api.base_url=session.url
		room=session.get("room","workshop")
	build_ui()
	build_stage()
	if api.token.is_empty():
		message("마을에서 로그인한 뒤 공방으로 들어오세요.")
	else: await refresh()

func theme_style() -> Theme:
	var t := Theme.new()
	var font := SystemFont.new();font.font_names=PackedStringArray(["Malgun Gothic","sans-serif"])
	t.default_font=font;t.default_font_size=14
	for type in ["Label","Button","OptionButton","LineEdit","TextEdit","ItemList","CheckButton"]:
		t.set_color("font_color",type,Color("3f352a"))
		if type in ["LineEdit","TextEdit"]:t.set_color("font_placeholder_color",type,Color("8d8373"))
		if type=="Label":continue
		for state_name in ["normal","hover","pressed","focus","selected","read_only"]:
			var style := StyleBoxFlat.new()
			style.bg_color=Color("cfdfbf") if state_name in ["hover","selected"] else (Color("e7e9d6") if type in ["Button","OptionButton","CheckButton"] else Color("fffdf5"))
			style.set_border_width_all(1);style.border_color=Color("ada88e")
			style.set_corner_radius_all(8);style.content_margin_left=10;style.content_margin_right=10;style.content_margin_top=8;style.content_margin_bottom=8
			t.set_stylebox(state_name,type,style)
	return t

func label(parent: Node,value: String,size_px:=14) -> Label:
	var l := Label.new();l.text=value;l.add_theme_font_size_override("font_size",size_px)
	l.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;l.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	parent.add_child(l);return l

func button(parent: Node,value: String,callback: Callable) -> Button:
	var b := Button.new();b.text=value;b.pressed.connect(callback);b.custom_minimum_size.y=38;parent.add_child(b);return b

func option(parent: Node,items: Array) -> OptionButton:
	var o := OptionButton.new();o.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	for value in items:o.add_item(value)
	parent.add_child(o);return o

func row(parent: Node) -> HBoxContainer:
	var r := HBoxContainer.new();r.add_theme_constant_override("separation",8);parent.add_child(r);return r

func build_ui() -> void:
	theme=theme_style()
	var bg := ColorRect.new();bg.color=Color("d6ddd0");bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(bg)
	var layout := HBoxContainer.new();layout.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);layout.add_theme_constant_override("separation",0);add_child(layout)
	var canvas := VBoxContainer.new();canvas.size_flags_horizontal=Control.SIZE_EXPAND_FILL;layout.add_child(canvas)
	var header := MarginContainer.new();header.add_theme_constant_override("margin_left",24);header.add_theme_constant_override("margin_top",16);header.add_theme_constant_override("margin_bottom",10);canvas.add_child(header)
	var head := VBoxContainer.new();header.add_child(head)
	label(head,"TRIPOTHON  /  LITTLE THINGS, YOUR STORIES",12).modulate=Color("8b7850")
	title_label=label(head,"물결빛 공방",26)
	label(head,"상상한 가구를 만들고, 색칠하고, 내 공간에 놓아요",13)
	if BuildMode.developer(): label(head,"개발 화면 · 생성 방식과 모델, 코드, 기록을 검증할 수 있습니다",11).modulate=Color("986b42")
	view_container=SubViewportContainer.new();view_container.stretch=true;view_container.size_flags_vertical=Control.SIZE_EXPAND_FILL;canvas.add_child(view_container)
	viewport=SubViewport.new();viewport.size=Vector2i(880,660);viewport.own_world_3d=true;viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS;viewport.msaa_3d=Viewport.MSAA_4X;view_container.add_child(viewport)
	view_container.gui_input.connect(view_input)
	var footer := MarginContainer.new();footer.add_theme_constant_override("margin_left",20);footer.add_theme_constant_override("margin_right",20);footer.add_theme_constant_override("margin_bottom",14);canvas.add_child(footer)
	var f := VBoxContainer.new();footer.add_child(f)
	status_label=label(f,"서버에 연결하고 있어요",14)
	label(f,"WASD 이동   E 상호작용   R 회전   Esc 취소",12).modulate=Color("817960")
	var nav := row(f)
	button(nav,"내 집",func(): await change_room("home"))
	button(nav,"공방",func(): await change_room("workshop"))
	button(nav,"마을로 나가기",leave)
	var dock := MarginContainer.new();dock.custom_minimum_size.x=380;dock.add_theme_constant_override("margin_left",16);dock.add_theme_constant_override("margin_right",16);dock.add_theme_constant_override("margin_top",14);layout.add_child(dock)
	var box := VBoxContainer.new();dock.add_child(box)
	wallet=label(box,"나의 공방",18)
	quote_panel=VBoxContainer.new();box.add_child(quote_panel);quote_panel.visible=false
	quote_label=label(quote_panel,"",14)
	var quote_actions := row(quote_panel)
	button(quote_actions,"도형으로 동작 미리보기" if BuildMode.developer() else "모습 미리보기",preview_design)
	button(quote_actions,"이 설계로 생성" if BuildMode.developer() else "가구 완성하기",confirm_job)
	button(quote_actions,"취소 · 별씨 환불" if BuildMode.developer() else "취소",cancel_job)
	var tabs := TabContainer.new();tabs.size_flags_vertical=Control.SIZE_EXPAND_FILL;box.add_child(tabs)
	var tab_panel := StyleBoxFlat.new();tab_panel.bg_color=Color("fff7e8");tab_panel.set_corner_radius_all(12)
	tab_panel.content_margin_left=8;tab_panel.content_margin_right=8;tab_panel.content_margin_top=8;tab_panel.content_margin_bottom=8
	tabs.add_theme_stylebox_override("panel",tab_panel)
	var tab_bar := tabs.get_tab_bar()
	for state_name in ["tab_selected","tab_unselected","tab_hovered"]:
		var tab_style := StyleBoxFlat.new()
		tab_style.bg_color=Color("c5d9b6") if state_name=="tab_selected" else Color("e9e4d5")
		tab_style.set_corner_radius_all(7)
		tab_style.content_margin_left=11;tab_style.content_margin_right=11;tab_style.content_margin_top=7;tab_style.content_margin_bottom=7
		tab_bar.add_theme_stylebox_override(state_name,tab_style)
		tabs.add_theme_stylebox_override(state_name,tab_style)
	tab_bar.add_theme_color_override("font_selected_color",Color("304533"))
	tab_bar.add_theme_color_override("font_unselected_color",Color("4e493d"))
	tabs.add_theme_color_override("font_selected_color",Color("304533"))
	tabs.add_theme_color_override("font_unselected_color",Color("4e493d"))
	var create_scroll := ScrollContainer.new();create_scroll.name="만들기";tabs.add_child(create_scroll)
	var create := VBoxContainer.new();create.size_flags_horizontal=Control.SIZE_EXPAND_FILL;create.add_theme_constant_override("separation",10);create_scroll.add_child(create)
	label(create,"어떤 물건을 만들까요?",20)
	prompt=TextEdit.new();prompt.custom_minimum_size.y=112;prompt.wrap_mode=TextEdit.LINE_WRAPPING_BOUNDARY;prompt.text="다가가면 꽃잎이 열리는 꽃 조명";create.add_child(prompt)
	var presets := row(create)
	button(presets,"꽃 조명",func(): prompt.text="다가가면 여섯 꽃잎이 열리고 떠나면 닫히는 꽃 조명")
	button(presets,"상자",func(): prompt.text="클릭하면 뚜껑이 부드럽게 열리고 다시 클릭하면 닫히는 나무 상자")
	button(presets,"시계",func(): prompt.text="시침과 분침이 움직이고 클릭하면 멈추는 탁상 시계")
	image_label=label(create,"참고 그림을 추가할 수 있어요",12)
	var image_buttons := row(create)
	button(image_buttons,"이미지 선택",func(): file_dialog.popup_centered_ratio(0.7))
	button(image_buttons,"제거",func(): image_data="";image_label.text="참고 이미지 없음";update_price())
	refine_reference=CheckButton.new();refine_reference.text="그림을 먼저 정리해서 만들기";refine_reference.tooltip_text="Tripo 이미지 편집: 부품당 예상 5크레딧 추가. 이후 이미지→3D 요금 적용.";create.add_child(refine_reference);refine_reference.toggled.connect(func(_value):update_price())
	file_dialog=FileDialog.new();file_dialog.access=FileDialog.ACCESS_FILESYSTEM;file_dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;file_dialog.filters=PackedStringArray(["*.png,*.jpg,*.jpeg ; Reference image"]);add_child(file_dialog);file_dialog.file_selected.connect(pick_image)
	label(create,"표면과 움직임",15)
	surface_mode=option(create,["내가 직접 색칠하기","완성된 질감 포함하기"])
	motion=option(create,["움직이는 가구","정적인 가구"])
	var dev_title := label(create,"개발용 생성 설정",15)
	designer=option(create,["샘플 설계 · API 비용 없음","LLM 설계 · 서버 설정 사용"])
	geometry=option(create,["검증용 도형 · Tripo 비용 없음","Tripo 실제 생성 · 크레딧 사용"])
	mesh_models=option(create,["H3 · 일반 가구 / 낮은 비용","P2 · 정밀 메시 / 높은 비용"])
	mesh_models.item_selected.connect(func(_value):update_price())
	var advanced := VBoxContainer.new()
	var advanced_button := button(create,"모델 비교 설정 펼치기",func(): advanced.visible=not advanced.visible)
	create.add_child(advanced);advanced.visible=false
	models=option(advanced,["gpt-6-luna","gpt-5.6-terra","gpt-6-sol","gpt-6-astra"])
	efforts=option(advanced,["low","medium","high","xhigh"]);efforts.select(2)
	provider_price=label(create,"검증용 도형: Tripo 비용 0",12)
	generation_button=button(create,"만들기 · 30 별씨",generate)
	surface_mode.item_selected.connect(func(_i): update_price());motion.item_selected.connect(func(_i): update_price())
	geometry.item_selected.connect(func(_i): update_price())
	var dev_note := label(create,"별씨는 게임 재화입니다. API 크레딧과 같은 단위가 아닙니다. 검증용 도형은 생성 메시의 완성도를 보여주지 않습니다.",12)
	dev_note.modulate=Color("817960")
	var own := VBoxContainer.new();own.name="보관함";tabs.add_child(own)
	label(own,"내가 만든 작은 세계",19)
	room_capacity=label(own,"배치한 가구를 확인하고 있어요",12)
	inventory=ItemList.new();inventory.custom_minimum_size.y=135;inventory.size_flags_vertical=Control.SIZE_EXPAND_FILL;own.add_child(inventory);inventory.item_selected.connect(select_item)
	var preview_view := SubViewportContainer.new();preview_view.custom_minimum_size.y=190;preview_view.stretch=true;own.add_child(preview_view)
	var preview_port := SubViewport.new();preview_port.size=Vector2i(330,190);preview_port.own_world_3d=true;preview_port.render_target_update_mode=SubViewport.UPDATE_ALWAYS;preview_port.msaa_3d=Viewport.MSAA_4X;preview_view.add_child(preview_port)
	preview_stage=Node3D.new();preview_port.add_child(preview_stage)
	var preview_env := WorldEnvironment.new();preview_env.environment=Environment.new();preview_env.environment.background_mode=Environment.BG_COLOR;preview_env.environment.background_color=Color("b5c1ad");preview_env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;preview_env.environment.ambient_light_color=Color.WHITE;preview_env.environment.ambient_light_energy=.12;preview_stage.add_child(preview_env)
	var preview_sun := DirectionalLight3D.new();preview_sun.rotation_degrees=Vector3(-40,-30,0);preview_sun.light_energy=.45;preview_stage.add_child(preview_sun)
	preview_camera=Camera3D.new();preview_camera.projection=Camera3D.PROJECTION_ORTHOGONAL;preview_camera.size=2.9;preview_camera.position=Vector3(2.7,2.2,4);preview_stage.add_child(preview_camera);preview_camera.look_at(Vector3(0,.65,0));preview_camera.current=true
	Art.box(preview_stage,Vector3(0,-.04,0),Vector3(8,.06,8),Color("a9b7a0"))
	preview_view.gui_input.connect(preview_input)
	label(own,"미리보기 · 드래그 회전 / 휠 확대",11).modulate=Color("b9c8ad")
	detail=label(own,"가구를 고르면 모습을 살펴볼 수 있어요",13)
	var actions := row(own)
	button(actions,"바닥에 배치",begin_place);button(actions,"회수",retrieve);button(actions,"사용",interact_selected)
	part_choice=option(own,["전체 색칠"])
	var palette := row(own)
	for color in ["#f1dfb8","#dfa958","#789887","#bd7f75","#7d9ca3"]:
		var b := button(palette,"●",func(): await paint(color));b.modulate=Color(color);b.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	var custom_row := row(own)
	var custom_color := ColorPickerButton.new();custom_color.text="직접 색 고르기";custom_color.edit_alpha=false;custom_color.color=Color("dfa958");custom_color.size_flags_horizontal=Control.SIZE_EXPAND_FILL;custom_row.add_child(custom_color)
	custom_color.popup_closed.connect(func():await paint("#"+custom_color.color.to_html(false)))
	button(custom_row,"원래 색 복원",func():await paint("#ffffff",true))
	button(own,"서버에서 새로고침",refresh)
	var source := VBoxContainer.new();source.name="동작 코드";tabs.add_child(source)
	label(source,"생성된 조작 함수와 이벤트",18)
	label(source,"서버가 검사한 숫자 연산·부품 제어 코드입니다. 파일이나 재화에 접근할 수 없습니다.",12)
	generated_functions=option(source,[])
	generated_functions.item_selected.connect(load_function_fields)
	function_signature=label(source,"",12)
	function_fields_scroll=ScrollContainer.new();function_fields_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;source.add_child(function_fields_scroll)
	function_fields_box=VBoxContainer.new();function_fields_box.size_flags_horizontal=Control.SIZE_EXPAND_FILL;function_fields_scroll.add_child(function_fields_box)
	raw_args_toggle=CheckButton.new();raw_args_toggle.text="개발자용 JSON 입력";source.add_child(raw_args_toggle)
	function_args=LineEdit.new();function_args.text="[]";function_args.placeholder_text="숫자 인수 예: [0.5]";source.add_child(function_args);function_args.visible=false
	raw_args_toggle.toggled.connect(func(enabled):function_args.visible=enabled;function_fields_scroll.visible=not enabled)
	button(source,"선택한 생성 함수 호출",invoke_generated)
	function_result=label(source,"가구를 선택하면 생성된 함수를 검사할 수 있어요.",12)
	code_view=CodeEdit.new();code_view.editable=false;code_view.size_flags_vertical=Control.SIZE_EXPAND_FILL;source.add_child(code_view)
	var fit_scroll := ScrollContainer.new();fit_scroll.name="부품 맞춤";tabs.add_child(fit_scroll)
	var fit := VBoxContainer.new();fit.size_flags_horizontal=Control.SIZE_EXPAND_FILL;fit_scroll.add_child(fit)
	label(fit,"움직이는 부품 맞추기",18)
	label(fit,"뚜껑·바늘의 위치와 회전축을 조정합니다. 저장하면 내 가구에만 적용되며 원래 설계로 되돌릴 수 있어요.",12)
	binding_part=option(fit,[]);binding_part.item_selected.connect(load_binding_fields)
	for spec in [["position","위치 · m",-3.0,3.0,.01],["rotation","방향 · 도",-360.0,360.0,1.0],["pivot","회전축 · 중심 기준",-.5,.5,.01],["size","크기 · m",.02,3.0,.01]]:
		label(fit,spec[1],13)
		var axes := row(fit);var fields: Array[SpinBox]=[]
		for axis in ["X","Y","Z"]:
			var field := SpinBox.new();field.prefix=axis;field.min_value=spec[2];field.max_value=spec[3];field.step=spec[4];field.size_flags_horizontal=Control.SIZE_EXPAND_FILL;axes.add_child(field);fields.append(field)
			field.value_changed.connect(func(_value):preview_binding_fields())
		binding_fields[spec[0]]=fields
	var fitting_actions := row(fit)
	button(fitting_actions,"맞춤 저장",func():await save_binding(false))
	button(fitting_actions,"원래 설계로",func():await save_binding(true))
	button(fit,"열기·닫기 등 동작 시험",interact_selected)
	binding_hint=label(fit,"가구를 고르면 부품 목록이 표시됩니다. 전체 크기는 배치 구역에 맞게 자동 조절됩니다.",12)
	var history := VBoxContainer.new();history.name="제작 기록";tabs.add_child(history)
	label(history,"최근 제작 30건 · 시간 UTC",18)
	history_list=ItemList.new();history_list.custom_minimum_size.y=180;history_list.item_selected.connect(select_history);history.add_child(history_list)
	history_detail=label(history,"기록을 선택하면 예약·확정 별씨와 확인된 Tripo 비용을 볼 수 있어요.",13)
	button(history,"이 설계의 도형 미리보기",func():await show_design(history_selected))
	button(history,"기록 새로고침",refresh)
	tabs.tab_changed.connect(func(index: int):
		if index==0 or index==4:return
		var target: Control=own if index==1 else (source if index==2 else fit)
		preview_view.reparent(target)
		target.move_child(preview_view,1 if index==1 else 2))
	if not BuildMode.developer():
		for control in [dev_title,designer,geometry,mesh_models,advanced_button,advanced,provider_price,dev_note,refine_reference]: control.visible=false
		for index in [2,3,4]: tabs.set_tab_hidden(index,true)
		prompt.text=""
		prompt.placeholder_text="예: 다가가면 꽃잎이 열리는 꽃 조명"
		generation_button.text="가구 만들기"

func update_price() -> void:
	var cost := (20 if surface_mode.selected==0 else 40)+(10 if motion.selected==0 else 0)
	generation_button.text="만들기 · %d 별씨"%cost
	if geometry.selected==1:
		var use_image := not image_data.is_empty() and (motion.selected==1 or refine_reference.button_pressed)
		var unit := (10+(10 if use_image else 0)) if mesh_models.selected==0 else 100
		if surface_mode.selected==1:unit+=10
		if not image_data.is_empty() and refine_reference.button_pressed:unit+=5
		provider_price.text="공식 요금·실측 기반 예상: "+("정적 1부품 · %d 크레딧"%unit if motion.selected==1 else "부품당 %d 크레딧 · 최대 8부품"%unit)+"\n설계 후 부품 수와 예상 비용을 확인합니다."
		generation_button.text="설계 먼저 · %d 별씨 예약"%cost
	else:provider_price.text="검증용 도형: Tripo 비용 0"

func message(value: String) -> void:
	status_label.text=value.replace("room_render_budget_exceeded","꾸미기 용량이 꽉 찼어요. 가구 일부를 회수하거나 다른 방에 놓아 주세요.")

func build_stage() -> void:
	stage=Node3D.new();viewport.add_child(stage)
	var env := WorldEnvironment.new();var environment := Environment.new()
	environment.background_mode=Environment.BG_COLOR;environment.background_color=Color("b8c8bd")
	environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;environment.ambient_light_color=Color("e6efd6");environment.ambient_light_energy=0.38
	env.environment=environment;stage.add_child(env)
	var sun := DirectionalLight3D.new();sun.rotation_degrees=Vector3(-52,-28,0);sun.light_color=Color("fff5e9");sun.light_energy=0.6;sun.shadow_enabled=true;stage.add_child(sun)
	camera=Camera3D.new();camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=12.5;camera.position=Vector3(10,13,15);stage.add_child(camera);camera.look_at(Vector3(0,0.8,0));camera.current=true
	furniture=Node3D.new();stage.add_child(furniture)
	room_root=Node3D.new();stage.add_child(room_root)
	placement_marker=Art.box(stage,Vector3(0,0.065,0),Vector3(1.95,0.015,1.95),Color("8ccbb1"))
	placement_marker.material_override.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	placement_marker.visible=false
	build_room()
	# Authored character is separate from all player-created furniture.
	if ResourceLoader.exists("res://assets/explorer_b_reference.glb"):
		hero=preload("res://scripts/player.gd").new();hero.controls_enabled=false;hero.visual_only=true;stage.add_child(hero);hero.position=Vector3(0,0,3)

func build_room() -> void:
	for child in room_root.get_children():child.queue_free()
	title_label.text="나의 작은 집" if room=="home" else "물결빛 공방"
	Art.box(room_root,Vector3(0,-0.18,0),Vector3(10.4,0.35,10.4),Color("7a5940"))
	for x in 20:
		Art.box(room_root,Vector3(-4.75+x*0.5,-0.01,0),Vector3(0.48,0.06,10),Color("b68f62") if x%3==0 else Color("c4a477"))
	Art.box(room_root,Vector3(0,1.7,-5),Vector3(10.4,3.5,0.22),Color("e1d4b4"))
	Art.box(room_root,Vector3(-5,1.7,0),Vector3(0.22,3.5,10),Color("e1d4b4"))
	for x in [-5,-2.5,0,2.5,5]:Art.box(room_root,Vector3(x,1.7,-4.82),Vector3(0.14,3.5,0.15),Color("775b43"))
	for z in [-5,-2.5,0,2.5,5]:Art.box(room_root,Vector3(-4.82,1.7,z),Vector3(0.15,3.5,0.14),Color("775b43"))
	for y in [0.18,3.3]:
		Art.box(room_root,Vector3(0,y,-4.8),Vector3(10,0.18,0.18),Color("775b43"))
		Art.box(room_root,Vector3(-4.8,y,0),Vector3(0.18,0.18,10),Color("775b43"))
	for x in [-2.5,2.5]:
		Art.box(room_root,Vector3(x,2.0,-4.65),Vector3(1.8,1.65,0.12),Color("628d89"))
		Art.box(room_root,Vector3(x,2.0,-4.53),Vector3(0.08,1.65,0.12),Color("f1d7a4"))
		Art.box(room_root,Vector3(x,2.0,-4.53),Vector3(1.8,0.08,0.12),Color("f1d7a4"))
		Art.box(room_root,Vector3(x,1.14,-4.5),Vector3(2.1,0.13,0.4),Color("765c44"))
	# Door threshold is kept clear by server placement rules.
	Art.box(room_root,Vector3(0,0.06,4.8),Vector3(2.6,0.12,0.5),Color("e0ca91"))
	# Cutaway front wall: a tall lintel hides the player at the entrance.
	for x in [-1.25,1.25]:Art.box(room_root,Vector3(x,.35,5),Vector3(0.18,.7,0.22),Color("7b6248"))
	var sign := Label3D.new();sign.text="마을  →";sign.position=Vector3(1.9,.85,4.85);sign.font_size=32;sign.pixel_size=0.006;room_root.add_child(sign)
	var rug := Art.box(room_root,Vector3(0,0.035,0),Vector3(3.8,0.02,3.2),Color("718d7c"))
	rug.name="WovenRug"
	for x in [-1.7,1.7]:Art.box(room_root,Vector3(x,0.049,0),Vector3(0.08,0.015,3),Color("d9c690"))
	if room=="workshop":
		Art.box(room_root,Vector3(-3.7,0.85,-3.1),Vector3(1.8,0.16,1.0),Color("8c6746"))
		for x in [-4.4,-3]:
			for z in [-3.5,-2.7]:Art.box(room_root,Vector3(x,0.4,z),Vector3(0.1,0.8,0.1),Color("785d43"))

func refresh() -> void:
	if refreshing:return
	refreshing=true
	var response: Dictionary=await api.request("/v1/studio")
	refreshing=false
	if not response.ok:
		message("서버 연결을 확인해 주세요 · "+response.error)
		clear_owned()
		return
	data=response.data
	wallet.text="별씨 %d"%data.shards
	if BuildMode.developer(): wallet.text+="  ·  "+("Tripo 실제 생성 가능" if data.geometry_enabled else ("개발 공방" if data.llm!="openai" else "온라인 공방"))
	var live: bool=data.get("mode","demo")=="live"
	for i in range(models.get_item_count()):models.set_item_disabled(i,live and i!=0)
	for i in range(efforts.get_item_count()):efforts.set_item_disabled(i,live and i!=2)
	if live:
		models.select(0);efforts.select(2)
	if is_instance_valid(hero):hero.apply_avatar(data.get("profile",{}).get("avatar",{}))
	update_capacity()
	history_list.clear()
	for entry in data.jobs:history_list.add_item(job_status(entry.state)+" · %d 별씨 · %s"%[entry.cost,Time.get_datetime_string_from_unix_time(int(entry.created)).replace("T"," ")])
	designer.set_item_disabled(0,live);designer.set_item_disabled(1,data.llm=="fixture")
	geometry.set_item_disabled(0,live);geometry.set_item_disabled(1,not data.geometry_enabled)
	generation_button.disabled=live and not data.geometry_enabled
	if not live_defaults_applied:
		live_defaults_applied=true
		if data.geometry_enabled and data.llm!="fixture":
			designer.select(1);geometry.select(1);update_price()
	inventory.clear()
	for obj in data.objects:inventory.add_item(("● " if obj.state=="placed" else "○ ")+obj.name)
	if not selected.is_empty():
		var exists := false
		for obj in data.objects:
			if obj.id==selected.id:selected=obj;exists=true
		if not exists: clear_selection()
	for job in data.jobs:
		if job.state not in ["ready","failed","cancelled"]:job_id=job.id;break
	await reload_placed()
	if not selected.is_empty() and is_instance_valid(inspected) and inspected.get_meta("studio",false) and not pending and not placement_mode:
		if selected.get("runtime_version",inspected.runtime_version)!=inspected.runtime_version:
			var selected_id: String=selected.id;var refresh_selection := selection_epoch
			var latest: Dictionary=await api.request("/v1/objects/"+selected_id+"/assembly")
			if refresh_selection!=selection_epoch:return
			if not latest.ok:clear_selection();message("선택한 가구를 다시 불러올 수 없어요.");return
			if latest.data.plan!=inspected.manifest.plan:
				if binding_dirty:
					message("다른 곳에서 부품 맞춤이 바뀌었어요. 편집값은 보존했습니다. 가구를 다시 선택하면 최신 설계를 불러옵니다.");return
				for index in data.objects.size():
					if data.objects[index].id==selected_id:await select_item(index);break
			else:
				inspected.accept_event({"state":latest.data.runtime.state,"commands":[],"version":latest.data.runtime.version})
				inspected.paint(latest.data.runtime.colors)
	message("서버 저장 완료 · "+("내 집" if room=="home" else "공방"))

func clear_selection() -> void:
	selection_epoch+=1;placement_epoch+=1
	binding_dirty=false
	selected={};placement_mode=false
	if is_instance_valid(inspected):inspected.queue_free()
	if is_instance_valid(ghost):ghost.queue_free()
	ghost=null
	if is_instance_valid(code_view):code_view.text=""
	if is_instance_valid(generated_functions):generated_functions.clear()
	if is_instance_valid(function_fields_box):load_function_fields(-1)
	if is_instance_valid(binding_part):binding_part.clear()
	if is_instance_valid(detail):detail.text="가구를 고르면 모습을 살펴볼 수 있어요"

func clear_owned() -> void:
	epoch+=1
	clear_selection()
	for n in furniture.get_children():n.queue_free()
	placed.clear()

func load_item(obj: Dictionary) -> Node3D:
	var value: Node3D=await Assembly.fetch(api,obj.id)
	if value:return value
	if obj.get("studio",false):return null
	var response: Dictionary=await api.request("/v1/objects/"+obj.id+"/model",{},HTTPClient.METHOD_GET,true)
	if not response.ok:return null
	value=Loader.load_bytes(response.bytes)
	if value:Loader.paint(value,Color(obj.color))
	return value

func reload_placed() -> void:
	epoch+=1;var current := epoch
	var desired := {}
	for obj in data.objects:
		if obj.state=="placed" and obj.room==room:desired[obj.id]=obj
	for id in placed.keys():
		if not desired.has(id):placed[id].queue_free();placed.erase(id)
	for obj in data.objects:
		if obj.state!="placed" or obj.room!=room:continue
		if placed.has(obj.id):
			var existing: Node3D=placed[obj.id]
			existing.position=Vector3(obj.x,0.07,obj.z);existing.rotation_degrees.y=obj.rotation
			if existing.get_meta("studio",false) and obj.get("runtime_version")!=null and existing.runtime_version!=obj.runtime_version:
				var fresh: Dictionary=await api.request("/v1/objects/"+obj.id+"/assembly")
				if current!=epoch:return
				if fresh.ok and is_instance_valid(existing):
					if fresh.data.plan!=existing.manifest.plan:
						var replacement := await load_item(obj)
						if current!=epoch:
							if replacement:replacement.queue_free()
							return
						if replacement:
							furniture.add_child(replacement);replacement.position=existing.position;replacement.rotation=existing.rotation;placed[obj.id]=replacement
						existing.queue_free()
						if not replacement:placed.erase(obj.id)
						continue
					existing.accept_event({"state":fresh.data.runtime.state,"commands":[],"version":fresh.data.runtime.version});existing.paint(fresh.data.runtime.colors)
				elif is_instance_valid(existing):existing.queue_free();placed.erase(obj.id)
			elif not existing.get_meta("studio",false) and existing.get_meta("paint",Color.WHITE)!=Color(obj.color):Loader.paint(existing,Color(obj.color))
			continue
		var item := await load_item(obj)
		if current!=epoch:
			if item:item.queue_free()
			return
		if item:
			furniture.add_child(item);item.position=Vector3(obj.x,0.07,obj.z);item.rotation_degrees.y=obj.rotation;placed[obj.id]=item

func select_item(index: int) -> void:
	if pending or index>=data.objects.size():return
	clear_selection();selected=data.objects[index];var id: String=selected.id;var selection_request := selection_epoch
	var item := await load_item(selected)
	if selected.get("id")!=id or selection_request!=selection_epoch:
		if item:item.queue_free()
		return
	if not item:message("에셋을 읽을 수 없습니다");return
	inspected=item;preview_stage.add_child(item);item.position=Vector3.ZERO
	var preview_size: Vector3=item.get_meta("size",Vector3.ONE)
	preview_camera.size=maxf(1.5,preview_size.y*1.5)
	if item.get_meta("studio",false) and item.pivots.has("lid"):preview_camera.size=maxf(1.9,preview_camera.size)
	detail.text=selected.name+"\n"+("배치됨 · "+selected.room if selected.state=="placed" else "보관 중")
	part_choice.clear();part_choice.add_item("전체 색칠")
	if item.get_meta("studio",false):
		generated_functions.clear()
		binding_part.clear()
		for fn in item.manifest.program.functions:generated_functions.add_item(fn)
		load_function_fields(0)
		for p in item.manifest.plan.parts:part_choice.add_item(p.id);binding_part.add_item(p.id)
		load_binding_fields(0)
		code_view.text=JSON.stringify(item.manifest.program,"  ")
		if BuildMode.developer():
			detail.text+="\n설계: "+str(item.manifest.provenance.provider)+"\n메시: "+str(item.manifest.provenance.geometry)
			if item.manifest.provenance.geometry=="tripo":detail.text+="\nTripo 실측: %s 크레딧"%str(item.manifest.provenance.get("tripo_credits_consumed","미기록"))
	else:code_view.text="개발자가 제작한 일반 에셋";generated_functions.clear();load_function_fields(-1)
	message("선택한 가구의 최신 상태를 불러왔어요.")

func load_function_fields(index: int) -> void:
	function_fields.clear()
	function_fields_scroll.custom_minimum_size.y=0
	for child in function_fields_box.get_children():function_fields_box.remove_child(child);child.queue_free()
	function_args.text="[]";function_signature.text="이 물건에는 생성된 조작 함수가 없어요."
	if not is_instance_valid(inspected) or not inspected.get_meta("studio",false) or index<0 or index>=generated_functions.item_count:return
	var function_name := generated_functions.get_item_text(index)
	var definition: Dictionary=inspected.manifest.program.functions[function_name]
	function_fields_scroll.custom_minimum_size.y=min(3,definition.params.size())*40
	var names: PackedStringArray=[]
	for parameter in definition.params:
		names.append(str(parameter))
		var line := row(function_fields_box)
		label(line,str(parameter),12).size_flags_horizontal=Control.SIZE_EXPAND_FILL
		var field := SpinBox.new();field.min_value=-1000000;field.max_value=1000000;field.step=.01;field.custom_minimum_size.x=150
		line.add_child(field);function_fields.append(field)
		field.value_changed.connect(func(_v):sync_function_args())
	function_signature.text=function_name+"("+", ".join(names)+")"+(" · 입력값 없이 실행" if names.is_empty() else " · 숫자를 입력하고 실행하세요")
	sync_function_args()

func sync_function_args() -> void:
	var values: Array=[]
	for field in function_fields:values.append(field.value)
	function_args.text=JSON.stringify(values)

func load_binding_fields(index: int) -> void:
	if not is_instance_valid(inspected) or not inspected.get_meta("studio",false) or index<0 or index>=binding_part.item_count:return
	var id := binding_part.get_item_text(index)
	binding_dirty=false
	for p in inspected.manifest.plan.parts:
		inspected.preview_binding(p.id,p)
		if p.id!=id:continue
		for key in binding_fields:
			for axis in 3:binding_fields[key][axis].set_value_no_signal(p[key][axis])
		binding_hint.text="%s · X 좌우 / Y 높이 / Z 앞뒤\n회전축 -0.5는 부품의 뒤·아래·왼쪽 끝, 0.5는 반대쪽 끝입니다."%id

func preview_binding_fields() -> void:
	if binding_part.item_count==0 or not is_instance_valid(inspected):return
	var edits := {}
	for key in binding_fields:
		edits[key]=[]
		for field in binding_fields[key]:edits[key].append(field.value)
	if edits.size()!=4:return
	inspected.preview_binding(binding_part.get_item_text(binding_part.selected),edits)
	binding_dirty=true
	binding_hint.text="미리보기만 변경됨 · ‘맞춤 저장’을 누르면 서버에 저장합니다."

func save_binding(reset: bool) -> void:
	if pending or selected.is_empty() or binding_part.item_count==0 or not is_instance_valid(inspected):return
	var id: String=selected.id
	var chosen := binding_part.get_item_text(binding_part.selected)
	var body := {"version":inspected.runtime_version,"part":chosen,"reset":reset}
	if not reset:
		for key in binding_fields:
			body[key]=[]
			for field in binding_fields[key]:body[key].append(field.value)
	pending=true
	var reply: Dictionary=await api.post("/v1/objects/"+id+"/bindings",api.mutation(body))
	pending=false
	if not reply.ok:message("맞춤을 저장하지 못했어요 · "+reply.error);return
	binding_dirty=false
	if placed.has(id):placed[id].queue_free();placed.erase(id)
	await refresh()
	for i in data.objects.size():
		if data.objects[i].id==id:await select_item(i);break
	for i in binding_part.item_count:
		if binding_part.get_item_text(i)==chosen:binding_part.select(i);load_binding_fields(i);break
	message("원래 부품 설계로 돌아왔어요" if reset else "부품 맞춤을 저장했어요")

func invoke_generated() -> void:
	if pending or selected.is_empty() or generated_functions.item_count==0 or not is_instance_valid(inspected):return
	var args=JSON.parse_string(function_args.text)
	if not args is Array:function_result.text="숫자 배열로 입력해 주세요. 예: [0.5]";return
	pending=true
	var reply: Dictionary=await api.post("/v1/objects/"+selected.id+"/invoke",api.mutation({"version":inspected.runtime_version,"function":generated_functions.get_item_text(generated_functions.selected),"args":args}))
	pending=false
	if reply.ok:
		inspected.accept_event(reply.data)
		if placed.has(selected.id):placed[selected.id].accept_event(reply.data)
		function_result.text="반환값: "+str(reply.data.result)+" · 명령 %d개"%reply.data.commands.size()
	else:function_result.text=reply.error

func generate() -> void:
	if pending or not job_id.is_empty():return
	pending=true;generation_button.disabled=true
	var body := {"prompt":prompt.text.strip_edges(),"material":"mesh" if surface_mode.selected==0 else "textured","motion":"dynamic" if motion.selected==0 else "static","designer":"fixture" if designer.selected==0 else "llm","geometry":"proxy" if geometry.selected==0 else "tripo","model":models.get_item_text(models.selected),"effort":efforts.get_item_text(efforts.selected),"image":image_data,"mesh_model":"v3.1-20260211" if mesh_models.selected==0 else "P2-20260801","image_mode":"refine" if geometry.selected==1 and not image_data.is_empty() and refine_reference.button_pressed else "original"}
	var response: Dictionary=await api.post("/v1/studio/jobs",api.mutation(body))
	pending=false;generation_button.disabled=false
	if not response.ok:message("생성을 시작하지 못했어요 · "+response.error);return
	job_id=response.data.id;message("설계를 준비하고 있어요. 다른 가구를 꾸미며 기다릴 수 있어요.");await refresh()

func poll_job() -> void:
	if polling or job_id.is_empty():return
	polling=true
	var response: Dictionary=await api.request("/v1/studio/jobs/"+job_id)
	polling=false
	if not response.ok:return
	var job: Dictionary=response.data
	quote_panel.visible=job.state=="awaiting_confirmation"
	if quote_panel.visible:
		if BuildMode.developer():
			quote_label.text="설계 완료 · %d부품\n총 %d 별씨 · 이미 예약 %d 별씨\nTripo 예상 %s 크레딧\n예상 비용 확인 후에만 유료 생성을 시작합니다."%[job.parts.size(),int(job.provenance.get("quoted_game_cost",job.cost)),int(job.cost),str(job.provenance.estimated_tripo_credits)]
		else:
			quote_label.text="가구를 만들 준비가 됐어요.\n필요한 별씨 %d개 · 이미 맡긴 별씨 %d개\n완성하기를 누르면 제작을 시작해요."%[int(job.provenance.get("quoted_game_cost",job.cost)),int(job.cost)]
	var progress := ""
	if job.state=="building":
		var ready := 0
		for state in job.parts.values():
			if state=="ready":ready+=1
		progress=" · %d / %d부품 완료"%[ready,job.parts.size()]
	message(job_status(job.state)+progress)
	if job.state in ["ready","failed","cancelled"]:
		job_id="";await refresh()

func confirm_job() -> void:
	if pending or job_id.is_empty():return
	pending=true
	var response: Dictionary=await api.post("/v1/studio/jobs/"+job_id+"/confirm",api.mutation())
	pending=false
	if response.ok:quote_panel.visible=false;message("확인한 설계로 3D 메시를 만들고 있어요")
	else:message(response.error)

func cancel_job() -> void:
	if pending or job_id.is_empty():return
	pending=true
	var response: Dictionary=await api.post("/v1/studio/jobs/"+job_id+"/cancel",api.mutation())
	pending=false
	if response.ok:quote_panel.visible=false;job_id="";await refresh()
	else:message(response.error)

func begin_place() -> void:
	if selected.is_empty() or pending:return
	placement_epoch+=1;var placement_request := placement_epoch;var object_id: String=selected.id
	placement_mode=true;placement_rotation=selected.rotation
	if is_instance_valid(ghost):ghost.queue_free()
	ghost=null
	var loaded := await load_item(selected.duplicate(true))
	if placement_request!=placement_epoch or not placement_mode or selected.get("id")!=object_id:
		if loaded:loaded.queue_free()
		return
	ghost=loaded
	if ghost:
		stage.add_child(ghost);ghost.position=Vector3(0,0.08,0);ghost.rotation_degrees.y=placement_rotation
		place_at=ghost.position
	else:
		placement_mode=false;message("가구를 불러오지 못했어요. 다시 선택해 주세요.");return
	message("바닥을 가리킨 뒤 클릭해 배치하세요 · R 회전 · Esc 취소")

func view_input(event: InputEvent) -> void:
	if placement_mode and event is InputEventMouseMotion:
		var origin := camera.project_ray_origin(event.position)
		var direction := camera.project_ray_normal(event.position)
		if absf(direction.y)>0.001:
			var point := origin+direction*(-origin.y/direction.y)
			place_at=Vector3(roundf(point.x*2)/2,0.08,roundf(point.z*2)/2)
			if is_instance_valid(ghost):ghost.position=place_at
	if placement_mode and event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_LEFT:await commit_place()

func job_status(state: String) -> String:
	return {"queued":"작업 대기","planning":"설계와 동작 코드 생성","awaiting_confirmation":"견적 확인 대기","building":"메시 생성 · 검증 · 조립","submitting":"Tripo 요청 전송","unknown":"요청 결과 확인 필요 · 중복 과금 방지를 위해 정지","ready":"완성","failed":"제작 실패 · 별씨 환불","cancelled":"제작 취소"}.get(state,state)

func select_history(index: int) -> void:
	if index<0 or index>=data.jobs.size():return
	var id: String=data.jobs[index].id;history_selected=id
	var response: Dictionary=await api.request("/v1/studio/jobs/"+id)
	if history_selected!=id:return
	if not response.ok:history_detail.text=response.error;return
	var job: Dictionary=response.data;var proof: Dictionary=job.provenance
	history_detail.text=job_status(job.state)+"\n별씨 예약/확정: %d\n"%job.cost
	if proof.has("quoted_game_cost"):history_detail.text+="설계 후 최종 견적: %d 별씨\n"%int(proof.quoted_game_cost)
	if proof.get("geometry")=="tripo":
		history_detail.text+="Tripo 예상: %s 크레딧\n확인된 사용: %s 크레딧\n"%[str(proof.get("estimated_tripo_credits","미기록")),str(proof.get("known_tripo_credits",0))]
		if not proof.get("billing_complete",false):history_detail.text+="일부 작업 비용은 아직 미확인입니다. 0원 확정이 아닙니다.\n"
	else:history_detail.text+="도형 메시 · Tripo 호출 없음\n"
	if job.state=="failed":history_detail.text+="게임 별씨는 환불했지만 이미 실행된 제공사 비용은 남을 수 있습니다.\n"
	if job.get("error"):history_detail.text+="상태 코드: "+str(job.error)

func preview_design() -> void:
	await show_design(job_id)

func show_design(id: String) -> void:
	if id.is_empty():return
	var response: Dictionary=await api.request("/v1/studio/jobs/"+id+"/preview")
	if not response.ok:message("설계 미리보기 실패 · "+response.error);return
	var window=load("res://scripts/design_preview.gd").new()
	add_child(window)
	if window.show_plan(response.data):window.popup_centered()
	else:window.queue_free();message("설계를 표시하지 못했습니다")

func preview_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and event.button_mask&MOUSE_BUTTON_MASK_LEFT and is_instance_valid(inspected):
		inspected.rotation.y+=event.relative.x*.012
	if event is InputEventMouseButton and event.pressed:
		if event.button_index==MOUSE_BUTTON_WHEEL_UP:preview_camera.size=maxf(1.5,preview_camera.size-.2)
		if event.button_index==MOUSE_BUTTON_WHEEL_DOWN:preview_camera.size=minf(4.0,preview_camera.size+.2)

func commit_place() -> void:
	if pending or selected.is_empty():return
	var blocked := placement_problem(place_at)
	if not blocked.is_empty():message(blocked);return
	pending=true
	var reply: Dictionary=await api.post("/v1/objects/"+selected.id+"/placement",api.mutation({"version":selected.version,"room":room,"x":place_at.x,"z":place_at.z,"rotation":placement_rotation}))
	pending=false
	if not reply.ok:message("여기에는 놓을 수 없어요 · "+reply.error);await refresh();return
	placement_mode=false
	if is_instance_valid(ghost):ghost.queue_free()
	await refresh()

func retrieve() -> void:
	if pending or selected.is_empty():return
	pending=true
	var reply: Dictionary=await api.post("/v1/objects/"+selected.id+"/placement",api.mutation({"version":selected.version,"action":"retrieve","room":room}))
	pending=false
	if not reply.ok:message(reply.error)
	await refresh()

func interact_selected() -> void:
	if pending or selected.is_empty() or not is_instance_valid(inspected) or not inspected.get_meta("studio",false):return
	pending=true
	var response: Dictionary=await api.post("/v1/objects/"+selected.id+"/event",api.mutation({"version":inspected.runtime_version,"event":"click"}))
	pending=false
	if response.ok:
		inspected.accept_event(response.data)
		if placed.has(selected.id):placed[selected.id].accept_event(response.data)
	else:message(response.error)

func paint(color: String, reset := false) -> void:
	if pending or selected.is_empty() or not is_instance_valid(inspected):return
	if reset and not inspected.get_meta("studio",false):message("기본 가구는 팔레트에서 색을 골라 주세요");return
	pending=true
	if inspected.get_meta("studio",false):
		var target := "all" if part_choice.selected==0 else part_choice.get_item_text(part_choice.selected)
		var response: Dictionary=await api.post("/v1/objects/"+selected.id+"/colors",api.mutation({"version":inspected.runtime_version,"part":target,"color":color,"reset":reset}))
		if response.ok:
			inspected.runtime_version=response.data.version;inspected.paint(response.data.colors)
			if placed.has(selected.id):placed[selected.id].runtime_version=response.data.version;placed[selected.id].paint(response.data.colors)
		else:message(response.error)
	else:
		var response: Dictionary=await api.post("/v1/objects/"+selected.id,api.mutation({"version":selected.version,"action":"paint","color":color}))
		if response.ok:selected.version=response.data.version;Loader.paint(inspected,Color(color))
		else:message(response.error)
	pending=false

func pick_image(path: String) -> void:
	var file := FileAccess.open(path,FileAccess.READ)
	if file==null or file.get_length()>1024*1024:message("이미지는 1MB 이하로 준비해 주세요");return
	var bytes := file.get_buffer(file.get_length())
	image_data="data:image/"+("png" if path.get_extension().to_lower()=="png" else "jpeg")+";base64,"+Marshalls.raw_to_base64(bytes)
	image_label.text=path.get_file()
	if data.get("llm","fixture")!="fixture":designer.select(1)
	update_price()

func change_room(value: String) -> void:
	clear_selection();room=value;build_room()
	update_capacity()
	if is_instance_valid(hero):hero.position=Vector3(0,0,3)
	await reload_placed()

func update_capacity() -> void:
	var capacity: Dictionary=data.get("room_usage",{}).get(room,{})
	room_capacity.text="배치 %d / 30 · 꾸미기 용량 %.0f%%"%[capacity.get("count",0),capacity.get("percent",0)]
	room_capacity.tooltip_text="가구의 복잡도와 이미지 크기에 따라 용량이 달라져요. 꽉 차면 일부 가구를 회수하거나 다른 방으로 옮겨 주세요."

func leave() -> void:
	Engine.set_meta("studio_session",{"token":api.token,"url":api.base_url,"room":room})
	get_tree().change_scene_to_file("res://scenes/main.tscn")

func _unhandled_key_input(event: InputEvent) -> void:
	if not event.is_pressed() or event.is_echo():return
	if event.physical_keycode==KEY_ESCAPE:
		placement_mode=false;placement_epoch+=1
		if is_instance_valid(ghost):ghost.queue_free()
		ghost=null
	if event.physical_keycode==KEY_R and placement_mode:
		placement_rotation=(placement_rotation+90)%360
		if is_instance_valid(ghost):ghost.rotation_degrees.y=placement_rotation
	if event.physical_keycode==KEY_E:
		if is_instance_valid(hero) and hero.position.z>3.6 and absf(hero.position.x)<1.5:leave()
		else:interact_nearest()

func interact_nearest() -> void:
	if not is_instance_valid(hero) or pending:return
	var nearest := "";var distance := 2.3
	for id in placed:
		var d: float=hero.position.distance_to(placed[id].position)
		if d<distance:nearest=id;distance=d
	if nearest.is_empty():return
	for i in data.objects.size():
		if data.objects[i].id==nearest:await select_item(i);await interact_selected();return

func proximity() -> void:
	if proximity_pending or pending or not is_instance_valid(hero):return
	proximity_pending=true
	var snapshot := placed.keys()
	for id in snapshot:
		if not placed.has(id):continue
		var item: Node3D=placed[id]
		if not is_instance_valid(item) or not item.get_meta("studio",false):continue
		var distance: float=hero.position.distance_to(item.position)
		var near_now: bool=distance<(2.5 if item.nearby else 1.8)
		if near_now==item.nearby:continue
		var response: Dictionary=await api.post("/v1/objects/"+id+"/event",api.mutation({"version":item.runtime_version,"event":"near" if near_now else "leave"}))
		if not is_instance_valid(item):continue
		if response.ok:
			item.nearby=near_now;item.accept_event(response.data)
			if selected.get("id")==id and is_instance_valid(inspected) and inspected.manifest.plan==item.manifest.plan:
				inspected.nearby=near_now;inspected.accept_event(response.data)
			if selected.get("id")==id and is_instance_valid(inspected):inspected.accept_event(response.data)
		elif response.get("status")==409:
			var fresh: Dictionary=await api.request("/v1/objects/"+id+"/assembly")
			if fresh.ok and is_instance_valid(item):item.runtime_version=fresh.data.runtime.version
		else:
			item.queue_free();placed.erase(id)
	proximity_pending=false

func _process(delta: float) -> void:
	if is_instance_valid(placement_marker):
		placement_marker.visible=placement_mode
		placement_marker.position=Vector3(place_at.x,0.065,place_at.z)
		placement_marker.material_override.albedo_color=Color("87c7a7") if placement_problem(place_at).is_empty() else Color("d27566")
	poll_time+=delta;auth_time+=delta
	if poll_time>2.5:poll_time=0;poll_job()
	if auth_time>20:auth_time=0;refresh()
	proximity_time+=delta
	if proximity_time>0.35:proximity_time=0;proximity()
	if not is_instance_valid(hero):return
	hero.external_motion=Vector2.ZERO
	if placement_mode:return
	var focus := get_viewport().gui_get_focus_owner()
	if focus is TextEdit or focus is LineEdit:return
	var direction := Vector3(float(Input.is_physical_key_pressed(KEY_D))-float(Input.is_physical_key_pressed(KEY_A)),0,float(Input.is_physical_key_pressed(KEY_S))-float(Input.is_physical_key_pressed(KEY_W)))
	if direction.length()>0:
		var step := direction.normalized()*delta*2.8
		var candidate: Vector3=hero.position+Vector3(step.x,0,0)
		if not movement_blocked(candidate):hero.position=candidate
		candidate=hero.position+Vector3(0,0,step.z)
		if not movement_blocked(candidate):hero.position=candidate
		hero.position.x=clampf(hero.position.x,-4.5,4.5);hero.position.z=clampf(hero.position.z,-4.5,4.65)
	hero.external_motion=Vector2(direction.x,direction.z)

func movement_blocked(at: Vector3) -> bool:
	if room=="workshop" and absf(at.x+3.7)<1.15 and absf(at.z+3.1)<0.75:return true
	for id in placed:
		var item: Node3D=placed[id]
		var size: Vector3=item.get_meta("size",Vector3(1.6,1.6,1.6))
		var local := (at-item.position).rotated(Vector3.UP,-item.rotation.y)
		if absf(local.x)<size.x*0.5+0.23 and absf(local.z)<size.z*0.5+0.23:return true
	return false

func placement_problem(at: Vector3) -> String:
	if absf(at.x)>4 or absf(at.z)>4:return "벽에서 한 칸 안쪽에 놓아 주세요."
	if absf(at.x)<1.5 and at.z>2.5:return "출입문 앞은 비워 주세요."
	if room=="workshop" and at.x < -1.8 and at.z < -1.5:return "고정 작업대와 겹쳐요."
	if is_instance_valid(hero) and absf(hero.position.x-at.x)<1.15 and absf(hero.position.z-at.z)<1.15:return "캐릭터가 서 있는 곳은 비워 주세요."
	for obj in data.get("objects",[]):
		if obj.id==selected.get("id") or obj.state!="placed" or obj.room!=room:continue
		if absf(obj.x-at.x)<2 and absf(obj.z-at.z)<2:return "다른 가구에서 두 칸 이상 떨어뜨려 주세요."
	return ""
