"""Named craft styles and sizes: the client sends ids, the server words the LLM designer, the concept
picture and Tripo prompts, and the game sizes the object by provenance.size_m."""
import asyncio
from server import craft_styles
from server.asset_assembly import demo_design, static_plan, simple_plan, extent
from server.asset_contract import prompt_for
from server.tests.test_studio import mutation, account
from server.tests.test_concept import Provider, world


class Designer:
    def __init__(self):
        self.styles = []

    async def generate(self, prompt, model, effort, image=None, style=None):
        self.styles.append(style)
        return (*demo_design('chest'), {'provider': 'mock_designer'})


def test_studio_lists_styles_and_sizes(tmp_path):
    app, client = world(tmp_path, Provider())
    with client as c:
        info = c.get('/v1/studio', headers=account(c, 'alice')).json()
    assert [s['id'] for s in info['styles']] == list(craft_styles.STYLE_IDS) and info['default_style'] == 'rpg'
    assert all(s['names']['ko'] and s['names']['en'] and s['names']['zh'] and s['hints']['ko'] for s in info['styles'])
    assert [s['id'] for s in info['sizes']] == ['auto', 'small', 'medium', 'large', 'huge']
    assert 'llm' not in info['styles'][0]  # server wording stays on the server


def test_style_and_size_reach_the_designer_picture_and_object(tmp_path):
    provider = Provider(); app, client = world(tmp_path, provider)
    designer = Designer(); app.state.studio.designer = designer
    with client as c:
        a = account(c, 'alice')
        body = mutation(prompt='a reading chair', geometry='tripo', designer='llm', motion='static', material='textured',
                        mesh_model='v3.1-20260211', concept=True, style='hanok', size='large')
        job = c.post('/v1/studio/jobs', headers=a, json=body).json()['id']
        asyncio.run(app.state.studio.process(job))
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
    assert 'Korean traditional' in designer.styles[0] and '1.8 m' in designer.styles[0]
    assert 'Korean traditional' in provider.calls[0][1]['prompt']
    assert 'Korean traditional' in value['design']['parts'][0]['prompt']  # merged static prompt
    assert value['provenance']['style'] == 'hanok' and value['provenance']['size_m'] == 1.8


def test_defaults_and_unknown_ids(tmp_path):
    app, client = world(tmp_path, Provider())
    with client as c:
        a = account(c, 'alice')
        bad = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='a lamp', style='gothic'))
        assert bad.status_code == 422
        bad = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='a lamp', size='giant'))
        assert bad.status_code == 422
        job = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='a lamp', motion='static')).json()['id']
        asyncio.run(app.state.studio.process(job))
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
    # Older clients send neither: the default look, the designer's own size.
    assert value['provenance']['style'] == 'rpg' and value['provenance']['size_m'] == 0


def test_prompts_carry_the_chosen_wording():
    assert 'storybook' in prompt_for('lamp', '', craft_styles.designer_style('cozy', 'auto'))
    assert 'semi-realistic' in prompt_for('lamp')
    assert 'faceted' in simple_plan('a stool', craft_styles.style('lowpoly')['prop'])['parts'][0]['prompt']


def test_static_furniture_keeps_the_designed_extent():
    plan, _ = demo_design('chest')
    merged = static_plan(plan, 'a chest')
    assert merged['parts'][0]['size'] == extent(plan['parts'])
    assert max(merged['parts'][0]['size']) < 3 and min(merged['parts'][0]['size']) >= .1
    assert merged['parts'][0]['size'] != [1.5, 1.5, 1.5]
