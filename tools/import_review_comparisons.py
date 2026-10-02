"""Offline import of measured H3/reference artifacts into the isolated review account.
Run with the localhost review server stopped. No provider requests, no secret files.
"""
import copy,hashlib,json,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.app import create_app
from server.config import Settings
from server.asset_assembly import demo_design
from server.asset_vm import AssetVM,exercise
from server.provider import validate_glb

def main():
    folder=ROOT/'artifacts/studio-review-data'
    app=create_app(Settings(data_dir=folder),worker_enabled=False)
    candidates=[]
    for motion in ('static','dynamic'):
        for material in ('mesh','textured'):
            plan,program=demo_design('chest')
            if motion=='static':
                plan['parts']=plan['parts'][:1];plan['parts'][0].update(id='static',size=[1.2,.8,.8],position=[0,.4,0])
                program={'version':1,'state':{},'functions':{},'events':{}}
            blobs={};credits=0
            for part in plan['parts']:
                src=ROOT/'artifacts/furniture/h3-comparison'/(part['id']+'-'+material)
                blobs[part['id']]=(src/'model.glb').read_bytes()
                credits+=json.loads((src/'result.json').read_text())['credits_consumed']
                part['color']='#ffffff' if material=='textured' else '#d1af75'
            plan['title']='H3 '+('정적' if motion=='static' else '열리는')+' 상자 · '+('직접 색칠' if material=='mesh' else '텍스처')
            provenance={'provider':'authored_comparison_plan','geometry':'tripo','material':material,'motion':motion,'tripo_model':'v3.1-20260211','tripo_credits_consumed':credits,'validation':exercise(program,list(blobs))}
            candidates.append(('review-h3-'+motion+'-'+material,{'schema':1,'plan':plan,'program':program,'provenance':provenance},blobs))
    source=ROOT/'artifacts/reference-chain/assembly.json'
    if source.exists():
        value=json.loads(source.read_text());value.pop('runtime',None)
        source_assets=ROOT/'artifacts/reference-chain/server-data/assets'
        # Public assembly omits private filenames; match each content hash locally.
        by_hash={hashlib.sha256(p.read_bytes()).hexdigest():p for p in source_assets.glob('*.glb')}
        blobs={p['id']:by_hash[p['sha256']].read_bytes() for p in value['plan']['parts']}
        value['plan']['title']='이미지 보정 → H3 화병'
        candidates.append(('review-image-refinement',value,blobs))
    repaired=ROOT/'artifacts/chest-body-refinement/assembly.json'
    if repaired.exists():
        reference=json.loads(repaired.read_text())
        value=copy.deepcopy(next(v for aid,v,_ in candidates if aid=='review-h3-dynamic-mesh'))
        blobs=copy.copy(next(b for aid,_,b in candidates if aid=='review-h3-dynamic-mesh'))
        expected=reference['plan']['parts'][0]['sha256']
        path=next(p for p in (repaired.parent/'server-data/assets').glob('*.glb') if hashlib.sha256(p.read_bytes()).hexdigest()==expected)
        blobs['body']=path.read_bytes()
        value['plan']['title']='H3 보정 상자 · 직접 색칠'
        value['provenance'].update(tripo_credits_consumed=45,repair_credits=25,initial_attempt_credits=20,repair_method='reference_image_refinement_then_image_to_model',repair_provenance=reference['provenance'])
        candidates.append(('review-h3-repaired',value,blobs))
    with app.state.db.transaction() as conn:
        user=conn.execute("SELECT id FROM users WHERE username='workshop'").fetchone()[0]
        for aid,value,blobs in candidates:
            if conn.execute('SELECT 1 FROM assets WHERE id=?',(aid,)).fetchone():continue
            for part in value['plan']['parts']:
                blob=blobs[part['id']];validate_glb(blob,allow_textures=value['provenance']['material']=='textured')
                filename=aid+'-'+part['id']+'.glb';(folder/'assets'/filename).write_bytes(blob)
                part.update(file=filename,sha256=hashlib.sha256(blob).hexdigest())
            first=value['plan']['parts'][0];oid=str(uuid.uuid4())
            conn.execute('INSERT INTO assets VALUES (?,?,?,?)',(aid,first['file'],first['sha256'],'studio'))
            conn.execute('INSERT INTO studio_assets VALUES (?,?)',(aid,json.dumps(value)))
            conn.execute("INSERT INTO objects(id,owner_id,creator_id,asset_id,name,created,state) VALUES (?,?,?,?,?,1,'inventory')",(oid,user,user,aid,value['plan']['title']))
            vm=AssetVM(value['program'],list(blobs));vm.run('spawn')
            conn.execute('INSERT INTO studio_runtime(object_id,state) VALUES (?,?)',(oid,json.dumps(vm.state)))
            conn.execute('INSERT OR IGNORE INTO asset_categories VALUES (?,0)',(value['plan']['category'],))
            for name,definition in value['program']['functions'].items():
                encoded=json.dumps(definition,sort_keys=True,separators=(',',':'))
                conn.execute('INSERT INTO generated_apis VALUES (?,?,?,?)',(aid,name,encoded,hashlib.sha256(encoded.encode()).hexdigest()))
    print(json.dumps({'imported_candidates':len(candidates),'paid_calls':0}))
if __name__=='__main__':main()
