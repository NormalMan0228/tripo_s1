extends Node
## NPC dialogue "babble": Animal-Crossing-style syllable blips that follow the typewriter
## reveal of a dialogue line. Each speaker has a pre-rendered syllable bank with its own
## pitch, formants and timbre (tools/make_creature_sfx.py); shadow folk are breathier,
## hollow and softly chorused. The syllable for each revealed character comes from the
## text itself: Hangul is decomposed (initial consonant -> onset, medial vowel -> vowel),
## Latin letters map to the nearest vowel/consonant class, anything else hashes to a slot.
## Questions rise at the end, exclamations sit higher and louder, lines drift down a little.
##
##   const VoiceBabble = preload("res://scripts/voice_babble.gd")
##   VoiceBabble.speak(app, speaker_id: String, text: String, speed := 0.0, label: Label = null)
##       speaker_id: "naru", "sora", "moru", "haeru", a shadow folk id ("postman", "sweeper",
##         "fisher", "kid", "farmer", "regular", "miller", "stargazer", "gardener", "shopkeeper",
##         "scout", "lamplighter", "gentleman", "poet", "stroller"), "villager"/"shadow"
##         (generic), or a portrait path / cast name (resolve() below). "" = silent (signs).
##       label: pass the typing Label and the blips follow label.visible_ratio exactly
##         (skipping to the full line stops the babble; a new text, hiding or freeing the
##         label ends it). Without a label the text is "typed" at `speed` characters per
##         second (0 = the dialogue box rule: clampf(len*0.028, .25, 1.6) s for the line).
##       At most one syllable per voice gap (~13-16 per second) however fast the text types.
##   VoiceBabble.stop(hard := false)   no more syllables (hard also cuts the one sounding)
##   VoiceBabble.resolve(cast_or_id, title := "") -> String   voice id ("" when silent)
##   VoiceBabble.speaking() -> bool,  VoiceBabble.syllables_played: int (tests)
## Bus "Voice" when the project has it, else "Master". Banks are cached per voice.
const DIR := "res://assets/sfx/voice/"
## Bank layout written by tools/make_creature_sfx.py: slot = onset * VOWELS.size() + vowel.
const SLOT := 0.115
const ONSETS := ["v", "n", "p", "s"]
const VOWELS := ["a", "e", "i", "o", "u", "eo", "eu"]
## Hangul initials ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ -> onset (0 vowel, 1 nasal/liquid, 2 plosive, 3 fricative)
const INITIAL_ONSET := [2, 2, 1, 2, 2, 1, 1, 2, 2, 3, 3, 0, 3, 3, 3, 2, 2, 2, 3]
## Hangul medials ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ -> vowel index
const MEDIAL_VOWEL := [0, 1, 0, 1, 5, 1, 5, 1, 3, 0, 1, 1, 3, 4, 5, 1, 2, 4, 6, 2, 2]
## Voice: gap = minimum seconds between syllables, db = trim, shadow = drifting pitch.
const VOICES := {
	"naru": {"gap": 0.068, "db": 0.0}, "sora": {"gap": 0.078, "db": -0.5}, "moru": {"gap": 0.085, "db": 0.5},
	"haeru": {"gap": 0.082, "db": 0.0}, "villager": {"gap": 0.074, "db": 0.0},
	"postman": {"gap": 0.066, "db": 0.0, "shadow": true}, "sweeper": {"gap": 0.082, "db": 0.0, "shadow": true},
	"fisher": {"gap": 0.085, "db": 0.0, "shadow": true}, "kid": {"gap": 0.062, "db": -0.5, "shadow": true},
	"farmer": {"gap": 0.08, "db": 0.0, "shadow": true}, "regular": {"gap": 0.076, "db": 0.0, "shadow": true},
	"miller": {"gap": 0.09, "db": 0.5, "shadow": true}, "stargazer": {"gap": 0.086, "db": 0.0, "shadow": true},
	"gardener": {"gap": 0.076, "db": 0.0, "shadow": true}, "shopkeeper": {"gap": 0.064, "db": 0.0, "shadow": true},
	"scout": {"gap": 0.068, "db": 0.0, "shadow": true}, "lamplighter": {"gap": 0.08, "db": 0.0, "shadow": true},
	"gentleman": {"gap": 0.092, "db": 0.5, "shadow": true}, "poet": {"gap": 0.086, "db": 0.0, "shadow": true},
	"stroller": {"gap": 0.088, "db": 0.0, "shadow": true}, "shadow": {"gap": 0.078, "db": 0.0, "shadow": true},
}
const NAMES := {"나루": "naru", "소라": "sora", "모루": "moru", "해루": "haeru"}
const BASE_DB := -15.0
const PLAYERS := 3
## A reveal that jumps this many characters in one frame is a skip: the babble stops.
const SKIP_JUMP := 10

static var instance = null
static var banks := {}
static var syllables_played := 0

var players: Array[AudioStreamPlayer] = []
var stop_at: Array[float] = []
var next := 0
var voice := ""
var text := ""
var label: Label
var cps := 30.0
var started := 0.0
var cursor := 0
var last_emit := -10.0
var word_start := true
var active := false
var pitch_shape := PackedFloat32Array()
var loud := PackedByteArray()
var rng := RandomNumberGenerator.new()

static func speak(_app, speaker_id: String, line: String, speed := 0.0, typing_label: Label = null) -> void:
	var id := resolve(speaker_id)
	var node = _node()
	if node == null: return
	if id.is_empty() or bank(id).is_empty():
		node.active = false
		return
	node._start(id, line, speed, typing_label)

static func stop(hard := false) -> void:
	if not is_instance_valid(instance): return
	instance.active = false
	if hard:
		for p in instance.players: p.stop()

static func speaking() -> bool:
	return is_instance_valid(instance) and instance.active

## Voice id for a cast name, resident id, portrait path ("res://assets/ui/shadow_postman.png")
## or, failing those, a dialogue title ("나루 · 길잡이", "수상한 그림자 · …"). Objects with
## no cast (signs, mailboxes, boards) return "" and stay silent.
static func resolve(cast_or_id: String, title := "") -> String:
	var id := cast_or_id.strip_edges().to_lower()
	if id.contains("/") or id.contains("."): id = id.get_file().get_basename()
	if id.begins_with("shadow_"): id = id.substr(7)
	if VOICES.has(id): return id
	for name in NAMES:
		if title.begins_with(name): return NAMES[name]
	if title.contains("그림자"): return "shadow"
	return "" if id.is_empty() else "villager"

## The voice's 28 syllable streams, sliced once from its PCM bank. A compressed import
## falls back to the whole bank (played from the slot offset and stopped after SLOT).
static func bank(id: String) -> Array:
	if banks.has(id): return banks[id]
	var list := []
	var path := DIR+id+".wav"
	if ResourceLoader.exists(path):
		var whole := load(path) as AudioStreamWAV
		if whole != null and whole.format == AudioStreamWAV.FORMAT_16_BITS and not whole.stereo:
			var data := whole.data
			var rate := float(whole.mix_rate)
			for k in ONSETS.size()*VOWELS.size():
				var a := int(round(k*SLOT*rate))*2
				var b := mini(int(round((k+1)*SLOT*rate))*2, data.size())
				var part := AudioStreamWAV.new()
				part.format = AudioStreamWAV.FORMAT_16_BITS
				part.mix_rate = whole.mix_rate
				part.data = data.slice(a, b)
				list.append(part)
		elif whole != null:
			list = [whole]
	banks[id] = list
	return list

static func _node() -> Node:
	if is_instance_valid(instance) and instance.is_inside_tree(): return instance
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null or tree.root == null: return null
	instance = tree.root.get_node_or_null("VoiceBabble")
	if instance == null:
		instance = load("res://scripts/voice_babble.gd").new()
		instance.name = "VoiceBabble"
		tree.root.add_child(instance)
	return instance

func _init() -> void:
	# Dialogue can sit over a paused tree; the babble keeps time regardless.
	process_mode = Node.PROCESS_MODE_ALWAYS
	rng.randomize()

func _ready() -> void:
	var bus := &"Voice" if AudioServer.get_bus_index("Voice") >= 0 else &"Master"
	for i in PLAYERS:
		var p := AudioStreamPlayer.new()
		p.bus = bus
		add_child(p)
		players.append(p)
		stop_at.append(0.0)

func _exit_tree() -> void:
	for p in players:
		p.stop()
		p.stream = null

func _start(id: String, line: String, speed: float, typing_label: Label) -> void:
	voice = id
	label = typing_label
	text = typing_label.text if is_instance_valid(typing_label) else line
	var length := maxi(text.length(), 1)
	cps = speed if speed > 0.0 else length/clampf(length*0.028, 0.25, 1.6)
	started = Time.get_ticks_msec()*0.001
	cursor = 0
	word_start = true
	last_emit = -10.0
	_shape()
	active = not text.strip_edges().is_empty()

## Per-character pitch: a gentle fall over each sentence, a rise into "?", a lift on "!".
func _shape() -> void:
	var n := text.length()
	pitch_shape.resize(n)
	loud.resize(n)
	var begin := 0
	for i in n:
		var c := text[i]
		if c in "?!.…~\n" or i == n-1:
			var size := i-begin+1
			for j in range(begin, i+1):
				var u := float(j-begin)/maxf(size-1, 1.0)
				var p := 1.0-0.045*u
				if c == "?": p += 0.17*smoothstep(0.55, 1.0, u)
				elif c == "!": p += 0.07
				pitch_shape[j] = p
				loud[j] = 1 if c == "!" else 0
			begin = i+1

func _process(_delta: float) -> void:
	var now := Time.get_ticks_msec()*0.001
	for i in players.size():
		if stop_at[i] > 0.0 and now >= stop_at[i]:
			players[i].stop()
			stop_at[i] = 0.0
	if not active: return
	var revealed := 0
	if label != null:
		if not is_instance_valid(label) or not label.is_visible_in_tree() or label.text != text:
			active = false
			return
		revealed = int(floor(label.visible_ratio*text.length()+0.001))
		if label.visible_ratio < 0.0: revealed = text.length()
	else:
		revealed = int((now-started)*cps)
	revealed = mini(revealed, text.length())
	if revealed-cursor >= SKIP_JUMP:
		# The player skipped ahead: no catch-up chatter.
		cursor = revealed
		active = cursor < text.length()
		return
	var gap: float = VOICES[voice].gap
	while cursor < revealed:
		var i := cursor
		cursor += 1
		var code := text.unicode_at(i)
		if not _voiced(code):
			if code == 32 or code == 10: word_start = true
			continue
		if now-last_emit >= gap or (word_start and now-last_emit >= gap*0.6):
			_emit(i, code)
			last_emit = now
			word_start = false
			break
		word_start = false
	if cursor >= text.length(): active = false

static func _voiced(code: int) -> bool:
	if code >= 0xAC00 and code <= 0xD7A3: return true
	if (code >= 65 and code <= 90) or (code >= 97 and code <= 122): return true
	if code >= 48 and code <= 57: return true
	return code > 0x2E80 and code != 0x3000  # CJK and kana

## Bank slot for one character.
func _slot(i: int, code: int) -> Vector2i:
	if code >= 0xAC00 and code <= 0xD7A3:
		var k := code-0xAC00
		return Vector2i(INITIAL_ONSET[k/588], MEDIAL_VOWEL[(k % 588)/28])
	var ch := char(code).to_lower()
	var vowel_of := {"a": 0, "e": 1, "i": 2, "o": 3, "u": 4, "y": 2}
	if vowel_of.has(ch): return Vector2i(0, vowel_of[ch])
	if (code >= 65 and code <= 90) or (code >= 97 and code <= 122):
		var onset := 2 if ch in "bdgkptcqx" else (3 if ch in "szfhjv" else 1)
		# Borrow the vowel that follows in the word, as a spoken syllable would.
		for j in range(i+1, mini(i+4, text.length())):
			var next_ch := text[j].to_lower()
			if vowel_of.has(next_ch): return Vector2i(onset, vowel_of[next_ch])
		return Vector2i(onset, 6)
	return Vector2i(code % ONSETS.size(), (code/ONSETS.size()) % VOWELS.size())

func _emit(i: int, code: int) -> void:
	var list := bank(voice)
	if list.is_empty(): return
	var at := _slot(i, code)
	var k := at.x*VOWELS.size()+at.y
	var spec: Dictionary = VOICES[voice]
	# Each character keeps its own small pitch offset (same letter, same note).
	var detune := float((code*2654435761) % 1000)/1000.0-0.5
	var pitch := pitch_shape[i] if i < pitch_shape.size() else 1.0
	pitch *= 1.0+detune*0.09
	if code >= 0xAC00 and code <= 0xD7A3 and (code-0xAC00) % 28 != 0: pitch *= 0.985
	if spec.get("shadow", false): pitch *= 1.0+0.025*sin(Time.get_ticks_msec()*0.0021)
	var db := BASE_DB+float(spec.db)+rng.randf_range(-1.0, 1.0)+(1.5 if i < loud.size() and loud[i] == 1 else 0.0)
	var p := players[next]
	var slot_index := next
	next = (next+1) % players.size()
	p.stop()
	p.volume_db = db
	p.pitch_scale = clampf(pitch, 0.7, 1.5)
	if list.size() > 1:
		p.stream = list[k]
		p.play()
		stop_at[slot_index] = 0.0
	else:
		p.stream = list[0]
		p.play(k*SLOT)
		stop_at[slot_index] = Time.get_ticks_msec()*0.001+SLOT/p.pitch_scale
	syllables_played += 1
