"""Test bridge for game/tests/life_loop.gd: runs one homestead action with the real
server rules on a JSON state file, so the Godot harness needs no network server.

usage: life_bridge.py <state.json> <body.json> <now>   (prints a JSON reply)
"""
import json, pathlib, sys, uuid
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from server import homestead
from server.models import LifeAction

state_path, body_path, now = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), float(sys.argv[3])
state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else homestead.initial()
body = json.loads(body_path.read_text(encoding='utf-8'))
try:
    if body.get('action') == '__get':
        reply = {'ok': True, 'data': homestead.public(state, now)}
    else:
        body.setdefault('request_id', str(uuid.uuid4()))
        reply = {'ok': True, 'data': homestead.act(state, LifeAction(**body), now)}
        state_path.write_text(json.dumps(state), encoding='utf-8')
except homestead.Rejected as error:
    reply = {'ok': False, 'error': str(error)}
except Exception as error:  # validation errors surface like the API's 422
    reply = {'ok': False, 'error': 'invalid_request', 'detail': str(error)}
print(json.dumps(reply, ensure_ascii=False))
