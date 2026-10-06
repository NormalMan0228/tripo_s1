"""Write the client copy of the authored survival layouts (server/survival_maps.py is the source).

  .tools/server-venv/Scripts/python.exe tools/export_survival_layouts.py
server/tests/test_survival_maps.py fails when game/maps/survival/layouts.json is out of date.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import survival_maps  # noqa: E402

TARGET = ROOT / 'game/maps/survival/layouts.json'


def render():
    return json.dumps(survival_maps.client_export(), ensure_ascii=False, indent=1) + '\n'


if __name__ == '__main__':
    TARGET.write_text(render(), encoding='utf-8')
    print('SURVIVAL_LAYOUTS_EXPORTED', TARGET.relative_to(ROOT).as_posix())
