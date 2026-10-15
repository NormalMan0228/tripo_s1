extends RefCounted
## ISS-1 pure math: where a socket record lands on an object in the world (placement yaw, the
## player's shape edit and mirror, the moving part that carries it), which way it faces, how far the
## walker may be bent toward it, and the procedural "virtual clips" that take a body onto it and off
## it again without a jump. Static functions only; the tests check every one (tests/ix_math_check.gd).
##
## A resolve context (ctx) is a plain dictionary:
##   xform  Transform3D  the carrier's global transform (whole_root, a part pivot, a prop or a room piece)
##   box    AABB         the carrier's box in its own frame before the shape factors (fractions `at` refer to it)
##   k      Vector3      shape factors between the carrier frame and the box (x < 0 when mirrored). Part
##                       pivots already carry the shape in their transform, so they pass Vector3.ONE.
##   mirror bool         the object is mirrored (swaps l/r in params); defaults to k.x < 0 or det < 0
##   scale  Vector3      |shape factors| of the whole object, for width/depth/length (defaults to |k|)
##   floor_y float       the floor height under the socket (NAN: unknown, heights then use xform's y)
const Schema = preload("res://scripts/ix/ix_schema.gd")

const UP := Vector3.UP
## Clamp of the planar residual a clip may be warped by (beyond it: re-align or another variant).
const WARP_XZ := 0.35
const WARP_YAW := deg_to_rad(45.0)
## Clamp of the vertical warp (seat height against the clip's reference height).
const WARP_LIMIT := 0.18
## The driver turns the walker at most this fast (rad/s); per tick the visual yaw moves <= 0.35 rad.
const TURN_RATE := 10.0
const STEP_LIMIT := 0.08
const YAW_STEP_LIMIT := 0.35

# ------------------------------------------------------------------ record -> point

## The record's point in its carrier's base frame (before shape factors): `pos` in metres, or `at` as
## fractions of the carrier box (x and z from the centre -0.5..0.5, y from the bottom 0..1). A repeated
## seat adds its base offset along the repeat axis (rep_dx, base metres).
static func base_point(rec: Dictionary, box: AABB) -> Vector3:
	var p: Vector3
	if rec.has("pos"): p = rec.pos
	else: p = box.position + box.size * (Vector3(rec.get("at", Vector3(0, 1, 0))) + Vector3(0.5, 0.0, 0.5))
	if rec.has("rep_dx"):
		var axis := Vector3.RIGHT if str(rec.get("repeat", {}).get("axis", "x")) == "x" else Vector3.BACK
		p += axis * float(rec.rep_dx)
	return p

## Carrier-frame point after the shape: componentwise k, then the clearance offset in metres (its x
## follows the mirror, so a clearance never stretches but still lands on the right side).
static func shaped_point(p_b: Vector3, k: Vector3, off: Vector3) -> Vector3:
	return p_b * k + Vector3(off.x * (-1.0 if k.x < 0.0 else 1.0), off.y, off.z)

## The socket's global point.
static func socket_point(rec: Dictionary, ctx: Dictionary) -> Vector3:
	var k: Vector3 = ctx.get("k", Vector3.ONE)
	var xform: Transform3D = ctx.get("xform", Transform3D.IDENTITY)
	return xform * shaped_point(base_point(rec, ctx.get("box", AABB())), k, Vector3(rec.get("off", Vector3.ZERO)))

## Whether the context is mirrored (through the shape factors or the carrier's own transform).
static func mirrored(ctx: Dictionary) -> bool:
	if ctx.has("mirror"): return bool(ctx.mirror)
	var k: Vector3 = ctx.get("k", Vector3.ONE)
	var xform: Transform3D = ctx.get("xform", Transform3D.IDENTITY)
	return (k.x * k.y * k.z < 0.0) != (xform.basis.determinant() < 0.0)

## The socket's orientation; it never inherits scale or mirror (orthonormal, det +1). yaw is degrees
## about +Y from the object's +Z. follow "yaw" keeps it upright; "full" takes the carrier's tilt too
## (swings, rockers).
static func socket_basis(rec: Dictionary, ctx: Dictionary) -> Basis:
	var k: Vector3 = ctx.get("k", Vector3.ONE)
	var xform: Transform3D = ctx.get("xform", Transform3D.IDENTITY)
	var yaw := deg_to_rad(float(rec.get("yaw", 0.0)))
	# A mirror carried by the shape factors flips the local direction; one inside the carrier's own
	# transform flips it through the basis below.
	var sx := -1.0 if k.x < 0.0 else 1.0
	var local := Vector3(sin(yaw) * sx, 0.0, cos(yaw))
	if str(rec.get("follow", "yaw")) == "full":
		var b := xform.basis.orthonormalized()
		var flip := 1.0
		if b.determinant() < 0.0:
			b.x = -b.x
			flip = -1.0
		return b * Basis(UP, yaw * sx * flip)
	var forward := xform.basis * local
	forward.y = 0.0
	if forward.length_squared() < 1e-8:
		forward = xform.basis.z
		forward.y = 0.0
		if forward.length_squared() < 1e-8: forward = Vector3.BACK
	return Basis.looking_at(forward.normalized(), UP, true)

## Yaw (radians about +Y, 0 = facing +Z) of a direction.
static func yaw_of(direction: Vector3) -> float:
	return atan2(direction.x, direction.z)

static func dir_of(yaw: float) -> Vector3:
	return Vector3(sin(yaw), 0.0, cos(yaw))

## Swaps l/r and left/right under a mirror.
static func mirror_side(value: String) -> String:
	match value:
		"l": return "r"
		"r": return "l"
		"left": return "right"
		"right": return "left"
	return value

## The whole resolution: {origin, basis, yaw, params, height, approach[], valid, why, mirror}.
## approach entries are feet points {pos, yaw (radians, facing on arrival), from}.
static func resolve(rec: Dictionary, ctx: Dictionary) -> Dictionary:
	var origin := socket_point(rec, ctx)
	var basis := socket_basis(rec, ctx)
	var mirror := mirrored(ctx)
	var k: Vector3 = ctx.get("k", Vector3.ONE)
	var scale: Vector3 = ctx.get("scale", k.abs())
	var params: Dictionary = (rec.get("params", {}) as Dictionary).duplicate()
	for key in ["hand", "head", "from"]:
		if mirror and params.has(key): params[key] = mirror_side(str(params[key]))
	if params.has("width"): params.width = float(params.width) * absf(scale.x)
	if params.has("depth"): params.depth = float(params.depth) * absf(scale.z)
	if params.has("length"):
		var along_x := str(params.get("head", "l")) in ["l", "r"]
		params.length = float(params.length) * absf(scale.x if along_x else scale.z)
	var floor_y: float = ctx.get("floor_y", NAN)
	if is_nan(floor_y): floor_y = Transform3D(ctx.get("xform", Transform3D.IDENTITY)).origin.y
	var height := origin.y - floor_y
	var out := {"id": str(rec.get("id", "")), "type": str(rec.get("type", "sit")), "variant": str(rec.get("variant", "")),
		"origin": origin, "basis": basis, "yaw": yaw_of(basis.z), "params": params, "height": height, "floor_y": floor_y,
		"mirror": mirror, "source": str(rec.get("source", "authored")), "valid": true, "why": ""}
	var why := validity(out)
	if not why.is_empty():
		out.valid = false
		out.why = why
	out["approach"] = approach_points(rec, ctx, out)
	return out

## Why a resolved socket cannot be offered ("" when it can).
static func validity(resolved: Dictionary) -> String:
	var kind := str(resolved.type)
	if Schema.HEIGHT_RANGE.has(kind):
		var span: Array = Schema.HEIGHT_RANGE[kind]
		var h := float(resolved.height)
		if h < float(span[0]): return "low"
		if h > float(span[1]): return "high"
	if kind == "lie":
		var p: Dictionary = resolved.params
		if float(p.get("length", 2.0)) < 1.3: return "short"
		if float(p.get("width", 0.9)) < 0.5: return "narrow"
	return ""

# ------------------------------------------------------------------ repeat, approach

## A repeated seat (a bench, a sofa) as one record per seat after the shape: n = floor(width/pitch)
## seats spread evenly over the scaled width; ids stay in unmirrored order (seat_0 is the base -x end).
static func expand(rec: Dictionary, k: Vector3) -> Array:
	var rep = rec.get("repeat")
	if not rep is Dictionary: return [rec]
	var axis := str(rep.get("axis", "x"))
	var base_width := float(rec.get("params", {}).get("width", rep.get("width", 1.0)))
	var factor := absf(k.x if axis == "x" else k.z)
	var width := base_width * factor
	var pitch := maxf(0.2, float(rep.get("pitch", 0.55)))
	if width < float(rep.get("min_width", 0.45)): return []
	var count := maxi(1, int(floor(width / pitch + 0.0001)))
	var out: Array = []
	var stem := str(rec.get("id", "seat")).trim_suffix("_0")
	for i in count:
		var one := rec.duplicate(true)
		one.erase("repeat")
		one["repeat"] = {"axis": axis}
		one["rep_dx"] = ((float(i) + 0.5) / count - 0.5) * base_width
		one["id"] = "%s_%d" % [stem, i]
		var params: Dictionary = one.get("params", {})
		params["width"] = base_width / count
		one["params"] = params
		out.append(one)
	return out

## Feet points to stand on before using the socket: the authored ones, or generated ones in front of it
## (and at +-45 degrees and both sides when there is room). Each is {pos, yaw, from}; pos is on the floor.
static func approach_points(rec: Dictionary, ctx: Dictionary, resolved: Dictionary) -> Array:
	var out: Array = []
	var floor_y: float = resolved.floor_y
	var origin: Vector3 = resolved.origin
	var forward: Vector3 = resolved.basis.z
	var side: Vector3 = resolved.basis.x
	for a in rec.get("approach", []):
		var p: Vector3
		if a.has("pos"): p = Transform3D(ctx.get("xform", Transform3D.IDENTITY)) * Vector3(a.pos)
		else:
			var probe := {"at": a.get("at", Vector3(0, 0, 0.5)), "off": a.get("off", Vector3.ZERO)}
			p = socket_point(probe, ctx)
		p.y = floor_y
		var turn := deg_to_rad(float(a.get("yaw", 180.0))) * (-1.0 if resolved.mirror else 1.0)
		var from := str(a.get("from", "front"))
		out.append({"pos": p, "yaw": wrapf(float(resolved.yaw) + turn, -PI, PI), "from": mirror_side(from) if resolved.mirror else from})
	if not out.is_empty(): return out
	var kind := str(resolved.type)
	var depth := float(resolved.params.get("depth", 0.45))
	var width := float(resolved.params.get("width", 0.5))
	var reach := clampf(depth + 0.35, 0.35, 0.70)
	if kind == "lie": reach = clampf(width * 0.5 + 0.42, 0.55, 0.95)
	elif kind == "sit_ground": reach = 0.55
	var flat := Vector3(origin.x, floor_y, origin.z)
	var toward := yaw_of(-forward)
	out.append({"pos": flat + forward * reach, "yaw": toward, "from": "front"})
	if kind != "lie":
		for turn in [deg_to_rad(45.0), deg_to_rad(-45.0)]:
			var d := forward.rotated(UP, turn)
			out.append({"pos": flat + d * reach, "yaw": yaw_of(-d), "from": "front_l" if turn > 0 else "front_r"})
	var lateral := width * 0.5 + 0.45
	out.append({"pos": flat + side * lateral + forward * 0.12, "yaw": yaw_of(-side), "from": "left"})
	out.append({"pos": flat - side * lateral + forward * 0.12, "yaw": yaw_of(side), "from": "right"})
	return out

## Approach candidates best first: a free spot with a clear straight path, then the closest, then the
## one needing the least turn. free/clear are injected (physics in the game, plain lambdas in tests).
static func rank_approach(points: Array, actor_pos: Vector3, actor_yaw: float, free: Callable = Callable(), clear: Callable = Callable()) -> Array:
	var scored: Array = []
	for p in points:
		var ok_spot := true if not free.is_valid() else bool(free.call(p.pos))
		var ok_path := true if not clear.is_valid() else bool(clear.call(actor_pos, p.pos))
		var flat := Vector2(p.pos.x - actor_pos.x, p.pos.z - actor_pos.z)
		var turn := absf(angle_difference(actor_yaw, float(p.yaw)))
		var score := (0.0 if ok_spot else 1000.0) + (0.0 if ok_path else 50.0) + flat.length() + 0.15 * turn
		var entry: Dictionary = p.duplicate()
		entry["score"] = score
		entry["free"] = ok_spot
		entry["clear"] = ok_path
		scored.append(entry)
	scored.sort_custom(func(a, b): return float(a.score) < float(b.score))
	return scored

# ------------------------------------------------------------------ the body on the socket

## Where the body root goes so that a character socket (contact_local: x left, y up, z forward, in
## the body frame at the hold pose) lands on the object socket point, the body facing `yaw`.
static func hold_root(point: Vector3, yaw: float, contact_local: Vector3) -> Vector3:
	return point - Basis(UP, yaw) * contact_local

## ALIGN's length: a short slide plus the turn, 0.15-0.40 s.
static func align_duration(distance: float, turn: float) -> float:
	return clampf(distance / 0.9 + absf(turn) / 4.5, 0.15, 0.40)

## Procedural ENTER/EXIT lengths (s).
const ENTER_SECONDS := {"sit": 0.55, "sit_low": 0.5, "perch": 0.5, "sit_ground": 0.6, "lie_sit": 0.5, "lie": 0.7}
const EXIT_SECONDS := {"sit": 0.5, "sit_low": 0.5, "perch": 0.45, "sit_ground": 0.6, "lie": 0.5, "lie_sit": 0.4}

static func smooth(edge0: float, edge1: float, x: float) -> float:
	return smoothstep(edge0, edge1, x)

## The procedural "virtual clip" (no asset, R = I): the feet point A to the hold root H. Across in
## 0.10-0.85 of the time, down in 0.25-1.0, so the knees bend before the body drops.
static func enter_curve(u: float, a: Vector3, h: Vector3) -> Vector3:
	var s_xz := smoothstep(0.10, 0.85, u)
	var s_y := smoothstep(0.25, 1.0, u)
	return Vector3(lerpf(a.x, h.x, s_xz), lerpf(a.y, h.y, s_y), lerpf(a.z, h.z, s_xz))

## Its mirror image back to the exit feet point X: up first (0-0.75), across in 0.15-0.90.
static func exit_curve(u: float, h: Vector3, x: Vector3) -> Vector3:
	return enter_curve(1.0 - u, x, h)

## Pose-layer weight over ENTER (0 -> 1 by 90 %) and over EXIT (1 -> 0 after the first 10 %).
static func enter_weight(u: float) -> float:
	return smoothstep(0.0, 0.9, u)

static func exit_weight(u: float) -> float:
	return smoothstep(0.0, 0.9, 1.0 - u)

## Turns `from` toward `to` by at most rate*delta (radians).
static func turn_toward(from: float, to: float, rate: float, delta: float) -> float:
	var gap := angle_difference(from, to)
	var limit := rate * delta
	return from + clampf(gap, -limit, limit)

# ------------------------------------------------------------------ clip warping (external clips)

## Drops y and keeps only the yaw of a transform.
static func flat(t: Transform3D) -> Transform3D:
	var f := t.basis.z
	f.y = 0.0
	var yaw := atan2(f.x, f.z) if f.length_squared() > 1e-10 else 0.0
	return Transform3D(Basis(UP, yaw), Vector3(t.origin.x, 0.0, t.origin.z))

## The planar residual a clip must be bent by: W0 = flat(S)*flat(C)^-1 puts the clip's socket_ref C on
## the socket S; E = A0^-1*W0 relative to the root at ENTER start. {E, W0, xz, yaw, ok, clamped}.
static func residual(a0: Transform3D, s: Transform3D, c: Transform3D) -> Dictionary:
	var w0 := flat(s) * flat(c).affine_inverse()
	var e := flat(a0).affine_inverse() * w0
	var xz := Vector2(e.origin.x, e.origin.z).length()
	var yaw := atan2(e.basis.z.x, e.basis.z.z)
	var ok := xz <= WARP_XZ + 1e-6 and absf(yaw) <= WARP_YAW + 1e-6
	var clamped := e
	if not ok:
		var scale := minf(1.0, WARP_XZ / maxf(xz, 1e-6))
		var y := clampf(yaw, -WARP_YAW, WARP_YAW)
		clamped = Transform3D(Basis(UP, y), Vector3(e.origin.x * scale, 0.0, e.origin.z * scale))
	return {"E": e, "W0": w0, "xz": xz, "yaw": yaw, "ok": ok, "clamped": clamped}

## alpha(t): 0 before warp_begin, 1 from contact on, smooth (zero slope at both ends) between.
static func alpha(t: float, tb: float, tc: float) -> float:
	if tc <= tb: return 1.0 if t >= tc else 0.0
	return smoothstep(0.0, 1.0, clampf((t - tb) / (tc - tb), 0.0, 1.0))

## lerp_T(I, E, a): partial planar transform (position and yaw).
static func partial(e: Transform3D, a: float) -> Transform3D:
	var yaw := atan2(e.basis.z.x, e.basis.z.z)
	return Transform3D(Basis(UP, yaw * a), e.origin * a)

## Root(t) = A0 * lerp_T(I, E, alpha(t)) * R(t): at contact and after, exactly W0*R(t).
static func warped_root(a0: Transform3D, e: Transform3D, r_t: Transform3D, t: float, tb: float, tc: float) -> Transform3D:
	return a0 * partial(e, alpha(t, tb, tc)) * r_t

## The vertical warp: {dh, clamped, ok} where dh = (seat height) - (clip reference height).
static func vertical(socket_y: float, floor_y: float, h_ref: float, limit := WARP_LIMIT) -> Dictionary:
	var dh := (socket_y - floor_y) - h_ref
	return {"dh": dh, "clamped": clampf(dh, -limit, limit), "ok": absf(dh) <= limit + 1e-6}

## The resting variant for a seat height: sit_low under 0.38 m, perch over 0.65 m, sit_ground under 0.15.
static func sit_variant(height: float) -> String:
	if height < 0.15: return "sit_ground"
	if height < 0.38: return "sit_low"
	if height > 0.65: return "perch"
	return "sit"

# ------------------------------------------------------------------ the legs (planar two-bone)

## Thigh and knee angles (radians about the body's sideways axis; + swings the lower end forward) that
## put an ankle `forward` metres ahead of the hip and `drop` metres below it, knee in front. Returns
## Vector2(thigh, knee) with knee <= 0 (a bend); the reach is clamped to what the leg can do.
static func leg_angles(thigh: float, shin: float, forward: float, drop: float) -> Vector2:
	var d := sqrt(forward * forward + drop * drop)
	d = clampf(d, absf(thigh - shin) + 0.005, thigh + shin - 0.002)
	var phi := atan2(forward, drop)
	var at_hip := acos(clampf((thigh * thigh + d * d - shin * shin) / (2.0 * thigh * d), -1.0, 1.0))
	var at_knee := acos(clampf((thigh * thigh + shin * shin - d * d) / (2.0 * thigh * shin), -1.0, 1.0))
	return Vector2(phi + at_hip, -(PI - at_knee))
