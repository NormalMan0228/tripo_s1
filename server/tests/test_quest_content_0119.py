"""Validate every translated content entry and its existing gameplay hooks."""
import json
import re
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from string import Formatter

import pytest

from server import archetypes, homestead, interactions, npc_homes, npc_letters
from server import quest_board, quest_content, quests
from server.tests.social_world import World


ROOT = Path(__file__).resolve().parents[2]
QUEST_DATA = json.loads((ROOT / 'server/data/quest_templates_0119.json').read_text(encoding='utf-8'))
LETTER_DATA = json.loads((ROOT / 'server/data/npc_letters_0119.json').read_text(encoding='utf-8'))
TEMPLATES = QUEST_DATA['templates']
LETTERS = LETTER_DATA['letters']
LANGUAGES = {'ko', 'en', 'zh'}
RESIDENTS = set(npc_homes.NPCS) | set(npc_homes.SENDERS)
FIELDS = {'title', 'request', 'accept', 'complete'}
FORMATTER = Formatter()


def placeholders(value):
    assert isinstance(value, str) and value.strip() == value and value
    assert '\ufffd' not in value
    found = Counter()
    for _, field, spec, conversion in FORMATTER.parse(value):
        if field is not None:
            assert not spec and conversion is None
            found[field] += 1
    return found


def test_pack_sizes_unique_ids_and_complete_resident_coverage():
    assert QUEST_DATA['version'] == LETTER_DATA['version'] == '0.11.9'
    assert len(TEMPLATES) == 60 and len(LETTERS) == 40
    ids = [entry['id'] for entry in TEMPLATES + LETTERS]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r'[a-z][a-z0-9_]*', ident) for ident in ids)
    resident_source = (ROOT / 'game/scripts/residents.gd').read_text(encoding='utf-8')
    resident_array = resident_source.split('const RESIDENTS := [', 1)[1].split('\n]', 1)[0]
    assert set(re.findall(r'"id"\s*:\s*"([a-z_]+)"', resident_array)) == RESIDENTS
    assert Counter(entry['npc'] for entry in TEMPLATES) == Counter(
        {npc: 4 if npc in {'regular', 'naru', 'kid'} else 3 for npc in RESIDENTS})
    assert {entry['quest_id'] for entry in TEMPLATES} == set(quests.QUESTS)
    assert set(quests.QUESTS) == set(quests.STARS)
    assert tuple(TEMPLATES) == quest_content.QUEST_TEMPLATES
    assert tuple(LETTERS) == quest_content.LETTER_TEMPLATES


@pytest.mark.parametrize('entry', TEMPLATES, ids=lambda entry: entry['id'])
def test_every_quest_template_uses_existing_conditions_and_translations(entry):
    assert set(entry) == {'id', 'quest_id', 'npc', 'difficulty', 'reward_tier', 'activity', 'text'}
    assert entry['npc'] in RESIDENTS
    source = quests.QUESTS[entry['quest_id']]
    assert entry['npc'] == source['npc']
    assert entry['reward_tier'] == entry['quest_id']
    assert entry['reward_tier'] in quests.STARS
    assert entry['difficulty'] in {'easy', 'normal'}
    assert source['kind'] in {'bring', 'catch', 'outfit', 'gift', 'light', 'arrange', 'visit', 'talk'}
    assert isinstance(source['count'], int) and source['count'] > 0
    assert set(source.get('items', ())) <= set(homestead.NAMES)
    assert set(source.get('tags', ())) <= set(npc_homes.TAG_WORDS)
    if 'to' in source:
        assert source['to'] in npc_homes.NPCS
    if source['kind'] == 'talk':
        assert set(source['places']) <= RESIDENTS
    elif source['kind'] == 'visit':
        assert set(source['places']) <= set(quests.ISLANDS) | {'observatory', 'lighthouse_pier', 'lookout'}
    if entry['activity'] == 'gather':
        drops = {drop[0] for node in homestead.FORAGE.values() for drop in node['drops']}
        drops |= {tree['fruit'] for tree in homestead.TREES.values()}
        assert source['kind'] == 'bring' and set(source['items']) <= drops
    elif entry['activity'] == 'farm':
        assert source['kind'] == 'bring' and set(source['items']) <= set(homestead.CROPS)
    elif entry['activity'] == 'fish':
        assert source['kind'] == 'catch' or (
            source['kind'] == 'bring' and set(source['items']) <= set(homestead.FISH))
    elif entry['activity'] == 'craft':
        assert source.get('craft') and source['kind'] in {'light', 'gift'}
        if source['kind'] == 'light':
            assert set(quests.GLOW_KINDS) <= set(interactions.KINDS)
            assert set(quests.GLOW_FAMILIES) <= {kind['family'] for kind in archetypes.BY_ID.values()}
        else:
            assert set(source['tags']) <= {'toy', 'animal'}
            assert any(kind['room'] == 'toys' for kind in archetypes.BY_ID.values())
    elif entry['activity'] == 'deliver':
        assert source['kind'] in {'bring', 'talk', 'gift'}
    else:
        assert entry['activity'] in {'visit', 'outfit', 'arrange'}
        assert entry['activity'] == source['kind']
    assert set(entry['text']) == LANGUAGES
    for translated in entry['text'].values():
        assert set(translated) == FIELDS
    for field in FIELDS:
        expected = placeholders(entry['text']['ko'][field])
        assert set(expected) <= {'count'}
        for language in LANGUAGES:
            assert placeholders(entry['text'][language][field]) == expected
            assert entry['text'][language][field].format(count=source['count'])


@pytest.mark.parametrize('entry', LETTERS, ids=lambda entry: entry['id'])
def test_every_letter_has_a_supported_sender_occasion_and_translation(entry):
    assert {'id', 'npc', 'occasion', 'text'} <= set(entry)
    assert set(entry) <= {'id', 'npc', 'occasion', 'text', 'gift_id'}
    assert entry['npc'] in RESIDENTS
    assert entry['occasion'] in {'request_done', 'resident_day', 'small_talk', 'move_in', 'move_out', 'came_back'}
    if 'gift_id' in entry:
        assert entry['gift_id'] in npc_homes.RETURN_GIFTS
    assert set(entry['text']) == LANGUAGES
    expected = placeholders(entry['text']['ko'])
    assert not expected
    for language in LANGUAGES:
        assert placeholders(entry['text'][language]) == expected
    assert quest_content.letter_template(entry['npc'], entry['occasion'], 'stable-event') == entry


def test_letter_coverage_matches_existing_dispatch_hooks():
    expected = {
        'request_done': RESIDENTS,
        'resident_day': set(npc_letters.RESIDENT_DAYS),
        'small_talk': {'naru', 'sora', 'moru', 'haeru', 'kid'},
        'move_in': {'shopkeeper'},
        'move_out': {'shopkeeper'},
        'came_back': {'shopkeeper'},
    }
    assert Counter(entry['occasion'] for entry in LETTERS) == Counter(
        {occasion: len(senders) for occasion, senders in expected.items()})
    for occasion, senders in expected.items():
        assert {entry['npc'] for entry in LETTERS if entry['occasion'] == occasion} == senders
    assert quest_content.letter_template('missing_resident', 'request_done') is None
    assert quest_content.letter_template('regular', 'small_talk') is None
    assert quest_content.letter_template('naru', 'unknown_occasion') is None


def test_board_rotation_reaches_all_60_variants_and_changes_each_occurrence():
    now = datetime(2027, 2, 1, 0, tzinfo=quest_board.ZONE).timestamp()
    seen = set()
    previous = {}
    for day in range(len(quests.QUESTS) * 4):
        at = now + day * 86400
        for quest_id in quest_board.offers(at):
            entry = quest_content.quest_template(quest_id, at)
            assert entry['quest_id'] == quest_id
            assert entry == quest_content.quest_template(quest_id, at + 86399)
            assert previous.get(quest_id) != entry['id']
            previous[quest_id] = entry['id']
            seen.add(entry['id'])
            source = next(template for template in TEMPLATES if template['id'] == entry['id'])
            for language in LANGUAGES:
                assert entry['text'][language] == {
                    key: value.format(count=quests.QUESTS[quest_id]['count'])
                    for key, value in source['text'][language].items()}
    assert seen == {entry['id'] for entry in TEMPLATES}


def test_content_returns_independent_copies():
    now = datetime(2027, 2, 1, tzinfo=quest_board.ZONE).timestamp()
    first = quest_content.quest_template('moka_pie', now)
    saved_title = first['text']['ko']['title']
    first['text']['ko']['title'] = 'changed by caller'
    assert quest_content.quest_template('moka_pie', now)['text']['ko']['title'] == saved_title
    letter = quest_content.letter_template('naru', 'request_done')
    saved_text = letter['text']['ko']
    letter['text']['ko'] = 'changed by caller'
    assert quest_content.letter_template('naru', 'request_done')['text']['ko'] == saved_text


@pytest.fixture
def world(tmp_path):
    world = World(tmp_path)
    world.now[0] = datetime(2027, 2, 1, 12, tzinfo=quest_board.ZONE).timestamp()
    yield world
    world.close()


def test_board_accept_complete_exposes_content_without_changing_rewards(world):
    w = world
    player = w.player('content_reader')
    for _ in range(len(quests.QUESTS)):
        if 'moka_pie' in quest_board.offers(w.now[0]):
            break
        w.tick(86400)
    board = w.get(player, '/v1/quest_board')['board']
    entry = next(item for item in board['list'] if item['id'] == 'moka_pie')
    assert entry['content'] == quest_content.quest_template('moka_pie', w.now[0])
    assert entry['kind'] == 'bring' and entry['items'] == ['apple'] and entry['need'] == 3
    assert entry['stars'] == quests.reward('moka_pie', w.settings.quest_stars_scale)
    with w.app.state.db.transaction() as conn:
        life = homestead.initial()
        life['bag']['apple'] = 3
        conn.execute('INSERT INTO homesteads VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state',
                     (player.id, json.dumps(life)))
    route = f"/v1/quest_board/{board['day']}/moka_pie"
    accepted = w.call(player, route + '/accept')
    completed = w.call(player, route + '/complete')
    assert accepted['quest']['content'] == completed['quest']['content'] == entry['content']
    assert completed['stars'] == entry['stars'] and completed['taken'] == {'apple': 3}
    letter = completed['letters'][0]
    assert letter['content'] == quest_content.letter_template('regular', 'request_done')
    assert letter['event']['payload'] == {'quest_id': 'moka_pie', 'day': board['day']}
    assert letter['gift'] is None
    assert w.get(player, '/v1/quest_board')['board']['completed'] == 1


def test_letter_content_preserves_legacy_and_event_fields_and_gifts(world):
    w = world
    player = w.player('letter_reader')
    ids = {}
    with w.app.state.db.transaction() as conn:
        # Existing letters are rendered without dispatching new small-talk mail.
        for name, npc, level in (
            ('story', 'regular', 0), ('heart', 'naru', 1), ('uncovered_heart', 'scout', 1),
            ('thanks', 'regular', npc_homes.QUEST_LETTER_LEVEL),
            ('welcome', 'shopkeeper', npc_homes.MOVE_LETTER_LEVEL),
            ('farewell', 'shopkeeper', npc_homes.MOVE_LETTER_LEVEL + 1),
            ('back', 'shopkeeper', npc_homes.MOVE_LETTER_LEVEL + 2),
        ):
            ids[name] = str(uuid.uuid4())
            conn.execute('INSERT INTO npc_letters(id,host_id,npc_id,level,created) VALUES (?,?,?,?,?)',
                         (ids[name], player.id, npc, level, w.now[0]))
        gift = str(uuid.uuid4())
        conn.execute('INSERT INTO objects(id,owner_id,creator_id,asset_id,name,created) VALUES (?,?,?,?,?,?)',
                     (gift, player.id, player.id, 'existing_gift', '기존 답례', w.now[0]))
        conn.execute('UPDATE npc_letters SET gift_object_id=? WHERE id=?', (gift, ids['heart']))
        ids['event_back'] = npc_letters.dispatch(conn, player.id, 'shopkeeper', 'move_in', 'return-1',
                                                w.now[0], {'kind': 'back', 'retained': 'payload'})
        ids['anniversary'] = npc_letters.dispatch(conn, player.id, 'naru', 'resident_day', '2027-01-09',
                                                 w.now[0], {'occasion': 'village_anniversary'})
    reply = w.get(player, '/v1/letters')
    letters = {letter['id']: letter for letter in reply['letters']}
    assert set(letters) == set(ids.values())
    assert 'content' not in letters[ids['story']] and 'story' in letters[ids['story']]
    assert 'content' not in letters[ids['uncovered_heart']]
    expected = {'heart': 'small_talk', 'thanks': 'request_done', 'welcome': 'move_in',
                'farewell': 'move_out', 'back': 'came_back', 'event_back': 'came_back',
                'anniversary': 'resident_day'}
    for name, occasion in expected.items():
        assert letters[ids[name]]['content']['occasion'] == occasion
    assert letters[ids['heart']]['gift'] == {'id': gift, 'name': '기존 답례'}
    assert letters[ids['heart']]['level'] == 1
    assert letters[ids['thanks']]['quest'] == {'npc': 'regular'}
    assert letters[ids['back']]['move'] == {'kind': 'back', 'npc': 'shopkeeper'}
    assert letters[ids['event_back']]['event'] == {'type': 'move_in', 'key': 'return-1',
                                                  'payload': {'kind': 'back', 'retained': 'payload'}}
    assert w.get(player, '/v1/letters') == reply
    with w.app.state.db.read() as conn:
        assert conn.execute('SELECT COUNT(*) FROM npc_letters').fetchone()[0] == len(ids)
        assert conn.execute('SELECT COUNT(*) FROM ledger').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM npc_friendship').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM objects').fetchone()[0] == 1
