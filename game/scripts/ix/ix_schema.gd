extends RefCounted
## Villagen Interaction Socket Standard v1 (ISS-1): the closed lists, the clip-name grammar and the
## socket record (docs/design/INTERACTION_SOCKETS.md, docs/design/ISS1_KO.md).
##
## A socket is a point on an object (or a character) with a direction and a type. Objects say where
## you sit, lie, use, grip or pass; characters say which body point meets it (seat_contact on a
## seat, pelvis_lie on a bed). Everything here is data and pure functions: no nodes, no physics.
##
## Frames: metres, seconds, radians (degrees only where a field ends in _deg or is called yaw).
## +Y is up. An object's front is +Z and its origin is the centre of its footprint on the floor.
## A socket's +Z is where the user's chest faces while using it (out of a chair, into a counter).

const VERSION := 1

## Socket types (a new type means a schema bump).
const TYPES := ["sit", "perch", "sit_ground", "lie", "stand_use", "reach", "grip", "look_at", "passage", "place", "talk"]
## The resting types the interaction driver plays in v1.
const REST_TYPES := ["sit", "perch", "sit_ground", "lie"]
## Contact heights above the floor (m) per resting type; outside them a socket is not offered.
const HEIGHT_RANGE := {"sit": [0.25, 0.68], "perch": [0.65, 1.10], "sit_ground": [-0.05, 0.15], "lie": [0.10, 0.95]}
## The character socket that meets each object socket type.
const ALIGNS := {"sit": "seat_contact", "perch": "seat_contact", "sit_ground": "seat_contact", "lie": "pelvis_lie",
	"stand_use": "root", "reach": "root", "grip": "grip_r", "look_at": "eyes", "passage": "root", "place": "hold_front", "talk": "root"}
## Clip family per socket type (external animation contract).
const FAMILY_OF := {"sit": "sit", "perch": "perch", "sit_ground": "sitg", "lie": "lie", "stand_use": "use", "reach": "reach",
	"passage": "door", "place": "place", "talk": "talk"}
const SIT_VARIANTS := ["chair", "stool", "bench", "sofa", "armchair", "throne", "swing", "rocker", "saddle"]
const LIE_VARIANTS := ["bed", "sofa", "lounger", "hammock", "bathtub", "mat"]
const SOURCES := ["authored", "server", "derived", "bbox"]

## Character sockets (ix_rig.gd SOCKETS gives their bones).
const CHARACTER_SOCKETS := ["root", "seat_contact", "pelvis_lie", "sole_l", "sole_r", "grip_r", "grip_l", "pinch_r", "pinch_l",
	"hold_front", "back", "hip_r", "hip_l", "eyes", "mouth", "head_top", "overhead"]

## Clip names: family_variant_phase[_qualifier].
const FAMILIES := ["sit", "perch", "sitg", "lie", "use", "reach", "crouch", "door", "talk", "give", "take", "carry", "tool", "act", "emote", "place"]
const PHASES := ["enter", "hold", "exit", "act", "fidget", "react"]
const QUALIFIERS := ["l90", "r90", "b180", "headl", "headr", "hr", "hl", "a", "b"]
## Markers a clip may carry (Animation.add_marker); events go in meta, not in markers.
const MARKERS := ["warp_begin", "contact", "settled", "release", "warp_end", "exit_ok", "interrupt_from", "grip_on", "grip_off",
	"handover", "loop_in", "loop_out", "foot_l_plant", "foot_r_plant"]
## Godot's scene importer treats these last tokens as node suffixes or loop flags (N1).
const BANNED_LAST := ["loop", "cycle", "col", "colonly", "convcol", "convcolonly", "navmesh", "rigid", "vehicle", "wheel", "occ", "occonly", "noimp"]
const NAME_LIMIT := 48

## Reference dimensions of the animation kit (m): where an external clip's contact was authored.
const REFERENCE := {"chair": 0.45, "bench": 0.45, "sofa": 0.42, "stool_low": 0.30, "bar_stool": 0.72, "ground": 0.0,
	"bed_top": 0.50, "bed_length": 2.0, "bed_width": 0.9, "hammock": 1.0, "sunbed": 0.35, "counter": 0.90, "desk": 0.75,
	"shelf": 1.40, "planter": 0.25, "door_handle": 1.0, "talk": 1.1}

static var _name_rx: RegEx

## N1: lower-case words joined by "_", at most six words and 48 characters; the last word is never an
## importer suffix, and a last word ending in a digit must be one of the qualifiers (l90, r90, b180).
static func valid_name(name: String) -> bool:
	if name.length() > NAME_LIMIT or name.is_empty(): return false
	if _name_rx == null:
		_name_rx = RegEx.new()
		_name_rx.compile("^[a-z][a-z0-9]*(_[a-z0-9]+){0,5}$")
	if _name_rx.search(name) == null: return false
	var words := name.split("_")
	var last := words[words.size() - 1]
	if last in BANNED_LAST: return false
	var stripped := last.rstrip("0123456789")
	if stripped != last:
		if not last in QUALIFIERS: return false
	if stripped in BANNED_LAST: return false
	return true

## {family, variant, phase, qualifiers, ok, why} of a clip name (meta is the truth; the name helps people).
static func parse_clip(name: String) -> Dictionary:
	var out := {"family": "", "variant": "", "phase": "", "qualifiers": [], "ok": false, "why": ""}
	if not valid_name(name):
		out.why = "name"
		return out
	var words := Array(name.split("_"))
	if words.size() < 3:
		out.why = "short"
		return out
	if not words[0] in FAMILIES:
		out.why = "family"
		return out
	out.family = words[0]
	out.variant = words[1]
	var at := 2
	while at < words.size() and not words[at] in PHASES: at += 1
	if at >= words.size():
		out.why = "phase"
		return out
	if at > 2: out.variant = "_".join(words.slice(1, at))
	out.phase = words[at]
	for q in words.slice(at + 1):
		if not q in QUALIFIERS:
			out.why = "qualifier"
			return out
		out.qualifiers.append(q)
	out.ok = true
	return out

## A socket record with every field present (the same dictionary in consts, server JSON and debug).
static func normalize(rec: Dictionary) -> Dictionary:
	var out := {"id": str(rec.get("id", "seat_0")), "type": str(rec.get("type", "sit")), "variant": str(rec.get("variant", "")),
		"carrier": str(rec.get("carrier", "")), "at": _vec(rec.get("at", [0.0, 1.0, 0.0])), "off": _vec(rec.get("off", [0.0, 0.0, 0.0])),
		"yaw": float(rec.get("yaw", 0.0)), "snap": bool(rec.get("snap", true)), "params": (rec.get("params", {}) as Dictionary).duplicate(),
		"approach": [], "exit": rec.get("exit", "approach"), "cap": int(rec.get("cap", 1)), "group": str(rec.get("group", "")),
		"repeat": rec.get("repeat", null), "source": str(rec.get("source", "authored")), "follow": str(rec.get("follow", "yaw"))}
	if rec.has("pos"): out["pos"] = _vec(rec.pos)
	for a in rec.get("approach", []):
		var entry := {"yaw": float(a.get("yaw", 180.0)), "from": str(a.get("from", "front")), "off": _vec(a.get("off", [0.0, 0.0, 0.0]))}
		if a.has("pos"): entry["pos"] = _vec(a.pos)
		else: entry["at"] = _vec(a.get("at", [0.0, 0.0, 0.5]))
		out.approach.append(entry)
	return out

## What is wrong with a record ([] when it is fine).
static func problems(rec: Dictionary) -> Array:
	var out: Array = []
	var id := str(rec.get("id", ""))
	if id.is_empty() or id.length() > 32 or not id.is_valid_ascii_identifier() or id.to_lower() != id: out.append("id")
	if not str(rec.get("type", "")) in TYPES: out.append("type")
	if not str(rec.get("source", "authored")) in SOURCES: out.append("source")
	var at = rec.get("at", [0, 1, 0])
	if at is Vector3: at = [at.x, at.y, at.z]
	if not rec.has("pos") and (absf(float(at[0])) > 0.5001 or absf(float(at[2])) > 0.5001 or float(at[1]) < -0.0001 or float(at[1]) > 1.0001): out.append("at")
	if str(rec.get("follow", "yaw")) not in ["yaw", "full"]: out.append("follow")
	return out

static func _vec(value) -> Vector3:
	if value is Vector3: return value
	if value is Array and value.size() >= 3: return Vector3(float(value[0]), float(value[1]), float(value[2]))
	return Vector3.ZERO
