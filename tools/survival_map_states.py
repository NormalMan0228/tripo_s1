"""Write server-generated survival states for the client map harness (game/tests/survival_maps.gd).

  .tools/server-venv/Scripts/python.exe tools/survival_map_states.py
Each artifacts/survival-maps/state-<map>.json is simulation.new_run(...) passed through public_state, so
the Godot harness dresses exactly what the server would send (obstacles, hazards, 60 resources).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import catalog, simulation  # noqa: E402

OUT = ROOT / 'artifacts/survival-maps'

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    for map_id in catalog.MAPS:
        state = simulation.public_state(simulation.new_run(20261006, 0, 60, map_id))
        (OUT / f'state-{map_id}.json').write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
        print('STATE', map_id, len(state['nodes']), 'nodes', len(state['obstacles']), 'obstacles')
