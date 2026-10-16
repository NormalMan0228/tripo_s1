extends RefCounted
## Expedition hit, harvest and craft effects, built on the Fx library: what a blow, a chop or a
## finished recipe looks like, so the field answers with effects as the village does. Static
## helpers; `app` is main.gd (world, player, ui). Nothing here creates a light.
##   CombatFx.slash(app, heavy := false, facing := Vector3.ZERO)   the swing trail in front of the hero
##       (facing ZERO: the hero's own facing)
##   CombatFx.strike(app, at, kill := false, parried := false)   a blow lands on an enemy at `at`
##   CombatFx.hurt(app)                            the hero takes a hit (sparks + a red edge flash)
##   CombatFx.harvest(app, kind, at)               tree / stone / fiber / berry gathered at `at`
##   CombatFx.harvest_on_contact(app, kind, at)    the same, when the axe/pick actually reaches it
##   CombatFx.crafted(app)                         an expedition recipe is made
##   CombatFx.fuel(app)                            fuel on the campfire (sparks, flare, a puff of smoke)
##   CombatFx.heal(app) / CombatFx.eat(app)        a bandage / a meal
##   CombatFx.ended(app, won)                      the run ends: a golden column, or a grey faint
const Fx := preload("res://scripts/fx.gd")
const GameSettings := preload("res://scripts/game_settings.gd")

## Swing trail: arc radii (m), half-angle swept (rad), how long the head travels and the fade.
const SLASH_IN := 1.15
const SLASH_OUT := 1.55
const SLASH_HALF := 1.05
const SLASH_TIME := 0.13
const SLASH_FADE := 0.16
const SLASH_TAIL := 0.55

static var vignette: GradientTexture2D

static func _world(app) -> Node3D:
	if app == null or not is_instance_valid(app): return null
	var world = app.get("world")
	if world is Node3D and is_instance_valid(world) and world.is_inside_tree(): return world
	return null

static func _ground(app, at: Vector3) -> Vector3:
	var player = app.get("player")
	if player is Node3D and is_instance_valid(player): return Vector3(at.x, player.global_position.y, at.z)
	return at

## The swing: a bright head sweeps across the front with a fading tail, then the whole arc fades.
static func slash(app, heavy := false, facing := Vector3.ZERO) -> void:
	var world := _world(app)
	if world == null or not is_instance_valid(app.player): return
	Fx.played += 1
	var arc := MeshInstance3D.new()
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.vertex_color_use_as_albedo = true
	# Added light, so the trail reads bright on pale sand and dark forest floor alike.
	mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	mat.albedo_color = Color(1, 1, 1, 1)
	arc.material_override = mat
	arc.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	world.add_child(arc)
	if facing.length() < 0.01: facing = app.player.get("facing") if app.player.get("facing") is Vector3 else Vector3.FORWARD
	arc.global_position = app.player.global_position+Vector3(0, 0.85 if not heavy else 0.75, 0)
	arc.rotation.y = atan2(-facing.x, -facing.z)
	# A slight tilt so the trail reads as a cut, not a flat disc.
	arc.rotation.z = 0.12
	var outer := SLASH_OUT+(0.2 if heavy else 0.0)
	var tint := Color("fff4cf") if not heavy else Color("ffd98a")
	var draw := func(head: float) -> void:
		if not is_instance_valid(arc): return
		var im := ImmediateMesh.new()
		im.surface_begin(Mesh.PRIMITIVE_TRIANGLE_STRIP)
		var steps := 14
		for i in steps+1:
			var u := float(i)/steps
			# u runs tail (0) -> head (1); the arc spans [head-SLASH_TAIL, head] in sweep space.
			var s := clampf(head-SLASH_TAIL*(1.0-u), 0.0, 1.0)
			var angle := -SLASH_HALF+2.0*SLASH_HALF*s
			var a := pow(u, 1.6)
			var width := lerpf(0.35, 1.0, u)
			var inner := lerpf(outer, SLASH_IN, width)
			im.surface_set_color(Color(tint, a*0.0))
			im.surface_add_vertex(Vector3(sin(angle)*inner, 0, -cos(angle)*inner))
			im.surface_set_color(Color(tint, a*0.95))
			im.surface_add_vertex(Vector3(sin(angle)*outer, 0, -cos(angle)*outer))
		im.surface_end()
		arc.mesh = im
	# Driven per frame with each step capped at 1/30 s (not a tween): a hitch on the frame of the
	# blow (a server answer, a first-time texture) would otherwise jump the whole swing in one step.
	var tree := arc.get_tree()
	var state := {"t": 0.0, "last": Time.get_ticks_usec()}
	var end := 1.0+SLASH_TAIL*0.35
	var tick := func() -> void:
		if not is_instance_valid(arc):
			if tree.process_frame.is_connected(state.cb): tree.process_frame.disconnect(state.cb)
			return
		var now := Time.get_ticks_usec()
		state.t += minf((now-int(state.last))/1000000.0, 1.0/30.0)
		state.last = now
		var t: float = state.t
		if t < SLASH_TIME:
			var u := t/SLASH_TIME
			draw.call(end*(1.0-(1.0-u)*(1.0-u)))
		elif t < SLASH_TIME+SLASH_FADE:
			# The full arc once; the fade only changes the material (the mesh was rebuilt every frame).
			if not state.has("full"):
				state.full = true
				draw.call(end)
			mat.albedo_color.a = 1.0-(t-SLASH_TIME)/SLASH_FADE
		else:
			tree.process_frame.disconnect(state.cb)
			arc.queue_free()
	state.cb = tick
	draw.call(0.05)
	tree.process_frame.connect(tick)

## A blow lands: sparks and a quick white flash at the enemy's chest, a ground ring; a kill adds a
## puff of smoke, glitter and a wider ring; a parried windup adds a bright clash ring.
static func strike(app, at: Vector3, kill := false, parried := false) -> void:
	var world := _world(app)
	if world == null: return
	var ground := _ground(app, at)
	var chest := ground+Vector3(0, 0.85, 0)
	Fx.burst(world, chest, "spark", 16 if kill else 10, Color(0,0,0,0), 0.18)
	Fx.glow(world, chest, Color("fff2cc"), 1.1 if not kill else 1.6, 0.28)
	Fx.ring(world, ground, 1.0 if not kill else 2.1, Color(1.0, 0.93, 0.75, 0.6), 0.35 if not kill else 0.6)
	if parried:
		Fx.ring(world, chest-Vector3(0, 0.3, 0), 1.3, Color(1, 1, 1, 0.85), 0.25)
		Fx.burst(world, chest, "sparkle", 8, Color(0,0,0,0), 0.25)
	if kill:
		Fx.burst(world, ground+Vector3(0, 0.5, 0), "smoke", 9, Color("8f8a94"), 0.45)
		Fx.burst(world, chest, "sparkle", 12, Color(0,0,0,0), 0.5)
		Fx.burst(world, ground+Vector3(0, 0.1, 0), "scuff", 8, Color("b9ad98"), 0.5)

## The hero is hit: red sparks at the chest and, when flashes are allowed, a red edge vignette.
static func hurt(app) -> void:
	var world := _world(app)
	if world == null or not is_instance_valid(app.player): return
	Fx.burst(world, app.player.global_position+Vector3(0, 1.0, 0), "spark", 9, Color("ff6b5c"), 0.22)
	if not GameSettings.flashes_allowed(): return
	var ui = app.get("ui")
	if not (ui is Control) or not is_instance_valid(ui): return
	var edge := TextureRect.new()
	edge.texture = _vignette()
	edge.stretch_mode = TextureRect.STRETCH_SCALE
	edge.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	edge.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	edge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	edge.modulate = Color(1, 1, 1, 0.0)
	ui.add_child(edge)
	var t := edge.create_tween()
	t.tween_property(edge, "modulate:a", 0.6, 0.05)
	t.tween_property(edge, "modulate:a", 0.0, 0.38).set_ease(Tween.EASE_IN)
	t.tween_callback(edge.queue_free)

static func _vignette() -> GradientTexture2D:
	if vignette != null: return vignette
	var g := Gradient.new()
	g.set_color(0, Color(0.85, 0.08, 0.05, 0.0))
	g.set_color(1, Color(0.75, 0.04, 0.03, 0.55))
	g.add_point(0.7, Color(0.85, 0.08, 0.05, 0.0))
	vignette = GradientTexture2D.new()
	vignette.gradient = g
	vignette.fill = GradientTexture2D.FILL_RADIAL
	vignette.fill_from = Vector2(0.5, 0.5)
	vignette.fill_to = Vector2(1.0, 1.0)
	vignette.width = 256
	vignette.height = 256
	return vignette

## Gathering: wood chips and falling leaves off a tree, grey chips, grit and a spark off stone,
## grass bits and fluff off fibre, red pips and glitter off a berry bush.
static func harvest(app, kind: String, at: Vector3) -> void:
	var world := _world(app)
	if world == null: return
	var ground := _ground(app, at)
	match kind:
		"tree":
			Fx.burst(world, ground+Vector3(0, 0.9, 0), "seed", 9, Color("c49a62"), 0.25)
			Fx.burst(world, ground+Vector3(0, 2.6, 0), "leaf", 6, Color(0,0,0,0), 0.9)
		"stone":
			Fx.burst(world, ground+Vector3(0, 0.5, 0), "seed", 9, Color("a29e96"), 0.22)
			Fx.burst(world, ground+Vector3(0, 0.35, 0), "scuff", 5, Color("bdb7ad"), 0.3)
			Fx.burst(world, ground+Vector3(0, 0.6, 0), "spark", 4, Color(0,0,0,0), 0.1)
		"fiber":
			Fx.burst(world, ground+Vector3(0, 0.45, 0), "blade", 9, Color(0,0,0,0), 0.3)
			Fx.burst(world, ground+Vector3(0, 0.6, 0), "fluff", 4, Color(0,0,0,0), 0.3)
		"berry":
			Fx.burst(world, ground+Vector3(0, 0.6, 0), "seed", 6, Color("d6455c"), 0.3)
			Fx.burst(world, ground+Vector3(0, 0.7, 0), "leaf", 4, Color(0,0,0,0), 0.35)
			Fx.burst(world, ground+Vector3(0, 0.8, 0), "sparkle", 4, Color(0,0,0,0), 0.3)
		_:
			Fx.burst(world, ground+Vector3(0, 0.5, 0), "dust", 6, Color(0,0,0,0), 0.3)

## A recipe made in the field: a warm glow, glitter rising round the hero and a ground ring.
static func crafted(app) -> void:
	var world := _world(app)
	if world == null or not is_instance_valid(app.player): return
	var feet: Vector3 = app.player.global_position
	Fx.glow(world, feet+Vector3(0, 1.0, 0), Color("ffd27a"), 2.0, 0.9)
	Fx.burst(world, feet+Vector3(0, 0.9, 0), "sparkle", 16, Color(0,0,0,0), 0.55)
	Fx.ring(world, feet, 1.8, Color(1.0, 0.9, 0.6, 0.7), 0.8)

## Fuel on the campfire: a flare and a rising stream of sparks over the flame, a puff of smoke.
static func fuel(app) -> void:
	var world := _world(app)
	if world == null: return
	var at := Vector3.ZERO
	var flame = app.get("flame")
	if flame is Node3D and is_instance_valid(flame) and flame.is_inside_tree(): at = flame.global_position
	Fx.glow(world, at+Vector3(0, 0.8, 0), Color("ff9a3c"), 2.6, 1.1)
	Fx.burst(world, at+Vector3(0, 0.5, 0), "spark", 16, Color(0,0,0,0), 0.3)
	Fx.stream(world, at+Vector3(0, 0.6, 0), "spark", 1.4, 14.0, Color(0,0,0,0), 0.25)
	Fx.burst(world, at+Vector3(0, 1.1, 0), "smoke", 5, Color("8d8781"), 0.3)

## A bandage: green glints rise round the hero inside a soft green glow and ring.
static func heal(app) -> void:
	var world := _world(app)
	if world == null or not is_instance_valid(app.player): return
	var feet: Vector3 = app.player.global_position
	Fx.glow(world, feet+Vector3(0, 1.0, 0), Color("8fe39a"), 1.9, 0.9)
	Fx.burst(world, feet+Vector3(0, 0.9, 0), "sparkle", 14, Color("b4f5a6"), 0.45)
	Fx.ring(world, feet, 1.3, Color(0.6, 1.0, 0.65, 0.6), 0.7)

## A meal: a few crumbs at the mouth and a small heart.
static func eat(app) -> void:
	var world := _world(app)
	if world == null or not is_instance_valid(app.player): return
	var head: Vector3 = app.player.global_position+Vector3(0, 1.45, 0)
	Fx.burst(world, head, "seed", 6, Color("e2bf7c"), 0.12)
	Fx.burst(world, head+Vector3(0, 0.3, 0), "heart", 2, Color(0,0,0,0), 0.15)

## The run ends: a won run raises a golden column of glitter with two widening rings; a lost one
## sinks into a grey puff with a few sleepy z's.
static func ended(app, won: bool) -> void:
	var world := _world(app)
	if world == null or not is_instance_valid(app.player): return
	var feet: Vector3 = app.player.global_position
	if won:
		Fx.glow(world, feet+Vector3(0, 1.2, 0), Color("ffd66b"), 3.2, 1.6)
		Fx.burst(world, feet+Vector3(0, 1.0, 0), "sparkle", 28, Color(0,0,0,0), 0.7)
		Fx.stream(world, feet+Vector3(0, 0.4, 0), "sparkle", 2.2, 12.0, Color(0,0,0,0), 0.5)
		Fx.ring(world, feet, 2.6, Color(1.0, 0.86, 0.45, 0.8), 1.0)
		Fx.ring(world, feet, 4.0, Color(1.0, 0.9, 0.6, 0.5), 1.5)
	else:
		Fx.burst(world, feet+Vector3(0, 0.6, 0), "smoke", 8, Color("7d7a80"), 0.5)
		Fx.burst(world, feet+Vector3(0, 1.4, 0), "zz", 3, Color(0,0,0,0), 0.2)

## Gathering chips on the frame the tool in hand reaches the node (tool_contact.gd): a trunk is met
## about chest-high, stone, fibre and berries lower down. Bare hands: at once.
static func harvest_on_contact(app, kind: String, at: Vector3) -> void:
	if app == null or not is_instance_valid(app) or not is_instance_valid(app.get("player")): return
	var ground := _ground(app, at)
	var aim := ground+Vector3(0, 0.9 if kind == "tree" else 0.35, 0)
	preload("res://scripts/tool_contact.gd").strike(app.player, aim, func(hit: Vector3):
		if is_instance_valid(app): harvest(app, kind, Vector3(hit.x, ground.y, hit.z)), 0.6)

## The first use of each effect material compiles its shader on that frame (measured on 0.11.9: a
## 53 ms hitch when the campfire is first lit, 184 ms when the buff first shows). Drawn once, almost
## invisible, while the expedition loads under its veil, they are ready before play.
static func warm_up(app, at: Vector3) -> void:
	var world := _world(app)
	if world == null: return
	var faint := Color(1, 1, 1, 0.01)
	for kind in ["spark", "smoke", "sparkle", "seed", "scuff", "leaf", "blade", "drop", "snow", "litter", "zz", "heart"]:
		Fx.burst(world, at, kind, 1, faint, 0.01)
	Fx.glow(world, at, Color(0.01, 0.01, 0.01), 0.05, 0.8)
	Fx.ring(world, at, 0.05, faint, 0.8)
	preload("res://scripts/campfire_buff_fx.gd").warm_up(world, at)
	_warm_monster_overlay(app)

## The monsters' rim/hit-flash overlay (monster.gd OVERLAY_CODE) compiled when the first beast
## appeared. Skinned meshes need their own variant, so it is drawn for a few frames, at zero
## strength (adds nothing), over the hero's own skinned meshes, then taken off again.
static func _warm_monster_overlay(app) -> void:
	var hero = app.get("player")
	if not (hero is Node3D) or not is_instance_valid(hero): return
	var Monster = preload("res://scripts/monster.gd")
	if Monster.overlay_shader == null:
		Monster.overlay_shader = Shader.new()
		Monster.overlay_shader.code = Monster.OVERLAY_CODE
	var mat := ShaderMaterial.new()
	mat.shader = Monster.overlay_shader
	for key in ["rim", "glow", "flash"]: mat.set_shader_parameter(key, 0.0)
	var dressed: Array = []
	for mesh in hero.find_children("*", "MeshInstance3D", true, false):
		if mesh.material_overlay == null:
			mesh.material_overlay = mat
			dressed.append(mesh)
	if dressed.is_empty(): return
	hero.get_tree().create_timer(0.5).timeout.connect(func():
		for mesh in dressed:
			if is_instance_valid(mesh) and mesh.material_overlay == mat: mesh.material_overlay = null)
