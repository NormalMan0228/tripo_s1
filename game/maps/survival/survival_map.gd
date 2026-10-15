extends Node3D
## Survival expedition maps (솔바람 숲 / 노을 채석장 / 서리빛 분지) built to the island village's
## standard: a sculpted basin terrain (flat, walkable play square; hills, cliffs and shores beyond it)
## with detail-mapped ground, authored landmarks on the server's obstacle circles, Tripo props in
## chunked MultiMeshes (LOD1 when the camera zooms out, no shadows for ground cover), per-map light
## and haze through the stage's time of day (survival_daytime.gd), Tripo resource visuals, and on the
## tutorial its guidance in the world (survival_guide.gd).
##
## Geometry that matters for play is server-authoritative (server/survival_maps.py); the client reads the
## exported copy (layouts.json) for dressing and the run state for obstacles, hazards and resources.
## Decor never stands where the walker can go unless it is foliage or ankle-high debris.
const ROOT := "res://maps/survival/"
const ASSETS := "res://maps/survival/assets/"
const VILLAGE := "res://maps/archipelago/assets/"
const DETAIL := "res://maps/archipelago/assets/v5/"
const PROP_SHADER := preload("res://maps/survival/survival_prop.gdshader")
const GROUND_SHADER := preload("res://maps/survival/survival_ground.gdshader")
const WATER_SHADER := preload("res://maps/survival/survival_water.gdshader")
const HAZARD_SHADER := preload("res://maps/survival/survival_hazard.gdshader")
const GRASS_SHADER := preload("res://maps/survival/survival_grass.gdshader")
const CHUNK := 12.0
## Under the loading card the build is paced over frames and the models load on worker threads.
const LoadPace = preload("res://scripts/load_pace.gd")
const Monster = preload("res://scripts/monster.gd")
## The map's static data baked ahead (ground, water, rim scatter; tools/bake_survival.py).
const SurvivalBake = preload("res://maps/survival/survival_bake.gd")
## The stage's time of day (day_progress as an hour of the village's sky, in this map's colours).
const Daytime = preload("res://maps/survival/survival_daytime.gd")
## The tutorial's goals shown in the world (beacons, sparkles, rings; no words).
const TutorialGuide = preload("res://maps/survival/survival_guide.gd")
const Daylight = preload("res://scripts/daylight.gd")
const LOD_ZOOM := 18.5
const FAR := 64.0
const RESOURCE_KINDS := ["tree","stone","berry","fiber"]

## Per-map look. The colours are the map's noon grade, the *_night values its night grade; the stage's
## time of day (survival_daytime.gd) carries them through morning, golden hour, sunset and evening.
const LOOK := {
	"forest": {
		"turf_low":"4f7d2d","turf_high":"92b145","soil":"6d5435","trail":"bfa275","rock":"8e8f80","accent":"3c6a2a",
		"haze":"a6cdc4","haze_night":"1a2c40","background":"9cc9c2","background_night":"132235",
		"ambient":"f4f8ff","ambient_energy":0.46,"ambient_night":"6f8bbd","ambient_night_energy":0.30,
		"sun":"fff0d2","sun_energy":0.62,"sun_night":"8eaee6","sun_night_energy":0.20,"sun_pitch":-52.0,"sun_yaw":-32.0,
		"grass_low":"5f8e33","grass_high":"b4cf62","snow":0.0,"strata":0.0,
		"rim_north":7.5,"rim_side":4.2,"rim_south":-1.7,"rim_width":11.0,"rim_noise":1.6,"terrace":0.0,
		"water_y":-0.55,"pond_y":-0.14,"water_shallow":"4aa59a","water_deep":"14485a","frozen":0.0,
		"grass":2600,"rim_grass":2000,
	},
	"quarry": {
		"turf_low":"a8835d","turf_high":"c9a57c","soil":"94603f","trail":"cdb48f","rock":"c98a5c","accent":"3e2620",
		"haze":"efbf98","haze_night":"2b2238","background":"f0c49c","background_night":"201a30",
		"ambient":"fff0e2","ambient_energy":0.44,"ambient_night":"7f6fb0","ambient_night_energy":0.30,
		"sun":"ffc58e","sun_energy":0.66,"sun_night":"a493d8","sun_night_energy":0.20,"sun_pitch":-30.0,"sun_yaw":-58.0,
		"grass_low":"9c8a45","grass_high":"e0c06e","snow":0.0,"strata":1.0,
		"rim_north":9.0,"rim_side":7.5,"rim_south":1.6,"rim_width":9.0,"rim_noise":0.8,"terrace":3.0,
		"water_y":-9.0,"pond_y":-9.0,"water_shallow":"4aa59a","water_deep":"14485a","frozen":0.0,
		"grass":1700,"rim_grass":1200,
	},
	"frost": {
		"turf_low":"a9bccb","turf_high":"cfdce6","soil":"7d8a96","trail":"a7b8c6","rock":"858f9c","accent":"9dbbd2",
		"haze":"cfe0ea","haze_night":"17284a","background":"c6dbe6","background_night":"0f1d38",
		"ambient":"cfdcf2","ambient_energy":0.30,"ambient_night":"7193d4","ambient_night_energy":0.30,
		"sun":"fff6ea","sun_energy":0.50,"sun_night":"9fc0f4","sun_night_energy":0.24,"sun_pitch":-40.0,"sun_yaw":-20.0,
		"grass_low":"a89e7c","grass_high":"ddd5bb","snow":1.0,"strata":0.0,
		"rim_north":10.0,"rim_side":5.0,"rim_south":-1.2,"rim_width":12.0,"rim_noise":1.8,"terrace":0.0,
		"water_y":-0.45,"pond_y":-9.0,"water_shallow":"9ec4d6","water_deep":"5f8fb0","frozen":1.0,
		"grass":320,"rim_grass":260,
	},
}

## Prop sources: Tripo survival set (assets/<id>.glb + _lod1) or village props (with their LOD files).
const VILLAGE_PROPS := {
	"tent_green":["environment/tent_green.glb",""],"tent_orange":["environment/tent_orange.glb",""],
	"white_flowers":["environment/white_flowers.glb","prop_lods/42_white_flowers.glb"],
	"yellow_flowers":["environment/yellow_flowers.glb","prop_lods/43_yellow_flowers.glb"],
	"pink_flowers":["environment/pink_flowers.glb","prop_lods/44_pink_flowers.glb"],
	"reeds":["environment/reeds.glb","prop_lods/45_reeds.glb"],
	"lamp":["environment/lamp.glb","prop_lods/27_lamp.glb"],
}
## Village ground cover (~20k triangles each, LODs 1.2k-1.6k): drawn with its LOD by the village's own
## screen-size rule (environment_layout.gd: LOD under 260 px tall, the full mesh again from 300 px),
## which keeps the LOD at every expedition zoom except the closest one on large screens at high detail.
const GROUND_COVER := ["reeds","white_flowers","yellow_flowers","pink_flowers"]
const COVER_LIMITS := Vector2(260,300)
const GameSettings = preload("res://scripts/game_settings.gd")

static var _layout_cache: Dictionary = {}

var map_id := "forest"
var state: Dictionary = {}
var spec: Dictionary = {}
var look: Dictionary = {}
var bounds := 22.0
var noise := FastNoiseLite.new()
var rng := RandomNumberGenerator.new()
var materials: Array[ShaderMaterial] = []
var glow_materials: Array[ShaderMaterial] = []
var props := {}
var batches := {}
var multimeshes: Array[Dictionary] = []
var cover_multimeshes: Array[Dictionary] = []
var low_active := false
var occupied: Array[Vector3] = []
var app: Node
var camera: Camera3D
var env: Environment
var sun: DirectionalLight3D
var night := 0.0
var dusk := 0.0
var daytime := Daytime.new()
## The camp fire's light (main.gd flame), brighter into the evening.
var fire_light: OmniLight3D
var guide: Node3D
var focus := Vector3.ZERO
var follow_particles: Array[Node3D] = []
var adopt_wait := 0.0
## This build's baked data (survival_bake.gd data(): fresh and made for this layout), or null to
## build everything here. tools/bake_survival.gd sets bake_record to collect the rim block.
var baked: Resource = null
var bake_record := false
var rim_record: Array = []
var rng_before_rim := 0
var rng_after_rim := 0
## The rim block came from the bake (survival_bake.gd rim_fits) in this build.
var rim_replayed := false
## The night's creatures: the models (this map's variant) of the species the coming night can bring
## (the run's night_species, server/catalog.py night_species: 2-3 species on the first nights, all five
## by night 4-6), read under the card once the props are in, one at a time on a worker thread, and held
## for the run: a species' first spawn finds its model in the resource cache (monster.gd setup; read
## there, the spawn frame held 155 ms). Each model holds ~9 MB of textures, so only the coming night's
## are read: when a new day brings species of its own, they are read early in that day, one at a time.
## Each read (~50 ms on its worker) puts ~10 ms of work on the main thread in one frame (~28 ms for the
## first model in a process, more on a busy machine): read together after the card they made 36-57 ms
## frames a second into play; two at a time under the card, 52-64 ms frames there and 25-40 ms scatter
## steps. The build waits for the last one before its batches.
## Off (--no-monster-prefetch, false before start_run, or a build without the card: tools, headless
## tests), each loads at its first spawn.
static var prefetch_monsters := not "--no-monster-prefetch" in OS.get_cmdline_user_args()
## The most the card waits for the creature models after the build (ms; they take 0.1-0.25 s): a
## slow disk or a stalled read leaves the rest to the day's reads (or their first spawn) instead of
## holding the card.
const MONSTER_FEED_WAIT_MSEC := 1500
## How far into a day (day_progress) its new species start loading: past the dawn, long before dusk.
const MONSTER_DAY_FROM := 0.05
var monster_scenes: Array[Resource] = []
## The creature models still to come in, the first one loading.
var monster_feed: Array[String] = []
## The ones the feed has asked LoadPace for. Each is asked once: one that failed on its worker is
## dropped (LoadPace would only hand the same failed load back, and the card would wait for ever).
var monster_asked := {}
## The models this run has in (or gave up on, failed); built under the card, the map then follows the
## run's days and reads the species each new night adds (_want_night_species).
var monster_done := {}
var monster_follow := false
var monster_check := 0.0
var stats := {"instances":0,"multimeshes":0,"props":0,"resource_visuals":0}

static func layouts() -> Dictionary:
	if _layout_cache.is_empty():
		_layout_cache = JSON.parse_string(FileAccess.get_file_as_string(ROOT+"layouts.json"))
	return _layout_cache

## Every model this map may place, for LoadPace.want() while the expedition's card comes up.
## The props each map places (its layout, scatter and camp), read on a worker thread while the
## expedition's card comes up. A stale entry only reads something unused; a prop missing here is
## read when it is first placed, as before.
const MAP_PROPS := {
	"forest":["log_bench","firewood_pile","camp_supplies","tent_orange","signpost","reeds","mossy_boulder","fern_clump",
		"forest_ruin","oak_broad","fallen_log","pine_tall","birch_slim","bush_round","mushroom_cluster","tree_stump",
		"white_flowers","yellow_flowers","pink_flowers"],
	"quarry":["ember_rock","log_bench","firewood_pile","tool_rack","tent_green","signpost","sandstone_cliff","sandstone_boulder",
		"cut_blocks","quarry_crane","mine_cart","dead_tree","dry_shrub"],
	"frost":["ice_crystal","log_bench","firewood_pile","sled_empty","tent_orange","signpost","snow_boulder","frost_shrine",
		"snow_pine","snowman","frost_shrub","snow_fence"]}

## The map whose look, layout and bake a run's map is built with: the tutorial is the forest basin
## (server/survival_maps.py ALIASES), an unknown map the forest.
static func basin(map: String) -> String:
	return map if LOOK.has(map) else "forest"

static func resource_paths(run_map: String) -> Array:
	var map := basin(run_map)
	# The baked data first: the build needs it before anything else.
	var paths := [SurvivalBake.path(map)]
	var placed: Array = MAP_PROPS.get(map, MAP_PROPS.forest)
	for id in placed:
		for path: String in prop_paths(id): if not path.is_empty(): paths.append(path)
	# The resource models (dressed when the run's nodes arrive, right after the build) and the
	# camp hearth; resource-only models without their LOD files, which they never show.
	for kind in RESOURCE_MODELS.get(map, RESOURCE_MODELS.forest):
		var id: String = RESOURCE_MODELS.get(map, RESOURCE_MODELS.forest)[kind][0]
		if id in placed: continue
		var path: String = prop_paths(id)[0]
		if not path in paths: paths.append(path)
	paths.append(CAMP)
	return paths

## The model of each creature species (every one when `species` is empty) for this map's variant
## (the ones monster.gd setup loads): the species' own, else its stand-in's (`stand_ins`, the run's
## night_stand_ins: server/catalog.py ENEMIES stand_in, today's art until a species has a model).
static func monster_paths(map: String, species: Array = [], stand_ins: Dictionary = {}) -> Array[String]:
	var paths: Array[String] = []
	for kind in (species if not species.is_empty() else Monster.WALK_REF.keys()):
		var art := Monster.art_species(str(kind),str(stand_ins.get(kind,"")),map)
		var path := Monster.resolved_path(art,map)
		if path != "" and not path in paths: paths.append(path)
	return paths

## The species the run's coming night can bring (server/catalog.py night_species, sent with the run);
## every species when the server does not say (an older server).
static func night_species(run: Dictionary) -> Array:
	var listed = run.get("night_species")
	if listed is Array and not (listed as Array).is_empty(): return listed
	return Monster.WALK_REF.keys()

## The camp's hearth model (camp centre of every map).
const CAMP := "res://assets/storybook_camp_v1.glb"

## A prop's model and its level-of-detail model ("" when it has none).
static func prop_paths(id: String) -> Array:
	if VILLAGE_PROPS.has(id):
		return [VILLAGE+VILLAGE_PROPS[id][0], VILLAGE+VILLAGE_PROPS[id][1] if VILLAGE_PROPS[id][1] != "" else ""]
	return [ASSETS+id+".glb", ASSETS+id+"_lod1.glb"]

## Paced under the loading card (await it), in one go otherwise; the order (and so the seeded layout)
## is the same either way.
func build(run: Dictionary) -> void:
	name = "SurvivalMap"
	state = run
	map_id = str(run.get("map_id","forest"))
	if not LOOK.has(map_id): map_id = "forest"
	look = LOOK[map_id]
	daytime.setup(look)
	var all := layouts()
	spec = all.maps[map_id]
	bounds = float(all.bounds)
	noise.seed = {"forest":11,"quarry":23,"frost":37}[map_id]
	noise.frequency = 0.045
	noise.fractal_octaves = 3
	rng.seed = noise.seed*7919
	process_priority = 100
	# Its per-frame work starts once it is built (a paced build spans frames).
	set_process(false)
	# The village's teardown (main.gd build_world) and this map's first draws in different frames: in
	# one they held the frame 50-64 ms under the card (the baked ground goes in at once).
	await LoadPace.step("survival map")
	# Read on a worker thread since the expedition began (resource_paths); used only when it is
	# fresh and was made for this run's obstacles and hazards, else the map is built as before.
	baked = null
	var bake_path := SurvivalBake.path(map_id)
	if not SurvivalBake.disabled and ResourceLoader.exists(bake_path):
		if LoadPace.pending(bake_path): await LoadPace.fetch(bake_path)
		baked = SurvivalBake.data(map_id,state,spec,bounds)
		# And only while this code still gives the ground and water the bake holds (its fingerprint:
		# an exported game cannot compare the scripts' text).
		if baked != null and not SurvivalBake.ground_fits(self,baked): baked = null
	var span := LoadPace.narrow(0.0, 0.35)
	await _build_ground()
	LoadPace.span = span
	await LoadPace.step("survival water")
	_build_water()
	await LoadPace.step("survival hazards")
	_build_hazards()
	LoadPace.done(0.45)
	# The props read on a worker thread since the expedition began (main.gd start_run).
	for path: String in resource_paths(map_id): if LoadPace.pending(path): await LoadPace.fetch(path)
	# The props are in and the ground is down: the night's creatures load from here (monster_feed).
	_start_monster_feed()
	await LoadPace.step("survival features")
	await _build_features()
	# The resource models, prepared here under the card: main.gd dresses the run's nodes with them
	# in the frame the expedition starts (update_run), which then only places nodes.
	var models: Dictionary = RESOURCE_MODELS[map_id]
	for kind in models:
		await LoadPace.step("resource models")
		_prop(models[kind][0],models[kind][0] in MAP_PROPS[map_id])
	LoadPace.done(0.6)
	span = LoadPace.narrow(0.6, 0.9)
	await _build_scatter()
	LoadPace.span = span
	await LoadPace.step("survival particles")
	_build_particles()
	# Before the batches: their buffers go to the GPU in the frame the build ends, as without the wait.
	await _finish_monster_feed()
	await LoadPace.step("survival batches")
	_finish_batches()
	# The tutorial's goals in the world, drawn from here so their shaders compile under the card.
	if bool(state.get("tutorial",false)) or str(state.get("map_id","")) == "tutorial":
		guide = TutorialGuide.new()
		add_child(guide)
	_advance_time(state,0.0)
	_apply_grade(true)
	set_process(true)
	LoadPace.done(1.0)

## Under the card, the night's creatures start loading (see prefetch_monsters).
func _start_monster_feed() -> void:
	monster_scenes.clear()
	monster_feed.clear()
	monster_asked.clear()
	monster_done.clear()
	monster_follow = prefetch_monsters and LoadPace.covered
	if not monster_follow: return
	monster_feed = monster_paths(map_id,night_species(state),state.get("night_stand_ins",{}))
	var tree := Engine.get_main_loop() as SceneTree
	if not tree.process_frame.is_connected(_feed_monsters): tree.process_frame.connect(_feed_monsters)
	_feed_monsters()

## During the run (every half second): early in a day, the models of the species its night can bring
## that are not in yet (a new day's roster adds species; one the card ran out of time for) join the
## feed, which reads them one at a time on a worker thread.
func _want_night_species(run: Dictionary, delta: float) -> void:
	if not monster_follow or LoadPace.covered: return
	monster_check -= delta
	if monster_check > 0.0: return
	monster_check = 0.5
	if bool(run.get("night",false)) or float(run.get("day_progress",0.0)) < MONSTER_DAY_FROM: return
	var added := false
	for path in monster_paths(map_id,night_species(run),run.get("night_stand_ins",{})):
		if monster_done.has(path) or path in monster_feed: continue
		monster_feed.append(path)
		added = true
	if not added: return
	var tree := Engine.get_main_loop() as SceneTree
	if not tree.process_frame.is_connected(_feed_monsters): tree.process_frame.connect(_feed_monsters)

## Every frame while models are to come: takes the one that came in and asks for the next.
func _feed_monsters() -> void:
	while not monster_feed.is_empty():
		var path: String = monster_feed[0]
		if LoadPace.pending(path): return
		if LoadPace.held.has(path) or ResourceLoader.has_cached(path):
			var scene := LoadPace.take(path)
			if scene != null: monster_scenes.append(scene)
			monster_done[path] = true
			monster_feed.pop_front()
			continue
		if not monster_asked.has(path):
			monster_asked[path] = true
			LoadPace.want([path])
			if LoadPace.pending(path): return
		# Not readable, or asked and gone without coming in (failed on its worker): its first spawn
		# tries again (monster.gd setup). A failed threaded load stays with ResourceLoader until it
		# is collected; collected here, that try reads the file afresh.
		if ResourceLoader.load_threaded_get_status(path) == ResourceLoader.THREAD_LOAD_FAILED:
			ResourceLoader.load_threaded_get(path)
		monster_done[path] = true
		monster_feed.pop_front()
	_stop_monster_feed()

func _stop_monster_feed() -> void:
	var tree := Engine.get_main_loop() as SceneTree
	if tree.process_frame.is_connected(_feed_monsters): tree.process_frame.disconnect(_feed_monsters)

## The feed stops; the models not in yet are read during the day (_want_night_species) or at their
## first spawn (monster.gd setup).
func _drop_monster_feed() -> void:
	_stop_monster_feed()
	for path in monster_feed: LoadPace.queue.erase(path)
	monster_feed.clear()
	monster_asked.clear()

## Before the batches: the card turns until the last creature model is in (_feed_monsters takes
## each one, asks for the next and drops a failed one), for at most MONSTER_FEED_WAIT_MSEC.
func _finish_monster_feed() -> void:
	var until := Time.get_ticks_msec()+MONSTER_FEED_WAIT_MSEC
	while not monster_feed.is_empty() and LoadPace.covered and is_inside_tree() and Time.get_ticks_msec() < until:
		# Frames spent waiting for a worker's file read, counted as LoadPace.fetch counts them. Not
		# fetch() itself: after a failed read its take() would read the file again on this thread.
		LoadPace.frame_waited = true
		await get_tree().process_frame
		LoadPace.frame_waited = true
		LoadPace.last_step = Time.get_ticks_usec()
	# Uncovered meanwhile, out of the tree or out of time: the rest are read during the day.
	_drop_monster_feed()

func _exit_tree() -> void:
	# Leaving before they are in: the next place's loads go first.
	monster_follow = false
	_drop_monster_feed()

# ------------------------------------------------------------------ terrain
## Distance beyond the flat play square (negative inside). A square measure keeps the walkable
## corners flat; low-frequency noise breaks the straight edges outside it.
func rim_distance(x: float, z: float) -> float:
	var square := maxf(absf(x),absf(z))
	var rim := square-(bounds+1.3)+noise.get_noise_2d(x*0.12+90.0,z*0.12)*2.2
	if square <= bounds+1.0: rim = minf(rim,0.0)
	return rim

func height(x: float, z: float) -> float:
	var h := _pond_dip(x,z)
	var e := maxf(maxf(absf(x),absf(z)),0.001)
	var rim := rim_distance(x,z)
	if rim <= 0.0: return h
	var dz := z/maxf(e,0.001)
	var top: float = lerpf(float(look.rim_side),float(look.rim_north),pow(clampf(-dz,0.0,1.0),1.4)) if dz < 0.0 else lerpf(float(look.rim_side),float(look.rim_south),pow(clampf(dz,0.0,1.0),1.4))
	var n := noise.get_noise_2d(x,z)
	if top < 0.0:
		return h+top*smoothstep(0.0,5.0,rim)+n*0.25*smoothstep(0.0,3.0,rim)
	var rise := smoothstep(0.0,float(look.rim_width),rim)
	var value := top*rise*(1.0+n*0.35)+maxf(0.0,rim-float(look.rim_width))*0.18*top/6.0
	value += noise.get_noise_2d(x*3.1,z*3.1)*float(look.rim_noise)*0.25*rise
	var step := float(look.terrace)
	if step > 0.0:
		var t := value/step
		value = (floorf(t)+smoothstep(0.62,0.98,t-floorf(t)))*step
	return h+value

func _pond_dip(x: float, z: float) -> float:
	if map_id != "forest": return 0.0
	var sd := 99.0
	for f in spec.features:
		if f.kind == "pond": sd = minf(sd,Vector2(x-f.x,z-f.z).length()-float(f.radius))
	if sd > 0.2: return 0.0
	return -1.1*smoothstep(0.0,-1.8,sd)

func pond_distance(x: float, z: float) -> float:
	var sd := 99.0
	for f in spec.features:
		if f.kind == "pond": sd = minf(sd,Vector2(x-f.x,z-f.z).length()-float(f.radius))
	return sd

func path_distance(x: float, z: float) -> float:
	var best := 99.0
	for path in spec.paths:
		var pts: Array = path.points
		for i in pts.size()-1:
			var a := Vector2(pts[i][0],pts[i][1])
			var b := Vector2(pts[i+1][0],pts[i+1][1])
			var p := Geometry2D.get_closest_point_to_segment(Vector2(x,z),a,b)
			best = minf(best,p.distance_to(Vector2(x,z))-float(path.width)*0.5)
	return best

func _grid_axis() -> PackedFloat32Array:
	var axis := PackedFloat32Array()
	var x := -FAR
	while x < -32.0: axis.append(x); x += 2.0
	x = -32.0
	while x < 32.0: axis.append(x); x += 0.5
	x = 32.0
	while x <= FAR+0.01: axis.append(x); x += 2.0
	return axis

func _build_ground() -> void:
	var mesh: ArrayMesh
	if baked != null:
		mesh = baked.get_meta("ground")
		LoadPace.done(1.0)
	else:
		mesh = await _ground_mesh()
	var node := MeshInstance3D.new()
	node.name = "Ground"
	node.mesh = mesh
	_ground_material(node)
	add_child(node)

## The terrain as one mesh on _grid_axis (0.5 m inside +-32 m, 2 m beyond): heights, normals and
## the splat colours (trail, soil, rock, accent) per vertex. Baked by tools/bake_survival.py.
func _ground_mesh() -> ArrayMesh:
	var axis := _grid_axis()
	var count := axis.size()
	var heights := PackedFloat32Array()
	heights.resize(count*count)
	for j in count:
		if j % 2 == 0:
			LoadPace.done(0.5*j/count)
			await LoadPace.step("survival heights")
		for i in count:
			heights[j*count+i] = height(axis[i],axis[j])
	var verts := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()
	verts.resize(count*count); normals.resize(count*count); colors.resize(count*count)
	var obstacles: Array = state.get("obstacles",spec.obstacles)
	var hazards: Array = state.get("hazards",spec.hazards)
	for j in count:
		if j % 2 == 0:
			LoadPace.done(0.5+0.5*j/count)
			await LoadPace.step("survival ground")
		for i in count:
			var x := axis[i]; var z := axis[j]
			var k := j*count+i
			var y := heights[k]
			verts[k] = Vector3(x,y,z)
			var il := maxi(i-1,0); var ir := mini(i+1,count-1)
			var jd := maxi(j-1,0); var ju := mini(j+1,count-1)
			normals[k] = _ground_normal(heights[j*count+il],heights[j*count+ir],axis[ir]-axis[il],heights[jd*count+i],heights[ju*count+i],axis[ju]-axis[jd])
			colors[k] = _splat(x,z,y,obstacles,hazards)
	var indices := PackedInt32Array()
	for j in count-1:
		for i in count-1:
			var a := j*count+i
			indices.append_array([a,a+1,a+count,a+1,a+count+1,a+count])
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_COLOR] = colors
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
	return mesh

## A ground vertex's normal from its neighbours' heights (left/right `wx` apart, down/up `wz` apart).
func _ground_normal(left: float, right: float, wx: float, down: float, up: float, wz: float) -> Vector3:
	var dx := (right-left)/maxf(wx,0.001)
	var dzv := (up-down)/maxf(wz,0.001)
	return Vector3(-dx,1.0,-dzv).normalized()

func _ground_material(node: MeshInstance3D) -> void:
	var mat := ShaderMaterial.new()
	mat.shader = GROUND_SHADER
	for key in ["grass_detail","sand_detail","rock_detail"]:
		mat.set_shader_parameter(key,load(DETAIL+key+".png"))
	mat.set_shader_parameter("grass_normal",load(DETAIL+"grass_detail_normal.png"))
	mat.set_shader_parameter("sand_normal",load(DETAIL+"sand_detail_normal.png"))
	mat.set_shader_parameter("rock_normal",load(DETAIL+"rock_detail_normal.png"))
	for key in ["turf_low","turf_high","trail","rock","accent"]:
		mat.set_shader_parameter(key,Color(look[key]))
	mat.set_shader_parameter("soil_color",Color(look.soil))
	mat.set_shader_parameter("trail_color",Color(look.trail))
	mat.set_shader_parameter("rock_color",Color(look.rock))
	mat.set_shader_parameter("accent_color",Color(look.accent))
	mat.set_shader_parameter("snow",float(look.snow))
	mat.set_shader_parameter("strata",float(look.strata))
	mat.set_shader_parameter("wet_level",float(look.water_y)+0.2 if map_id != "quarry" else -20.0)
	var segments := PackedVector4Array()
	var widths := PackedFloat32Array()
	for path in spec.paths:
		var pts: Array = path.points
		for i in pts.size()-1:
			segments.append(Vector4(pts[i][0],pts[i][1],pts[i+1][0],pts[i+1][1]))
			widths.append(float(path.width)*0.5)
	while segments.size() < 32:
		segments.append(Vector4(999,999,999,999)); widths.append(0.0)
	mat.set_shader_parameter("path_segments",segments)
	mat.set_shader_parameter("path_half_widths",widths)
	mat.set_shader_parameter("path_count",mini(spec.paths.reduce(func(acc,p): return acc+p.points.size()-1,0),32))
	node.material_override = mat
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	materials.append(mat)

func _splat(x: float, z: float, y: float, obstacles: Array, hazards: Array) -> Color:
	var inside := maxf(absf(x),absf(z)) < bounds+4.0
	var wobble := noise.get_noise_2d(x*2.3,z*2.3)*0.22
	var trail := 0.0
	var soil := 0.0
	var rock := 0.0
	var accent := 0.0
	var camp := Vector2(x,z).length()
	trail = 1.0-smoothstep(2.9,3.9,camp+wobble*2.0)
	if inside:
		var d := path_distance(x,z)+wobble
		trail = maxf(trail,1.0-smoothstep(-0.15,0.35,d))
		for o in obstacles:
			var od := Vector2(x-o.x,z-o.z).length()-float(o.radius)
			if str(o.get("kind","")) in ["pond"]: continue
			soil = maxf(soil,(1.0-smoothstep(-0.4,0.6,od+wobble))*0.5)
		for h in hazards:
			var hd := Vector2(x-h.x,z-h.z).length()-float(h.radius)
			if h.kind == "ember": accent = maxf(accent,1.0-smoothstep(-0.2,1.8,hd+wobble))
			else: accent = maxf(accent,(1.0-smoothstep(0.0,1.4,hd+wobble))*0.7)
	match map_id:
		"forest":
			var rim := rim_distance(x,z)
			# The woods beyond the clearing sit in their own shade: mossy, darker turf.
			accent = maxf(accent,clampf(0.65+noise.get_noise_2d(x*0.6,z*0.6)*0.5,0.0,0.9)*smoothstep(-0.5,3.0,rim)*(1.0 if z < bounds else 0.0))
			if map_id == "forest" and pond_distance(x,z) < 1.2: soil = maxf(soil,1.0-smoothstep(-0.4,1.2,pond_distance(x,z)))
			if y < float(look.water_y)+0.35 and z > bounds: soil = 1.0
		"quarry":
			soil = maxf(soil,clampf(noise.get_noise_2d(x*0.35+40.0,z*0.35)*1.2+0.25,0.0,0.7))
			if y > 0.4: rock = clampf((y-0.4)*0.25,0.0,0.6)
		"frost":
			soil = soil*0.6
	return Color(clampf(trail,0.0,1.0),clampf(soil,0.0,1.0),rock,clampf(accent,0.0,1.0))

# ------------------------------------------------------------------ water
func _build_water() -> void:
	var mat: ShaderMaterial = null
	for patch in _water_patches():
		if mat == null: mat = _water_material(map_id == "frost")
		_water_patch(patch[0],patch[1],patch[2],mat,patch[3])

## The map's water sheets: [area, grid step, level, pond] (the forest's pond and lake, frost's lake).
func _water_patches() -> Array:
	var lake := [Rect2(-FAR,bounds-1.0,FAR*2.0,FAR-bounds+1.0),2.0,float(look.water_y),false]
	match map_id:
		"forest": return [[Rect2(4.0,3.0,14.0,13.5),0.4,float(look.pond_y),true],lake]
		"frost": return [lake]
	return []

func _water_material(frozen: bool) -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = WATER_SHADER
	mat.set_shader_parameter("surface_normal",load(VILLAGE+"v3/pond_surface_normal.png"))
	mat.set_shader_parameter("shallow_color",Color(look.water_shallow))
	mat.set_shader_parameter("deep_color",Color(look.water_deep))
	mat.set_shader_parameter("frozen",1.0 if frozen else 0.0)
	materials.append(mat)
	return mat

func _water_patch(area: Rect2, step: float, level: float, mat: ShaderMaterial, pond: bool) -> void:
	var mesh: ArrayMesh = _baked_water("Pond" if pond else "Lake") if baked != null else _water_mesh(area,step,level,pond)
	if mesh == null: return
	var node := MeshInstance3D.new()
	node.name = "Pond" if pond else "Lake"
	node.mesh = mesh
	node.material_override = mat
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)

func _baked_water(water_name: String) -> ArrayMesh:
	for entry in baked.get_meta("water",[]):
		if entry[0] == water_name: return entry[1]
	return null

## A water sheet at `level` over the cells where it is above the ground (null when there are none),
## shore foam in the vertex colour. Baked by tools/bake_survival.py.
func _water_mesh(area: Rect2, step: float, level: float, pond: bool) -> ArrayMesh:
	var nx := int(ceil(area.size.x/step))+1
	var nz := int(ceil(area.size.y/step))+1
	var verts := PackedVector3Array(); var colors := PackedColorArray(); var normals := PackedVector3Array()
	var wet := PackedByteArray()
	for j in nz:
		for i in nx:
			var x := area.position.x+i*step; var z := area.position.y+j*step
			var vertex := _water_vertex(x,z,level,pond)
			verts.append(Vector3(x,level,z)); normals.append(Vector3.UP)
			colors.append(Color(vertex.x,0,0,1))
			wet.append(1 if vertex.y > 0.0 else 0)
	var indices := PackedInt32Array()
	for j in nz-1:
		for i in nx-1:
			var a := j*nx+i
			if wet[a]+wet[a+1]+wet[a+nx]+wet[a+nx+1] == 0: continue
			indices.append_array([a,a+1,a+nx,a+1,a+nx+1,a+nx])
	if indices.is_empty(): return null
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts; arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_COLOR] = colors; arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
	return mesh

## A water vertex at (x, z): its shore foam (x) and whether the water is over the ground there (y 1/0).
func _water_vertex(x: float, z: float, level: float, pond: bool) -> Vector2:
	var depth := level-height(x,z)
	var shore := clampf(-pond_distance(x,z)/2.4,0.0,1.0) if pond else clampf(depth/1.4,0.0,1.0)
	return Vector2(shore,1.0 if depth > -0.05 else 0.0)

# ------------------------------------------------------------------ hazards
func _build_hazards() -> void:
	var hazards: Array = state.get("hazards",spec.hazards)
	var groups: Array = []
	for h in hazards:
		var joined := false
		for g in groups:
			for o in g:
				if o.kind == h.kind and Vector2(o.x-h.x,o.z-h.z).length() < float(o.radius)+float(h.radius) and g.size() < 4:
					g.append(h); joined = true; break
			if joined: break
		if not joined: groups.append([h])
	for g in groups:
		var lo := Vector2(INF,INF); var hi := Vector2(-INF,-INF)
		var circles := PackedVector4Array()
		for h in g:
			lo = lo.min(Vector2(h.x-h.radius*1.35,h.z-h.radius*1.35))
			hi = hi.max(Vector2(h.x+h.radius*1.35,h.z+h.radius*1.35))
			circles.append(Vector4(h.x,h.z,h.radius,0))
		while circles.size() < 4: circles.append(Vector4(999,999,1,0))
		var quad := PlaneMesh.new()
		quad.size = hi-lo
		var node := MeshInstance3D.new()
		node.name = "Hazard_"+str(g[0].kind)
		node.mesh = quad
		node.position = Vector3((lo.x+hi.x)*0.5,0.03 if g[0].kind == "ember" else 0.022,(lo.y+hi.y)*0.5)
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var mat := ShaderMaterial.new()
		mat.shader = HAZARD_SHADER
		mat.set_shader_parameter("mode",0 if g[0].kind == "ember" else 1)
		mat.set_shader_parameter("circles",circles)
		mat.set_shader_parameter("circle_count",g.size())
		mat.render_priority = 1
		node.material_override = mat
		add_child(node)
		materials.append(mat)
		for h in g:
			_hazard_dressing(h)
	# One readable label per hazard group, shown when the walker is near (main.gd nameplate fade).
	for g in groups:
		var h: Dictionary = g[0]
		var label := Label3D.new()
		label.text = TranslationServer.translate("얼음 · 이동 둔화") if h.kind == "ice" else TranslationServer.translate("열기 · 접근 주의")
		label.position = Vector3(h.x,0.7,h.z)
		label.pixel_size = 0.006; label.font_size = 40; label.outline_size = 10
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.modulate = Color("e5f6f4") if h.kind == "ice" else Color("ffcb92")
		label.outline_modulate = Color(0,0,0,0.55)
		label.add_to_group("place_nameplates")
		add_child(label)

func _hazard_dressing(h: Dictionary) -> void:
	var count := int(float(h.radius)*2.2)
	for i in count:
		var a := rng.randf()*TAU
		var r := float(h.radius)*rng.randf_range(0.82,1.05)
		var p := Vector2(h.x+cos(a)*r,h.z+sin(a)*r)
		if path_distance(p.x,p.y) < 0.3: continue
		if h.kind == "ember": _instance("ember_rock",Vector3(p.x,-0.04,p.y),rng.randf()*TAU,rng.randf_range(0.22,0.34),{"shadow":false})
		else: _instance("ice_crystal",Vector3(p.x,-0.03,p.y),rng.randf()*TAU,rng.randf_range(0.16,0.26),{"shadow":false})
	if h.kind == "ember":
		var sparks := CPUParticles3D.new()
		sparks.position = Vector3(h.x,0.1,h.z)
		sparks.amount = int(10*float(h.radius))
		sparks.lifetime = 2.2
		sparks.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
		sparks.emission_sphere_radius = float(h.radius)*0.8
		sparks.direction = Vector3.UP; sparks.spread = 20
		sparks.initial_velocity_min = 0.4; sparks.initial_velocity_max = 1.1
		sparks.gravity = Vector3(0.15,0.25,0)
		sparks.scale_amount_min = 0.03; sparks.scale_amount_max = 0.06
		var sm := SphereMesh.new(); sm.radius = 0.5; sm.height = 1.0; sm.radial_segments = 6; sm.rings = 3
		sparks.mesh = sm
		var spark_mat := StandardMaterial3D.new()
		spark_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		spark_mat.albedo_color = Color("ffb35c")
		sparks.material_override = spark_mat
		sparks.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(sparks)

# ------------------------------------------------------------------ props
## `want_low` false skips the prop's LOD file (resource models, which never show it); a later call
## that wants it loads it then.
func _prop(id: String, want_low := true) -> Dictionary:
	if props.has(id):
		var known: Dictionary = props[id]
		if want_low and known.get("low_skipped",false): _add_low(id,known)
		return known
	var path: String = prop_paths(id)[0]
	var entry := {"ok":false}
	if not ResourceLoader.exists(path):
		props[id] = entry
		return entry
	# Read on a worker thread at the start of the expedition (LoadPace.want) when it is listed.
	var scene := (LoadPace.take(path) as PackedScene).instantiate()
	var meshes := scene.find_children("*","MeshInstance3D",true,false)
	if meshes.is_empty():
		scene.free(); props[id] = entry; return entry
	var high: Mesh
	var material: ShaderMaterial = null
	var plain := _plain_mesh(scene,meshes) if path.begins_with(ASSETS) else null
	if plain != null:
		# A survival GLB is one node with one surface and no transform, imported without automatic
		# LODs: its imported mesh is drawn as it is (no copy read back from the GPU), the converted
		# material set on the nodes that draw it (material_override).
		high = plain.mesh
		material = _convert_material(_source_material(plain,0),id)
	else:
		# Every mesh node of the GLB merged into one mesh (node transforms baked in), one converted
		# material per surface, so a prop is one MultiMesh / one node however its GLB is split.
		# (Village props stay merged: their imports generate automatic LODs the copy leaves out.)
		var merged := ArrayMesh.new()
		var converted := {}
		for node in meshes:
			var source := node as MeshInstance3D
			var xf := _scene_transform(scene,source)
			for surface in source.mesh.get_surface_count():
				_append_surface(merged,source.mesh,surface,xf)
				var original := _source_material(source,surface)
				var key := original.get_instance_id() if original else 0
				if not converted.has(key): converted[key] = _convert_material(original,id)
				merged.surface_set_material(merged.get_surface_count()-1,converted[key])
		high = merged
	scene.free()
	entry = {"ok":true,"mesh":high,"low":high,"aabb":high.get_aabb(),"material":material}
	props[id] = entry
	stats.props += 1
	if want_low: _add_low(id,entry)
	else: entry["low_skipped"] = true
	return entry

## The prop's level-of-detail mesh into entry.low (it stays the full mesh without a usable LOD file).
func _add_low(id: String, entry: Dictionary) -> void:
	entry.erase("low_skipped")
	var lod_path: String = prop_paths(id)[1]
	if lod_path == "" or not ResourceLoader.exists(lod_path): return
	var high: Mesh = entry.mesh
	var lod_scene := (LoadPace.take(lod_path) as PackedScene).instantiate()
	var lod_meshes := lod_scene.find_children("*","MeshInstance3D",true,false)
	var plain := _plain_mesh(lod_scene,lod_meshes) if entry.material != null else null
	if plain != null:
		if plain.mesh.get_surface_count() == high.get_surface_count(): entry.low = plain.mesh
		lod_scene.free()
		return
	var candidate := ArrayMesh.new()
	for node in lod_meshes:
		var source := node as MeshInstance3D
		for surface in source.mesh.get_surface_count():
			_append_surface(candidate,source.mesh,surface,_scene_transform(lod_scene,source))
	lod_scene.free()
	# LOD files carry geometry only; they reuse the full prop's materials surface by surface.
	if candidate.get_surface_count() == high.get_surface_count():
		for surface in candidate.get_surface_count():
			candidate.surface_set_material(surface,high.surface_get_material(surface))
		entry.low = candidate

## The scene's only mesh node when it can be drawn as imported: one surface, no node transform, no
## skin or blend shapes (null otherwise).
func _plain_mesh(scene: Node, meshes: Array) -> MeshInstance3D:
	if meshes.size() != 1: return null
	var node := meshes[0] as MeshInstance3D
	if node.mesh == null or node.mesh.get_surface_count() != 1 or node.skin != null: return null
	if node.mesh is ArrayMesh and (node.mesh as ArrayMesh).get_blend_shape_count() > 0: return null
	if not _scene_transform(scene,node).is_equal_approx(Transform3D.IDENTITY): return null
	return node

func _source_material(node: MeshInstance3D, surface: int) -> Material:
	var original: Material = node.get_surface_override_material(surface)
	if original == null: original = node.mesh.surface_get_material(surface)
	return original

func _scene_transform(scene: Node, node: Node) -> Transform3D:
	var xf := Transform3D.IDENTITY
	var current := node
	while current != null and current != scene:
		if current is Node3D: xf = (current as Node3D).transform*xf
		current = current.get_parent()
	if scene is Node3D: xf = (scene as Node3D).transform*xf
	return xf

func _append_surface(out: ArrayMesh, mesh: Mesh, surface: int, xf: Transform3D) -> void:
	var arrays := mesh.surface_get_arrays(surface)
	if not xf.is_equal_approx(Transform3D.IDENTITY):
		var v: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		for i in v.size(): v[i] = xf*v[i]
		arrays[Mesh.ARRAY_VERTEX] = v
		var normal_basis := xf.basis.inverse().transposed()
		if arrays[Mesh.ARRAY_NORMAL] != null:
			var n: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
			for i in n.size(): n[i] = (normal_basis*n[i]).normalized()
			arrays[Mesh.ARRAY_NORMAL] = n
		if arrays[Mesh.ARRAY_TANGENT] != null:
			var t: PackedFloat32Array = arrays[Mesh.ARRAY_TANGENT]
			for i in t.size()/4:
				var d := (xf.basis*Vector3(t[i*4],t[i*4+1],t[i*4+2])).normalized()
				t[i*4] = d.x; t[i*4+1] = d.y; t[i*4+2] = d.z
			arrays[Mesh.ARRAY_TANGENT] = t
	out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)

## Per prop and map: tint, snow, wind and night glow on top of the Tripo albedo/normal textures.
func _convert_material(source: Material, id: String) -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = PROP_SHADER
	if source is BaseMaterial3D:
		var base := source as BaseMaterial3D
		mat.set_shader_parameter("albedo_texture",base.albedo_texture)
		mat.set_shader_parameter("base_color",base.albedo_color)
		mat.set_shader_parameter("normal_texture",base.normal_texture)
		mat.set_shader_parameter("use_normal",base.normal_enabled and base.normal_texture != null)
	var foliage := id in ["pine_tall","oak_broad","birch_slim","bush_round","berry_bush","fiber_grass","fern_clump","snow_pine","frost_shrub","dry_shrub","reeds","white_flowers","yellow_flowers","pink_flowers"]
	if foliage:
		var tall := id in ["pine_tall","oak_broad","birch_slim","snow_pine"]
		mat.set_shader_parameter("wind",0.07 if tall else 0.05)
		mat.set_shader_parameter("wind_height",5.0 if tall else 1.0)
	var tint := Color.WHITE
	var sat := 1.0
	var bright := 1.0
	match map_id:
		"quarry":
			if id in ["birch_slim"]: tint = Color("ffc070"); sat = 1.25
			elif id in ["stone_pile","fiber_grass"]: tint = Color("f2cf9e")
			elif id in ["berry_bush"]: tint = Color("e8e0b0")
		"frost":
			if id in ["stone_pile","fiber_grass","berry_bush","log_bench","firewood_pile","tent_orange","tent_green","tree_stump","camp_supplies","sled_empty","signpost"]:
				mat.set_shader_parameter("snow",0.85)
			if id in ["fiber_grass"]: tint = Color("dfe8e0"); sat = 0.7
			if id in ["firewood_pile","log_bench"]: tint = Color("d9c3a8"); sat = 0.8
		"forest":
			if id in ["pine_tall"]: bright = 1.04
			elif id in ["mossy_boulder"]: tint = Color("d8dde6"); sat = 0.45
			elif id in ["oak_broad"]: tint = Color("e6f2d0"); sat = 1.25; bright = 0.95
	mat.set_shader_parameter("tint",tint)
	mat.set_shader_parameter("saturation",sat)
	mat.set_shader_parameter("brightness",bright)
	if id in ["ember_rock","mine_cart"]:
		mat.set_shader_parameter("glow_mode",1); mat.set_shader_parameter("glow_color",Color("ff7a2a"))
		glow_materials.append(mat)
	elif id in ["ice_crystal"]:
		mat.set_shader_parameter("glow_mode",2); mat.set_shader_parameter("glow_color",Color("7fd8ff"))
		glow_materials.append(mat)
	elif id in ["frost_shrine"]:
		mat.set_shader_parameter("glow_mode",1); mat.set_shader_parameter("glow_color",Color("ffc46b"))
		glow_materials.append(mat)
	elif id == "mushroom_cluster":
		mat.set_shader_parameter("glow_mode",1); mat.set_shader_parameter("glow_color",Color("ff9a7a"))
		glow_materials.append(mat)
	mat.set_meta("glow_base",{"ember_rock":2.2,"mine_cart":1.2,"ice_crystal":1.3,"frost_shrine":2.0,"tool_rack":0.8,"signpost":0.5,"mushroom_cluster":0.35}.get(id,0.0))
	materials.append(mat)
	return mat

## Queue one instance of a prop for the chunked MultiMesh batches.
func _instance(id: String, at: Vector3, yaw: float, scale: float, opts := {}) -> bool:
	var entry := _prop(id)
	if not entry.ok: return false
	var basis := Basis(Vector3.UP,yaw).scaled(Vector3.ONE*scale)
	if opts.has("tilt"): basis = Basis(Vector3(cos(yaw),0,sin(yaw)),float(opts.tilt))*basis
	var shadow: bool = opts.get("shadow",true)
	var lod: String = "cover" if id in GROUND_COVER else opts.get("lod","auto")
	var key := "%s|%s|%s|%d_%d" % [id,shadow,lod,int(floor(at.x/CHUNK)),int(floor(at.z/CHUNK))]
	if not batches.has(key):
		batches[key] = {"id":id,"shadow":shadow,"lod":lod,"xforms":[]}
	batches[key].xforms.append(Transform3D(basis,at))
	stats.instances += 1
	return true

func _finish_batches() -> void:
	var root := Node3D.new()
	root.name = "Props"
	add_child(root)
	for key in batches:
		var b: Dictionary = batches[key]
		var entry := _prop(b.id)
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		var always_low: bool = b.lod == "low"
		var cover: bool = b.lod == "cover" and entry.low != entry.mesh
		mm.mesh = entry.low if always_low or cover else entry.mesh
		mm.instance_count = b.xforms.size()
		var largest := 0.0
		for i in b.xforms.size():
			mm.set_instance_transform(i,b.xforms[i])
			var s: Vector3 = (b.xforms[i] as Transform3D).basis.get_scale()
			largest = maxf(largest,maxf(s.x,maxf(s.y,s.z)))
		var node := MultiMeshInstance3D.new()
		node.multimesh = mm
		if entry.material: node.material_override = entry.material
		node.set_meta("prop",b.id)
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if b.shadow else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(node)
		if cover:
			# Ground cover: its LOD until the tallest instance reaches COVER_LIMITS on screen.
			var extent: Vector3 = entry.aabb.size
			cover_multimeshes.append({"mm":mm,"high":entry.mesh,"low":entry.low,"low_active":true,"size":maxf(extent.x,maxf(extent.y,extent.z))*largest})
		elif not always_low and entry.low != entry.mesh:
			multimeshes.append({"mm":mm,"high":entry.mesh,"low":entry.low})
		stats.multimeshes += 1
	batches.clear()

## A single authored prop (landmarks, camp kit): its own node so it can carry labels and lights.
func _single(id: String, at: Vector3, yaw: float, scale: float, shadow := true) -> MeshInstance3D:
	var entry := _prop(id)
	if not entry.ok: return null
	var node := MeshInstance3D.new()
	node.name = id
	node.mesh = entry.mesh
	if entry.material: node.material_override = entry.material
	node.position = at
	node.rotation.y = yaw
	node.scale = Vector3.ONE*scale
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadow else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
	return node

func _fit_scale(id: String, measure: String, metres: float) -> float:
	var entry := _prop(id)
	if not entry.ok: return 1.0
	var size: Vector3 = entry.aabb.size
	var source: float = size.y if measure == "height" else maxf(size.x,size.z)
	return metres/maxf(source,0.001)

# ------------------------------------------------------------------ features (server obstacle circles)
func _build_features() -> void:
	for f in spec.features:
		await LoadPace.step("survival feature")
		var at := Vector3(f.x,0,f.z)
		var yaw := deg_to_rad(float(f.get("yaw",rng.randf()*360.0)))
		var r := float(f.get("radius",1.0))
		match str(f.kind):
			"bench": _single("log_bench",at,yaw,_fit_scale("log_bench","width",1.7))
			"firewood": _single("firewood_pile",at,yaw,_fit_scale("firewood_pile","width",1.3))
			"supplies": _single("camp_supplies",at,yaw,_fit_scale("camp_supplies","width",1.4))
			"tools": _single("tool_rack",at,yaw,_fit_scale("tool_rack","width",1.5))
			"sled":
				# The first Tripo sled has a little rider on it; the empty one replaces it once generated.
				var sled := "sled_empty" if ResourceLoader.exists(ASSETS+"sled_empty.glb") else "camp_supplies"
				_single(sled,at,yaw,_fit_scale(sled,"width",1.5))
			"sign": _single("signpost",at,yaw,_fit_scale("signpost","height",1.9))
			"snowman": _single("snowman",at,yaw,_fit_scale("snowman","height",1.4))
			"tent":
				var tent := "tent_green" if map_id == "quarry" else "tent_orange"
				# Ridge across the view so both canvas slopes read from the follow camera.
				_single(tent,at,deg_to_rad(140.0),_fit_scale(tent,"width",2.7))
			"pond": _pond_dressing(f)
			"boulder":
				_single("mossy_boulder",at+Vector3(0,-0.1,0),yaw,_fit_scale("mossy_boulder","width",r*2.15))
				for i in 3: _instance("fern_clump",at+Vector3(cos(i*2.1+yaw),0,sin(i*2.1+yaw))*(r*0.95),rng.randf()*TAU,rng.randf_range(0.7,1.0),{"shadow":false})
			"ruin":
				_single("forest_ruin",at,yaw,_fit_scale("forest_ruin","width",float(f.span)+r*2.0))
				_landmark(at+Vector3(0,4.2,0),"옛 돌문")
			"oak": _single("oak_broad",at,yaw,rng.randf_range(0.95,1.1))
			"log": _single("fallen_log",at+Vector3(0,-0.05,0),yaw,_fit_scale("fallen_log","width",float(f.length)+0.3))
			"outcrop":
				_single("sandstone_cliff",at+Vector3(0,-0.15,0),yaw,_fit_scale("sandstone_cliff","width",r*2.25))
				for i in 2: _instance("sandstone_boulder",at+Vector3(cos(i*2.6+yaw),0,sin(i*2.6+yaw))*(r*0.92),rng.randf()*TAU,rng.randf_range(0.28,0.4))
			"blocks": _single("cut_blocks",at,yaw,_fit_scale("cut_blocks","width",r*2.1))
			"crane":
				_single("quarry_crane",at,yaw,_fit_scale("quarry_crane","height",5.4))
				_landmark(at+Vector3(0,6.0,0),"노을 기중기")
			"cart":
				_single("mine_cart",at,0.0,_fit_scale("mine_cart","width",1.8))
			"deadtree": _single("dead_tree",at,yaw,rng.randf_range(0.9,1.1))
			"snow_boulder": _single("snow_boulder",at+Vector3(0,-0.1,0),yaw,_fit_scale("snow_boulder","width",r*2.2))
			"shrine":
				_single("frost_shrine",at,0.0,_fit_scale("frost_shrine","height",3.2))
				_landmark(at+Vector3(0,3.9,0),"서리 등불탑")
			"crystal": _single("ice_crystal",at,yaw,_fit_scale("ice_crystal","width",r*2.0))
			"pine": _single("snow_pine",at,yaw,rng.randf_range(0.95,1.1))
	_camp_center()
	if map_id == "quarry": _rails(19.0)

func _landmark(at: Vector3, text: String) -> void:
	var label := Label3D.new()
	label.text = TranslationServer.translate(text)
	label.position = at
	label.pixel_size = 0.0065; label.font_size = 44; label.outline_size = 12
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.modulate = Color("f3e6c0"); label.outline_modulate = Color(0,0,0,0.5)
	label.add_to_group("place_nameplates")
	add_child(label)

func _camp_center() -> void:
	var hearth := LoadPace.take(CAMP) as PackedScene if ResourceLoader.exists(CAMP) else null
	if hearth:
		var node := hearth.instantiate()
		node.name = "Hearth"
		add_child(node)
	var label := Label3D.new()
	label.text = TranslationServer.translate("야영지")
	label.position = Vector3(0,1.6,-0.8)
	label.pixel_size = 0.006; label.font_size = 40; label.outline_size = 10
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.modulate = Color("eedb9c"); label.outline_modulate = Color(0,0,0,0.5)
	label.add_to_group("place_nameplates")
	add_child(label)

func _pond_dressing(f: Dictionary) -> void:
	var r := float(f.radius)
	var count := int(r*5)
	for i in count:
		var a := rng.randf()*TAU
		var p := Vector2(f.x,f.z)+Vector2(cos(a),sin(a))*r*rng.randf_range(0.82,1.02)
		if pond_distance(p.x,p.y) < -0.55: continue
		if path_distance(p.x,p.y) < 0.4: continue
		if rng.randf() < 0.6: _instance("reeds",Vector3(p.x,height(p.x,p.y)-0.05,p.y),rng.randf()*TAU,rng.randf_range(0.7,1.0),{"shadow":false})
		else: _instance("mossy_boulder",Vector3(p.x,height(p.x,p.y)-0.12,p.y),rng.randf()*TAU,rng.randf_range(0.13,0.2),{"shadow":false})

func _rails(x: float) -> void:
	var wood := StandardMaterial3D.new(); wood.albedo_color = Color("6b4a33"); wood.roughness = 0.9
	var iron := StandardMaterial3D.new(); iron.albedo_color = Color("4c4a4f"); iron.roughness = 0.45; iron.metallic = 0.6
	var sleepers := MultiMesh.new()
	sleepers.transform_format = MultiMesh.TRANSFORM_3D
	var box := BoxMesh.new(); box.size = Vector3(1.6,0.08,0.24)
	sleepers.mesh = box
	var z := -FAR*0.6
	var xf: Array[Transform3D] = []
	while z < FAR*0.6:
		xf.append(Transform3D(Basis(Vector3.UP,rng.randf_range(-0.05,0.05)),Vector3(x,height(x,z)+0.03,z)))
		z += 0.7
	sleepers.instance_count = xf.size()
	for i in xf.size(): sleepers.set_instance_transform(i,xf[i])
	var node := MultiMeshInstance3D.new(); node.multimesh = sleepers; node.material_override = wood
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
	for side in [-0.5,0.5]:
		var rail := MeshInstance3D.new()
		var st := SurfaceTool.new(); st.begin(Mesh.PRIMITIVE_TRIANGLES)
		z = -FAR*0.6
		while z < FAR*0.6:
			var y0 := height(x,z)+0.1; var y1 := height(x,z+1.0)+0.1
			for p in [Vector3(x+side-0.04,y0,z),Vector3(x+side+0.04,y0,z),Vector3(x+side-0.04,y1,z+1.0),Vector3(x+side+0.04,y0,z),Vector3(x+side+0.04,y1,z+1.0),Vector3(x+side-0.04,y1,z+1.0)]:
				st.set_normal(Vector3.UP); st.add_vertex(p)
			z += 1.0
		rail.mesh = st.commit(); rail.material_override = iron
		rail.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(rail)

# ------------------------------------------------------------------ scatter
func _free(x: float, z: float, clearance: float, avoid_paths := true) -> bool:
	if Vector2(x,z).length() < 4.4+clearance: return false
	if avoid_paths and path_distance(x,z) < clearance: return false
	for o in state.get("obstacles",spec.obstacles):
		if Vector2(x-o.x,z-o.z).length() < float(o.radius)+clearance: return false
	for h in state.get("hazards",spec.hazards):
		if Vector2(x-h.x,z-h.z).length() < float(h.radius)+clearance: return false
	for n in state.get("nodes",[]):
		if Vector2(x-n.x,z-n.z).length() < 1.1+clearance: return false
	for c in occupied:
		if Vector2(x-c.x,z-c.y).length() < c.z+clearance: return false
	return true

func _sample_inside() -> Vector2:
	return Vector2(rng.randf_range(-bounds-0.5,bounds+0.5),rng.randf_range(-bounds-0.5,bounds+0.5))

func _sample_rim(min_rim: float, max_rim: float, south_ok: bool) -> Vector2:
	for attempt in 30:
		var p := Vector2(rng.randf_range(-FAR+4,FAR-4),rng.randf_range(-FAR+4,FAR-4))
		var r := rim_distance(p.x,p.y)
		if r < min_rim or r > max_rim: continue
		if not south_ok and p.y > bounds-2.0: continue
		return p
	return Vector2(INF,INF)

func _scatter_inside(id: String, count: int, scale_min: float, scale_max: float, clearance: float, opts := {}, avoid_paths := true, reserve := 0.0) -> void:
	var placed := 0
	for attempt in count*8:
		if placed >= count: break
		var p := _sample_inside()
		if not _free(p.x,p.y,clearance,avoid_paths): continue
		var s := rng.randf_range(scale_min,scale_max)
		if _instance(id,Vector3(p.x,height(p.x,p.y)-0.03,p.y),rng.randf()*TAU,s,opts): placed += 1
		if reserve > 0.0: occupied.append(Vector3(p.x,p.y,reserve*s))

func _scatter_rim(id: String, count: int, scale_min: float, scale_max: float, min_rim: float, max_rim: float, south_ok: bool, opts := {}, spacing := 0.0) -> void:
	var placed := 0
	var spots: Array[Vector2] = []
	for attempt in count*6:
		if placed >= count: break
		var p := _sample_rim(min_rim,max_rim,south_ok)
		if p.x == INF: continue
		var y := height(p.x,p.y)
		if y < float(look.water_y)+0.15: continue
		if spacing > 0.0:
			var crowded := false
			for q in spots:
				if q.distance_to(p) < spacing: crowded = true; break
			if crowded: continue
			spots.append(p)
		if _instance(id,Vector3(p.x,y-0.1,p.y),rng.randf()*TAU,rng.randf_range(scale_min,scale_max),opts): placed += 1

## The rim block (scatter beyond the play square: the same for every run of a map, baked) then the
## inside block (it keeps clear of the run's resource nodes, so it is placed here every time) and grass.
func _build_scatter() -> void:
	# The baked rim when it starts from this build's random state and the rim code still places what
	# it placed for the bake (survival_bake.gd rim_fits); else the rim block runs here.
	var replay := false
	if baked != null and baked.has_meta("rim"):
		await LoadPace.step("scatter")
		replay = SurvivalBake.rim_fits(self,baked)
	rim_replayed = replay
	if replay:
		await LoadPace.step("scatter")
		_replay_rim(baked.get_meta("rim"))
		rng.state = int(baked.get_meta("rng_after_rim"))
	else:
		var before := {}
		if bake_record:
			for key in batches: before[key] = batches[key].xforms.size()
			rng_before_rim = rng.state
		await _scatter_rim_block()
		if bake_record:
			rim_record = _record_rim(before)
			rng_after_rim = rng.state
	await _scatter_inside_block()
	await LoadPace.step("scatter")
	await _grass()

## The instances the rim block queued, per batch key in the batches' order: [key, id, shadow, lod,
## 12 floats per transform (basis columns, origin)].
func _record_rim(before: Dictionary) -> Array:
	var out := []
	for key in batches:
		var b: Dictionary = batches[key]
		var from: int = before.get(key,0)
		if b.xforms.size() <= from: continue
		var flat := PackedFloat32Array()
		for i in range(from,b.xforms.size()):
			var xf: Transform3D = b.xforms[i]
			flat.append_array([xf.basis.x.x,xf.basis.x.y,xf.basis.x.z,xf.basis.y.x,xf.basis.y.y,xf.basis.y.z,
				xf.basis.z.x,xf.basis.z.y,xf.basis.z.z,xf.origin.x,xf.origin.y,xf.origin.z])
		out.append([key,b.id,b.shadow,b.lod,flat])
	return out

## Queues the baked rim block as _instance() did: keys new to the batches in their first order, each
## key's transforms appended in their order.
func _replay_rim(rim: Array) -> void:
	for record in rim:
		var key: String = record[0]
		var id: String = record[1]
		if not _prop(id).ok: continue
		if not batches.has(key): batches[key] = {"id":id,"shadow":record[2],"lod":record[3],"xforms":[]}
		var list: Array = batches[key].xforms
		var flat: PackedFloat32Array = record[4]
		for i in range(0,flat.size(),12):
			list.append(Transform3D(Vector3(flat[i],flat[i+1],flat[i+2]),Vector3(flat[i+3],flat[i+4],flat[i+5]),
				Vector3(flat[i+6],flat[i+7],flat[i+8]),Vector3(flat[i+9],flat[i+10],flat[i+11])))
		stats.instances += flat.size()/12

## The bake's fingerprints of this map's code (survival_bake.gd ground_fits, rim_fits). An exported
## game cannot read its scripts' text, so it compares what the code gives now with what it gave when
## the bake was made: at fixed points, and for a short seeded run of the rim block.
const PROBE_SEED := 20261015
const PROBE_POINTS := 48
const PROBE_WATER_POINTS := 12
const RIM_PROBE_COUNT := 3

## The ground grid, and at PROBE_POINTS grid vertices the height, normal and splat colour as the
## ground mesh has them (heights in float32 as it holds them); per water sheet its area, step and
## level, and the shore foam and wet flag at PROBE_WATER_POINTS of its vertices. For the run's layout.
func bake_probe() -> PackedFloat64Array:
	var out := PackedFloat64Array()
	var axis := _grid_axis()
	var count := axis.size()
	out.append_array([count,axis[0],axis[count/2],axis[count-1]])
	var obstacles: Array = state.get("obstacles",spec.obstacles)
	var hazards: Array = state.get("hazards",spec.hazards)
	var pick := RandomNumberGenerator.new()
	pick.seed = PROBE_SEED
	var h := PackedFloat32Array()
	h.resize(5)
	for n in PROBE_POINTS:
		var i := pick.randi_range(1,count-2)
		var j := pick.randi_range(1,count-2)
		h[0] = height(axis[i],axis[j])
		h[1] = height(axis[i-1],axis[j]); h[2] = height(axis[i+1],axis[j])
		h[3] = height(axis[i],axis[j-1]); h[4] = height(axis[i],axis[j+1])
		var normal := _ground_normal(h[1],h[2],axis[i+1]-axis[i-1],h[3],h[4],axis[j+1]-axis[j-1])
		var color := _splat(axis[i],axis[j],h[0],obstacles,hazards)
		out.append_array([h[0],normal.x,normal.y,normal.z,color.r,color.g,color.b,color.a])
	for patch in _water_patches():
		var area: Rect2 = patch[0]
		var step: float = patch[1]
		out.append_array([area.position.x,area.position.y,area.size.x,area.size.y,step,patch[2],1.0 if patch[3] else 0.0])
		var nx := int(ceil(area.size.x/step))+1
		var nz := int(ceil(area.size.y/step))+1
		for n in PROBE_WATER_POINTS:
			var i := pick.randi_range(0,nx-1)
			var j := pick.randi_range(0,nz-1)
			var vertex := _water_vertex(area.position.x+i*step,area.position.y+j*step,patch[2],patch[3])
			out.append_array([vertex.x,vertex.y])
	return out

## The rim block's code in a short run of its own: every entry capped at RIM_PROBE_COUNT (the quarry
## wall's first row over a few metres), from a seeded random state into batches of its own. The
## instances it queues, per batch key. The build's batches, random state and stats are left as they were.
func rim_probe() -> PackedFloat64Array:
	var keep_state := rng.state
	var keep_batches := batches
	var keep_instances: int = stats.instances
	batches = {}
	rng.seed = PROBE_SEED
	for entry: Array in RIM_BLOCK.get(map_id,[]): _rim_entry(entry,RIM_PROBE_COUNT)
	var out := PackedFloat64Array()
	for key: String in batches:
		out.append(key.hash())
		for xf: Transform3D in batches[key].xforms:
			out.append_array([xf.origin.x,xf.origin.y,xf.origin.z,xf.basis.x.x,xf.basis.x.y,xf.basis.x.z,xf.basis.y.y])
	batches = keep_batches
	rng.state = keep_state
	stats.instances = keep_instances
	return out

## The rim block, per map in its order (the build steps the card between entries):
## ["rim", id, count, scale_min, scale_max, min_rim, max_rim, south_ok, opts, spacing] (_scatter_rim),
## ["shore", id, count, scale_min, scale_max] (_shore) and ["cliff"] (_cliff_wall, CLIFF_ROWS).
## Constants, so an exported game sees a change here in the bake's fingerprint (survival_bake.gd).
const RIM_BLOCK := {
	"forest":[["rim","pine_tall",55,0.75,1.1,1.0,8.0,false,{},2.6],["rim","pine_tall",110,0.85,1.25,8.0,30.0,false,{"lod":"low"},2.8],
		["rim","oak_broad",10,0.85,1.05,2.0,8.0,false,{},4.5],["rim","oak_broad",18,0.9,1.2,8.0,26.0,false,{"lod":"low"},4.5],
		["rim","birch_slim",16,0.8,1.05,0.8,8.0,false,{},2.8],["rim","birch_slim",16,0.85,1.15,8.0,24.0,false,{"lod":"low"},2.8],
		["rim","bush_round",50,0.8,1.3,0.0,16.0,true,{"shadow":false},0.0],["rim","fern_clump",60,0.8,1.3,0.0,14.0,true,{"shadow":false},0.0],
		["shore","reeds",70,0.8,1.2]],
	"quarry":[["cliff"],["rim","dead_tree",14,0.8,1.2,6.0,26.0,false,{"lod":"low"},5.0],
		["rim","dry_shrub",70,0.8,1.4,0.0,24.0,true,{"shadow":false},0.0],["rim","sandstone_boulder",40,0.5,1.1,0.8,20.0,true,{"lod":"low"},0.0]],
	"frost":[["rim","snow_pine",60,0.75,1.1,1.0,8.0,false,{},2.6],["rim","snow_pine",120,0.85,1.25,8.0,30.0,false,{"lod":"low"},2.8],
		["rim","snow_boulder",26,0.6,1.3,0.8,22.0,true,{"lod":"low"},0.0],["rim","frost_shrub",40,0.8,1.2,0.0,14.0,true,{"shadow":false},0.0],
		["rim","ice_crystal",10,0.5,0.9,2.0,14.0,false,{},0.0]]}
## Quarry wall rows: [offset beyond the square, gap, scale_min, scale_max, lod].
const CLIFF_ROWS := [[1.2,2.1,1.5,2.2,"auto"],[5.2,2.6,1.4,2.1,"auto"],[9.5,3.2,1.5,2.3,"low"],[14.0,4.0,1.6,2.4,"low"]]

func _scatter_rim_block() -> void:
	for entry: Array in RIM_BLOCK.get(map_id,[]):
		await LoadPace.step("scatter")
		_rim_entry(entry,-1)

## One rim block entry; `most` >= 0 caps its count (the fingerprint's short run, rim_probe()).
func _rim_entry(entry: Array, most: int) -> void:
	match String(entry[0]):
		"rim": _scatter_rim(entry[1],int(entry[2]) if most < 0 else mini(int(entry[2]),most),entry[3],entry[4],entry[5],entry[6],entry[7],entry[8],entry[9])
		"shore": _shore(entry[1],int(entry[2]) if most < 0 else mini(int(entry[2]),most),entry[3],entry[4])
		"cliff": _cliff_wall(CLIFF_ROWS if most < 0 else CLIFF_ROWS.slice(0,1),INF if most < 0 else float(most)*3.0)

func _scatter_inside_block() -> void:
	match map_id:
		"forest":
			await LoadPace.step("scatter")
			_scatter_inside("bush_round",16,0.7,1.0,1.4,{"shadow":false},true,0.9)
			await LoadPace.step("scatter")
			_scatter_inside("fern_clump",46,0.7,1.15,0.6,{"shadow":false},true)
			await LoadPace.step("scatter")
			_scatter_inside("mushroom_cluster",24,0.6,1.0,0.4,{"shadow":false},true)
			await LoadPace.step("scatter")
			_scatter_inside("tree_stump",6,0.7,0.9,1.0,{},true,0.6)
			for flower in ["white_flowers","yellow_flowers","pink_flowers"]:
				await LoadPace.step("scatter")
				_scatter_inside(flower,14,0.55,0.8,0.3,{"shadow":false},true)
		"quarry":
			await LoadPace.step("scatter")
			_scatter_inside("dry_shrub",26,0.6,1.0,0.8,{"shadow":false},true,0.6)
			await LoadPace.step("scatter")
			_scatter_inside("sandstone_boulder",12,0.14,0.22,0.5,{"shadow":false},true)
			await LoadPace.step("scatter")
			_scatter_inside("cut_blocks",4,0.18,0.24,1.2,{},true,1.0)
		"frost":
			await LoadPace.step("scatter")
			_scatter_inside("frost_shrub",18,0.6,0.95,1.0,{"shadow":false},true,0.7)
			await LoadPace.step("scatter")
			_scatter_inside("ice_crystal",8,0.22,0.32,0.6,{"shadow":false},true)
			await LoadPace.step("scatter")
			_snow_fences()

func _shore(id: String, count: int, smin: float, smax: float) -> void:
	var placed := 0
	for attempt in count*10:
		if placed >= count: break
		var p := Vector2(rng.randf_range(-FAR+6,FAR-6),rng.randf_range(bounds,bounds+8.0))
		var y := height(p.x,p.y)
		if absf(y-float(look.water_y)) > 0.3: continue
		if _instance(id,Vector3(p.x,y-0.05,p.y),rng.randf()*TAU,rng.randf_range(smin,smax),{"shadow":false}): placed += 1

## Quarry walls: rows of sandstone shelves along the terrace risers (north, east, west; the south
## stays open as the cart road out) sell the cut pit; scattered blocks fill the upper ledges.
func _cliff_wall(rows: Array = CLIFF_ROWS, reach := INF) -> void:
	for row in rows:
		var offset: float = row[0]
		var gap: float = row[1]
		var edge := bounds+1.3+offset
		var t := -FAR
		while t < minf(FAR,-FAR+reach):
			for side in 3:
				var p := Vector2(t,-edge) if side == 0 else Vector2(edge*(1.0 if side == 1 else -1.0),t)
				if p.y > bounds+2.0 or absf(p.x) > FAR-2.0 or absf(p.y) > FAR-2.0: continue
				if side == 0 and absf(p.x) > edge+1.0: continue
				p += Vector2(rng.randf_range(-0.6,0.6),rng.randf_range(-0.6,0.6))
				if rim_distance(p.x,p.y) < 0.6: continue
				_instance("sandstone_cliff",Vector3(p.x,height(p.x,p.y)-1.1,p.y),rng.randf()*TAU,rng.randf_range(row[2],row[3]),{"lod":row[4]})
			t += gap*rng.randf_range(0.8,1.2)

## Snow fences run along the basin's edge just outside the walkable square (north, east, west), in
## broken runs with gaps where the trails leave the basin.
func _snow_fences() -> void:
	var edge := bounds+1.7
	for side in 3:
		var t := -edge
		var run := 0
		while t < edge:
			var p := Vector2(t,-edge) if side == 0 else Vector2(edge*(1.0 if side == 1 else -1.0),t)
			var yaw := 0.0 if side == 0 else PI*0.5
			var gap := path_distance(p.x,p.y) < 1.6 or (run > 3 and rng.randf() < 0.35)
			if gap:
				run = 0
			else:
				run += 1
				var q := p+Vector2(rng.randf_range(-0.1,0.1),rng.randf_range(-0.15,0.15))
				_instance("snow_fence",Vector3(q.x,height(q.x,q.y)-0.03,q.y),yaw+rng.randf_range(-0.06,0.06),0.95)
			t += 2.25

func _grass() -> void:
	var blade := _tuft_mesh()
	var mat := ShaderMaterial.new()
	mat.shader = GRASS_SHADER
	mat.set_shader_parameter("low_color",Color(look.grass_low))
	mat.set_shader_parameter("high_color",Color(look.grass_high))
	mat.set_shader_parameter("frost",float(look.snow))
	materials.append(mat)
	var chunks: Dictionary = await _grass_chunks()
	for key in chunks:
		await LoadPace.step("grass chunk")
		var list: Array = chunks[key]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_custom_data = true
		mm.mesh = blade
		mm.instance_count = list.size()
		for i in list.size():
			mm.set_instance_transform(i,list[i][0])
			mm.set_instance_custom_data(i,list[i][1])
		var node := MultiMeshInstance3D.new()
		node.multimesh = mm
		node.material_override = mat
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(node)
		stats.multimeshes += 1
		stats.instances += list.size()

## The grass tufts per CHUNK cell (Vector2i): [transform, custom data] in the order they are placed.
## They draw from the map's rng after the inside scatter, so they change with the run's nodes.
func _grass_chunks() -> Dictionary:
	var chunks := {}
	var total := int(look.grass)+int(look.rim_grass)
	for i in total*2:
		if i >= total*2: break
		if i % 256 == 255: await LoadPace.step("grass")
		var inside := i < int(look.grass)*2
		var p := _sample_inside() if inside else _sample_rim(0.0,20.0,true)
		if p.x == INF: continue
		var y := height(p.x,p.y)
		if y < float(look.water_y)+0.1: continue
		if map_id == "forest" and pond_distance(p.x,p.y) < 0.3: continue
		# Tufts gather in drifts (by noise) instead of carpeting the whole lawn.
		if noise.get_noise_2d(p.x*0.9+31.0,p.y*0.9) < -0.05 and rng.randf() < 0.85: continue
		if inside:
			if path_distance(p.x,p.y) < 0.15 or Vector2(p.x,p.y).length() < 3.6: continue
			var skip := false
			for h in state.get("hazards",spec.hazards):
				if Vector2(p.x-h.x,p.y-h.z).length() < float(h.radius)+0.3: skip = true; break
			if skip: continue
		var key := Vector2i(int(floor(p.x/CHUNK)),int(floor(p.y/CHUNK)))
		if not chunks.has(key): chunks[key] = []
		var s := rng.randf_range(0.7,1.3)
		chunks[key].append([Transform3D(Basis(Vector3.UP,rng.randf()*TAU).scaled(Vector3(s,s*rng.randf_range(0.8,1.25),s)),Vector3(p.x,y-0.02,p.y)),Color(rng.randf(),rng.randf(),0,0)])
	return chunks

func _tuft_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var r := RandomNumberGenerator.new(); r.seed = 5
	for i in 9:
		var a := i*TAU/9.0+r.randf()*0.4
		var d := Vector3(cos(a),0,sin(a))
		var base := d*r.randf_range(0.02,0.09)
		var h := r.randf_range(0.12,0.24)
		var lean := d*r.randf_range(0.05,0.11)
		var side := Vector3(-d.z,0,d.x)*0.022
		st.set_normal(Vector3.UP)
		st.set_color(Color(0,0,0)); st.add_vertex(base-side)
		st.set_color(Color(0,0,0)); st.add_vertex(base+side)
		st.set_color(Color(1,0,0)); st.add_vertex(base+lean+Vector3(0,h,0))
	if map_id == "forest":
		for i in 2:
			var c := Vector3(r.randf_range(-0.06,0.06),r.randf_range(0.2,0.28),r.randf_range(-0.06,0.06))
			for k in 4:
				var a := k*TAU/4.0
				st.set_normal(Vector3.UP)
				st.set_color(Color(1,1,0)); st.add_vertex(c)
				st.set_color(Color(1,1,0)); st.add_vertex(c+Vector3(cos(a),0.15,sin(a))*0.045)
				st.set_color(Color(1,1,0)); st.add_vertex(c+Vector3(cos(a+1.2),0.15,sin(a+1.2))*0.045)
	return st.commit()

# ------------------------------------------------------------------ particles / atmosphere
func _build_particles() -> void:
	var motes := CPUParticles3D.new()
	motes.name = "Motes"
	motes.amount = 150 if map_id == "frost" else 50
	motes.lifetime = 9.0 if map_id == "frost" else 7.0
	motes.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	motes.emission_box_extents = Vector3(18,4,16) if map_id == "frost" else Vector3(15,1.6,12)
	motes.direction = Vector3(0.3,-1,0.1) if map_id == "frost" else Vector3(1,0.15,0.3)
	motes.spread = 15
	motes.initial_velocity_min = 0.5 if map_id == "frost" else 0.08
	motes.initial_velocity_max = 0.9 if map_id == "frost" else 0.25
	motes.gravity = Vector3.ZERO
	motes.scale_amount_min = 0.025 if map_id == "frost" else 0.02
	motes.scale_amount_max = 0.06 if map_id == "frost" else 0.04
	var sm := SphereMesh.new(); sm.radius = 0.5; sm.height = 1.0; sm.radial_segments = 6; sm.rings = 3
	motes.mesh = sm
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = {"forest":Color("f4f0b0"),"quarry":Color("ffe0b0"),"frost":Color("f6fbff")}[map_id]
	motes.material_override = mat
	motes.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	motes.position.y = 6.0 if map_id == "frost" else 1.4
	add_child(motes)
	follow_particles.append(motes)
	if map_id == "forest":
		var flies := CPUParticles3D.new()
		flies.name = "Fireflies"
		flies.amount = 40; flies.lifetime = 6.0
		flies.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
		flies.emission_box_extents = Vector3(14,1.0,11)
		flies.direction = Vector3(0,1,0); flies.spread = 180
		flies.initial_velocity_min = 0.05; flies.initial_velocity_max = 0.2
		flies.gravity = Vector3.ZERO
		flies.scale_amount_min = 0.05; flies.scale_amount_max = 0.08
		flies.mesh = sm
		var glow := StandardMaterial3D.new()
		glow.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		glow.albedo_color = Color("e8ff8a")
		flies.material_override = glow
		flies.position.y = 1.0
		flies.emitting = false
		flies.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(flies)
		follow_particles.append(flies)

# ------------------------------------------------------------------ resources (Tripo visuals)
const RESOURCE_MODELS := {
	"forest":{"tree":["pine_tall",0.6],"stone":["stone_pile",0.82],"berry":["berry_bush",0.95],"fiber":["fiber_grass",0.9],"stump":["tree_stump",0.72]},
	"quarry":{"tree":["birch_slim",0.72],"stone":["stone_pile",0.85],"berry":["berry_bush",0.9],"fiber":["fiber_grass",0.85],"stump":["tree_stump",0.66]},
	"frost":{"tree":["snow_pine",0.62],"stone":["stone_pile",0.82],"berry":["frost_shrub",0.95],"fiber":["fiber_grass",0.82],"stump":["tree_stump",0.7]},
}

## Dress one resource root (main.gd's node at the resource position). Trees get a hidden "Stump" child
## that main.gd shows when the tree is depleted.
func dress_resource(root: Node3D, kind: String) -> void:
	if root.has_meta("survival_dressed"): return
	root.set_meta("survival_dressed",true)
	var models: Dictionary = RESOURCE_MODELS[map_id]
	if not models.has(kind): return
	for child in root.get_children():
		root.remove_child(child)
		child.queue_free()
	var pick: Array = models[kind]
	var entry := _prop(pick[0],false)
	if not entry.ok: return
	var h := absi(hash(Vector2i(roundi(root.position.x*10.0),roundi(root.position.z*10.0))))
	var model := MeshInstance3D.new()
	model.name = "Model"
	model.mesh = entry.mesh
	if entry.material: model.material_override = entry.material
	model.rotation.y = float(h%628)/100.0
	model.scale = Vector3.ONE*float(pick[1])*(0.92+float(h%17)/100.0)
	root.add_child(model)
	if kind == "tree":
		var stump_entry := _prop(models.stump[0],false)
		if stump_entry.ok:
			var stump := MeshInstance3D.new()
			stump.name = "Stump"
			stump.mesh = stump_entry.mesh
			if stump_entry.material: stump.material_override = stump_entry.material
			stump.scale = Vector3.ONE*float(models.stump[1])
			stump.visible = false
			root.add_child(stump)
	stats.resource_visuals += 1

## main.gd builds a Node3D per resource (meta "kind") with primitive meshes; swap in the Tripo models.
func _adopt_resources() -> void:
	var world := get_parent()
	if world == null: return
	for child in world.get_children():
		if child is Node3D and child.has_meta("kind") and not child.has_meta("survival_dressed"):
			dress_resource(child,str(child.get_meta("kind")))

# ------------------------------------------------------------------ per frame
func _process(delta: float) -> void:
	_bind()
	var run: Dictionary = state
	if is_instance_valid(app) and app.get("run") is Dictionary and not (app.get("run") as Dictionary).is_empty():
		run = app.get("run")
	_want_night_species(run,delta)
	_advance_time(run,delta)
	if is_instance_valid(app) and app.get("player") is Node3D and is_instance_valid(app.get("player")):
		focus = (app.get("player") as Node3D).global_position
	var cam_pos := camera.global_position if is_instance_valid(camera) else Vector3(0,1000,0)
	for mat in materials:
		mat.set_shader_parameter("focus",focus)
		mat.set_shader_parameter("camera_world",cam_pos)
		mat.set_shader_parameter("night",night)
		mat.set_shader_parameter("haze_color",_haze())
	for mat in glow_materials:
		mat.set_shader_parameter("glow",float(mat.get_meta("glow_base",0.0))*(0.25+night*1.0))
	for p in follow_particles:
		if is_instance_valid(p): p.global_position = Vector3(focus.x,p.global_position.y,focus.z-2.0)
	var flies := get_node_or_null("Fireflies") as CPUParticles3D
	if flies: flies.emitting = night > 0.5
	if is_instance_valid(camera):
		var want_low := camera.size > LOD_ZOOM
		if want_low != low_active:
			low_active = want_low
			for m in multimeshes: m.mm.mesh = m.low if low_active else m.high
		if not cover_multimeshes.is_empty():
			# The village's rule (environment_layout.gd _update_prop_lods) for an orthographic camera.
			var pixels := get_viewport().get_visible_rect().size.y*GameSettings.lod_multiplier()
			for m in cover_multimeshes:
				var projected: float = m.size*pixels/maxf(camera.size,0.1)
				var use_low := projected < (COVER_LIMITS.y if m.low_active else COVER_LIMITS.x)
				if use_low != bool(m.low_active):
					m.low_active = use_low
					m.mm.mesh = m.low if use_low else m.high
	_apply_grade(false)
	adopt_wait -= delta
	if adopt_wait <= 0.0:
		adopt_wait = 0.15
		_adopt_resources()

func _bind() -> void:
	if is_instance_valid(app): return
	# main.gd (or a test harness) is the nearest ancestor with a camera property.
	var scene: Node = get_parent()
	while scene != null and not (scene.get("camera") is Camera3D):
		scene = scene.get_parent()
	if scene == null: return
	app = scene
	var cam = scene.get("camera")
	camera = cam if cam is Camera3D else get_viewport().get_camera_3d()
	var e = scene.get("environment")
	env = e if e is Environment else null
	var s = scene.get("sun")
	sun = s if s is DirectionalLight3D else null
	if env == null:
		var we := scene.find_children("*","WorldEnvironment",true,false)
		if not we.is_empty(): env = (we[0] as WorldEnvironment).environment
	if sun == null:
		var lights := scene.find_children("*","DirectionalLight3D",true,false)
		if not lights.is_empty(): sun = lights[0]

## The stage's hour from the run's day_progress (eased; delta <= 0 snaps): night and dusk for the
## shaders, the colours _apply_grade sets.
func _advance_time(run: Dictionary, delta: float) -> void:
	daytime.advance(float(run.get("day_progress",0.3)),bool(run.get("night",false)),bool(run.get("boss_night",false)),delta)
	night = daytime.night
	dusk = daytime.dusk

func _haze() -> Color:
	return daytime.haze

## The map's grade at the stage's hour. main.gd lerps its own survival values every frame; this
## node runs after it (process_priority) and sets the map's grade instead. The night colour grade
## (daylight.gd's curve, a share of it) follows the graphics setting as in the village.
func _apply_grade(_snap: bool) -> void:
	if env == null or sun == null:
		_bind()
	if env != null:
		env.background_mode = Environment.BG_COLOR
		env.background_color = daytime.background
		env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		env.ambient_light_color = daytime.ambient_color
		env.ambient_light_energy = daytime.ambient_energy
		env.fog_enabled = false
		# Stepped, so the curve's texture is redrawn a few times over an evening, not every frame.
		var grade := snappedf(daytime.grade,1.0/32.0) if GameSettings.night_grade() else 0.0
		env.adjustment_enabled = daytime.saturation < 0.995 or grade > 0.002
		env.adjustment_saturation = daytime.saturation
		Daylight._grade(env,grade)
	if sun != null:
		sun.light_color = daytime.sun_color
		sun.light_energy = daytime.sun_energy
		sun.rotation_degrees = daytime.sun_rotation
	# The camp fire burns brighter and reaches further as the light goes.
	if not is_instance_valid(fire_light): fire_light = _find_fire_light()
	if fire_light != null:
		fire_light.light_energy = float(fire_light.get_meta("survival_base_energy"))*(1.0+FIRE_NIGHT_GAIN*night)
		fire_light.omni_range = float(fire_light.get_meta("survival_base_range"))*(1.0+0.2*night)

## Night multiplier on the camp fire's light (main.gd flame).
const FIRE_NIGHT_GAIN := 0.6

func _find_fire_light() -> OmniLight3D:
	var flame = app.get(&"flame") if is_instance_valid(app) else null
	if not is_instance_valid(flame) or not (flame is Node3D): return null
	for child in (flame as Node3D).get_children():
		if child is OmniLight3D:
			if not child.has_meta("survival_base_energy"):
				child.set_meta("survival_base_energy",child.light_energy)
				child.set_meta("survival_base_range",child.omni_range)
			return child
	return null

func report() -> Dictionary:
	var out := stats.duplicate()
	out["map"] = map_id
	out["materials"] = materials.size()
	return out
