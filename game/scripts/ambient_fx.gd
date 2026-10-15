extends Node
## Life in the village air, around wherever the hero walks: fireflies blinking and drifting at
## night, petals and seed fluff riding the breeze by day, cross-faded by daylight.gd's "night"
## value. Two pooled CPU emitters that follow the hero (particles stay where they were born), about
## forty particles in all, thinned by reduced motion; off outside the village.
##   AmbientFx.attach(app)      (main.gd, once)
const Fx := preload("res://scripts/fx.gd")
const GameSettings := preload("res://scripts/game_settings.gd")

const FIREFLIES := 30
const DRIFT := 10
## Where they live round the hero (half extents, m) and how high.
const AREA := Vector3(7.5, 1.0, 7.5)
const FLY_HEIGHT := 1.3
const DRIFT_HEIGHT := 2.6
## The breeze the day's petals ride.
const WIND := Vector3(0.55, 0.0, 0.2)

var app: Node
var flies: CPUParticles3D
var drift: CPUParticles3D
var night := 0.0

static func attach(host: Node) -> Node:
	var found := host.get_node_or_null("AmbientFx")
	if found: return found
	var a := new()
	a.name = "AmbientFx"
	a.app = host
	host.add_child(a)
	return a

func _process(_delta: float) -> void:
	var hero = app.get("player") if app != null and is_instance_valid(app) else null
	var world = app.get("world") if app != null and is_instance_valid(app) else null
	var village: bool = str(app.get("screen")) == "village" and hero is Node3D and is_instance_valid(hero) and hero.is_inside_tree() and world is Node3D and is_instance_valid(world)
	if not village:
		_stop()
		return
	if not is_instance_valid(flies) or flies.get_parent() != world: _build(world)
	var light = app.get("daylight")
	if light != null and is_instance_valid(light) and light.get("current") is Dictionary:
		night = clampf(float(light.current.get("night", night)), 0.0, 1.0)
	var at: Vector3 = hero.global_position
	flies.global_position = at+Vector3(0, FLY_HEIGHT, 0)
	drift.global_position = at+Vector3(-WIND.x*4.0, DRIFT_HEIGHT, -WIND.z*4.0)
	flies.emitting = night > 0.45
	drift.emitting = night < 0.35

func _stop() -> void:
	if is_instance_valid(flies): flies.emitting = false
	if is_instance_valid(drift): drift.emitting = false

func _build(world: Node3D) -> void:
	if is_instance_valid(flies): flies.queue_free()
	if is_instance_valid(drift): drift.queue_free()
	var scale := GameSettings.particle_scale()
	# Fireflies: soft additive dots wandering slowly, blinking on and off over their life.
	flies = _emitter(world, "spark", true, maxi(4, roundi(FIREFLIES*scale)), 6.0)
	flies.name = "AmbientFireflies"
	flies.emission_box_extents = AREA
	flies.direction = Vector3.UP
	flies.spread = 180.0
	flies.initial_velocity_min = 0.08
	flies.initial_velocity_max = 0.3
	flies.gravity = Vector3(0, 0.02, 0)
	flies.tangential_accel_min = -0.12
	flies.tangential_accel_max = 0.12
	flies.scale_amount_min = 0.17
	flies.scale_amount_max = 0.26
	var blink := Gradient.new()
	var glow := Color(0.86, 1.0, 0.48)
	blink.set_color(0, Color(glow, 0.0))
	for point in [[0.12, 1.0], [0.28, 0.15], [0.4, 0.95], [0.55, 0.1], [0.7, 1.0], [0.85, 0.3]]:
		blink.add_point(point[0], Color(glow, point[1]))
	blink.set_color(blink.get_point_count()-1, Color(glow, 0.0))
	flies.color_ramp = blink
	# Day drift: a few petals and seed fluff crossing on the breeze, turning as they fall slowly.
	drift = _emitter(world, "petal", false, maxi(2, roundi(DRIFT*scale)), 7.0)
	drift.name = "AmbientDrift"
	drift.emission_box_extents = Vector3(AREA.x, 0.6, AREA.z)
	drift.direction = WIND.normalized()
	drift.spread = 20.0
	drift.initial_velocity_min = 0.35
	drift.initial_velocity_max = 0.7
	drift.gravity = Vector3(0, -0.12, 0)
	drift.angle_min = -180.0
	drift.angle_max = 180.0
	drift.angular_velocity_min = -90.0
	drift.angular_velocity_max = 90.0
	drift.tangential_accel_min = -0.2
	drift.tangential_accel_max = 0.2
	drift.scale_amount_min = 0.15
	drift.scale_amount_max = 0.23
	var fade := Gradient.new()
	fade.set_color(0, Color(1, 1, 1, 0))
	fade.add_point(0.12, Color(1, 1, 1, 0.95))
	fade.add_point(0.85, Color(1, 1, 1, 0.9))
	fade.set_color(fade.get_point_count()-1, Color(1, 1, 1, 0))
	drift.color_ramp = fade
	var mix := Gradient.new()
	mix.set_color(0, Color("f6a8c8"))
	mix.add_point(0.35, Color("fbd3e3"))
	mix.add_point(0.7, Color("fffbea"))
	mix.set_color(mix.get_point_count()-1, Color("f4c4dc"))
	mix.interpolation_mode = Gradient.GRADIENT_INTERPOLATE_CONSTANT
	drift.color_initial_ramp = mix

func _emitter(world: Node3D, symbol: String, glow: bool, amount: int, life: float) -> CPUParticles3D:
	var e := CPUParticles3D.new()
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	e.mesh = quad
	var m := StandardMaterial3D.new()
	m.albedo_texture = Fx.tex(symbol)
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.billboard_keep_scale = true
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	if glow:
		m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	else:
		m.roughness = 1.0
	e.material_override = m
	e.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	e.amount = amount
	e.lifetime = life
	e.preprocess = life
	e.local_coords = false
	e.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	e.emitting = false
	world.add_child(e)
	return e
