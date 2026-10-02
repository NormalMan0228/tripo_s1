"""Read-only final check of the private review store; emit counts, never accounts."""
import json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.asset_vm import exercise_extended
from server.stored_assets import read_glb
from server.provider import validate_glb

data=ROOT/'artifacts/studio-review-data'
result={'assets':0,'parts':0,'tripo_assets':0,'bytes':0,'failures':[]}
with sqlite3.connect((data/'world.sqlite3').as_uri()+'?mode=ro',uri=True) as database:
    rows=database.execute('SELECT manifest FROM studio_assets').fetchall()
    for index,(raw,) in enumerate(rows):
        manifest=json.loads(raw)
        try:
            exercise_extended(manifest['program'],{p['id'] for p in manifest['plan']['parts']})
            for part in manifest['plan']['parts']:
                blob=read_glb(data/'assets',part['file'],part['sha256'])
                validate_glb(blob,allow_textures=manifest['provenance'].get('material')=='textured')
                result['parts']+=1;result['bytes']+=len(blob)
            result['assets']+=1
            result['tripo_assets']+=manifest['provenance'].get('geometry')=='tripo'
        except Exception as error:
            result['failures'].append({'row':index,'error_type':type(error).__name__})
(ROOT/'artifacts/review-assets-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result));raise SystemExit(bool(result['failures']))
