"""The deploy files hand every VILLAGEN_* setting of server/config.py to the API container:
compose passes only the variables its environment block lists (--env-file only fills ${...})."""
import re
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = sorted(set(re.findall(r"os\.getenv\('(VILLAGEN_[A-Z_]+)'", (ROOT/'server'/'config.py').read_text(encoding='utf-8'))))


def test_config_reads_the_social_settings():
    assert {'VILLAGEN_GLOBAL_CHAT', 'VILLAGEN_SOCIAL_ROSTER', 'VILLAGEN_PRESENCE_BUDGET'} <= set(SETTINGS)


@pytest.mark.parametrize('compose', ['ops/compose.yaml', 'ops/compose.staging.yaml'])
def test_compose_passes_every_villagen_setting(compose):
    text = (ROOT/compose).read_text(encoding='utf-8')
    missing = [name for name in SETTINGS if not re.search(r'^\s+%s: \$\{%s(:-[^}]*)?\}' % (name, name), text, re.M)]
    assert missing == []


@pytest.mark.parametrize('example', ['ops/production.env.example', 'ops/staging.env.example'])
def test_env_examples_document_the_social_settings(example):
    text = (ROOT/example).read_text(encoding='utf-8')
    missing = [name for name in SETTINGS if name != 'VILLAGEN_SERVER_COMMIT' and name+'=' not in text]
    assert missing == []


def test_the_documented_vm_load_test_command_parses_and_keeps_its_report_in_tmp():
    """SOCIAL_API.md 9.4: the load tool runs on the VM inside the development image, with the
    checkout mounted read-only, so its report must go under /tmp."""
    import importlib.util
    import shlex
    doc = (ROOT/'docs'/'design'/'SOCIAL_API.md').read_text(encoding='utf-8')
    line = next(l for l in doc.splitlines() if 'python tools/test_multiplayer_load.py' in l)
    words = shlex.split(line.strip())
    spec = importlib.util.spec_from_file_location('load_tool', ROOT/'tools'/'test_multiplayer_load.py')
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    args = tool.make_parser().parse_args(words[words.index('tools/test_multiplayer_load.py')+1:])
    assert args.output.startswith('/tmp/') and args.workers <= 2 and args.follow_advice
    assert '-v "$PWD:/src:ro"' in doc and '--network none' in doc
