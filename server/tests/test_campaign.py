import json,uuid
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server import campaign,simulation

def mutation(**kw):return {'request_id':str(uuid.uuid4()),**kw}
def account(c,name):
    token=c.post('/v1/auth/register',json={'username':name,'password':'Local-campaign-test'}).json()['token']
    return {'Authorization':'Bearer '+token}
def finish_fixture(app,run_id,complete=True):
    # Unit-test state fixture, separate from the real-time Godot playthrough.
    with app.state.db.transaction() as conn:
        state=json.loads(conn.execute('SELECT state FROM runs WHERE id=?',(run_id,)).fetchone()[0])
        state.update(status='won',elapsed=420,harvested=50,fires=10,crafted={'axe':1,'spear':1,'soup':2} if complete else {})
        conn.execute("UPDATE runs SET state=?,status='won',reward=60 WHERE id=?",(json.dumps(state),run_id))

def test_story_gates_authoritative_map_and_once_only_bonus(tmp_path):
    app=create_app(Settings(data_dir=tmp_path),worker_enabled=False)
    with TestClient(app) as c:
        a=account(c,'alice');b=account(c,'bob')
        chapters=c.get('/v1/me',headers=a).json()['campaign']
        assert [x['unlocked'] for x in chapters]==[True,False,False]
        assert c.post('/v1/runs',headers=a,json=mutation(chapter_id='quiet_quarry')).status_code==409
        assert c.post('/v1/runs',headers=a,json=mutation(chapter_id='first_fire',story_bonus=999)).status_code==422
        for chapter in campaign.CHAPTERS:
            rid=c.post('/v1/runs',headers=a,json=mutation(chapter_id=chapter['id'],map_id='frost')).json()['id']
            assert c.get('/v1/runs/'+rid,headers=a).json()['map_id']==chapter['map_id']
            finish_fixture(app,rid)
            ready=c.get('/v1/runs/'+rid,headers=a).json()
            assert ready['story']['objectives_met'] and ready['reward']==60+chapter['bonus']
            assert c.get('/v1/me',headers=a).json()['pending_reward']['reward']==ready['reward']
            assert c.post('/v1/runs/'+rid+'/claim',headers=b,json=mutation()).status_code==404
            first=mutation();reply=c.post('/v1/runs/'+rid+'/claim',headers=a,json=first)
            assert reply.json()['story_bonus']==chapter['bonus']
            assert c.post('/v1/runs/'+rid+'/claim',headers=a,json=first).json()==reply.json()
            assert c.post('/v1/runs/'+rid+'/claim',headers=a,json=mutation()).status_code==409
            assert c.get('/v1/runs/'+rid,headers=a).json()['reward']==ready['reward']
        assert all(x['completed'] for x in c.get('/v1/me',headers=a).json()['campaign'])
        assert not any(x['completed'] for x in c.get('/v1/me',headers=b).json()['campaign'])
        replay=c.post('/v1/runs',headers=a,json=mutation(chapter_id='first_fire')).json()['id'];finish_fixture(app,replay)
        assert c.post('/v1/runs/'+replay+'/claim',headers=a,json=mutation()).json()['story_bonus']==0

def test_missing_objectives_and_multiple_pending_wins_cannot_farm_story_bonus(tmp_path):
    app=create_app(Settings(data_dir=tmp_path),worker_enabled=False)
    with TestClient(app) as c:
        a=account(c,'alice')
        rid=c.post('/v1/runs',headers=a,json=mutation(chapter_id='first_fire')).json()['id'];finish_fixture(app,rid,False)
        assert not c.get('/v1/runs/'+rid,headers=a).json()['story']['objectives_met']
        assert c.post('/v1/runs/'+rid+'/claim',headers=a,json=mutation()).json()['story_bonus']==0
        ids=[]
        for _ in range(2):
            rid=c.post('/v1/runs',headers=a,json=mutation(chapter_id='first_fire')).json()['id'];finish_fixture(app,rid);ids.append(rid)
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies=list(pool.map(lambda rid:c.post('/v1/runs/'+rid+'/claim',headers=a,json=mutation()),ids))
        assert all(r.status_code==200 for r in replies)
        assert sorted(r.json()['story_bonus'] for r in replies)==[0,20]

def test_crafting_and_fire_counters_record_only_successful_actions():
    s=simulation.new_run(1,0,60);s['inventory'].update(wood=15,stone=4,berry=6)
    s['elapsed']=1;simulation.action(s,'craft','axe')
    assert s['crafted']=={'axe':1}
    s['elapsed']=2;simulation.action(s,'craft','axe');assert s['crafted']=={'axe':1}
    s['elapsed']=3;simulation.action(s,'craft','soup');assert s['crafted']['soup']==1
    s.update(x=0,z=2,elapsed=4);simulation.action(s,'fire');assert s['fires']==1
    s.update(x=10,z=10,elapsed=5);simulation.action(s,'fire');assert s['fires']==1
    s['chapter_id']='first_fire';assert not campaign.progress(s)['objectives_met']
