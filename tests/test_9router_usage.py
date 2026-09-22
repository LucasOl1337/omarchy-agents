import importlib.machinery
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

_path = Path(__file__).parents[1] / "bin/omarchy-agent-usage-9router"
_loader = importlib.machinery.SourceFileLoader("ninerouter_usage", str(_path))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
ninerouter = importlib.util.module_from_spec(_spec)
_loader.exec_module(ninerouter)


class NineRouterUsageTests(unittest.TestCase):
    def test_iso_utc_becomes_local_day(self):
        local = datetime.now().astimezone().replace(year=2026, month=9, day=17, hour=7, minute=0, second=0, microsecond=0)
        utc = local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        self.assertEqual(ninerouter.day_from_stamp(utc), "2026-09-17")
        self.assertEqual(ninerouter.day_from_stamp(""), "")
        self.assertEqual(ninerouter.day_from_stamp(None), "")

    def _db(self, rows):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "data.sqlite"
        conn = sqlite3.connect(path)
        conn.execute(
            "CREATE TABLE usageHistory(id INTEGER PRIMARY KEY, timestamp TEXT, provider TEXT, model TEXT, "
            "promptTokens INTEGER, completionTokens INTEGER, cost REAL, tokens TEXT)"
        )
        for i, row in enumerate(rows, start=1):
            conn.execute(
                "INSERT INTO usageHistory VALUES (?,?,?,?,?,?,?,?)",
                (
                    i,
                    row["timestamp"],
                    row.get("provider", "codex"),
                    row["model"],
                    row.get("promptTokens", 0),
                    row.get("completionTokens", 0),
                    row.get("cost", 0),
                    json.dumps(row.get("tokens") or {}),
                ),
            )
        conn.commit()
        conn.close()
        return path

    def test_missing_db_is_empty(self):
        stats = ninerouter.collect(Path("/tmp/does-not-exist-9router.sqlite"))
        self.assertEqual(stats["todayTotalTokens"], 0)
        self.assertEqual(stats["totalPrompts"], 0)
        self.assertEqual(stats["modelUsage"], {})

    def test_old_day_is_not_today(self):
        path = self._db([{
            "timestamp": "2026-09-06T12:00:00.000Z",
            "model": "gpt-5.6-sol(medium)",
            "promptTokens": 1000,
            "completionTokens": 20,
            "tokens": {"prompt_tokens": 1000, "completion_tokens": 20, "cached_tokens": 0, "cache_creation_input_tokens": 0},
        }])
        stats = ninerouter.collect(path)
        today = datetime.now().astimezone().date().isoformat()
        self.assertIn("2026-09-06", stats["activeDates"])
        if today != "2026-09-06":
            self.assertEqual(stats["todayTotalTokens"], 0)
            self.assertEqual(stats["todayPrompts"], 0)
        by_date = {row["date"]: row["messageCount"] for row in stats["history"]}
        self.assertEqual(by_date["2026-09-06"], 1020)

    def test_cache_is_split_out_of_input(self):
        path = self._db([{
            "timestamp": "2026-09-17T12:00:00.000Z",
            "model": "gpt-5.6-sol(high)",
            "promptTokens": 100,
            "completionTokens": 10,
            "tokens": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "cached_tokens": 40,
                "cache_creation_input_tokens": 5,
            },
        }])
        stats = ninerouter.collect(path)
        bucket = stats["modelUsage"]["gpt-5.6-sol(high)"]
        self.assertEqual(bucket, {
            "inputTokens": 55,
            "outputTokens": 10,
            "cacheReadInputTokens": 40,
            "cacheCreationInputTokens": 5,
        })

    def test_gateway_counts_every_backend(self):
        now = datetime.now().astimezone()
        stamp = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        path = self._db([
            {
                "timestamp": stamp,
                "provider": "codex",
                "model": "gpt-5.6-sol(medium)",
                "promptTokens": 50,
                "completionTokens": 5,
                "cost": 0.1,
                "tokens": {"prompt_tokens": 50, "completion_tokens": 5},
            },
            {
                "timestamp": stamp,
                "provider": "grok-cli",
                "model": "grok-4.6",
                "promptTokens": 20,
                "completionTokens": 2,
                "cost": 0.05,
                "tokens": {"prompt_tokens": 20, "completion_tokens": 2},
            },
        ])
        stats = ninerouter.collect(path)
        self.assertEqual(stats["todayPrompts"], 2)
        self.assertEqual(stats["todaySessions"], 1)
        self.assertEqual(stats["todayTotalTokens"], 77)
        self.assertEqual(stats["todayTokensByModel"]["gpt-5.6-sol(medium)"], 55)
        self.assertEqual(stats["todayTokensByModel"]["grok-4.6"], 22)
        self.assertAlmostEqual(stats["todayCost"], 0.15)
        self.assertEqual(ninerouter.status_line(stats).startswith("US$"), True)

    def test_zero_token_rows_are_skipped(self):
        path = self._db([{
            "timestamp": "2026-09-17T12:00:00.000Z",
            "model": "gpt-5.6-sol(medium)",
            "promptTokens": 0,
            "completionTokens": 0,
            "tokens": {},
        }])
        stats = ninerouter.collect(path)
        self.assertEqual(stats["totalPrompts"], 0)

    def _federated_fetch(self, path, params):
        period = params["period"]
        if path.endswith("/chart"):
            size = 24 if period == "today" else (7 if period == "7d" else 30)
            return [{
                "label": f"{index:02d}:00" if period == "today" else f"day-{index}",
                "tokens": (index + 1) * 10,
                "cost": index / 10,
                "sources": {"Local": {"tokens": index + 1}, "Railway": {"tokens": (index + 1) * 9}},
            } for index in range(size)]
        multiplier = {"today": 1, "7d": 2, "30d": 3, "all": 4}[period]
        return {
            "totalRequests": 3 * multiplier,
            "totalPromptTokens": 100 * multiplier,
            "totalCompletionTokens": 10 * multiplier,
            "totalCost": 1.25 * multiplier,
            "sources": [
                {"label": "Local", "available": True, "requests": multiplier, "tokens": 20 * multiplier},
                {"label": "Railway", "available": True, "requests": 2 * multiplier, "tokens": 90 * multiplier},
            ],
            "byModel": {
                "Local|same (codex)": {"origin": "Local", "rawModel": "same", "promptTokens": 10 * multiplier,
                                          "completionTokens": multiplier, "cachedTokens": 2 * multiplier},
                "Railway|same (codex)": {"origin": "Railway", "rawModel": "same", "promptTokens": 90 * multiplier,
                                            "completionTokens": 9 * multiplier, "cachedTokens": 20 * multiplier},
            },
        }

    def test_federated_api_sums_sources_and_keeps_model_origins_separate(self):
        stats = ninerouter.collect_api(self._federated_fetch)
        self.assertEqual(stats["usageOrigin"], "federated-api")
        self.assertEqual(stats["scope"], "account")
        self.assertEqual(stats["apiErrors"], [])
        self.assertEqual(stats["todayPrompts"], 3)
        self.assertEqual(stats["todayTotalTokens"], 110)
        self.assertEqual(stats["todayCost"], 1.25)
        self.assertEqual([source["label"] for source in stats["sources"]], ["Local", "Railway"])
        self.assertEqual(stats["todayTokensByModel"], {"Local · same": 11, "Railway · same": 99})
        self.assertEqual(set(stats["modelUsage"]), {"Local · same", "Railway · same"})
        self.assertEqual(sum(row["messageCount"] for row in stats["todayHours"]), 3000)
        self.assertEqual(stats["todayHours"][0]["sources"], {"Local": 1, "Railway": 9})

    def test_collect_falls_back_to_local_db_when_api_is_unavailable(self):
        now = datetime.now().astimezone().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        path = self._db([{"timestamp": now, "model": "local-only", "promptTokens": 5, "completionTokens": 1}])
        with patch.object(ninerouter, "db_path", return_value=path):
            stats = ninerouter.collect(fetch=lambda *_: (_ for _ in ()).throw(RuntimeError("offline")))
        self.assertEqual(stats["usageOrigin"], "local-db")
        self.assertEqual(stats["todayTotalTokens"], 6)
        self.assertEqual(stats["sources"][0]["label"], "Local")
        self.assertEqual(stats["scope"], "device")

    def test_one_failed_chart_keeps_federated_stats(self):
        def fetch(path, params):
            if path.endswith("/chart") and params["period"] == "7d":
                raise RuntimeError("temporary chart failure")
            return self._federated_fetch(path, params)

        stats = ninerouter.collect_api(fetch)
        self.assertEqual(stats["usageOrigin"], "federated-api")
        self.assertEqual(stats["todayTotalTokens"], 110)
        self.assertEqual(stats["recentDays"], [])
        self.assertTrue(any(error.startswith("chart/7d:") for error in stats["apiErrors"]))

    def test_cli_token_matches_server_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "auth").mkdir()
            (root / "machine-id").write_text("machine")
            (root / "auth" / "cli-secret").write_text("secret")
            expected = __import__("hashlib").sha256(b"machine9r-cli-authsecret").hexdigest()[:16]
            self.assertEqual(ninerouter.cli_token(root), expected)


if __name__ == "__main__":
    unittest.main()
