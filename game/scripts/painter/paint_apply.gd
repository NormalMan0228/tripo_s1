extends RefCounted
## Painted textures on crafted objects wherever they appear (village, rooms, visits) and the
## mesh/look data the painter starts from.
##
## One saved PNG per object (server: /v1/objects/{id}/paint, guests: the social route). Its
## atlas has one square tile per mesh surface ("slot"), in slots_of() order; a single-surface
## object uses the whole image. After a model is loaded, attach() fetches the paint for the
## object's paint_version (cached by object and version) and puts each tile on its surface as
## the albedo texture (colour white, so part tints do not dye it). Normal and ORM maps stay.
const Loader = preload("res://scripts/model_loader.gd")
const Core = preload("res://scripts/painter/paint_core.gd")
const SIZE := 1024
const MAX_IMAGES := 6
const MAX_TEXTURE_SETS := 48

static var images := {}
static var image_order: Array[String] = []
static var texture_sets := {}
static var texture_order: Array[String] = []

# ------------------------------------------------------------------ slots

## Painted surfaces in a fixed order: a studio assembly by manifest part, then mesh, then
## surface; a single model by mesh order. [{mesh, surface, part}]
static func slots_of(root: Node) -> Array:
	var out := []
	if root == null: return out
	if root.get_meta("studio", false) and "manifest" in root and "surfaces" in root:
		var manifest: Dictionary = root.manifest
		var surfaces: Dictionary = root.surfaces
		for part in manifest.get("plan", {}).get("parts", []):
			var id := str(part.get("id", ""))
			for mesh in surfaces.get(id, []):
				if not is_instance_valid(mesh) or mesh.mesh == null: continue
				for s in mesh.mesh.get_surface_count(): out.append({"mesh": mesh, "surface": s, "part": id})
		return out
	for mesh in craft_meshes(root):
		for s in mesh.mesh.get_surface_count(): out.append({"mesh": mesh, "surface": s, "part": ""})
	return out

## The model's own meshes (load_bytes tags them), not markers added later (a placement disc).
static func craft_meshes(root: Node) -> Array[MeshInstance3D]:
	var meshes: Array[MeshInstance3D] = []
	Loader._collect_meshes(root, meshes)
	var tagged: Array[MeshInstance3D] = []
	for mesh in meshes:
		if mesh.has_meta("craft_surface"): tagged.append(mesh)
	return tagged if not tagged.is_empty() else meshes

## Core.setup() input: each slot's triangles in the root's space.
static func mesh_slots(root: Node3D) -> Array:
	var out := []
	for slot in slots_of(root):
		var mesh: MeshInstance3D = slot.mesh
		var s: int = slot.surface
		var entry := {"vertices": PackedVector3Array(), "normals": PackedVector3Array(), "uvs": PackedVector2Array(), "indices": PackedInt32Array()}
		if mesh.mesh.surface_get_primitive_type(s) == Mesh.PRIMITIVE_TRIANGLES:
			var arrays := mesh.mesh.surface_get_arrays(s)
			var xf := Loader._local_transform(mesh, root)
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			entry.vertices = xf * vertices
			if arrays[Mesh.ARRAY_NORMAL] is PackedVector3Array:
				var normal_xf := Transform3D(xf.basis.inverse().transposed(), Vector3.ZERO)
				entry.normals = normal_xf * (arrays[Mesh.ARRAY_NORMAL] as PackedVector3Array)
			if arrays[Mesh.ARRAY_TEX_UV] is PackedVector2Array: entry.uvs = arrays[Mesh.ARRAY_TEX_UV]
			if arrays[Mesh.ARRAY_INDEX] is PackedInt32Array: entry.indices = arrays[Mesh.ARRAY_INDEX]
		out.append(entry)
	return out

## Every surface has usable UVs (the painter can paint it); otherwise only a whole colour.
static func has_uvs(root: Node3D) -> bool:
	var slots := slots_of(root)
	if slots.is_empty(): return false
	for slot in slots:
		var mesh: MeshInstance3D = slot.mesh
		if mesh.mesh.surface_get_primitive_type(slot.surface) != Mesh.PRIMITIVE_TRIANGLES: return false
		var arrays := mesh.mesh.surface_get_arrays(slot.surface)
		var uvs = arrays[Mesh.ARRAY_TEX_UV]
		if not uvs is PackedVector2Array or (uvs as PackedVector2Array).size() != (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() or not Core.usable_uvs(uvs): return false
	return true

# ------------------------------------------------------------------ the look before painting

## Per slot, the unpainted look: {image: Image or null (RGBA8, decompressed), color: Color}.
## Main thread (reads textures from the renderer).
static func slot_looks(root: Node3D) -> Array:
	var out := []
	var studio: bool = root.get_meta("studio", false)
	for slot in slots_of(root):
		var mesh: MeshInstance3D = slot.mesh
		var s: int = slot.surface
		var texture: Texture2D = null
		var color := Color.WHITE
		if studio:
			var base: Array = mesh.get_meta("paint_base", [])
			var material := mesh.get_surface_override_material(s)
			if s < base.size(): texture = base[s]
			elif material is BaseMaterial3D: texture = material.albedo_texture
			var colors: Dictionary = root.colors if "colors" in root else {}
			var originals: Array = mesh.get_meta("original_colors", [])
			if colors.has(slot.part): color = Color(str(colors[slot.part]))
			elif s < originals.size(): color = originals[s]
		else:
			color = root.get_meta("paint", Color.WHITE)
		var image: Image = null
		if texture != null:
			image = texture.get_image()
			if image != null:
				image = image.duplicate()
				if image.is_compressed(): image.decompress()
				image.clear_mipmaps()
				image.convert(Image.FORMAT_RGBA8)
		out.append({"image": image, "color": color})
	return out

## The atlas of those looks (RGBA8, size x size). Plain image work: safe on a worker thread.
static func compose_looks(looks: Array, size := SIZE) -> PackedByteArray:
	var grid := Core.grid_side(looks.size())
	var tile := size / grid
	var atlas := Image.create(size, size, false, Image.FORMAT_RGBA8)
	atlas.fill(Color(0.6, 0.6, 0.6))
	for k in looks.size():
		var look: Dictionary = looks[k]
		var color: Color = look.color
		color.a = 1.0
		var part: Image
		if look.image != null:
			part = (look.image as Image).duplicate()
			part.resize(tile, tile, Image.INTERPOLATE_BILINEAR)
			if not color.is_equal_approx(Color.WHITE):
				var data := part.get_data()
				for o in range(0, data.size(), 4):
					data[o] = int(data[o] * color.r + 0.5); data[o + 1] = int(data[o + 1] * color.g + 0.5); data[o + 2] = int(data[o + 2] * color.b + 0.5)
					data[o + 3] = 255
				part = Image.create_from_data(tile, tile, false, Image.FORMAT_RGBA8, data)
		else:
			part = Image.create(tile, tile, false, Image.FORMAT_RGBA8)
			part.fill(color)
		atlas.blit_rect(part, Rect2i(0, 0, tile, tile), Vector2i((k % grid) * tile, (k / grid) * tile))
	var out := atlas.get_data()
	for o in range(3, out.size(), 4): out[o] = 255
	return out

## A saved paint image as the painter's RGBA8 base layer.
static func image_bytes(image: Image, size := SIZE) -> PackedByteArray:
	var copy := image.duplicate()
	if copy.is_compressed(): copy.decompress()
	copy.clear_mipmaps()
	copy.convert(Image.FORMAT_RGBA8)
	if copy.get_width() != size or copy.get_height() != size: copy.resize(size, size, Image.INTERPOLATE_BILINEAR)
	return copy.get_data()

# ------------------------------------------------------------------ applying

## Puts a paint image on a loaded model. key ("id:version") shares textures between copies.
static func apply(root: Node3D, image: Image, key := "") -> void:
	var slots := slots_of(root)
	if slots.is_empty() or image == null: return
	apply_textures(root, textures_for(image, slots.size(), key), key)

static func apply_textures(root: Node3D, list: Array, key := "") -> void:
	var slots := slots_of(root)
	if slots.size() != list.size(): return
	for k in slots.size():
		var mesh: MeshInstance3D = slots[k].mesh
		var s: int = slots[k].surface
		_remember_base(mesh)
		var painted: Array = mesh.get_meta("paint_textures", [])
		painted.resize(mesh.mesh.get_surface_count())
		painted[s] = list[k]
		mesh.set_meta("paint_textures", painted)
	root.set_meta("paint_key", key)
	refresh(root)

## Back to the unpainted look.
static func clear(root: Node3D) -> void:
	for slot in slots_of(root):
		var mesh: MeshInstance3D = slot.mesh
		if not mesh.has_meta("paint_textures"): continue
		mesh.remove_meta("paint_textures")
		if not root.get_meta("studio", false):
			for s in mesh.mesh.get_surface_count(): mesh.set_surface_override_material(s, null)
	root.remove_meta("paint_key")
	refresh(root)

## Re-applies materials from the meshes' paint metadata.
static func refresh(root: Node3D) -> void:
	if root.get_meta("studio", false) and root.has_method("paint"):
		root.paint(root.colors)
	else:
		Loader.paint(root, root.get_meta("paint", Color.WHITE))

static func _remember_base(mesh: MeshInstance3D) -> void:
	if mesh.has_meta("paint_base"): return
	var base := []
	for s in mesh.mesh.get_surface_count():
		var material := mesh.get_surface_override_material(s)
		base.append(material.albedo_texture if material is BaseMaterial3D else null)
	mesh.set_meta("paint_base", base)

## One texture per slot cut from the atlas, with mipmaps and (where the renderer can)
## block compression. Main thread only (compressing on a worker crashed the engine).
static func textures_for(image: Image, count: int, key := "") -> Array:
	var cache_key := key + "#" + str(count)
	if not key.is_empty() and texture_sets.has(cache_key): return texture_sets[cache_key]
	var grid := Core.grid_side(count)
	var w := image.get_width() / grid
	var h := image.get_height() / grid
	var out := []
	for k in count:
		var part := image.get_region(Rect2i((k % grid) * w, (k / grid) * h, w, h)) if count > 1 else image.duplicate()
		if part.is_compressed(): part.decompress()
		if part.get_format() not in [Image.FORMAT_RGB8, Image.FORMAT_RGBA8]: part.convert(Image.FORMAT_RGBA8)
		# Block compression wants sides divisible by 4.
		var pw := maxi(4, part.get_width() / 4 * 4); var ph := maxi(4, part.get_height() / 4 * 4)
		if pw != part.get_width() or ph != part.get_height(): part.resize(pw, ph, Image.INTERPOLATE_BILINEAR)
		part.generate_mipmaps()
		if RenderingServer.has_os_feature("s3tc"): part.compress(Image.COMPRESS_S3TC, Image.COMPRESS_SOURCE_SRGB)
		elif RenderingServer.has_os_feature("etc2"): part.compress(Image.COMPRESS_ETC2, Image.COMPRESS_SOURCE_SRGB)
		out.append(ImageTexture.create_from_image(part))
	if not key.is_empty():
		texture_sets[cache_key] = out
		texture_order.append(cache_key)
		while texture_order.size() > MAX_TEXTURE_SETS: texture_sets.erase(texture_order.pop_front())
	return out

# ------------------------------------------------------------------ server

static func remember(key: String, image: Image) -> void:
	if images.has(key): image_order.erase(key)
	images[key] = image
	image_order.append(key)
	while image_order.size() > MAX_IMAGES: images.erase(image_order.pop_front())

static func key_for(obj: Dictionary) -> String:
	var version = obj.get("paint_version")
	return "" if version == null else str(obj.get("id", "")) + ":" + str(int(version))

## The object's saved paint (cached), or null.
static func fetch(api: Node, obj: Dictionary, prefix := "/v1/objects/") -> Image:
	var key := key_for(obj)
	if key.is_empty(): return null
	if images.has(key): return images[key]
	var reply: Dictionary = await api.request(prefix + str(obj.id) + "/paint", {}, HTTPClient.METHOD_GET, true)
	if not reply.get("ok", false) or not reply.has("bytes"): return null
	var image := Image.new()
	if image.load_png_from_buffer(reply.bytes) != OK or image.is_empty(): return null
	remember(key, image)
	return image

## After loading a model: shows the object's paint (or none) for its paint_version.
static func attach(api: Node, root: Node3D, obj: Dictionary, prefix := "/v1/objects/") -> void:
	if root == null: return
	var key := key_for(obj)
	if key.is_empty():
		if root.has_meta("paint_key"): clear(root)
		return
	if str(root.get_meta("paint_key", "")) == key: return
	var count := slots_of(root).size()
	var cache_key := key + "#" + str(count)
	if texture_sets.has(cache_key):
		apply_textures(root, texture_sets[cache_key], key)
		return
	var image := await fetch(api, obj, prefix)
	if image == null or not is_instance_valid(root): return
	apply(root, image, key)

## Saves a composite (RGB8 PNG) for an object; returns the server reply.
static func upload(api: Node, object_id: String, png: PackedByteArray) -> Dictionary:
	return await api.request("/v1/objects/" + object_id + "/paint", api.mutation({"png": Marshalls.raw_to_base64(png)}), HTTPClient.METHOD_POST, false, 45.0)

static func clear_remote(api: Node, object_id: String) -> Dictionary:
	return await api.post("/v1/objects/" + object_id + "/paint", api.mutation({"clear": true}))
