"""Per-day Claude model totals and the signed-in account label."""
import json
import tempfile
import unittest
from datetime import datetime
from importlib.machinery import SourceFileLoader
from pathlib import Path

daily = SourceFileLoader(
    "claude_daily",
    str(Path(__file__).parents[1] / "bin/omarchy-agent-usage-claude-daily"),
).load_module()


class ClaudeDailyTests(unittest.TestCase):
    def test_week_keeps_each_days_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects = root / "projects" / "demo"
            projects.mkdir(parents=True)
            (projects / "session.jsonl").write_text(
                "\n".join([
                    json.dumps({
                        "type": "assistant",
                        "timestamp": "2026-09-30T15:00:00-03:00",
                        "message": {"role": "assistant", "model": "claude-opus-5-5",
                                    "usage": {"input_tokens": 100, "output_tokens": 20,
                                              "cache_read_input_tokens": 5, "cache_creation_input_tokens": 0}},
                    }),
                    json.dumps({
                        "type": "assistant",
                        "timestamp": "2026-10-01T09:00:00-03:00",
                        "message": {"role": "assistant", "model": "claude-opus-5-5",
                                    "usage": {"input_tokens": 7}},
                    }),
                ]) + "\n",
                encoding="utf-8",
            )
            cache = {"files": {}}
            days = daily.daily_models(root / "projects", cache)
            rows = daily.history_rows(days)
            by_day = {row["date"]: row for row in rows}
            self.assertEqual(by_day["2026-09-30"]["tokensByModel"]["claude-opus-5-5"], 125)
            self.assertEqual(by_day["2026-10-01"]["tokensByModel"]["claude-opus-5-5"], 7)
            self.assertEqual(by_day["2026-09-30"]["messageCount"], 125)

    def test_the_same_message_id_counts_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects = root / "projects" / "demo"
            projects.mkdir(parents=True)
            line = json.dumps({
                "type": "assistant",
                "timestamp": "2026-10-01T09:00:00-03:00",
                "message": {
                    "id": "msg_same",
                    "role": "assistant",
                    "model": "claude-opus-5-5",
                    "usage": {"input_tokens": 10, "output_tokens": 1},
                },
            })
            (projects / "session.jsonl").write_text(line + "\n" + line + "\n", encoding="utf-8")
            days = daily.daily_models(root / "projects", {"files": {}})
            self.assertEqual(days["2026-10-01"]["claude-opus-5-5"], 11)

    def test_chart_days_follow_the_model_scan(self):
        today = datetime.now().astimezone().date().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects = root / "projects" / "demo"
            projects.mkdir(parents=True)
            (projects / "session.jsonl").write_text(
                "\n".join([
                    json.dumps({
                        "type": "assistant",
                        "timestamp": "2026-09-30T15:00:00-03:00",
                        "message": {"role": "assistant", "model": "claude-opus-5-5",
                                    "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 5}},
                    }),
                    json.dumps({
                        "type": "assistant",
                        "timestamp": today + "T09:00:00-03:00",
                        "message": {"role": "assistant", "model": "claude-opus-5-5",
                                    "usage": {"input_tokens": 7}},
                    }),
                ]) + "\n",
                encoding="utf-8",
            )
            record = {
                "todayTotalTokens": 1,
                "todayTokensByModel": {"claude-opus-5-5": 1},
                "recentDays": [
                    {"date": "2026-09-30", "messageCount": 1},
                    {"date": today, "messageCount": 1},
                    {"date": "2026-09-01", "messageCount": 9},
                ],
            }
            days = daily.daily_models(root / "projects", {"files": {}})
            daily.apply_daily(record, days)
            by_day = {row["date"]: row["messageCount"] for row in record["recentDays"]}
            self.assertEqual(by_day["2026-09-30"], 125)
            self.assertEqual(by_day[today], 7)
            self.assertEqual(by_day["2026-09-01"], 9)
            self.assertEqual(record["todayTotalTokens"], 7)
            self.assertEqual(record["todayTokensByModel"]["claude-opus-5-5"], 7)

    def test_unchanged_file_is_not_reread(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects = root / "projects" / "demo"
            projects.mkdir(parents=True)
            target = projects / "session.jsonl"
            target.write_text("{}\n", encoding="utf-8")
            cache = {"files": {}}
            daily.daily_models(root / "projects", cache)
            cached = cache["files"][str(target)]
            cached["days"] = {"2026-10-01": {"claude-opus-5-5": 3}}
            days = daily.daily_models(root / "projects", cache)
            self.assertEqual(days["2026-10-01"]["claude-opus-5-5"], 3)


if __name__ == "__main__":
    unittest.main()
