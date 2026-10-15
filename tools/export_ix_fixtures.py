"""Writes the offline fixture plans of every resting archetype (rest 'sit' or 'lie') to
game/tests/fixtures/ix_archetypes.json, for the client socket-derivation check
(game/tests/ix_sources_check.gd). No network, no paid calls.

    .tools/server-venv/Scripts/python.exe tools/export_ix_fixtures.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.archetype_library import ARCHETYPES  # noqa: E402


def main() -> None:
    out = []
    for arch in ARCHETYPES:
        rest = arch.get('rest', '')
        fixture = arch.get('fixture')
        if rest not in ('sit', 'lie') or not fixture:
            continue
        parts = []
        for p in fixture['parts']:
            parts.append({'id': p['id'], 'parent': p.get('parent', ''), 'shape': p.get('shape', 'box'), 'size': p['size'],
                          'position': p['position'], 'rotation': p.get('rotation', [0, 0, 0]), 'pivot': p.get('pivot', [0, 0, 0])})
        out.append({'id': arch['id'], 'rest': rest, 'family': arch.get('family', ''), 'title': fixture.get('title', ''), 'parts': parts})
    target = ROOT / 'game' / 'tests' / 'fixtures' / 'ix_archetypes.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({'version': 1, 'archetypes': out}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('IX_FIXTURES', len(out), ' '.join(a['id'] for a in out))


if __name__ == '__main__':
    main()
