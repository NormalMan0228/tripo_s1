extends RefCounted
## One simple sky for every window, outside and in: a two-colour gradient (zenith over horizon) made
## from Daylight.sample(hour), so window glass follows the time of day the same way everywhere.
##  - Exterior glass (maps/archipelago/building_exterior.gdshader `sky_top`/`sky_horizon`/`sky_mix`):
##    by day the panes reflect it; at night the warm room glow (where someone is awake) sits over it.
##    building_dressing.gd update() feeds it.
##  - Interior window views (interiors.gd WINDOW_SHADER): the painted outlook keeps its scenery
##    (hills, sea, roofs, the moon and stars) and the gradient replaces its sky. studio.gd's
##    apply_daylight feeds it with the sample it already takes.
## The hour comes from the callers (Daylight's override_hour / the studio's hour_override): there is
## no second time override here.
const Daylight = preload("res://scripts/daylight.gd")
## Deep zenith blue the clear-day background leans towards (the background itself is the pale horizon).
const DAY_ZENITH := Color("5f9fd6")

## {top, horizon} colours for a Daylight.sample() dictionary.
static func gradient(values: Dictionary) -> Dictionary:
	var night := float(values.get("night", 0.0))
	var day := float(values.get("daylight", 1.0))
	var background: Color = values.get("background_color", Color("b8e3ee"))
	var haze: Color = values.get("fog_color", background)
	var sun: Color = values.get("sun_color", Color.WHITE)
	# Low sun (dawn, dusk): the horizon warms with the sun's colour; a high sun leaves it pale.
	var low := (1.0-smoothstep(0.0, 0.45, day))*(1.0-night)
	var top := background.lerp(DAY_ZENITH, 0.5*day*(1.0-night)).darkened(0.18*night)
	var horizon := haze.lerp(sun, 0.5*low)
	return {"top": top, "horizon": horizon}

static func at(hour: float) -> Dictionary:
	return gradient(Daylight.sample(hour))

## Writes the gradient into a material with `sky_top` and `sky_horizon` (either window shader).
static func feed(material: ShaderMaterial, values: Dictionary) -> void:
	if material == null: return
	var sky := gradient(values)
	material.set_shader_parameter("sky_top", sky.top)
	material.set_shader_parameter("sky_horizon", sky.horizon)
