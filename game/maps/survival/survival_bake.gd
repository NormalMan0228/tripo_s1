extends RefCounted
## The survival maps' baked static data (game/maps/survival/generated/survival_<map>.res, git-ignored),
## made by tools/bake_survival.gd, and whether it still matches the inputs.
##
## Each file is a plain Resource whose metadata holds what the build makes the same way for every run
## of the map: the ground mesh (heights, normals, splat colours on the same 0.5 m / 2 m grid, float,
## one mesh: byte for byte the mesh the build makes), the water sheets ("Pond", "Lake"), and the rim
## block of the scatter (its instances per batch key and the rng state after it). Materials, hazards,
## features, labels, particles, the inside scatter (it keeps clear of the run's resource nodes), the
## grass (it draws from the rng after the inside scatter), fences, resources and monsters are built at
## runtime every time.
##
## metas: format, engine, key, map_id, layout_sig, ground (ArrayMesh), water ([[name, ArrayMesh]]),
##        rim ([[key, id, shadow, lod, PackedFloat32Array]]), rng_after_rim (int).
##
## Fresh means: same FORMAT, engine, KEY_FILES text and set of prop models present (a missing prop
## changes how many random numbers the placement draws) as when it was baked. A stale or missing bake
## is never used: the map then builds as before. A run whose obstacles or hazards are not the layout's
## (a run saved before the server re-synced its layout) does not match layout_sig and builds as before.
## Exported games cannot read their scripts' text: there the bake counts when it is there for this
## format and engine (packaging re-bakes or refuses a stale one: tools/bake_survival.py).
const DIR := "res://maps/survival/generated/"
const FORMAT := 1
const MAPS := ["forest","quarry","frost"]
## The files whose content decides what the bake holds.
const KEY_FILES := ["res://maps/survival/layouts.json","res://maps/survival/survival_map.gd","res://maps/survival/survival_bake.gd"]
const MAP_SCRIPT := "res://maps/survival/survival_map.gd"
## --no-survival-bake: build the maps as if there were no baked data (tests compare both).
static var disabled := "--no-survival-bake" in OS.get_cmdline_user_args()
## Running from an exported pack (scripts there are compiled and their text is not readable): the
## release templates, or the editor binary with --main-pack.
static var exported := OS.has_feature("template") or not FileAccess.file_exists(MAP_SCRIPT)
## Tools: read the files past the resource cache (the bake rewrites them while running).
static var uncached := false
static var _problems := {}
static var _key := ""

static func path(map_id: String) -> String:
	return DIR+"survival_%s.res" % map_id

## The engine the bake was made with: version and source commit (as island_bake.gd).
static func engine() -> String:
	var info := Engine.get_version_info()
	return "%d.%d.%d.%s.%s" % [info.major, info.minor, info.patch, info.status, info.hash]

## The inputs' key: format, engine, KEY_FILES and which prop models exist (per map, in order).
static func key() -> String:
	if not _key.is_empty(): return _key
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(("%d|%s|" % [FORMAT, engine()]).to_utf8_buffer())
	for file: String in KEY_FILES:
		var text := FileAccess.get_file_as_string(file).replace("\r\n", "\n")
		context.update((file+"|").to_utf8_buffer())
		if not text.is_empty(): context.update(text.to_utf8_buffer())
	var map_script: GDScript = load(MAP_SCRIPT)
	var placed: Dictionary = map_script.MAP_PROPS
	for map_id in MAPS:
		var present := []
		for id in placed[map_id]:
			present.append("%s=%s" % [id, ResourceLoader.exists(map_script.prop_paths(id)[0])])
		context.update(("%s:%s|" % [map_id, ",".join(present)]).to_utf8_buffer())
	_key = context.finish().hex_encode()
	return _key

## The run's obstacles and hazards (the layout's when the run has none) and the play square: the
## ground's splat colours and the random numbers drawn before the rim block depend on them.
static func layout_sig(state: Dictionary, spec: Dictionary, bounds: float) -> String:
	var layout := [state.get("obstacles", spec.obstacles), state.get("hazards", spec.hazards), bounds]
	return JSON.stringify(layout, "", true, true).md5_text()

## Why the map's bake cannot be used ("" when it can): missing, format, engine, map or key. Checked
## once per run of the game; a stale bake warns once.
static func problem(map_id: String) -> String:
	if _problems.has(map_id): return _problems[map_id]
	var why := _problem(map_id)
	_problems[map_id] = why
	if why != "" and why != "missing":
		push_warning("Survival bake for %s is stale (%s): the map builds without it; run tools/bake_survival.py" % [map_id, why])
	return why

static func _problem(map_id: String) -> String:
	var data := _resource(map_id)
	if data == null: return "missing"
	if int(data.get_meta("format", 0)) != FORMAT: return "format"
	if String(data.get_meta("engine", "")) != engine(): return "engine"
	if String(data.get_meta("map_id", "")) != map_id: return "map"
	if exported: return ""
	if String(data.get_meta("key", "")) != key(): return "key"
	return ""

static func _resource(map_id: String) -> Resource:
	var file := path(map_id)
	if not ResourceLoader.exists(file): return null
	if uncached: return ResourceLoader.load(file, "", ResourceLoader.CACHE_MODE_IGNORE)
	# Read on a worker thread when the expedition began (survival_map.gd resource_paths).
	return preload("res://scripts/load_pace.gd").take(file)

## The map's baked data for this run, or null when it is switched off, missing, stale or made for
## another layout (the map then builds everything itself).
static func data(map_id: String, state: Dictionary, spec: Dictionary, bounds: float) -> Resource:
	if disabled or problem(map_id) != "": return null
	var baked := _resource(map_id)
	if baked == null or String(baked.get_meta("layout_sig", "")) != layout_sig(state, spec, bounds): return null
	return baked

## Forget what was checked (the bake tool rewrites the data while running).
static func reset() -> void:
	_problems = {}
	_key = ""
