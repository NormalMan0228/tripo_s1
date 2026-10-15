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
    assert check_text('porno poster') == 'sexual'
    assert check_text('코카인 상자') == 'drugs'
    assert check_text('씨발 의자') == 'words'
    # Obfuscations and compounds, and English swears.
    for text, category in (('나 체 조각상', 'sexual'), ('s e x chair', 'sexual'), ('s3x chair', 'sexual'), ('p0rn poster', 'sexual'),
                           ('selfharm kit', 'violence'), ('빨간나치깃발', 'hate'), ('미니히틀러 동상', 'hate'), ('가짜코카인 상자', 'drugs'),
                           ('fuck you sign', 'words'), ('f u c k chair', 'words')):
        assert check_text(text) == category, text
    assert check_text('잘린머리 장식') == 'violence' and check_text('나체 조각상') == 'sexual' and check_text('meth lab table') == 'drugs'
    # Hangul matches at the start of a word only; ambiguous Latin words are left to the LLM designer.
    for fine in ('작은 버섯 모양 의자', '마약 방석 같은 푹신한 쿠션', '고어텍스 재킷 걸이', '대마법사의 지팡이', '완성기념 트로피',
                 '내장형 서랍장', '해골 장식 촛대', '장난감 총 진열대', 'sexy red sofa', '다시 발견한 보물상자', '시발점 표지판',
                 '처음부터 끝까지 원목인 책상', '이음부를 금속으로 감싼 의자', '마음부자 저금통', '얼음부엉이 조각상', '참수리 조각상',
                 '고어 문자가 새겨진 돌판', '시신경 모형', '바나나체어', '마나체스트', '마약 침대', '마약 담요', '도시체험관 모형',
                 '성기사의 방패', 'white power strip', 'naked flame lamp', 'cock weathervane', 'balls of yarn basket',
                 '녹음부스 책상', '방음부스', '소음경고 표지판', '바나나치즈케이크 모형', '자살방지 포스터', '자살 방지 안내판', 'Gore-Tex jacket hanger',
                 '야 동물 모양 의자', '음 부엌 선반', '나 체스판 만들어줘', '나 치즈 모양 쿠션', '자 살구색 소파', '오후 3시 체크인 안내판',
                 'https://www.ikea.com/kr/ko/p/poang-chair에 있는 의자', 'fire retardant curtain', 'bastard sword rack', 'cocktail table',
                 '3d printer', 'essex sign'):
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
        # Games from 0.11.8 word the code; released ones print a sentence (it has a space).
        reply = c.post('/v1/studio/jobs', headers={**a, 'x-villagen-version': '0.11.8'}, json=mutation(prompt='나치 깃발', motion='static'))
        assert reply.status_code == 422 and reply.json()['detail'] == 'refused_hate'
        reply = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='나치 깃발', motion='static'))
        assert reply.status_code == 422 and reply.json()['detail'] == '혐오를 담은 상징은 만들 수 없어요.'
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
    # An odd word next to a full design is not a refusal; alone it is.
    assert refusal('{"refused":"N/A","plan":{},"program":{}}') == '' and refusal('{"refused":"N/A"}') == 'other'
    assert refusal('{"refused":"other","plan":{},"program":{}}') == 'other'


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
    # The camera's rotation is applied before the metadata goes.
    raw = io.BytesIO(); data = Image.Exif(); data[0x0112] = 6
    Image.new('RGB', (400, 200), 'orange').save(raw, 'JPEG', exif=data.tobytes())
    assert _decode(reference_image('data:image/jpeg;base64,' + base64.b64encode(raw.getvalue()).decode())).size == (200, 400)
    for value, code in ((_data_url((10, 10)), 'image_too_small'), ('data:image/gif;base64,R0lGOD', 'image_unreadable'),
                        ('data:image/png;base64,AAAA', 'image_unreadable'), (_data_url((5000, 100)), 'image_too_large')):
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
        # The stored request keeps the scaled photo; the worker reuses it as it is.
        import sqlite3
        stored = app.state.studio.db
        with stored.read() as conn:
            kept = json.loads(conn.execute('SELECT request FROM studio_jobs WHERE id=?', (reply.json()['id'],)).fetchone()[0])['image']
        assert len(kept) < 1_400_000 and _decode(kept).size[0] <= 2048
        # A photo is only looked at after sign-in.
        anonymous = c.post('/v1/studio/jobs', json=mutation(prompt='a cosy chest', designer='llm', motion='static', image=large))
        assert anonymous.status_code == 401
