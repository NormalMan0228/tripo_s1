"""The shaper must preserve data, share bandwidth, and count compressed bytes."""
import asyncio
from pathlib import Path
import random
import sys
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
from slow_proxy import Link, SlowProxy


class LinkTests(unittest.TestCase):
    def test_shared_queue_serializes_rate(self):
        link = Link(bits_per_second=8000, rtt=.3, loss=0)
        with patch('slow_proxy.time.perf_counter', return_value=10):
            first = link.reserve(b'x'*1000)
            second = link.reserve(b'x'*1000)
        self.assertEqual(first, (11.15, 0, 0))
        self.assertEqual(second, (12.15, 0, 0))

    def test_loss_costs_bandwidth_and_rtt_without_corruption(self):
        link = Link(bits_per_second=8000, rtt=.3, loss=1)
        with patch('slow_proxy.time.perf_counter', return_value=10):
            arrival, repeated, lost = link.reserve(b'x'*1500)
        self.assertAlmostEqual(arrival, 13.45)
        self.assertEqual((repeated, lost), (1500, 2))


class ProxyTests(unittest.IsolatedAsyncioTestCase):
    async def test_counts_real_delivered_bytes_and_preserves_stream(self):
        body = random.Random(3).randbytes(30000)
        received = []
        async def origin(reader, writer):
            received.append(await reader.readexactly(4))
            writer.write(body)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        server = await asyncio.start_server(origin, '127.0.0.1', 0)
        proxy = SlowProxy(server.sockets[0].getsockname()[1], bits_per_second=8_000_000, rtt=.01, loss=0)
        port = await proxy.listen('asset')
        start = time.perf_counter()
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        writer.write(b'GET!')
        await writer.drain()
        actual = await reader.readexactly(len(body))
        report = proxy.report(start, time.perf_counter())['asset']
        self.assertEqual(received, [b'GET!'])
        self.assertEqual(actual, body)
        self.assertEqual(report['upload_http_bytes'], 4)
        self.assertEqual(report['download_http_bytes'], len(body))
        self.assertEqual(report['http_wire_bytes'], len(body)+4)
        writer.close()
        await writer.wait_closed()
        await proxy.close()
        server.close()
        await server.wait_closed()
