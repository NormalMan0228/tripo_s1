"""diverse: render a take family from more candidates than it needs and keep only takes that differ.

    import diverse as D
    meta = D.diverse_family(out_dir, "snow_walk", 14, fn, sr=22050, ref_db=-15.0, seed_base="world")

fn(rng, k) renders candidate k (k = 0, 1, 2 ...) from a design grid (sfxlib.cycle) plus random
detail, exactly like sfxlib.make_family's fn. Every candidate goes through sfxlib.finish() and is
compared with the takes kept so far using sfx_qa's own similarity (both resolutions) and waveform
cross-correlation. A candidate is kept when it stays below `sim_max` / `xc_max` (a margin under
sfx_qa's 0.90 / 0.95 fail line) against every kept take; candidates are tried in order until `n`
are kept or `max_candidates` ran out (then the least similar rejects fill up and a warning is
printed). Kept takes are written as <event>_<start>.wav ... in the order they were kept, so a
re-run with the same code renders the same files. Like make_family, it refuses to overwrite a
protected file (sfxlib.protected), and it
applies make_family's A-weighted balance (sfxlib.aw_balance) to the kept takes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sfxlib as L  # noqa: E402
import sfx_qa as Q  # noqa: E402

SIM_MAX = 0.875
XC_MAX = 0.90


def pair_sim(fa, fb) -> float:
    """sfx_qa's near-identity score in both directions (the search warps only its second take, so
    the score is not symmetric; the QA compares in file order, either way round)."""
    return max(min(Q.similarity_parts(fa, fb).values()), min(Q.similarity_parts(fb, fa).values()))


def diverse_family(out_dir, event: str, n: int, fn, sr: int = L.DEFAULT_SR, ref_db: float | None = None,
                   seed_base: str = "", start: int = 1, max_candidates: int | None = None, sim_max: float = SIM_MAX,
                   xc_max: float = XC_MAX, finish_kw: dict | None = None, allow_overwrite: bool = False,
                   dry_run: bool = False, loop: bool = False, aw_balance_db: float | None = L.AW_BALANCE_DB) -> list:
    out_dir = Path(out_dir)
    targets = [out_dir / ("%s_%d.wav" % (event, i)) for i in range(int(start), int(start) + int(n))]
    L._guard(targets, allow_overwrite)
    max_candidates = max_candidates or max(3 * n, n + 12)
    kept, rejects = [], []
    for k in range(max_candidates):
        if len(kept) >= n:
            break
        seed = L.take_seed(event, k, seed_base)
        res = fn(np.random.default_rng(seed), k)
        notes = {}
        if isinstance(res, tuple):
            res, notes = res[0], dict(res[1]) if len(res) > 1 else {}
        y = L.finish(np.asarray(res, float), sr, ref_db=ref_db, loop=loop, **(finish_kw or {}))
        feat = Q.features(y, sr)
        worst, worst_xc, with_k = 0.0, 0.0, None
        for other in kept:
            s = pair_sim(feat, other["feat"])
            c = Q.xcorr(feat, other["feat"])
            if s > worst:
                worst, with_k = s, other["k"]
            worst_xc = max(worst_xc, c)
            if s >= sim_max or c >= xc_max:
                break
        cand = {"k": k, "seed": seed, "raw": np.asarray(res, float), "y": y, "feat": feat, "notes": notes,
                "worst": worst, "worst_xc": worst_xc, "with": with_k}
        if worst < sim_max and worst_xc < xc_max:
            kept.append(cand)
        else:
            rejects.append(cand)
    if len(kept) < n:
        print("diverse: warning: %s: only %d of %d candidates differ enough; filling with the least similar rejects"
              % (event, len(kept), n), file=sys.stderr)
        while len(kept) < n and rejects:
            for c in rejects:   # the true worst score against everything kept so far
                c["worst"] = max([pair_sim(c["feat"], o["feat"]) for o in kept] or [0.0])
            rejects.sort(key=lambda c: c["worst"])
            kept.append(rejects.pop(0))
    kept = kept[:n]
    if aw_balance_db is not None and ref_db is not None and not loop:
        # A-weighted level matching, as in make_family (sfxlib.aw_balance)
        kw = {k: v for k, v in (finish_kw or {}).items() if k != "loop"}
        ys, bal = L.aw_balance([c["raw"] for c in kept], [c["y"] for c in kept], sr, ref_db, kw,
                               L.sibling_levels(out_dir, event, targets), aw_balance_db)
        for c, y, b in zip(kept, ys, bal):
            if b:
                c["y"] = y
                c["notes"] = dict(c["notes"], **b)
    meta = []
    for path, c in zip(targets, kept):
        if not dry_run:
            L.write_wav(path, c["y"], sr)
        d = L._describe(path, c["y"], sr, ref_db)
        d.update({"event": event, "candidate": c["k"], "seed": c["seed"], "worst_sim": round(c["worst"], 3)}, **c["notes"])
        meta.append(d)
    return meta


def tried(meta: list) -> int:
    """Candidates rendered for a family (highest kept candidate index + 1)."""
    return 1 + max((d.get("candidate", 0) for d in meta), default=-1)
