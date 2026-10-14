"""One-shot CC5 task (run by the user: CC5 > Script > Load Python). Not a bridge: it runs once and exits.

1. logs what the Headshot APIs offer (RLPy.RHeadshot, RLPy2.Headshot3) so the next steps can be scripted precisely
2. imports the clean head through Headshot mesh mode:
   RLPy.RHeadshot.ImportHeadFromObj(obj, Neutral body, subdivision level 2, automatic alignment, neutral neck)
3. saves the project, renders a preview image, tries an FBX export (the trial may limit exports - logged either way)
Everything is written to art/characters/character1_face_v2/hd/cc5/.
"""
import os, sys, time, traceback
import RLPy
try:
    import RLPy2
except Exception:
    RLPy2 = None

BASE = r"C:\lsm26\triphthonS1\art\characters\character1_face_v2\hd"
OBJ = os.path.join(BASE, "export", "character1_head_headshot.obj")
OUT = os.path.join(BASE, "cc5")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "run_headshot_mesh_log.txt"), "w", encoding="utf-8")


def log(*a):
    LOG.write(" ".join(str(x) for x in a) + "\n"); LOG.flush()


def step(name, fn):
    t0 = time.time()
    try:
        r = fn(); log(f"[ok] {name} ({time.time() - t0:.1f}s):", r); return r
    except Exception:
        log(f"[error] {name}:\n" + traceback.format_exc()); return None


log("CC5 headshot mesh run", time.strftime("%Y-%m-%d %H:%M:%S"), "python", sys.version.split()[0])
# 1. API inventory
step("RHeadshot methods", lambda: [m for m in dir(RLPy.RHeadshot) if not m.startswith("_")])
step("RHeadshot.ImportHeadFromObj doc", lambda: RLPy.RHeadshot.ImportHeadFromObj.__doc__)
if RLPy2 is not None:
    step("RLPy2 headshot-ish names", lambda: [a for a in dir(RLPy2) if "ead" in a or "HS" in a])
    hs = step("RLPy2.Headshot3.GetInterface", lambda: RLPy2.Headshot3.GetInterface())
    if hs is not None:
        step("Headshot3 interface methods", lambda: [m for m in dir(hs) if not m.startswith("_")])
        for m in [m for m in dir(hs) if not m.startswith("_")]:
            step(f"doc {m}", lambda m=m: getattr(getattr(hs, m), "__doc__", None))
# 2. mesh mode import
st = step("ImportHeadFromObj", lambda: RLPy.RHeadshot.ImportHeadFromObj(OBJ, RLPy.EHSBodyType_Neutral, RLPy.EHSLevel_Two, RLPy.IntVector(), True))
if st is not None:
    step("status code", lambda: (st.IsSuccess() if hasattr(st, "IsSuccess") else st))
avatars = step("avatars", lambda: RLPy.RScene.GetAvatars()) or []
step("avatar names", lambda: [a.GetName() for a in avatars])
if avatars:
    av = avatars[0]
    step("save ccProject", lambda: RLPy.RFileIO.SaveFile(av, RLPy.RSaveFileSetting(), os.path.join(OUT, "character1_headshot.ccProject")))
    step("render preview", lambda: RLPy.RGlobal.RenderImage(os.path.join(OUT, "character1_headshot_render.png")))
    step("export fbx", lambda: RLPy.RFileIO.ExportFbxFile(av, os.path.join(OUT, "character1_headshot.fbx"), RLPy.RExportFbxSetting()))
log("done")
LOG.close()
