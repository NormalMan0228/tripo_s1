"""Loopback TCP link shaper. Counts HTTP wire bytes before decompression.

Shared 1.5 Mbit/s per direction, 150 ms propagation each way, deterministic
1% loss of modeled 1460-byte segments: retransmission bandwidth + one RTT.
This is an application-level approximation, not kernel packet loss.
"""
import asyncio
from collections import Counter, defaultdict
import random
import time


class Link:
    def __init__(self, bits_per_second=1_500_000, rtt=.3, loss=.01, seed=119):
        self.rate, self.rtt, self.loss = bits_per_second / 8, rtt, loss
        self.random, self.available = random.Random(seed), 0.0

    def reserve(self, data):
        repeated = lost = 0
        for offset in range(0, len(data), 1460):
            if self.random.random() < self.loss:
                repeated += min(1460, len(data) - offset)
                lost += 1
        self.available = max(time.perf_counter(), self.available) + (len(data) + repeated) / self.rate
        return self.available + self.rtt / 2 + (self.rtt if repeated else 0), repeated, lost


class SlowProxy:
    def __init__(self, upstream_port, **settings):
        self.upstream_port = upstream_port
        self.links = {name: Link(**settings) for name in ("upload", "download")}
        self.servers, self.tasks, self.events = [], set(), []

    async def listen(self, category):
        server = await asyncio.start_server(lambda reader, writer: self.accept(category, reader, writer), "127.0.0.1", 0)
        self.servers.append(server)
        return server.sockets[0].getsockname()[1]

    async def accept(self, category, reader, writer):
        task, upstream = asyncio.current_task(), None
        self.tasks.add(task)
        try:
            target, upstream = await asyncio.open_connection("127.0.0.1", self.upstream_port)
            await asyncio.gather(self.relay(category, "upload", reader, upstream), self.relay(category, "download", target, writer))
        except (ConnectionError, OSError, asyncio.CancelledError):
            pass
        finally:
            writer.close()
            if upstream:
                upstream.close()
            self.tasks.discard(task)

    async def relay(self, category, direction, reader, writer):
        queue, link = asyncio.Queue(maxsize=4), self.links[direction]

        async def receive():
            try:
                while data := await reader.read(16384):
                    arrival, repeated, lost = link.reserve(data)
                    await queue.put((arrival, data, repeated, lost))
            finally:
                await queue.put(None)

        producer = asyncio.create_task(receive())
        try:
            while item := await queue.get():
                arrival, data, repeated, lost = item
                await asyncio.sleep(max(0, arrival - time.perf_counter()))
                writer.write(data)
                await writer.drain()
                self.events.append((time.perf_counter(), category, direction, len(data), repeated, lost))
            if writer.can_write_eof():
                writer.write_eof()
        finally:
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)

    def report(self, start, end):
        groups = defaultdict(Counter)
        for stamp, category, direction, size, repeated, lost in self.events:
            if start <= stamp <= end:
                row = groups[category]
                row[direction + "_http_bytes"] += size
                row["http_wire_bytes"] += size
                row["modeled_retransmitted_bytes"] += repeated
                row["modeled_lost_segments"] += lost
        return {category: {**row, "http_wire_bytes_per_minute": round(row["http_wire_bytes"] * 60 / (end - start), 2)} for category, row in groups.items()}

    async def close(self):
        for server in self.servers:
            server.close()
        await asyncio.gather(*(server.wait_closed() for server in self.servers))
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
