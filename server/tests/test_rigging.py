import asyncio
import copy
import json
import struct
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.asset_studio import tripo_credits_committed, billing
from server.config import Settings
from server.fake_tripo import transport
from server.provider import ProviderError, TripoProvider, validate_glb
from server.rigged_glb import fixture_rigged_glb, merge_clips, pack, unpack, validate_rigged_glb


def mutation(**kwargs):
    return {'request_id':str(uuid.uuid4()), **kwargs}


@pytest.fixture
def world(tmp_path):
    settings=Settings(data_dir=tmp_path,mode='live',paid_enabled=True,fake_tripo=True,environment='staging',
                      registration_code='test-only-invitation-123456',rig_anim_enabled=True,
                      max_credits_per_craft=200,tripo_credit_budget=1000)
    app=create_app(settings,worker_enabled=False)
    fake=transport(); calls=[]; tasks={}; faults={}
    def handle(request):
        path=request.url.path
        if request.url.host=='fake.tripo3d.ai' and '/fake-a-' in path:
            if faults.pop('download_once',False):return httpx.Response(503)
            if faults.get('static_download'):
                from server.asset_assembly import fixture_glb
                return httpx.Response(200,content=fixture_glb('box'))
        if request.method=='POST':
            payload=json.loads(request.content)
            calls.append((path,payload))
            if faults.get('uncertain') and path.endswith(faults['uncertain']):
                raise httpx.ReadTimeout('ambiguous',request=request)
        if '/tasks/' in path:
            task=path.rsplit('/',1)[-1];kind=tasks[task]
            if faults.get('poll_once')==kind:
                faults.pop('poll_once')
                return httpx.Response(503,json={'code':1})
            result=fake.handle_request(request).json()
            result['data']['credits_consumed']={'text-to-model':10,'image-to-model':20,'text-to-image':5,'rig':25,'retarget':10}[kind]
            if faults.get('fail')==kind:result['data']['status']='failed'
            if faults.get('running')==kind:result['data']['status']='running'
            return httpx.Response(200,json=result)
        response=fake.handle_request(request)
        if request.method=='POST' and response.status_code==200:
            tasks[response.json()['data']['task_id']]=path.rsplit('/',1)[-1]
        return response
    app.state.studio.provider=TripoProvider(settings,httpx.MockTransport(handle))
    with TestClient(app,base_url='https://testserver') as c:
        auth=c.post('/v1/auth/register',json={'username':'riguser','password':'Rig-test-password',
                                            'invitation':settings.registration_code})
        h={'Authorization':'Bearer '+auth.json()['token']}
        with app.state.db.transaction() as db:db.execute('UPDATE users SET shards=500')
        yield app,c,h,calls,faults


def queue(world, **changes):
    app,c,h,_,_=world
    return c.post('/v1/studio/jobs',headers=h,json=mutation(prompt='friendly robot character',animate=True,
        geometry='tripo',designer='simple',mesh_model='v3.1-20260211',**changes))


def start(world, **changes):
    app,c,h,_,_=world
    response=queue(world,**changes);assert response.status_code==200,response.text
    job=response.json()['id'];asyncio.run(app.state.studio.process(job))
    quote=c.get('/v1/studio/jobs/'+job,headers=h).json()
    assert quote['state']=='awaiting_confirmation',quote
    response=c.post('/v1/studio/jobs/'+job+'/confirm',headers=h,json=mutation())
    assert response.status_code==200,response.text
    return job,quote


def finish(world,job):
    app,c,h,_,_=world;states=[]
    for _ in range(25):
        asyncio.run(app.state.studio.process(job))
        status=c.get('/v1/studio/jobs/'+job,headers=h).json();states.append(status['stage'])
        if status['state'] in ('ready','failed','unknown'):return status,states
    raise AssertionError(status)


@pytest.mark.xfail(reason='rig credit accounting is not yet ported to tripo_budget attempts (codex/budgetsafe); TRIPOTHON_RIG_ANIM_ENABLED stays off on the main server', strict=False)
@pytest.mark.parametrize('concept',[False,True])
def test_success_chain_reserves_and_exposes_real_clips(world,concept):
    app,c,h,calls,_=world
    assert c.get('/v1/studio',headers=h).json()['rigging']['clips']==['idle','walk']
    job,quote=start(world,concept=concept)
    expected=70 if concept else 55
    assert quote['provenance']['estimated_tripo_credits']==expected
    with app.state.db.transaction() as db:assert tripo_credits_committed(db)==expected
    status,states=finish(world,job)
    assert status['state']=='ready',status
    assert 'rig' in states and 'rig' in status['stages']
    rig=status['provenance']['rig']
    assert rig['moves'] is True and rig['clips']==['idle','walk'] and rig['default_clip']=='idle'
    assert status['provenance']['tripo_credits_consumed']==expected
    routes=[path.rsplit('/',1)[-1] for path,_ in calls]
    assert routes==(['text-to-image','image-to-model'] if concept else ['text-to-model'])+['rig','retarget','retarget']
    assert 'A-pose' in calls[0][1]['prompt']
    assert calls[-2][1]['animation']=='preset:biped:idle' and calls[-1][1]['animation']=='preset:biped:walk'
    assert calls[-1][1]['input']==calls[-2][1]['input']
    oid=status['object_id'];assembly=c.get('/v1/objects/'+oid+'/assembly',headers=h).json()
    assert assembly['provenance']['rig']==rig
    assert len(assembly['plan']['parts'])==1 and not assembly['program']['events']
    part=assembly['plan']['parts'][0]
    blob=c.get('/v1/objects/'+oid+'/parts/'+part['id'],headers=h).content
    stats={};validate_rigged_glb(blob,stats=stats)
    assert stats['clips']==['idle','walk']
    listing=c.get('/v1/studio',headers=h).json()['objects'][0]
    assert listing['moves'] and listing['clips']==['idle','walk']
    placement=c.post('/v1/objects/'+oid+'/placement',headers=h,json=mutation(version=1,room='home',x=2,z=0))
    assert placement.status_code==200,placement.text
    with app.state.db.transaction() as db:assert tripo_credits_committed(db)==expected


@pytest.mark.xfail(reason='rig credit accounting is not yet ported to tripo_budget attempts (codex/budgetsafe); TRIPOTHON_RIG_ANIM_ENABLED stays off on the main server', strict=False)
@pytest.mark.parametrize('failure,code,spent',[('rig','rig_failed',35),('retarget','animation_failed',45)])
def test_failure_refunds_once_but_keeps_provider_spend(world,failure,code,spent):
    app,c,h,calls,faults=world;faults['fail']=failure
    job,_=start(world);status,_=finish(world,job)
    assert status['state']=='failed' and status['error']==code,status
    assert c.get('/v1/me',headers=h).json()['shards']==500
    for _ in range(2):asyncio.run(app.state.studio.process(job))
    assert c.get('/v1/me',headers=h).json()['shards']==500
    with app.state.db.transaction() as db:
        assert tripo_credits_committed(db)==spent
        assert db.execute('SELECT count(*) FROM studio_assets').fetchone()[0]==0


def test_disabled_and_character_gate_without_paid_requests(world):
    app,c,h,calls,_=world
    app.state.settings.rig_anim_enabled=False
    assert 'rigging' not in c.get('/v1/studio',headers=h).json()
    assert queue(world).json()['detail']=='rigging_disabled'
    app.state.settings.rig_anim_enabled=True
    response=c.post('/v1/studio/jobs',headers=h,json=mutation(prompt='wooden chair',animate=True,geometry='tripo',designer='simple'))
    assert response.json()['detail']=='animate_requires_character'
    assert calls==[]


@pytest.mark.parametrize('field,code',[('max_credits_per_craft','craft_over_trial_limit'),('tripo_credit_budget','tripo_budget_exhausted')])
def test_combined_cost_rejected_before_charge_or_provider(world,field,code):
    app,c,h,calls,_=world
    setattr(app.state.settings,field,54)
    assert queue(world).json()['detail']==code
    assert calls==[] and c.get('/v1/me',headers=h).json()['shards']==500


def test_budget_rechecked_at_confirmation(world):
    app,c,h,calls,_=world
    job=queue(world).json()['id'];asyncio.run(app.state.studio.process(job))
    app.state.settings.tripo_credit_budget=54
    response=c.post('/v1/studio/jobs/'+job+'/confirm',headers=h,json=mutation())
    assert response.json()['detail']=='tripo_budget_exhausted' and calls==[]


@pytest.mark.parametrize('kind',['rig','retarget'])
def test_transient_poll_retry_keeps_task_and_submission_count(world,kind):
    app,c,h,calls,faults=world;faults['poll_once']=kind
    job,_=start(world);status,_=finish(world,job)
    assert status['state']=='ready',status
    assert len(calls)==4


@pytest.mark.xfail(reason='rig credit accounting is not yet ported to tripo_budget attempts (codex/budgetsafe); TRIPOTHON_RIG_ANIM_ENABLED stays off on the main server', strict=False)
@pytest.mark.parametrize('kind',['rig','retarget'])
def test_ambiguous_submission_holds_reservation_without_resubmit(world,kind):
    app,c,h,calls,faults=world;faults['uncertain']=kind
    job,_=start(world);status,_=finish(world,job)
    assert status['state']=='unknown',status
    count=len(calls)
    asyncio.run(app.state.studio.process(job))
    assert len(calls)==count
    with app.state.db.transaction() as db:assert tripo_credits_committed(db)==55
    assert c.get('/v1/me',headers=h).json()['shards']==445


def test_animation_deadline_refunds(world):
    app,c,h,calls,faults=world;faults['running']='rig'
    job,_=start(world)
    for _ in range(3):asyncio.run(app.state.studio.process(job))
    with app.state.db.transaction() as db:
        row=db.execute('SELECT parts FROM studio_jobs WHERE id=?',(job,)).fetchone()
        parts=json.loads(row[0]);entry=next(iter(parts.values()));assert entry['state']=='rigging'
        entry['submitted']=0
        db.execute('UPDATE studio_jobs SET parts=? WHERE id=?',(json.dumps(parts),job))
    status,_=finish(world,job)
    assert status['state']=='failed' and status['error']=='generation_timeout'
    assert c.get('/v1/me',headers=h).json()['shards']==500


def test_rigged_validation_is_opt_in_and_bounded():
    blob=fixture_rigged_glb(('idle','walk'));stats={}
    validate_rigged_glb(blob,stats=stats)
    assert stats['bones']==2 and stats['clips']==['idle','walk']
    with pytest.raises(ProviderError):validate_glb(blob)
    with pytest.raises(ProviderError):validate_rigged_glb(blob[:-1])
    with pytest.raises(ProviderError):validate_rigged_glb(blob+b'\0'*(20*1024*1024))


@pytest.mark.parametrize('change',[
    lambda d:d['buffers'][0].update(uri='https://example.invalid/a'),
    lambda d:d['nodes'][0].update(extensions={}),
    lambda d:d.update(extensionsRequired=['evil']),
    lambda d:d['skins'].append(copy.deepcopy(d['skins'][0])),
    lambda d:d['skins'][0].update(joints=list(range(129))),
    lambda d:d['accessors'][d['skins'][0]['inverseBindMatrices']].update(count=1),
    lambda d:d.update(animations=d['animations']*9),
    lambda d:d['animations'][0].update(channels=d['animations'][0]['channels']*513),
    lambda d:d['animations'][0]['channels'][0]['target'].update(path='weights'),
    lambda d:d['animations'][0]['channels'][0]['target'].update(node=-1),
    lambda d:d['meshes'][0]['primitives'][0].update(targets=[]),
    lambda d:d['animations'][0]['samplers'][0].update(interpolation='CUBICSPLINE'),
])
def test_reject_malformed_rig_structure(change):
    doc,data=unpack(fixture_rigged_glb());change(doc)
    with pytest.raises(ProviderError):validate_rigged_glb(pack(doc,data))


@pytest.mark.parametrize('target,row,values_',[
    ('time',1,(float('nan'),)),('time',2,(61,)),('time',1,(0,)),
    ('rotation',1,(0,0,0,0)),('rotation',1,(0,0,0,1)),
    ('joints',0,(2,0,0,0)),('weights',0,(0,0,0,0)),
])
def test_reject_bad_binary_animation_values(target,row,values_):
    doc,data=unpack(fixture_rigged_glb());data=bytearray(data)
    primitive=doc['meshes'][0]['primitives'][0];sampler=doc['animations'][0]['samplers'][0]
    index={'time':sampler['input'],'rotation':sampler['output'],'joints':primitive['attributes']['JOINTS_0'],
           'weights':primitive['attributes']['WEIGHTS_0']}[target]
    accessor=doc['accessors'][index];view=doc['bufferViews'][accessor['bufferView']]
    fmt='<' + ('B' if target=='joints' else 'f')*len(values_)
    struct.pack_into(fmt,data,view.get('byteOffset',0)+row*struct.calcsize(fmt),*values_)
    with pytest.raises(ProviderError):validate_rigged_glb(pack(doc,bytes(data)))


def test_merge_rejects_mismatching_rest_skeleton():
    blob=fixture_rigged_glb();doc,data=unpack(blob)
    doc['nodes'][2]['translation']=[0,1,0]
    with pytest.raises(ProviderError,match='animation_skeleton_mismatch'):
        merge_clips({'idle':blob,'walk':pack(doc,data)})


def test_environment_flag_defaults_off(monkeypatch,tmp_path):
    monkeypatch.delenv('TRIPOTHON_RIG_ANIM_ENABLED',raising=False)
    assert Settings(data_dir=tmp_path).rig_anim_enabled is False
    monkeypatch.setenv('TRIPOTHON_RIG_ANIM_ENABLED','true')
    assert Settings(data_dir=tmp_path).rig_anim_enabled is True


def test_restart_after_rig_submit_boundary_never_resubmits(world):
    app,c,h,calls,_=world;job,_=start(world)
    for _ in range(2):asyncio.run(app.state.studio.process(job))
    with app.state.db.transaction() as db:
        parts=json.loads(db.execute('SELECT parts FROM studio_jobs WHERE id=?',(job,)).fetchone()[0])
        assert next(iter(parts.values()))['state']=='rig_pending'
        db.execute("UPDATE studio_jobs SET state='submitting' WHERE id=?",(job,))
    restarted=create_app(app.state.settings,provider=app.state.studio.provider,worker_enabled=False)
    count=len(calls);asyncio.run(restarted.state.studio.process(job))
    status=c.get('/v1/studio/jobs/'+job,headers=h).json()
    assert status['state']=='unknown' and status['error']=='submission_interrupted'
    assert len(calls)==count
    with app.state.db.transaction() as db:assert tripo_credits_committed(db)==55


def test_known_rig_task_survives_restart(world):
    app,c,h,calls,_=world;job,_=start(world)
    for _ in range(3):asyncio.run(app.state.studio.process(job))
    restarted=create_app(app.state.settings,provider=app.state.studio.provider,worker_enabled=False)
    restarted_world=(restarted,c,h,calls,{})
    status,_=finish(restarted_world,job)
    assert status['state']=='ready' and len(calls)==4


@pytest.mark.xfail(reason='rig credit accounting is not yet ported to tripo_budget attempts (codex/budgetsafe); TRIPOTHON_RIG_ANIM_ENABLED stays off on the main server', strict=False)
def test_tester_budget_reserves_the_entire_chain(world):
    app,c,h,calls,_=world
    with app.state.db.transaction() as db:db.execute('UPDATE users SET is_tester=1')
    app.state.settings.tester_credit_budget=54
    assert queue(world).json()['detail']=='tester_credit_budget_exhausted' and calls==[]
    app.state.settings.tester_credit_budget=55
    job,_=start(world)
    with app.state.db.transaction() as db:
        assert db.execute('SELECT credits FROM tester_credit_spend WHERE reference=?',(job+':build',)).fetchone()[0]==55


def test_turning_flag_off_stops_paid_steps_and_can_resume(world):
    app,c,h,calls,_=world;job,_=start(world)
    for _ in range(2):asyncio.run(app.state.studio.process(job))
    app.state.settings.rig_anim_enabled=False
    count=len(calls);asyncio.run(app.state.studio.process(job))
    status=c.get('/v1/studio/jobs/'+job,headers=h).json()
    assert status['state']=='building' and status['error']=='rigging_disabled' and len(calls)==count
    app.state.settings.rig_anim_enabled=True
    status,_=finish(world,job)
    assert status['state']=='ready' and len(calls)==4


@pytest.mark.xfail(reason='rig credit accounting is not yet ported to tripo_budget attempts (codex/budgetsafe); TRIPOTHON_RIG_ANIM_ENABLED stays off on the main server', strict=False)
def test_missing_rig_bill_retains_full_reservation(world):
    app,c,h,_,_=world;job,_=start(world);status,_=finish(world,job)
    assert status['state']=='ready'
    with app.state.db.transaction() as db:
        parts=json.loads(db.execute('SELECT parts FROM studio_jobs WHERE id=?',(job,)).fetchone()[0])
        next(iter(parts.values()))['rig'].pop('credits_consumed')
        assert billing(parts)['billing_complete'] is False
        db.execute('UPDATE studio_jobs SET parts=? WHERE id=?',(json.dumps(parts),job))
        assert tripo_credits_committed(db)==55


def test_ordinary_download_rejects_animated_assets(world):
    app,_,_,_,_=world
    provider=app.state.studio.provider
    async def run():
        data=await provider.request('POST','/animations/retarget',{'input':'mock-rig','animation':'preset:biped:idle'})
        result=await provider.task(data['task_id'])
        with pytest.raises(ProviderError):await provider.download(result['output']['model_url'])
        await provider.download(result['output']['model_url'],rigged=True)
    asyncio.run(run())


def test_animation_download_retries_without_retarget_charge(world):
    app,c,h,calls,faults=world;faults['download_once']=True
    job,_=start(world);status,_=finish(world,job)
    assert status['state']=='ready' and len(calls)==4
    assert status['provenance']['tripo_credits_consumed']==55


def test_static_retarget_output_fails_validation_and_refunds(world):
    app,c,h,calls,faults=world;faults['static_download']=True
    job,_=start(world);status,_=finish(world,job)
    assert status['state']=='failed' and status['error']=='invalid_model'
    assert c.get('/v1/me',headers=h).json()['shards']==500
    assert len(calls)==3


@pytest.mark.xfail(reason='rig credit accounting is not yet ported to tripo_budget attempts (codex/budgetsafe); TRIPOTHON_RIG_ANIM_ENABLED stays off on the main server', strict=False)
def test_provider_overrun_stops_next_paid_stage(world):
    app,c,h,calls,_=world;job,_=start(world)
    for _ in range(4):asyncio.run(app.state.studio.process(job))
    with app.state.db.transaction() as db:
        parts=json.loads(db.execute('SELECT parts FROM studio_jobs WHERE id=?',(job,)).fetchone()[0])
        entry=next(iter(parts.values()));assert entry['state']=='animation_pending'
        entry['rig']['credits_consumed']=180
        db.execute('UPDATE studio_jobs SET parts=? WHERE id=?',(json.dumps(parts),job))
    status,_=finish(world,job)
    assert status['state']=='failed' and status['error']=='craft_over_trial_limit'
    assert len(calls)==2
