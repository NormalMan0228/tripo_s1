"""Texture restore fixture. No model/API requests or original media modification."""
import base64,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.asset_assembly import demo_design,fixture_glb
rows=[]
for textured in [False,True]:
    plan,program=demo_design('chest')
    rows.append({'schema':1,'plan':plan,'program':program,'runtime':{},'provenance':{'geometry':'procedural_proxy'},
        'textured':textured,'blobs':{p['id']:base64.b64encode(fixture_glb(p['shape'],textured)).decode() for p in plan['parts']}})
(ROOT/'artifacts/material-cases.json').write_text(json.dumps(rows),encoding='utf-8')
