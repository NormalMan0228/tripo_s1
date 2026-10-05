extends Node3D

const PlayerScript = preload("res://scripts/player.gd")
const ModelLoader = preload("res://scripts/model_loader.gd")
const SAMPLE := "res://assets/sample_stool.glb"
const COLORS := [Color("f6eee0"), Color("e9b959"), Color("de806b"), Color("70afa3"), Color("7c9ec6")]
var player: CharacterBody3D
var camera: Camera3D
var preview: Node3D
var selected_color := COLORS[0]
var placed: Array[Node3D] = []
var occupied: Array[Rect2] = []
var status: Label
var count_label: Label
var cursor_valid := false

func _ready() -> void:
	_setup_input()
	_build_world()
	_build_ui()

func _setup_input() -> void:
	var bindings := {
		"move_left": [KEY_A, KEY_LEFT], "move_right": [KEY_D, KEY_RIGHT],
		"move_forward": [KEY_W, KEY_UP], "move_back": [KEY_S, KEY_DOWN]
	}
	for action in bindings:
		if not InputMap.has_action(action):
			InputMap.add_action(action)
		for key in bindings[action]:
			var event := InputEventKey.new()
			event.physical_keycode = key
			InputMap.action_add_event(action, event)

func _box(parent: Node3D, at: Vector3, size: Vector3, color: Color, solid := false) -> void:
	var mesh := MeshInstance3D.new()
	var cube := BoxMesh.new()
	cube.size = size
	mesh.mesh = cube
	mesh.position = at
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 1.0
	mesh.material_override = material
	parent.add_child(mesh)
	if solid:
		var body := StaticBody3D.new()
		var collision := CollisionShape3D.new()
		var shape := BoxShape3D.new()
		shape.size = size
		collision.shape = shape
		body.position = at
		body.add_child(collision)
		parent.add_child(body)

func _build_world() -> void:
	var world := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("b5d5db")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color.WHITE
	environment.ambient_light_energy = 0.55
	world.environment = environment
	add_child(world)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-55, -30, 0)
	sun.light_color = Color.WHITE
	sun.light_energy = 0.3
	sun.shadow_enabled = true
	add_child(sun)
	_box(self, Vector3(0, -0.3, 0), Vector3(24, 0.6, 24), Color("9eae77"), true)
	_box(self, Vector3(0, 0.008, 0), Vector3(2.8, 0.016, 23), Color("d7c7a3"))
	_box(self, Vector3(0, 0.014, -3), Vector3(17, 0.018, 2.5), Color("d7c7a3"))
	for at in [Vector3(-12, 0.8, 0), Vector3(12, 0.8, 0)]:
		_box(self, at, Vector3(0.35, 1.6, 24), Color("748768"), true)
	for at in [Vector3(0, 0.8, -12), Vector3(0, 0.8, 12)]:
		_box(self, at, Vector3(24, 1.6, 0.35), Color("748768"), true)
	_box(self, Vector3(-5, 1.4, -6), Vector3(4, 2.8, 3.3), Color("edd9b3"), true)
	_box(self, Vector3(-5, 3.0, -6), Vector3(4.6, 0.5, 3.9), Color("b96d5c"))
	_box(self, Vector3(-5, 0.85, -4.32), Vector3(0.85, 1.7, 0.08), Color("69877d"))
	occupied.append(Rect2(-7.2, -8.0, 4.4, 3.9))
	for at in [Vector3(-9, 0, -2), Vector3(-9, 0, 5), Vector3(-6, 0, 8), Vector3(8, 0, -8), Vector3(9, 0, 2), Vector3(7, 0, 8)]:
		_tree(at)
	_box(self, Vector3(5, 0.4, -5), Vector3(2.6, 0.8, 2.6), Color("748c8b"), true)
	_box(self, Vector3(5, 1.3, -5), Vector3(1.4, 1.0, 1.4), Color("abbdb4"))
	occupied.append(Rect2(3.5, -6.5, 3.0, 3.0))
	player = PlayerScript.new()
	player.name = "Player"
	player.position = Vector3(0, 0.1, 4)
	add_child(player)
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 17
	camera.current = true
	add_child(camera)
	_follow_camera()

func _tree(at: Vector3) -> void:
	_box(self, at + Vector3(0, 0.8, 0), Vector3(0.55, 1.6, 0.55), Color("957956"), true)
	var mesh := MeshInstance3D.new()
	var canopy := SphereMesh.new()
	canopy.radius = 1.2
	canopy.height = 2.6
	canopy.radial_segments = 10
	canopy.rings = 5
	mesh.mesh = canopy
	mesh.position = at + Vector3(0, 2.4, 0)
	var material := StandardMaterial3D.new()
	material.albedo_color = Color("5e8a72")
	material.roughness = 1.0
	mesh.material_override = material
	add_child(mesh)
	occupied.append(Rect2(Vector2(at.x - 1.2, at.z - 1.2), Vector2(2.4, 2.4)))

func _build_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var panel := PanelContainer.new()
	panel.position = Vector2(24, 24)
	panel.custom_minimum_size = Vector2(300, 0)
	var style := StyleBoxFlat.new()
	style.bg_color = Color("f7f2e9")
	style.set_corner_radius_all(14)
	style.content_margin_left = 20
	style.content_margin_right = 20
	style.content_margin_top = 18
	style.content_margin_bottom = 18
	panel.add_theme_stylebox_override("panel", style)
	var font := SystemFont.new()
	font.font_names = PackedStringArray(["Malgun Gothic", "sans-serif"])
	var theme := Theme.new()
	theme.default_font = font
	theme.default_font_size = 15
	theme.set_color("font_color", "Label", Color("263f3a"))
	theme.set_color("font_color", "Button", Color("f7f2e9"))
	panel.theme = theme
	layer.add_child(panel)
	var rows := VBoxContainer.new()
	rows.add_theme_constant_override("separation", 12)
	panel.add_child(rows)
	var title := Label.new()
	title.text = tr("나의 작은 마을")
	title.add_theme_font_size_override("font_size", 25)
	rows.add_child(title)
	var subtitle := Label.new()
	subtitle.text = tr("첫 제작 테스트 · 샘플 모드\nWASD / 방향키로 걷기")
	rows.add_child(subtitle)
	var create := Button.new()
	create.text = tr("샘플 의자 불러오기")
	create.custom_minimum_size.y = 42
	create.focus_mode = Control.FOCUS_NONE
	create.pressed.connect(begin_sample)
	rows.add_child(create)
	var palette := HBoxContainer.new()
	rows.add_child(palette)
	var names := [tr("크림"), tr("노랑"), tr("분홍"), tr("초록"), tr("파랑")]
	for i in COLORS.size():
		var color: Color = COLORS[i]
		var button := Button.new()
		button.text = names[i]
		button.modulate = color
		button.focus_mode = Control.FOCUS_NONE
		button.pressed.connect(func() -> void: set_paint(color))
		palette.add_child(button)
	status = Label.new()
	status.custom_minimum_size.x = 260
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status.text = tr("의자를 불러와 색을 고르고, 마을 바닥을 클릭해 놓아 보세요.")
	rows.add_child(status)
	var hint := Label.new()
	hint.text = tr("마우스: 놓을 위치 선택\nR: 회전 · Esc: 배치 취소\nBackspace: 마지막 배치 회수")
	rows.add_child(hint)
	count_label = Label.new()
	count_label.text = tr("놓은 물건 0 / 30")
	rows.add_child(count_label)
	var footer := Label.new()
	footer.text = tr("API 사용·비용 없음\n지금 놓은 물건은 종료하면 초기화됩니다.\n생존 도전·생성·거래는 다음 제작 단계입니다.")
	footer.add_theme_font_size_override("font_size", 12)
	rows.add_child(footer)

func _follow_camera() -> void:
	var target := player.position + Vector3(0, 0.6, -2)
	camera.position = target + Vector3(0, 15, 12)
	camera.look_at(target)

func _process(_delta: float) -> void:
	_follow_camera()
	if preview == null:
		return
	var mouse := get_viewport().get_mouse_position()
	var hit: Variant = Plane(Vector3.UP, 0).intersects_ray(camera.project_ray_origin(mouse), camera.project_ray_normal(mouse))
	cursor_valid = hit != null
	if cursor_valid:
		var point: Vector3 = hit
		preview.position = Vector3(snappedf(point.x, 0.5), 0.02, snappedf(point.z, 0.5))
		cursor_valid = can_place(preview)
	status.text = tr("클릭하면 배치합니다. R로 회전할 수 있어요.") if cursor_valid else tr("비어 있는 마을 바닥을 선택해 주세요.")

func begin_sample() -> void:
	if placed.size() >= 30:
		status.text = tr("이번 테스트에서는 30개까지 놓을 수 있어요.")
		return
	cancel_preview()
	preview = ModelLoader.load_sample(SAMPLE)
	if preview == null:
		status.text = tr("샘플 GLB를 읽지 못했습니다. 파일을 확인해 주세요.")
		return
	add_child(preview)
	ModelLoader.paint(preview, selected_color)
	player.controls_enabled = false

func set_paint(color: Color) -> void:
	selected_color = color
	if preview != null:
		ModelLoader.paint(preview, color)

func footprint(object: Node3D) -> Rect2:
	var size: Vector3 = object.get_meta("size")
	var bounds: AABB = object.transform * AABB(Vector3(-size.x / 2, 0, -size.z / 2), size)
	return Rect2(Vector2(bounds.position.x, bounds.position.z), Vector2(bounds.size.x, bounds.size.z)).grow(0.12)

func can_place(object: Node3D) -> bool:
	var area := footprint(object)
	if not Rect2(-11.5, -11.5, 23, 23).encloses(area):
		return false
	if area.grow(0.4).has_point(Vector2(player.position.x, player.position.z)):
		return false
	for blocker in occupied:
		if area.intersects(blocker):
			return false
	for decoration in placed:
		if area.intersects(footprint(decoration)):
			return false
	return true

func place_preview() -> bool:
	if preview == null or not can_place(preview):
		return false
	ModelLoader.add_collision(preview)
	placed.append(preview)
	preview = null
	player.controls_enabled = true
	count_label.text = tr("놓은 물건 %d / 30") % placed.size()
	status.text = tr("배치 완료! 걸어가서 확인해 보세요. 다음 의자는 다른 색으로 놓을 수 있어요.")
	return true

func cancel_preview() -> void:
	if preview != null:
		preview.queue_free()
		preview = null
	player.controls_enabled = true

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		match event.physical_keycode:
			KEY_ESCAPE:
				cancel_preview()
				status.text = tr("배치를 취소했습니다. 마을을 걸어 다닐 수 있어요.")
			KEY_R:
				if preview != null:
					preview.rotate_y(PI / 2)
			KEY_BACKSPACE:
				if not placed.is_empty():
					var last: Node3D = placed.pop_back()
					last.queue_free()
					count_label.text = tr("놓은 물건 %d / 30") % placed.size()
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		if preview != null and cursor_valid:
			place_preview()
