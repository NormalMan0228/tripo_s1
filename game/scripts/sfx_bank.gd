extends RefCounted
## Runtime take picker for sound families (tools/sfx): one event is the bare original
## <base>.wav (when there is one) plus <base>_1.wav, <base>_2.wav ... Static API, no class_name
## (PCK patches):
##   const SfxBank = preload("res://scripts/sfx_bank.gd")
##   SfxBank.play_on(voice, "ui/hover", -4.0)                    # pick + jitter + play
##   var take: AudioStream = SfxBank.pick("res://assets/sfx/combat/hit_flesh")
##   voice.pitch_scale = base_pitch*SfxBank.pitch(0.05)          # 0.95..1.05
##   voice.volume_db = base_db+SfxBank.db(1.0)                   # +-1 dB
##
## base: "res://assets/sfx/<dir>/<event>" or the short "<dir>/<event>" (ROOT is prefixed); a
##   trailing ".wav" is ignored.
## Discovery (paths / count / has): probes ResourceLoader.exists(), which also sees the import
##   remaps of an exported pack (DirAccess lists .import files there, not .wav). Counts up from
##   _1, tolerates one missing index, stops at the second miss in a row or MAX_TAKES. Cached per
##   base. Only imported WAVs exist for the engine: run the importer after adding takes.
## Picking (pick / pick_path): a shuffle bag per base. Every take plays once per cycle in random
##   order; a new cycle never starts with the take that just played, and with 6+ takes the last
##   two played are avoided. Only the chosen take is loaded; loaded streams stay cached.
##   bag_index(key, size) is the same bag for any list (synthesised streams, node pools).
## Jitter: pitch(spread) -> 1 +- spread, db(spread) -> +- spread dB, from one randomized
##   RandomNumberGenerator; set_seed(v) makes bags and jitter reproducible (tests).
## Exit: the caches are static. CleanExit (clean_exit.gd) calls clear() when the tree goes, so no
##   stream is still cached when the engine checks for leaked resources; clear() is also safe to
##   call any time (the next pick reloads).
## Headless: play_on plays like any player (Dummy driver); a caller that must stay silent in
##   tests (RpgUi.sfx) keeps its own headless check.
const ROOT := "res://assets/sfx/"
const MAX_TAKES := 64

static var _paths := {}
static var _bags := {}
static var _streams := {}
static var _rng := RandomNumberGenerator.new()
static var _seeded := false

## Every take of a family: [base.wav] + base_1.wav, base_2.wav ... (empty when none exist).
static func paths(base: String) -> PackedStringArray:
	return _probe(_norm(base))

static func count(base: String) -> int:
	return _probe(_norm(base)).size()

static func has(base: String) -> bool:
	return not _probe(_norm(base)).is_empty()

## The next take's path from the family's shuffle bag, "" when the family has no takes.
static func pick_path(base: String) -> String:
	var key := _norm(base)
	var list := _probe(key)
	if list.is_empty(): return ""
	return list[bag_index(key, list.size())]

## The next take (loaded on first use, then cached), null when the family has no takes.
static func pick(base: String) -> AudioStream:
	var path := pick_path(base)
	return stream(path) if not path.is_empty() else null

## One take by path, loaded once and cached.
static func stream(path: String) -> AudioStream:
	if path.is_empty(): return null
	if _streams.has(path): return _streams[path]
	var loaded: AudioStream = (load(path) as AudioStream) if ResourceLoader.exists(path) else null
	if loaded != null: _streams[path] = loaded
	return loaded

## Loads every take of a family ahead of a burst (avoids a disk read on the first play of each).
static func warm(base: String) -> int:
	var loaded := 0
	for path in paths(base):
		if stream(path) != null: loaded += 1
	return loaded

## Shuffle-bag index in 0..size-1 for `key`: each index once per cycle, no immediate repeat
## across cycles, and with size >= 6 neither of the last two.
static func bag_index(key: String, size: int) -> int:
	if size <= 1: return 0
	var state: Dictionary = _bags.get(key, {})
	var bag: Array = state.get("bag", [])
	var recent: Array = state.get("recent", [])
	if int(state.get("size", size)) != size:
		bag = []
		recent = []
	if bag.is_empty(): bag = _new_bag(size, recent)
	var index: int = bag.pop_front()
	recent.append(index)
	var keep := 2 if size >= 6 else 1
	while recent.size() > keep: recent.pop_front()
	_bags[key] = {"bag": bag, "recent": recent, "size": size}
	return index

## Pitch-scale jitter: 1.0 +- spread.
static func pitch(spread := 0.04) -> float:
	return _pitch(spread)

## Volume jitter in dB: +- spread.
static func db(spread := 1.0) -> float:
	return _db(spread)

## Reproducible bags and jitter from here on (tests); clear() as well to restart the bags.
static func set_seed(value: int) -> void:
	_rng.seed = value
	_seeded = true

## Picks a take of `base` onto an AudioStreamPlayer / 2D / 3D, sets pitch_scale = pitch*jitter
## and volume_db = db+jitter, and plays it (once the player enters the tree if it is not in
## it yet). False when the family has no takes or `player` is not an audio player.
static func play_on(player: Node, base: String, db := 0.0, pitch := 1.0, spread_pitch := 0.04, spread_db := 1.0) -> bool:
	if player == null or not is_instance_valid(player): return false
	if not (player is AudioStreamPlayer or player is AudioStreamPlayer2D or player is AudioStreamPlayer3D): return false
	var chosen := pick(base)
	if chosen == null: return false
	player.set("stream", chosen)
	player.set("pitch_scale", clampf(pitch*_pitch(spread_pitch), 0.25, 4.0))
	player.set("volume_db", db+_db(spread_db))
	if player.is_inside_tree():
		player.call("play")
	else:
		var start := Callable(player, "play")
		if not player.tree_entered.is_connected(start): player.tree_entered.connect(start, CONNECT_ONE_SHOT)
	return true

## Streams currently held by the cache (tests, diagnostics).
static func cached_count() -> int:
	return _streams.size()

## Drops every cache: discovered paths, bags and loaded streams.
static func clear() -> void:
	_paths.clear()
	_bags.clear()
	_streams.clear()

# ------------------------------------------------------------------ internals
static func _norm(base: String) -> String:
	var key := base.strip_edges()
	if key.ends_with(".wav"): key = key.left(key.length()-4)
	if not key.contains("://"): key = ROOT+key.trim_prefix("/")
	return key

static func _probe(key: String) -> PackedStringArray:
	if _paths.has(key): return _paths[key]
	var found := PackedStringArray()
	if ResourceLoader.exists(key+".wav"): found.append(key+".wav")
	var misses := 0
	for n in range(1, MAX_TAKES+1):
		var path := "%s_%d.wav" % [key, n]
		if ResourceLoader.exists(path):
			found.append(path)
			misses = 0
		else:
			misses += 1
			if misses >= 2: break
	_paths[key] = found
	return found

static func _r() -> RandomNumberGenerator:
	if not _seeded:
		_rng.randomize()
		_seeded = true
	return _rng

static func _pitch(spread: float) -> float:
	return 1.0+_r().randf_range(-spread, spread) if spread > 0.0 else 1.0

static func _db(spread: float) -> float:
	return _r().randf_range(-spread, spread) if spread > 0.0 else 0.0

## A shuffled 0..size-1; the first entries are swapped away from the recently played ones:
## position 0 avoids all of `recent`, position 1 the very last one (recent holds 1 or 2).
static func _new_bag(size: int, recent: Array) -> Array:
	var rng := _r()
	var bag := []
	for i in size: bag.append(i)
	for i in range(size-1, 0, -1):
		var j := rng.randi_range(0, i)
		var held = bag[i]
		bag[i] = bag[j]
		bag[j] = held
	var keep := recent.size()
	for pos in mini(keep, size-1):
		var banned := recent.slice(recent.size()-(keep-pos))
		if not banned.has(bag[pos]): continue
		var span := size-pos-1
		var offset := rng.randi_range(0, span-1)
		for k in span:
			var j := pos+1+(offset+k) % span
			if not banned.has(bag[j]):
				var held = bag[pos]
				bag[pos] = bag[j]
				bag[j] = held
				break
	return bag
