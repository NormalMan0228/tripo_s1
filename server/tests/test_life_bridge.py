"""The local Godot harness keeps the same refusal contract as the HTTP API."""
import json
import runpy
import sys
from pathlib import Path

import pytest

from server import homestead


BRIDGE = Path(__file__).resolve().parents[2] / 'tools' / 'life_bridge.py'


@pytest.mark.parametrize('balance,code', [(0, 'life_not_enough_coins'),
                                         ('12', 'invalid_coin_balance'),
                                         (True, 'invalid_coin_balance'),
                                         (1.0, 'invalid_coin_balance')])
def test_leaf_coin_refusals_preserve_bridge_error_and_state(tmp_path, monkeypatch, capsys, balance, code):
    state_path = tmp_path / 'state.json'
    body_path = tmp_path / 'body.json'
    state = homestead.initial()
    state['coins'] = balance
    state_path.write_text(json.dumps(state), encoding='utf-8')
    before = state_path.read_bytes()
    body_path.write_text(json.dumps({'version': 0, 'action': 'buy', 'item': 'bait'}), encoding='utf-8')
    monkeypatch.setattr('sys.argv', [str(BRIDGE), str(state_path), str(body_path), '1000000'])
    # The script imports the workspace for standalone Godot calls; contain that path edit.
    monkeypatch.setattr('sys.path', list(sys.path))

    runpy.run_path(str(BRIDGE), run_name='__main__')

    assert json.loads(capsys.readouterr().out) == {'ok': False, 'error': code}
    assert state_path.read_bytes() == before
