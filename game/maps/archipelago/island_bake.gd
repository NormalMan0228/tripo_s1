extends RefCounted
## The archipelago's generated data (game/maps/archipelago/generated/, git-ignored), made by
## tools/bake_archipelago.gd from the map's inputs, and whether it still matches them.
##
## collision.res  every collider the build makes from a render mesh, as simplified faces
##                (meshoptimizer, at most EPSILON off the render mesh) in chunks of at most
##                CHUNK_TRIS triangles: one cheap shape a frame instead of a 30-130 ms trimesh.
## island.scn     the unchanging part of the map as the build leaves it (terrain with its levelled
##                ground pads and materials, buildings, bridges, props placed and fitted, rock walls,
##                ramps, roads), GLB models referenced, not copied. The colliders with simplified faces
##                are left out (their bodies stay) and listed in the root's "baked_colliders" meta:
##                read on a worker thread, a scene's shapes would all reach the physics server in one
##                frame; they are made a chunk a frame after it is in (Archipelago.build).
## manifest.json  {"format", "engine", "key", "stamp", "content_key", ...}: `key` hashes the inputs
##                that decide the build (KEY_FILES: layouts and the scripts that build; the engine
##                version); `stamp` lists every map asset's modification time, so a source run
##                notices a re-ported or reimported asset without hashing 1.8 GB;
##                `content_key` (tools, tests, packaging) adds the assets' MD5s.
## A missing or stale bake is never used: the map then builds as before (render-mesh trimeshes).
## Exported games cannot read their scripts' text: there the bake counts when it is there for this
## format and engine (packaging re-bakes or refuses a stale one: tools/bake_archipelago.py).
const DIR := "res://maps/archipelago/generated/"
const MANIFEST := DIR+"manifest.json"
const COLLISION := DIR+"collision.res"
const ISLAND := DIR+"island.scn"
const FORMAT := 3
## Simplification error (metres in the world): the ground, then everything else.
const GROUND_EPSILON := 0.01
const EPSILON := 0.02
## Buildings: up to WALK_ZONE metres above their lowest point (steps, porches, floors, doorways)
## the faces stay within WALK_ZONE_EPSILON (0: as they are); walls and roofs above within EPSILON.
const WALK_ZONE := 3.6
const WALK_ZONE_EPSILON := 0.003
## Bridges and this prop (the piers, walked on like bridges) keep WALK_ZONE_EPSILON everywhere.
const WALKABLE_PROP := "20_pier"
const CHUNK_TRIS := 6000
const ASSETS := "res://maps/archipelago/assets/"
## The files whose content decides what the map build makes.
const KEY_FILES := [
	"res://maps/archipelago/building_placements.json", "res://maps/archipelago/environment_layout.json",
	"res://maps/archipelago/archipelago.gd", "res://maps/archipelago/building_layout.gd",
	"res://maps/archipelago/environment_layout.gd", "res://maps/archipelago/island_bake.gd",
	"res://scripts/roads.gd", "res://scripts/town.gd", "res://scripts/load_pace.gd", "res://scripts/art.gd",
]
## --no-bake: build the map as if there were no generated data (tests compare both).
static var disabled := "--no-bake" in OS.get_cmdline_user_args()
## --no-island: build at runtime (with the generated collision) instead of loading the baked island.
static var island_disabled := "--no-island" in OS.get_cmdline_user_args()
static var _checked := false
static var _fresh := false
static var _collision: Dictionary = {}
## Running from an exported pack (scripts there are compiled and their text is not readable, the
## assets' sources are not there): the release templates, or the editor binary with --main-pack.
static var exported := OS.has_feature("template") or not FileAccess.file_exists("res://maps/archipelago/archipelago.gd")

## The engine the bake was made with: version and source commit, not the build's name (the game's
## IME-patched export templates call themselves "custom_build", the editor "official").
static func engine() -> String:
	var info := Engine.get_version_info()
	return "%d.%d.%d.%s.%s" % [info.major, info.minor, info.patch, info.status, info.hash]

## The inputs' key: layouts, build scripts, engine version and format.
static func key() -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(("%d|%s|" % [FORMAT, engine()]).to_utf8_buffer())
	for path: String in KEY_FILES:
		var text := FileAccess.get_file_as_string(path).replace("\r\n", "\n")
		context.update((path+"|").to_utf8_buffer())
		if not text.is_empty(): context.update(text.to_utf8_buffer())
	return context.finish().hex_encode()

## Every map asset: GLB and PNG by modification time, .import by its text (source runs only; empty
## in exports): a re-ported asset or changed import settings make the bake stale.
static func stamp() -> Dictionary:
	var out := {}
	if exported: return out
	var dirs: Array[String] = [ASSETS]
	while not dirs.is_empty():
		var dir: String = dirs.pop_back()
		for sub in DirAccess.get_directories_at(dir): dirs.append(dir+sub+"/")
		for file in DirAccess.get_files_at(dir):
			if file.get_extension() == "import":
				# Godot saves .import files again on any reimport (here or in another checkout sharing
				# the folder) without changing them: their text counts, not their time (small files).
				out[(dir+file).trim_prefix(ASSETS)] = "md5:" + FileAccess.get_file_as_string(dir+file).replace("\r\n", "\n").md5_text()
			elif file.get_extension() in ["glb", "png"]:
				out[(dir+file).trim_prefix(ASSETS)] = str(FileAccess.get_modified_time(dir+file))
	return out

## The assets' content (MD5 of every GLB, PNG and .import): for tools and tests, not at runtime.
static func content_key() -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(key().to_utf8_buffer())
	var files := stamp().keys()
	files.sort()
	for file: String in files:
		context.update((file+"|"+FileAccess.get_md5(ASSETS+file)+"|").to_utf8_buffer())
	return context.finish().hex_encode()

static func manifest() -> Dictionary:
	if not FileAccess.file_exists(MANIFEST): return {}
	var data = JSON.parse_string(FileAccess.get_file_as_string(MANIFEST))
	return data if data is Dictionary else {}

## Why the generated data cannot be used ("" when it can): missing, format, key or assets.
static func problem() -> String:
	var data := manifest()
	if data.is_empty(): return "missing"
	if int(data.get("format", 0)) != FORMAT: return "format"
	if String(data.get("engine", "")) != engine(): return "engine"
	if exported: return ""
	if String(data.get("key", "")) != key(): return "key"
	if data.get("stamp", {}) != stamp(): return "assets"
	return ""

## The generated data matches the inputs (checked once per run) and is not switched off.
static func fresh() -> bool:
	if disabled: return false
	if not _checked:
		_checked = true
		var why := problem()
		_fresh = why.is_empty()
		if not _fresh and why != "missing": push_warning("Archipelago bake is stale (%s): the map builds without it; run tools/bake_archipelago.py" % why)
	return _fresh

## The baked island can be used: fresh, present, and not switched off.
static func island_ready() -> bool:
	return not island_disabled and fresh() and ResourceLoader.exists(ISLAND)

## The simplified collision chunks for a collider key (see collider_key), or [] for none.
static func collision_chunks(collider: String) -> Array:
	if not fresh(): return []
	if _collision.is_empty() and ResourceLoader.exists(COLLISION):
		# Read on a worker thread when the build asked for it early (Archipelago.resource_paths).
		var library := preload("res://scripts/load_pace.gd").take(COLLISION)
		_collision = library.get_meta("chunks", {}) if library else {}
		if _collision.is_empty(): _collision = {"": []}
	return _collision.get(collider, [])

## The key a collider is stored under: the mesh's path below the map ("prop:<id>:<path>" for the
## shapes props share between their instances).
static func collider_key(map: Node, mesh: Node, shared_prop := "") -> String:
	if shared_prop.is_empty(): return String(map.get_path_to(mesh))
	var prop := mesh
	while prop.get_parent() != null and not String(prop.name).begins_with(shared_prop): prop = prop.get_parent()
	return "prop:"+shared_prop+":"+String(prop.get_path_to(mesh))

## The map is built: its shapes hold their own copies of the faces, so the library can go.
static func drop_collision() -> void:
	_collision = {}

## Forget what was checked and loaded (the bake tool rewrites the data while running).
static func reset() -> void:
	_checked = false
	_fresh = false
	_collision = {}
