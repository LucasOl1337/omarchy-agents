"""Contract for Panel.qml periodModelMap.

Keep this in sync with the QML: bounded periods (day/week/month) may only
use history.tokensByModel and todayTokensByModel. modelUsage is all-time or
the current billing cycle and belongs to Total alone.
"""
import unittest
from datetime import date, timedelta


def bucket_total(bucket):
    if isinstance(bucket, (int, float)):
        return int(bucket)
    if not isinstance(bucket, dict):
        return 0
    return int(sum(float(bucket.get(k, 0) or 0) for k in (
        "inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")))


def add_token(usage, mid, value):
    usage.setdefault(mid, {
        "inputTokens": 0, "outputTokens": 0,
        "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0,
    })
    if isinstance(value, dict):
        for key in usage[mid]:
            usage[mid][key] += int(float(value.get(key, 0) or 0))
    else:
        usage[mid]["inputTokens"] += int(float(value or 0))


def usage_map_total(usage):
    return sum(bucket_total(v) for v in usage.values())


def period_start(kind, today):
    if kind == "day":
        return today
    if kind == "week":
        return (date.fromisoformat(today) - timedelta(days=6)).isoformat()
    if kind == "month":
        return (date.fromisoformat(today) - timedelta(days=29)).isoformat()
    return ""


_EFFORTS = ("none", "off", "auto", "ultra", "max", "xhigh", "high", "medium", "low", "minimal")


def route_tail(model_id):
    if "/" not in model_id:
        return model_id
    prefix, rest = model_id.split("/", 1)
    if prefix.isascii() and prefix[:1].islower() and all(ch.islower() or ch.isdigit() for ch in prefix):
        return rest
    return model_id


def bare_model_id(model_id):
    raw = str(model_id or "")
    if " · " in raw:
        raw = raw.split(" · ", 1)[1]
    raw = route_tail(raw)
    for effort in _EFFORTS:
        suffix = f"({effort})"
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]
            break
    for effort in _EFFORTS:
        suffix = f"-{effort}"
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]
            break
    return raw


def all_model_key(model_id, existing):
    bare = bare_model_id(model_id)
    if bare and bare in existing:
        return bare
    raw = str(model_id or "")
    without_origin = raw.split(" · ", 1)[1] if " · " in raw else raw
    if without_origin in existing:
        return without_origin
    routed = route_tail(without_origin)
    if routed in existing:
        return routed
    return bare or raw


def period_model_map(p, kind, today):
    if not p:
        return {}
    if p.get("providerId") == "all":
        combined = {}
        children = [child for child in (p.get("providers") or []) if child and child.get("providerId") != "all"]
        ordered = [child for child in children if child.get("providerId") != "9router"]
        ordered += [child for child in children if child.get("providerId") == "9router"]
        for child in ordered:
            from_router = child.get("providerId") == "9router"
            for mid, val in period_model_map(child, kind, today).items():
                key = all_model_key(mid, combined) if from_router else mid
                add_token(combined, key, val)
        return combined
    if kind == "total":
        usage = {}
        for mid, val in (p.get("modelUsage") or {}).items():
            add_token(usage, mid, val)
        return usage
    explicit = p.get("periodTokensByModel") or {}
    if explicit.get(kind):
        usage = {}
        for mid, val in explicit[kind].items():
            add_token(usage, mid, val)
        return usage
    start = period_start(kind, today)
    usage = {}
    today_covered = False
    for row in p.get("history") or []:
        day = str(row.get("date") or "")
        if start and day < start:
            continue
        models = row.get("tokensByModel") or {}
        before = usage_map_total(usage)
        for mid, val in models.items():
            add_token(usage, mid, val)
        if day == today and usage_map_total(usage) > before:
            today_covered = True
    if not today_covered and period_today_is_current(p, today):
        for mid, val in (p.get("todayTokensByModel") or {}).items():
            add_token(usage, mid, val)
    return usage


def period_today_is_current(p, today):
    updated = p.get("updatedAt")
    if updated:
        try:
            stamp = str(updated).replace("Z", "+00:00")
            parsed = date.fromisoformat(stamp[:10])
            if parsed.isoformat() == today:
                return True
        except ValueError:
            pass
    for row in (p.get("recentDays") or []) + (p.get("history") or []):
        if str((row or {}).get("date") or "") == today:
            return True
    return False


class PeriodModelMapTests(unittest.TestCase):
    today = "2026-09-09"

    def test_day_does_not_use_cursor_billing_cycle(self):
        cursor = {
            "providerId": "cursor",
            "todayTotalTokens": 0,
            "todayTokensByModel": {},
            "history": [],
            "recentDays": [{"date": self.today, "messageCount": 1}],
            "modelUsage": {
                "grok-bot-default": {"inputTokens": 1_100_000_000},
                "cursor-grok-4.6-xhigh-fast": {"inputTokens": 994_200_000},
            },
        }
        grok = {
            "providerId": "grok",
            "updatedAt": "2026-09-09T12:00:00+00:00",
            "todayTotalTokens": 196_600_000,
            "todayTokensByModel": {"grok-4.6-build": 196_600_000},
            "history": [],
            "modelUsage": {"grok-4.6-build": {"inputTokens": 851_000_000}},
        }
        combined = period_model_map(
            {"providerId": "all", "providers": [cursor, grok]}, "day", self.today)
        self.assertNotIn("grok-bot-default", combined)
        self.assertNotIn("cursor-grok-4.6-xhigh-fast", combined)
        self.assertEqual(bucket_total(combined["grok-4.6-build"]), 196_600_000)

    def test_total_still_shows_cycle_usage(self):
        cursor = {
            "providerId": "cursor",
            "todayTokensByModel": {},
            "modelUsage": {"grok-bot-default": {"inputTokens": 1_100_000_000}},
        }
        usage = period_model_map(cursor, "total", self.today)
        self.assertEqual(bucket_total(usage["grok-bot-default"]), 1_100_000_000)

    def test_history_today_is_not_double_counted(self):
        hermes = {
            "providerId": "hermes",
            "todayTokensByModel": {"grok-4.6": 1_500_000},
            "history": [{
                "date": self.today,
                "messageCount": 1_500_000,
                "tokensByModel": {"grok-4.6": 1_500_000},
            }],
            "modelUsage": {"grok-4.6": {"inputTokens": 272_000_000}},
        }
        usage = period_model_map(hermes, "day", self.today)
        self.assertEqual(bucket_total(usage["grok-4.6"]), 1_500_000)

    def test_week_keeps_per_day_history_and_skips_all_time(self):
        hermes = {
            "providerId": "hermes",
            "todayTokensByModel": {"grok-4.6": 10},
            "history": [
                {"date": "2026-09-08", "tokensByModel": {"gpt-6-astra": 100}},
                {"date": "2026-09-09", "tokensByModel": {"grok-4.6": 10}},
            ],
            "modelUsage": {"gpt-6-astra": {"inputTokens": 74_000_000}},
        }
        usage = period_model_map(hermes, "week", self.today)
        self.assertEqual(bucket_total(usage["gpt-6-astra"]), 100)
        self.assertEqual(bucket_total(usage["grok-4.6"]), 10)

    def test_stale_today_tokens_are_not_a_day_fallback(self):
        stale = {
            "providerId": "opencode",
            "updatedAt": None,
            "todayTotalTokens": 585147,
            "todayTokensByModel": {"muse-spark-1.3-contributor-free": 585147},
            "history": [],
            "recentDays": [{"date": "2026-09-06", "messageCount": 585147}],
        }
        usage = period_model_map(stale, "day", self.today)
        self.assertEqual(usage, {})

    def test_all_sums_9router_into_the_same_model_name(self):
        claude = {
            "providerId": "claude",
            "modelUsage": {"claude-opus-5-5": {"inputTokens": 100}},
            "periodTokensByModel": {"week": {"claude-opus-5-5": 10}},
        }
        codex = {
            "providerId": "codex",
            "modelUsage": {"gpt-6-astra": {"inputTokens": 50}, "gpt-6-sol": {"inputTokens": 7}},
            "periodTokensByModel": {"week": {"gpt-6-sol": 4}},
        }
        cursor = {
            "providerId": "cursor",
            "modelUsage": {
                "cursor-grok-4.6-high": {"inputTokens": 20},
                "cursor-grok-4.6-xhigh": {"inputTokens": 30},
            },
        }
        router = {
            "providerId": "9router",
            "modelUsage": {
                "Sherlocker · claude-opus-5-5(high)": {"inputTokens": 40, "cacheReadInputTokens": 5},
                "Railway · cc/claude-opus-5-5(high)": {"outputTokens": 8},
                "Railway · cx/gpt-6-astra-xhigh": {"inputTokens": 15},
                "Hostinger · cx/gpt-6-sol": {"inputTokens": 3},
                "Railway · cu/cursor-grok-4.6-high": {"inputTokens": 2},
                "Sherlocker · cx/gpt-6-luna(medium)": {"inputTokens": 9},
            },
            "periodTokensByModel": {
                "week": {
                    "Sherlocker · claude-opus-5-5(high)": 6,
                    "Railway · cx/gpt-6-sol": 1,
                },
            },
        }
        total = period_model_map(
            {"providerId": "all", "providers": [router, claude, codex, cursor]},
            "total",
            self.today,
        )
        self.assertEqual(bucket_total(total["claude-opus-5-5"]), 153)
        self.assertEqual(bucket_total(total["gpt-6-astra"]), 65)
        self.assertEqual(bucket_total(total["gpt-6-sol"]), 10)
        self.assertEqual(bucket_total(total["cursor-grok-4.6-high"]), 22)
        self.assertEqual(bucket_total(total["cursor-grok-4.6-xhigh"]), 30)
        self.assertEqual(bucket_total(total["gpt-6-luna"]), 9)
        self.assertNotIn("Sherlocker · claude-opus-5-5(high)", total)
        week = period_model_map(
            {"providerId": "all", "providers": [claude, router, codex]},
            "week",
            self.today,
        )
        self.assertEqual(bucket_total(week["claude-opus-5-5"]), 16)
        self.assertEqual(bucket_total(week["gpt-6-sol"]), 5)

    def test_effort_suffix_joins_the_bare_model_when_that_row_exists(self):
        usage = period_model_map({
            "providerId": "all",
            "providers": [
                {"providerId": "grok", "modelUsage": {"gpt-5.6-sol(medium)": {"inputTokens": 1}}},
                {"providerId": "codex", "modelUsage": {"gpt-5.6-sol": {"inputTokens": 100}}},
                {"providerId": "9router", "modelUsage": {
                    "Railway · cx/gpt-5.6-sol(medium)": {"inputTokens": 40},
                }},
            ],
        }, "total", self.today)
        self.assertEqual(bucket_total(usage["gpt-5.6-sol"]), 140)
        self.assertEqual(bucket_total(usage["gpt-5.6-sol(medium)"]), 1)

    def test_federated_explicit_period_keeps_origins_separate(self):
        router = {
            "providerId": "9router",
            "periodTokensByModel": {
                "week": {"Local · same": 11, "Railway · same": 99},
            },
            "history": [],
            "modelUsage": {"Local · same": {"inputTokens": 9999}},
        }
        usage = period_model_map(router, "week", self.today)
        self.assertEqual(bucket_total(usage["Local · same"]), 11)
        self.assertEqual(bucket_total(usage["Railway · same"]), 99)
        self.assertEqual(usage_map_total(usage), 110)


if __name__ == "__main__":
    unittest.main()
