extends Node3D
## The tutorial's guidance in the world (the first expedition: run.tutorial; its goals are
## server/catalog.py TUTORIAL_REQUIREMENTS: gather 6, craft an axe, light a fire, defeat 2
## creatures). Effects, never words (the goal card on the HUD is the UI's). One goal at a time in
## the server's order, read from the run's own counters (harvested, crafted.axe, fires, kills; the
## targets from run.story.goals):
##  - gather: a gold gem bobbing over the resource to take next (what the next goals need first:
##    stone and wood for the axe, wood for the fire, else the nearest), a soft light pillar and a
##    ring under it, sparkles, and its model's outline pulsing (material_overlay);
##  - craft: with the materials in the bag, the bag's icon (the hotbar's bag opens the craft list)
##    bobs over the walker with sparkles and a ring at its feet; without them, the missing
##    material is marked as in gather;
##  - fire: the hearth's zone (the 3 m where the fire can be lit) glows as a ring with the gem over
##    the hearth; inside it the fire's icon bobs over the walker; short of wood, a tree is marked;
##  - creatures: a red gem and ring on the nearest one (on any that comes close before then too);
##    by day the gem waits over the hearth for the night.
## A goal met gives a sparkle burst, a ring and a chime at the walker; once the tutorial is cleared
## everything fades out. The look is the village route guide's (guide.gd: its pillar and ring
## shaders, its cut gem). The pieces are made once and moved; the targets are re-picked a few times
## a second; a frame only eases positions and bobs the gems.
const Fx = preload("res://scripts/fx.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const ICON_BAG := "res://assets/ui/icons/bag.png"
const ICON_FIRE := "res://assets/ui/icons/fire.png"
const GOLD := Color(1.0, 0.8, 0.4)
const RED := Color(1.0, 0.34, 0.26)
## server/simulation.py: the fire is lit within 3 m of the camp centre; harvest reach 2.3 m.
const CAMP_REACH := 3.0
## Goals in the server's order (TUTORIAL_REQUIREMENTS) and their targets when the run has no story.
enum {GATHER, CRAFT, FIRE, KILL, DONE}
const TARGETS := [6, 1, 1, 2]
## A creature this close is marked whatever the goal.
const THREAT_NEAR := 6.0
const PILLAR := 3.0
## The village guide's gem, a little larger at the expedition camera's distance.
const GEM_SIZE := 1.3
const REFRESH := 0.2
## The first seconds every piece is drawn (unseen) once, so its shader compiles under the card:
## a group every few frames (the beacon, the hearth ring and the creature mark, the walker's cue,
## the outline), not all in the map's first frame, which is long already (~30-40 ms of compiles).
const WARM := 1.2
const WARM_FRAMES := [3, 6, 9, 12]
const EMPTY := []

## A pulsing gold rim over the resource to take (as material_overlay; blended, not added, so it
## reads on bright ground by day; the prop shader's wind sway repeated so it stays on the leaves).
const OUTLINE_SHADER := """
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_back, shadows_disabled, fog_disabled;
uniform vec4 tint : source_color = vec4(1.0, 0.8, 0.4, 1.0);
uniform float strength = 1.0;
uniform float calm = 0.0;
uniform float wind = 0.0;
uniform float wind_height = 4.0;
void vertex() {
	if (wind > 0.0) {
		vec3 world = (MODEL_MATRIX*vec4(VERTEX, 1.0)).xyz;
		float h = max(VERTEX.y, 0.0)/wind_height;
		float sway = sin(TIME*1.3+world.x*0.37+world.z*0.29)+0.45*sin(TIME*2.7+world.x*0.9);
		vec3 push = vec3(sway, 0.0, sway*0.6)*wind*h*h;
		VERTEX += inverse(mat3(MODEL_MATRIX))*push;
	}
	VERTEX += NORMAL*0.015;
}
void fragment() {
	float rim = pow(1.0-clamp(dot(NORMAL, VIEW), 0.0, 1.0), 1.8);
	float beat = calm > 0.5 ? 0.7 : 0.5+0.5*sin(TIME*4.2);
	ALBEDO = tint.rgb;
	ALPHA = clamp((rim*1.1+0.12*beat)*(0.55+0.45*beat)*strength, 0.0, 0.9);
}
"""

var map: Node
var step := -1
var counts := PackedInt32Array([0, 0, 0, 0])
var targets := PackedInt32Array(TARGETS)
var met := [false, false, false, false]
## 1 shown .. 0 gone (cleared).
var fade := 1.0
var clearing := false
var clock := 0.0
var refresh := 0.0
var warm := WARM
var frames := 0
var calm := false
# Where the gold gem stands (ground point; INF: hidden) and how high it floats there.
var goal_at := Vector3.INF
var goal_top := 1.6
var gem_height := 1.6
var goal_dim := false
var goal_model: MeshInstance3D
var sparkle_at := Vector3.INF
## Over the walker: "" (none), "bag" (craft), "fire" (light the fire here).
var cue_kind := ""
var show_zone := false
var threat_node: Node3D
# Eased strengths per piece (0..1).
var beacon_s := 0.0
var zone_s := 0.0
var cue_s := 0.0
var threat_s := 0.0
var applied := PackedFloat32Array([-1.0, -1.0, -1.0, -1.0, -1.0])
var night := 0.0
# Pieces.
var beacon: Node3D
var gem: Node3D
var pillar_material: ShaderMaterial
var ring_material: ShaderMaterial
var zone: MeshInstance3D
var zone_material: ShaderMaterial
var cue: Node3D
var icon: Sprite3D
var cue_glow_material: StandardMaterial3D
var foot: MeshInstance3D
var foot_material: ShaderMaterial
var threat: Node3D
var threat_gem: Node3D
var threat_material: ShaderMaterial
var outline_material: ShaderMaterial
var sparkles: CPUParticles3D
var warmer: MeshInstance3D
var icons := {}
## One ring shader for the four rings (one compile).
var ring_shader: Shader

func _ready() -> void:
	name = "TutorialGuide"
	map = get_parent()
	process_priority = 110
	calm = GameSettings.reduced_motion()
	_build()

# ------------------------------------------------------------------ pieces
func _build() -> void:
	var village_guide: GDScript = load("res://scripts/guide.gd")
	var pillar_code: String = village_guide.PILLAR_SHADER
	var ring_code: String = village_guide.RING_SHADER
	var start := Vector3(0.0, 0.0, 1.4)
	beacon = _node("Beacon", start)
	var tube := CylinderMesh.new()
	tube.top_radius = 0.2
	tube.bottom_radius = 0.34
	tube.height = PILLAR
	tube.radial_segments = 14
	tube.rings = 1
	tube.cap_top = false
	tube.cap_bottom = false
	ring_shader = Shader.new()
	ring_shader.code = ring_code
	var pillar_shader := Shader.new()
	pillar_shader.code = pillar_code
	pillar_material = _shader(pillar_shader, 2, GOLD)
	pillar_material.set_shader_parameter("height", PILLAR)
	_mesh(beacon, tube, pillar_material, Vector3(0, PILLAR*0.5, 0))
	ring_material = _shader(ring_shader, 3, GOLD)
	_mesh(beacon, _plane(3.2), ring_material, Vector3(0, 0.06, 0))
	gem = _gem(beacon, Color("ffcf5c"), Color("ffb440"))
	zone_material = _shader(ring_shader, 3, Color(1.0, 0.72, 0.36))
	zone = _mesh(self, _plane(CAMP_REACH*4.0+0.4), zone_material, Vector3(0, 0.05, 0))
	cue = _node("Cue", start)
	icon = Sprite3D.new()
	icon.pixel_size = 0.0072
	icon.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	icon.no_depth_test = true
	icon.render_priority = 7
	icon.texture = _icon(ICON_BAG)
	icon.position.y = 2.7
	icon.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	cue.add_child(icon)
	cue_glow_material = StandardMaterial3D.new()
	cue_glow_material.albedo_texture = Fx.tex("soft")
	cue_glow_material.albedo_color = Color(1.0, 0.78, 0.42, 0.0)
	cue_glow_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	cue_glow_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	cue_glow_material.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	cue_glow_material.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	cue_glow_material.no_depth_test = true
	cue_glow_material.render_priority = 6
	var glow_quad := QuadMesh.new()
	glow_quad.size = Vector2(1.8, 1.8)
	_mesh(icon, glow_quad, cue_glow_material, Vector3.ZERO)
	foot_material = _shader(ring_shader, 3, GOLD)
	foot = _mesh(cue, _plane(2.4), foot_material, Vector3(0, 0.06, 0))
	threat = _node("Threat", start)
	threat_material = _shader(ring_shader, 3, RED)
	threat_material.set_shader_parameter("rim", Color(0.3, 0.04, 0.02))
	_mesh(threat, _plane(2.8), threat_material, Vector3(0, 0.07, 0))
	threat_gem = _gem(threat, Color("ff6a50"), Color("ff3a24"))
	outline_material = ShaderMaterial.new()
	var outline := Shader.new()
	outline.code = OUTLINE_SHADER
	outline_material.shader = outline
	outline_material.set_shader_parameter("tint", GOLD)
	sparkles = CPUParticles3D.new()
	sparkles.name = "Sparkles"
	sparkles.mesh = QuadMesh.new()
	# Blended gold stars (fx.gd's "flat" shading): additive ones vanish on sunlit ground.
	sparkles.material_override = Fx._particle_material("star", "flat")
	sparkles.amount = maxi(5, roundi(16*GameSettings.particle_scale()))
	sparkles.lifetime = 1.2
	sparkles.local_coords = false
	sparkles.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	sparkles.emission_sphere_radius = 0.6
	sparkles.direction = Vector3.UP
	sparkles.spread = 180.0
	sparkles.initial_velocity_min = 0.2
	sparkles.initial_velocity_max = 0.7
	sparkles.gravity = Vector3(0, 0.5, 0)
	sparkles.damping_min = 0.6
	sparkles.damping_max = 1.0
	# fx.gd's star is thin: larger than its village sparkles, read from the expedition camera.
	sparkles.scale_amount_min = 0.34
	sparkles.scale_amount_max = 0.56
	var size := Curve.new()
	size.add_point(Vector2(0, 0.2)); size.add_point(Vector2(0.2, 1.0)); size.add_point(Vector2(1, 0.3))
	sparkles.scale_amount_curve = size
	var fade_out := Gradient.new()
	fade_out.set_color(0, Color(1, 1, 1, 1))
	fade_out.set_color(1, Color(1, 1, 1, 0))
	sparkles.color_ramp = fade_out
	var mix := Gradient.new()
	mix.set_color(0, Color("ffe066"))
	mix.set_color(1, Color("ffb52e"))
	mix.add_point(0.5, Color("fff6c8"))
	mix.interpolation_mode = Gradient.GRADIENT_INTERPOLATE_CONSTANT
	sparkles.color_initial_ramp = mix
	sparkles.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	sparkles.emitting = false
	add_child(sparkles)
	sparkles.global_position = start+Vector3(0, 0.9, 0)
	# Drawn once under the card (all at strength 0): the outline's shader on a small stand-in.
	warmer = MeshInstance3D.new()
	var ball := SphereMesh.new()
	ball.radius = 0.2
	ball.height = 0.4
	ball.radial_segments = 8
	ball.rings = 4
	warmer.mesh = ball
	warmer.material_override = outline_material
	warmer.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	warmer.visible = false
	add_child(warmer)
	warmer.global_position = start+Vector3(0, 0.3, 0)
	_apply_strengths(true)
	_show_pieces()

func _node(label: String, at: Vector3) -> Node3D:
	var node := Node3D.new()
	node.name = label
	node.top_level = true
	add_child(node)
	node.global_position = at
	return node

func _mesh(parent: Node3D, mesh: Mesh, material: Material, at: Vector3) -> MeshInstance3D:
	var piece := MeshInstance3D.new()
	piece.mesh = mesh
	piece.material_override = material
	piece.position = at
	piece.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(piece)
	return piece

func _plane(size: float) -> PlaneMesh:
	var plane := PlaneMesh.new()
	plane.size = Vector2(size, size)
	return plane

func _shader(shader: Shader, priority: int, tint: Color) -> ShaderMaterial:
	var material := ShaderMaterial.new()
	material.shader = shader
	material.render_priority = priority
	material.set_shader_parameter("tint", tint)
	material.set_shader_parameter("calm", 1.0 if calm else 0.0)
	return material

## The village guide's cut gem pointing down: short crown, long pavilion.
func _gem(parent: Node3D, color: Color, glow: Color) -> Node3D:
	var holder := Node3D.new()
	holder.position.y = 1.6
	parent.add_child(holder)
	var shine := StandardMaterial3D.new()
	shine.albedo_color = color
	shine.emission_enabled = true
	shine.emission = glow
	shine.emission_energy_multiplier = 1.0
	shine.metallic = 0.25
	shine.roughness = 0.3
	for half in [[0.3, 0.0, 0.24, 0.15], [0.6, 0.24, 0.0, -0.3]]:
		var point := CylinderMesh.new()
		point.height = half[0]
		point.top_radius = half[1]
		point.bottom_radius = half[2]
		point.radial_segments = 4
		point.rings = 1
		_mesh(holder, point, shine, Vector3(0, half[3], 0))
	return holder

func _icon(path: String) -> Texture2D:
	if not icons.has(path): icons[path] = load(path) if ResourceLoader.exists(path) else null
	return icons[path]

# ------------------------------------------------------------------ goals
func _process(delta: float) -> void:
	if not is_instance_valid(map): return
	var app: Node = map.app
	clock += delta
	frames += 1
	night = float(map.night)
	if warm > 0.0:
		warm -= delta
		# Not over before the last group was drawn (a slow card).
		if warm <= 0.0 and not _staged(3): warm = 0.001
		if is_instance_valid(warmer): warmer.visible = warm > 0.0 and _staged(3)
		if warm <= 0.0 and is_instance_valid(warmer):
			warmer.queue_free()
			warmer = null
		_show_pieces()
	if not is_instance_valid(app) or not (app.get(&"run") is Dictionary): return
	var player = app.get(&"player")
	if not is_instance_valid(player): return
	refresh -= delta
	if refresh <= 0.0:
		refresh = REFRESH
		_plan(app)
	_ease(delta, player as Node3D)

## The goal now and what marks it.
func _plan(app: Node) -> void:
	var run: Dictionary = app.get(&"run")
	if run.is_empty(): return
	_read_counts(run)
	var now := DONE
	var cleared := true
	for i in 4: cleared = cleared and counts[i] >= targets[i]
	for i in 4:
		var done: bool = counts[i] >= targets[i]
		# A goal met while the guide watched (the last one is the clear's own burst).
		if done and not met[i] and step >= 0 and not cleared: _celebrate(app, false)
		met[i] = done
		if not done and now == DONE: now = i
	step = now
	if run.get("status", "active") != "active" or step == DONE:
		if not clearing:
			clearing = true
			_celebrate(app, true)
		return
	var at := Vector2(float(run.get("x", 0.0)), float(run.get("z", 0.0)))
	var inv: Dictionary = run.get("inventory", {})
	var wood := int(inv.get("wood", 0))
	var stone := int(inv.get("stone", 0))
	goal_at = Vector3.INF
	goal_dim = false
	cue_kind = ""
	show_zone = false
	sparkle_at = Vector3.INF
	var model: MeshInstance3D = null
	var want_threat := false
	match step:
		GATHER:
			model = _mark_resource(app, run, _wanted_kind(wood, stone), at)
		CRAFT:
			if wood >= 3 and stone >= 2: cue_kind = "bag"
			else: model = _mark_resource(app, run, "stone" if stone < 2 else "tree", at)
		FIRE:
			if wood < 2: model = _mark_resource(app, run, "tree", at)
			else:
				show_zone = true
				if at.length() <= CAMP_REACH-0.2: cue_kind = "fire"
				else: _mark_hearth(false)
		KILL:
			want_threat = true
	# The nearest creature: the goal's mark, or a warning when one comes close earlier.
	var nearest: Node3D = null
	if not met[KILL]:
		var best := INF
		var nodes = app.get(&"enemy_nodes")
		var enemies = run.get("enemies")
		if not (nodes is Dictionary) or not (enemies is Array): enemies = EMPTY
		for enemy in enemies:
			var node = (nodes as Dictionary).get(enemy.get("id", ""))
			if not is_instance_valid(node): continue
			var d := at.distance_to(Vector2(float(enemy.x), float(enemy.z)))
			if d < best:
				best = d
				nearest = node
		if nearest != null and not want_threat and best > THREAT_NEAR: nearest = null
	threat_node = nearest
	if step == KILL and nearest == null: _mark_hearth(true)
	if cue_kind != "": sparkle_at = Vector3.INF
	_outline(model)

## The run's counters (harvested, crafted.axe, fires, kills) and the server's targets
## (run.story.goals, in TUTORIAL_REQUIREMENTS order; the defaults without a story).
func _read_counts(run: Dictionary) -> void:
	var crafted = run.get("crafted")
	counts[0] = int(run.get("harvested", 0))
	counts[1] = int((crafted as Dictionary).get("axe", 0)) if crafted is Dictionary else 0
	counts[2] = int(run.get("fires", 0))
	counts[3] = int(run.get("kills", 0))
	var story = run.get("story")
	var goals = story.get("goals") if story is Dictionary else null
	if goals is Array and (goals as Array).size() == 4:
		for i in 4: targets[i] = int(goals[i].get("target", TARGETS[i]))

## What to gather first: stone and wood for the axe, then wood for the fire; else the nearest.
func _wanted_kind(wood: int, stone: int) -> String:
	var axe_done: bool = counts[CRAFT] >= targets[CRAFT]
	if not axe_done and stone < 2: return "stone"
	var need := (3 if not axe_done else 0)+(2 if counts[FIRE] < targets[FIRE] else 0)
	if wood < need: return "tree"
	return ""

## The nearest standing resource of `kind` ("" any; any when none of that kind is left).
func _mark_resource(app: Node, run: Dictionary, kind: String, at: Vector2) -> MeshInstance3D:
	var best := INF
	var pick = null
	var listed = run.get("nodes")
	if not (listed is Array): return null
	# The nearest of `kind`; any kind when none of it is left.
	for any in 2:
		if any == 1 and (pick != null or kind == ""): break
		for n in listed:
			if float(n.get("quantity", 0)) <= 0.0: continue
			if any == 0 and kind != "" and str(n.get("kind", "")) != kind: continue
			var d := at.distance_to(Vector2(float(n.x), float(n.z)))
			if d < best:
				best = d
				pick = n
	if pick == null: return null
	goal_at = Vector3(float(pick.x), 0.0, float(pick.z))
	goal_top = 1.35
	sparkle_at = goal_at+Vector3(0, 0.7, 0)
	var nodes = app.get(&"nodes")
	var root = (nodes as Dictionary).get(pick.get("id", "")) if nodes is Dictionary else null
	if not is_instance_valid(root): return null
	var model := (root as Node3D).get_node_or_null("Model") as MeshInstance3D
	if model == null or not model.visible: return null
	var top := model.get_aabb().end.y*model.scale.y
	goal_top = clampf(top+0.6, 1.35, 6.0)
	sparkle_at = goal_at+Vector3(0, clampf(top*0.5, 0.4, 1.6), 0)
	return model

func _mark_hearth(dim: bool) -> void:
	goal_at = Vector3.ZERO
	goal_top = 1.9
	goal_dim = dim

## The picked model's outline (material_overlay), moved off the last one.
func _outline(model: MeshInstance3D) -> void:
	if model == goal_model: return
	if is_instance_valid(goal_model) and goal_model.material_overlay == outline_material: goal_model.material_overlay = null
	goal_model = model
	if model == null: return
	var source := model.material_override as ShaderMaterial
	var wind = source.get_shader_parameter("wind") if source != null else null
	var wind_height = source.get_shader_parameter("wind_height") if source != null else null
	outline_material.set_shader_parameter("wind", float(wind) if wind != null else 0.0)
	outline_material.set_shader_parameter("wind_height", float(wind_height) if wind_height != null else 4.0)
	model.material_overlay = outline_material

## A goal met (or the tutorial cleared): a sparkle burst, a ring and a chime at the walker.
func _celebrate(app: Node, big: bool) -> void:
	var player = app.get(&"player")
	if not is_instance_valid(player): return
	var at: Vector3 = (player as Node3D).global_position
	Fx.burst(map, at+Vector3(0, 1.1, 0), "sparkle", 22 if big else 14, Color(0, 0, 0, 0), 0.4)
	Fx.ring(map, at, 2.6 if big else 1.8, Color(1.0, 0.86, 0.5, 0.75), 1.0)
	Fx.sound(app, "twinkle", at, 1.15 if big else 1.0)

# ------------------------------------------------------------------ frame
func _ease(delta: float, player: Node3D) -> void:
	var k := 1.0-exp(-delta*4.0)
	fade = move_toward(fade, 0.0 if clearing else 1.0, delta/1.2)
	beacon_s = lerpf(beacon_s, (0.0 if goal_at == Vector3.INF else (0.55 if goal_dim else 1.0))*fade, k)
	zone_s = lerpf(zone_s, (1.0 if show_zone else 0.0)*fade, k)
	cue_s = lerpf(cue_s, (1.0 if cue_kind != "" else 0.0)*fade, k)
	threat_s = lerpf(threat_s, (1.0 if is_instance_valid(threat_node) else 0.0)*fade, k)
	var bob := 0.0 if calm else sin(clock*2.2)*0.12
	var spin := 0.0 if calm else delta*1.3
	if goal_at != Vector3.INF:
		# The gem glides from one goal to the next; one shown afresh (or far away) starts there.
		var follow := 1.0-exp(-delta*7.0)
		if beacon_s < 0.05 or beacon.global_position.distance_to(goal_at) > 30.0:
			beacon.global_position = goal_at
			gem_height = goal_top
		else:
			beacon.global_position = beacon.global_position.lerp(goal_at, follow)
			gem_height = lerpf(gem_height, goal_top, follow)
	gem.position.y = gem_height+bob
	gem.rotation.y += spin
	if cue_kind != "":
		var texture := _icon(ICON_BAG if cue_kind == "bag" else ICON_FIRE)
		if icon.texture != texture: icon.texture = texture
	cue.global_position = player.global_position
	icon.position.y = 2.7+bob*0.8
	if is_instance_valid(threat_node):
		threat.global_position = threat_node.global_position
	threat_gem.position.y = 2.0+bob
	threat_gem.rotation.y += spin
	var spot := sparkle_at
	if cue_kind != "": spot = player.global_position+Vector3(0, 1.2, 0)
	if spot != Vector3.INF and fade > 0.3 and _staged(2):
		sparkles.global_position = spot
		if not sparkles.emitting: sparkles.emitting = true
	elif sparkles.emitting and warm <= 0.0:
		sparkles.emitting = false
	_apply_strengths(false)
	if clearing and fade <= 0.0 and beacon_s < 0.01 and cue_s < 0.01 and zone_s < 0.01 and threat_s < 0.01:
		_outline(null)
		visible = false
		set_process(false)

## Strengths into the materials (only when they changed); a hidden piece stops drawing, except
## while warming up.
func _apply_strengths(force: bool) -> void:
	# Brighter at night, a little softer by day (the village guide's tune_light).
	var beacon_value := beacon_s*lerpf(0.75, 1.0, night)
	if _changed(0, beacon_value, force):
		pillar_material.set_shader_parameter("strength", beacon_value)
		ring_material.set_shader_parameter("strength", beacon_value)
		outline_material.set_shader_parameter("strength", lerpf(0.65, 1.0, night)*beacon_s)
		gem.scale = Vector3.ONE*maxf(beacon_s, 0.001)*GEM_SIZE
	if _changed(1, zone_s, force):
		zone_material.set_shader_parameter("strength", zone_s*0.8)
	var night_changed := _changed(4, night, force)
	if _changed(2, cue_s, force) or night_changed:
		foot_material.set_shader_parameter("strength", cue_s)
		icon.modulate = Color(1, 1, 1, cue_s)
		# The soft glow behind the icon shows at dusk and night (by day it only greys the ground).
		cue_glow_material.albedo_color = Color(1.0, 0.78, 0.42, cue_s*lerpf(0.08, 0.55, night))
	if _changed(3, threat_s, force):
		threat_material.set_shader_parameter("strength", threat_s)
		threat_gem.scale = Vector3.ONE*maxf(threat_s, 0.001)*GEM_SIZE
	if night_changed:
		# Dark outlines by day (gold on pale ground), pure glow at night.
		var rim := lerpf(0.5, 0.1, night)
		ring_material.set_shader_parameter("rim_amount", rim)
		zone_material.set_shader_parameter("rim_amount", rim)
		foot_material.set_shader_parameter("rim_amount", rim)
		threat_material.set_shader_parameter("rim_amount", rim)
	_show_pieces()

## A piece is drawn while it shows, and once while warming up (its group's frame reached).
func _show_pieces() -> void:
	var warming := warm > 0.0
	beacon.visible = _staged(0) and (warming or beacon_s > 0.01)
	zone.visible = _staged(1) and (warming or zone_s > 0.01)
	threat.visible = _staged(1) and (warming or threat_s > 0.01)
	cue.visible = _staged(2) and (warming or cue_s > 0.01)

func _staged(group: int) -> bool:
	return frames >= int(WARM_FRAMES[group])

func _changed(index: int, value: float, force: bool) -> bool:
	if not force and absf(applied[index]-value) < 0.004: return false
	applied[index] = value
	return true

func _exit_tree() -> void:
	_outline(null)
