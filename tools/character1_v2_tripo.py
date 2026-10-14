"""character1 face v2: Tripo generation / post-process jobs with a ledger capped by the user's authorization.

User authorization (2026-10-05): "트라이포 api 크레딧을 3천 허용합니다" — HD, Smart Mesh, part segmentation and
Blender, everything, to find the best face-rigging workflow. References: art/references/character1_v2_bald_clean
(neutral closed mouth, bald, brows/lashes/liner removed after the user's brow feedback).

Usage (run with .tools/art-venv python):
  character1_v2_tripo.py balance
  character1_v2_tripo.py submit <job>        # one paid task, never resubmitted automatically
  character1_v2_tripo.py poll <job> [--wait]  # status; downloads every output URL on success
  character1_v2_tripo.py ledger
"""
import argparse, asyncio, hashlib, json, re, sys, time
from pathlib import Path
R = Path(__file__).resolve().parents[1]; sys.path[:0] = [str(R), str(R / 'tools')]
import httpx
from urllib.parse import urlparse
from server.config import Settings, read_tripo_key
from server.provider import TripoProvider, ProviderError
from generate_dev_character import upload

CAP = 3000
LEDGER = R / 'artifacts/character1-face-v2/budget.json'
OUT = R / 'art/characters/character1_face_v2/tripo'
REF = R / 'art/references/character1_v2_bald_clean'
MV = [('front', '01_front.png'), ('left', '02_left.png'), ('back', '03_back.png'), ('right', '04_right.png')]
TEX_P2 = {'texture': True, 'pbr': True, 'export_uv': True, 'texture_quality': 'detailed', 'texture_version': 'v3.5-20260815',
          'delight': True, 'texture_alignment': 'original_image', 'orientation': 'align_image'}

REF_OPEN = R / 'art/references/character1_v2_openmouth'
SEG = 'art/characters/character1_face_v2/seg'
REF_HDFIX = R / 'art/references/character1_v2_bald_hdfix'          # side views: blurred brow patch rebuilt (fix_ref_brow_silhouette.py)
REF_OPEN_HDFIX = R / 'art/references/character1_v2_openmouth_hdfix'
HD_GEO = {'model': 'v3.1-20260211', 'geometry_quality': 'detailed', 'face_limit': 1000000, 'texture': False, 'pbr': False,
          'quad': False, 'smart_low_poly': False, 'generate_parts': False, 'export_uv': False, 'orientation': 'align_image'}
JOBS = {
    # HD geometry for the wrap-input head (2026-10-05): clean high-res surface; topology comes from the wrap tool later
    'hd_geo_closed_a': dict(route='/generation/multiview-to-model', refs=MV, ref_dir=REF_HDFIX, reserve=90,
                            payload={**HD_GEO, 'model_seed': 2026100581}),
    'hd_geo_closed_b': dict(route='/generation/multiview-to-model', refs=MV, ref_dir=REF_HDFIX, reserve=90,
                            payload={**HD_GEO, 'model_seed': 2026100582}),
    'hd_geo_open': dict(route='/generation/multiview-to-model', refs=MV, ref_dir=REF_OPEN_HDFIX, reserve=90,
                        payload={**HD_GEO, 'model_seed': 2026100583}),
    'segref_hdopen': dict(route='/mesh/segment', source='hd_geo_open', ref=f'{SEG}/open_mask_full.png', reserve=50,
                          payload={'model': 'v2.0-20260430'}),
    'p2_mv_open_geo': dict(route='/generation/multiview-to-model', refs=MV, ref_dir=REF_OPEN, reserve=130,
                           payload={'model': 'P2-20260801', 'quad': True, 'face_limit': 20000, 'texture': False,
                                    'pbr': False, 'export_uv': False, 'model_seed': 2026100571}),
    # generation candidates
    'p2_mv_tex': dict(route='/generation/multiview-to-model', refs=MV, reserve=150,
                      payload={'model': 'P2-20260801', 'quad': True, 'face_limit': 20000, **TEX_P2,
                               'model_seed': 2026100561, 'texture_seed': 2026100561}),
    'hd_mv_tex': dict(route='/generation/multiview-to-model', refs=MV, reserve=90,
                      payload={'model': 'v3.1-20260211', 'geometry_quality': 'detailed', 'face_limit': 1000000,
                               'texture': True, 'pbr': True, 'texture_quality': 'detailed', 'texture_version': 'v3.0-20250812',
                               'quad': False, 'smart_low_poly': False, 'generate_parts': False, 'export_uv': True,
                               'orientation': 'align_image', 'texture_alignment': 'original_image',
                               'model_seed': 2026100562, 'texture_seed': 2026100562}),
    'p2_mv_quad40k': dict(route='/generation/multiview-to-model', refs=MV, reserve=130,
                          payload={'model': 'P2-20260801', 'quad': True, 'face_limit': 40000, 'texture': False, 'pbr': False,
                                   'export_uv': True, 'model_seed': 2026100563}),
    'p2_front_tex': dict(route='/generation/image-to-model', refs=[('front', '01_front.png')], reserve=150,
                         payload={'model': 'P2-20260801', 'quad': True, 'face_limit': 20000, **TEX_P2,
                                  'model_seed': 2026100564, 'texture_seed': 2026100564}),
    'hd_mv_parts': dict(route='/generation/multiview-to-model', refs=MV, reserve=90,
                        payload={'model': 'v3.1-20260211', 'geometry_quality': 'detailed', 'face_limit': 500000,
                                 'texture': False, 'pbr': False, 'quad': False, 'smart_low_poly': False,
                                 'generate_parts': True, 'export_uv': False, 'model_seed': 2026100565}),
    # post-process on earlier tasks (input = task id of the named job)
    'seg_p2': dict(route='/mesh/segment', source='p2_mv_tex', reserve=60,
                   payload={'model': 'v2.0-20260430', 'segmentation_granularity': 'detailed', 'split_by_connectivity': True}),
    'seg_hd': dict(route='/mesh/segment', source='hd_mv_tex', reserve=60,
                   payload={'model': 'v2.0-20260430', 'segmentation_granularity': 'detailed', 'split_by_connectivity': True}),
    'retopo_p2_quad10k': dict(route='/mesh/decimate', glb='art/characters/character1_face_v2/p2_head_for_retopo.glb', reserve=40,
                              payload={'model': 'v2.0', 'face_limit': 10000, 'quad': True, 'bake': True}),
    'retopo_p2_quad_glb': dict(route='/mesh/decimate', glb='art/characters/character1_face_v2/p2_head_for_retopo.glb', reserve=40,
                               payload={'model': 'v2.0', 'face_limit': 12000, 'quad': True, 'bake': True}),
    'retopo_p2_quad': dict(route='/mesh/decimate', source='p2_mv_tex', reserve=40,
                           payload={'model': 'v2.0', 'face_limit': 12000, 'quad': True, 'bake': True}),
    'retopo_hd_quad': dict(route='/mesh/decimate', source='hd_mv_tex', reserve=40,
                           payload={'model': 'v2.0', 'face_limit': 12000, 'quad': True, 'bake': True}),
    # Segmentation v2 with a part-colour ref_image (2026-10-05 experiments). ref = image under the repo root.
    'segref_open_full': dict(route='/mesh/segment', source='p2_mv_open_geo', ref=f'{SEG}/open_mask_full.png', reserve=50,
                             payload={'model': 'v2.0-20260430'}),
    'segref_open_coarse': dict(route='/mesh/segment', source='p2_mv_open_geo', ref=f'{SEG}/open_mask_coarse.png', reserve=50,
                               payload={'model': 'v2.0-20260430'}),
    'segref_open_photo': dict(route='/mesh/segment', source='p2_mv_open_geo', ref='art/references/character1_v2_openmouth/01_front.png',
                              reserve=50, payload={'model': 'v2.0-20260430'}),
    'seg_open_detailed': dict(route='/mesh/segment', source='p2_mv_open_geo', reserve=50,
                              payload={'model': 'v2.0-20260430', 'segmentation_granularity': 'detailed', 'split_by_connectivity': True}),
    'segref_closed_full': dict(route='/mesh/segment', glb=f'{SEG}/closed_head.glb', ref=f'{SEG}/closed_mask_full.png', reserve=50,
                               payload={'model': 'v2.0-20260430'}),
    'segref_closed_photo': dict(route='/mesh/segment', glb=f'{SEG}/closed_head.glb', ref='art/references/character1_v2_bald_clean/01_front.png',
                                reserve=50, payload={'model': 'v2.0-20260430'}),
    'seg_closed_detailed': dict(route='/mesh/segment', glb=f'{SEG}/closed_head.glb', reserve=50,
                                payload={'model': 'v2.0-20260430', 'segmentation_granularity': 'detailed', 'split_by_connectivity': True}),
    'segref_cleanopen_full': dict(route='/mesh/segment', glb=f'{SEG}/clean_open_head.glb', ref=f'{SEG}/open_mask_full.png', reserve=50,
                                  payload={'model': 'v2.0-20260430'}),
    'segref_closed_rig': dict(route='/mesh/segment', glb=f'{SEG}/closed_head.glb', ref=f'{SEG}/closedrig_mask_rig.png', reserve=50,
                              payload={'model': 'v2.0-20260430'}),
    'segref_p2tex_closedmask': dict(route='/mesh/segment', source='p2_mv_tex', ref=f'{SEG}/closed_mask_full.png', reserve=50,
                                    payload={'model': 'v2.0-20260430'}),
}


def read(p, default=None):
    return json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else default


def save(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp'); tmp.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding='utf-8'); tmp.replace(p)


def ledger():
    d = read(LEDGER) or {'tripo_cap': CAP, 'authorization': '2026-10-05 user: "트라이포 api 크레딧을 3천 허용합니다"',
                         'references': {v: hashlib.sha256((REF / f).read_bytes()).hexdigest() for v, f in MV}, 'tasks': {}}
    return d


def committed(d):
    return sum(float(t.get('credits_consumed', t['reservation'])) for t in d['tasks'].values() if t.get('state') != 'refused')


async def download(url, dest_dir, stem):
    u = urlparse(url); host = u.hostname or ''
    if u.scheme != 'https' or not (host == 'tripo3d.ai' or host.endswith('.tripo3d.ai') or host.endswith('.tripo3d.com')):
        raise ProviderError('unsafe_asset_url')
    async with httpx.AsyncClient(timeout=180, follow_redirects=False) as c:
        r = await c.get(url)
    b = r.content
    if r.status_code != 200 or len(b) < 12:
        raise ProviderError('download_failed')
    ext = 'glb' if b[:4] == b'glTF' else 'fbx' if (b.startswith(b'Kaydara FBX Binary') or b[:200].lstrip().startswith(b'; FBX')) \
        else 'zip' if b[:4] == b'PK\x03\x04' else 'png' if b[:4] == b'\x89PNG' else 'jpg' if b[:2] == b'\xff\xd8' else 'webp' if b[8:12] == b'WEBP' else 'bin'
    p = dest_dir / f'{stem}.{ext}'; p.write_bytes(b)
    return p


async def run(op, job, wait):
    prov = TripoProvider(Settings(tripo_key=read_tripo_key(Path.home() / 'Desktop/tripo_key.txt')))
    if op == 'balance':
        print(json.dumps({'balance': await prov.balance()})); return
    d = ledger()
    if op == 'ledger':
        print(json.dumps({'cap': d['tripo_cap'], 'committed': committed(d),
                          'tasks': {k: {x: v.get(x) for x in ('state', 'reservation', 'credits_consumed', 'task_id')} for k, v in d['tasks'].items()}}, indent=1, ensure_ascii=False))
        return
    J = JOBS[job]; out = OUT / job; out.mkdir(parents=True, exist_ok=True)
    e = d['tasks'].get(job)
    if op == 'submit':
        if e:
            print(json.dumps({'status': 'exists_no_resubmit', 'task_id': e.get('task_id'), 'state': e.get('state')})); return
        if committed(d) + J['reserve'] > d['tripo_cap']:
            raise ProviderError('budget_exhausted')
        RD = J.get('ref_dir', REF)
        if RD == REF:
            for v, f in J.get('refs', []):
                if hashlib.sha256((REF / f).read_bytes()).hexdigest() != d['references'].get(v, hashlib.sha256((REF / f).read_bytes()).hexdigest()):
                    raise ProviderError('reference_changed_since_ledger')
        bal = await prov.balance()
        if bal < J['reserve']:
            raise ProviderError('insufficient_balance')
        payload = dict(J['payload'])
        if 'refs' in J:
            toks = [(v, await upload(prov, RD / f)) for v, f in J['refs']]
            if J['route'].endswith('multiview-to-model'):
                payload['inputs'] = [{v: t} for v, t in toks]
            else:
                payload['input'] = toks[0][1]
        elif 'glb' in J:
            blob = (R / J['glb']).read_bytes()
            async with httpx.AsyncClient(timeout=120, follow_redirects=False) as c:
                r = await c.post(prov.BASE + '/files', headers={'Authorization': 'Bearer ' + prov.settings.tripo_key},
                                 files={'file': (Path(J['glb']).name, blob, 'model/gltf-binary')})
            tok = r.json().get('data', {}).get('file_token')
            if not isinstance(tok, str):
                raise ProviderError('glb_upload_failed')
            payload['input'] = tok
        else:
            src = d['tasks'].get(J['source'], {})
            if src.get('state') != 'success':
                raise ProviderError('source_not_ready')
            payload['input'] = src['task_id']
        if 'ref' in J:
            payload['ref_image'] = await upload(prov, R / J['ref'])
        e = {'state': 'intent', 'reservation': J['reserve'], 'route': J['route'], 'created': time.time(), 'balance_before': bal,
             'references': {v: [str((RD / f).relative_to(R)), hashlib.sha256((RD / f).read_bytes()).hexdigest()] for v, f in J.get('refs', [])},
             'payload': {k: v for k, v in payload.items() if k not in ('input', 'inputs', 'ref_image')}, 'automatic_resubmit': False}
        if 'ref' in J:
            e['ref_image'] = [J['ref'], hashlib.sha256((R / J['ref']).read_bytes()).hexdigest()]
        if 'glb' in J:
            e['glb'] = [J['glb'], hashlib.sha256((R / J['glb']).read_bytes()).hexdigest()]
        d['tasks'][job] = e; save(LEDGER, d)
        res = await prov.request('POST', J['route'], payload)
        tid = res.get('task_id')
        if not isinstance(tid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,200}', tid):
            raise ProviderError('upstream_schema', uncertain=True)
        e.update(state='submitted', task_id=tid); save(LEDGER, d)
        print(json.dumps({'status': 'submitted', 'job': job, 'task_id': tid})); return
    # poll
    if not e or not e.get('task_id'):
        raise ProviderError('no_task')
    while True:
        t = await prov.task(e['task_id'])
        st = t.get('status')
        if st in ('success', 'failed', 'cancelled', 'banned', 'expired', 'unknown') or not wait:
            break
        print(json.dumps({'job': job, 'status': st, 'progress': t.get('progress')}), flush=True)
        await asyncio.sleep(15)
    info = {'job': job, 'task_id': e['task_id'], 'status': st, 'progress': t.get('progress'), 'credits_consumed': t.get('credits_consumed')}
    if st in ('success', 'failed', 'cancelled', 'banned', 'expired'):
        e['state'] = st
        if isinstance(t.get('credits_consumed'), (int, float)):
            e['credits_consumed'] = t['credits_consumed']
        save(LEDGER, d)
    if st == 'success':
        files = {}
        output = t.get('output') or {}
        for k, v in output.items():
            if isinstance(v, str) and v.startswith('https://'):
                files[k] = str((await download(v, out, k)).relative_to(R))
        info['files'] = files; info['output_keys'] = list(output.keys())
        save(out / 'result.json', {**info, 'task': {k: v for k, v in t.items() if k != 'output'}})
    info['committed'] = committed(d)
    print(json.dumps(info, ensure_ascii=False))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('op', choices=['balance', 'submit', 'poll', 'ledger'])
    ap.add_argument('job', nargs='?'); ap.add_argument('--wait', action='store_true')
    a = ap.parse_args()
    try:
        asyncio.run(run(a.op, a.job, a.wait))
    except Exception as ex:
        print(json.dumps({'error': ex.code if isinstance(ex, ProviderError) else f'{type(ex).__name__}: {ex}', 'automatic_resubmit': False}))
        sys.exit(1)
