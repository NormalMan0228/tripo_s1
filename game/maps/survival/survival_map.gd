extends Node3D
## Survival expedition maps (솔바람 숲 / 노을 채석장 / 서리빛 분지) built to the island village's
## standard: a sculpted basin terrain (flat, walkable play square; hills, cliffs and shores beyond it)
## with detail-mapped ground, authored landmarks on the server's obstacle circles, Tripo props in
## chunked MultiMeshes (LOD1 when the camera zooms out, no shadows for ground cover), per-map light,
## haze and night grade, and Tripo resource visuals.
##
## Geometry that matters for play is server-authoritative (server/survival_maps.py); the client reads the
## exported copy (layouts.json) for dressing and the run state for obstacles, hazards and resources.
## Decor never stands where the walker can go unless it is foliage or ankle-high debris.
const ROOT := "res://maps/survival/"
const ASSETS := "res://maps/survival/assets/"
const VILLAGE := "res://maps/archipelago/assets/"
const DETAIL := "res://maps/archipelago/assets/v5/"
const PROP_SHADER := preload("res://maps/survival/survival_prop.gdshader")
const GROUND_SHADER := preload("res://maps/survival/survival_ground.gdshader")
const WATER_SHADER := preload("res://maps/survival/survival_water.gdshader")
const HAZARD_SHADER := preload("res://maps/survival/survival_hazard.gdshader")
const GRASS_SHADER := preload("res://maps/survival/survival_grass.gdshader")
const CHUNK := 12.0
const LOD_ZOOM := 18.5
const FAR := 64.0
const RESOURCE_KINDS := ["tree","stone","berry","fiber"]

## Per-map look. Colours are the day grade; night values blend in from run.day_progress.
const LOOK := {
	"forest": {
		"turf_low":"4f7d2d","turf_high":"92b145","soil":"6d5435","trail":"bfa275","rock":"8e8f80","accent":"3c6a2a",
		"haze":"a6cdc4","haze_night":"1a2c40","background":"9cc9c2","background_night":"132235",
		"ambient":"f4f8ff","ambient_energy":0.46,"ambient_night":"6f8bbd","ambient_night_energy":0.30,
		"sun":"fff0d2","sun_energy":0.62,"sun_night":"8eaee6","sun_night_energy":0.20,"sun_pitch":-52.0,"sun_yaw":-32.0,
		"grass_low":"5f8e33","grass_high":"b4cf62","snow":0.0,"strata":0.0,
		"rim_north":7.5,"rim_side":4.2,"rim_south":-1.7,"rim_width":11.0,"rim_noise":1.6,"terrace":0.0,
		"water_y":-0.55,"pond_y":-0.14,"water_shallow":"4aa59a","water_deep":"14485a","frozen":0.0,
		"grass":2600,"rim_grass":2000,
	},
	"quarry": {
		"turf_low":"a8835d","turf_high":"c9a57c","soil":"94603f","trail":"cdb48f","rock":"c98a5c","accent":"3e2620",
		"haze":"efbf98","haze_night":"2b2238","background":"f0c49c","background_night":"201a30",
		"ambient":"fff0e2","ambient_energy":0.44,"ambient_night":"7f6fb0","ambient_night_energy":0.30,
		"sun":"ffc58e","sun_energy":0.66,"sun_night":"a493d8","sun_night_energy":0.20,"sun_pitch":-30.0,"sun_yaw":-58.0,
		"grass_low":"9c8a45","grass_high":"e0c06e","snow":0.0,"strata":1.0,
		"rim_north":9.0,"rim_side":7.5,"rim_south":1.6,"rim_width":9.0,"rim_noise":0.8,"terrace":3.0,
		"water_y":-9.0,"pond_y":-9.0,"water_shallow":"4aa59a","water_deep":"14485a","frozen":0.0,
		"grass":1700,"rim_grass":1200,
	},
	"frost": {
		"turf_low":"a9bccb","turf_high":"cfdce6","soil":"7d8a96","trail":"a7b8c6","rock":"858f9c","accent":"9dbbd2",
		"haze":"cfe0ea","haze_night":"17284a","background":"c6dbe6","background_night":"0f1d38",
		"ambient":"cfdcf2","ambient_energy":0.30,"ambient_night":"7193d4","ambient_night_energy":0.30,
		"sun":"fff6ea","sun_energy":0.50,"sun_night":"9fc0f4","sun_night_energy":0.24,"sun_pitch":-40.0,"sun_yaw":-20.0,
		"grass_low":"a89e7c","grass_high":"ddd5bb","snow":1.0,"strata":0.0,
		"rim_north":10.0,"rim_side":5.0,"rim_south":-1.2,"rim_width":12.0,"rim_noise":1.8,"terrace":0.0,
		"water_y":-0.45,"pond_y":-9.0,"water_shallow":"9ec4d6","water_deep":"5f8fb0","frozen":1.0,
		"grass":320,"rim_grass":260,
	},
}

## Prop sources: Tripo survival set (assets/<id>.glb + _lod1) or village props (with their LOD files).
const VILLAGE_PROPS := {
	"tent_green":["environment/tent_green.glb",""],"tent_orange":["environment/tent_orange.glb",""],
	"white_flowers":["environment/white_flowers.glb","prop_lods/42_white_flowers.glb"],
	"yellow_flowers":["environment/yellow_flowers.glb","prop_lods/43_yellow_flowers.glb"],
	"pink_flowers":["environment/pink_flowers.glb","prop_lods/44_pink_flowers.glb"],
	"reeds":["environment/reeds.glb","prop_lods/45_reeds.glb"],
	"lamp":["environment/lamp.glb","prop_lods/27_lamp.glb"],
}

static var _layout_cache: Dictionary = {}

var map_id := "forest"
var state: Dictionary = {}
var spec: Dictionary = {}
var look: Dictionary = {}
var bounds := 22.0
var noise := FastNoiseLite.new()
var rng := RandomNumberGenerator.new()
var materials: Array[ShaderMaterial] = []
var glow_materials: Array[ShaderMaterial] = []
var props := {}
var batches := {}
var multimeshes: Array[Dictionary] = []
var low_active := false
var occupied: Array[Vector3] = []
var app: Node
var camera: Camera3D
var env: Environment
var sun: DirectionalLight3D
var night := 0.0
var dusk := 0.0
var focus := Vector3.ZERO
var follow_particles: Array[Node3D] = []
var adopt_wait := 0.0
var stats := {"instances":0,"multimeshes":0,"props":0,"resource_visuals":0}

static func layouts() -> Dictionary:
	if _layout_cache.is_empty():
		_layout_cache = JSON.parse_string(FileAccess.get_file_as_string(ROOT+"layouts.json"))
	return _layout_cache

func build(run: Dictionary) -> void:
	name = "SurvivalMap"
	state = run
	map_id = str(run.get("map_id","forest"))
	if not LOOK.has(map_id): map_id = "forest"
	look = LOOK[map_id]
	var all := layouts()
	spec = all.maps[map_id]
	bounds = float(all.bounds)
	noise.seed = {"forest":11,"quarry":23,"frost":37}[map_id]
	noise.frequency = 0.045
	noise.fractal_octaves = 3
	rng.seed = noise.seed*7919
	process_priority = 100
	_build_ground()
	_build_water()
	_build_hazards()
	_build_features()
	_build_scatter()
	_build_particles()
	_finish_batches()
	_apply_grade(true)

# ------------------------------------------------------------------ terrain
## Distance beyond the flat play square (negative inside). A square measure keeps the walkable
## corners flat; low-frequency noise breaks the straight edges outside it.
func rim_distance(x: float, z: float) -> float:
	var square := maxf(absf(x),absf(z))
	var rim := square-(bounds+1.3)+noise.get_noise_2d(x*0.12+90.0,z*0.12)*2.2
	if square <= bounds+1.0: rim = minf(rim,0.0)
	return rim

func height(x: float, z: float) -> float:
	var h := _pond_dip(x,z)
	var e := maxf(maxf(absf(x),absf(z)),0.001)
	var rim := rim_distance(x,z)
	if rim <= 0.0: return h
	var dz := z/maxf(e,0.001)
	var top: float = lerpf(float(look.rim_side),float(look.rim_north),pow(clampf(-dz,0.0,1.0),1.4)) if dz < 0.0 else lerpf(float(look.rim_side),float(look.rim_south),pow(clampf(dz,0.0,1.0),1.4))
	var n := noise.get_noise_2d(x,z)
	if top < 0.0:
		return h+top*smoothstep(0.0,5.0,rim)+n*0.25*smoothstep(0.0,3.0,rim)
	var rise := smoothstep(0.0,float(look.rim_width),rim)
	var value := top*rise*(1.0+n*0.35)+maxf(0.0,rim-float(look.rim_width))*0.18*top/6.0
	value += noise.get_noise_2d(x*3.1,z*3.1)*float(look.rim_noise)*0.25*rise
	var step := float(look.terrace)
	if step > 0.0:
		var t := value/step
		value = (floorf(t)+smoothstep(0.62,0.98,t-floorf(t)))*step
	return h+value

func _pond_dip(x: float, z: float) -> float:
	if map_id != "forest": return 0.0
	var sd := 99.0
	for f in spec.features:
		if f.kind == "pond": sd = minf(sd,Vector2(x-f.x,z-f.z).length()-float(f.radius))
	if sd > 0.2: return 0.0
	return -1.1*smoothstep(0.0,-1.8,sd)

func pond_distance(x: float, z: float) -> float:
	var sd := 99.0
	for f in spec.features:
		if f.kind == "pond": sd = minf(sd,Vector2(x-f.x,z-f.z).length()-float(f.radius))
	return sd

func path_distance(x: float, z: float) -> float:
	var best := 99.0
	for path in spec.paths:
		var pts: Array = path.points
		for i in pts.size()-1:
			var a := Vector2(pts[i][0],pts[i][1])
			var b := Vector2(pts[i+1][0],pts[i+1][1])
			var p := Geometry2D.get_closest_point_to_segment(Vector2(x,z),a,b)
			best = minf(best,p.distance_to(Vector2(x,z))-float(path.width)*0.5)
	return best

func _grid_axis() -> PackedFloat32Array:
	var axis := PackedFloat32Array()
	var x := -FAR
	while x < -32.0: axis.append(x); x += 2.0
	x = -32.0
	while x < 32.0: axis.append(x); x += 0.5
	x = 32.0
	while x <= FAR+0.01: axis.append(x); x += 2.0
	return axis

func _build_ground() -> void:
	var axis := _grid_axis()
	var count := axis.size()
	var heights := PackedFloat32Array()
	heights.resize(count*count)
	for j in count:
		for i in count:
			heights[j*count+i] = height(axis[i],axis[j])
	var verts := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()
	verts.resize(count*count); normals.resize(count*count); colors.resize(count*count)
	var obstacles: Array = state.get("obstacles",spec.obstacles)
	var hazards: Array = state.get("hazards",spec.hazards)
	for j in count:
		for i in count:
			var x := axis[i]; var z := axis[j]
			var k := j*count+i
			var y := heights[k]
			verts[k] = Vector3(x,y,z)
			var il := maxi(i-1,0); var ir := mini(i+1,count-1)
			var jd := maxi(j-1,0); var ju := mini(j+1,count-1)
			var dx := (heights[j*count+ir]-heights[j*count+il])/maxf(axis[ir]-axis[il],0.001)
			var dzv := (heights[ju*count+i]-heights[jd*count+i])/maxf(axis[ju]-axis[jd],0.001)
			normals[k] = Vector3(-dx,1.0,-dzv).normalized()
			colors[k] = _splat(x,z,y,obstacles,hazards)
	var indices := PackedInt32Array()
	for j in count-1:
		for i in count-1:
			var a := j*count+i
			indices.append_array([a,a+1,a+count,a+1,a+count+1,a+count])
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_COLOR] = colors
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
	var node := MeshInstance3D.new()
	node.name = "Ground"
	node.mesh = mesh
	var mat := ShaderMaterial.new()
	mat.shader = GROUND_SHADER
	for key in ["grass_detail","sand_detail","rock_detail"]:
		mat.set_shader_parameter(key,load(DETAIL+key+".png"))
	mat.set_shader_parameter("grass_normal",load(DETAIL+"grass_detail_normal.png"))
	mat.set_shader_parameter("sand_normal",load(DETAIL+"sand_detail_normal.png"))
	mat.set_shader_parameter("rock_normal",load(DETAIL+"rock_detail_normal.png"))
	for key in ["turf_low","turf_high","trail","rock","accent"]:
		mat.set_shader_parameter(key,Color(look[key]))
	mat.set_shader_parameter("soil_color",Color(look.soil))
	mat.set_shader_parameter("trail_color",Color(look.trail))
	mat.set_shader_parameter("rock_color",Color(look.rock))
	mat.set_shader_parameter("accent_color",Color(look.accent))
	mat.set_shader_parameter("snow",float(look.snow))
	mat.set_shader_parameter("strata",float(look.strata))
	mat.set_shader_parameter("wet_level",float(look.water_y)+0.2 if map_id != "quarry" else -20.0)
	var segments := PackedVector4Array()
	var widths := PackedFloat32Array()
	for path in spec.paths:
		var pts: Array = path.points
		for i in pts.size()-1:
			segments.append(Vector4(pts[i][0],pts[i][1],pts[i+1][0],pts[i+1][1]))
			widths.append(float(path.width)*0.5)
	while segments.size() < 32:
		segments.append(Vector4(999,999,999,999)); widths.append(0.0)
	mat.set_shader_parameter("path_segments",segments)
	mat.set_shader_parameter("path_half_widths",widths)
	mat.set_shader_parameter("path_count",mini(spec.paths.reduce(func(acc,p): return acc+p.points.size()-1,0),32))
	node.material_override = mat
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
	materials.append(mat)

func _splat(x: float, z: float, y: float, obstacles: Array, hazards: Array) -> Color:
	var inside := maxf(absf(x),absf(z)) < bounds+4.0
	var wobble := noise.get_noise_2d(x*2.3,z*2.3)*0.22
	var trail := 0.0
	var soil := 0.0
	var rock := 0.0
	var accent := 0.0
	var camp := Vector2(x,z).length()
	trail = 1.0-smoothstep(2.9,3.9,camp+wobble*2.0)
	if inside:
		var d := path_distance(x,z)+wobble
		trail = maxf(trail,1.0-smoothstep(-0.15,0.35,d))
		for o in obstacles:
			var od := Vector2(x-o.x,z-o.z).length()-float(o.radius)
			if str(o.get("kind","")) in ["pond"]: continue
			soil = maxf(soil,(1.0-smoothstep(-0.4,0.6,od+wobble))*0.5)
		for h in hazards:
			var hd := Vector2(x-h.x,z-h.z).length()-float(h.radius)
			if h.kind == "ember": accent = maxf(accent,1.0-smoothstep(-0.2,1.8,hd+wobble))
			else: accent = maxf(accent,(1.0-smoothstep(0.0,1.4,hd+wobble))*0.7)
	match map_id:
		"forest":
			var rim := rim_distance(x,z)
			# The woods beyond the clearing sit in their own shade: mossy, darker turf.
			accent = maxf(accent,clampf(0.65+noise.get_noise_2d(x*0.6,z*0.6)*0.5,0.0,0.9)*smoothstep(-0.5,3.0,rim)*(1.0 if z < bounds else 0.0))
			if map_id == "forest" and pond_distance(x,z) < 1.2: soil = maxf(soil,1.0-smoothstep(-0.4,1.2,pond_distance(x,z)))
			if y < float(look.water_y)+0.35 and z > bounds: soil = 1.0
		"quarry":
			soil = maxf(soil,clampf(noise.get_noise_2d(x*0.35+40.0,z*0.35)*1.2+0.25,0.0,0.7))
			if y > 0.4: rock = clampf((y-0.4)*0.25,0.0,0.6)
		"frost":
			soil = soil*0.6
	return Color(clampf(trail,0.0,1.0),clampf(soil,0.0,1.0),rock,clampf(accent,0.0,1.0))

# ------------------------------------------------------------------ water
func _build_water() -> void:
	if map_id == "forest":
		var mat := _water_material(false)
		_water_patch(Rect2(4.0,3.0,14.0,13.5),0.4,float(look.pond_y),mat,true)
		_water_patch(Rect2(-FAR,bounds-1.0,FAR*2.0,FAR-bounds+1.0),2.0,float(look.water_y),mat,false)
	elif map_id == "frost":
		_water_patch(Rect2(-FAR,bounds-1.0,FAR*2.0,FAR-bounds+1.0),2.0,float(look.water_y),_water_material(true),false)

func _water_material(frozen: bool) -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = WATER_SHADER
	mat.set_shader_parameter("surface_normal",load(VILLAGE+"v3/pond_surface_normal.png"))
	mat.set_shader_parameter("shallow_color",Color(look.water_shallow))
	mat.set_shader_parameter("deep_color",Color(look.water_deep))
	mat.set_shader_parameter("frozen",1.0 if frozen else 0.0)
	materials.append(mat)
	return mat

func _water_patch(area: Rect2, step: float, level: float, mat: ShaderMaterial, pond: bool) -> void:
	var nx := int(ceil(area.size.x/step))+1
	var nz := int(ceil(area.size.y/step))+1
	var verts := PackedVector3Array(); var colors := PackedColorArray(); var normals := PackedVector3Array()
	var wet := PackedByteArray()
	for j in nz:
		for i in nx:
			var x := area.position.x+i*step; var z := area.position.y+j*step
			var ground := height(x,z)
			var depth := level-ground
			verts.append(Vector3(x,level,z)); normals.append(Vector3.UP)
			var shore := clampf(-pond_distance(x,z)/2.4,0.0,1.0) if pond else clampf(depth/1.4,0.0,1.0)
			colors.append(Color(shore,0,0,1))
			wet.append(1 if depth > -0.05 else 0)
	var indices := PackedInt32Array()
	for j in nz-1:
		for i in nx-1:
			var a := j*nx+i
			if wet[a]+wet[a+1]+wet[a+nx]+wet[a+nx+1] == 0: continue
			indices.append_array([a,a+1,a+nx,a+1,a+nx+1,a+nx])
	if indices.is_empty(): return
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts; arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_COLOR] = colors; arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
	var node := MeshInstance3D.new()
	node.name = "Pond" if pond else "Lake"
	node.mesh = mesh
	node.material_override = mat
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)

# ------------------------------------------------------------------ hazards
func _build_hazards() -> void:
	var hazards: Array = state.get("hazards",spec.hazards)
	var groups: Array = []
	for h in hazards:
		var joined := false
		for g in groups:
			for o in g:
				if o.kind == h.kind and Vector2(o.x-h.x,o.z-h.z).length() < float(o.radius)+float(h.radius) and g.size() < 4:
					g.append(h); joined = true; break
			if joined: break
		if not joined: groups.append([h])
	for g in groups:
		var lo := Vector2(INF,INF); var hi := Vector2(-INF,-INF)
		var circles := PackedVector4Array()
		for h in g:
			lo = lo.min(Vector2(h.x-h.radius*1.35,h.z-h.radius*1.35))
			hi = hi.max(Vector2(h.x+h.radius*1.35,h.z+h.radius*1.35))
			circles.append(Vector4(h.x,h.z,h.radius,0))
		while circles.size() < 4: circles.append(Vector4(999,999,1,0))
		var quad := PlaneMesh.new()
		quad.size = hi-lo
		var node := MeshInstance3D.new()
		node.name = "Hazard_"+str(g[0].kind)
		node.mesh = quad
		node.position = Vector3((lo.x+hi.x)*0.5,0.03 if g[0].kind == "ember" else 0.022,(lo.y+hi.y)*0.5)
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var mat := ShaderMaterial.new()
		mat.shader = HAZARD_SHADER
		mat.set_shader_parameter("mode",0 if g[0].kind == "ember" else 1)
		mat.set_shader_parameter("circles",circles)
		mat.set_shader_parameter("circle_count",g.size())
		mat.render_priority = 1
		node.material_override = mat
		add_child(node)
		materials.append(mat)
		for h in g:
			_hazard_dressing(h)
	# One readable label per hazard group, shown when the walker is near (main.gd nameplate fade).
	for g in groups:
		var h: Dictionary = g[0]
		var label := Label3D.new()
		label.text = TranslationServer.translate("얼음 · 이동 둔화") if h.kind == "ice" else TranslationServer.translate("열기 · 접근 주의")
		label.position = Vector3(h.x,0.7,h.z)
		label.pixel_size = 0.006; label.font_size = 40; label.outline_size = 10
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.modulate = Color("e5f6f4") if h.kind == "ice" else Color("ffcb92")
		label.outline_modulate = Color(0,0,0,0.55)
		label.add_to_group("place_nameplates")
		add_child(label)

func _hazard_dressing(h: Dictionary) -> void:
	var count := int(float(h.radius)*2.2)
	for i in count:
		var a := rng.randf()*TAU
		var r := float(h.radius)*rng.randf_range(0.82,1.05)
		var p := Vector2(h.x+cos(a)*r,h.z+sin(a)*r)
		if path_distance(p.x,p.y) < 0.3: continue
		if h.kind == "ember": _instance("ember_rock",Vector3(p.x,-0.04,p.y),rng.randf()*TAU,rng.randf_range(0.22,0.34),{"shadow":false})
		else: _instance("ice_crystal",Vector3(p.x,-0.03,p.y),rng.randf()*TAU,rng.randf_range(0.16,0.26),{"shadow":false})
	if h.kind == "ember":
		var sparks := CPUParticles3D.new()
		sparks.position = Vector3(h.x,0.1,h.z)
		sparks.amount = int(10*float(h.radius))
		sparks.lifetime = 2.2
		sparks.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
		sparks.emission_sphere_radius = float(h.radius)*0.8
		sparks.direction = Vector3.UP; sparks.spread = 20
		sparks.initial_velocity_min = 0.4; sparks.initial_velocity_max = 1.1
		sparks.gravity = Vector3(0.15,0.25,0)
		sparks.scale_amount_min = 0.03; sparks.scale_amount_max = 0.06
		var sm := SphereMesh.new(); sm.radius = 0.5; sm.height = 1.0; sm.radial_segments = 6; sm.rings = 3
		sparks.mesh = sm
		var spark_mat := StandardMaterial3D.new()
		spark_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		spark_mat.albedo_color = Color("ffb35c")
		sparks.material_override = spark_mat
		sparks.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(sparks)

# ------------------------------------------------------------------ props
func _prop(id: String) -> Dictionary:
	if props.has(id): return props[id]
	var path := ""; var lod_path := ""
	if VILLAGE_PROPS.has(id):
		path = VILLAGE+VILLAGE_PROPS[id][0]
		lod_path = VILLAGE+VILLAGE_PROPS[id][1] if VILLAGE_PROPS[id][1] != "" else ""
	else:
		path = ASSETS+id+".glb"
		lod_path = ASSETS+id+"_lod1.glb"
	var entry := {"ok":false}
	if not ResourceLoader.exists(path):
		props[id] = entry
		return entry
	var scene := (load(path) as PackedScene).instantiate()
	var meshes := scene.find_children("*","MeshInstance3D",true,false)
	if meshes.is_empty():
		scene.free(); props[id] = entry; return entry
	# Every mesh node of the GLB merged into one mesh (node transforms baked in), one converted
	# material per surface, so a prop is one MultiMesh / one node however its GLB is split.
	var high := ArrayMesh.new()
	var converted := {}
	for node in meshes:
		var source := node as MeshInstance3D
		var xf := _scene_transform(scene,source)
		for surface in source.mesh.get_surface_count():
			_append_surface(high,source.mesh,surface,xf)
			var original: Material = source.get_surface_override_material(surface)
			if original == null: original = source.mesh.surface_get_material(surface)
			var key := original.get_instance_id() if original else 0
			if not converted.has(key): converted[key] = _convert_material(original,id)
			high.surface_set_material(high.get_surface_count()-1,converted[key])
	scene.free()
	var low: ArrayMesh = null
	if lod_path != "" and ResourceLoader.exists(lod_path):
		var lod_scene := (load(lod_path) as PackedScene).instantiate()
		var lod_meshes := lod_scene.find_children("*","MeshInstance3D",true,false)
		var candidate := ArrayMesh.new()
		for node in lod_meshes:
			var source := node as MeshInstance3D
			for surface in source.mesh.get_surface_count():
				_append_surface(candidate,source.mesh,surface,_scene_transform(lod_scene,source))
		lod_scene.free()
		# LOD files carry geometry only; they reuse the full prop's materials surface by surface.
		if candidate.get_surface_count() == high.get_surface_count():
			for surface in candidate.get_surface_count():
				candidate.surface_set_material(surface,high.surface_get_material(surface))
			low = candidate
	entry = {"ok":true,"mesh":high,"low":low if low != null else high,"aabb":high.get_aabb()}
	props[id] = entry
	stats.props += 1
	return entry

func _scene_transform(scene: Node, node: Node) -> Transform3D:
	var xf := Transform3D.IDENTITY
	var current := node
	while current != null and current != scene:
		if current is Node3D: xf = (current as Node3D).transform*xf
		current = current.get_parent()
	if scene is Node3D: xf = (scene as Node3D).transform*xf
	return xf

func _append_surface(out: ArrayMesh, mesh: Mesh, surface: int, xf: Transform3D) -> void:
	var arrays := mesh.surface_get_arrays(surface)
	if not xf.is_equal_approx(Transform3D.IDENTITY):
		var v: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		for i in v.size(): v[i] = xf*v[i]
		arrays[Mesh.ARRAY_VERTEX] = v
		var normal_basis := xf.basis.inverse().transposed()
		if arrays[Mesh.ARRAY_NORMAL] != null:
			var n: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
			for i in n.size(): n[i] = (normal_basis*n[i]).normalized()
			arrays[Mesh.ARRAY_NORMAL] = n
		if arrays[Mesh.ARRAY_TANGENT] != null:
			var t: PackedFloat32Array = arrays[Mesh.ARRAY_TANGENT]
			for i in t.size()/4:
				var d := (xf.basis*Vector3(t[i*4],t[i*4+1],t[i*4+2])).normalized()
				t[i*4] = d.x; t[i*4+1] = d.y; t[i*4+2] = d.z
			arrays[Mesh.ARRAY_TANGENT] = t
	out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)

## Per prop and map: tint, snow, wind and night glow on top of the Tripo albedo/normal textures.
func _convert_material(source: Material, id: String) -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = PROP_SHADER
	if source is BaseMaterial3D:
		var base := source as BaseMaterial3D
		mat.set_shader_parameter("albedo_texture",base.albedo_texture)
		mat.set_shader_parameter("base_color",base.albedo_color)
		mat.set_shader_parameter("normal_texture",base.normal_texture)
		mat.set_shader_parameter("use_normal",base.normal_enabled and base.normal_texture != null)
	var foliage := id in ["pine_tall","oak_broad","birch_slim","bush_round","berry_bush","fiber_grass","fern_clump","snow_pine","frost_shrub","dry_shrub","reeds","white_flowers","yellow_flowers","pink_flowers"]
	if foliage:
		var tall := id in ["pine_tall","oak_broad","birch_slim","snow_pine"]
		mat.set_shader_parameter("wind",0.07 if tall else 0.05)
		mat.set_shader_parameter("wind_height",5.0 if tall else 1.0)
	var tint := Color.WHITE
	var sat := 1.0
	var bright := 1.0
	match map_id:
		"quarry":
			if id in ["birch_slim"]: tint = Color("ffc070"); sat = 1.25
			elif id in ["stone_pile","fiber_grass"]: tint = Color("f2cf9e")
			elif id in ["berry_bush"]: tint = Color("e8e0b0")
		"frost":
			if id in ["stone_pile","fiber_grass","berry_bush","log_bench","firewood_pile","tent_orange","tent_green","tree_stump","camp_supplies","sled_empty","signpost"]:
				mat.set_shader_parameter("snow",0.85)
			if id in ["fiber_grass"]: tint = Color("dfe8e0"); sat = 0.7
			if id in ["firewood_pile","log_bench"]: tint = Color("d9c3a8"); sat = 0.8
		"forest":
			if id in ["pine_tall"]: bright = 1.04
			elif id in ["mossy_boulder"]: tint = Color("d8dde6"); sat = 0.45
			elif id in ["oak_broad"]: tint = Color("e6f2d0"); sat = 1.25; bright = 0.95
	mat.set_shader_parameter("tint",tint)
	mat.set_shader_parameter("saturation",sat)
	mat.set_shader_parameter("brightness",bright)
	if id in ["ember_rock","mine_cart"]:
		mat.set_shader_parameter("glow_mode",1); mat.set_shader_parameter("glow_color",Color("ff7a2a"))
		glow_materials.append(mat)
	elif id in ["ice_crystal"]:
		mat.set_shader_parameter("glow_mode",2); mat.set_shader_parameter("glow_color",Color("7fd8ff"))
		glow_materials.append(mat)
	elif id in ["frost_shrine"]:
		mat.set_shader_parameter("glow_mode",1); mat.set_shader_parameter("glow_color",Color("ffc46b"))
		glow_materials.append(mat)
	elif id == "mushroom_cluster":
		mat.set_shader_parameter("glow_mode",1); mat.set_shader_parameter("glow_color",Color("ff9a7a"))
		glow_materials.append(mat)
	mat.set_meta("glow_base",{"ember_rock":2.2,"mine_cart":1.2,"ice_crystal":1.3,"frost_shrine":2.0,"tool_rack":0.8,"signpost":0.5,"mushroom_cluster":0.35}.get(id,0.0))
	materials.append(mat)
	return mat

## Queue one instance of a prop for the chunked MultiMesh batches.
func _instance(id: String, at: Vector3, yaw: float, scale: float, opts := {}) -> bool:
	var entry := _prop(id)
	if not entry.ok: return false
	var basis := Basis(Vector3.UP,yaw).scaled(Vector3.ONE*scale)
	if opts.has("tilt"): basis = Basis(Vector3(cos(yaw),0,sin(yaw)),float(opts.tilt))*basis
	var shadow: bool = opts.get("shadow",true)
	var lod: String = opts.get("lod","auto")
	var key := "%s|%s|%s|%d_%d" % [id,shadow,lod,int(floor(at.x/CHUNK)),int(floor(at.z/CHUNK))]
	if not batches.has(key):
		batches[key] = {"id":id,"shadow":shadow,"lod":lod,"xforms":[]}
	batches[key].xforms.append(Transform3D(basis,at))
	stats.instances += 1
	return true

func _finish_batches() -> void:
	var root := Node3D.new()
	root.name = "Props"
	add_child(root)
	for key in batches:
		var b: Dictionary = batches[key]
		var entry := _prop(b.id)
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		var always_low: bool = b.lod == "low"
		mm.mesh = entry.low if always_low else entry.mesh
		mm.instance_count = b.xforms.size()
		for i in b.xforms.size(): mm.set_instance_transform(i,b.xforms[i])
		var node := MultiMeshInstance3D.new()
		node.multimesh = mm
		node.set_meta("prop",b.id)
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if b.shadow else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(node)
		if not always_low and entry.low != entry.mesh:
			multimeshes.append({"mm":mm,"high":entry.mesh,"low":entry.low})
		stats.multimeshes += 1
	batches.clear()

## A single authored prop (landmarks, camp kit): its own node so it can carry labels and lights.
func _single(id: String, at: Vector3, yaw: float, scale: float, shadow := true) -> MeshInstance3D:
	var entry := _prop(id)
	if not entry.ok: return null
	var node := MeshInstance3D.new()
	node.name = id
	node.mesh = entry.mesh
	node.position = at
	node.rotation.y = yaw
	node.scale = Vector3.ONE*scale
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadow else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
	return node

func _fit_scale(id: String, measure: String, metres: float) -> float:
	var entry := _prop(id)
	if not entry.ok: return 1.0
	var size: Vector3 = entry.aabb.size
	var source: float = size.y if measure == "height" else maxf(size.x,size.z)
	return metres/maxf(source,0.001)

# ------------------------------------------------------------------ features (server obstacle circles)
func _build_features() -> void:
	for f in spec.features:
		var at := Vector3(f.x,0,f.z)
		var yaw := deg_to_rad(float(f.get("yaw",rng.randf()*360.0)))
		var r := float(f.get("radius",1.0))
		match str(f.kind):
			"bench": _single("log_bench",at,yaw,_fit_scale("log_bench","width",1.7))
			"firewood": _single("firewood_pile",at,yaw,_fit_scale("firewood_pile","width",1.3))
			"supplies": _single("camp_supplies",at,yaw,_fit_scale("camp_supplies","width",1.4))
			"tools": _single("tool_rack",at,yaw,_fit_scale("tool_rack","width",1.5))
			"sled":
				# The first Tripo sled has a little rider on it; the empty one replaces it once generated.
				var sled := "sled_empty" if ResourceLoader.exists(ASSETS+"sled_empty.glb") else "camp_supplies"
				_single(sled,at,yaw,_fit_scale(sled,"width",1.5))
			"sign": _single("signpost",at,yaw,_fit_scale("signpost","height",1.9))
			"snowman": _single("snowman",at,yaw,_fit_scale("snowman","height",1.4))
			"tent":
				var tent := "tent_green" if map_id == "quarry" else "tent_orange"
				# Ridge across the view so both canvas slopes read from the follow camera.
				_single(tent,at,deg_to_rad(140.0),_fit_scale(tent,"width",2.7))
			"pond": _pond_dressing(f)
			"boulder":
				_single("mossy_boulder",at+Vector3(0,-0.1,0),yaw,_fit_scale("mossy_boulder","width",r*2.15))
				for i in 3: _instance("fern_clump",at+Vector3(cos(i*2.1+yaw),0,sin(i*2.1+yaw))*(r*0.95),rng.randf()*TAU,rng.randf_range(0.7,1.0),{"shadow":false})
			"ruin":
				_single("forest_ruin",at,yaw,_fit_scale("forest_ruin","width",float(f.span)+r*2.0))
				_landmark(at+Vector3(0,4.2,0),"옛 돌문")
			"oak": _single("oak_broad",at,yaw,rng.randf_range(0.95,1.1))
			"log": _single("fallen_log",at+Vector3(0,-0.05,0),yaw,_fit_scale("fallen_log","width",float(f.length)+0.3))
			"outcrop":
				_single("sandstone_cliff",at+Vector3(0,-0.15,0),yaw,_fit_scale("sandstone_cliff","width",r*2.25))
				for i in 2: _instance("sandstone_boulder",at+Vector3(cos(i*2.6+yaw),0,sin(i*2.6+yaw))*(r*0.92),rng.randf()*TAU,rng.randf_range(0.28,0.4))
			"blocks": _single("cut_blocks",at,yaw,_fit_scale("cut_blocks","width",r*2.1))
			"crane":
				_single("quarry_crane",at,yaw,_fit_scale("quarry_crane","height",5.4))
				_landmark(at+Vector3(0,6.0,0),"노을 기중기")
			"cart":
				_single("mine_cart",at,0.0,_fit_scale("mine_cart","width",1.8))
			"deadtree": _single("dead_tree",at,yaw,rng.randf_range(0.9,1.1))
			"snow_boulder": _single("snow_boulder",at+Vector3(0,-0.1,0),yaw,_fit_scale("snow_boulder","width",r*2.2))
			"shrine":
				_single("frost_shrine",at,0.0,_fit_scale("frost_shrine","height",3.2))
				_landmark(at+Vector3(0,3.9,0),"서리 등불탑")
			"crystal": _single("ice_crystal",at,yaw,_fit_scale("ice_crystal","width",r*2.0))
			"pine": _single("snow_pine",at,yaw,rng.randf_range(0.95,1.1))
	_camp_center()
	if map_id == "quarry": _rails(19.0)

func _landmark(at: Vector3, text: String) -> void:
	var label := Label3D.new()
	label.text = TranslationServer.translate(text)
	label.position = at
	label.pixel_size = 0.0065; label.font_size = 44; label.outline_size = 12
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.modulate = Color("f3e6c0"); label.outline_modulate = Color(0,0,0,0.5)
	label.add_to_group("place_nameplates")
	add_child(label)

func _camp_center() -> void:
	var hearth := load("res://assets/storybook_camp_v1.glb") as PackedScene
	if hearth:
		var node := hearth.instantiate()
		node.name = "Hearth"
		add_child(node)
	var label := Label3D.new()
	label.text = TranslationServer.translate("야영지")
	label.position = Vector3(0,1.6,-0.8)
	label.pixel_size = 0.006; label.font_size = 40; label.outline_size = 10
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.modulate = Color("eedb9c"); label.outline_modulate = Color(0,0,0,0.5)
	label.add_to_group("place_nameplates")
	add_child(label)

func _pond_dressing(f: Dictionary) -> void:
	var r := float(f.radius)
	var count := int(r*5)
	for i in count:
		var a := rng.randf()*TAU
		var p := Vector2(f.x,f.z)+Vector2(cos(a),sin(a))*r*rng.randf_range(0.82,1.02)
		if pond_distance(p.x,p.y) < -0.55: continue
		if path_distance(p.x,p.y) < 0.4: continue
		if rng.randf() < 0.6: _instance("reeds",Vector3(p.x,height(p.x,p.y)-0.05,p.y),rng.randf()*TAU,rng.randf_range(0.7,1.0),{"shadow":false})
		else: _instance("mossy_boulder",Vector3(p.x,height(p.x,p.y)-0.12,p.y),rng.randf()*TAU,rng.randf_range(0.13,0.2),{"shadow":false})

func _rails(x: float) -> void:
	var wood := StandardMaterial3D.new(); wood.albedo_color = Color("6b4a33"); wood.roughness = 0.9
	var iron := StandardMaterial3D.new(); iron.albedo_color = Color("4c4a4f"); iron.roughness = 0.45; iron.metallic = 0.6
	var sleepers := MultiMesh.new()
	sleepers.transform_format = MultiMesh.TRANSFORM_3D
	var box := BoxMesh.new(); box.size = Vector3(1.6,0.08,0.24)
	sleepers.mesh = box
	var z := -FAR*0.6
	var xf: Array[Transform3D] = []
	while z < FAR*0.6:
		xf.append(Transform3D(Basis(Vector3.UP,rng.randf_range(-0.05,0.05)),Vector3(x,height(x,z)+0.03,z)))
		z += 0.7
	sleepers.instance_count = xf.size()
	for i in xf.size(): sleepers.set_instance_transform(i,xf[i])
	var node := MultiMeshInstance3D.new(); node.multimesh = sleepers; node.material_override = wood
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
	for side in [-0.5,0.5]:
		var rail := MeshInstance3D.new()
		var st := SurfaceTool.new(); st.begin(Mesh.PRIMITIVE_TRIANGLES)
		z = -FAR*0.6
		while z < FAR*0.6:
			var y0 := height(x,z)+0.1; var y1 := height(x,z+1.0)+0.1
			for p in [Vector3(x+side-0.04,y0,z),Vector3(x+side+0.04,y0,z),Vector3(x+side-0.04,y1,z+1.0),Vector3(x+side+0.04,y0,z),Vector3(x+side+0.04,y1,z+1.0),Vector3(x+side-0.04,y1,z+1.0)]:
				st.set_normal(Vector3.UP); st.add_vertex(p)
			z += 1.0
		rail.mesh = st.commit(); rail.material_override = iron
		rail.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(rail)

# ------------------------------------------------------------------ scatter
func _free(x: float, z: float, clearance: float, avoid_paths := true) -> bool:
	if Vector2(x,z).length() < 4.4+clearance: return false
	if avoid_paths and path_distance(x,z) < clearance: return false
	for o in state.get("obstacles",spec.obstacles):
		if Vector2(x-o.x,z-o.z).length() < float(o.radius)+clearance: return false
	for h in state.get("hazards",spec.hazards):
		if Vector2(x-h.x,z-h.z).length() < float(h.radius)+clearance: return false
	for n in state.get("nodes",[]):
		if Vector2(x-n.x,z-n.z).length() < 1.1+clearance: return false
	for c in occupied:
		if Vector2(x-c.x,z-c.y).length() < c.z+clearance: return false
	return true

func _sample_inside() -> Vector2:
	return Vector2(rng.randf_range(-bounds-0.5,bounds+0.5),rng.randf_range(-bounds-0.5,bounds+0.5))

func _sample_rim(min_rim: float, max_rim: float, south_ok: bool) -> Vector2:
	for attempt in 30:
		var p := Vector2(rng.randf_range(-FAR+4,FAR-4),rng.randf_range(-FAR+4,FAR-4))
		var r := rim_distance(p.x,p.y)
		if r < min_rim or r > max_rim: continue
		if not south_ok and p.y > bounds-2.0: continue
		return p
	return Vector2(INF,INF)

func _scatter_inside(id: String, count: int, scale_min: float, scale_max: float, clearance: float, opts := {}, avoid_paths := true, reserve := 0.0) -> void:
	var placed := 0
	for attempt in count*8:
		if placed >= count: break
		var p := _sample_inside()
		if not _free(p.x,p.y,clearance,avoid_paths): continue
		var s := rng.randf_range(scale_min,scale_max)
		if _instance(id,Vector3(p.x,height(p.x,p.y)-0.03,p.y),rng.randf()*TAU,s,opts): placed += 1
		if reserve > 0.0: occupied.append(Vector3(p.x,p.y,reserve*s))

func _scatter_rim(id: String, count: int, scale_min: float, scale_max: float, min_rim: float, max_rim: float, south_ok: bool, opts := {}, spacing := 0.0) -> void:
	var placed := 0
	var spots: Array[Vector2] = []
	for attempt in count*6:
		if placed >= count: break
		var p := _sample_rim(min_rim,max_rim,south_ok)
		if p.x == INF: continue
		var y := height(p.x,p.y)
		if y < float(look.water_y)+0.15: continue
		if spacing > 0.0:
			var crowded := false
			for q in spots:
				if q.distance_to(p) < spacing: crowded = true; break
			if crowded: continue
			spots.append(p)
		if _instance(id,Vector3(p.x,y-0.1,p.y),rng.randf()*TAU,rng.randf_range(scale_min,scale_max),opts): placed += 1

func _build_scatter() -> void:
	match map_id:
		"forest":
			_scatter_rim("pine_tall",55,0.75,1.1,1.0,8.0,false,{},2.6)
			_scatter_rim("pine_tall",110,0.85,1.25,8.0,30.0,false,{"lod":"low"},2.8)
			_scatter_rim("oak_broad",10,0.85,1.05,2.0,8.0,false,{},4.5)
			_scatter_rim("oak_broad",18,0.9,1.2,8.0,26.0,false,{"lod":"low"},4.5)
			_scatter_rim("birch_slim",16,0.8,1.05,0.8,8.0,false,{},2.8)
			_scatter_rim("birch_slim",16,0.85,1.15,8.0,24.0,false,{"lod":"low"},2.8)
			_scatter_rim("bush_round",50,0.8,1.3,0.0,16.0,true,{"shadow":false})
			_scatter_rim("fern_clump",60,0.8,1.3,0.0,14.0,true,{"shadow":false})
			_shore("reeds",70,0.8,1.2)
			_scatter_inside("bush_round",16,0.7,1.0,1.4,{"shadow":false},true,0.9)
			_scatter_inside("fern_clump",46,0.7,1.15,0.6,{"shadow":false},true)
			_scatter_inside("mushroom_cluster",24,0.6,1.0,0.4,{"shadow":false},true)
			_scatter_inside("tree_stump",6,0.7,0.9,1.0,{},true,0.6)
			for flower in ["white_flowers","yellow_flowers","pink_flowers"]:
				_scatter_inside(flower,14,0.55,0.8,0.3,{"shadow":false},true)
		"quarry":
			_cliff_wall()
			_scatter_rim("dead_tree",14,0.8,1.2,6.0,26.0,false,{"lod":"low"},5.0)
			_scatter_rim("dry_shrub",70,0.8,1.4,0.0,24.0,true,{"shadow":false})
			_scatter_rim("sandstone_boulder",40,0.5,1.1,0.8,20.0,true,{"lod":"low"})
			_scatter_inside("dry_shrub",26,0.6,1.0,0.8,{"shadow":false},true,0.6)
			_scatter_inside("sandstone_boulder",12,0.14,0.22,0.5,{"shadow":false},true)
			_scatter_inside("cut_blocks",4,0.18,0.24,1.2,{},true,1.0)
		"frost":
			_scatter_rim("snow_pine",60,0.75,1.1,1.0,8.0,false,{},2.6)
			_scatter_rim("snow_pine",120,0.85,1.25,8.0,30.0,false,{"lod":"low"},2.8)
			_scatter_rim("snow_boulder",26,0.6,1.3,0.8,22.0,true,{"lod":"low"})
			_scatter_rim("frost_shrub",40,0.8,1.2,0.0,14.0,true,{"shadow":false})
			_scatter_rim("ice_crystal",10,0.5,0.9,2.0,14.0,false,{})
			_scatter_inside("frost_shrub",18,0.6,0.95,1.0,{"shadow":false},true,0.7)
			_scatter_inside("ice_crystal",8,0.22,0.32,0.6,{"shadow":false},true)
			_snow_fences()
	_grass()

func _shore(id: String, count: int, smin: float, smax: float) -> void:
	var placed := 0
	for attempt in count*10:
		if placed >= count: break
		var p := Vector2(rng.randf_range(-FAR+6,FAR-6),rng.randf_range(bounds,bounds+8.0))
		var y := height(p.x,p.y)
		if absf(y-float(look.water_y)) > 0.3: continue
		if _instance(id,Vector3(p.x,y-0.05,p.y),rng.randf()*TAU,rng.randf_range(smin,smax),{"shadow":false}): placed += 1

## Quarry walls: rows of sandstone shelves along the terrace risers (north, east, west; the south
## stays open as the cart road out) sell the cut pit; scattered blocks fill the upper ledges.
func _cliff_wall() -> void:
	for row in [[1.2,2.1,1.5,2.2,"auto"],[5.2,2.6,1.4,2.1,"auto"],[9.5,3.2,1.5,2.3,"low"],[14.0,4.0,1.6,2.4,"low"]]:
		var offset: float = row[0]
		var gap: float = row[1]
		var edge := bounds+1.3+offset
		var t := -FAR
		while t < FAR:
			for side in 3:
				var p := Vector2(t,-edge) if side == 0 else Vector2(edge*(1.0 if side == 1 else -1.0),t)
				if p.y > bounds+2.0 or absf(p.x) > FAR-2.0 or absf(p.y) > FAR-2.0: continue
				if side == 0 and absf(p.x) > edge+1.0: continue
				p += Vector2(rng.randf_range(-0.6,0.6),rng.randf_range(-0.6,0.6))
				if rim_distance(p.x,p.y) < 0.6: continue
				_instance("sandstone_cliff",Vector3(p.x,height(p.x,p.y)-1.1,p.y),rng.randf()*TAU,rng.randf_range(row[2],row[3]),{"lod":row[4]})
			t += gap*rng.randf_range(0.8,1.2)

## Snow fences run along the basin's edge just outside the walkable square (north, east, west), in
## broken runs with gaps where the trails leave the basin.
func _snow_fences() -> void:
	var edge := bounds+1.7
	for side in 3:
		var t := -edge
		var run := 0
		while t < edge:
			var p := Vector2(t,-edge) if side == 0 else Vector2(edge*(1.0 if side == 1 else -1.0),t)
			var yaw := 0.0 if side == 0 else PI*0.5
			var gap := path_distance(p.x,p.y) < 1.6 or (run > 3 and rng.randf() < 0.35)
			if gap:
				run = 0
			else:
				run += 1
				var q := p+Vector2(rng.randf_range(-0.1,0.1),rng.randf_range(-0.15,0.15))
				_instance("snow_fence",Vector3(q.x,height(q.x,q.y)-0.03,q.y),yaw+rng.randf_range(-0.06,0.06),0.95)
			t += 2.25

func _grass() -> void:
	var blade := _tuft_mesh()
	var mat := ShaderMaterial.new()
	mat.shader = GRASS_SHADER
	mat.set_shader_parameter("low_color",Color(look.grass_low))
	mat.set_shader_parameter("high_color",Color(look.grass_high))
	mat.set_shader_parameter("frost",float(look.snow))
	materials.append(mat)
	var chunks := {}
	var total := int(look.grass)+int(look.rim_grass)
	for i in total*2:
		if i >= total*2: break
		var inside := i < int(look.grass)*2
		var p := _sample_inside() if inside else _sample_rim(0.0,20.0,true)
		if p.x == INF: continue
		var y := height(p.x,p.y)
		if y < float(look.water_y)+0.1: continue
		if map_id == "forest" and pond_distance(p.x,p.y) < 0.3: continue
		# Tufts gather in drifts (by noise) instead of carpeting the whole lawn.
		if noise.get_noise_2d(p.x*0.9+31.0,p.y*0.9) < -0.05 and rng.randf() < 0.85: continue
		if inside:
			if path_distance(p.x,p.y) < 0.15 or Vector2(p.x,p.y).length() < 3.6: continue
			var skip := false
			for h in state.get("hazards",spec.hazards):
				if Vector2(p.x-h.x,p.y-h.z).length() < float(h.radius)+0.3: skip = true; break
			if skip: continue
		var key := Vector2i(int(floor(p.x/CHUNK)),int(floor(p.y/CHUNK)))
		if not chunks.has(key): chunks[key] = []
		var s := rng.randf_range(0.7,1.3)
		chunks[key].append([Transform3D(Basis(Vector3.UP,rng.randf()*TAU).scaled(Vector3(s,s*rng.randf_range(0.8,1.25),s)),Vector3(p.x,y-0.02,p.y)),Color(rng.randf(),rng.randf(),0,0)])
	for key in chunks:
		var list: Array = chunks[key]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_custom_data = true
		mm.mesh = blade
		mm.instance_count = list.size()
		for i in list.size():
			mm.set_instance_transform(i,list[i][0])
			mm.set_instance_custom_data(i,list[i][1])
		var node := MultiMeshInstance3D.new()
		node.multimesh = mm
		node.material_override = mat
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(node)
		stats.multimeshes += 1
		stats.instances += list.size()

func _tuft_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var r := RandomNumberGenerator.new(); r.seed = 5
	for i in 9:
		var a := i*TAU/9.0+r.randf()*0.4
		var d := Vector3(cos(a),0,sin(a))
		var base := d*r.randf_range(0.02,0.09)
		var h := r.randf_range(0.12,0.24)
		var lean := d*r.randf_range(0.05,0.11)
		var side := Vector3(-d.z,0,d.x)*0.022
		st.set_normal(Vector3.UP)
		st.set_color(Color(0,0,0)); st.add_vertex(base-side)
		st.set_color(Color(0,0,0)); st.add_vertex(base+side)
		st.set_color(Color(1,0,0)); st.add_vertex(base+lean+Vector3(0,h,0))
	if map_id == "forest":
		for i in 2:
			var c := Vector3(r.randf_range(-0.06,0.06),r.randf_range(0.2,0.28),r.randf_range(-0.06,0.06))
			for k in 4:
				var a := k*TAU/4.0
				st.set_normal(Vector3.UP)
				st.set_color(Color(1,1,0)); st.add_vertex(c)
				st.set_color(Color(1,1,0)); st.add_vertex(c+Vector3(cos(a),0.15,sin(a))*0.045)
				st.set_color(Color(1,1,0)); st.add_vertex(c+Vector3(cos(a+1.2),0.15,sin(a+1.2))*0.045)
	return st.commit()

# ------------------------------------------------------------------ particles / atmosphere
func _build_particles() -> void:
	var motes := CPUParticles3D.new()
	motes.name = "Motes"
	motes.amount = 150 if map_id == "frost" else 50
	motes.lifetime = 9.0 if map_id == "frost" else 7.0
	motes.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	motes.emission_box_extents = Vector3(18,4,16) if map_id == "frost" else Vector3(15,1.6,12)
	motes.direction = Vector3(0.3,-1,0.1) if map_id == "frost" else Vector3(1,0.15,0.3)
	motes.spread = 15
	motes.initial_velocity_min = 0.5 if map_id == "frost" else 0.08
	motes.initial_velocity_max = 0.9 if map_id == "frost" else 0.25
	motes.gravity = Vector3.ZERO
	motes.scale_amount_min = 0.025 if map_id == "frost" else 0.02
	motes.scale_amount_max = 0.06 if map_id == "frost" else 0.04
	var sm := SphereMesh.new(); sm.radius = 0.5; sm.height = 1.0; sm.radial_segments = 6; sm.rings = 3
	motes.mesh = sm
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = {"forest":Color("f4f0b0"),"quarry":Color("ffe0b0"),"frost":Color("f6fbff")}[map_id]
	motes.material_override = mat
	motes.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	motes.position.y = 6.0 if map_id == "frost" else 1.4
	add_child(motes)
	follow_particles.append(motes)
	if map_id == "forest":
		var flies := CPUParticles3D.new()
		flies.name = "Fireflies"
		flies.amount = 40; flies.lifetime = 6.0
		flies.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
		flies.emission_box_extents = Vector3(14,1.0,11)
		flies.direction = Vector3(0,1,0); flies.spread = 180
		flies.initial_velocity_min = 0.05; flies.initial_velocity_max = 0.2
		flies.gravity = Vector3.ZERO
		flies.scale_amount_min = 0.05; flies.scale_amount_max = 0.08
		flies.mesh = sm
		var glow := StandardMaterial3D.new()
		glow.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		glow.albedo_color = Color("e8ff8a")
		flies.material_override = glow
		flies.position.y = 1.0
		flies.emitting = false
		flies.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(flies)
		follow_particles.append(flies)

# ------------------------------------------------------------------ resources (Tripo visuals)
const RESOURCE_MODELS := {
	"forest":{"tree":["pine_tall",0.6],"stone":["stone_pile",0.82],"berry":["berry_bush",0.95],"fiber":["fiber_grass",0.9],"stump":["tree_stump",0.72]},
	"quarry":{"tree":["birch_slim",0.72],"stone":["stone_pile",0.85],"berry":["berry_bush",0.9],"fiber":["fiber_grass",0.85],"stump":["tree_stump",0.66]},
	"frost":{"tree":["snow_pine",0.62],"stone":["stone_pile",0.82],"berry":["frost_shrub",0.95],"fiber":["fiber_grass",0.82],"stump":["tree_stump",0.7]},
}

## Dress one resource root (main.gd's node at the resource position). Trees get a hidden "Stump" child
## that main.gd shows when the tree is depleted.
func dress_resource(root: Node3D, kind: String) -> void:
	if root.has_meta("survival_dressed"): return
	root.set_meta("survival_dressed",true)
	var models: Dictionary = RESOURCE_MODELS[map_id]
	if not models.has(kind): return
	for child in root.get_children():
		root.remove_child(child)
		child.queue_free()
	var pick: Array = models[kind]
	var entry := _prop(pick[0])
	if not entry.ok: return
	var h := absi(hash(Vector2i(roundi(root.position.x*10.0),roundi(root.position.z*10.0))))
	var model := MeshInstance3D.new()
	model.name = "Model"
	model.mesh = entry.mesh
	model.rotation.y = float(h%628)/100.0
	model.scale = Vector3.ONE*float(pick[1])*(0.92+float(h%17)/100.0)
	root.add_child(model)
	if kind == "tree":
		var stump_entry := _prop(models.stump[0])
		if stump_entry.ok:
			var stump := MeshInstance3D.new()
			stump.name = "Stump"
			stump.mesh = stump_entry.mesh
			stump.scale = Vector3.ONE*float(models.stump[1])
			stump.visible = false
			root.add_child(stump)
	stats.resource_visuals += 1

## main.gd builds a Node3D per resource (meta "kind") with primitive meshes; swap in the Tripo models.
func _adopt_resources() -> void:
	var world := get_parent()
	if world == null: return
	for child in world.get_children():
		if child is Node3D and child.has_meta("kind") and not child.has_meta("survival_dressed"):
			dress_resource(child,str(child.get_meta("kind")))

# ------------------------------------------------------------------ per frame
func _process(delta: float) -> void:
	_bind()
	var run: Dictionary = state
	if is_instance_valid(app) and app.get("run") is Dictionary and not (app.get("run") as Dictionary).is_empty():
		run = app.get("run")
	var progress := float(run.get("day_progress",0.3))
	var target_night := smoothstep(0.62,0.70,progress)*(1.0-smoothstep(0.95,1.0,progress))
	if bool(run.get("night",false)): target_night = maxf(target_night,0.9)
	var target_dusk := smoothstep(0.50,0.62,progress)*(1.0-smoothstep(0.66,0.72,progress))
	night = lerpf(night,target_night,minf(1.0,delta*1.5)) if delta > 0.0 else target_night
	dusk = lerpf(dusk,target_dusk,minf(1.0,delta*1.5)) if delta > 0.0 else target_dusk
	if is_instance_valid(app) and app.get("player") is Node3D and is_instance_valid(app.get("player")):
		focus = (app.get("player") as Node3D).global_position
	var cam_pos := camera.global_position if is_instance_valid(camera) else Vector3(0,1000,0)
	for mat in materials:
		mat.set_shader_parameter("focus",focus)
		mat.set_shader_parameter("camera_world",cam_pos)
		mat.set_shader_parameter("night",night)
		mat.set_shader_parameter("haze_color",_haze())
	for mat in glow_materials:
		mat.set_shader_parameter("glow",float(mat.get_meta("glow_base",0.0))*(0.25+night*1.0))
	for p in follow_particles:
		if is_instance_valid(p): p.global_position = Vector3(focus.x,p.global_position.y,focus.z-2.0)
	var flies := get_node_or_null("Fireflies") as CPUParticles3D
	if flies: flies.emitting = night > 0.5
	if is_instance_valid(camera):
		var want_low := camera.size > LOD_ZOOM
		if want_low != low_active:
			low_active = want_low
			for m in multimeshes: m.mm.mesh = m.low if low_active else m.high
	_apply_grade(false)
	adopt_wait -= delta
	if adopt_wait <= 0.0:
		adopt_wait = 0.15
		_adopt_resources()

func _bind() -> void:
	if is_instance_valid(app): return
	# main.gd (or a test harness) is the nearest ancestor with a camera property.
	var scene: Node = get_parent()
	while scene != null and not (scene.get("camera") is Camera3D):
		scene = scene.get_parent()
	if scene == null: return
	app = scene
	var cam = scene.get("camera")
	camera = cam if cam is Camera3D else get_viewport().get_camera_3d()
	var e = scene.get("environment")
	env = e if e is Environment else null
	var s = scene.get("sun")
	sun = s if s is DirectionalLight3D else null
	if env == null:
		var we := scene.find_children("*","WorldEnvironment",true,false)
		if not we.is_empty(): env = (we[0] as WorldEnvironment).environment
	if sun == null:
		var lights := scene.find_children("*","DirectionalLight3D",true,false)
		if not lights.is_empty(): sun = lights[0]

func _haze() -> Color:
	var day := Color(look.haze)
	if dusk > 0.0: day = day.lerp(Color("f2b98c") if map_id != "frost" else Color("e0c4d8"),dusk*0.6)
	return day.lerp(Color(look.haze_night),night)

## Day / dusk / night grade for this map. main.gd lerps its own survival values every frame; this
## node runs after it (process_priority) and sets the map's grade instead.
func _apply_grade(_snap: bool) -> void:
	if env == null or sun == null:
		_bind()
	if env != null:
		env.background_mode = Environment.BG_COLOR
		env.background_color = Color(look.background).lerp(Color(look.background_night),night)
		env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		env.ambient_light_color = Color(look.ambient).lerp(Color(look.ambient_night),night)
		env.ambient_light_energy = lerpf(float(look.ambient_energy),float(look.ambient_night_energy),night)
		env.fog_enabled = false
	if sun != null:
		var day_sun := Color(look.sun).lerp(Color("ffb27a"),dusk*0.55)
		sun.light_color = day_sun.lerp(Color(look.sun_night),night)
		sun.light_energy = lerpf(float(look.sun_energy),float(look.sun_night_energy),night)
		sun.rotation_degrees = Vector3(lerpf(float(look.sun_pitch),-58.0,night)+dusk*14.0,float(look.sun_yaw)+night*40.0,0)

func report() -> Dictionary:
	var out := stats.duplicate()
	out["map"] = map_id
	out["materials"] = materials.size()
	return out
