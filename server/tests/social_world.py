"""A test world for the social layer (test_chat.py, test_friends.py): an app on a fake clock and
players made straight in the database (no password hashing, no sign-up rate limit)."""
import hashlib
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings


@dataclass
class Player:
    id: str
    name: str
    headers: dict


class World:
    def __init__(self, tmp_path, **overrides):
        self.now = [1000000.]
        self.settings = Settings(data_dir=tmp_path)
        for key, value in overrides.items():
            setattr(self.settings, key, value)
        self.app = create_app(self.settings, clock=lambda: self.now[0], worker_enabled=False)
        self.client = TestClient(self.app)
        self.client.__enter__()

    def close(self):
        self.client.__exit__(None, None, None)

    def db(self):
        conn = sqlite3.connect(self.settings.data_dir/'world.sqlite3', isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def player(self, name, role='player'):
        user_id, token = str(uuid.uuid4()), secrets.token_urlsafe(24)
        with self.db() as conn:
            conn.execute('INSERT INTO users(id,username,password_hash,shards,created,role) VALUES (?,?,?,?,?,?)', (user_id, name, 'x', 0, self.now[0], role))
            conn.execute('INSERT INTO sessions(token_hash,user_id,expires,created) VALUES (?,?,?,?)',
                         (hashlib.sha256(token.encode()).hexdigest(), user_id, self.now[0]+10**7, self.now[0]))
        return Player(user_id, name, {'Authorization': 'Bearer '+token})

    def players(self, *names):
        return [self.player(n) for n in names]

    def tick(self, seconds):
        self.now[0] += seconds

    def call(self, who, path, status=200, **body):
        response = self.client.post(path, headers=who.headers, json={'request_id': str(uuid.uuid4()), **body})
        assert response.status_code == status, (path, response.status_code, response.text)
        return response.json()

    def refused(self, who, path, status, **body):
        return self.call(who, path, status, **body)['detail']

    def get(self, who, path, status=200):
        response = self.client.get(path, headers=who.headers)
        assert response.status_code == status, (path, response.status_code, response.text)
        return response.json()

    def presence(self, who, status=200, **body):
        response = self.client.post('/v1/social/presence', headers=who.headers, json=body)
        assert response.status_code == status, response.text
        return response.json()

    def say(self, who, text, status=200, **extra):
        self.tick(1.01)
        return self.call(who, '/v1/social/messages', status, text=text, **extra)

    def befriend(self, a, b):
        sent = self.call(a, '/v1/friends/requests', username=b.name)
        self.call(b, '/v1/friends/requests/'+sent['id']+'/accept')

    def visit(self, guest, host):
        """host invites guest into the village, the guest accepts (the released flow)."""
        self.presence(host)
        invite = self.call(host, '/v1/social/invites', username=guest.name, kind='village')
        return self.call(guest, '/v1/social/invites/'+invite['id']+'/accept')

    def people(self, who):
        return self.get(who, '/v1/social/people')
