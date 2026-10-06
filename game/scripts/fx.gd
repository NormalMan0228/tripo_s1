extends RefCounted
## Cheap one-shot visual effects for the village: feedback that shows instead of a
## sentence. Static helpers only (no autoload, no setup):
##   const Fx = preload("res://scripts/fx.gd")
## Pass any Node3D that lives in the world the effect belongs to (the town, app.world,
## a prop). Particle emitters are pooled per kind and reused once they finish; all
## other pieces are short tweens that free themselves. No lights are ever created:
## glows are additive billboards. Textures are drawn once, lazily, and shared.
##
## --- particles --------------------------------------------------------------------
##   Fx.burst(parent, at: Vector3, kind: String, amount := 12, tint := Color(0,0,0,0), radius := 0.25)
##       One-shot puff. kind: "leaf", "petal", "sparkle", "drop", "splash", "note",
##       "heart", "smoke", "steam", "dust", "spark", "seed", "fluff", "zz".
##       tint (alpha > 0) replaces the kind's own colour mix.
##   Fx.stream(parent, at: Vector3, kind: String, seconds := 2.0, rate := 5.0, tint := Color(0,0,0,0), radius := 0.2)
##       Same kinds, emitted steadily for a few seconds (speaker notes, campfire sparks).
##   Fx.gust(parent, at: Vector3, toward: Vector3, kind := "leaf", amount := 10, radius := 0.4)
##       A puff blown sideways along `toward` (wind past a weather vane).
## --- pops and shapes ------------------------------------------------------------
##   Fx.bubble(parent, at: Vector3, symbol: String, color := Color(0,0,0,0)) -> Sprite3D
##       A small speech-bubble icon that pops up, floats ~0.6 m and fades (1.4 s).
##       symbol: "heart", "note", "star", "drop", "zz", "leaf", "flame", "sun", "dots".
##   Fx.ring(parent, at: Vector3, radius := 1.2, color := Color(1,1,1,0.7), seconds := 0.9)
##       Flat ring that widens and fades on the ground or on water.
##   Fx.glow(parent, at: Vector3, color := Color("ffb45a"), size := 1.6, seconds := 1.6)
##       Additive billboard that swells and fades (a warm glow without a light).
##   Fx.dragonfly(parent, at: Vector3, heading := Vector3.RIGHT)
##       A dragonfly darts out of reeds along a wavy path and flies off (2.6 s).
## --- node motion ------------------------------------------------------------------
##   Fx.wobble(node: Node3D, amount := 0.06, axis := Vector3.RIGHT, cycles := 4, seconds := 0.7)
##       Damped sway about the node's origin (its base) around a parent-space axis.
##       Re-triggering restarts from the rest pose, so it never drifts.
##   Fx.squash(node: Node3D, amount := 0.15, seconds := 0.3)
##       Squash-and-stretch pop on the node's scale, back to its rest scale.
## --- screen-space (need app.ui and app.camera) ----------------------------------
##   Fx.item_pop(app, at: Vector3, item: String, count := 1, delay := 0.0)
##       "+N" with the item's life_icon.gd icon, pinned to a 3D point, floats up and fades.
##   Fx.fly_to_bag(app, items: Dictionary, from: Vector3, delay := 0.0)
##       Item icons fly into the storage slot (village_life.fly_items when available).
##   Fx.polaroid(app, image: Image)
##       The photo pops up as a little polaroid and slides into the corner.
##   Fx.title(app, at: Vector3, text: String, color := Color("f5e5b7"))
##       Short floating caption. Only for information (names, places), never chatter.
## --- sound ------------------------------------------------------------------------
##   Fx.sound(app, kind: String, at := Vector3.INF, pitch := 1.0, db := 0.0)
##       Synthesized one-shots on the Master bus (so M-mute silences them): "thud",
##       "leaves", "twinkle", "crackle", "splash", "pluck", "pop", "chirp", "whoosh",
##       "tune", "drink". Quieter with distance from app.player when `at` is given.
## --- tests ------------------------------------------------------------------------
##   Fx.played: int   counts every effect started (harnesses check it went up).
const Icon := preload("res://scripts/life_icon.gd")
const Art := preload("res://scripts/life_art.gd")
const POOL_MAX := 6
const TEX := 48

static var played := 0
static var pools := {}
static var textures := {}
static var materials := {}
static var quad: QuadMesh
static var streams := {}
static var voices: Array = []
static var voice_next := 0

## size [min,max] m, life s, speed [min,max], gravity (y), spread deg, symbol texture,
## shading ("lit" darkens at night, "add" glows), colours picked per particle.
const KINDS := {
	"leaf":{"tex":"leaf","shade":"lit","size":[0.18,0.3],"life":1.5,"speed":[1.4,3.0],"gravity":-2.6,"spread":75,"damp":1.6,"spin":true,
		"colors":["7fb85a","4f8f3e","a9c95a","5e9e48"]},
	"petal":{"tex":"petal","shade":"lit","size":[0.12,0.2],"life":1.6,"speed":[0.8,1.8],"gravity":-1.2,"spread":80,"damp":1.4,"spin":true,
		"colors":["f6a8c8","fbd3e3","ffffff","f4c4dc"]},
	"sparkle":{"tex":"star","shade":"add","size":[0.16,0.32],"life":1.0,"speed":[0.3,1.1],"gravity":0.5,"spread":180,"damp":1.0,
		"colors":["fff3b0","ffe27a","ffffff"]},
	"drop":{"tex":"drop","shade":"flat","size":[0.09,0.15],"life":0.7,"speed":[1.6,3.0],"gravity":-10.0,"spread":35,"damp":0.0,
		"colors":["9fd8f5","d8f2ff","7cc4ec"]},
	"splash":{"tex":"drop","shade":"flat","size":[0.1,0.17],"life":0.8,"speed":[1.8,3.4],"gravity":-9.0,"spread":28,"damp":0.0,
		"colors":["e6f6ff","b7e2f7","ffffff"]},
	"note":{"tex":"note","shade":"flat","size":[0.22,0.32],"life":1.8,"speed":[0.5,1.0],"gravity":0.35,"spread":35,"damp":0.6,"sway":true,
		"colors":["f7d26a","f29bb8","8fc4f2","a8dc7a","c7a6f2"]},
	"heart":{"tex":"heart","shade":"flat","size":[0.16,0.26],"life":1.5,"speed":[0.5,0.9],"gravity":0.4,"spread":30,"damp":0.5,"sway":true,
		"colors":["f57a9e","ff9fbd","f25c84"]},
	"smoke":{"tex":"soft","shade":"lit","size":[0.45,0.8],"life":2.0,"speed":[0.3,0.6],"gravity":0.7,"spread":20,"damp":0.6,"grow":true,
		"colors":["b9b3ad","9e9893","cfcac4"],"alpha":0.5},
	"steam":{"tex":"soft","shade":"flat","size":[0.25,0.45],"life":1.6,"speed":[0.25,0.5],"gravity":0.5,"spread":15,"damp":0.4,"grow":true,
		"colors":["ffffff","eef4f8"],"alpha":0.45},
	"dust":{"tex":"soft","shade":"lit","size":[0.22,0.42],"life":0.9,"speed":[0.6,1.6],"gravity":-0.6,"spread":70,"damp":2.2,"grow":true,
		"colors":["d8c8a8","c6b48f","e3d6bd"],"alpha":0.7},
	"spark":{"tex":"spark","shade":"add","size":[0.06,0.12],"life":1.1,"speed":[1.0,2.4],"gravity":1.2,"spread":25,"damp":0.8,
		"colors":["ffb347","ffd27a","ff8a3d"]},
	"seed":{"tex":"soft","shade":"lit","size":[0.08,0.13],"life":0.8,"speed":[1.2,2.4],"gravity":-8.0,"spread":60,"damp":0.0,
		"colors":["e5cf8e","c9a96a","f0dca8"]},
	"fluff":{"tex":"spark","shade":"flat","size":[0.07,0.12],"life":2.4,"speed":[0.4,1.0],"gravity":0.15,"spread":80,"damp":0.9,"sway":true,
		"colors":["fffbea","f6f0d8","ffffff"]},
	"zz":{"tex":"z","shade":"flat","size":[0.16,0.26],"life":2.0,"speed":[0.35,0.55],"gravity":0.15,"spread":20,"damp":0.3,"sway":true,
		"colors":["d9e6ff","ffffff","c3d4f5"]},
}

# ------------------------------------------------------------------ particles
static func burst(parent: Node3D, at: Vector3, kind: String, amount := 12, tint := Color(0,0,0,0), radius := 0.25) -> void:
	if not _ok(parent) or not KINDS.has(kind): return
	played += 1
	var e := _emitter(parent, kind)
	_configure(e, kind, tint, radius)
	e.one_shot = true
	e.explosiveness = 0.88
	e.amount = maxi(1, amount)
	e.global_position = at
	e.restart()

## A puff blown sideways (wind): same kinds as burst, flying along `toward`.
static func gust(parent: Node3D, at: Vector3, toward: Vector3, kind := "leaf", amount := 10, radius := 0.4) -> void:
	if not _ok(parent) or not KINDS.has(kind): return
	played += 1
	var e := _emitter(parent, kind)
	_configure(e, kind, Color(0,0,0,0), radius)
	e.one_shot = true
	e.explosiveness = 0.55
	e.amount = maxi(1, amount)
	e.direction = (toward.normalized()+Vector3(0,0.25,0)).normalized() if toward.length() > 0.01 else Vector3.UP
	e.spread = 16.0
	e.initial_velocity_min = 2.6
	e.initial_velocity_max = 4.2
	e.gravity = Vector3(0, -0.8, 0)
	e.damping_min = 0.4
	e.damping_max = 0.8
	e.global_position = at
	e.restart()

static func stream(parent: Node3D, at: Vector3, kind: String, seconds := 2.0, rate := 5.0, tint := Color(0,0,0,0), radius := 0.2) -> void:
	if not _ok(parent) or not KINDS.has(kind): return
	played += 1
	var e := _emitter(parent, kind)
	_configure(e, kind, tint, radius)
	e.one_shot = false
	e.explosiveness = 0.0
	e.amount = maxi(2, int(ceil(rate*e.lifetime)))
	e.global_position = at
	e.restart()
	var stop := e.create_tween()
	stop.tween_interval(seconds)
	stop.tween_callback(func(): e.emitting = false)

static func _ok(parent: Node) -> bool:
	return is_instance_valid(parent) and parent.is_inside_tree()

static func _emitter(parent: Node3D, kind: String) -> CPUParticles3D:
	var list: Array = pools.get(kind, [])
	var world := parent.get_world_3d()
	var pick: CPUParticles3D = null
	for e in list.duplicate():
		if not is_instance_valid(e):
			list.erase(e)
			continue
		if not e.emitting and e.is_inside_tree() and e.get_world_3d() == world:
			pick = e
			break
	if pick == null:
		pick = CPUParticles3D.new()
		pick.name = "Fx_"+kind
		pick.emitting = false
		parent.add_child(pick)
		if list.size() < POOL_MAX: list.append(pick)
		else: pick.finished.connect(pick.queue_free)
	pools[kind] = list
	return pick

static func _configure(e: CPUParticles3D, kind: String, tint: Color, radius: float) -> void:
	var k: Dictionary = KINDS[kind]
	e.mesh = _quad()
	e.material_override = _particle_material(String(k.tex), String(k.shade))
	e.lifetime = float(k.life)
	e.local_coords = false
	e.direction = Vector3.UP
	e.spread = float(k.spread)
	e.initial_velocity_min = float(k.speed[0])
	e.initial_velocity_max = float(k.speed[1])
	e.gravity = Vector3(0, float(k.gravity), 0)
	e.damping_min = float(k.damp)*0.7
	e.damping_max = float(k.damp)
	e.scale_amount_min = float(k.size[0])
	e.scale_amount_max = float(k.size[1])
	e.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	e.emission_sphere_radius = radius
	e.angle_min = -180.0 if k.get("spin", false) or kind == "zz" else 0.0
	e.angle_max = 180.0 if k.get("spin", false) else (15.0 if kind == "zz" else 0.0)
	e.angular_velocity_min = -280.0 if k.get("spin", false) else 0.0
	e.angular_velocity_max = 280.0 if k.get("spin", false) else 0.0
	# Gentle side-to-side drift for floaty kinds (notes, hearts, fluff).
	e.orbit_velocity_min = 0.0
	e.orbit_velocity_max = 0.0
	e.tangential_accel_min = -0.6 if k.get("sway", false) else 0.0
	e.tangential_accel_max = 0.6 if k.get("sway", false) else 0.0
	var curve := Curve.new()
	if k.get("grow", false):
		curve.add_point(Vector2(0, 0.45)); curve.add_point(Vector2(1, 1.0))
	else:
		curve.add_point(Vector2(0, 0.2)); curve.add_point(Vector2(0.12, 1.0)); curve.add_point(Vector2(0.75, 0.9)); curve.add_point(Vector2(1, 0.35))
	e.scale_amount_curve = curve
	var fade := Gradient.new()
	var alpha: float = float(k.get("alpha", 1.0))
	fade.set_color(0, Color(1,1,1,alpha))
	fade.set_color(1, Color(1,1,1,0))
	fade.add_point(0.65, Color(1,1,1,alpha))
	e.color_ramp = fade
	if tint.a > 0.0:
		e.color = tint
		e.color_initial_ramp = null
	else:
		e.color = Color.WHITE
		var mix := Gradient.new()
		var colors: Array = k.colors
		mix.set_color(0, Color(colors[0]))
		mix.set_color(1, Color(colors[colors.size()-1]))
		for i in range(1, colors.size()-1): mix.add_point(float(i)/(colors.size()-1), Color(colors[i]))
		mix.interpolation_mode = Gradient.GRADIENT_INTERPOLATE_CONSTANT
		e.color_initial_ramp = mix

static func _quad() -> QuadMesh:
	if quad == null:
		quad = QuadMesh.new()
		quad.size = Vector2.ONE
	return quad

static func _particle_material(symbol: String, shade: String) -> StandardMaterial3D:
	var key := symbol+"/"+shade
	if materials.has(key): return materials[key]
	var m := StandardMaterial3D.new()
	m.albedo_texture = tex(symbol)
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	# Particle billboards drop their scale unless told to keep it.
	m.billboard_keep_scale = true
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	if shade != "lit": m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	else: m.roughness = 1.0
	if shade == "add": m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	materials[key] = m
	return m

# ------------------------------------------------------------------ textures
## White symbols with alpha, drawn once at 48 px with 2x2 supersampling.
static func tex(symbol: String) -> Texture2D:
	if textures.has(symbol): return textures[symbol]
	var img := Image.create(TEX, TEX, false, Image.FORMAT_RGBA8)
	for y in TEX:
		for x in TEX:
			var a := 0.0
			if symbol in ["soft","spark","star"]:
				a = _soft(symbol, _uv(x+0.5, y+0.5))
			else:
				for s in 4: a += 0.25 if _inside(symbol, _uv(x+0.25+0.5*(s%2), y+0.25+0.5*(s/2))) else 0.0
			img.set_pixel(x, y, Color(1,1,1,a))
	img.generate_mipmaps()
	var t := ImageTexture.create_from_image(img)
	textures[symbol] = t
	return t

static func _uv(x: float, y: float) -> Vector2:
	return Vector2(x/TEX*2.0-1.0, 1.0-y/TEX*2.0)

static func _soft(symbol: String, p: Vector2) -> float:
	var r := p.length()
	match symbol:
		"soft": return pow(clampf(1.0-r, 0.0, 1.0), 1.6)
		"spark": return clampf(exp(-r*r*14.0)+0.35*exp(-r*r*3.5), 0.0, 1.0)
		_: return clampf(1.0-14.2*absf(p.x)*absf(p.y)-0.8*r, 0.0, 1.0)

static func _seg(p: Vector2, a: Vector2, b: Vector2) -> float:
	return Geometry2D.get_closest_point_to_segment(p, a, b).distance_to(p)

static func _inside(symbol: String, p: Vector2) -> bool:
	match symbol:
		"heart":
			var q := Vector2(p.x*1.22, p.y*1.22+0.22)
			var f := pow(q.x*q.x+q.y*q.y-1.0, 3.0)-q.x*q.x*q.y*q.y*q.y
			return f <= 0.0
		"note":
			var h := (p-Vector2(-0.26,-0.5)).rotated(0.4)
			if (h.x*h.x)/(0.3*0.3)+(h.y*h.y)/(0.21*0.21) <= 1.0: return true
			if p.x >= -0.02 and p.x <= 0.1 and p.y >= -0.5 and p.y <= 0.82: return true
			return _seg(p, Vector2(0.06,0.78), Vector2(0.42,0.46)) < 0.09 or _seg(p, Vector2(0.42,0.46), Vector2(0.36,0.12)) < 0.07
		"drop":
			if p.distance_to(Vector2(0,-0.28)) <= 0.52: return true
			return Geometry2D.is_point_in_polygon(p, PackedVector2Array([Vector2(0,0.9),Vector2(-0.45,-0.05),Vector2(0.45,-0.05)]))
		"z":
			var w := 0.13
			return _seg(p, Vector2(-0.48,0.52), Vector2(0.48,0.52)) < w or _seg(p, Vector2(0.48,0.52), Vector2(-0.48,-0.52)) < w or _seg(p, Vector2(-0.48,-0.52), Vector2(0.48,-0.52)) < w
		"leaf", "petal":
			var u := (p.x+p.y)*0.7071
			var v := (p.y-p.x)*0.7071
			var ru := 0.95 if symbol == "leaf" else 0.75
			var rv := 0.4 if symbol == "leaf" else 0.48
			var taper := 1.0-0.35*absf(u)/ru if symbol == "leaf" else 1.0
			return (u*u)/(ru*ru)+(v*v)/(rv*rv*taper*taper) <= 1.0
		"flame":
			if p.distance_to(Vector2(0,-0.35)) <= 0.45: return true
			return Geometry2D.is_point_in_polygon(p, PackedVector2Array([Vector2(0.05,0.9),Vector2(-0.43,-0.25),Vector2(0.43,-0.25)]))
		"sun":
			if p.length() <= 0.42: return true
			var a := fposmod(atan2(p.y, p.x), TAU/8.0)-TAU/16.0
			return p.length() <= 0.82 and p.length() >= 0.55 and absf(a) < 0.16
		"dots":
			for x in [-0.5, 0.0, 0.5]:
				if p.distance_to(Vector2(x, 0)) <= 0.17: return true
			return false
		"star":
			var a2 := atan2(p.y, p.x)+PI/2.0
			var r := 0.42+0.42*pow(absf(cos(a2*2.5)), 3.0)
			return p.length() <= r
	return false

## A bubble: white rounded card with a small tail, outlined, symbol in colour.
static func bubble_texture(symbol: String, color: Color) -> Texture2D:
	var key := "bubble/%s/%s" % [symbol, color.to_html()]
	if textures.has(key): return textures[key]
	var n := 64
	var img := Image.create(n, n, false, Image.FORMAT_RGBA8)
	var ink := Color("5b4632")
	for y in n:
		for x in n:
			var c := Color(0,0,0,0)
			for s in 4:
				var p := Vector2((x+0.25+0.5*(s%2))/n*2.0-1.0, 1.0-(y+0.25+0.5*(s/2))/n*2.0)
				var here := Color(0,0,0,0)
				var body := p.distance_to(Vector2(0,0.1)) <= 0.8 or Geometry2D.is_point_in_polygon(p, PackedVector2Array([Vector2(-0.05,-0.97),Vector2(-0.32,-0.5),Vector2(0.18,-0.55)]))
				var edge := p.distance_to(Vector2(0,0.1)) <= 0.88 or Geometry2D.is_point_in_polygon(p, PackedVector2Array([Vector2(-0.06,-1.0),Vector2(-0.4,-0.46),Vector2(0.26,-0.52)]))
				if body: here = Color("fffaf0")
				elif edge: here = Color(ink, 0.9)
				var q := (p-Vector2(0,0.1))/0.56
				if body and q.length() < 1.15:
					if symbol in ["star","sparkle"]:
						if _inside("star", q): here = color
					elif symbol == "zz":
						if _inside("z", (q-Vector2(-0.3,-0.25))/0.6) or _inside("z", (q-Vector2(0.35,0.3))/0.45): here = color
					elif _inside(symbol, q): here = color
				c += here*0.25
			img.set_pixel(x, y, Color(c.r/maxf(c.a,0.001), c.g/maxf(c.a,0.001), c.b/maxf(c.a,0.001), c.a) if c.a > 0.0 else c)
	img.generate_mipmaps()
	var t := ImageTexture.create_from_image(img)
	textures[key] = t
	return t

# ------------------------------------------------------------------ pops and shapes
const BUBBLE_COLORS := {"heart":"f2557f","note":"e59a2f","star":"f0b429","drop":"4aa8e0","zz":"6c84c9","leaf":"5ea84a",
	"flame":"ef7a32","sun":"f2b22c","dots":"8a7a66","sparkle":"f0b429"}

static func bubble(parent: Node3D, at: Vector3, symbol: String, color := Color(0,0,0,0)) -> Sprite3D:
	if not _ok(parent): return null
	played += 1
	var c: Color = color if color.a > 0.0 else Color(BUBBLE_COLORS.get(symbol, "8a7a66"))
	var s := Sprite3D.new()
	s.texture = bubble_texture(symbol, c)
	s.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	s.pixel_size = 0.0095
	s.no_depth_test = true
	s.render_priority = 10
	s.shaded = false
	s.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(s)
	s.global_position = at
	s.scale = Vector3.ONE*0.05
	var t := s.create_tween()
	t.tween_property(s, "scale", Vector3.ONE*1.12, 0.18).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	t.tween_property(s, "scale", Vector3.ONE, 0.1)
	t.parallel().tween_property(s, "position:y", s.position.y+0.6, 1.25).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	t.parallel().tween_property(s, "modulate:a", 0.0, 0.35).set_delay(0.9)
	t.tween_callback(s.queue_free)
	return s

static func ring(parent: Node3D, at: Vector3, radius := 1.2, color := Color(1,1,1,0.7), seconds := 0.9) -> void:
	if not _ok(parent): return
	played += 1
	var r := MeshInstance3D.new()
	r.mesh = Art.mesh("ring")
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.albedo_color = color
	r.material_override = m
	r.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(r)
	r.global_position = at+Vector3(0,0.04,0)
	r.scale = Vector3.ONE*0.12
	var t := r.create_tween().set_parallel(true)
	t.tween_property(r, "scale", Vector3.ONE*radius, seconds).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	t.tween_property(m, "albedo_color:a", 0.0, seconds).set_ease(Tween.EASE_IN)
	t.chain().tween_callback(r.queue_free)

static func glow(parent: Node3D, at: Vector3, color := Color("ffb45a"), size := 1.6, seconds := 1.6) -> void:
	if not _ok(parent): return
	played += 1
	var g := MeshInstance3D.new()
	g.mesh = _quad()
	var m := StandardMaterial3D.new()
	m.albedo_texture = tex("soft")
	m.albedo_color = Color(color, 0.0)
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.no_depth_test = false
	g.material_override = m
	g.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(g)
	g.global_position = at
	g.scale = Vector3.ONE*size*0.6
	var t := g.create_tween()
	t.tween_property(m, "albedo_color:a", 0.75, seconds*0.25)
	t.parallel().tween_property(g, "scale", Vector3.ONE*size, seconds*0.4).set_trans(Tween.TRANS_SINE)
	t.tween_property(g, "scale", Vector3.ONE*size*1.06, seconds*0.25).set_trans(Tween.TRANS_SINE)
	t.tween_property(m, "albedo_color:a", 0.0, seconds*0.35)
	t.tween_callback(g.queue_free)

static var dragonfly_mesh: ArrayMesh
static func dragonfly(parent: Node3D, at: Vector3, heading := Vector3.RIGHT) -> void:
	if not _ok(parent): return
	played += 1
	var fly := Node3D.new()
	parent.add_child(fly)
	fly.global_position = at
	var body := MeshInstance3D.new()
	body.mesh = Art.mesh("capsule")
	body.scale = Vector3(0.025,0.11,0.025)
	body.rotation.x = PI/2
	body.material_override = Art.mat(Color("3b8fb0"), 0.4, 0.4)
	fly.add_child(body)
	var head := MeshInstance3D.new()
	head.mesh = Art.mesh("ball")
	head.scale = Vector3.ONE*0.05
	head.position = Vector3(0,0,0.11)
	head.material_override = Art.mat(Color("2c6f8c"), 0.4)
	fly.add_child(head)
	var wings: Array[MeshInstance3D] = []
	var wing_mat := Art.mat(Color(0.85,0.95,1.0,0.55), 0.2, 0.0, true)
	for side in [-1, 1]:
		for z in [0.03, -0.02]:
			var w := MeshInstance3D.new()
			w.mesh = Art.mesh("ball")
			w.scale = Vector3(0.13,0.008,0.035)
			w.position = Vector3(side*0.07, 0.015, z)
			w.material_override = wing_mat
			fly.add_child(w)
			wings.append(w)
	for n in fly.get_children(): (n as GeometryInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var dir := Vector3(heading.x, 0, heading.z).normalized()
	if dir == Vector3.ZERO: dir = Vector3.RIGHT
	var side_dir := dir.cross(Vector3.UP)
	var start := at
	var path := func(t: float) -> void:
		if not is_instance_valid(fly): return
		var u := t*2.6
		var p := start+dir*(u*1.6+u*u*0.5)+side_dir*sin(u*3.1)*0.5+Vector3(0, 0.5*u+sin(u*5.0)*0.12, 0)
		var ahead := start+dir*((u+0.05)*1.6+(u+0.05)*(u+0.05)*0.5)+side_dir*sin((u+0.05)*3.1)*0.5+Vector3(0, 0.5*(u+0.05), 0)
		fly.global_position = p
		if ahead.distance_to(p) > 0.001: fly.look_at(ahead, Vector3.UP, true)
		for i in wings.size():
			wings[i].rotation.z = sin(u*70.0+i)*0.6*(1 if i < 2 else -1)
		fly.scale = Vector3.ONE*(1.0 if t < 0.8 else maxf(0.01, (1.0-t)*5.0))
	var t := fly.create_tween()
	t.tween_method(path, 0.0, 1.0, 2.6)
	t.tween_callback(fly.queue_free)

# ------------------------------------------------------------------ node motion
static func wobble(node: Node3D, amount := 0.06, axis := Vector3.RIGHT, cycles := 4, seconds := 0.7) -> void:
	if not is_instance_valid(node): return
	played += 1
	if node.has_meta("fx_wobble"):
		var old: Tween = node.get_meta("fx_wobble")
		if old and old.is_valid(): old.kill()
		node.basis = node.get_meta("fx_rest")
	var rest := node.basis
	node.set_meta("fx_rest", rest)
	var axis_n := axis.normalized() if axis.length() > 0.001 else Vector3.RIGHT
	var sway := func(t: float) -> void:
		if not is_instance_valid(node): return
		var angle := amount*sin(t*TAU*float(cycles)*0.5+0.0)*pow(1.0-t, 1.6)
		node.basis = Basis(axis_n, angle)*rest
	var tween := node.create_tween()
	tween.tween_method(sway, 0.0, 1.0, seconds)
	tween.tween_callback(func():
		if is_instance_valid(node):
			node.basis = rest
			node.remove_meta("fx_wobble"))
	node.set_meta("fx_wobble", tween)

static func squash(node: Node3D, amount := 0.15, seconds := 0.3) -> void:
	if not is_instance_valid(node): return
	played += 1
	if node.has_meta("fx_squash"):
		var old: Tween = node.get_meta("fx_squash")
		if old and old.is_valid(): old.kill()
		node.scale = node.get_meta("fx_scale")
	var rest := node.scale
	node.set_meta("fx_scale", rest)
	var t := node.create_tween()
	t.tween_property(node, "scale", rest*Vector3(1.0+amount, 1.0-amount, 1.0+amount), seconds*0.3)
	t.tween_property(node, "scale", rest*Vector3(1.0-amount*0.5, 1.0+amount*0.6, 1.0-amount*0.5), seconds*0.3)
	t.tween_property(node, "scale", rest, seconds*0.4).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	t.tween_callback(func(): if is_instance_valid(node): node.remove_meta("fx_squash"))
	node.set_meta("fx_squash", t)

# ------------------------------------------------------------------ screen-space
static func _screen(app) -> bool:
	return app != null and is_instance_valid(app) and "ui" in app and is_instance_valid(app.ui) and "camera" in app and is_instance_valid(app.camera)

static func item_pop(app, at: Vector3, item: String, count := 1, delay := 0.0) -> void:
	if not _screen(app): return
	played += 1
	var box := HBoxContainer.new()
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_theme_constant_override("separation", 2)
	box.add_child(Icon.make(item, 40))
	var label := Label.new()
	label.text = "+%d" % count
	label.add_theme_font_size_override("font_size", 24)
	label.add_theme_color_override("font_color", Color("fff3c4"))
	label.add_theme_color_override("font_outline_color", Color("4a3523"))
	label.add_theme_constant_override("outline_size", 7)
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	box.add_child(label)
	box.modulate.a = 0.0
	app.ui.add_child(box)
	var camera: Camera3D = app.camera
	var place := func(t: float) -> void:
		if not is_instance_valid(box) or not is_instance_valid(camera): return
		var p := at+Vector3(0, 0.3+t*0.9, 0)
		box.visible = not camera.is_position_behind(p)
		box.size = box.get_combined_minimum_size()
		box.pivot_offset = box.size*0.5
		box.position = camera.unproject_position(p)-box.size*0.5
		var pop := minf(1.0, t*6.0)
		box.scale = Vector2.ONE*(0.4+0.75*pop-0.15*clampf(t*6.0-1.0, 0.0, 1.0))
		box.modulate.a = minf(1.0, t*8.0)*(1.0-smoothstep(0.65, 1.0, t))
	var tween := box.create_tween()
	if delay > 0.0: tween.tween_interval(delay)
	tween.tween_method(place, 0.0, 1.0, 1.25)
	tween.tween_callback(box.queue_free)

static func fly_to_bag(app, items: Dictionary, from: Vector3, delay := 0.0) -> void:
	if app == null or not is_instance_valid(app): return
	played += 1
	if "life" in app and is_instance_valid(app.life) and app.life.has_method("fly_items"):
		app.life.fly_items(items, from, delay)

static func polaroid(app, image: Image) -> void:
	if not _screen(app) or image == null or image.is_empty(): return
	played += 1
	var small := image.duplicate() as Image
	var w := 220
	small.resize(w, int(w*float(image.get_height())/image.get_width()), Image.INTERPOLATE_BILINEAR)
	var card := PanelContainer.new()
	var paper := StyleBoxFlat.new()
	paper.bg_color = Color("fbf8f0")
	paper.set_content_margin_all(9)
	paper.content_margin_bottom = 30
	paper.shadow_color = Color(0,0,0,0.35)
	paper.shadow_size = 8
	card.add_theme_stylebox_override("panel", paper)
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var pic := TextureRect.new()
	pic.texture = ImageTexture.create_from_image(small)
	pic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(pic)
	app.ui.add_child(card)
	var view: Vector2 = app.ui.get_viewport_rect().size
	card.size = card.get_combined_minimum_size()
	card.pivot_offset = card.size*0.5
	card.position = view*0.5-card.size*0.5
	card.scale = Vector2.ONE*0.2
	card.rotation = -0.08
	var t := card.create_tween()
	t.tween_property(card, "scale", Vector2.ONE*1.1, 0.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	t.parallel().tween_property(card, "rotation", 0.06, 0.25)
	t.tween_interval(0.9)
	t.tween_property(card, "position", Vector2(view.x-card.size.x*0.55-24, view.y-card.size.y*0.55-120), 0.5).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)
	t.parallel().tween_property(card, "scale", Vector2.ONE*0.45, 0.5)
	t.tween_interval(0.8)
	t.tween_property(card, "modulate:a", 0.0, 0.4)
	t.tween_callback(card.queue_free)

static func title(app, at: Vector3, text: String, color := Color("f5e5b7")) -> void:
	if app == null or not is_instance_valid(app): return
	played += 1
	if app.has_method("floating_feedback"): app.floating_feedback(text, at, color)

# ------------------------------------------------------------------ sound
static func sound(app, kind: String, at := Vector3.INF, pitch := 1.0, db := 0.0) -> void:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null or tree.root == null: return
	var volume := -12.0+db
	if at != Vector3.INF and app != null and is_instance_valid(app) and "player" in app and is_instance_valid(app.player):
		volume -= clampf(app.player.global_position.distance_to(at)-3.0, 0.0, 30.0)*0.8
		if volume < -42.0: return
	if voices.is_empty() or not is_instance_valid(voices[0]):
		voices.clear()
		var holder := tree.root.get_node_or_null("FxAudio")
		if holder == null:
			holder = Node.new()
			holder.name = "FxAudio"
			tree.root.add_child(holder)
		for i in 5:
			var v := AudioStreamPlayer.new()
			v.bus = &"Master"
			holder.add_child(v)
			voices.append(v)
	if not streams.has(kind): streams[kind] = _synth(kind)
	var voice: AudioStreamPlayer = voices[voice_next]
	voice_next = (voice_next+1)%voices.size()
	if not voice.is_inside_tree(): return
	voice.stream = streams[kind]
	voice.pitch_scale = pitch*randf_range(0.96, 1.04)
	voice.volume_db = volume
	voice.play()

static func _synth(kind: String) -> AudioStreamWAV:
	var rate := 22050
	var length: float = {"thud":0.2,"leaves":0.6,"twinkle":0.6,"crackle":0.7,"splash":0.4,"pluck":0.35,"pop":0.2,"chirp":0.5,
		"whoosh":0.45,"tune":1.5,"drink":0.5}.get(kind, 0.3)
	var n := int(length*rate)
	var rng := RandomNumberGenerator.new()
	rng.seed = kind.hash()
	var low := 0.0
	var data := PackedByteArray()
	data.resize(n*2)
	for i in n:
		var t := float(i)/rate
		var u := t/length
		var noise := rng.randf_range(-1.0, 1.0)
		var v := 0.0
		match kind:
			"thud":
				low += (noise-low)*0.25
				v = sin(TAU*(140.0-70.0*u)*t)*0.9*exp(-u*9.0)+low*0.8*exp(-u*20.0)
			"leaves":
				low += (noise-low)*0.5
				v = (noise-low)*0.8*sin(PI*u)*(0.55+0.45*absf(sin(t*26.0)))
			"twinkle":
				for k in 3:
					var start := k*0.12
					if t >= start: v += sin(TAU*[1568.0,2093.0,2637.0][k]*(t-start))*0.32*exp(-(t-start)*9.0)
			"crackle":
				low += (noise-low)*0.7
				var pulse := 1.0 if fmod(t*37.0+sin(t*11.0)*3.0, 1.0) < 0.06 else 0.0
				v = (noise-low)*(0.15+pulse*0.9)*(1.0-u)
			"splash":
				low += (noise-low)*0.35
				v = low*1.4*exp(-u*6.0)+sin(TAU*(500.0-300.0*u)*t)*0.4*exp(-u*10.0)
			"pluck":
				v = (sin(TAU*660.0*t)*0.5+sin(TAU*1320.0*t)*0.2+sin(TAU*1980.0*t)*0.08)*exp(-u*7.0)
			"pop":
				v = sin(TAU*(300.0+900.0*u)*t)*0.75*exp(-u*5.0)
			"chirp":
				var k2 := fmod(u*3.0, 1.0)
				v = sin(TAU*(2400.0+1400.0*sin(k2*PI))*t)*0.35*sin(PI*k2)*(1.0 if k2 < 0.7 else 0.0)
			"whoosh":
				low += (noise-low)*(0.05+0.35*sin(PI*u))
				v = low*1.6*sin(PI*u)
			"tune":
				var notes := [523.25, 659.25, 783.99, 659.25, 880.0, 783.99]
				var step := mini(notes.size()-1, int(u*notes.size()))
				var local := fmod(u*notes.size(), 1.0)
				v = (sin(TAU*notes[step]*t)*0.4+sin(TAU*notes[step]*2.0*t)*0.1)*exp(-local*3.0)
			"drink":
				var g := fmod(u*4.0, 1.0)
				v = sin(TAU*(260.0+200.0*g)*t)*0.5*exp(-g*6.0)
		var env := minf(1.0, t*300.0)
		data.encode_s16(i*2, int(clampf(v*env, -1.0, 1.0)*20000))
	var s := AudioStreamWAV.new()
	s.format = AudioStreamWAV.FORMAT_16_BITS
	s.mix_rate = rate
	s.data = data
	return s
