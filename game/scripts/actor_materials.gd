extends RefCounted
## Reuse immutable material variants between avatars/previews/peers. Textures stay
## shared with the imported model; customization never duplicates an image.
const Tint=preload("res://shaders/avatar_tint.gdshader")
const LIMIT := 192
const ROUGHNESS := {"hair":.52,"skin":.66,"coat":.9,"pants":.93,"boots":.64,"accent":.72,"backpack":.68}
static var cache := {}
static var order: Array[String] = []
static var hits := 0
static var misses := 0

static func surface(source: StandardMaterial3D, avatar: Dictionary) -> Material:
	var fields := source.resource_name.to_lower().split("__")
	var part: String=fields[0]
	if part=="detail": part="accent"
	if not ROUGHNESS.has(part): return source
	var id: String=str(avatar.get("character",""))
	var hidden: bool=part=="backpack" and not avatar.get("backpack",true)
	var color := str(avatar.get(part,""))
	var key := "%d|%s|%s|%s|%s"%[source.get_instance_id(),part,id,color,hidden]
	if cache.has(key): hits+=1;return cache[key]
	misses+=1
	var rough: float=ROUGHNESS[part]
	var metal := 0.0
	# The smith's plates and the artisan's grey fittings are metal; coloured
	# bandanas and leather belts on the other six remain dielectric.
	if id=="m4" and part in ["coat","accent"]: rough=.42;metal=.65
	elif id=="m2" and part=="accent": rough=.48;metal=.55
	elif id=="f3" and part=="coat": rough=.72
	var material: Material
	if not hidden and not color.is_empty() and fields.size()==2 and source.albedo_texture:
		var tinted := ShaderMaterial.new();tinted.shader=Tint
		tinted.set_shader_parameter("albedo_texture",source.albedo_texture)
		tinted.set_shader_parameter("tint",Color(color))
		tinted.set_shader_parameter("reference_color",Color("#"+fields[1]))
		tinted.set_shader_parameter("skin_part",part=="skin")
		tinted.set_shader_parameter("roughness_factor",rough)
		tinted.set_shader_parameter("metallic_factor",metal)
		tinted.set_shader_parameter("specular_factor",.36 if part=="skin" else .45)
		material=tinted
	else:
		var plain: StandardMaterial3D=source.duplicate()
		plain.roughness=rough;plain.metallic=metal
		if hidden:
			plain.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA;plain.albedo_color.a=0.0
		material=plain
	cache[key]=material;order.append(key)
	while order.size()>LIMIT: cache.erase(order.pop_front())
	return material
