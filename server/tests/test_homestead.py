from concurrent.futures import ThreadPoolExecutor
from server.tests.test_api import world, account, mutation

def get(c,a): return c.get('/v1/homestead',headers=a).json()
def do(c,a,action,**kw):
    return c.post('/v1/homestead',headers=a,json=mutation(version=get(c,a)['version'],action=action,**kw))

def test_crops_require_seed_water_and_server_growth_then_persist(world):
    app,c,t=world; a=account(c,'farmer')
    assert get(c,a)['version']==0
    assert do(c,a,'plant',item='turnip',plot=0).status_code==200
    assert get(c,a)['bag']['turnip_seed']==2
    t[0]+=1000
    assert do(c,a,'harvest',plot=0).status_code==409
    assert do(c,a,'water',plot=0).status_code==200
    assert do(c,a,'water',plot=0).status_code==409
    t[0]+=89.9
    assert do(c,a,'harvest',plot=0).status_code==409
    t[0]+=.1
    assert do(c,a,'harvest',plot=0).json()['bag']['turnip']==2
    assert do(c,a,'harvest',plot=0).status_code==409
    assert c.post('/v1/auth/logout',headers=a).status_code==200
    login=c.post('/v1/auth/login',json={'username':'farmer','password':'Testing-only-12345'}).json()
    a={'Authorization':'Bearer '+login['token']}
    assert get(c,a)['bag']['turnip']==2

def test_life_auth_owner_version_idempotency_and_injection(world):
    app,c,t=world; a=account(c,'life_alice'); b=account(c,'life_bob')
    payload=mutation(version=0,action='plant',plot=2,item='pumpkin')
    assert c.get('/v1/homestead').status_code==401
    assert c.post('/v1/homestead',json=payload).status_code==401
    first=c.post('/v1/homestead',headers=a,json=payload)
    assert first.status_code==200
    assert c.post('/v1/homestead',headers=a,json=payload).json()==first.json()
    assert not get(c,b)['plots'][2]
    assert c.post('/v1/homestead',headers=a,json=mutation(version=0,action='buy',item='bait')).status_code==409
    for injected in [{'owner_id':'life_bob'},{'ready_at':0},{'coins':999},{'quantity':-1},{'plot':-1},{'plot':6}]:
        assert c.post('/v1/homestead',headers=a,json=payload|injected).status_code==422
    assert do(c,a,'plant',item='../../key',plot=0).status_code==409

def test_fishing_consumes_bait_and_timing_cannot_be_skipped(world):
    app,c,t=world; a=account(c,'angler')
    state=do(c,a,'cast').json()
    assert state['bag']['bait']==4
    assert 'catch' not in state['fishing']
    assert do(c,a,'cast').status_code==409
    early=do(c,a,'reel').json()
    assert early['caught']==0 and early['fishing'] is None
    state=do(c,a,'cast',spot='sea').json()
    t[0]=state['fishing']['bite_at']+.5
    payload=mutation(version=state['version'],action='reel')
    caught=c.post('/v1/homestead',headers=a,json=payload).json()
    assert caught['caught']==1 and sum(caught['collection'].values())==1
    assert c.post('/v1/homestead',headers=a,json=payload).json()==caught
    assert do(c,a,'reel').status_code==409
    state=do(c,a,'cast').json(); t[0]=state['fishing']['ends_at']+.001
    assert do(c,a,'reel').json()['caught']==1

def test_leaf_economy_never_mints_shards_and_enforces_costs(world):
    app,c,t=world; a=account(c,'villager')
    shards=c.get('/v1/me',headers=a).json()['shards']
    assert do(c,a,'gather',item='apple').json()['bag']['apple']==2
    assert do(c,a,'gather',item='apple').status_code==409
    assert do(c,a,'sell',item='apple',quantity=3).status_code==409
    assert do(c,a,'sell',item='apple',quantity=2).json()['coins']==16
    assert do(c,a,'buy',item='bait',quantity=16).json()['coins']==0
    assert do(c,a,'buy',item='bait').status_code==409
    assert do(c,a,'buy',item='shards').status_code==409
    assert do(c,a,'sell',item='turnip_seed').status_code==409
    assert c.get('/v1/me',headers=a).json()['shards']==shards
    t[0]+=60
    assert do(c,a,'gather',item='apple').status_code==200

def test_two_simultaneous_harvests_credit_only_once(world):
    app,c,t=world; a=account(c,'race_farmer')
    do(c,a,'plant',item='pumpkin'); do(c,a,'water'); t[0]+=150
    version=get(c,a)['version']
    def harvest(_): return c.post('/v1/homestead',headers=a,json=mutation(version=version,action='harvest')).status_code
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(harvest,range(2)))
    assert sorted(results)==[200,409]
    assert get(c,a)['bag']['pumpkin']==2

def test_daily_order_is_atomic_even_when_partial_ingredients_exist(world,monkeypatch):

    monkeypatch.setattr('server.homestead.secrets.randbelow',lambda upper: upper-1)
    app,c,t=world; a=account(c,'orders')
    do(c,a,'plant',item='turnip'); do(c,a,'water'); t[0]+=90; do(c,a,'harvest')
    before=get(c,a)
    assert do(c,a,'order').status_code==409
    assert get(c,a)['bag']==before['bag']
    # Catch through the actual rules; pond has a 85% perch probability.
    for _ in range(30):
        do(c,a,'buy',item='bait')
        cast=do(c,a,'cast').json(); t[0]=cast['fishing']['bite_at']+.1
        do(c,a,'reel')
        if get(c,a)['bag'].get('perch',0): break
    assert get(c,a)['bag'].get('perch',0)>0
    coins=get(c,a)['coins']
    assert do(c,a,'order').json()['coins']==coins+20
    assert do(c,a,'order').status_code==409
    t[0]+=86400
    login=c.post('/v1/auth/login',json={'username':'orders','password':'Testing-only-12345'}).json()
    a={'Authorization':'Bearer '+login['token']}
    assert get(c,a)['order_available']

def test_village_state_survives_backup_restore_and_old_db_upgrade(world,tmp_path):
    from fastapi.testclient import TestClient
    from server.app import create_app
    from server.config import Settings
    from server.backups import create_backup,restore_backup
    app,c,t=world; a=account(c,'backup_farmer')
    # Simulate the previous schema: adding the new table must retain the old account.
    with app.state.db.transaction() as db: db.execute('DROP TABLE homesteads')
    upgraded=create_app(app.state.settings,clock=lambda:t[0],worker_enabled=False)
    with TestClient(upgraded) as client:
        assert get(client,a)['bag']['turnip_seed']==3
        do(client,a,'plant',item='pumpkin'); do(client,a,'water')
        before=get(client,a)
    source=app.state.settings.data_dir
    snapshot=tmp_path.parent/(tmp_path.name+'-snapshot')
    restored=tmp_path.parent/(tmp_path.name+'-restored')
    create_backup(source,snapshot)
    restore_backup(snapshot,restored,'demo')
    recovered=create_app(Settings(data_dir=restored),clock=lambda:t[0]+151,worker_enabled=False)
    with TestClient(recovered) as client:
        assert client.get('/v1/homestead',headers=a).status_code==401
        login=client.post('/v1/auth/login',json={'username':'backup_farmer','password':'Testing-only-12345'}).json()
        auth={'Authorization':'Bearer '+login['token']}
        assert get(client,auth)['coins']==before['coins']
        assert get(client,auth)['plots'][0]['ready']
        assert do(client,auth,'harvest').json()['bag']['pumpkin']==2
