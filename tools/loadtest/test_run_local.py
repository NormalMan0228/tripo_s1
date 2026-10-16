"""네트워크나 서버를 실행하지 않는 로컬 부하 도구 회귀테스트."""

import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_local import Scenario, gather_owned, loopback_guard, percentile, route_key, safe_env
import run_local


class 비동기회귀테스트(unittest.IsolatedAsyncioTestCase):
    async def test_전체_시간제한에도_부분_통계와_서버정리를_보존한다(self):
        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get(self, *args, **kwargs):
                return SimpleNamespace(status_code=200,
                    json=lambda: {"mode": "demo", "tripo_fake": True})

            async def request(self, *args, **kwargs):
                await asyncio.Future()

        class HangingScenario(Scenario):
            async def setup(self, restart_server):
                pass

            async def load(self):
                self.metrics.phase = "load"
                self.started = run_local.time.perf_counter()
                await self.request(None, "GET", "/v1/me")

        sample = {"cpu_seconds": 0, "rss_bytes": 0, "threads": 0,
                  "process_count": 1, "pids": [], "unavailable_pids": []}
        fake_process = SimpleNamespace(pid=12345, poll=lambda: None)
        with tempfile.TemporaryDirectory(dir=run_local.HERE / ".tmp") as directory:
            args = SimpleNamespace(output=Path(directory), craft_mode="fixture", seconds=10,
                                   http_client="stdlib", seeded_diagnostic=False)
            with (patch("run_local.subprocess.Popen", return_value=fake_process),
                  patch("run_local.socket", SimpleNamespace(socket=MagicMock())) as sock,
                  patch("run_local.print", create=True),
                  patch("httpx.AsyncClient", return_value=FakeClient()),
                  patch("run_local.Scenario", HangingScenario),
                  patch("run_local.process_sample", return_value=sample),
                  patch("run_local.checkpoint", return_value={"db_bytes": 0}),
                  patch("run_local.stop_process_tree") as stop):
                sock.socket.return_value.__enter__.return_value.getsockname.return_value = ("127.0.0.1", 12345)
                result = await asyncio.wait_for(run_local.run_one(2, args, 20), .1)
                stop.assert_called_once_with(fake_process)
        self.assertEqual(result["fatal_error"], "cancelled_or_time_budget_exhausted")
        self.assertEqual(result["endpoints"]["load"]["GET /v1/me"]["status_counts"],
                         {"cancelled_at_shutdown": 1})
        self.assertTrue(result["temporary_data_removed"])

    async def test_목록_detail을_가진_422_응답도_집계한다(self):
        class FakeClient:
            async def request(self, *args, **kwargs):
                return SimpleNamespace(
                    status_code=422,
                    content=b"validation failure",
                    json=lambda: {"detail": [{"type": "missing", "loc": ["body", "prompt"]}]},
                )

        scenario = Scenario(FakeClient(), 2, 10, "fixture")
        scenario.metrics.phase = "load"
        _, status = await scenario.request(None, "POST", "/v1/studio/jobs", {})
        report = scenario.metrics.report()
        endpoint = report["endpoints"]["load"]["POST /v1/studio/jobs"]
        self.assertEqual(status, "422")
        self.assertEqual(endpoint["requests"], 1)
        self.assertEqual(endpoint["status_counts"], {"422": 1})
        self.assertEqual(report["error_details"][0]["detail"], "non_code_detail")
        self.assertEqual(report["error_details"][0]["count"], 1)

    async def test_취소된_HTTP_요청을_시작_단계의_통계에_남긴다(self):
        started = asyncio.Event()
        cleaned = asyncio.Event()

        class FakeClient:
            async def request(self, *args, **kwargs):
                started.set()
                try:
                    await asyncio.Future()
                finally:
                    cleaned.set()

        scenario = Scenario(FakeClient(), 2, 10, "fixture")
        scenario.metrics.phase = "load"
        task = asyncio.create_task(scenario.request(None, "GET", "/v1/social/people"))
        await asyncio.wait_for(started.wait(), 1)
        scenario.metrics.phase = "drain"
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(cleaned.is_set())
        report = scenario.metrics.report()
        endpoint = report["endpoints"]["load"]["GET /v1/social/people"]
        self.assertEqual(endpoint["requests"], 1)
        self.assertEqual(endpoint["status_counts"], {"cancelled_at_shutdown": 1})
        self.assertEqual(report["error_details"][0]["detail"], "cancelled_at_shutdown")
        self.assertNotIn("drain", report["endpoints"])

    async def test_한_작업이_실패하면_형제_작업의_취소까지_완료한다(self):
        started = asyncio.Event()
        cancelled = asyncio.Event()
        cleaned = asyncio.Event()

        async def sibling():
            started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                cancelled.set()
                raise
            finally:
                # Cleanup is asynchronous: gather_owned must await it as well.
                await asyncio.sleep(0)
                cleaned.set()

        async def failing():
            await started.wait()
            raise RuntimeError("expected_setup_failure")

        with self.assertRaisesRegex(RuntimeError, "expected_setup_failure"):
            await asyncio.wait_for(gather_owned([sibling(), failing()]), 1)
        self.assertTrue(cancelled.is_set())
        self.assertTrue(cleaned.is_set())


class 순수함수회귀테스트(unittest.TestCase):
    def test_guard가_외부_연결과_바인딩과_DNS를_호출_전에_차단한다(self):
        # Invoke the audit hook directly; these are inert test arguments.
        cases = [
            ("socket.connect", (None, ("203.0.113.1", 443))),
            ("socket.bind", (None, ("0.0.0.0", 8000))),
            ("socket.sendto", (None, ("203.0.113.1", 53))),
            ("socket.connect", (None, ("localhost", 8000))),
            ("socket.connect", (None, ("::1", 8000, 0, 0))),
            ("socket.getaddrinfo", ("example.invalid", 443, 0, 0, 0)),
            ("socket.gethostbyname", ("example.invalid",)),
            ("socket.gethostbyaddr", ("203.0.113.1",)),
        ]
        for event, arguments in cases:
            with self.subTest(event=event, arguments=arguments):
                with self.assertRaises(PermissionError):
                    loopback_guard(event, arguments)

    def test_guard가_명시적인_IPv4_루프백은_허용한다(self):
        for event in ("socket.connect", "socket.bind", "socket.sendto"):
            with self.subTest(event=event):
                self.assertIsNone(loopback_guard(event, (None, ("127.0.0.1", 8000))))
        self.assertIsNone(loopback_guard("socket.getaddrinfo", ("127.0.0.1", 8000, 0, 0, 0)))
        self.assertIsNone(loopback_guard("socket.gethostbyname", ("127.0.0.1",)))
        self.assertIsNone(loopback_guard("socket.gethostbyaddr", ("127.0.0.1",)))

    def test_서버_환경에_비밀과_프록시를_상속하지_않는다(self):
        blocked = {
            "TRIPO_API_KEY", "TRIPO_API_KEY_FILE", "OPENAI_API_KEY",
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "PYTHONPATH",
        }
        inherited = {name: "test-only-do-not-inherit" for name in blocked}
        inherited.update(SYSTEMROOT="test-system-root", PATH="test-path",
                         TRIPOTHON_FAKE_TRIPO="false", TRIPOTHON_DATA_DIR="wrong-data-dir")
        destination = Path("isolated-test-data")
        for craft_mode in ("fixture", "tripo"):
            with self.subTest(craft_mode=craft_mode), patch.dict("os.environ", inherited, clear=True):
                env = safe_env(destination, craft_mode)
            self.assertTrue(blocked.isdisjoint({name.upper() for name in env}))
            self.assertNotIn("test-only-do-not-inherit", env.values())
            self.assertEqual(env["SYSTEMROOT"], "test-system-root")
            self.assertEqual(env["PATH"], "test-path")
            self.assertEqual(env["TRIPOTHON_DATA_DIR"], str(destination))
            self.assertEqual(env["TEMP"], str(destination))
            self.assertEqual(env["TMP"], str(destination))
            self.assertEqual(env["TRIPOTHON_FAKE_TRIPO"], "true")
            self.assertEqual(env["TRIPOTHON_STUDIO_LLM"], "fixture")
            self.assertEqual(env["TRIPOTHON_MODE"], "demo")
            self.assertEqual(env["TRIPO_ENABLE_PAID"], "true" if craft_mode == "tripo" else "false")

    def test_백분위수의_빈_입력과_경계와_nearest_rank를_검증한다(self):
        self.assertIsNone(percentile([], 95))
        values = list(range(20, 0, -1))
        for rank, expected in ((0, 1), (50, 10), (95, 19), (99, 20), (100, 20)):
            with self.subTest(rank=rank):
                self.assertEqual(percentile(values, rank), expected)
        for rank in (-1, 101, float("nan")):
            with self.subTest(invalid_rank=rank):
                with self.assertRaises(ValueError):
                    percentile(values, rank)

    def test_서로_다른_UUID_경로를_같은_엔드포인트로_집계한다(self):
        identifiers = (
            "12345678-1234-1234-1234-123456789abc",
            "abcdef12-abcd-abcd-abcd-abcdef123456",
        )
        for identifier in identifiers:
            with self.subTest(identifier=identifier):
                self.assertEqual(route_key("GET", f"/v1/studio/jobs/{identifier}"),
                                 "GET /v1/studio/jobs/{id}")
                self.assertEqual(route_key("POST", f"/v1/social/invites/{identifier}/accept"),
                                 "POST /v1/social/invites/{id}/accept")
        self.assertEqual(route_key("GET", "/v1/social/people"), "GET /v1/social/people")
        self.assertEqual(route_key("GET", "/v1/studio/jobs/not-a-uuid"),
                         "GET /v1/studio/jobs/not-a-uuid")


if __name__ == "__main__":
    unittest.main()
