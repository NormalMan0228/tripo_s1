"""Seed only an isolated local review database with paid comparison artifacts.
Existing player worlds are never reset. This is a developer import, not a public API.
"""
import hashlib,json,shutil,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server.asset_assembly import demo_design
from server.provider import validate_glb
from server.asset_vm import exercise

def main():
    folder=ROOT/'artifacts/studio-review-data'
    app=create_app(Settings(data_dir=folder,studio_llm='codex',daily_generation_limit=100),worker_enabled=False)
    # Explicitly disposable localhost demo identity, never a production credential.
    with TestClient(app) as c:
        credentials={'username':'workshop','password':'tripothon-local-demo'}
        reply=c.post('/v1/auth/register',json=credentials)
        if reply.status_code!=200:reply=c.post('/v1/auth/login',json=credentials)
        if reply.status_code!=200:raise RuntimeError('review_login_failed')
        h={'Authorization':'Bearer '+reply.json()['token']}
        with app.state.db.transaction() as conn:
            user=conn.execute("SELECT id FROM users WHERE username='workshop'").fetchone()[0]
            if not conn.execute("SELECT 1 FROM ledger WHERE user_id=? AND reason='review_allowance'",(user,)).fetchone():
                conn.execute('UPDATE users SET shards=shards+500 WHERE id=?',(user,))
                conn.execute('INSERT INTO ledger VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),user,500,'review_allowance','review',0))
            for motion in ('static','dynamic'):
                for material in ('mesh','textured'):
                    aid='review-'+motion+'-'+material
                    if conn.execute('SELECT 1 FROM assets WHERE id=?',(aid,)).fetchone():continue
                    plan,program=demo_design('chest')
                    if motion=='static':
                        plan['parts']=plan['parts'][:1];plan['parts'][0].update(id='static',size=[1.2,.8,.8],position=[0,.4,0],color='#ffffff')
                        program={'version':1,'state':{},'functions':{},'events':{}}
                    credits=0
                    for p in plan['parts']:
                        name=p['id'];src=ROOT/'artifacts/furniture/runtime-comparison'/(name+'-'+material)
                        blob=(src/'model.glb').read_bytes();validate_glb(blob,allow_textures=material=='textured')
                        filename=aid+'-'+name+'.glb';(folder/'assets'/filename).write_bytes(blob)
                        p.update(file=filename,sha256=hashlib.sha256(blob).hexdigest(),color='#ffffff' if material=='textured' else '#d1af75')
                        credits+=json.loads((src/'result.json').read_text())['balance_delta']
                    plan['title']=('정적' if motion=='static' else '열리는')+' 상자 · '+('직접 색칠' if material=='mesh' else '텍스처')
                    provenance={'provider':'authored_comparison_plan','geometry':'tripo','material':material,'motion':motion,'tripo_model':'P2-20260801','tripo_credits_consumed':credits,'validation':exercise(program,[p['id'] for p in plan['parts']])}
                    value={'schema':1,'plan':plan,'program':program,'provenance':provenance};oid=str(uuid.uuid4())
                    conn.execute('INSERT INTO assets VALUES (?,?,?,?)',(aid,plan['parts'][0]['file'],plan['parts'][0]['sha256'],'studio'))
                    conn.execute('INSERT INTO studio_assets VALUES (?,?)',(aid,json.dumps(value)))
                    conn.execute("INSERT INTO objects(id,owner_id,creator_id,asset_id,name,created,state,x,z) VALUES (?,?,?,?,?,0,'placed',?,?)",(oid,user,user,aid,plan['title'],-2 if motion=='static' else 2,-2 if material=='mesh' else 1))
                    conn.execute('INSERT INTO studio_runtime(object_id,state) VALUES (?,?)',(oid,json.dumps(program['state'])))
                    conn.execute("INSERT INTO furniture_locations VALUES (?,'workshop')",(oid,))
        # No bearer credential is written into review artifacts.
        print(json.dumps({'review_seeded':True,'objects':len(c.get('/v1/studio',headers=h).json()['objects']),'paid_generation_calls':0}))
if __name__=='__main__':main()
