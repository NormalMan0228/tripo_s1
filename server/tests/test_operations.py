import hashlib
import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.backups import create_backup, restore_backup, verify_backup, BackupError
from server.config import Settings, read_tripo_key, configured_tripo_key


def test_secret_file_formats_and_safe_errors(tmp_path,monkeypatch):
    key=tmp_path/'secret.txt'
    key.write_text('\ufeffTRIPO_API_KEY="unit-test-secret"\n',encoding='utf-8')
    assert read_tripo_key(key)=='unit-test-secret'
    monkeypatch.delenv('TRIPO_API_KEY',raising=False)
    monkeypatch.setenv('TRIPO_API_KEY_FILE',str(key))
    assert configured_tripo_key()=='unit-test-secret'
    assert 'unit-test-secret' not in repr(Settings())
    monkeypatch.setenv('TRIPO_API_KEY','second-test-secret')
    with pytest.raises(ValueError,match='configure_only_one_tripo_key_source'):
        configured_tripo_key()
    for bad in ('unit-test-secret\r\nsecond-line','', 'x'*4097, 'Bearer unit-test-secret'):
        key.write_text(bad,encoding='utf-8')
        with pytest.raises(ValueError) as caught: read_tripo_key(key)
        assert str(caught.value)=='invalid_tripo_key_file'


def test_online_backup_restore_and_held_paid_jobs(tmp_path):
    data=tmp_path/'source'; snapshot=tmp_path/'snapshot'; restored=tmp_path/'restored'
    app=create_app(Settings(data_dir=data),worker_enabled=False)
    with TestClient(app) as client:
        credentials={'username':'backup_user','password':'Test-password-12345'}
        response=client.post('/v1/auth/register',json=credentials)
        auth={'Authorization':'Bearer '+response.json()['token']}
        job=client.post('/v1/generations',headers=auth,json={'request_id':str(uuid.uuid4()),'prompt':'wooden chair'}).json()
        me=client.get('/v1/me',headers=auth).json()
        manifest=create_backup(data,snapshot)
        assert manifest['counts']['users']==1 and manifest['counts']['objects']==1
        assert verify_backup(snapshot)==manifest
        with pytest.raises(BackupError): restore_backup(snapshot,restored,'live')
        assert not restored.exists()
        restore_backup(snapshot,restored,'demo')
        with pytest.raises(BackupError): restore_backup(snapshot,restored,'demo')
        other=create_app(Settings(data_dir=restored),worker_enabled=False)
        with TestClient(other) as recovered:
            assert recovered.get('/v1/me',headers=auth).status_code==401
            token=recovered.post('/v1/auth/login',json=credentials).json()['token']
            new_auth={'Authorization':'Bearer '+token}
            current=recovered.get('/v1/me',headers=new_auth).json()
            assert current['objects']==me['objects'] and current['shards']==55
            assert recovered.get('/v1/objects/'+me['objects'][0]['id']+'/model',headers=new_auth).content[:4]==b'glTF'
            held=recovered.get('/v1/generations/'+job['id'],headers=new_auth).json()
            assert held['state']=='unknown'
        # Restoring never revokes sessions or changes money in the original database.
        assert client.get('/v1/me',headers=auth).json()['shards']==55
    model=snapshot/'assets'/'starter.glb'
    model.write_bytes(b'tampered')
    with pytest.raises(BackupError,match='asset_digest_mismatch'): verify_backup(snapshot)


def test_backup_rejects_traversal_and_corruption(tmp_path):
    data=tmp_path/'source'
    app=create_app(Settings(data_dir=data),worker_enabled=False)
    with app.state.db.transaction() as conn:
        conn.execute("UPDATE assets SET relative_path='../secret.glb' WHERE id='starter'")
    with pytest.raises(BackupError,match='invalid_asset_path'): create_backup(data,tmp_path/'snapshot')
    assert not (tmp_path/'snapshot').exists()
    with app.state.db.transaction() as conn:
        conn.execute("UPDATE assets SET relative_path='starter.glb' WHERE id='starter'")
    create_backup(data,tmp_path/'snapshot')
    with closing(sqlite3.connect(tmp_path/'snapshot'/'world.sqlite3')) as conn:
        conn.execute("UPDATE metadata SET value='live' WHERE key='mode'")
        conn.commit()
    with pytest.raises(BackupError,match='database_digest_mismatch'): verify_backup(tmp_path/'snapshot')


def test_completed_job_is_never_delivered_twice(tmp_path):
    import asyncio
    app=create_app(Settings(data_dir=tmp_path),worker_enabled=False)
    with TestClient(app) as client:
        credentials={'username':'repeat_user','password':'Test-password-12345'}
        token=client.post('/v1/auth/register',json=credentials).json()['token']
        auth={'Authorization':'Bearer '+token}
        job=client.post('/v1/generations',headers=auth,json={'request_id':str(uuid.uuid4()),'prompt':'stool'}).json()
        asyncio.run(app.state.process_job(job['id']))
        asyncio.run(app.state.process_job(job['id']))
        assert len(client.get('/v1/me',headers=auth).json()['objects'])==2


def test_backup_restores_all_assembly_parts_edits_and_private_access(tmp_path):
    from server.tests.test_studio import account, build, mutation
    data=tmp_path/'source'; snapshot=tmp_path/'snapshot'; restored=tmp_path/'restored'
    app=create_app(Settings(data_dir=data),worker_enabled=False)
    with TestClient(app) as client:
        owner=account(client,'owner'); stranger=account(client,'stranger')
        oid=build(app,client,owner,'flower',material='textured'); route='/v1/objects/'+oid
        before=client.get(route+'/assembly',headers=owner).json()
        part=before['plan']['parts'][1]['id']
        assert client.post(route+'/bindings',headers=owner,json=mutation(version=1,part=part,pivot=[.1,0,0])).status_code==200
        assert client.post(route+'/colors',headers=owner,json=mutation(version=2,color='#bbdd44',part=part)).status_code==200
        assert client.post(route+'/event',headers=owner,json=mutation(version=3,event='click')).status_code==200
        assert client.post(route+'/placement',headers=owner,json=mutation(version=1,room='home',x=2,z=0)).status_code==200
        expected=client.get(route+'/assembly',headers=owner).json()
        inventory=client.get('/v1/studio',headers=owner).json()['objects']
        manifest=create_backup(data,snapshot)
        assert len(manifest['assets'])==9  # Eight flower parts plus starter.
        restore_backup(snapshot,restored,'demo')
        other=create_app(Settings(data_dir=restored),worker_enabled=False)
        with TestClient(other) as recovered:
            def login(name):
                response=recovered.post('/v1/auth/login',json={'username':name,'password':'Studio-test-password'})
                return {'Authorization':'Bearer '+response.json()['token']}
            new_owner=login('owner'); new_stranger=login('stranger')
            assert recovered.get(route+'/assembly',headers=owner).status_code==401
            assert recovered.get(route+'/assembly',headers=new_owner).json()==expected
            assert recovered.get('/v1/studio',headers=new_owner).json()['objects']==inventory
            for p in expected['plan']['parts']:
                response=recovered.get(route+'/parts/'+p['id'],headers=new_owner)
                assert hashlib.sha256(response.content).hexdigest()==p['sha256']
                assert recovered.get(route+'/parts/'+p['id'],headers=new_stranger).status_code==404
            assert recovered.get(route+'/assembly',headers=new_stranger).status_code==404
        secondary=before['plan']['parts'][-1]['file']
        (snapshot/'assets'/secondary).write_bytes(b'tampered-secondary-part')
        with pytest.raises(BackupError,match='asset_digest_mismatch'):verify_backup(snapshot)


def test_backup_keeps_unpublished_parts_and_holds_every_pending_job(tmp_path):
    from server.tests.test_studio import account,mutation
    from server.asset_assembly import fixture_glb
    data=tmp_path/'source'; app=create_app(Settings(data_dir=data),worker_enabled=False)
    with TestClient(app) as client:
        owner=account(client,'owner')
        job=client.post('/v1/studio/jobs',headers=owner,json=mutation(prompt='chest')).json()['id']
        blob=fixture_glb('box'); (data/'assets'/'pending-body.glb').write_bytes(blob)
        parts={'body':{'state':'ready','file':'pending-body.glb','sha256':hashlib.sha256(blob).hexdigest()},'lid':{'state':'generating','task':'known-provider-task'}}
        with app.state.db.transaction() as db:
            db.execute("UPDATE studio_jobs SET state='building',parts=? WHERE id=?",(json.dumps(parts),job))
            db.execute('INSERT INTO studio_leases VALUES (?,?,?)',(job,'old-worker',9999999999))
        manifest=create_backup(data,tmp_path/'snapshot')
        assert len(manifest['assets'])==2
        restore_backup(tmp_path/'snapshot',tmp_path/'restored','demo')
        with closing(sqlite3.connect(tmp_path/'restored'/'world.sqlite3')) as db:
            assert db.execute('SELECT state,error,parts FROM studio_jobs').fetchone()==('unknown','restore_requires_reconciliation',json.dumps(parts))
            assert db.execute('SELECT count(*) FROM studio_leases').fetchone()[0]==0
            assert db.execute('SELECT shards FROM users').fetchone()[0]==50
        assert (tmp_path/'restored'/'assets'/'pending-body.glb').read_bytes()==blob
        with app.state.db.transaction() as db:
            parts['body']['sha256']='0'*64
            parts['body']['file']='starter.glb'
            db.execute('UPDATE studio_jobs SET parts=? WHERE id=?',(json.dumps(parts),job))
        with pytest.raises(BackupError,match='conflicting_asset_digest'):create_backup(data,tmp_path/'conflict')


def test_restored_studio_reservation_requires_external_evidence_for_release(tmp_path):
    from server.tests.test_studio import account,mutation
    from server.operations import refund_studio_not_submitted,OperationError
    app=create_app(Settings(data_dir=tmp_path),worker_enabled=False)
    with TestClient(app) as client:
        owner=account(client,'owner')
        job=client.post('/v1/studio/jobs',headers=owner,json=mutation(prompt='chest')).json()['id']
        with app.state.db.transaction() as db:db.execute("UPDATE studio_jobs SET state='unknown' WHERE id=?",(job,))
        with pytest.raises(OperationError,match='confirm_provider_non_submission_required'):
            refund_studio_not_submitted(app.state.db,job,'case-123')
        with pytest.raises(OperationError,match='evidence_reference_required'):
            refund_studio_not_submitted(app.state.db,job,'',verified=True)
        with app.state.db.transaction() as db:
            db.execute('UPDATE studio_jobs SET parts=? WHERE id=?',(json.dumps({'body':{'task':'existing-paid-task','state':'generating'}}),job))
        with pytest.raises(OperationError,match='recorded_task_must_be_reconciled'):
            refund_studio_not_submitted(app.state.db,job,'case-123',verified=True)
        with app.state.db.transaction() as db:db.execute("UPDATE studio_jobs SET parts='{}' WHERE id=?",(job,))
        result=refund_studio_not_submitted(app.state.db,job,'case-123',verified=True)
        assert result['amount']==30
        assert client.get('/v1/me',headers=owner).json()['shards']==80
        with pytest.raises(OperationError,match='job_not_held'):
            refund_studio_not_submitted(app.state.db,job,'case-123',verified=True)
        with app.state.db.transaction() as db:
            assert db.execute("SELECT count(*) FROM ledger WHERE reason='studio_refund'").fetchone()[0]==1
            assert 'case-123' in db.execute("SELECT outcome FROM audit WHERE action='studio_operator_refund_not_submitted'").fetchone()[0]


def test_forest_preserves_camp_and_resource_spacing():
    import math
    from server.simulation import new_run
    for seed in range(100):
        nodes=new_run(seed,0,60)['nodes']
        assert len(nodes)==60
        for index,node in enumerate(nodes):
            assert abs(node['x'])<=17 and abs(node['z'])<=17
            if index>=4: assert math.hypot(node['x'],node['z'])>=4.5
            assert all(math.hypot(node['x']-other['x'],node['z']-other['z'])>=2.2 for other in nodes[:index])
