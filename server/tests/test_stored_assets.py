import hashlib,json
import pytest
from server.tests.test_studio import world,account,build,mutation
from server.stored_assets import read_glb
from server.provider import ProviderError

@pytest.mark.parametrize('damage',['missing','changed'])
def test_missing_or_corrupt_part_fails_closed_without_paths(world,damage):
    app,c=world;owner=account(c,'owner');stranger=account(c,'stranger')
    oid=build(app,c,owner,'chest');route='/v1/objects/'+oid
    with app.state.db.transaction() as conn:
        asset=conn.execute('SELECT asset_id FROM objects WHERE id=?',(oid,)).fetchone()[0]
        manifest=json.loads(conn.execute('SELECT manifest FROM studio_assets WHERE asset_id=?',(asset,)).fetchone()[0])
    part=manifest['plan']['parts'][1];path=app.state.settings.data_dir/'assets'/part['file']
    if damage=='missing':path.unlink()
    else:path.write_bytes(b'private corrupt server file')
    response=c.get(route+'/parts/'+part['id'],headers=owner)
    assert response.status_code==503 and response.json()=={'detail':'asset_integrity_failed'}
    assert 'private' not in response.text and str(path) not in response.text
    assert c.get(route+'/parts/'+part['id'],headers=stranger).status_code==404
    response=c.post(route+'/placement',headers=owner,json=mutation(version=1,room='home',x=2,z=0))
    assert response.status_code==503
    obj=next(o for o in c.get('/v1/me',headers=owner).json()['objects'] if o['id']==oid)
    assert obj['version']==1 and obj['state']=='inventory'

def test_shared_reader_limits_bytes_and_rejects_escape(tmp_path):
    assets=tmp_path/'assets';assets.mkdir()
    # Even a matching hash cannot permit a larger file or traversal.
    payload=b'x'*(20*1024*1024+1);(assets/'large.glb').write_bytes(payload)
    with pytest.raises(ProviderError,match='asset_integrity_failed'):
        read_glb(assets,'large.glb',hashlib.sha256(payload).hexdigest())
    (tmp_path/'outside.glb').write_bytes(b'private')
    with pytest.raises(ProviderError,match='asset_integrity_failed'):
        read_glb(assets,'../outside.glb',hashlib.sha256(b'private').hexdigest())
