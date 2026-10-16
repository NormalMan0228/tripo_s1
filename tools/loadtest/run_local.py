"""Loopback-only 0.11.8 workload. See docs/LOADTEST_0118_KO.md.

No server patching, account seeding, real credentials, or remote URL option.
One asyncio load generator; one unmodified Uvicorn worker. All output and
temporary server data stay below tools/loadtest/. Run with the server venv.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
import json
import hashlib
import math
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SERVER_PYTHON = Path(r"C:\lsm26\triphthonS1\.tools\server-venv\Scripts\python.exe")
sys.path.insert(0, str(HERE))
from metrics import db_sizes, percentile, process_sample, stop_process_tree


def loopback_guard(event, args):
    """Fail closed before socket/DNS activity, including inside the server child."""
    if event in {"socket.connect", "socket.bind", "socket.sendto"}:
        address = args[-1]
        if not isinstance(address, tuple) or address[0] != "127.0.0.1":
            raise PermissionError("loadtest_loopback_only")
    elif event == "socket.getaddrinfo" and args[0] != "127.0.0.1":
        raise PermissionError("loadtest_no_remote_dns")
    elif event in {"socket.gethostbyname", "socket.gethostbyaddr"} and args[0] != "127.0.0.1":
        raise PermissionError("loadtest_no_remote_dns")


def safe_env(data, craft_mode):
    # An allowlist avoids inheriting API keys, secret-file paths, proxies or .envs.
    names = {"SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "COMSPEC", "SYSTEMDRIVE"}
    env = {k: v for k, v in os.environ.items() if k.upper() in names}
    env.update(TEMP=str(data), TMP=str(data), PYTHONDONTWRITEBYTECODE="1",
               PYTHONUTF8="1", PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1",
               OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               TRIPOTHON_DATA_DIR=str(data), TRIPOTHON_MODE="demo",
               TRIPOTHON_STUDIO_LLM="fixture", TRIPOTHON_FAKE_TRIPO="true",
               TRIPO_ENABLE_PAID="true" if craft_mode == "tripo" else "false",
               TRIPO_DAILY_REQUEST_LIMIT="0", TRIPOTHON_ENVIRONMENT="loadtest")
    return env


def serve(port):
    sys.addaudithook(loopback_guard)
    sys.path.insert(0, str(ROOT))
    import uvicorn
    uvicorn.run("server.app:create_app", factory=True, host="127.0.0.1", port=port,
                workers=1, access_log=False, proxy_headers=False, log_level="warning")


def route_key(method, path):
    path = re.sub(r"/[0-9a-f]{8}-[0-9a-f-]{27,}(?=/|$)", "/{id}", path)
    return method + " " + path


async def gather_owned(coroutines):
    """Do not leave setup siblings running if one fails or the budget expires."""
    tasks = [asyncio.create_task(coro) for coro in coroutines]
    try:
        return await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class Measurements:
    def __init__(self):
        self.phase = "setup"
        self.rows = defaultdict(list)
        self.details = Counter()
        self.lock_responses = 0
        self.bytes_received = Counter()

    def record(self, phase, route, elapsed, status, detail, size):
        self.rows[(phase, route)].append((elapsed * 1000, status))
        self.bytes_received[phase] += size
        if status != "200":
            # Only a short server error CODE, never bodies/tokens/user data.
            detail = detail if isinstance(detail, str) and re.fullmatch(r"[a-zA-Z0-9_. -]{1,100}", detail) else "non_code_detail"
            self.details[(phase, route, status, detail)] += 1
        if "locked" in (detail or "").lower():
            self.lock_responses += 1

    def report(self):
        result = {}
        for (phase, route), rows in sorted(self.rows.items()):
            latency = [row[0] for row in rows]
            good = [row[0] for row in rows if row[1] == "200"]
            result.setdefault(phase, {})[route] = {
                "requests": len(rows), "status_counts": dict(Counter(row[1] for row in rows)),
                **{f"p{p}_ms": percentile(latency, p) for p in (50, 95, 99)},
                "max_ms": round(max(latency), 3),
                "success_p95_ms": percentile(good, 95),
            }
        return {"endpoints": result, "error_details": [
            {"phase": k[0], "endpoint": k[1], "status": k[2], "detail": k[3], "count": count}
            for k, count in sorted(self.details.items())],
            "sqlite_lock_response_count": self.lock_responses,
            "response_bytes": dict(self.bytes_received)}


class Scenario:
    def __init__(self, client, players, seconds, craft_mode, http_client="stdlib"):
        self.client, self.n, self.seconds, self.craft_mode = client, players, seconds, craft_mode
        self.http_client = http_client
        self.metrics = Measurements()
        self.people = []
        self.player_clients = []
        self.tasks = []
        self.stop = False
        self.started = None
        self.ended = None
        self.coverage = Counter()
        self.craft_results = Counter()
        self.craft_seconds = []
        self.advice = []
        self.presence_gaps = []
        self.loop_lag = []
        self.errors = []

    async def request(self, p, method, path, body=None, timeout=15):
        headers = {}
        if p and p.get("token"):
            headers["Authorization"] = "Bearer " + p["token"]
        start, phase = time.perf_counter(), self.metrics.phase
        detail, size, value = "", 0, {}
        try:
            # Separate small pools avoid HTTPX's shared-pool reassignment cost
            # growing with every queued player request. No extra threads.
            client = p.get("client", self.client) if p else self.client
            r = await client.request(method, path, json=body, headers=headers, timeout=timeout)
            status, size = str(r.status_code), len(r.content)
            try:
                value = r.json()
            except ValueError:
                value = {}
            detail = value.get("detail", "http_error") if isinstance(value, dict) else "http_error"
        except asyncio.CancelledError:
            self.metrics.record(phase, route_key(method, path), time.perf_counter() - start,
                                "cancelled_at_shutdown", "cancelled_at_shutdown", 0)
            raise
        except Exception as error:
            import httpx
            if not isinstance(error, httpx.HTTPError):
                raise
            status, detail = "transport_error", type(error).__name__
        self.metrics.record(phase, route_key(method, path), time.perf_counter() - start, status, detail, size)
        return (value if isinstance(value, dict) else {}), status

    async def post(self, p, path, **body):
        return await self.request(p, "POST", path, {"request_id": str(uuid.uuid4()), **body})

    async def required(self, p, method, path, body=None):
        value, status = await self.request(p, method, path, body)
        if status != "200":
            raise RuntimeError(f"setup_failed: {route_key(method, path)} {status}")
        return value

    async def mutate_required(self, p, path, **body):
        return await self.required(p, "POST", path, {"request_id": str(uuid.uuid4()), **body})

    async def presence(self, p):
        now = time.perf_counter()
        body = {"scene": p["scene"], "place": p["scene"], "floor": 0,
                "x": math.sin(now) * 1.5, "z": math.cos(now) * 1.5,
                "y": 0, "yaw": 0, "vx": 1.5 * math.cos(now), "vz": -1.5 * math.sin(now),
                "t": now % 100000, "since": p["cursor"]}
        value, status = await self.request(p, "POST", "/v1/social/presence", body, timeout=4)
        if status == "200":
            p["cursor"] = (value.get("chat") or {}).get("cursor", p["cursor"])
            if self.metrics.phase == "load":
                advice = (value.get("social") or {}).get("poll", {}).get("together")
                if advice is not None:
                    self.advice.append(advice)
        return value, status

    async def periodic(self, p, interval, action, condition=lambda: True, is_presence=False):
        await asyncio.sleep(p["index"] / self.n * interval)
        previous = None
        while not self.stop:
            tick = time.perf_counter()
            if condition():
                if is_presence and self.metrics.phase == "load" and previous is not None:
                    self.presence_gaps.append((tick - previous) * 1000)
                await action()
                previous = tick
            # Match the client's pending guard: no parallel requests for one
            # poller, and no catch-up bursts when a response exceeds the period.
            await asyncio.sleep(max(0, interval - (time.perf_counter() - tick)))

    async def setup(self, restart_server):
        # Two concurrent Argon2 registrations, not N hashing threads at once.
        gate = asyncio.Semaphore(2)
        async def register(index):
            async with gate:
                p = {"index": index, "name": f"load_{index:03d}", "cursor": 0, "scene": "village",
                     "host": index % 2 == 0}
                import httpx
                if self.http_client == "stdlib":
                    from http_client import AsyncClient
                    p["client"] = AsyncClient(self.client.base_url)
                else:
                    p["client"] = httpx.AsyncClient(base_url=self.client.base_url, trust_env=False,
                        follow_redirects=False, limits=httpx.Limits(max_connections=6,
                        max_keepalive_connections=6, keepalive_expiry=4))
                self.player_clients.append(p["client"])
                password = "Loadtest-only-" + uuid.uuid4().hex
                value = await self.required(p, "POST", "/v1/auth/register",
                                            {"username": p["name"], "password": password})
                p["token"] = value["token"]
                self.coverage["registered"] += 1
                return p
        # Demo mode accepts only actual loopback identity. Its unchanged auth
        # limit is 20/IP/minute. Register in batches of 20, restarting our owned
        # server between batches (same temporary DB). This models pre-existing
        # accounts, not a simultaneous sign-up burst; no direct DB seeding.
        for offset in range(0, self.n, 20):
            if offset:
                await restart_server()
                self.coverage["setup_server_restarts"] += 1
            self.people.extend(await gather_owned(register(i) for i in range(offset, min(offset + 20, self.n))))
        pair_gate = asyncio.Semaphore(3)

        async def visit(host, guest):
            invite = await self.mutate_required(host, "/v1/social/invites", username=guest["name"], kind="village")
            await self.mutate_required(guest, f"/v1/social/invites/{invite['id']}/accept")
            host["scene"] = "home"
            await self.presence(host)
            access = await self.required(guest, "GET", "/v1/home/access")
            if not access.get("open"):
                raise RuntimeError("home_door_not_open")
            guest["scene"] = "home"
            home, status = await self.presence(guest)
            if status != "200" or not (home.get("home") or {}).get("open") or not home.get("space"):
                raise RuntimeError("home_visit_not_confirmed")
            await self.required(host, "GET", "/v1/studio")
            self.coverage["visited_another_home"] += 1
            host["scene"] = guest["scene"] = "village"
            await self.presence(host)
            await self.presence(guest)

        async def pair(a, b):
            async with pair_gate:
                await visit(b, a)
                await self.mutate_required(a, "/v1/social/home")
                await visit(a, b)
                sent = await self.mutate_required(a, "/v1/social/messages", text="hello privately",
                                                  channel="whisper", to=b["name"])
                if sent.get("state") != "requested":
                    raise RuntimeError("whisper_request_not_created")
                inbox = await self.required(b, "GET", "/v1/social/whispers/requests")
                ident = sent["request"]["id"]
                if not any(row["id"] == ident for row in inbox.get("requests", [])):
                    raise RuntimeError("whisper_request_missing_from_inbox")
                reply = await self.mutate_required(b, f"/v1/social/whispers/requests/{ident}/accept")
                if reply.get("state") != "accepted":
                    raise RuntimeError("whisper_request_not_accepted")
                self.coverage["whisper_requests_accepted"] += 1
                for p in (a, b):
                    p["peer"] = b if p is a else a
                    self.tasks.append(asyncio.create_task(self.periodic(
                        p, .25, lambda p=p: self.presence(p), is_presence=True)))
        await gather_owned(pair(self.people[i], self.people[i + 1]) for i in range(0, self.n, 2))

    async def diagnostic_setup(self, data):
        """Supplemental capacity probe only; never presented as API workflow QA."""
        sys.path.insert(0, str(ROOT / "tools"))
        from test_multiplayer_load import seed
        seeded = seed(data / "world.sqlite3", self.n, 0, 0, 1, 7)
        from http_client import AsyncClient
        with closing(sqlite3.connect(data / "world.sqlite3", timeout=15)) as conn:
            conn.execute("DELETE FROM mp_visits")
            for i in range(0, self.n, 2):
                a, b = seeded[i:i + 2]
                conn.execute("INSERT INTO mp_visits VALUES (?,?,?)", (b["id"], a["id"], time.time() + 600))
                for x, y in ((a, b), (b, a)):
                    conn.execute("INSERT OR IGNORE INTO social_friends VALUES (?,?,?)", (x["id"], y["id"], time.time()))
            conn.execute("UPDATE users SET shards=80")
            conn.commit()
        for index, entry in enumerate(seeded):
            client = AsyncClient(self.client.base_url)
            self.player_clients.append(client)
            self.people.append({"index": index, "name": entry["name"], "cursor": 0,
                "scene": "village", "host": index % 2 == 0, "client": client,
                "token": entry["headers"]["Authorization"][7:]})
        for i, p in enumerate(self.people):
            p["peer"] = self.people[i ^ 1]
            self.tasks.append(asyncio.create_task(self.periodic(p, .25, lambda p=p: self.presence(p), is_presence=True)))
        self.coverage["seeded_diagnostic_accounts"] = self.n

    async def chat(self, p):
        # User behavior, not a client poll interval. Spread global sends below
        # the server-wide 20/10 s cap (all 100 players send within 75 seconds).
        schedule = ((3 + p["index"] * .03, "local"), (7 + p["index"] * .03, "whisper"),
                    (12 + p["index"] * .60, "global"))
        if self.coverage["seeded_diagnostic_accounts"]:
            # Explicit burst diagnostic: global policy rejections are expected.
            schedule = ((1 + p["index"] * .01, "local"), (4 + p["index"] * .01, "whisper"),
                        (7 + p["index"] * .02, "global"))
        for delay, channel in schedule:
            await asyncio.sleep(max(0, self.started + delay - time.perf_counter()))
            if self.stop:
                return
            body = {"text": f"hello {channel} from player {p['index']}", "channel": channel}
            if channel == "whisper":
                body["to"] = p["peer"]["name"]
            value, status = await self.post(p, "/v1/social/messages", **body)
            self.coverage["chat_" + channel + ("_ok" if status == "200" and "id" in value else "_failed")] += 1

    async def craft(self, p):
        await asyncio.sleep(2 + p["index"] * .04)
        before = time.perf_counter()
        body = {"prompt": "tiny mushroom stool", "motion": "static", "concept": False,
                "material": "mesh", "geometry": "proxy", "designer": "fixture"}
        if self.craft_mode == "tripo":
            body.update(geometry="tripo", designer="simple", mesh_model="v3.1-20260211")
        value, status = await self.post(p, "/v1/studio/jobs", **body)
        self.coverage["craft_attempted"] += 1
        if status != "200":
            self.craft_results["rejected_" + status + "_" + str(value.get("detail", "transport"))] += 1
            return
        ident = value["id"]
        self.coverage["craft_accepted"] += 1
        failures = 0
        while not self.stop:
            value, status = await self.request(p, "GET", f"/v1/studio/jobs/{ident}")
            if status != "200":
                failures += 1
                if status in ("401", "404"):
                    self.craft_results["poll_" + status] += 1
                    return
                await asyncio.sleep(min(30, 2 ** (min(failures, 4) + 1)))
                continue
            failures = 0
            state = value.get("state")
            if state in {"ready", "failed", "cancelled", "unknown"}:
                self.craft_results[state] += 1
                if state == "ready":
                    self.craft_seconds.append(time.perf_counter() - before)
                    provenance = value.get("provenance") or {}
                    self.coverage["craft_geometry_" + str(provenance.get("geometry"))] += 1
                    if self.craft_mode == "tripo" and provenance.get("tripo_credits_consumed") == 0:
                        self.coverage["fake_tripo_zero_credits"] += 1
                return
            if state == "awaiting_confirmation":
                _, confirm_status = await self.post(p, f"/v1/studio/jobs/{ident}/confirm", use_concept=False)
                if confirm_status != "200":
                    self.craft_results["confirm_rejected_" + confirm_status] += 1
                    return
            await asyncio.sleep(2)
        self.craft_results["unfinished"] += 1

    async def lag_monitor(self):
        while not self.stop:
            tick = time.perf_counter()
            await asyncio.sleep(.25)
            self.loop_lag.append(max(0, time.perf_counter() - tick - .25) * 1000)

    async def load(self):
        self.metrics.phase = "load"
        self.started = time.perf_counter()
        for p in self.people:
            self.tasks.extend([
                asyncio.create_task(self.periodic(p, 4, lambda p=p: self.request(p, "GET", "/v1/social/whispers/requests"))),
                asyncio.create_task(self.periodic(p, 5, lambda p=p: self.request(p, "GET", "/v1/social/people"))),
                asyncio.create_task(self.periodic(p, 3, lambda p=p: self.request(p, "GET", "/v1/me"), lambda p=p: p["host"])),
                asyncio.create_task(self.chat(p)), asyncio.create_task(self.craft(p))])
        self.tasks.append(asyncio.create_task(self.lag_monitor()))
        await asyncio.sleep(self.seconds)
        self.ended = time.perf_counter()
        self.stop = True
        self.metrics.phase = "drain"
        # Finish in-flight HTTP requests so timeouts are counted, then cancel
        # sleeping pollers. Shutdown requests are not part of the load sample.
        await asyncio.sleep(4.5)
        self.metrics.phase = "teardown"

    async def close(self):
        self.stop = True
        for task in self.tasks:
            if not task.done():
                task.cancel()
        results = await asyncio.gather(*self.tasks, return_exceptions=True)
        self.errors += [type(result).__name__ for result in results
                        if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError)]
        await asyncio.gather(*(client.aclose() for client in self.player_clients))

    def report(self):
        result = self.metrics.report()
        duration = (self.ended or time.perf_counter()) - self.started if self.started else 0
        endpoints = result["endpoints"].get("load", {})
        requests = sum(row["requests"] for row in endpoints.values())
        presence = endpoints.get("POST /v1/social/presence", {}).get("requests", 0)
        result.update(players=self.n, craft_mode=self.craft_mode, duration_seconds=round(duration, 3),
                      requests_per_second=round(requests / duration, 3) if duration else None,
                      presence_requests_per_second=round(presence / duration, 3) if duration else None,
                      target_presence_per_second=self.n * 4, coverage=dict(self.coverage),
                      craft_results=dict(self.craft_results), task_errors=self.errors,
                      craft_seconds={f"p{p}": percentile(self.craft_seconds, p) for p in (50, 95, 99)},
                      presence_start_gap_ms={f"p{p}": percentile(self.presence_gaps, p) for p in (50, 95, 99)},
                      generator_event_loop_lag_ms={f"p{p}": percentile(self.loop_lag, p) for p in (50, 95, 99)},
                      server_advice_together_seconds_max=max(self.advice, default=None))
        # A 200-only HTTP summary is insufficient: check actual home/whisper/
        # craft completion. Diagnostic Tripo runs deliberately expose rejection.
        result["workflow_complete"] = (self.coverage["registered"] == self.n
            and self.coverage["visited_another_home"] == self.n
            and self.coverage["whisper_requests_accepted"] == self.n // 2
            and all(self.coverage["chat_" + channel + "_ok"] == self.n for channel in ("local", "global", "whisper"))
            and self.craft_results["ready"] == self.n and not self.errors)
        return result


def checkpoint(data):
    with closing(sqlite3.connect(data / "world.sqlite3", timeout=15)) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        pages = conn.execute("PRAGMA page_count").fetchone()[0]
        free = conn.execute("PRAGMA freelist_count").fetchone()[0]
        rows = {table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in ("users", "studio_jobs", "mp_messages", "requests")}
    return {"journal_mode": mode, "pages": pages, "free_pages": free, "rows": rows, **db_sizes(data)}


async def run_one(n, args, remaining):
    import httpx
    run_start = time.perf_counter()
    temp_root = HERE / ".tmp"
    temp_root.mkdir(exist_ok=True)
    log_name = f"server-{args.craft_mode}-{n}.log"
    result = {"players": n, "craft_mode": args.craft_mode}
    samples, process, scenario = [], None, None
    with tempfile.TemporaryDirectory(prefix="run-", dir=temp_root) as folder:
        data = Path(folder)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with (args.output / log_name).open("w", encoding="utf-8") as log:
            try:
                def spawn():
                    child = subprocess.Popen([str(SERVER_PYTHON), "-B", str(Path(__file__).resolve()),
                                            "--serve", "--port", str(port)], cwd=ROOT,
                                           env=safe_env(data, args.craft_mode), stdout=log, stderr=log,
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                    (data / "owned-server.json").write_text(json.dumps({"pid": child.pid, "port": port}), encoding="utf-8")
                    return child
                process = spawn()
                limits = httpx.Limits(max_connections=n * 4 + 10, max_keepalive_connections=n * 4 + 10,
                                     keepalive_expiry=4)
                async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", limits=limits,
                                             trust_env=False, follow_redirects=False) as client:
                    for attempt in range(150):
                        if process.poll() is not None:
                            raise RuntimeError("server_exited_before_ready")
                        try:
                            response = await client.get("/health", timeout=.5)
                            if response.status_code == 200:
                                health = response.json()
                                break
                        except httpx.HTTPError:
                            pass
                        await asyncio.sleep(.1)
                    else:
                        raise RuntimeError("server_readiness_timeout")
                    if health.get("mode") != "demo" or health.get("tripo_fake") is not True:
                        raise RuntimeError("unsafe_server_health")
                    result["health"] = {k: health.get(k) for k in ("mode", "tripo_fake", "environment", "social_poll")}
                    result["database_before"] = checkpoint(data)
                    scenario = Scenario(client, n, args.seconds, args.craft_mode, args.http_client)
                    async def restart_server():
                        nonlocal process
                        stop_process_tree(process)
                        process = spawn()
                        for _ in range(150):
                            if process.poll() is not None:
                                raise RuntimeError("registration_restart_exited")
                            try:
                                response = await client.get("/health", timeout=.5)
                                if response.status_code == 200:
                                    return
                            except httpx.HTTPError:
                                pass
                            await asyncio.sleep(.1)
                        raise RuntimeError("registration_restart_timeout")
                    async def monitor():
                        while True:
                            samples.append({"elapsed_seconds": round(time.perf_counter() - run_start, 3),
                                            "phase": scenario.metrics.phase, **process_sample(process.pid),
                                            "generator_cpu_seconds": time.process_time(), "database": db_sizes(data)})
                            await asyncio.sleep(1)
                    monitor_task = asyncio.create_task(monitor())
                    try:
                        # Includes API setup, measured load and in-flight drain.
                        async def exercise():
                            if args.seeded_diagnostic:
                                await scenario.diagnostic_setup(data)
                            else:
                                await scenario.setup(restart_server)
                            print(f"{n}명 준비 완료; {args.seconds}초 부하 시작", flush=True)
                            await scenario.load()
                        await asyncio.wait_for(exercise(), max(1, remaining - (time.perf_counter() - run_start)))
                    finally:
                        await scenario.close()
                        monitor_task.cancel()
                        await asyncio.gather(monitor_task, return_exceptions=True)
                        result.update(scenario.report())
                    result["database_after"] = checkpoint(data)
            except asyncio.CancelledError:
                # wait_for cancels run_one at the overall deadline. The inner
                # finally has already closed tasks and retained their samples.
                # Keep those measurements instead of replacing the entire run
                # with a single timeout error. main stops after this fatal run.
                result["fatal_error"] = "cancelled_or_time_budget_exhausted"
            except Exception as error:
                result["fatal_error"] = type(error).__name__ + ": " + str(error)[:150]
            finally:
                if process:
                    stop_process_tree(process)
        result["server_log"] = log_name
        log_text = (args.output / log_name).read_text(encoding="utf-8", errors="replace")
        result["sqlite_lock_log_count"] = len(re.findall(r"database (?:table |schema )?is locked|SQLITE_BUSY|SQLITE_LOCKED", log_text, re.I))
        result["server_traceback_count"] = log_text.count("Traceback (most recent call last)")
        result["resource_samples"] = samples
        loaded = [sample for sample in samples if sample["phase"] == "load"]
        if len(loaded) > 1:
            first, last = loaded[0], loaded[-1]
            dt = last["elapsed_seconds"] - first["elapsed_seconds"]
            cpu = [max(0, b["cpu_seconds"] - a["cpu_seconds"]) / (b["elapsed_seconds"] - a["elapsed_seconds"]) * 100
                   for a, b in zip(loaded, loaded[1:])]
            result["resources"] = {
                "cpu_percent_one_core_mean": round(max(0, last["cpu_seconds"] - first["cpu_seconds"]) / dt * 100, 3),
                "cpu_percent_one_core_p95": percentile(cpu, 95),
                "rss_peak_bytes": max(s["rss_bytes"] for s in loaded),
                "threads_peak": max(s["threads"] for s in loaded),
                "generator_cpu_percent_one_core": round((last["generator_cpu_seconds"] - first["generator_cpu_seconds"]) / dt * 100, 3),
                "wal_peak_bytes": max(s["database"]["wal_bytes"] for s in samples),
                "db_total_peak_bytes": max(s["database"]["total_bytes"] for s in samples)}
            result["resource_measurement_incomplete"] = any(s.get("unavailable_pids") or not s["process_count"] for s in loaded)
        if "database_after" in result:
            result["database_growth_bytes"] = result["database_after"]["db_bytes"] - result["database_before"]["db_bytes"]
    result["run_wall_seconds"] = round(time.perf_counter() - run_start, 3)
    result["temporary_data_removed"] = not data.exists()
    return result


async def run(args):
    sys.addaudithook(loopback_guard)
    args.output.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "server_python": str(SERVER_PYTHON),
              "host": "127.0.0.1", "server_workers": 1, "generator_threads": 1,
              "machine_logical_cpus": os.cpu_count(), "seconds_per_run": args.seconds,
              "http_client": args.http_client,
              "seeded_diagnostic": args.seeded_diagnostic,
              "tool_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                              for name in ("run_local.py", "metrics.py", "http_client.py")},
              "authentication_setup": "20 registrations per server start; same temporary DB; no direct seeding",
              "runs": []}
    try:
        report["revision"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        report["revision"] = "unavailable"
    for n in args.players:
        remaining = args.max_total_seconds - (time.perf_counter() - start)
        if remaining < args.seconds + 10:
            report["budget_exhausted"] = True
            break
        print(f"{n}명 / {args.craft_mode} 로컬 서버 시작", flush=True)
        try:
            result = await asyncio.wait_for(run_one(n, args, remaining - 10), max(1, remaining - 10))
        except asyncio.TimeoutError:
            result = {"players": n, "fatal_error": "total_time_budget_exhausted"}
            report["budget_exhausted"] = True
        report["runs"].append(result)
        report["total_wall_seconds"] = round(time.perf_counter() - start, 3)
        (args.output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: result.get(k) for k in ("players", "duration_seconds", "requests_per_second",
                         "workflow_complete", "craft_results", "resources", "fatal_error")}, ensure_ascii=False), flush=True)
        if result.get("fatal_error"):
            break
    report["total_wall_seconds"] = round(time.perf_counter() - start, 3)
    (args.output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return int(bool(report.get("budget_exhausted")) or any(
        r.get("fatal_error") or r.get("task_errors") or r.get("server_traceback_count")
        or r.get("resource_measurement_incomplete")
        or any(e["status"] != "409" or e["detail"] != "provider_busy" or args.craft_mode != "tripo"
               for e in r.get("error_details", []))
        or (args.craft_mode == "fixture" and not r.get("workflow_complete")) for r in report["runs"]))


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--players", type=int, nargs="+", default=[30], help="even player counts, 2..100")
    p.add_argument("--seconds", type=int, default=90, help="measured seconds per N, 10..180")
    p.add_argument("--craft-mode", choices=("fixture", "tripo"), default="fixture")
    p.add_argument("--http-client", choices=("stdlib", "httpx"), default="stdlib",
                   help="small asyncio HTTP/1.1 transport; httpx for comparison")
    p.add_argument("--seeded-diagnostic", action="store_true",
                   help="supplemental burst probe with seeded accounts; not full workflow validation")
    p.add_argument("--max-total-seconds", type=int, default=600, help="includes setup; never above 600")
    p.add_argument("--output", type=Path, default=HERE / "results" / "latest")
    p.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--port", type=int, default=0, help=argparse.SUPPRESS)
    return p


def main():
    p = parser()
    args = p.parse_args()
    if args.serve:
        return serve(args.port)
    if not SERVER_PYTHON.is_file():
        p.error("required server venv Python not found")
    if any(n < 2 or n > 100 or n % 2 for n in args.players):
        p.error("players must be even numbers between 2 and 100")
    if args.seeded_diagnostic and args.http_client != "stdlib":
        p.error("seeded diagnostic uses the stdlib transport")
    if not 10 <= args.seconds <= 180 or not 10 <= args.max_total_seconds <= 600:
        p.error("seconds 10..180; max-total-seconds 10..600")
    args.output = args.output.resolve()
    if not args.output.is_relative_to(HERE / "results"):
        p.error("output must be below tools/loadtest/results")
    if (args.output / "results.json").exists():
        p.error("choose a new output directory; existing evidence is not overwritten")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
