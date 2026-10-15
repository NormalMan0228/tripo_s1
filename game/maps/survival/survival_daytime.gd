extends RefCounted
## Time of day on an expedition map (survival_map.gd): the stage's day_progress (0..1; the night is
## its last 35 %, server/stages.py) read as an hour of the village's sky (scripts/daylight.gd KEYS),
## so every stage goes morning -> day -> golden hour -> sunset -> evening -> night -> dawn. Longer
## stages simply last longer: the mapping is by progress.
##
## Each map keeps its own grade (survival_map.gd LOOK). By day daylight's colours are scaled by the
## map's tint against daylight's noon; by night the map's night colours move as far as daylight's
## move from its 21:00 (an offset: twilight hues stay, nothing is pushed past white); energies are
## scaled on both sides. The two blend by the night weight, so noon is exactly today's tuned day
## grade, deep night exactly its night grade, and the sky in between follows the village's palette
## (warm golden hour, orange sunset, blue-purple evening, pink dawn). The sun swings from the east-right in the
## morning through the map's own noon angle to the west-left in the evening, lower (longer
## shadows) away from noon; the moon takes over while the twilight is darkest.
##
## The sunset (day_progress ~0.56-0.63, 17:36-19:06) is each map's own (SUNSET): a deep orange sun
## held strong while it sets, a warm sky and haze, a little more saturation and a warm colour grade,
## so the passing of the day reads at a glance; it gives way to the evening's blue by ~0.66. A boss
## night (the server holds day_progress at 0.82) stays in deep night under a red moon, a dark red
## sky and haze and a red grade in the shadows and mid tones; highlights (the fire, lit faces) stay
## near neutral so the walker, the creatures and the camp read.
##
## advance() eases toward the run's progress each frame and writes plain fields (no allocations);
## survival_map.gd applies them to the environment (grade_environment()), the sun and its materials.
const Daylight = preload("res://scripts/daylight.gd")

## day_progress -> hour, piecewise linear (hours past 24 wrap): sunrise as the stage opens,
## morning, the map's tuned noon at 0.3, afternoon, golden hour, sunset as the light goes, evening
## as the creatures arrive (night from 0.65), night from 0.75, dawn over the last 5 %.
const HOURS := [[0.0, 6.5], [0.15, 8.6], [0.30, 12.0], [0.50, 15.5], [0.56, 17.6], [0.60, 18.6],
	[0.63, 19.1], [0.65, 19.4], [0.68, 19.8], [0.75, 21.0], [0.95, 28.6], [1.0, 30.5]]
## The anchors the map's LOOK values belong to.
const DAY_HOUR := 12.0
const NIGHT_HOUR := 21.0
## How fast the shown hour catches up with the run's (per second): no pops when the server's
## progress steps, a jump (entering mid-stage is snapped instead) eases over a couple of seconds.
const EASE := 1.6
## The sun's path is daylight's, gentler: its height eases toward the noon angle (elevation ratio to
## this power) and its swing from noon is this share of daylight's, so an afternoon still reads as day.
const PITCH_CURVE := 0.6
const SWING := 0.8
## The moon: the map's night angle (today's -58 deg pitch, yaw + 40), drifting a little over the night.
const MOON_PITCH := 58.0
const MOON_YAW := 40.0
## Share of daylight's night saturation and colour-grade curve (daylight.gd GRADE_NIGHT) on top of
## the maps' own moonlit shading (their shaders' `night`), so the night stays today's night.
const SATURATION_SHARE := 0.45
const GRADE_SHARE := 0.4

## The sunset's hours: it rises over the golden hour (from 16:24, full at 17:36 = progress 0.56) and
## gives way to the evening (from 19:00 = 0.63, gone by 19:42 = 0.66).
const SUNSET_RISE := Vector2(16.4, 17.6)
const SUNSET_FADE := Vector2(19.0, 19.7)
## Each map's sunset: the sun's colour (share of it), its energy held against the falling daylight,
## the ambient (shadow fill), sky and haze colours with their shares, extra saturation, and the
## colour grade (curve points at daylight.gd GRADE_AT, blended in by `grade`). The forest goes deep
## orange; the quarry, warm all day, a saturated orange-red; the frost a pink-orange light against
## blue snow shadows (its ambient and its grade's shadows stay blue).
const SUNSET := {
	"forest": {"sun":["ff7a2e", 0.9], "sun_energy":0.66, "ambient":["c88f8a", 0.45], "sky":["f07a3c", 0.85],
		"haze":["f0904c", 0.8], "saturation":0.16, "grade":0.75,
		"curve":[Color(0.0, 0.0, 0.0), Color(0.37, 0.27, 0.20), Color(0.73, 0.57, 0.42), Color(1.0, 0.89, 0.74)]},
	"quarry": {"sun":["ff5a24", 0.9], "sun_energy":0.72, "ambient":["c87a7a", 0.45], "sky":["e65430", 0.85],
		"haze":["e8683c", 0.8], "saturation":0.22, "grade":0.8,
		"curve":[Color(0.02, 0.0, 0.0), Color(0.39, 0.24, 0.18), Color(0.76, 0.53, 0.40), Color(1.0, 0.86, 0.72)]},
	"frost": {"sun":["ff8a58", 0.9], "sun_energy":0.58, "ambient":["6f86d8", 0.4], "sky":["f2986e", 0.8],
		"haze":["eca484", 0.75], "saturation":0.12, "grade":0.7,
		"curve":[Color(0.0, 0.01, 0.06), Color(0.27, 0.28, 0.37), Color(0.73, 0.59, 0.52), Color(1.0, 0.89, 0.78)]},
}
## The boss night: a red moon, red-violet fill, a dark red sky and haze (shares at full boss), the
## moon a little brighter so the field still reads, and a red grade over the night's (curve as above:
## dark and mid tones red, highlights near neutral).
const BOSS_MOON := Color("ff4a3c")
const BOSS_MOON_SHARE := 0.65
const BOSS_MOON_GAIN := 1.25
const BOSS_AMBIENT := Color("a8404e")
const BOSS_AMBIENT_SHARE := 0.4
const BOSS_SKY := Color("4a0c16")
const BOSS_SKY_SHARE := 0.7
const BOSS_HAZE := Color("5e1420")
const BOSS_HAZE_SHARE := 0.6
const BOSS_SATURATION := 0.1
const BOSS_GRADE := 0.55
const BOSS_CURVE := [Color(0.03, 0.0, 0.0), Color(0.37, 0.19, 0.19), Color(0.70, 0.52, 0.49), Color(1.0, 0.93, 0.88)]
## Grade weights move in steps of this, so the curve's texture is redrawn a few times over an
## evening, not every frame.
const GRADE_STEP := 1.0/32.0

## Daylight's KEYS as typed arrays (parsed once).
static var _hours := PackedFloat32Array()
static var _sun := PackedColorArray()
static var _sun_energy := PackedFloat32Array()
static var _ambient := PackedColorArray()
static var _ambient_energy := PackedFloat32Array()
static var _sky := PackedColorArray()
static var _fog := PackedColorArray()
static var _saturation := PackedFloat32Array()

## The hour shown (0..24), eased toward the run's.
var hour := DAY_HOUR
## 0 day .. 1 night (daylight.gd's night: by the sun's elevation), the maps' shader `night`.
var night := 0.0
## Warm low-sun light (golden hour, sunset, sunrise), 0..1.
var dusk := 0.0
## The sunset's weight (SUNSET_RISE .. SUNSET_FADE), 0..1.
var sunset := 0.0
## The boss night's tint, eased 0..1.
var boss := 0.0
var started := false
## What the frame applies (survival_map.gd _apply_grade).
var sun_color := Color.WHITE
var sun_energy := 0.0
var sun_rotation := Vector3.ZERO
var ambient_color := Color.WHITE
var ambient_energy := 0.0
var background := Color.WHITE
var haze := Color.WHITE
var saturation := 1.0
## The colour grade's weights: daylight's night curve, the map's sunset curve, the boss night's.
var grade := 0.0
var sunset_grade := 0.0
var boss_grade := 0.0

# The map's tints against daylight's noon (ratios) and its offsets from daylight's night, its sun angles.
var _sun_day := Color.WHITE
var _sun_night := Color.WHITE
var _ambient_day := Color.WHITE
var _ambient_night := Color.WHITE
var _sky_day := Color.WHITE
var _sky_night := Color.WHITE
var _haze_day := Color.WHITE
var _haze_night := Color.WHITE
var _gain_sun := Vector2.ONE
var _gain_ambient := Vector2.ONE
var _noon_pitch := 52.0
var _min_pitch := 20.0
var _yaw := -32.0
# The map's sunset (SUNSET, parsed).
var _set_sun := Color.WHITE
var _set_sun_share := 0.0
var _set_sun_energy := 0.0
var _set_ambient := Color.WHITE
var _set_ambient_share := 0.0
var _set_sky := Color.WHITE
var _set_sky_share := 0.0
var _set_haze := Color.WHITE
var _set_haze_share := 0.0
var _set_saturation := 0.0
var _set_grade := 0.0
var _set_curve: Array = []
# One daylight sample (_sample writes these).
var _s_sun := Color.WHITE
var _s_sun_energy := 0.0
var _s_ambient := Color.WHITE
var _s_ambient_energy := 0.0
var _s_sky := Color.WHITE
var _s_fog := Color.WHITE
var _s_saturation := 1.0

static func _keys() -> void:
	if not _hours.is_empty(): return
	for key: Array in Daylight.KEYS:
		_hours.append(float(key[0]))
		_sun.append(Color(String(key[1])))
		_sun_energy.append(float(key[2]))
		_ambient.append(Color(String(key[3])))
		_ambient_energy.append(float(key[4]))
		_sky.append(Color(String(key[5])))
		_fog.append(Color(String(key[6])))
		_saturation.append(float(key[9]))

## The hour a stage's progress stands for (may pass 24; callers wrap).
static func hour_at(progress: float) -> float:
	var p := clampf(progress, 0.0, 1.0)
	for i in range(1, HOURS.size()):
		var b: Array = HOURS[i]
		if p <= float(b[0]):
			var a: Array = HOURS[i-1]
			return lerpf(float(a[1]), float(b[1]), (p-float(a[0]))/maxf(float(b[0])-float(a[0]), 0.0001))
	return float(HOURS[HOURS.size()-1][1])

## The map's day (LOOK colours) and night (LOOK *_night) against daylight's noon and 21:00, and its
## sunset (SUNSET[map], the forest's for a map without one).
func setup(look: Dictionary, map := "forest") -> void:
	_keys()
	_sample(DAY_HOUR)
	var noon := [_s_sun, _s_ambient, _s_sky, _s_fog, _s_sun_energy, _s_ambient_energy]
	_sample(NIGHT_HOUR)
	var late := [_s_sun, _s_ambient, _s_sky, _s_fog, _s_sun_energy, _s_ambient_energy]
	_sun_day = _ratio(Color(look.sun), noon[0])
	_sun_night = Color(look.sun_night)-late[0]
	_ambient_day = _ratio(Color(look.ambient), noon[1])
	_ambient_night = Color(look.ambient_night)-late[1]
	_sky_day = _ratio(Color(look.background), noon[2])
	_sky_night = Color(look.background_night)-late[2]
	_haze_day = _ratio(Color(look.haze), noon[3])
	_haze_night = Color(look.haze_night)-late[3]
	_gain_sun = Vector2(float(look.sun_energy)/maxf(noon[4], 0.01), float(look.sun_night_energy)/maxf(late[4], 0.01))
	_gain_ambient = Vector2(float(look.ambient_energy)/maxf(noon[5], 0.01), float(look.ambient_night_energy)/maxf(late[5], 0.01))
	_noon_pitch = absf(float(look.sun_pitch))
	_min_pitch = minf(Daylight.MIN_SHADOW_PITCH, _noon_pitch*0.6)
	_yaw = float(look.sun_yaw)
	var palette: Dictionary = SUNSET.get(map, SUNSET.forest)
	_set_sun = Color(String(palette.sun[0]))
	_set_sun_share = float(palette.sun[1])
	_set_sun_energy = float(palette.sun_energy)
	_set_ambient = Color(String(palette.ambient[0]))
	_set_ambient_share = float(palette.ambient[1])
	_set_sky = Color(String(palette.sky[0]))
	_set_sky_share = float(palette.sky[1])
	_set_haze = Color(String(palette.haze[0]))
	_set_haze_share = float(palette.haze[1])
	_set_saturation = float(palette.saturation)
	_set_grade = float(palette.grade)
	_set_curve = palette.curve
	started = false

static func _ratio(a: Color, b: Color) -> Color:
	return Color(a.r/maxf(b.r, 0.04), a.g/maxf(b.g, 0.04), a.b/maxf(b.b, 0.04), 1.0)

## Daylight.sample()'s colours and energies for `h` into the _s_* fields.
func _sample(h: float) -> void:
	h = fposmod(h, 24.0)
	var index := 0
	for i in _hours.size():
		if _hours[i] <= h: index = i
	var next := (index+1) % _hours.size()
	var span_end := _hours[next]+(24.0 if index == _hours.size()-1 else 0.0)
	var x := clampf((h-_hours[index])/maxf(span_end-_hours[index], 0.001), 0.0, 1.0)
	var t := x*x*(3.0-2.0*x)
	_s_sun = _sun[index].lerp(_sun[next], t)
	_s_sun_energy = lerpf(_sun_energy[index], _sun_energy[next], t)
	_s_ambient = _ambient[index].lerp(_ambient[next], t)
	_s_ambient_energy = lerpf(_ambient_energy[index], _ambient_energy[next], t)
	_s_sky = _sky[index].lerp(_sky[next], t)
	_s_fog = _fog[index].lerp(_fog[next], t)
	_s_saturation = lerpf(_saturation[index], _saturation[next], t)

## One frame: the run's progress (and whether the server says night / boss night) eased in;
## delta <= 0 snaps (a fresh build, tests).
func advance(progress: float, server_night: bool, boss_night: bool, delta: float) -> void:
	var target := fposmod(hour_at(progress), 24.0)
	var want_boss := 1.0 if boss_night else 0.0
	if delta <= 0.0 or not started:
		started = true
		hour = target
		boss = want_boss
	else:
		var step := minf(1.0, delta*EASE)
		hour = fposmod(hour+wrapf(target-hour, -12.0, 12.0)*step, 24.0)
		boss = move_toward(boss, want_boss, delta*0.6)
	_sample(hour)
	var elevation := Daylight.sun_elevation(hour)
	var dark := 1.0-smoothstep(-10.0, 4.0, elevation)
	# A night the server announces is dark whatever the progress says (runs from older servers).
	if server_night: dark = maxf(dark, 0.9)
	night = dark if delta <= 0.0 else move_toward(night, dark, delta*1.2)
	dusk = smoothstep(15.8, 17.8, hour)*(1.0-smoothstep(18.9, 19.6, hour))+smoothstep(5.4, 6.0, hour)*(1.0-smoothstep(6.8, 8.4, hour))
	sunset = smoothstep(SUNSET_RISE.x, SUNSET_RISE.y, hour)*(1.0-smoothstep(SUNSET_FADE.x, SUNSET_FADE.y, hour))
	var w := night
	sun_color = (_s_sun*_sun_day).lerp(_s_sun+_sun_night, w).clamp()
	sun_energy = _s_sun_energy*lerpf(_gain_sun.x, _gain_sun.y, w)
	ambient_color = (_s_ambient*_ambient_day).lerp(_s_ambient+_ambient_night, w).clamp()
	ambient_energy = _s_ambient_energy*lerpf(_gain_ambient.x, _gain_ambient.y, w)
	background = (_s_sky*_sky_day).lerp(_s_sky+_sky_night, w).clamp()
	haze = (_s_fog*_haze_day).lerp(_s_fog+_haze_night, w).clamp()
	saturation = lerpf(1.0, _s_saturation, SATURATION_SHARE)
	grade = w*GRADE_SHARE
	sunset_grade = 0.0
	boss_grade = 0.0
	if sunset > 0.001:
		# The sun keeps its strength while it goes down (daylight's falls to a tenth by 19:06), less
		# so as the evening comes.
		var hold := sunset*(1.0-0.55*smoothstep(18.6, 19.4, hour))
		sun_color = sun_color.lerp(_set_sun, _set_sun_share*sunset)
		sun_energy = lerpf(sun_energy, _set_sun_energy, hold)
		ambient_color = ambient_color.lerp(_set_ambient, _set_ambient_share*sunset)
		background = background.lerp(_set_sky, _set_sky_share*sunset)
		haze = haze.lerp(_set_haze, _set_haze_share*sunset)
		saturation += _set_saturation*sunset
		sunset_grade = _set_grade*sunset
	if boss > 0.001:
		sun_color = sun_color.lerp(BOSS_MOON, BOSS_MOON_SHARE*boss)
		sun_energy *= lerpf(1.0, BOSS_MOON_GAIN, boss)
		ambient_color = ambient_color.lerp(BOSS_AMBIENT, BOSS_AMBIENT_SHARE*boss)
		background = background.lerp(BOSS_SKY, BOSS_SKY_SHARE*boss)
		haze = haze.lerp(BOSS_HAZE, BOSS_HAZE_SHARE*boss)
		saturation += BOSS_SATURATION*boss
		boss_grade = BOSS_GRADE*boss
	_sun_angle(elevation)

## The sun's path at the map's own noon angle (daylight.gd's yaw swing and elevation curve), lower
## away from noon but never under _min_pitch; the moon's angle while the twilight is darkest.
func _sun_angle(elevation: float) -> void:
	var h := hour
	var pitch := maxf(_noon_pitch*pow(clampf(elevation/Daylight.NOON_PITCH, 0.0, 1.0), PITCH_CURVE), _min_pitch)
	var swing: float
	if h < Daylight.NOON:
		swing = lerpf(55.0, Daylight.NOON_YAW, clampf((h-Daylight.SUNRISE)/(Daylight.NOON-Daylight.SUNRISE), 0.0, 1.0))
	else:
		swing = lerpf(Daylight.NOON_YAW, -112.0, clampf((h-Daylight.NOON)/(Daylight.SUNSET-Daylight.NOON), 0.0, 1.0))
	var yaw := _yaw+(swing-Daylight.NOON_YAW)*SWING
	var night_t := clampf(fposmod(h-19.0, 24.0)/10.5, 0.0, 1.0)
	var moon := smoothstep(2.0, -6.0, elevation)
	sun_rotation = Vector3(-lerpf(pitch, MOON_PITCH, moon), lerpf(yaw, _yaw+MOON_YAW+lerpf(10.0, -15.0, night_t), moon), 0.0)

## The environment's saturation and colour grade for this frame (`graded`: the graphics setting
## "night colour", which switches the curve off as in the village). The curve is daylight.gd's night
## grade (the same points and weight as before), then the map's sunset curve, then the boss night's,
## each by its weight in GRADE_STEP steps; it is redrawn only when a weight moves a step. The curve's
## texture is tagged as daylight's (an unknown weight), so the village redraws it on its next frame
## and Daylight.detach() lets it go.
func grade_environment(env: Environment, graded: bool) -> void:
	var weights := Vector3(snappedf(grade, GRADE_STEP), snappedf(sunset_grade, GRADE_STEP), snappedf(boss_grade, GRADE_STEP)) if graded else Vector3.ZERO
	var curved := weights.x > 0.002 or weights.y > 0.002 or weights.z > 0.002
	env.adjustment_enabled = absf(saturation-1.0) > 0.005 or curved
	env.adjustment_saturation = saturation
	var lut := env.adjustment_color_correction as GradientTexture1D
	if lut == null or not lut.has_meta("survival_grade"):
		if not curved: return
		lut = GradientTexture1D.new()
		lut.width = 128
		lut.gradient = Gradient.new()
		lut.gradient.offsets = PackedFloat32Array(Daylight.GRADE_AT)
		lut.set_meta("daylight_grade", -1.0)
		lut.set_meta("survival_grade", Vector3(-1.0, -1.0, -1.0))
		env.adjustment_color_correction = lut
	if lut.get_meta("survival_grade") == weights: return
	lut.set_meta("survival_grade", weights)
	var colors := PackedColorArray()
	for i in Daylight.GRADE_AT.size():
		var level: float = Daylight.GRADE_AT[i]
		var c := Color(level, level, level).lerp(Daylight.GRADE_NIGHT[i], weights.x)
		if weights.y > 0.0 and i < _set_curve.size(): c = c.lerp(_set_curve[i], weights.y)
		if weights.z > 0.0: c = c.lerp(BOSS_CURVE[i], weights.z)
		colors.append(c)
	lut.gradient.colors = colors
