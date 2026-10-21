extends RefCounted
## One look for the player's character everywhere.
##
## The description is the server profile (server/models.py Avatar) and its version: the wardrobe
## saves it (/v1/profile), /v1/me, /v1/studio and the sign-in answer carry it, and every presence
## record (village, visits, the home, co-op expeditions) carries each player's look and
## avatar_version. player.gd is the one builder. The village walker, other players, the room
## walker and visitors, the wardrobe preview and the HUD medallion (avatar_portrait.gd) all go
## through walker() and wear(): a body is built in its look from the first frame, and rebuilt only
## when the version (or, without one, the look itself) changes, never on every poll.

const Fx = preload("res://scripts/fx.gd")
const PlayerScript = preload("res://scripts/player.gd")
const Roster = preload("res://scripts/character_roster.gd")

## Mirrors server/models.py Avatar. A missing field means the default, so {} and the full
## default record are the same look and never rebuild a body.
const DEFAULTS := {"character":"f1","hair":"#d36629","coat":"#d8ad2b","pants":"#347272","boots":"#ece9e5","skin":"#d09b87","headwear":"none","backpack":true,"accent":"#844330"}
## Fields and values only a server with avatar_v2 (/health; docs/design/AVATAR8_API_KO.md) takes.
const V2_ONLY := ["accent"]
const OLD_SKINS := ["#e4b587","#f0cdb1","#bc865c","#895b43","#604431"]
const PARTS := ["hair","coat","pants","boots","skin"]

## The full look: defaults filled in, unknown fields dropped.
static func normalize(value) -> Dictionary:
	var look: Dictionary = DEFAULTS.duplicate(true)
	if not value is Dictionary: return look
	for key in DEFAULTS:
		if not value.has(key): continue
		var field = value[key]
		if key=="backpack":
			if field is bool: look[key]=field
		elif field is String and not field.is_empty():
			look[key]=field
	look.character=Roster.canonical(str(look.character))
	return look

## The look a body wears: the saved look with a model it can show (model_id).
static func shown(value) -> Dictionary:
	var look := normalize(value)
	look.character = model_id(str(look.character))
	return look

## Old saved/presence ids become a modern character, never an old model.
static func model_id(id: String) -> String:
	return Roster.canonical(id)

## The look as the server takes it: an older server (no avatar_v2) gets no accent, the travel cap
## for the straw hat and the nearest of its five skins.
static func for_server(value, v2: bool) -> Dictionary:
	var look := normalize(value)
	if v2: return look
	for key in V2_ONLY: look.erase(key)
	if look.headwear == "straw": look.headwear = "cap"
	# An older server knows only its four: a new character goes as the old one of its kind.
	var id := str(look.character)
	if id.length() == 2 and id[0] in ["m", "f"] and id[1].is_valid_int(): look.character = "explorer" if id[0] == "m" else "explorer_b"
	if not look.skin in OLD_SKINS:
		var want := Color(str(look.skin))
		var best: String = OLD_SKINS[0]
		for skin in OLD_SKINS:
			var c := Color(skin)
			if Vector3(c.r - want.r, c.g - want.g, c.b - want.b).length() < Vector3(Color(best).r - want.r, Color(best).g - want.g, Color(best).b - want.b).length(): best = skin
		look.skin = best
	return look

## A short key for comparing looks (field order does not matter).
static func signature(value) -> String:
	var look := normalize(value)
	var fields := PackedStringArray()
	for key in DEFAULTS: fields.append(str(look[key]))
	return "|".join(fields)

## A walker (player.gd) built in this look from its first frame. Callers set position and
## controls; the look is applied in _ready, so the default character never shows first.
## The modern roster plus the shared resident rig/motion used by the town's NPCs.
static func resource_paths() -> Array:
	return Roster.IDS.map(func(id):return Roster.model_path(id))+["res://assets/explorer_b_wardrobe.glb","res://assets/explorer_b_motion.glb"]

static func walker(look, version := -1) -> CharacterBody3D:
	var body: CharacterBody3D = PlayerScript.new()
	body.avatar = shown(look)
	body.look_version = version
	return body

## Puts a look on a body. With a version (profile version / avatar_version) the check is one
## integer: the version already worn (or an older one, from an answer that was overtaken) returns
## at once. Returns true when the body was rebuilt.
## animate: a changed look in the world arrives with a small hop and a twinkle.
static func wear(body: Node, look, version := -1, animate := false) -> bool:
	if not is_instance_valid(body): return false
	if version>=0 and version<=int(body.look_version): return false
	if version>=0: body.look_version = version
	var changed: bool = body.apply_avatar(shown(look))
	if changed and animate and body.is_inside_tree() and body.get_parent() is Node3D and is_instance_valid(body.visual):
		Fx.squash(body.visual, 0.12, 0.38)
		Fx.burst(body.get_parent(), body.global_position+Vector3(0,1.1,0), "sparkle", 10, Color(0,0,0,0), 0.35)
	return changed

## What a body actually shows, read back from its nodes and materials (not from the look it was
## given): the character model file, the tint on each recoloured part, the hat and the backpack.
## Tests compare this between places.
static func applied(body: Node) -> Dictionary:
	var out := {"model":"", "tints":{}, "headwear":"none", "backpack":false, "builds":0}
	if not is_instance_valid(body) or not is_instance_valid(body.visual): return out
	out.builds = int(body.look_builds)
	var models: Array = body.visual.find_children("*", "", true, false).filter(func(n): return str(n.scene_file_path).ends_with(".glb"))
	if not models.is_empty(): out.model = str(models[0].scene_file_path).get_file().get_basename()
	for mesh in body.visual.find_children("*", "MeshInstance3D", true, false):
		if not mesh.mesh: continue
		for index in mesh.mesh.get_surface_count():
			var source: Material = mesh.mesh.surface_get_material(index)
			if not source: continue
			var part: String = source.resource_name.to_lower().split("__")[0]
			var shown: Material = mesh.get_surface_override_material(index)
			if part=="backpack" and shown is StandardMaterial3D:
				out.backpack = shown.albedo_color.a>0.01
			elif part in PARTS and shown is ShaderMaterial:
				out.tints[part] = "#"+Color(shown.get_shader_parameter("tint")).to_html(false)
	for node in body.visual.find_children("Headwear_*", "", true, false):
		out.headwear = str(node.name).trim_prefix("Headwear_")
	if not body.visual.find_children("Backpack", "", true, false).is_empty(): out.backpack = true
	return out
