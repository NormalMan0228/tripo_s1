# Commercial and freemium tools that auto-generate facial blendshapes (ARKit 52) or face rigs for an arbitrary head mesh — status as of 2026-10-13

Scope note: these are research notes for the Korean report writer. Every claim has an inline source. Vendor pages are marketing and are flagged where it matters. "Original mesh kept" means the expressions are delivered as shape keys or blendshapes on the user's own vertex set. "Template" means the user's head is re-expressed in the vendor's base topology, through a wrap, conform, or fit.

---

## Q1. Which tools can take ANY head mesh (stylized, anime, cartoon or monster) and produce the 52 ARKit blendshapes on the ORIGINAL mesh, without forcing a template topology?

### Takeaway
No commercial product in 2026 does this fully automatically for any mesh. The ones that keep the user's own topology are Faceit, which is semi-automatic, the cheaper rig-to-shape-key Blender add-ons (ShapeKeyGen, Shapekey Assist, FaceFlex), and Polywink's upload service. Polywink requires broadly humanoid proportions, and its site is "under maintenance" in 2026. Everything else gives you its own topology instead of yours: Reallusion Headshot (CC topology), MetaHuman (MetaHuman topology), KeenTools FaceBuilder (its own head), Ziva (standard point order, discontinued), Daz (Genesis), and the avatar SDKs.

### Cited Findings

**A. Tools that keep the user's mesh and topology**

- **Faceit (Blender add-on, by Fynn Braren)**
  - It describes itself as a "semi-automatic, non-destructive workflow" for creating facial shape keys on arbitrary characters, and Faceit 1.8 can "Semi-automatically create the 52 ARKit shape keys" — [Faceit docs](https://faceit-doc.readthedocs.io/en/latest/).
  - Workflow: you assign facial parts by picking surfaces, then "Fit rig and expressions to your character, by placing the Faceit landmarks." "Weights [are] generated based on Landmarks." Finally you "Bake the deformation from the modifier stack, pose and sculpting into final shape keys." The listing calls it "fully non-destructive" — [Superhive Faceit page](https://superhivemarket.com/products/faceit).
  - Supported characters per the listing: "a photorealistic human, anthropomorphic or cartoon model". A bunny is shown, with "The 52 ARKit shape keys automatically generated for bunny" — [Superhive Faceit page](https://superhivemarket.com/products/faceit).
  - Expressions come from presets ("Presets include the 52 ARKit expressions that are required for the motion capture functionality"). You then refine them on the rig and bake them to shape keys. Expressions are mirrored automatically when they use _L/_R naming — [Faceit docs: create expressions](https://faceit-doc.readthedocs.io/en/latest/create-expressions/).
  - Faceit 2.3 "allows to use any kind of custom rig" and custom expressions such as visemes, tongue and FACS. It also imports Audio2Face motion — [Faceit docs](https://faceit-doc.readthedocs.io/en/latest/).
- **ShapeKeyGen (Blender, $15)**: "designed to generate all 52 ARKit Blendshapes" for "your rigged character". It needs Auto-Rig Pro, Rigify, or a custom rig. Workflow: register the face parts, Transfer Animation, tune multipliers, Generate ShapeKeys. It targets "stylized, cartoon, or semi-realistic characters" — [Superhive ShapeKeyGen](https://superhivemarket.com/products/shapekeygen).
- **Other add-ons that bake ARKit-named shape keys from rig poses on your mesh**
  - Shapekey Assist ($15) generates the 52 from poses you set on the timeline — [Superhive](https://superhivemarket.com/products/shapekey-assist/docs).
  - FaceFlex needs a rigged face that you pose against an ARKit 52 reference guide. The vendor claims "61 ARKit & 90 Wonder Studio blendshapes" — [Superhive FaceFlex](https://superhivemarket.com/products/faceflex).
  - The free, MIT-licensed "ARKit Creator/Baker" is a manual, guided pose-and-bake add-on — [GitHub](https://github.com/tsikerdekis/ARKit-Creator-Blender-Addon/).
- **Polywink (Eisko, Paris; upload service)**
  - Blendshapes on Demand: €499 per model for 157 FACS blendshapes, "perfectly adapted to the specific topology and UV of your 3D head model" and "directly transferred onto your mesh". It works for "a scanned head, a photorealistic human or a cartoonish character". Output is FBX, delivered in 24 h. Hair, eyelashes and brows must be removed — [Polywink BoD](https://polywink.com/en/9-automatic-expressions-blendshapes-on-demand.html).
  - "Motion Capture Avatar from iPhone": €299, "automatically generates the 52 blendshapes needed" (ARKit/ARCore). Inputs: up to 200,000 polygons, a neutral pose, and eyeballs plus inner mouth as separate meshes. Output is FBX, or MB + FBX for Maya, with free retakes for 3 months — [Polywink iPhone page](https://polywink.com/en/15-facial-animation-for-iphone-x.html).
  - Polywink's 2018 launch claim: "no restrictions on topology or UV layout", but it works only "so long as the proportions are broadly humanoid" — [CG Channel 2018](https://www.cgchannel.com/2018/07/polywink-creates-blendshapes-and-rigs-for-any-head-model/).
  - In 2026 the Polywink home page shows a banner that it is "currently under maintenance" and points to contact@eisko.com — [polywink.com](https://www.polywink.com/).
- **FaceGen Customizer (Singular Inversions)**: exports keep "The mesh topology, vertex ordering and texture layout ... identical to the currently targetted mesh". However, "the animation morphs supplied with the FaceGen Modeller default models are specific to those meshes", so you must copy expression morphs to your topology yourself. It is not an automatic expression generator for a custom mesh — [FaceGen Customizer](https://facegen.com/customizer.htm).
- **NVIDIA Audio2Face Blendshape Generation**
  - It generates blendshapes from a custom neutral mesh after Character Transfer, which places correspondence points on your mesh, and exports USD. Template options are "NV 46 Pose" and "ARkit 51 Pose". NVIDIA staff in the forum said that 52 ARKit shapes on a custom mesh are not supported, only the 46-pose template — [A2F doc (now redirects)](https://docs.omniverse.nvidia.com/audio2face/latest/user-manual/character-transfer/blendshape-generation.html); [NVIDIA forum 199713](https://forums.developer.nvidia.com/t/how-to-export-arkit-blendshapes-weights/199713); [NVIDIA forum 323984](https://forums.developer.nvidia.com/t/can-someone-guide-me-how-i-export-blendershape-generation-with-blendshape-template-52arkit-poses-in-headless/323984).
  - On 2026-10-13 the official doc URL returned a 301 redirect to the NVIDIA ACE for Games page (observed by fetch) — [doc URL](https://docs.omniverse.nvidia.com/audio2face/latest/user-manual/character-transfer/blendshape-generation.html).

**B. Tools that re-express your head in their own template topology**

- **Reallusion Character Creator 5 + Headshot 3 (Mesh mode)**: you can "wrap the source mesh to a selected subdivision level from SubD-0 to SubD-2", and the result is "an astonishingly detailed CC3+ head at 4,000 quads" — [Reallusion Headshot mesh page](https://www.reallusion.com/Character-Creator/headshot/3d-head-from-mesh.html). The Headshot 2 manual says "The imported mesh you see in the viewport is solely for reference and does not directly affect the outcome" — [Headshot 2 manual, Mesh Mode](https://manual.reallusion.com/Headshot_for_CC/ENU/2.0/06-Mesh-Mode/Quick-Guide-Mesh-Mode.html).
- **Epic MetaHuman (From Mesh / From Custom Mesh / From Template Mesh)**
  - From Custom Mesh: "The output is a fully rigged MetaHuman on standard MetaHuman topology that preserves your original mesh's proportions." Its final "Refine Vertices" step projects each template vertex "to the closest point on the custom mesh surface" — [Epic docs: From Custom Mesh Tool](https://dev.epicgames.com/documentation/metahuman/metahuman-creator-from-custom-mesh-tool-in-unreal-engine).
  - From Template Mesh: "The mesh must be the MetaHuman Template mesh in terms of topology" — [Epic docs](https://dev.epicgames.com/documentation/metahuman/from-template-mesh).
- **KeenTools FaceBuilder**: "51 built-in ARKit-compatible FACS blendshapes" on its own head. FAQ: "Can I use a custom 3D model instead of the default head?" "Not at the moment." The suggested workaround is to "wrap the FaceBuilder mesh with the needed topology" — [KeenTools FaceBuilder for Blender](https://keentools.io/products/facebuilder-for-blender).
- **KeenTools Cloud API**: photos in, head out, with "Personalized 51 ARKit blendshapes in a single API call" and "MetaHuman-compatible topology" — [cloud.keentools.io](https://cloud.keentools.io/).
- **Unity Ziva Face Trainer (discontinued)**: marketed as working on "any face mesh". In practice "the head mesh must be cleaned and retopologised manually to match a standard point order", for example by wrapping it to Ziva's generic face in Wrap3 — [CG Channel 2022](https://www.cgchannel.com/?p=138719); [80.lv](https://80.lv/articles/ziva-dynamics-releases-ziva-face-trainer/).
- **Daz Face Transfer 2**: an AI photo-to-likeness tool that outputs Genesis 9 figure shapes, so it uses Genesis topology — [Daz Face Transfer 2](https://www.daz3d.com/face-transfer-2).
- **Avatar SDK MetaPerson**: uses its own avatar template and a "mobile_51 blendshape set" for facial animation — [Avatar SDK blog 2024-12](https://avatarsdk.com/blog/2024/12/07/metaperson-creator-updates-and-the-partnership-with-deepmotion).
- **Avaturn**: custom assets are built on its "template avatars" — [Avaturn docs](https://docs.avaturn.me/docs/ux_customization/assets/intro/).
- **Didimo Popul8**: "By leveraging existing character topologies, rigging, and textures, Popul8 enables developers to generate thousands of unique characters." It is a variation and population generator, not a blendshape generator for an arbitrary mesh — [voicebot.ai 2023](https://voicebot.ai/2023/04/17/virtual-human-developer-didimo-launches-generative-ai-character-creator-popul8/).

**C. Tools that do not generate expressions at all**

These need the shapes or rig to exist already.

- **Mixamo**: no facial rig or blendshapes. The old Fuse path gave about 50 facial blendshapes, but it ended around 2020 — [Adobe community](https://community.adobe.com/t5/mixamo-discussions/can-i-add-facial-expressions-with-mixamo/m-p/12092736).
- **Reallusion AccuRIG**: "does not provide Face rigging functionality" — [cgdive review](https://cgdivetest.super.site/tools/accurig); [Reallusion forum 2022](https://forum.reallusion.com/PrintTopic522024.aspx).
- **Cascadeur 2024.2**: added blendshape support, but "it isn't possible to create blendshapes directly". You can only adjust shapes already set up on imported characters — [CG Channel 2024](https://www.cgchannel.com/2024/09/nekki-unveils-cascadeur-2024-2/).
- **Autodesk Flow Studio (formerly Wonder Studio)**: "supports 88 unique blendshapes" based on FACS with strict naming. You provide the shapes, and the system uses whatever exists — [Wonder Dynamics help: blendshapes](https://help.wonderdynamics.com/character-creation/ai-mocap-system/markerless-face-capture/blendshapes).
- **ReveRig**: needs the 52 ARKit shape keys to exist already — [Blender Market ReveRig](https://blendermarket.com/products/reverig).
- **Faceware and Hyprface**: capture and retarget only (see Q3).

**D. Anime / VRoid niche**

- **HANA_Tool v5** (¥1,500, VRM 1.x, BOOTH): sets up a Perfect Sync expression using bundled VRoid data. It works across VRoid designs only because "the vertex information is the same for VRoid", so it does not apply to arbitrary meshes — [BOOTH HANA_Tool v5](https://booth.pm/en/items/4607357).
- **The "[VRM] ARKIT 52 Blendshape Clipping List Create" tool** (Unity, about ¥300) maps an avatar's existing blendshapes to ARKit names; it does not create shapes — [BOOTH](https://booth.pm/en/items/8607308).

**Comparison table (status as of 2026-10)**

| Tool | Automates | Keeps original mesh? | Output | Styles claimed | Price | Headless / Blender | Status |
|---|---|---|---|---|---|---|---|
| Faceit 1.8 / 2.3 | Landmark-fitted rig, bind weights, bake ARKit 52 and custom expressions to shape keys | Yes (shape keys baked on your objects) | 52 ARKit shape keys, A2F set, visemes, custom; slider control rig | Realistic, anthropomorphic, cartoon | $78 / $99 / $289 for 2–9 seats; GPL — [Superhive](https://superhivemarket.com/products/faceit) | Blender only (3.0–5.2); no documented Python API | Active |
| ShapeKeyGen | Bake 52 ARKit from rig animation | Yes | 52 ARKit shape keys | Stylized, cartoon, semi-realistic | $15, GPL — [Superhive](https://superhivemarket.com/products/shapekeygen) | Blender 3.6–5.0; needs rig | Active |
| Polywink BoD / iPhone | Upload service, 24 h | Yes (vendor claim) | 157 FACS (€499) or 52 ARKit (€299) FBX/MB | Scan, realistic, cartoon; humanoid only | €299–€999 per model — [polywink](https://www.polywink.com/) | No API stated; manual upload | Site "under maintenance" 2026 |
| Reallusion Headshot 3 + CC5 | Wrap mesh to CC head plus full CC facial system | No (CC topology) | CC HD Expression profile (262 BS + 128 correctives), ExPlus incl. 52 ARKit | Realistic and stylized | Headshot $199 + CC5 $299 — [CG Channel](https://www.cgchannel.com/2026/07/reallusion-releases-headshot-3-0/) | Mesh mode GUI-only in our test | Active |
| MetaHuman (UE 5.6–5.8) | Track, fit template, cloud auto-rig | No (MH topology) | MetaHuman DNA rig (joints + RigLogic) | Human-like; stylized "may not solve well" | Free under UE licence below $1M revenue — [metahuman.com](https://www.metahuman.com/license) | Python/Blueprint batch API (5.7+); cloud rigging | Active |
| KeenTools FaceBuilder | Photo-fit own head | No (own head) | 51 ARKit-compatible FACS | Realistic human | $15.99/mo (annual) – $699/yr studio — [KeenTools](https://keentools.io/products/facebuilder-for-blender) | Blender add-on; Cloud REST API for photos | Active |
| Faceform (R3DS) Wrap | Wrap template to scan, DeltaTransfer of blendshape deltas | Template topology | Whatever you transfer | Any (manual control) | Indie $570 / Pro $1,070–1,470 perpetual — [CG Channel](https://www.cgchannel.com/2025/12/faceform-releases-wrap-2025-11-and-wrap4d-2025-11/) | Python Script node (Wrap4D), CLI (older docs) | Active |
| Audio2Face BS Generation | Character Transfer then 46-pose generation | Yes (your neutral) | 46 NV poses (52 ARKit not supported on custom mesh) | Human-like | Free | App deprecated with Launcher | Legacy |
| Ziva Face Trainer | ML face puppet | No (standard point order) | ZivaRT puppet, ARKit-compatible | Human/humanoid | — | — | Discontinued 2024 |
| FaceGen Customizer | Statistical face fitting on your mesh | Yes | Morphs not auto-made for custom mesh | Realistic human | In Modeller Enterprise $1,900 — [FaceGen](https://facegen.com/modeller.htm) | — | Active |

### Inferences
- The only shipping commercial routes that put ARKit-52 shape keys on the user's own vertex set are rig-based baking (Faceit, ShapeKeyGen, Shapekey Assist, FaceFlex) and Polywink's service. Shape keys must share the base vertex count, so rig-based baking keeps topology by construction. Polywink keeps topology only by vendor claim and is now of uncertain availability.
- Faceit is the strongest automated fit for an "original-preserving + Blender + ARKit 52" pipeline. It is semi-automatic, not one-click: landmarks, face-part registration and quality passes still have to be done by hand or by script.
- MetaHuman, Reallusion and KeenTools all replace the user's face surface with their template topology. MetaHuman projects template vertices onto your surface, so the shape is approximated, but the vertex set is theirs. This conflicts with the project's "keep original mesh" rule unless the template's expression deltas are transferred back onto the original mesh in a second step, for example with Blender Surface Deform or Wrap DeltaTransfer.

### Gaps
- Polywink's current operating status and prices could not be confirmed beyond the 2026 maintenance banner and the € prices on its pages.
- No vendor documents how Polywink's transfer works internally (template plus deformation transfer, or ML).
- No public evidence was found that Hyprface or Hyprsense ever offered blendshape generation for custom meshes.

---

## Q2. How do they work under the hood, and what happens with non-human, cartoon or anime proportions?

### Takeaway
There are three mechanisms:
1. **Landmark-fitted rig, then bake.** Faceit and the ShapeKeyGen family deform your own mesh with a generic rig fitted to landmarks, then bake the poses to shape keys. This adapts to any proportions but quality depends on the rig fit.
2. **Template wrap or conform.** Headshot, MetaHuman, Ziva, Wrap and FaceBuilder fit a human template to your mesh's surface. They fail or degrade on extreme or stylized proportions, empty eye sockets, big cartoon eyes and fantasy features.
3. **Deformation transfer from a template's expressions to your neutral via correspondences.** Audio2Face, likely Polywink, and Wrap DeltaTransfer work this way. They are bounded by humanoid proportions and the template pose set.

### Cited Findings
- **Faceit (rig fit + bake)**: landmarks fit the rig and expressions to the character, weights are generated from the landmarks, and the deformation is baked to shape keys — [Superhive Faceit](https://superhivemarket.com/products/faceit). A reviewer says it has been their default "either human, animal or hybrid" — [Faceit ratings](https://superhivemarket.com/products/faceit/ratings).
- **MetaHuman (template conform)**: tracking "creates a series of markers along the facial features of your mesh", and "Identity Solve fits the Template Mesh vertices to the volume of the Neutral Pose Mesh". The mesh needs open eyes with visible sclera, and "Empty eye sockets are very likely to track poorly and generate fitting artifacts" — [Epic docs: From Mesh](https://dev.epicgames.com/documentation/metahuman/from-mesh).
- **MetaHuman stylized limits**, from the From Custom Mesh docs — [Epic docs](https://dev.epicgames.com/documentation/metahuman/metahuman-creator-from-custom-mesh-tool-in-unreal-engine):
  - "You get the best results from meshes that resemble human morphology in an A pose."
  - "Heavily stylized meshes or meshes with extreme proportions may not solve well."
  - "characters far outside average proportions can show volume loss or pinching during animation."
  - "fantasy features (pointed ears, heavy brow ridges) solve with varying quality."
- **MetaHuman forum failures**:
  - A smooth, textureless stylized face gave "Failed to Auto-Track Face Contour Landmarks" — [UE forum](https://forums.unrealengine.com/t/cannot-import-to-custom-mesh-in-metahuman-the-2d-view-shows-only-a-black-head-silhouette/2746663).
  - In UE 5.8.3 the face stayed identical to the archetype when the face detector returned nothing — [UE forum](https://forums.unrealengine.com/t/ue-5-8-3-metahuman-from-custom-mesh-head-only-facemesh-stays-archetype-identical-when-facial-tracking-fails-though-native-conformtarget-does-deform-what-input-contract-are-we-missing/2838004).
  - Users advise wrapping the MetaHuman Conform Topology asset onto the head in a DCC first — [UE forum](https://forums.unrealengine.com/t/the-3d-model-does-not-fit-well-with-metahuman-identity-in-unreal-engine/2731307).
- **Reallusion Headshot (template wrap)**: uses auto-detected alignment points, then Refine Mesh brushes to "match your model to the topology guide" — [Headshot 2 manual](https://manual.reallusion.com/Headshot_for_CC/ENU/2.0/06-Mesh-Mode/Quick-Guide-Mesh-Mode.html). Reallusion's own warnings — [Reallusion mesh page](https://www.reallusion.com/Character-Creator/headshot/3d-head-from-mesh.html):
  - "Wrapping a sophisticated or creatively designed 3D head can present challenges and potentially yield unintended results."
  - Eyelash and inner-lip projection is difficult.
  - Extra alignment points exist for exaggerated features.
- **Reallusion: local project test, 2026-10-11, CC5 + Headshot 3 trial on character1** — [project memory: cc5-headshot.md](C:/Users/dd/.claude/projects/C--lsm26-triphthonS1/memory/cc5-headshot.md):
  - Auto Detection placed the big cartoon eyes' lower-lid points mid-eyeball.
  - Thin, fused cartoon lips produced an almost absent upper lip.
  - CC's Eye_Blink did not close a 2.6 cm-tall cartoon eye. The upper lid stopped short, because CC's blink delta is sized for human eye openings.
- **Reallusion facial profiles** only transfer between characters with identical mesh data ("triangles, quads, the number of vertex and faces, and vertex IDs") — [Reallusion FeedBackTracker](https://reallusion.com/FeedBackTracker/Issue/Copy-Facial-Profile-with-custom-sliders-to-another-Character-doesnt-work).
- **Ziva**: the mesh had to be fitted to Ziva's generic face in Wrap3 using point and polygon selections, cleaned, and subdivided. Training used a 15 TB library of 4D scans and produced a 30 MB puppet running at about 3 ms per frame — [CG Channel 2022](https://www.cgchannel.com/?p=138719).
- **Faceform Wrap**: the DeltaTransfer node (Wrap 2025.11) lets users "retarget vertex expressions or series of blendshapes between characters" by moving deformation deltas from one neutral mesh to another. The StretchVertexMask node computes stretch-compression masks for blendshapes — [CG Channel 2025-12](https://www.cgchannel.com/2025/12/faceform-releases-wrap-2025-11-and-wrap4d-2025-11/).
- **Audio2Face Blendshape Generation**: Character Transfer from the template head "Mark" to the target, then generation of a fixed template pose set. NVIDIA's own Audio2Face-3D data pipeline transfers ARKit poses from a template to a neutral with matching topology by vertex displacement, or uses deformation transfer when needed, then applies artist cleanup — [arXiv 2508.16401](https://arxiv.org/pdf/2508.16401); [NVIDIA forum](https://forums.developer.nvidia.com/t/how-to-export-arkit-blendshapes-weights/199713).
- **Polywink**: shapes come from scanned expressions "or from the ARKit for the standard option" and are "directly transferred onto your mesh"; the method is not specified — [Polywink BoD](https://polywink.com/en/9-automatic-expressions-blendshapes-on-demand.html). Proportions must be "broadly humanoid" — [CG Channel 2018](https://www.cgchannel.com/2018/07/polywink-creates-blendshapes-and-rigs-for-any-head-model/).
- **AccuRIG on stylized bodies**: a stylized monkey worked with "minor distortion due to the stylized nature of the head and neck". Body only — [BlenderNation 2022](https://www.blendernation.com/2022/11/30/accurig-to-blender-pipeline-an-easy-accurate-way-to-auto-rig-any-character-promoted/); [cgdive](https://cgdivetest.super.site/tools/accurig).
- **Research, not commercial** (2023–2026), which claims topology-agnostic automatic face rigging:
  - "Fully Automatic Blendshape Generation for Stylized Characters" (IEEE VR 2023, VAE + MLP latent mapping) — [SJTU PDF](https://sjtu-characterlab.github.io/files/Fully_Automatic_Blendshape_Generation_for_Stylized_Characters.pdf).
  - RigAnyFace (NeurIPS 2025): neutral mesh to FACS blendshapes, including disconnected parts — [arXiv 2511.18601](https://arxiv.org/html/2511.18601).
  - OmniFaceRig (2026 preprint): surface-only mesh to up to 155 blendshapes plus teeth, gums and tongue, for human and animal characters — [arXiv 2606.08043](https://arxiv.org/html/2606.08043v1).
  - TopoRig (2026 preprint, title only seen) — [arXiv 2609.15746](https://arxiv.org/pdf/2609.15746).
  - An open-source ARKit deformation-transfer implementation — [GitHub vasiliskatr](https://github.com/vasiliskatr/deformation_transfer_ARkit_blendshapes).

### Inferences
- Template-wrap systems carry two built-in assumptions: human-sized eye openings and lip thickness. That is why the local Headshot test failed on big anime-style eyes and thin cartoon lips. MetaHuman's docs give the same warning. Expect similar failures on monsters (no sclera, muzzles, beaks) and on very fat or very thin faces ("volume loss or pinching").
- Rig-fit-and-bake (Faceit) tolerates odd proportions better, because the rig is placed on your landmarks and the result is only as good as the rig poses. Big cartoon eyes still need blink tuning. Muzzles and snouts depend on how well a human-derived rig maps onto them; Faceit's bunny example shows this is possible.
- No commercial tool found applies ML to generate ARKit 52 directly for arbitrary stylized meshes. That capability currently exists only in research preprints such as OmniFaceRig and RigAnyFace.

### Gaps
- Polywink's internal algorithm and its behaviour on non-humanoid heads are not documented.
- No independent benchmark compares Faceit, Polywink and Headshot on the same stylized heads.
- Whether Faceform's DeltaTransfer works between different topologies, or needs a wrapped common topology first, is not documented in the sources found.

---

## Q3. Exact prices, licence terms for commercial game use, and headless, scripted or Blender use

### Takeaway
- **Cheapest commercial ARKit-52-on-own-mesh path:** Faceit $78–$99 (GPL, Blender 3.0–5.2) or ShapeKeyGen $15. Neither has a documented headless API; as Blender add-ons they can only be driven through bpy, undocumented.
- **MetaHuman:** free under $1M revenue, now usable in any engine, with a real Python batch API (5.7/5.8+). It is cloud-dependent and template-topology.
- **Reallusion:** $299 + $199, mostly GUI.
- **Wrap:** $570–$1,470 perpetual, with Python nodes.
- **Polywink:** €299–€999 per model, manual upload, currently in maintenance.
- **Discontinued or defunct:** Ziva (2024), Ready Player Me (2026-01-31), Hyprface SDK (absorbed by Epic in 2020), the Audio2Face standalone app (Launcher deprecated 2025-10-01).

### Cited Findings

**Faceit**
- $78 (1.8 ARKit), $99 (2.3 Unlimited), $289 (Studio, 2–9 seats). License: GPL. Blender 3.0–5.2, extension compatible — [Superhive Faceit](https://superhivemarket.com/products/faceit).
- No Python API is documented. The docs name operators such as "Load Faceit Expressions" — [Faceit docs](https://faceit-doc.readthedocs.io/en/latest/create-expressions/).
- A web search for `bpy.ops.faceit` scripting examples found nothing (searched 2026-10-13).

**Other Blender add-ons**
- ShapeKeyGen: $15, GPL, Blender 3.6–5.0 — [Superhive](https://superhivemarket.com/products/shapekeygen).
- Shapekey Assist $15, MHFRT $24.99, Shapekeys Extended $8, Facebeats Pro $29 (Blender 4.5–5.0) — [Superhive Shapekey Assist](https://superhivemarket.com/products/shapekey-assist/docs); [MHFRT](https://superhivemarket.com/products/mhfrt/versions); [Shapekeys Extended](https://superhivemarket.com/products/shapekeys-extended/docs); [Facebeats Pro](https://superhivemarket.com/products/facebeats-pro--arkit-performance-layer/faq).

**Auto-Rig Pro**
- Lite $25, Full $50, 10 seats $162, 20 seats $227, with 12 months of updates — [sorceress.games guide (competitor-authored)](https://sorceress.games/blog/auto-rig-pro-free-download-the-honest-2026-path).
- Artell's listing mentions "Advanced facial setup with automated placement" and animated shape-key support — [Gumroad Auto-Rig Pro](https://artell.gumroad.com/l/auto-rig-pro).
- It does not generate ARKit 52 itself; ShapeKeyGen is used on top of it — [Superhive ShapeKeyGen](https://superhivemarket.com/products/shapekeygen).

**Polywink**
- Current pages:
  - Blendshapes on Demand €499 per model.
  - Advanced Rig on Demand €999 (236 blendshapes).
  - Motion Capture Avatar from iPhone €299.
  - MetaHuman Rig service, price not listed — [polywink.com](https://www.polywink.com/).
- 2018 licence tiers:
  - BoD $499 internal / $999 commercial.
  - Rig on Demand $999 / $1,999.
  - iPhone X $299 per model, commercial — [CG Channel 2018](https://www.cgchannel.com/2018/07/polywink-creates-blendshapes-and-rigs-for-any-head-model/).
- The current pages do not state commercial terms. The free sample is CC BY-NC-ND — [Polywink iPhone page](https://polywink.com/en/15-facial-animation-for-iphone-x.html).
- No API is mentioned. Blender is not listed among supported software — [Polywink BoD](https://polywink.com/en/9-automatic-expressions-blendshapes-on-demand.html).

**Reallusion**
- Pricing:
  - CC5 perpetual $299; subscriptions from $29/month or $99/year.
  - Headshot 3.1 perpetual $199.
  - Headshot 1400+ morph pack $99.
  - AI image credits: 15 DA points for 2K, 30 for 4K — [CG Channel 2026-07](https://www.cgchannel.com/2026/07/reallusion-releases-headshot-3-0/).
  - ActorMIXER Pro $199; CC5 Deluxe bundle $499 — [CG Channel 2025-08](https://www.cgchannel.com/2025/08/reallusion-releases-character-creator-5/).
- Release dates: Headshot 3.0 posted 2026-04-28; 3.1 by 2026-07-07 — [CG Channel](https://www.cgchannel.com/2026/07/reallusion-releases-headshot-3-0/).
- AccuFACE 2 (2026-08):
  - Tailored to CC5 HD characters. It drives the "HD Expression Profile (262 blendshapes and 128 corrective morphs)" and supports stylized characters through Expression Curves.
  - No price is given. iClone Personal is a permanently free edition — [Digital Production 2026-08-10](https://digitalproduction.com/2026/08/10/accuface-2-grand-launch-professional-grade-facial-mocap-for-cc5-hd-characters/).
- The ExPlus profile adds 63 blendshapes (52 ARKit + 11 tongue) to CC characters — [CC4 manual](https://manual.reallusion.com/Character-Creator-4/Content/ENU/4.0/08_Animation/Creating-Character-with-ARKit-Profile.htm).
- Automation, from the local project test — [project memory: cc5-headshot.md](C:/Users/dd/.claude/projects/C--lsm26-triphthonS1/memory/cc5-headshot.md):
  - CC5 embeds Python 3.8 (RLPy).
  - The Headshot 3 API exposes photo mode only; mesh mode is GUI-only.
  - The legacy `RHeadshot.ImportHeadFromObj` crashed.
  - The Headshot 3 trial refuses Save Project, FBX and OBJ export.

**MetaHuman**
- Licence:
  - "Included in the standard Unreal Engine license", free under $1M USD revenue.
  - MetaHumans "can be used with any engine or creative software" — [metahuman.com/license](https://www.metahuman.com/license).
  - The 2025-06 change allowed use in Unity, Godot and others — [Digital Production 2025-06](https://digitalproduction.com/2025/06/05/metahumans-graduate-ready-for-unity-godot-and-the-fab-cash-register/).
  - A third-party claim of $1,850 per seat per year above the threshold is unverified — [Medium guide](https://medium.com/@Jamesroha/a-beginners-guide-to-metahumans-in-unreal-engine-5-6-and-5-7-e9b14fadbf3d).
- Automation:
  - MetaHuman 5.7 adds a Python/Blueprint API to "automate and batch process nearly all editing and assembly operations" (sculpt, conform, wardrobe, rigging, textures), including runs on a compute farm — [MetaHuman 5.7 release notes](https://dev.epicgames.com/documentation/metahuman/metahuman-5-7-release-notes).
  - The current scripting docs list UE 5.8+ as a prerequisite — [Epic Python scripting docs](https://dev.epicgames.com/documentation/metahuman/metahuman-creator-python-scripting-in-unreal-engine).
  - `request_auto_rigging` calls MetaHuman Cloud services. Known issue: a rig cannot be removed once generated — [UE forum](https://forums.unrealengine.com/t/metahuman-python-api-add-ability-to-edit-metahuman-creator-assets-in-place/2763639).
  - Identity Solve and auto-rigging run in the cloud — [Epic docs: From Mesh](https://dev.epicgames.com/documentation/metahuman/from-mesh).
- Blender: the Poly Hammer "Character DNA" add-on imports, edits and exports MetaHuman DNA. Pricing:
  - Earlier: base edition free, Pro $79 individual, teams from $259 — [CG Channel 2025-03](https://www.cgchannel.com/2025/03/poly-hammer-releases-metahuman-dna-add-on-for-blender/).
  - 2026-07: headline says "now free" — [CG Channel 2026-07](https://www.cgchannel.com/2026/07/the-character-dna-metahuman-add-on-for-blender-is-now-free/).
  - Epic changed its licensing to allow MetaHumans to be used directly in Blender — [same](https://www.cgchannel.com/2026/07/the-character-dna-metahuman-add-on-for-blender-is-now-free/).

**KeenTools FaceBuilder**
- Freelancer: $15.99/month billed yearly ($191.88) or $19.99/month.
- Studio: $699/year floating. FaceBundle $999/year studio.
- 15-day full trial. "All subscriptions can be used for commercial work." Freelancer plans are for individuals only.
- The add-on is an "open source adapter for KeenTools Core Library" — [KeenTools](https://keentools.io/products/facebuilder-for-blender).
- Cloud API: REST, billed per reconstruction and per download call; prices are not public on the landing page — [cloud.keentools.io](https://cloud.keentools.io/).

**Faceform (formerly R3DS) Wrap**
- Wrap Indie $570 perpetual node-locked (revenue under $100k/year).
- Professional $1,070 node-locked / $1,470 floating. Wrap4D price on enquiry. Free for education. Windows and Linux.
- The Wrap4D "Script node runs external Python scripts" — [CG Channel 2025-12](https://www.cgchannel.com/2025/12/faceform-releases-wrap-2025-11-and-wrap4d-2025-11/).
- Perpetual with 1 year of updates or annual subscription. An extra maintenance year costs 50% — [russian3dscanner.com](https://russian3dscanner.com/?p=191).
- WrapX (2014) introduced a "Python API for better integration and batch processing" — [CGPress](https://cgpress.org/archives/wrapx-batch-topology-transfer-tool.html).
- An older R3DS page mentions a command-line interface — [russian3dscanner.com](https://www.russian3dscanner.com/?p=16).

**NVIDIA Audio2Face**
- Omniverse Launcher deprecated as of 2025-10-01 — [NVIDIA legacy tools](https://developer.nvidia.com/omniverse/legacy-tools).
- On 2025-09-24 NVIDIA open-sourced the following. No licence is named in the blog post — [NVIDIA blog](https://developer.nvidia.com/blog/nvidia-open-sources-audio2face-animation-model):
  - Audio2Face models (regression v2.2, diffusion v3.0)
  - Audio2Emotion
  - The SDK
  - The training framework
  - A Maya plugin and a UE 5.5/5.6 plugin
- A forum reply says the A2F app "has been depreciated. Along with Launcher", while the NIM and plugins live on — [NVIDIA forum](https://forums.developer.nvidia.com/t/trouble-integrating-audio2face-with-omniverse-app-without-omniverse-launcher/348726).
- A user found no headless method for exporting Blendshape Generation output — [NVIDIA forum 323984](https://forums.developer.nvidia.com/t/can-someone-guide-me-how-i-export-blendershape-generation-with-blendshape-template-52arkit-poses-in-headless/323984).

**Ziva**
- Unity stopped sales and active support on 2024-04-02. Licences could be converted to 5-year terms. Customer portal access ended after 2024-10-02.
- DNEG received an exclusive perpetual licence to the Ziva IP — [CG Channel 2024-04](https://www.cgchannel.com/2024/04/unity-discontinues-the-ziva-products/).

**Hyprsense / Hyprface**
- Epic acquired Hyprsense in late 2020 — [AWN](https://www.awn.com/news/epic-acquires-hyprsense-technology-optimize-players-immersive-experience); [PocketGamer.biz](https://www.pocketgamer.biz/epic-acquires-facial-animation-firm-hyprsense).
- Hyprface was a real-time facial mocap SDK. A forum user says "everything was terminated" — [UE forum](https://forums.unrealengine.com/t/hyprface-in-ue4/479970).

**Ready Player Me**
- Acquired by Netflix in December 2025. The public platform went offline on 2026-01-31 — [PocketGamer.biz](https://www.pocketgamer.biz/netflix-acquires-avatar-creation-platform-ready-player-me); [Avatar SDK blog 2026 (competitor)](https://avatarsdk.com/blog/2026/08/31/avatar-platforms-2026-whos-alive-whos-gone/).

**Avatar SDK MetaPerson / Avaturn (in3D)**
- MetaPerson: first avatar free; Pro $800/month for 6,000 avatars.
- Avaturn: Pro $800/month for 1,000 avatars.
- Avaturn and in3D belong to the same company (Goodsize Inc.).
- Source: vendor-competitor blog — [Avatar SDK blog 2026](https://avatarsdk.com/blog/2026/08/31/avatar-platforms-2026-whos-alive-whos-gone/).

**Didimo**
- Still active in January 2026 (Porto, Portugal). B2B Popul8; $15.8M total raised, last round $7.15M in 2022 — [Portugal Global 2026-01](https://www.portugalglobal.pt/en/news/2026/janeiro/didimo-has-built-its-growth-on-the-gaming-industry); [Dealroom](https://dealroom.co/companies/didimo/).

**Daz 3D**
- An Interactive License is required to use Daz store content "in video games or other applications". It is per product, only where the creator offers it, and non-refundable — [Daz Interactive License](https://www.daz3d.com/interactive-license-info).
- Face Transfer 2 trial: three saved shapes without watermark — [Daz Face Transfer 2](https://www.daz3d.com/face-transfer-2).

**FaceGen**
- Modeller Core $300, Pro $900, Enterprise $1,900. Customizer is included only in Enterprise — [FaceGen Modeller](https://facegen.com/modeller.htm); [Customizer](https://facegen.com/customizer.htm).

**Faceware**
- Analyzer 3 Studio $299/year, Retargeter 5 Studio $179/year, Studio Plus $1,749 / $999 — [Faceware pricing](https://facewaretech.com/pricing).
- Faceware Studio 2.0: Professional $2,340/year, Indie $239/year — [Faceware shop](https://my.facewaretech.com/shop).

**Autodesk Flow Studio (Wonder)**
- Character upload requires validation with its Blender 3.6.2 or Maya 2022–2024 add-ons, a 500 MB file and 1.5M polygons maximum — [Wonder Dynamics help](https://help.wonderdynamics.com/character-creation/ai-mocap-system/markerless-face-capture/blendshapes).

### Inferences
- For a headless or batch pipeline that must keep the original mesh, no commercial product offers a documented API. A custom pipeline would combine these:
  - Faceit operators called through `bpy` in background Blender. This is undocumented, but an add-on's operators register under `bpy.ops` when enabled.
  - Or Wrap's Python/CLI plus a DeltaTransfer-style step.
  - Or open-source deformation transfer.
- MetaHuman is the only commercial system with an official batch Python API, but its output is MetaHuman topology driven by a cloud auto-rigger. Using it on our characters would violate the "never reshape / keep original mesh" rule unless a back-transfer step is added.
- Faceit's GPL licence (add-on code) does not restrict the commercial use of the shape keys it produces. The output belongs to the user's asset. This is our inference from the GPL-for-code norm on Superhive, not a stated term.

### Gaps
- Not verified: current Polywink commercial licence terms, AccuFACE 2 price, Daz Face Transfer 2 price, the Reallusion export/EULA terms for shipping CC-derived heads in a non-Unreal/Unity game, KeenTools Cloud API per-call prices, Faceware enterprise terms, and whether Faceit officially supports scripted or headless use.
- The licence of the open-sourced Audio2Face components is not named in NVIDIA's blog.

---

## Q4. Known limitations and user complaints

### Takeaway
Three kinds of complaint recur:
- **Template systems** (MetaHuman, Headshot, Ziva, Daz Face Transfer) fail on stylized or extreme proportions and lose likeness: volume loss, pinching, fitting artifacts, bad eyes and lips.
- **Rig-bake add-ons** need a rig and manual tuning.
- **Services** (Polywink) are humanoid-only and may not be available.

Faceit has very positive reviews with few complaints. Its weakness is that it is semi-manual and has no documented scripting.

### Cited Findings
- **Faceit**: average 5 stars from 80 ratings, 93% at the top score. The main complaint is that "Beginners may still struggle a bit". Reviewers praise automatic ARKit 52 generation, landmark-based face outlining and easy corrective shape keys — [Faceit ratings](https://superhivemarket.com/products/faceit/ratings). The listing hedges: "Results usually require no further Weight Painting" — [Superhive Faceit](https://superhivemarket.com/products/faceit).
- **ShapeKeyGen**: custom rigs need setup, and expressions need multiplier tuning — [Superhive ShapeKeyGen](https://superhivemarket.com/products/shapekeygen).
- **MetaHuman**:
  - Stylized meshes "may not solve well", and volume loss or pinching appears on extreme proportions — [Epic docs](https://dev.epicgames.com/documentation/metahuman/metahuman-creator-from-custom-mesh-tool-in-unreal-engine).
  - Empty eye sockets track poorly — [Epic docs: From Mesh](https://dev.epicgames.com/documentation/metahuman/from-mesh).
  - Grooms (brows, beards) are not preserved by Identity Solve — [UE forum](https://forums.unrealengine.com/t/the-3d-model-does-not-fit-well-with-metahuman-identity-in-unreal-engine/2731307).
  - The cloud dependency is stated in the docs — [Epic docs: From Mesh](https://dev.epicgames.com/documentation/metahuman/from-mesh).
- **Reallusion Headshot**:
  - Wrapping creative heads "can present challenges and potentially yield unintended results"; textures tear on partial meshes; eyelashes and inner lips are hard to project — [Reallusion](https://www.reallusion.com/Character-Creator/headshot/3d-head-from-mesh.html).
  - A user reported that Wrap at CC subdivision level 3 did not work — [Reallusion forum](https://discussions.reallusion.com/t/3dscan-head-base-mesh-level-wrap/13662).
  - In the local test: cartoon eyes and lips failed and the blink did not close, as described in Q2 — [project memory](C:/Users/dd/.claude/projects/C--lsm26-triphthonS1/memory/cc5-headshot.md).
- **Daz Face Transfer 2**: the add-on Face Transfer Shapes 2 exists because generated faces look wider than the photo, are flattened in profile, have distorted ears, and have under-defined features — [Daz Face Transfer Shapes 2](https://delorean.daz3d.com/face-transfer-shapes-2-for-genesis-9).
- **Audio2Face**: forum threads report errors setting up the blendshape solve for Reallusion CC characters and near-zero blendshape conversion values — [NVIDIA forum 265804](https://forums.developer.nvidia.com/t/audio2face-setup-blendshape-solve-error-with-reallusion-character-creator/265804); [NVIDIA forum 231524](https://forums.developer.nvidia.com/t/blendshape-data-conversion-resutls-amost-zero-values/231524). These are thread titles; the threads were not read. A search summary also mentioned a user who had to freeze a scale of 50 in Maya before transfer worked, but the exact thread was not identified, so treat that as unverified. The 52-ARKit-on-custom-mesh limitation is covered in Q1.
- **Ziva**: required manual retopology to a standard point order, despite marketing it as "any face mesh" — [CG Channel 2022](https://www.cgchannel.com/?p=138719). The product was discontinued at short notice, announced by email and blog on the same day — [CG Channel 2024](https://www.cgchannel.com/2024/04/unity-discontinues-the-ziva-products/).
- **FaceGen Customizer**: a Daz forum user reported up to about 20 hours of compute per mesh. This is anecdotal and undated — [Daz forum](https://www.daz3d.com/forums/discussion/comment/278574/).
- **Cascadeur**: the facial feature only adjusts existing blendshapes — [CG Channel 2024](https://www.cgchannel.com/2024/09/nekki-unveils-cascadeur-2024-2/).
- **Mixamo**: the face blendshapes from Fuse disappeared after about 2020 — [Adobe community](https://community.adobe.com/t5/mixamo-discussions/mixamo-doesn-t-provide-facial-rigging/m-p/11656026).
- **Ready Player Me**: shut down. Studios such as VRChat that depended on it had to migrate — [Genies blog (competitor)](https://genies.com/blog/ready-player-me-shutdown).

### Inferences
- "Template" vendors are honest in their own docs that heavily stylized or non-human heads fall outside their design. Anime heads with large eyes, monsters, and very fat or very thin faces should be treated as unsupported by MetaHuman and Headshot.
- The practical commercial shortlist for "ARKit 52 on the original stylized mesh" is Faceit first, with ShapeKeyGen or FaceFlex as cheaper rig-dependent alternatives. Polywink can be added only if Eisko confirms the service is running.
- Even with Faceit, big cartoon eyes and thin lips will need per-character fixes, such as blink correctives and lip-roll shapes. That matches the project's earlier finding that CC's human-sized blink delta failed on a 2.6 cm eye.

### Gaps
- No user reviews were found that test Faceit specifically on anime-style or monster heads. The ratings page only mentions "animal or hybrid".
- No independent review was found of Polywink output quality on cartoon or creature heads.
- No commercial 2024–2026 AI startup was found that ships "any mesh → 52 ARKit" for stylized or non-human heads. Searches surfaced only research preprints (OmniFaceRig, RigAnyFace, TopoRig) and freelancer services on Fiverr ($10–$100+ per head, manual) — [Fiverr](https://www.fiverr.com/gigs/52-arkit-blendshape). Anything World, Avaturn and in3D facial specs (ARKit coverage) were not confirmed from official docs.
