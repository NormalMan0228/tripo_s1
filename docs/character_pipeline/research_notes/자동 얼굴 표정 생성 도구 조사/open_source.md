# Open-source tools for automatic facial blendshapes (ARKit 52) and face rigs on arbitrary head meshes

Research date: 2026-10-13. Stars and "last push" dates come from the GitHub REST API on that date. "No license" means the repo has no LICENSE file, so all rights are reserved by default. "Dormant" means no push for 2 years or more.

---

## Q1. Which open-source projects exist, and what does each do? (dense catalogue)

### Takeaway
The usable code falls into six families. (a) End-to-end "neutral head in, expression set out" tools: QtMeshEditor `qtmesh facerig` (MIT, template + NRICP + deformation transfer), TopoRig (neural, academic-only) and NFR (neural, MIT code). (b) Deformation-transfer and example-based-rigging libraries (mostly MIT, mostly dormant). (c) Blender "pose a face rig, then bake 52 keys" add-ons, which are not automatic. (d) Blender shape-key transfer add-ons based on Surface Deform or nearest-vertex. (e) FLAME/3DMM tools, which are mostly non-commercial and replace your topology. (f) Body auto-riggers (UniRig, MagicArticulate, Puppeteer and others), which produce no facial expressions.

### Cited Findings

#### (a) End-to-end: neutral head mesh → expression shapes (closest to the goal)

| Project | What / method | Input needed | Keeps original mesh? | Stylized / non-human | Output | License | Activity | Headless |
|---|---|---|---|---|---|---|---|---|
| **QtMeshEditor `qtmesh facerig`** ([repo](https://github.com/fernandotonon/QtMeshEditor), [epic #889](https://github.com/fernandotonon/QtMeshEditor/issues/889)) | Attaches the 52 ARKit morph targets to a neutral head. Uses an ICT-FaceKit template, then NRICP to fit the template to the user mesh, then per-triangle deformation transfer. The issue calls it "a deterministic geometry algorithm (sparse linear solve), not a neural net". `src/FaceRig/` contains `FaceLandmarkDetector`, `NonRigidICP`, `DeformationTransfer`, `FaceRigAlign` and unit tests ([tree](https://github.com/fernandotonon/QtMeshEditor)) | Neutral head mesh (glb). `--template ict\|<file>`, `--only` subset | Yes by design: "Output: the same mesh carrying `jawOpen`, `mouthSmileL…`" ([#889](https://github.com/fernandotonon/QtMeshEditor/issues/889)) | The issue says "Humanoid-only, by construction… A prop, quadruped, or non-face mesh yields garbage"; creature rigs are out of scope ([#889](https://github.com/fernandotonon/QtMeshEditor/issues/889)) | glb with morph targets. It also pairs with the `qtmesh lipsync` (Audio2Face-3D via ONNX) and `qtmesh mocap` commands ([README](https://github.com/fernandotonon/QtMeshEditor)) | MIT. The ICT template is MIT; FLAME and Wrap3D were explicitly rejected over licensing ([#889](https://github.com/fernandotonon/QtMeshEditor/issues/889)) | 61★, push 2026-10-09; epic closed 2026-07-22 | C++/Qt CLI (`qtmesh facerig head.glb -o rigged.glb`) plus an MCP tool. Not a Blender add-on, but callable as a subprocess |
| **TopoRig** ([repo](https://github.com/TaatiTeam/TopoRig), [arXiv 2609.15746](https://arxiv.org/abs/2609.15746)) | Neural network that predicts per-vertex displacements from FACS controls. Trained with three kinds of supervision: template-biased common-topology rigs, transferred rigs across topologies, and image cues. Starts from the ICT FaceKit expression model; 3,496 generated training identities ([arXiv](https://arxiv.org/abs/2609.15746)) | Neutral GLB/FBX, auto-aligned to the ICT reference with MediaPipe landmarks via Blender 4.2. OBJ needs a landmark JSON alongside ([README](https://github.com/TaatiTeam/TopoRig)) | Yes: it "predicts deformations directly on input mesh vertices while keeping the original topology" ([arXiv](https://arxiv.org/abs/2609.15746)). The optional mouth post-process splits joined lips and adds teeth/tongue; the optional eye post-process replaces eyeballs ([README](https://github.com/TaatiTeam/TopoRig)) | "Diverse character geometries" and unseen topologies; cartoon or anime is not explicitly evaluated ([arXiv](https://arxiv.org/abs/2609.15746)) | One deformed GLB per AU (`--au-id jawOpen`, AU index 0–52, ICT/ARKit-style names) plus previews; Gradio UI ([README](https://github.com/TaatiTeam/TopoRig)). The paper covers 45 non-gaze controls of the 53-control ICT vocabulary ([arXiv](https://arxiv.org/abs/2609.15746)) | **TopoRig Academic Use License 1.0: non-commercial only**. "Commercial use is not permitted… internal commercial research or development" ([LICENSE](https://github.com/TaatiTeam/TopoRig)) | 7★, push 2026-09-20 (new) | Python 3.11 + PyTorch 2.7, CUDA 12.8 or CPU, Linux x86_64. Uses `bpy` and `blender --background` ([README](https://github.com/TaatiTeam/TopoRig)) |
| **NFR: Neural Face Rigging** (SIGGRAPH 2023) ([repo](https://github.com/dafei-qin/NFR_pytorch)) | Transfers facial animation to "any customized face mesh, even with different topology". DiffusionNet-style surface network with FACS-like codes from the ICT blendshape space (code index 0–52) ([README](https://github.com/dafei-qin/NFR_pytorch)) | Target mesh must have "no mouth/eye/nose sockets and eye balls"; mouth and eyes must be cut; rough alignment in the provided `align.blend` ([README](https://github.com/dafei-qin/NFR_pytorch)) | Yes; it deforms the target's own vertices | Topology-agnostic, but trained on human data (ICT + Multiface) ([README](https://github.com/dafei-qin/NFR_pytorch)) | Deformed meshes driven by 53 FACS-like codes; interactive vedo viewer | Code MIT. Pretrained data comes from ICT-FaceKit (MIT) and Multiface, which is **CC-BY-NC 4.0** ([Multiface](https://github.com/facebookresearch/multiface)). Sample pack on HF "derived from ICT-FaceKit" ([HF](https://huggingface.co/datasets/HKU-CGVU/NFR-sample-data)) | 98★, push 2026-08-03 | Tested on Ubuntu 20.04 + RTX 4090. "Windows is currently not supported unless you manually install pytorch3d". The test script needs a display (vedo) ([README](https://github.com/dafei-qin/NFR_pytorch)) |
| **vasiliskatr/deformation_transfer_ARkit_blendshapes** ([repo](https://github.com/vasiliskatr/deformation_transfer_ARkit_blendshapes)) | Sumner–Popović deformation transfer applied to "generating all the ARkit facial blend shapes for any 3D face" | Source ARKit set + target neutral **already NRICP-fitted**. The author used commercial Wrap3D for that step ([README](https://github.com/vasiliskatr/deformation_transfer_ARkit_blendshapes)) | Yes; the target topology is kept | Only as good as the correspondence | Meshes (numpy/plotly) | MIT. The bundled source ARKit meshes (Kite & Lightning) and target (ICT) are "only for demonstration purposes" ([README](https://github.com/vasiliskatr/deformation_transfer_ARkit_blendshapes)) | 70★, push 2022-01-14 (**dormant**) | Pure Python (numpy, scipy, numba, pandas, plotly) |
| **vasiliskatr/example_based_facial_rigging_ARkit_blendshapes** ([repo](https://github.com/vasiliskatr/example_based_facial_rigging_ARkit_blendshapes)) | Example-Based Facial Rigging (Li et al. 2010): refines generic ARKit shapes using a few example poses of the target | Same-topology generic blendshapes plus a few target poses. Use the DT repo first if topology differs ([README](https://github.com/vasiliskatr/example_based_facial_rigging_ARkit_blendshapes)) | Yes | n/a | Meshes | MIT | 43★, push 2022-01-16 (**dormant**) | Python (numpy, scipy, numba, qpsolvers) |
| **OmniFaceRig-repro** ([repo](https://github.com/ChenyuHeee/OmniFaceRig-repro)) | Third-party reproduction: image → TRELLIS mesh → 53-joint skeleton + "52 ARKit blendshapes (sparse morph targets, delta-field smoothed)" + teeth/gums/tongue from ICT assets. Vendors ICT-FaceKit and the vasiliskatr code ([README](https://github.com/ChenyuHeee/OmniFaceRig-repro)) | 2D image or T-pose GLB | Works on the generated mesh | Tested on 23 "official T-pose avatars" | Rigged GLB | **No license** (vendored parts keep their own) | 4★, push 2026-08-26 | Python server scripts |
| **mdj128/facial-animation ("Tripo Face Rig")** ([repo](https://github.com/mdj128/facial-animation)) | Procedural face rig for generated (Tripo) heads: jaw/tongue/eye/brow bones "where the measured parts support them, procedural facial shape keys, a mouth cavity, and optional ARKit/VRChat drafts"; Rhubarb lipsync; Unity package. Self-described as "experimental artist-assisted"; "Mouth detection and facial weights need visual review per character" ([README](https://github.com/mdj128/facial-animation)) | Prepared `.blend` with a `head` mesh and named `upper_jaw`, `lower_jaw` and `tongue` objects | Its default keeps lip seams intact; `autorig.py` legacy mode can split the seam ([README](https://github.com/mdj128/facial-animation)) | Aimed at generated stylized heads; no measured quality numbers | .blend → FBX → Unity | MIT | 12★, push 2026-09-06 | Blender 5.1.1 CLI via PowerShell wrappers (`rig.ps1`); Codex/Claude skill included |
| **dwgx/blender-copilot** (MCP server) ([repo](https://github.com/dwgx/blender-copilot)) | `ft_create_arkit_shapes` (procedural/template/from_existing) and `ft_create_unified_expressions`. The "procedural" mode places spherical vertex-group regions at fixed proportions of the head bounding box (e.g. `r_eye = head_height * 0.06`) and applies displacement recipes ([face_tracking_tools.py](https://github.com/dwgx/blender-copilot)) | Any mesh; heuristic proportions | Yes (adds keys) | Crude for any non-average proportions | Shape keys | MIT | 7★, push 2026-09-30 | Driven through MCP against a running Blender |
| **arturwyroslak/mediapipe-arkit-automesh** ([repo](https://github.com/arturwyroslak/mediapipe-arkit-automesh)) | Claims "automatically add ARKit-compatible blendshapes", but `backend/blender_script.py` only adds **blank keys** plus a "DEMO… fake deformation to 'jawOpen'" (moves z<0 vertices by -0.05) ([source](https://github.com/arturwyroslak/mediapipe-arkit-automesh)) | GLB | — | — | GLB | No license | 3★, push 2026-02-17 | Headless Blender, but **non-functional stub** |
| arturwyroslak/face-to-blendshape-3d ([repo](https://github.com/arturwyroslak/face-to-blendshape-3d)) | Generates a *new* face model with 52 ARKit morphs from a photo (MediaPipe) | Photo | No (new mesh) | — | 3D model | MIT | 14★, push 2026-02-11 | — |
| digitalp/arkit-blendshape-tool ([repo](https://github.com/digitalp/arkit-blendshape-tool)) | Copies 52 ARKit + 15 Oculus visemes from a reference GLB avatar (e.g. Avaturn T2) to a target GLB by vertex correspondence with `--max-distance 0.15` / `--falloff-distance 0.08` ([README](https://github.com/digitalp/arkit-blendshape-tool)) | Reference avatar overlapping the target | Yes | Only for near-identical head shapes | GLB, CLI + web UI | No license | 1★, push 2026-04-07 | Python CLI |

Paper-only (no code found):
- **OmniFaceRig** (Meta Reality Labs, SIGGRAPH Asia / TOG 2026, arXiv 2606.08043) builds up to 155 FACS blendshapes plus a procedural inner mouth, with "no manual landmarks, user templates, or per-asset setup". It covers humans, humanoids and long- or short-muzzled animals, and fails on beaks, snouts and insects. The project page lists no code; the dataset is "Coming Soon" ([project page](https://omnifacerig.github.io)).
- **RigAnyFace** (NeurIPS 2025; Penn State + Roblox) builds a FACS blendshape rig for diverse topologies, including multiple disconnected components and "non-humanoid heads". It shows no code link ([arXiv 2511.18601](https://arxiv.org/abs/2511.18601), [project page](https://wenchao-m.github.io/RigAnyFace.github.io/)).
- **Fully Automatic Blendshape Generation for Stylized Characters** (Wang et al., IEEE VR 2023, SJTU). No code or release link was found in the PDF metadata ([PDF](https://sjtu-characterlab.github.io/files/Fully_Automatic_Blendshape_Generation_for_Stylized_Characters.pdf)).

#### (b) Deformation transfer (DT), example-based rigging and NRICP libraries

| Repo | Notes | License | Activity |
|---|---|---|---|
| [mickare/Deformation-Transfer-for-Triangle-Meshes](https://github.com/mickare/Deformation-Transfer-for-Triangle-Meshes) | Python ≥3.9. Includes the **correspondence step**: progressively "inflates" the source into the target with pinned markers and closest-point costs, then DT by Frobenius minimisation. Browser 3D views ([README](https://github.com/mickare/Deformation-Transfer-for-Triangle-Meshes)) | MIT | 215★, push 2021-07 (dormant) |
| [chand81/Deformation-Transfer](https://github.com/chand81/Deformation-Transfer) | "Transfer deformations from source mesh to target mesh, keeping the identity of target intact" | MIT | 126★, push 2014-11 (dormant) |
| [jerenchen/deformxfer](https://github.com/jerenchen/deformxfer) | C++ header-only DT | BSD-3-Clause | 51★, push 2021-11 (dormant) |
| [kyle-gh/DeformationTransfer](https://github.com/kyle-gh/DeformationTransfer) | C++ (CGAL, Eigen): correspondence-marker tool plus transfer tool | No license | 34★, push 2020-08 (dormant) |
| [kyle-gh/ExampleBasedFacialRigging](https://github.com/kyle-gh/ExampleBasedFacialRigging) | C++17 EBFR: "resulting blendshapes carry the source's controller semantics and maintain the identity of the target" ([README](https://github.com/kyle-gh/ExampleBasedFacialRigging)) | No license | 61★, push 2021-05 (dormant) |
| [jpl917/BlendshapeGeneration](https://github.com/jpl917/BlendshapeGeneration) | C++ EBFR (ceres, SuiteSparse, trimesh2) | No license | 88★, push 2021-04 (dormant) |
| [ziyeshanwai/python-deformation-transfer](https://github.com/ziyeshanwai/python-deformation-transfer) | Python DT | No license | 53★, push 2021-06 (dormant) |
| [Golevka/deformation-transfer](https://github.com/Golevka/deformation-transfer) | ANSI C DT | No license | 290★, push 2012-06 (dormant) |
| [fabyday/smooth-contact-aware-facial-blendshape-transfer](https://github.com/fabyday/smooth-contact-aware-facial-blendshape-transfer) | Unofficial implementation of the contact-aware blendshape transfer paper (DOI 10.1145/2491832.2491836) | MIT | 5★, push 2022-06 (dormant) |
| [gaolinorange/Automatic-Unpaired-Shape-Deformation-Transfer](https://github.com/gaolinorange/Automatic-Unpaired-Shape-Deformation-Transfer) | SIGGRAPH Asia 2018 neural unpaired deformation transfer | MIT (LICENSE text) | 253★, push 2021-04 (dormant) |
| [brianlaiii/VectorDisplacementTransfer](https://github.com/brianlaiii/VectorDisplacementTransfer) | "BlendShape delta transfer tool that preserves local vertex rotations" | Apache-2.0 | 32★, push 2025-03 |
| [AWACC2020/Blendshape-Transfer-for-Maya](https://github.com/AWACC2020/Blendshape-Transfer-for-Maya) | Maya, different topology | MIT | 15★, push 2022-09 |
| **trimesh** `registration.nricp_amberg` / `nricp_sumner` ([source](https://github.com/mikedh/trimesh)) | Non-rigid ICP (Amberg 2007 "Optimal Step", and Sumner). Drop-in replacement for the Wrap3D step in DT pipelines | MIT | 3,700★, active (2026-10-12) |
| [wuhaozhe/pytorch-nicp](https://github.com/wuhaozhe/pytorch-nicp) | GPU non-rigid ICP | MIT | 279★, push 2021-11 (dormant) |
| [charlienash/nricp](https://github.com/charlienash/nricp) | MATLAB NRICP | MIT | 209★, push 2018-04 (dormant) |

#### (c) Blender add-ons for ARKit / Perfect Sync (mostly "pose a rig → bake")

| Add-on | What it really does | License | Activity | Headless |
|---|---|---|---|---|
| **CaptureForge / FaceForge** ([repo](https://github.com/H0wZy/captureforge)) | **Auto rig fit**: renders the head, finds MediaPipe landmarks, places a lean face rig (jaw, eyes, lids, brows, mouth, cheeks, tongue) with automatic weights, or fits a Rigify face metarig. Then you pose each ARKit marker and it bakes `evaluated(pose) − evaluated(neutral)` per mesh. Smooth L/R split, quality inspector (flipped normals, crushed triangles, symmetry), review sheet, video/webcam mocap. Notes that "stylized heads sometimes need" manual help when MediaPipe finds no face ([README](https://github.com/H0wZy/captureforge)) | GPL-3.0-or-later | 1★, push 2026-10-06 (new) | Yes: "Every feature is a plain Python function… run it with `blender --background`" |
| [tsikerdekis/ARKit-Creator-Blender-Addon](https://github.com/tsikerdekis/ARKit-Creator-Blender-Addon) | Guided pose-and-bake for Rigify / AutoRig Pro rigs, with reference images per shape | MIT | 13★, push 2025-08 | GUI-oriented |
| [elijah-atkins/ARKitBlendshapeHelper](https://github.com/elijah-atkins/ARKitBlendshapeHelper) | Requires an existing face rig; you pose 52 ARKit expressions on frames 1–52, then it bakes them to a duplicate ([README](https://github.com/elijah-atkins/ARKitBlendshapeHelper)) | No license | 94★, push 2025-08 | GUI |
| [harlynkingm/ARKit-Pose-Recorder-for-Blender](https://github.com/harlynkingm/ARKit-Pose-Recorder-for-Blender) | Pose face bones → 52 ARKit keys | Apache-2.0 | 0★, push 2026-07 | — |
| Angelus ARKit Helper ([extensions.blender.org](https://extensions.blender.org/add-ons/arkit-blendshape-tools/)) | "Add ARKit" adds 52 + 18 unmirrored keys, mirror split, driver linking. The page does not say whether the keys are sculpted | GPL-3.0+ | v0.7.5, Mar 2026 | — |
| LZ Shape Key Generator ([git.gay](https://git.gay/lunazera/Blender-Generate-Shapekeys)) | Adds **blank** 52 ARKit keys | GPL-3 | — | — |
| [PaoloESAN/gacha-setup](https://github.com/PaoloESAN/gacha-setup) | Blender 5.2+ automated rigging and **facial rigs for specific gacha-game models** (credited face-rig authors per game) | GPL-3.0 | 21★, push 2026-10-13 | — |
| [jpbouza/BlenRig](https://github.com/jpbouza/BlenRig) | Full rig system including a face, with guided "Rigging Assistant" and a shape-key sculpting workflow | GPL-3.0 | 174★, push 2026-09-14 | Assistant is GUI |
| [cgtinker/BlendArMocap](https://github.com/cgtinker/BlendArMocap) | MediaPipe tracking that *drives* a Rigify rig; creates no shapes | GPL-3.0 | 1,087★, push 2025-12 | — |
| CATS ([original](https://github.com/absolute-quantum/cats-blender-plugin)) | VRChat import/optimise, "Pose to Shape Key", decimation that keeps shape keys. No ARKit generation in the README | MIT | 4,110★, push 2024-05 (**abandoned**). Continuation [teamneoneko/Cats-Blender-Plugin](https://github.com/teamneoneko/Cats-Blender-Plugin) (GPL-3) and [Avatar-Toolkit](https://github.com/teamneoneko/Avatar-Toolkit) are both **archived** | — |
| [saturday06/VRM-Addon-for-Blender](https://github.com/saturday06/VRM-Addon-for-Blender) | VRM import/export and utilities for Blender 2.93–5.2. Needed for the Perfect Sync / VRM expression mapping; it does not generate shapes | MIT | 1,725★, push 2026-10-12 | Used headless by blender-vrm-perfect-sync |
| Paid or closed, for reference only: ShapeKeyGen (Gumroad/Superhive, from $15, seller claims all 52 for ARP/Rigify/custom rigs) ([Superhive](https://superhivemarket.com/products/shapekeygen)); YAARKitHelper (Booth, price shown ¥0) ([Booth](https://booth.pm/en/items/8433374)); ARKit Toolset (itch) ([itch](https://andy-hellgrim.itch.io/arkit-toolset)); Shapekeys Extended ($8, blank face-tracking sets incl. Unified Expressions) ([docs](https://superhivemarket.com/products/shapekeys-extended/docs)); **HANA_Tool** v5 (Booth ¥1,500, bundles hinzka's VRoid Perfect Sync data, VRoid only) ([Booth](https://booth.pm/en/items/4607357)) | | | | |

VRChat side: [Adjerry91/VRCFaceTracking-Templates](https://github.com/Adjerry91/VRCFaceTracking-Templates) (MIT, 293★) is a Unity animator template. It *requires* an avatar that already has SRanipal, ARKit or Unified Expressions blendshapes ([README](https://github.com/Adjerry91/VRCFaceTracking-Templates)). [usagi/un-vrc-perfectsync](https://github.com/usagi/un-vrc-perfectsync) (MIT, Unity) checks and creates the 52 from an avatar's *existing* blendshapes.

#### (d) Shape-key transfer add-ons (move shapes from a fitted template onto your mesh)

| Repo | Method | License | Activity |
|---|---|---|---|
| [MykytaPetrenko/ShapeKeyWrap](https://github.com/MykytaPetrenko/ShapeKeyWrap) | Wraps the **Surface Deform** modifier (bind noise, corrective smooth, delete-empty). Fails on edges with 3+ linked faces or concave faces ([README](https://github.com/MykytaPetrenko/ShapeKeyWrap)) | GPL-3.0 | 116★, push 2026-09-04 |
| [fblah/ShapeKeyTransferBlender](https://github.com/fblah/ShapeKeyTransferBlender) | Overlap the meshes at the origin, then transfer; written for ManuelBastioniLab → other meshes; Blender 2.93 ([README](https://github.com/fblah/ShapeKeyTransferBlender)) | GPL-3.0 | 196★, push 2025-11 |
| [neongm/RinvosBlendshapeTransfer](https://github.com/neongm/RinvosBlendshapeTransfer) | Automates Surface Deform with pre-processing; "still requires cleanup after transfer in a lot of cases" ([README](https://github.com/neongm/RinvosBlendshapeTransfer)) | MIT | 15★, push 2025-07 |
| [elainyilanchen/blender-vrm-perfect-sync](https://github.com/elainyilanchen/blender-vrm-perfect-sync) | Batch-copies the 52 Perfect Sync shapes from a donor VRoid model **by vertex order** (hinzka approach). "Thin wrapper over headless Blender scripts" ([README](https://github.com/elainyilanchen/blender-vrm-perfect-sync)) | MIT code (sample donors have their own licence) | 4★, push 2026-07 |
| [DFKI-SignLanguage/Transfer-ShapeKeys-Via-UV-Blender-Addon](https://github.com/DFKI-SignLanguage/Transfer-ShapeKeys-Via-UV-Blender-Addon) | Vertex matching through compatible UV maps | MPL-2.0 | 6★, push 2024-01 |
| Mesh Data Transfer: [Furionk/mesh-data-transfer](https://github.com/Furionk/mesh-data-transfer) (GPL-3, 9★). **Caution:** org "Mesh-Data-Transfer-products/…-Download" (0★, created 2026-02) looks like a re-upload or download-bait repo; avoid it ([GitHub search](https://github.com/Mesh-Data-Transfer-products/Mesh-Data-Transfer-Blender-Download)) | | | |

#### (e) Neural / parametric-model (3DMM) approaches

| Project | Relevance | License | Activity |
|---|---|---|---|
| [USC-ICT/ICT-FaceKit](https://github.com/USC-ICT/ICT-FaceKit) | Realistic morphable face. **53 expression shapes with ARKit naming**, with `_L`/`_R` and browInnerUp/cheekPuff split per side ([README](https://github.com/USC-ICT/ICT-FaceKit)). The "Full face model" will use "a different USC specific license" | **MIT** (light model) | 765★, push 2020-12 (stable, not maintained) |
| FLAME family: [DECA](https://github.com/yfeng95/DECA), [EMOCA](https://github.com/radekd91/emoca) | Image → FLAME fit. Output is FLAME topology, so your mesh is **replaced** | "Software Copyright License for **non-commercial** scientific research purposes" (both LICENSE files) | 2,528★ / 861★; push 2023-07 / 2024-12 (dormant) |
| [georgeretsi/smirk](https://github.com/georgeretsi/smirk), [soubhiksanyal/FLAME_PyTorch](https://github.com/soubhiksanyal/FLAME_PyTorch), [Rubikplayer/flame-fitting](https://github.com/Rubikplayer/flame-fitting) | Code MIT / MIT / no license; all need the FLAME model file | — | push 2024-05 / 2023-05 / 2023-02 |
| FLAME model ([site](https://flame.is.tue.mpg.de/)) | 100 PCA expression components, not ARKit. "Released FLAME 2023 Open Model with the Open Source License (CC-BY-4.0)" (news 11/25); "previous versions are only available for non-commercial research purposes" ([site](https://flame.is.tue.mpg.de/)) | FLAME 2023 Open: CC-BY-4.0 | — |
| [PeizhiYan/mediapipe-blendshapes-to-flame](https://github.com/PeizhiYan/mediapipe-blendshapes-to-flame) | Maps MediaPipe's 52 scores → FLAME's 100 expression coefficients + jaw/eye pose ([README](https://github.com/PeizhiYan/mediapipe-blendshapes-to-flame)) | No license | 72★, push 2025-09 |
| [facebookresearch/MHR](https://github.com/facebookresearch/MHR) (Momentum Human Rig) | Body + face parametric model: "72 expression parameters… Artist-sculpted, sparse semantic blendshape weights that follow FACS", not ARKit; rig FBX with identity and expression blendshapes ([README](https://github.com/facebookresearch/MHR)) | **Apache-2.0** | 868★, push 2026-10-13 |
| [PeizhuoLi/neural-blend-shapes](https://github.com/PeizhuoLi/neural-blend-shapes) (Li et al., SIGGRAPH 2021) | **Body** articulation rigging + pose-dependent corrective blend shapes; no facial expressions | BSD-2-style | 703★, push 2021-08 (dormant) |
| [ThibaultGROUEIX/NeuralJacobianFields](https://github.com/ThibaultGROUEIX/NeuralJacobianFields) | Generic learned mesh mappings (deformation transfer capable) | Adobe Research License, **non-commercial** | 161★, push 2025-04 |
| [nmwsharp/diffusion-net](https://github.com/nmwsharp/diffusion-net) | Surface-learning backbone (used by NFR / RigAnyFace) | MIT | 506★, push 2022-08 |
| [google-ai-edge/mediapipe](https://github.com/google-ai-edge/mediapipe) | Face Landmarker gives 52 ARKit-style scores and landmarks. Useful for **auto landmarking** of a rendered head (as TopoRig and CaptureForge do), not for creating shapes | Apache-2.0 | 37k★, active |

#### (f) "Rig anything" models from 2024–2026: body skeletons only
A README grep for "facial / blendshape / expression" found no face-expression output in any of these:
- [zhan-xu/RigNet](https://github.com/zhan-xu/RigNet): GPL-3, 1,520★, push 2024-11.
- [Seed3D/MagicArticulate](https://github.com/Seed3D/MagicArticulate): Apache-2.0, 418★, push 2025-09.
- [VAST-AI-Research/UniRig](https://github.com/VAST-AI-Research/UniRig): MIT, 1,825★, push 2026-06. Skeleton + skinning, trained with Rig-XL / VRoid ([README](https://github.com/VAST-AI-Research/UniRig)).
- [Seed3D/Puppeteer](https://github.com/Seed3D/Puppeteer): Apache-2.0, 428★, push 2025-09.
- [jasongzy/Make-It-Animatable](https://github.com/jasongzy/Make-It-Animatable): MIT, 464★, push 2026-09.
- [c8241998/HumanRig](https://github.com/c8241998/HumanRig): MIT, 92★, push 2026-09.
- [Isabella98Liu/RigAnything](https://github.com/Isabella98Liu/RigAnything): **Adobe Research License (non-commercial)**, 164★, push 2025-10.
- "Anymate": no GitHub repo found by name search.

#### (g) NVIDIA Audio2Face-3D (open-sourced 2025)
- The hub repo ([NVIDIA/Audio2Face-3D](https://github.com/NVIDIA/Audio2Face-3D), 469★) links the pieces:
  - [SDK](https://github.com/NVIDIA/Audio2Face-3D-SDK): C++/CUDA, **MIT**, push 2025-08.
  - [Training Framework](https://github.com/NVIDIA/Audio2Face-3D-Training-Framework): **Apache-2.0**, push 2025-10.
  - [Maya-ACE](https://github.com/NVIDIA/Maya-ACE): **MIT**, push 2026-02.
  - UE5 plugin.
  - The NIM microservice is under the NVIDIA Software License ([hub README](https://github.com/NVIDIA/Audio2Face-3D)).
- Model v3.0: "governed by the NVIDIA Open Model License… ready for commercial/non-commercial use"; input is 16 kHz audio ([HF card](https://huggingface.co/nvidia/Audio2Face-3D-v3.0)).
- The Claire sample dataset has a restrictive sample-data licence ([HF](https://huggingface.co/datasets/Nvidia/Audio2Face-3D-Dataset-v1.0.0-claire)).
- **Audio2Face does not create blendshapes for a new mesh.**
  - The network outputs deltas on its own fixed actor mesh.
  - The blendshape solve needs *your* existing set "v ≈ v₀ + D·w" and "remains general for any blendshape model".
  - Its shipped ARKit-compatible model is for its own subjects.
  - The paper's template transfer assumes meshes that "share consistent topology" ([paper](https://arxiv.org/html/2508.16401v1)).
- Blender bridge: [BruzWJ/Audio2Face-blender-addon](https://github.com/BruzWJ/Audio2Face-blender-addon) (GPL-3, 7★, push 2026-09). QtMeshEditor also runs A2F-3D via ONNX to animate ARKit targets ([README](https://github.com/fernandotonon/QtMeshEditor)).

### Inferences
- In this catalogue, only DT-based tools and the neural vertex-displacement models (TopoRig, NFR) write deltas onto the *input* mesh's own vertices. That matches the project rule "keep the original mesh". FLAME/DECA/EMOCA fitting, OmniFaceRig (fitted face mesh fusion) and TopoRig's optional eye/mouth post-processing all change the geometry.
- Every DT-based option needs a good template↔target correspondence. The weak link in the vasiliskatr pipeline (Wrap3D) can be replaced by MIT `trimesh.registration.nricp_amberg` seeded with MediaPipe landmarks from a front render. That is essentially what QtMeshEditor implemented in C++.
- The pose-and-bake add-ons (CaptureForge, ARKit-Creator, ARKitBlendshapeHelper, Pose Recorder) are not "automatic". They shift the work from sculpting 52 shapes to posing 52 rig states. CaptureForge's auto rig fit plus a reusable pose library (bone-space poses saved once and re-applied) could make it semi-automatic for similar rigs.

### Gaps
- I did not run any of these tools, so quality on our four style heads (realistic f02, semi f06, cartoon f11, anime f09) is unverified.
- TopoRig's README AU list (0–52) and the paper's 45 non-gaze controls differ; the exact name list was not printed.
- NFR checkpoint licence: the Google Drive weights carry no separate licence statement. Their commercial status is unclear because part of the training data (Multiface) is CC-BY-NC.
- QtMeshEditor's facerig quality metrics and its exact template asset/version could not be checked without building it.
- "Anymate" and RigAnyFace code were not found; OmniFaceRig code is not announced.

---

## Q2. Is there any open-source tool that takes ANY head mesh (cartoon, anime, monster) and outputs ARKit 52 shape keys on the original mesh automatically?

### Takeaway
No. Nothing verified as of 2026-10-13 does this for *any* style while also being commercially licensed. The closest options are:
- **QtMeshEditor `qtmesh facerig`**: MIT, automatic, humanoid only "by construction".
- **TopoRig**: automatic neural, topology-agnostic, ICT/ARKit-style AUs, keeps topology, but **academic non-commercial** only.
- **NFR**: MIT code, but needs mesh preparation and its weights were partly trained on non-commercial data.

Systems that claim non-humanoid coverage (OmniFaceRig, RigAnyFace) have released no code.

### Cited Findings
- QtMeshEditor states that deformation transfer from a human ARKit template "only makes sense for roughly human/humanoid face meshes. A prop, quadruped, or non-face mesh yields garbage", and lists creature face rigs as out of scope ([#889](https://github.com/fernandotonon/QtMeshEditor/issues/889)). The CLI `qtmesh facerig head.glb -o rigged.glb` is documented as shipped: "fit ARKit template + transfer 52 shapes" ([README](https://github.com/fernandotonon/QtMeshEditor)).
- TopoRig takes a neutral GLB/FBX, auto-aligns it with the ICT reference via MediaPipe landmarks in Blender, and generates per-AU expressions ([README](https://github.com/TaatiTeam/TopoRig)). It is evaluated on "unseen mesh topologies" but does not specifically address cartoon styles ([arXiv](https://arxiv.org/abs/2609.15746)). Its licence bans commercial use ([LICENSE](https://github.com/TaatiTeam/TopoRig)).
- NFR: "can transfer facial animations to any customized face mesh, even with different topology". It requires no inner sockets or eyeballs, cut mouth and eyes, and manual rough alignment ([README](https://github.com/dafei-qin/NFR_pytorch)).
- OmniFaceRig handles humans, humanoids and muzzled animals and fails on beaks, snouts and insects. It has no code link and its dataset is "Coming Soon" ([project page](https://omnifacerig.github.io)).
- RigAnyFace shows "non-humanoid characters with multiple disconnected components", with no code link ([project page](https://wenchao-m.github.io/RigAnyFace.github.io/)).
- For anime specifically, the only automatic route found is **VRoid-only vertex-order copying** of hinzka's Perfect Sync shapes ([blender-vrm-perfect-sync](https://github.com/elainyilanchen/blender-vrm-perfect-sync), [hinzka](https://github.com/hinzka/52blendshapes-for-VRoid-face)). It requires the exact VRoid base topology.
- The tools marketed as "automatic ARKit generation" in Blender are either blank-key generators ([LZ](https://git.gay/lunazera/Blender-Generate-Shapekeys), [Angelus](https://extensions.blender.org/add-ons/arkit-blendshape-tools/)), stubs ([mediapipe-arkit-automesh](https://github.com/arturwyroslak/mediapipe-arkit-automesh)), bounding-box heuristics ([blender-copilot](https://github.com/dwgx/blender-copilot)), or rig-pose bakers ([CaptureForge](https://github.com/H0wZy/captureforge), [ARKit-Creator](https://github.com/tsikerdekis/ARKit-Creator-Blender-Addon), [ARKitBlendshapeHelper](https://github.com/elijah-atkins/ARKitBlendshapeHelper)).

### Inferences
- For stylized heads, the most promising permissive route is **per-style templates + correspondence + DT**:
  - ICT-FaceKit (MIT) for realistic and semi-realistic heads.
  - hinzka's VRoid Perfect Sync (free commercial use) for anime.
  - A self-made template for cartoon heads.
  - Fit with landmark-seeded NRICP (trimesh, MIT), then DT (vasiliskatr / mickare, MIT) into shape keys on the original mesh.
  - TopoRig is useful as a *research baseline or QA reference*, not for shipping.
- Monster or non-human heads have no open-source automatic path today. Expect manual or semi-manual rigs (CaptureForge auto-fit + pose baking) or a dedicated template per creature family, mirroring OmniFaceRig's "topology-specific templates" idea.

### Gaps
- No open-source cartoon-style ARKit 52 template under a permissive licence was found.
- No benchmark compares QtMeshEditor, TopoRig and NFR on the same stylized heads.

---

## Q3. Which ones are commercially usable (licence)?

### Takeaway
- **Permissive and commercially usable:**
  - Code: QtMeshEditor (MIT), the vasiliskatr DT/EBFR repos (MIT), mickare (MIT), chand81 (MIT), deformxfer (BSD-3), trimesh NRICP (MIT), pytorch-nicp (MIT), NFR *code* (MIT).
  - Templates/models: ICT-FaceKit light model (MIT), Microsoft Rocketbox (MIT), MHR (Apache-2.0), FLAME 2023 Open (CC-BY-4.0, not ARKit).
  - Audio2Face-3D: SDK (MIT), training framework (Apache-2.0), models (NVIDIA Open Model License, commercial OK).
  - Blender tools: ARKit-Creator (MIT), Pose Recorder (Apache), Tripo Face Rig (MIT), blender-vrm-perfect-sync code (MIT), RinvosBlendshapeTransfer (MIT).
- **GPL** (usable to *produce* assets; copyleft only if you redistribute the code): CaptureForge, ShapeKeyWrap, fblah transfer, Angelus helper, BlenRig, RigNet.
- **Non-commercial:** TopoRig, DECA, EMOCA, older FLAME, NeuralJacobianFields, RigAnything, Multiface data.
- **No licence** (all rights reserved): elijah-atkins helper, kyle-gh, jpl917, ziyeshanwai, Golevka, digitalp tool, OmniFaceRig-repro, Headbox, mediapipe-to-flame.

### Cited Findings
- TopoRig: "Commercial use is not permitted under this license. This includes… internal commercial research or development" ([LICENSE](https://github.com/TaatiTeam/TopoRig)).
- DECA and EMOCA: "Software Copyright License for non-commercial scientific research purposes" ([DECA](https://github.com/yfeng95/DECA), [EMOCA](https://github.com/radekd91/emoca)).
- FLAME: the 2023 Open model is CC-BY-4.0; earlier versions are non-commercial only ([FLAME](https://flame.is.tue.mpg.de/)).
- RigAnything and NeuralJacobianFields: Adobe Research License, "noncommercial research purposes" only ([RigAnything](https://github.com/Isabella98Liu/RigAnything), [NJF](https://github.com/ThibaultGROUEIX/NeuralJacobianFields)).
- Multiface (part of NFR's training data): "CC-BY-NC 4.0 licensed" ([Multiface](https://github.com/facebookresearch/multiface)).
- ICT-FaceKit: "released under the MIT license"; the full model will use a different USC-specific licence ([ICT](https://github.com/USC-ICT/ICT-FaceKit)).
- Microsoft Rocketbox: "Updated license to MIT" (12/2020); "Release of ARkit compatible blendshapes" (6/2022); avatars with "15 visemes, 48 FACS, 30 for the Vive facial tracker" (2/2022). The repo is archived ([Rocketbox](https://github.com/microsoft/Microsoft-Rocketbox)). The Headbox transfer tool ([openVRlab/Headbox](https://github.com/openVRlab/Headbox), 54★, push 2022-10) has no licence file.
- hinzka/52blendshapes-for-VRoid-face: README grants free personal **and commercial** use, redistribution and sale of VRM files or modified data, with no credit required. It adds that third-party rights and service/software terms still apply. GitHub shows no LICENSE file ([README](https://github.com/hinzka/52blendshapes-for-VRoid-face)).
- VRoid base models: only certain old alpha-era VRoid models are CC0; AvatarSample A–C have more restrictive terms ([OpenGameArt archive](https://opengameart.org/content/vroid-studio-cc0-models)). [Cappyadams/VRoid-Blendshape-Models](https://github.com/Cappyadams/VRoid-Blendshape-Models) is CC0 but does not yet contain an ARKit set (README).
- Audio2Face-3D v3.0 model: "governed by the NVIDIA Open Model License… ready for commercial/non-commercial use" ([HF](https://huggingface.co/nvidia/Audio2Face-3D-v3.0)). Code licences per [hub README](https://github.com/NVIDIA/Audio2Face-3D).
- MHR: "licensed under the Apache Software License 2.0" ([MHR](https://github.com/facebookresearch/MHR)).
- The vasiliskatr repos are MIT, but their demo source ARKit meshes (Kite & Lightning) are "only for demonstration purposes" ([DT README](https://github.com/vasiliskatr/deformation_transfer_ARkit_blendshapes)). A shipping pipeline must swap in a licensed source set such as ICT-FaceKit, which QtMeshEditor did ([#889](https://github.com/fernandotonon/QtMeshEditor/issues/889)).

### Inferences
- Under GPL-3, a Blender add-on that runs inside our own asset pipeline does not impose GPL on the shape keys or meshes it produces. Only redistributing the add-on code (e.g. inside a game installer) would trigger copyleft. This is a general reading of GPL, not legal advice.
- The safest commercial stack is ICT-FaceKit (MIT) + trimesh NRICP (MIT) + an MIT DT implementation, run in our own scripts, plus the hinzka VRoid data (README grant) for an anime template, and Audio2Face-3D for speech-driven weights.

### Gaps
- hinzka's model is derived from VRoid Studio's sample models. Whether pixiv's terms for those base meshes restrict reuse of the *shape deltas* on non-VRoid meshes was not verified.
- The ShapeKeyGen and YAARKitHelper licences (paid or closed) were not checked.

---

## Q4. Which could plug into a headless Blender (or plain Python) pipeline?

### Takeaway
- **Explicitly headless-Blender:** CaptureForge core modules, blender-vrm-perfect-sync, Tripo Face Rig (Blender CLI wrappers), and TopoRig (`bpy` + `blender --background` for landmark mapping).
- **Plain Python, embeddable next to Blender:** the vasiliskatr DT/EBFR repos, mickare DT, trimesh NRICP, and NFR/TopoRig inference (needs CUDA/Linux).
- **Subprocess CLI:** QtMeshEditor `qtmesh facerig`.
- GUI-only or MCP-driven: ARKitBlendshapeHelper, ARKit-Creator, blender-copilot (needs a running Blender + MCP).

### Cited Findings
- CaptureForge: "Every feature is a plain Python function that takes explicit objects, so scripts and AI agents can run it with `blender --background`". Example: `markers.create_markers(scene, presets.ARKIT_SYMMETRIC)` ([README](https://github.com/H0wZy/captureforge)).
- blender-vrm-perfect-sync: "Everything the GUI does is a thin wrapper over headless Blender scripts you can run yourself" ([README](https://github.com/elainyilanchen/blender-vrm-perfect-sync)).
- Tripo Face Rig: `.\rig.ps1 .\work\character\source.blend` produces `source_rig.blend` plus a JSON report. "Core scripts run in Blender's Python"; tested on Blender 5.1.1 ([README](https://github.com/mdj128/facial-animation)).
- TopoRig needs the Blender executable for automatic landmark mapping (`blender --background --factory-startup`) and Python 3.11 with Linux x86_64 as the stated target ([README](https://github.com/TaatiTeam/TopoRig)).
- NFR officially supports only Ubuntu; Windows needs a manual pytorch3d build; its test script needs a display for vedo ([README](https://github.com/dafei-qin/NFR_pytorch)).
- vasiliskatr DT dependencies: numpy, scipy, numba, pandas, plotly ([README](https://github.com/vasiliskatr/deformation_transfer_ARkit_blendshapes)). mickare DT needs Python ≥3.9 with requirements.txt ([README](https://github.com/mickare/Deformation-Transfer-for-Triangle-Meshes)).
- trimesh exposes `nricp_amberg` and `nricp_sumner` in `trimesh/registration.py` ([trimesh](https://github.com/mikedh/trimesh)).
- QtMeshEditor's FaceRig core is described as "pure-data… Ogre-free and headless-unit-tested", with CLI `qtmesh facerig <head> -o <out.glb> [--template ict|<file>] [--only …] [--json]` ([#889](https://github.com/fernandotonon/QtMeshEditor/issues/889)).
- blender-copilot's ARKit tools run through an MCP server sending code to Blender ([repo](https://github.com/dwgx/blender-copilot)).

### Inferences
- A Windows-friendly, headless and fully permissive pipeline that fits the project's `tools/face_auto` would work like this:
  1. Render the front view in Blender `--background`.
  2. Get MediaPipe landmarks (Apache-2.0).
  3. Run trimesh NRICP to fit the style template (ICT / VRoid / own cartoon) onto the original head.
  4. Run DT (port vasiliskatr/mickare, MIT) to produce 52 deltas on the original vertices.
  5. Write the shape keys via `bpy`.
  6. Use the CaptureForge-style quality inspector ideas (flipped or crushed triangles, symmetry) for QA.
- The neural options (TopoRig, NFR) are Linux/CUDA-oriented, so on this Windows PC they would need WSL2 or a cloud VM. They are best kept as offline comparison baselines.

### Gaps
- Whether numba (used by the vasiliskatr code) installs cleanly into Blender's bundled Python on Windows was not tested.
- QtMeshEditor's Windows CLI build availability and how it handles OBJ/FBX input versus GLB-only were not verified.
- CaptureForge has 1★ and is brand new (2026); its robustness is unknown.
