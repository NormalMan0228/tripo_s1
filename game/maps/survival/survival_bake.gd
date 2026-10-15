extends RefCounted
## The survival maps' baked static data (game/maps/survival/generated/survival_<map>.res, git-ignored),
## made by tools/bake_survival.gd, and whether it still matches the inputs.
##
## Each file is a plain Resource whose metadata holds what the build makes the same way for every run
## of the map: the ground mesh (heights, normals, splat colours on the same 0.5 m / 2 m grid, float,
## one mesh: byte for byte the mesh the build makes), the water sheets ("Pond", "Lake"), and the rim
## block of the scatter (its instances per batch key and the rng state before and after it). Materials,
## hazards, features, labels, particles, the inside scatter (it keeps clear of the run's resource
## nodes), the grass (it draws from the rng after the inside scatter), fences, resources and monsters
## are built at runtime every time.
##
## metas: format, engine, key, export_key, map_id, layout_sig, ground (ArrayMesh), water ([[name,
##        ArrayMesh]]), rim ([[key, id, shadow, lod, PackedFloat32Array]]), rng_before_rim and
##        rng_after_rim (int), probe and rim_probe (PackedFloat64Array, survival_map.gd bake_probe and
##        rim_probe).
##
## Fresh means, checked by every game that uses it, exported or not:
## - the same FORMAT and engine, and export_key(): layouts.json, the set of prop models present (a
##   missing prop changes how many random numbers the placement draws) and the map script's constants
##   (LOOK, MAP_PROPS, RIM_BLOCK, ...);
## - ground_fits(): the map's ground and water code gives what bake_probe() gave at the bake (heights,
##   normals, splat colours, water sheets at fixed points);
## - rim_fits(), when the scatter comes to the rim: the build's random state is the one the baked rim
##   started from, and a short seeded run of the rim code (rim_probe) queues what it queued at the bake.
## Where the scripts' text is readable (the editor, tools, tests) key() must match too: the text of
## layouts.json, survival_map.gd and survival_bake.gd, so any edit there makes the bake stale.
## An exported game cannot read its scripts' text; the checks above are what it compares instead. An
## edit only inside the rim helpers' bodies that leaves their short run unchanged would pass there;
## the export steps re-bake or refuse a stale bake by key (tools/bake_survival.py).
## A stale or missing bake is never used: the map then builds as before (the rim alone when only the
## rim checks fail). A run whose obstacles or hazards are not the layout's (a run saved before the
## server re-synced its layout) does not match layout_sig and builds as before.
const DIR := "res://maps/survival/generated/"
const FORMAT := 2
const MAPS := ["forest","quarry","frost"]
## The files whose content decides what the bake holds.
const KEY_FILES := ["res://maps/survival/layouts.json","res://maps/survival/survival_map.gd","res://maps/survival/survival_bake.gd"]
const MAP_SCRIPT := "res://maps/survival/survival_map.gd"
## How far a fingerprint value may be off (metres, unit normals and colours): the same engine and
## code give the same values; a change in the code moves some of them much further.
const PROBE_TOLERANCE := 0.0001
## --no-survival-bake: build the maps as if there were no baked data (tests compare both).
static var disabled := "--no-survival-bake" in OS.get_cmdline_user_args()
## Running from an exported pack (scripts there are compiled and their text is not readable): the
## release templates, or the editor binary with --main-pack.
static var exported := OS.has_feature("template") or not FileAccess.file_exists(MAP_SCRIPT)
## Tools: read the files past the resource cache (the bake rewrites them while running).
static var uncached := false
static var _problems := {}
static var _fits := {}
static var _key := ""
static var _export_key := ""

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
	context.update(_present().to_utf8_buffer())
	_key = context.finish().hex_encode()
	return _key

## What an exported game can read of the inputs: format, engine, layouts.json (exported as text), which
## prop models exist and the map script's constants (values, not resources), by name.
static func export_key() -> String:
	if not _export_key.is_empty(): return _export_key
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(("%d|%s|" % [FORMAT, engine()]).to_utf8_buffer())
	context.update(FileAccess.get_file_as_string(KEY_FILES[0]).replace("\r\n", "\n").to_utf8_buffer())
	context.update(_present().to_utf8_buffer())
	var constants := (load(MAP_SCRIPT) as GDScript).get_script_constant_map()
	var names := constants.keys()
	names.sort()
	for constant in names:
		var value = constants[constant]
		if typeof(value) == TYPE_OBJECT: continue
		context.update(("%s=%s|" % [constant, var_to_str(value)]).to_utf8_buffer())
	_export_key = context.finish().hex_encode()
	return _export_key

## Which prop models exist, per map in MAP_PROPS order.
static func _present() -> String:
	var map_script: GDScript = load(MAP_SCRIPT)
	var placed: Dictionary = map_script.MAP_PROPS
	var out := ""
	for map_id in MAPS:
		var present := []
		for id in placed[map_id]:
			present.append("%s=%s" % [id, ResourceLoader.exists(map_script.prop_paths(id)[0])])
		out += "%s:%s|" % [map_id, ",".join(present)]
	return out

## The run's obstacles and hazards (the layout's when the run has none) and the play square: the
## ground's splat colours and the random numbers drawn before the rim block depend on them.
static func layout_sig(state: Dictionary, spec: Dictionary, bounds: float) -> String:
	var layout := [state.get("obstacles", spec.obstacles), state.get("hazards", spec.hazards), bounds]
	return JSON.stringify(layout, "", true, true).md5_text()

## Why the map's bake cannot be used ("" when it can): missing, format, engine, map, export key or
## key. Checked once per run of the game; a stale bake warns once.
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
	if String(data.get_meta("export_key", "")) != export_key(): return "export key"
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

## The map's ground and water code still gives what the bake holds (survival_map.gd bake_probe, at the
## start of the build, before anything is placed). Once per map and script in a run of the game (the
## layout is the bake's: data() checked layout_sig); a mismatch warns once.
static func ground_fits(map: Node, baked: Resource) -> bool:
	var id := "ground|%s|%d" % [map.map_id, map.get_script().get_instance_id()]
	if not _fits.has(id):
		_fits[id] = _same(map.bake_probe(), baked.get_meta("probe", PackedFloat64Array()))
		if not _fits[id]:
			push_warning("Survival bake for %s does not match the map's ground or water code: the map builds without it; run tools/bake_survival.py" % map.map_id)
	return _fits[id]

## The baked rim can stand in for the rim block here: the build's random state is the one the rim
## started from at the bake (the hazards and features before it drew the same numbers), and a short
## seeded run of the rim code queues what it queued then (survival_map.gd rim_probe, once per map and
## script in a run of the game). Otherwise the rim block runs; the baked ground and water stay.
static func rim_fits(map: Node, baked: Resource) -> bool:
	var id := "rim|%s|%d" % [map.map_id, map.get_script().get_instance_id()]
	if int(map.rng.state) != int(baked.get_meta("rng_before_rim", -1)):
		if not _fits.has(id+"|rng"):
			_fits[id+"|rng"] = false
			push_warning("Survival bake for %s: the scatter reaches the rim from another random state; the rim is built here; run tools/bake_survival.py" % map.map_id)
		return false
	if not _fits.has(id):
		_fits[id] = _same(map.rim_probe(), baked.get_meta("rim_probe", PackedFloat64Array()))
		if not _fits[id]:
			push_warning("Survival bake for %s does not match the map's rim code: the rim is built here; run tools/bake_survival.py" % map.map_id)
	return _fits[id]

static func _same(now: PackedFloat64Array, then: PackedFloat64Array) -> bool:
	if now.is_empty() or now.size() != then.size(): return false
	for i in now.size():
		if absf(now[i]-then[i]) > PROBE_TOLERANCE: return false
	return true

## Forget what was checked (the bake tool rewrites the data while running; tests switch `exported`).
static func reset() -> void:
	_problems = {}
	_fits = {}
	_key = ""
	_export_key = ""
