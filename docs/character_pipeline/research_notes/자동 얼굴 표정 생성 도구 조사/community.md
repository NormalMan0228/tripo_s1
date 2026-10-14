# Community practice: making ARKit-52 / Perfect Sync blendshapes for stylized, anime, cartoon and non-human faces

Scope note (read first): Reddit could not be read in this session. reddit.com is blocked for the web-search tool, for the page fetcher, and for the built-in browser pane ("not allowed due to safety restrictions"). So there are no Reddit quotes below. The community evidence comes instead from the VTuber/VRChat ecosystem (VSeeFace, VMagicMirror and Warudo docs, Booth tool pages, the Japanese note.com and hatenablog guides, VRChat feedback), from the Blender Artists, Unreal, NVIDIA and Reallusion forums, from Superhive reviews, from Fiverr, VGen, Coconala and Ko-fi listings, and from VFX trade press (fxguide, befores & afters, Art of VFX). Polycount, Fiverr and Etsy pages returned HTTP 403, so for those only search-result text was available. Dates are given where known. Anything from before 2022 is marked as older.

---

## Q1. Has anyone built a tool or pipeline that automatically makes the 52 expressions for arbitrary stylized or non-human heads, and how well does it work?

### Takeaway
No tool that practitioners rely on is fully automatic for arbitrary stylized or creature heads. The tools in real use fall into four groups:
- **Template-copy tools.** These work only on one known base mesh, such as VRoid with HANA_Tool.
- **Landmark-plus-rig generators.** Faceit is the example. You place landmarks, bind, load ARKit poses, then sculpt or pose fixes.
- **"Pose 52 frames, bake to shape keys" scripts.** Examples are ShapeKeyGen, ARKitBlendshapeHelper and the Kilutica script. A human still authors every pose.
- **Paid services.** Polywink is one: an algorithm runs, then staff check the result by hand. It requires roughly humanoid input.

Every route ends with manual correction, mostly on the lips, eyelids and mouthClose. Fully automatic stylized or non-human generation exists only in recent academic preprints.

### Cited Findings
**Polywink "Blendshapes on Demand" (commercial service)**
- Price is €499 per model and turnaround is "within 24 hours" (the page also says "a couple of hours"). The output is 157 FACS blendshapes, and the standard set is "derived from ARKit". — [Polywink](https://polywink.com/en/9-automatic-expressions-blendshapes-on-demand.html)
- Input requirements: neutral pose, "eyes open and mouth shut", no eyelashes, brows or beard, and no combined geometries. Eyes and inner mouth may be supplied but are not converted into blendshapes. — [Polywink](https://polywink.com/en/9-automatic-expressions-blendshapes-on-demand.html)
- Each model is processed by the algorithm and "then manually checked by our team" before delivery. Press coverage says results work for stylized characters as long as proportions are broadly humanoid. — [80.lv](https://80.lv/articles/004adk-polywink-accessible-facial-animation)
- 2018 launch pricing (older): $499 internal / $999 commercial for blendshapes, $999 / $1,999 for a rig, and $299 for the iPhone X (ARKit, 51-shape) package. Processing was within 24 h. — [CG Channel 2018](https://www.cgchannel.com/2018/07/polywink-creates-blendshapes-and-rigs-for-any-head-model/)
- A 2019 press release markets "52 automatically generated ARKit blendshapes for any 3D model". — [CGW 2019](https://www.cgw.com/Press-Center/News/2019/Polywink-Releases-New-Facial-Animation-Solution.aspx)
- No independent user test of Polywink on stylized heads was found. The only forum-style comment is a cgpress reader questioning the cost. — [cgpress](https://cgpress.org/archives/polywink-offer-online-tools-to-create-blendshapes-and-rigs-for-facial-animation.html)

**Faceit (Blender add-on, semi-automatic)**
- Its docs describe it as working on "arbitrary 3D characters", realistic or cartoon. Version 1.8 rigs the face, "semi-automatically" creates the 52 ARKit shape keys, and builds a control rig. — [Faceit docs](https://faceit-doc.readthedocs.io/)
- The ARKit expressions come from presets and are then adapted "by posing or sculpting" to the character's morphology. If the character already has a face rig, empty expressions load and "the poses will have to be created manually". — [Faceit docs – create expressions](https://faceit-doc.readthedocs.io/en/latest/create-expressions/)
- The FAQ covers several cases:
  - Wolves, sheep and dragons can be rigged.
  - Anime flat eyes (no round eyeball) need the eye-bone pivots moved further inside the head.
  - Bad bind results usually trace back to the landmark setup.
  - Weights usually need cleaning.
  - Eyelids clip through eyeballs after baking, because shape keys are linear. The fix is a driver-controlled corrective that pushes the lid out halfway through the blink.
  — [Faceit FAQ](https://faceit-doc.readthedocs.io/en/latest/FAQ/)
- Reviews: average 5 from 80 ratings. Quotes include "This add-on cuts that work in half", "it automatically generated all 52 arkit poses", default tool for "either human, animal or hybrid" rigs, and "Beginners may still struggle a bit". — [Superhive ratings](https://superhivemarket.com/products/faceit/ratings)
- A Blender Artists thread from December 2022 questions paying €80 for 1–3 characters. One reply: "Learn how to rig, then you'll know whether buying additional tools is worth it". — [Blender Artists](https://blenderartists.org/t/faceit-add-on-for-blender/1419740)

**Pose-and-bake tools (human-authored poses, automated baking)**
- **ShapeKeyGen** ($15, Blender 3.6–5.0) transfers a pose animation onto AutoRig Pro or Rigify (custom rigs need "minimal manual adjustments"). You tune with multipliers when expressions look off, then "Generate ShapeKeys" and "Make ARKit" to rename. Its "stylized, cartoon, or semi-realistic" claim is marketing, with no user reviews shown. — [Superhive ShapeKeyGen](https://superhivemarket.com/products/shapekeygen)
- **ARKitBlendshapeHelper** (free, GitHub): you build a temporary rig and pose "52 ARKit poses for your character in frames 1-52", then it applies them as shape keys. — [GitHub](https://github.com/elijah-atkins/ARKitBlendshapeHelper)
- **Kilutica3D script** (DeviantArt, posted 19 May 2026): takes a facial rig whose poses are keyed in a pose action and outputs all 52 shape keys. The pose action can be reused across "similar humanoid characters". The author calls the manual method a "massive production bottleneck" and claims "minutes instead of hours". — [DeviantArt](https://www.deviantart.com/kilutica3d/art/Automate-52-ARKit-Shapekeys-in-Blender-1334945244)
- **Maya "Facial MoCap Blendshape Generator"** (ArtStation): also needs you to hand-rig and pose the 52. One reviewer says it doesn't work and copies 52 identical expressions. — [ArtStation](https://www.artstation.com/marketplace/p/edbb2/maya-facial-mocap-blendshape-generator)
- **ARKit Toolset** (itch.io): guides you through the 52 with previews and side mirroring. You still sculpt each shape. — [itch.io](https://andy-hellgrim.itch.io/arkit-toolset)
- **YAARKitHelper** (Booth): creates the 52 template keys, does a smooth L/R split, and mirrors (including asymmetric meshes via manual marks). It also has a delta scaler and smoother. It calls the 52 keys the most time-consuming part of avatar making and claims "90%" faster, which is a vendor claim. — [Booth](https://booth.pm/en/items/8433374)

**VRoid and VRChat-specific tools**
- **HANA_Tool** (paid, Booth): applies Perfect Sync data to VRoid avatars. It bundles Perfect Sync data for male and female VRoid bodies made by はいぬっか (hinzka), and data loads only onto a mesh whose vertex count matches. ClipBuilder clips "start at 100" and must be fine-tuned. Splits in cramped regions (between eyes and brows) tend to break shapes. — [Booth v4](https://booth.pm/en/items/2604269), [Booth v5](https://kuniyan.booth.pm/items/4607357)
- The VSeeFace manual calls HANA_Tool "an easy, but not free, way" for VRoid avatars. You must export the VRM "without optimizing or decimating the mesh". A vertex-count mismatch error means the model was edited or decimated. The manual gives no automatic route for non-VRoid models. — [VSeeFace](https://www.vseeface.icu/)
- VMagicMirror: HANA_Tool works only if the VRoid model is "enough plane" (little modified after export). Otherwise you make the 52 in Blender. — [VMagicMirror](https://malaybaku.github.io/VMagicMirror/en/tips/perfect_sync/)
- **FaceTra Shape Creator** (Hai): a Unity editor tool that creates face-tracking blendshapes non-destructively "by morphing meshes" and automates "a large portion of a laborious process". It was "designed primarily for anime-like avatars", should work on kemono, has had "some success" with furry, and "will be rough to use at first". Available to Patreon supporters, or 1000 JPY on pixivFANBOX. — [hai-vr docs](https://docs.hai-vr.dev/docs/products/facetra-shape-creator)
- **ARKit → Unified Expressions converter** (Booth, 400 JPY): converts the shapes automatically and shows which UE shapes "still need sculpting". — [Booth](https://booth.pm/en/items/8607387)

**NVIDIA Audio2Face blendshape generation and MetaHuman**
- **Audio2Face** generates a shape set from a custom neutral mesh. Its template is labelled an "ARKit 51 pose" solution. — [NVIDIA docs](https://docs.omniverse.nvidia.com/audio2face/latest/user-manual/character-transfer/blendshape-generation.html)
- Audio2Face forum reports (2023):
  - All 46 generated shapes "look the same" after character transfer. — [NVIDIA forum](https://forums.developer.nvidia.com/t/audio2face-blendshape-creation-issues-the-blendshapes-all-look-the-same/267400)
  - Lips look broken after mesh fitting. — [NVIDIA forum](https://forums.developer.nvidia.com/t/blendshape-metahuman-wrong-representation/273917)
  - Good M/P/B closure is "sometimes difficult". — [NVIDIA forum](https://forums.developer.nvidia.com/t/adjusting-mouth-shape-to-better-match-phonemes-blendshape-solve-options/245461)
  - The jaw stays closed even at JawOpen 200%. — [Reallusion forum](https://forum.reallusion.com/540247/Group1.aspx)
- **MetaHuman is not a stylized solution.** An Unreal forum thread (June 2023 – March 2025) gives several points:
  - Epic's Kiteboy uses "(mostly) blendshapes, hard-sculpted", driven by Live Link ARKit.
  - Mesh to MetaHuman "always results in a cartoon face" with photoreal skin.
  - The workarounds are all paid: Mesh Morpher, MetaPipe (Maya), or the Character Creator control rig.
  — [Unreal forum](https://forums.unrealengine.com/t/metahuman-rig-to-stylized-cartoony-characters/1200631)
- A 5.6/5.7 pipeline reference lists stylized, cartoon and non-humanoid characters as a known gap. Mesh to MetaHuman flattens features back toward photoreal. — [Medium](https://medium.com/@Jamesroha/metahuman-5-6-5-7-pipeline-reference-170d302b078e)
- **ARKitRemap** converts MetaHuman Animator curves into ARKit-52 curves, so the capture can drive Faceit or any other ARKit-52 face. Only the README was checked. — [GitHub](https://github.com/Dylanyz/ARKitRemap)

**Research and proposals (not yet practitioner-validated)**
- An IEEE VR 2023 paper notes that automatic landmark detection works for human faces "but not for stylized characters". It uses learned feature transfer instead. — [IEEE VR 2023 PDF](https://fuxivirtualhuman.github.io/pdf/IEEEVR2023_BSGen.pdf)
- OmniFaceRig (arXiv 2026) uses sparse deformation transfer of a FACS library to humans, long- and short-muzzle animals, and stylized humanoids. — [arXiv](https://arxiv.org/html/2606.08043v1)
- RegHead (arXiv 2026) builds a non-humanoid expression dataset plus a feed-forward registration step. — [arXiv](https://arxiv.org/pdf/2607.12206)
- A QtMeshEditor issue proposes "fit template head + transfer deformations" so users needn't hand-sculpt 52 shapes. It is only a proposal. — [GitHub issue](https://github.com/fernandotonon/QtMeshEditor/issues/889)
- **John Hable's solver** (Nov 2021, older; scan-based, realistic): ~100 scanned expressions produce 50 shapes. The solved lips stay closed in most shapes, but "the smile opens the lips when it really should not". Lip and eyelid opening and closing "would definitely need to be fixed". — [Filmic Worlds](https://filmicworlds.com/blog/solving-face-scans-for-arkit/)

### Inferences
- The reliable automatic case is "same topology as the template". HANA_Tool works because every VRoid face shares vertex order; it breaks on edited or decimated meshes. Everything else is either landmark-driven (Faceit, Polywink) and assumes a human layout, or a human authors the poses.
- Even vendors build in a manual step: Polywink's staff check, Faceit's "adapt by sculpting", ShapeKeyGen's multipliers, HANA_Tool's "fine-tune". Teams should budget a cleanup pass whatever tool is used.
- For our pipeline (tools/face_auto, original mesh preserved), the community pattern closest to it is landmark rig → pose library → bake → corrective sculpt (Faceit / ShapeKeyGen style). Template wraps of the mesh itself are what HANA and Polywink do internally, and they need humanoid or same-topology input.

### Gaps
- No Reddit testimony could be gathered (blocked), so there are no Reddit "I tried tool X on my anime model" anecdotes.
- No hands-on public review of Polywink on cartoon or creature heads was found.
- No public measurements of how much cleanup Faceit needs per stylized character (hours, or number of shapes re-sculpted).

---

## Q2. One template for everything, per-style templates, or manual sculpting per character?

### Takeaway
Practitioners split by scale and style:
- **VTuber and VRoid users rely on per-base-mesh templates.** One dataset per base face is copied onto outfit variants.
- **Commercial avatar makers ship hand-made sets per avatar.**
- **Stylized game and animation teams use few blendshapes.** They rely on joints plus a small number of correctives, partly because blendshapes must be redone whenever the model changes.

Nobody credibly claims one human template works for anime, cartoon and creature faces alike. Anime guides explicitly say anime faces need different handling: move parts, not cheeks.

### Cited Findings
**Per-template and per-base-mesh practice**
- HANA_Tool copies a full Perfect Sync setup to "a VRoid with the same face and different outfit". Its data loads only on a matching vertex count. — [Booth](https://booth.pm/en/items/2604269), [VSeeFace](https://www.vseeface.icu/)
- A Coconala Perfect Sync service charges ¥500 extra per additional model sharing the same face mesh, versus ¥5,000 for the first. The same seller says animal-type (ケモノ系) or robot-type designs "may be difficult to accept". — [Coconala](https://coconala.com/services/1648942)
- VRChat furry and kemono add-ons are sold per avatar and need "an unmodified original FBX" (Varg). They depend on the specific base model. — [Pawlygon Varg](https://pawlygon.gumroad.com/l/varg-addon), [Chibi Tora addon](https://booth.pm/en/items/8524064)

**Anime faces differ from realistic ones**
- hinzka (who coined "Perfect Sync") built anime samples on VRoid and realistic samples on FaceCap's model. The guide says anime models break less when you move parts (mouth corners, lower eyelids) than the whole cheek: "頬全体を動かすより「口角」「下まぶた」などパーツを動かした表現のほうが破綻が少ない". — [hinzka 2021](https://hinzka.hatenablog.com/entry/2021/12/02/005814)
- The note.com/054 guide (Sept 2024) says cel-style models have no real cheek or nose movement. It uses the lower eyelid and mouth for cheekSquint and the brow for noseSneer. Ignoring left/right and up/down symmetry, the 52 reduce to "30種類", of which the mouth is 15. — [note.com/054](https://note.com/054/n/n60a59495a757)

**Manual sculpting per character**
- VMagicMirror and Warudo both say the default path for non-VRoid models is to make the 52 in Blender or Maya by hand. Warudo adds that "many modelers offer the service". — [VMagicMirror](https://malaybaku.github.io/VMagicMirror/en/tips/perfect_sync/), [Warudo](https://docs.warudo.app/docs/tutorials/3d-primer)

**Studios: few shapes plus joints plus reuse**
- Disney's "A Deformer-Based Approach to Facial Rigging" (SIGGRAPH 2013, older) weighs blendshapes as fast but "memory intensive and sensitive to model changes". — [Disney Animation](https://disneyanimation.com/publications/a-deformer-based-approach-to-facial-rigging/)
- DreamWorks' facial system has been used on most films since 1997. A newer artist-oriented approach shortened face-rig setup and made rig components reusable across characters. — [DreamWorks abstract](https://research.dreamworks.com/wp-content/uploads/2018/07/05-pohle-abstract.done-Edited.pdf), [ACM](https://dl.acm.org/doi/10.1145/2791261.2791262)
- Chris LeSage's "Face Plates" cartoony rig (older, about 2010s) kept roughly 8–10 blendshapes per character (pucker, "ewww"). The goal was to avoid "too many corrective blendshapes which would have to be re-done or tweaked with each modelling revision". — [Rigmarole blog](https://chrislesage.com/character-rigging/new-demoreel-and-face-rig-structure/)
- Jeremy Ernst (Epic; GDC 2011 Gears of War 3 facial rigging) built a "Cartoony Witch Face Rig" in Nov 2020 that is "mostly joint-driven with about 20 corrective blend shapes". — [Jeremy Ernst devblog](https://www.jeremyernst.com/devblog/category/Rigging), [GDC Vault](https://www.gdcvault.com/play/1014366/Fast-and-Efficient-Facial-Rigging)
- An 80.lv CGMA student project uses a Pixar-inspired stylized face with about 50 sculpted mini-expressions. Jaw, eyelids, eyes and nostrils use joints because they move along arcs. — [80.lv](https://80.lv/articles/005cg-cgma-student-project-facial-rigging)
- Epic's Live Link docs note that most real-time character faces are "not animated with blend shapes alone". A facial skeleton usually helps. — [Epic docs](https://dev.epicgames.com/documentation/unreal-engine/recording-face-animation-on-ios-device-in-unreal-engine)
- A 2006 Polycount thread (older) suggests that for "a more exaggerated, cartoony character, bones might be the way to go". — [Polycount](https://polycount.com/discussion/45238/facial-animation-blendshapes-or-bones)
- Rare's Sea of Thieves builds all characters from one base mesh, with facial features done by masked normal maps. — [Polycount](https://polycount.com/discussion/199554/sea-of-thieves-character-art)

### Inferences
- The VTuber/VRChat world has converged on per-base-mesh templates: one carefully authored set per base face, reused across outfits. "One template for every face" is not practised.
- For a game that generates many characters from varied stylized heads, the community and studio evidence points to a hybrid:
  - a shared rig or pose library (a template at the level of controls, not of vertices)
  - a per-character bake
  - a small per-style set of hand correctives (mouthClose, blink, smile corners)
- This matches our current direction: rig-based expressions plus per-style fixes. It argues against a single vertex-level human template.

### Gaps
- No practitioner write-up was found that measures per-style templates against per-character sculpting on the same characters.

---

## Q3. What is the common practical recipe for anime (VRoid-style) and cartoon characters?

### Takeaway
**VRoid characters:** export the VRM without decimation, run HANA_Tool in Unity to add the 52 clips, tune them, and export.

**Non-VRoid anime characters:**
1. Create the 52 shape keys in Blender, by posing bones and applying the pose as a shape key, or by sculpting duplicates and using "join as shapes".
2. Mirror and split L/R with a gradient.
3. Export FBX.
4. In Unity, make one BlendShapeClip per shape at weight 100 (empty clips are allowed).
5. Export the VRM.

Anime-specific tricks matter more than tools:
- move parts, not cheeks
- shrink the iris in eyeWide and blink shapes
- build mouthClose relative to jawOpen
- tongueOut straight

**Cartoon game characters:** use a Faceit- or pose-library-generated set plus sculpted correctives, or hand-sculpt and remap names via Live Link remap.

### Cited Findings
**VRoid recipe**
- The VSeeFace steps: install Unity, UniVRM and HANA_Tool; the Reader reads the Face blendshapes; ClipBuilder adds the clips; then UniVRM "Export humanoid". — [VSeeFace](https://www.vseeface.icu/)
- All 52 clips must exist ("may be empty"). Set FBX "Blendshape Normals" to None or Legacy, otherwise blinking shifts the shading. — [VSeeFace](https://www.vseeface.icu/), [VSeeFace manual](https://github.com/emilianavt/VSeeFaceManual)

**Manual (non-VRoid) recipe**
- Make the 52 in Blender. In Unity, one BlendShapeClip per shape at weight 100; leave a clip empty if a shape is skipped. Subtle ones can be skipped: "you can skip some of them if you feel they are too subtle". — [VMagicMirror](https://malaybaku.github.io/VMagicMirror/en/tips/perfect_sync/)
- Japanese Blender tips:
  - Create all 52 empty named keys with a script in the Scripting workspace. — [Satoki](https://satoki.art/blender/perfect-sync/)
  - Duplicate the mesh, edit it, then "join as shapes". — [dskjal](https://dskjal.com/blender/create-blend-shape)
  - Pose the face rig and use the Armature modifier's "Apply as Shape Key". — [knb-mayumi](https://knb-mayumi.com/shapekey-make/)

**hinzka's anime tips** ([hinzka 2021](https://hinzka.hatenablog.com/entry/2021/12/02/005814))
- Eye look stays bone-driven, so don't put eyeball rotation into shape keys if the eyes are bones.
- Blend lid shapes more at the lid centre than at the edges.
- Blink makes the iris bounce or poke through; add iris scaling to the closed-eye shape.
- On big-eyed characters, opening the lids may not show enough white, so shrink the iris in eyeWide.
- eyeSquint stacks with blink, so don't use it as a simple "joy closed-eye". Subtract the closed eye, then add the joy shape.
- jawOpen and mouthClose are a pair: at 100% each, the jaw is open but the lips are closed.
- Smile shapes tend to lift the whole mouth, so lower the mouth to compensate.
- Keep funnel and pucker from showing teeth or clipping at the corners.
- mouthRoll can make a toon-textured mouth disappear.
- Make cheekPuff survive in combination with pucker.
- tongueOut goes straight out, with the downward curve coming from jawOpen. Size the tongue to clear the lower lip.
- L/R splits should use a gradient that sums to 100%, not a hard centre cut.

**note.com/054 tips** ([note.com/054](https://note.com/054/n/n60a59495a757))
- mouthUpperUp and mouthLowerDown at 100% on both sides must not break the mesh.
- eyeLookIn/Out mean inner and outer, not left and right.
- tongueOut should move only the tongue.

**Cartoon / stylized (non-VRoid)**
- The Faceit route: landmarks, then bind, then ARKit presets, then sculpt fixes; for anime flat eyes, move the eye pivots inward. — [Faceit FAQ](https://faceit-doc.readthedocs.io/en/latest/FAQ/)
- Unreal: names needn't match ARKit, because a LiveLinkRemap asset can translate them. Shapes should cover the same facial areas as ARKit. — [Epic docs](https://dev.epicgames.com/documentation/unreal-engine/recording-face-animation-on-ios-device-in-unreal-engine)
- Kiteboy (Epic's stylized demo): hand-sculpted blendshapes driven by ARKit channels, with Blueprint post-processing. — [Unreal forum](https://forums.unrealengine.com/t/metahuman-rig-to-stylized-cartoony-characters/1200631)
- 80.lv (2 June 2026): an artist built "a really clean armature that lets you animate ARKit blendshapes" on an anime character, Mt. Lady, and released Blender and VRM files. The method details are not given. — [80.lv](https://80.lv/articles/ultra-expressive-arkit-facial-control-rig-for-mt-lady)

**VRChat variant**
- VRCFaceTracking "Unified Expressions" templates (Jerry's) accept SRanipal, ARKit or UE names, case-sensitive, on the Body mesh, with a separate variant for TongueOut step shapes. — [GitHub templates](https://github.com/ADJERRY91/VRCFACETRACKING-TEMPLATES)
- A VRM auto-setup tool maps ARKit, Unified Expressions and visemes. Its UE→ARKit conversion is beta, and some avatars have "weird/unconventional names". — [GitHub](https://github.com/tracer755/VRC_VRM_BlendShape_Avatar_Setup)

### Inferences
- For anime-style heads, the decisive know-how is a short list of per-shape rules, not a smarter tool: iris scaling, mouthClose pairing, parts-not-cheeks, gradient L/R. These can be encoded as automated post-processing rules in tools/face_auto, e.g. auto-generating mouthClose as (jawOpen + closed-lips) − jawOpen, and auto-scaling the iris on blink and eyeWide.
- Because about 30 unique shapes plus mirroring cover the 52, a generator should author one side and mirror with a gradient split rather than author 52 independently.

### Gaps
- No written first-hand recipe was found for a "chubby" or very thin stylized face specifically. Cheek-mass handling for chubby faces appears only indirectly (cheekPuff combined with pucker, and "move parts not cheeks").
- The YouTube description for "FaceIT for Anime characters" could not be retrieved, because the page had no description text. — [YouTube](https://www.youtube.com/watch?v=pB-0h5-VpDs)

---

## Q4. Common failure cases with automatic transfer: mouth corners, lips not separating, eyelids, big anime eyes, cartoon proportions, chubby cheeks, creatures

### Takeaway
The same few failures recur across tools:
1. **mouthClose built wrong or missing.** Lips can't stay shut when the jaw opens, or the jaw over-closes.
2. **Lips that open or stay stuck incorrectly** (smile parting the lips; M/P/B not sealing).
3. **Eyelids clipping through eyeballs.** Linear shape keys on a curved surface, made worse by big or flat anime eyes.
4. **Mouth corners moving the whole mouth**, or clipping on funnel and pucker.
5. **Cheek or nose shapes that don't exist on cel-shaded or toon faces.**
6. **Creatures and furry avatars** whose jaws over-close or clip, or that can't track tongue and lips because the shapes were derived from default ones.

### Cited Findings
**mouthClose / jawOpen**
- mouthClose "morphs vertices relatively to the Jaw Open shape". You "will need to assemble" it yourself. — [hai-vr FaceTra docs](https://docs.hai-vr.dev/docs/products/facetra-shape-creator/shapes/mouth-closed)
- Meta's Unity-Movement sample FBX lacked mouthClose, so the lips couldn't stay shut with the jaw open. — [GitHub issue #69](https://github.com/oculus-samples/Unity-Movement/issues/69)
- CC3 users were missing the ARKit mouthClose. The advice was to mix it in 3DXchange. Unity clamps blendshape sliders to 0–100, while some shapes need negative values. — [Reallusion forum](https://forum.reallusion.com/457128/Jaw-down-mouth-closed-blendshape)
- If ARKit tracking drives a model without ARKit shapes, the mouth looks half-open at rest. The fix is to add Perfect Sync or push the jawOpen, funnel and pucker thresholds negative (e.g. −0.25). — [Warudo face tracking](https://docs.warudo.app/docs/mocap/face-tracking)
- The VRChat bug "Selfie Expression causes some avatar jaws to close too much" (31 March 2025, still active July 2026, 61 votes): "Basically every avatar I use" clips, "especially furry avatars". The suspected cause is avatars whose other vowels don't open the mouth enough when blended with a negative "aa". — [VRChat feedback](https://feedback.vrchat.com/bug-reports/p/selfie-expression-causes-some-avatar-jaws-to-close-too-much)

**Lips**
- Solved shapes keep the lips closed mostly, but "the smile opens the lips when it really should not". Jaw-down lip variants were essential to capture. — [Filmic Worlds 2021](https://filmicworlds.com/blog/solving-face-scans-for-arkit/)
- Audio2Face: M/P/B closure is "sometimes difficult". NVIDIA suggested symmetry constraints and lipOpenOffset. — [NVIDIA forum](https://forums.developer.nvidia.com/t/adjusting-mouth-shape-to-better-match-phonemes-blendshape-solve-options/245461)
- Audio2Face mesh fitting produced broken-looking lips. — [NVIDIA forum](https://forums.developer.nvidia.com/t/blendshape-metahuman-wrong-representation/273917)
- Lowering the mouth corners on both lips causes jitter, so put the motion on one lip. — [hinzka](https://hinzka.hatenablog.com/entry/2021/12/02/005814)

**Eyelids and big anime eyes**
- Eyelids clip through eyeballs after baking, because shape keys are linear. The fix is a driver-controlled corrective halfway through the blink. — [Faceit FAQ](https://faceit-doc.readthedocs.io/en/latest/FAQ/)
- Flat anime eyes need the eye pivots moved inside the head. — [Faceit FAQ](https://faceit-doc.readthedocs.io/en/latest/FAQ/)
- Blinking makes the iris bounce or poke through; scale the iris. On big eyes, eyeWide doesn't show the white, so shrink the iris. — [hinzka](https://hinzka.hatenablog.com/entry/2021/12/02/005814)
- If the eyes are blendshape-driven, remove eye bones from the Unity humanoid mapping and set gaze strength to 0. Otherwise both bone and blendshape motion apply, and ears or hair get mis-assigned as eye bones. — [VSeeFace](https://www.vseeface.icu/)
- Eyes or teeth look wrong in expressions; the quick fix is to disable tracking, and the better fix is "to not open the mouth quite as far" in VRoid. — [VSeeFace](https://www.vseeface.icu/)

**Mouth corners, cheeks and toon shading**
- Smile shapes lift the whole mouth. Funnel and pucker clip at the corners. mouthRoll erases toon-textured mouths. cheekPuff breaks when combined with pucker. — [hinzka](https://hinzka.hatenablog.com/entry/2021/12/02/005814)
- Cel-style faces have no real cheek or nose movement, so the motion is reassigned to the lower lid, mouth and brow. — [note.com/054](https://note.com/054/n/n60a59495a757)
- Blendshape normals cause shading to shift during blinks and expressions. — [VSeeFace](https://www.vseeface.icu/)

**Left/right splitting**
- A hard centre split looks unnatural; use a gradient. — [hinzka](https://hinzka.hatenablog.com/entry/2021/12/02/005814)
- Naively splitting a symmetric pose gives shapes containing motion ARKit doesn't expect. One symmetric lip-up read as about 47% L and 50% R. — [Filmic Worlds](https://filmicworlds.com/blog/solving-face-scans-for-arkit/)
- HANA_Tool warns that splits between the eyes and brows tend to break. — [Booth](https://booth.pm/en/items/2604269)

**Creatures, furry and derived shapes**
- Avatars built mostly from default shapes can't track the tongue or precise lips. — [Booth Melvii](https://booth.pm/en/items/8876191), [Booth Shami](https://booth.pm/en/items/8406598)
- Unity stores blendshape values by index, so reordering breaks adapted characters. — [YAF devlog](https://squirrelbite.itch.io/yaf/devlog/609320/yaf-fox-vr-avatar-v110-update)
- A Coconala seller hesitates to take kemono or robot faces. — [Coconala](https://coconala.com/services/1648942)

**Combination dependencies**
- ARKit assumes specific shape combinations, and two shapes can counteract each other. On whether a published guide to these dependencies exists: "There isn't one." — [Filmic Worlds](https://filmicworlds.com/blog/solving-face-scans-for-arkit/)

### Inferences
- mouthClose, blink and the eye/iris, smile corners and the L/R split are the four places an automatic generator most needs explicit, rule-based handling. They match the user's earlier pipeline findings (canthus-anchored blink, mouth interior).
- Testing should cover combinations (jawOpen + mouthClose, pucker + cheekPuff, blink + squint, smile + jawOpen), not single shapes. Several failures only appear in combination.

### Gaps
- No source quantified failure rates by style: anime, cartoon, chubby, thin or creature.
- Chubby-cheek-specific failures (e.g. cheekPuff on already-round cheeks) were not documented anywhere found.

---

## Q5. Marketplaces and services for "52 blendshapes for any model": prices, turnaround, and typical time and cost

### Takeaway
There is a cheap tier and an expensive tier.

**Cheap tier, for VRoid or simple VRM models:**
- Fiverr: $10–25 with 1-day delivery
- Ko-fi: $10
- Coconala: from ¥5,000 (~11 days actual)

**Custom stylized models:**
- VGen: $45–100+, with waitlists
- a Fiverr ARKit-52 gig at $100
- freelancer upgrades around $200 on top of a character package

**Automated service:** Polywink at €499 per model, delivered within 24 h.

No credible first-hand hour count for hand-making 52 shapes was found. Vendors and tool sellers call it the most time-consuming avatar step and claim 50–90% savings.

### Cited Findings
**Fiverr** (pages 403; data from search-result text)
- $10, VRoid Perfect Sync, 1-day, 3 revisions. — [Fiverr bottegastrega](https://www.fiverr.com/bottegastrega/add-blendshapes-to-your-avatar-for-perfect-sync-android-and-iphone)
- $20, 1-day, requires a .vroid file. — [Fiverr hainme](https://www.fiverr.com/hainme/add-apple-arkit-blendshapes-to-your-avatar-for-perfect-sync)
- $25. — [Fiverr yutaru](https://www.fiverr.com/yutaru/add-apple-arkit-blendshapes-to-your-avatar-for-perfect-sync-4b76)
- "52 blendshapes for apple arkit" for $100. — [Fiverr sheikenimation](https://www.fiverr.com/sheikenimation/create-52-blendshapes-for-apple-arkit)

**VGen**
- MisfitWorks (Risa): from $100 advance, one slot per month via a waitlist, and the reference stage takes about a month. — [VGen](https://vgen.co/v_risalab/service/custom-arkit-blendshapes-for-3d-model/34facee4-17ef-4646-9663-fb1dbf8d5e7f)
- Dyenome: $45 for ARKit plus NVIDIA RTX tracking, and about $5 per custom expression. It was not accepting requests when indexed. — [VGen](https://vgen.co/Dyenome/service/custom-expressions-and-arkit-blendshapes-for-3d/84680de8-1a4d-464a-86a0-f6128cba9af1)

**Ko-fi and Etsy**
- Ko-fi: $10 for 52 blendshapes on VRM, sold out. — [Ko-fi](https://ko-fi.com/s/addc554753)
- Etsy: a "52 ARKit blendshapes for your 3D VTuber model" listing exists, but its price was unreadable (403). — [Etsy](https://www.etsy.com/listing/1557033521/52-arkit-blendshapes-for-your-3d-vtuber)

**Coconala (Japan)**
- From ¥5,000 per model.
- Stated delivery 14 days; actual average about 11 days.
- ¥500 per extra model with the same face mesh; ¥2,000 for FBX/PMX→VRM.
- 104 sales; 90 reviews at 5.0.
- Non-VRoid models welcome; kemono and robot designs may be hard to accept.
— [Coconala](https://coconala.com/services/1648942)

**Freelancer bundles and general commissions**
- "52 Blendshapes UPGRADE | $200" on top of a "Stylized PBR Package | $1350", with extra blendshapes at $25 and up. — [advnubs price sheet](https://advnubs.carrd.co/)
- General VTuber model commissions start at $350; VRChat avatars run $80–500. — [Gumroad commissions page](https://levitella.gumroad.com/l/commissions)

**Polywink**
- €499 per model, 157 FACS shapes, within 24 h. 2018 figures (older): $499 internal / $999 commercial; iPhone X package $299. — [Polywink](https://polywink.com/en/9-automatic-expressions-blendshapes-on-demand.html), [CG Channel 2018](https://www.cgchannel.com/2018/07/polywink-creates-blendshapes-and-rigs-for-any-head-model/)

**Pre-made characters that ship with 52**
- Free chibi anime base mesh "with the 52 ARkit facial blendshapes plus a few more". — [Koban Wanko](https://kobanwanko.gumroad.com/l/ChibiBaseMesh)
- Stylized nut mascot with 52+ ARKit shapes, $79. — [TurboSquid](https://www.turbosquid.com/zh_cn/3d-models/stylized-cartoon-character-fully-rigged-arkit-face-rig-nut-mascot-3d-model-2499401)

**Tool prices**
- Faceit: about €80 (2022 thread); the CGDive listing says $99. — [Blender Artists](https://blenderartists.org/t/faceit-add-on-for-blender/1419740)
- ShapeKeyGen: $15. — [Superhive](https://superhivemarket.com/products/shapekeygen)
- ARKit→UE converter: 400 JPY. — [Booth](https://booth.pm/en/items/8607387)
- FaceTra: ≥1000 JPY FANBOX tier. — [hai-vr](https://docs.hai-vr.dev/docs/products/facetra-shape-creator)

**Time claims** (all qualitative or vendor claims)
- The manual method is a "massive production bottleneck"; the script takes "minutes instead of hours". — [Kilutica3D](https://www.deviantart.com/kilutica3d/art/Automate-52-ARKit-Shapekeys-in-Blender-1334945244)
- "cuts that work in half". — [Faceit review](https://superhivemarket.com/products/faceit/ratings)
- "90%" faster. — [YAARKitHelper](https://booth.pm/en/items/8433374)
- Hable needed about 100 scans to solve 50 shapes. — [Filmic Worlds](https://filmicworlds.com/blog/solving-face-scans-for-arkit/)

### Inferences
- The $10–25 one-day Fiverr offers are almost certainly HANA_Tool-style VRoid template application, given the ".vroid required" condition, not custom sculpting. Custom or stylized work prices at about $45–200+ with multi-week queues.
- The Coconala surcharge (¥500 for the same face versus ¥5,000 for a new one) is a market signal: almost all the cost is per new face shape, which is exactly the part automation would replace.

### Gaps
- No reliable hours-per-52-shapes figure from a practitioner. The likely sources (Reddit threads) were inaccessible.
- Current Polywink pricing for an ARKit-only (52) package was not stated on the page.
- No Fiverr or VGen listing clearly priced creature or non-human ARKit sets.

---

## Q6. How do studios handle stylized and creature faces (GDC, SIGGRAPH, VFX)?

### Takeaway
High-end creature work does not auto-transfer human blendshapes. Studios capture a human FACS performance and map it onto a creature-specific rig that extends FACS, then add creature-specific deformers (tusks, muzzles) and simulation. The frontier has moved from blendshapes to muscle and ML solvers.

Stylized animation studios build reusable rig components and use deformers and joints rather than large per-character blendshape libraries.

Game-studio GDC talks on facial pipelines found here are mostly photoreal. No Naughty Dog, Ubisoft, Blizzard or Pixar talk specific to stylized faces was located.

### Cited Findings
**Wētā FX**
- Gollum, Kong and Caesar relied on FACS blendshapes that needed time-consuming slider work. For the Na'vi in Avatar: The Way of Water, Wētā moved to muscle-fibre curves driving the skin, plus a neural network. — [fxguide](https://www.fxguide.com/fxfeatured/exclusive-joe-letteri-discusses-weta-fxs-new-facial-pipeline-on-avatar-2/)
- The training set was 6,000–8,000 scan frames from 80 clips, about 60% FACS poses and 40% speech. — [fxguide](https://www.fxguide.com/fxfeatured/exclusive-joe-letteri-discusses-weta-fxs-new-facial-pipeline-on-avatar-2/)
- Apes: the actor-to-ape mapping "is not, and never is, a direct translation". The rigs extend FACS so mapping stays consistent. Actors record FACS shapes, phonemes and dialogue. — [Cartoon Brew](https://www.cartoonbrew.com/vfx/performance-capture-creature-apes-created-war-planet-apes-152357.html)
- Apes: the Deep Learning Facial Solver, first developed for Gemini Man, solves from capture. Ape rigs support both solver output and full keyframing. — [befores & afters 2024](https://beforesandafters.com/2024/05/12/how-exactly-does-weta-fx-take-on-set-performance-capture-and-translate-it-into-living-breathing-apes/)
- The FDLS paper splits the face into regions (upper face, jaw, lips, cheeks, eyelids, eyeballs), each tied only to its relevant channels. — [FDLS paper](https://scribblethink.org/Work/Pdfs/ma_FdlsADeepLearningApproachToProductionQualityControllableAndRetargetableFacialPerformances.pdf)
- At DigiPro 2016 (older), Wētā would not disclose its FACS pose count beyond "in excess of 40". — [fxguide DigiPro 2016](https://www.fxguide.com/quicktakes/siggraph-saturday-digipro/)

**ILM, Warcraft (2016, older)**
- The Muse software tracked 150+ face dots. The stereo track drove ILM's FEZ FACS shape system, with a SnapSolver locking the mesh to the dots.
- Lips were solved to the human actor, then run through a multipass sim using a custom tusk deformer inspired by a Pixar development for Monsters University, which pushes the mouth corners out.
- A separate team built the face pipeline, and there were over two hours of solved facial capture.
— [Art of VFX](https://www.artofvfx.com/?p=15409), [CGW 2016](https://www.cgw.com/Publications/CGW/2016/Volume-39-Issue-4-Jul-Aug-2016-/Crafty-Effects.aspx)
- Caveat: these two articles were seen through search excerpts, and the per-quote attribution between them was not verified.

**Disney**
- Zootopia 2 has 178+ animals; De'Snake has 3,000+ scales that shift with expressions. — [ACM SIGGRAPH on X](https://x.com/siggraph/status/2010835789953769680)
- The production moved animation from Maya to Presto and animated on two systems with a split strategy. — [SIGGRAPH blog 2026](https://blog.siggraph.org/2026/07/production-insights-from-zootopia-2-and-the-lost-bus-ahead-of-siggraph-2026.html/)
- The SIGGRAPH 2026 talk list includes "Face Rigging through Curvenet Parametrization" (film not confirmed). — [Self Shadow links](https://blog.selfshadow.com/2026/07/26/siggraph-2026-links/)
- The 2016 Zootopia talk "From Armadillo to Zebra" covered character diversity; face-rig specifics are unconfirmed. — [Disney publications](https://www.disneyanimation.com/technology/publications)

**DreamWorks and Blender Studio**
- DreamWorks: reusable facial rig components across characters. — [DreamWorks abstract](https://research.dreamworks.com/wp-content/uploads/2018/07/05-pohle-abstract.done-Edited.pdf)
- Blender Studio (Rik Schutte, Blender Conference, 17 Sept 2025): "Facial Rigging for Stylized Character Animation" for the character Storm. It is built region by region (mouth, eyes, cheeks, brows) and driven by animator needs; the abstract gives no blendshape/bone split. — [Blender Conference](https://conference.blender.org/2025/presentations/4069/)

**Games**
- Epic's Kiteboy: hand-sculpted ARKit-driven blendshapes. — [Unreal forum](https://forums.unrealengine.com/t/metahuman-rig-to-stylized-cartoony-characters/1200631)
- Jeremy Ernst (Epic): joints plus about 20 correctives for a cartoony face. — [Jeremy Ernst](https://www.jeremyernst.com/devblog/category/Rigging)
- GDC talks on facial pipelines found were photoreal:
  - ML Summit "From Photo to Expression" (auto-creates blendshapes for character identities). — [GDC Vault](https://gdcvault.com/play/1034555/)
  - Call of Duty: MWII with DI4D. — [GDC Vault](https://www.gdcvault.com/play/1029448/The-Facial-Animation-Pipeline-of)
  - John Hable's scan pipeline (older). — [GDC Vault](https://www.gdcvault.com/play/1020209/Next-Gen-Characters-From-Facial)
- Overwatch: the Blizzard GDC animation talks found cover body animation (Mei, first-person), not face rigs. — [80.lv](https://80.lv/articles/david-gibson-animating-mei-in-overwatch)
- Guilty Gear Xrd (GDC 2015, older): its art-style talk exists, but face-rig detail was not found in accessible text. — [Arc System Works](https://www.arcsystemworks.com/guilty-gear-xrd-art-talk-at-game-developers-conference-2015/)

### Inferences
- The studio pattern for creatures is "FACS-semantic control set → creature-specific rig → retarget plus creature correctives (tusk, muzzle deformers)". Copying human vertex deltas is not the approach. For a game that must emit ARKit-52 for monsters, this suggests:
  - keep the ARKit names as semantic channels
  - author per-creature-class mappings (e.g. long-muzzle mouth corners, lidless eyes)
  - accept that some channels are empty or remapped, as the VTuber docs allow empty clips
- Stylized studios avoid big per-character blendshape libraries because they must be redone on model changes (Disney, LeSage). That strengthens the case for generating shapes procedurally from a rig every time the mesh changes.

### Gaps
- No accessible GDC or SIGGRAPH material was found from Naughty Dog, Ubisoft, Blizzard or Pixar specifically about stylized facial rigs or automatic generation. The ILM/Pixar tusk-deformer link is the only Pixar-related technical detail found.
- Reddit, ArtStation-blog and Polycount threads on creature ARKit sets could not be read (blocked or 403).
