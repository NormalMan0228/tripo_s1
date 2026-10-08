extends SubViewportContainer
## The painter's 3D view: the object in its own world, lit by a headlight, with every
## surface drawn by paint_display.gdshader from the painter's layers. Right-drag (or
## Alt/Space + left-drag) orbits, middle-drag (or Shift + right-drag) pans, the wheel zooms.
## Left-button presses and moves go out through paint_event for the tools; the overlay draws
## the brush outline and the gradient line.
signal paint_event(event: InputEvent)

const Loader = preload("res://scripts/model_loader.gd")
const DISPLAY = preload("res://scripts/painter/paint_display.gdshader")
const FOV := 35.0

var port: SubViewport
var camera: Camera3D
var world_root: Node3D
var overlay: Control
var materials: Array[ShaderMaterial] = []
var textures := {}          # Core.Layer -> {texture: ImageTexture, revision: int}
var backdrop_texture: ImageTexture
var binding := ""
var size_px := 1024
var bounds := AABB(Vector3(-0.5, 0, -0.5), Vector3.ONE)
var target := Vector3.ZERO
var yaw := 0.65
var pitch := -0.32
var distance := 3.0
var orbiting := false
var panning := false
var cursor := Vector2(-100, -100)
var cursor_inside := false
var cursor_radius := 10.0
var cursor_kind := "brush"   # brush, cross, none
var line_from := Vector2.ZERO
var line_to := Vector2.ZERO
var line_visible := false

func _ready() -> void:
	stretch = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	# Keys stay with the workspace (shortcuts), never the view.
	focus_mode = Control.FOCUS_NONE
	mouse_default_cursor_shape = Control.CURSOR_CROSS
	port = SubViewport.new()
	port.own_world_3d = true
	port.msaa_3d = Viewport.MSAA_4X
	port.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(port)
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("2a3134")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color.WHITE
	environment.ambient_light_energy = 0.55
	environment.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var world_environment := WorldEnvironment.new()
	world_environment.environment = environment
	port.add_child(world_environment)
	camera = Camera3D.new()
	camera.fov = FOV
	camera.near = 0.01
	camera.far = 200.0
	port.add_child(camera)
	camera.current = true
	# A headlight keeps the side being painted lit; a soft top light gives it shape.
	var headlight := DirectionalLight3D.new()
	headlight.light_energy = 0.75
	headlight.rotation_degrees = Vector3(-12, 8, 0)
	camera.add_child(headlight)
	var top := DirectionalLight3D.new()
	top.light_energy = 0.3
	top.rotation_degrees = Vector3(-70, -30, 0)
	port.add_child(top)
	world_root = Node3D.new()
	port.add_child(world_root)
	overlay = Control.new()
	overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	overlay.draw.connect(_draw_overlay)
	add_child(overlay)
	mouse_entered.connect(func(): cursor_inside = true; overlay.queue_redraw())
	mouse_exited.connect(func(): cursor_inside = false; overlay.queue_redraw())

## Shows a copy of the model's surfaces (shared meshes, current pose) with one display
## material per slot; atlas tiles come from the core.
func show_model(model: Node3D, slots: Array, core) -> void:
	size_px = core.size
	for child in world_root.get_children(): child.queue_free()
	materials.clear()
	var copies := {}
	for k in slots.size():
		var source: MeshInstance3D = slots[k].mesh
		var s: int = slots[k].surface
		if not copies.has(source):
			var copy := MeshInstance3D.new()
			copy.mesh = source.mesh
			copy.transform = Loader._local_transform(source, model)
			world_root.add_child(copy)
			copies[source] = copy
		var material := ShaderMaterial.new()
		material.shader = DISPLAY
		var rect: Rect2i = core.slot_rects[k]
		material.set_shader_parameter("tile", Vector4(float(rect.size.x) / size_px, float(rect.size.y) / size_px, float(rect.position.x) / size_px, float(rect.position.y) / size_px))
		var original := source.get_active_material(s)
		if original is BaseMaterial3D and original.normal_enabled and original.normal_texture != null:
			material.set_shader_parameter("normal_texture", original.normal_texture)
			material.set_shader_parameter("normal_amount", original.normal_scale)
		if original is BaseMaterial3D: material.set_shader_parameter("roughness_value", clampf(original.roughness, 0.3, 1.0))
		(copies[source] as MeshInstance3D).set_surface_override_material(s, material)
		materials.append(material)
	bounds = core.bounds
	var image := Image.create_from_data(size_px, size_px, false, Image.FORMAT_RGBA8, core.backdrop)
	backdrop_texture = ImageTexture.create_from_image(image)
	for material in materials: material.set_shader_parameter("backdrop", backdrop_texture)
	binding = ""
	textures.clear()
	sync(core)
	reset_view()

## Uploads layers whose pixels changed and rebinds the shader when the stack changed.
func sync(core) -> void:
	if materials.is_empty(): return
	var present := {}
	for layer in core.layers:
		present[layer] = true
		var entry: Dictionary = textures.get(layer, {})
		if entry.is_empty() or int(entry.revision) != layer.revision:
			var image := Image.create_from_data(size_px, size_px, false, Image.FORMAT_RGBA8, layer.data)
			if entry.is_empty():
				entry = {"texture": ImageTexture.create_from_image(image), "revision": layer.revision}
				textures[layer] = entry
				binding = ""
			else:
				(entry.texture as ImageTexture).update(image)
				entry.revision = layer.revision
	for layer in textures.keys():
		if not present.has(layer): textures.erase(layer)
	var opacity := PackedFloat32Array(); opacity.resize(8)
	var modes := PackedInt32Array(); modes.resize(8)
	var signature := ""
	for i in core.layers.size():
		var layer = core.layers[i]
		opacity[i] = layer.opacity if layer.visible else 0.0
		modes[i] = layer.mode
		signature += "%d:%s;" % [layer.get_instance_id(), str(textures[layer].texture.get_rid())]
	signature += str(opacity) + str(modes)
	if signature == binding: return
	binding = signature
	for material in materials:
		material.set_shader_parameter("layer_count", core.layers.size())
		material.set_shader_parameter("opacity", opacity)
		material.set_shader_parameter("modes", modes)
		for i in 8:
			material.set_shader_parameter("layer%d" % i, textures[core.layers[i]].texture if i < core.layers.size() else null)

func reset_view() -> void:
	target = bounds.get_center()
	var radius := maxf(bounds.size.length() * 0.5, 0.05)
	distance = radius / sin(deg_to_rad(FOV * 0.5)) * 1.12
	yaw = 0.65
	pitch = -0.32
	_place_camera()

func _place_camera() -> void:
	var basis := Basis.from_euler(Vector3(pitch, yaw, 0.0))
	camera.position = target + basis * Vector3(0, 0, distance)
	camera.look_at(target, Vector3.UP)
	camera.near = maxf(distance * 0.01, 0.005)

## Object-space ray through a point of the view.
func ray(at: Vector2) -> Array:
	return [camera.project_ray_origin(at), camera.project_ray_normal(at)]

## World units per screen pixel at a point (brush sizes are in screen pixels).
func world_per_pixel(point: Vector3) -> float:
	var depth := maxf((point - camera.global_position).dot(-camera.global_transform.basis.z), 0.001)
	return 2.0 * depth * tan(deg_to_rad(FOV * 0.5)) / maxf(1.0, float(port.size.y))

func camera_right() -> Vector3:
	return camera.global_transform.basis.x.normalized()

func camera_up() -> Vector3:
	return camera.global_transform.basis.y.normalized()

## Where a view ray meets the plane through `point` facing the camera.
func plane_point(at: Vector2, point: Vector3) -> Vector3:
	var r := ray(at)
	var normal := camera.global_transform.basis.z
	var denom: float = (r[1] as Vector3).dot(normal)
	if absf(denom) < 1e-6: return point
	return r[0] + r[1] * ((point - (r[0] as Vector3)).dot(normal) / denom)

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		cursor = event.position
		overlay.queue_redraw()
	if event is InputEventMouseButton:
		var orbit_keys: bool = event.alt_pressed or Input.is_key_pressed(KEY_SPACE)
		match event.button_index:
			MOUSE_BUTTON_RIGHT:
				if event.shift_pressed: panning = event.pressed
				else: orbiting = event.pressed
				if not event.pressed: panning = false
				accept_event(); return
			MOUSE_BUTTON_MIDDLE:
				panning = event.pressed
				accept_event(); return
			MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN:
				if event.pressed:
					var factor := 0.88 if event.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0 / 0.88
					var radius := maxf(bounds.size.length() * 0.5, 0.05)
					distance = clampf(distance * factor, radius * 0.25, radius * 12.0)
					_place_camera()
				accept_event(); return
			MOUSE_BUTTON_LEFT:
				if event.pressed and orbit_keys and not event.is_command_or_control_pressed():
					orbiting = true
					accept_event(); return
				if not event.pressed and orbiting and not Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
					orbiting = false
					accept_event(); return
	if event is InputEventMouseMotion and (orbiting or panning):
		if orbiting:
			yaw -= event.relative.x * 0.008
			pitch = clampf(pitch - event.relative.y * 0.008, -1.45, 1.45)
		else:
			var scale := world_per_pixel(target)
			target += (-camera_right() * event.relative.x + camera_up() * event.relative.y) * scale
		_place_camera()
		accept_event()
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT or event is InputEventMouseMotion:
		paint_event.emit(event)
		accept_event()

func _draw_overlay() -> void:
	if line_visible:
		overlay.draw_line(line_from, line_to, Color(0, 0, 0, 0.6), 4.0, true)
		overlay.draw_line(line_from, line_to, Color("ffe08a"), 2.0, true)
		overlay.draw_circle(line_from, 4.0, Color("ffe08a"))
		overlay.draw_arc(line_to, 5.0, 0, TAU, 16, Color("ffe08a"), 2.0, true)
	if not cursor_inside or orbiting or panning: return
	if cursor_kind == "brush":
		var r := maxf(cursor_radius, 1.5)
		overlay.draw_arc(cursor, r, 0, TAU, maxi(24, int(r)), Color(0, 0, 0, 0.55), 2.6, true)
		overlay.draw_arc(cursor, r, 0, TAU, maxi(24, int(r)), Color(1, 1, 1, 0.9), 1.2, true)
	elif cursor_kind == "cross":
		for d in [Vector2(1, 0), Vector2(0, 1)]:
			overlay.draw_line(cursor - d * 9, cursor + d * 9, Color(0, 0, 0, 0.6), 3.0)
			overlay.draw_line(cursor - d * 9, cursor + d * 9, Color.WHITE, 1.2)
