"""Outgoing generation requests must not impose an unrelated house/furniture style."""
import base64
import io
import pytest
from PIL import Image
from server import craft_styles
from server.asset_assembly import simple_plan, static_plan, demo_design
from server.tests.test_concept import Provider, world, run
from server.tests.test_studio import account, mutation


HIDDEN = ('sunny island village', 'Avoid horror', 'realistic skin and razor edges',
          'No people', 'no text', 'soft illustrated island style', 'Cozy rounded matte game furniture',
          'Complete assembled static furniture', 'no base plate')


def no_hidden_look(prompt):
    for text in HIDDEN:
        assert text.casefold() not in prompt.casefold()


@pytest.mark.parametrize('style', craft_styles.STYLE_IDS)
def test_selected_style_and_subject_reach_picture_and_text_mesh(tmp_path, style):
    provider = Provider()
    app, client = world(tmp_path, provider)
    request = 'a fictional chibi robot character with a blue scarf and the letters AX on its chest'
    with client as c:
        owner = account(c, 'alice')
        body = mutation(prompt=request, geometry='tripo', designer='simple', motion='static',
                        material='textured', mesh_model='v3.1-20260211', concept=True, style=style)
        reply = c.post('/v1/studio/jobs', headers=owner, json=body)
        assert reply.status_code == 200, reply.json()
        job = reply.json()['id']
        run(app, job)
        image_prompt = provider.calls[0][1]['prompt']
        assert request in image_prompt
        assert craft_styles.style(style)['concept'] in image_prompt
        assert 'take priority over conflicting style defaults' in image_prompt
        no_hidden_look(image_prompt)
        assert c.post('/v1/studio/jobs/'+job+'/confirm', headers=owner,
                      json=mutation(use_concept=False)).status_code == 200
        run(app, job, 4)
        route, payload = provider.calls[-1]
        assert route == '/generation/text-to-model'
        assert request in payload['prompt']
        assert craft_styles.style(style)['prop'] in payload['prompt']
        no_hidden_look(payload['prompt'])


@pytest.mark.parametrize('style', ['anime', 'realistic', 'lowpoly'])
def test_reference_refinement_uses_selected_style_not_island_style(tmp_path, style):
    provider = Provider()
    app, client = world(tmp_path, provider)
    raw = io.BytesIO()
    Image.new('RGB', (32, 32), 'blue').save(raw, 'PNG')
    image = 'data:image/png;base64,' + base64.b64encode(raw.getvalue()).decode()
    with client as c:
        owner = account(c, 'alice')
        body = mutation(prompt='blue robot character', geometry='tripo', designer='llm', motion='static',
                        image=image, image_mode='refine', style=style, mesh_model='v3.1-20260211')
        job = c.post('/v1/studio/jobs', headers=owner, json=body).json()['id']
        run(app, job)
        assert c.post('/v1/studio/jobs/'+job+'/confirm', headers=owner, json=mutation()).status_code == 200
        run(app, job)
        route, payload = provider.calls[0]
        assert route == '/generation/image-to-image'
        assert len(provider.uploads) == 1
        uploaded = Image.open(io.BytesIO(base64.b64decode(provider.uploads[0].split(',')[1])))
        assert uploaded.size == (32, 32) and uploaded.getpixel((16, 16))[2] >= 250
        assert craft_styles.style(style)['concept'] in payload['prompt']
        assert 'description or reference take priority' in payload['prompt']
        no_hidden_look(payload['prompt'])


def test_designer_and_single_piece_fallback_have_no_hidden_appearance():
    for style in craft_styles.STYLE_IDS:
        text = craft_styles.designer_style(style, 'auto')
        assert craft_styles.style(style)['llm'] in text
        no_hidden_look(text)
    plan, _ = demo_design('chest')
    no_hidden_look(static_plan(plan, 'blue robot character')['parts'][0]['prompt'])
    # The old direct path cut the request at 300 characters before adding a hidden look.
    request = 'blue robot character ' + 'small detail ' * 25 + 'red antenna'
    part = simple_plan(request)['parts'][0]['prompt']
    assert 'red antenna' in part
    no_hidden_look(part)


@pytest.mark.parametrize('style', craft_styles.STYLE_IDS)
def test_maximum_part_keeps_all_details_within_provider_limit(style):
    description = 'x' * 780 + ' red antenna at tail'
    assert len(description) == 800
    prompt = craft_styles.mesh_prompt(description, style)
    assert description in prompt and len(prompt) <= 1024
    assert craft_styles.style(style)['names']['en'] in prompt
