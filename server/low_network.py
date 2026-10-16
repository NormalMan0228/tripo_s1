"""Bounded JSON compression and authenticated conditional polling.

No response is cached on the server: the route (including auth, rate limits and
time-sensitive state) runs before its exact JSON bytes are compared. Presence
is a POST heartbeat, so it is compressed but never answered with HTTP 304.
"""
import gzip
import hashlib
import re
import zlib

from starlette.datastructures import Headers, MutableHeaders


POLL_PATH = re.compile(
    r'/v1/(?:social(?:/people|/whispers/requests)?|studio(?:/library|/jobs/[^/]+)?|generations/[^/]+)'
)


def accepted_encoding(value):
    """Respect explicit q=0 (including an override of a wildcard)."""
    quality = {}
    for entry in value.lower().split(','):
        fields = [part.strip() for part in entry.split(';')]
        if not fields[0]:
            continue
        q = 1.0
        for field in fields[1:]:
            if field.startswith('q='):
                try:
                    q = float(field[2:])
                except ValueError:
                    q = 0.0
        quality[fields[0]] = q if 0.0 <= q <= 1.0 else 0.0
    ranked = [(quality.get(name, quality.get('*', 0.0)), name) for name in ('deflate', 'gzip')]
    q, name = max(ranked)
    return name if q > 0 else None


def etag_matches(value, tag):
    # GET/HEAD If-None-Match uses weak comparison. Our opaque tags are hex, so
    # no embedded comma needs unquoting; unrelated opaque tags cannot match.
    expected = tag.removeprefix('W/')
    return any(part.strip() == '*' or part.strip().removeprefix('W/') == expected
               for part in value.split(','))


def vary(headers, *names):
    values = [part.strip() for part in headers.get('vary', '').split(',') if part.strip()]
    if '*' not in values:
        for name in names:
            if name.lower() not in [value.lower() for value in values]:
                values.append(name)
        headers['vary'] = ', '.join(values)


class LowNetworkMiddleware:
    """Only buffer JSON, at most 4 MiB. Files and streams pass straight through."""

    def __init__(self, app, minimum_size=1024, maximum_size=4 * 1024 * 1024):
        self.app = app
        self.minimum_size = minimum_size
        self.maximum_size = maximum_size

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] == 'HEAD':
            return await self.app(scope, receive, send)
        request = Headers(scope=scope)
        encoding = accepted_encoding(request.get('accept-encoding', ''))
        conditional = scope['method'] == 'GET' and bool(POLL_PATH.fullmatch(scope.get('path', '')))
        start, chunks, size = None, [], 0

        async def transform(message):
            nonlocal start, chunks, size
            if message['type'] == 'http.response.start':
                headers = Headers(raw=message.get('headers', []))
                length = headers.get('content-length', '')
                is_json = headers.get('content-type', '').split(';', 1)[0].strip() == 'application/json'
                if (message['status'] == 200 and is_json and 'content-encoding' not in headers
                        and (not length.isdigit() or int(length) <= self.maximum_size)):
                    start = message
                else:
                    await send(message)
                return
            if message['type'] != 'http.response.body' or start is None:
                await send(message)
                return
            body = message.get('body', b'')
            chunks.append(body)
            size += len(body)
            if size > self.maximum_size:
                # A streaming JSON response without Content-Length may exceed
                # the bound. Flush what we have and stop buffering immediately.
                await send(start)
                start = None
                await send({**message, 'body': b''.join(chunks)})
                chunks = []
                return
            if message.get('more_body', False):
                return
            body = b''.join(chunks)
            headers = MutableHeaders(scope=start)
            vary(headers, 'Accept-Encoding')
            if conditional:
                tag = 'W/"' + hashlib.sha256(body).hexdigest() + '"'
                headers['etag'] = tag
                vary(headers, 'Authorization', 'X-Villagen-Cache', 'X-Villagen-VM', 'X-Villagen-UTC-Offset')
                if request.get('x-villagen-cache') == '1' or 'if-none-match' in request:
                    headers['cache-control'] = 'private, no-cache'
                if etag_matches(request.get('if-none-match', ''), tag):
                    start['status'] = 304
                    for name in ('content-length', 'content-type'):
                        if name in headers:
                            del headers[name]
                    await send(start)
                    await send({'type': 'http.response.body', 'body': b''})
                    return
            if encoding and len(body) >= self.minimum_size:
                compressed = gzip.compress(body, compresslevel=5, mtime=0) if encoding == 'gzip' else zlib.compress(body, 5)
                if len(compressed) < len(body):
                    body = compressed
                    headers['content-encoding'] = encoding
            headers['content-length'] = str(len(body))
            await send(start)
            await send({'type': 'http.response.body', 'body': body})

        await self.app(scope, receive, transform)
