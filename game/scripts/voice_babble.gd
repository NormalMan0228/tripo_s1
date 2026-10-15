extends Node
## NPC dialogue "babble": Animal-Crossing-style syllable blips that follow the typewriter
## reveal of a dialogue line. Each speaker has a pre-rendered syllable bank with its own
## pitch, formants and timbre (tools/make_creature_sfx.py); shadow folk are breathier,
## hollow and softly chorused. The syllable for each revealed character comes from the
## text itself: Hangul is decomposed (initial consonant -> onset, medial vowel -> vowel),
## Latin letters map to the nearest vowel/consonant class, anything else hashes to a slot.
## Questions rise at the end, exclamations sit higher and louder, lines drift down a little.
## Variety (tools/sfx/gen_voice.py): every voice also has alternate banks <id>_2.wav and
## <id>_3.wav with the same slot layout but re-synthesised syllables (other contour, length,
## coda, breath, vowel colour). Each syllable takes its slot from a bank drawn out of a
## per-(voice, slot) shuffle bag, so the same syllable never repeats its take back to back,
## and gets +-2 % random pitch on top of the per-character note. Missing alternates are fine.
##
##   const VoiceBabble = preload("res://scripts/voice_babble.gd")
##   VoiceBabble.speak(app, speaker_id: String, text: String, speed := 0.0, label: Label = null)
##       speaker_id: "naru", "sora", "moru", "haeru", a shadow folk id ("postman", "sweeper",
##         "fisher", "kid", "farmer", "regular", "miller", "stargazer", "gardener", "shopkeeper",
##         "scout", "lamplighter", "gentleman", "poet", "stroller"), "villager"/"shadow"
##         (generic), or a portrait path / cast name (resolve() below).
##         "" / "letter" / "sign" (objects with no speaker: signs, mailboxes, boards) = no voice,
##         soft quill/paper ticks follow the typing instead (voice/quill_<n>.wav, UI bus).
##       label: pass the typing Label and the blips follow label.visible_ratio exactly
##         (skipping to the full line stops the babble; a new text, hiding or freeing the
##         label ends it). Without a label the text is "typed" at `speed` characters per
##         second (0 = the dialogue box rule: clampf(len*0.028, .25, 1.6) s for the line).
##         A new dialogue Label (a new conversation) starts with the speaker's greeting bark
##         (greet() below); the first syllables wait for it.
##       At most one syllable per voice gap (~13-16 per second) however fast the text types.
##   VoiceBabble.greet(app, id) -> bool   a short "hiya!" bark in the speaker's register
##       (voice/greet_<register>_<n>.wav); one per voice per GREET_GAP seconds.
##   VoiceBabble.emote(app, id, kind, at := Vector3.INF) -> bool   the bark of an emote
##       bubble: kind "note"/"♪", "exclaim"/"!", "dots"/"…", "heart"/"♥", "mail"/"✉",
##       "sleep"/"zz" (voice/emote_<register>_<kind>_<n>.wav). at = world position: quieter
##       with distance from app.player (or the camera), silent beyond EMOTE_RANGE. Throttled:
##       one per voice per EMOTE_GAP s, EMOTE_SPACING s between any two, never over the
##       speaker's own dialogue.
##   VoiceBabble.stop(hard := false)   no more syllables (hard also cuts the one sounding)
##   VoiceBabble.resolve(cast_or_id, title := "") -> String   voice id ("" when silent)
##   VoiceBabble.speaking() -> bool,  VoiceBabble.syllables_played: int (tests);
##     ticks_played / greets_played / emotes_played count the other sounds.
## Bus "Voice" when the project has it, else "Master" (quill ticks: "UI"). Banks are cached
## per voice; barks and ticks go through sfx_bank.gd (shuffle bags, lazy cached loading).
const SfxBank = preload("res://scripts/sfx_bank.gd")
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
## Random pitch per syllable on top of the per-character note (+-).
const PITCH_JITTER := 0.02

## Barks (tools/sfx/gen_voice.py): every voice speaks in one of four registers; a take is
## pitched by (voice f0 / register f0)^0.6 toward the speaker. [register, voice f0 Hz]
const BARK_VOICES := {
	"naru": ["high", 290.0], "sora": ["high", 360.0], "moru": ["low", 125.0], "haeru": ["mid", 205.0],
	"villager": ["high", 260.0], "postman": ["mid", 235.0], "sweeper": ["mid", 175.0], "fisher": ["low", 155.0],
	"kid": ["child", 430.0], "farmer": ["mid", 185.0], "regular": ["high", 255.0], "miller": ["low", 128.0],
	"stargazer": ["high", 300.0], "gardener": ["high", 275.0], "shopkeeper": ["high", 245.0], "scout": ["mid", 215.0],
	"lamplighter": ["mid", 195.0], "gentleman": ["low", 112.0], "poet": ["high", 245.0], "stroller": ["mid", 170.0],
	"shadow": ["mid", 210.0],
}
const REGISTER_F0 := {"low": 128.0, "mid": 205.0, "high": 285.0, "child": 420.0}
## File name prefixes of the barks and ticks in DIR (everything else there is a syllable bank).
const BARK_PREFIXES := ["emote_", "greet_", "quill_"]
## Emote bubble text or name -> bark kind.
const EMOTE_KINDS := {
	"note": "note", "♪": "note", "♫": "note", "~": "note", "✦": "note", "star": "note", "sparkle": "note",
	"exclaim": "exclaim", "!": "exclaim", "!!": "exclaim", "?": "exclaim", "!?": "exclaim", "?!": "exclaim",
	"dots": "dots", "…": "dots", "...": "dots", "..": "dots",
	"heart": "heart", "♥": "heart", "❤": "heart", "♡": "heart",
	"mail": "mail", "✉": "mail", "letter": "mail",
	"sleep": "sleep", "zz": "sleep", "z": "sleep", "zzz": "sleep", "💤": "sleep",
}
## Level of each emote kind (dB, before the voice trim and distance).
const EMOTE_DB := {"note": -17.0, "exclaim": -14.5, "dots": -17.5, "heart": -15.5, "mail": -15.0, "sleep": -19.0}
const EMOTE_GAP := 3.0
const EMOTE_SPACING := 0.3
## Distance rule: full level within `near` m of the listener, -0.8 dB per m beyond, silent past
## EMOTE_RANGE (player listener) or EMOTE_RANGE + CAMERA_NEAR (camera listener, no app.player).
const EMOTE_RANGE := 26.0
const CAMERA_NEAR := 9.0
const GREET_DB := 1.0
## Seconds before the same voice greets again (a gift dialogue right after a talk stays quiet).
const GREET_GAP := 30.0
## The first syllables of a line wait at most this long for the greeting bark.
const GREET_HOLD := 0.28
## Quill ticks for lines without a speaker.
const QUILL_IDS := ["", "letter", "sign"]
const QUILL_GAP := 0.06
const QUILL_DB := -11.0

static var instance = null
static var banks := {}
static var bank_sets := {}
static var syllables_played := 0
static var ticks_played := 0
static var greets_played := 0
static var emotes_played := 0

var players: Array[AudioStreamPlayer] = []
var stop_at: Array[float] = []
var next := 0
var barks: Array[AudioStreamPlayer] = []
var bark_next := 0
var ticks: Array[AudioStreamPlayer] = []
var tick_next := 0
var voice := ""
var text := ""
var label: Label
var cps := 30.0
var started := 0.0
var cursor := 0
var last_emit := -10.0
var word_start := true
var active := false
var quill := false
var hold_until := 0.0
var hold_voice := ""
var greeted_label := 0
var last_greet := {}
var last_emote := {}
var last_any_emote := -10.0
var pitch_shape := PackedFloat32Array()
var loud := PackedByteArray()
var rng := RandomNumberGenerator.new()

static func speak(_app, speaker_id: String, line: String, speed := 0.0, typing_label: Label = null) -> void:
	var raw := speaker_id.strip_edges().to_lower()
	var id := resolve(speaker_id)
	var node = _node()
	if node == null: return
	if raw in QUILL_IDS:
		node._start_quill(line, speed, typing_label)
		return
	if id.is_empty() or bank(id).is_empty():
		node.active = false
		return
	# A new dialogue box (a new Label) is a new conversation: greet first. Another voice's
	# greeting never holds this line (greet(id) right before speak(id) does).
	if node.hold_voice != id: node.hold_until = 0.0
	if typing_label != null and typing_label.get_instance_id() != node.greeted_label:
		node.greeted_label = typing_label.get_instance_id()
		node._greet(id)
	node._start(id, line, speed, typing_label)

static func stop(hard := false) -> void:
	if not is_instance_valid(instance): return
	instance.active = false
	if hard:
		for p in instance.players: p.stop()
		for p in instance.ticks: p.stop()

static func speaking() -> bool:
	return is_instance_valid(instance) and instance.active

## Greeting bark of a speaker (cast name, resident id or portrait path); false when it is
## silent, greeted within GREET_GAP s, or the register has no takes.
static func greet(_app, id: String) -> bool:
	var voice_id := resolve(id)
	if voice_id.is_empty(): return false
	var node = _node()
	if node == null: return false
	return node._greet(voice_id)

## The bark of an emote bubble (see the header); false when it was skipped.
static func emote(app, id: String, kind: String, at := Vector3.INF) -> bool:
	var node = _node()
	if node == null: return false
	return node._emote(app, id, kind, at)

## Bark kind of an emote bubble's text or name ("" when it has none).
static func emote_kind(kind: String) -> String:
	var key := kind.strip_edges()
	return str(EMOTE_KINDS.get(key, EMOTE_KINDS.get(key.to_lower(), "")))

## Register of a voice id ("mid" for unknown ids).
static func register_of(voice_id: String) -> String:
	return str(BARK_VOICES.get(voice_id, ["mid", 205.0])[0])

## Pitch scale that moves a register's bark toward the voice's own f0.
static func bark_pitch(voice_id: String) -> float:
	var entry: Array = BARK_VOICES.get(voice_id, ["mid", 205.0])
	var f0: float = REGISTER_F0.get(str(entry[0]), 205.0)
	return clampf(pow(float(entry[1])/f0, 0.6), 0.86, 1.16)

## True for the bark / tick files in DIR (not syllable banks).
static func is_bark_file(file_name: String) -> bool:
	for prefix in BARK_PREFIXES:
		if file_name.begins_with(prefix): return true
	return false

## Voice id for a cast name, resident id, portrait path ("res://assets/ui/shadow_postman.png")
## or, failing those, a dialogue title ("나루 · 길잡이", "수상한 그림자 · …"). Objects with
## no cast (signs, mailboxes, boards) return "" and stay silent.
static func resolve(cast_or_id: String, title := "") -> String:
	var id := cast_or_id.strip_edges().to_lower()
	if id.contains("/") or id.contains("."): id = id.get_file().get_basename()
	if id.begins_with("shadow_"): id = id.substr(7)
	# Daytime villagers (day_folk.gd) keep the voice of the rounds they walk.
	if id.begins_with("day_"): id = id.substr(4)
	if VOICES.has(id): return id
	for name in NAMES:
		if title.begins_with(name): return NAMES[name]
	if title.contains("그림자"): return "shadow"
	return "" if id.is_empty() else "villager"

## The voice's 28 syllable streams, sliced once from its PCM bank. A compressed import
## falls back to the whole bank (played from the slot offset and stopped after SLOT).
static func bank(id: String) -> Array:
	if banks.has(id): return banks[id]
	var list := _slice(DIR+id+".wav", true)
	banks[id] = list
	return list

## Every bank of a voice: [bank(id)] plus the alternates (<id>_2.wav, <id>_3.wav ...) that
## slice into the same 28 syllables (PCM import). Alternates imported compressed are skipped.
static func bank_set(id: String) -> Array:
	if bank_sets.has(id): return bank_sets[id]
	var main := bank(id)
	var sets := [main] if not main.is_empty() else []
	if not main.is_empty():
		for path in SfxBank.paths(DIR+id):
			if path == DIR+id+".wav": continue
			var alt := _slice(path, false)
			if alt.size() == ONSETS.size()*VOWELS.size(): sets.append(alt)
	bank_sets[id] = sets
	return sets

static func _slice(path: String, allow_whole: bool) -> Array:
	var list := []
	if not ResourceLoader.exists(path): return list
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
	elif whole != null and allow_whole:
		list = [whole]
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

static func _now() -> float:
	return Time.get_ticks_msec()*0.001

func _init() -> void:
	# Dialogue can sit over a paused tree; the babble keeps time regardless.
	process_mode = Node.PROCESS_MODE_ALWAYS
	rng.randomize()

func _ready() -> void:
	var bus := &"Voice" if AudioServer.get_bus_index("Voice") >= 0 else &"Master"
	var ui_bus := &"UI" if AudioServer.get_bus_index("UI") >= 0 else &"Master"
	for i in PLAYERS:
		players.append(_player(bus))
		stop_at.append(0.0)
	for i in 2:
		barks.append(_player(bus))
		ticks.append(_player(ui_bus))

func _player(bus: StringName) -> AudioStreamPlayer:
	var p := AudioStreamPlayer.new()
	p.bus = bus
	add_child(p)
	return p

func _exit_tree() -> void:
	for list in [players, barks, ticks]:
		for p in list:
			p.stop()
			p.stream = null

func _start(id: String, line: String, speed: float, typing_label: Label) -> void:
	voice = id
	quill = false
	_begin(line, speed, typing_label)

## Lines without a speaker: soft quill ticks instead of a voice (silent when none imported).
func _start_quill(line: String, speed: float, typing_label: Label) -> void:
	voice = ""
	quill = true
	if SfxBank.warm(DIR+"quill") == 0:
		active = false
		return
	_begin(line, speed, typing_label)

func _begin(line: String, speed: float, typing_label: Label) -> void:
	label = typing_label
	text = typing_label.text if is_instance_valid(typing_label) else line
	var length := maxi(text.length(), 1)
	cps = speed if speed > 0.0 else length/clampf(length*0.028, 0.25, 1.6)
	started = _now()
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
	var now := _now()
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
	var gap: float = QUILL_GAP if quill else float(VOICES[voice].gap)
	var held := not quill and now < hold_until
	while cursor < revealed:
		var i := cursor
		cursor += 1
		var code := text.unicode_at(i)
		if not _voiced(code):
			if code == 32 or code == 10: word_start = true
			continue
		if not held and (now-last_emit >= gap or (word_start and now-last_emit >= gap*0.6)):
			if quill:
				_tick()
				# Pen strokes are less even than syllables.
				last_emit = now+rng.randf_range(0.0, 0.035)
			else:
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
	var sets := bank_set(voice)
	if sets.is_empty(): return
	var at := _slot(i, code)
	var k := at.x*VOWELS.size()+at.y
	# One bank per syllable from this slot's shuffle bag: never the same take twice in a row.
	var list: Array = sets[0] if sets.size() == 1 else sets[SfxBank.bag_index("babble/%s/%d" % [voice, k], sets.size())]
	if list.is_empty(): return
	var spec: Dictionary = VOICES[voice]
	# Each character keeps its own small pitch offset (same letter, same note).
	var detune := float((code*2654435761) % 1000)/1000.0-0.5
	var pitch := pitch_shape[i] if i < pitch_shape.size() else 1.0
	pitch *= 1.0+detune*0.09
	pitch *= 1.0+rng.randf_range(-PITCH_JITTER, PITCH_JITTER)
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
		stop_at[slot_index] = _now()+SLOT/p.pitch_scale
	syllables_played += 1

## One quill/paper tick (UI bus).
func _tick() -> void:
	var take := SfxBank.pick(DIR+"quill")
	if take == null or ticks.is_empty(): return
	var p := ticks[tick_next]
	tick_next = (tick_next+1) % ticks.size()
	p.stream = take
	p.pitch_scale = SfxBank.pitch(0.06)
	p.volume_db = QUILL_DB+SfxBank.db(1.5)
	p.play()
	ticks_played += 1

func _greet(voice_id: String) -> bool:
	var now := _now()
	if now-float(last_greet.get(voice_id, -1000.0)) < GREET_GAP: return false
	var take := SfxBank.pick(DIR+"greet_"+register_of(voice_id))
	if take == null: return false
	last_greet[voice_id] = now
	var pitch := bark_pitch(voice_id)*SfxBank.pitch(0.03)
	var spec: Dictionary = VOICES.get(voice_id, {"db": 0.0})
	_bark(take, pitch, BASE_DB+float(spec.get("db", 0.0))+GREET_DB+SfxBank.db(1.0))
	hold_until = now+minf(take.get_length()/pitch*0.8, GREET_HOLD)
	hold_voice = voice_id
	greets_played += 1
	return true

func _emote(app, id: String, kind: String, at: Vector3) -> bool:
	var bark_kind := emote_kind(kind)
	if bark_kind.is_empty(): return false
	var voice_id := resolve(id)
	if voice_id.is_empty(): voice_id = "villager"
	var now := _now()
	if now-last_any_emote < EMOTE_SPACING: return false
	if now-float(last_emote.get(voice_id, -1000.0)) < EMOTE_GAP: return false
	# Never over the speaker's own dialogue.
	if active and not quill and voice == voice_id: return false
	var volume: float = EMOTE_DB[bark_kind]+float(VOICES.get(voice_id, {"db": 0.0}).get("db", 0.0))
	if at != Vector3.INF:
		var ear := _listener(app)
		if ear.size() == 2:
			var ear_at: Vector3 = ear[0]
			var near: float = ear[1]
			var d := ear_at.distance_to(at)
			if d > EMOTE_RANGE+near-3.0: return false
			volume -= clampf(d-near, 0.0, 30.0)*0.8
	var take := SfxBank.pick(DIR+"emote_%s_%s" % [register_of(voice_id), bark_kind])
	if take == null: return false
	last_emote[voice_id] = now
	last_any_emote = now
	_bark(take, bark_pitch(voice_id)*SfxBank.pitch(0.035), volume+SfxBank.db(1.0))
	emotes_played += 1
	return true

## [position, near distance] of the listener: app.player (or the current scene's player), else
## the current camera; [] when there is neither.
func _listener(app) -> Array:
	var host = app
	if host == null or not is_instance_valid(host):
		host = get_tree().current_scene if is_inside_tree() else null
	if host != null and is_instance_valid(host) and "player" in host:
		var who = host.get("player")
		if is_instance_valid(who) and who is Node3D and who.is_inside_tree(): return [who.global_position, 3.0]
	var camera: Camera3D = get_viewport().get_camera_3d() if is_inside_tree() else null
	if camera != null: return [camera.global_position, CAMERA_NEAR]
	return []

func _bark(take: AudioStream, pitch: float, db: float) -> void:
	if barks.is_empty(): return
	# A free player if there is one, else the one that started first.
	var p := barks[bark_next]
	for candidate in barks:
		if not candidate.playing:
			p = candidate
			break
	bark_next = (barks.find(p)+1) % barks.size()
	p.stream = take
	p.pitch_scale = clampf(pitch, 0.7, 1.5)
	p.volume_db = db
	p.play()
