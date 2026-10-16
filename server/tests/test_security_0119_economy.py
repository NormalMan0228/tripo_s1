"""0.11.9 reward eligibility must ignore changes to cosmetic request time."""
from datetime import datetime

import pytest

from server import quest_board, quests
from server.tests.social_world import World


@pytest.mark.parametrize('action', ['accept', 'progress'])
@pytest.mark.parametrize('account_night', [False, True])
def test_board_night_rewards_use_fixed_account_time(tmp_path, action, account_night):
    w = World(tmp_path)
    try:
        w.now[0] = datetime(2027, 2, 1, 21 if account_night else 12,
                            tzinfo=quest_board.ZONE).timestamp()
        player = w.player('board_night_boundary')
        quest_id = 'haneul_stars'
        for _ in range(len(quests.QUESTS)):
            if quest_id in quest_board.offers(w.now[0]):
                break
            w.tick(86400)
        else:
            raise AssertionError('night quest never offered')

        # First authentication fixes the account to Korea time. A later header
        # intentionally makes the rendered lighting opposite to reward time.
        assert w.get(player, '/v1/homestead')['night'] == account_night
        player.headers['X-Villagen-UTC-Offset'] = '0'
        assert w.get(player, '/v1/homestead')['night'] != account_night
        path = f'/v1/quest_board/{quest_board.board_day(w.now[0])}/{quest_id}'
        if action == 'accept':
            result = w.call(player, path + '/accept', place='observatory')
            assert result['quest']['state'] == ('ready' if account_night else 'active')
        else:
            w.call(player, path + '/accept')
            if account_night:
                assert w.call(player, path + '/progress', place='observatory')['quest']['state'] == 'ready'
            else:
                assert w.refused(player, path + '/progress', 409,
                                 place='observatory') == 'quest_not_night'

        if account_night:
            result = w.call(player, path + '/complete')
            expected = quests.reward(quest_id, w.settings.quest_stars_scale)
            assert result['stars'] == result['shards'] == expected
            assert w.refused(player, path + '/complete', 409) == 'quest_already_done'
        else:
            assert w.refused(player, path + '/complete', 409) == 'quest_not_ready'
            with w.app.state.db.read() as conn:
                assert conn.execute('SELECT COUNT(*) FROM ledger WHERE user_id=?', (player.id,)).fetchone()[0] == 0
                assert conn.execute('SELECT COUNT(*) FROM npc_letter_events WHERE host_id=?',
                                    (player.id,)).fetchone()[0] == 0
    finally:
        w.close()
