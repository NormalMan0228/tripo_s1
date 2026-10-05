import asyncio
import copy
import json
import math
import uuid
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server.asset_vm import AssetVM,ProgramError,validate_program
from server.asset_assembly import demo_design,fixture_glb,validate_plan
from server.provider import validate_glb,ProviderError

def mutation(**kw):return {'request_id':str(uuid.uuid4()),**kw}
def account(c,name):
    r=c.post('/v1/auth/register',json={'username':name,'password':'studio-test-password'})
    assert r.status_code==200
    return {'Authorization':'Bearer '+r.json()['token']}
@pytest.fixture
def world(tmp_path):
    app=create_app(Settings(data_dir=tmp_path,daily_generation_limit=100),worker_enabled=False)
    with TestClient(app) as c:yield app,c
def build(app,c,h,prompt='flower',**kw):
    reply=c.post('/v1/studio/jobs',headers=h,json=mutation(prompt=prompt,**kw))
    assert reply.status_code==200,reply.text
    job=reply.json()['id'];asyncio.run(app.state.studio.process(job))
    result=c.get('/v1/studio/jobs/'+job,headers=h).json()
    assert result['state']=='ready',result
    return result['object_id']

def test_complete_assembly_security_paint_and_placement(world):
    app,c=world;a=account(c,'alice');b=account(c,'bob')
    oid=build(app,c,a,material='textured');route='/v1/objects/'+oid
    assert c.get(route+'/assembly').status_code==401
    assert c.get(route+'/assembly',headers=b).status_code==404
    value=c.get(route+'/assembly',headers=a).json()
    assert len(value['plan']['parts'])==8 and value['provenance']['geometry']=='procedural_proxy'
    part=value['plan']['parts'][0]
    response=c.get(route+'/parts/'+part['id'],headers=a)
    assert response.content[:4]==b'glTF' and response.headers['cache-control']=='no-store'
    assert c.get(route+'/parts/'+part['id'],headers=b).status_code==404
    assert c.post(route+'/colors',headers=b,json=mutation(version=1,color='#abcdef')).status_code==404
    p=mutation(version=1,color='#abcdef',part=part['id'])
    result=c.post(route+'/colors',headers=a,json=p)
    assert result.status_code==200 and result.json()['colors']=={part['id']:'#abcdef'}
    assert c.post(route+'/colors',headers=a,json=p).json()==result.json()
    assert c.post(route+'/event',headers=a,json=mutation(version=1,event='click')).status_code==409
    event=c.post(route+'/event',headers=a,json=mutation(version=2,event='click'))
    assert event.status_code==200 and event.json()['patch']['open']==1
    assert c.post(route+'/placement',headers=a,json=mutation(version=1,room='home',x=0,z=4)).status_code==409
    placed=c.post(route+'/placement',headers=a,json=mutation(version=1,room='home',x=2,z=0))
    assert placed.status_code==200
    objects=c.get('/v1/studio',headers=a).json()['objects']
    assert next(o for o in objects if o['id']==oid)['room']=='home'
    assert c.post(route+'/placement',headers=a,json=mutation(version=1,room='home',x=-2,z=0)).status_code==409

def test_queue_replay_cancellation_and_cost_tampering(world):
    app,c=world;a=account(c,'alice')
    payload=mutation(prompt='wooden chest',motion='static')
    first=c.post('/v1/studio/jobs',headers=a,json=payload)
    assert first.status_code==200 and first.json()['cost']==20
    assert c.post('/v1/studio/jobs',headers=a,json=payload).json()==first.json()
    assert c.get('/v1/me',headers=a).json()['shards']==60
    assert c.post('/v1/studio/jobs',headers=a,json=mutation(prompt='chest',cost=0)).status_code==422
    cancel=mutation();url='/v1/studio/jobs/'+first.json()['id']+'/cancel'
    assert c.post(url,headers=a,json=cancel).status_code==200
    assert c.post(url,headers=a,json=cancel).status_code==200
    asyncio.run(app.state.studio.process(first.json()['id']))
    assert c.get('/v1/me',headers=a).json()['shards']==80

def test_color_restore_is_per_part_private_and_preserves_original_plan(world):
    app,c=world;a=account(c,'alice');b=account(c,'bob');oid=build(app,c,a,'chest',material='textured');route='/v1/objects/'+oid
    original=c.get(route+'/assembly',headers=a).json()['plan']
    assert c.post(route+'/colors',headers=a,json=mutation(version=1,color='#123456')).status_code==200
    reset=mutation(version=2,color='#ffffff',part='lid',reset=True)
    assert c.post(route+'/colors',headers=b,json=reset).status_code==404
    restored=c.post(route+'/colors',headers=a,json=reset)
    assert restored.json()['colors']=={'body':'#123456'}
    assert c.post(route+'/colors',headers=a,json=reset).json()==restored.json()
    assert c.get(route+'/assembly',headers=a).json()['plan']==original
    assert c.post(route+'/colors',headers=a,json=mutation(version=3,color='#ffffff',reset=True)).json()['colors']=={}


def test_binding_corrections_are_private_bounded_versioned_and_reversible(world):
    app,c=world;a=account(c,'alice');b=account(c,'bob')
    oid=build(app,c,a,prompt='chest');route='/v1/objects/'+oid
    original=c.get(route+'/assembly',headers=a).json()
    body=mutation(version=1,part='lid',pivot=[0,0,-.4],rotation=[0,90,0])
    assert c.post(route+'/bindings',headers=b,json=body).status_code==404
    reply=c.post(route+'/bindings',headers=a,json=body)
    assert reply.status_code==200 and reply.json()['version']==2
    assert c.post(route+'/bindings',headers=a,json=body).json()==reply.json()
    edited=c.get(route+'/assembly',headers=a).json()
    assert edited['plan']['parts'][1]['pivot']==[0,0,-.4]
    assert edited['original_plan']==original['plan']
    assert edited['plan']['parts'][1]['sha256']==original['plan']['parts'][1]['sha256']
    assert c.post(route+'/bindings',headers=a,json=mutation(version=1,part='lid',reset=True)).status_code==409
    for invalid in ({'size':[999,1,1]},{'pivot':[0,0,2]},{'position':[0,4,0]}):
        assert c.post(route+'/bindings',headers=a,json=mutation(version=2,part='lid',**invalid)).status_code==422
    assert c.post(route+'/bindings',headers=a,json=mutation(version=2,part='../../asset',reset=True)).status_code==422
    assert c.post(route+'/bindings',headers=a,json=mutation(version=2,part='lid',reset=True)).status_code==200
    assert c.get(route+'/assembly',headers=a).json()['plan']==original['plan']

def test_failure_refund_once_and_restart(world):
    app,c=world;a=account(c,'alice')
    p=mutation(prompt='wooden chest',designer='llm')
    assert c.post('/v1/studio/jobs',headers=a,json=p).status_code==503
    app.state.settings.studio_llm='openai'
    r=c.post('/v1/studio/jobs',headers=a,json=p);assert r.status_code==200
    job=r.json()['id'];asyncio.run(app.state.studio.process(job));asyncio.run(app.state.studio.process(job))
    assert c.get('/v1/studio/jobs/'+job,headers=a).json()['state']=='failed'
    assert c.get('/v1/me',headers=a).json()['shards']==80

def test_failed_design_preserves_token_usage_but_never_publishes(world):
    from server.design_provider import DesignFailure
    app,c=world;owner=account(c,'owner');stranger=account(c,'stranger')
    class BrokenDesigner:
        async def generate(self,*args):
            raise DesignFailure([{'usage':{'input_tokens':200,'output_tokens':100},'validation_error':'ProgramError: invalid_expression'},
                                 {'usage':{'input_tokens':250,'output_tokens':120},'validation_error':'ProgramError: invalid_expression'}])
    app.state.settings.studio_llm='openai';app.state.studio.designer=BrokenDesigner()
    job=c.post('/v1/studio/jobs',headers=owner,json=mutation(prompt='a clock',designer='llm')).json()['id']
    asyncio.run(app.state.studio.process(job));asyncio.run(app.state.studio.process(job))
    result=c.get('/v1/studio/jobs/'+job,headers=owner).json()
    assert result['state']=='failed' and result['object_id'] is None
    assert result['provenance']['usage']=={'input_tokens':450,'output_tokens':220}
    assert result['provenance']['tripo_credits_consumed']==0
    assert c.get('/v1/studio/jobs/'+job,headers=stranger).status_code==404
    assert c.get('/v1/me',headers=owner).json()['shards']==80

def test_transfer_revokes_manifest_parts_and_events(world):
    app,c=world;a=account(c,'alice');b=account(c,'bob');oid=build(app,c,a,'chest')
    route='/v1/objects/'+oid
    listed=c.post('/v1/market',headers=a,json=mutation(object_id=oid,version=1,price=10)).json()['id']
    assert c.post(route+'/event',headers=a,json=mutation(version=1,event='click')).status_code==409
    assert c.post('/v1/market/'+listed+'/buy',headers=b,json=mutation()).status_code==200
    assert c.get(route+'/assembly',headers=a).status_code==404
    assert c.get(route+'/parts/body',headers=a).status_code==404
    assert c.get(route+'/assembly',headers=b).status_code==200

@pytest.mark.parametrize('shape',['box','ellipsoid','petal'])
def test_fixture_glb_and_texture_gate(shape):
    validate_glb(fixture_glb(shape))
    with pytest.raises(ProviderError):validate_glb(fixture_glb(shape,True))
    validate_glb(fixture_glb(shape,True),allow_textures=True)

def test_vm_rolls_back_state_commands_and_limits_recursion():
    plan,p=demo_design('chest');ids=[x['id'] for x in plan['parts']]
    p['events']['click']=[['store','open',1],['emit','rotate_x','lid',-30],['set','bad',['div',1,0]]]
    vm=AssetVM(p,ids)
    with pytest.raises(ProgramError):vm.run('click')
    assert vm.state['open']==0 and vm.commands==[]
    p['functions']['recursive']={'params':[],'body':[],'return':['call','recursive']}
    p['events']['click']=[['do',['call','recursive']]]
    with pytest.raises(ProgramError):AssetVM(p,ids).run('click')

@pytest.mark.parametrize('expr',[['call',[]],['call',{}],['input','filesystem'],['import','os'],float('nan')])
def test_vm_rejects_malformed_and_capabilities(expr):
    plan,p=demo_design('chest');p['events']['click']=[['set','bad',expr]]
    with pytest.raises(ProgramError):validate_program(p,['body','lid'])

def test_plan_rejects_cycles_and_bad_pivots():
    plan,_=demo_design('chest');plan['parts'][0]['parent']='lid';plan['parts'][1]['parent']='body'
    with pytest.raises(ProgramError):validate_plan(plan)

def test_proxy_programs_long_running_and_deterministic():
    for text in ('flower','clock','chest'):
        plan,p=demo_design(text);vm=AssetVM(p,[x['id'] for x in plan['parts']])
        for i in range(1000):
            if i%100==0:vm.run('click')
            vm.run('tick',{'dt':.1,'time':i*1000,'near':i%2})
        assert all(math.isfinite(x) for x in vm.state.values())

def test_independent_workers_share_lease(world):
    app,c=world;a=account(c,'alice')
    job=c.post('/v1/studio/jobs',headers=a,json=mutation(prompt='wooden chest')).json()['id']
    with app.state.db.transaction() as conn:
        conn.execute('INSERT INTO studio_leases VALUES (?,?,?)',(job,'other-worker',app.state.studio.clock()+600))
    asyncio.run(app.state.studio.process(job))
    assert c.get('/v1/studio/jobs/'+job,headers=a).json()['state']=='queued'
    with app.state.db.transaction() as conn:conn.execute('DELETE FROM studio_leases WHERE job_id=?',(job,))
    asyncio.run(app.state.studio.process(job))
    assert c.get('/v1/studio/jobs/'+job,headers=a).json()['state']=='ready'

def test_restart_keeps_active_other_worker_and_unknown_submit(tmp_path):
    settings=Settings(data_dir=tmp_path,daily_generation_limit=100)
    app=create_app(settings,worker_enabled=False)
    with TestClient(app) as c:
        a=account(c,'alice');job=c.post('/v1/studio/jobs',headers=a,json=mutation(prompt='wooden chest')).json()['id']
        with app.state.db.transaction() as conn:
            conn.execute("UPDATE studio_jobs SET state='submitting' WHERE id=?",(job,))
            conn.execute('INSERT INTO studio_leases VALUES (?,?,?)',(job,'alive',app.state.studio.clock()+600))
        second=create_app(settings,worker_enabled=False)
        assert c.get('/v1/studio/jobs/'+job,headers=a).json()['state']=='submitting'
        with app.state.db.transaction() as conn:conn.execute('DELETE FROM studio_leases WHERE job_id=?',(job,))
        third=create_app(settings,worker_enabled=False)
        assert c.get('/v1/studio/jobs/'+job,headers=a).json()['state']=='unknown'

def test_placement_isolated_between_rooms_and_legacy_route(world):
    app,c=world;a=account(c,'alice')
    objects=[build(app,c,a,'chest',motion='static') for _ in range(2)]
    for oid,room in zip(objects,['home','workshop']):
        assert c.post('/v1/objects/'+oid+'/placement',headers=a,json=mutation(version=1,room=room,x=2,z=0)).status_code==200
    result=c.get('/v1/me',headers=a).json()['objects']
    assert {o['room'] for o in result if o['id'] in objects}=={'home','workshop'}
    oid=objects[0]
    assert c.post('/v1/objects/'+oid,headers=a,json=mutation(version=2,action='retrieve')).status_code==200
    assert c.post('/v1/objects/'+oid,headers=a,json=mutation(version=3,action='place',x=3,z=3)).status_code==200
    assert next(o for o in c.get('/v1/me',headers=a).json()['objects'] if o['id']==oid)['room']=='village'

class FurnitureProvider:
    def __init__(self,uncertain=False):self.calls=[];self.uncertain=uncertain
    async def balance(self):return 10000
    async def request(self,method,path,payload):
        self.calls.append(payload)
        if self.uncertain:raise ProviderError('upstream_unreachable',uncertain=True)
        return {'task_id':'task-'+str(len(self.calls))}
    async def task(self,task):return {'status':'success','credits_consumed':100,'output':{'model_url':'private-test-model'}}
    async def download(self,url,allow_textures=False):return fixture_glb('box',allow_textures)

def paid_world(tmp_path,provider,rate=.1):
    settings=Settings(data_dir=tmp_path,paid_enabled=True,tripo_key='private-test-key',daily_generation_limit=100,studio_credit_rate=rate)
    app=create_app(settings,provider=provider,worker_enabled=False)
    return app,TestClient(app)

def test_preflight_preview_is_private_readonly_and_never_calls_provider(tmp_path):
    import base64
    provider=FurnitureProvider();app,client=paid_world(tmp_path,provider)
    with client as c:
        a=account(c,'alice');b=account(c,'bob')
        job=c.post('/v1/studio/jobs',headers=a,json=mutation(prompt='wooden chest',geometry='tripo')).json()['id']
        route='/v1/studio/jobs/'+job+'/preview'
        assert c.get(route,headers=a).status_code==409
        asyncio.run(app.state.studio.process(job))
        before=c.get('/v1/me',headers=a).json()
        assert c.get(route).status_code==401
        assert c.get(route,headers=b).status_code==404
        value=c.get(route,headers=a).json()
        assert value['preview_only'] and len(value['plan']['parts'])==2
        for encoded in value['blobs'].values():validate_glb(base64.b64decode(encoded))
        vm=AssetVM(value['program'],list(value['blobs']))
        vm.run('click');assert vm.state['open']==1
        assert not provider.calls
        assert c.get('/v1/me',headers=a).json()==before
        assert c.get('/v1/studio/jobs/'+job,headers=a).json()['state']=='awaiting_confirmation'

def test_unconfirmed_quote_does_not_block_other_players_but_confirm_stays_single(tmp_path):
    provider=FurnitureProvider();app,client=paid_world(tmp_path,provider)
    with client as c:
        a=account(c,'alice');b=account(c,'bob')
        stale=c.post('/v1/studio/jobs',headers=a,json=mutation(prompt='wooden chest',geometry='tripo',motion='static')).json()['id']
        asyncio.run(app.state.studio.process(stale))
        assert c.get('/v1/studio/jobs/'+stale,headers=a).json()['state']=='awaiting_confirmation'
        # The owner still has one pending job; other players may request a quote.
        assert c.post('/v1/studio/jobs',headers=a,json=mutation(prompt='stool',geometry='tripo',motion='static')).json()['detail']=='generation_pending'
        fresh=c.post('/v1/studio/jobs',headers=b,json=mutation(prompt='stool',geometry='tripo',motion='static'))
        assert fresh.status_code==200;fresh=fresh.json()['id']
        asyncio.run(app.state.studio.process(fresh))
        assert c.post('/v1/studio/jobs/'+fresh+'/confirm',headers=b,json=mutation()).status_code==200
        # Only one confirmed job may use the provider at a time.
        assert c.post('/v1/studio/jobs/'+stale+'/confirm',headers=a,json=mutation()).json()['detail']=='provider_busy'
        assert c.get('/v1/studio/jobs/'+stale,headers=a).json()['state']=='awaiting_confirmation'
        assert not provider.calls

def test_paid_design_quote_precedes_generation_and_confirm_is_idempotent(tmp_path):
    provider=FurnitureProvider();app,client=paid_world(tmp_path,provider)
    with client as c:
        a=account(c,'alice');b=account(c,'bob')
        job=c.post('/v1/studio/jobs',headers=a,json=mutation(prompt='wooden chest',geometry='tripo',motion='static')).json()['id']
        asyncio.run(app.state.studio.process(job))
        status=c.get('/v1/studio/jobs/'+job,headers=a).json()
        assert status['state']=='awaiting_confirmation' and status['provenance']['estimated_tripo_credits']==100
        assert len(status['parts'])==1 and not provider.calls
        assert c.post('/v1/studio/jobs/'+job+'/confirm',headers=b,json=mutation()).status_code==404
        confirmation=mutation()
        first=c.post('/v1/studio/jobs/'+job+'/confirm',headers=a,json=confirmation)
        assert first.status_code==200
        assert c.post('/v1/studio/jobs/'+job+'/confirm',headers=a,json=confirmation).json()==first.json()
        for _ in range(5):asyncio.run(app.state.studio.process(job))
        assert len(provider.calls)==1
        ready=c.get('/v1/studio/jobs/'+job,headers=a).json()
        assert ready['state']=='ready' and ready['provenance']['tripo_credits_consumed']==100

def test_paid_quote_can_cancel_without_provider_call(tmp_path):
    provider=FurnitureProvider();app,client=paid_world(tmp_path,provider)
    with client as c:
        a=account(c,'alice')
        job=c.post('/v1/studio/jobs',headers=a,json=mutation(prompt='wooden chest',geometry='tripo',material='textured')).json()['id']
        asyncio.run(app.state.studio.process(job))
        assert c.get('/v1/studio/jobs/'+job,headers=a).json()['provenance']['estimated_tripo_credits']==220
        cancel=mutation()
        for _ in range(2):assert c.post('/v1/studio/jobs/'+job+'/cancel',headers=a,json=cancel).status_code==200
        assert not provider.calls and c.get('/v1/me',headers=a).json()['shards']==80


def test_final_quote_requires_currency_before_any_paid_submission(tmp_path):
    provider=FurnitureProvider();app,client=paid_world(tmp_path,provider,rate=1)
    with client as c:
        a=account(c,'alice')
        job=c.post('/v1/studio/jobs',headers=a,json=mutation(prompt='chest',geometry='tripo',motion='static')).json()['id']
        asyncio.run(app.state.studio.process(job))
        status=c.get('/v1/studio/jobs/'+job,headers=a).json()
        assert status['provenance']['quoted_game_cost']==100 and status['cost']==20
        assert c.post('/v1/studio/jobs/'+job+'/confirm',headers=a,json=mutation()).status_code==409
        assert not provider.calls
        with app.state.db.transaction() as conn:
            user=conn.execute("SELECT id FROM users WHERE username='alice'").fetchone()[0]
            app.state.studio.money(conn,user,50,'test_reward','reward')
        confirmation=mutation()
        for _ in range(2):assert c.post('/v1/studio/jobs/'+job+'/confirm',headers=a,json=confirmation).status_code==200
        assert c.get('/v1/me',headers=a).json()['shards']==30
        app.state.studio.error(job,ProviderError('test_failure'))
        app.state.studio.error(job,ProviderError('duplicate_failure'))
        assert c.get('/v1/me',headers=a).json()['shards']==130


def test_rejected_paid_mesh_keeps_actual_cost_and_refunds_game_currency(tmp_path):
    class InvalidMesh(FurnitureProvider):
        async def download(self,url,allow_textures=False):raise ProviderError('invalid_model')
    provider=InvalidMesh();app,client=paid_world(tmp_path,provider)
    with client as c:
        a=account(c,'alice')
        job=c.post('/v1/studio/jobs',headers=a,json=mutation(prompt='wooden chest',geometry='tripo',motion='static')).json()['id']
        asyncio.run(app.state.studio.process(job))
        c.post('/v1/studio/jobs/'+job+'/confirm',headers=a,json=mutation())
        for _ in range(4):asyncio.run(app.state.studio.process(job))
        result=c.get('/v1/studio/jobs/'+job,headers=a).json()
        assert result['state']=='failed' and result['provenance']['tripo_credits_consumed']==100
        assert c.get('/v1/me',headers=a).json()['shards']==80
        assert len(provider.calls)==1


def test_missing_provider_billing_is_unknown_not_free():
    from server.asset_studio import billing
    assert billing({'body':{'task':'known','state':'generating'}})=={'known_tripo_credits':0,'tripo_credits_consumed':None,'billing_complete':False}
    value=billing({'body':{'task':'known','credits_consumed':100},'lid':{'task':'pending'}})
    assert value['known_tripo_credits']==100 and value['tripo_credits_consumed'] is None

def test_ambiguous_paid_submission_never_retries(tmp_path):
    provider=FurnitureProvider(uncertain=True);app,client=paid_world(tmp_path,provider)
    with client as c:
        a=account(c,'alice')
        job=c.post('/v1/studio/jobs',headers=a,json=mutation(prompt='wooden chest',geometry='tripo')).json()['id']
        asyncio.run(app.state.studio.process(job))
        c.post('/v1/studio/jobs/'+job+'/confirm',headers=a,json=mutation())
        for _ in range(4):asyncio.run(app.state.studio.process(job))
        assert len(provider.calls)==1
        assert c.get('/v1/studio/jobs/'+job,headers=a).json()['state']=='unknown'
        assert c.get('/v1/me',headers=a).json()['shards']==50

def test_resumed_failure_refunds_only_the_outstanding_charge(world):
    app,c=world;a=account(c,'alice')
    job=c.post('/v1/studio/jobs',headers=a,json=mutation(prompt='wooden chest')).json()['id']
    app.state.studio.error(job,ProviderError('first_failure'))
    with app.state.db.transaction() as conn:
        row=conn.execute('SELECT * FROM studio_jobs WHERE id=?',(job,)).fetchone()
        app.state.studio.money(conn,row['owner_id'],-row['cost'],'studio_resume_charge',job)
        conn.execute("UPDATE studio_jobs SET state='building' WHERE id=?",(job,))
    app.state.studio.error(job,ProviderError('second_failure'))
    app.state.studio.error(job,ProviderError('duplicate_failure'))
    assert c.get('/v1/me',headers=a).json()['shards']==80

def test_reserved_house_and_workbench_cannot_be_bypassed(world):
    app,c=world;a=account(c,'alice');oid=build(app,c,a,'chest',motion='static');route='/v1/objects/'+oid
    assert c.post(route+'/placement',headers=a,json=mutation(version=1,room='workshop',x=-3,z=-3)).status_code==409
    assert c.post(route+'/placement',headers=a,json=mutation(version=1,room='village',x=-10.8,z=-7)).status_code==409
    assert c.post(route,headers=a,json=mutation(version=1,action='place',x=-10.8,z=-7)).status_code==409

def test_generated_api_is_owned_versioned_idempotent_and_registered(world):
    app,c=world;a=account(c,'alice');b=account(c,'bob');oid=build(app,c,a,'chest');route='/v1/objects/'+oid+'/invoke'
    call=mutation(version=1,function='hinge_angle',args=[.5])
    assert c.post(route,headers=b,json=call).status_code==404
    result=c.post(route,headers=a,json=call)
    assert result.status_code==200 and result.json()['result']==-47.5
    assert c.post(route,headers=a,json=call).json()==result.json()
    assert c.post(route,headers=a,json=mutation(version=1,function='hinge_angle',args=[1])).status_code==409
    assert c.post(route,headers=a,json=mutation(version=2,function='os_system',args=[])).status_code==409
    assert c.post(route,headers=a,json=mutation(version=2,function='hinge_angle',args=[])).status_code==409
    assert c.get('/v1/me',headers=a).json()['shards']==50
    with app.state.db.transaction() as conn:
        entry=conn.execute('SELECT generated_apis.name,digest FROM generated_apis JOIN objects ON generated_apis.asset_id=objects.asset_id WHERE objects.id=?',(oid,)).fetchone()
        assert entry['name']=='hinge_angle' and len(entry['digest'])==64

def test_generated_api_rolls_back_on_host_limit():
    plan,program=demo_design('chest')
    program['functions']['unsafe']={'params':['angle'],'body':[['store','open',1],['emit','rotate_x','lid',['var','angle']]],'return':0}
    vm=AssetVM(program,['body','lid'])
    with pytest.raises(ProgramError):vm.invoke('unsafe',[1000])
    assert vm.state['open']==0 and vm.commands==[]
    with pytest.raises(ProgramError):vm.invoke('hinge_angle',[['call','unsafe',0]])

def test_reference_refinement_to_model_keeps_task_chain_and_costs(tmp_path):
    import base64,io
    from PIL import Image
    class Provider(FurnitureProvider):
        async def upload_image(self,image):return 'private_file_token'
        async def request(self,method,path,payload):
            self.calls.append((path,payload))
            return {'task_id':'refined_reference' if path.endswith('image-to-image') else 'generated_mesh'}
        async def task(self,task):
            return {'status':'success','credits_consumed':5 if task=='refined_reference' else 20,'output':{'model_url':'private-test-model'}}
    class Designer:
        async def generate(self,*args):return (*demo_design('chest'),{'provider':'mock_designer'})
    provider=Provider();settings=Settings(data_dir=tmp_path,paid_enabled=True,tripo_key='private-test-key',studio_llm='openai')
    app=create_app(settings,provider=provider,designer=Designer(),worker_enabled=False)
    raw=io.BytesIO();Image.new('RGB',(32,32),'white').save(raw,format='PNG');image='data:image/png;base64,'+base64.b64encode(raw.getvalue()).decode()
    with TestClient(app) as c:
        a=account(c,'alice')
        request=mutation(prompt='wooden chest',geometry='tripo',designer='llm',motion='static',image=image,image_mode='refine',mesh_model='v3.1-20260211')
        job=c.post('/v1/studio/jobs',headers=a,json=request).json()['id']
        asyncio.run(app.state.studio.process(job))
        assert c.get('/v1/studio/jobs/'+job,headers=a).json()['provenance']['estimated_tripo_credits']==25
        assert not provider.calls
        c.post('/v1/studio/jobs/'+job+'/confirm',headers=a,json=mutation())
        for _ in range(5):asyncio.run(app.state.studio.process(job))
        assert [x[0] for x in provider.calls]==['/generation/image-to-image','/generation/image-to-model']
        assert provider.calls[0][1]['input']=='private_file_token'
        assert provider.calls[1][1]['input']=='refined_reference'
        value=c.get('/v1/studio/jobs/'+job,headers=a).json()
        assert value['state']=='ready' and value['provenance']['tripo_credits_consumed']==25
        assert value['provenance']['image_refinement_credits']==5
