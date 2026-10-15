extends RefCounted
## Frames an orthographic preview camera on a model that stands at the origin (bottom at y = 0, centred
## on x/z) with the box `size` (asset_assembly.gd's "size" meta), so wide, deep and tall objects show
## whole instead of losing their top or front edge (task 73). The camera keeps its viewing direction.
##   PreviewFrame.fit(camera, model.get_meta("size", Vector3.ZERO))

## The first camera directly under `stage` (the village inspector builds its own), or null.
static func camera_in(stage: Node) -> Camera3D:
	if stage == null: return null
	for child in stage.get_children():
		if child is Camera3D: return child
	return null

static func fit(camera: Camera3D, size: Vector3, margin := 1.18) -> void:
	if camera == null or size.length() < 0.01: return
	var target := Vector3(0, size.y * 0.5, 0)
	var direction := camera.position - target
	if direction.length() < 0.01: direction = Vector3(2, 1.1, 3)
	direction = direction.normalized()
	var place := target + direction * maxf(6.0, size.length() * 3.0)
	var basis := Basis.looking_at(target - place, Vector3.UP)
	camera.transform = Transform3D(basis, place)
	# The box's corners seen from the camera: half its width and height on screen.
	var half_x := 0.0
	var half_y := 0.0
	for i in 8:
		var corner := Vector3(float(i & 1) - 0.5, float((i >> 1) & 1) - 0.5, float((i >> 2) & 1) - 0.5) * size
		half_x = maxf(half_x, absf(corner.dot(basis.x)))
		half_y = maxf(half_y, absf(corner.dot(basis.y)))
	var aspect := 1.0
	if camera.is_inside_tree():
		var view := camera.get_viewport().get_visible_rect().size
		if view.y > 0.0: aspect = view.x / view.y
	camera.size = maxf(0.6, maxf(2.0 * half_y, 2.0 * half_x / aspect) * margin)
