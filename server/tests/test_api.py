import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings, ROOT
from server.provider import TripoProvider, ProviderError, validate_glb

def mutation(**kw): return dict(request_id=str(uuid.uuid4()),**kw)

@pytest.fixture
def world(tmp_path):
    now=[1000000.]
    app=create_app(Settings(data_dir=tmp_path,daily_generation_limit=100),clock=lambda:now[0],worker_enabled=False)
    with TestClient(app) as client:
        yield app,client,now

def account(client,name):
    r=client.post('/v1/auth/register',json={'username':name,'password':'testing-only-12345'})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

def test_ownership_versions_and_no_public_assets(world):
    app,c,t=world; a=account(c,'alice'); b=account(c,'bob')
    item=c.get('/v1/me',headers=a).json()['objects'][0]
    route='/v1/objects/'+item['id']
    assert c.get(route+'/model').status_code==401
    assert c.get(route+'/model',headers=b).status_code==404
    r=c.get(route+'/model',headers=a)
    assert r.content[:4]==b'glTF' and r.headers['cache-control']=='no-store'
    edit=mutation(version=1,action='paint',color='#ff0022')
    assert c.post(route,headers=b,json=edit).status_code==404
    assert c.post(route,headers=a,json=edit).json()['version']==2
    assert c.post(route,headers=a,json=edit).json()['version']==2
    assert c.post(route,headers=a,json={**edit,'color':'#ffffff'}).status_code==409
    assert c.post(route,headers=a,json=mutation(version=1,action='retrieve')).status_code==409
    assert c.post(route,headers=a,json=mutation(version=2,action='place',x=5,z=4)).status_code==200
    assert c.post(route,headers=a,json=mutation(version=3,action='paint',owner_id='bob')).status_code==422
    assert c.post('/v1/auth/logout',headers=a).status_code==200
    assert c.get(route+'/model',headers=a).status_code==401

def test_generation_idempotency_private_status(world):
    app,c,t=world; a=account(c,'alice'); b=account(c,'bob')
    payload=mutation(prompt='round wooden stool')
    first=c.post('/v1/generations',headers=a,json=payload).json()
    assert c.post('/v1/generations',headers=a,json=payload).json()==first
    assert c.get('/v1/me',headers=a).json()['shards']==55
    assert c.get('/v1/generations/'+first['id'],headers=b).status_code==404
    asyncio.run(app.state.process_job(first['id']))
    job=c.get('/v1/generations/'+first['id'],headers=a).json()
    assert job['state']=='ready'
    assert c.get('/v1/objects/'+job['object_id']+'/model',headers=a).content[:4]==b'glTF'
    assert c.get('/v1/objects/'+job['object_id']+'/model',headers=b).status_code==404

def test_market_race_and_revocation(world):
    app,c,t=world; a=account(c,'alice'); b=account(c,'bob'); d=account(c,'dave')
    item=c.get('/v1/me',headers=a).json()['objects'][0]
    lid=c.post('/v1/market',headers=a,json=mutation(object_id=item['id'],version=1,price=30)).json()['id']
    assert c.post('/v1/objects/'+item['id'],headers=a,json=mutation(version=2,action='paint')).status_code==409
    def buy(h): return c.post('/v1/market/'+lid+'/buy',headers=h,json=mutation()).status_code
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(buy,[b,d]))
    assert sorted(results)==[200,409]
    assert c.get('/v1/objects/'+item['id']+'/model',headers=a).status_code==404
    assert c.get('/v1/me',headers=a).json()['shards']==110
    assert sum(c.get('/v1/me',headers=h).json()['shards'] for h in [a,b,d])==240

def test_survival_rejects_time_position_score_and_replay(world):
    app,c,t=world; a=account(c,'alice'); b=account(c,'bob')
    rid=c.post('/v1/runs',headers=a,json=mutation()).json()['id']; route='/v1/runs/'+rid
    assert c.get(route,headers=b).status_code==404
    assert c.post(route+'/input',headers=a,json={'sequence':1,'x':18,'elapsed':420,'score':500}).status_code==422
    t[0]+=1000
    state=c.post(route+'/input',headers=a,json={'sequence':1,'dx':1}).json()
    assert state['elapsed']<=.3 and state['x']<=1.35
    assert c.post(route+'/input',headers=a,json={'sequence':1}).status_code==409
    assert c.post(route+'/claim',headers=a,json=mutation()).status_code==409
    # A trusted fixture advances the run near its ending; no public API can set this.
    with app.state.db.transaction() as conn:
        s=json.loads(conn.execute('SELECT state FROM runs WHERE id=?',(rid,)).fetchone()[0])
        s.update(elapsed=419.9,hunger=100,hp=100,fire_until=500,x=0,z=0)
        conn.execute('UPDATE runs SET state=? WHERE id=?',(json.dumps(s),rid))
    t[0]+=.2
    state=c.post(route+'/input',headers=a,json={'sequence':2}).json()
    assert state['status']=='won'
    claim=mutation(); r=c.post(route+'/claim',headers=a,json=claim)
    assert r.status_code==200
    assert c.post(route+'/claim',headers=a,json=claim).json()==r.json()
    assert c.post(route+'/claim',headers=a,json=mutation()).status_code==409
    assert c.get('/v1/me',headers=a).json()['shards']==80+r.json()['reward']

def test_persistence_and_mode_boundary(world):
    app,c,t=world; a=account(c,'alice')
    app2=create_app(app.state.settings,clock=lambda:t[0],worker_enabled=False)
    with TestClient(app2) as second:
        assert second.get('/v1/me',headers=a).json()['username']=='alice'
    with pytest.raises(ValueError):
        create_app(Settings(data_dir=app.state.settings.data_dir,mode='live',registration_code='a'*24))

def test_provider_contract_and_sanitized_errors(tmp_path):
    settings=Settings(data_dir=tmp_path,tripo_key='test-secret-never-return')
    calls=[]
    def handler(req):
        calls.append(req)
        if req.url.path.endswith('/balance'): return httpx.Response(200,json={'code':0,'data':{'balance':500,'frozen':0}})
        if req.method=='POST':
            body=json.loads(req.content); assert body['texture'] is False and body['pbr'] is False
            return httpx.Response(200,json={'code':0,'data':{'task_id':'task_test'}})
        return httpx.Response(200,json={'code':0,'data':{'status':'success','output':{'model_url':'https://cdn.tripo3d.ai/model.glb'}}})
    p=TripoProvider(settings,httpx.MockTransport(handler))
    assert asyncio.run(p.balance())==500
    assert asyncio.run(p.submit('chair'))=='task_test'
    assert asyncio.run(p.task('task_test'))['status']=='success'
    for code,body,expected in [(401,'secret','upstream_authentication'),(400,'<html>secret</html>','upstream_non_json')]:
        p=TripoProvider(settings,httpx.MockTransport(lambda req:httpx.Response(code,text=body)))
        with pytest.raises(ProviderError) as err: asyncio.run(p.balance())
        assert str(err.value)==expected and 'secret' not in str(err.value)
    with pytest.raises(ProviderError): asyncio.run(p.download('https://127.0.0.1/private'))

def test_model_validator():
    blob=(ROOT/'game/assets/sample_stool.glb').read_bytes()
    assert validate_glb(blob)['asset']['version']=='2.0'
    with pytest.raises(ProviderError): validate_glb(blob[:-1])

def test_limits_expiry_and_insufficient_funds(world):
    app,c,t=world; a=account(c,'alice'); b=account(c,'bob')
    assert c.post('/v1/auth/login',content=b'x'*9000).status_code==413
    item=c.get('/v1/me',headers=a).json()['objects'][0]
    lid=c.post('/v1/market',headers=a,json=mutation(object_id=item['id'],version=1,price=100)).json()['id']
    assert c.post('/v1/market/'+lid+'/buy',headers=b,json=mutation()).status_code==409
    assert c.get('/v1/me',headers=b).json()['shards']==80
    assert c.get('/v1/market',headers=b).json()['listings'][0]['id']==lid
    assert c.post('/v1/market/'+lid+'/cancel',headers=b,json=mutation()).status_code==404
    assert c.post('/v1/market/'+lid+'/cancel',headers=a,json=mutation()).status_code==200
    t[0]+=app.state.settings.session_seconds+1
    assert c.get('/v1/me',headers=a).status_code==401

def test_full_seven_day_simulation():
    from server import simulation as sim
    # Simulate the full 420s using only valid movement/harvest/eat/fire intents.
    # The bot visits the guaranteed tree and berry bush, then returns to camp.
    s=sim.new_run(42,0,60)
    now=0.
    target=None
    for tick in range(4300):
        now+=.1
        inv=s['inventory']
        if s['status']!='active': break
        if s['hunger']<65 and (inv['berry'] or inv['soup']): sim.action(s,'eat')
        if s['elapsed']%60>37 and s['fire_until']-s['elapsed']<2 and inv['wood']>=2 and abs(s['x'])<2:
            sim.action(s,'fire')
        if inv['wood']<8 and s['nodes'][0]['quantity']>0: target=(1.2,0,'n0')
        elif inv['berry']<5 and s['nodes'][1]['quantity']>0: target=(-1.2,0,'n1')
        else: target=(0,0,'')
        dx=max(-1,min(1,(target[0]-s['x'])*2))
        dz=max(-1,min(1,(target[1]-s['z'])*2))
        sim.advance(s,now,dx,dz)
        if target[2] and abs(target[0]-s['x'])<.1: sim.action(s,'harvest',target[2])
    assert s['status']=='won',dict(hp=s['hp'],hunger=s['hunger'],elapsed=s['elapsed'])
    assert 35<=sim.reward(s)<=100

def test_live_transport_pipeline_without_spending(tmp_path):
    calls=[]; failures={'poll':True}
    blob=(ROOT/'game/assets/sample_stool.glb').read_bytes()
    def handler(req):
        calls.append((req.method,req.url.path))
        if req.url.host=='cdn.tripo3d.ai':
            assert 'authorization' not in req.headers
            return httpx.Response(200,content=blob)
        assert req.headers['authorization']=='Bearer test-only-placeholder'
        if req.url.path.endswith('/balance'): return httpx.Response(200,json={'code':0,'data':{'balance':1000}})
        if req.method=='POST': return httpx.Response(200,json={'code':0,'data':{'task_id':'task_mock'}})
        if failures['poll']:
            failures['poll']=False
            raise httpx.ConnectError('mock outage')
        return httpx.Response(200,json={'code':0,'data':{'status':'success','output':{'model_url':'https://cdn.tripo3d.ai/output/model.glb'}}})
    settings=Settings(data_dir=tmp_path,mode='live',registration_code='test-invitation-only-12345',paid_enabled=True,tripo_key='test-only-placeholder')
    provider=TripoProvider(settings,httpx.MockTransport(handler))
    app=create_app(settings,provider=provider,worker_enabled=False)
    with TestClient(app,base_url='https://testserver') as c:
        body={'username':'alice','password':'test-password-123','invitation':settings.registration_code}
        token=c.post('/v1/auth/register',json=body).json()['token']; h={'Authorization':'Bearer '+token}
        assert c.get('/v1/me',headers=h).json()['shards']==0
        # Server-side test grant, deliberately not exposed as an endpoint.
        with app.state.db.transaction() as conn: conn.execute('UPDATE users SET shards=100')
        job=c.post('/v1/generations',headers=h,json=mutation(prompt='wooden stool')).json()
        asyncio.run(app.state.process_job(job['id']))
        assert c.get('/v1/generations/'+job['id'],headers=h).json()['state']=='generating'
        asyncio.run(app.state.process_job(job['id']))
        ready=c.get('/v1/generations/'+job['id'],headers=h).json()
        assert ready['state']=='ready'
        assert c.get('/v1/objects/'+ready['object_id']+'/model',headers=h).content==blob
        assert sum(1 for m,p in calls if m=='POST')==1
        assert c.get('/v1/me',headers=h).json()['shards']==75

def test_uncertain_submit_holds_paid_lock(tmp_path):
    def handler(req):
        if req.method=='POST': raise httpx.ReadTimeout('mock timeout')
        return httpx.Response(200,json={'code':0,'data':{'balance':1000}})
    settings=Settings(data_dir=tmp_path,mode='live',registration_code='test-invitation-only-12345',paid_enabled=True,tripo_key='fake')
    app=create_app(settings,provider=TripoProvider(settings,httpx.MockTransport(handler)),worker_enabled=False)
    with TestClient(app,base_url='https://testserver') as c:
        r=c.post('/v1/auth/register',json={'username':'alice','password':'test-password-123','invitation':settings.registration_code})
        h={'Authorization':'Bearer '+r.json()['token']}
        with app.state.db.transaction() as conn: conn.execute('UPDATE users SET shards=100')
        job=c.post('/v1/generations',headers=h,json=mutation(prompt='wooden stool')).json()
        asyncio.run(app.state.process_job(job['id']))
        assert c.get('/v1/generations/'+job['id'],headers=h).json()['state']=='unknown'
        assert c.post('/v1/generations',headers=h,json=mutation(prompt='another stool')).status_code==409
        assert c.get('/v1/me',headers=h).json()['shards']==75
