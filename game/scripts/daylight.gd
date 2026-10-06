extends Node
## Real-time day and night for the village, driven by the PC's local clock.
## sample(hour) is the whole look as data; a node from this script, once attached,
## re-samples the clock every couple of seconds and eases the scene toward it.
## Noon matches Archipelago.apply_lighting, which is tuned for the Compatibility
## renderer's linear tonemap: brighter values wash the meadows out.

## Sun path: rises 06:00, peaks at 12:00 (the tuned -54 deg), sets 18:45.
const SUNRISE := 6.0
const NOON := 12.0
const SUNSET := 18.75
const NOON_PITCH := 54.0
const NOON_YAW := -32.0
## Lowest sun angle used for shadows; below it the light only fades.
const MIN_SHADOW_PITCH := 20.0
## Lamps ("27_lamp") burn at this multiple of their authored energy at night.
const LAMP_NIGHT_GAIN := 4.0
## ...and reach this much further than authored, so each lamp pools on the path.
const LAMP_NIGHT_REACH := 1.3

## [hour, sun colour, sun energy, ambient colour, ambient energy, background,
## fog colour, fog density, lamps 0..1, saturation]. Eased between neighbours;
## wraps at 24 h. Low sun keeps a cool ambient so shadows read blue against warm
## light; night lowers saturation so the meadows read moonlit rather than dim green.
const KEYS := [
	[0.0, "a3bcff", .22, "3a55aa", .23, "121b35", "22335f", .008, 1.0, .62],
	[4.6, "a3bcff", .22, "3a55aa", .23, "121b35", "22335f", .008, 1.0, .62],
	[5.3, "b4abe2", .10, "5b67b0", .27, "363d6c", "3d4679", .007, 1.0, .70],
	[5.9, "ffa48c", .14, "959bd0", .31, "d39ea9", "d0a3b6", .0035, .6, .86],
	[6.5, "ffb680", .24, "aeb6dc", .335, "f2c7a8", "ebc9bb", .0015, 0.0, .96],
	[7.4, "ffd9aa", .27, "cfd8ea", .35, "d6e4e6", "e0e2dc", 0.0, 0.0, 1.0],
	[9.0, "fff0d8", .29, "e6eef0", .36, "bde3ec", "c4e2ea", 0.0, 0.0, 1.0],
	[12.0, "fff5df", .30, "e4eef2", .36, "b8e3ee", "b8e3ee", 0.0, 0.0, 1.0],
	[15.0, "fff3dc", .30, "e6eef0", .36, "bde2ea", "c4e0e6", 0.0, 0.0, 1.0],
	[16.8, "ffe4b8", .30, "dfe2ea", .355, "cfe0e0", "e4dccb", 0.0, 0.0, 1.0],
	[17.8, "ffca8e", .28, "c4cbe6", .34, "efcda8", "f0c9a0", .001, 0.0, 1.0],
	[18.5, "ffae78", .20, "a9b0de", .33, "eea585", "d9a39a", .002, .5, .92],
	[19.1, "d690a0", .08, "7a7ec4", .30, "6a5c94", "585c94", .005, 1.0, .80],
	[19.8, "a3bcff", .17, "4560b0", .26, "1f2a50", "283a68", .007, 1.0, .66],
	[21.0, "a3bcff", .22, "3a55aa", .23, "121b35", "22335f", .008, 1.0, .62],
]

## Night colour grade: a per-channel curve (the Environment's 1D colour-correction
## LUT) through these points. Dark and mid tones lean moonlit blue; brighter values
## (lamp pools, lit faces) return to neutral so lamplight keeps its warmth.
## Blended in by the "night" value and switched off by day.
const GRADE_AT := [0.0, .30, .62, 1.0]
const GRADE_NIGHT := [Color(0.0, .012, .07), Color(.19, .265, .335), Color(.63, .61, .57), Color(1.0, .97, .90)]

## Soft glow drawn over each lit lantern head: a camera-facing quad pulled a little
## toward the viewer so the lantern housing does not hide it.
const HALO_SHADER := """
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;
uniform float strength = 0.0;
uniform vec4 tint : source_color = vec4(1.0, 0.80, 0.48, 1.0);
void vertex() {
	MODELVIEW_MATRIX = VIEW_MATRIX*mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	VERTEX.z += 0.45;
}
void fragment() {
	float d = length(UV-vec2(0.5))*2.0;
	float glow = pow(max(1.0-d, 0.0), 2.4)*0.75+pow(max(1.0-d*2.6, 0.0), 2.0)*0.6;
	ALBEDO = tint.rgb*glow*strength;
}
"""
const HALO_SIZE := 1.1

## Set to an hour (0..24) to freeze the clock, for tests and debugging.
var override_hour := -1.0
## Seconds between clock samples; each new sample is eased in over blend_seconds.
var update_interval := 2.0
var blend_seconds := 1.5
var environment: Environment
var sun: DirectionalLight3D
var lamps: Array[OmniLight3D] = []
var halos: Array[MeshInstance3D] = []
var current: Dictionary = {}
var _from: Dictionary = {}
var _target: Dictionary = {}
var _blend := 1.0
var _until_sample := 0.0
var _halo_material: ShaderMaterial

## Local clock time as fractional hours.
static func clock_hour() -> float:
	var now := Time.get_datetime_dict_from_system()
	return float(now.hour)+float(now.minute)/60.0+float(now.second)/3600.0

## Signed sun elevation in degrees: 54 at noon, 0 at sunrise/sunset, -40 at midnight-ish.
static func sun_elevation(hour: float) -> float:
	var h := fposmod(hour, 24.0)
	if h >= SUNRISE and h <= NOON:
		return NOON_PITCH*sin(PI*.5*(h-SUNRISE)/(NOON-SUNRISE))
	if h > NOON and h <= SUNSET:
		return NOON_PITCH*sin(PI*.5*(SUNSET-h)/(SUNSET-NOON))
	var night_length := 24.0-SUNSET+SUNRISE
	return -40.0*sin(PI*fposmod(h-SUNSET, 24.0)/night_length)

static func _ease(t: float) -> float:
	return t*t*(3.0-2.0*t)

## The whole lighting state for a local hour (0..24, fractional).
static func sample(hour: float) -> Dictionary:
	var h := fposmod(hour, 24.0)
	# KEYS starts at 0 h, so some key always lies at or before h.
	var index := 0
	for i in KEYS.size():
		if float(KEYS[i][0]) <= h:
			index = i
	var a: Array = KEYS[index]
	var b: Array = KEYS[(index+1)%KEYS.size()]
	var span_start := float(a[0])
	var span_end := float(b[0])+(24.0 if index == KEYS.size()-1 else 0.0)
	var t := _ease(clampf((h-span_start)/maxf(span_end-span_start, .001), 0.0, 1.0))
	var elevation := sun_elevation(h)
	# The sun swings from the east-right (morning) through the tuned noon angle to
	# the west-left (evening); the moon takes over while the twilight is darkest.
	var sun_yaw: float
	if h < NOON:
		sun_yaw = lerpf(55.0, NOON_YAW, clampf((h-SUNRISE)/(NOON-SUNRISE), 0.0, 1.0))
	else:
		sun_yaw = lerpf(NOON_YAW, -112.0, clampf((h-NOON)/(SUNSET-NOON), 0.0, 1.0))
	var sun_pitch := maxf(elevation, MIN_SHADOW_PITCH)
	var night_t := fposmod(h-19.0, 24.0)/10.5
	var moon_pitch := 42.0+14.0*sin(PI*clampf(night_t, 0.0, 1.0))
	var moon_yaw := lerpf(38.0, -60.0, clampf(night_t, 0.0, 1.0))
	var moon := smoothstep(2.0, -6.0, elevation)
	var pitch := lerpf(sun_pitch, moon_pitch, moon)
	var yaw := lerpf(sun_yaw, moon_yaw, moon)
	var night := 1.0-smoothstep(-10.0, 4.0, elevation)
	return {
		"hour": h,
		"sun_rotation": Vector3(-pitch, yaw, 0.0),
		"sun_color": Color(String(a[1])).lerp(Color(String(b[1])), t),
		"sun_energy": lerpf(a[2], b[2], t),
		"ambient_color": Color(String(a[3])).lerp(Color(String(b[3])), t),
		"ambient_energy": lerpf(a[4], b[4], t),
		"background_color": Color(String(a[5])).lerp(Color(String(b[5])), t),
		"fog_color": Color(String(a[6])).lerp(Color(String(b[6])), t),
		"fog_density": lerpf(a[7], b[7], t),
		# Multiplier on each lamp's authored energy (0 = lamps off).
		"lamp_energy": lerpf(a[8], b[8], t)*LAMP_NIGHT_GAIN,
		"saturation": lerpf(a[9], b[9], t),
		"night": night,
		"daylight": clampf(elevation/NOON_PITCH, 0.0, 1.0),
	}

## Writes a sample (or an eased mix of two) into the scene.
static func apply(values: Dictionary, env: Environment, light: DirectionalLight3D, lamp_lights: Array[OmniLight3D] = []) -> void:
	if env != null:
		env.background_color = values.background_color
		env.ambient_light_color = values.ambient_color
		env.ambient_light_energy = values.ambient_energy
		var density: float = values.fog_density
		env.fog_enabled = density > .0002
		env.fog_light_color = values.fog_color
		env.fog_light_energy = 1.0
		env.fog_sun_scatter = 0.0
		env.fog_density = density
		var saturation: float = values.get("saturation", 1.0)
		var grade: float = values.get("night", 0.0)
		env.adjustment_enabled = saturation < .995 or grade > .002
		env.adjustment_saturation = saturation
		_grade(env, grade)
	if light != null:
		light.rotation_degrees = values.sun_rotation
		light.light_color = values.sun_color
		light.light_energy = values.sun_energy
	var gain: float = values.lamp_energy
	for lamp in lamp_lights:
		if not is_instance_valid(lamp):
			continue
		lamp.light_energy = float(lamp.get_meta("daylight_base_energy", lamp.light_energy))*gain
		lamp.omni_range = float(lamp.get_meta("daylight_base_range", lamp.omni_range))*lerpf(1.0, LAMP_NIGHT_REACH, clampf(gain/LAMP_NIGHT_GAIN, 0.0, 1.0))
		lamp.visible = gain > .01

## Keeps the environment's colour-correction curve at the given night weight.
static func _grade(env: Environment, weight: float) -> void:
	var lut := env.adjustment_color_correction as GradientTexture1D
	if lut == null or not lut.has_meta("daylight_grade"):
		if weight <= .002:
			return
		lut = GradientTexture1D.new()
		lut.width = 128
		lut.gradient = Gradient.new()
		lut.gradient.offsets = PackedFloat32Array(GRADE_AT)
		lut.set_meta("daylight_grade", -1.0)
		env.adjustment_color_correction = lut
	if absf(float(lut.get_meta("daylight_grade"))-weight) < .004:
		return
	lut.set_meta("daylight_grade", weight)
	var colors := PackedColorArray()
	for i in GRADE_AT.size():
		var level: float = GRADE_AT[i]
		colors.append(Color(level, level, level).lerp(GRADE_NIGHT[i], weight))
	lut.gradient.colors = colors

## The lantern lights of the map's "27_lamp" props (environment_layout.gd).
static func find_lamps(map_root: Node) -> Array[OmniLight3D]:
	var found: Array[OmniLight3D] = []
	if map_root == null:
		return found
	for node in map_root.find_children("*", "OmniLight3D", true, false):
		var parent := node.get_parent()
		if parent == null or not parent.has_meta("placement_spec"):
			continue
		var spec = parent.get_meta("placement_spec")
		if spec is Dictionary and String(spec.get("id", "")) == "27_lamp":
			var lamp := node as OmniLight3D
			if not lamp.has_meta("daylight_base_energy"):
				lamp.set_meta("daylight_base_energy", lamp.light_energy)
				lamp.set_meta("daylight_base_range", lamp.omni_range)
			found.append(lamp)
	return found

static func _mix(a: Dictionary, b: Dictionary, t: float) -> Dictionary:
	var out := {}
	for key in b:
		var x = a.get(key, b[key])
		var y = b[key]
		if y is float:
			out[key] = lerpf(x, y, t)
		elif y is Color or y is Vector3:
			out[key] = x.lerp(y, t)
		else:
			out[key] = y
	return out

func current_hour() -> float:
	return override_hour if override_hour >= 0.0 else clock_hour()

## Takes over the village lighting. Snaps straight to the current time. Safe to call
## again whenever the village is rebuilt (a kept map reuses its lamp glows).
func attach(env: Environment, light: DirectionalLight3D, map_root: Node) -> void:
	environment = env
	sun = light
	lamps = find_lamps(map_root)
	_add_halos()
	current = {}
	refresh(true)
	set_process(true)

## Stops driving the scene (call it before survival or any other lighting takes
## over): lamps get their authored energy back, the glows go, and the night
## grade and fog are switched off. Sun and ambient are left to the caller.
func detach() -> void:
	set_process(false)
	for lamp in lamps:
		if is_instance_valid(lamp):
			lamp.light_energy = float(lamp.get_meta("daylight_base_energy", lamp.light_energy))
			lamp.omni_range = float(lamp.get_meta("daylight_base_range", lamp.omni_range))
			lamp.visible = true
	for halo in halos:
		if is_instance_valid(halo):
			halo.get_parent().remove_child(halo)
			halo.queue_free()
	halos.clear()
	lamps.clear()
	if environment != null:
		environment.adjustment_enabled = false
		environment.adjustment_saturation = 1.0
		if environment.adjustment_color_correction != null and environment.adjustment_color_correction.has_meta("daylight_grade"):
			environment.adjustment_color_correction = null
		environment.fog_enabled = false
	environment = null
	sun = null
	current = {}

## Re-samples the clock (or override_hour). snap applies at once; otherwise a
## visible change is eased in over blend_seconds and a tiny one is applied directly.
func refresh(snap := false) -> void:
	_target = sample(current_hour())
	_until_sample = update_interval
	if snap or current.is_empty() or _difference(current, _target) < .01:
		current = _target
		_blend = 1.0
		_apply_current()
	else:
		_from = current
		_blend = 0.0

static func _difference(a: Dictionary, b: Dictionary) -> float:
	var total := 0.0
	for key in ["sun_energy", "ambient_energy", "saturation", "night"]:
		total += absf(float(a[key])-float(b[key]))
	total += absf(float(a.lamp_energy)-float(b.lamp_energy))/LAMP_NIGHT_GAIN
	total += absf(float(a.fog_density)-float(b.fog_density))*50.0
	total += (a.sun_rotation-b.sun_rotation).length()/30.0
	for key in ["sun_color", "ambient_color", "background_color"]:
		var x: Color = a[key]
		var y: Color = b[key]
		total += absf(x.r-y.r)+absf(x.g-y.g)+absf(x.b-y.b)
	return total

func _ready() -> void:
	set_process(environment != null)

func _process(delta: float) -> void:
	if environment == null and sun == null:
		return
	_until_sample -= delta
	if _until_sample <= 0.0:
		refresh()
	if _blend < 1.0:
		_blend = minf(1.0, _blend+delta/maxf(blend_seconds, .001))
		current = _mix(_from, _target, _ease(_blend))
		_apply_current()

func _apply_current() -> void:
	apply(current, environment, sun, lamps)
	if _halo_material != null:
		_halo_material.set_shader_parameter("strength", clampf(float(current.lamp_energy)/LAMP_NIGHT_GAIN, 0.0, 1.0))

func _add_halos() -> void:
	halos.clear()
	if lamps.is_empty():
		return
	if _halo_material == null:
		var shader := Shader.new()
		shader.code = HALO_SHADER
		_halo_material = ShaderMaterial.new()
		_halo_material.shader = shader
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE*HALO_SIZE
	for lamp in lamps:
		var halo := lamp.get_node_or_null("DaylightHalo") as MeshInstance3D
		if halo == null:
			halo = MeshInstance3D.new()
			halo.name = "DaylightHalo"
			halo.mesh = quad
			halo.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			# A child of the light, so it hides with the light by day.
			lamp.add_child(halo)
		halo.material_override = _halo_material
		halos.append(halo)
