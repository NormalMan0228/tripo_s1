"""실제 연결 없이 가짜 asyncio 스트림으로 HTTP 클라이언트를 검증한다."""

import asyncio
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from http_client import AsyncClient, LocalHTTPError, MAX_BODY, MAX_HEADERS
from httpx import TimeoutException


class FakeWriter:
    def __init__(self):
        self.closed = False
        self.writes = []
        self.started = asyncio.Event()

    def write(self, data):
        self.writes.append(data)

    async def drain(self):
        self.started.set()

    def is_closing(self):
        return self.closed

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass


def fake_stream(data=b""):
    reader = asyncio.StreamReader(limit=MAX_HEADERS)
    reader.feed_data(data)
    return reader, FakeWriter()


def response(status=200, body=b"{}", extra=b""):
    return (b"HTTP/1.1 " + str(status).encode() + b" OK\r\nContent-Length: "
            + str(len(body)).encode() + b"\r\n" + extra + b"\r\n" + body)


class 로컬HTTP회귀테스트(unittest.IsolatedAsyncioTestCase):
    async def test_연결을_재사용하고_만료시키며_redirect는_따르지_않는다(self):
        first = fake_stream(response() + response(302, extra=b"Location: https://example.invalid/\r\n"))
        second = fake_stream(response())
        connect = AsyncMock(side_effect=[first, second])
        with patch("http_client.asyncio.open_connection", connect):
            async with AsyncClient("http://127.0.0.1:12345") as client:
                self.assertEqual((await client.request("GET", "/health")).json(), {})
                self.assertEqual((await client.request("GET", "/redirect")).status_code, 302)
                self.assertEqual(connect.await_count, 1)
                client._idle[0].last_used -= 5
                self.assertEqual((await client.request("GET", "/after-expiry")).status_code, 200)
                self.assertTrue(first[1].closed)
                self.assertEqual(connect.await_count, 2)
        connect.assert_called_with("127.0.0.1", 12345, limit=MAX_HEADERS)
        self.assertTrue(second[1].closed)

    async def test_중간응답과_chunked_JSON과_trailer를_읽는다(self):
        body = json.dumps({"a": 1}, separators=(",", ":")).encode()
        raw = (b"HTTP/1.1 100 Continue\r\n\r\nHTTP/1.1 200 OK\r\n"
               b"Transfer-Encoding: chunked\r\n\r\n" + format(len(body), "x").encode()
               + b";extension=value\r\n" + body + b"\r\n0\r\nX-Test: yes\r\n\r\n")
        reader, writer = fake_stream(raw)
        with patch("http_client.asyncio.open_connection", AsyncMock(return_value=(reader, writer))):
            async with AsyncClient("http://127.0.0.1:12345") as client:
                answer = await client.request("POST", "/json", json={"sent": True})
                self.assertEqual(answer.json(), {"a": 1})
                head, payload = writer.writes[0].split(b"\r\n\r\n", 1)
                self.assertIn(b"POST /json HTTP/1.1", head)
                self.assertEqual(json.loads(payload), {"sent": True})

    async def test_외부_URL과_경로와_헤더_주입을_연결_전에_차단한다(self):
        connect = AsyncMock(side_effect=AssertionError("실제 연결 금지"))
        with patch("http_client.asyncio.open_connection", connect):
            for url in ("https://127.0.0.1:12", "http://example.invalid:12",
                        "http://127.0.0.1", "http://127.0.0.1:12/path",
                        "http://user@127.0.0.1:12"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    AsyncClient(url)
            async with AsyncClient("http://127.0.0.1:12345") as client:
                for path in ("https://example.invalid/", "//example.invalid/",
                             "/x\r\nHost: bad", "/a\\b"):
                    with self.subTest(path=path), self.assertRaises(LocalHTTPError):
                        await client.request("GET", path)
                for headers in ({"Host": "example.invalid"}, {"X-Test": "bad\r\nInjected: yes"}):
                    with self.subTest(headers=headers), self.assertRaises(LocalHTTPError):
                        await client.request("GET", "/", headers=headers)
        connect.assert_not_awaited()

    async def test_본문과_헤더_상한_및_모호한_프레이밍을_거부한다(self):
        invalid = [
            b"HTTP/1.1 200 OK\r\nContent-Length: " + str(MAX_BODY + 1).encode() + b"\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nX: " + b"x" * MAX_HEADERS + b"\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Length: 2\r\n\r\n{}",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
            + format(MAX_BODY + 1, "x").encode() + b"\r\n",
        ]
        for index, raw in enumerate(invalid):
            with self.subTest(case=index):
                reader, writer = fake_stream(raw)
                with patch("http_client.asyncio.open_connection", AsyncMock(return_value=(reader, writer))):
                    async with AsyncClient("http://127.0.0.1:12345") as client:
                        with self.assertRaises(LocalHTTPError):
                            await client.request("GET", "/invalid")
                        self.assertTrue(writer.closed)

    async def test_전체_제한시간과_취소가_연결을_닫으며_전파된다(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel):
                reader, writer = fake_stream()
                with patch("http_client.asyncio.open_connection", AsyncMock(return_value=(reader, writer))):
                    async with AsyncClient("http://127.0.0.1:12345") as client:
                        task = asyncio.create_task(client.request("GET", "/slow", timeout=5 if cancel else .01))
                        await asyncio.wait_for(writer.started.wait(), 1)
                        if cancel:
                            task.cancel()
                        with self.assertRaises(asyncio.CancelledError if cancel else TimeoutException):
                            await task
                        self.assertTrue(writer.closed)

    async def test_일곱_동시요청도_연결_여섯개를_넘지_않는다(self):
        opened = []

        async def connect(*args, **kwargs):
            pair = fake_stream()
            opened.append(pair)
            return pair

        with patch("http_client.asyncio.open_connection", connect):
            async with AsyncClient("http://127.0.0.1:12345", max_connections=6) as client:
                tasks = [asyncio.create_task(client.request("GET", "/pool")) for _ in range(7)]
                try:
                    for _ in range(10):
                        await asyncio.sleep(0)
                    self.assertEqual(len(opened), 6)
                    for reader, _ in opened:
                        reader.feed_data(response() + response())
                    answers = await asyncio.wait_for(asyncio.gather(*tasks), 1)
                    self.assertTrue(all(answer.status_code == 200 for answer in answers))
                    self.assertEqual(len(opened), 6)
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    unittest.main()
