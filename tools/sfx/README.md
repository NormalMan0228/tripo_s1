# tools/sfx: sound take families

Every sound event gets several structurally different takes, and the game picks them through a
shuffle bag with small pitch and volume jitter, so no sound repeats identically. Everything is
synthesised with numpy/scipy (license-clean, no downloads, no AI models).

| file | what |
|---|---|
| `sfxlib.py` | synthesis building blocks, WAV IO, loudness matching, `make_family()` writer. Self-test: `python tools/sfx/sfxlib.py` |
| `sfx_qa.py` | QA: levels, clicks, DC, clipping, silence, loop seams, near-identical takes, contact sheet |
| `game/scripts/sfx_bank.gd` | runtime take picker (shuffle bag, lazy cached loading, jitter) |
| `game/tests/sfx_bank_check.gd` | headless test of the picker |

Python: `.tools\art-venv\Scripts\python.exe` (numpy, scipy, Pillow; no soundfile, no matplotlib).
Generators of the six sound owners live next to these files (`tools/sfx/make_<key>.py`) and add a
section to this README.

## Naming

- `res://assets/sfx/<dir>/<event>.wav` is the existing original (if any); new takes are
  `<event>_<n>.wav`, n = 1, 2, 3 ... contiguous. `sfx_bank.gd` finds the bare file plus the numbered
  takes, tolerates **one** missing index and stops at the second.
- Never overwrite or delete an existing WAV. Team recordings (`combat/harvest_tree_1.wav`,
  `harvest_stone_1.wav`, `harvest_fiber_1.wav`, `doors/*`, `ui/*.wav`) and the outputs of the older
  generators stay as they are; new takes are new files. `make_family()` and `write_take()` refuse
  to write over a protected file (`sfxlib.protected()`): every git-tracked file, or, with the
  environment variable `SFX_BASE=<ref>`, only the files that already existed at `<ref>`. The new
  takes of this work are committed, so re-render them with
  `$env:SFX_BASE = 'merge-version-gate'` (PowerShell) set; without it the guard refuses, and
  `gen_combat.py` would number new takes after them. If `_1` exists, start your family at `start=2`.
- Do **not** run `tools/make_village_sfx.py`, `tools/make_creature_sfx.py` or
  `tools/build_ui_sounds.py`; they overwrite. The first two can be imported for their helpers
  (they have a `__main__` guard; their module `SR` is 32000):
  `sys.path.insert(0, "tools"); import make_creature_sfx as C`.
  **`build_ui_sounds.py` has no guard: importing it regenerates `ui/*.wav`.** Copy its few helpers
  instead of importing it.

## Format and loudness

- Mono, 16-bit PCM, canonical 44-byte header (`sfxlib.write_wav`). 22050 Hz by default; 32000 Hz
  only where brightness matters (metal, glass, sparkles, high clicks).
- Loudness is the loudest 120 ms RMS after a 2nd-order 150 Hz high-pass (`st_rms_peak_db`). This is
  the measure that `game/tests/audio_bank_check.gd` and the older generators use.
- Match each new family to the existing file of that kind within +-1.5 dB:
  `ref = L.ref_db_of(L.SFX_ROOT / "ui" / "click.wav")`. For a new kind, match a sibling, for
  example a new `fish/thrash` against `fish/plop`.
- `finish()` (which `make_family()` runs for you) does the following:
  - removes DC (mean, then a 20 Hz high-pass);
  - matches the level and runs the look-ahead limiter with a -1 dBFS ceiling, so nothing clips;
  - trims silence below -60 dBFS (keeping 12 ms after the tail);
  - applies a raised-cosine 3 ms fade-in and 20 ms fade-out (both 2–5 ms in and 10–30 ms out are
    fine).

  When the limiter has to take more than 6 dB off the peak, `make_family()` prints a warning.
  Soften the transient or pick a lower reference.
- Keep files short. Tests in the shared directories also apply:
  - `audio_bank_check.gd` reads every WAV in `creatures/`, `combat/`, `hero/` and `voice/`. Each must
    be under 150 KB, and its length and st-rms must sit inside the group range:
    - creatures: 0.3–2.0 s, -24 to -13 dBFS
    - combat: 0.15–2.3 s, -25 to -12 dBFS
    - hero: 0.15–2.3 s, -27 to -14 dBFS
    - voice: 3.0–3.4 s, exactly 28 slots
  - `make_village_sfx.py` keeps `doors/` and `field/` files under 120 KB.
- Report your size budget as the sum of new WAV bytes. `make_family()` returns a `bytes` value for
  each take, and `family_report()` prints the KB total.
- **Perceived level (A-weighted).** The flat st-rms match lets a bright take in a dark family sound
  3-5 dB louder than its siblings (a 3 kHz tick next to 150 Hz thumps). `aw_st_db()` is the same
  120 ms peak after IEC A-weighting. `make_family()` and `diverse_family()` run `aw_balance()` after
  finishing a family: a take more than 1.5 dB (`AW_BALANCE_DB`) above the family's median A-weighted
  level (existing files of the family included) is re-finished quieter, at most 1.75 dB
  (`AW_FLAT_ROOM_DB`) under the family's flat median, and, if that is not enough, darkened by the
  gentlest 1st-order low-pass that gets it there (kept only when it really lowers the perceived
  level: a take with nothing below 1 kHz only gets duller). Its notes (`aw_over_db`, `aw_gain_db`,
  `aw_lowpass_hz`) land in the take metadata. Pass `aw_balance_db=None` to switch it off. A take
  that still stands out needs a design change (less breath, more body), as `gen_voice.emote_dots`
  takes 3 and 5 got.

## Designing takes that really differ

The QA compares every two takes of a family on a fine time × frequency map (see below). Pure random
parameter draws (`f0 = rng.uniform(400, 520)`) end up with pairs that sit within a few percent of
each other, and the QA flags those pairs, correctly: they sound like the same sample played twice.
Build families on a grid of structural archetypes instead, then add small random detail:

```python
mat, hits, step = L.cycle(i, ["wood", "ceramic"], [1, 2, 3], [1.0, 1.15, 0.86, 1.32, 0.76])
```

`cycle()` picks `axis[i % len(axis)]` from each axis. With coprime axis lengths (2, 3, 5, 7), every
take up to their product gets its own combination.

Good axes:
- number and timing of transients (single, double or triple knock; a flam; a drag);
- partial ratios and material (`MATERIALS`, `spread=`);
- pitch steps of at least 10 % between neighbouring archetypes;
- duration ±15 %, with a different envelope shape (single or double hump, flutter);
- noise colour and texture;
- a sweep direction;
- an extra layer (cloth, debris, a tail).

Whooshes and other smooth noise swells are the hardest case. Give them flutter, double humps, a
whistle or a different sweep direction, not just different lengths.

Deriving takes from a recording means slicing at its transients and re-ordering or dropping the
pieces, plus layering. Use `onsets`, `segments`, `splice`, `transient_shape`, `tilt`, `repitch` and
`xfade_concat`. Re-pitching and EQ alone are not enough: the QA flags takes that are only
repitch + tilt of the same recording (sim 0.97–0.99).

## Library overview (`sfxlib.py`)

- **IO:** `write_wav`, `read_wav` (any PCM 8/16/24/32 or float WAV, mono or stereo, odd headers),
  `wav_info`, `resample`, `repitch(x, ratio)` (tape-speed).
- **Level:**
  - `st_rms_peak_db`, `peak_db`, `match_to`, `ref_db_of`;
  - `finish`, `limit`, `trim_silence`, `fades`, `remove_dc`;
  - `loopify` + `finish(loop=True)` for loops.
- **Noise:** `white`, `pink`, `brown` (RMS 0.25, n samples).
- **Filters** (all take `sr`):
  - `lp`, `hp`, `bp` (Butterworth, `zero_phase=` optional);
  - `peaking`, `shelf`, `tilt`;
  - `svf` (a time-varying state-variable filter for sweeps);
  - `resonate` (excite a resonator bank with any signal).
- **Envelopes:** `env_points`, `adsr`, `exp_decay`, `attack_decay`.
- **Bodies and tones:**
  - `modal(sr, f0, material)` with `MATERIALS` wood, metal, glass, stone, ceramic and bell, with
    randomised ratios, decays, amplitudes and a strike click;
  - `modal_bank`;
  - `ks_pluck` (Karplus–Strong);
  - `fm_bell`;
  - `osc` and `chirp`.
- **Texture:** `scatter` (granular, from a callable or a source array), `reverb(room=0..1)`,
  `saturate`.
- **Mixing:** `mix(a, (b, gain, offset_s))`, `place`, `concat(xfade=)`, `pad_to`, `norm_peak`,
  `norm_rms`.
- **Families:**
  - `cycle`;
  - `take_seed(event, i)`, a stable seed per take;
  - `make_family(out_dir, event, n, fn, sr, ref_db, start=1)`, where `fn(rng, i)` returns an array
    or `(array, notes)`;
  - `write_take` for single files;
  - `family_report`.

Example:

```python
import sys; sys.path.insert(0, "tools/sfx")
import numpy as np
import sfxlib as L
SR = L.DEFAULT_SR
GAPS = [(0.12, 0.12, 0.12), (0.2, 0.1, 0.06), (0.07, 0.11, 0.18), (0.025, 0.15, 0.1)]  # even, rushing, dragging, flam (s)

def thrash(rng, i):
    hits, size, gaps = L.cycle(i, [3, 2, 4], [0.7, 1.0, 1.4, 0.82, 1.2], GAPS)
    out = np.zeros(L.secs(0.75, SR))
    at = 0.0
    for h in range(hits):
        s = size * rng.uniform(0.85, 1.15)                      # each splash its own size
        burst = L.bp(L.white(L.secs(0.12, SR), rng), SR, 500 / s, 4000 / s) * L.exp_decay(0.12, SR, rng.uniform(0.02, 0.04))
        L.place(out, burst, at, SR, gain=rng.uniform(0.6, 1.0))
        at += gaps[h % 3] * rng.uniform(0.9, 1.1)
    return L.reverb(out, SR, room=rng.uniform(0.1, 0.3), rng=rng)

ref = L.ref_db_of(L.SFX_ROOT / "combat" / "hit_flesh_1.wav")
# try ideas in your scratch folder first; real families go to L.SFX_ROOT / "<dir>"
meta = L.make_family(L.SCRATCH / "<key>" / "fish", "thrash", 8, thrash, sr=SR, ref_db=ref)
```

This example passes QA (max sim 0.85). With the hits axis `[2, 3, 4]`, the two 2-hit takes would
get the 25 ms flam and the 70 ms drag. "chk-chk" at those two spacings sounds alike, and the QA
flags the pair (0.90–0.96). Check that every archetype that collapses (here, 2 hits use only the
first gap) still differs in its remaining axes.

## QA (`sfx_qa.py`)

Run QA on your own files and the original of each family. Put sheets and JSON in the scratch area,
not the repo:

```
.tools\art-venv\Scripts\python.exe tools\sfx\sfx_qa.py "game\assets\sfx\ui\hover*.wav" "game\assets\sfx\ui\click*.wav" --min-takes 8 --sheet "$SFXWORK\<key>\ui.png" --json "$SFXWORK\<key>\ui.json"
```

The QA takes about 5–10 s per 100 files. The JSON lists every pair with its `freq` and `time`
scores.

Set `SFXWORK` first in PowerShell:
`$SFXWORK = 'C:\Users\dd\AppData\Local\Temp\claude\C--lsm26-triphthonS1\72dd4eba-2f77-432d-a4e0-50886f25eeb1\scratchpad\sfxwork'`.
Each owner uses its own `<key>` folder. `sfxlib.SCRATCH` points there, and the `SFX_SCRATCH`
environment variable overrides it.

**Per-file checks:**
- duration, peak, st-rms, DC, clipped samples;
- edge levels: the first and last 2 ms and the first and last sample;
- leading and trailing silence;
- spectral centroid;
- header shape.

**Families:** files in one directory whose names differ only by a trailing `_<n>`. The bare
original joins its takes. `--group dir` puts a whole folder in one family, which helps catch
cross-family look-alikes. `--group none` checks files alone.

**FAIL (exit code 1):**
- any clipped sample;
- |DC| > 0.01;
- first sample above -40 dBFS;
- last sample above -50 dBFS, or the last 2 ms above -36 dBFS;
- leading silence over 40 ms, or trailing silence over 80 ms;
- a file that is not mono 16-bit PCM with a 44-byte header;
- a silent file;
- a take more than 2 dB from the family median;
- a new take more than `--aw-over` (2.5 dB) above the family's median A-weighted st-rms (`aw` in
  the report: the perceived level, which the flat measure misses for bright takes);
- a family spread over `--max-spread` (3 dB);
- fewer takes than `--min-takes`;
- a near-identical pair.

Problems of original files are reported as WARN, since those files must not change; use
`--strict` to make them FAIL. A loudness outlier, or a near-identical pair that involves a new
take, always FAILs. Originals are the git-tracked files, or with `--base <ref>` the files that
already existed at `<ref>` (its merge base with HEAD): everything added since then, committed or
untracked (`git diff --diff-filter=A <ref>...HEAD` plus untracked files), is new and can FAIL.
Now that the takes of this work are committed, run the QA with `--base merge-version-gate`;
without it every committed take counts as an original and its problems drop to WARN. The report
marks originals `[orig]`.

**Loops:**
- Files named `*loop*`, files in `beds/`, `ambience/` or `loops/`, and every input with `--loop`
  are treated as loops.
- They get a seam check instead of the fade and silence checks: the second difference across the
  wrap is compared with the file's own 99th percentile.

**Near-identical:** a pair fails when either score passes its threshold.
- `sim >= 0.90`. `sim` is the lower of two scores, one per resolution. Each score is the best
  Pearson correlation of the two takes' log band-energy maps.
  - Each map covers a 40 dB range under that take's own peak.
  - The search aligns onsets, then tries ±30 ms of lag, time scale 0.92–1.08 and pitch 0.92–1.08,
    independently, in 2 % steps.
  - `freq`: 80 bands from 80 Hz to 10 kHz (about 1/11 octave each), 1024-point frames every 5 ms.
    It sees partials, pitch contours and material.
  - `time`: 32 bands from 100 Hz to 10 kHz, 256-point frames every 2.5 ms. It sees flams, double
    taps, rhythm and attack shape.

  A pair is near-identical only if it matches at both resolutions.
- `xc >= 0.95`. `xc` is the peak normalised waveform cross-correlation, which catches literal
  copies.

### QA similarity calibration (2026-10-15)

The table shows `sim` measured on the existing assets and on synthetic families.

| set | what it is | sim min / median / max | flagged at 0.90 |
|---|---|---|---|
| synthetic jitter copies | 57 existing files × 3: repitch ±6 %, ±1.5 dB, 0–15 ms offset, ±2 dB tilt | 0.934 / 0.986 / 0.999 | 100 % |
| synthetic copies, harder | ±8 % repitch + reverb + noise floor | 0.840 / 0.963 / 0.995 | 89 % |
| creatures windup / strike / hurt / death | take 2 = take 1 re-seeded, pitch jitter only (audit: "differ only by jitter") | 0.811 / 0.91–0.94 / 0.973 | 60–80 % |
| combat families | swings and hits (audit: near-duplicates) | 0.772 / 0.949 / 0.983 | 81 % |
| lazy families (re-seed + ±4 % pitch, same structure) | knock / whoosh / thrash / tick | 0.873 / 0.93–0.98 / 0.995 | 100 / 100 / 96 / 87 % |
| creatures alert | structurally different (howl vs barks, other note sequence or contour) | 0.428 / 0.805 / 0.932 | 20 % (only shroom: same "oooh", other contour) |
| creatures idle | different grunt or blip counts and timing | 0.197 / 0.809 / 0.890 | 0 % |
| different kinds in one folder | door rooms, field props, ui kinds | -0.44 / 0.21 / 0.872 | 0 % |
| designed families (`cycle()` grid) | knock / thrash / whoosh / tick / recording splices | 0.06–0.53 / 0.35–0.83 / 0.90–0.96 | 0–13 %, only pairs that share or nearly share an archetype |

At 0.90 and above, two takes are the same gesture: they differ only in pitch, gain, a re-seeded
noise layer or reverb, and the runtime jitter already covers those. Below 0.90 they differ in
structure.

The `time` resolution was added after a single 46 ms resolution scored a 25 ms flam against a
70 ms double splash at 0.92. With both resolutions the designed thrash family dropped from a
median of 0.58 to 0.51, and every positive set kept its flag rate.

The calibration script is `sfxwork/foundation/calib3.py` (scratch); its results are in
`calib3.json`.

## Runtime: `game/scripts/sfx_bank.gd`

```gdscript
const SfxBank = preload("res://scripts/sfx_bank.gd")   # no class_name (PCK patches)

# inside an existing play API, keeping its signature:
var take := SfxBank.pick("ui/"+kind)          # or "res://assets/sfx/ui/"+kind
if take == null: return
voice.stream = take
voice.pitch_scale = SfxBank.pitch(0.03)        # 1 +- 0.03
voice.volume_db = volume_db+SfxBank.db(1.0)    # +- 1 dB
voice.play()

# one-shot onto any AudioStreamPlayer / 2D / 3D (plays once it is in the tree):
SfxBank.play_on($Sfx, "field/creak_soft", -9.0, 1.0, 0.04, 1.5)

# the same no-repeat bag for any list (synthesised streams, node pools):
var i := SfxBank.bag_index("step/grass/walk", streams.size())
```

**API:**
- Discovery:
  - `paths(base) -> PackedStringArray`
  - `count(base) -> int`
  - `has(base) -> bool`
- Picking:
  - `pick(base) -> AudioStream`, null when the family has no takes
  - `pick_path(base) -> String`
  - `stream(path) -> AudioStream`
  - `warm(base) -> int`, which preloads every take of a family
  - `bag_index(key, size) -> int`
- Jitter:
  - `pitch(spread := 0.04) -> float`
  - `db(spread := 1.0) -> float`
  - `set_seed(v)`
- Playback: `play_on(player, base, db := 0.0, pitch := 1.0, spread_pitch := 0.04, spread_db := 1.0) -> bool`
- Cache: `cached_count() -> int`, `clear()`

**Behaviour:**
- Discovery probes `ResourceLoader.exists()`, never DirAccess, so it also works in exported packs.
  Results are cached per base.
- Each family has its own shuffle bag. Every take plays once per cycle. A new cycle never starts
  with the take that just played, and with 6 or more takes the last two are avoided.
- Only the chosen take is loaded. Loaded streams stay cached.
- The caches are static. CleanExit (`clean_exit.gd`) calls `clear()` at shutdown, which keeps
  "resources still in use at exit" out of the logs. Never preload new WAVs; they are not imported
  yet when your script is written.
- Never load new takes in a script through `preload()` or a fixed `range(1, 5)` loop. The old
  loaders (combat_audio.gd:78, creature_audio.gd:134, hero_voice.gd:86) cap at 4 takes; switch
  them to `SfxBank.paths()` or `pick()`.
- Tests that pin exact counts or objects need updating together with your change:
  - `audio_check.gd` (VARIATIONS takes per surface)
  - `door_sounds_check.gd` (`door_stream` returns one exact cached path)
  - `audio_bank_check.gd` (ranges, ≥2 takes)
  - `settings_check.gd` (RpgUi `_voice` / `_last_played`)

## Import (done by another stage, once for everyone)

- New WAVs are invisible to `ResourceLoader.exists()` until `godot --headless --path game --import`
  has run. During the categories stage **nobody** runs `--import`, the tests or `tools\test.ps1`:
  concurrent imports corrupt the cache.
- The default WAV import is QOA (`compress/mode=2`). The import stage sets these parameters:
  - `compress/mode=0` (PCM) for anything whose `.data` is read at runtime (voice banks, loop math in
    sound.gd);
  - `edit/loop_mode=2` (forward) and `edit/loop_begin=0`, `edit/loop_end=-1` for loops.

  If your family needs either, list it in your hand-off. The pattern for editing import parameters
  is `tools/build_survival_assets.py` `configure_imports()`.
- Commit the `.wav` and its `.wav.import` together. `game/.godot` is ignored.

## Life, fishing and core effects (`gen_life.py`)

```
.tools\art-venv\Scripts\python.exe tools\sfx\gen_life.py                 # all 44 families -> game/assets/sfx/{life,core}
.tools\art-venv\Scripts\python.exe tools\sfx\gen_life.py --only tick,thrash --out "$SFXWORK\life\try"
.tools\art-venv\Scripts\python.exe tools\sfx\gen_life.py --list          # families, take counts, reference levels
.tools\art-venv\Scripts\python.exe tools\sfx\sfx_qa.py game\assets\sfx\life game\assets\sfx\core --min-takes 3
```

The script renders 273 takes, about 5.6 MB, in 6 s. Every take re-renders identically: the seed
comes from `take_seed(event, n, "gen_life-v1")`.

**Families:**
- `life/`, played by `life_sfx.gd` `play(kind, pitch, volume)`:
  - Farming and foraging: hoe, seed, water, rustle, pop, rock, shell, collect, pocket, grab.
  - Fishing: tick, nibble, cast, windup, whiz, plop, ripple, bite, strike, thrash, reel_back,
    fish_out, escape, catch, card, rod_equip.
  - Trees and the village: fruit_detach, bounce, fruit_water, knock, bell.
- `core/`, played by `sound.gd` `effect(kind)`: reward, gather, craft, eat, bandage, fire, error,
  sell, buy, errand, newday, win, lose, and `eat_soup` (4 takes: a warm sip and a light spoon clink
  on the bowl in four orders, 1 dB under eat). `eat_soup` plays once `main.gd` calls
  `sound.effect("eat_soup")` for soup (the server answers "열매 수프를 먹었습니다."); until then soup
  plays core/eat like berries.
- The forage kinds `dig_stone`, `dig_grass` and `chop_wood` play the recorded
  `combat/harvest_{stone,fiber,tree}` families. Take `_1` is the team recording; the combat
  generator owns the other takes.

**Loudness.** Most of these kinds used to be runtime synths, so no file existed to match.
- The generator holds numpy ports of `life_sfx.gd make()` and `sound.gd make_effect()`. It
  measures each port and adds the player volume (life −13 dB, core −16 dB) to get the effective
  level a family has to match.
- New kinds match a sibling (`FAMILIES` reference column). For example, thrash, ripple, fish_out
  and fruit_water match plop; bell matches the core reward jingle it replaces.
- Files sit `HEADROOM_DB` (6 dB) under that level so that transients never reach the limiter.
  `life_sfx.gd` and `sound.gd` add `BAKED_DB` (+6 dB) back when they play a baked take.
- If you change one of the two constants, change the other with it.

**Runtime behaviour:**
- Every play picks from the shuffle bag (`sfx_bank.gd`) with pitch ±4 % and ±1 dB jitter,
  multiplied with the caller's pitch.
- A kind without takes falls back to its old synth (`STAND_IN` maps new kinds to the nearest one).
- `LifeSfx.play_at(kind, at, listener, ...)` attenuates by distance like `Fx.sound`.
- `LifeSfx.pocket()` plays a pentatonic ladder for items landing in the bag one after another.
- None of these files is a loop, and none has its `.data` read at runtime, so the default QOA
  import is fine.
- `game/tests/life_sound_check.gd` (after the import) checks the take counts, both players and
  the music silence gaps.

## NPC voice: alternate babble banks, barks, quill ticks (`gen_voice.py`)

```
.tools\art-venv\Scripts\python.exe tools\sfx\gen_voice.py                       # everything -> game/assets/sfx/voice
.tools\art-venv\Scripts\python.exe tools\sfx\gen_voice.py --only emote,greet --out "$SFXWORK\voice\try"
.tools\art-venv\Scripts\python.exe tools\sfx\gen_voice.py --only banks --slots "$SFXWORK\voice\slots"   # + per-syllable QA files
.tools\art-venv\Scripts\python.exe tools\sfx\sfx_qa.py game\assets\sfx\voice --min-takes 3
.tools\art-venv\Scripts\python.exe tools\sfx\sfx_qa.py "$SFXWORK\voice\slots"          # 588 syllable families x 3 takes
```

The script renders 196 files, 8.8 MB (8.4 MiB), in about 2.5 minutes; the banks take most of that time
because of the syllable rerolls. It imports `make_creature_sfx.py` for the formant voice (`voice()`,
`VOICE_CAST`, the bank layout) and never runs that file's `main()`.

**Files** (all 22050 Hz, in `voice/`):
- **Alternate banks** `<id>_2.wav` and `<id>_3.wav` for all 21 voices.
  - They use the same layout as `<id>.wav`: 28 slots of 0.115 s (onset × vowel), every syllable
    silent in its last 8 ms.
  - Each syllable is re-synthesised with another seed and a grid of structural variants. The axes
    are the pitch contour (fall, late rise, dip, flat or early peak, against the original's arch),
    the length (±20 %, or a late-peaking swell when the slot caps the length), the coda (n, m, a
    breathy h or a clipped stop; the original is always open), the vowel colour (a glide from or
    toward a neighbouring vowel), breath, attack, release, tilt, the shadow-chorus delay and the
    stargazer's sparkle partial.
  - f0, formant scale, breath class and chorus stay the character's own.
  - **QA-driven reroll:** every syllable is scored with `sfx_qa.similarity` against the same slot
    of the original bank and of bank 2. When the score reaches 0.86 the syllable is re-rendered
    with the next coda, contour, envelope and, later, length, glide, breath and attack, so every
    slot family stays under the 0.90 QA line.
- **Emote barks** `emote_<register>_<kind>_<n>.wav`: 4 registers (low 128 Hz, mid 205 Hz, high
  285 Hz, child 420 Hz) × 6 kinds × 5 takes.
  - note: hm-hm-hmm, la-la, du-du-du, a legato mm~, na-na-na-na.
  - exclaim: oh!, eh?!, ah!, hup!, whoa~.
  - dots: hmm…, hm-hm, uh…, mmm?, ehh….
  - heart: aww~, ooh~, hehe, mm~, ehehe.
  - mail: here!, ta-da!, yoo-hoo, o-ho!, hey-ya!.
  - sleep: a snore, zzz, a sleepy murmur with a sigh, zz-zz, a long exhale.
- **Greeting barks** `greet_<register>_<n>.wav`, 6 per register: hiya!, oh, hi!, hello~, hey!,
  hi-hi!, yo-ho~.
- **Quill ticks** `quill_<n>.wav`, 10 takes: nib hiss with a pen knock, a dot, a double scritch, a
  wobbly swish, a thump with a downstroke, a tap with a scratch, a paper rustle, a triple flick, a
  nib "tsk" and a zigzag scribble.

**Loudness.**
- The banks use the original generator's per-syllable level (-17 dBFS over 40 ms at 32 kHz). They
  land within 1 dB of their original.
- The barks match the median st-rms of the original banks (-19.0 dBFS).
- The quill ticks match `ui/hover.wav` (-25.0 dBFS). Ticks shorter than the 120 ms window are
  measured over their own length, so the generator matches them before trimming.

**Runtime** (`game/scripts/voice_babble.gd`):
- `speak()`:
  - Picks the bank for each syllable from a per-(voice, slot) `SfxBank.bag_index` bag, so a
    syllable never plays the same take twice in a row.
  - Adds ±2 % random pitch on top of the per-character note.
  - Keeps working with only `<id>.wav`. `bank(id)` still returns the primary bank, and
    `bank_set(id)` returns all of them.
- `speak("" | "sign" | "letter", ...)` plays quill ticks on the UI bus instead of a voice. They
  count in `ticks_played`, not `syllables_played`.
- A new dialogue Label means a new conversation: `speak()` plays `greet()` first and holds the
  first syllables for at most 0.28 s. The same voice greets at most once every 30 s.
- `VoiceBabble.emote(app, id, kind, at)`:
  - `kind` is a bubble glyph or a kind name.
  - Plays at most once per voice every 3 s, with at least 0.3 s between any two emotes, and never
    over that speaker's own dialogue.
  - Volume drops 0.8 dB/m past 3 m from `app.player`, or past 9 m from the camera when there is
    no app. It is silent beyond 26 m.
- Each register's take is pitched by (voice f0 / register f0)^0.6 toward the speaker
  (`BARK_VOICES`).

**Import.**
- The 42 alternate banks need `compress/mode=0` (PCM): their `.data` is sliced at runtime. A
  compressed alternate is skipped, not misread.
- The barks and ticks use the default QOA import.
- `audio_bank_check.gd` checks only the banks in `voice/`; `game/tests/voice_variety_check.gd`
  covers the alternates, barks, ticks, the no-repeat rule, the greeting and the emote throttles.

## UI sounds (`gen_ui.py`)

```
.tools\art-venv\Scripts\python.exe tools\sfx\gen_ui.py                    # all 52 kinds -> game/assets/sfx/ui
.tools\art-venv\Scripts\python.exe tools\sfx\gen_ui.py --only hover,brush --out "$SFXWORK\ui\try"
.tools\art-venv\Scripts\python.exe tools\sfx\gen_ui.py --list             # kinds, take counts, level reference, length cap
.tools\art-venv\Scripts\python.exe tools\sfx\sfx_qa.py game\assets\sfx\ui --min-takes 4
```

The script renders 349 takes, about 5.3 MB, in about 5 s, at 22.05 kHz like the originals. Every
take re-renders byte-identically: its seed is `take_seed(kind, n, "ui")`. A try-out `--out` dir
also receives copies of the six originals, so the QA compares new takes against them. The script
never imports `build_ui_sounds.py`. It removes only its own untracked takes numbered past a
family's size.

**Style.** The takes extend the soft originals: sine ticks with a breath of noise, small bell
tones on a G-major pentatonic (G A B D E), and filtered-noise swishes. The bodies come in several
timbres (bell, glass, kalimba, celesta, music box, marimba, wood). The new kinds reuse that
palette:
- paper flicks for page, tab and layer;
- drawer runners (pink-noise friction with rattle or roller texture, then a wooden stop);
- coin tinks;
- bubbles for chat and paint;
- bristle strokes (narrow-band noise with grains) for the brush.

**Kinds** (`ui/<kind>.wav` original where marked, plus `_1.._N`):

| group | kinds (takes) |
|---|---|
| originals | hover\* 14, click\* 12, open\* 8, close\* 8, toast\* 10, confirm\* 8 |
| menus | deny 8, tab 8, select 8, slider 12, drawer_open 6, drawer_close 6, count 10, coin_gain 6, key_capture 4, save 5 |
| social | chat_in 8, chat_out 6, whisper 4, friend 4, join 4, leave 4, notify 6, toast_success 6, toast_warn 6, toast_error 6, toast_social 6 |
| quests | quest_accept 5, quest_ready 4, quest_complete 5, star 8, unlock 4 |
| placement | rotate 12, snap 10, place 8, lift 6, cancel 6, valid 4, invalid 4 |
| painter | paint 8, brush 12, fill 4, undo 6, redo 6, layer 6, swatch 6 |
| craft, dialogue | craft_submit 4, craft_step 6, craft_done 4, craft_fail 4, page 8, choice 6 |

**Design grid.** Each kind crosses two or three `cycle()` axes with coprime lengths, so no two
takes share an archetype. Typical axes:
- body or timbre;
- gesture (single, flam, press and release, double, a tail);
- a pitch step: geometric sets at least 25 % apart where a family is pitch-led, such as slider and
  cancel;
- melodic motif and rhythm for the chimes;
- envelope shape and sweep for the swishes.

The QA showed two things to avoid:
- **Pitch multipliers on bodies.** `modal(f * 0.62)` against another body at `f` made two
  "different" takes land on one pitch.
- **Band alone as the only difference between noise strokes.** The brush became 6 gestures × 2
  bands, so every pair differs in gesture.

**Levels.** Each family is level-matched (120 ms st-rms) to its original, or to a sibling for a
new kind (`--list` shows which). `leveled()` finishes each take once before `make_family`
finishes it again, so short takes (< 120 ms) also land on the reference. Tails are cut 50 dB
down, then given a 30 ms fade and capped per kind (0.08 s ticks up to 1.4 s fanfares). The
shared limiter never has to act.

**QA (2026-10-15).**
- 355 files in 52 families pass with `--min-takes 4`; exit 0, no warnings.
- Highest pair sim is 0.886 (snap); the median of the family maxima is 0.83.
- Highest waveform xc is 0.928.
- Largest family loudness spread is 0.8 dB.

**Runtime.** `RpgUi.sfx(kind, volume_db)` (rpg_ui.gd) works like this:
- It picks a take through `sfx_bank.gd` (shuffle bag, no immediate repeat) with ±4 % pitch and
  ±1 dB.
- It keeps the hover throttle (45 ms), the same-kind dedupe (60 ms), the headless early return,
  `_voice` (+1 per play) and `_last_played`.
- Loaded streams stay on the `RpgUiSounds` host's meta.
- It has six players, and a free one is used first, so a fanfare is not cut by hover ticks.
- A kind without imported takes falls back to a related kind (`toast_error` → `deny` → `close`);
  an unknown kind is silent.
- A message kind played just before a message (deny, chat_in, place, toast_error, …) stands in
  for that message's generic toast chime: the chime is deduped.

`game/tests/ui_sfx_check.gd` checks every kind's takes after the import. The WAVs use the
default import: no PCM, no loops.

## Props, field objects, interiors and doors (`gen_props.py`, `gen_doors.py`)

```
.tools\art-venv\Scripts\python.exe tools\sfx\gen_props.py            # fx/, field/, interior/ (370 files)
.tools\art-venv\Scripts\python.exe tools\sfx\gen_props.py --list     # families, take counts, rates
.tools\art-venv\Scripts\python.exe tools\sfx\gen_doors.py            # doors/<room>_<kind>_1..3 (84 files)
```

Both take `--root <dir>` for trial runs in scratch, plus `--only fx,field,interior,world` /
`--family thud,seat` (props) or `--room 01_cafe` (doors). Renders are seeded per take, so a re-run
writes the same files. Neither writes over a git-tracked file. Helpers come from
`tools/make_village_sfx.py` (`creak`, `bell`, `tube`, `thud`, `wind`, `rumble`...), which is
imported and never run.

**What is made.**
- `fx/<kind>_<n>`: the `Fx.sound` kinds were runtime synth and are now baked. 20 families plus
  one loop:
  - thud, leaves, leaves_needle, leaves_palm, twinkle, pluck, pop, tune, splash, crackle,
    whoosh, chirp, drink;
  - new: canvas (tent), hull (boat), seat, cushion, speaker (six different songs), dragonfly,
    sputter, and the loop `firepit_loop_1`.
- `field/<name>_<n>`: more takes next to the bare original, which stays take 0. New kinds are
  hammock, flap, flag, peck, tweet, bucket, telescope, arrive, stand, seeds and settle.
- `field/chest_<n>` and `field/chest_rattle_<n>` (treasure.gd, no bare original): the treasure
  chest's opening, 6 takes at 32 kHz (catch hasp / snap / bolt × hinge long / two-stage / low /
  airy × the lid's stop thunk / bounce × the gold's sparkle rise / fall / chord / dust / trill),
  and its lid jiggled against the catch while the server answers, 6 takes (2 to 5 knocks in an
  even, rushing, dragging or flam rhythm × metal jingle / last clack / none).
- `interior/<kind>_<n>`: the 15 `Interiors.sfx` kinds, 6 takes each, plus `steps` (8 stair
  takes in place of 4 identical thuds).
- `doors/<room>_<kind>_<n>`: 3 takes per room and kind, so with the original there are 4.
- `world/portal_<n>`: 4 variants of the team's portal stinger `world/portal.wav` (which stays
  take 0; `sound.gd stinger()` bags the family): deep (13 % lower, the fading hum wavers), quick
  (the build cut short, a shorter tail), double (a softer second wave), open (the build is the
  reversed decay drawing in, a low-pass opening to the peak). Derived from the recording, at
  22050 Hz, levelled to it; max sim 0.86.

**Designing the takes.** Most families are tables of explicit recipes, not random draws:
- creaks are scripts of (time, length, f_start, f_end) events;
- door takes turn per-room knobs: latch worked once, rattled or fumbled; hinge reversed,
  stuttering or dragging; door bounce or ease shut; bell order, count and partner bells;
  glass pane size; lighthouse bolt.

Creaks, bells and long ringing objects (gong, shop bell, lighthouse) only pass QA when the
rhythm or the partial set changes. Re-timing alone is not enough.

**Levels.**
- fx and interior families match the st-rms of the runtime synth they replace. `fx_synth` and
  `interior_synth` in `gen_props.py` are ports of `fx.gd _synth` and `interiors.gd sfx`.
- Field families match their original. New kinds match a sibling:
  - flap and flag → lid
  - peck → box
  - tweet → birds
  - bucket → coin
  - telescope → brass
  - arrive → whoosh
  - stand and seeds → paper
  - settle and hammock → wood_creak
  - chest → box; chest_rattle → box - 4 dB (the anticipation sits under the open)
- Doors match their own original file.
- `relevel()` corrects short takes once `finish()` has trimmed them. Every take is within
  0.83 dB of its reference.
- Sample rate is 22050 Hz, or 32 kHz for twinkle, coin, shutter, brass, telescope, ding, chime
  and clink.

**QA (2026-10-15)**, `sfx_qa.py game\assets\sfx\<dir>` with the originals, exit 0 for all four:

| dir | files (incl. originals) | families | max sim | median family max | max xc | max spread |
|---|---|---|---|---|---|---|
| fx | 124 | 21 | 0.887 | 0.816 | 0.556 | 0.72 dB |
| field | 162 | 25 | 0.899 | 0.838 | 0.836 | 0.54 dB |
| interior | 98 | 16 | 0.898 | 0.792 | 0.583 | 0.83 dB |
| doors | 112 | 28 | 0.897 | 0.800 | 0.791 | 0.60 dB |

The WARN lines are trailing silence in the git-tracked field and door originals. The new files
total 16.6 MB.

**Runtime.**
- `Fx.sound` picks through `sfx_bank.gd` with ±4 % pitch and ±1 dB. `Fx.take_for` and
  `SYNTH_FALLBACK` keep the synth as a stand-in while a family has no WAVs.
- `field_objects.play` uses the bag with ±3 % pitch and ±1 dB.
- `Interiors.sfx` returns the next take wrapped in an `AudioStreamRandomizer` that adds jitter.
  `Interiors.play(host, kind)` pools 4 players under the room.
- `Transition.door_stream` returns the room's next take, cached by the bank, and `play_door`
  adds jitter.
- `town.gd` keeps a distance-levelled campfire loop.
- Import settings:
  - `fx/firepit_loop_1.wav` needs `edit/loop_mode=2`. Without it, `town.gd` restarts the loop
    on `finished`.
  - Nothing here needs PCM.

## World: footsteps and ambience (`make_world_steps.py`, `make_world_ambience.py`, `diverse.py`)

```
.tools\art-venv\Scripts\python.exe tools\sfx\make_world_steps.py                       # 16 surfaces x walk/run x 14 + cloth 8 (about 3 min)
.tools\art-venv\Scripts\python.exe tools\sfx\make_world_ambience.py                    # 19 beds + 11 one-shot families (about 2 min)
.tools\art-venv\Scripts\python.exe tools\sfx\make_world_ambience.py --only beds        # or: --only spots, --only coast,bird,gull
```
Add `--scratch` to render into `$SFXWORK\world\` instead of the repo, and `--allow-overwrite` to re-render
files these generators wrote before (none of them is a team recording). Seeds are stable: a re-run
renders the same files.

**Outputs**
- `steps/<surface>_<walk|run>_<n>.wav`, n = 1..14, for grass, sand, stone, wood, rock, shallow, snow,
  ice, gravel, leaves, ash, dirt, planks, tile, rug, stairs; `steps/cloth_<n>.wav` (8, a cloth/gear
  rustle layered on about 30 % of hero steps). 22050 Hz.
- `ambience/<bed>.wav`: 60 s loops (coast, wind and their muffled twins 64 s): birds, insects,
  night, forest, waterfall, hearth (22050 Hz), coast (16000), birds_far, wind, frost, quarry,
  ember, clock, cafe (11025), mill (8000), room (6000), sea_muffled, wind_muffled,
  waterfall_muffled (5000). The rates follow the content and the 34 MB budget; the dark beds have
  nothing above their Nyquist. Insects, night crickets, forest leaves, waterfall spray and hearth
  crackle were squeezed against the 5.5 kHz Nyquist at 11025 Hz and moved to 22050 Hz on
  2026-10-15 (+1.32 MB each, same long-term level, `BED_DB` unchanged); texture grain lengths are
  written at 11025 Hz and scaled with `smp()`. `waterfall_muffled` was left as rendered from the
  11025 Hz waterfall (below 380 Hz nothing differs).
- `ambience/spots/<kind>_<n>.wav`: bird 16, gull 8, wave_crash 10, wave_slap 8, gust 8, cricket 8,
  owl 6, frog 8, rooster 3, windmill_creak 6, distant_bell 3.

**Footsteps.** A step is a list of contacts (heel, toe, flat plant, slide-in scuff, drag, weight
settle) rendered through a surface model: grainy band-limited noise, a body thump, resonant grit
grains, resonant modes (boards, rock, tile, ice, stairs), water, creaks and a small room for the
indoor floors. Candidate k takes one of 14 contact rhythms (7 per texture variant), a tone
(band shift x sole formant x thump weight) and a grit/decay size from a `cycle()` grid. Running
takes are shorter, harder and brighter (audio_check measures both).

**Beds** are periodic by construction: noise is shaped in the frequency domain over the whole loop,
slow envelopes contain whole cycles of the loop only, events wrap around the end and reverbs are
circular convolutions, so the wrap is like any other sample (no crossfade). They carry no
identifiable events: bird phrases, wave crashes, gusts and close crickets are one-shots that
`ambience_spots.gd` scatters at random times and places. Beds sit at -20 dBFS long-term RMS; the
generator prints the `BED_DB` that `world_audio.gd` carries for its in-game target (`TARGET`).

**`diverse.py`** renders more candidates than a family needs and keeps a candidate only when sfx_qa's
own similarity (both directions, both resolutions) stays under 0.875 and the waveform correlation
under 0.90 against every take kept so far. Use it for any noise-like family where a plain grid
still leaves look-alike pairs:
`D.diverse_family(out_dir, event, n, fn, sr=..., ref_db=..., seed_base="...")`, where fn(rng, k)
renders candidate k = 0, 1, 2, ...

**Levels.** Steps: per-surface file reference `REF_DB` (st-rms -14..-18 dBFS; hard floors lower so
the limiter keeps their transient), `world_audio.gd SURFACE_DB` restores the in-game balance of the
earlier runtime synth (measured with a numpy port of it). One-shots: st-rms -12 dBFS; per-kind level
in `ambience_spots.gd KINDS`.

**Import** (the import stage): the 19 beds `ambience/*.wav` need `edit/loop_mode=2`,
`edit/loop_begin=0`, `edit/loop_end=-1`; everything else keeps the default (QOA). No file here is read
as `.data` at runtime (audio_check.gd reads the source WAVs).

**Runtime** (`world_audio.gd`, `ambience_spots.gd`):
- `footstep(surface, speed)` picks `steps/<surface>_<gait>` through the sfx_bank bag (no repeat), adds
  left/right foot offsets and the cloth layer; the old synth stays as a fallback when nothing is
  imported.
- `remote_step(at, surface, speed, db := -8.0)` has its own positional voices and bag; `stride(key,
  at, delta, surface, own)` turns any walker's position into steps.
- `land(speed, surface)`, `splash(size)`.
- `set_ambience({... "zone", "room", "hour", "windmill_at", "ember"})`, `room_ambience(theme)` and
  `room_surface(floor_kind, decor, at)` for interiors.
- `warm_beds()` reads every bed at once (loading screens, tests); otherwise beds load on a worker
  thread the first time they are wanted, and `prepare()` starts the village beds during the first
  loading card.

QA (2026-10-15): steps 456 files / 33 families, max sim 0.875, max xc 0.76, loudness spread <= 0.8 dB;
one-shots 84 files / 11 families, max sim 0.869, max xc 0.68, spread <= 0.4 dB; beds 19 loops, seams
clean. All `SFX_QA PASS`. New WAV bytes: 33,736,908 (steps 5.5 MB, beds 24.2 MB, one-shots 4.0 MB).

## Combat, creatures and the hero's voice (`gen_combat.py`)

`gen_combat.py` (with `gen_combat_kit.py` for shared helpers and `gen_combat_creatures.py` for
the monsters) builds on the helpers of `tools/make_creature_sfx.py` (vocal formant voice, snarl,
breathy noise, thud, debris, flame, bloop). It imports them and never runs that file's `main()`.
Everything renders at 32 kHz and is resampled per family:
- 22050 Hz by default;
- 32000 Hz for metal/stone/chime families: `hit_stone`, `hit_spirit`, `block`, `critical`,
  `dissolve`, the derived `harvest_*`, hero `reward` and `levelup`.

```
.tools\art-venv\Scripts\python.exe tools\sfx\gen_combat.py                      # everything (~1 min)
.tools\art-venv\Scripts\python.exe tools\sfx\gen_combat.py --only combat,hero   # groups: combat hero creatures layers steps
.tools\art-venv\Scripts\python.exe tools\sfx\gen_combat.py --family hit_flesh,wolf_idle
.tools\art-venv\Scripts\python.exe tools\sfx\gen_combat.py --list               # families, start index, rate
```

**Numbering and levels**
- Numbering continues after the highest original take of each event (git-tracked, or with
  `SFX_BASE=<ref>` the takes that existed at `<ref>`), so the older takes and the team recordings
  stay. `--root <dir>` renders into a scratch root (the family's originals are copied there).
- Re-running renders the same files from the same seeds. Untracked takes numbered past a
  family's range are removed.
- Each family is levelled to the median st-rms of its original takes. A new kind matches a
  sibling: `whiff` matches the swings, `equip`/`cold`/`hunger`/`ember`/`bandage` match `dodge`,
  `sputter`/`depleted_*`/`craft_*` match `fuel`, `night_warn` matches `night`, and
  `campfire_loop` matches `heartbeat_loop`.
- Creatures use the `make_creature_sfx.CREATURE_DB` targets per event.

**Families**
- combat/
  - swings: 12 per weapon, each one archetype from `SWING_SPECS`/`FIST_SPECS` (shape, sweep,
    length, extra layer); heavies: 6 each.
  - hits: 10 each; block 6, dodge 8, critical 5, spawn 6, dissolve 6, player_hit 8, fuel 5,
    night 3, dawn 3, harvest_berry 10.
  - `harvest_tree`/`stone`/`fiber` `_2.._12` are derived from the team recording `_1`:
    - tree: the recorded chop is the core, with new bodies, double chops, splinters, leaves,
      creaks;
    - stone: the recording's strikes re-cut into new rhythms, plus a dull rock ring, chips or a
      scrape kept low-passed under the strikes;
    - fiber: only the recording's own tear, re-cut (order, piece count and length, a pause in
      some takes, its own dynamics); no synthetic rip, root snap, soil pops or tilt any more.
    - stone and fiber are EQ'd back to `_1`'s long-term spectrum (`ltas_match()`: 1/12-octave
      bands, zero-phase, at most 9 dB, never a boost below 125 Hz), so the bag sounds like one
      material: fiber keeps the recording's 8-16 kHz rustle (37.7 % of the energy vs 35.7 % in
      `_1`, was 24 %). LTAS correlation with `_1` (40 log bands 100 Hz-10 kHz, band-averaged
      Welch): stone 0.96-0.99, fiber 0.87-0.97 (was 0.14-0.6). The review's centre-sampled variant
      gives stone 0.92-0.98 and fiber 0.56-0.91: for 0.15-0.3 s noise takes it is mostly Welch
      noise (a 0.15 s window of `_1` itself scores 0.57). Max sim in the family 0.85 / 0.80.
    - `harvest_fiber_1` opens with 98 ms of silence (the file stays): `combat_audio.gd` and
      `life_sfx.gd` start that take 0.09 s in (`LEAD_IN`).
  - new events: whiff 6, equip 5, sputter 5, `depleted_<tree|stone|fiber|berry>` 3 each,
    night_warn 3, cold 4, hunger 4, ember 4, `craft_<tool|soup|bandage>` 4 each, bandage 4.
  - `campfire_loop.wav`: 6.1 s, seamless (`loopify`). The import stage must give it
    `edit/loop_mode=2`.
- hero/: attack 10, hurt 8, harvest 8, eat 5, tired 5, faint 3, levelup 3, attack_heavy 5,
  pickup 6, dodge 5, reward 4. Each take is its own syllable, vowel, contour or length; the
  attack set is listed in `ATTACK_SPECS`.
- creatures/
  - `<species>_<event>_<n>`: 7 region-neutral takes per species x event. Each archetype has its
    own call count, contour, length and layer.
  - The original `<species>_<event>_<region>_1/2` takes stay in each region's runtime pool.
  - Region colour is a runtime layer, `layer_<region>_<accent|bed>_<n>` (6 accent + 4 bed per
    region), instead of three copies of every take.
  - `step_<paw|hoof|stomp|squelch|flutter>_<n>` (8/8/8/8/6) are monster footfalls.
  - `boar_charge_<n>` and `boar_dazed_<n>` have 6 each.

**QA**
- Every family passes `sfx_qa.py`: `combat/`, `hero/` and `creatures/` exit 0. The only WARNs
  are git-tracked files: the older near-duplicate takes and the recordings' header shape.
- The runtime pools are checked too: neutral takes plus each region's own takes, as one family
  per region. All 90 pools pass.
- The checks behind these numbers are in the scratch folder `sfxwork/combat/`: `qa_fams.py`
  (per family, in-process), `qa_pools.py`, and the contact sheets/JSON.

**Runtime**
- `combat_audio.gd`, `creature_audio.gd` and `hero_voice.gd` pick through `sfx_bank.gd`
  bags.
- `creature_audio.gd` pools are `pool_paths()`; a region layer plays under a region-neutral
  take; `step()` plays footfalls.
- `combat_audio.gd` adds:
  - `swing()` combos, where every third swing is heavy;
  - spawn/dissolve stagger: 60–250 ms apart, at most 4 per burst;
  - the `campfire()` loop with a watchdog;
  - `cue()`, `edge()`, `changed()`, `later()`, `depleted()`, `craft()`.
- `audio_bank_check.gd` holds the minimum take counts and the playback checks.
