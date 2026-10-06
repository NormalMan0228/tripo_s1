import json
import math
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders

# Login brute-force protection, counted per (lower-cased) username.
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_LOCK_SECONDS = 15 * 60
MAX_SESSIONS_PER_USER = 5
# Starseeds (users.shards) one admin may grant themselves per UTC day.
ADMIN_DAILY_SHARD_LIMIT = 200000
SECURITY_EVENT_RETENTION_SECONDS = 90 * 86400

# Explicit directional formatting characters (embeddings, overrides, isolates and
# marks). They can make chat or names render reversed/spoofed on other clients.
BIDI_CONTROLS = frozenset('؜‎‏‪‫‬‭‮⁦⁧⁨⁩')


def clean_text(value):
    """Drop ASCII control characters, bidi controls and other non-printable
    characters (C1 controls, zero-width/format characters, line separators)."""
    return ''.join(c for c in value
                   if ord(c) >= 32 and ord(c) != 127 and c not in BIDI_CONTROLS and c.isprintable()).strip()


def record_event(conn, kind, user_id, detail, now):
    conn.execute('INSERT INTO security_events(kind,user_id,detail,created) VALUES (?,?,?,?)',
                 (kind, user_id, None if detail is None else json.dumps(detail, sort_keys=True), now))
    # Bounded retention: failed-login noise must not grow the database forever.
    conn.execute('DELETE FROM security_events WHERE created<?', (now - SECURITY_EVENT_RETENTION_SECONDS,))


def login_retry_after(conn, username, now):
    """Seconds until this username may try again, or 0 when it is not locked.

    Locked once LOGIN_MAX_FAILURES attempts fall inside LOGIN_WINDOW_SECONDS; the
    lock lasts LOGIN_LOCK_SECONDS from the last of them. Rejected (locked)
    attempts are not recorded, so an attacker cannot extend the lock forever."""
    rows = [r[0] for r in conn.execute('SELECT created FROM login_attempts WHERE username=? ORDER BY created DESC LIMIT ?',
                                       (username, LOGIN_MAX_FAILURES))]
    if len(rows) < LOGIN_MAX_FAILURES or rows[0] - rows[-1] > LOGIN_WINDOW_SECONDS:
        return 0
    remaining = rows[0] + LOGIN_LOCK_SECONDS - now
    return max(1, math.ceil(remaining)) if remaining > 0 else 0


class SecurityHeadersMiddleware:
    """Hardening headers on every HTTP response, including early 413/429 replies
    produced by other middleware. Headers are replaced, never duplicated."""
    HEADERS = {'x-content-type-options': 'nosniff', 'x-frame-options': 'DENY', 'referrer-policy': 'no-referrer'}

    def __init__(self, app):
        self.app = app

    @staticmethod
    def sensitive(path):
        return path == '/v1/me' or path.startswith(('/v1/me/', '/v1/auth/', '/v1/admin/'))

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        sensitive = self.sensitive(scope.get('path', ''))

        async def send_with_headers(message):
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)
                for key, value in self.HEADERS.items():
                    headers[key] = value
                # Nothing this API serves is meant for shared caches; credentials,
                # tokens and balances must never be stored.
                if sensitive or 'cache-control' not in headers:
                    headers['cache-control'] = 'no-store'
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodyLimitMiddleware:
    """Bound bytes while receiving, including chunked bodies without Content-Length."""
    def __init__(self, app, limit=8192, path_limits=None):
        self.app, self.limit, self.path_limits = app, limit, path_limits or {}

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in ('POST','PUT','PATCH'):
            return await self.app(scope,receive,send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type']=='http.disconnect': return
            size += len(message.get('body',b''))
            if size>self.path_limits.get(scope.get('path'),self.limit):
                return await JSONResponse({'detail':'body_too_large'},413)(scope,receive,send)
            chunks.append(message.get('body',b''))
            if not message.get('more_body',False): break
        delivered = False
        async def bounded_receive():
            nonlocal delivered
            if delivered: return await receive()
            delivered = True
            return {'type':'http.request','body':b''.join(chunks),'more_body':False}
        await self.app(scope,bounded_receive,send)
