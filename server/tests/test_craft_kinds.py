"""Picking the kind in the craft window ('기능' row): the server lists the library types that really
do something (server/craft_kinds.py) and a picked one replaces the guess from the words."""
import json
from server import archetypes, craft_kinds, craft_styles
from server import behaviour_library as library
from server.archetypes import BY_ID
from server.asset_studio import DESIGN_RULES
from server.tests.test_living_objects import world, account, craft, mutation, CountingDesigner, VM2  # noqa: F401


def test_studio_lists_the_kinds_a_player_can_pick(world):
    app, c = world
    info = c.get('/v1/studio', headers=account(c, 'alice')).json()
    kinds = info['kinds']
    assert [k['id'] for k in kinds] == list(craft_kinds.IDS) and len(kinds) >= 10
    for k in kinds:
        arch = BY_ID[k['id']]
        assert arch['behaviours'] or arch['single'] or arch.get('rest'), k['id']
        assert all(k['names'][lang] and k['hint'][lang] and k['does'][lang] for lang in ('ko', 'en', 'zh')), k['id']
        assert k['icon'] and isinstance(k['moving_meshes'], int) and isinstance(k['always_moving'], bool)
        # The same facts the typing question (POST /v1/studio/kind) gives for a guessed type.
        guessed = archetypes.craft_kind('', k['id'])
        assert (guessed['moving_meshes'], guessed['always_moving']) == (k['moving_meshes'], k['always_moving'])
    by_id = {k['id']: k for k in kinds}
    assert by_id['seat']['names']['ko'] == '의자' and '0.45' in by_id['seat']['hint']['ko'] and by_id['seat']['rest'] == 'sit'
    assert by_id['clock']['always_moving'] and by_id['clock']['moving_meshes'] == 1
    # A lid or a door only works as a separate part: the window builds those kinds moving.
    assert by_id['chest']['needs_moving'] and by_id['fan']['needs_moving'] and not by_id['lamp']['needs_moving']
    assert not by_id['seat']['needs_moving'] and not by_id['clock']['needs_moving']


def test_a_picked_kind_wins_over_the_words(world):
    app, c = world
    a = account(c, 'alice')
    # The words name a chest; the player picked a lamp: a lamp that lights up when clicked.
    lamp, value = craft(app, c, a, '작은 나무 상자', archetype='lamp')
    assert value['provenance']['archetype'] == 'lamp' and value['provenance']['archetype_picked'] is True
    assert value['provenance']['behaviour']['archetype'] == 'lamp' and value['provenance']['behaviour']['presets'] >= 1
    assembly = c.get('/v1/objects/' + lamp + '/assembly', headers={**a, **VM2}).json()
    assert {p['id'] for p in assembly['plan']['parts']} == {'base', 'shade'}
    assert assembly['interaction']['mode'] == 'presets' and 'click' in assembly['interaction']['program']['events']
    assert 'shade' in json.dumps(assembly['interaction']['program']['events'])
    # The same words without a pick: the guess (a chest) as before, no picked flag.
    _, auto = craft(app, c, a, '작은 나무 상자')
    assert auto['provenance']['archetype'] == 'chest' and 'archetype_picked' not in auto['provenance']
    # A chair from words that name nothing in the library: seated like any chair.
    b = account(c, 'bobby')
    chair, value = craft(app, c, b, '버섯 모양 물건', archetype='seat')
    assert value['provenance']['archetype'] == 'seat'
    assembly = c.get('/v1/objects/' + chair + '/assembly', headers={**b, **VM2}).json()
    assert assembly['interaction']['rest'] == 'sit'
    # A chest picked for odd words: its lid opens on click.
    chest, value = craft(app, c, b, '커다란 돌덩이', archetype='chest')
    assembly = c.get('/v1/objects/' + chest + '/assembly', headers={**b, **VM2}).json()
    assert value['provenance']['archetype'] == 'chest' and 'lid' in json.dumps(assembly['interaction']['program'])


def test_a_picked_clock_is_built_moving_with_free_hands(world):
    app, c = world
    a = account(c, 'alice')
    _, value = craft(app, c, a, '나무 상자', archetype='clock', motion='static')
    assert value['provenance']['archetype'] == 'clock' and value['provenance']['motion'] == 'dynamic'
    assert {'hour_hand', 'minute_hand'} <= set(value['parts'])
    # The price stays what was asked (a still piece).
    assert value['cost'] == 20


def test_unknown_or_lifeless_kinds_are_refused(world):
    app, c = world
    a = account(c, 'alice')
    shards = c.get('/v1/me', headers=a).json()['shards']
    for bad in ('spaceship', 'table', 'x' * 60):
        reply = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='a lamp', archetype=bad))
        assert reply.status_code == 422 and reply.json()['detail'] == 'unknown_craft_kind', (bad, reply.text)
    assert c.get('/v1/me', headers=a).json()['shards'] == shards
    # '' is the default (the guess), as older clients send nothing.
    _, value = craft(app, c, a, 'a reading lamp', archetype='', motion='static')
    assert value['provenance']['archetype'] == 'lamp' and 'archetype_picked' not in value['provenance']


def test_the_request_id_still_makes_a_pick_idempotent(world):
    app, c = world
    a = account(c, 'alice')
    body = mutation(prompt='작은 나무 상자', archetype='lamp')
    first = c.post('/v1/studio/jobs', headers=a, json=body)
    again = c.post('/v1/studio/jobs', headers=a, json=body)
    assert first.status_code == 200 and again.json()['id'] == first.json()['id']


def test_a_picked_kind_has_its_own_learned_design(world):
    app, c = world
    a, b = account(c, 'alice'), account(c, 'bobby')
    designer = CountingDesigner()
    app.state.settings.studio_llm = 'openai'
    app.state.studio.designer = designer
    _, first = craft(app, c, a, 'A small hourglass', designer='llm')
    assert len(designer.calls) == 1 and 'archetype_picked' not in first['provenance']
    # The auto key is the one older servers made (learned designs keep being served after the update).
    style_text = craft_styles.designer_style('rpg', 'auto', None)
    old_key = library.make_key('design', library.normalize('A small hourglass'), 'rpg', 'auto', 'dynamic', style_text,
                               archetypes.VERSION, DESIGN_RULES)
    with app.state.db.read() as conn:
        assert library.find(conn, old_key) is not None
    # Picked as a lamp: not the auto design; the designer is told the type and its size rule.
    _, picked = craft(app, c, b, 'a small hourglass', designer='llm', archetype='lamp')
    assert len(designer.calls) == 2 and picked['provenance']['provider'] == 'openai'
    assert picked['provenance']['archetype'] == 'lamp' and 'Set plan.category to "lamp"' in designer.calls[1]
    assert 'Size rule: ' + craft_kinds.size_rule('lamp') in designer.calls[1]
    # The same pick again is served from the learned library; the auto request still gets the auto design.
    _, again = craft(app, c, a, 'a small hourglass', designer='llm', archetype='lamp')
    assert len(designer.calls) == 2 and again['provenance']['provider'] == 'library' and again['provenance']['archetype'] == 'lamp'
    _, auto = craft(app, c, b, 'a small hourglass', designer='llm')
    assert len(designer.calls) == 2 and auto['provenance']['library']['key'] == old_key
    assert 'archetype_picked' not in auto['provenance']
