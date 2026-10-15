extends Node3D
## Things a walker carries around (assignment 64): an umbrella over the head, a lantern that glows
## after dark, a paper fan, a balloon on a string, a bouquet, a basket of fruit, a fish to show off
## and a bundle on a stick. Each one sits on an ISS-1 character socket (ix/ix_schema.gd
## CHARACTER_SOCKETS: grip_r, pinch_r, hold_front, back) and is built from a handful of shared
## primitives (life_art.gd); held_pose.gd moves the arms so the hands really hold it.
##
## One node per walker ("Held", a child of player.gd): the hero's (adopt), other players' (show_on,
## from presence `held`, docs/contracts/SERVER_CONTRACTS_KO.md 2). A tool in hand (player.equip:
## rod, hoe, watering can, axe) puts the carried thing away for as long as it is out.
const Art = preload("res://scripts/life_art.gd")
const Fx = preload("res://scripts/fx.gd")
const HeldPose = preload("res://scripts/held_pose.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const Daylight = preload("res://scripts/daylight.gd")
const NODE_NAME := "Held"

## id -> socket, name, the bag items any one of which lets the hero take it out (empty: always).
## Poses (body frame: +X the walker's left, +Y up, +Z forward): `off` is in arm lengths from the
## right shoulder (one-hand) or the middle of the shoulders (hold_front); `hands` are metres from
## the item. Each hand: [handle, hand direction, palm normal, elbow pole].
const CATALOG := {
	"umbrella": {"socket": "grip_r", "name": "우산", "needs": [], "fingers": [true, false],
		"off": Vector3(0.14, -0.6, 0.5), "r": [Vector3.ZERO, Vector3(0.3, 0.2, 1.0), Vector3(1.0, 0.0, -0.3), Vector3(-0.7, -1.0, -0.3)]},
	"lantern": {"socket": "grip_r", "name": "등불", "needs": [], "fingers": [true, false],
		"off": Vector3(0.06, -0.86, 0.42), "r": [Vector3.ZERO, Vector3(0.15, -0.4, 1.0), Vector3(1.0, 0.0, 0.0), Vector3(-0.5, -1.0, -0.4)]},
	"fan": {"socket": "grip_r", "name": "부채", "needs": [], "fingers": [true, false],
		"off": Vector3(-0.05, -0.62, 0.55), "r": [Vector3.ZERO, Vector3(0.2, 0.3, 1.0), Vector3(1.0, 0.0, -0.2), Vector3(-0.7, -1.0, -0.2)]},
	"balloon": {"socket": "pinch_r", "name": "풍선", "needs": [], "fingers": [true, false],
		"off": Vector3(0.04, -0.8, 0.46), "r": [Vector3.ZERO, Vector3(0.1, -0.2, 1.0), Vector3(1.0, 0.0, 0.0), Vector3(-0.5, -1.0, -0.3)]},
	"bouquet": {"socket": "hold_front", "name": "꽃다발", "needs": ["flower", "sunflower"], "fingers": [true, true],
		"off": Vector3(0.0, -0.66, 0.52),
		"r": [Vector3(-0.035, -0.02, 0.0), Vector3(0.25, 0.0, 1.0), Vector3(1.0, 0.0, -0.2), Vector3(-0.8, -1.0, -0.2)],
		"l": [Vector3(0.035, -0.08, 0.0), Vector3(-0.25, 0.0, 1.0), Vector3(-1.0, 0.0, -0.2), Vector3(0.8, -1.0, -0.2)]},
	"basket": {"socket": "hold_front", "name": "과일 바구니", "needs": ["apple", "strawberry", "coconut", "turnip", "carrot", "pumpkin"],
		"fingers": [true, true], "off": Vector3(0.0, -0.98, 0.56),
		"r": [Vector3(-0.17, 0.06, 0.0), Vector3(0.1, -0.25, 1.0), Vector3(1.0, 0.0, 0.0), Vector3(-0.6, -1.0, -0.3)],
		"l": [Vector3(0.17, 0.06, 0.0), Vector3(-0.1, -0.25, 1.0), Vector3(-1.0, 0.0, 0.0), Vector3(0.6, -1.0, -0.3)]},
	"fish": {"socket": "hold_front", "name": "자랑 물고기", "needs": ["crucian", "carp", "catfish", "koi", "mackerel", "puffer", "squid",
		"tuna", "silverfish", "sweetfish", "rainbow", "eel", "trout", "perch"], "fingers": [false, false],
		"off": Vector3(0.0, -0.66, 0.66),
		"r": [Vector3(-0.13, -0.05, 0.0), Vector3(0.45, 0.0, 1.0), Vector3(0.0, 1.0, 0.0), Vector3(-0.8, -1.0, -0.2)],
		"l": [Vector3(0.13, -0.05, 0.0), Vector3(-0.45, 0.0, 1.0), Vector3(0.0, 1.0, 0.0), Vector3(0.8, -1.0, -0.2)]},
	"bindle": {"socket": "back", "name": "보따리", "needs": [], "fingers": [true, false],
		"off": Vector3(0.1, -0.38, 0.5), "r": [Vector3.ZERO, Vector3(1.0, 0.0, 0.2), Vector3(0.0, -0.75, -1.0), Vector3(-0.4, -1.0, 0.1)]},
}
const ORDER := ["umbrella", "lantern", "fan", "balloon", "bouquet", "basket", "fish", "bindle"]

## The hero's choice this session (kept across worlds and rooms) and the last thing it held.
static var hero_choice := ""
static var last_choice := ""
static var hero_ref: WeakRef
static var app_ref: WeakRef
## The server refused `held` once (422 naming it): not sent again this session.
static var held_refused := false

var player: Node
var id := ""
var hero := false
var model: Node3D
var pose: SkeletonModifier3D
var skel: Skeleton3D
var shown := false
var parts := {}
var clock := 0.0
var night := 0.0
var night_at := -10.0
var sway := Vector3.ZERO
var sway_speed := Vector3.ZERO
var balloon_at := Vector3.INF
var balloon_speed := Vector3.ZERO
var pop: Tween

# ------------------------------------------------------------------ ids, presence

## A presence id as drawn: a catalog id, or "fish_<species>" (the fish shows that species). Unknown
## ids draw empty-handed (the contract's rule).
static func base_of(value: String) -> String:
	if CATALOG.has(value): return value
	if value.begins_with("fish_") and Art.FISH_LOOK.has(value.trim_prefix("fish_")): return "fish"
	return ""

## Whether the bag lets the hero take it out (empty needs: always).
static func allowed(item: String, bag: Dictionary) -> bool:
	var needs: Array = CATALOG.get(base_of(item), {}).get("needs", [])
	if needs.is_empty(): return true
	for need in needs:
		if int(bag.get(need, 0)) > 0: return true
	return false

## The id the hero takes out for a catalog entry: the fish is the best one in the bag.
static func pick_id(item: String, bag: Dictionary) -> String:
	if item != "fish": return item
	var best := ""
	var price := -1
	for kind in CATALOG.fish.needs:
		if int(bag.get(kind, 0)) > 0 and Art.FISH_LOOK.has(kind):
			var value := int({"koi": 40, "tuna": 45, "eel": 24, "rainbow": 14, "catfish": 12, "puffer": 12, "squid": 11, "carp": 9}.get(kind, 4))
			if value > price:
				price = value
				best = kind
	return "fish_" + best if not best.is_empty() else "fish"

## The presence field (only when /health advertises presence_held: 1 and it was never refused).
static func presence_extra(hub) -> Dictionary:
	if held_refused or hub == null or not is_instance_valid(hub): return {}
	var health = hub.get("health")
	if not health is Dictionary or int(health.get("presence_held", 0)) != 1: return {}
	return {"held": hero_showing()}

## A 422 that names `held`: stop sending it; true when this was ours (poll again as it was).
static func refused(response: Dictionary) -> bool:
	if int(response.get("status", 0)) != 422 or held_refused: return false
	var named: Array = response.get("fields", []) if response.get("fields") is Array else []
	if not "held" in named: return false
	held_refused = true
	return true

## What the hero shows right now ("" with empty hands or a tool out).
static func hero_showing() -> String:
	var walker = hero_ref.get_ref() if hero_ref else null
	if not is_instance_valid(walker): return ""
	var h: Node = walker.get_node_or_null(NODE_NAME)
	return h.id if h and h.shown else ""

# ------------------------------------------------------------------ walkers

static func holder_of(walker: Node, create := true) -> Node:
	if not is_instance_valid(walker): return null
	var h := walker.get_node_or_null(NODE_NAME)
	if h == null and create:
		h = load("res://scripts/held_items.gd").new()
		h.name = NODE_NAME
		h.player = walker
		walker.add_child(h)
	return h

## The hero of a world (main.gd / studio.gd): takes out this session's choice again.
static func adopt(app, walker: Node) -> void:
	if not is_instance_valid(walker): return
	if app != null: app_ref = weakref(app)
	hero_ref = weakref(walker)
	var h := holder_of(walker)
	h.hero = app != null
	h.set_item(hero_choice, false)

## Another player's carried thing from their presence record.
static func show_on(walker: Node, value) -> void:
	var item := str(value) if value != null else ""
	if base_of(item).is_empty(): item = ""
	var h := holder_of(walker, not item.is_empty())
	if h and h.id != item: h.set_item(item, true)

## The hero takes something out (or puts it away with ""), with the pop and sparkle.
static func hold(item: String) -> void:
	var walker = hero_ref.get_ref() if hero_ref else null
	if not base_of(item).is_empty(): last_choice = item
	hero_choice = item if not base_of(item).is_empty() else ""
	if is_instance_valid(walker): holder_of(walker).set_item(hero_choice, true)

# ------------------------------------------------------------------ the holder node

func _ready() -> void:
	if player == null: player = get_parent()

func set_item(item: String, effects := true) -> void:
	if base_of(item).is_empty(): item = ""
	var was := id
	id = item
	if was != id: _drop_model()
	rebuild()
	refresh(effects)

## After the character was rebuilt (player.apply_avatar): pose layer, skeleton signal and model.
func rebuild() -> void:
	if not is_instance_valid(player) or not is_instance_valid(player.visual): return
	var s: Skeleton3D = player.hand_skeleton if is_instance_valid(player.hand_skeleton) else null
	if s != skel:
		if is_instance_valid(skel) and skel.skeleton_updated.is_connected(_place): skel.skeleton_updated.disconnect(_place)
		skel = s
		if is_instance_valid(skel): skel.skeleton_updated.connect(_place)
	pose = HeldPose.attach(player, self) if is_instance_valid(skel) else null
	# A rebuilt character freed the old visual's children (the model with them).
	if is_instance_valid(model) and (model.is_queued_for_deletion() or model.get_parent() != player.visual):
		model = null
		parts.clear()
		shown = false
	if not id.is_empty() and not is_instance_valid(model): _build()
	_place()

## Shows or hides the item for the walker's state (a tool out puts it away).
func refresh(effects := true) -> void:
	var want := not id.is_empty() and str(player.get("equipped")) == "" and is_instance_valid(model)
	var spec: Dictionary = CATALOG.get(base_of(id), {})
	if is_instance_valid(pose):
		pose.target = 1.0 if want else 0.0
		pose.fade = 0.2
	var fingers = player.get("finger_pose")
	if is_instance_valid(fingers):
		var fist: Array = spec.get("fingers", [false, false])
		fingers.holding = str(player.get("equipped")) != "" or (want and bool(fist[0]))
		fingers.holding_left = want and bool(fist[1])
	if want == shown: return
	shown = want
	if not is_instance_valid(model): return
	var quiet := GameSettings.reduced_motion()
	if pop and pop.is_valid(): pop.kill()
	if want:
		model.visible = true
		model.scale = Vector3.ONE * (1.0 if quiet else 0.05)
		if not quiet:
			pop = model.create_tween()
			pop.tween_interval(0.08)
			pop.tween_property(model, "scale", Vector3.ONE * 1.12, 0.16).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
			pop.tween_property(model, "scale", Vector3.ONE, 0.1)
		if base_of(id) == "umbrella" and parts.has("canopy"): (parts.canopy as Node3D).scale = Vector3(0.18, 1.5, 0.18) if not quiet else Vector3.ONE
		if effects and player.is_inside_tree() and player.get_parent() is Node3D:
			var at: Vector3 = model.global_position + Vector3(0, 0.15, 0)
			Fx.burst(player.get_parent(), at, "sparkle", 6 if quiet else 10, Color(0, 0, 0, 0), 0.22)
			Fx.sound(app_ref.get_ref() if app_ref else null, "pop", at if not hero else Vector3.INF, 1.15, -2.0)
	else:
		if effects and not quiet and model.visible:
			pop = model.create_tween()
			pop.tween_property(model, "scale", Vector3.ONE * 0.05, 0.14).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_IN)
			pop.tween_callback(func(): if not shown and is_instance_valid(model): model.visible = false)
		else:
			model.visible = false

func _drop_model() -> void:
	if is_instance_valid(model):
		if model.get_parent(): model.get_parent().remove_child(model)
		model.queue_free()
	model = null
	parts.clear()
	shown = false
	balloon_at = Vector3.INF

# ------------------------------------------------------------------ pose and placement

## Body frame -> the visual frame (the visual faces -Z; +X body is the walker's left).
static func vb(v: Vector3) -> Vector3:
	return Vector3(-v.x, v.y, -v.z)

## Where the item sits in the visual frame from the shoulders now ({} when the rig is unread).
func anchor(p: SkeletonModifier3D) -> Vector3:
	var spec: Dictionary = CATALOG.get(base_of(id), {})
	if spec.is_empty() or not p.ready_for(skel): return Vector3.INF
	var arm: float = p.cfg.get("arm", 0.55)
	var off: Vector3 = spec.off
	if spec.socket == "hold_front":
		var mid: Vector3 = (p.shoulder(skel, "r") + p.shoulder(skel, "l")) * 0.5
		return mid + vb(off * arm)
	return p.shoulder(skel, "r") + vb(off * arm)

## held_pose.gd asks every tick: palm targets for the hands that hold.
func arm_targets(p: SkeletonModifier3D) -> Dictionary:
	var out := {}
	var spec: Dictionary = CATALOG.get(base_of(id), {})
	var at := anchor(p)
	if spec.is_empty() or not at.is_finite(): return out
	for side in ["r", "l"]:
		if not spec.has(side): continue
		var hand: Array = spec[side]
		out[side] = {"at": at + vb(hand[0]), "dir": vb(hand[1]).normalized(), "palm": vb(hand[2]).normalized(), "pole": vb(hand[3]).normalized()}
	return out

## Puts the model where the hands are after the final pose (the skeleton's update), in the visual
## frame so it moves with the drawn body.
func _place() -> void:
	if not is_instance_valid(model) or not is_instance_valid(player) or not is_instance_valid(player.visual): return
	var spec: Dictionary = CATALOG.get(base_of(id), {})
	var at := mount(str(spec.get("socket", "grip_r")))
	if not at.is_finite(): return
	# Position only: the turn is set once (_build) and the scale belongs to the pop tween.
	model.position = at

## THE one place that maps a carry socket onto the body (visual frame, final pose). grip_r and back
## go to the equipment sockets (N6 equip_sockets.gd, via player.socket(), which takes the ISS-1 names;
## its hand_r is IxRig.GRIP_R's grip) once the player has socket(); until then, and for pinch_r and
## hold_front (not equipment sockets), the points come from the ix rig here (held_pose.gd palms):
## pinch_r = the right palm, hold_front = the midpoint of both palms less the item's mean handle.
## The bindle's socket is back but its stick is held in the right hand, so it follows grip_r.
func mount(socket: String) -> Vector3:
	if not is_instance_valid(pose) or not is_instance_valid(skel) or not pose.ready_for(skel):
		return Vector3(0.36, 0.95, -0.25) if socket != "hold_front" else Vector3(0, 0.9, -0.4)
	var spec: Dictionary = CATALOG.get(base_of(id), {})
	match socket:
		"hold_front":
			var mean := (vb(spec.r[0]) + vb(spec.l[0])) * 0.5 if spec.has("r") and spec.has("l") else Vector3.ZERO
			return (pose.palm_point(skel, "r") + pose.palm_point(skel, "l")) * 0.5 - mean
		"pinch_r":
			return pose.palm_point(skel, "r")
		"back":
			if spec.has("r"): return equipment_point("grip_r")
			return equipment_point("back")
	return equipment_point("grip_r")

## An equipment socket's point now (visual frame): player.socket(name) when it exists (read from its
## bone's current pose, so it never lags a tick behind the hand), else the ix rig's own points.
func equipment_point(name: String) -> Vector3:
	if player.has_method("socket"):
		var node = player.socket(name)
		if node is Node3D and node.get_parent() is BoneAttachment3D:
			var bone := skel.find_bone((node.get_parent() as BoneAttachment3D).bone_name)
			if bone >= 0:
				var to_visual: Transform3D = player.visual.global_transform.affine_inverse() * skel.global_transform
				return to_visual * (skel.get_bone_global_pose(bone) * (node as Node3D).transform).origin
	if name == "back": return (pose.shoulder(skel, "r") + pose.shoulder(skel, "l")) * 0.5 + vb(Vector3(0, -0.05, -0.15))
	return pose.palm_point(skel, "r")

## Hand-to-handle distances (metres) for checks: {"r": d, "l": d}.
func grip_error() -> Dictionary:
	var out := {}
	if not is_instance_valid(pose) or not is_instance_valid(skel) or not is_instance_valid(model): return out
	var spec: Dictionary = CATALOG.get(base_of(id), {})
	for side in ["r", "l"]:
		if not spec.has(side): continue
		var handle: Vector3 = model.position + vb(spec[side][0])
		out[side] = pose.palm_point(skel, side).distance_to(handle)
	return out

# ------------------------------------------------------------------ motion

func _process(delta: float) -> void:
	if not shown or not is_instance_valid(model) or not is_instance_valid(player): return
	clock += delta
	var quiet := GameSettings.reduced_motion()
	var kind := base_of(id)
	var lean: Vector2 = player.get("lean") if player.get("lean") is Vector2 else Vector2.ZERO
	# A hanging or bobbing part trails the walk on a soft spring (the body leans into speed).
	var want := Vector3(lean.x * 3.0, 0.0, -lean.y * 3.0) + (Vector3(sin(clock * 1.3) * 0.05, 0, sin(clock * 0.9) * 0.04) if not quiet else Vector3.ZERO)
	sway_speed += ((want - sway) * 40.0 - sway_speed * 7.0) * delta
	sway += sway_speed * delta
	match kind:
		"umbrella":
			if parts.has("canopy"):
				var c: Node3D = parts.canopy
				c.scale = c.scale.lerp(Vector3.ONE, 1.0 - exp(-9.0 * delta))
		"lantern":
			if parts.has("pivot"): (parts.pivot as Node3D).rotation = Vector3(sway.x, 0, sway.z)
			if clock - night_at > 1.0 or night_at < 0.0:
				night_at = clock
				night = _night()
			if parts.has("glow"):
				var m: StandardMaterial3D = (parts.glow as MeshInstance3D).material_override
				var pulse := 1.0 if quiet else 0.92 + 0.08 * sin(clock * 5.3)
				m.albedo_color.a = (0.05 + 0.5 * night) * pulse
				(parts.glow as Node3D).visible = m.albedo_color.a > 0.02
		"fan":
			if parts.has("blade"):
				var wave := 0.0 if quiet else sin(clock * 6.0) * 0.45
				(parts.blade as Node3D).rotation = Vector3(0, -0.55 + wave, 0)
		"balloon":
			_balloon(delta, quiet)
		"bouquet", "basket", "fish":
			model.rotation.z = 0.0 if quiet else sin(clock * 2.0) * 0.015

func _night() -> float:
	var app = app_ref.get_ref() if app_ref else null
	if is_instance_valid(app) and app.get("daylight") and app.daylight.get("current") is Dictionary and app.daylight.current.has("night"):
		return float(app.daylight.current.night)
	return float(Daylight.sample(Daylight.clock_hour()).night)

## The balloon floats a metre over the hand, trails the walk and bobs; the string follows.
func _balloon(delta: float, quiet: bool) -> void:
	if not parts.has("ball") or not parts.has("string"): return
	var ball: Node3D = parts.ball
	var string: Node3D = parts.string
	var velocity := Vector3.ZERO
	var walk = player.get("locomotion_velocity")
	if walk is Vector2 and is_instance_valid(player.visual):
		velocity = model.global_basis.orthonormalized().inverse() * Vector3(walk.x, 0, walk.y)
	var rest := Vector3(0.05, 1.05, 0.0) - Vector3(velocity.x, 0, velocity.z) * 0.07
	if not quiet: rest += Vector3(sin(clock * 1.1) * 0.05, sin(clock * 1.7) * 0.04, cos(clock * 0.8) * 0.04)
	if not balloon_at.is_finite(): balloon_at = rest
	balloon_speed += ((rest - balloon_at) * 18.0 - balloon_speed * 4.0) * delta
	balloon_at += balloon_speed * delta
	balloon_at = balloon_at.normalized() * clampf(balloon_at.length(), 0.6, 1.1)
	ball.position = balloon_at
	string.position = balloon_at * 0.5
	var up := balloon_at.normalized()
	var side := up.cross(Vector3.FORWARD)
	if side.length_squared() < 0.001: side = Vector3.RIGHT
	side = side.normalized()
	string.basis = Basis(side * 0.006, up * balloon_at.length(), side.cross(up) * 0.006)

# ------------------------------------------------------------------ models

func _build() -> void:
	_drop_model()
	if not is_instance_valid(player) or not is_instance_valid(player.visual): return
	model = Node3D.new()
	model.name = "HeldItem"
	model.rotation.y = PI
	player.visual.add_child(model)
	model.visible = false
	var kind := base_of(id)
	var root := Node3D.new()
	model.add_child(root)
	match kind:
		"umbrella": _umbrella(root)
		"lantern": _lantern(root)
		"fan": _fan(root)
		"balloon": _balloon_model(root)
		"bouquet": _bouquet(root)
		"basket": _basket(root)
		"fish": _fish(root)
		"bindle": _bindle(root)
	for m in model.find_children("*", "MeshInstance3D", true, false):
		(m as MeshInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if (m as MeshInstance3D).scale.length() < 0.5 else GeometryInstance3D.SHADOW_CASTING_SETTING_ON

## Model frame = body frame (+X the walker's left, +Y up, +Z forward), origin on the handle.
func _umbrella(root: Node3D) -> void:
	# Shaft tipped a little back and in so the canopy sits over the head.
	var shaft := Node3D.new()
	root.add_child(shaft)
	shaft.basis = Basis(Vector3(0, 0, 1), -0.14) * Basis(Vector3(1, 0, 0), -0.18)
	Art.part(shaft, "rod", Vector3(0, 0.44, 0), Vector3(0.022, 1.0, 0.022), Color("6b4a33"))
	Art.part(shaft, "capsule", Vector3(0, -0.1, 0), Vector3(0.04, 0.05, 0.04), Color("8a5a3a"))
	var canopy := Node3D.new()
	canopy.position = Vector3(0, 0.92, 0)
	shaft.add_child(canopy)
	Art.part(canopy, "dome", Vector3.ZERO, Vector3(1.1, 0.55, 1.1), Color("f08c8c"), Vector3.ZERO, 0.7)
	Art.part(canopy, "dome", Vector3(0, 0.005, 0), Vector3(1.04, 0.12, 1.04), Color("f6c9b8"), Vector3(PI, 0, 0), 0.9)
	for i in 8:
		var a := TAU * i / 8.0
		Art.part(canopy, "ball", Vector3(cos(a) * 0.54, -0.01, sin(a) * 0.54), Vector3.ONE * 0.045, Color("fff4e8"))
	Art.part(canopy, "cone", Vector3(0, 0.32, 0), Vector3(0.05, 0.12, 0.05), Color("6b4a33"))
	parts["canopy"] = canopy

func _lantern(root: Node3D) -> void:
	var pivot := Node3D.new()
	root.add_child(pivot)
	Art.part(pivot, "rod", Vector3(0, -0.06, 0), Vector3(0.012, 0.13, 0.012), Color("3e3a36"))
	var body := Node3D.new()
	body.position = Vector3(0, -0.22, 0)
	pivot.add_child(body)
	Art.part(body, "cone", Vector3(0, 0.11, 0), Vector3(0.2, 0.07, 0.2), Color("4a4038"))
	Art.part(body, "box", Vector3(0, -0.1, 0), Vector3(0.17, 0.025, 0.17), Color("4a4038"))
	for x in [-1, 1]:
		for z in [-1, 1]:
			Art.part(body, "box", Vector3(x * 0.075, 0, z * 0.075), Vector3(0.02, 0.2, 0.02), Color("5a4c40"))
	var core := MeshInstance3D.new()
	core.mesh = Art.mesh("ball")
	core.scale = Vector3(0.13, 0.17, 0.13)
	core.material_override = Art.mat(Color("ffd27a"), 0.5, 2.2, true)
	body.add_child(core)
	Art.part(body, "box", Vector3.ZERO, Vector3(0.15, 0.18, 0.15), Color(1.0, 0.93, 0.78, 0.35), Vector3.ZERO, 0.3)
	var glow := MeshInstance3D.new()
	var quad := QuadMesh.new()
	quad.size = Vector2(1.0, 1.0)
	glow.mesh = quad
	var m := StandardMaterial3D.new()
	m.albedo_texture = Fx.tex("soft")
	m.albedo_color = Color(1.0, 0.72, 0.36, 0.0)
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	glow.material_override = m
	glow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	glow.scale = Vector3.ONE * 0.7
	body.add_child(glow)
	parts["pivot"] = pivot
	parts["glow"] = glow

func _fan(root: Node3D) -> void:
	# Tipped out to the walker's right so the face stays in view.
	root.basis = Basis(Vector3.BACK, 0.3)
	Art.part(root, "rod", Vector3(0, 0.05, 0), Vector3(0.016, 0.2, 0.016), Color("8a5a3a"))
	var blade := Node3D.new()
	blade.position = Vector3(0, 0.15, 0)
	root.add_child(blade)
	# A round paper fan (taegeuk-coloured halves), standing face-on to the walker.
	Art.part(blade, "ball", Vector3(0, 0.12, 0), Vector3(0.27, 0.27, 0.014), Color("f3ead6"))
	Art.part(blade, "ball", Vector3(0, 0.135, 0.006), Vector3(0.19, 0.17, 0.012), Color("d9534f"))
	Art.part(blade, "ball", Vector3(0, 0.08, 0.009), Vector3(0.11, 0.08, 0.012), Color("3c6fb6"))
	parts["blade"] = blade

func _balloon_model(root: Node3D) -> void:
	var string := Art.part(root, "rod", Vector3(0, 0.5, 0), Vector3(0.006, 1.0, 0.006), Color("f5f0e6"))
	var ball := Node3D.new()
	root.add_child(ball)
	Art.part(ball, "ball", Vector3(0, 0.18, 0), Vector3(0.34, 0.4, 0.34), Color("f2667f"), Vector3.ZERO, 0.35)
	Art.part(ball, "ball", Vector3(-0.06, 0.26, 0.12), Vector3(0.07, 0.09, 0.04), Color("ffd6de"), Vector3.ZERO, 0.2)
	Art.part(ball, "cone", Vector3(0, -0.02, 0), Vector3(0.05, 0.05, 0.05), Color("d94d68"), Vector3(PI, 0, 0))
	parts["string"] = string
	parts["ball"] = ball

func _bouquet(root: Node3D) -> void:
	var tilt := Node3D.new()
	tilt.rotation = Vector3(0.35, 0, 0)
	root.add_child(tilt)
	Art.part(tilt, "cone", Vector3(0, 0.06, 0), Vector3(0.16, 0.3, 0.16), Color("f3e1c4"), Vector3(PI, 0, 0))
	Art.part(tilt, "rod", Vector3(0, -0.05, 0), Vector3(0.07, 0.03, 0.07), Color("e57a8f"))
	var colors := Art.FLOWER_COLORS
	for i in 7:
		var a := TAU * i / 7.0
		var r := 0.0 if i == 0 else 0.075
		var at := Vector3(cos(a) * r, 0.24 + (0.03 if i == 0 else 0.0), sin(a) * r)
		Art.part(tilt, "ball", at, Vector3.ONE * 0.075, colors[i % colors.size()], Vector3.ZERO, 0.6)
		Art.part(tilt, "ball", at + Vector3(0, 0.03, 0), Vector3.ONE * 0.03, Color("f7d35a"))
	for i in 5:
		var a := TAU * i / 5.0 + 0.3
		Art.leaf(tilt, Vector3(cos(a) * 0.06, 0.2, sin(a) * 0.06), a, 0.5, 0.09, Color("6aac5a"))

func _basket(root: Node3D) -> void:
	Art.part(root, "rod", Vector3(0, -0.02, 0), Vector3(0.32, 0.15, 0.24), Color("b98a52"))
	for y in [-0.06, 0.0, 0.05]:
		Art.part(root, "rod", Vector3(0, y, 0), Vector3(0.335, 0.012, 0.255), Color("94693c"))
	# The handle arch over the fruit, side to side.
	for i in 7:
		var a := PI * i / 6.0
		Art.part(root, "ball", Vector3(cos(a) * 0.15, 0.06 + sin(a) * 0.16, 0), Vector3(0.035, 0.035, 0.035), Color("94693c"))
	var fruit := [Color("e0443c"), Color("f29a35"), Color("e0443c"), Color("9ec94a"), Color("f2c94c")]
	for i in fruit.size():
		var a := TAU * i / fruit.size()
		Art.part(root, "ball", Vector3(cos(a) * 0.07, 0.065, sin(a) * 0.05), Vector3.ONE * 0.085, fruit[i], Vector3.ZERO, 0.5)

func _fish(root: Node3D) -> void:
	var species := id.trim_prefix("fish_") if id.begins_with("fish_") else "carp"
	var fish := Art.fish(species, 0.46)
	# Lying across the hands, head to the walker's right, belly down, a little proud tilt.
	fish.basis = Basis(Vector3.UP, -PI / 2) * Basis(Vector3.FORWARD, 0.12)
	fish.position = Vector3(0, 0.05, 0)
	root.add_child(fish)

func _bindle(root: Node3D) -> void:
	# The stick runs from the hand back over the shoulder; the bundle hangs behind.
	var stick := Node3D.new()
	root.add_child(stick)
	var back := Vector3(-0.1, 1.0, -0.75).normalized()
	stick.basis = Basis(Quaternion(Vector3.UP, back))
	Art.part(stick, "rod", Vector3(0, 0.38, 0), Vector3(0.028, 0.92, 0.028), Color("8a6a45"))
	var bundle := Node3D.new()
	bundle.position = back * 0.8 + Vector3(0, -0.12, 0)
	root.add_child(bundle)
	Art.part(bundle, "ball", Vector3.ZERO, Vector3(0.26, 0.24, 0.24), Color("d4574e"), Vector3.ZERO, 0.9)
	Art.part(bundle, "ball", Vector3(0, 0.12, 0), Vector3(0.1, 0.07, 0.1), Color("b8453d"))
	for i in 4:
		var a := TAU * i / 4.0 + 0.4
		Art.part(bundle, "ball", Vector3(cos(a) * 0.1, 0.02, sin(a) * 0.1), Vector3.ONE * 0.045, Color("f4efe0"))

# ------------------------------------------------------------------ the bag strip

## A row of carryable things for the storage window (village_life.open_storage): click to take one
## out (the window closes so the pop is seen), click the one in hand to put it away.
static func strip(parent: Control, app, bag: Dictionary) -> void:
	var RpgUi = load("res://scripts/rpg_ui.gd")
	var row := HBoxContainer.new()
	row.name = "HeldStrip"
	row.add_theme_constant_override("separation", 6)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	parent.add_child(row)
	for item in ORDER:
		var spec: Dictionary = CATALOG[item]
		var ok := allowed(item, bag)
		var current: bool = base_of(hero_choice) == item
		var button := Button.new()
		button.name = "Held_" + item
		button.custom_minimum_size = Vector2(76, 76)
		button.focus_mode = Control.FOCUS_NONE
		var paper: StyleBox = RpgUi.frame("slot_paper", Color("ffe39a") if current else Color.WHITE)
		for state in ["normal", "hover", "pressed", "disabled"]:
			button.add_theme_stylebox_override(state, paper)
		var picture := ItemIcon.new()
		picture.item = item
		picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
		picture.set_anchors_preset(Control.PRESET_FULL_RECT)
		picture.offset_left = 10; picture.offset_top = 6; picture.offset_right = -10; picture.offset_bottom = -18
		button.add_child(picture)
		var caption := Label.new()
		caption.text = _t("넣기") if current else _t(spec.name)
		caption.add_theme_font_size_override("font_size", 11)
		caption.add_theme_color_override("font_color", RpgUi.PAPER_INK)
		caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
		caption.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
		caption.offset_top = -19; caption.offset_bottom = -3
		button.add_child(caption)
		if not ok:
			button.disabled = true
			button.modulate = Color(1, 1, 1, 0.42)
		RpgUi.name_tip(button, _t(spec.name) if ok else _t(spec.name) + " · " + _t("가방에 재료가 있으면 들 수 있어요"))
		var chosen: String = item
		button.pressed.connect(func():
			RpgUi.sfx("select", -8.0)
			hold("" if base_of(hero_choice) == chosen else pick_id(chosen, bag))
			if app != null and is_instance_valid(app) and app.has_method("close_village_modal"): app.close_village_modal())
		row.add_child(button)

static func _t(text: String) -> String:
	return TranslationServer.translate(text)

## Flat icons for the strip, drawn like life_icon.gd (simple shapes, paper ink outline).
class ItemIcon extends Control:
	var item := ""
	func _draw() -> void:
		var s := minf(size.x, size.y) / 64.0
		draw_set_transform(Vector2((size.x - 64 * s) * 0.5, (size.y - 64 * s) * 0.5), 0, Vector2(s, s))
		var ink := Color("5a4632")
		match item:
			"umbrella":
				_arc_fill(Vector2(32, 30), 24, PI, TAU, Color("f08c8c"))
				draw_line(Vector2(32, 30), Vector2(32, 54), ink, 3)
				draw_arc(Vector2(28, 54), 4, 0, PI, 8, ink, 3)
			"lantern":
				draw_line(Vector2(32, 6), Vector2(32, 16), ink, 3)
				draw_circle(Vector2(32, 38), 16, Color(1.0, 0.8, 0.4, 0.35))
				draw_rect(Rect2(22, 18, 20, 34), Color("ffd27a"))
				draw_rect(Rect2(22, 18, 20, 34), ink, false, 3)
				draw_rect(Rect2(19, 14, 26, 5), ink)
			"fan":
				draw_line(Vector2(32, 36), Vector2(32, 60), Color("8a5a3a"), 4)
				_arc_fill(Vector2(32, 26), 20, PI, TAU, Color("d9534f"))
				_arc_fill(Vector2(32, 26), 20, 0, PI, Color("3c6fb6"))
			"balloon":
				draw_line(Vector2(32, 40), Vector2(30, 62), ink, 2)
				draw_circle(Vector2(32, 22), 17, Color("f2667f"))
				draw_circle(Vector2(26, 15), 4, Color("ffd6de"))
			"bouquet":
				draw_colored_polygon(PackedVector2Array([Vector2(20, 30), Vector2(44, 30), Vector2(32, 60)]), Color("f3e1c4"))
				for p in [[Vector2(24, 24), "f27fae"], [Vector2(40, 24), "b98cf0"], [Vector2(32, 16), "f7cf3a"], [Vector2(32, 28), "f0705f"]]:
					draw_circle(p[0], 8, Color(p[1]))
			"basket":
				draw_arc(Vector2(32, 34), 16, PI, TAU, 12, Color("94693c"), 4)
				for p in [[Vector2(24, 32), "e0443c"], [Vector2(34, 30), "f29a35"], [Vector2(42, 33), "9ec94a"]]:
					draw_circle(p[0], 7, Color(p[1]))
				draw_colored_polygon(PackedVector2Array([Vector2(12, 34), Vector2(52, 34), Vector2(46, 56), Vector2(18, 56)]), Color("b98a52"))
			"fish":
				draw_colored_polygon(PackedVector2Array([Vector2(8, 32), Vector2(20, 22), Vector2(44, 22), Vector2(54, 32), Vector2(44, 42), Vector2(20, 42)]), Color("7fa6c4"))
				draw_colored_polygon(PackedVector2Array([Vector2(10, 32), Vector2(2, 22), Vector2(2, 42)]), Color("5f86a4"))
				draw_circle(Vector2(46, 30), 3, ink)
			"bindle":
				draw_line(Vector2(10, 58), Vector2(46, 16), Color("8a6a45"), 4)
				draw_circle(Vector2(46, 20), 13, Color("d4574e"))
				draw_circle(Vector2(46, 9), 4, Color("b8453d"))
	func _arc_fill(c: Vector2, r: float, from: float, to: float, color: Color) -> void:
		var p := PackedVector2Array([c])
		for i in 13: p.append(c + Vector2(cos(lerpf(from, to, i / 12.0)), sin(lerpf(from, to, i / 12.0))) * r)
		draw_colored_polygon(p, color)
