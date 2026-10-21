"""One stalled design cannot stop other players, refunds or the queue."""
import asyncio
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server.asset_assembly import demo_design
from server.tests.test_studio import account, mutation
from server.tests.test_craft_reliability import SlowProvider


class Designer:
    def __init__(self):
        self.started=[]
        self.cancelled=[]

    async def generate(self,prompt,*args):
        self.started.append(prompt)
        if prompt.startswith('stalled'):
            try:await asyncio.Event().wait()
            finally:self.cancelled.append(prompt)
        plan,program=demo_design('chest')
        return plan,program,{'provider':'offline','usage':{}}


def test_stalled_design_does_not_block_new_jobs_and_times_out_once(tmp_path):
    now=[1000000.0];designer=Designer()
    settings=Settings(data_dir=tmp_path,studio_llm='openai',studio_workers=2,daily_generation_limit=100)
    app=create_app(settings,clock=lambda:now[0],designer=designer,worker_enabled=False)
    settings.studio_design_deadline=.5
    with TestClient(app) as c:
        owners=[account(c,name) for name in ('alice','bob','carol')]
        jobs=[c.post('/v1/studio/jobs',headers=h,json=mutation(prompt=prompt,designer='llm',motion='static')).json()['id']
              for h,prompt in zip(owners,('stalled chair','fast chair','later chair'))]
        now[0]+=3
        studio=app.state.studio

        async def exercise():
            await studio.tick()
            assert len(studio.tasks)==2
            # The fast job must complete while the first designer is still blocked.
            await asyncio.wait_for(studio.tasks[jobs[1]],.4)
            assert not studio.tasks[jobs[0]].done()
            await studio.tick()
            assert jobs[2] in studio.tasks
            await asyncio.wait_for(studio.tasks[jobs[2]],.4)
            await asyncio.wait_for(studio.tasks[jobs[0]],1)
            await studio.tick()
            await studio.process(jobs[0])  # terminal jobs cannot refund or call twice
        asyncio.run(exercise())
        results=[c.get('/v1/studio/jobs/'+job,headers=h).json() for job,h in zip(jobs,owners)]
        assert results[0]['state']=='failed' and results[0]['error']=='llm_timeout'
        assert results[0]['reason']=='timeout'
        assert [r['state'] for r in results[1:]]==['ready','ready']
        assert len(designer.started)==3 and len(designer.cancelled)==1
        assert c.get('/v1/me',headers=owners[0]).json()['shards']==80
        assert c.get('/v1/me',headers=owners[0]).json()['pending_craft'] is None
        with app.state.db.read() as conn:
            assert conn.execute('SELECT count(*) FROM studio_leases').fetchone()[0]==0
            assert conn.execute('SELECT count(*) FROM llm_call_reservations').fetchone()[0]==3


def test_paid_queue_is_bounded_per_server_and_single_per_owner(tmp_path):
    settings=Settings(data_dir=tmp_path,paid_enabled=True,tripo_key='offline-key',studio_workers=2,studio_queue_limit=2,daily_generation_limit=100)
    app=create_app(settings,provider=SlowProvider(),worker_enabled=False)
    with TestClient(app) as c:
        a,b,d=[account(c,name) for name in ('alice','bob','carol')]
        request=lambda h:c.post('/v1/studio/jobs',headers=h,json=mutation(prompt='stool',geometry='tripo',motion='static'))
        first=request(a);assert first.status_code==200
        assert request(b).status_code==200
        assert request(a).json()['detail']=='generation_pending'
        before=c.get('/v1/me',headers=d).json()['shards']
        assert request(d).json()['detail']=='provider_busy'
        assert c.get('/v1/me',headers=d).json()['shards']==before
        c.post('/v1/studio/jobs/'+first.json()['id']+'/cancel',headers=a,json=mutation())
        assert request(d).status_code==200


def test_orphaned_planning_job_recovers_without_restarting_server(tmp_path):
    app=create_app(Settings(data_dir=tmp_path),worker_enabled=False)
    with TestClient(app) as c:
        owner=account(c,'alice')
        job=c.post('/v1/studio/jobs',headers=owner,json=mutation(prompt='chair')).json()['id']
        with app.state.db.transaction() as conn:
            conn.execute("UPDATE studio_jobs SET state='planning' WHERE id=?",(job,))
        asyncio.run(app.state.studio.tick())
        assert c.get('/v1/studio/jobs/'+job,headers=owner).json()['state']=='failed'
        assert c.get('/v1/me',headers=owner).json()['shards']==80


def test_two_players_submit_and_finish_independent_paid_tasks(tmp_path):
    class OverlappingProvider(SlowProvider):
        async def request(self,*args):
            result=await super().request(*args)
            if len(self.calls)==2:self.both.set()
            await self.release.wait()
            return result
    provider=OverlappingProvider()
    settings=Settings(data_dir=tmp_path,paid_enabled=True,tripo_key='offline-key',daily_generation_limit=100,studio_credit_rate=.1)
    app=create_app(settings,provider=provider,worker_enabled=False)
    with TestClient(app) as c:
        owners=[account(c,name) for name in ('alice','bob')]
        jobs=[c.post('/v1/studio/jobs',headers=h,json=mutation(prompt='chair',geometry='tripo',motion='static')).json()['id'] for h in owners]
        async def quote():await asyncio.gather(*(app.state.studio.process(job) for job in jobs))
        asyncio.run(quote())
        for job,owner in zip(jobs,owners):
            assert c.post('/v1/studio/jobs/'+job+'/confirm',headers=owner,json=mutation()).status_code==200
        async def build():
            provider.both=asyncio.Event();provider.release=asyncio.Event()
            tasks=[asyncio.create_task(app.state.studio.process(job)) for job in jobs]
            try:await asyncio.wait_for(provider.both.wait(),1)
            finally:provider.release.set()
            await asyncio.gather(*tasks)
            provider.status='success'
            await asyncio.gather(*(app.state.studio.process(job) for job in jobs))
        asyncio.run(build())
        results=[c.get('/v1/studio/jobs/'+job,headers=h).json() for job,h in zip(jobs,owners)]
        assert all(r['state']=='ready' for r in results)
        assert results[0]['object_id']!=results[1]['object_id']
        assert len(provider.calls)==2
        assert c.get('/v1/studio/jobs/'+jobs[0],headers=owners[1]).status_code==404


def test_production_lifespan_runs_and_stops_the_studio_worker(tmp_path):
    import time
    now=[1000000.0]
    app=create_app(Settings(data_dir=tmp_path),clock=lambda:now[0],worker_enabled=True)
    with TestClient(app) as c:
        owner=account(c,'alice')
        job=c.post('/v1/studio/jobs',headers=owner,json=mutation(prompt='chair',motion='static')).json()['id']
        now[0]+=3
        deadline=time.monotonic()+6
        while time.monotonic()<deadline:
            state=c.get('/v1/studio/jobs/'+job,headers=owner).json()['state']
            if state=='ready':break
            time.sleep(.05)
        assert state=='ready'
    assert not app.state.studio.tasks


@pytest.mark.parametrize('fields',[{'studio_workers':0},{'studio_workers':9},{'studio_queue_limit':1},{'studio_design_deadline':0}])
def test_invalid_worker_settings_are_rejected(tmp_path,fields):
    with pytest.raises(ValueError):create_app(Settings(data_dir=tmp_path,**fields),worker_enabled=False)
