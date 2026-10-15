# Villagen Interaction Socket Standard v1 (ISS-1): final spec

## A. Verdict

| Criterion (1-10) | D1 ISS-1 (data first) | D2 (runtime first) | D3 (pragmatic) |
|---|---|---|---|
| Correct for Godot 4.7.2 | 7 | 9 | 8 |
| Fit for external humanoid clips | 9 | 8 | 6 |
| Smooth, continuous motion | 8 | 9 | 7 |
| Fit with today's code and PCK patching | 6 | 7 | 9 |
| Demo stability | 5 | 5 | 9 |
| Testability | 9 | 8 | 8 |
| **Average** | **7.3** | **7.7** | **7.8** |

**D1** has the strongest standard:
- an importer-safe name grammar;
- a warp built from the clip-start root curve plus `socket_ref`;
- reference-skeleton tiers and a reference-prop kit;
- a validator and the best test plan.

It loses points on four counts.
- **Its new JSON would not ship.** `game/data/rigs`, `game/data/sockets`, `assets/anim/ix/index.json` and the `*.ix.json` sidecars are outside `include_filter` (game/export_presets.cfg:10, 46, 82), so every PCK would silently lack them.
- **It writes sockets into generated files.**
  - `environment_layout.json` is rewritten by tools/prepare_archipelago_environment_layout.py:328 and tools/build_archipelago_fitted_bridges.py:142-143.
  - `assets/interior/manifest.json` is written by tools/generate_interior_assets.py, and `Interiors.manifest()` keeps only five keys (interiors.gd:1373).
- **Two assumptions are wrong.**
  - The index file is unnecessary: `ResourceLoader.list_directory` strips `.import`/`.remap` (core/io/resource_loader.cpp:1741-1743) and is exposed to GDScript (core/core_bind.cpp:160).
  - Its role-based server templates assume a `seat` role. Rest archetypes bind only a root `whole` role (server/archetype_library.py:379-383, 434-442, 461-464).
- **Smaller gaps.** The import option is `animation/import_rest_as_RESET`, not `_reset`. There is no demo-first ordering.

**D2** has the most accurate engine facts:
- there is no inertialization anywhere in `scene/`;
- `play_with_capture` captures only VALUE tracks set to UPDATE_CAPTURE (animation_mixer.cpp:2368);
- RetargetModifier3D calls `find_bone(<profile name>)` on both skeletons;
- the JSON export trap;
- the Z-up axis calibration.

It also has the richest smoothing toolbox: a blend table, a residual root warp, a variant chooser and input buffering.

It loses points on four counts.
- **Visual ownership.** "The driver owns the visual transform" collides with player.gd, which writes `visual.position` every frame (287-294) and `visual.rotation` every tick (334).
- **Root anchored at the socket.** This makes the body jump to the anchor at ENTER and relies on a custom inertializer to hide it.
- **Duplicated limiter.** It misses that `locomotion_pose` already limits angular velocity on every body bone every tick (locomotion_pose.gd:14-35, 99-110).
- **Two factual slips.**
  - "Facing +Y in Blender = +Z in glTF" is wrong: Blender −Y maps to glTF +Z, and Explorer B itself faces +X (style_character.gd:18).
  - `game/tools_internal/` would ship, because `exclude_filter` only drops `tests/*`.

**D3** has the best fit and demo path:
- it moves the body inside the physics tick (`tick_from` at player.gd:300, `tick_to` at 368), so render interpolation stays on;
- it needs only about 20 lines in player.gd;
- `rest_seat` becomes a facade over the new driver;
- the pose layer overrides instead of adding;
- prop sockets live in code;
- the P0 order and its fallback are explicit.

It loses points on three counts.
- The external-clip contract is thin: no reference-prop kit, no root motion, and a registry JSON that needs a preset edit.
- On low or high seats, feet float or sink until leg IK exists.
- It places the pose layer "at the RestPose position", which is after `locomotion_pose` (rest_seat.gd:31-33 appends with `add_child`). It must go before.

**Base: D3** for structure, demo order, player hook and facade. Grafts:
- from D1: the standard itself, warp math, validator and tests;
- from D2: `.res` clip sets with markers and measured metadata, the blend table, the variant chooser, input buffering, IK axis calibration, and tools under `tests/`.

## B. Conflicts resolved

| # | Conflict | Decision | Why |
|---|---|---|---|
| C1 | Root motion: D1 extracts a root curve; D2 fixes Root at the socket anchor; D3 has none | Frame 0 has Root at the feet. ENTER/EXIT clips **may** move Root (xz and yaw); HOLD clips may not. The bake moves Root motion into meta `root_curve` and zeroes the Root track. In-place clips have R(t)=I. | Works for root-motion and Mixamo-style sources alike. The body never jumps; warping bends the path instead. |
| C2 | Seat-height correction: hips offset plus leg IK (D1/D2) vs moving the root down (D3) | Mode `root` (D3) is the default and the demo path. Mode `hips` (feet planted) switches on per rig once leg IK passes calibration (WP11). | Hips mode needs IK axes on the Z-up Tripo rig, which are unverified. |
| C3 | Continuity guard: a custom inertializer (D2) vs nothing | Use the existing limiter (20 rad/s body, 24 rad/s legs, locomotion_pose.gd:14-35). It runs every tick even when foot IK is off (99-110). New GDScript pose writers go **before** `locomotion_pose`. IK and LookAt go after it with ramped influence. The inertializer becomes optional WP18, triggered only by lab results. | The limiter is already paid for and tested by locomotion_continuity (pass < 25°/tick). |
| C4 | Data storage | No new JSON folders and no preset edit. Rig, item, interior-kind and map-prop data live in GDScript const modules. Clips are one `.res` AnimationLibrary per set under `res://assets/anim/interact/`, found with `ResourceLoader.list_directory`. Sidecar JSON stays in the art inbox. | The include filter is explicit in all 3 presets. Two candidate JSON hosts are regenerated by tools. |
| C5 | Socket source order | Fixed assets use authored consts. Crafted objects derive on the client from real geometry. Server templates (WP16) are only **hints**: type, count, yaw, xz. The client always snaps height to the mesh. The bbox formula is the last resort. The owner's 쉬기 (rest) flag decides **whether** something is a seat; sockets decide **where and how**. | Static crafts are one Tripo mesh generated from text. The designed parts survive only in `designed` (asset_studio.py:808); `static_plan` runs at 810. One-piece fitting keeps proportions (asset_assembly.gd:200-207). Voxel boxes are quantized (GRID 10, craft_collision.gd:11): up to 0.16 m on a 1.6 m bench. |
| C6 | Who owns the visual | The driver never writes `visual`. It writes the body position and `facing` inside the tick, plus two hook fields: `face_override` (exact yaw) and `clip_override`. | player.gd owns `visual` (287-294, 334). |
| C7 | Approach | D3's mover strategy: `player.steer` in the village (`move_and_slide`, real collision) and `studio.move_hero` in rooms with door/stairs side effects off. No navmesh. Movement input cancels APPROACH immediately; input during ENTER is buffered. | Player intent wins; this is the commercial-RPG feel. |
| C8 | Presence | Optional Strict `ix` submodel `{k,p,c,t0,o,s,h}`, gated by `/health.interaction_sync==1`. `t0` is on the sender's clock (RemoteMotion.now()). | Matches remote_motion's delayed playhead. A pose-only field (D3) cannot follow rocking seats. |
| C9 | Lying | The CharacterBody3D always stays upright. Procedural lie tilts the Root bone around Hip; clip lie plays the clip. | rest_seat.gd:87 tips the capsule today. |
| C10 | Clip names | D1's grammar `family_variant_phase[_qualifier]`. The validator enforces it, but **meta is the truth**, not the name. | Importer-safe and human-readable. |
| C11 | Pose layer position | `move_child(ix_pose, locomotion_pose.get_index())`, so it runs before the limiter. | Modifier child order is processing order (skeleton_3d.cpp:1177-1212). |
| C12 | AnimationTree | Not in v1 (all three agree). The data stays compatible with a later move. | MANUAL advance and gait-phase sync (player.gd:113, 339-359). |

## 1. Invariants (every test checks them)

| Code | Invariant |
|---|---|
| P1 | Body position and yaw change only inside `player._physics_process`, between `tick_from` and `tick_to`. Per-tick bounds are ≤ 0.08 m and ≤ 0.35 rad of visual yaw; the driver turns at ≤ 10 rad/s. The only exceptions are declared ABORTs: a scene change, or a target more than 3 m away. |
| P2 | One pose layer, which overrides rather than adds. It is never freed mid-pose. It fades through `influence` and is set `active=false` at 0. The engine applies influence to any modifier (skeleton_3d.cpp:1192-1207). |
| P3 | Every interaction runs CLAIM → APPROACH → ALIGN → ENTER → HOLD (⇄ ACT) → EXIT → RECOVER, with ABORT possible from any state. Geometry comes only from sockets. |
| P4 | Patch-safe. No change to project.godot, patch_boot.gd or export_presets.cfg. No autoloads and no `class_name`; scripts are preloaded consts. Bake and validation tools live in `game/tests/` (excluded from export). |
| P5 | Keep the original mesh (user rule). Sockets are bones, markers or data only. |

## 2. Frames, units, names

| Item | Rule |
|---|---|
| Units | Metres, seconds, radians. Data may give yaw in degrees (`yaw`, `*_deg`). |
| Up | +Y |
| Object frame | Front is +Z (asset_assembly.gd:105-107; interiors `fit_model`). The origin is the centre of the footprint on the floor (asset_assembly.gd:179). |
| Character frame | Origin = body root on the floor. +Z = `player.facing`; the visual's −Z faces it (player.gd:334). |
| Socket +Z | The direction the user's chest faces while using it: out of a chair, into a counter, through a door. For `lie`, see 4.2. |
| Clip data | All meta (`socket_ref`, start/end, `root_curve`) is in character-frame game metres, so `CHARACTER_SCALE` 1.7 is already applied. The bake converts from rig space using `forward_fix` (Explorer B GLB +X → character +Z, style_character.gd:18). Animators never type numbers; the kit measures them. |
| Clip rate | 30 fps baked |

**Name grammar** (from D1):
- **N1.** Identifiers match `^[a-z][a-z0-9]*(_[a-z0-9]+){0,5}$` and are at most 48 characters. The last token is never one of `loop`, `cycle`, `col`, `colonly`, `convcol`, `convcolonly`, `navmesh`, `rigid`, `vehicle`, `wheel`, `occ`, `occonly`, `noimp`. The meaning never rests on a trailing number. Reason: `_teststr` strips trailing digits and underscores (resource_importer_scene.cpp:429-447), and loop names are renamed (771-777).
- **N2.** Looping is meta, never a name; the looping phase is called `hold`.
- **N3.** Every GLB the bake reads is imported with `nodes/use_name_suffixes=false`, which turns off the whole suffix pass (666-670).
- **N4.** Node prefixes: `SK_<id>` for character socket nodes, `SO_<id>` for object socket markers, `SOCKET_<id>` for Blender empties. An empty parented to a bone imports as a BoneAttachment3D (gltf_document.cpp:4704-4716).

## 3. Character sockets: `game/scripts/ix/ix_rig.gd` (const data plus helpers)

**Profiles:**

| Profile | Rigs | Clips in v1 |
|---|---|---|
| `vrs` | Explorer B wardrobe/reference/motion; shadow folk and day villagers use the same MODEL/MOTION (shadow_figure.gd:60-61) | Yes |
| `tripo41_apose` | Legacy explorer/ranger/tinker; haeru_v1 | No: procedural pose plus approach/exit only (haeru runs without MANUAL advance or the modifier stack, player.gd:89-104) |
| `npc_cast` | `.L/.R` rig with ForeTwist | No; map declared, deferred |

**Humanoid map** (SkeletonProfileHumanoid name → Tripo bone, for `vrs` and `tripo41_apose`):

| Region | Map |
|---|---|
| Spine | Root→Root, Hips→Hip, Spine→Waist, Chest→Spine01, UpperChest→Spine02, Neck→NeckTwist01, Head→Head |
| Arms (Left/Right) | Shoulder→L_Clavicle, UpperArm→L_Upperarm, LowerArm→L_Forearm, Hand→L_Hand (same pattern on the right) |
| Legs (Left/Right) | UpperLeg→L_Thigh, LowerLeg→L_Calf, Foot→L_Foot, Toes→L_ToeBase |
| Fingers | `L_Thumb_01..03` → ThumbMetacarpal/Proximal/Distal; `L_Index_01..03` → Proximal/Intermediate/Distal; the other fingers follow the same pattern |
| Unmapped | Pelvis, NeckTwist02, all twist bones |

**API:**
- `detect(skel)`: `Hip` plus `R_Hand` → vrs or tripo41_apose by the arm rest angle; `Hips` plus `Hand.R` → npc_cast.
- `bone(skel, humanoid)`.
- `measure(skel)`, cached per skeleton instance:
  - `hip_height`, the same formula as rest_seat.gd:37-43;
  - leg reach and arm reach;
  - eye height;
  - `seat_drop` = 0.10, the "+0.1" in rest_seat.gd:72.
- `pose_axes`: a per-bone bend axis in the body frame, calibrated once because the Tripo armature is Z-up.

**Socket table:** each entry is `id → [humanoid bone, bone-local Transform3D in skeleton units]`. Socket nodes cancel the inherited skeleton scale, as player.gd:221 does.

| Socket | Bone | Definition |
|---|---|---|
| `root` | Root | Floor under the feet; +Z forward |
| `seat_contact` | Hips | Thigh-joint height minus `seat_drop`; aligned to `sit` sockets |
| `pelvis_lie` | Hips | Hips centre; aligned to `lie` sockets |
| `sole_l` / `sole_r` | Foot | Foot bone dropped to the floor plane at rest; foot IK goals |
| `grip_r` / `grip_l` | Hand | vrs: exactly `Transform3D(Basis(LEFT,FORWARD,DOWN), (-.015,.095,0))` (player.gd:220-221); left mirrored |
| `pinch_r` / `pinch_l` | Index_03 (fallback Hand) | Small items |
| `hold_front` | UpperChest | 0.25 m in front; two-hand carry and gifts |
| `back` | UpperChest | Backpack (player.gd:496-514) |
| `hip_r` / `hip_l` | Hips | Holstered tools |
| `eyes` | Head | LookAt origin and the target others look at |
| `mouth` | Head | Eat/drink targets |
| `head_top` | Head | Hats (player.gd:475-484) |
| `overhead` | Head | Nameplate and bubbles (social.gd:225-236 uses y = 2.05) |

- `socket_global(skel, id) -> Transform3D` is math only and creates no node.
- `socket_node(skel, id)` lazily creates a BoneAttachment3D with a child `SK_<id>`. It is used only where an engine node needs a target: held items and IK.
- A GLB `SOCKET_<id>` empty wins when present.
- **Item sockets** (`ITEM_SOCKETS` in `ix_data.gd`): `grip` (+Y toward the business end), `grip_2`, `tip` (rod tip `(0,1.63,0)`, player.gd:236), `rest`. To attach: `item.global = hand_socket.global * item_grip.affine_inverse()`.

## 4. Object sockets

### 4.1 Record (the same dictionary in consts, server JSON and debug output)

```gdscript
{"id":"seat_0","type":"sit","variant":"chair","carrier":"",
 "at":[0.0,1.0,0.10], "off":[0,0,0], "yaw":0, "snap":true,
 "params":{"back":true,"arms":false,"width":0.5,"depth":0.45},
 "approach":[{"at":[0,0,0.5],"off":[0,0,0.35],"yaw":180,"from":"front"}],
 "exit":"approach","cap":1,"group":"","repeat":null,"source":"authored"}
```

| Field | Rule |
|---|---|
| `id` | `[a-z0-9_]{1,32}`, stable, in unmirrored order |
| `carrier` | Empty: `whole_root` for crafts, or the prop/record root. Otherwise a part id, meaning that part's pivot node. |
| `at` | Fractions of the carrier box. x and z run −0.5…0.5 from the centre; y runs 0…1 from the bottom. Fixed assets may use `pos` in metres instead. |
| `off` | Metres added after shape scaling, for clearances that must not stretch. x is negated under mirror. |
| `yaw` | Degrees about +Y relative to object +Z |
| `snap` | When true, the client snaps y to the real surface under xz |
| `approach` / `exit` | Feet points; `yaw` is the facing on arrival. `exit:"approach"` reuses the approach points. |
| `repeat` | `{"axis":"x","pitch":0.55,"min_width":0.45}`, expanded after scaling |
| `source` | `authored`, `server`, `derived` or `bbox` |

### 4.2 Types (closed list; a new type means a schema bump)

| Type | Contact point | Valid range or key params | Aligned character socket | Procedural pose | Clip family |
|---|---|---|---|---|---|
| `sit` | Seat surface | Height 0.30-0.65 m. Params: `variant` (chair, stool, bench, sofa, armchair, throne, swing, rocker, saddle), `back`, `arms`, `width`, `depth` | seat_contact | sit / sit_low | sit |
| `perch` | High seat; legs dangle, no foot plant | Height 0.65-1.10 m | seat_contact | perch | perch |
| `sit_ground` | Floor or rug | Height < 0.15 m | seat_contact | sit_ground | sitg |
| `lie` | Mattress top under the pelvis. +Z points out of the entry side (the side you sit on before lying back). | `head` ∈ {l, r} as seen from that sitting character (swapped under mirror); `length` ≥ 1.55; `width` ≥ 0.55; `recline_deg`; `sunk` | pelvis_lie | lie (Root tilt) | lie |
| `stand_use` | Floor at the user's feet | `work_height`, `work_point`, `kind` (counter, desk, wall, lever, crank, instrument) | root | reach envelope | use |
| `reach` | Feet point (dynamic: plots, forage spots) | `target`, `band` (ground, low, mid, high) | root + grip_r | kneel / reach | reach, crouch |
| `grip` | Handle centre; +Y along the handle | `hand` (r, l, any, both), `style`, `motion` | grip_r / grip_l | IK only | inside other sets |
| `look_at` | Look point | `weight`, `radius` | eyes | LookAt only | none |
| `passage` | Threshold centre; +Z = inside | `inside`, `outside`, `handle` | root | walk | door |
| `place` | Surface point | `max`, `tags` | hold_front | reach | place |
| `talk` | Dynamic ring at 1.1-1.4 m around an NPC | — | root + eyes | ALIGN only | talk |

### 4.3 Sources (`game/scripts/ix/ix_sources.gd`, `for_node(node, rest_hint) -> Array`)

1. **Owner override.** Reserved for after v1; it needs a server-first `Choice` field.
2. **Authored consts** in `game/scripts/ix/ix_data.gd`:
   - `INTERIOR_KINDS`:
     - wooden_chair: 1 sit;
     - armchair: 1 sit, `arms`;
     - sofa: sit with repeat 3;
     - bench: sit with repeat 2;
     - bed: 1 lie plus 2 sit (edge, `back=false`);
     - bathtub: lie, `sunk`;
     - toilet: sit, stool variant;
     - one `stand_use` per `Interiors.ACTIONS` kind (interiors.gd:203).
   - `PROP_MODELS`: 26_bench (2 sit), 25_picnic_table (4 sit), 32_cafe_chair (1 sit), 29_beach_lounger (1 lie, recline 25°). Values are in the model frame and are measured in the lab before use.
   - `from_field_entry(entry)`: swing, rocker and hammock, using `seat_local`, `pivot`, `front` and `stand` with `carrier` = the pivot.
3. **Crafted objects** (client derivation, cached in node meta `ix_sockets` keyed by `size`, `shape` and runtime version):
   - (a) **Server hints.** If `interaction.sockets` is present (WP16), take type, count, yaw and xz from it.
   - (b) **Multi-part crafts.** Derive from the designed part boxes, which fit exactly (asset_assembly.gd:200-207). The carrier is the pivot of the part holding the surface, so rocking and swinging come for free.
   - (c) **One-piece crafts.** Find candidates on the collision boxes (`base_center`/`base_size`, model_loader.gd:168-194).
   - (d) **Height snap, always.** Cast a vertical ray against `CraftCollision.surfaces(root)` triangles (`Geometry3D.ray_intersects_triangle`) at the socket xz. Take the highest hit below a ceiling of `t_candidate + 0.25`. This runs once per object and shape version.
4. **Bbox fallback.** Today's formulas, corrected: seat height = `min(size.y*0.5, 0.5)`. These sockets are shown amber in the gizmo.

### 4.4 Derivation rules (base frame, k = 1)

**`sit`:**
1. Candidate box tops `t` lie in 0.25-0.75 with an area of at least 0.30×0.30 m.
2. Merge coplanar tops (|Δt| < 0.04 that touch). Pick the largest area; on a tie, the lower one.
3. The back is a box with top > t+0.20 lying within 0.15 m of one edge. Front is the opposite side; default +Z.
4. Arm boxes on ±X reduce the usable width.
5. Seat count: n = clamp(floor(width/0.55), 1, 4).
6. Hip point: front edge − fwd·clamp(depth·0.55, 0.12, 0.30), at height `t`, then snapped.

**`lie`:** the largest top in 0.12-0.95 with length ≥ 1.3 and width ≥ 0.55.
- The head goes toward a taller box (headboard). Otherwise toward −Z, or −X when x > z (as today).
- The pelvis sits at the centre shifted 0.10 toward the feet.
- The entry side is the free long side, defaulting to +Z.

**Other types and degradation:**

| Condition | Result |
|---|---|
| Highest top < 0.12 | `sit_ground` |
| Top 0.75-1.10 | `perch` |
| Lie length too short | `sit` (bed edge) |
| Top > 1.10 | Rejected; toast "너무 높아요" |

### 4.5 Runtime resolution (`ix_math.resolve(rec, ctx) -> {origin, basis, carrier, params, approach[], exit[], valid, why}`)

1. **Point in the carrier frame.**
   - Whole carrier: `p_b = box.pos + box.size*(at + (0.5,0,0.5))` in the base frame (or `pos`). Then `p_k = p_b * k` (componentwise; object_transform.gd:116-119 scales the ShapeFrame position and scale by k) + `off`. Finally `origin = whole_root.global_transform * p_k`.
   - Part carrier: `p_pivot = (-pivot + (fx, fy-0.5, fz)) * part.size`, then `origin = pivot.global_transform * p_pivot`. The pivot-local designed box follows from `fit_part` at asset_assembly.gd:207.
   - Both forms carry the placement yaw, size factor, per-axis shape, mirror, `whole_root` motion and part motion.
2. **Orientation never inherits scale or mirror.**
   - Take `f = carrier.global_basis * (sin(yaw), 0, cos(yaw))`.
   - `follow:"yaw"` (default): set `f.y = 0` and use `Basis.looking_at(f.normalized(), UP, true)` (use_model_front, so +Z is forward; core/math/basis.h:231).
   - `follow:"full"` (swing, rocker): use the orthonormalized carrier basis with x negated when `det < 0`, times `Basis(UP, yaw)`.
3. **Mirror** (`det < 0`): swap `l`/`r` in `hand`, `head` and `from`. Ids do not change.
4. **Parameters.**
   - Scale: `width *= |kx|`, `depth *= |kz|`; `length` follows the head axis.
   - Re-measure heights as `origin.y − floor_y`, where `floor_y` comes from a ray down on layers 1|2 or falls back to the holder's y.
   - Expand `repeat` after scaling.
5. **Validity.** Apply the type ranges using `ix_rig.measure()`.
   - The approach point must be free: `PhysicsDirectSpaceState3D.cast_motion` with a capsule of radius 0.32 and height 1.5 on layers 1|2|8|16.
   - An invalid socket stays listed (red in the gizmo, with a reason) but is never offered.
6. **Coordinate frames.** Everything is global. This removes today's mix of local and global frames (rest_seat.gd:46-52, main.gd:3525).

### 4.6 Approach, exit and occupancy

- **Candidates.** Authored, or generated: front at clamp(depth + 0.35, 0.35, 0.70), ±45° and both sides.
- **Ranking.** Clear straight path, then distance, then the turn needed.
- **Exit.** Re-chosen at exit time: the claimed point if free, else another free one. A chair against a wall exits to the side.
- **Occupancy.** A static `claims` dictionary in `ix_driver.gd`: `"<instance_id>:<socket_id>" → actor_id`. Remote (WP17) and NPC (WP15) claims join later.

## 5. Interaction driver: `game/scripts/ix/ix_driver.gd`

One Node per actor, owned by the `rest_seat` facade.
- **API:** `begin({node, socket_id|type, rest_hint, on_settled, on_done}) -> bool`, `request_exit()`, `abort(reason)`, `busy()`, `seated()` (ENTER through EXIT), `locks_input()`, `state`, `socket`.
- **Strategies:** `mover` is steer in the village or `studio.move_hero(dir, delta, travel=false)` in rooms. `input_allowed` is a Callable such as `main.world_movement_allowed`.
- **Tick:** `drive(player, delta)` is called by the player hook every physics tick.

| State | Behaviour | Leaves when |
|---|---|---|
| CLAIM | Pick the nearest valid, free, facing-compatible socket; choose the approach and the direction variant | Claimed; otherwise toast "자리가 없어요" |
| APPROACH | Skipped within 0.12 m and 25°. Steer at walk speed, decelerating over the last 0.5 m. Movement input cancels at once. | Arrived. No progress for 0.5 s, or start > 2.6 m away: SHORT_ALIGN when ≤ 1.2 m, else cancel with an icon bubble. |
| ALIGN | `visual_only=true`. Slide the residual with smoothstep; turn at ≤ 10 rad/s. Duration clamp(d/0.9 + \|Δθ\|/4.5, 0.15, 0.40) s. If \|Δθ\| > 60°, `external_velocity` = 0.6 m/s along the facing so the steps play. | Done |
| ENTER | Procedural: sit 0.55 s, sit_low/perch 0.5 s, sit_ground 0.6 s, lie 0.5 + 0.7 s. With a clip: the clip length. Root follows the warp (§7). Pose weight or clip plays. Input is buffered. | End, or the `settled` marker |
| HOLD | Re-resolve the socket every tick (moving carriers). Carrier tilt goes to the pose-layer Root tilt, never the body basis (fixes field_objects.gd:1402). | E, Esc, or movement while `input_allowed` |
| ACT | Masked one-shots (WP12) | End, back to HOLD |
| EXIT | Reverse toward the exit point. Procedural sit 0.5 s (×0.7 when started by a movement key); lie 0.4 + 0.5 s. | At u ≥ 0.8 or `exit_ok`: control returns; held movement blends into walk |
| RECOVER | Body already at the exit feet point. Restore `visual_only`. `facing` = socket +Z (fixes `Vector3.BACK`, rest_seat.gd:105). Release the claim. If `test_move` reports overlap, nudge to the next free candidate within 0.1 s. | 1 tick |
| ABORT | Triggers: piece freed, scene change, or a foreign move. The driver tracks its own last written position, replacing the 0.05 m check (rest_seat.gd:123). Weight goes to 0 over 0.15 s and the body stays. A look rebuild is **not** an abort: the pose layer re-attaches to the new skeleton. | Done |

**Player hook** (player.gd, about 25 lines, inert when `ix == null`):
- New fields: `var ix`, `var steer := Vector2.ZERO`, `var face_override := NAN`, `var clip_override := ""`, `var clip_blend := -1.0`.
- Call `ix.drive(self, delta)` right after line 300.
- `steer` becomes the movement when controls are off. It is treated like controls for `locomotion_velocity` and `look_motion` (327-328).
- `face_override` replaces the facing lerp (334).
- The clip switch honours `clip_override`/`clip_blend` (339-347).
- `react()` skips the squash while `seated()` (392-396).

**Gates:**
- main.gd sets `controls_enabled` in three places (1103, 2772, 2961). All three become `world_movement_allowed() and not ix_locked()`.
- studio.gd's walk gate (1997-1999) adds `not seat.driver.locks_input()`.
- The prompt at main.gd:2793 uses `seat.resting()`, so the facade maps `resting()` to `seated()`.

## 6. Animation runtime layering

Skeleton child order on Explorer B (it is the processing order):

```
action_pose → finger_pose → ix_pose (NEW; inserted before the limiter)
→ locomotion_pose (walk/run foot IK + angular limiter, always on)
→ [WP11] TwoBoneIK3D legs → TwoBoneIK3D arms → LookAtModifier3D head
→ [WP18, optional] inertializer
```

**`ix_pose.gd`** (SkeletonModifier3D):
- **Modes:** `sit`, `sit_low`, `perch`, `sit_ground`, `lie`, `kneel`, `reach_low`.
  - `lie` tilts the Root bone about Hip, with a compensating translation.
  - `kneel` samples Legs_Crouch_Step; `reach_low` samples Arms_Reach_Grip (both in explorer_b_wardrobe.glb, unused today).
- **Targets:** rest-relative rotations about body axes (the RestPose math, interiors.gd:2799-2810) through `ix_rig.pose_axes`. v1 angles are today's RestPose values: thigh 1.5, calf −1.55, upper arm 0.35, forearm 0.7.
- **Blend:** `slerp(anim_local, target_local, mask[bone])`. Masks: legs 1.0, spine 0.6, arms 0.5, head 0 (owned by LookAt). The idle keeps breathing in the upper body.
- **Fade:** the overall weight is `influence`; `active=false` at 0.
- **Test compatibility:** a `mode` property, because village_rest_check reads `seat.pose.mode`.
- **WP9:** masked clip overlays sampled with `Animation.rotation_track_interpolate` (the finger_pose pattern).

**Clips (WP9):**
- AnimationPlayer stays the only full-body mixer: MANUAL, advanced at player.gd:356-357.
- The `ix` library is added beside `movement` and `""`.
- The locomotion switch is suspended while `clip_override` is set; `speed_scale` is 1.

**Blend policy** (clip meta overrides it):

| Transition | Blend |
|---|---|
| idle/walk → enter | 0.20 s |
| enter → hold | 0.00-0.08 s (the validator demands a matching boundary) |
| hold → act (masked) | 0.15 s in / 0.20 s out |
| hold → fidget | 0.25 s / 0.25 s |
| hold → exit | 0.20 s |
| exit → locomotion | 0.25 s, or 0.18 s at `exit_ok` with input |
| abort | 0.20 s |

## 7. Warping math (`ix_math.gd`, static, unit-tested)

**Definitions:**
- `S` is the resolved socket and `floor_y` the floor height under it.
- From clip meta:
  - `R(t)`: the root curve (identity for in-place clips);
  - `C = socket_ref`: the socket in clip-start space, measured at `contact`;
  - `h_ref`: the reference height.
- Markers: `tb = warp_begin` (default 0), `tc = contact` (default 0.7·len).
- `α(t) = smoothstep(clamp((t−tb)/(tc−tb), 0, 1))`.

**Formulas:**

| Part | Formula |
|---|---|
| Planar warp | `W0 = flat(S)·flat(C)⁻¹`, where `flat` drops y and keeps yaw. `A0` is the root at ENTER start. `E = A0⁻¹·W0`. Clamp \|E.xz\| ≤ 0.35 m and \|E.yaw\| ≤ 45°; beyond that, re-ALIGN or pick another variant. |
| Root path | `Root(t) = A0 · lerp_T(I, E, α(t)) · R(t)`. For t ≥ tc this equals `W0·R(t)`, so the contact lands exactly on the socket. |
| Vertical | `Δh = (S.y − floor_y) − h_ref`, clamped to ±0.18 m (`warp_limit`); beyond that, use another variant (sit_low, perch, sitg). Mode `root`: offset `root.y` by `Δh·α(t)`. Mode `hips` (WP11): offset Hips by `Δh·α(t)` with leg IK planting the feet. |
| Procedural virtual clip | `R = I`. Hold root `H.xz = S.xz`, `H.y = S.y + seat_drop − hip_height` (rest_seat.gd:72). `pos.xz(u) = lerp(A.xz, H.xz, smoothstep(0.10, 0.85, u))`; `pos.y(u) = lerp(A.y, H.y, smoothstep(0.25, 1.0, u))`; weight `w(u) = smoothstep(0, 0.9, u)`. Lie: Hip at the mattress point + 0.12 up. |
| HOLD | Clip: `Root = S(t)·C⁻¹·R(t_end)`. Procedural: `H` is recomputed from `S(t)` every tick. The carrier's pitch and roll go to the ix_pose Root tilt. |
| EXIT | Mirror image. `β(t)` runs over `[release, warp_end]` and blends from the seated path to `E_exit·R_exit(end)⁻¹·R_exit(t)`. |

**Continuity:** α and β have zero slope at both window ends, so there is no velocity step. Per-tick bounds are asserted by the tests.

## 8. External animation contract

1. **Canonical skeleton (VRS)** is the Explorer B bind: explorer_b_wardrobe.glb, 71 joints. The 41 body bones are required; fingers are optional.
   - **Tier A:** authored on the kit rig.
   - **Tier B:** any humanoid (Mixamo `mixamorig:*`, Rigify `DEF-*`, UE Mannequin, VRM, video mocap) plus a bone map. `tools/ix_intake.py` (Blender, headless) does:
     - a rest-aligned world-rotation retarget: `q_tgt_local = rest_tgt_parent⁻¹·(R_src_world·rest_src_world⁻¹·rest_tgt_world)`;
     - hips translation scaled by the leg-length ratio;
     - forward reoriented to the kit arrow;
     - a 30 fps bake;
     - root policy `none|xz` (moving hips travel into Root);
     - foot-contact cleanup.
   - The runtime only name-copies VRS clips. RetargetModifier3D is unusable here, because it needs profile-named bones in both skeletons.
2. **Kit.** `art/anim_kit/villagen_ix_kit_v1.blend` and `.glb`, built by `tools/ix_kit_export.py`:
   - the VRS armature at its exact bind, with object scale 1.7 unapplied, so the scene is in game metres;
   - an arrow empty marking the rig's forward (+X in both the GLB and Blender for Explorer B; never assume −Y);
   - a floor grid;
   - reference props with `SOCKET_<type>_<id>` empties at the reference dimensions below.
3. **Rules:**
   - At frame 0, Root is at the feet facing the arrow.
   - ENTER/EXIT may move Root. HOLD keeps Root still (|Δ| < 1 cm) and loops between `loop_in` and `loop_out` within 2° per bone and 5 mm on the hips.
   - Vertical motion lives only on Hips.
   - No scale tracks.
   - Length: ENTER/EXIT/ACT ≤ 8 s; HOLD ≤ 20 s.
   - The ENTER last frame must match the HOLD first frame within 3° and 1 cm (otherwise a warning, and the blend becomes 0.12 s).
   - The ENTER first frame and the EXIT last frame must be within 15° per bone of B_Scout frame 0.
4. **Reference dimensions (m):**

   | Prop | Reference |
   |---|---|
   | chair / bench | 0.45 |
   | sofa | 0.42 |
   | low stool | 0.30 |
   | bar stool (perch) | 0.72 |
   | ground | 0 |
   | bed | top 0.50, length 2.0, width 0.9 |
   | hammock | 1.0 |
   | sunbed | 0.35 with a 35° backrest |
   | counter | 0.90 |
   | desk / table | 0.75 |
   | shelf | 1.40 |
   | planter | 0.25 |
   | door handle | 1.0 at z +0.45 |
   | talk partner | 1.1 away |

5. **Names.** `family_variant_phase[_qualifier]`.
   - Families: sit, perch, sitg, lie, use, reach, crouch, door, talk, give, take, carry, tool, act, emote.
   - Phases: enter, hold, exit, act, fidget, react.
   - Qualifiers: l90, r90, b180, headl, headr, hr, hl, a, b.
   - A set is `family_variant`. Fallback chain: exact set → `family_any` → procedural.
6. **Markers** (`Animation.add_marker`, animation.cpp:4044-4051): warp_begin, contact, settled, release, warp_end, exit_ok, interrupt_from, grip_on, grip_off, handover, loop_in, loop_out, foot_l_plant, foot_r_plant.
   - Events go in a meta list, not in markers: `sfx_*`, `fx_*`, `obj_click`, `item_show`, `item_hide`.
7. **Meta.** `Animation.set_meta("ix", {...})` holds:
   - schema `villagen.clip/1`, family, variant, phase, qualifiers, rig `vrs`, source {tool, license, author};
   - loop, mask (full, upper, arm_r, arm_l, head, lower), blend_in, blend_out;
   - ref dims, warp_limit;
   - `socket_ref`, start and end (measured from the kit or estimated from the hips at `contact`);
   - `root_curve` (packed samples);
   - curves: ik_foot_l, ik_foot_r, ik_hand_r, ik_hand_l, look;
   - events.
8. **Drop-in (no code change):**
   1. Put the source and an optional `<clip>.ix.json` sidecar into `art/anim_inbox/<family>/`.
   2. Run `python tools/ix_intake.py`. It writes VRS GLBs to `art/anim_baked/`, imported with `use_name_suffixes=false`, fps 30, `remove_immutable_tracks=true`, `import_rest_as_RESET=false` and `import_as_skeleton_bones=false`.
   3. Run `godot --headless --path game --script res://tests/ix_clip_bake.gd -- <dir>`. It validates the clips and writes `game/assets/anim/interact/<set>.res`.
   4. Export the patch with tools/game_patch.py.

   At runtime, `ResourceLoader.list_directory("res://assets/anim/interact")` discovers the sets, and each set loads lazily on first use.
9. **Validator** (shared by the bake and the runtime test). It rejects:
   - names breaking N1;
   - bones outside VRS;
   - fps other than 30;
   - Root drift in HOLD or a frame-0 Root that is not identity;
   - a broken HOLD seam;
   - missing required markers (enter: contact; exit: release);
   - markers out of order (warp_begin < contact ≤ settled);
   - quaternion sign flips;
   - non-identity scale tracks;
   - lengths over the limits;
   - a `socket_ref` more than 1.2 m from the start root;
   - a plant foot higher than 2 cm.
10. **Placeholders.**
    - The procedural virtual clips need no asset.
    - The bake also produces `sit_any`, `lie_any`, `crouch_any` and `reach_any` sets, from keyed procedural poses, Legs_Crouch_Step and Arms_Reach_Grip.
    - An external clip replaces a placeholder set purely as data.

## 9. NPCs and multiplayer

**NPCs (WP15):**
- `ix_actor.gd` is an adapter exposing `skeleton`, `animator`, `visual`, `set_facing`, `walk_to` and the rig profile.
- Residents walk to the approach point and ENTER when visible. An off-screen start goes straight to HOLD; this is the only snap allowed.
- `shadow_figure.bend()` and the `pose_resident` formulas (studio.gd:2425-2470) are deleted.
- Gifted crafted chairs work through crafted derivation (studio.gd:2746-2797), and residents and the player share socket claims.
- LOD: no IK beyond 15 m or off screen; the existing animation strides stay.

**Presence (WP17):**
- `Presence.ix: IxState | None = None`, a Strict submodel. Its fields:

  | Field | Meaning | Limits |
  |---|---|---|
  | `k` | Socket type | Literal of the types |
  | `p` | Phase | enter, hold, act, exit |
  | `c` | Set | ≤ 48, `[a-z0-9_]` |
  | `t0` | Sender clock (`RemoteMotion.now()`) | — |
  | `o` | Object ref: `obj:<id>`, `prop:<model>#<n>`, `fx:<id>`, `rf:<floor>:<i>` | ≤ 64 |
  | `s` | Socket id | ≤ 32 |
  | `h` | Δh | −0.3…0.3 |

- Server: a guarded `ALTER` adds `mp_presence.ix` (the pattern at multiplayer.py:96-101). `ix` is echoed in village players and room peers.
- `/health` gains `interaction_sync: 1` (app.py:266-271); `multiplayer_protocol` stays 1 (main.gd:313, 759).
- Client:
  - Send `ix` only when the server advertises the flag.
  - A 422 while sending `ix` disables `ix` only. Today any 422 drops rich presence (social.gd:153-155).
  - Remote puppet: play the phase from `t0` on remote_motion's delayed clock and apply `h`. Lock onto the local socket when `o`/`s` resolves; otherwise follow presence spots.
  - If two players claim one seat at once, the earlier `t0` keeps it, then the lower user id.
- Deploy the server first. The judges' server stays untouched, so the flag is absent there and the feature stays off.

## 10. Debugging and lab (WP5)

**`ix_debug.gd`** (ImmediateMesh plus Label3D) draws:
- socket axes;
- type colours: sit gold, lie blue, use green, grip orange or purple, look white, approach/exit cyan, claimed grey, invalid red, bbox amber;
- approach and exit arrows;
- the driver's state and phase;
- the contact error vector in cm.

It is toggled by an F3 dev panel checkbox or `--ix-debug`. It is off by default and costs nothing when off.

**`game/tests/ix_lab.gd`** (windowed on the BenQ screen via tools/test_window_position.ps1):
- **Cases:**
  - box seats at 0.30, 0.45 and 0.72;
  - the interior kinds;
  - crafted fixtures: a rocking chair (rocking), bed, bench, sofa;
  - the map props.
- **Variations:** yaw 0, 90 and 217; shape 50, 100 and 200 % width; mirrored copies.
- **Run:** the cycle is scripted from 3 directions.
- **Output:** `artifacts/ix/<case>_<phase>.png` (6 frames per phase) and `artifacts/ix/lab.json` (contact error, maximum root and joint steps, exit clearance).
- **Doc:** feeds the Korean doc in `docs/interaction_standard/` (figures, QA table, failures).

## 11. Migration map

| Today | Becomes | WP |
|---|---|---|
| `rest_seat` teleport + RestPose (rest_seat.gd:59-105, interiors.gd:2794-2822) | Facade over the driver; RestPose deleted | 2, 4 |
| Crafted seats and beds (studio.gd:1710-1725, main.gd:3521-3567) | Derived sockets; `whole_root`/pivot carriers, so rockers carry the sitter | 3, 4 |
| Swing, rocker, hammock with SeatPose (field_objects.gd:1351-1455) | Socket records with a pivot carrier; SeatPose deleted; EXIT to `entry.stand` | 8 |
| Map benches etc. (`react('eat')`, town.gd:286-375) | Real sit/lie through `PROP_MODELS` | 6 |
| Use actions (studio.gd:1761-1790, 2191) | `stand_use` plus a reach envelope plus LookAt; no squash | 12 |
| Farming (village_life.gd:320-404) | `reach` sockets, a short input lock, tool scale ramps | 12 |
| Fishing (fishing.gd:93-177) | ALIGN to the cast point; a stance clip later | 12 |
| Doors (main.gd:3354-3375, studio.gd:707-714) | `passage`: walk through under the veil, step in on arrival | 13 |
| Talk (main.gd:3244-3317) | Turn within 20° or 0.4 s before the modal opens | 7 |
| Residents and shadow poses (studio.gd:2378-2536, shadow_figure.gd:828-889) | NPC driver; `bend()` deleted | 15 |
| Tool, hat and backpack literals (player.gd:197-236, 475-514) | Character and item sockets | 14 |
| Presence without pose (multiplayer.py:68-78) | `ix` submodel | 17 |

## 12. Tests and acceptance thresholds

**Thresholds:**

| Measure | Threshold |
|---|---|
| Body step | ≤ 0.08 m per tick |
| Visual yaw step | ≤ 0.35 rad per tick |
| Joint step | < 25° per 60 Hz tick (the locomotion_continuity metric) |
| Contact error (procedural) | ≤ 3 cm |
| Contact error at `contact` (clip) | ≤ 2 cm |
| Exit position | Within ±0.05 m of the exit point |
| Exit facing | Socket +Z ±5° |
| After RECOVER | No overlap |
| E to sitting from 1 m | ≤ 2.0 s |

**Sampling rule:** read final bone poses in the **last** modifier's `modification_processed` signal, because Skeleton3D restores the base pose after drawing. Today locomotion_continuity reads `previous_solved` and misses later modifiers.

**Must stay green:** controller_acceptance, explorer_b_integration, locomotion_continuity, field_objects_check, home_roundtrip, home_visit, door_sounds_check, npc_dialogue, multiplayer, residents_check, avatar_rooms_check, furniture_stress, hud_fold_check, compile_all.

**Expected test changes:** village_rest_check changes by design:
- "stands where it stood" becomes "stands at the exit point";
- the lie check `basis.y.y < 0.2` becomes "body basis identity, Hip on the mattress".

## 13. Work packages and demo plan

| WP | Title | Demo |
|---|---|---|
| 1 | ISS core schema and math | **DEMO** |
| 2 | Rig map and unified pose layer | **DEMO** |
| 3 | Object socket sources | **DEMO** |
| 4 | Driver, player hook, rest_seat facade | **DEMO** |
| 5 | Gizmo, lab, Korean standard doc | **DEMO** |
| 6 | Map props really seat | demo-optional |
| 7 | Talk turns before the dialogue | demo-optional |
| 8 | Field objects on the driver | after |
| 9 | Clip runtime and placeholder sets | after |
| 10 | Intake, kit, contract doc | after |
| 11 | IK and LookAt | after |
| 12 | Short actions | after |
| 13 | Doors | after |
| 14 | Character and item sockets | after |
| 15 | NPCs | after |
| 16 | Server socket hints | after |
| 17 | Multiplayer sync | after |
| 18 | Inertializer (only if the lab demands it) | after |

**The demo** (main topic: in-game object creation) needs WP1-5.
- Payoff: craft a chair, place it, press E, and the character walks up, turns, sits down smoothly, rocks with the chair, and stands up facing out.
- **Fallback if WP4 slips:** ship WP2 alone. It brings the blended pose layer, plus the exit facing set to the seat's front instead of `Vector3.BACK`.
- Every WP ships as a PCK patch with its own Korean test note and figures (user rule).

## 14. Open decisions (defaults so work can start)

1. **Clip sources:** Tier B intake, free sources first (Blender-authored, licensed Mixamo, the video lab). Paid Tripo or Scenario generation only with an explicit credit cap from the user.
2. **Remote sitting:** visible, behind the `interaction_sync` flag.
3. **Owner socket editing:** after v1.
4. **NPC cast rig:** deferred.
5. **AnimationTree:** deferred.
6. **Map props:** they really seat; the prompts already promise it (town.gd:82-90).
7. **Crafted VM click** (main.gd:3545): stays immediate in v1; it moves to the `contact` marker once clips exist (WP9).


## Work packages

### WP1 [DEMO] ISS core: schema and pure math
- Goal: Build the pure, testable core with no runtime behaviour change.
- ix_schema.gd: the closed lists (socket types, phases, families, character socket ids), the N1 name grammar and banned last tokens, and record normalisation with defaults.
- ix_math.gd:
  - record to point: at+off, or pos in metres;
  - shape factors k and mirror;
  - carrier transform: whole_root, or a part pivot via (-pivot+f)*size;
  - yaw-only and full bases (Basis.looking_at with use_model_front);
  - parameter scaling and repeat expansion;
  - validity ranges;
  - approach candidate generation and ranking, with physics checks injected;
  - warp functions: residual E with clamps, alpha windows, Root(t), the vertical Δh warp, and the procedural virtual-clip curves for sit, sit_low, perch, sit_ground and lie.
- Files: game/scripts/ix/ix_schema.gd, game/scripts/ix/ix_math.gd, game/tests/ix_math_check.gd
- Tests: Resolution under yaw 0/37/90/217/359, shape 50/100/200 % per axis, mirror, and a part pivot rotated 20 deg: contact point within 1 mm of the analytic value; basis orthonormal with det +1; l/r swapped and ids stable under mirror; Bench repeat: 1.5 m gives 2 seats and x2 width gives 5; frac+off and pos round-trip; Warp: Root equals A0*R(tb) at tb and W0*R(t) for t>=tc within 1 mm; zero velocity step at window ends; per-tick step <=0.08 m at 60 Hz for durations >=0.45 s; out-of-clamp residual is reported; Name grammar accepts sit_chair_enter_l90 and rejects sit_loop, sit_chair_cycle, grip-col and names ending in digits
- Risk: Low: pure functions with no wiring.

### WP2 [DEMO] Rig map and unified pose layer
- Goal: Two new scripts and a small rest_seat change.
- ix_rig.gd:
  - profiles vrs, tripo41_apose and npc_cast, with clip flags;
  - detect(), and bone() by humanoid name;
  - measure(): hip height as in rest_seat.gd:37-43, leg and arm reach, eye height, seat_drop 0.10;
  - the pose_axes calibration table.
- ix_pose.gd (SkeletonModifier3D):
  - modes sit, sit_low, perch, sit_ground, lie (Root tilt about Hip), kneel (samples Legs_Crouch_Step) and reach_low;
  - override blend toward absolute targets with masks: legs 1, spine 0.6, arms 0.5, head 0;
  - weight through influence, active=false at 0, and a compatibility `mode` property;
  - inserted with move_child before locomotion_pose, so the existing angular limiter smooths it.
- rest_seat.gd: ensure_pose uses ix_pose. stand() faces the seat's front instead of Vector3.BACK. Teleport logic is unchanged here, so this WP can ship alone as the demo fallback.
- Files: game/scripts/ix/ix_rig.gd, game/scripts/ix/ix_pose.gd, game/scripts/rest_seat.gd, game/tests/ix_pose_check.gd
- Depends on: WP1
- Tests: The profile resolves every mapped bone on explorer_b_wardrobe, reference and motion; hip height equals rest_seat.hip_height() within 1 mm; Root mode: seated seat_contact y within +-3 cm of the seat top for seats 0.30/0.45/0.60; lie keeps the body basis identity with Hip at mattress +0.12 +-0.03 m; Fade in and out: max joint step <25 deg per tick, sampled in the last modifier's modification_processed; influence 0 leaves the layer inactive; The ix_pose node sits before locomotion_pose; village_rest_check still sees seat.pose.mode == 'sit'
- Risk: Medium: the Tripo armature is Z-up, so wrong pose_axes signs give backward knees. Verify with one capture.

### WP3 [DEMO] Object socket sources (fixed assets and crafted derivation)
- Goal: Build ix_sources.gd with for_node() running the priority chain (authored, then server hint, then derived, then bbox), and ix_data.gd consts.
- INTERIOR_KINDS: wooden_chair, armchair, sofa (repeat 3), bench (repeat 2), bed (lie plus edge sits), bathtub, toilet, and a stand_use per Interiors.ACTIONS kind.
- PROP_MODELS: placeholders flagged uncalibrated.
- from_field_entry().
- derive_crafted():
  - multi-part crafts use the designed part boxes, with the carrier set to the part's pivot;
  - one-piece crafts find candidates on the collision boxes;
  - the height is always snapped by a ray-triangle test against CraftCollision.surfaces();
  - results are cached in node meta keyed by size, shape and runtime version.
- A corrected bbox fallback.
- A tools script exports the archetype fixture plans to JSON for tests.
- Files: game/scripts/ix/ix_sources.gd, game/scripts/ix/ix_data.gd, tools/export_ix_fixtures.py, game/tests/fixtures/ix_archetypes.json, game/tests/ix_sources_check.gd
- Depends on: WP1
- Tests: Fixtures (rocking_chair, bench, sofa, armchair, throne, bed, rug, hammock, swing, sunbed) give the expected type, count and height within 2 cm of the fixture top; the back at -Z gives fwd +Z; Carriers: the rocking chair's seat rides whole_root or the seat pivot; the swing rides the ropes pivot; A one-piece proxy bed snaps to its real top; a 50 % shrunk bed degrades to sit; a rug gives sit_ground; Every interior kind yields valid sockets; the cache invalidates after an object_transform shape change
- Risk: Medium: odd Tripo meshes can mislead derivation. The bbox fallback stays and is shown amber in the gizmo.

### WP4 [DEMO] Interaction driver, player hook, rest_seat facade
- Goal: Build ix_driver.gd and wire it in.
- ix_driver.gd:
  - states CLAIM, APPROACH, ALIGN, ENTER, HOLD, EXIT, RECOVER and ABORT, using procedural virtual clips;
  - occupancy claims;
  - moving-carrier follow, with tilt sent to ix_pose;
  - exit re-selection with capsule tests;
  - cancel and buffer input through an injected input_allowed;
  - re-attach on look rebuild.
- player.gd hook (about 25 lines, inert when ix is null): drive() after tick_from (line 300); steer as movement and locomotion (301-303, 327-328); face_override (334); clip_override and clip_blend (339-347); squash skipped while seated (392-396).
- rest_seat.gd becomes a facade with the same API and fields, and Interiors.RestPose is deleted.
- main.gd: the three controls_enabled sites (1103, 2772, 2961) add `not ix_locked()`; the village mover is steer.
- studio.gd: the walk gate adds the driver lock, and the mover is move_hero with door and stairs side effects off.
- Files: game/scripts/ix/ix_driver.gd, game/scripts/player.gd, game/scripts/rest_seat.gd, game/scripts/interiors.gd, game/scripts/main.gd, game/scripts/studio.gd, game/tests/ix_flow_check.gd, game/tests/village_rest_check.gd
- Depends on: WP1, WP2, WP3
- Tests: ix_flow_check (offline: a player on a floor with box seats 0.30/0.45, a bed and a rocking holder): phases run in order; body step <=0.08 m and visual yaw step <=0.35 rad per tick; joint step <25 deg per tick; seat_contact within 3 cm in HOLD; the rocking holder keeps the hips within 2 cm of the moving socket; Exit within 0.05 m of the exit point, facing socket +Z +-5 deg, with test_move free; movement during APPROACH cancels within 1 tick; a foreign teleport aborts with weight 0 within 0.2 s; a look rebuild while seated stays seated; two actors on a bench take seat_0 and seat_1; village_rest_check updated: hold within 0.06 m of the derived point, standing at the exit point, lie with body basis identity, no frame jump >0.08 m; controller_acceptance, explorer_b_integration, locomotion_continuity, field_objects_check, home_roundtrip and avatar_rooms_check still pass
- Risk: Medium-high: the player physics loop is shared by every scene and remote player. Keep it inert when ix is null and rerun the movement tests before any patch.

### WP5 [DEMO] Socket gizmo, interaction lab, Korean ISS-1 doc
- Goal: Make the sockets visible and measurable before the demo.
- ix_debug.gd: socket axes, type and validity colours, approach and exit arrows, driver phase label, contact error vector. Toggled by an F3 dev panel checkbox or --ix-debug; off by default.
- ix_lab.gd, windowed on the BenQ screen:
  - covers box seats 0.30/0.45/0.72, the interior kinds and the crafted fixtures (including a rocking chair);
  - varies yaw 0/90/217, shape 50/100/200 % and mirror;
  - runs from 3 approach directions;
  - writes PNG strips and lab.json.
- Calibrate INTERIOR_KINDS and pose_axes from the lab.
- Write the Korean standard doc with figures and a QA table.
- Files: game/scripts/ix/ix_debug.gd, game/scripts/main.gd, game/tests/ix_lab.gd, docs/interaction_standard/
- Depends on: WP4
- Tests: ix_lab --capture writes artifacts/ix/*.png for every case and phase, and lab.json with contact error <=3 cm, max root step <=0.08 m and max joint step <25 deg; hud_fold_check still passes; with the gizmo off, no ix_debug node exists
- Risk: Low: dev-only. Keep capture runs few, for token economy.

### WP6 [DEMO-optional] Map props really seat or lay the player
- Goal: Measure the front axis of 26_bench, 25_picnic_table, 32_cafe_chair and 29_beach_lounger in the lab. Fill PROP_MODELS in the model frame; sockets resolve through prop.global_transform, which includes yaw_degrees and uniform scale (environment_layout.gd:78-88). town.use_prop routes these four ids to the village driver and drops their react('eat') branch. Models without data keep the old effect.
- Files: game/scripts/ix/ix_data.gd, game/scripts/town.gd, game/tests/ix_town_props_check.gd
- Depends on: WP4, WP5
- Tests: Every instance of the 4 models in environment_layout.json yields valid sockets with a clear approach; E seats or lays the walker on each model at its real instance yaw and scale; capture strip of the bench and lounger
- Risk: Medium: a wrong front guess seats players facing the backrest. The lab measurement gates it.

### WP7 [DEMO-optional] Talk: turn before the dialogue opens
- Goal: main.open_dialogue opens the modal once the NPC faces the player within 20 deg, or after at most 0.4 s. The NPC turns at 9/s during talk (npc.gd:102-104; shadow walkers likewise). The player steps back to 1.3 m through a talk socket (ALIGN only) when closer than 0.9 m.
- Files: game/scripts/main.gd, game/scripts/npc.gd, game/scripts/shadow_figure.gd, game/tests/npc_dialogue.gd
- Depends on: WP4
- Tests: The modal opens after facing <=20 deg or <=0.4 s; No player position step >0.08 m during the turn; Existing dialogue tests pass
- Risk: Low.

### WP8 Field objects (swing, rocker, hammock) on the driver
- Goal: Swing, rocker and hammock entries become socket records via from_field_entry, with carrier = pivot and follow full. sit, update_seat and stand_up go through the driver. Tilt moves to the ix_pose Root tilt instead of player.global_basis (field_objects.gd:1402). SeatPose is deleted, removing the queue_free snap at 1415. walker_moving is gated on world_movement_allowed, so typing w/a/s/d no longer ends a seat (283-284).
- Files: game/scripts/field_objects.gd, game/scripts/ix/ix_sources.gd, game/tests/field_objects_check.gd
- Depends on: WP4
- Tests: No per-tick jump >0.08 m on sit or stand; hips within 2 cm of the moving seat; body basis identity while swinging; Typing in a focused LineEdit does not stand the walker up; existing field object checks pass
- Risk: Low-medium.

### WP9 Clip runtime and placeholder clip sets
- Goal: Build ix_clips.gd and the placeholder sets.
- Discover res://assets/anim/interact/*.res with ResourceLoader.list_directory and lazy-load each set.
- Copy tracks onto the actor skeleton through one shared helper, cached per model. It replaces the duplicates at style_character.gd:30-49 and shadow_figure.gd:333-353.
- Add the 'ix' library and pick variants by arrival yaw and position.
- Play through clip_override, with marker windows, root_curve warp, the vertical warp in root mode, the blend policy table and events.
- tests/ix_clip_bake.gd (validator plus bake) produces the placeholder sets sit_any, lie_any, crouch_any and reach_any from keyed procedural poses, Legs_Crouch_Step and Arms_Reach_Grip.
- Files: game/scripts/ix/ix_clips.gd, game/scripts/ix/ix_driver.gd, game/scripts/player.gd, game/scripts/style_character.gd, game/scripts/shadow_figure.gd, game/tests/ix_clip_bake.gd, game/tests/ix_clips_check.gd, game/assets/anim/interact/
- Depends on: WP4
- Tests: Discovery finds every set, including from an exported pack (--main-pack, as in tools/measure_loading.ps1:90); Contact error <=2 cm at the contact marker for seats 0.36/0.45/0.56; per-tick bounds hold; every type falls back to procedural when its set is missing; The validator passes the placeholder sets; locomotion_continuity and explorer_b_integration are unchanged
- Risk: Medium: per-skeleton track rewrite and MANUAL advance interplay.

### WP10 External animation intake, reference kit and contract doc
- Goal: Three tools and the contract doc.
- tools/ix_kit_export.py builds the kit: the VRS armature at its exact bind with scale 1.7 unapplied, a forward arrow, a floor grid, and reference props with SOCKET_ empties.
- tools/ix_intake.py (Blender, headless):
  - bone maps (Mixamo, Rigify, VRS);
  - a rest-aligned world-rotation retarget;
  - hips scaled by leg-length ratio;
  - forward reoriented to the arrow;
  - a 30 fps bake and the root policy;
  - foot-contact cleanup;
  - timeline markers merged with the sidecar into the bake input.
- The validator rules live in tests/ix_clip_bake.gd, shared with WP9.
- A Korean contract doc with figures: kit renders, axis arrow, marker timeline, reference dimensions.
- Files: tools/ix_kit_export.py, tools/ix_intake.py, tools/ix_bonemaps/mixamo.json, tools/ix_bonemaps/rigify.json, game/tests/ix_clip_bake.gd, docs/interaction_standard/
- Depends on: WP9
- Tests: Round trip on a free sample: B_ShapeSummon re-exported as a foreign rig with renamed bones and an A-pose rest bakes to a .res that passes the validator and plays; Fixtures with a wrong bind, Root drift, a name ending in _loop and a missing contact marker are each rejected with a readable message; no paid credits are used
- Risk: Medium: retarget artefacts (A/T-pose, no-root sources) and Blender axis mistakes. The kit arrow and the validator's toe-ahead check guard them.

### WP11 IK and look-at layer
- Goal: ix_ik.gd lazily adds two TwoBoneIK3D modifiers after locomotion_pose.
- Legs and arms: one setting per side, with root/middle/end bone names from ix_rig, and target and pole Marker3D nodes under the stage.
- LookAtModifier3D: bone Head, origin_from ExternalNode = eyes socket, duration 0.25-0.35, Sine InOut, angle limits 70/35 deg.
- Influence follows clip curves or procedural envelopes.
- Axis and pole calibration on the Z-up rig. When it passes, vertical-warp hips mode (feet planted) is enabled.
- IK is off for NPCs at LOD distance.
- Files: game/scripts/ix/ix_ik.gd, game/scripts/ix/ix_rig.gd, game/scripts/ix/ix_driver.gd, game/tests/ix_ik_check.gd
- Depends on: WP2, WP4
- Tests: End bone within 1 cm of reachable targets; gaze within 3 deg inside the limits; Hips mode keeps the soles within 2 cm of the floor for seats 0.36-0.56; No joint step >25 deg per tick while influence ramps; locomotion_continuity unchanged
- Risk: Medium: forward and pole axes on the Tripo Z-up armature are unverified. If calibration fails, stay in root mode.

### WP12 Short actions: use, farming, fishing
- Goal: Dynamic stand_use sockets for room ACTIONS kinds and reach sockets for plots and forage spots.
- Approach ring at 0.55-0.85 m; crouch for the ground band.
- Act envelope sampled on the arm mask, with optional hand IK, and LookAt at the object.
- Controls are locked only during the act window.
- Tools scale in over 0.12 s and out over 0.15 s instead of popping (player.gd:201-214).
- The whole-visual squash is removed for interaction kinds.
- Fishing aligns to the cast point first.
- Files: game/scripts/village_life.gd, game/scripts/studio.gd, game/scripts/fishing.gd, game/scripts/player.gd, game/scripts/ix/ix_driver.gd, game/tests/ix_flow_check.gd
- Depends on: WP4
- Tests: Harvest started from 2.0 m approaches to 0.85 +-0.1 m; controls are locked only during the act window; no frame where a tool pops at full scale; village_life and fishing tests pass
- Risk: Medium: about 30 react() call sites. Migrate one family at a time; the action_pose fallback stays.

### WP13 Doors: walk through instead of a cut
- Goal: Village doors get passage sockets (village_life.gd:162-170, main.gd:3354-3375): approach the outside point within 1.9 m, align, push (reach envelope), step 0.5 m, and fade out at 40 % of the step. On room arrival, spawn 0.9 m outside spawn_point and follow_path in under the fade-in (studio.gd:707-714, 822-872). Room to village: walk out after door_return (main.gd:314-317). Total door time stays at or under 1.2 s.
- Files: game/scripts/main.gd, game/scripts/studio.gd, game/scripts/village_life.gd, game/tests/ix_door_check.gd
- Depends on: WP4
- Tests: No position step >0.08 m before the veil is opaque; no snap at room spawn; home_roundtrip, home_visit and door_sounds_check pass
- Risk: Low-medium: scene-change timing against the veil.

### WP14 Character and item sockets
- Goal: ix_rig gets the full socket table as bone-local offsets with inherited-scale cancellation. grip_r is exactly the literal at player.gd:220-221; the other sockets are measured from the rest pose at runtime. socket_node() lazily creates BoneAttachment3D + SK_<id>, and GLB SOCKET_ empties are preferred. ITEM_SOCKETS adds grip, tip (rod tip from player.gd:236) and rest. equip, headwear, backpack, villager_accessories and shadow_figure.attach all switch to them.
- Files: game/scripts/ix/ix_rig.gd, game/scripts/ix/ix_data.gd, game/scripts/player.gd, game/scripts/shadow_figure.gd, game/scripts/villager_accessories.gd, game/tests/ix_rig_check.gd
- Depends on: WP2
- Tests: The tool transform matches the old equip() transform within 1 mm for explorer_b; the haeru path is unchanged; hat and backpack within 2 mm; wardrobe_check and avatar_everywhere_check pass; the held-tool capture is visually unchanged
- Risk: Low-medium: measured offsets may differ from the hand-tuned literals.

### WP15 NPC residents and shadow figures on the driver
- Goal: ix_actor.gd adapts shadow_figure and player.gd. Visible residents walk to the approach point and enter; off-screen ones start in HOLD. set_pose blends through ix_pose, and bend() is deleted. pose_resident's formulas (studio.gd:2425-2470) are replaced. Interiors.choose_spot claims sockets by key. Gifted crafted chairs become usable (studio.gd:2746-2797), and the floor-0-only filter (studio.gd:1700) is lifted for loft slots. LOD rules apply.
- Files: game/scripts/ix/ix_actor.gd, game/scripts/shadow_figure.gd, game/scripts/studio.gd, game/scripts/interiors.gd, game/tests/ix_resident_check.gd
- Depends on: WP4, WP3
- Tests: A resident walks to a gifted chair and sits with hips within 3 cm; it never appears seated while visible; the player and a resident never share a socket; residents_check and avatar_rooms_check pass; furniture_stress stays in its frame budget with 8 residents
- Risk: Medium: walk-to-sit delays resident schedules; cost of full rooms on school PCs.

### WP16 Server socket hints for crafted archetypes
- Goal: server/sockets.py adds Strict Socket and SocketSet models (at most 8 sockets and 4 approaches, frac bounds). derive() works geometrically over the pre-merge designed plan (`designed`, asset_studio.py:808, before static_plan at 810), with part-id words (seat, cushion, mattress, plank, net) as tie-breakers, normalised to extent(). The result is stored in spec['sockets'] and exposed as interaction.sockets by interactions.apply; old clients ignore the key. It is recomputed after a bindings edit (asset_studio.py:510-529). The visitor assembly route adds provenance.size_m (multiplayer.py:490). ix_sources treats these as hints and always snaps height.
- Files: server/sockets.py, server/archetypes.py, server/asset_studio.py, server/interactions.py, server/multiplayer.py, server/tests/test_sockets.py, game/scripts/ix/ix_sources.gd
- Depends on: WP1, WP3
- Tests: pytest: every rest archetype fixture yields valid hints; static crafts keep their hints after static_plan; apply exposes them; owner and visitor assemblies report equal size_m; payloads without sockets still validate; Client ix_sources_check case: hints plus mesh snap give the right height
- Risk: Low for old clients. Existing objects have no hints, so client derivation covers them. Deploy the server separately.

### WP17 Multiplayer interaction sync
- Goal: Server:
- Presence.ix Strict submodel {k,p,c,t0,o,s,h};
- an mp_presence.ix column via guarded ALTER;
- ix echoed in village players and room peers;
- /health interaction_sync:1, with multiplayer_protocol kept at 1.

Client:
- social.gd and studio.gd send ix only when the flag is present;
- a 422 while sending ix disables ix only, not rich presence;
- remote_motion hands seated peers to a puppet driver that plays the phase from t0 on the remote clock, applies h, and locks onto the local socket when o/s resolves.
- Files: server/multiplayer.py, server/app.py, server/tests/test_multiplayer.py, game/scripts/social.gd, game/scripts/studio.gd, game/scripts/remote_motion.gd, game/scripts/ix/ix_driver.gd, game/tests/ix_remote_check.gd
- Depends on: WP4
- Tests: pytest: presence with and without ix; bad values get 422; ix is echoed to visible players; the health flag is present; ix_remote_check: A's payload fed to B ends seated within 3 cm; clearing ix plays the exit; multiplayer.gd against an old-schema server: no ix is sent and rich presence is kept
- Risk: Medium: deploy the server first. The judges' server stays untouched, so the flag is absent there and the feature stays off.

### WP18 Optional pose inertializer (only if the lab demands it)
- Goal: Entry criterion: lab.json shows a joint step >=25 deg per tick, or a visible pop the angular limiter does not catch. Then add an offset-decay inertializer modifier as the last modifier, triggered by the driver at known switches. NPCs record only when armed.
- Files: game/scripts/ix/ix_inertializer.gd, game/tests/ix_inertializer_check.gd
- Depends on: WP9
- Tests: A 60 deg step input gives <=25 deg per tick; the output converges to <0.5 deg after 4 half-lives; no cost when idle
- Risk: Low-medium: quaternion sign handling and cost on NPCs.

## Risks

- The player physics hook (player.gd:300-368) is shared by every scene, the room hero and remote players. A bug there breaks walking everywhere. Keep it inert when ix is null, and rerun controller_acceptance, explorer_b_integration, locomotion_continuity and multiplayer before every patch.
- Tripo armatures are Z-up with unverified bone axes. ix_pose.pose_axes, the TwoBoneIK3D poles and the LookAtModifier3D forward_axis need one in-engine calibration each, or knees bend backwards and necks twist. IK stays gated behind a calibrated flag, with root mode as the fallback.
- Static crafts are one Tripo mesh generated from text, so the designed parts (kept only in `designed`, asset_studio.py:808) do not match the real seat height. Voxel collision boxes are quantized (GRID 10, up to ~0.16 m on a 1.6 m bench). Height must always be snapped to the mesh triangles.
- Data outside include_filter is silently missing from PCKs (export_presets.cfg:10/46/82 list only i18n, maps, assets/interior and assets/monsters JSON). environment_layout.json and interior/manifest.json are regenerated by tools. Socket, rig and clip data therefore live in .gd consts and .res sets only.
- Root mode lowers the body to put the hips on the seat, so feet float or sink on low and high seats until leg IK (WP11) lands. sit_low, perch and sit_ground variants with clamps limit this for the demo.
- Legacy explorer/ranger/tinker rigs (A-pose) and haeru, which has no MANUAL advance and no modifier stack (player.gd:89-104), get procedural poses only. A remote player with a legacy look never plays interaction clips in v1.
- There is no navigation (no NavigationAgent3D). Straight-line approaches can fail in cramped rooms, so the short-align and cancel fallbacks must stay clean. In rooms, studio.walk moves the hero in _process, so it must be gated while the driver owns the hero, or the two movers will jitter.
- Existing tests encode today's teleports: village_rest_check expects standing within 0.05 m of the old spot and a tipped body basis for lying. They must change in the same patch as WP4, or CI flags intended changes.
- Presence is Strict (extra=forbid), so the server must deploy before clients send ix. The judges' server stays untouched with the flag absent. social.gd:153-155 currently drops rich presence on any 422, so the ix fallback must be separate.
- The continuity guard depends on locomotion_pose's angular limiter, which exists only on Explorer B builds. Shadow figures and residents (WP15) rely on ramped weights alone, and WP18 is the escape hatch.
- Blender and glTF axis confusion: Explorer B faces +X in its GLB and in Blender, while Mixamo-style sources face glTF +Z (Blender -Y). Contract text alone is error-prone, so the kit arrow and a validator toe-ahead check are mandatory.
- Retargeted external clips can slide feet or break wrists. The validator checks structure, not looks, so every new set needs a lab capture review.
- Paid clip sources (Tripo retarget presets, Scenario) fall under the user's credit-cap rule. The pipeline must work on free sources first.
- Demo timing: WP4 is the critical path. If it slips, ship WP2 alone (blended pose plus exit facing the seat's front) as the smaller smoothing step.