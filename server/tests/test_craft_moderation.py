"""Inappropriate crafts are refused with a reason (never softened), every failure carries a reason the
window words, Tripo bans are refusals (not held crafts), and reference photos are checked, scaled down
and stripped of metadata."""
import asyncio, base64, io, json
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from server.app import create_app
from server.config import Settings
from server.craft_moderation import check_text, failure_reason, category_of
from server.design_provider import DesignProvider, refusal
from server.asset_studio import reference_image, IMAGE_KEPT_BYTES, IMAGE_KEPT_SIDE
from server.provider import ProviderError
from server.tests.test_studio import mutation, account
from server.tests.test_concept import Provider, Designer, world, run


def test_word_list_refuses_by_category_and_spares_ordinary_words():
    assert check_text('나치 깃발 액자') == 'hate'
    assert check_text('잘린 머리 장식') == 'violence'
    assert check_text('naked man statue') == 'sexual'
    assert check_text('코카인 상자') == 'drugs'
    assert check_text('씨발 의자') == 'words'
    for fine in ('작은 버섯 모양 의자', '마약 방석 같은 푹신한 쿠션', '고어텍스 재킷 걸이', '대마법사의 지팡이', '완성기념 트로피',
                 '내장형 서랍장', '해골 장식 촛대', '장난감 총 진열대', 'sexy red sofa', '다시 발견한 보물상자', '시발점 표지판'):
        assert check_text(fine) == '', fine


def test_reasons_group_every_error_code():
    assert failure_reason('refused_sexual') == ('refused', 'sexual')
    assert failure_reason('refused_banana') == ('refused', 'other')
    assert failure_reason('generation_timeout') == ('timeout', '')
    assert failure_reason('llm_invalid_design') == ('design', '')
    assert failure_reason('assembly_render_budget_exceeded') == ('heavy', '')
    assert failure_reason('worker_lease_expired') == ('restart', '')
    assert failure_reason('something_new') == ('other', '')
    assert failure_reason('') == ('', '')
    assert category_of('Nudity') == 'sexual' and category_of('') == '' and category_of('weird') == 'other'


def test_a_listed_word_is_refused_before_any_charge(tmp_path):
    app, client = world(tmp_path, Provider())
    with client as c:
        a = account(c, 'alice')
        shards = c.get('/v1/me', headers=a).json()['shards']
        reply = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='나치 깃발', motion='static'))
        assert reply.status_code == 422 and reply.json()['detail'] == 'refused_hate'
        assert c.get('/v1/me', headers=a).json()['shards'] == shards
        assert c.get('/v1/studio', headers=a).json()['jobs'] == []


class RefusingDesigner:
    def __init__(self, category): self.category = category
    async def generate(self, *args):
        from server.design_provider import DesignRefused
        raise DesignRefused([{'usage': {'input_tokens': 10}}], self.category)


def test_the_designer_refusal_ends_the_craft_with_its_reason_and_refunds(tmp_path):
    provider = Provider()
    settings = Settings(data_dir=tmp_path, paid_enabled=True, tripo_key='private-test-key', daily_generation_limit=100, studio_llm='openai')
    app = create_app(settings, provider=provider, designer=RefusingDesigner('person'), worker_enabled=False)
    with TestClient(app, base_url='https://testserver') as c:
        a = account(c, 'alice')
        shards = c.get('/v1/me', headers=a).json()['shards']
        job = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='a statue of my teacher', geometry='tripo', designer='llm', motion='static')).json()['id']
        run(app, job)
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['state'] == 'failed' and value['error'] == 'refused_person'
        assert value['reason'] == 'refused' and value['refusal'] == 'person'
        # LLM tokens were spent and recorded; nothing reached Tripo; the starseeds came back.
        assert value['provenance']['usage'] == {'input_tokens': 10} and not provider.calls
        assert c.get('/v1/me', headers=a).json()['shards'] == shards


def test_designer_answers_refusal_json_without_a_repair_round():
    class Settings_:
        studio_llm = 'openai'; studio_design_format = 'classic'; llm_key = 'k'; gemini_models = ()
    calls = []
    class Fake(DesignProvider):
        async def _openai(self, *args):
            calls.append(1)
            return json.dumps({'refused': 'sexual'}), {'input_tokens': 3}
    with pytest.raises(ProviderError) as caught:
        asyncio.run(Fake(Settings_()).generate('x', 'gpt-6-luna', 'high'))
    assert caught.value.code == 'refused_sexual' and calls == [1]
    assert refusal('{"refused":""}') == '' and refusal('not json') == ''


class BanningProvider(Provider):
    def __init__(self, ban_concept=False):
        super().__init__(); self.ban_concept = ban_concept
    async def task(self, task):
        if task.startswith('concept'):
            if self.ban_concept: return {'status': 'banned'}
            return await super().task(task)
        return {'status': 'banned'}


def test_a_tripo_ban_is_a_refusal_not_a_held_craft(tmp_path):
    provider = BanningProvider(); app, client = world(tmp_path, provider)
    with client as c:
        a = account(c, 'alice')
        shards = c.get('/v1/me', headers=a).json()['shards']
        job = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='a cosy chest', geometry='tripo', designer='llm', motion='static', mesh_model='v3.1-20260211')).json()['id']
        run(app, job)
        assert c.post('/v1/studio/jobs/' + job + '/confirm', headers=a, json=mutation()).status_code == 200
        run(app, job, 2)
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['state'] == 'failed' and value['error'] == 'refused_other' and value['reason'] == 'refused'
        assert c.get('/v1/me', headers=a).json()['shards'] == shards


def test_a_banned_concept_picture_ends_the_craft(tmp_path):
    provider = BanningProvider(ban_concept=True); app, client = world(tmp_path, provider)
    with client as c:
        a = account(c, 'alice')
        job = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='a cosy chest', geometry='tripo', designer='llm', motion='static',
                                                                 mesh_model='v3.1-20260211', concept=True)).json()['id']
        run(app, job)
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert value['state'] == 'failed' and value['error'] == 'refused_other'


def _data_url(size, kind='JPEG', mode='RGB', noise=False, exif=False):
    image = Image.effect_noise(size, 90).convert(mode) if noise else Image.new(mode, size, 'orange')
    raw = io.BytesIO()
    extra = {}
    if exif:
        data = Image.Exif(); data[0x010F] = 'CameraMaker'; extra['exif'] = data.tobytes()
    image.save(raw, kind, **extra)
    return 'data:image/' + kind.lower() + ';base64,' + base64.b64encode(raw.getvalue()).decode()


def _decode(url):
    return Image.open(io.BytesIO(base64.b64decode(url.split(',', 1)[1])))


def test_reference_photos_are_scaled_down_and_stripped():
    big = reference_image(_data_url((3000, 2000), noise=True, exif=True))
    picture = _decode(big)
    assert max(picture.size) <= IMAGE_KEPT_SIDE and len(base64.b64decode(big.split(',', 1)[1])) <= IMAGE_KEPT_BYTES
    assert not picture.getexif()
    # Transparency stays a PNG.
    assert reference_image(_data_url((300, 200), 'PNG', 'RGBA')).startswith('data:image/png;')
    for value, code in ((_data_url((10, 10)), 'image_too_small'), ('data:image/gif;base64,R0lGOD', 'image_unreadable'),
                        ('data:image/png;base64,AAAA', 'image_unreadable'), (_data_url((9000, 100)), 'image_too_large')):
        with pytest.raises(ValueError) as caught:
            reference_image(value)
        assert str(caught.value) == code


def test_a_refused_photo_says_why(tmp_path):
    app, client = world(tmp_path, Provider())
    with client as c:
        a = account(c, 'alice')
        small = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='a cosy chest', designer='llm', motion='static', image=_data_url((10, 10))))
        assert small.status_code == 422 and small.json()['detail'] == 'image_too_small'
        # A photo larger than the old 1 MB limit is accepted and kept small.
        large = _data_url((2400, 1800), noise=True)
        assert len(large) > 1_400_000
        reply = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='a cosy chest', designer='llm', motion='static', image=large))
        assert reply.status_code == 200, reply.text
