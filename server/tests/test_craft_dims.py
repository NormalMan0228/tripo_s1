"""The box the player drags in the craft window (StudioRequest.dims = [width x, height y, depth z] m):
the sides reach the LLM designer and the one-piece Tripo prompts, the game sizes the object by its
longest side (provenance.size_m), and crafts without a box behave as before."""
import asyncio
import json
from server import craft_styles, archetypes
from server import behaviour_library as library
from server.asset_assembly import demo_design, static_plan, simple_plan
from server.tests.test_studio import mutation, account
from server.tests.test_concept import Provider, world
from server.tests.test_craft_styles import Designer


def craft(**kw):
    return mutation(prompt='a reading chair', geometry='tripo', designer='llm', motion='static', material='textured',
                    mesh_model='v3.1-20260211', concept=True, **kw)


def run(tmp_path, **kw):
    provider = Provider(); app, client = world(tmp_path, provider)
    designer = Designer(); app.state.studio.designer = designer
    with client as c:
        a = account(c, 'alice')
        r = c.post('/v1/studio/jobs', headers=a, json=craft(**kw))
        assert r.status_code == 200, r.text
        job = r.json()['id']
        asyncio.run(app.state.studio.process(job))
        value = c.get('/v1/studio/jobs/' + job, headers=a).json()
    return value, designer, provider


def test_studio_advertises_the_box(tmp_path):
    app, client = world(tmp_path, Provider())
    with client as c:
        info = c.get('/v1/studio', headers=account(c, 'alice')).json()
    assert info['dims'] == {'min': 0.1, 'max': 3.0}


def test_dims_reach_the_designer_the_prompts_and_the_object(tmp_path):
    value, designer, provider = run(tmp_path, dims=[1.2, 0.9, 0.6])
    style = designer.styles[0]
    assert '1.2 m wide (x)' in style and '0.9 m tall (y)' in style and '0.6 m deep (z)' in style
    assert 'longest side' not in style and 'real-world dimensions' not in style
    words = 'proportions about 1.2 m wide x 0.9 m tall x 0.6 m deep'
    assert words in value['design']['parts'][0]['prompt'].lower()  # merged one-piece Tripo prompt
    assert words in provider.calls[0][1]['prompt'].lower()  # the concept picture of that piece
    prov = value['provenance']
    assert prov['dims'] == [1.2, 0.9, 0.6] and prov['size_m'] == 1.2  # the game scales the longest side


def test_dims_win_over_a_size_preset_and_snap_to_5_cm(tmp_path):
    value, designer, _ = run(tmp_path, size='small', dims=[0.5, 2.43, 1.01])
    assert value['provenance']['dims'] == [0.5, 2.45, 1.0] and value['provenance']['size_m'] == 2.45
    assert '2.45 m tall (y)' in designer.styles[0] and '0.6 m on its longest side' not in designer.styles[0]


def test_bad_boxes_are_refused(tmp_path):
    app, client = world(tmp_path, Provider())
    with client as c:
        a = account(c, 'alice')
        for dims in ([0.05, 1, 1], [1, 1, 3.5], [1, -1, 1], [1, 1], [1, 1, 1, 1], ['a', 1, 1], 1.2):
            r = c.post('/v1/studio/jobs', headers=a, json=craft(dims=dims))
            assert r.status_code == 422 and r.json()['detail'] == 'invalid_craft_request', dims
        body = json.dumps(craft(dims=[1, 1, 1])).replace('[1, 1, 1]', '[NaN, 1, 1]')
        r = c.post('/v1/studio/jobs', headers={**a, 'Content-Type': 'application/json'}, content=body)
        assert r.status_code == 422 and r.json()['detail'] == 'invalid_craft_request'


def test_without_a_box_nothing_changes(tmp_path):
    value, designer, _ = run(tmp_path, size='large')
    prov = value['provenance']
    assert 'dims' not in prov and prov['size_m'] == 1.8
    assert '1.8 m on its longest side' in designer.styles[0] and 'wide (x)' not in designer.styles[0]
    assert 'proportions about' not in value['design']['parts'][0]['prompt'].lower()
    # The learned-design key is the one older servers made, so the library keeps serving it.
    old = library.make_key('design', library.normalize('a reading chair'), 'rpg', 'large', 'static',
                           craft_styles.designer_style('rpg', 'large'), archetypes.VERSION)
    assert prov['library_key'] == old


def test_the_box_has_its_own_learned_design(tmp_path):
    a, _, _ = run(tmp_path / 'a', dims=[1.0, 1.0, 1.0])
    b, _, _ = run(tmp_path / 'b', dims=[2.0, 1.0, 1.0])
    c, _, _ = run(tmp_path / 'c')
    keys = {a['provenance']['library_key'], b['provenance']['library_key'], c['provenance']['library_key']}
    assert len(keys) == 3


def test_one_piece_plans_name_the_box():
    plan = simple_plan('a tall lamp', dims=[0.4, 1.8, 0.4])
    part = plan['parts'][0]
    assert part['size'] == [0.4, 1.8, 0.4] and part['position'][1] == 0.9
    assert 'proportions about 0.4 m wide x 1.8 m tall x 0.4 m deep' in part['prompt']
    # Made static afterwards: the box is not named twice.
    assert static_plan(plan, 'a tall lamp', dims=[0.4, 1.8, 0.4])['parts'][0]['prompt'].count('proportions about') == 1
    assert simple_plan('a stool')['parts'][0]['size'] == [1.2, 1.2, 1.2]
    merged = static_plan(demo_design('chest')[0], 'a chest', dims=[1.5, 0.8, 0.7])
    assert merged['parts'][0]['prompt'].startswith('Complete assembled static furniture')
    assert 'Proportions about 1.5 m wide x 0.8 m tall x 0.7 m deep. a chest' in merged['parts'][0]['prompt']
    assert 'wide (x)' in craft_styles.designer_style('rpg', 'auto', [1, 2, 3])
    assert 'wide (x)' not in craft_styles.designer_style('rpg', 'auto')
