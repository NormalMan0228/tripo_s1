"""Paid four-view boundaries, restart, fallback choices and budget accounting."""
import json
import pytest
from server import tripo_budget
from server.asset_studio import build_progress
from server.provider import ProviderError
from server.studio_multiview import output_views
from server.tests.test_concept import Provider as BaseProvider, world, run
from server.tests.test_studio import account, mutation


class Provider(BaseProvider):
    def __init__(self, mode='', mesh_credits=30):
        super().__init__();self.mode=mode;self.mesh_credits=mesh_credits;self.polls=[]
    async def request(self, method, path, payload):
        if path.endswith('image-to-multiview'):
            self.calls.append((path,payload))
            if self.mode=='ambiguous':raise ProviderError('upstream_unreachable',uncertain=True)
            return {'task_id':'views-1'}
        return await super().request(method,path,payload)
    async def task(self, task):
        self.polls.append(task)
        if task=='views-1':
            if self.mode=='transient':
                self.mode='';raise ProviderError('upstream_unavailable')
            if self.mode=='running':return {'status':'running','progress':50}
            if self.mode=='failed':return {'status':'failed','credits_consumed':10}
            return {'status':'success','credits_consumed':10,'output':{'generate_multiview_image':{
                v+'_view_url':'https://tripo-data.example.tripo3d.com/'+v+'.png' for v in ('front','left','back','right')}}}
        result=await super().task(task)
        if task.startswith('mesh'):result['credits_consumed']=self.mesh_credits
        return result


def start(app,c,owner,**changes):
    body=dict(prompt='robot character with a red scarf',geometry='tripo',designer='simple',motion='static',
              material='textured',mesh_model='v3.1-20260211',concept=True)
    body.update(changes)
    response=c.post('/v1/studio/jobs',headers=owner,json=mutation(**body))
    assert response.status_code==200,response.text
    job=response.json()['id'];run(app,job)
    return job


def confirm(c,owner,job,**changes):
    result=c.post('/v1/studio/jobs/'+job+'/confirm',headers=owner,json=mutation(**changes))
    assert result.status_code==200,result.text
    return result.json()


@pytest.mark.parametrize('model,mesh_cost',[('v3.1-20260211',30),('P2-20260801',110)])
def test_four_views_are_inputs_and_only_owner_can_read_them(tmp_path,model,mesh_cost):
    provider=Provider(mesh_credits=mesh_cost);app,client=world(tmp_path,provider,welcome_stars=500)
    with client as c:
        owner=account(c,'alice');other=account(c,'bob')
        with app.state.db.transaction() as conn:conn.execute('UPDATE users SET shards=1000')
        job=start(app,c,owner,mesh_model=model)
        quote=c.get('/v1/studio/jobs/'+job,headers=owner).json()
        assert quote['concept']['estimate_with_concept']==mesh_cost+15
        assert confirm(c,owner,job)['estimate']==mesh_cost+15
        with app.state.db.read() as conn:
            assert tripo_budget.committed_credits(conn)==mesh_cost+15
        run(app,job,5)
        value=c.get('/v1/studio/jobs/'+job,headers=owner).json()
        assert value['state']=='ready',value
        assert value['provenance']['tripo_credits_consumed']==mesh_cost+15
        assert [p for p,_ in provider.calls]==['/generation/text-to-image','/generation/image-to-multiview','/generation/multiview-to-model']
        payload=provider.calls[-1][1]
        assert 'input' not in payload and 'prompt' not in payload
        assert payload['model']==model and [list(v)[0] for v in payload['inputs']]==['front','left','back','right']
        assert len(provider.uploads)==5
        assert set(value['multiview_images'])=={'front','left','back','right'}
        for url in value['multiview_images'].values():
            assert c.get(url,headers=owner).content[:2]==b'\xff\xd8'
            assert c.get(url,headers=other).status_code==404
            assert c.get(url).status_code==401


@pytest.mark.parametrize('choice',['text','disabled','legacy'])
def test_explicit_text_single_view_and_old_jobs_do_not_pay_for_views(tmp_path,choice):
    provider=Provider();app,client=world(tmp_path,provider)
    with client as c:
        owner=account(c,'alice')
        job=start(app,c,owner,**({'multiview':False} if choice=='disabled' else {}))
        if choice=='legacy':
            with app.state.db.transaction() as conn:
                row=conn.execute('SELECT request FROM studio_jobs WHERE id=?',(job,)).fetchone()
                body=json.loads(row['request']);body.pop('multiview')
                conn.execute('UPDATE studio_jobs SET request=? WHERE id=?',(json.dumps(body),job))
        confirm(c,owner,job,use_concept=choice!='text');run(app,job,4)
        assert not any('multiview' in path for path,_ in provider.calls)


def test_restart_and_transient_poll_keep_one_paid_task(tmp_path):
    provider=Provider(mode='transient');app,client=world(tmp_path,provider)
    with client as c:
        owner=account(c,'alice');job=start(app,c,owner);confirm(c,owner,job)
        run(app,job)  # POST accepted, ID durable
        run(app,job)  # transient poll failure
        row=app.state.db
        with row.read() as conn:
            data=dict(conn.execute('SELECT * FROM studio_jobs WHERE id=?',(job,)).fetchone())
            assert data['state']=='building'
            assert next(iter(json.loads(data['parts']).values()))['multiview_task']=='views-1'
    # Recreate the application against the same database and saved reference files.
    restarted,client=world(tmp_path,provider)
    with client as c:
        run(restarted,job,5)
        assert c.get('/v1/studio/jobs/'+job,headers=owner).json()['state']=='ready'
        assert len([p for p,_ in provider.calls if p.endswith('image-to-multiview')])==1


@pytest.mark.parametrize('mode,state',[('ambiguous','unknown'),('failed','failed')])
def test_failed_or_ambiguous_views_never_submit_a_mesh_or_repeat_paid_post(tmp_path,mode,state):
    provider=Provider(mode=mode);app,client=world(tmp_path,provider)
    with client as c:
        owner=account(c,'alice');job=start(app,c,owner);confirm(c,owner,job)
        run(app,job,6)
        status=c.get('/v1/studio/jobs/'+job,headers=owner).json()
        assert status['state']==state,status
        assert [p for p,_ in provider.calls]==['/generation/text-to-image','/generation/image-to-multiview']
        with app.state.db.read() as conn:
            assert tripo_budget.attempt_credits(conn,job)==15
            if mode=='ambiguous':assert not tripo_budget.job_billing(conn,job)['billing_complete']


def test_multiview_cost_is_rejected_before_any_paid_call(tmp_path):
    provider=Provider();app,client=world(tmp_path,provider,mode='live',registration_code='test-only-invitation-123456',
                                    max_credits_per_craft=44,welcome_stars=500,llm_key='test-only-llm')
    with client as c:
        token=c.post('/v1/auth/register',json={'username':'alice','password':'Test-password-123','invitation':'test-only-invitation-123456'}).json()['token']
        response=c.post('/v1/studio/jobs',headers={'Authorization':'Bearer '+token},json=mutation(
            prompt='robot character',geometry='tripo',designer='simple',motion='static',material='textured',
            mesh_model='v3.1-20260211',concept=True))
        assert response.status_code==403 and response.json()['detail']=='craft_over_trial_limit'
        assert provider.calls==[]


def test_timeout_is_finite_and_progress_stays_bounded(tmp_path):
    provider=Provider(mode='running');app,client=world(tmp_path,provider)
    with client as c:
        owner=account(c,'alice');job=start(app,c,owner);confirm(c,owner,job);run(app,job)
        with app.state.db.transaction() as conn:
            row=conn.execute('SELECT parts FROM studio_jobs WHERE id=?',(job,)).fetchone()
            parts=json.loads(row['parts']);next(iter(parts.values()))['submitted']=0
            conn.execute('UPDATE studio_jobs SET parts=? WHERE id=?',(json.dumps(parts),job))
        run(app,job)
        status=c.get('/v1/studio/jobs/'+job,headers=owner).json()
        assert status['state']=='failed' and status['error']=='generation_timeout'
    assert build_progress({'p':{'state':'multiview_generating','multiview_task':'v','progress':50}})==.1


def test_documented_and_live_output_shapes_and_missing_view():
    flat={v+'_view_url':'https://example.test/'+v for v in ('front','left','back','right')}
    assert output_views(flat)==output_views({'generate_multiview_image':flat})
    flat.pop('back_view_url')
    with pytest.raises(ProviderError):output_views(flat)


def test_mesh_retry_reuses_four_views(tmp_path):
    class RetryProvider(Provider):
        first=True
        async def task(self,task):
            if task.startswith('mesh') and self.first:
                self.first=False;return {'status':'failed','credits_consumed':0}
            return await super().task(task)
    provider=RetryProvider();app,client=world(tmp_path,provider,studio_retries=1)
    with client as c:
        owner=account(c,'alice');job=start(app,c,owner);confirm(c,owner,job);run(app,job,8)
        assert c.get('/v1/studio/jobs/'+job,headers=owner).json()['state']=='ready'
        assert len([p for p,_ in provider.calls if p.endswith('image-to-multiview')])==1
        assert len([p for p,_ in provider.calls if p.endswith('multiview-to-model')])==2
