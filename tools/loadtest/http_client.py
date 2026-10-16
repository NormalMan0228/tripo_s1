"""Small asyncio HTTP/1.1 client restricted to the local load-test server.

Only the exception base comes from HTTPX, for the runner's existing error
accounting. Transport, pooling, parsing and JSON handling use the stdlib.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json as jsonlib
import re
import time
from urllib.parse import urlsplit

from httpx import HTTPError, TimeoutException


MAX_BODY = 16 * 1024 * 1024
MAX_HEADERS = 64 * 1024
KEEPALIVE_SECONDS = 4
_TOKEN = re.compile(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+")


class LocalHTTPError(HTTPError):
    """Local transport or framing failure; messages never contain request data."""


@dataclass(slots=True)
class Response:
    status_code: int
    content: bytes

    def json(self):
        return jsonlib.loads(self.content)


@dataclass(eq=False, slots=True)
class _Connection:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    last_used: float


class AsyncClient:
    def __init__(self, base_url, max_connections=6):
        value = str(base_url)
        parsed = urlsplit(value)
        try:
            port = parsed.port
        except ValueError as error:
            raise ValueError("local_http_invalid_base_url") from error
        if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
                or port is None or not 1 <= port <= 65535
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                or any(ord(character) <= 32 for character in value)):
            raise ValueError("local_http_requires_127_0_0_1_and_explicit_port")
        if not isinstance(max_connections, int) or not 1 <= max_connections <= 6:
            raise ValueError("local_http_max_connections_must_be_1_to_6")
        self.base_url = f"http://127.0.0.1:{port}"
        self._port = port
        self._semaphore = asyncio.Semaphore(max_connections)
        self._idle = []
        self._connections = set()
        self._closed = False

    async def __aenter__(self):
        if self._closed:
            raise LocalHTTPError("local_http_client_closed")
        return self

    async def __aexit__(self, *args):
        await self.aclose()

    def _discard(self, connection):
        self._connections.discard(connection)
        connection.writer.close()

    async def _borrow(self):
        if self._closed:
            raise LocalHTTPError("local_http_client_closed")
        while self._idle:
            connection = self._idle.pop()
            if (time.monotonic() - connection.last_used < KEEPALIVE_SECONDS
                    and not connection.reader.at_eof()
                    and not connection.writer.is_closing()):
                return connection
            self._discard(connection)
        reader, writer = await asyncio.open_connection("127.0.0.1", self._port, limit=MAX_HEADERS)
        connection = _Connection(reader, writer, time.monotonic())
        self._connections.add(connection)
        if self._closed:
            self._discard(connection)
            raise LocalHTTPError("local_http_client_closed")
        return connection

    def _request_bytes(self, method, path, body, headers):
        if not isinstance(method, str) or not re.fullmatch(r"[A-Z]+", method):
            raise LocalHTTPError("local_http_invalid_method")
        if (not isinstance(path, str) or not path.startswith("/") or path.startswith("//")
                or "\\" in path or "#" in path
                or any(ord(character) <= 32 or ord(character) >= 127 for character in path)):
            raise LocalHTTPError("local_http_requires_relative_ascii_path")
        fields = {
            "host": f"127.0.0.1:{self._port}", "connection": "keep-alive",
            "accept": "application/json", "accept-encoding": "identity",
        }
        for key, value in (headers or {}).items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise LocalHTTPError("local_http_invalid_header")
            name = key.lower()
            if name in {"host", "connection", "content-length", "transfer-encoding"}:
                raise LocalHTTPError("local_http_reserved_header")
            if (not _TOKEN.fullmatch(key.encode("ascii"))
                    or any(ord(character) < 32 or ord(character) == 127 for character in value)):
                raise LocalHTTPError("local_http_invalid_header")
            fields[name] = value
        payload = b"" if body is None else jsonlib.dumps(body, separators=(",", ":")).encode("utf-8")
        if len(payload) > MAX_BODY:
            raise LocalHTTPError("local_http_request_body_too_large")
        if body is not None:
            fields.setdefault("content-type", "application/json")
        fields["content-length"] = str(len(payload))
        head = (f"{method} {path} HTTP/1.1\r\n" + "".join(
            f"{key}: {value}\r\n" for key, value in fields.items()) + "\r\n").encode("latin-1")
        if len(head) > MAX_HEADERS:
            raise LocalHTTPError("local_http_request_headers_too_large")
        return head + payload

    async def _headers(self, reader):
        raw = await reader.readuntil(b"\r\n\r\n")
        if len(raw) > MAX_HEADERS:
            raise LocalHTTPError("local_http_response_headers_too_large")
        lines = raw[:-4].split(b"\r\n")
        match = re.fullmatch(rb"HTTP/(1\.[01]) ([0-9]{3})(?: [^\r\n]*)?", lines[0])
        if not match:
            raise LocalHTTPError("local_http_invalid_status_line")
        status = int(match[2])
        if not 100 <= status <= 599:
            raise LocalHTTPError("local_http_invalid_status_code")
        fields = {}
        for line in lines[1:]:
            name, colon, value = line.partition(b":")
            if not colon or not _TOKEN.fullmatch(name):
                raise LocalHTTPError("local_http_invalid_response_header")
            key = name.decode("ascii").lower()
            value = value.strip().decode("latin-1")
            # Reject ambiguous framing rather than desynchronizing a reused stream.
            if key in fields and key in {"content-length", "transfer-encoding"}:
                raise LocalHTTPError("local_http_duplicate_framing_header")
            fields[key] = fields[key] + "," + value if key in fields else value
        return match[1], status, fields

    async def _chunked(self, reader):
        content = bytearray()
        while True:
            line = await reader.readuntil(b"\r\n")
            if len(line) > MAX_HEADERS:
                raise LocalHTTPError("local_http_chunk_header_too_large")
            raw_size = line[:-2].split(b";", 1)[0]
            if not re.fullmatch(rb"[0-9a-fA-F]+", raw_size):
                raise LocalHTTPError("local_http_invalid_chunk_size")
            size = int(raw_size, 16)
            if size == 0:
                trailer_size = 0
                while True:
                    trailer = await reader.readuntil(b"\r\n")
                    trailer_size += len(trailer)
                    if trailer_size > MAX_HEADERS:
                        raise LocalHTTPError("local_http_trailers_too_large")
                    if trailer == b"\r\n":
                        return bytes(content)
                    name, colon, _ = trailer[:-2].partition(b":")
                    if not colon or not _TOKEN.fullmatch(name):
                        raise LocalHTTPError("local_http_invalid_trailer")
            if len(content) + size > MAX_BODY:
                raise LocalHTTPError("local_http_response_body_too_large")
            content.extend(await reader.readexactly(size))
            if await reader.readexactly(2) != b"\r\n":
                raise LocalHTTPError("local_http_invalid_chunk_ending")

    async def _response(self, reader, method):
        for _ in range(8):
            version, status, headers = await self._headers(reader)
            if status >= 200:
                break
            if status == 101:
                raise LocalHTTPError("local_http_upgrade_unsupported")
        else:
            raise LocalHTTPError("local_http_too_many_interim_responses")
        connection_tokens = {value.strip().lower() for value in headers.get("connection", "").split(",")}
        reusable = "close" not in connection_tokens and (
            version == b"1.1" or "keep-alive" in connection_tokens)
        if method == "HEAD" or status in (204, 304):
            return Response(status, b""), reusable
        transfer = headers.get("transfer-encoding")
        length = headers.get("content-length")
        if transfer is not None:
            if transfer.lower() != "chunked" or length is not None:
                raise LocalHTTPError("local_http_unsupported_transfer_encoding")
            content = await self._chunked(reader)
        elif length is not None:
            if not re.fullmatch(r"[0-9]+", length) or int(length) > MAX_BODY:
                raise LocalHTTPError("local_http_invalid_content_length")
            content = await reader.readexactly(int(length))
        else:
            # A close-delimited response consumes the connection permanently.
            reusable = False
            chunks, total = [], 0
            while True:
                chunk = await reader.read(min(65536, MAX_BODY + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > MAX_BODY:
                    raise LocalHTTPError("local_http_response_body_too_large")
            content = b"".join(chunks)
        return Response(status, content), reusable

    async def request(self, method, path, json=None, headers=None, timeout=15):
        connection = None
        try:
            async with asyncio.timeout(timeout):
                wire = self._request_bytes(method, path, json, headers)
                async with self._semaphore:
                    connection = await self._borrow()
                    connection.writer.write(wire)
                    await connection.writer.drain()
                    response, reusable = await self._response(connection.reader, method)
                    if reusable and not self._closed:
                        connection.last_used = time.monotonic()
                        self._idle.append(connection)
                        connection = None
                    return response
        except asyncio.CancelledError:
            raise
        except TimeoutError as error:
            raise TimeoutException("local_http_total_timeout") from error
        except HTTPError:
            raise
        except (OSError, ValueError, TypeError, asyncio.IncompleteReadError,
                asyncio.LimitOverrunError) as error:
            raise LocalHTTPError("local_http_" + type(error).__name__) from error
        finally:
            if connection is not None:
                # Closing the transport synchronously preserves the overall
                # deadline, including when cancellation caused this cleanup.
                self._discard(connection)

    async def aclose(self):
        self._closed = True
        self._idle.clear()
        connections = list(self._connections)
        for connection in connections:
            self._discard(connection)
        try:
            async with asyncio.timeout(2):
                await asyncio.gather(*(connection.writer.wait_closed() for connection in connections),
                                     return_exceptions=True)
        except TimeoutError:
            self._connections.clear()
