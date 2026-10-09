"""Day and night follow the player's own time zone (X-Villagen-UTC-Offset, minutes from UTC);
released clients that send nothing keep Korea's +9 h."""
import calendar
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server import homestead
from server.tests.test_studio import account

# 2026-10-09 12:00 UTC: 21:00 in Seoul (night), 08:00 in New York (EDT, day), 13:00 in Paris (CEST).
NOON_UTC = calendar.timegm((2026, 10, 9, 12, 0, 0))


def world(tmp_path):
    app = create_app(Settings(data_dir=tmp_path), clock=lambda: NOON_UTC, worker_enabled=False)
    return TestClient(app)


def night(client, headers, offset=None):
    extra = dict(headers)
    if offset is not None: extra['X-Villagen-UTC-Offset'] = str(offset)
    reply = client.get('/v1/homestead', headers=extra)
    assert reply.status_code == 200, reply.text
    return reply.json()['night']


def test_night_follows_the_players_clock(tmp_path):
    with world(tmp_path) as c:
        a = account(c, 'alice')
        assert night(c, a, 540) is True        # Seoul 21:00
        assert night(c, a, -240) is False      # New York 08:00
        assert night(c, a, 120) is False       # Paris 13:00
        assert night(c, a) is True             # no header: Korea time, as before
        assert night(c, a, 'nonsense') is True  # unreadable: Korea time
        assert night(c, a, 9999) is True       # out of range: Korea time


def test_the_daily_order_resets_at_the_players_midnight():
    token = homestead.UTC_OFFSET.set(540)
    try:
        seoul = homestead.local_day(NOON_UTC)
    finally:
        homestead.UTC_OFFSET.reset(token)
    token = homestead.UTC_OFFSET.set(-600)
    try:
        hawaii = homestead.local_day(NOON_UTC)
    finally:
        homestead.UTC_OFFSET.reset(token)
    # 21:00 on the 9th in Seoul, 02:00 on the 9th in Hawaii: same date, and the UTC date too.
    assert seoul == hawaii == NOON_UTC // 86400
    token = homestead.UTC_OFFSET.set(840)
    try:
        assert homestead.local_day(NOON_UTC) == NOON_UTC // 86400 + 1   # Kiribati is already on the 10th
    finally:
        homestead.UTC_OFFSET.reset(token)
