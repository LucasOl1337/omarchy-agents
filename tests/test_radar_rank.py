"""Contract for Panel.qml Radar ranking.

Keep this in sync with the QML: buildRadarQuotaRows / buildRadarByoRows.
Quota windows sort by use-now headroom; exhausted pools sink; providers
with no limits never mix into the quota list.
"""
import unittest


ALARMING = 0.9
EXHAUSTED = 1.0
IMMINENT_MS = 30 * 60 * 1000
NUDGE_FROM = 0.7


def window_kind(title):
    text = str(title or "").lower()
    if "month" in text:
        return "monthly"
    if "week" in text or "7-day" in text or "seven" in text:
        return "weekly"
    if "session" in text:
        return "session"
    return "other"


def radar_band(percent, reset_ms):
    if percent >= EXHAUSTED:
        return 3
    imminent = reset_ms > 0 and reset_ms < IMMINENT_MS
    if percent >= ALARMING and not imminent:
        return 2
    return 1


def radar_score(percent, reset_ms, band):
    headroom = max(0.0, 1.0 - percent)
    if band == 3:
        return (1e15 - reset_ms) if reset_ms > 0 else 0.0
    score = headroom
    if percent >= NUDGE_FROM and reset_ms > 0:
        score += 0.05 * (1.0 / (1.0 + reset_ms / 3_600_000))
    return score


def radar_why(harness, title, percent, reset_ms, exhausted, alarming, imminent):
    name = f"{harness} {title}".strip()
    if exhausted:
        line = f"{name} 100% · esgotado"
    else:
        line = f"{name} {round(percent * 100)}% usado"
        if alarming and imminent:
            line += " · quase reset"
        elif alarming:
            line += " · alarmante"
    if reset_ms > 0:
        line += " · reset em " + format_duration(reset_ms)
    return line


def format_duration(ms):
    if not (ms > 0):
        return "now"
    minutes = int(ms // 60000)
    hours = minutes // 60
    days = hours // 24
    if days > 0:
        return f"{days}d {hours % 24}h"
    if hours > 0:
        return f"{hours}h {minutes % 60}m"
    return f"{max(1, minutes)}m"


def build_quota_rows(providers, now_ms=0):
    rows = []
    balance_shown = set()
    for p in providers:
        if not p or p.get("providerId") == "all":
            continue
        windows = list(p.get("limits") or [])
        balance = p.get("balance")
        if not windows and balance and float(balance.get("funded") or 0) > 0:
            funded = float(balance["funded"])
            remaining = float(balance.get("remaining") or 0)
            windows = [{"title": "Prepaid", "percent": 1.0 - remaining / funded, "resetMs": -1}]
        if not windows:
            continue
        harness = p.get("chipName") or p.get("providerName")
        tier = str(p.get("tierLabel") or "")
        if tier:
            tier = tier[0].upper() + tier[1:]
        balance_text = ""
        if balance and p.get("providerId") not in balance_shown:
            remaining = float(balance.get("remaining") or 0)
            currency = str(balance.get("currency") or "USD")
            prefix = "$" if currency == "USD" else currency + " "
            balance_text = f"{harness} · {prefix}{remaining:.2f} restantes"
            balance_shown.add(p.get("providerId"))
        for i, win in enumerate(windows):
            percent = float(win["percent"])
            reset_ms = float(win.get("resetMs", -1))
            exhausted = percent >= EXHAUSTED
            imminent = reset_ms > 0 and reset_ms < IMMINENT_MS
            alarming = percent >= ALARMING
            band = radar_band(percent, reset_ms)
            rows.append({
                "providerId": p.get("providerId"),
                "harness": harness,
                "tier": tier,
                "title": win.get("title") or "Limit",
                "kind": window_kind(win.get("title")),
                "percent": percent,
                "headroom": max(0.0, 1.0 - percent),
                "resetMs": reset_ms,
                "exhausted": exhausted,
                "alarming": alarming,
                "imminent": imminent,
                "band": band,
                "score": radar_score(percent, reset_ms, band),
                "badge": "esgotado" if exhausted else (
                    "quase reset" if alarming and imminent else ("alarmante" if alarming else "")
                ),
                "why": radar_why(harness, win.get("title") or "Limit", percent, reset_ms,
                                 exhausted, alarming, imminent),
                "balanceText": balance_text if i == 0 else "",
            })
    rows.sort(key=lambda r: (r["band"], -r["score"], r["harness"]))
    return rows


def build_byo_rows(providers):
    rows = []
    for p in providers:
        if not p or p.get("providerId") == "all":
            continue
        windows = p.get("limits") or []
        balance = p.get("balance")
        if windows:
            continue
        if balance and float(balance.get("funded") or 0) > 0:
            continue
        today = int(p.get("todayTotalTokens") or 0)
        harness = p.get("chipName") or p.get("providerName")
        why = "sem cota" + (f" · {today} tokens hoje" if today > 0 else "")
        rows.append({
            "providerId": p.get("providerId"),
            "harness": harness,
            "todayTokens": today,
            "why": why,
        })
    rows.sort(key=lambda r: -r["todayTokens"])
    return rows


class RadarRankTests(unittest.TestCase):
    def live_machine(self):
        hour = 3_600_000
        day = 24 * hour
        return [
            {"providerId": "all", "limits": [{"title": "Ignored", "percent": 0, "resetMs": day}]},
            {"providerId": "claude", "chipName": "Claude", "tierLabel": "max", "limits": [
                {"title": "Session", "percent": 0.11, "resetMs": 4 * hour},
                {"title": "Weekly", "percent": 0.77, "resetMs": 5 * day},
                {"title": "Fable Weekly", "percent": 1.0, "resetMs": 3 * day},
            ]},
            {"providerId": "antigravity", "chipName": "AGY", "tierLabel": "Google", "limits": [
                {"title": "Gemini Session", "percent": 0.91, "resetMs": 2 * hour},
                {"title": "Gemini Weekly", "percent": 0.15, "resetMs": 6 * day},
                {"title": "Claude / GPT Session", "percent": 0.40, "resetMs": 3 * hour},
                {"title": "Claude / GPT Weekly", "percent": 0.60, "resetMs": 4 * day},
            ]},
            {"providerId": "cursor", "chipName": "Cursor", "limits": [
                {"title": "Cursor Models", "percent": 0.11, "resetMs": 10 * day},
                {"title": "Other Models", "percent": 0.83, "resetMs": 10 * day},
            ]},
            {"providerId": "grok", "chipName": "Grok", "limits": [
                {"title": "Weekly", "percent": 0.76, "resetMs": 2 * day},
            ]},
            {"providerId": "codex", "chipName": "Codex", "limits": [
                {"title": "Weekly", "percent": 0.0, "resetMs": 7 * day},
            ]},
            {"providerId": "hermes", "chipName": "Hermes", "tierLabel": "Local",
             "limits": [], "todayTotalTokens": 8000},
            {"providerId": "opencode", "chipName": "OpenCode", "tierLabel": "Local",
             "limits": [], "todayTotalTokens": 2000},
            {"providerId": "devin", "chipName": "Devin", "tierLabel": "Local",
             "limits": [], "todayTotalTokens": 0},
        ]

    def keys(self, rows):
        return [f"{r['harness']} {r['title']}" for r in rows]

    def test_emptiest_usable_pool_is_first(self):
        rows = build_quota_rows(self.live_machine())
        self.assertEqual(rows[0]["harness"], "Codex")
        self.assertEqual(rows[0]["title"], "Weekly")
        self.assertAlmostEqual(rows[0]["headroom"], 1.0)
        self.assertIn("0% usado", rows[0]["why"])
        self.assertIn("reset em 7d", rows[0]["why"])

    def test_exhausted_sinks_and_gets_a_badge(self):
        rows = build_quota_rows(self.live_machine())
        last = rows[-1]
        self.assertEqual(last["title"], "Fable Weekly")
        self.assertTrue(last["exhausted"])
        self.assertEqual(last["badge"], "esgotado")
        self.assertIn("esgotado", last["why"])
        self.assertEqual(self.keys(rows).count("Claude Fable Weekly"), 1)

    def test_alarming_without_imminent_reset_is_near_bottom(self):
        rows = build_quota_rows(self.live_machine())
        keys = self.keys(rows)
        self.assertLess(keys.index("Codex Weekly"), keys.index("AGY Gemini Session"))
        self.assertLess(keys.index("AGY Gemini Session"), keys.index("Claude Fable Weekly"))
        gemini = next(r for r in rows if r["title"] == "Gemini Session")
        self.assertEqual(gemini["band"], 2)
        self.assertEqual(gemini["badge"], "alarmante")

    def test_alarming_with_imminent_reset_stays_usable(self):
        providers = [{
            "providerId": "agy", "chipName": "AGY",
            "limits": [
                {"title": "Gemini Session", "percent": 0.91, "resetMs": 20 * 60 * 1000},
                {"title": "Gemini Weekly", "percent": 0.15, "resetMs": 6 * 24 * 3_600_000},
            ],
        }]
        rows = build_quota_rows(providers)
        session = next(r for r in rows if r["title"] == "Gemini Session")
        self.assertEqual(session["band"], 1)
        self.assertEqual(session["badge"], "quase reset")
        self.assertIn("quase reset", session["why"])

    def test_session_and_weekly_both_surface_ranked_by_headroom(self):
        keys = self.keys(build_quota_rows(self.live_machine()))
        self.assertLess(keys.index("Claude Session"), keys.index("Claude Weekly"))
        self.assertLess(keys.index("AGY Gemini Weekly"), keys.index("AGY Gemini Session"))
        self.assertIn("Claude Session", keys)
        self.assertIn("Claude Weekly", keys)

    def test_all_aggregate_is_skipped(self):
        keys = self.keys(build_quota_rows(self.live_machine()))
        self.assertNotIn("Ignored", " ".join(keys))

    def test_byo_is_separate_and_ranked_by_today_tokens(self):
        byo = build_byo_rows(self.live_machine())
        self.assertEqual([r["harness"] for r in byo], ["Hermes", "OpenCode", "Devin"])
        self.assertTrue(all("sem cota" in r["why"] for r in byo))
        quota_ids = {r["providerId"] for r in build_quota_rows(self.live_machine())}
        self.assertFalse(quota_ids & {"hermes", "opencode", "devin"})

    def test_prepaid_without_limits_is_a_quota_row(self):
        rows = build_quota_rows([{
            "providerId": "fireworks",
            "chipName": "Fireworks",
            "limits": [],
            "balance": {"remaining": 4.2, "funded": 20.0, "currency": "USD"},
        }])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Prepaid")
        self.assertAlmostEqual(rows[0]["percent"], 0.79)
        self.assertIn("$4.20 restantes", rows[0]["balanceText"])
        self.assertEqual(build_byo_rows([{
            "providerId": "fireworks",
            "chipName": "Fireworks",
            "limits": [],
            "balance": {"remaining": 4.2, "funded": 20.0, "currency": "USD"},
        }]), [])

    def test_sooner_reset_nudge_does_not_outrank_real_headroom(self):
        rows = build_quota_rows([
            {"providerId": "a", "chipName": "A", "limits": [
                {"title": "Weekly", "percent": 0.80, "resetMs": 10 * 60 * 1000},
            ]},
            {"providerId": "b", "chipName": "B", "limits": [
                {"title": "Weekly", "percent": 0.10, "resetMs": 7 * 24 * 3_600_000},
            ]},
        ])
        self.assertEqual(rows[0]["harness"], "B")
        self.assertEqual(rows[1]["harness"], "A")


if __name__ == "__main__":
    unittest.main()
