extends Node
## Under-foot effects: a small puff where a foot lands, drawn from the same surface judgement as
## the footstep sound (world_audio.gd `stepped`, SURFACE_FX): dust on dry ground (tinted per
## surface), splashes and a ripple in shallows, snow powder, a few dry leaves in litter, grass
## bits on grass. Hard floors show nothing. Remote walkers past REMOTE_AUDIBLE never emit, and a
## shared budget keeps a crowd from flooding the particle pools.
##   FootFx.attach(app, world_audio) -> Node   (app: main.gd; needs app.world or app.player)
const Fx := preload("res://scripts/fx.gd")
const Fishing := preload("res://scripts/fishing.gd")

## Puffs per second across every walker, and how many may bank up.
const RATE := 12.0
const BANK := 5.0
## Dust colour per dry surface (scuff kind is tinted with it).
## Against the ground: a shade lighter on dark soil, a little darker on pale sand (flat: no night
## darkening of its own, see _shade).
const DUST := {"sand": Color("cdb284"), "dirt": Color("cdb28c"), "gravel": Color("dcd8d0"), "ash": Color("b3afab")}
## Grass bits only on some steps (every step reads as mowing).
const GRASS_CHANCE := 0.6

var app: Node
var tokens := BANK
var last_ms := 0
var rng := RandomNumberGenerator.new()
## The hero's last foot plant (heading when the body reports no velocity).
var last_hero := Vector3.INF
## Puffs drawn (tests).
var drawn := 0

static func attach(host: Node, audio: Node) -> Node:
	var f := new()
	f.name = "FootFx"
	f.app = host
	host.add_child(f)
	if audio != null and audio.has_signal("stepped"): audio.stepped.connect(f.on_stepped)
	return f

func on_stepped(info: Dictionary) -> void:
	var fx := str(info.get("fx", ""))
	var kind := str(info.get("kind", "step"))
	if fx.is_empty() and kind != "splash": return
	var at: Vector3 = info.get("at", Vector3.INF)
	if at == Vector3.INF: return
	var parent := _parent()
	if parent == null: return
	if not _spend(2.0 if kind != "step" else 1.0): return
	var run := str(info.get("gait", "walk")) == "run"
	var hero := str(info.get("who", "hero")) == "hero"
	var back := Vector3.ZERO
	var side := Vector3.ZERO
	if hero:
		# Heading: the body's velocity, else (expedition walkers are placed, not moved) the way from
		# the last foot plant to this one.
		var v := Vector3.ZERO
		if is_instance_valid(app.player) and app.player is CharacterBody3D: v = app.player.velocity
		v.y = 0.0
		if v.length() <= 0.3 and last_hero != Vector3.INF:
			var d := (at-last_hero)*Vector3(1, 0, 1)
			if d.length() > 0.05 and d.length() < 3.0: v = d
		last_hero = at
		if v.length() > 0.01:
			back = -v.normalized()
			side = v.normalized().cross(Vector3.UP)
	var foot := int(info.get("foot", -1))
	var spot := at+side*(0.11 if foot == 1 else -0.11 if foot == 0 else 0.0)+back*0.12+Vector3(0, 0.05, 0)
	drawn += 1
	match kind:
		"land": _land(parent, spot, fx, str(info.get("surface", "")))
		"splash": _splash(parent, at, float(info.get("size", 1.0)))
		_: _step(parent, spot, fx, str(info.get("surface", "")), run, back)

func _step(parent: Node3D, spot: Vector3, fx: String, surface: String, run: bool, back: Vector3) -> void:
	match fx:
		"dust":
			Fx.kick(parent, spot, "scuff", 5 if run else 3, back, _shade(DUST.get(surface, Color("e8dcc4"))), 0.08, 1.25 if run else 0.8)
		"splash":
			var top := _water(spot)
			Fx.kick(parent, top, "splash", 7 if run else 4, back, _shade(Color("e6f6ff")), 0.1, 0.55 if run else 0.4)
			Fx.ring(parent, top-Vector3(0, 0.03, 0), 0.75 if run else 0.55, _shade(Color(1, 1, 1, 0.42)), 0.7)
		"snow":
			Fx.kick(parent, spot, "snow", 7 if run else 4, back, _shade(Color("f4f8fc")), 0.07, 1.1 if run else 0.75)
		"leaves":
			Fx.kick(parent, spot, "litter", 4 if run else 2, back, Color(0,0,0,0), 0.08, 1.1 if run else 0.8)
			if run: Fx.kick(parent, spot, "scuff", 2, back, Color("c4a77c"), 0.05, 0.7)
		"grass":
			if rng.randf() < (GRASS_CHANCE*1.6 if run else GRASS_CHANCE):
				Fx.kick(parent, spot, "blade", 4 if run else 3, back, _shade(Color("c3df74")), 0.06, 1.0 if run else 0.7)

## Landing from a jump or a fall: a wider ring of the same stuff.
func _land(parent: Node3D, spot: Vector3, fx: String, surface: String) -> void:
	match fx:
		"dust":
			Fx.burst(parent, spot, "scuff", 8, _shade(DUST.get(surface, Color("e8dcc4"))), 0.28)
			Fx.ring(parent, spot, 0.9, _shade(Color(DUST.get(surface, Color("e8dcc4")), 0.45)), 0.5)
		"snow": Fx.burst(parent, spot, "snow", 12, _shade(Color("f4f8fc")), 0.3)
		"leaves": Fx.burst(parent, spot, "litter", 5, Color(0,0,0,0), 0.3)
		"grass": Fx.burst(parent, spot, "blade", 5, _shade(Color("c3df74")), 0.25)
		"splash": _splash(parent, spot, 0.6)

## Wading in or falling into water: drops thrown up and a ring on the surface (size ~0.5..1.5).
func _splash(parent: Node3D, at: Vector3, size: float) -> void:
	var top := _water(at)
	var s := clampf(size, 0.3, 1.6)
	Fx.burst(parent, top, "splash", roundi(8+10*s), _shade(Color("e6f6ff")), 0.2+0.25*s)
	Fx.ring(parent, top-Vector3(0, 0.03, 0), 1.0+1.2*s, _shade(Color(1, 1, 1, 0.55)), 0.9)
	if s >= 0.75: Fx.ring(parent, top-Vector3(0, 0.03, 0), 0.6+0.8*s, _shade(Color(1, 1, 1, 0.4)), 0.65)

## The water surface over a wading foot: the village's ponds and sea; elsewhere a little above the foot.
func _water(at: Vector3) -> Vector3:
	if str(app.get("screen")) == "village":
		return Vector3(at.x, maxf(at.y, Fishing.water_level(Vector2(at.x, at.z)))+0.02, at.z)
	return at+Vector3(0, 0.08, 0)

## The puff colours are unshaded (they must read against the ground in daylight), so they take the
## scene's light here: darker and a little toward the ambient colour at night (daylight.gd current).
func _shade(c: Color) -> Color:
	var light = app.get("daylight")
	if light == null or not is_instance_valid(light): return c
	var now = light.get("current")
	if not (now is Dictionary) or not now.has("night"): return c
	var night := clampf(float(now.night), 0.0, 1.0)
	var ambient: Color = now.get("ambient_color", Color.WHITE)
	var lit := Color(c.r, c.g, c.b)*lerpf(1.0, 0.42, night)
	lit = lit.lerp(lit*ambient, 0.35*night)
	return Color(lit.r, lit.g, lit.b, c.a)

func _parent() -> Node3D:
	var world = app.get("world")
	if world is Node3D and is_instance_valid(world) and world.is_inside_tree(): return world
	var player = app.get("player")
	if player is Node3D and is_instance_valid(player) and player.is_inside_tree() and player.get_parent() is Node3D: return player.get_parent()
	return null

func _spend(cost: float) -> bool:
	var now := Time.get_ticks_msec()
	tokens = minf(BANK, tokens+(now-last_ms)*0.001*RATE)
	last_ms = now
	if tokens < cost: return false
	tokens -= cost
	return true
