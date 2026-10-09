extends RefCounted

static func load_sample(path: String) -> Node3D:
	var bytes := FileAccess.get_file_as_bytes(path)
	return load_bytes(bytes)

# Downloaded models stay in memory. The server validates GLB before publishing it.
static func load_bytes(bytes: PackedByteArray) -> Node3D:
	if bytes.is_empty() or bytes.size() > 20 * 1024 * 1024:
		return null
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	if document.append_from_buffer(bytes, "", state) != OK:
		return null
	var imported := document.generate_scene(state) as Node3D
	if imported == null:
		return null
	var meshes: Array[MeshInstance3D] = []
	_collect_meshes(imported, meshes)
	if meshes.is_empty():
		imported.free()
		return null
	# The model's own surfaces (painter slots); markers added later are not painted.
	for instance in meshes: instance.set_meta("craft_surface", true)
	shrink_textures(imported)
	var bounds := AABB()
	var first := true
	for instance in meshes:
		var transform := _local_transform(instance, imported)
		var mesh_bounds: AABB = transform * instance.get_aabb()
		bounds = mesh_bounds if first else bounds.merge(mesh_bounds)
		first = false
	var longest: float = maxf(bounds.size.x, maxf(bounds.size.y, bounds.size.z))
	if not is_finite(longest) or longest < 0.001:
		imported.free()
		return null
	var root := Node3D.new()
	root.name = "SampleDecoration"
	var pivot := Node3D.new()
	root.add_child(pivot)
	pivot.add_child(imported)
	var factor := 1.6 / longest
	pivot.scale = Vector3.ONE * factor
	pivot.position = -Vector3(bounds.get_center().x, bounds.position.y, bounds.get_center().z) * factor
	root.set_meta("size", bounds.size * factor)
	root.set_meta("paint", Color.WHITE)
	paint(root, Color.WHITE)
	return root

static func _local_transform(node: Node3D, imported: Node3D) -> Transform3D:
	var result := node.transform
	var current := node
	while current != imported:
		current = current.get_parent() as Node3D
		if current == null:
			break
		result = current.transform * result
	return result

## Tripo-coloured crafts arrive with three 2048 px maps (colour, normal, ORM): kept as they are that
## is roughly 67 MB of video memory per object and a decode hitch. Downloaded models are scaled to fit
## `limit` px and, where the renderer supports it, block-compressed (S3TC on PC, ETC2 elsewhere), about
## an eighth of the memory. Normal maps are only scaled (their compressed form needs a different shader
## path). Authored game assets are imported by the editor and never pass through here.
const TEXTURE_LIMIT := 1024
static var compressor_warm := false
## Godot's release templates ship without the block compressor (compressing there only logs
## "_image_compress_bc_func is null"), so exported games keep the scaled image (about a quarter of the
## memory); editor and source runs also compress.
static var compressor_ok := not OS.has_feature("template")

## The first block compression in a session spends about a second setting up (later ones take ~5 ms).
## Main and the room scene call this while their loading veil is up, so the first crafted model does not
## stall. It must run on the main thread: compressing on a worker thread crashed the engine (4.7.2).
static func warm_up_compression() -> void:
	if compressor_warm or not compressor_ok: return
	compressor_warm = true
	var image := Image.create(64, 64, false, Image.FORMAT_RGB8)
	var format := _block_format()
	if format >= 0 and image.compress(format) != OK: compressor_ok = false

static func _block_format() -> int:
	if RenderingServer.has_os_feature("s3tc"): return Image.COMPRESS_S3TC
	if RenderingServer.has_os_feature("etc2"): return Image.COMPRESS_ETC2
	return -1

static func shrink_textures(root: Node, limit := TEXTURE_LIMIT) -> Dictionary:
	var stats := {"textures": 0, "resized": 0, "compressed": 0, "bytes_before": 0, "bytes_after": 0}
	var replaced := {}
	var meshes: Array[MeshInstance3D] = []
	_collect_meshes(root, meshes)
	for instance in meshes:
		if instance.mesh == null: continue
		for surface in instance.mesh.get_surface_count():
			for material in [instance.mesh.surface_get_material(surface), instance.get_surface_override_material(surface)]:
				if not material is BaseMaterial3D: continue
				for param in BaseMaterial3D.TEXTURE_MAX:
					var texture: Texture2D = material.get_texture(param)
					if texture == null: continue
					if not replaced.has(texture):
						replaced[texture] = _shrink_texture(texture, limit, param == BaseMaterial3D.TEXTURE_NORMAL, stats)
					if replaced[texture] != null: material.set_texture(param, replaced[texture])
	return stats

static func _shrink_texture(texture: Texture2D, limit: int, normal: bool, stats: Dictionary) -> Texture2D:
	var image := texture.get_image()
	if image == null or image.is_empty(): return null
	stats.textures += 1
	stats.bytes_before += image.get_data().size()
	if image.is_compressed() and image.decompress() != OK: return null
	var longest := maxi(image.get_width(), image.get_height())
	var scale := minf(1.0, float(limit) / longest)
	# Block compression wants both sides divisible by 4.
	var width := maxi(4, int(round(image.get_width() * scale / 4.0)) * 4)
	var height := maxi(4, int(round(image.get_height() * scale / 4.0)) * 4)
	if width != image.get_width() or height != image.get_height():
		# Bilinear: an exact halving looks the same as Lanczos at a tenth of the time (15 vs 116 ms).
		image.resize(width, height, Image.INTERPOLATE_BILINEAR)
		stats.resized += 1
	image.generate_mipmaps()
	var format := _block_format()
	if not normal and compressor_ok and format >= 0:
		# Runtime compression can be missing from a build; the scaled image is used then.
		if image.compress(format, Image.COMPRESS_SOURCE_GENERIC) == OK: stats.compressed += 1
		else: compressor_ok = false
	stats.bytes_after += image.get_data().size()
	return ImageTexture.create_from_image(image)

static func _collect_meshes(node: Node, result: Array[MeshInstance3D]) -> void:
	if node is MeshInstance3D and node.mesh != null:
		result.append(node)
	for child in node.get_children():
		_collect_meshes(child, result)

## Whole-object colour. Surfaces carrying a painted texture (painter/paint_apply.gd sets
## "paint_textures") keep it; a placement marker added under the model is left alone.
static func paint(root: Node3D, color: Color) -> void:
	var meshes: Array[MeshInstance3D] = []
	_collect_meshes(root, meshes)
	var tagged: Array[MeshInstance3D] = []
	for instance in meshes:
		if instance.has_meta("craft_surface"): tagged.append(instance)
	if not tagged.is_empty(): meshes = tagged
	for instance in meshes:
		var painted: Array = instance.get_meta("paint_textures", [])
		if not painted.is_empty():
			instance.material_override = null
			for surface in instance.mesh.get_surface_count():
				var textured := StandardMaterial3D.new()
				textured.roughness = 0.9
				if surface < painted.size() and painted[surface] != null: textured.albedo_texture = painted[surface]
				else: textured.albedo_color = color
				instance.set_surface_override_material(surface, textured)
			continue
		var material := StandardMaterial3D.new()
		material.albedo_color = color
		material.roughness = 0.9
		instance.material_override = material
	root.set_meta("paint", color)

static func add_collision(root: Node3D) -> void:
	var size: Vector3 = root.get_meta("size")
	var body := StaticBody3D.new()
	# Furniture blocks walkers but is not ground for height probes or placement.
	body.collision_layer = 16
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	shape.shape = box
	shape.position.y = size.y / 2.0
	body.add_child(shape)
	root.add_child(body)
