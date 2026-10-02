"""Synthetic public fixture for measuring 5/15/30 active assemblies, no API calls."""
import base64,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.asset_assembly import demo_design,fixture_glb
plan,program=demo_design('flower')
value={'schema':1,'plan':plan,'program':program,'runtime':{},'provenance':{'geometry':'procedural_proxy'},
       'blobs':{p['id']:base64.b64encode(fixture_glb(p['shape'],False)).decode() for p in plan['parts']}}
(ROOT/'artifacts/furniture-stress.json').write_text(json.dumps(value),encoding='utf-8')
