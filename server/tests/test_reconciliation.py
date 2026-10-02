import asyncio
import uuid
import httpx
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings,ROOT
from server.operations import OperationError,attach_task,refund_not_submitted
from server.provider import TripoProvider


@pytest.fixture
def held(tmp_path):
    calls=[]
    def handler(req):
        calls.append((req.method,req.url.path))
        if req.url.host=='cdn.tripo3d.ai': return httpx.Response(200,content=(ROOT/'game/assets/sample_stool.glb').read_bytes())
        if req.method=='POST': raise httpx.ReadTimeout('mock uncertain submission')
        if req.url.path.endswith('/balance'): return httpx.Response(200,json={'code':0,'data':{'balance':1000}})
        return httpx.Response(200,json={'code':0,'data':{'status':'success','output':{'model_url':'https://cdn.tripo3d.ai/confirmed.glb'}}})
    settings=Settings(data_dir=tmp_path,mode='live',registration_code='test-only-invitation-123456',tripo_key='test-placeholder',paid_enabled=True)
    app=create_app(settings,provider=TripoProvider(settings,httpx.MockTransport(handler)),worker_enabled=False)
    with TestClient(app,base_url='https://testserver') as client:
        response=client.post('/v1/auth/register',json={'username':'operator_test','password':'testing-only-password','invitation':settings.registration_code})
        auth={'Authorization':'Bearer '+response.json()['token']}
        with app.state.db.transaction() as conn: conn.execute('UPDATE users SET shards=100')
        job=client.post('/v1/generations',headers=auth,json={'request_id':str(uuid.uuid4()),'prompt':'wooden stool'}).json()['id']
        asyncio.run(app.state.process_job(job))
        assert client.get('/v1/generations/'+job,headers=auth).json()['state']=='unknown'
        yield app,client,auth,job,calls


def test_recovered_task_polls_without_another_paid_submission(held):
    app,client,auth,job,calls=held
    with pytest.raises(OperationError): attach_task(app.state.db,job,'verified-task','unknown','case-001')
    attach_task(app.state.db,job,'verified-task','success','case-001')
    asyncio.run(app.state.process_job(job))
    assert client.get('/v1/generations/'+job,headers=auth).json()['state']=='ready'
    assert client.get('/v1/me',headers=auth).json()['shards']==75
    assert sum(method=='POST' for method,path in calls)==1
    with pytest.raises(OperationError): attach_task(app.state.db,job,'verified-task','success','case-001')
    with app.state.db.transaction() as conn:
        assert conn.execute("SELECT count(*) FROM audit WHERE action='operator_attach_task'").fetchone()[0]==1


def test_operator_refund_requires_evidence_and_cannot_repeat(held):
    app,client,auth,job,calls=held
    with pytest.raises(OperationError): refund_not_submitted(app.state.db,job,'case-002')
    assert client.get('/v1/me',headers=auth).json()['shards']==75
    refund_not_submitted(app.state.db,job,'case-002',verified=True)
    assert client.get('/v1/me',headers=auth).json()['shards']==100
    with pytest.raises(OperationError): refund_not_submitted(app.state.db,job,'case-002',verified=True)
    assert client.get('/v1/me',headers=auth).json()['shards']==100


def test_known_provider_task_cannot_be_replaced_or_refunded_as_unsubmitted(held):
    app,client,auth,job,calls=held
    with app.state.db.transaction() as conn: conn.execute('UPDATE jobs SET provider_task=? WHERE id=?',('original-task',job))
    with pytest.raises(OperationError): attach_task(app.state.db,job,'different-task','success','case-003')
    with pytest.raises(OperationError): refund_not_submitted(app.state.db,job,'case-003',verified=True)
    assert client.get('/v1/me',headers=auth).json()['shards']==75
