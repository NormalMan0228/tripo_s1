extends Node
## Campfire buff (server campfire.mode "buff", docs/design/CAMPFIRE_BUFF_KO.md): the hero looks
## empowered while the fire's buffs are on. Reads only the run's own fields, never decides them:
##   run.buffs[]  {id: "campfire_regeneration" (inside the lit radius) | "warmed" (5 s after-heat,
##                attack x1.1), remaining}
##   run.campfire {mode, active, x, z, radius}; run.players[] {x, z, revive {active, progress}} (co-op)
## What shows:
##   - a warm rim light on the hero (additive overlay, breathing slowly), full inside the radius and
##     fading with the after-heat's remaining seconds once outside, then gone over ~0.6 s
##   - slow embers rising round the feet while it lasts
##   - a flare (glow, ring, sparks) and buff_warm when it starts; buff_end when it ends
##   - a soft warm shimmer on each heal tick (buff_heal at most every 1.5 s)
##   - a faint ring on the ground at the fire's radius while the hero is near a lit buff fire
##   - a warm pulse on a downed teammate while they are being revived
## Hook (main.gd update_run): CampfireBuffFx.apply(app, run). Nothing shows in barrier mode or
## for an old server without these fields.
const Fx := preload("res://scripts/fx.gd")
const Art := preload("res://scripts/life_art.gd")
const GameSettings := preload("res://scripts/game_settings.gd")
const CombatAudio := preload("res://scripts/combat_audio.gd")

const WARM := Color(1.0, 0.6, 0.24)
const AFTER := 5.0
const FADE := 0.6
const HEAL_EVERY := 1.5
const RIM_CODE := """
shader_type spatial;
render_mode blend_add, unshaded, depth_draw_never, cull_back, shadows_disabled;
uniform vec4 rim_color : source_color = vec4(1.0, 0.6, 0.24, 1.0);
uniform float strength = 0.0;
uniform float flare = 0.0;
void fragment() {
	float facing = clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	float rim = pow(1.0 - facing, 2.4);
	float breath = 0.82 + 0.18 * sin(TIME * 2.6);
	ALBEDO = rim_color.rgb * (rim * breath * strength * 1.25 + strength * 0.07 + flare * 0.35);
}
"""

static var rim_shader: Shader

var app: Node
var rim: ShaderMaterial
var dressed: Node3D
var embers: CPUParticles3D
var ring: MeshInstance3D
var ring_mat: StandardMaterial3D
## Smoothed 0..1 looks and the server's targets.
var level := 0.0
var target := 0.0
var flare := 0.0
var ring_level := 0.0
var ring_target := 0.0
var on := false
var heal_clock := 0.0
var inside := false
var pulse_clock := 0.0
var downed: Array = []
## Tests: how many flares / heal shimmers / revive pulses were drawn.
var flares := 0
var shimmers := 0
var pulses := 0

static func of(host: Node) -> Node:
	var found := host.get_node_or_null("CampfireBuffFx")
	if found: return found
	var f := new()
	f.name = "CampfireBuffFx"
	f.app = host
	host.add_child(f)
	return f

## Called with every run update (main.gd update_run).
static func apply(host: Node, state: Dictionary) -> void:
	of(host).take(state)

func take(state: Dictionary) -> void:
	var camp = state.get("campfire")
	var buff_mode: bool = camp is Dictionary and str(camp.get("mode", "")) == "buff"
	var regen := false
	var warmed := 0.0
	for buff in state.get("buffs", []):
		if not buff is Dictionary: continue
		match str(buff.get("id", "")):
			"campfire_regeneration": regen = true
			"warmed": warmed = maxf(warmed, float(buff.get("remaining", 0.0)))
	var alive: bool = str(state.get("status", "active")) == "active" and float(state.get("hp", 1.0)) > 0.0
	inside = buff_mode and alive and regen
	target = 0.0 if not buff_mode or not alive else (1.0 if regen else clampf(warmed/AFTER, 0.0, 1.0)*0.85)
	var lit: bool = buff_mode and camp is Dictionary and bool(camp.get("active", float(state.get("fire_remaining", 0.0)) > 0.0))
	ring_target = 0.0
	if lit and is_instance_valid(app.get("player")):
		var hero: Vector3 = app.player.global_position
		var d := Vector2(hero.x-float(camp.get("x", 0.0)), hero.z-float(camp.get("z", 0.0))).length()
		var r := float(camp.get("radius", 4.0))
		ring_target = clampf(1.0-(d-r)/3.0, 0.0, 1.0)
		_place_ring(Vector3(float(camp.get("x", 0.0)), hero.y, float(camp.get("z", 0.0))), r)
	downed.clear()
	if buff_mode:
		for mate in state.get("players", []):
			if mate is Dictionary and mate.get("revive") is Dictionary and bool(mate.revive.get("active", false)):
				downed.append(Vector3(float(mate.get("x", 0.0)), 0.0, float(mate.get("z", 0.0))))
	if target > 0.01 and not on: _start()
	elif target <= 0.01 and on: _end()

func _start() -> void:
	on = true
	if not _dress(): return
	flare = 1.0
	flares += 1
	var world := _world()
	if world != null:
		var feet: Vector3 = app.player.global_position
		Fx.glow(world, feet+Vector3(0, 1.0, 0), Color("ffb45a"), 2.0, 0.8)
		Fx.ring(world, feet, 1.5, Color(1.0, 0.72, 0.4, 0.75), 0.6)
		Fx.burst(world, feet+Vector3(0, 0.6, 0), "spark", 14, Color(0,0,0,0), 0.35)
	CombatAudio.play(app, "buff_warm")
	heal_clock = 0.0

func _end() -> void:
	on = false
	CombatAudio.play(app, "buff_end")

func _process(delta: float) -> void:
	if app == null or not is_instance_valid(app): return
	if str(app.get("screen")) != "survival":
		target = 0.0
		ring_target = 0.0
		on = false
	level = move_toward(level, target, delta/FADE)
	flare = maxf(0.0, flare-delta*2.2)
	ring_level = move_toward(ring_level, ring_target, delta*1.5)
	if level > 0.001 or flare > 0.0:
		if not _dress(): return
		rim.set_shader_parameter("strength", level)
		rim.set_shader_parameter("flare", flare)
	elif is_instance_valid(dressed):
		_undress()
	if is_instance_valid(embers):
		embers.emitting = level > 0.15
	if is_instance_valid(ring_mat):
		ring.visible = ring_level > 0.01
		ring_mat.albedo_color.a = 0.32*ring_level*(0.8+0.2*sin(Time.get_ticks_msec()*0.002))
	if inside and on:
		heal_clock += delta
		if heal_clock >= HEAL_EVERY:
			heal_clock = 0.0
			_shimmer()
	if not downed.is_empty():
		pulse_clock += delta
		if pulse_clock >= 0.9:
			pulse_clock = 0.0
			_pulse()

## Rim overlay on every mesh of the hero (tools and held things glow along) and an ember emitter at
## the feet; rebuilt when the hero is a new walker (a new run, a changed look).
func _dress() -> bool:
	var hero = app.get("player")
	if not (hero is Node3D) or not is_instance_valid(hero) or not hero.is_inside_tree(): return false
	if hero == dressed and is_instance_valid(embers): return true
	if is_instance_valid(dressed): _undress()
	if rim_shader == null:
		rim_shader = Shader.new()
		rim_shader.code = RIM_CODE
	if rim == null:
		rim = ShaderMaterial.new()
		rim.shader = rim_shader
		rim.set_shader_parameter("rim_color", WARM)
	for mesh in hero.find_children("*", "MeshInstance3D", true, false):
		if (mesh as MeshInstance3D).material_overlay == null: mesh.material_overlay = rim
	embers = CPUParticles3D.new()
	embers.name = "BuffEmbers"
	embers.mesh = QuadMesh.new()
	(embers.mesh as QuadMesh).size = Vector2.ONE
	var m := StandardMaterial3D.new()
	m.albedo_texture = Fx.tex("spark")
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.billboard_keep_scale = true
	embers.material_override = m
	embers.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	embers.amount = maxi(3, roundi(12*GameSettings.particle_scale()))
	embers.lifetime = 1.5
	embers.local_coords = false
	embers.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	embers.emission_sphere_radius = 0.38
	embers.direction = Vector3.UP
	embers.spread = 18.0
	embers.initial_velocity_min = 0.35
	embers.initial_velocity_max = 0.8
	embers.gravity = Vector3(0, 0.45, 0)
	embers.damping_min = 0.2
	embers.damping_max = 0.4
	embers.tangential_accel_min = -0.4
	embers.tangential_accel_max = 0.4
	embers.scale_amount_min = 0.05
	embers.scale_amount_max = 0.11
	var fade := Gradient.new()
	fade.set_color(0, Color(1.0, 0.85, 0.5, 0.0))
	fade.add_point(0.15, Color(1.0, 0.7, 0.3, 1.0))
	fade.set_color(1, Color(1.0, 0.35, 0.1, 0.0))
	embers.color_ramp = fade
	embers.emitting = false
	hero.add_child(embers)
	embers.position = Vector3(0, 0.25, 0)
	dressed = hero
	return true

func _undress() -> void:
	if is_instance_valid(dressed):
		for mesh in dressed.find_children("*", "MeshInstance3D", true, false):
			if mesh.material_overlay == rim: mesh.material_overlay = null
	if is_instance_valid(embers): embers.queue_free()
	dressed = null
	embers = null

func _world() -> Node3D:
	var world = app.get("world")
	if world is Node3D and is_instance_valid(world) and world.is_inside_tree(): return world
	return null

func _place_ring(at: Vector3, radius: float) -> void:
	var world := _world()
	if world == null: return
	if not is_instance_valid(ring):
		ring = MeshInstance3D.new()
		ring.name = "BuffRadius"
		ring.mesh = Art.mesh("ring")
		ring_mat = StandardMaterial3D.new()
		ring_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		ring_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		ring_mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
		ring_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
		ring_mat.albedo_color = Color(1.0, 0.66, 0.3, 0.0)
		ring.material_override = ring_mat
		ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		ring.visible = false
		world.add_child(ring)
	ring.global_position = at+Vector3(0, 0.05, 0)
	ring.scale = Vector3.ONE*radius

## A heal tick inside the radius: a few warm glints rise off the hero's shoulders.
func _shimmer() -> void:
	var world := _world()
	if world == null or not is_instance_valid(app.get("player")): return
	shimmers += 1
	Fx.burst(world, app.player.global_position+Vector3(0, 1.1, 0), "sparkle", 4, Color("ffd38a"), 0.35)
	CombatAudio.play(app, "buff_heal")

## A downed teammate being revived by the fire: a warm ring and glow pulse on them.
func _pulse() -> void:
	var world := _world()
	if world == null: return
	for at in downed:
		var y: float = app.player.global_position.y if is_instance_valid(app.get("player")) else 0.0
		var p: Vector3 = at+Vector3(0, y, 0)
		pulses += 1
		Fx.ring(world, p, 1.6, Color(1.0, 0.7, 0.35, 0.6), 0.8)
		Fx.glow(world, p+Vector3(0, 0.5, 0), Color("ffb45a"), 1.4, 0.8)

## The rim overlay, the embers' additive particles and the additive radius ring each compile a shader
## on first draw (a 184 ms hitch when the buff first showed): draw them once, invisibly, while the
## expedition loads (CombatFx.warm_up).
static func warm_up(world: Node3D, at: Vector3) -> void:
	if rim_shader == null:
		rim_shader = Shader.new()
		rim_shader.code = RIM_CODE
	var holder := Node3D.new()
	world.add_child(holder)
	holder.global_position = at
	var ball := MeshInstance3D.new()
	var sphere := SphereMesh.new()
	sphere.radius = 0.02
	sphere.height = 0.04
	ball.mesh = sphere
	var clear := StandardMaterial3D.new()
	clear.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	clear.albedo_color = Color(1, 1, 1, 0.0)
	ball.material_override = clear
	var rim_warm := ShaderMaterial.new()
	rim_warm.shader = rim_shader
	rim_warm.set_shader_parameter("strength", 0.0)
	ball.material_overlay = rim_warm
	holder.add_child(ball)
	var ring_warm := MeshInstance3D.new()
	ring_warm.mesh = Art.mesh("ring")
	var rm := StandardMaterial3D.new()
	rm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	rm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	rm.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	rm.cull_mode = BaseMaterial3D.CULL_DISABLED
	rm.albedo_color = Color(0, 0, 0, 0.0)
	ring_warm.material_override = rm
	ring_warm.scale = Vector3.ONE*0.05
	holder.add_child(ring_warm)
	var sparks := CPUParticles3D.new()
	sparks.mesh = QuadMesh.new()
	var m := StandardMaterial3D.new()
	m.albedo_texture = Fx.tex("spark")
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.billboard_keep_scale = true
	sparks.material_override = m
	sparks.amount = 1
	sparks.lifetime = 0.5
	sparks.color = Color(0, 0, 0, 0.0)
	sparks.scale_amount_min = 0.01
	sparks.scale_amount_max = 0.01
	holder.add_child(sparks)
	sparks.emitting = true
	holder.get_tree().create_timer(1.0).timeout.connect(func(): if is_instance_valid(holder): holder.queue_free())
