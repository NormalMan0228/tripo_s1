"""Text-only crafts draw a concept picture first (Tripo text-to-image, 5 credits); the player approves it
(3D from the picture), redraws it, or builds from the text instead."""
import asyncio, io
from fastapi.testclient import TestClient
from PIL import Image
from server.app import create_app
from server.config import Settings
from server.provider import ProviderError, jpeg_preview
from server.asset_assembly import demo_design, fixture_glb
from server.tests.test_studio import mutation, account


class Provider:
    def __init__(self, fail_concept=False):
        self.calls = []
        self.fail_concept = fail_concept
    async def balance(self): return 10000
    async def request(self, method, path, payload):
        self.calls.append((path, payload))
        if path.endswith('text-to-image'): return {'task_id': 'concept-%d' % len(self.calls)}
        return {'task_id': 'mesh-%d' % len(self.calls)}
    async def task(self, task):
        if task.startswith('concept'):
            if self.fail_concept: return {'status': 'failed'}
            return {'status': 'success', 'credits_consumed': 5, 'output': {'generated_image': 'https://tripo-data.example.tripo3d.com/c.webp'}}
        return {'status': 'success', 'credits_consumed': 30, 'output': {'model_url': 'private-test-model'}}
    async def fetch_image(self, url):
        raw = io.BytesIO(); Image.new('RGB', (64, 48), 'orange').save(raw, 'PNG')
        return jpeg_preview(raw.getvalue())
    async def download(self, url, allow_textures=False): return fixture_glb('box', allow_textures)


class Designer:
    async def generate(self, *args): return (*demo_design('chest'), {'provider': 'mock_designer'})


def world(tmp_path, provider, **extra):
    options = {'studio_llm': 'openai', **extra}
    settings = Settings(data_dir=tmp_path, paid_enabled=True, tripo_key='private-test-key', daily_generation_limit=100, **options)
    app = create_app(settings, provider=provider, designer=Designer(), worker_enabled=False)
    app.state.studio.poll_pause = 0
    return app, TestClient(app, base_url='https://testserver')


def craft(**kw):
    return mutation(prompt='a cosy chest', geometry='tripo', designer='llm', motion='static', material='textured',
                    mesh_model='v3.1-20260211', concept=True, **kw)


def run(app, job, times=1):
    for _ in range(times): asyncio.run(app.state.studio.process(job))


def test_approved_concept_becomes_the_3d_reference(tmp_path):
    provider = Provider(); app, client = world(tmp_path, provider)
    with client as c:
        a = account(c, 'alice')
        job = c.post('/v1/studio/jobs', headers=a, json=craft()).json()['id']
        run(app, job)
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['state'] == 'awaiting_confirmation'
        assert value['concept']['draws'] == 1 and value['concept']['estimate_with_concept'] == 35 and value['concept']['estimate_text_only'] == 25
        assert value['design']['parts'][0]['prompt']  # the AI text is shown with the picture
        picture = c.get(value['concept']['url'], headers=a)
        assert picture.status_code == 200 and picture.headers['content-type'] == 'image/jpeg' and picture.content[:2] == b'\xff\xd8'
        assert c.get(value['concept']['url']).status_code == 401
        assert [p for p, _ in provider.calls] == ['/generation/text-to-image']
        assert 'Concept art' in provider.calls[0][1]['prompt']
        assert c.post('/v1/studio/jobs/' + job + '/confirm', headers=a, json=mutation(use_concept=True)).status_code == 200
        run(app, job, 4)
        assert [p for p, _ in provider.calls] == ['/generation/text-to-image', '/generation/image-to-model']
        assert provider.calls[1][1]['input'] == 'concept-1'
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['state'] == 'ready' and value['provenance']['tripo_credits_consumed'] == 35
        assert value['provenance']['image_path'] == 'approved_concept_image_to_tripo'


def test_redraw_then_build_from_text_instead(tmp_path):
    provider = Provider(); app, client = world(tmp_path, provider)
    with client as c:
        a = account(c, 'alice')
        job = c.post('/v1/studio/jobs', headers=a, json=craft()).json()['id']
        run(app, job)
        assert c.post('/v1/studio/jobs/' + job + '/redraw', headers=a, json=mutation()).json()['state'] == 'queued'
        run(app, job)
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['state'] == 'awaiting_confirmation' and value['concept']['draws'] == 2
        assert value['concept']['estimate_with_concept'] == 40 and value['concept']['estimate_text_only'] == 30
        confirmed = c.post('/v1/studio/jobs/' + job + '/confirm', headers=a, json=mutation(use_concept=False))
        assert confirmed.status_code == 200 and confirmed.json()['estimate'] == 30
        run(app, job, 4)
        assert [p for p, _ in provider.calls][-1] == '/generation/text-to-model'
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        # Both pictures were paid for even though the text was used.
        assert value['state'] == 'ready' and value['provenance']['tripo_credits_consumed'] == 40


def test_concept_respects_the_per_craft_cap_and_redraw_limit(tmp_path):
    provider = Provider()
    app, client = world(tmp_path, provider, mode='live', registration_code='test-only-invitation-123456',
                        max_credits_per_craft=35, studio_llm='gemini', gemini_key='test-only-key', welcome_stars=200)
    with client as c:
        token = c.post('/v1/auth/register', json={'username': 'capped', 'password': 'Test-password-123', 'invitation': 'test-only-invitation-123456'}).json()['token']
        a = {'Authorization': 'Bearer ' + token}
        created = c.post('/v1/studio/jobs', headers=a, json=craft(model='gpt-6-luna', effort='high'))
        assert created.status_code == 200, created.json()
        job = created.json()['id']
        run(app, job)
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['concept']['estimate_with_concept'] == 35
        # Another picture would make it 40 > 35.
        refused = c.post('/v1/studio/jobs/' + job + '/redraw', headers=a, json=mutation())
        assert refused.status_code == 403 and refused.json()['detail'] == 'craft_over_trial_limit'


def test_a_failed_picture_never_fails_the_craft(tmp_path):
    provider = Provider(fail_concept=True); app, client = world(tmp_path, provider)
    with client as c:
        a = account(c, 'alice')
        job = c.post('/v1/studio/jobs', headers=a, json=craft()).json()['id']
        run(app, job)
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['state'] == 'awaiting_confirmation' and 'concept' not in value
        assert value['provenance']['concept_error'] == 'concept_failed'


def test_photo_crafts_skip_the_concept_and_proxy_crafts_get_a_placeholder(tmp_path):
    import base64
    provider = Provider(); app, client = world(tmp_path, provider)
    raw = io.BytesIO(); Image.new('RGB', (32, 32), 'white').save(raw, 'PNG')
    photo = 'data:image/png;base64,' + base64.b64encode(raw.getvalue()).decode()
    with client as c:
        a = account(c, 'alice')
        job = c.post('/v1/studio/jobs', headers=a, json=craft(image=photo)).json()['id']
        run(app, job)
        assert 'concept' not in c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert not provider.calls
        c.post('/v1/studio/jobs/' + job + '/cancel', headers=a, json=mutation())
    demo = create_app(Settings(data_dir=tmp_path / 'demo', daily_generation_limit=100), worker_enabled=False)
    with TestClient(demo) as c:
        a = account(c, 'bob')
        job = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='wooden chest', motion='static', concept=True)).json()['id']
        asyncio.run(demo.state.studio.process(job))
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['state'] == 'awaiting_confirmation' and value['concept']['draws'] == 1
        assert c.get(value['concept']['url'], headers=a).status_code == 200
        assert c.post('/v1/studio/jobs/' + job + '/confirm', headers=a, json=mutation()).status_code == 200
        for _ in range(3): asyncio.run(demo.state.studio.process(job))
        assert c.get('/v1/studio/jobs/' + job, headers=a).json()['state'] == 'ready'
