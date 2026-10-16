"""Friends, blocks, privacy, the people roster, reports and knock/drop-in visits (server/friends.py)."""
import pytest
from server.tests.social_world import World
from server import friends as social


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    yield w
    w.close()


@pytest.fixture
def make_world(tmp_path):
    made = []

    def make(**overrides):
        made.append(World(tmp_path/str(len(made)), **overrides))
        return made[-1]
    yield make
    for w in made:
        w.close()


def names(entries):
    return [e['username'] for e in entries]


def test_request_accept_and_both_lists(world):
    w = world
    alice, bravo = w.players('alice', 'bravo')
    v0 = w.presence(bravo, since=0)['social']['v']
    sent = w.call(alice, '/v1/friends/requests', username='BRAVO')
    assert sent['state'] == 'sent'
    badge = w.presence(bravo, since=0)['social']
    assert badge['requests'] == 1 and badge['v'] > v0
    assert names(w.people(bravo)['requests']['incoming']) == ['alice']
    assert names(w.people(alice)['requests']['outgoing']) == ['bravo']
    assert w.call(alice, '/v1/friends/requests', username='bravo') == sent  # asking again changes nothing
    assert w.call(bravo, '/v1/friends/requests/'+sent['id']+'/accept')['state'] == 'accepted'
    assert names(w.people(alice)['friends']) == ['bravo'] and names(w.people(bravo)['friends']) == ['alice']
    assert w.people(bravo)['requests'] == {'incoming': [], 'outgoing': []}
    assert w.call(alice, '/v1/friends/requests', username='bravo')['state'] == 'friends'
    assert w.refused(bravo, '/v1/friends/requests/'+sent['id']+'/accept', 404) == 'request_unavailable'
    assert w.refused(alice, '/v1/friends/requests', 404, username='nobody') == 'user_not_found'
    assert w.refused(alice, '/v1/friends/requests', 422, username='alice') == 'friend_self'
    w.call(bravo, '/v1/friends/remove', user_id=alice.id)
    assert w.people(alice)['friends'] == [] and w.people(bravo)['friends'] == []


def test_requests_by_id_reverse_auto_accept_cancel_and_decline_cooldown(world):
    w = world
    alice, bravo, charlie = w.players('alice', 'bravo', 'charlie')
    w.call(alice, '/v1/friends/requests', user_id=bravo.id)
    assert w.call(bravo, '/v1/friends/requests', user_id=alice.id)['state'] == 'accepted'
    assert names(w.people(alice)['friends']) == ['bravo']
    sent = w.call(alice, '/v1/friends/requests', username='charlie')
    w.call(alice, '/v1/friends/requests/'+sent['id']+'/cancel')
    assert w.people(charlie)['requests']['incoming'] == []
    sent = w.call(alice, '/v1/friends/requests', username='charlie')
    w.call(charlie, '/v1/friends/requests/'+sent['id']+'/decline')
    assert w.people(alice)['requests']['outgoing'] == []
    # Asking again within a day looks sent but never reaches charlie.
    again = w.call(alice, '/v1/friends/requests', username='charlie')
    assert again['state'] == 'sent' and names(w.people(alice)['requests']['outgoing']) == ['charlie']
    assert w.people(charlie)['requests']['incoming'] == [] and w.presence(charlie, since=0)['social']['requests'] == 0
    assert w.refused(charlie, '/v1/friends/requests/'+again['id']+'/accept', 404) == 'request_unavailable'
    # Once the cooldown is over, asking again sends the request kept back (the same id).
    w.tick(86401)
    assert w.call(alice, '/v1/friends/requests', username='charlie') == again
    assert names(w.people(charlie)['requests']['incoming']) == ['alice']
    assert w.call(charlie, '/v1/friends/requests/'+again['id']+'/accept')['state'] == 'accepted'


def test_a_request_kept_back_reaches_the_player_once_nothing_keeps_it_back(world):
    w = world
    alice, bravo, charlie = w.players('alice', 'bravo', 'charlie')
    # The receiver's pref: nobody, then everyone again.
    w.call(bravo, '/v1/social/prefs', requests='nobody')
    sent = w.call(alice, '/v1/friends/requests', username='bravo')
    assert w.people(bravo)['requests']['incoming'] == []
    w.call(bravo, '/v1/social/prefs', requests='everyone')
    assert w.call(alice, '/v1/friends/requests', username='bravo') == sent
    assert names(w.people(bravo)['requests']['incoming']) == ['alice']
    # A block, then lifted.
    w.call(charlie, '/v1/social/blocks', user_id=alice.id)
    w.call(charlie, '/v1/social/blocks/remove', user_id=alice.id)
    w.call(charlie, '/v1/social/prefs', requests='nobody')
    kept = w.call(alice, '/v1/friends/requests', username='charlie')
    w.call(charlie, '/v1/social/prefs', requests='everyone')
    w.call(charlie, '/v1/social/blocks', user_id=alice.id)
    w.call(charlie, '/v1/social/blocks/remove', user_id=alice.id)
    again = w.call(alice, '/v1/friends/requests', username='charlie')
    assert names(w.people(charlie)['requests']['incoming']) == ['alice'] and again['state'] == 'sent'
    assert kept['id'] != again['id']   # the block cancelled the first one


def test_request_limits(world):
    w = world
    alice = w.player('alice')
    others = w.players(*('p%02d' % i for i in range(21)))
    for p in others[:social.REQUESTS_PER_DAY]:
        w.call(alice, '/v1/friends/requests', user_id=p.id)
    assert w.refused(alice, '/v1/friends/requests', 429, user_id=others[-1].id) == 'friend_requests_limited'
    w.tick(86401)
    assert w.refused(alice, '/v1/friends/requests', 409, user_id=others[-1].id) == 'friend_requests_pending_full'
    # A full list: the 101st friend is refused.
    with w.db() as conn:
        fillers = [str(i) for i in range(social.FRIEND_LIMIT)]
        for f in fillers:
            conn.execute("INSERT INTO users(id,username,password_hash,shards,created) VALUES (?,?,'x',0,0)", ('f'+f, 'filler'+f))
            conn.execute('INSERT INTO social_friends VALUES (?,?,0)', (others[0].id, 'f'+f))
    request_id = w.people(others[0])['requests']['incoming'][0]['id']
    assert w.refused(others[0], '/v1/friends/requests/'+request_id+'/accept', 409) == 'friend_list_full'


def test_block_ends_everything_and_hides_both_ways(world):
    w = world
    alice, bravo, charlie = w.players('alice', 'bravo', 'charlie')
    w.befriend(alice, bravo)
    w.visit(bravo, alice)
    w.call(charlie, '/v1/friends/requests', username='alice')
    w.presence(bravo, x=1)
    assert 'bravo' in names(w.people(alice)['online'])
    w.call(alice, '/v1/social/blocks', user_id=bravo.id)
    view = w.people(alice)
    assert view['friends'] == [] and names(view['blocked']) == ['bravo']
    assert w.presence(bravo)['visit_ended']['reason'] == 'ended'
    w.tick(social.ROSTER_SECONDS)
    assert 'bravo' not in names(w.people(alice)['online']) and 'alice' not in names(w.people(bravo)['online'])
    # Requests from the blocked player vanish silently; the blocker is told to unblock first.
    assert w.call(bravo, '/v1/friends/requests', username='alice')['state'] == 'sent'
    assert w.people(alice)['requests']['incoming'][0]['username'] == 'charlie' and len(w.people(alice)['requests']['incoming']) == 1
    assert w.refused(alice, '/v1/friends/requests', 409, username='bravo') == 'user_blocked'
    assert w.refused(bravo, '/v1/social/invites', 404, username='alice', kind='village') == 'invite_target_unavailable'
    assert w.refused(alice, '/v1/social/invites', 404, username='bravo', kind='village') == 'invite_target_unavailable'
    assert w.call(bravo, '/v1/social/visit', user_id=alice.id)['state'] == 'asked'
    assert 'knocks' not in w.presence(alice)
    assert w.refused(alice, '/v1/social/blocks', 422, user_id=alice.id) == 'block_self'
    w.call(alice, '/v1/social/blocks/remove', user_id=bravo.id)
    assert w.people(alice)['blocked'] == []
    w.visit(bravo, alice)
    assert w.presence(bravo)['visiting']


def test_roster_privacy(make_world):
    w = make_world()
    alice, bravo, charlie, delta = w.players('alice', 'bravo', 'charlie', 'delta')
    w.befriend(alice, bravo)
    w.visit(charlie, alice)
    for p, place in ((alice, 'village'), (bravo, 'workshop'), (charlie, 'village'), (delta, 'expedition')):
        w.presence(p, scene='village' if place == 'village' else 'away', place=place)
    view = {e['username']: e for e in w.people(alice)['online']}
    assert view['bravo']['where'] == {'place': 'workshop'} and view['bravo']['friend']
    assert view['charlie']['where']['host_name'] == 'alice'      # the same village
    assert 'where' not in view['delta'] and view['delta']['place'] == 'expedition'
    assert set(view['delta']) == {'id', 'username', 'display_name', 'avatar', 'avatar_version', 'friend', 'place'}
    assert names(w.people(alice)['online'])[0] == 'bravo'           # friends first
    assert w.people(delta)['online_count'] == 4
    # Appear offline: gone from every list, shown offline to friends.
    w.call(bravo, '/v1/social/prefs', appear_offline=True)
    w.tick(social.ROSTER_SECONDS)
    w.presence(bravo, scene='away', place='workshop')
    mine = w.people(alice)
    assert 'bravo' not in names(mine['online']) and mine['friends'][0]['online'] is False and mine['friends'][0]['last_seen'] is None
    assert w.presence(alice, since=0)['social']['friends_online'] == 0
    w.call(bravo, '/v1/social/prefs', appear_offline=False, roster='friends')
    w.tick(social.ROSTER_SECONDS)
    for p in (alice, bravo, charlie, delta):
        w.presence(p, scene='away')
    assert 'bravo' in names(w.people(alice)['online']) and 'bravo' not in names(w.people(delta)['online'])
    assert w.presence(alice, since=0)['social']['friends_online'] == 1
    # The operator's setting: friends only, or nobody.
    for setting, seen in (('friends', {'bravo'}), ('off', set())):
        w.settings.social_roster = setting
        assert set(names(w.people(alice)['online'])) == seen and w.people(alice)['roster'] == setting


def test_friends_list_place_last_seen_and_joinable(world):
    w = world
    alice, bravo = w.players('alice', 'bravo')
    w.befriend(alice, bravo)
    w.presence(bravo, scene='home', place='home', floor=1)
    friend = w.people(alice)['friends'][0]
    assert friend['online'] and friend['where'] == {'place': 'home', 'host_id': bravo.id, 'host_name': 'bravo', 'host_display_name': 'bravo', 'floor': 1}
    assert friend['joinable'] and friend['drop_in'] is False and friend['last_seen'] is None
    w.call(bravo, '/v1/social/prefs', drop_in='friends')
    assert w.people(alice)['friends'][0]['drop_in'] is True
    left = w.now[0]
    w.client.post('/v1/social/offline', headers=bravo.headers)
    w.tick(social.ROSTER_SECONDS)
    friend = w.people(alice)['friends'][0]
    assert not friend['online'] and friend['last_seen'] == left and not friend['joinable']


def test_my_village_lists_guests_indoors_invites_and_knocks(world):
    w = world
    alice, bravo, charlie = w.players('alice', 'bravo', 'charlie')
    w.visit(bravo, alice)
    w.presence(bravo, scene='home', place='home', floor=0)
    w.call(alice, '/v1/social/invites', username='charlie', kind='village')
    mine = w.people(alice)['my_village']
    assert mine['host']['username'] == 'alice' and not mine['visiting']
    assert mine['guests'] == [{'id': bravo.id, 'username': 'bravo', 'display_name': 'bravo', 'online': True, 'place': 'home', 'floor': 0}]
    assert names(mine['invites_out']) == ['charlie']
    guest_view = w.people(bravo)['my_village']
    assert guest_view['visiting'] and guest_view['host']['username'] == 'alice' and 'invites_out' not in guest_view
    # The eject button works for a guest indoors.
    w.call(alice, '/v1/social/eject', user_id=bravo.id)
    assert w.people(alice)['my_village']['guests'] == []


def test_drop_in_and_knocks(world):
    w = world
    alice, bravo, charlie, delta, echo = w.players('alice', 'bravo', 'charlie', 'delta', 'echo')
    for p in (bravo, charlie, delta):
        w.befriend(alice, p)
    w.presence(alice, since=0)
    # Friends with drop-in on walk straight in from their village.
    w.call(alice, '/v1/social/prefs', drop_in='friends')
    w.presence(bravo)
    assert w.call(bravo, '/v1/social/visit', user_id=alice.id) == {'state': 'visiting'}
    assert w.presence(bravo)['host_id'] == alice.id
    # From indoors (or with drop-in off) it is a knock the host answers.
    w.presence(charlie, scene='home')
    asked = w.call(charlie, '/v1/social/visit', user_id=alice.id)
    assert asked['state'] == 'asked'
    assert w.refused(charlie, '/v1/social/visit', 429, user_id=alice.id) == 'knock_limited'
    host = w.presence(alice, since=0)
    assert host['social']['knocks'] == 1 and [k['sender'] for k in host['knocks']] == ['charlie']
    assert all(i['kind'] != 'knock' for i in host['invites'])        # released games never see knocks
    knock = host['knocks'][0]['id']
    answer = w.call(alice, '/v1/social/invites/'+knock+'/accept')
    assert answer['knock'] == 'invited'
    invitation = next(i for i in w.get(charlie, '/v1/social')['invites'] if i['kind'] == 'village')
    assert invitation['sender'] == 'alice'
    # A knock from the village goes straight in once accepted.
    w.call(alice, '/v1/social/prefs', drop_in='off')
    w.presence(delta)
    w.call(delta, '/v1/social/visit', user_id=alice.id)
    knock = w.presence(alice)['knocks'][0]['id']
    assert w.call(alice, '/v1/social/invites/'+knock+'/accept')['knock'] == 'visiting'
    assert w.presence(delta)['visiting']
    # Two guests already: the village is full; a declined knock leaves nothing behind.
    w.presence(charlie)
    w.presence(echo)
    w.call(echo, '/v1/social/visit', user_id=alice.id)
    knock = w.presence(alice)['knocks'][0]['id']
    assert w.refused(alice, '/v1/social/invites/'+knock+'/accept', 409) == 'village_full'
    w.call(alice, '/v1/social/invites/'+knock+'/decline')
    assert 'knocks' not in w.presence(alice)
    # A host who is not here: friends are told so; anyone else gets the silent answer (below).
    w.client.post('/v1/social/offline', headers=alice.headers)
    assert w.refused(bravo, '/v1/social/visit', 409, user_id=alice.id) == 'host_offline'
    w.presence(alice, since=0)
    w.call(alice, '/v1/social/prefs', requests='nobody')
    w.tick(61)
    assert w.call(echo, '/v1/social/visit', user_id=alice.id)['state'] == 'asked'
    assert 'knocks' not in w.presence(alice)
    assert w.refused(echo, '/v1/social/visit', 422, user_id=echo.id) == 'visit_self'


def test_strangers_get_the_same_knock_answers_whatever_the_host_does(make_world):
    """A stranger cannot tell from /v1/social/visit whether a host is online, away, hidden
    from them (roster: friends, appear offline) or has blocked them."""
    w = make_world()
    host, other, prying = w.players('host', 'other', 'prying')
    w.presence(other, since=0)

    shown = []

    def answers(who):
        first = w.call(who, '/v1/social/visit', user_id=host.id)
        again = w.refused(who, '/v1/social/visit', 429, user_id=host.id)
        with w.db() as conn:
            shown.append(conn.execute("SELECT count(*) FROM mp_invites WHERE sender_id=? AND kind='knock' AND state='pending'", (who.id,)).fetchone()[0])
        w.tick(61)
        return first['state'], again

    w.presence(host, since=0)
    at_home = answers(prying)
    assert at_home == ('asked', 'knock_limited')
    assert [k['sender'] for k in w.presence(host, since=0)['knocks']] == ['prying']
    cases = []
    w.call(host, '/v1/social/prefs', roster='friends')
    cases.append(answers(prying))
    w.call(host, '/v1/social/prefs', roster='everyone', appear_offline=True)
    cases.append(answers(prying))
    w.call(host, '/v1/social/prefs', appear_offline=False)
    w.visit(host, other)                       # the host is away, visiting
    cases.append(answers(prying))
    w.call(host, '/v1/social/home')
    w.presence(host, since=0)
    w.call(host, '/v1/social/blocks', user_id=prying.id)
    cases.append(answers(prying))
    w.client.post('/v1/social/offline', headers=host.headers)
    w.call(host, '/v1/social/blocks/remove', user_id=prying.id)
    cases.append(answers(prying))              # offline
    assert cases == [at_home]*5
    assert shown == [1, 0, 0, 0, 0, 0]         # only the knock on the host at home reached it


def test_a_new_knock_replaces_the_earlier_one(world):
    w = world
    alice, bravo = w.players('alice', 'bravo')
    w.presence(alice, since=0)
    w.call(bravo, '/v1/social/visit', user_id=alice.id)
    w.tick(61)
    w.presence(alice, since=0)
    w.call(bravo, '/v1/social/visit', user_id=alice.id)
    host = w.presence(alice, since=0)
    assert [k['sender'] for k in host['knocks']] == ['bravo'] and host['social']['knocks'] == 1
    assert names(w.people(alice)['my_village']['knocks']) == ['bravo']


def test_knocking_on_a_released_game_says_it_cannot_answer(world):
    w = world
    alice, bravo, charlie = w.players('alice', 'bravo', 'charlie')
    w.befriend(alice, charlie)
    w.presence(alice)                          # 0.11.x: no since, never shows knocks
    assert w.call(bravo, '/v1/social/visit', user_id=alice.id) == {'state': 'host_cannot_answer'}
    assert w.call(charlie, '/v1/social/visit', user_id=alice.id) == {'state': 'host_cannot_answer'}
    with w.db() as conn:
        assert conn.execute("SELECT count(*) FROM mp_invites WHERE kind='knock'").fetchone()[0] == 0
    w.presence(alice, since=0)                 # the same sign-in on a chat2 game
    w.presence(alice)                          # (a later poll without since keeps it)
    assert w.call(bravo, '/v1/social/visit', user_id=alice.id)['state'] == 'asked'
    assert [k['sender'] for k in w.presence(alice, since=0)['knocks']] == ['bravo']


def test_a_host_away_visiting_cannot_let_a_knock_in(world):
    w = world
    alice, bravo, charlie = w.players('alice', 'bravo', 'charlie')
    w.presence(alice, since=0)
    w.presence(bravo)
    w.call(bravo, '/v1/social/visit', user_id=alice.id)
    knock = w.presence(alice, since=0)['knocks'][0]['id']
    w.visit(alice, charlie)                    # alice goes to charlie's village
    assert w.refused(alice, '/v1/social/invites/'+knock+'/accept', 409) == 'return_home_before_inviting'


def test_my_village_shows_a_guest_appearing_offline_as_offline(world):
    w = world
    alice, bravo = w.players('alice', 'bravo')
    w.visit(bravo, alice)
    w.presence(bravo)
    w.call(bravo, '/v1/social/prefs', appear_offline=True)
    w.tick(4)
    seen = w.people(alice)
    assert seen['online'] == [] and [(g['username'], g['online']) for g in seen['my_village']['guests']] == [('bravo', False)]
    assert [(g['username'], g['online']) for g in w.people(bravo)['my_village']['guests']] == [('bravo', True)]


def test_roster_is_cached_for_three_seconds(world):
    w = world
    alice, bravo = w.players('alice', 'bravo')
    roster = w.app.state.friends.roster
    w.presence(alice)
    w.people(alice)
    builds = roster.rebuilds
    w.presence(bravo)
    w.tick(1)
    assert 'bravo' not in names(w.people(alice)['online']) and roster.rebuilds == builds
    w.presence(alice, since=0)
    assert roster.rebuilds == builds                                     # presence badges share it
    w.tick(3)
    w.presence(bravo)
    assert 'bravo' in names(w.people(alice)['online']) and roster.rebuilds == builds+1


def test_people_has_its_own_rate_limit(world):
    w = world
    alice = w.player('alice')
    for _ in range(social.PEOPLE_PER_MINUTE):
        w.people(alice)
    assert w.get(alice, '/v1/social/people', 429)['detail'] == 'people_rate_limited'
    w.tick(61)
    w.people(alice)


def test_reports_snapshot_the_lines_and_reach_operators(world):
    w = world
    alice, bravo = w.players('alice', 'bravo')
    boss = w.player('teacher_y', role='admin')
    w.visit(bravo, alice)
    line = w.say(bravo, 'you are 시발 bad', channel='local')
    w.say(bravo, 'second line', channel='local')
    report = w.call(alice, '/v1/social/report', user_id=bravo.id, message_id=line['id'], reason='abuse', note='계속 욕해요')
    assert w.call(alice, '/v1/social/report', user_id=bravo.id, message_id=line['id'], reason='abuse') == report
    assert w.get(alice, '/v1/admin/reports', 403)['detail'] == 'admin_only'
    listed = w.get(boss, '/v1/admin/reports')['reports'][0]
    assert listed['reported'] == 'bravo' and listed['reporter'] == 'alice' and listed['text'] == 'you are ** bad'
    assert [c['text'] for c in listed['context']] == ['you are ** bad', 'second line'] and listed['context'][0]['room'] == 'village'
    w.call(boss, '/v1/admin/reports/%d/close' % listed['id'])
    assert w.get(boss, '/v1/admin/reports')['reports'] == []
    assert w.refused(alice, '/v1/social/report', 422, user_id=alice.id, reason='spam') == 'report_self'
    for i in range(social.REPORTS_PER_DAY-1):
        w.call(alice, '/v1/social/report', user_id=bravo.id, message_id=1000+i, reason='spam')
    assert w.refused(alice, '/v1/social/report', 429, user_id=bravo.id, reason='other') == 'report_limited'


def test_a_report_never_attaches_a_line_the_reporter_could_not_read(world):
    w = world
    alice, bravo, charlie = w.players('alice', 'bravo', 'charlie')
    w.befriend(bravo, charlie)
    w.presence(charlie, since=0)
    whisper = w.say(bravo, 'secret for charlie', channel='whisper', to='charlie')
    w.call(bravo, '/v1/party')
    party = w.say(bravo, 'party only', channel='party')
    seen = w.say(bravo, 'hello all', channel='global')
    boss = w.player('teacher_y', role='admin')
    for line in (whisper, party, seen):
        w.call(alice, '/v1/social/report', user_id=bravo.id, message_id=line['id'], reason='abuse')
    stored = {r['message_id']: r['text'] for r in w.get(boss, '/v1/admin/reports')['reports']}
    assert stored == {whisper['id']: None, party['id']: None, seen['id']: 'hello all'}


def test_the_same_report_again_returns_the_first_id_even_past_the_daily_limit(world):
    w = world
    alice = w.player('alice')
    others = w.players(*('r%02d' % i for i in range(social.REPORTS_PER_DAY)))
    first = w.call(alice, '/v1/social/report', user_id=others[0].id, message_id=5, reason='spam')
    for p in others[1:]:
        w.call(alice, '/v1/social/report', user_id=p.id, reason='spam')
    assert w.refused(alice, '/v1/social/report', 429, user_id=others[1].id, message_id=9, reason='spam') == 'report_limited'
    assert w.call(alice, '/v1/social/report', user_id=others[0].id, message_id=5, reason='spam')['id'] == first['id']


def test_prefs_round_trip(world):
    w = world
    alice = w.player('alice')
    assert w.people(alice)['prefs'] == {'appear_offline': False, 'roster': 'everyone', 'requests': 'everyone', 'drop_in': 'off'}
    v = w.people(alice)['v']
    assert w.call(alice, '/v1/social/prefs', requests='nobody', drop_in='friends') == {'appear_offline': False, 'roster': 'everyone', 'requests': 'nobody', 'drop_in': 'friends'}
    assert w.people(alice)['v'] > v
    assert w.client.post('/v1/social/prefs', headers=alice.headers, json={'request_id': '00000000-0000-4000-8000-000000000003', 'drop_in': 'everyone'}).status_code == 422
