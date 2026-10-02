extends Node3D

const Art = preload("res://scripts/art.gd")
const Loader = preload("res://scripts/model_loader.gd")
const Player = preload("res://scripts/player.gd")
const Api = preload("res://scripts/api.gd")
const Sound = preload("res://scripts/sound.gd")
const Landscape = preload("res://scripts/world_detail.gd")
const TownLayout = preload("res://scripts/town.gd")
# Trading is deferred while the village / survival / generation loop is developed.
const TRADING_UI_ENABLED := false
const ITEM_NAMES := {"wood":"목재","stone":"돌","berry":"열매","fiber":"섬유","axe":"도끼","spear":"창","soup":"수프","bandage":"붕대"}
const COLORS := ["#f6eee0","#edbc63","#d98477","#70afa3","#7c9ec6"]
const RECIPES := {"axe":{"wood":3,"stone":2},"spear":{"wood":4,"stone":2},"soup":{"berry":3,"wood":1},"bandage":{"fiber":3}}
var api: Node
var furniture_proximity_time := 0.0
var furniture_event_pending := false
var sound: Node
var world: Node3D
var player: CharacterBody3D
var camera: Camera3D
var environment: Environment
var sun: DirectionalLight3D
var ui: Control
var left: VBoxContainer
var right: VBoxContainer
var notice: Label
var wallet: Label
var metrics: Label
var pack: Label
var objects_list: ItemList
var object_info: Label
var prompt: LineEdit
var price: SpinBox
var screen := "login"
var me: Dictionary = {}
var selected: Dictionary = {}
var run: Dictionary = {}
var run_id := ""
var job_id := ""
var loaded: Dictionary = {}
var nodes: Dictionary = {}
var enemy_nodes: Dictionary = {}
var object_root: Node3D
var preview: Node3D
var preview_rotation := 0
var flame: Node3D
var busy := false
var ticking := false
var tick_elapsed := 0.0
var poll_elapsed := 0.0
var entitlement_elapsed := 0.0
var polling_entitlements := false
var refreshing := false
var polling_job := false
var reward_button: Button
var hint: Label
var hp_bar: ProgressBar
var hunger_bar: ProgressBar
var hp_readout: Label
var hunger_readout: Label
var pending_action := ""
var pending_target := ""
var network_failures := 0
var world_epoch := 0
var craft_buttons: Dictionary = {}
var harvest_marker: MeshInstance3D
var objective: Label
var day_track: Label
var toast_panel: PanelContainer
var toast_time := 0.0
var last_notice := ""
var ambience: CPUParticles3D
var results_shown := false
var prior_day := 1
var prior_night := false
var inspect_panel: PanelContainer
var inspect_view: SubViewport
var inspect_stage: Node3D
var inspect_model: Node3D
var inspect_request := 0
var stamina_bar: ProgressBar
var stamina_readout: Label
var supplies: Label
var camp_status: Label
var field_map: Control
var warmth_ring: MeshInstance3D
var strike_markers: Dictionary = {}
var repeat_action := 0.0
var return_dialog: ConfirmationDialog
var last_camp_warning := -100.0
var canopy_elapsed := 0.0
var paused := false
var pause_shade: Control
var inventory_slots: Dictionary = {}
var quick_counts: Dictionary = {}
var expedition_button: Button
var village_modal: Control
var npcs: Array[Node3D]=[]
var chosen_map := "forest"
var chosen_difficulty := "standard"
var town: Node3D
var life: Node

func _ready() -> void:
	api = Api.new()
	add_child(api)
	sound = Sound.new()
	add_child(sound)
	life=preload("res://scripts/village_life.gd").new()
	life.app=self
	add_child(life)
	for action in {"move_left":KEY_A,"move_right":KEY_D,"move_forward":KEY_W,"move_back":KEY_S}:
		if not InputMap.has_action(action): InputMap.add_action(action)
		var event := InputEventKey.new()
		event.physical_keycode = {"move_left":KEY_A,"move_right":KEY_D,"move_forward":KEY_W,"move_back":KEY_S}[action]
		InputMap.action_add_event(action,event)
	var e := WorldEnvironment.new()
	environment = Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("b7ccd1")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color.WHITE
	environment.ambient_light_energy = 0.35
	environment.tonemap_mode=Environment.TONE_MAPPER_LINEAR
	e.environment = environment
	add_child(e)
	sun = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48,-32,0)
	sun.light_color=Color("fff5e9")
	sun.light_energy = 0.25
	sun.shadow_enabled = true
	add_child(sun)
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 16
	camera.current = true
	add_child(camera)
	var layer := CanvasLayer.new()
	add_child(layer)
	ui = Control.new()
	ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.theme = make_theme()
	layer.add_child(ui)
	build_world(false)
	if Engine.has_meta("studio_session"):
		var session: Dictionary=Engine.get_meta("studio_session")
		Engine.remove_meta("studio_session")
		api.token=session.token;api.base_url=session.url
		await enter_village()
		player.position=TownLayout.HOME_RETURN if session.get("room")=="home" else Vector3(-5,0.1,-2.6)
		follow_camera(1)
	else: login_ui()

func make_theme() -> Theme:
	var theme := Theme.new()
	var font := SystemFont.new()
	font.font_names = PackedStringArray(["Malgun Gothic","sans-serif"])
	theme.default_font = font
	theme.default_font_size = 15
	for type in ["Label","Button","LineEdit","ItemList","SpinBox"]:
		theme.set_color("font_color",type,Color("f5f0df"))
	theme.set_color("font_hover_color","Button",Color("fff8e6"))
	theme.set_color("font_pressed_color","Button",Color("152b2d"))
	theme.set_color("font_disabled_color","Button",Color("8d9c94"))
	theme.set_color("font_selected_color","ItemList",Color("fff5d9"))
	var selected_item := StyleBoxFlat.new()
	selected_item.bg_color=Color("3c665e")
	selected_item.set_corner_radius_all(7)
	selected_item.set_border_width_all(1)
	selected_item.border_color=Color("ddc486",0.72)
	theme.set_stylebox("selected","ItemList",selected_item)
	theme.set_stylebox("selected_focus","ItemList",selected_item)
	for type in ["Button","LineEdit","ItemList"]:
		for kind in ["normal","hover","pressed","focus","disabled"]:
			var style := StyleBoxFlat.new()
			style.bg_color = Color("365d58") if kind=="hover" else Color("193538") if kind=="pressed" else Color("263e40") if kind=="normal" else Color("203438")
			style.set_corner_radius_all(10)
			style.set_border_width_all(1)
			style.border_color=Color("72917f",0.4)
			style.content_margin_left = 12
			style.content_margin_right = 12
			style.content_margin_top = 9
			style.content_margin_bottom = 9
			if kind=="focus":
				style.set_border_width_all(2)
				style.border_color = Color("e5c477")
			theme.set_stylebox(kind,type,style)
	return theme

func clear_ui() -> void:
	craft_buttons.clear()
	inventory_slots.clear()
	quick_counts.clear()
	paused=false
	if is_instance_valid(return_dialog): return_dialog.queue_free()
	inspect_request+=1
	for child in ui.get_children():
		ui.remove_child(child)
		child.queue_free()

func panel(at: Vector2, width: float, variant := "default") -> VBoxContainer:
	var p := PanelContainer.new()
	p.position = at
	p.custom_minimum_size.x = width
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.06,0.12,0.13,0.94) if variant=="hero" else Color(0.075,0.14,0.15,0.93)
	style.set_corner_radius_all(16)
	style.set_border_width_all(1)
	style.border_width_top=2 if variant in ["hero","objective","toolbar"] else 1
	style.border_color=Color("d8b873",0.68) if variant in ["hero","objective"] else Color("89af9a",0.48)
	style.shadow_color=Color(0.01,0.06,0.07,0.34)
	style.shadow_size=12
	style.shadow_offset=Vector2(0,5)
	style.content_margin_left = 19
	style.content_margin_right = 19
	style.content_margin_top = 17
	style.content_margin_bottom = 17
	p.add_theme_stylebox_override("panel",style)
	ui.add_child(p)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation",8)
	p.add_child(v)
	return v

func text(parent: Node, value: String, size := 15) -> Label:
	var l := Label.new()
	l.text = value
	l.add_theme_font_size_override("font_size",size)
	parent.add_child(l)
	return l

func rule(parent: Node) -> void:
	var line := ColorRect.new()
	line.color=Color("c7ac72",0.36)
	line.custom_minimum_size.y=1
	line.mouse_filter=Control.MOUSE_FILTER_IGNORE
	parent.add_child(line)

func button(parent: Node, value: String, callback: Callable, variant := "default") -> Button:
	var b := Button.new()
	b.text = value
	b.custom_minimum_size.y = 43 if variant in ["primary","slot"] else 38
	b.focus_mode = Control.FOCUS_NONE
	if variant in ["primary","slot"]:
		for kind in ["normal","hover","pressed"]:
			var style := StyleBoxFlat.new()
			style.set_corner_radius_all(10)
			style.set_border_width_all(1)
			style.content_margin_left=12
			style.content_margin_right=12
			style.content_margin_top=9
			style.content_margin_bottom=9
			if variant=="primary":
				style.bg_color=Color("f3d992") if kind=="hover" else Color("af894c") if kind=="pressed" else Color("d3b474")
				style.border_color=Color("f5e3ae")
			else:
				style.bg_color=Color("37625c") if kind=="hover" else Color("152e32") if kind=="pressed" else Color("234447")
				style.border_color=Color("88a995",0.58)
			b.add_theme_stylebox_override(kind,style)
		b.add_theme_color_override("font_color",Color("23342d") if variant=="primary" else Color("f2ead7"))
		b.add_theme_color_override("font_hover_color",Color("23342d") if variant=="primary" else Color("fff8e6"))
	b.pressed.connect(func():
		sound.effect("click")
		callback.call())
	parent.add_child(b)
	return b

func message(value: String) -> void:
	if is_instance_valid(notice): notice.text = value
	if is_instance_valid(toast_panel) and value!=last_notice and not value.is_empty():
		last_notice=value
		toast_time=4.5
		toast_panel.visible=true

func error_message(code: String) -> String:
	var messages := {"connection_failed":"서버 연결이 끊겼습니다. 서버를 실행한 뒤 다시 접속하세요.",
		"server_update_required":"이전 서버가 실행 중입니다. 서버를 종료한 뒤 새 실행본으로 다시 시작하세요.",
		"invalid_credentials":"아이디 또는 비밀번호를 확인하세요.","username_unavailable":"이미 사용 중인 이름입니다.",
		"invalid_request":"입력 형식을 확인하세요. 이름 3~24자, 비밀번호 10자 이상입니다.",
		"insufficient_shards":"별씨가 부족합니다. 생존 도전을 완료해 보세요.","placement_overlap":"다른 물건과 겹칩니다.",
		"room_render_budget_exceeded":"꾸미기 용량이 꽉 찼습니다. 가구 일부를 회수한 뒤 배치해 주세요.",
		"spawn_area_reserved":"중앙 광장에는 놓을 수 없습니다.","house_area_reserved":"집 주변의 공간을 비워 주세요.",
		"gate_area_reserved":"숲 입구에는 놓을 수 없습니다.","daily_generation_limit":"오늘 생성 한도에 도달했습니다.",
		"live_generation_disabled":"Tripo 실생성이 아직 설정되지 않았습니다.","generation_pending":"진행 중인 생성이 있습니다.",
		"session_expired":"로그인이 만료됐습니다. 다시 접속하세요.","object_not_found":"이 물건을 사용할 권한이 없습니다.",
		"stale_object_version":"물건 상태가 바뀌었습니다. 목록을 새로고침하세요.","object_is_listed":"판매 중인 물건입니다. 판매를 취소하세요.",
		"insufficient_provider_credit":"Tripo 크레딧이 부족합니다. 별씨는 환불됩니다."}
	return str(messages.get(code,"요청을 완료하지 못했습니다: "+code))

func check(result: Dictionary) -> bool:
	if not result.ok:
		message(error_message(result.error))
		return false
	return true

func login_ui() -> void:
	screen = "login"
	clear_ui()
	left = panel(Vector2(48,154),370,"hero")
	text(left,"✦  TRIPOTHON  /  SEVEN NIGHTS",12).modulate = Color("e4c989")
	text(left,"일곱 밤, 나의 마을",30)
	text(left,"돌아올 마을이 있어, 숲으로 떠납니다.",14)
	rule(left)
	var host := LineEdit.new()
	host.text = api.base_url
	text(left,"탐험가 이름",13)
	var username := LineEdit.new()
	username.placeholder_text = "영문·숫자·밑줄 3~24자"
	left.add_child(username)
	var password := LineEdit.new()
	password.placeholder_text = "비밀번호 · 10자 이상"
	password.secret = true
	left.add_child(password)
	var invitation := LineEdit.new()
	invitation.placeholder_text = "초대 코드 · 로컬 샘플 서버는 불필요"
	invitation.secret = true
	button(left,"마을에 들어가기  →",func(): authenticate(false,host.text,username.text,password.text,invitation.text),"primary")
	button(left,"새 탐험가 만들기",func(): authenticate(true,host.text,username.text,password.text,invitation.text))
	var advanced := VBoxContainer.new()
	button(left,"연결 설정",func(): advanced.visible=not advanced.visible)
	left.add_child(advanced)
	text(advanced,"서버 주소 · 외부 서버는 HTTPS",12)
	advanced.add_child(host)
	advanced.add_child(invitation)
	advanced.visible=false
	notice = text(left,"로컬 샘플 모드에서는 API 비용이 발생하지 않습니다.",13)
	notice.custom_minimum_size.x = 320
	notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text(left,"숲에서 생존하고 · 별씨를 모으고\n나만의 물건으로 마을을 채워 보세요.",13)
	player.controls_enabled = false
	var portrait_panel := panel(Vector2(986,225),246,"hero")
	text(portrait_panel,"당신의 첫 번째 탐험",17)
	var portrait := TextureRect.new()
	portrait.texture=load("res://assets/explorer_b_portrait.png")
	portrait.expand_mode=TextureRect.EXPAND_IGNORE_SIZE
	portrait.stretch_mode=TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	portrait.custom_minimum_size=Vector2(210,250)
	portrait_panel.add_child(portrait)
	text(portrait_panel,"WASD  산책하기\nE  상호작용    I  보관함",12)
	password.text_submitted.connect(func(_value): authenticate(false,host.text,username.text,password.text,invitation.text))

func authenticate(register: bool, host: String, username: String, password: String, invitation: String) -> void:
	if busy: return
	host = host.strip_edges().trim_suffix("/")
	var local_pattern := RegEx.new()
	local_pattern.compile("^http://(127\\.0\\.0\\.1|localhost):[0-9]{1,5}$")
	if not (host.begins_with("https://") or local_pattern.search(host)!=null):
		message("원격 서버는 HTTPS 주소를 사용하세요.")
		return
	busy = true
	api.base_url = host
	api.token = ""
	message("서버에 접속 중…")
	var health: Dictionary=await api.request("/health")
	if not check(health):
		busy=false
		return
	if health.data.get("service","")!="tripothon" or int(health.data.get("protocol",0))!=6:
		busy=false
		message(error_message("server_update_required"))
		return
	var result: Dictionary = await api.post("/v1/auth/"+("register" if register else "login"),{"username":username,"password":password,"invitation":invitation})
	busy = false
	if not check(result): return
	api.token = result.data.token
	api.mode = result.data.mode
	await enter_village()

func build_world(survival: bool) -> void:
	world_epoch += 1
	paused=false
	results_shown=false
	prior_day=1
	prior_night=false
	sound.play_music("forest" if survival else "village")
	if is_instance_valid(world):
		remove_child(world)
		world.queue_free()
	preview = null
	loaded.clear()
	nodes.clear()
	enemy_nodes.clear()
	strike_markers.clear()
	pending_action=""
	pending_target=""
	tick_elapsed=0
	last_camp_warning=-100
	world = Node3D.new()
	add_child(world)
	npcs.clear()
	close_village_modal()
	town=null
	if survival: preload("res://scripts/biomes.gd").build(world,run)
	else:
		town=preload("res://scripts/town.gd").new()
		for chapter in me.get("campaign",[]):
			if chapter.completed:town.story_progress+=1
		world.add_child(town)
	object_root = Node3D.new()
	world.add_child(object_root)
	player = Player.new()
	world.add_child(player)
	player.apply_avatar(me.get("profile",{}).get("avatar",{}))
	if not survival: spawn_villagers()
	player.position = Vector3(0,0.1,3) if not survival else Vector3(run.get("x",0),0.1,run.get("z",1.4))
	flame = Node3D.new()
	world.add_child(flame)
	for index in 3:
		var tongue := MeshInstance3D.new();var quad := QuadMesh.new();quad.size=Vector2(.72,.72)
		tongue.mesh=quad;tongue.position.y=.47;tongue.rotation.y=index*PI/3
		tongue.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var fire_material := ShaderMaterial.new();fire_material.shader=preload("res://shaders/camp_flame.gdshader")
		fire_material.set_shader_parameter("phase",float(index)*1.8);tongue.material_override=fire_material;flame.add_child(tongue)
	flame.visible = false
	harvest_marker = MeshInstance3D.new()
	var ring := TorusMesh.new()
	ring.inner_radius=0.7
	ring.outer_radius=0.77
	ring.rings=24
	ring.ring_segments=8
	harvest_marker.mesh=ring
	var marker_material := Art.material(Color("f2d38c"))
	marker_material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	harvest_marker.material_override=marker_material
	harvest_marker.visible=false
	world.add_child(harvest_marker)
	warmth_ring=MeshInstance3D.new()
	var warm_mesh := TorusMesh.new()
	warm_mesh.inner_radius=3.94
	warm_mesh.outer_radius=4.0
	warm_mesh.rings=64
	warm_mesh.ring_segments=6
	warmth_ring.mesh=warm_mesh
	warmth_ring.position.y=0.035
	var warm_mat := Art.material(Color(0.92,0.73,0.38,0.4))
	warm_mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	warm_mat.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	warmth_ring.material_override=warm_mat
	warmth_ring.visible=false
	world.add_child(warmth_ring)
	var light := OmniLight3D.new()
	light.position.y = 1
	light.light_color = Color("ffb16b")
	light.light_energy = 1.5
	light.omni_range = 7
	flame.add_child(light)
	var sparks := CPUParticles3D.new()
	sparks.amount=22
	sparks.lifetime=1.1
	sparks.position.y=0.3
	sparks.direction=Vector3.UP
	sparks.spread=25
	sparks.initial_velocity_min=0.6
	sparks.initial_velocity_max=1.3
	sparks.gravity=Vector3(0,0.35,0)
	sparks.scale_amount_min=0.035
	sparks.scale_amount_max=0.075
	var spark_mesh := SphereMesh.new()
	spark_mesh.radius=0.5
	spark_mesh.height=1
	sparks.mesh=spark_mesh
	var spark_mat := Art.material(Color("ffd68c"))
	spark_mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	sparks.material_override=spark_mat
	flame.add_child(sparks)
	ambience=CPUParticles3D.new()
	ambience.amount=45
	ambience.lifetime=8
	ambience.emission_shape=CPUParticles3D.EMISSION_SHAPE_BOX
	ambience.emission_box_extents=Vector3(12,1.7,12)
	ambience.position.y=1.6
	ambience.direction=Vector3(1,0.2,0.3)
	ambience.initial_velocity_min=0.12
	ambience.initial_velocity_max=0.3
	ambience.gravity=Vector3.ZERO
	ambience.scale_amount_min=0.018
	ambience.scale_amount_max=0.035
	ambience.mesh=spark_mesh
	ambience.material_override=spark_mat
	world.add_child(ambience)
	environment.ambient_light_energy = 0.35
	environment.ambient_light_color=Color.WHITE
	environment.background_color = Color("88bcb9")
	sun.light_energy = 0.25
	sun.light_color=Color("fff5e9")
	camera.size = 16
	follow_camera(1)

func enter_village() -> void:
	screen = "loading"
	build_world(false)
	clear_ui()
	left = panel(Vector2(24,24),250,"hero")
	text(left,"✦  STARSEED  /  HOME",11).modulate = Color("e4c989")
	text(left,"물결빛 마을",24)
	rule(left)
	var wallet_row := HBoxContainer.new()
	left.add_child(wallet_row)
	var seed_icon := TextureRect.new()
	seed_icon.texture=load("res://assets/starseed.svg")
	seed_icon.custom_minimum_size=Vector2(36,36)
	seed_icon.expand_mode=TextureRect.EXPAND_IGNORE_SIZE
	seed_icon.stretch_mode=TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	wallet_row.add_child(seed_icon)
	wallet = text(wallet_row,"서버 연결 중…",13)
	reward_button=button(left,"받지 않은 생존 보상 받기",claim_pending_reward)
	reward_button.visible=false
	right = panel(Vector2(954,24),302,"hero")
	var drawer_title := HBoxContainer.new()
	right.add_child(drawer_title)
	text(drawer_title,"나의 보관함",22).size_flags_horizontal=Control.SIZE_EXPAND_FILL
	button(drawer_title,"×",toggle_drawer)
	objects_list = ItemList.new()
	objects_list.custom_minimum_size = Vector2(252,155)
	objects_list.item_selected.connect(select_object)
	right.add_child(objects_list)
	object_info = text(right,"물건을 선택하세요.",13)
	object_info.custom_minimum_size.x = 250
	object_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var palette := HBoxContainer.new()
	right.add_child(palette)
	for color in COLORS:
		var b := button(palette,"●",func(): paint_object(color))
		b.modulate = Color(color)
	button(right,"선택한 물건 놓기",begin_place)
	button(right,"선택한 물건 회수",retrieve_object)
	button(right,"선택한 가구 사용",func():await village_furniture_event(selected.get("id",""),"click"))
	if TRADING_UI_ENABLED:
		var sell_row := HBoxContainer.new()
		right.add_child(sell_row)
		price = SpinBox.new()
		price.min_value = 1
		price.max_value = 10000
		price.value = 25
		price.custom_minimum_size.x = 115
		sell_row.add_child(price)
		button(sell_row,"별씨로 판매",sell_object)
	text(right,"상상 공방",21)
	button(right,"공방 안으로 들어가기",open_studio)
	prompt = LineEdit.new()
	prompt.placeholder_text = "예: 둥근 버섯 모양 의자"
	prompt.max_length = 500
	right.add_child(prompt)
	prompt.visible=false # Retained for legacy integration/recovery, outside the player flow.
	text(right,"공방에서 새 가구를 만들고\n색칠·부품 맞춤을 할 수 있어요.",12)
	var utilities := HBoxContainer.new()
	right.add_child(utilities)
	button(utilities,"새로고침",refresh_inventory)
	button(utilities,"로그아웃",logout)
	right.get_parent().visible=false
	build_play_hud(false)
	build_inspector()
	await refresh_inventory()
	screen = "village"
	await life.enter()
	player.controls_enabled = true
	world_hint("Tab · 마을 지도   B · 생활 창고   E · 가까운 곳과 상호작용")
	message("넓어진 물결빛 마을에 오신 것을 환영해요. Tab으로 텃밭과 낚시터를 찾아보세요.")

func toggle_drawer() -> void:
	if not is_instance_valid(right): return
	var opening: bool=not right.get_parent().visible
	right.get_parent().visible=opening
	if is_instance_valid(objective): objective.get_parent().get_parent().visible=not opening
	if is_instance_valid(inspect_panel): inspect_panel.visible=opening
	if is_instance_valid(inspect_view): inspect_view.render_target_update_mode=SubViewport.UPDATE_ALWAYS if opening else SubViewport.UPDATE_DISABLED

func build_inspector() -> void:
	var card := panel(Vector2(24,220),250)
	inspect_panel=card.get_parent()
	inspect_panel.visible=false
	text(card,"물건 미리 보기",15)
	inspect_view=SubViewport.new()
	inspect_view.size=Vector2i(320,280)
	inspect_view.transparent_bg=true
	inspect_view.own_world_3d=true
	inspect_view.render_target_update_mode=SubViewport.UPDATE_DISABLED
	inspect_panel.add_child(inspect_view)
	inspect_stage=Node3D.new()
	inspect_view.add_child(inspect_stage)
	var preview_camera := Camera3D.new()
	preview_camera.projection=Camera3D.PROJECTION_ORTHOGONAL
	preview_camera.size=2.7
	inspect_stage.add_child(preview_camera)
	preview_camera.position=Vector3(2,1.75,3)
	preview_camera.look_at(Vector3(0,0.65,0))
	var preview_light := DirectionalLight3D.new()
	preview_light.rotation_degrees=Vector3(-45,-30,0)
	preview_light.light_energy=0.4
	inspect_stage.add_child(preview_light)
	var env := WorldEnvironment.new()
	env.environment=Environment.new()
	env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color=Color.WHITE
	env.environment.ambient_light_energy=0.5
	inspect_stage.add_child(env)
	var view := TextureRect.new()
	view.texture=inspect_view.get_texture()
	view.custom_minimum_size=Vector2(210,185)
	view.expand_mode=TextureRect.EXPAND_IGNORE_SIZE
	view.stretch_mode=TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	view.mouse_filter=Control.MOUSE_FILTER_IGNORE
	card.add_child(view)
	text(card,"팔레트로 전체 색을 바꿔 보세요.\nR · 배치 방향 회전",12).modulate=Color("bfccba")

func inspect_object(obj: Dictionary) -> void:
	if not is_instance_valid(inspect_stage): return
	inspect_request+=1
	var request := inspect_request
	if is_instance_valid(inspect_model):
		inspect_model.queue_free()
		inspect_model=null
	var model := await load_object(obj)
	if request!=inspect_request or not is_instance_valid(inspect_stage) or selected.get("id","")!=obj.id:
		if model: model.queue_free()
		return
	if model:
		inspect_model=model
		if not model.get_meta("studio",false):Loader.paint(model,Color(selected.color))
		inspect_stage.add_child(model)

func build_play_hud(survival: bool) -> void:
	var task_card := panel(Vector2(962,24),294,"objective")
	text(task_card,"✦  오늘의 탐험 목표" if survival else "✦  오늘의 마을 이야기",11).modulate=Color("e4c989")
	rule(task_card)
	objective=text(task_card,"",14)
	objective.custom_minimum_size.x=254
	objective.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	var toolbar := panel(Vector2(310,668 if survival else 704),660,"toolbar")
	if survival:
		var quick_row := HBoxContainer.new();quick_row.alignment=BoxContainer.ALIGNMENT_CENTER
		quick_row.add_theme_constant_override("separation",16);toolbar.add_child(quick_row)
		for item in ["wood","stone","berry","fiber"]:
			var icon := TextureRect.new();icon.texture=load("res://assets/items/"+item+".svg")
			icon.custom_minimum_size=Vector2(24,24);icon.expand_mode=TextureRect.EXPAND_IGNORE_SIZE
			icon.stretch_mode=TextureRect.STRETCH_KEEP_ASPECT_CENTERED;icon.tooltip_text=ITEM_NAMES[item];quick_row.add_child(icon)
			quick_counts[item]=text(quick_row,"0",15)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation",8)
	toolbar.add_child(row)
	button(row,"[ I ]  가방 · 제작" if survival else "[ I ]  보관함",toggle_drawer,"slot")
	if survival:
		button(row,"[ Q ]  먹기",func(): intent("eat"),"slot")
		button(row,"[ F ]  불 지키기",func(): intent("fire"),"slot")
		button(row,"[ H ]  붕대",func(): intent("heal"),"slot")
		button(row,"귀환",confirm_return,"slot")
	else:
		if TRADING_UI_ENABLED: button(row,"별씨 장터",show_market)
		expedition_button=button(row,"탐험 지도  →",open_expedition,"primary")
		button(row,"옷장",open_wardrobe,"slot")
		button(row,"[ Tab ]  지도",life.open_map,"slot")
		button(row,"[ B ]  창고",life.open_storage,"slot")
	for child in row.get_children(): child.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	var toast := panel(Vector2(365,586 if survival else 620),550,"objective")
	toast_panel=toast.get_parent()
	toast_panel.mouse_filter=Control.MOUSE_FILTER_IGNORE
	notice=text(toast,"",14)
	notice.custom_minimum_size.x=510
	notice.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	toast_panel.visible=false
	last_notice=""
	if survival:
		var tracker := panel(Vector2(460,24),360,"hero")
		day_track=text(tracker,"",16)
		day_track.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER

func world_hint(value: String) -> void:
	hint=Label.new()
	hint.text=value
	hint.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	hint.position=Vector2(320,640 if screen=="survival" else 670)
	hint.size=Vector2(640,35)
	hint.add_theme_font_size_override("font_size",15)
	hint.add_theme_color_override("font_outline_color",Color("17282c"))
	hint.add_theme_constant_override("outline_size",5)
	hint.mouse_filter=Control.MOUSE_FILTER_IGNORE
	ui.add_child(hint)

func meter(parent: Node, color: Color) -> ProgressBar:
	var bar := ProgressBar.new()
	bar.custom_minimum_size.y=9
	bar.show_percentage=false
	var fill := StyleBoxFlat.new()
	fill.bg_color=color
	fill.set_corner_radius_all(5)
	var bg := StyleBoxFlat.new()
	bg.bg_color=Color("304449")
	bg.set_corner_radius_all(5)
	bar.add_theme_stylebox_override("fill",fill)
	bar.add_theme_stylebox_override("background",bg)
	parent.add_child(bar)
	return bar

func status_meter(parent: Node, title: String, color: Color) -> Dictionary:
	var header := HBoxContainer.new()
	parent.add_child(header)
	var name_label := text(header,title,12)
	name_label.modulate=Color("c2d3c3")
	name_label.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	var value_label := text(header,"100 / 100",12)
	value_label.modulate=Color("f7edce")
	var bar := meter(parent,color)
	return {"bar":bar,"readout":value_label}

func refresh_inventory() -> void:
	var requested_epoch := world_epoch
	while refreshing:
		await get_tree().process_frame
		if requested_epoch!=world_epoch: return
	refreshing=true
	var epoch := world_epoch
	var old_selection: String = selected.get("id","")
	var result: Dictionary = await api.request("/v1/me")
	if epoch!=world_epoch or not check(result):
		refreshing=false
		return
	me = result.data
	if screen=="village" and is_instance_valid(player): player.apply_avatar(me.get("profile",{}).get("avatar",{}))
	reward_button.visible=me.get("pending_reward")!=null
	if is_instance_valid(expedition_button):
		var saved = me.get("active_run_summary")
		expedition_button.text=("탐험 이어하기 · %d일" % saved.day) if saved is Dictionary else "탐험 지도 →"
	if me.get("pending_job")!=null and job_id.is_empty(): job_id=me.pending_job
	wallet.text = "%s  ·  별씨 %d\n%s" % [me.username,me.shards,"Tripo 연결 · 공방에서 이용" if me.get("studio_tripo_enabled",false) else ("샘플 서버 · 실제 API 비용 없음" if me.mode=="demo" else "Tripo 서버 연결")]
	objects_list.clear()
	selected = {}
	for obj in me.objects:
		var state_name: String = {"inventory":"보관","placed":"배치","listed":"판매"}[obj.state]
		objects_list.add_item("[%s] %s" % [state_name,obj.name])
	for node in object_root.get_children():
		object_root.remove_child(node)
		node.queue_free()
	loaded.clear()
	for obj in me.objects:
		if obj.state=="placed" and obj.get("room","village")=="village":
			var asset = await load_object(obj)
			if epoch!=world_epoch:
				if is_instance_valid(asset): asset.queue_free()
				refreshing=false
				return
			if asset:
				object_root.add_child(asset)
				asset.position = Vector3(obj.x,0,obj.z)
				asset.rotation_degrees.y = obj.rotation
				Loader.add_collision(asset)
				loaded[obj.id] = asset
	if objects_list.item_count>0:
		var index := 0
		for i in me.objects.size():
			if me.objects[i].id==old_selection: index=i
		objects_list.select(index)
		select_object(index)
	refreshing=false

func claim_pending_reward() -> void:
	if busy or me.get("pending_reward")==null: return
	busy=true
	var result: Dictionary = await api.post("/v1/runs/"+me.pending_reward.id+"/claim",api.mutation())
	busy=false
	if check(result):
		await refresh_inventory()
		message("생존 보상 %d 별씨를 받았습니다." % result.data.reward)

func poll_entitlements() -> void:
	if polling_entitlements or busy or refreshing: return
	polling_entitlements=true
	var epoch := world_epoch
	var result: Dictionary = await api.request("/v1/me")
	polling_entitlements=false
	if epoch!=world_epoch: return
	if not result.ok:
		# Fail closed on auth loss or disconnection; don't retain protected models.
		cancel_preview()
		api.token=""
		build_world(false)
		login_ui()
		message(error_message(result.error))
		return
	if JSON.stringify(result.data.objects)!=JSON.stringify(me.objects) or result.data.shards!=me.shards:
		cancel_preview()
		await refresh_inventory()

func select_object(index: int) -> void:
	if is_instance_valid(preview): cancel_preview()
	selected = me.objects[index]
	var state_name: String={"inventory":"보관 중","placed":"마을에 배치됨","listed":"장터에서 판매 중"}[selected.state]
	object_info.text = "%s\n%s" % [selected.name,state_name]
	inspect_object(selected.duplicate())

func load_object(obj: Dictionary) -> Node3D:
	var assembly: Node3D=await preload("res://scripts/asset_assembly.gd").fetch(api,obj.id)
	if assembly: return assembly
	if obj.get("studio",false):message("가구의 모든 부품을 불러오지 못했습니다.");return null
	var response: Dictionary = await api.request("/v1/objects/"+obj.id+"/model",{},HTTPClient.METHOD_GET,true)
	if not check(response): return null
	var model := Loader.load_bytes(response.bytes)
	if model: Loader.paint(model,Color(obj.color))
	else: message("모델을 읽을 수 없습니다.")
	return model

func edit_object(extra: Dictionary) -> bool:
	if selected.is_empty() or busy: return false
	busy = true
	var id: String = selected.id
	var response: Dictionary = await api.post("/v1/objects/"+id,api.mutation(extra.merged({"version":selected.version})))
	busy = false
	if not check(response): return false
	selected = response.data
	return true

func paint_object(color: String) -> void:
	if selected.get("studio",false):
		if busy or not is_instance_valid(inspect_model):return
		busy=true
		var reply: Dictionary=await api.post("/v1/objects/"+selected.id+"/colors",api.mutation({"version":inspect_model.runtime_version,"part":"all","color":color}))
		busy=false
		if not check(reply):return
		for item in [inspect_model,loaded.get(selected.id),preview]:
			if is_instance_valid(item) and item.get_meta("studio",false):item.paint(reply.data.colors);item.runtime_version=reply.data.version
		for obj in me.objects:
			if obj.id==selected.id:obj.runtime_version=reply.data.version
		message("가구의 모든 부품 색상을 저장했어요.")
		return
	if await edit_object({"action":"paint","color":color}):
		message("색상이 서버에 저장됐습니다.")
		if is_instance_valid(preview): Loader.paint(preview,Color(color))
		if loaded.has(selected.id): Loader.paint(loaded[selected.id],Color(color))
		if is_instance_valid(inspect_model): Loader.paint(inspect_model,Color(color))
		for i in me.objects.size():
			if me.objects[i].id==selected.id:
				me.objects[i]=selected

func retrieve_object() -> void:
	cancel_preview()
	if await edit_object({"action":"retrieve"}):
		await refresh_inventory()
		message("보관함으로 회수했습니다.")

func begin_place() -> void:
	if selected.is_empty() or busy or refreshing: return
	if selected.state!="inventory":
		message("보관 중인 물건을 선택하세요.")
		return
	cancel_preview()
	busy = true
	preview = await load_object(selected)
	busy = false
	if preview:
		world.add_child(preview)
		preview_rotation=0
		player.controls_enabled=false
		if right.get_parent().visible: toggle_drawer()
		message("마음에 드는 바닥을 클릭하세요. R로 돌리고 Esc로 취소할 수 있어요.")

func cancel_preview() -> void:
	if is_instance_valid(preview): preview.queue_free()
	preview=null
	if is_instance_valid(player): player.controls_enabled=screen=="village"

func place_preview() -> void:
	if not is_instance_valid(preview): return
	var p := preview.position
	if absf(p.x)>11 or absf(p.z)>11: return
	if Vector2(player.position.x-p.x,player.position.z-p.z).length()<1.3:
		message("캐릭터와 겹치지 않는 곳에 놓으세요.")
		return
	if await edit_object({"action":"place","x":p.x,"z":p.z,"rotation":preview_rotation}):
		cancel_preview()
		await refresh_inventory()
		message("마을에 놓았습니다. 다시 접속해도 유지됩니다.")

func generate() -> void:
	if busy or not job_id.is_empty(): return
	if prompt.text.strip_edges().length()<3:
		message("만들고 싶은 물건을 세 글자 이상 적어 주세요.")
		return
	busy=true
	var result: Dictionary = await api.post("/v1/generations",api.mutation({"prompt":prompt.text}))
	busy=false
	if not check(result): return
	job_id=result.data.id
	message("공방에서 만들고 있습니다…")
	await refresh_inventory()

func poll_job() -> void:
	if polling_job or job_id.is_empty(): return
	polling_job=true
	var epoch := world_epoch
	var result: Dictionary = await api.request("/v1/generations/"+job_id)
	if epoch!=world_epoch:
		polling_job=false
		return
	if not check(result):
		polling_job=false
		return
	if result.data.state=="ready":
		await refresh_inventory()
		job_id=""
		message("새 물건이 보관함에 도착했습니다!")
	elif result.data.state in ["failed","unknown"]:
		job_id=""
		message("생성 상태: "+result.data.state+" · "+error_message(str(result.data.error_code)))
	else: message("공방에서 물건을 만들고 있습니다…")
	polling_job=false

func sell_object() -> void:
	if not TRADING_UI_ENABLED or selected.is_empty() or busy: return
	busy=true
	var result: Dictionary = await api.post("/v1/market",api.mutation({"object_id":selected.id,"version":selected.version,"price":int(price.value)}))
	busy=false
	if check(result):
		await refresh_inventory()
		message("장터에 등록했습니다. 판매 중에는 배치와 색칠이 잠깁니다.")

func show_market() -> void:
	if not TRADING_UI_ENABLED: return
	cancel_preview()
	var result: Dictionary = await api.request("/v1/market")
	if not check(result): return
	var popup := Window.new()
	popup.title="별씨 장터"
	popup.size=Vector2i(650,470)
	popup.theme=ui.theme
	popup.close_requested.connect(popup.queue_free)
	add_child(popup)
	var scroll := ScrollContainer.new()
	scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	popup.add_child(scroll)
	var rows := VBoxContainer.new()
	rows.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	scroll.add_child(rows)
	text(rows,"물건과 별씨는 서버에서 동시에 이전됩니다.",17)
	if result.data.listings.is_empty(): text(rows,"아직 등록된 물건이 없습니다.")
	for listing in result.data.listings:
		var line := HBoxContainer.new()
		rows.add_child(line)
		text(line,"%s · %d 별씨 · %s" % [listing.name,listing.price,listing.seller]).size_flags_horizontal=Control.SIZE_EXPAND_FILL
		button(line,"판매 취소" if listing.mine else "구매",func():
			var response: Dictionary = await api.post("/v1/market/"+listing.id+("/cancel" if listing.mine else "/buy"),api.mutation())
			if check(response):
				popup.queue_free()
				await refresh_inventory()
				message("장터 거래가 완료됐습니다."))
	popup.popup_centered()

func start_run(map_id := "forest", difficulty := "standard", chapter_id := "") -> void:
	if busy: return
	close_village_modal()
	cancel_preview()
	busy=true
	var result: Dictionary = await api.post("/v1/runs",api.mutation({"map_id":map_id,"difficulty":difficulty,"chapter_id":chapter_id}))
	if not check(result):
		busy=false
		return
	run_id=result.data.id
	var snapshot: Dictionary = await api.request("/v1/runs/"+run_id)
	if not check(snapshot):
		busy=false
		return
	run=snapshot.data
	build_world(true)
	clear_ui()
	screen="survival"
	player.controls_enabled=false
	left=panel(Vector2(24,24),250,"hero")
	text(left,"✦  SEVEN NIGHTS  /  EXPEDITION",11).modulate=Color("e4c989")
	text(left,region_name(run.get("map_id","forest")),22)
	text(left,"%s · 보상 ×%.3f" % [difficulty_name(run.get("difficulty","standard")),run.get("reward_multiplier",1.0)],12)
	rule(left)
	metrics=text(left,"",13)
	var hp_meter := status_meter(left,"♥  체력",Color("d98f80"))
	hp_bar=hp_meter.bar;hp_readout=hp_meter.readout
	var hunger_meter := status_meter(left,"◆  포만감",Color("d9ba75"))
	hunger_bar=hunger_meter.bar;hunger_readout=hunger_meter.readout
	var stamina_meter := status_meter(left,"✧  기력",Color("7fc5b7"))
	stamina_bar=stamina_meter.bar;stamina_readout=stamina_meter.readout
	hp_bar.tooltip_text="체력";hunger_bar.tooltip_text="포만감";stamina_bar.tooltip_text="기력"
	var navigation := panel(Vector2(24,327),250)
	field_map=preload("res://scripts/field_map.gd").new()
	navigation.add_child(field_map)
	camp_status=text(navigation,"",12)
	right=panel(Vector2(954,24),302,"hero")
	var drawer_title := HBoxContainer.new()
	right.add_child(drawer_title)
	text(drawer_title,"탐험 가방",23).size_flags_horizontal=Control.SIZE_EXPAND_FILL
	button(drawer_title,"×",toggle_drawer)
	pack=text(right,"")
	var inventory_grid := GridContainer.new()
	inventory_grid.columns=4
	inventory_grid.add_theme_constant_override("h_separation",5)
	inventory_grid.add_theme_constant_override("v_separation",5)
	right.add_child(inventory_grid)
	for item in ITEM_NAMES:
		var slot := Button.new()
		slot.custom_minimum_size=Vector2(61,70)
		slot.focus_mode=Control.FOCUS_NONE
		slot.tooltip_text=ITEM_NAMES[item]+(" · 클릭해서 먹기" if item in ["berry","soup"] else " · 클릭해서 치료" if item=="bandage" else "")
		slot.pressed.connect(func():
			if item in ["berry","soup"]: intent("eat",item)
			elif item=="bandage": intent("heal"))
		inventory_grid.add_child(slot)
		var icon := TextureRect.new()
		icon.expand_mode=TextureRect.EXPAND_IGNORE_SIZE
		icon.texture=load("res://assets/items/"+item+".svg")
		icon.position=Vector2(10,4)
		icon.size=Vector2(40,40)
		icon.mouse_filter=Control.MOUSE_FILTER_IGNORE
		slot.add_child(icon)
		var count := Label.new()
		count.position=Vector2(0,44)
		count.size=Vector2(61,20)
		count.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
		count.mouse_filter=Control.MOUSE_FILTER_IGNORE
		slot.add_child(count)
		inventory_slots[item]={"count":count,"icon":icon,"button":slot}
	text(right,"제작대",20)
	craft_buttons.axe=button(right,"돌도끼 · 목재 3 + 돌 2",func(): intent("craft","axe"))
	craft_buttons.spear=button(right,"창 · 목재 4 + 돌 2",func(): intent("craft","spear"))
	craft_buttons.soup=button(right,"수프 · 열매 3 + 목재 1",func(): intent("craft","soup"))
	craft_buttons.bandage=button(right,"붕대 · 섬유 3",func(): intent("craft","bandage"))
	craft_buttons.axe.tooltip_text="나무에서 목재를 한 번에 2개 채집합니다. 밤의 모닥불용 목재 2개를 남겨 두세요."
	craft_buttons.spear.tooltip_text="공격 피해 10 → 25. 적의 준비 동작을 공격으로 끊을 수 있습니다."
	craft_buttons.soup.tooltip_text="열매보다 많은 포만감과 체력을 회복합니다. Q를 누르면 수프를 먼저 먹습니다."
	craft_buttons.bandage.tooltip_text="H로 사용하면 체력 30을 회복합니다. 체력이 가득 차면 소모하지 않습니다."
	text(right,"제작 전에 밤에 쓸 목재 2개를 남겨 두세요.",12).modulate=Color("e9c98b")
	text(right,"목표: 일곱 번째 밤까지 생존\n1일 = 60초 · 총 약 7분\nE / Space를 누르고 있으면 반복 행동\n붉은 원은 적의 공격 예고입니다.\nShift로 원 밖으로 빠져나오세요.\n연결이 끊기면 진행이 멈춥니다.",12)
	right.get_parent().visible=false
	build_play_hud(true)
	update_run()
	world_hint("나무·열매·돌·풀에 가까이 가서 E로 채집하세요.")
	busy=false

func intent(action: String, target := "") -> void:
	if screen!="survival" or paused or run.get("status","")!="active": return
	# Eating, healing, crafting and fueling take precedence over a held gather/attack key.
	if not pending_action.is_empty() and (action in ["harvest","attack"] or pending_action not in ["harvest","attack"]): return
	if action=="harvest" and target.is_empty():
		var nearest := 2.4
		for node in run.nodes:
			var dist := Vector2(run.x-node.x,run.z-node.z).length()
			if node.quantity>0 and dist<nearest:
				nearest=dist
				target=node.id
		if target.is_empty():
			message("채집할 나무·바위·풀·열매 가까이 가세요.")
			return
	pending_action=action
	pending_target=target

func tick_run() -> void:
	if ticking or busy or paused or run.get("status","")!="active": return
	ticking=true
	var movement := Input.get_vector("move_left","move_right","move_forward","move_back")
	var ready: bool=run.get("action_cooldown",0)<=0.01 and (pending_action!="attack" or run.get("attack_cooldown",0)<=0.01)
	var payload := {"sequence":int(run.sequence)+1,"dx":movement.x,"dz":movement.y,"sprint":Input.is_physical_key_pressed(KEY_SHIFT),"action":pending_action if ready else "","target":pending_target if ready else ""}
	if ready:
		pending_action=""
		pending_target=""
	var epoch := world_epoch
	var result: Dictionary = await api.post("/v1/runs/"+run_id+"/input",payload)
	if epoch!=world_epoch:
		ticking=false
		return
	if not result.ok:
		network_failures+=1
		message("서버 응답을 기다리고 있습니다. 연결을 복구하면 이어집니다.")
		# An uncertain response may have committed. Resync sequence before sending again.
		var snapshot: Dictionary = await api.request("/v1/runs/"+run_id)
		if epoch!=world_epoch:
			ticking=false
			return
		if snapshot.ok:
			run=snapshot.data
			update_run()
		ticking=false
		return
	ticking=false
	network_failures=0
	if result.data.hp<run.get("hp",100)-1:
		sound.effect("hurt")
		player.react("hurt")
		floating_feedback("−%d" % int(ceil(run.hp-result.data.hp)),player.position,Color("ef9983"))
	if result.data.status=="won" and run.get("status","")!="won": sound.effect("reward")
	if not str(payload.action).is_empty():
		var feedback: String=result.data.message
		if feedback.contains("+"):
			sound.effect("gather")
			for n in run.nodes:
				if n.id==payload.target:
					player.equip("axe" if n.kind=="tree" and run.inventory.axe>0 else "")
					player.face_point(Vector3(n.x,0,n.z))
					resource_response(n)
			player.react("gather")
			floating_feedback(feedback,player.position,Color("ece1b4"))
		elif feedback.contains("제작 완료"):
			sound.effect("craft")
			player.react("craft")
			floating_feedback(feedback,player.position,Color("b8dfb1"))
		elif feedback.contains("먹었습니다") or feedback.contains("회복했습니다"):
			sound.effect("eat")
			player.react("eat")
		elif feedback.contains("피웠습니다"): sound.effect("fire")
		elif feedback.contains("공격!") or feedback=="가까운 적이 없습니다.":
			sound.effect("hit")
			player.equip("spear" if run.inventory.spear>0 else "axe" if run.inventory.axe>0 else "")
			for enemy in run.enemies:
				var hp_after := 0.0
				for after in result.data.enemies:
					if after.id==enemy.id: hp_after=after.hp
				if hp_after<enemy.hp:
					player.face_point(Vector3(enemy.x,0,enemy.z))
					floating_feedback(str(int(enemy.hp-hp_after)),Vector3(enemy.x,0,enemy.z),Color("f3c980"))
					break
			player.react("attack")
			attack_sweep()
	run=result.data
	update_run()

func update_run() -> void:
	var remaining := int(ceil(run.get("phase_remaining",0)))
	metrics.text="%s   ·   %s %d초" % ["달이 뜬 밤" if run.night else "탐험하기 좋은 낮","아침까지" if run.night else "밤까지",remaining]
	if is_instance_valid(day_track):
		var days := ""
		for i in 7: days+=("● " if i<int(run.day) else "○ ")
		day_track.text="DAY %02d    %s" % [run.day,days]
	hp_bar.value=run.hp
	hunger_bar.value=run.hunger
	stamina_bar.value=run.get("stamina",100)
	hp_readout.text="%d / 100" % int(run.hp)
	hunger_readout.text="%d / 100" % int(run.hunger)
	stamina_readout.text="%d / 100" % int(run.get("stamina",100))
	for item in quick_counts: quick_counts[item].text=str(int(run.inventory[item]))
	var camp_distance := Vector2(run.x,run.z).length()
	camp_status.text="야영지 %.0fm · 불 %d초\n%s" % [camp_distance,run.fire_remaining,"불빛 안 · 밤의 위협을 막아 줍니다" if run.get("warm",false) else "지도 중앙의 ▲로 돌아오세요"]
	if run.get("terrain_effect","")=="ice": camp_status.text+="\n얼음 위 · 이동 둔화 / 허기 증가"
	elif run.get("terrain_effect","")=="ember": camp_status.text+="\n뜨거운 균열! 빨리 벗어나세요"
	field_map.update_state(run,Vector2(player.facing.x,player.facing.z))
	var total := 0
	for item in ITEM_NAMES:
		var amount := int(run.inventory[item])
		total+=amount
		inventory_slots[item].count.text=str(amount)
		inventory_slots[item].icon.modulate=Color.WHITE if amount>0 else Color(0.45,0.5,0.47)
		inventory_slots[item].button.disabled=amount<=0
	pack.text="탐험 소지품  %d / 80" % total
	if is_instance_valid(objective):
		if run.status=="won": objective.text="일곱 밤을 견뎌냈어요!\n귀환하여 %d 별씨를 받으세요." % run.reward
		elif run.status!="active": objective.text="이번 탐험은 여기까지예요.\n귀환 후 다시 도전할 수 있어요."
		elif run.hunger<35: objective.text="먼저 배를 채우세요\nQ로 열매나 수프를 먹으세요."
		elif run.night: objective.text="불빛 안에서 밤을 버티세요\nF · 목재 2개로 불 30초 연장\n\n붉은 원 = 적의 공격 예고\nShift로 피하거나 Space로 공격"
		elif run.inventory.wood<4: objective.text="첫 준비 · 목재 모으기\n나무 옆에서 E로 채집하세요.\n밤에 쓸 목재를 남겨 두세요."
		elif run.inventory.axe==0: objective.text="도끼를 만들면 채집이 빨라져요\n목재 3 + 돌 2를 모으세요.\nI · 가방에서 도구 만들기"
		else: objective.text="다음 밤을 준비하세요\n열매와 목재를 비축하고,\n창으로 그림자 짐승에 맞서세요."
		if run.get("story") is Dictionary and run.status=="active":
			objective.text=run.story.title+"\n"
			for goal in run.story.goals:objective.text+="%s  %d / %d\n"%[goal.label,goal.current,goal.target]
			objective.text+="\n"+("Q · 먼저 음식을 드세요" if run.hunger<35 else "I 제작 · F 모닥불 · Q 식사")
	for recipe in craft_buttons:
		var can_make: bool=run.status=="active"
		for item in RECIPES[recipe]:
			if run.inventory.get(item,0)<RECIPES[recipe][item]: can_make=false
		if recipe in ["axe","spear"] and run.inventory.get(recipe,0)>0: can_make=false
		craft_buttons[recipe].disabled=not can_make
	if Time.get_ticks_msec()*0.001>=player.action_until and (not is_instance_valid(player.action_pose) or player.action_pose.elapsed>=player.action_pose.duration):
		player.equip("spear" if run.inventory.spear>0 else "axe" if run.inventory.axe>0 else "")
	message(run.message)
	if run.status=="won": message("생존 성공! 마을로 돌아가 %d 별씨를 받으세요." % run.reward)
	if int(run.day)!=prior_day:
		prior_day=int(run.day)
		message("%d일째 아침이에요. 숲을 둘러보고 다음 밤을 준비하세요." % run.day)
		sound.effect("reward")
	if bool(run.night)!=prior_night:
		prior_night=bool(run.night)
		if run.night: message("해가 졌어요. 야영지로 돌아가 불을 지키세요.")
	if run.status!="active" and not results_shown:
		results_shown=true
		if is_instance_valid(return_dialog): return_dialog.queue_free()
		show_results()
	flame.visible=run.fire_remaining>0
	warmth_ring.visible=flame.visible
	if run.status=="active" and run.elapsed-last_camp_warning>12:
		if run.night and run.fire_remaining>0 and run.fire_remaining<7:
			message("모닥불이 곧 꺼져요. 야영지에서 F로 목재를 보태세요.")
			last_camp_warning=run.elapsed
		elif not run.night and remaining<=10:
			message("밤까지 %d초! 야영지로 돌아갈 준비를 하세요." % remaining)
			last_camp_warning=run.elapsed
	for n in run.nodes:
		if not nodes.has(n.id):
			var root := Node3D.new()
			world.add_child(root)
			root.position=Vector3(n.x,0,n.z)
			match n.kind:
				"tree": Art.tree(root,Vector3.ZERO,true,false)
				"stone":
					Landscape.rock(root,Vector3(0,0.37,0),Vector3(1.25,0.9,1.1),Color("879588"))
					Landscape.rock(root,Vector3(0.4,0.16,0.35),Vector3(0.5,0.4,0.45),Color("a7afa0"))
				"berry":
					Art.sphere(root,Vector3(0,0.45,0),Vector3(1,0.9,1),Color("718e71"))
					for x in [-0.3,0.0,0.3]: Art.sphere(root,Vector3(x,0.7,0.3),Vector3.ONE*0.2,Color("d07878"))
				"fiber":
					for i in 7:
						var leaf := Art.sphere(root,Vector3(sin(i*2.4)*0.24,0.3,cos(i*2.4)*0.24),Vector3(0.09,0.65,0.22),Color("95a562"))
						leaf.rotation=Vector3(sin(i)*0.5,i*2.4,cos(i)*0.4)
			nodes[n.id]=root
			nodes[n.id].set_meta("kind",n.kind)
			if run.get("map_id","forest")!="forest":
				for mesh in root.find_children("*","MeshInstance3D",true,false):
					if mesh.is_in_group("canopy"):
						mesh.material_override.albedo_color=Color("b8d3cf") if run.map_id=="frost" else Color("958654")
			if n.kind=="tree":
				var stump := Landscape.cylinder(root,Vector3(0,0.15,0),0.27,0.3,Color("b5986a"),9)
				stump.name="Stump"
				stump.visible=false
		if n.kind=="tree":
			for child in nodes[n.id].get_children(): child.visible=(n.quantity<=0) if child.name=="Stump" else (n.quantity>0)
		else: nodes[n.id].visible=n.quantity>0
	var alive := []
	for enemy in run.enemies:
		alive.append(enemy.id)
		if not enemy_nodes.has(enemy.id):
			var root := preload("res://scripts/shadow_beast.gd").new()
			root.kind=enemy.get("kind","wolf")
			world.add_child(root)
			root.position=Vector3(enemy.x,0,enemy.z)
			enemy_nodes[enemy.id]=root
			var marker := MeshInstance3D.new()
			var disk := CylinderMesh.new()
			disk.top_radius=enemy.get("impact",1.35)
			disk.bottom_radius=enemy.get("impact",1.35)
			disk.height=0.018
			disk.radial_segments=32
			marker.mesh=disk
			var danger := Art.material(Color(0.95,0.25,0.18,0.4))
			danger.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
			danger.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
			marker.material_override=danger
			world.add_child(marker)
			strike_markers[enemy.id]=marker
		var node: Node3D=enemy_nodes[enemy.id]
		node.update_snapshot(enemy,Vector3(run.x,0,run.z))
		var strike: MeshInstance3D=strike_markers[enemy.id]
		strike.visible=enemy.get("phase","")=="windup"
		strike.position=Vector3(enemy.get("target_x",enemy.x),0.04,enemy.get("target_z",enemy.z))
	for id in enemy_nodes.keys():
		if id not in alive:
			enemy_nodes[id].queue_free()
			enemy_nodes.erase(id)
			strike_markers[id].queue_free()
			strike_markers.erase(id)

func resource_response(resource: Dictionary) -> void:
	if not nodes.has(resource.id): return
	var root: Node3D=nodes[resource.id]
	var tween := root.create_tween()
	tween.tween_property(root,"rotation:z",0.045,0.07)
	tween.tween_property(root,"rotation:z",-0.025,0.06)
	tween.tween_property(root,"rotation:z",0.0,0.12)
	for i in 5:
		var chip := Art.box(world,Vector3(resource.x,0.75,resource.z),Vector3.ONE*0.08,Color("c4a26d") if resource.kind=="tree" else Color("aabc8a"))
		var scatter := chip.create_tween().set_parallel(true)
		scatter.tween_property(chip,"position",chip.position+Vector3(sin(i*2.4)*0.8,-0.65,cos(i*2.4)*0.8),0.4)
		scatter.tween_property(chip,"scale",Vector3.ZERO,0.3).set_delay(0.1)
		scatter.chain().tween_callback(chip.queue_free)

func confirm_return() -> void:
	if run.get("status","")!="active":
		leave_run()
		return
	if is_instance_valid(return_dialog): return
	return_dialog=ConfirmationDialog.new()
	return_dialog.title="탐험을 마칠까요?"
	return_dialog.dialog_text="지금 돌아가면 이번 도전이 끝나고 완주 보상을 받을 수 없습니다.\n"+("현재 탐험은 일시 정지되어 있습니다." if paused else "이 창을 보는 동안에도 생존 시간은 흐릅니다.")
	return_dialog.ok_button_text="탐험을 마치고 귀환"
	return_dialog.cancel_button_text="계속 생존하기"
	return_dialog.confirmed.connect(func():
		return_dialog.queue_free()
		leave_run())
	return_dialog.canceled.connect(return_dialog.queue_free)
	add_child(return_dialog)
	return_dialog.popup_centered(Vector2i(530,160))

func toggle_pause() -> void:
	if screen!="survival" or run.get("status","")!="active": return
	if paused:
		paused=false
		if is_instance_valid(pause_shade): pause_shade.queue_free()
		return
	paused=true
	pending_action=""
	pending_target=""
	pause_shade=ColorRect.new()
	pause_shade.color=Color(0.025,0.07,0.08,0.8)
	pause_shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ui.add_child(pause_shade)
	var card := panel(Vector2(405,190),470)
	# Own the menu under the shade so resume frees the complete overlay.
	var container := card.get_parent()
	ui.remove_child(container)
	pause_shade.add_child(container)
	text(card,"잠깐 숨 고르기",27)
	text(card,"현재 도전은 1인 생존 모드입니다.\n일시 정지 중에는 생존 시간과 허기가 멈춥니다.",14)
	text(card,"WASD 이동 · Shift 달리기\nE 채집 · Space 공격 (길게 누르면 반복)\nQ 먹기 · F 모닥불 · H 붕대\nI 가방/제작 · 휠 확대/축소 · M 소리",14)
	button(card,"Esc · 계속 생존하기",toggle_pause)
	button(card,"진행을 저장하고 마을로",suspend_run)
	button(card,"소리 켜기 / 끄기",sound.toggle)
	button(card,"탐험을 마치고 귀환",confirm_return)

func retry_run() -> void:
	var region: String=run.get("map_id","forest")
	var difficulty: String=run.get("difficulty","standard")
	await leave_run()
	if screen=="village": await start_run(region,difficulty)

func suspend_run() -> void:
	if busy or screen!="survival" or run.get("status","")!="active": return
	busy=true
	paused=true
	pending_action=""
	while ticking: await get_tree().process_frame
	# Each accepted input is already persisted by the server. Preserve this active run.
	run_id=""
	busy=false
	await enter_village()
	message("탐험을 저장했습니다. 하단의 이어하기로 같은 날부터 돌아갈 수 있어요.")

func floating_feedback(value: String, at: Vector3, color: Color) -> void:
	var label := Label3D.new()
	label.text=value
	label.font_size=32
	label.pixel_size=0.007
	label.position=at+Vector3(0,2.1,0)
	label.billboard=BaseMaterial3D.BILLBOARD_ENABLED
	label.modulate=color
	label.outline_size=5
	world.add_child(label)
	var tween := label.create_tween().set_parallel(true)
	tween.tween_property(label,"position:y",label.position.y+0.85,1)
	tween.tween_property(label,"modulate:a",0.0,0.5).set_delay(0.5)
	tween.chain().tween_callback(label.queue_free)

func attack_sweep() -> void:
	var mesh := ImmediateMesh.new()
	mesh.surface_begin(Mesh.PRIMITIVE_TRIANGLE_STRIP)
	for i in 13:
		var angle := -0.85+i*1.7/12
		for radius in [1.3,1.47]: mesh.surface_add_vertex(Vector3(sin(angle)*radius,0,-cos(angle)*radius))
	mesh.surface_end()
	var arc := MeshInstance3D.new()
	arc.mesh=mesh
	arc.position=player.position+Vector3(0,0.8,0)
	arc.rotation.y=atan2(-player.facing.x,-player.facing.z)
	var mat := Art.material(Color("efe4b4"))
	mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.cull_mode=BaseMaterial3D.CULL_DISABLED
	mat.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	arc.material_override=mat
	world.add_child(arc)
	var tween := arc.create_tween()
	tween.tween_property(mat,"albedo_color:a",0,0.23)
	tween.tween_callback(arc.queue_free)

func show_results() -> void:
	paused=false
	if is_instance_valid(pause_shade): pause_shade.queue_free()
	var shade := ColorRect.new()
	shade.color=Color(0.035,0.08,0.09,0.65)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ui.add_child(shade)
	var card := panel(Vector2(410,215),460)
	var won: bool=run.status=="won"
	text(card,"EXPEDITION COMPLETE" if won else "UNTIL NEXT TIME",12).modulate=Color("cfbe8c")
	text(card,"일곱 밤을 견뎌냈어요" if won else "다시 피울 작은 불씨",28)
	text(card,"%s · %s · 보상 ×%.3f" % [region_name(run.get("map_id","forest")),difficulty_name(run.get("difficulty","standard")),run.get("reward_multiplier",1.0)],14)
	text(card,"생존  %d일     채집  %d회     처치  %d" % [run.day,run.get("harvested",0),run.get("kills",0)],16)
	text(card,"보상  %d 별씨" % run.get("reward",0) if won else "완주 보상은 7일 생존 후 받을 수 있어요.",22 if won else 14)
	if run.get("story") is Dictionary:
		var story_text := "목표가 남아 있어 이야기는 다음 도전에서 이어집니다."
		if run.story.objectives_met:story_text=run.story.ending+"\n첫 완료 보너스 %d 별씨"%int(run.get("story_bonus",0))
		var story_note := text(card,story_text,14);story_note.custom_minimum_size.x=420;story_note.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	if not won:
		var lesson := "밤에는 목재 2개를 남기고 야영지의 불을 지키세요."
		if run.get("hunger",100)<1: lesson="열매와 수프를 비축하고, 포만감이 떨어지면 Q로 먹으세요."
		elif run.get("fire_remaining",0)>0: lesson="모닥불의 금색 원 안으로 돌아오거나, 붉은 공격 예고를 피하세요."
		var advice := text(card,lesson,13)
		advice.custom_minimum_size.x=420
		advice.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	button(card,"보상 받고 마을로" if won else "마을로 돌아가기",leave_run)
	if not won: button(card,"새 탐험으로 다시 도전",retry_run)

func leave_run() -> void:
	if busy: return
	busy=true
	while ticking: await get_tree().process_frame
	if run.status=="won" and not run.claimed:
		var result: Dictionary = await api.post("/v1/runs/"+run_id+"/claim",api.mutation())
		if not check(result):
			busy=false
			return
	elif run.status=="active":
		var result: Dictionary = await api.post("/v1/runs/"+run_id+"/abandon",api.mutation())
		if not check(result):
			busy=false
			return
	busy=false
	run_id=""
	await enter_village()

func logout() -> void:
	if busy: return
	busy=true
	screen="logging_out"
	world_epoch+=1
	await api.post("/v1/auth/logout",{})
	api.token=""
	job_id=""
	build_world(false)
	login_ui()
	busy=false

func follow_camera(delta: float) -> void:
	if not is_instance_valid(player): return
	var target := player.position+Vector3(0,0.6,-1)
	var at := target+Vector3(0,14,17)
	camera.position=camera.position.lerp(at,minf(1,delta*6))
	camera.look_at(target)

func _process(delta: float) -> void:
	follow_camera(delta)
	canopy_elapsed+=delta
	if canopy_elapsed>0.08:
		canopy_elapsed=0
		update_canopy_visibility()
	if is_instance_valid(inspect_model) and is_instance_valid(inspect_panel) and inspect_panel.visible:
		inspect_model.rotation.y+=delta*0.35
	if toast_time>0:
		toast_time-=delta
		if toast_time<=0 and is_instance_valid(toast_panel): toast_panel.visible=false
	if is_instance_valid(flame) and flame.visible:
		flame.scale=Vector3(1.0+sin(Time.get_ticks_msec()*0.011)*0.07,1.0+sin(Time.get_ticks_msec()*0.015)*0.12,1.0)
	if screen=="survival":
		player.external_motion=Input.get_vector("move_left","move_right","move_forward","move_back") if run.get("status","")=="active" and not paused and network_failures==0 else Vector2.ZERO
		player.sprinting=run.get("sprinting",false)
		repeat_action+=delta
		if repeat_action>=0.43 and not paused:
			repeat_action=0
			if Input.is_physical_key_pressed(KEY_SPACE): intent("attack")
			elif Input.is_physical_key_pressed(KEY_E): intent("harvest")
		player.position=player.position.lerp(Vector3(run.get("x",0),0.03,run.get("z",0)),minf(delta*18,1))
		tick_elapsed+=delta
		if tick_elapsed>=0.1:
			tick_elapsed=0
			tick_run()
		var night: bool=run.get("night",false)
		environment.ambient_light_energy=lerpf(environment.ambient_light_energy,0.25 if night else 0.35,delta*1.2)
		environment.ambient_light_color=environment.ambient_light_color.lerp(Color("788fab") if night else Color.WHITE,delta)
		sun.light_energy=lerpf(sun.light_energy,0.22 if night else 0.25,delta*1.2)
		sun.light_color=sun.light_color.lerp(Color("7fa9cf") if night else Color("fff5e9"),delta)
		environment.background_color=environment.background_color.lerp(Color("233b50") if night else Color("88bcb9"),delta)
		update_harvest_hint()
	elif screen=="village":
		player.sprinting=Input.is_physical_key_pressed(KEY_SHIFT)
		if is_instance_valid(objective):
			var placed := 0
			for obj in me.get("objects",[]):
				if obj.state=="placed": placed+=1
			if is_instance_valid(preview): objective.text="나만의 자리 찾기\n바닥을 클릭하면 배치돼요.\nR · 회전    Esc · 취소"
			elif me.get("active_run_summary") is Dictionary: objective.text="돌아갈 탐험이 있어요\n%d일째 · 체력 %d\n하단의 이어하기 또는 돌문 앞 E\n\n마을에서는 생존 시간이 멈춥니다." % [me.active_run_summary.day,me.active_run_summary.hp]
			elif placed==0: objective.text="첫 번째 마을 꾸미기\nI로 보관함을 열어 색을 고르고,\n환영의 의자를 놓아 보세요."
			else: objective.text="나의 마을 · 물건 %d개 배치\n숲에서 7일을 살아남으면\n새 물건을 만들 별씨를 받아요.\n\n돌문 앞에서 E · 탐험 시작" % placed
			if not is_instance_valid(preview) and (not life.goal.is_empty() or not me.get("active_run_summary") is Dictionary): objective.text=life.goal_text()
		if not is_instance_valid(preview):
			player.controls_enabled=not is_instance_valid(village_modal) and not get_viewport().gui_get_focus_owner() is LineEdit
			if is_instance_valid(hint):
				var npc := nearest_npc()
				var activity: Dictionary=life.closest()
				if not activity.is_empty(): hint.text="E · "+activity.title+"   |   B · 생활 창고"
				elif npc: hint.text="E · %s와 이야기하기" % npc.get_meta("title")
				elif player.position.distance_to(Vector3(7,0,-5.5))<3: hint.text="E · 탐험 지역과 난이도 고르기"
				elif player.position.distance_to(TownLayout.HOME_DOOR)<2: hint.text="E · 나의 집으로 들어가기"
				elif player.position.distance_to(Vector3(-5,0,-2.6))<2.5: hint.text="E · 별씨 공방에서 물건 꾸미기"
				elif not nearest_furniture().is_empty():hint.text="E · 가까운 가구 사용"
				else: hint.text="WASD · 산책하기    휠 · 가까이 보기    I · 나의 물건"
		entitlement_elapsed+=delta
		furniture_proximity_time+=delta
		if furniture_proximity_time>.5:furniture_proximity_time=0;village_furniture_proximity()
		if entitlement_elapsed>3:
			entitlement_elapsed=0
			poll_entitlements()
		if not job_id.is_empty():
			poll_elapsed+=delta
			if poll_elapsed>2:
				poll_elapsed=0
				poll_job()
		if is_instance_valid(preview):
			var mouse := get_viewport().get_mouse_position()
			var point = Plane(Vector3.UP,0).intersects_ray(camera.project_ray_origin(mouse),camera.project_ray_normal(mouse))
			if point!=null:
				preview.position=Vector3(snappedf(point.x,0.5),0,snappedf(point.z,0.5))
				preview.rotation_degrees.y=preview_rotation

func update_canopy_visibility() -> void:
	if not is_instance_valid(player): return
	var hero_screen := camera.unproject_position(player.position+Vector3(0,1,0))
	var radius := 720.0/camera.size
	for canopy in get_tree().get_nodes_in_group("canopy"):
		if not world.is_ancestor_of(canopy): continue
		var point: Vector3=canopy.global_transform*canopy.get_aabb().get_center()
		canopy.rotation.x=sin(Time.get_ticks_msec()*0.0012+point.x)*0.008
		canopy.rotation.z=sin(Time.get_ticks_msec()*0.0009+point.z)*0.008
		var obscures: bool=point.z>player.position.z-0.7 and point.z<player.position.z+5 and camera.unproject_position(point).distance_to(hero_screen)<radius*1.65
		var mat: StandardMaterial3D=canopy.material_override
		var color := mat.albedo_color
		color.a=lerpf(color.a,0.2 if obscures else 1.0,0.45)
		mat.albedo_color=color
		mat.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS if color.a<0.99 else BaseMaterial3D.TRANSPARENCY_DISABLED

func update_harvest_hint() -> void:
	if not is_instance_valid(hint): return
	var closest := 2.3
	var selected_node: Dictionary={}
	for n in run.get("nodes",[]):
		var distance := Vector2(run.x-n.x,run.z-n.z).length()
		if n.quantity>0 and distance<closest:
			closest=distance
			selected_node=n
	harvest_marker.visible=not selected_node.is_empty() and run.status=="active"
	if harvest_marker.visible:
		harvest_marker.position=Vector3(selected_node.x,0.1,selected_node.z)
		var names := {"tree":"나무","stone":"돌","berry":"열매","fiber":"풀"}
		hint.text="E · %s 채집 (남은 자원 %d)  |  I · 가방  |  M · 소리" % [names[selected_node.kind],selected_node.quantity]
	elif run.status=="active":
		hint.text="자원 가까이 이동하세요  |  I · 가방  |  휠 · 확대/축소  |  M · 소리"
	else:
		hint.text="탐험이 끝났습니다. 마을로 돌아가 결과를 확인하세요."

func _unhandled_input(event: InputEvent) -> void:
	if is_instance_valid(village_modal):
		if event is InputEventKey and event.pressed and not event.echo and event.physical_keycode==KEY_E and life.mode=="fish": life.reel()
		if event is InputEventKey and event.pressed and event.physical_keycode==KEY_ESCAPE: close_village_modal()
		return
	if event is InputEventKey and event.pressed and not event.echo and event.physical_keycode==KEY_ESCAPE and screen=="survival":
		toggle_pause()
		return
	if paused: return
	if screen in ["village","survival"] and event is InputEventMouseButton and event.pressed:
		if event.button_index==MOUSE_BUTTON_WHEEL_UP: camera.size=maxf(12,camera.size-1)
		if event.button_index==MOUSE_BUTTON_WHEEL_DOWN: camera.size=minf(26,camera.size+1)
	if event is InputEventKey and event.pressed and not event.echo:
		if event.physical_keycode==KEY_M:
			sound.toggle()
			message("소리를 껐습니다. M으로 다시 켤 수 있습니다." if sound.muted else "소리를 켰습니다.")
		if screen in ["village","survival"] and event.physical_keycode==KEY_I:
			toggle_drawer()
		if screen=="survival":
			match event.physical_keycode:
				KEY_E: intent("harvest")
				KEY_Q: intent("eat")
				KEY_F: intent("fire")
				KEY_H: intent("heal")
				KEY_SPACE: intent("attack")
		elif screen=="village":
			if event.physical_keycode==KEY_TAB: life.open_map()
			if event.physical_keycode==KEY_B: life.open_storage()
			if event.physical_keycode==KEY_ESCAPE: cancel_preview()
			if event.physical_keycode==KEY_R: preview_rotation=(preview_rotation+90)%360
			if event.physical_keycode==KEY_E and not life.closest().is_empty(): life.interact()
			elif event.physical_keycode==KEY_E and nearest_npc(): talk_to(nearest_npc())
			elif event.physical_keycode==KEY_E and player.position.distance_to(Vector3(7,0,-5.5))<3: open_expedition()
			elif event.physical_keycode==KEY_E and player.position.distance_to(TownLayout.HOME_DOOR)<2: open_studio("home")
			elif event.physical_keycode==KEY_E and player.position.distance_to(Vector3(-5,0,-2.6))<2.5: open_studio()
			elif event.physical_keycode==KEY_E: village_furniture_event(nearest_furniture(),"click")
	if screen=="village" and event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_LEFT:
		place_preview()

func region_name(id: String) -> String:
	return {"forest":"솔바람 숲","quarry":"노을 채석장","frost":"서리빛 분지"}.get(id,id)

func difficulty_name(id: String) -> String:
	return {"relaxed":"산책","standard":"탐험","veteran":"개척"}.get(id,id)

func close_village_modal() -> void:
	if is_instance_valid(life): life.closed()
	if is_instance_valid(village_modal):
		village_modal.get_parent().remove_child(village_modal)
		village_modal.queue_free()
	village_modal=null

func modal_card(title: String) -> VBoxContainer:
	close_village_modal()
	cancel_preview()
	village_modal=Control.new()
	village_modal.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ui.add_child(village_modal)
	var shade := ColorRect.new()
	shade.color=Color(0.025,0.05,0.06,0.76)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	village_modal.add_child(shade)
	var v := panel(Vector2(265,100),750)
	var card := v.get_parent()
	ui.remove_child(card)
	village_modal.add_child(card)
	var row := HBoxContainer.new()
	v.add_child(row)
	text(row,title,25).size_flags_horizontal=Control.SIZE_EXPAND_FILL
	button(row,"닫기 · Esc",close_village_modal)
	player.controls_enabled=false
	return v

func open_expedition() -> void:
	if screen!="village" or busy: return
	if me.get("active_run_summary") is Dictionary:
		await start_run()
		return
	var v := modal_card("어느 곳에서 일곱 밤을 보낼까요?")
	button(v,"이야기 수첩 · 섬의 세 가지 기록",open_story)
	text(v,"지역과 난이도는 탐험을 시작하면 고정됩니다.",13)
	var region_row := HBoxContainer.new()
	v.add_child(region_row)
	var details := text(v,"",14)
	details.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	details.custom_minimum_size=Vector2(700,68)
	var diff_row := HBoxContainer.new()
	v.add_child(diff_row)
	var estimate := text(v,"",15)
	estimate.custom_minimum_size.y=60
	var maps: Array=me.get("catalog",{}).get("maps",[])
	var difficulties: Array=me.get("catalog",{}).get("difficulties",[])
	var refresh := func():
		var multiplier := 1.0
		for region in maps:
			if region.id==chosen_map:
				details.text=region.name+"\n"+region.description
				multiplier*=float(region.reward_multiplier)
		for difficulty in difficulties:
			if difficulty.id==chosen_difficulty:
				multiplier*=float(difficulty.reward_multiplier)
				estimate.text=difficulty.description+"\n완주 성과에 따른 별씨 보상 ×%.3f · 예상 %d–%d개" % [multiplier,int(floor(35*multiplier+0.000001)),int(floor(100*multiplier+0.000001))]
		for b in region_row.get_children(): b.button_pressed=b.get_meta("id")==chosen_map
		for b in diff_row.get_children(): b.button_pressed=b.get_meta("id")==chosen_difficulty
	for region in maps:
		var b := button(region_row,region.name,func(): chosen_map=region.id; refresh.call())
		b.set_meta("id",region.id)
		b.toggle_mode=true
		b.size_flags_horizontal=Control.SIZE_EXPAND_FILL
		b.custom_minimum_size.y=90
	for difficulty in difficulties:
		var b := button(diff_row,difficulty.name+" · ×%.1f" % difficulty.reward_multiplier,func(): chosen_difficulty=difficulty.id; refresh.call())
		b.set_meta("id",difficulty.id)
		b.toggle_mode=true
		b.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	button(v,"준비 완료 · 일곱 밤 시작",func(): start_run(chosen_map,chosen_difficulty))
	refresh.call()

func open_story() -> void:
	if screen!="village" or busy:return
	var v := modal_card("이야기 수첩 · 돌아오는 빛")
	text(v,"첫 완료 시 별씨와 집 앞 기념등이 추가됩니다. 자유 탐험은 지역 제한 없이 계속할 수 있어요.",13)
	var choice := HBoxContainer.new();v.add_child(choice)
	var description := text(v,"",16);description.custom_minimum_size=Vector2(700,140);description.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	var goals := text(v,"",15);goals.custom_minimum_size.y=100
	var difficulty := OptionButton.new();difficulty.add_item("산책 · 천천히 이야기 즐기기");difficulty.add_item("탐험 · 기본 생존");difficulty.add_item("개척 · 더 강한 적");difficulty.select(1);v.add_child(difficulty)
	var start := button(v,"이야기 시작",func():pass)
	var selected_story := {"id":""}
	var select_chapter := func(chapter):
		selected_story.id=chapter.id
		description.text=chapter.speaker+"의 부탁\n\n"+chapter.intro
		goals.text="이번 탐험의 목표\n"+" · ".join(chapter.objectives)+"\n\n"+("첫 완료 보상 수령 완료 · 다시 도전할 수 있어요" if chapter.completed else "첫 완료 보상 +%d 별씨 · %s"%[chapter.bonus,"도전 가능" if chapter.unlocked else "이전 장을 먼저 완료하세요"])
		start.disabled=not chapter.unlocked
		for child in choice.get_children():child.button_pressed=child.get_meta("id")==chapter.id
	start.pressed.connect(func():
		for chapter in me.get("campaign",[]):
			if chapter.id==selected_story.id:start_run(chapter.map_id,["relaxed","standard","veteran"][difficulty.selected],chapter.id))
	for chapter in me.get("campaign",[]):
		var b := button(choice,chapter.title+(" ✓" if chapter.completed else ""),func():select_chapter.call(chapter));b.toggle_mode=true;b.set_meta("id",chapter.id);b.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	var chapters: Array=me.get("campaign",[])
	if chapters.is_empty():description.text="서버를 업데이트한 뒤 다시 접속해 주세요";start.disabled=true
	else:
		var current: Dictionary=chapters[0]
		for chapter in chapters:
			if chapter.unlocked and not chapter.completed:current=chapter;break
		select_chapter.call(current)

func spawn_villagers() -> void:
	var entries := [
		{"title":"나루 · 길잡이","role":"map","at":Vector3(5.1,0.1,-3.1),"character":"explorer","coat":"#70afa3"},
		{"title":"소라 · 재단사","role":"wardrobe","at":Vector3(-3.8,0.1,2.0),"character":"ranger","coat":"#ab789f"},
		{"title":"모루 · 야영 전문가","role":"guide","at":Vector3(6.5,0.1,5.5),"character":"tinker","coat":"#6889a1"},
		{"title":"단비 · 씨앗지기","role":"farmer","at":Vector3(-19.3,0.65,0.9),"character":"ranger","coat":"#70afa3"},
		{"title":"해루 · 낚시꾼","role":"angler","at":Vector3(29.6,0.1,26),"character":"tinker","coat":"#dba448"}]
	for entry in entries:
		var npc := Player.new()
		npc.controls_enabled=false
		npc.avatar={"character":entry.character,"coat":entry.coat,"backpack":false,"headwear":"cap" if entry.role=="guide" else "none"}
		world.add_child(npc)
		npc.position=entry.at
		npc.facing=Vector3(0,0,1)
		npc.set_meta("title",entry.title)
		npc.set_meta("role",entry.role)
		Art.label3d(npc,entry.title,Vector3(0,2.05,0),Color("f0dfba"))
		npcs.append(npc)

func nearest_npc() -> Node3D:
	var found: Node3D
	var distance := 2.1
	for npc in npcs:
		if not is_instance_valid(npc): continue
		var d := player.position.distance_to(npc.position)
		if d<distance:
			distance=d
			found=npc
	return found

func talk_to(npc: Node3D) -> void:
	npc.face_point(player.position)
	var v := modal_card(npc.get_meta("title"))
	var role: String=npc.get_meta("role")
	if role in ["farmer","angler"]:
		text(v,"순무는 90초, 호박은 150초면 자라요.\n심은 뒤 물을 한 번 주고 마을을 돌아보세요.\n수확물과 물고기는 잎전으로 바꾸거나 식탁에 배달할 수 있어요." if role=="farmer" else "낚싯대와 물뿌리개는 준비되어 있어요. 미끼만 챙기세요!\n찌를 던지고 금빛 입질 신호가 오면 E로 당겨요.\n바다에는 은빛 도미가, 호수에는 강농어가 더 많아요.",17)
		button(v,"씨앗과 미끼 가게" if role=="farmer" else "낚시 도감과 생활 창고",life.open_shop if role=="farmer" else life.open_storage)
		return
	var words: String={"map":"숲을 지나면 뜨거운 채석장, 더 먼 곳에는 서리빛 분지가 있어요.\n처음이라면 산책 난이도로 길을 익혀 보세요.\n도전이 어려울수록 완주했을 때 받는 별씨도 늘어납니다.","wardrobe":"여행에도 나다운 옷차림이 필요하죠!\n머리와 옷, 바지, 신발 색을 따로 골라 보세요.\n외형은 생존 능력에 영향을 주지 않아요.","guide":"첫날에는 목재와 돌을 모아 도끼부터 만드세요.\n밤에는 모닥불 곁에서 몸을 녹이고, 빨간 공격 예고 밖으로 피하세요.\n이끼 수호자는 느리지만 강하고, 불씨 도깨비는 먼 곳에서도 공격해요.\n서리 지역에서는 식량과 땔감을 평소보다 넉넉히 준비하세요."}.get(role,"")
	var label := text(v,words,17)
	label.custom_minimum_size.y=160
	label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	if role=="map": button(v,"탐험 지도 펼치기",open_expedition)
	elif role=="wardrobe": button(v,"옷장 열기",open_wardrobe)
	else: button(v,"준비하러 가기",close_village_modal)

func open_wardrobe() -> void:
	if screen!="village": return
	var v := modal_card("나의 여행자")
	var editor := preload("res://scripts/wardrobe.gd").new()
	editor.avatar=me.get("profile",{}).get("avatar",{}).duplicate(true)
	v.add_child(editor)
	var status := text(v,"외형은 모든 지역에서 같게 유지됩니다. 능력치는 바뀌지 않습니다.",12)
	var save := button(v,"이 모습으로 저장",func():
		var result: Dictionary=await api.post("/v1/profile",api.mutation({"version":me.get("profile",{}).get("version",0),"avatar":editor.avatar}))
		if not is_instance_valid(editor): return
		if result.ok:
			me.profile=result.data
			player.apply_avatar(me.profile.avatar)
			close_village_modal()
			message("새로운 여행자 모습이 저장되었습니다.")
		else:
			status.text="저장하지 못했습니다. 옷장을 닫고 새로고침한 뒤 다시 시도하세요."
	)
	save.custom_minimum_size.y=42


func open_studio(destination: String="workshop") -> void:
	if busy or api.token.is_empty(): return
	Engine.set_meta("studio_session",{"token":api.token,"url":api.base_url,"room":destination})
	get_tree().change_scene_to_file("res://scenes/studio.tscn")

func nearest_furniture() -> String:
	var result := "";var distance := 2.3
	for id in loaded:
		var item: Node3D=loaded[id]
		if not is_instance_valid(item) or not item.get_meta("studio",false):continue
		var d: float=player.position.distance_to(item.position)
		if d<distance:distance=d;result=id
	return result

func village_furniture_event(id: String,event: String) -> void:
	if id.is_empty() or busy or refreshing or furniture_event_pending:return
	var item: Node3D=loaded.get(id)
	if not is_instance_valid(item) and selected.get("id")==id:item=inspect_model
	if not is_instance_valid(item) or not item.get_meta("studio",false):return
	furniture_event_pending=true
	var epoch := world_epoch
	var reply: Dictionary=await api.post("/v1/objects/"+id+"/event",api.mutation({"version":item.runtime_version,"event":event}))
	furniture_event_pending=false
	if epoch!=world_epoch:return
	if not reply.ok:
		if reply.get("status")==409:await refresh_inventory()
		else:message(error_message(reply.error))
		return
	if is_instance_valid(item):
		item.accept_event(reply.data)
		if event in ["near","leave"]:item.nearby=event=="near"
	if selected.get("id")==id and is_instance_valid(inspect_model) and inspect_model!=item:inspect_model.accept_event(reply.data)
	for obj in me.objects:
		if obj.id==id:obj.runtime_version=reply.data.version

func village_furniture_proximity() -> void:
	if furniture_event_pending or busy or refreshing or not is_instance_valid(player):return
	for id in loaded.keys():
		if not loaded.has(id):continue
		var item: Node3D=loaded[id]
		if not is_instance_valid(item) or not item.get_meta("studio",false):continue
		var near_now: bool=player.position.distance_to(item.position)<(2.5 if item.nearby else 1.8)
		if near_now!=item.nearby:await village_furniture_event(id,"near" if near_now else "leave")
