"""Operator import into isolated review inventory, transactionally; no provider calls."""
import hashlib,json,sqlite3,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.asset_vm import AssetVM,exercise_extended
from server.stored_assets import read_glb
from server.provider import validate_glb
SOURCE=ROOT/'artifacts/picture-furniture-20261002'
DEST=ROOT/'artifacts/studio-review-data'
added=[]
with sqlite3.connect(DEST/'world.sqlite3',timeout=30) as conn:
    conn.execute('PRAGMA foreign_keys=ON');conn.execute('BEGIN IMMEDIATE')
    user=conn.execute('SELECT id FROM users WHERE username=?',('workshop',)).fetchone()[0]
    for kind in ('static','dynamic'):
        aid='picture-20261002-'+kind
        if conn.execute('SELECT 1 FROM assets WHERE id=?',(aid,)).fetchone():continue
        value=json.loads((SOURCE/kind/'assembly.json').read_text());value.pop('runtime',None);value.pop('original_plan',None);value.pop('object_version',None)
        value['plan']['title']='그림 입력 · '+('정적 상자' if kind=='static' else '열리는 상자')
        exercise_extended(value['program'],{p['id'] for p in value['plan']['parts']})
        for part in value['plan']['parts']:
            blob=read_glb(SOURCE/'server-data/assets',part['file'],part['sha256']);validate_glb(blob,allow_textures=True)
            filename=aid+'-'+part['id']+'.glb';path=DEST/'assets'/filename
            if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()!=part['sha256']:raise RuntimeError('import_file_conflict')
            if not path.exists():path.write_bytes(blob)
            part['file']=filename
        first=value['plan']['parts'][0];oid=str(uuid.uuid4())
        conn.execute('INSERT INTO assets VALUES (?,?,?,?)',(aid,first['file'],first['sha256'],'studio'))
        conn.execute('INSERT INTO studio_assets VALUES (?,?)',(aid,json.dumps(value)))
        conn.execute("INSERT INTO objects(id,owner_id,creator_id,asset_id,name,created,state) VALUES (?,?,?,?,?,1,'inventory')",(oid,user,user,aid,value['plan']['title']))
        vm=AssetVM(value['program'],[p['id'] for p in value['plan']['parts']]);vm.run('spawn')
        conn.execute('INSERT INTO studio_runtime(object_id,state) VALUES (?,?)',(oid,json.dumps(vm.state)))
        conn.execute('INSERT OR IGNORE INTO asset_categories VALUES (?,0)',(value['plan']['category'],))
        for name,definition in value['program']['functions'].items():
            encoded=json.dumps(definition,sort_keys=True,separators=(',',':'))
            conn.execute('INSERT INTO generated_apis VALUES (?,?,?,?)',(aid,name,encoded,hashlib.sha256(encoded.encode()).hexdigest()))
        added.append(kind)
print(json.dumps({'imported':added,'paid_api_calls':0}))
