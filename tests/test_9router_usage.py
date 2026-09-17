import importlib.machinery
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
