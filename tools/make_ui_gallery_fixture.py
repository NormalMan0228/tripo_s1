"""Record real server replies for the UI gallery test without opening a port.

Runs the FastAPI app in-process (TestClient), registers a player, plants a crop,
starts an expedition, and writes the JSON the client screens consume to
game/tests/fixtures/ui_gallery.json. The gallery replays them through a stub API.
"""
import json, sys, uuid, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings

def m(**kw): return dict(request_id=str(uuid.uuid4()), **kw)

with tempfile.TemporaryDirectory() as tmp:
    now = [1000000.]
    app = create_app(Settings(data_dir=Path(tmp), daily_generation_limit=100), clock=lambda: now[0], worker_enabled=False)
    with TestClient(app) as c:
        r = c.post('/v1/auth/register', json={'username': 'haneul', 'password': 'Testing-only-12345'})
        auth = {'Authorization': 'Bearer ' + r.json()['token']}
        out = {'/health': c.get('/health').json()}
        home = c.get('/v1/homestead', headers=auth).json()
        home = c.post('/v1/homestead', headers=auth, json=m(version=home['version'], action='plant', item='turnip', plot=0)).json()
        out['/v1/homestead'] = c.get('/v1/homestead', headers=auth).json()
        out['/v1/me'] = c.get('/v1/me', headers=auth).json()
        social = c.get('/v1/social', headers=auth)
        if social.status_code == 200: out['/v1/social'] = social.json()
        studio = c.get('/v1/studio', headers=auth)
        if studio.status_code == 200: out['/v1/studio'] = studio.json()
        run = c.post('/v1/runs', headers=auth, json=m(map_id='forest', difficulty='standard', chapter_id='')).json()
        out['run'] = c.get('/v1/runs/' + run['id'], headers=auth).json()
(ROOT / 'game/tests/fixtures').mkdir(parents=True, exist_ok=True)
(ROOT / 'game/tests/fixtures/ui_gallery.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
print('wrote', len(json.dumps(out)), 'bytes:', ', '.join(out))
