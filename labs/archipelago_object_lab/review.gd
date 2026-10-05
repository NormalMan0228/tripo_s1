extends Node3D

var camera: Camera3D
var azimuth := .55
var elevation := .38
var center := Vector3(0,3.7,0)
var capture := OS.get_cmdline_user_args().has("--capture-review")
var frame := 0
var spin := false
var help_layer: CanvasLayer
var spec: Dictionary
var full_size := 12.5
var full_center := Vector3(0,3.7,0)
var full_azimuth := .55
var building: Node3D
var explorer: Node3D
var label: Label
var selector: OptionButton
var gallery: Array = []
var gallery_index := 0
var validate_gallery := OS.get_cmdline_user_args().has("--validate-gallery")
var gallery_check_frame := 0
var gallery_checked := 0

func _ready() -> void:
	var spec_path := "res://active_review.json"
	var arguments := OS.get_cmdline_user_args()
	var asset_arg := arguments.find("--asset")
	if asset_arg >= 0 and asset_arg+1 < arguments.size():
		spec_path = "res://reviews/"+arguments[asset_arg+1]+".json"
	spec = JSON.parse_string(FileAccess.get_file_as_string(spec_path))
	var height: float = spec["height_m"]
	var width: float = spec["width_m"]
	full_size = maxf((width+3.6)/1.44,maxf(3.2,maxf(height*1.56,maxf(width*.95,float(spec.get("depth_m",0))*.78))))
	full_center = Vector3(0,maxf(height*.4625,.85),0)
	center = full_center
	full_azimuth = float(spec.get("initial_azimuth",.55))
	azimuth = full_azimuth
	DisplayServer.window_set_title("Tripothon — "+String(spec["name"])+" 검토")
	var world := WorldEnvironment.new()
	world.environment = Environment.new()
	var env := world.environment
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("e6e3d9")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("f3efdf")
	env.ambient_light_energy = .42
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	add_child(world)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-48,-28,0)
	light.light_color = Color("fff5e7")
	light.light_energy = 1.2
	light.shadow_enabled = true
	add_child(light)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-30,140,0)
	fill.light_color = Color("dfeeff")
	fill.light_energy = .35
	add_child(fill)
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(120,120)
	floor_mesh.mesh = plane
	var material := StandardMaterial3D.new()
	material.albedo_color = Color("d3d0c4")
	material.roughness = .9
	floor_mesh.material_override = material
	floor_mesh.position.y = -.025
	add_child(floor_mesh)
	explorer = load("res://assets/explorer_reference.glb").instantiate()
	add_child(explorer)
	var bounds := AABB()
	var first := true
	for item in explorer.find_children("*","MeshInstance3D",true,false):
		var m := item as MeshInstance3D
		var relative := explorer.global_transform.affine_inverse()*m.global_transform
		var b: AABB = relative*m.get_aabb()
		bounds = b if first else bounds.merge(b)
		first = false
	var factor := 1.7/bounds.size.y
	explorer.scale = Vector3.ONE*factor
	explorer.position = Vector3(-width*.5-1.4,0,1.3)-Vector3(bounds.get_center().x,bounds.position.y,bounds.get_center().z)*factor
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = full_size
	camera.near = .1
	camera.far = 500
	add_child(camera)
	help_layer = CanvasLayer.new()
	add_child(help_layer)
	var panel := PanelContainer.new()
	panel.position = Vector2(20,20)
	help_layer.add_child(panel)
	var margin := MarginContainer.new()
	for side in ["left","right","top","bottom"]:
		margin.add_theme_constant_override("margin_"+side,14)
	panel.add_child(margin)
	var layout := VBoxContainer.new()
	margin.add_child(layout)
	label = Label.new()
	label.text = "오브젝트 %s · %s\n건물 높이 %.1fm · 캐릭터 1.70m\n오른쪽 드래그: 회전 · 휠: 확대 · Space: 자동 회전\n1: 정면 · 2: 측면 · 3: 뒷면 · R: 전체 · H: 안내 숨기기" % [String(spec["asset"]).get_slice("_",0),String(spec["name"]),height]
	label.add_theme_font_size_override("font_size",19)
	layout.add_child(label)
	if not capture and FileAccess.file_exists("res://batch_review.json"):
		var batch: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://batch_review.json"))
		gallery = batch.get("assets",[])
		selector = OptionButton.new()
		selector.focus_mode = Control.FOCUS_NONE
		selector.add_theme_font_size_override("font_size",19)
		for i in range(gallery.size()):
			var entry: Dictionary = gallery[i]
			selector.add_item("%02d / %02d · %s" % [i+1,gallery.size(),entry["name"]])
			if entry["asset"] == spec["asset"]:
				gallery_index = i
		selector.select(gallery_index)
		selector.item_selected.connect(_select_asset)
		layout.add_child(selector)
	_show_asset(spec)
	if capture:
		help_layer.visible = false
	_update_camera()
	print("OBJECT_REVIEW_READY asset=",spec["asset"]," character_height_m=1.7")

func _show_asset(next_spec: Dictionary) -> void:
	if is_instance_valid(building):
		building.free()
	spec = next_spec
	building = ResourceLoader.load(String(spec["model"]),"PackedScene",ResourceLoader.CACHE_MODE_IGNORE).instantiate()
	add_child(building)
	var height: float = spec["height_m"]
	var width: float = spec["width_m"]
	explorer.position.x = -width*.5-1.4
	explorer.position.z = float(spec.get("depth_m",0))*.5+1.3 if spec.get("category", "building") == "bridge" else 1.3
	full_size = maxf((width+3.6)/1.44,maxf(3.2,maxf(height*1.56,maxf(width*.95,float(spec.get("depth_m",0))*.78))))
	full_center = Vector3(0,maxf(height*.4625,.85),0)
	center = full_center
	full_azimuth = float(spec.get("initial_azimuth",.55))
	azimuth = full_azimuth
	elevation = .38
	camera.size = full_size
	label.text = "%s · 높이 %.1fm · 캐릭터 1.70m\n오른쪽 드래그: 회전 · 휠: 확대 · Space: 자동 회전\n1/2/3: 정면/측면/뒷면 · R: 전체 · H: 안내 숨기기\n목록 또는 ← / → : 이전·다음 오브젝트" % [String(spec["name"]),height]
	DisplayServer.window_set_title("Tripothon — "+String(spec["name"])+" 검토")
	_update_camera()

func _select_asset(index: int) -> void:
	gallery_index = index
	selector.select(index)
	_show_asset(gallery[index])
	print("OBJECT_REVIEW_SELECTED ",spec["asset"])

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		azimuth -= event.relative.x*.005
		elevation = clampf(elevation+event.relative.y*.004,-.12,1.4)
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			camera.size = maxf(.4,camera.size*.88)
		if event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			camera.size = minf(30,camera.size/.88)
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode in [KEY_LEFT,KEY_RIGHT] and gallery.size()>0:
			var step := -1 if event.keycode == KEY_LEFT else 1
			_select_asset(posmod(gallery_index+step,gallery.size()))
		if event.keycode == KEY_SPACE:
			spin = not spin
		if event.keycode in [KEY_1,KEY_2,KEY_3]:
			azimuth = 0 if event.keycode == KEY_1 else (PI*.5 if event.keycode == KEY_2 else PI)
			elevation = .22
		if event.keycode == KEY_R:
			center = full_center
			camera.size = full_size
			azimuth = full_azimuth
			elevation = .38
		if event.keycode == KEY_H:
			help_layer.visible = not help_layer.visible
		if event.keycode == KEY_ESCAPE:
			get_tree().quit()
	_update_camera()

func _update_camera() -> void:
	camera.position = center+Vector3(sin(azimuth)*cos(elevation),sin(elevation),cos(azimuth)*cos(elevation))*30
	camera.look_at(center)

func _save_view(name: String) -> void:
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	image.save_png(ProjectSettings.globalize_path(String(spec["out"])+String(spec["stem"])+"_"+name+".png"))
	print("OBJECT_REVIEW_CAPTURE ",name)

func _process(delta: float) -> void:
	if validate_gallery:
		gallery_check_frame += 1
		if gallery_check_frame % 45 == 1 and gallery_checked < gallery.size():
			_select_asset(gallery_checked)
			gallery_checked += 1
		if gallery_checked == gallery.size() and gallery_check_frame > gallery.size()*45:
			print("BATCH_GALLERY_LOAD_COMPLETE count=",gallery_checked)
			get_tree().quit()
	if spin:
		azimuth += delta*.35
		_update_camera()
	if not capture:
		return
	frame += 1
	if frame == 60:
		_save_view.call_deferred("front")
	if frame == 70:
		azimuth = PI
		elevation = .25
		_update_camera()
	if frame == 110:
		_save_view.call_deferred("back")
	if frame == 120:
		azimuth = PI*.5
		_update_camera()
	if frame == 160:
		_save_view.call_deferred("side")
	if frame == 170:
		azimuth = 0
		elevation = .05
		center = Vector3(0,float(spec["height_m"])*.2625,0)
		camera.size = float(spec["height_m"])*.6875
		_update_camera()
	if frame == 210:
		_save_view.call_deferred("entrance")
	if frame == 220:
		print("OBJECT_REVIEW_CAPTURE_COMPLETE")
		get_tree().quit()
