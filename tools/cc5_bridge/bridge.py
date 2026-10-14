"""CC5 file bridge: lets an external agent run RLPy scripts inside Character Creator 5.

Started with  CharacterCreator.exe -RunPython <this file>  (or Script > Load Python).
Every 0.5 s it looks for *.py in <root>/inbox, executes each one in CC5's main thread with RLPy / RLPy2 available,
and writes <root>/outbox/<name>.log (stdout + stderr + traceback) and <root>/outbox/<name>.done (ok | error).
Local files only; nothing listens on the network.  <root>/heartbeat.txt is updated while the bridge runs.
"""
import os, sys, io, time, traceback, builtins, shutil
import RLPy
try:
    import RLPy2
except Exception:
    RLPy2 = None
from PySide2.QtCore import QTimer

ROOT = os.environ.get("CC5_BRIDGE_ROOT", r"C:\lsm26\triphthonS1\.cc5_bridge")
INBOX, OUTBOX, DONE = (os.path.join(ROOT, d) for d in ("inbox", "outbox", "processed"))
for d in (INBOX, OUTBOX, DONE):
    os.makedirs(d, exist_ok=True)
STATE = {"ns": {"RLPy": RLPy, "RLPy2": RLPy2, "__name__": "__cc5_bridge__"}}


def _tick():
    try:
        with open(os.path.join(ROOT, "heartbeat.txt"), "w") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S"))
        for name in sorted(os.listdir(INBOX)):
            if not name.endswith(".py"):
                continue
            src = os.path.join(INBOX, name)
            code = open(src, encoding="utf-8").read()
            shutil.move(src, os.path.join(DONE, name))
            buf = io.StringIO(); old = sys.stdout, sys.stderr; sys.stdout = sys.stderr = buf
            status = "ok"
            t0 = time.time()
            try:
                exec(compile(code, name, "exec"), STATE["ns"])
            except Exception:
                traceback.print_exc(); status = "error"
            finally:
                sys.stdout, sys.stderr = old
            stem = os.path.splitext(name)[0]
            with open(os.path.join(OUTBOX, stem + ".log"), "w", encoding="utf-8") as f:
                f.write(buf.getvalue())
            with open(os.path.join(OUTBOX, stem + ".done"), "w") as f:
                f.write(f"{status} {time.time() - t0:.2f}s")
    except Exception:
        with open(os.path.join(ROOT, "bridge_error.txt"), "a") as f:
            f.write(traceback.format_exc())


if not getattr(builtins, "_cc5_bridge_timer", None):
    t = QTimer(); t.timeout.connect(_tick); t.start(500)
    builtins._cc5_bridge_timer = t
    print("CC5 bridge running, root:", ROOT)
