extends Control
const Api=preload("res://scripts/api.gd")
const Assembly=preload("res://scripts/asset_assembly.gd")
const Loader=preload("res://scripts/model_loader.gd")
const Art=preload("res://scripts/art.gd")
const BuildMode=preload("res://scripts/build_mode.gd")
const ControllerProfile=preload("res://scripts/controller_profile.gd")
const Transition=preload("res://scripts/transition.gd")
const I18n=preload("res://scripts/i18n.gd")
const Interiors=preload("res://scripts/interiors.gd")
const Daylight=preload("res://scripts/daylight.gd")
const RpgUi=preload("res://scripts/rpg_ui.gd")
const Residents=preload("res://scripts/residents.gd")
const GameSettings=preload("res://scripts/game_settings.gd")
const PauseMenu=preload("res://scripts/pause_menu.gd")
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
## Home visits: a friend's home opens read-only; everyone inside the same home
## shares presence so visitors and the host see each other.
var visit_host := ""
var visit_name := ""
var dock_panel: Control
var room_buttons: Array[Button] = []
var peers: Dictionary = {}
var presence_time := 0.0
var presence_pending := false
var shared_presence := false
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
## Reference-image buttons, locked on trial servers (one cheap craft only).
var image_buttons: HBoxContainer
var binding_part: OptionButton
var binding_fields: Dictionary={}
var binding_hint: Label
var binding_dirty := false
var history_list: ItemList
var history_detail: Label
var history_selected := ""
var live_defaults_applied := false
var placement_tools: PanelContainer
var placement_title: Label
var placement_feedback: Label
var place_button: Button
var floor_grid: MeshInstance3D
var grid_toggle: CheckButton
## Interior rooms: "home" and "workshop" can be decorated; a building id such as
## "01_cafe" opens that building's read-only public interior (scripts/interiors.gd).
var room_spec: Dictionary={}
var decor: Array=[]
var public_room := false
var subtitle_label: Label
var controls_label: Label
var environment: Environment
var sun: DirectionalLight3D
var cam_focus := Vector3.ZERO
var interact_count := 0
var bubble: PanelContainer
var bubble_label: Label
var bubble_anchor := Vector3.ZERO
var bubble_tween: Tween
var hint_label: Label
var hint_anchor := Vector3.ZERO
var hint_time := 0.0
var tone_player: AudioStreamPlayer
var leaving := false
## Floors: the building spec, one root per floor (only the current one is shown)
## and each floor's furniture/window records. room_spec is the current floor.
var building_spec: Dictionary={}
var floor_index := 0
var floor_roots: Array=[]
var decor_by_floor: Array=[]
var travelling := false
## Tests drive the walker directly and switch this off to keep it on one floor.
var travel_enabled := true
var sfx_player: AudioStreamPlayer
var place_label: Label
var current_room := -1
var cam_distance := 9.0
## Real-time outside light (Daylight); a test can pin the hour.
var hour_override := -1.0
var daylight_time := 0.0
var daylight_sample: Dictionary={}
## Sitting or lying on furniture.
var rest_pose: SkeletonModifier3D
var resting := ""
var rest_return := Vector3.ZERO
var walk_out := Vector3.ZERO
## RPG-style HUD over the full-screen room view.
var name_panel: PanelContainer
var name_tween: Tween
var toast_panel: PanelContainer
var toast_tween: Tween
var hint_chip: PanelContainer
var hint_key: Label
var dock_toggle: Button
var leave_button: Button
## The last piece of furniture used (tests read it).
var last_used: Dictionary={}
## Residents inside public buildings (scripts/residents.gd decides who is where).
var npcs: Dictionary={}
var residents_time := 0.0
var cue_time := 0.0
var talk_box: Control
var talk_body: Label
var talk_footer: HBoxContainer
## The RpgUi.dialogue window parts while a resident is talking.
var talk_window: Dictionary = {}
var talk_lines: Array=[]
var talk_choices: Array=[]
var talk_page := 0
var talk_id := ""
var pick_cycle := 0
var pick_spot := Vector3(INF,0,INF)
var pick_time := -100.0

func _ready() -> void:
	I18n.setup()
	var veil := Transition.of(get_tree())
	veil.cover()
	veil.fade_in(0.55)
	api=Api.new();add_child(api)
	if Engine.has_meta("studio_session"):
		var session: Dictionary=Engine.get_meta("studio_session")
		api.token=session.token;api.base_url=session.url
		room=str(session.get("room","workshop"))
		visit_host=str(session.get("visit_host",""))
		visit_name=str(session.get("visit_name",""))
		shared_presence=bool(session.get("multiplayer",false)) and room=="home"
		Engine.remove_meta("studio_session")
	if not Interiors.has_interior(room): room="workshop"
	public_room=Interiors.is_public(room)
	veil.play_door("close",room)
	tone_player=AudioStreamPlayer.new();tone_player.volume_db=-5;tone_player.bus=GameSettings.BUS_SFX;add_child(tone_player)
	sfx_player=AudioStreamPlayer.new();sfx_player.volume_db=-8;sfx_player.bus=GameSettings.BUS_SFX;add_child(sfx_player)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--hour="): hour_override=clampf(float(arg.trim_prefix("--hour=")),0.0,23.99)
	if Engine.has_meta("interior_hour"): hour_override=float(Engine.get_meta("interior_hour"))
	build_ui()
	build_stage()
	set_dock_open(room=="workshop")
	if public_room:
		# Village buildings are only for looking around: no inventory, crafting or editing.
		dock_panel.visible=false;dock_toggle.visible=false
		for b in room_buttons: b.visible=false
		message(tr(str(room_spec.flavour)))
		if not api.token.is_empty(): load_avatar()
		return
	if not visit_host.is_empty():
		# Visitors only look around: no inventory, crafting, room switching or editing.
		dock_panel.visible=false;dock_toggle.visible=false
		for b in room_buttons: b.visible=false
		message(tr("%s님의 집에 놀러 왔어요. 가구는 구경만 할 수 있어요.") % visit_name)
	if api.token.is_empty():
		message(tr("마을에서 로그인한 뒤 공방으로 들어오세요."))
	else: await refresh()

## Public rooms need no studio data; the walker still wears the player's look.
func load_avatar() -> void:
	var response: Dictionary=await api.request("/v1/studio")
	if response.ok and is_instance_valid(hero) and response.data is Dictionary:
		hero.apply_avatar(response.data.get("profile",{}).get("avatar",{}))

func theme_style() -> Theme:
	var t := Theme.new()
	t.default_font=RpgUi.FONT_BODY;t.default_font_size=14
	t.set_font("font","Button",RpgUi.FONT_STRONG)
	RpgUi.tooltip_theme(t)
	for type in ["VScrollBar","HScrollBar"]:
		t.set_stylebox("scroll",type,RpgUi.frame("scroll_track"));t.set_stylebox("grabber",type,RpgUi.frame("scroll_grabber"))
		t.set_stylebox("grabber_highlight",type,RpgUi.frame("scroll_grabber_hover"));t.set_stylebox("grabber_pressed",type,RpgUi.frame("scroll_grabber_hover"))
	for type in ["HSlider","VSlider"]:
		t.set_stylebox("slider",type,RpgUi.frame("bar_bg"));t.set_stylebox("grabber_area",type,RpgUi.frame("bar_fill",Color("e9b552")))
		t.set_icon("grabber",type,RpgUi.half("slider_grabber"));t.set_icon("grabber_highlight",type,RpgUi.half("slider_grabber_hover"))
	for type in ["Label","Button","ColorPickerButton","OptionButton","LineEdit","TextEdit","ItemList","CheckButton","CodeEdit"]:
		t.set_color("font_color",type,RpgUi.INK)
		if type in ["Button","OptionButton","CheckButton","ColorPickerButton"]:
			t.set_color("font_hover_color",type,Color("ffe08a"));t.set_color("font_pressed_color",type,Color("ffe08a"))
			t.set_color("font_disabled_color",type,Color(RpgUi.INK,.4))
		if type in ["LineEdit","TextEdit","CodeEdit"]:t.set_color("font_placeholder_color",type,Color(1,1,1,.42))
		if type=="Label":continue
		for state_name in ["normal","hover","pressed","focus","selected","read_only","disabled"]:
			var field: bool = type in ["LineEdit","TextEdit","CodeEdit"]
			var fill := Color(0.05,0.07,0.08,.72) if field else (Color(0.24,0.2,0.12,.95) if state_name in ["hover","selected"] else (Color(0.36,0.28,0.14,.95) if state_name=="pressed" else Color(0.09,0.12,0.13,.9)))
			var style := RpgUi.style(fill,8,RpgUi.GOLD if state_name in ["hover","focus","pressed"] else Color(RpgUi.GOLD,.45),1)
			style.shadow_size=0
			style.content_margin_left=10;style.content_margin_right=10;style.content_margin_top=7;style.content_margin_bottom=7
			t.set_stylebox(state_name,type,style)
	var list_panel := RpgUi.style(Color(0.05,0.07,0.08,.6),8,Color(RpgUi.GOLD,.35),1)
	list_panel.shadow_size=0
	t.set_stylebox("panel","ItemList",list_panel)
	var chosen := RpgUi.style(Color(0.36,0.28,0.14,.9),6,RpgUi.GOLD,1);chosen.shadow_size=0
	t.set_stylebox("selected","ItemList",chosen);t.set_stylebox("selected_focus","ItemList",chosen)
	t.set_color("font_selected_color","ItemList",Color("ffe08a"))
	var popup := RpgUi.style(Color(0.08,0.1,0.11,.97),8,Color(RpgUi.GOLD,.6),1)
	t.set_stylebox("panel","PopupMenu",popup)
	t.set_color("font_color","PopupMenu",RpgUi.INK);t.set_color("font_hover_color","PopupMenu",Color("ffe08a"))
	t.set_stylebox("hover","PopupMenu",chosen)
	t.set_color("font_color","SpinBox",RpgUi.INK)
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

## A small gold key cap ("E", "C", "Esc") like the village hotbar's.
func key_cap(parent: Node, key: String) -> Label:
	var cap := Label.new()
	cap.text=key
	cap.add_theme_font_size_override("font_size",12)
	cap.add_theme_color_override("font_color",Color("2b2112"))
	cap.add_theme_font_override("font",RpgUi.FONT_BOLD)
	cap.add_theme_stylebox_override("normal",RpgUi.frame("keycap"))
	cap.size_flags_vertical=Control.SIZE_SHRINK_CENTER
	cap.mouse_filter=Control.MOUSE_FILTER_IGNORE
	parent.add_child(cap)
	return cap

## A compact dark RPG button for the HUD, with an optional key cap.
func hud_button(parent: Node, value: String, callback: Callable, key := "") -> Button:
	var b := Button.new()
	b.text=value
	b.focus_mode=Control.FOCUS_NONE
	b.custom_minimum_size=Vector2(0,44)
	b.add_theme_font_size_override("font_size",16)
	b.add_theme_font_override("font",RpgUi.FONT_STRONG)
	for state in ["normal","hover","pressed","disabled"]:
		var plate := RpgUi.frame("btn_night_"+state)
		plate.content_margin_left=16 if key.is_empty() else 30
		b.add_theme_stylebox_override(state,plate)
	RpgUi.hover_motion(b,1.04)
	for state in ["font_color","font_hover_color","font_pressed_color"]:
		b.add_theme_color_override(state,Color("fff2cf") if state!="font_hover_color" else Color("ffe08a"))
	b.pressed.connect(callback)
	parent.add_child(b)
	if not key.is_empty():
		var cap := key_cap(b,key)
		cap.position=Vector2(-6,-9)
	return b

func set_dock_open(open: bool) -> void:
	if not is_instance_valid(dock_panel): return
	dock_panel.visible=open and visit_host.is_empty() and not public_room
	if is_instance_valid(dock_toggle): dock_toggle.modulate=Color(1,1,1,1) if not dock_panel.visible else Color(1,0.92,0.75,1)

## The place panel shows on arrival and on every room or floor change, then fades.
func show_place_panel() -> void:
	if not is_instance_valid(name_panel): return
	if name_tween and name_tween.is_valid(): name_tween.kill()
	name_panel.modulate.a=1.0
	name_tween=create_tween()
	name_tween.tween_interval(6.0)
	name_tween.tween_property(name_panel,"modulate:a",0.0,0.8)

func row(parent: Node) -> HBoxContainer:
	var r := HBoxContainer.new();r.add_theme_constant_override("separation",8);parent.add_child(r);return r

func build_ui() -> void:
	theme=theme_style()
	# The room fills the whole screen; the HUD floats over it like the village's.
	view_container=SubViewportContainer.new();view_container.stretch=true;view_container.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(view_container)
	viewport=SubViewport.new();viewport.size=Vector2i(1280,800);viewport.own_world_3d=true;viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS;viewport.msaa_3d=Viewport.MSAA_4X;view_container.add_child(viewport)
	GameSettings.track_viewport(viewport,view_container)
	view_container.gui_input.connect(view_input)
	# Top left: where you are (building, floor, room) and a short line about it.
	name_panel=PanelContainer.new();name_panel.name="PlacePanel";name_panel.position=Vector2(18,16);name_panel.mouse_filter=Control.MOUSE_FILTER_IGNORE
	name_panel.add_theme_stylebox_override("panel",RpgUi.panel_style("night"))
	add_child(name_panel)
	var head := VBoxContainer.new();head.add_theme_constant_override("separation",2);name_panel.add_child(head)
	var title_row := HBoxContainer.new();title_row.add_theme_constant_override("separation",10);head.add_child(title_row)
	title_label=RpgUi.label(title_row,tr("물결빛 공방"),23)
	place_label=RpgUi.label(title_row,"",14,RpgUi.GOLD)
	place_label.size_flags_vertical=Control.SIZE_SHRINK_END
	subtitle_label=RpgUi.label(head,tr("상상한 가구를 만들고, 색칠하고, 내 공간에 놓아요"),13,Color("d8e3d4"),false)
	subtitle_label.custom_minimum_size.x=0;subtitle_label.autowrap_mode=TextServer.AUTOWRAP_OFF
	if BuildMode.developer(): RpgUi.label(head,tr("개발 화면 · 생성 방식과 모델, 코드, 기록을 검증할 수 있습니다"),11,Color("e3b07a"),false)
	# Top centre: what just happened (server replies, furniture lines).
	toast_panel=PanelContainer.new();toast_panel.name="StatusToast";toast_panel.mouse_filter=Control.MOUSE_FILTER_IGNORE
	toast_panel.add_theme_stylebox_override("panel",RpgUi.panel_style("pill"))
	toast_panel.set_anchors_preset(Control.PRESET_CENTER_TOP);toast_panel.grow_horizontal=Control.GROW_DIRECTION_BOTH
	toast_panel.offset_top=92;toast_panel.offset_bottom=92
	add_child(toast_panel)
	status_label=RpgUi.label(toast_panel,tr("서버에 연결하고 있어요"),15,RpgUi.INK,false)
	status_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	toast_panel.visible=false
	# Bottom centre: a key chip for what E (or walking) does right here.
	hint_chip=PanelContainer.new();hint_chip.name="HintChip";hint_chip.mouse_filter=Control.MOUSE_FILTER_IGNORE
	hint_chip.add_theme_stylebox_override("panel",RpgUi.panel_style("pill"))
	hint_chip.set_anchors_preset(Control.PRESET_CENTER_BOTTOM);hint_chip.grow_horizontal=Control.GROW_DIRECTION_BOTH;hint_chip.grow_vertical=Control.GROW_DIRECTION_BEGIN
	add_child(hint_chip)
	var chip_row := HBoxContainer.new();chip_row.add_theme_constant_override("separation",8);chip_row.mouse_filter=Control.MOUSE_FILTER_IGNORE;hint_chip.add_child(chip_row)
	hint_key=key_cap(chip_row,"E")
	controls_label=RpgUi.label(chip_row,tr("WASD 이동   E 상호작용   R 회전   Esc 취소"),15,RpgUi.INK,false)
	# Bottom left: the way out (and the player's two rooms).
	var nav := HBoxContainer.new();nav.name="RoomNav";nav.add_theme_constant_override("separation",8)
	nav.set_anchors_preset(Control.PRESET_BOTTOM_LEFT);nav.grow_vertical=Control.GROW_DIRECTION_BEGIN
	nav.offset_left=18;nav.offset_right=18;nav.offset_top=-66;nav.offset_bottom=-22
	add_child(nav)
	leave_button=hud_button(nav,tr("마을로 나가기"),leave)
	leave_button.icon=RpgUi.icon_texture("home");leave_button.expand_icon=false
	leave_button.add_theme_constant_override("icon_max_width",24)
	room_buttons.append(hud_button(nav,tr("내 집"),func(): await change_room("home")))
	room_buttons.append(hud_button(nav,tr("공방"),func(): await change_room("workshop")))
	# In-world dressing tools remain visible next to the furniture, not in dev tabs.
	placement_tools=PanelContainer.new();placement_tools.name="PlacementTools"
	placement_tools.position=Vector2(18,128);placement_tools.custom_minimum_size.x=345
	placement_tools.add_theme_stylebox_override("panel",RpgUi.panel_style("night"))
	add_child(placement_tools);placement_tools.visible=false
	var tools := VBoxContainer.new();tools.add_theme_constant_override("separation",8);placement_tools.add_child(tools)
	placement_title=label(tools,tr("가구 놓기"),18)
	placement_title.max_lines_visible=1;placement_title.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS
	placement_feedback=label(tools,tr("빈자리를 골라 주세요"),13)
	var rotate_row := row(tools)
	button(rotate_row,tr("↶ 회전"),func():rotate_placement(-90))
	button(rotate_row,tr("회전 ↷"),func():rotate_placement(90))
	grid_toggle=CheckButton.new();grid_toggle.text=tr("격자");grid_toggle.button_pressed=true;rotate_row.add_child(grid_toggle)
	var confirm_row := row(tools)
	place_button=button(confirm_row,tr("여기에 놓기"),commit_place);place_button.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	button(confirm_row,tr("취소"),cancel_placement)
	# Right: the crafting and decorating drawer, opened from a hotbar-style slot.
	var dock := PanelContainer.new();dock_panel=dock;dock.name="Dock"
	dock.add_theme_stylebox_override("panel",RpgUi.panel_style("night"))
	dock.set_anchors_preset(Control.PRESET_RIGHT_WIDE);dock.grow_horizontal=Control.GROW_DIRECTION_BEGIN
	dock.offset_left=-412;dock.offset_right=-14;dock.offset_top=14;dock.offset_bottom=-112
	add_child(dock)
	dock_toggle=Button.new();dock_toggle.name="DockToggle";dock_toggle.custom_minimum_size=Vector2(78,78);dock_toggle.focus_mode=Control.FOCUS_NONE
	RpgUi.name_tip(dock_toggle,tr("제작"),"C")
	for state in ["normal","hover","pressed"]:
		dock_toggle.add_theme_stylebox_override(state,RpgUi.frame({"normal":"slot_night","hover":"slot_night_hover","pressed":"slot_night_pressed"}[state]))
	RpgUi.hover_motion(dock_toggle,1.08,Vector2(0.5,1.0))
	dock_toggle.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT);dock_toggle.grow_horizontal=Control.GROW_DIRECTION_BEGIN;dock_toggle.grow_vertical=Control.GROW_DIRECTION_BEGIN
	dock_toggle.offset_left=-96;dock_toggle.offset_right=-18;dock_toggle.offset_top=-96;dock_toggle.offset_bottom=-18
	add_child(dock_toggle)
	var slot := VBoxContainer.new();slot.alignment=BoxContainer.ALIGNMENT_CENTER;slot.mouse_filter=Control.MOUSE_FILTER_IGNORE
	slot.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);slot.add_theme_constant_override("separation",0);dock_toggle.add_child(slot)
	var art := RpgUi.icon("res://assets/ui/craft.svg",38);art.size_flags_horizontal=Control.SIZE_SHRINK_CENTER;slot.add_child(art)
	var caption := RpgUi.label(slot,tr("제작"),12);caption.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;caption.mouse_filter=Control.MOUSE_FILTER_IGNORE
	var toggle_cap := key_cap(dock_toggle,"C");toggle_cap.position=Vector2(-6,-8)
	dock_toggle.pressed.connect(func(): set_dock_open(not dock_panel.visible))
	var box := VBoxContainer.new();dock.add_child(box)
	wallet=RpgUi.label(box,tr("나의 공방"),18,RpgUi.GOLD)
	quote_panel=VBoxContainer.new();box.add_child(quote_panel);quote_panel.visible=false
	quote_label=label(quote_panel,"",14)
	var quote_actions := row(quote_panel)
	button(quote_actions,tr("도형으로 동작 미리보기") if BuildMode.developer() else tr("모습 미리보기"),preview_design)
	button(quote_actions,tr("이 설계로 생성") if BuildMode.developer() else tr("가구 완성하기"),confirm_job)
	button(quote_actions,tr("취소 · 별씨 환불") if BuildMode.developer() else tr("취소"),cancel_job)
	var tabs := TabContainer.new();tabs.size_flags_vertical=Control.SIZE_EXPAND_FILL;box.add_child(tabs)
	var tab_panel := StyleBoxFlat.new();tab_panel.bg_color=Color(0.05,0.07,0.08,.55);tab_panel.set_corner_radius_all(12)
	tab_panel.content_margin_left=8;tab_panel.content_margin_right=8;tab_panel.content_margin_top=8;tab_panel.content_margin_bottom=8
	tabs.add_theme_stylebox_override("panel",tab_panel)
	var tab_bar := tabs.get_tab_bar()
	for state_name in ["tab_selected","tab_unselected","tab_hovered"]:
		var tab_style := StyleBoxFlat.new()
		tab_style.bg_color=Color(0.36,0.28,0.14,.95) if state_name=="tab_selected" else Color(0.09,0.12,0.13,.9)
		tab_style.set_border_width_all(1);tab_style.border_color=Color(RpgUi.GOLD,.8 if state_name=="tab_selected" else .4)
		tab_style.set_corner_radius_all(7)
		tab_style.content_margin_left=11;tab_style.content_margin_right=11;tab_style.content_margin_top=7;tab_style.content_margin_bottom=7
		tab_bar.add_theme_stylebox_override(state_name,tab_style)
		tabs.add_theme_stylebox_override(state_name,tab_style)
	tab_bar.add_theme_color_override("font_selected_color",Color("ffe08a"))
	tab_bar.add_theme_color_override("font_unselected_color",RpgUi.INK)
	tab_bar.add_theme_color_override("font_hovered_color",Color("ffe08a"))
	tabs.add_theme_color_override("font_selected_color",Color("ffe08a"))
	tabs.add_theme_color_override("font_unselected_color",RpgUi.INK)
	var create_scroll := ScrollContainer.new();create_scroll.name=tr("만들기");tabs.add_child(create_scroll)
	var create := VBoxContainer.new();create.size_flags_horizontal=Control.SIZE_EXPAND_FILL;create.add_theme_constant_override("separation",10);create_scroll.add_child(create)
	label(create,tr("어떤 물건을 만들까요?"),20)
	prompt=TextEdit.new();prompt.custom_minimum_size.y=112;prompt.wrap_mode=TextEdit.LINE_WRAPPING_BOUNDARY;prompt.text=tr("다가가면 꽃잎이 열리는 꽃 조명");create.add_child(prompt)
	var presets := row(create)
	button(presets,tr("꽃 조명"),func(): prompt.text=tr("다가가면 여섯 꽃잎이 열리고 떠나면 닫히는 꽃 조명"))
	button(presets,tr("상자"),func(): prompt.text=tr("클릭하면 뚜껑이 부드럽게 열리고 다시 클릭하면 닫히는 나무 상자"))
	button(presets,tr("시계"),func(): prompt.text=tr("시침과 분침이 움직이고 클릭하면 멈추는 탁상 시계"))
	image_label=label(create,tr("참고 그림을 추가할 수 있어요"),12)
	image_buttons = row(create)
	button(image_buttons,tr("이미지 선택"),func(): file_dialog.popup_centered_ratio(0.7))
	button(image_buttons,tr("제거"),func(): image_data="";image_label.text=tr("참고 이미지 없음");update_price())
	refine_reference=CheckButton.new();refine_reference.text=tr("그림을 먼저 정리해서 만들기");refine_reference.tooltip_text=tr("Tripo 이미지 편집: 부품당 예상 5크레딧 추가. 이후 이미지→3D 요금 적용.");create.add_child(refine_reference);refine_reference.toggled.connect(func(_value):update_price())
	file_dialog=FileDialog.new();file_dialog.access=FileDialog.ACCESS_FILESYSTEM;file_dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;file_dialog.filters=PackedStringArray(["*.png,*.jpg,*.jpeg ; Reference image"]);add_child(file_dialog);file_dialog.file_selected.connect(pick_image)
	label(create,tr("표면과 움직임"),15)
	surface_mode=option(create,[tr("내가 직접 색칠하기"),tr("완성된 질감 포함하기")])
	motion=option(create,[tr("움직이는 가구"),tr("정적인 가구")])
	var dev_title := label(create,tr("개발용 생성 설정"),15)
	designer=option(create,[tr("샘플 설계 · API 비용 없음"),tr("LLM 설계 · 서버 설정 사용")])
	geometry=option(create,[tr("검증용 도형 · Tripo 비용 없음"),tr("Tripo 실제 생성 · 크레딧 사용")])
	mesh_models=option(create,[tr("H3 · 일반 가구 / 낮은 비용"),tr("P2 · 정밀 메시 / 높은 비용")])
	mesh_models.item_selected.connect(func(_value):update_price())
	var advanced := VBoxContainer.new()
	var advanced_button := button(create,tr("모델 비교 설정 펼치기"),func(): advanced.visible=not advanced.visible)
	create.add_child(advanced);advanced.visible=false
	models=option(advanced,["gpt-6-luna","gpt-5.6-terra","gpt-6-sol","gpt-6-astra"])
	efforts=option(advanced,["low","medium","high","xhigh"]);efforts.select(2)
	provider_price=label(create,tr("검증용 도형: Tripo 비용 0"),12)
	generation_button=button(create,tr("만들기 · 30 별씨"),generate)
	surface_mode.item_selected.connect(func(_i): update_price());motion.item_selected.connect(func(_i): update_price())
	geometry.item_selected.connect(func(_i): update_price())
	var dev_note := label(create,tr("별씨는 게임 재화입니다. API 크레딧과 같은 단위가 아닙니다. 검증용 도형은 생성 메시의 완성도를 보여주지 않습니다."),12)
	dev_note.modulate=Color("817960")
	var own := VBoxContainer.new();own.name=tr("보관함");tabs.add_child(own)
	label(own,tr("내가 만든 작은 세계"),19)
	room_capacity=label(own,tr("배치한 가구를 확인하고 있어요"),12)
	inventory=ItemList.new();inventory.custom_minimum_size.y=135;inventory.size_flags_vertical=Control.SIZE_EXPAND_FILL;inventory.fixed_icon_size=Vector2i(26,26);own.add_child(inventory);inventory.item_selected.connect(select_item)
	var preview_view := SubViewportContainer.new();preview_view.custom_minimum_size.y=190;preview_view.stretch=true;own.add_child(preview_view)
	var preview_port := SubViewport.new();preview_port.size=Vector2i(330,190);preview_port.own_world_3d=true;preview_port.render_target_update_mode=SubViewport.UPDATE_ALWAYS;preview_port.msaa_3d=Viewport.MSAA_4X;preview_view.add_child(preview_port)
	preview_stage=Node3D.new();preview_port.add_child(preview_stage)
	var preview_env := WorldEnvironment.new();preview_env.environment=Environment.new();preview_env.environment.background_mode=Environment.BG_COLOR;preview_env.environment.background_color=Color("b5c1ad");preview_env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;preview_env.environment.ambient_light_color=Color.WHITE;preview_env.environment.ambient_light_energy=.12;preview_stage.add_child(preview_env)
	var preview_sun := DirectionalLight3D.new();preview_sun.rotation_degrees=Vector3(-40,-30,0);preview_sun.light_energy=.45;preview_stage.add_child(preview_sun)
	preview_camera=Camera3D.new();preview_camera.projection=Camera3D.PROJECTION_ORTHOGONAL;preview_camera.size=2.9;preview_camera.position=Vector3(2.7,2.2,4);preview_stage.add_child(preview_camera);preview_camera.look_at(Vector3(0,.65,0));preview_camera.current=true
	Art.box(preview_stage,Vector3(0,-.04,0),Vector3(8,.06,8),Color("a9b7a0"))
	preview_view.gui_input.connect(preview_input)
	label(own,tr("미리보기 · 드래그 회전 / 휠 확대"),11).modulate=Color("817960")
	detail=label(own,tr("가구를 고르면 모습을 살펴볼 수 있어요"),13)
	var actions := row(own)
	button(actions,tr("바닥에 배치"),begin_place);button(actions,tr("회수"),retrieve);button(actions,tr("사용"),interact_selected)
	part_choice=option(own,[tr("전체 색칠")])
	var palette := row(own)
	for color in ["#f1dfb8","#dfa958","#789887","#bd7f75","#7d9ca3"]:
		var b := button(palette,"●",func(): await paint(color));b.modulate=Color(color);b.size_flags_horizontal=Control.SIZE_EXPAND_FILL
		RpgUi.name_tip(b,RpgUi.color_name(color))
	var custom_row := row(own)
	var custom_color := ColorPickerButton.new();custom_color.text=tr("직접 색 고르기");custom_color.edit_alpha=false;custom_color.color=Color("dfa958");custom_color.size_flags_horizontal=Control.SIZE_EXPAND_FILL;custom_row.add_child(custom_color)
	custom_color.popup_closed.connect(func():await paint("#"+custom_color.color.to_html(false)))
	button(custom_row,tr("원래 색 복원"),func():await paint("#ffffff",true))
	button(own,tr("새로고침"),refresh)
	var source := VBoxContainer.new();source.name=tr("동작 코드");tabs.add_child(source)
	label(source,tr("생성된 조작 함수와 이벤트"),18)
	label(source,tr("서버가 검사한 숫자 연산·부품 제어 코드입니다. 파일이나 재화에 접근할 수 없습니다."),12)
	generated_functions=option(source,[])
	generated_functions.item_selected.connect(load_function_fields)
	function_signature=label(source,"",12)
	function_fields_scroll=ScrollContainer.new();function_fields_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;source.add_child(function_fields_scroll)
	function_fields_box=VBoxContainer.new();function_fields_box.size_flags_horizontal=Control.SIZE_EXPAND_FILL;function_fields_scroll.add_child(function_fields_box)
	raw_args_toggle=CheckButton.new();raw_args_toggle.text=tr("개발자용 JSON 입력");source.add_child(raw_args_toggle)
	function_args=LineEdit.new();function_args.text="[]";function_args.placeholder_text=tr("숫자 인수 예: [0.5]");source.add_child(function_args);function_args.visible=false
	raw_args_toggle.toggled.connect(func(enabled):function_args.visible=enabled;function_fields_scroll.visible=not enabled)
	button(source,tr("선택한 생성 함수 호출"),invoke_generated)
	function_result=label(source,tr("가구를 선택하면 생성된 함수를 검사할 수 있어요."),12)
	code_view=CodeEdit.new();code_view.editable=false;code_view.size_flags_vertical=Control.SIZE_EXPAND_FILL;source.add_child(code_view)
	var fit_scroll := ScrollContainer.new();fit_scroll.name=tr("부품 맞춤");tabs.add_child(fit_scroll)
	var fit := VBoxContainer.new();fit.size_flags_horizontal=Control.SIZE_EXPAND_FILL;fit_scroll.add_child(fit)
	label(fit,tr("움직이는 부품 맞추기"),18)
	label(fit,tr("뚜껑·바늘의 위치와 회전축을 조정합니다. 저장하면 내 가구에만 적용되며 원래 설계로 되돌릴 수 있어요."),12)
	binding_part=option(fit,[]);binding_part.item_selected.connect(load_binding_fields)
	for spec in [["position",tr("위치 · m"),-3.0,3.0,.01],["rotation",tr("방향 · 도"),-360.0,360.0,1.0],["pivot",tr("회전축 · 중심 기준"),-.5,.5,.01],["size",tr("크기 · m"),.02,3.0,.01]]:
		label(fit,spec[1],13)
		var axes := row(fit);var fields: Array[SpinBox]=[]
		for axis in ["X","Y","Z"]:
			var field := SpinBox.new();field.prefix=axis;field.min_value=spec[2];field.max_value=spec[3];field.step=spec[4];field.size_flags_horizontal=Control.SIZE_EXPAND_FILL;axes.add_child(field);fields.append(field)
			field.value_changed.connect(func(_value):preview_binding_fields())
		binding_fields[spec[0]]=fields
	var fitting_actions := row(fit)
	button(fitting_actions,tr("맞춤 저장"),func():await save_binding(false))
	button(fitting_actions,tr("원래 설계로"),func():await save_binding(true))
	button(fit,tr("열기·닫기 등 동작 시험"),interact_selected)
	binding_hint=label(fit,tr("가구를 고르면 부품 목록이 표시됩니다. 전체 크기는 배치 구역에 맞게 자동 조절됩니다."),12)
	var history := VBoxContainer.new();history.name=tr("제작 기록");tabs.add_child(history)
	label(history,tr("최근 제작 30건 · 시간 UTC"),18)
	history_list=ItemList.new();history_list.custom_minimum_size.y=180;history_list.item_selected.connect(select_history);history.add_child(history_list)
	history_detail=label(history,tr("기록을 선택하면 예약·확정 별씨와 확인된 Tripo 비용을 볼 수 있어요."),13)
	button(history,tr("이 설계의 도형 미리보기"),func():await show_design(history_selected))
	button(history,tr("기록 새로고침"),refresh)
	tabs.tab_changed.connect(func(index: int):
		if index==0 or index==4:return
		var target: Control=own if index==1 else (source if index==2 else fit)
		preview_view.reparent(target)
		target.move_child(preview_view,1 if index==1 else 2))
	if not BuildMode.developer():
		for control in [dev_title,designer,geometry,mesh_models,advanced_button,advanced,provider_price,dev_note,refine_reference]: control.visible=false
		for index in [2,3,4]: tabs.set_tab_hidden(index,true)
		prompt.text=""
		prompt.placeholder_text=tr("예: 다가가면 꽃잎이 열리는 꽃 조명")
		generation_button.text=tr("가구 만들기")

func update_price() -> void:
	var cost := (20 if surface_mode.selected==0 else 40)+(10 if motion.selected==0 else 0)
	generation_button.text=tr("만들기 · %d 별씨")%cost
	if geometry.selected==1:
		var use_image := not image_data.is_empty() and (motion.selected==1 or refine_reference.button_pressed)
		var unit := (10+(10 if use_image else 0)) if mesh_models.selected==0 else 100
		if surface_mode.selected==1:unit+=10
		if not image_data.is_empty() and refine_reference.button_pressed:unit+=5
		provider_price.text=tr("공식 요금·실측 기반 예상: ")+(tr("정적 1부품 · %d 크레딧")%unit if motion.selected==1 else tr("부품당 %d 크레딧 · 최대 8부품")%unit)+tr("\n설계 후 부품 수와 예상 비용을 확인합니다.")
		generation_button.text=tr("설계 먼저 · %d 별씨 예약")%cost
	else:provider_price.text=tr("검증용 도형: Tripo 비용 0")

func message(value: String, toast := true) -> void:
	value=value.replace("room_render_budget_exceeded",tr("꾸미기 용량이 꽉 찼어요. 가구 일부를 회수하거나 다른 방에 놓아 주세요."))
	if not BuildMode.developer():
		var words := {"insufficient_shards":tr("별씨가 부족해요. 탐험 보상을 모아 보세요."),"stale_version":tr("가구가 바뀌었어요. 다시 골라 주세요."),"stale_runtime_version":tr("가구가 바뀌었어요. 다시 골라 주세요."),"not_found":tr("물건을 찾을 수 없어요. 보관함을 새로고침해 주세요."),"unauthorized":tr("다시 로그인해 주세요."),"geometry_disabled":tr("지금은 새 가구 제작을 준비하고 있어요."),"placement_overlap":tr("다른 가구와 겹쳐요."),"placement_out_of_bounds":tr("벽과 출입문에서 떨어진 곳에 놓아 주세요."),"model_download_failed":tr("가구를 읽지 못했어요. 잠시 뒤 다시 골라 주세요.")}
		var pattern := RegEx.new();pattern.compile("[a-z][a-z0-9]*_[a-z0-9_]+")
		# Only known codes, or a reply that is nothing but a code, are rewritten;
		# player names such as host_841 stay as they are.
		if pattern.search(value) and pattern.search(value).get_string()==value.strip_edges() and not words.has(value.strip_edges()):
			value=tr("지금은 완료하지 못했어요. 잠시 뒤 다시 시도해 주세요.")
		for match_value in pattern.search_all(value):
			var code: String=match_value.get_string()
			if words.has(code): value=value.replace(code,words[code])
	status_label.text=value
	if is_instance_valid(toast_panel) and is_inside_tree():
		if not toast:
			toast_panel.visible=false
			return
		toast_panel.visible=not value.is_empty()
		toast_panel.modulate.a=1.0
		toast_panel.reset_size()
		var toast_width: float=toast_panel.get_combined_minimum_size().x
		toast_panel.offset_left=-toast_width*0.5;toast_panel.offset_right=toast_width*0.5
		if toast_tween and toast_tween.is_valid(): toast_tween.kill()
		toast_tween=create_tween()
		toast_tween.tween_interval(4.5)
		toast_tween.tween_property(toast_panel,"modulate:a",0.0,0.6)

func build_stage() -> void:
	stage=Node3D.new();viewport.add_child(stage)
	var env := WorldEnvironment.new();environment=Environment.new()
	environment.background_mode=Environment.BG_COLOR;environment.background_color=Color("2a2420")
	environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;environment.ambient_light_color=Color("f2e4cb");environment.ambient_light_energy=0.42
	env.environment=environment;stage.add_child(env)
	sun=DirectionalLight3D.new();sun.rotation_degrees=Vector3(-56,18,0);sun.light_color=Color("fff1dc");sun.light_energy=0.55;sun.shadow_enabled=true
	sun.directional_shadow_max_distance=28;stage.add_child(sun)
	GameSettings.track_light(sun)
	# Animal Crossing style: a perspective camera in front of the open front edge,
	# above the door, looking down toward the back wall and following the walker.
	camera=Camera3D.new();camera.projection=Camera3D.PROJECTION_PERSPECTIVE;camera.fov=40;camera.near=0.2;camera.far=80
	stage.add_child(camera);camera.current=true
	furniture=Node3D.new();stage.add_child(furniture)
	room_root=Node3D.new();stage.add_child(room_root)
	placement_marker=Art.box(stage,Vector3(0,0.065,0),Vector3(1.95,0.015,1.95),Color("8ccbb1"))
	placement_marker.material_override.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	placement_marker.material_override.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	placement_marker.visible=false
	floor_grid=MeshInstance3D.new();floor_grid.name="DecoratingGrid"
	var lines := ImmediateMesh.new();lines.surface_begin(Mesh.PRIMITIVE_LINES)
	for cell in 21:
		var at := -5.0+cell*.5
		lines.surface_add_vertex(Vector3(at,.056,-5));lines.surface_add_vertex(Vector3(at,.056,5))
		lines.surface_add_vertex(Vector3(-5,.056,at));lines.surface_add_vertex(Vector3(5,.056,at))
	lines.surface_end();floor_grid.mesh=lines
	var grid_material := Art.material(Color("f4ead0",.32));grid_material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	grid_material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;floor_grid.material_override=grid_material
	floor_grid.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	stage.add_child(floor_grid);floor_grid.visible=false
	build_overlays()
	build_room()
	# Authored character is separate from all player-created furniture.
	if ResourceLoader.exists("res://assets/explorer_b_reference.glb"):
		hero=preload("res://scripts/player.gd").new();hero.controls_enabled=false;hero.visual_only=true;stage.add_child(hero)
		place_hero_at_door()

## Speech bubble and "E" badge drawn over the room view, pinned to 3D points.
func build_overlays() -> void:
	bubble=PanelContainer.new();bubble.name="InteractionBubble";bubble.mouse_filter=Control.MOUSE_FILTER_IGNORE;bubble.visible=false
	var bubble_style := StyleBoxFlat.new();bubble_style.bg_color=Color("fffaf0",.97);bubble_style.set_corner_radius_all(16)
	bubble_style.set_border_width_all(2);bubble_style.border_color=Color("c9b48a")
	bubble_style.content_margin_left=16;bubble_style.content_margin_right=16;bubble_style.content_margin_top=10;bubble_style.content_margin_bottom=10
	bubble_style.shadow_color=Color(0,0,0,.18);bubble_style.shadow_size=6;bubble_style.shadow_offset=Vector2(0,3)
	bubble.add_theme_stylebox_override("panel",bubble_style)
	bubble_label=Label.new();bubble_label.add_theme_font_size_override("font_size",17);bubble_label.add_theme_color_override("font_color",Color("4a3b2b"))
	bubble_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;bubble.add_child(bubble_label)
	add_child(bubble)
	var tail := Polygon2D.new();tail.name="Tail";tail.color=Color("fffaf0");tail.polygon=PackedVector2Array([Vector2(-9,0),Vector2(9,0),Vector2(0,11)])
	bubble.add_child(tail)
	hint_label=Label.new();hint_label.name="InteractHint";hint_label.text="E";hint_label.mouse_filter=Control.MOUSE_FILTER_IGNORE;hint_label.visible=false
	hint_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	var hint_style := StyleBoxFlat.new();hint_style.bg_color=Color("4a3b2b",.9);hint_style.set_corner_radius_all(14)
	hint_style.content_margin_left=9;hint_style.content_margin_right=9;hint_style.content_margin_top=3;hint_style.content_margin_bottom=3
	hint_label.add_theme_stylebox_override("normal",hint_style);hint_label.add_theme_color_override("font_color",Color("ffe9b0"));hint_label.add_theme_font_size_override("font_size",15)
	add_child(hint_label)

## Keeps an overlay control centred just above a 3D point of the room view.
func pin_overlay(control: Control, anchor: Vector3, lift := 10.0) -> void:
	if not control.visible or not is_instance_valid(camera): return
	if camera.is_position_behind(anchor):
		control.modulate.a=0.0;return
	var at := view_container.global_position+camera.unproject_position(anchor)
	control.reset_size()
	var left := clampf(at.x-control.size.x*0.5,view_container.global_position.x+6,view_container.global_position.x+view_container.size.x-control.size.x-6)
	control.global_position=Vector2(left,maxf(at.y-control.size.y-lift,view_container.global_position.y+6))
	var tail := control.get_node_or_null("Tail") as Polygon2D
	if tail: tail.position=Vector2(clampf(at.x-left,18,control.size.x-18),control.size.y-1)

func place_hero_at_door() -> void:
	if not is_instance_valid(hero): return
	stand_up(false)
	set_floor(0)
	hero.position=Interiors.spawn_point(room_spec)
	# Turned toward the camera, as if just stepping in through the door.
	hero.facing=Vector3.BACK
	update_camera(0.0,true)

## Rebuilds every floor of the current building; the ground floor is shown.
func build_room() -> void:
	for child in room_root.get_children():child.queue_free()
	npcs.clear()
	close_talk()
	building_spec=Interiors.spec(room)
	public_room=bool(building_spec.public)
	floor_roots.clear();decor_by_floor.clear()
	for index in building_spec.floors.size():
		var level := Node3D.new();level.name="Floor_%d" % index;room_root.add_child(level)
		floor_roots.append(level)
		decor_by_floor.append(Interiors.build(level,building_spec.floors[index]))
	floor_index=-1
	set_floor(0)
	title_label.text=tr("나의 작은 집") if room=="home" else tr("물결빛 공방")
	subtitle_label.text=tr("상상한 가구를 만들고, 색칠하고, 내 공간에 놓아요")
	if not visit_host.is_empty(): title_label.text=tr("%s님의 집") % visit_name
	if public_room:
		title_label.text=tr(str(building_spec.name))
		subtitle_label.text=tr(str(building_spec.kind))+"  ·  "+tr(str(building_spec.flavour))
	set_chip("",default_hint())
	show_place_panel()
	apply_daylight(true)
	refresh_residents(true)
	apply_daylight(true)
	if is_instance_valid(bubble): bubble.visible=false
	if is_instance_valid(hint_label): hint_label.visible=false
	update_camera(0.0,true)

## Shows one floor; player-made furniture and visitors live on the ground floor.
func set_floor(index: int) -> void:
	if building_spec.is_empty(): return
	index=clampi(index,0,building_spec.floors.size()-1)
	floor_index=index
	room_spec=building_spec.floors[index]
	decor=decor_by_floor[index]
	for i in floor_roots.size(): floor_roots[i].visible=i==index
	if is_instance_valid(furniture): furniture.visible=index==0
	if is_instance_valid(floor_grid): floor_grid.visible=false
	for entry in peers.values():
		if is_instance_valid(entry.node): entry.node.visible=int(entry.get("floor",0))==index
	current_room=-1
	update_place_label()

func update_place_label() -> void:
	if not is_instance_valid(place_label) or room_spec.is_empty(): return
	var x: float=hero.position.x if is_instance_valid(hero) else 0.0
	var index := Interiors.room_at(room_spec,x)
	if index==current_room: return
	current_room=index
	var parts: PackedStringArray=[]
	if int(room_spec.floors)>1 and not str(room_spec.label).is_empty(): parts.append(tr(str(room_spec.label)))
	var room_name := tr(str(room_spec.rooms[index].name))
	if parts.is_empty() or parts[0]!=room_name: parts.append(room_name)
	place_label.text="·  "+"  ·  ".join(parts)
	show_place_panel()

## Stairs, ladders and hatches: a short fade with footsteps, then the other floor.
func travel(record: Dictionary, instant := false) -> void:
	if travelling or not record.has("link") or leaving: return
	travelling=true
	stand_up(false)
	var link: Dictionary=record.link
	var from_floor := floor_index
	if is_instance_valid(bubble): bubble.visible=false
	if not instant and is_instance_valid(hero):
		# Walk onto the stair and up (or down into the hatch); the floors swap
		# under a short fade near the end of the visible part of the climb.
		sfx_player.stream=Interiors.sfx("steps");sfx_player.play()
		var veil := Transition.of(get_tree())
		var path: Array[Vector3]=Interiors.climb_path(record,hero.position)
		await follow_path(path,1.15,0.62,veil,record.kind=="ladder",record)
		if veil.veil.modulate.a<0.99: await veil.fade_out(0.12)
	set_floor(int(link.to))
	var counterpart := {}
	for other in decor:
		if other.has("link") and int(other.link.to)==from_floor: counterpart=other;break
	if is_instance_valid(hero):
		hero.external_velocity=Vector2.ZERO;hero.external_motion=Vector2.ZERO
		hero.position=link.arrive
		hero.facing=Vector3.BACK
	apply_daylight(true)
	if not instant and is_instance_valid(hero) and not counterpart.is_empty():
		# Step off the stair on the new floor instead of appearing on the spot.
		var off: Array[Vector3]=Interiors.arrival_path(counterpart,link.arrive)
		hero.position=off[0]
		update_camera(0.0,true)
		Transition.of(get_tree()).fade_in(0.3)
		await follow_path(off,1.15,-1.0,null,counterpart.kind=="ladder",counterpart)
	else:
		update_camera(0.0,true)
		if not instant: await Transition.of(get_tree()).fade_in(0.3)
	if is_instance_valid(hero):
		hero.position=link.arrive
		hero.external_velocity=Vector2.ZERO;hero.external_motion=Vector2.ZERO
	travelling=false

## Moves the walker along points (with height) at walking pace: the walk clip
## runs from the real displacement, so steps never slide. On a ladder the
## walker faces the rungs and rises with a little bob instead.
func follow_path(points: Array[Vector3], speed: float, fade_at: float, veil: CanvasLayer, ladder := false, record := {}) -> void:
	if points.size()<2 or not is_instance_valid(hero): return
	var lengths: Array[float]=[]
	var total := 0.0
	for i in points.size()-1:
		var length: float=points[i].distance_to(points[i+1])
		lengths.append(length)
		total+=length
	if total<0.001: return
	var face_ladder := Vector3.ZERO
	if ladder and not record.is_empty(): face_ladder=Vector3(0,0,-1).rotated(Vector3.UP,float(record.yaw))
	var travelled := 0.0
	var faded := false
	while travelled<total:
		var delta := get_process_delta_time()
		if delta<=0.0: delta=1.0/60.0
		# One distance along the whole path, so steps keep an even pace across corners.
		var segment := 0
		var along := travelled
		while segment<lengths.size()-1 and along>lengths[segment]:
			along-=lengths[segment];segment+=1
		var a: Vector3=points[segment]
		var b: Vector3=points[segment+1]
		var flat := Vector3(b.x-a.x,0,b.z-a.z)
		var climbing_rungs: bool=ladder and flat.length()<0.05
		travelled=minf(total,travelled+speed*delta*(0.6 if climbing_rungs else 1.0))
		along=travelled
		segment=0
		while segment<lengths.size()-1 and along>lengths[segment]:
			along-=lengths[segment];segment+=1
		var before: Vector3=hero.position
		hero.position=points[segment].lerp(points[segment+1],clampf(along/maxf(lengths[segment],0.0001),0.0,1.0))
		var step := Vector2(hero.position.x-before.x,hero.position.z-before.z)
		if climbing_rungs or step.length()<0.0005:
			if climbing_rungs: hero.facing=face_ladder
			hero.external_velocity=Vector2.ZERO;hero.external_motion=Vector2.ZERO
		else:
			hero.facing=Vector3(step.x,0,step.y).normalized()
			# Steps are steep: the stepping clip keeps at least a gentle walking pace.
			hero.external_velocity=step.normalized()*maxf(step.length()/delta,0.9)
			hero.external_motion=step.normalized()
		if fade_at>=0.0 and not faded and veil and travelled/total>=fade_at:
			faded=true
			veil.fade_out(0.3)
		await get_tree().process_frame
		if not is_instance_valid(hero): return
	hero.external_velocity=Vector2.ZERO;hero.external_motion=Vector2.ZERO

## Real-time light: windows, sunbeams, ambient, sun and room lamps follow the clock.
func apply_daylight(force := false) -> void:
	if building_spec.is_empty() or not is_instance_valid(environment): return
	var hour := hour_override if hour_override>=0.0 else Daylight.clock_hour()
	daylight_sample=Daylight.sample(hour)
	var day: float=daylight_sample.daylight
	var night: float=daylight_sample.night
	var sun_color: Color=daylight_sample.sun_color
	var tint := Color.WHITE.lerp(sun_color,0.55)*lerpf(0.82,1.08,day)
	tint.a=1.0
	for view in get_tree().get_nodes_in_group("window_view"):
		if not room_root.is_ancestor_of(view): continue
		var material: ShaderMaterial=view.material_override
		material.set_shader_parameter("night",clampf(night*1.15,0.0,1.0))
		material.set_shader_parameter("tint",tint)
	for index in floor_roots.size():
		if force or index==floor_index: Interiors.sunbeams(floor_roots[index],building_spec.floors[index],daylight_sample)
	var colors: Dictionary=room_spec.colors
	var theme_ambient := Color(str(colors.ambient))
	environment.ambient_light_color=theme_ambient.lerp(daylight_sample.ambient_color,0.25+0.35*night)
	environment.ambient_light_energy=lerpf(0.31,0.42,day)*(0.86 if room_spec.theme=="observatory" else 1.0)
	environment.background_color=Color("2a2420").lerp(Color("0f1430"),night)
	sun.light_color=sun_color if day>0.05 else Color("a3bcff")
	sun.light_energy=lerpf(0.1,0.55,day)*(0.6 if room_spec.theme=="observatory" else 1.0)
	var awake_rooms := {}
	var sleeping_rooms := {}
	for entry in npcs.values():
		var where := "%d/%d" % [int(entry.floor),Interiors.room_at(building_spec.floors[entry.floor],float(entry.holder.position.x))]
		if entry.state.get("asleep",false): sleeping_rooms[where]=true
		else: awake_rooms[where]=true
	for index in floor_roots.size():
		for lamp in floor_roots[index].find_children("*","OmniLight3D",true,false):
			if not lamp.is_in_group("room_lamp"): continue
			var where := "%d/%d" % [index,int(lamp.get_meta("room",0))]
			var dim := 0.3 if sleeping_rooms.has(where) and not awake_rooms.has(where) else 1.0
			lamp.light_energy=float(lamp.get_meta("base_energy",0.5))*lerpf(0.8,1.45,night)*dim
	for entry in npcs.values():
		if entry.body.has_method("set_night"): entry.body.set_night(clampf(night,0.0,0.6))
		# Rooms keep their own lamps only: a carried lantern stays unlit indoors.
		var lantern = entry.body.get("lantern_light")
		if lantern is OmniLight3D: lantern.visible=false

func refresh() -> void:
	if public_room: return
	if not visit_host.is_empty():
		await share_presence()
		return
	if refreshing:return
	refreshing=true
	var response: Dictionary=await api.request("/v1/studio")
	refreshing=false
	if not response.ok:
		message(tr("서버 연결을 확인해 주세요 · ")+response.error)
		clear_owned()
		return
	data=response.data
	wallet.text=tr("별씨 %d")%data.shards
	if BuildMode.developer(): wallet.text+="  ·  "+(tr("Tripo 실제 생성 가능") if data.geometry_enabled else (tr("개발 공방") if data.llm!="openai" else tr("온라인 공방")))
	var live: bool=data.get("mode","demo")=="live"
	for i in range(models.get_item_count()):models.set_item_disabled(i,live and i!=0)
	for i in range(efforts.get_item_count()):efforts.set_item_disabled(i,live and i!=2)
	if live:
		models.select(0);efforts.select(2)
	# Trial servers cap Tripo credits per craft: only the cheapest craft is offered
	# (paint it yourself · static · H3 · text only).
	var trial: bool=int(data.get("max_tripo_credits",0))>0
	surface_mode.set_item_disabled(1,trial);motion.set_item_disabled(0,trial);mesh_models.set_item_disabled(1,trial)
	if trial:
		surface_mode.select(0);motion.select(1);mesh_models.select(0)
		image_data="";image_label.text=tr("체험판에서는 글로 설명한 정적인 가구 한 덩어리를 만들어요.")
		refine_reference.button_pressed=false
		update_price()
	refine_reference.disabled=trial
	for child in image_buttons.get_children():
		if child is Button:child.disabled=trial
	if is_instance_valid(hero):hero.apply_avatar(data.get("profile",{}).get("avatar",{}))
	update_capacity()
	history_list.clear()
	for entry in data.jobs:history_list.add_item(job_status(entry.state)+tr(" · %d 별씨 · %s")%[entry.cost,Time.get_datetime_string_from_unix_time(int(entry.created)).replace("T"," ")])
	designer.set_item_disabled(0,live);designer.set_item_disabled(1,data.llm=="fixture")
	geometry.set_item_disabled(0,live);geometry.set_item_disabled(1,not data.geometry_enabled)
	generation_button.disabled=live and not data.geometry_enabled
	if not live_defaults_applied:
		live_defaults_applied=true
		if data.geometry_enabled and data.llm!="fixture":
			designer.select(1);geometry.select(1);update_price()
	inventory.clear()
	for obj in data.objects:
		var kind := "furniture"
		var title: String=str(obj.name).to_lower()
		if "상자" in title or "chest" in title or "box" in title:kind="chest"
		elif "시계" in title or "clock" in title:kind="clock"
		elif "조명" in title or "lamp" in title:kind="lamp"
		inventory.add_item(("● " if obj.state=="placed" else "○ ")+obj.name,load("res://assets/items/"+kind+".svg"))
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
			if not latest.ok:clear_selection();message(tr("선택한 가구를 다시 불러올 수 없어요."));return
			if latest.data.plan!=inspected.manifest.plan:
				if binding_dirty:
					message(tr("다른 곳에서 부품 맞춤이 바뀌었어요. 편집값은 보존했습니다. 가구를 다시 선택하면 최신 설계를 불러옵니다."));return
				for index in data.objects.size():
					if data.objects[index].id==selected_id:await select_item(index);break
			else:
				inspected.accept_event({"state":latest.data.runtime.state,"commands":[],"version":latest.data.runtime.version})
				inspected.paint(latest.data.runtime.colors)
	if not placement_mode:message(tr("꾸민 모습이 저장됐어요 · ")+(tr("내 집") if room=="home" else tr("공방")))

func clear_selection() -> void:
	cancel_placement()
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
	if is_instance_valid(detail):detail.text=tr("가구를 고르면 모습을 살펴볼 수 있어요")

func clear_owned() -> void:
	epoch+=1
	clear_selection()
	for n in furniture.get_children():n.queue_free()
	placed.clear()

func load_item(obj: Dictionary) -> Node3D:
	# A visitor reads the host's furniture through the read-only guest routes.
	var prefix := "/v1/objects/" if visit_host.is_empty() else "/v1/social/village/objects/"
	var value: Node3D=await Assembly.fetch(api,obj.id,prefix)
	if value:return value
	if obj.get("studio",false):return null
	var response: Dictionary=await api.request(prefix+obj.id+"/model",{},HTTPClient.METHOD_GET,true)
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
	if not item:message(tr("에셋을 읽을 수 없습니다"));return
	inspected=item;preview_stage.add_child(item);item.position=Vector3.ZERO
	var preview_size: Vector3=item.get_meta("size",Vector3.ONE)
	preview_camera.size=maxf(1.5,preview_size.y*1.5)
	if item.get_meta("studio",false) and item.pivots.has("lid"):preview_camera.size=maxf(1.9,preview_camera.size)
	detail.text=selected.name+"\n"+(tr("배치됨 · ")+{"home":tr("내 집"),"workshop":tr("공방"),"village":tr("마을")}.get(selected.room,tr("다른 공간")) if selected.state=="placed" else tr("보관 중"))
	part_choice.clear();part_choice.add_item(tr("전체 색칠"))
	if item.get_meta("studio",false):
		generated_functions.clear()
		binding_part.clear()
		for fn in item.manifest.program.functions:generated_functions.add_item(fn)
		load_function_fields(0)
		for p in item.manifest.plan.parts:
			var friendly: String={"body":tr("본체"),"lid":tr("뚜껑"),"base":tr("받침"),"stem":tr("줄기"),"hour_hand":tr("시침"),"minute_hand":tr("분침"),"second_hand":tr("초침"),"face":tr("앞면"),"bulb":tr("전구")}.get(p.id,tr("부분 %d")%part_choice.item_count)
			if str(p.id).begins_with("petal_"):friendly=tr("꽃잎 ")+str(p.id).trim_prefix("petal_")
			part_choice.add_item(str(p.id) if BuildMode.developer() else friendly)
			part_choice.set_item_metadata(part_choice.item_count-1,p.id)
			binding_part.add_item(p.id)
		load_binding_fields(0)
		code_view.text=JSON.stringify(item.manifest.program,"  ")
		if BuildMode.developer():
			detail.text+=tr("\n설계: ")+str(item.manifest.provenance.provider)+tr("\n메시: ")+str(item.manifest.provenance.geometry)
			if item.manifest.provenance.geometry=="tripo":detail.text+=tr("\nTripo 실측: %s 크레딧")%str(item.manifest.provenance.get("tripo_credits_consumed",tr("미기록")))
	else:code_view.text=tr("개발자가 제작한 일반 에셋");generated_functions.clear();load_function_fields(-1)
	message(tr("선택한 가구의 최신 상태를 불러왔어요."))

func load_function_fields(index: int) -> void:
	function_fields.clear()
	function_fields_scroll.custom_minimum_size.y=0
	for child in function_fields_box.get_children():function_fields_box.remove_child(child);child.queue_free()
	function_args.text="[]";function_signature.text=tr("이 물건에는 생성된 조작 함수가 없어요.")
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
	function_signature.text=function_name+"("+", ".join(names)+")"+(tr(" · 입력값 없이 실행") if names.is_empty() else tr(" · 숫자를 입력하고 실행하세요"))
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
		binding_hint.text=tr("%s · X 좌우 / Y 높이 / Z 앞뒤\n회전축 -0.5는 부품의 뒤·아래·왼쪽 끝, 0.5는 반대쪽 끝입니다.")%id

func preview_binding_fields() -> void:
	if binding_part.item_count==0 or not is_instance_valid(inspected):return
	var edits := {}
	for key in binding_fields:
		edits[key]=[]
		for field in binding_fields[key]:edits[key].append(field.value)
	if edits.size()!=4:return
	inspected.preview_binding(binding_part.get_item_text(binding_part.selected),edits)
	binding_dirty=true
	binding_hint.text=tr("미리보기만 변경됨 · ‘맞춤 저장’을 누르면 서버에 저장합니다.")

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
	if not reply.ok:message(tr("맞춤을 저장하지 못했어요 · ")+reply.error);return
	binding_dirty=false
	if placed.has(id):placed[id].queue_free();placed.erase(id)
	await refresh()
	for i in data.objects.size():
		if data.objects[i].id==id:await select_item(i);break
	for i in binding_part.item_count:
		if binding_part.get_item_text(i)==chosen:binding_part.select(i);load_binding_fields(i);break
	message(tr("원래 부품 설계로 돌아왔어요") if reset else tr("부품 맞춤을 저장했어요"))

func invoke_generated() -> void:
	if pending or selected.is_empty() or generated_functions.item_count==0 or not is_instance_valid(inspected):return
	var args=JSON.parse_string(function_args.text)
	if not args is Array:function_result.text=tr("숫자 배열로 입력해 주세요. 예: [0.5]");return
	pending=true
	var reply: Dictionary=await api.post("/v1/objects/"+selected.id+"/invoke",api.mutation({"version":inspected.runtime_version,"function":generated_functions.get_item_text(generated_functions.selected),"args":args}))
	pending=false
	if reply.ok:
		inspected.accept_event(reply.data)
		if placed.has(selected.id):placed[selected.id].accept_event(reply.data)
		function_result.text=tr("반환값: ")+str(reply.data.result)+tr(" · 명령 %d개")%reply.data.commands.size()
	else:function_result.text=reply.error

func generate() -> void:
	if pending or not job_id.is_empty():return
	pending=true;generation_button.disabled=true
	var body := {"prompt":prompt.text.strip_edges(),"material":"mesh" if surface_mode.selected==0 else "textured","motion":"dynamic" if motion.selected==0 else "static","designer":"fixture" if designer.selected==0 else "llm","geometry":"proxy" if geometry.selected==0 else "tripo","model":models.get_item_text(models.selected),"effort":efforts.get_item_text(efforts.selected),"image":image_data,"mesh_model":"v3.1-20260211" if mesh_models.selected==0 else "P2-20260801","image_mode":"refine" if geometry.selected==1 and not image_data.is_empty() and refine_reference.button_pressed else "original"}
	var response: Dictionary=await api.post("/v1/studio/jobs",api.mutation(body))
	pending=false;generation_button.disabled=false
	if not response.ok:
		message(tr("체험판에서는 가장 간단한 제작(직접 색칠 · 정적인 가구 · H3)만 할 수 있어요.") if response.error=="craft_over_trial_limit" else tr("생성을 시작하지 못했어요 · ")+response.error)
		return
	job_id=response.data.id;message(tr("설계를 준비하고 있어요. 다른 가구를 꾸미며 기다릴 수 있어요."));await refresh()

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
			quote_label.text=tr("설계 완료 · %d부품\n총 %d 별씨 · 이미 예약 %d 별씨\nTripo 예상 %s 크레딧\n예상 비용 확인 후에만 유료 생성을 시작합니다.")%[job.parts.size(),int(job.provenance.get("quoted_game_cost",job.cost)),int(job.cost),str(job.provenance.estimated_tripo_credits)]
		else:
			quote_label.text=tr("가구를 만들 준비가 됐어요.\n필요한 별씨 %d개 · 이미 맡긴 별씨 %d개\n완성하기를 누르면 제작을 시작해요.")%[int(job.provenance.get("quoted_game_cost",job.cost)),int(job.cost)]
	var progress := ""
	if job.state=="building":
		var ready := 0
		for state in job.parts.values():
			if state=="ready":ready+=1
		progress=tr(" · %d / %d부품 완료")%[ready,job.parts.size()]
	message(job_status(job.state)+progress)
	if job.state in ["ready","failed","cancelled"]:
		job_id="";await refresh()

func confirm_job() -> void:
	if pending or job_id.is_empty():return
	pending=true
	var response: Dictionary=await api.post("/v1/studio/jobs/"+job_id+"/confirm",api.mutation())
	pending=false
	if response.ok:quote_panel.visible=false;message(tr("확인한 설계로 3D 메시를 만들고 있어요"))
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
	if floor_index!=0:
		# Decorating happens on the ground floor, where the server keeps the furniture.
		stand_up(false);set_floor(0);place_hero_at_door()
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
		# When moving furniture, hide its old instance until confirmation or cancel.
		if placed.has(object_id):placed[object_id].visible=false
		for mesh in ghost.find_children("*","MeshInstance3D",true,false):
			for index in mesh.mesh.get_surface_count():
				var source: Material=mesh.get_active_material(index)
				if source is StandardMaterial3D:
					var translucent: StandardMaterial3D=source.duplicate()
					translucent.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
					translucent.albedo_color.a=.62
					mesh.set_surface_override_material(index,translucent)
		place_at=ghost.position
	else:
		placement_mode=false;message(tr("가구를 불러오지 못했어요. 다시 선택해 주세요."));return
	message(tr("빈 바닥을 가리켜 보세요 · 클릭해서 놓기 · R 회전"))

func rotate_placement(degrees: int) -> void:
	if not placement_mode or pending:return
	placement_rotation=posmod(placement_rotation+degrees,360)
	if is_instance_valid(ghost):ghost.rotation_degrees.y=placement_rotation

func cancel_placement() -> void:
	placement_mode=false;placement_epoch+=1
	if is_instance_valid(ghost):ghost.queue_free()
	ghost=null
	if placed.has(selected.get("id")) and is_instance_valid(placed[selected.id]):placed[selected.id].visible=true

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
	if not BuildMode.developer():
		return {"queued":tr("만들기를 기다리고 있어요"),"planning":tr("상상을 설계하고 있어요"),"awaiting_confirmation":tr("완성할 준비가 됐어요"),"building":tr("가구를 만들고 있어요"),"submitting":tr("가구를 만들고 있어요"),"unknown":tr("제작 결과를 확인하고 있어요"),"ready":tr("가구 완성!"),"failed":tr("제작을 완료하지 못했어요 · 맡긴 별씨를 돌려드렸어요"),"cancelled":tr("제작을 취소했어요")}.get(state,tr("제작 상황을 확인하고 있어요"))
	return {"queued":tr("작업 대기"),"planning":tr("설계와 동작 코드 생성"),"awaiting_confirmation":tr("견적 확인 대기"),"building":tr("메시 생성 · 검증 · 조립"),"submitting":tr("Tripo 요청 전송"),"unknown":tr("요청 결과 확인 필요 · 중복 과금 방지를 위해 정지"),"ready":tr("완성"),"failed":tr("제작 실패 · 별씨 환불"),"cancelled":tr("제작 취소")}.get(state,state)

func select_history(index: int) -> void:
	if index<0 or index>=data.jobs.size():return
	var id: String=data.jobs[index].id;history_selected=id
	var response: Dictionary=await api.request("/v1/studio/jobs/"+id)
	if history_selected!=id:return
	if not response.ok:history_detail.text=response.error;return
	var job: Dictionary=response.data;var proof: Dictionary=job.provenance
	history_detail.text=job_status(job.state)+tr("\n별씨 예약/확정: %d\n")%job.cost
	if proof.has("quoted_game_cost"):history_detail.text+=tr("설계 후 최종 견적: %d 별씨\n")%int(proof.quoted_game_cost)
	if proof.get("geometry")=="tripo":
		history_detail.text+=tr("Tripo 예상: %s 크레딧\n확인된 사용: %s 크레딧\n")%[str(proof.get("estimated_tripo_credits",tr("미기록"))),str(proof.get("known_tripo_credits",0))]
		if not proof.get("billing_complete",false):history_detail.text+=tr("일부 작업 비용은 아직 미확인입니다. 0원 확정이 아닙니다.\n")
	else:history_detail.text+=tr("도형 메시 · Tripo 호출 없음\n")
	if job.state=="failed":history_detail.text+=tr("게임 별씨는 환불했지만 이미 실행된 제공사 비용은 남을 수 있습니다.\n")
	if job.get("error"):history_detail.text+=tr("상태 코드: ")+str(job.error)

func preview_design() -> void:
	await show_design(job_id)

func show_design(id: String) -> void:
	if id.is_empty():return
	var response: Dictionary=await api.request("/v1/studio/jobs/"+id+"/preview")
	if not response.ok:message(tr("설계 미리보기 실패 · ")+response.error);return
	var window=load("res://scripts/design_preview.gd").new()
	add_child(window)
	if window.show_plan(response.data):window.popup_centered()
	else:window.queue_free();message(tr("설계를 표시하지 못했습니다"))

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
	if not reply.ok:message(tr("여기에는 놓을 수 없어요 · ")+reply.error);await refresh();return
	cancel_placement()
	await refresh()
	message(tr("좋아요! 가구를 놓았어요."))

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
	if reset and not inspected.get_meta("studio",false):message(tr("기본 가구는 팔레트에서 색을 골라 주세요"));return
	pending=true
	if inspected.get_meta("studio",false):
		var target := "all" if part_choice.selected==0 else str(part_choice.get_item_metadata(part_choice.selected))
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
	if file==null or file.get_length()>1024*1024:message(tr("이미지는 1MB 이하로 준비해 주세요"));return
	var bytes := file.get_buffer(file.get_length())
	image_data="data:image/"+("png" if path.get_extension().to_lower()=="png" else "jpeg")+";base64,"+Marshalls.raw_to_base64(bytes)
	image_label.text=path.get_file()
	if data.get("llm","fixture")!="fixture":designer.select(1)
	update_price()

func change_room(value: String) -> void:
	clear_selection();room=value;build_room()
	update_capacity()
	place_hero_at_door()
	await reload_placed()

func update_capacity() -> void:
	var capacity: Dictionary=data.get("room_usage",{}).get(room,{})
	room_capacity.text=tr("배치 %d / 30 · 꾸미기 용량 %.0f%%")%[capacity.get("count",0),capacity.get("percent",0)]
	room_capacity.tooltip_text=tr("가구의 복잡도와 이미지 크기에 따라 용량이 달라져요. 꽉 차면 일부 가구를 회수하거나 다른 방으로 옮겨 주세요.")

func _exit_tree() -> void:
	if not Engine.has_meta("studio_session"): preload("res://scripts/town.gd").discard_kept()

## Shares this walker's spot inside the home and, for visitors, loads the host's
## furniture. Everyone in the same home sees the others (server: mp_presence).
## The floor travels in y (3 m a floor) so walkers only meet on the same floor.
func share_presence() -> void:
	if presence_pending or not is_instance_valid(hero) or api.token.is_empty(): return
	presence_pending=true
	var heading: float=hero.visual.rotation.y if is_instance_valid(hero.visual) else 0.0
	var response: Dictionary=await api.post("/v1/social/presence",{"scene":"home","x":hero.position.x,"z":hero.position.z,"y":floor_index*3.0,"yaw":wrapf(heading,-PI,PI)})
	presence_pending=false
	if not response.ok or not is_inside_tree(): return
	var space = response.data.get("space")
	if not space is Dictionary: return
	if not visit_host.is_empty():
		if str(space.host_id)!=visit_host:
			message(tr("방문이 끝나 마을로 돌아갑니다."))
			visit_host=""
			leave()
			return
		var objects: Array=space.objects
		for obj in objects: obj.room="home"
		var signature := JSON.stringify(objects)
		if signature!=str(data.get("signature","")):
			data={"objects":objects,"signature":signature}
			await reload_placed()
	var self_id := str(response.data.get("self_id",""))
	var present := {}
	for record in space.players:
		if str(record.id)==self_id: continue
		present[record.id]=true
		var level := int(roundf(float(record.get("y",0.0))/3.0))
		if not peers.has(record.id):
			var body: Node3D=preload("res://scripts/player.gd").new()
			body.controls_enabled=false;body.visual_only=true
			stage.add_child(body)
			body.apply_avatar(record.get("avatar",{}))
			body.position=Vector3(record.x,0,record.z)
			var plate := Art.label3d(body,str(record.username),Vector3(0,2.05,0),Color("f0dfba"))
			Art.style_nameplate(plate)
			peers[record.id]={"node":body,"target":Vector3(record.x,0,record.z)}
		peers[record.id].target=Vector3(record.x,0,record.z)
		if int(peers[record.id].get("floor",-1))!=level:
			# Changing floors is a jump, not a glide across the room.
			peers[record.id].node.position=peers[record.id].target
		peers[record.id]["floor"]=level
		peers[record.id].node.visible=level==floor_index
	for id in peers.keys():
		if not present.has(id):
			if is_instance_valid(peers[id].node): peers[id].node.queue_free()
			peers.erase(id)

func update_peers(delta: float) -> void:
	for entry in peers.values():
		var body: Node3D=entry.node
		if not is_instance_valid(body): continue
		var before: Vector3=body.position
		body.position=body.position.lerp(entry.target,ControllerProfile.damping(8.0,delta))
		var moved := Vector2(body.position.x-before.x,body.position.z-before.z)/maxf(delta,.001)
		body.external_velocity=moved if moved.length()>.05 else Vector2.ZERO
		body.external_motion=body.external_velocity.normalized()

func leave() -> void:
	var veil := Transition.of(get_tree())
	if veil.veil.modulate.a > 0.5 or leaving: return
	leaving=true
	stand_up(false)
	# The walker keeps walking out through the doorway while the veil falls.
	if floor_index==0 and is_instance_valid(hero):
		walk_out=Vector3(float(room_spec.get("door_x",0.0)),0,float(room_spec.size.y)*0.5+1.6)
	veil.play_door("open",room)
	await veil.fade_out(0.45)
	if is_instance_valid(hero):
		hero.external_velocity=Vector2.ZERO;hero.external_motion=Vector2.ZERO
	Engine.set_meta("studio_session",{"token":api.token,"url":api.base_url,"room":room})
	get_tree().change_scene_to_file("res://scenes/main.tscn")

func _unhandled_key_input(event: InputEvent) -> void:
	if not event.is_pressed() or event.is_echo():return
	# Rebinding-aware: a key bound to Interact reports KEY_E (game_settings.gd).
	var key := GameSettings.canonical_key(event)
	if is_instance_valid(talk_box):
		match key:
			KEY_E,KEY_SPACE,KEY_ENTER: advance_talk()
			KEY_ESCAPE: close_talk()
			KEY_1,KEY_2,KEY_3:
				var index: int=event.physical_keycode-KEY_1
				if talk_page>=talk_lines.size()-1 and index<talk_choices.size(): run_choice(str(talk_choices[index][1]))
		get_viewport().set_input_as_handled()
		return
	var focus := get_viewport().gui_get_focus_owner()
	if focus is LineEdit or focus is TextEdit:return
	if event.physical_keycode==KEY_ESCAPE:
		if placement_mode: cancel_placement()
		elif not resting.is_empty(): stand_up()
		elif is_instance_valid(dock_panel) and dock_panel.visible: set_dock_open(false)
		else: PauseMenu.open(self)
	if key==KEY_C and is_instance_valid(dock_toggle) and dock_toggle.visible:
		set_dock_open(not dock_panel.visible)
	if key==KEY_R and placement_mode:
		rotate_placement(90)
	if key==KEY_E:
		if not resting.is_empty():stand_up()
		elif is_instance_valid(hero) and floor_index==0 and Interiors.near_door(room_spec,hero.position):leave()
		else:interact_nearest()

func interact_nearest() -> void:
	if not is_instance_valid(hero) or pending or travelling:return
	var list := decor_candidates()
	var pick := next_pick(list.size())
	var fixed: Dictionary=list[pick] if not list.is_empty() else {}
	var nearest := "";var distance := 2.3
	if visit_host.is_empty() and not public_room and floor_index==0:
		for id in placed:
			var d: float=hero.position.distance_to(placed[id].position)
			if d<distance:nearest=id;distance=d
	# Player-made furniture keeps its server interaction; room furniture talks locally.
	if not fixed.is_empty() and (nearest.is_empty() or float(fixed.distance)+1.0<distance):
		pick_cycle=pick;pick_spot=hero.position;pick_time=Time.get_ticks_msec()*0.001
		use_decor(fixed.record)
		return
	if nearest.is_empty():return
	for i in data.objects.size():
		if data.objects[i].id==nearest:await select_item(i);await interact_selected();return

## Everything within reach, best first: the piece the walker faces and is closest
## to leads; pieces hanging above others (a clock over a wardrobe, a window over
## the sink) follow, and pressing E again on the same spot moves on to them.
func decor_candidates() -> Array:
	var found: Array=[]
	if not is_instance_valid(hero): return found
	var facing: Vector3=hero.facing
	facing.y=0
	for record in decor:
		if not record.interactive or not is_instance_valid(record.node): continue
		var local: Vector3=(hero.position-record.center).rotated(Vector3.UP,-float(record.yaw))
		var half: Vector2=record.half
		var gap := Vector2(maxf(0.0,absf(local.x)-half.x),maxf(0.0,absf(local.z)-half.y)).length()
		var reach := 1.35 if record.mounted else 0.85
		if gap>=reach: continue
		var toward: Vector3=record.center-hero.position
		toward.y=0
		var score := gap-0.45*(facing.normalized().dot(toward.normalized()) if toward.length()>0.01 and facing.length()>0.01 else 0.0)
		found.append({"record":record,"distance":gap,"score":score})
	found.sort_custom(func(a,b): return a.score<b.score)
	return found

## Which candidate the next E press uses (cycling while the walker stays put).
func next_pick(count: int) -> int:
	if count<=0 or not is_instance_valid(hero): return 0
	if hero.position.distance_to(pick_spot)<0.25 and Time.get_ticks_msec()*0.001-pick_time<8.0: return (pick_cycle+1)%count
	return 0

## The piece of room furniture the next E press would use, as {record, distance}.
func nearest_decor() -> Dictionary:
	var list := decor_candidates()
	if list.is_empty(): return {}
	return list[next_pick(list.size())]

func use_decor(record: Dictionary) -> void:
	last_used=record
	var who := str(record.get("id","")) if record.kind=="resident" else str(record.get("occupant",""))
	if not who.is_empty() and npcs.has(who):
		talk_to(who,record)
		return
	interact_count+=1
	var hour: float=daylight_sample.get("hour",12.0)
	var result: Dictionary=Interiors.interact(record,interact_count,hour,str(building_spec.get("outlook","meadow")))
	if result.is_empty(): return
	var action: String=result.get("action","look")
	if action=="travel" and travel_enabled:
		travel(record)
		return
	if is_instance_valid(hero) and action!="sit" and action!="lie": hero.face_point(record.center)
	if result.has("chip"): say(str(result.chip),record)
	elif not result.get("quiet",false): say(str(result.text),record)
	var sound: String=result.get("sound","pop")
	if sound=="piano":
		tone_player.stream=Interiors.piano_stream(interact_count)
		tone_player.play()
	else:
		sfx_player.stream=Interiors.sfx(sound);sfx_player.play()
	play_effect(action,record)

## A short speech bubble above the furniture, mirrored in the status bar.
func say(text: String, record: Dictionary) -> void:
	message(text,false)
	if not is_instance_valid(bubble): return
	var size: Vector3=record.get("size",Vector3.ONE)
	var top: float=record.node.global_position.y+(size.y*0.5 if record.mounted else size.y)
	var long_line := text.length()>28
	bubble_label.text=text
	bubble_label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART if long_line else TextServer.AUTOWRAP_OFF
	bubble_label.custom_minimum_size.x=340 if long_line else 0
	bubble_anchor=Vector3(record.center.x,minf(top+0.25,float(room_spec.height)),record.center.z)
	bubble.modulate.a=1.0;bubble.visible=true
	hint_label.visible=false
	pin_overlay(bubble,bubble_anchor,14)
	if bubble_tween and bubble_tween.is_valid(): bubble_tween.kill()
	bubble_tween=create_tween()
	bubble_tween.tween_interval(3.4)
	bubble_tween.tween_property(bubble,"modulate:a",0.0,0.45)
	bubble_tween.tween_callback(func(): bubble.visible=false)

## Shows a small "E" over whatever the walker can use (furniture or the door) and
## the matching key chip at the bottom of the screen.
func update_hint() -> void:
	if not is_instance_valid(hint_label) or not is_instance_valid(hero) or placement_mode or travelling:
		if is_instance_valid(hint_label): hint_label.visible=false
		set_chip("",default_hint())
		return
	if not resting.is_empty():
		hint_label.visible=false
		set_chip("E",tr("일어나기"))
		return
	if floor_index==0 and Interiors.near_door(room_spec,hero.position):
		hint_label.text="E"
		hint_anchor=Vector3(float(room_spec.get("door_x",0.0)),1.45,float(room_spec.size.y)*0.5+0.3)
		hint_label.visible=true
		set_chip("E",tr("문 쪽으로 걸어 나가면 마을로"))
		return
	var fixed := nearest_decor()
	if fixed.is_empty():
		hint_label.visible=false
		set_chip("",default_hint())
		return
	var record: Dictionary=fixed.record
	var size: Vector3=record.get("size",Vector3.ONE)
	var top: float=record.node.global_position.y+(size.y*0.5 if record.mounted else size.y)
	var up: bool=record.has("link") and int(record.link.to)>floor_index
	hint_label.text="E  ▲" if up else ("E  ▼" if record.has("link") else "E")
	hint_anchor=Vector3(record.center.x,minf(top+0.15,float(room_spec.height)),record.center.z)
	hint_label.visible=not bubble.visible
	var who := str(record.get("id","")) if record.kind=="resident" else str(record.get("occupant",""))
	if not who.is_empty() and npcs.has(who):
		set_chip("E",tr("쉿, 자고 있어요") if npcs[who].state.get("asleep",false) else tr("말 걸기"))
	elif record.has("link"): set_chip("E",(tr("▲ 계단 오르기") if up else tr("▼ 계단 내려가기")))
	else: set_chip("E",tr(str(Interiors.ACTION_HINTS.get(str(Interiors.ACTIONS.get(str(record.kind),"look")),"살펴보기"))))

func default_hint() -> String:
	if public_room or not visit_host.is_empty(): return tr("WASD 이동   E 살펴보기")
	return tr("WASD 이동   E 상호작용   R 회전   Esc 취소")

func set_chip(key: String, text: String) -> void:
	if not is_instance_valid(hint_chip): return
	if key=="E": key=GameSettings.key_label("interact")
	# Interaction prompts can be switched off; the plain controls line stays.
	hint_chip.modulate.a=1.0 if key.is_empty() or GameSettings.show_prompts() else 0.0
	if is_instance_valid(hint_label):
		hint_label.modulate.a=1.0 if GameSettings.show_prompts() else 0.0
		if not key.is_empty() and key!="E": hint_label.text=hint_label.text.replace("E",key)
	hint_key.visible=not key.is_empty()
	hint_key.text=key
	controls_label.text=text
	hint_chip.reset_size()
	var chip: Vector2=hint_chip.get_combined_minimum_size()
	hint_chip.offset_left=-chip.x*0.5;hint_chip.offset_right=chip.x*0.5
	hint_chip.offset_top=-chip.y-28;hint_chip.offset_bottom=-28

## Camera framing: in front of the open front edge, above the door side, framing
## the room the walker is in (closer than outside); distance follows that room.
func camera_rig() -> Dictionary:
	var size: Vector2=room_spec.get("size",Vector2(10,10))
	var rooms: Array=room_spec.get("rooms",[{"x0":-size.x*0.5,"x1":size.x*0.5}])
	var index := Interiors.room_at(room_spec,hero.position.x) if is_instance_valid(hero) and not room_spec.is_empty() else 0
	var x0: float=rooms[index].x0
	var x1: float=rooms[index].x1
	var aspect := 1.5
	if is_instance_valid(viewport) and viewport.size.y>0: aspect=float(viewport.size.x)/float(viewport.size.y)
	var pitch := deg_to_rad(30.0)
	var width := x1-x0
	# The view is full screen (1280x800): a little further back than the old
	# letterboxed view so a whole room still fits around the walker.
	var distance := clampf((4.4+maxf(size.y,width*0.85)*0.6)*1.2,9.0,13.4)
	var half_width := distance*tan(deg_to_rad(camera.fov*0.5))*aspect
	var limit := maxf(width*0.5+0.4-half_width*0.92,minf(0.9,width*0.09))
	return {"offset":Vector3(0,sin(pitch),cos(pitch)),"distance":distance,"centre":(x0+x1)*0.5,"x_limit":limit}

func update_camera(delta: float, snap := false) -> void:
	if not is_instance_valid(camera) or room_spec.is_empty(): return
	var size: Vector2=room_spec.size
	var rig := camera_rig()
	var at: Vector3=hero.position if is_instance_valid(hero) else Interiors.spawn_point(room_spec)
	var limit: float=rig.x_limit
	var centre: float=rig.centre
	var target := Vector3(centre+clampf((at.x-centre)*0.65,-limit,limit),0.85+maxf(at.y,0.0)*0.6,clampf(lerpf(-size.y*0.12,at.z,0.55),-size.y*0.5+1.8,size.y*0.5-1.4))
	var weight := ControllerProfile.damping(3.2,delta)
	cam_focus=target if snap else cam_focus.lerp(target,weight)
	cam_distance=float(rig.distance) if snap else lerpf(cam_distance,float(rig.distance),weight)
	camera.position=cam_focus+(rig.offset as Vector3)*cam_distance
	camera.look_at(cam_focus)
	# With the drawer open the room slides left so it stays framed beside it.
	var aspect := float(viewport.size.x)/maxf(1.0,float(viewport.size.y))
	var shift := 0.16*2.0*cam_distance*tan(deg_to_rad(camera.fov*0.5))*aspect if is_instance_valid(dock_panel) and dock_panel.visible else 0.0
	camera.h_offset=shift if snap else lerpf(camera.h_offset,shift,weight)

func proximity() -> void:
	if proximity_pending or pending or not is_instance_valid(hero) or not visit_host.is_empty():return
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
	if is_instance_valid(placement_tools):
		placement_tools.visible=placement_mode
		if placement_mode:
			var problem := placement_problem(place_at)
			placement_title.text=tr("놓을 자리 고르기 · ")+str(selected.get("name",tr("가구")))
			placement_feedback.text=tr("이곳에 놓을 수 있어요 · %d°")%placement_rotation if problem.is_empty() else problem
			placement_feedback.modulate=Color("4a6d50") if problem.is_empty() else Color("a25445")
			place_button.disabled=pending or not problem.is_empty() or not is_instance_valid(ghost)
	if is_instance_valid(floor_grid):floor_grid.visible=placement_mode and grid_toggle.button_pressed
	if is_instance_valid(placement_marker):
		placement_marker.visible=placement_mode
		placement_marker.position=Vector3(place_at.x,0.065,place_at.z)
		placement_marker.material_override.albedo_color=Color("87c7a7",.32) if placement_problem(place_at).is_empty() else Color("d27566",.32)
	poll_time+=delta;auth_time+=delta
	if visit_host.is_empty() and not public_room and not api.token.is_empty():
		if poll_time>2.5:poll_time=0;poll_job()
		if auth_time>20:auth_time=0;refresh()
	presence_time+=delta
	if (shared_presence or not visit_host.is_empty()) and presence_time>0.35:
		presence_time=0
		share_presence()
	update_peers(delta)
	proximity_time+=delta
	if proximity_time>0.35:proximity_time=0;proximity()
	if not is_instance_valid(hero):return
	hero.external_motion=Vector2.ZERO
	hero.external_velocity=Vector2.ZERO
	hint_time+=delta
	if hint_time>0.15:hint_time=0;update_hint();update_place_label();update_name_plates()
	daylight_time+=delta
	if daylight_time>20.0:daylight_time=0;apply_daylight()
	residents_time+=delta
	if residents_time>25.0:residents_time=0;refresh_residents(false);apply_daylight()
	cue_time+=delta
	if cue_time>3.5:cue_time=0;resident_cues()
	if leaving:
		walk_out_step(delta)
	elif not placement_mode and not travelling and not is_instance_valid(talk_box) and not PauseMenu.is_open():
		var focus := get_viewport().gui_get_focus_owner()
		if not (focus is TextEdit or focus is LineEdit):walk(delta)
	update_camera(delta)
	if is_instance_valid(bubble) and bubble.visible: pin_overlay(bubble,bubble_anchor,14)
	if is_instance_valid(hint_label) and hint_label.visible: pin_overlay(hint_label,hint_anchor,6)

## Out through the doorway while the screen fades, at walking pace.
func walk_out_step(delta: float) -> void:
	if not is_instance_valid(hero) or walk_out==Vector3.ZERO: return
	var before: Vector3=hero.position
	hero.position=hero.position.move_toward(walk_out,ControllerProfile.ROOM_WALK*delta)
	report_motion(before,delta)

## WASD walking inside the room.
func walk(delta: float) -> void:
	var input_direction := Input.get_vector("move_left","move_right","move_forward","move_back")
	var direction := Vector3(input_direction.x,0,input_direction.y)
	if direction.length()<=0:return
	if not resting.is_empty():
		stand_up()
		return
	move_hero(direction,delta)

## One step of walking: stays on the floor, slides along furniture, eases into
## doorways, climbs stairs it walks into and leaves through the front door.
func move_hero(direction: Vector3, delta: float) -> void:
	if not is_instance_valid(hero) or direction.length()<=0.0: return
	var before: Vector3=hero.position
	var step := direction.normalized()*delta*ControllerProfile.ROOM_WALK
	var limits := Interiors.walk_limits(room_spec)
	var door_x: float=limits.door_x
	# Heading for the front door from a little to the side: ease into the doorway.
	if room_spec.get("has_door",false) and step.z>0 and hero.position.z>float(limits.front)-0.25 and absf(hero.position.x-door_x)<Interiors.DOOR_HALF+0.4:
		var eased := Vector3(move_toward(hero.position.x,door_x,delta*1.6),0,hero.position.z)
		if can_stand(eased): hero.position=eased
	# ...and the same for doorways between rooms.
	for door in room_spec.get("doorways",[]):
		var middle: float=(float(door.z0)+float(door.z1))*0.5
		if absf(step.x)>0.001 and absf(hero.position.x-float(door.x))<0.9 and absf(hero.position.z-middle)<Interiors.DOORWAY*0.5+0.45:
			var eased := Vector3(hero.position.x,0,move_toward(hero.position.z,middle,delta*1.6))
			if can_stand(eased): hero.position=eased
	var stuck := movement_blocked(hero.position)
	var candidate: Vector3=hero.position+Vector3(step.x,0,0)
	if can_stand(candidate,stuck):hero.position=candidate
	else: try_stairs(candidate,direction)
	candidate=hero.position+Vector3(0,0,step.z)
	if can_stand(candidate,stuck):hero.position=candidate
	else: try_stairs(candidate,direction)
	report_motion(before,delta)
	if room_spec.get("has_door",false) and step.z>0 and direction.normalized().z>0.5 and Interiors.at_door(room_spec,hero.position+Vector3(0,0,step.z)):leave()

## The walk clip and contact IK follow where the walker really went: a blocked or
## clamped step reads as standing still instead of marching in place.
func report_motion(before: Vector3, delta: float) -> void:
	var moved := Vector2(hero.position.x-before.x,hero.position.z-before.z)/maxf(delta,.001)
	if moved.length()<0.25: moved=Vector2.ZERO
	hero.external_velocity=moved
	hero.external_motion=moved.normalized()

## Walking into a staircase, ladder or hatch takes it.
func try_stairs(at: Vector3, direction: Vector3) -> void:
	if not travel_enabled or travelling: return
	var record := blocking_record(at)
	if record.is_empty() or not record.has("link"): return
	var toward: Vector3=record.center-hero.position
	toward.y=0
	if toward.length()<0.01 or direction.normalized().dot(toward.normalized())>0.35: travel(record)

func can_stand(at: Vector3, stuck := false) -> bool:
	if not Interiors.walkable(room_spec,at):return false
	return stuck or not movement_blocked(at)

func movement_blocked(at: Vector3) -> bool:
	if not blocking_record(at).is_empty(): return true
	if floor_index!=0: return false
	for id in placed:
		var item: Node3D=placed[id]
		var size: Vector3=item.get_meta("size",Vector3(1.6,1.6,1.6))
		var local := (at-item.position).rotated(Vector3.UP,-item.rotation.y)
		if absf(local.x)<size.x*0.5+ControllerProfile.BODY_RADIUS and absf(local.z)<size.z*0.5+ControllerProfile.BODY_RADIUS:return true
	return false

## The room furniture whose footprint the walker would stand in at this spot.
func blocking_record(at: Vector3) -> Dictionary:
	for record in decor:
		if not record.solid:continue
		var local: Vector3=(at-record.center).rotated(Vector3.UP,-float(record.yaw))
		var half: Vector2=record.half
		if absf(local.x)<half.x+ControllerProfile.BODY_RADIUS*0.8 and absf(local.z)<half.y+ControllerProfile.BODY_RADIUS*0.8:return record
	return {}

## Client-side check before asking the server; the server accepts x,z in [-4,4]
## with the door strip (|x|<1.5, z>2.5) kept clear, for home and workshop only.
func placement_problem(at: Vector3) -> String:
	if public_room:return tr("이곳에는 가구를 놓을 수 없어요.")
	if floor_index!=0:return tr("가구는 1층에만 놓을 수 있어요.")
	if absf(at.x)>4 or absf(at.z)>4:return tr("벽에서 한 칸 안쪽에 놓아 주세요.")
	if absf(at.x)<1.5 and at.z>2.5:return tr("출입문 앞은 비워 주세요.")
	if room=="workshop" and at.x < -1.8 and at.z < -1.5:return tr("고정 작업대와 겹쳐요.")
	for record in decor:
		if not record.solid:continue
		var half: Vector2=record.world_half
		if absf(record.center.x-at.x)<half.x+0.75 and absf(record.center.z-at.z)<half.y+0.75:return tr("방에 원래 있던 가구와 겹쳐요.")
	if is_instance_valid(hero) and absf(hero.position.x-at.x)<1.15 and absf(hero.position.z-at.z)<1.15:return tr("캐릭터가 서 있는 곳은 비워 주세요.")
	for obj in data.get("objects",[]):
		if obj.id==selected.get("id") or obj.state!="placed" or obj.room!=room:continue
		if absf(obj.x-at.x)<2 and absf(obj.z-at.z)<2:return tr("다른 가구에서 두 칸 이상 떨어뜨려 주세요.")
	return ""

# ---------------------------------------------------------------- furniture feedback

## What using furniture looks like: small, cheap effects instead of sentences.
func play_effect(action: String, record: Dictionary) -> void:
	var node: Node3D=record.node
	var size: Vector3=record.get("size",Vector3.ONE)
	var base_y: float=node.global_position.y
	var top: Vector3=Vector3(record.center.x,base_y+(size.y*0.5 if record.mounted else size.y),record.center.z)
	var front: Vector3=Vector3(0,0,1).rotated(Vector3.UP,float(record.yaw))
	match action:
		"sit": sit_on(record)
		"lie": lie_on(record);sparkle(top+Vector3(0,0.2,0),Color("cfd8ff"),3)
		"open":
			if record.has("lid"):
				var lid: Node3D=record.lid
				var tween := lid.create_tween()
				tween.tween_property(lid,"rotation:x",-1.1,0.35).set_trans(Tween.TRANS_BACK)
				tween.tween_interval(1.4)
				tween.tween_property(lid,"rotation:x",0.0,0.3)
			else: wobble(node,Vector3(1.03,0.97,1.03))
			sparkle(top+front*0.2,Color("ffe39a"),5)
		"cook":
			puff(top+Vector3(0,0.1,0),Color("f4f4f2",0.8),9,1.3,0.3,0.26)
			puff(top+Vector3(0,0.05,0),Color("ffb347",0.9),5,0.35,0.2,0.04)
		"wash":
			bubbles(top+front*0.1+Vector3(0,0.05,0),9)
			puff(top+Vector3(0,0.4,0),Color("7fc4ec",0.9),6,-0.5,0.2,0.05)
		"water":
			puff(top+Vector3(0,0.45,0),Color("7fc4ec",0.9),9,-0.55,0.3,0.06)
			sparkle(top+Vector3(0,0.15,0),Color("c8f0b0"),3)
			wobble(node,Vector3(1.02,1.05,1.02))
		"warm": puff(Vector3(record.center.x,0.6,record.center.z)+front*(size.z*0.5),Color("ffb347",0.95),12,1.3,0.35,0.06)
		"shine":
			sparkle(top+Vector3(0,-size.y*0.35,0),Color("fff2b0"),8)
			ring(top+Vector3(0,-size.y*0.4,0),Color("ffe39a",0.8),1.6)
			for light in node.find_children("*","OmniLight3D",true,false):
				var glow := light.create_tween()
				glow.tween_property(light,"light_energy",light.light_energy*3.0,0.25)
				glow.tween_property(light,"light_energy",light.light_energy,0.8)
		"play":
			for i in 4: note_pop(top+Vector3(randf_range(-0.4,0.4),0.1,0),"♪" if i%2==0 else "♫",i*0.18)
		"read": pages(top+front*0.25,5)
		"wind":
			ring(top,Color("e9d29b",0.9),0.9)
			spin_hands(node)
		"ring":
			ring(top+Vector3(0,0.1,0),Color("ffe39a",0.9),1.2)
			note_pop(top+Vector3(0,0.2,0),"♪",0.0)
		"sip":
			puff(top+Vector3(0,0.05,0),Color("f4f4f2",0.6),4,0.6,0.12,0.08)
			note_pop(top+Vector3(0,0.25,0),"♥",0.15)
		"hammer":
			burst(top+Vector3(0,0.05,0),Color("ffd36a"),8)
			wobble(node,Vector3(1.03,0.96,1.03))
		"pat","grind","pull":
			puff(top,Color("f3ead6",0.8),9,0.6,0.35,0.12)
			wobble(node,Vector3(1.03,0.96,1.03))
			if record.has("bob"):
				var sack: Node3D=record.bob
				var lift := sack.create_tween()
				lift.tween_property(sack,"position:y",sack.position.y+0.8,0.5).set_trans(Tween.TRANS_SINE)
				lift.tween_property(sack,"position:y",sack.position.y,0.6).set_trans(Tween.TRANS_BOUNCE)
		"knock":
			puff(top,Color("c9b9a0",0.6),6,0.4,0.3,0.1)
			wobble(node,Vector3(1.04,0.96,1.04))
		"turn":
			wobble(node,Vector3(1.03,0.97,1.03));turn_once(node,action)
			sparkle(top,Color("fff2b0"),4)
		"switch": ring(top,Color("ffcf86",0.7),0.6)
		"look_out": sparkle(top,Color("fff2b0"),3)
		_:
			wobble(node,Vector3(1.02,1.02,1.02))
			sparkle(top,Color("fff2b0"),3)
	if is_instance_valid(hero) and action in ["read","wash","cook","warm","water","ring","hammer","wind","sip"]: hero.react("craft")

## Shared little meshes and materials so effects never allocate much.
var fx_meshes: Dictionary={}
func fx_mesh(kind: String) -> Mesh:
	if fx_meshes.has(kind): return fx_meshes[kind]
	var mesh: Mesh
	match kind:
		"page":
			var quad := QuadMesh.new();quad.size=Vector2(0.14,0.1);mesh=quad
		"ring":
			var torus := TorusMesh.new();torus.inner_radius=0.42;torus.outer_radius=0.5;torus.rings=24;torus.ring_segments=4;mesh=torus
		_:
			var ball := SphereMesh.new();ball.radius=0.5;ball.height=1.0;ball.radial_segments=8;ball.rings=4;mesh=ball
	fx_meshes[kind]=mesh
	return mesh

func fx_node(kind: String, color: Color, at: Vector3, scale_value: float) -> MeshInstance3D:
	var bit := MeshInstance3D.new()
	bit.mesh=fx_mesh(kind)
	var material := StandardMaterial3D.new()
	material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	material.cull_mode=BaseMaterial3D.CULL_DISABLED
	material.albedo_color=color
	bit.material_override=material
	bit.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	stage.add_child(bit)
	bit.global_position=at
	bit.scale=Vector3.ONE*scale_value
	return bit

## Little four-point stars that pop and fade.
func sparkle(at: Vector3, color: Color, count: int) -> void:
	for i in count:
		var star := Art.label3d(stage,"✦",at+Vector3(randf_range(-0.35,0.35),randf_range(-0.1,0.3),randf_range(-0.2,0.2)),color)
		star.font_size=58;star.outline_size=8;star.outline_modulate=Color(0.45,0.3,0.08,0.7);star.no_depth_test=true
		star.scale=Vector3.ONE*0.2
		var tween := star.create_tween()
		tween.tween_interval(i*0.08)
		tween.tween_property(star,"scale",Vector3.ONE,0.18).set_trans(Tween.TRANS_BACK)
		tween.parallel().tween_property(star,"position:y",star.position.y+0.25,0.7)
		tween.tween_property(star,"modulate:a",0.0,0.35)
		tween.tween_callback(star.queue_free)

func note_pop(at: Vector3, text: String, delay: float) -> void:
	var note := Art.label3d(stage,text,at,Color("fff2c8"))
	note.font_size=62;note.outline_size=8;note.outline_modulate=Color(0.25,0.18,0.3,0.8);note.no_depth_test=true;note.modulate.a=0.0
	var tween := note.create_tween()
	tween.tween_interval(delay)
	tween.tween_property(note,"modulate:a",1.0,0.1)
	tween.parallel().tween_property(note,"position",at+Vector3(randf_range(-0.3,0.3),0.7,0),1.1).set_trans(Tween.TRANS_SINE)
	tween.tween_property(note,"modulate:a",0.0,0.3)
	tween.tween_callback(note.queue_free)

## A soft ring that widens and fades (bells, clocks, lamps, the lens).
func ring(at: Vector3, color: Color, width: float) -> void:
	var halo := fx_node("ring",color,at,0.2)
	var tween := halo.create_tween()
	tween.set_parallel(true)
	tween.tween_property(halo,"scale",Vector3(width,0.3,width),0.6).set_trans(Tween.TRANS_SINE)
	tween.tween_property(halo.material_override,"albedo_color:a",0.0,0.6)
	tween.set_parallel(false)
	tween.tween_callback(halo.queue_free)

## Soap bubbles that wobble upward.
func bubbles(at: Vector3, count: int) -> void:
	for i in count:
		var bubble_bit := fx_node("ball",Color("dff4ff",0.6),at+Vector3(randf_range(-0.3,0.3),0,randf_range(-0.15,0.15)),randf_range(0.09,0.17))
		var tween := bubble_bit.create_tween()
		tween.tween_interval(i*0.07)
		tween.tween_property(bubble_bit,"global_position",bubble_bit.global_position+Vector3(randf_range(-0.2,0.2),randf_range(0.5,0.9),0),1.0).set_trans(Tween.TRANS_SINE)
		tween.tween_callback(bubble_bit.queue_free)

## Pages that flutter up out of a book.
func pages(at: Vector3, count: int) -> void:
	for i in count:
		var page := fx_node("page",Color("fbf6e6",0.95),at+Vector3(randf_range(-0.2,0.2),0,0),1.8)
		var tween := page.create_tween()
		tween.tween_interval(i*0.09)
		tween.set_parallel(true)
		tween.tween_property(page,"global_position",page.global_position+Vector3(randf_range(-0.4,0.4),randf_range(0.5,0.9),randf_range(0.0,0.3)),0.9)
		tween.tween_property(page,"rotation",Vector3(randf_range(-2,2),randf_range(-3,3),randf_range(-2,2)),0.9)
		tween.tween_property(page.material_override,"albedo_color:a",0.0,0.9).set_delay(0.4)
		tween.set_parallel(false)
		tween.tween_callback(page.queue_free)

## Sparks that jump out and fall (a hammer on the workbench).
func burst(at: Vector3, color: Color, count: int) -> void:
	for i in count:
		var spark := fx_node("ball",color,at,0.05)
		var out := Vector3(randf_range(-0.5,0.5),0,randf_range(-0.5,0.5))
		var tween := spark.create_tween()
		tween.tween_property(spark,"global_position",at+out*0.6+Vector3(0,0.35,0),0.18)
		tween.tween_property(spark,"global_position",at+out+Vector3(0,-0.2,0),0.3).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
		tween.tween_callback(spark.queue_free)

## Clock hands whirl round once (built clocks); a generated clock just rings.
func spin_hands(node: Node3D) -> void:
	for hand in node.find_children("*","Node3D",true,false):
		if hand.get_child_count()==1 and hand.get_child(0) is MeshInstance3D and absf(hand.position.z)>0.04 and absf(hand.position.z)<0.07:
			var tween := hand.create_tween()
			tween.tween_property(hand,"rotation:z",hand.rotation.z-TAU,0.8).set_trans(Tween.TRANS_CUBIC)

func wobble(node: Node3D, peak: Vector3) -> void:
	if not is_instance_valid(node) or node.has_meta("wobbling"): return
	node.set_meta("wobbling",true)
	var tween := node.create_tween()
	tween.tween_property(node,"scale",peak,0.08)
	tween.tween_property(node,"scale",Vector3.ONE,0.22).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_callback(func(): node.remove_meta("wobbling"))

func turn_once(node: Node3D, action: String) -> void:
	if action!="turn": return
	var model := node.get_node_or_null("Model") as Node3D
	var target: Node3D=model if model else node
	var tween := target.create_tween()
	tween.tween_property(target,"rotation:y",target.rotation.y+0.5,0.5).set_trans(Tween.TRANS_SINE)
	tween.tween_property(target,"rotation:y",target.rotation.y,0.7).set_trans(Tween.TRANS_SINE)

## A few soft particles (steam, water drops, embers, flour) that drift and fade.
func puff(at: Vector3, color: Color, count: int, rise: float, spread: float, radius: float) -> void:
	var material := StandardMaterial3D.new()
	material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	material.albedo_color=color
	for i in count:
		var bit := MeshInstance3D.new()
		var ball := SphereMesh.new();ball.radius=radius;ball.height=radius*2;ball.radial_segments=8;ball.rings=4
		bit.mesh=ball;bit.material_override=material.duplicate()
		bit.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		stage.add_child(bit)
		bit.global_position=at+Vector3(randf_range(-spread,spread),randf_range(0,0.15),randf_range(-spread,spread))
		var tween := bit.create_tween()
		tween.tween_interval(i*0.06)
		tween.set_parallel(true)
		tween.tween_property(bit,"global_position",bit.global_position+Vector3(randf_range(-0.15,0.15),rise,randf_range(-0.15,0.15)),0.9)
		tween.tween_property(bit,"scale",Vector3.ONE*(1.8 if rise>0 else 0.6),0.9)
		tween.tween_property(bit.material_override,"albedo_color:a",0.0,0.9)
		tween.set_parallel(false)
		tween.tween_callback(bit.queue_free)

func ensure_rest_pose() -> bool:
	if not is_instance_valid(hero) or not is_instance_valid(hero.hand_skeleton): return false
	if not is_instance_valid(rest_pose) or rest_pose.get_parent()!=hero.hand_skeleton:
		rest_pose=Interiors.RestPose.new()
		hero.hand_skeleton.add_child(rest_pose)
	rest_pose.body=hero.visual
	return true

func hip_height() -> float:
	if not is_instance_valid(hero) or not is_instance_valid(hero.hand_skeleton): return 0.85
	var skeleton: Skeleton3D=hero.hand_skeleton
	var bone := skeleton.find_bone("L_Thigh")
	if bone<0: return 0.85
	var hip: Vector3=skeleton.global_transform*skeleton.get_bone_global_rest(bone).origin
	return clampf(hip.y-hero.global_position.y,0.5,1.1)

## Sits on a chair, sofa or bench: hips and knees bend and the walker settles on
## the seat facing out. Any movement key or E gets up again.
func sit_on(record: Dictionary) -> void:
	if not is_instance_valid(hero) or not resting.is_empty(): return
	var size: Vector3=record.size
	var yaw: float=record.yaw
	var front := Vector3(0,0,1).rotated(Vector3.UP,yaw)
	var seat_x := 0.0
	if record.kind=="sofa":
		var local: Vector3=(hero.position-record.center).rotated(Vector3.UP,-yaw)
		seat_x=clampf(local.x,-size.x*0.25,size.x*0.25)
	var seat: Vector3=record.center+Vector3(seat_x,0,0.04).rotated(Vector3.UP,yaw)
	rest_return=hero.position
	resting="sit"
	var height: float=size.y*0.5 if record.kind!="bench" else 0.47
	hero.position=Vector3(seat.x,height-hip_height()+0.1,seat.z)
	hero.facing=front
	hero.external_velocity=Vector2.ZERO;hero.external_motion=Vector2.ZERO
	if ensure_rest_pose(): rest_pose.mode="sit"

## Lies down on a bed, head on the pillow.
func lie_on(record: Dictionary) -> void:
	if not is_instance_valid(hero) or not resting.is_empty(): return
	var size: Vector3=record.size
	var yaw: float=record.yaw
	var head := Vector3(0,0,-1).rotated(Vector3.UP,yaw)
	rest_return=hero.position
	resting="lie"
	var feet: Vector3=record.center-head*(size.z*0.5-0.2)
	hero.facing=Vector3(0,0,-1)
	var down := Vector3(0,-1,0)
	hero.basis=Basis(head.cross(down),head,down)
	hero.position=Vector3(feet.x,minf(size.y*0.5,0.62)+0.14,feet.z)
	hero.external_velocity=Vector2.ZERO;hero.external_motion=Vector2.ZERO
	if ensure_rest_pose(): rest_pose.mode=""

func stand_up(face_away := true) -> void:
	if resting.is_empty() or not is_instance_valid(hero): return
	resting=""
	hero.basis=Basis()
	hero.position=Vector3(rest_return.x,0,rest_return.z)
	if is_instance_valid(rest_pose): rest_pose.mode=""
	if face_away: hero.facing=Vector3.BACK

# ---------------------------------------------------------------- residents

func resident_clock() -> Dictionary:
	var day: int=int(Engine.get_meta("interior_day")) if Engine.has_meta("interior_day") else int(Residents.clock().day)
	return {"hour":float(daylight_sample.get("hour",Daylight.clock_hour())),"day":day}

## Brings the room in line with the schedule: leavers walk out, newcomers walk
## in through the door, people whose activity changed move to their new spot.
func refresh_residents(instant := false) -> void:
	if not public_room or building_spec.is_empty(): return
	var c := resident_clock()
	var now: Array=Residents.occupants(str(building_spec.building),c.hour,c.day)
	var wanted := {}
	for occupant in now: wanted[str(occupant.id)]=occupant
	var taken := {}
	for id in npcs.keys():
		var entry: Dictionary=npcs[id]
		var next: Dictionary=wanted.get(id,{})
		if next.is_empty(): remove_resident(id,not instant)
		elif next.activity!=entry.state.activity or next.spot!=entry.state.spot or next.asleep!=entry.state.asleep:
			var from: Vector3=entry.holder.position
			var same_floor: bool=int(entry.floor)==floor_index
			remove_resident(id,false)
			place_resident(next,taken,from if same_floor and not instant else Vector3.INF)
		else:
			entry.state=next
			if not entry.record.is_empty(): taken[entry.record.node.get_instance_id()]=true
	for occupant in now:
		var id := str(occupant.id)
		if npcs.has(id): continue
		var door := Vector3(float(building_spec.floors[0].get("door_x",0.0)),0,float(building_spec.floors[0].size.y)*0.5-0.45)
		place_resident(occupant,taken,door if not instant and floor_index==0 else Vector3.INF)

func place_resident(occupant: Dictionary, taken: Dictionary, walk_from := Vector3.INF) -> void:
	var id := str(occupant.id)
	var pick: Dictionary=Interiors.choose_spot(occupant,decor_by_floor,taken)
	var level := int(pick.get("floor",0))
	var record: Dictionary=pick.get("record",{})
	if not record.is_empty(): taken[record.node.get_instance_id()]=true
	var holder := Node3D.new();holder.name="Resident_"+id
	floor_roots[level].add_child(holder)
	var body := make_body(id,holder)
	var entry := {"id":id,"holder":holder,"body":body,"state":occupant,"floor":level,"record":record,"pose":"stand","talk":{},"zzz":null}
	npcs[id]=entry
	pose_resident(entry)
	if walk_from!=Vector3.INF and level==floor_index and entry.pose=="stand":
		var target: Vector3=holder.position
		holder.position=walk_from
		walk_to(entry,target,func(): pass)

## A still figure for a resident: shadow folk from shadow_figure.gd, the cast from npc.gd.
func make_body(id: String, holder: Node3D) -> Node3D:
	var info: Dictionary=Residents.resident(id)
	if str(info.get("kind",""))=="cast":
		var npc_script := load("res://scripts/npc.gd") as GDScript
		if npc_script and npc_script.call("available",id):
			var npc: Node3D=npc_script.new()
			holder.add_child(npc)
			npc.call("setup",id,0.0)
			name_plate(holder,id)
			return npc
	else:
		var shadow_script := load("res://scripts/shadow_figure.gd") as GDScript
		if shadow_script and shadow_script.can_instantiate():
			var figure = shadow_script.call("create_still",id)
			if figure is Node3D:
				holder.add_child(figure)
				return figure
	var stand_in := Interiors.stand_in_figure(id)
	holder.add_child(stand_in)
	name_plate(holder,id)
	return stand_in

func name_plate(holder: Node3D, id: String) -> void:
	var plate := Art.label3d(holder,tr(Interiors.resident_title(id)),Vector3(0,2.1,0),Color("d4cdf2"))
	plate.font_size=28;plate.outline_size=4;plate.name="NamePlate"

## Puts a resident on their spot: lying in their bed, sitting on a seat, or
## standing in front of the piece they use, facing it.
func pose_resident(entry: Dictionary) -> void:
	var record: Dictionary=entry.record
	var occupant: Dictionary=entry.state
	var holder: Node3D=entry.holder
	var body: Node3D=entry.body
	var level := int(entry.floor)
	var f: Dictionary=building_spec.floors[level]
	var still := body.has_method("set_pose")
	holder.basis=Basis()
	var kind := str(record.get("kind",""))
	if occupant.get("asleep",false) and kind=="bed":
		entry.pose="lie"
		var size: Vector3=record.size
		var head := Vector3(0,0,-1).rotated(Vector3.UP,float(record.yaw))
		var top := minf(size.y*0.5,0.62)+0.02
		if still:
			holder.position=record.center+Vector3(0,top,0)
			body.face(atan2(head.x,head.z))
			body.set_pose("lie")
		else:
			holder.position=record.center-head*(size.z*0.5-0.2)+Vector3(0,top+0.12,0)
			holder.basis=Basis(head.cross(Vector3.UP),head,Vector3.UP)
		record["occupant"]=entry.id
		var zzz := Label3D.new();zzz.text="Z z z";zzz.font_size=34;zzz.pixel_size=0.005;zzz.outline_size=6
		zzz.billboard=BaseMaterial3D.BILLBOARD_ENABLED;zzz.modulate=Color("cfd8ff")
		holder.get_parent().add_child(zzz)
		zzz.position=record.center-head*(size.z*0.5-0.45)+Vector3(0,top+0.75,0)
		var bob := zzz.create_tween().set_loops()
		bob.tween_property(zzz,"position:y",zzz.position.y+0.18,1.2).set_trans(Tween.TRANS_SINE)
		bob.tween_property(zzz,"position:y",zzz.position.y,1.2).set_trans(Tween.TRANS_SINE)
		entry.zzz=zzz
		hide_plate(holder,body,true)
		return
	if kind in Interiors.SEATS and still:
		entry.pose="sit"
		var size: Vector3=record.size
		var height: float=size.y*0.5 if kind!="bench" else 0.47
		holder.position=record.center+Vector3(0,0,0.04).rotated(Vector3.UP,float(record.yaw))+Vector3(0,height+0.02,0)
		body.face(float(record.yaw))
		body.set_pose("sit")
		record["occupant"]=entry.id
		return
	entry.pose="stand"
	var others: Array=[]
	for other in npcs.values():
		if other!=entry and int(other.floor)==level and other.pose=="stand": others.append(other.holder.position)
	var at: Vector3=Interiors.stand_spot(record,f,decor_by_floor[level],others) if not record.is_empty() else Interiors.spawn_point(f)+Vector3(0.9,0,-0.6)
	holder.position=at
	var look: Vector3=(record.center if not record.is_empty() else at+Vector3(0,0,1))-at
	face_body(entry,atan2(look.x,look.z) if Vector2(look.x,look.z).length()>0.05 else 0.0)
	if still: body.set_pose("stand")
	var talk := {"kind":"resident","id":entry.id,"node":holder,"center":at,"yaw":0.0,"mounted":false,"solid":true,"interactive":true,"glb":false,
		"size":Vector3(0.6,1.75,0.6),"half":Vector2(0.28,0.28),"world_half":Vector2(0.28,0.28),"top":1.75,"floor":level,"room":Interiors.room_at(f,at.x)}
	decor_by_floor[level].append(talk)
	entry.talk=talk

func face_body(entry: Dictionary, yaw: float) -> void:
	var body: Node3D=entry.body
	if body.has_method("face"): body.face(yaw)
	elif body.get("turn_target")!=null:
		body.set("turn_target",yaw);body.rotation.y=yaw
	else: body.rotation.y=yaw

func hide_plate(holder: Node3D, body: Node3D, hidden: bool) -> void:
	var plate := holder.get_node_or_null("NamePlate") as Label3D
	if plate: plate.visible=not hidden
	var own = body.get("nameplate")
	if own is Label3D: own.visible=not hidden

func remove_resident(id: String, walk_out_door: bool) -> void:
	var entry: Dictionary=npcs.get(id,{})
	if entry.is_empty(): return
	npcs.erase(id)
	if talk_id==id: close_talk()
	var record: Dictionary=entry.record
	if str(record.get("occupant",""))==id: record.erase("occupant")
	if not entry.talk.is_empty(): decor_by_floor[int(entry.floor)].erase(entry.talk)
	if is_instance_valid(entry.zzz): entry.zzz.queue_free()
	var holder: Node3D=entry.holder
	if walk_out_door and int(entry.floor)==floor_index and entry.pose=="stand" and is_instance_valid(holder):
		var f: Dictionary=building_spec.floors[int(entry.floor)]
		var exit: Vector3
		if int(entry.floor)==0: exit=Vector3(float(f.get("door_x",0.0)),0,float(f.size.y)*0.5+0.3)
		else:
			exit=holder.position
			for other in decor_by_floor[int(entry.floor)]:
				if other.has("link") and int(other.link.to)<int(entry.floor): exit=other.center
		walk_to(entry,exit,func():
			var fade := holder.create_tween()
			fade.tween_property(holder,"scale",Vector3(0.9,0.05,0.9),0.35)
			fade.tween_callback(holder.queue_free))
	elif is_instance_valid(holder): holder.queue_free()

## Walks a standing resident in place along a straight line (they are props: no collision).
func walk_to(entry: Dictionary, target: Vector3, done: Callable) -> void:
	var holder: Node3D=entry.holder
	var body: Node3D=entry.body
	var from: Vector3=holder.position
	var offset := target-from
	offset.y=0
	if offset.length()<0.05:
		done.call();return
	face_body(entry,atan2(offset.x,offset.z))
	if body.has_method("play_clip"): body.play_clip("walk")
	var tween := holder.create_tween()
	tween.tween_property(holder,"position",target,offset.length()/1.1)
	tween.tween_callback(func():
		if body.has_method("play_clip"): body.play_clip("idle")
		if not entry.record.is_empty() and npcs.has(str(entry.id)):
			var look: Vector3=entry.record.center-holder.position
			face_body(entry,atan2(look.x,look.z))
		done.call())

## Small signs of life on the floor the walker is on: steam, notes, flour, stars.
func resident_cues() -> void:
	for entry in npcs.values():
		if int(entry.floor)!=floor_index or entry.state.get("asleep",false) or entry.record.is_empty(): continue
		var record: Dictionary=entry.record
		var size: Vector3=record.get("size",Vector3.ONE)
		var top := Vector3(record.center.x,record.node.global_position.y+size.y,record.center.z)
		match str(entry.state.activity):
			"cook": puff(top+Vector3(0,0.1,0),Color("f4f4f2",0.7),5,1.0,0.2,0.18)
			"barista": if randf()<0.5: puff(top+Vector3(0,0.1,0),Color("f4f4f2",0.6),4,0.8,0.2,0.14)
			"mill": puff(top,Color("f3ead6",0.7),5,0.5,0.4,0.12)
			"tend": puff(top+Vector3(0,0.3,0),Color("7fc4ec",0.85),6,-0.45,0.25,0.06)
			"piano": pop_over(entry,"♪")
			"stargaze": pop_over(entry,"✦")
			"read","tidy": if randf()<0.3: pop_over(entry,"…")

func pop_over(entry: Dictionary, text: String) -> void:
	var body: Node3D=entry.body
	if body.has_method("pop"):
		body.pop(text,1.6);return
	var label := Art.label3d(entry.holder,text,Vector3(0,2.0,0),Color("fff2c8"))
	label.font_size=40
	var tween := label.create_tween()
	tween.set_parallel(true)
	tween.tween_property(label,"position:y",2.5,1.4)
	tween.tween_property(label,"modulate:a",0.0,1.4)
	tween.set_parallel(false)
	tween.tween_callback(label.queue_free)

## E on a resident: sleepers only murmur; everyone else talks.
func talk_to(id: String, record: Dictionary) -> void:
	var entry: Dictionary=npcs[id]
	if is_instance_valid(hero): hero.face_point(entry.holder.global_position)
	if entry.state.get("asleep",false):
		say(tr("쿨쿨… 깊이 잠들었어요."),record)
		return
	open_talk(id)

## The village's RPG dialogue box: portrait, name plate, typed lines, choices.
func open_talk(id: String) -> void:
	close_talk()
	var entry: Dictionary=npcs[id]
	var c := resident_clock()
	var talk: Dictionary=Interiors.resident_talk(id,entry.state,building_spec,c.hour)
	talk_id=id;talk_lines=talk.lines;talk_choices=talk.choices;talk_page=0
	if entry.pose=="stand" and is_instance_valid(hero):
		var look: Vector3=hero.global_position-entry.holder.global_position
		face_body(entry,atan2(look.x,look.z))
	if entry.body.has_method("smile"): entry.body.smile(3.0)
	sfx_player.stream=Interiors.sfx("pop");sfx_player.play()
	talk_box=Control.new();talk_box.name="TalkBox";talk_box.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	talk_box.mouse_filter=Control.MOUSE_FILTER_IGNORE
	add_child(talk_box)
	# The same illustrated card + night box as the village (RpgUi.dialogue).
	talk_window=RpgUi.dialogue(talk_box,tr(Interiors.resident_title(id)),Interiors.portrait(id))
	talk_window.shade.gui_input.connect(func(event):
		if event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_LEFT: advance_talk())
	talk_body=talk_window.body
	# Kept for older callers; choices now live in talk_window.choices.
	talk_footer=HBoxContainer.new();talk_footer.visible=false;talk_box.add_child(talk_footer)
	for item in [name_panel,hint_chip,hint_label,bubble]:
		if is_instance_valid(item): item.visible=false
	show_talk_page()

func show_talk_page() -> void:
	if not is_instance_valid(talk_box): return
	talk_body.text=str(talk_lines[talk_page])
	talk_body.visible_ratio=0.0
	RpgUi.dialogue_line(talk_window,talk_body.text)
	var typing := talk_body.create_tween()
	typing.tween_property(talk_body,"visible_ratio",1.0,GameSettings.typing_seconds(talk_body.text.length()))
	if talk_page<talk_lines.size()-1:
		RpgUi.dialogue_more(talk_window,true)
	else:
		RpgUi.dialogue_more(talk_window,false)
		var entries := []
		for choice in talk_choices:
			var action := str(choice[1])
			entries.append([tr(str(choice[0])),func(): run_choice(action)])
		RpgUi.dialogue_choices(talk_window,entries)

func advance_talk() -> void:
	if not is_instance_valid(talk_box): return
	if talk_body.visible_ratio<1.0:
		talk_body.visible_ratio=1.0
	elif talk_page<talk_lines.size()-1:
		talk_page+=1
		sfx_player.stream=Interiors.sfx("click");sfx_player.play()
		show_talk_page()
	elif not talk_choices.is_empty():
		run_choice(str(talk_choices[0][1]))

func close_talk() -> void:
	if is_instance_valid(talk_box): talk_box.queue_free()
	talk_box=null
	talk_window={}
	talk_id=""
	if is_instance_valid(hint_chip): hint_chip.visible=true

## What a dialogue choice does: small gifts and tips, or the telescope at night.
func run_choice(action: String) -> void:
	var id := talk_id
	close_talk()
	var head: Vector3=hero.global_position+Vector3(0,1.6,0) if is_instance_valid(hero) else Vector3.ZERO
	match action:
		"coffee":
			message(tr("따뜻한 코코아를 받았어요. 달콤해요!"))
			sfx_player.stream=Interiors.sfx("clink");sfx_player.play()
			puff(head,Color("f4f4f2",0.7),5,0.8,0.15,0.12)
		"seed_tip":
			message(tr("추천: 별사탕 씨앗은 햇살 좋은 밭에서 잘 자라요."))
			sfx_player.stream=Interiors.sfx("ding");sfx_player.play()
		"shop_tip":
			message(tr("오늘의 추천은 반짝이는 낚싯바늘이에요."))
			sfx_player.stream=Interiors.sfx("ding");sfx_player.play()
		"flour":
			message(tr("밀가루 한 줌을 받았어요. 고소한 냄새가 나요."))
			puff(head-Vector3(0,0.6,0),Color("f3ead6",0.8),8,0.5,0.3,0.12)
		"flower":
			message(tr("들꽃 한 송이를 받았어요. 향기가 좋아요."))
			sfx_player.stream=Interiors.sfx("chime");sfx_player.play()
		"fish_tip":
			message(tr("물때가 바뀔 때 찌를 던져 보세요. 꼭 낚일 거예요!"))
		"telescope":
			for record in decor:
				if record.kind=="telescope" and not record.has("occupant"):
					use_decor(record);return
			message(tr("별자리가 보여요. 오늘은 고래자리가 또렷해요!"))
	if npcs.has(id) and npcs[id].body.has_method("smile"): npcs[id].body.smile(2.0)

## Name plates show only for residents close to the walker, like in the village.
func update_name_plates() -> void:
	if npcs.is_empty() or not is_instance_valid(hero): return
	for entry in npcs.values():
		if int(entry.floor)!=floor_index: continue
		var near: bool=entry.holder.global_position.distance_to(hero.global_position)<3.2 and entry.pose!="lie"
		hide_plate(entry.holder,entry.body,not near)
