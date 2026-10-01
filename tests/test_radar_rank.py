"""Contract for Panel.qml Radar ranking.

Keep this in sync with the QML: buildRadarQuotaRows / buildRadarByoRows.
The radar only ranks the five paid subscriptions — Claude, Codex, Grok,
Cursor, Antigravity — one weekly pool each. Sessions, extra model-scoped
pools, and every other harness stay out; exhausted pools sink; providers
with no limits never mix into the quota list.
"""
import re
import unittest


ALARMING = 0.9
EXHAUSTED = 1.0
IMMINENT_MS = 30 * 60 * 1000
NUDGE_FROM = 0.7


def radar_provider_allowed(provider_id):
    pid = str(provider_id or "").lower()
    return pid in ("claude", "codex", "grok", "cursor", "agy", "a01") or "antigravity" in pid


def radar_window_allowed(provider_id, title):
    pid = str(provider_id or "").lower()
    text = str(title or "").lower()
    if pid in ("antigravity", "agy", "a01") or "antigravity" in pid:
        return "gemini" in text and "weekly" in text and "session" not in text
    if "session" in text:
        return False
    if pid == "cursor":
        return True
    return text == "weekly"


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


def radar_pool(title):
    name = str(title or "")
    if name.lower() == "weekly":
        return ""
    return re.sub(r"\s+weekly$", "", name, flags=re.I)


def radar_why(percent, reset_ms, exhausted, alarming, imminent):
    line = "esgotado" if exhausted else f"{round(max(0.0, 1.0 - percent) * 100)}% livre"
    if not exhausted and alarming and imminent:
        line += " · quase reset"
    if reset_ms > 0:
        line += (" · volta em " if exhausted else " · reset em ") + format_duration(reset_ms)
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
        if not radar_provider_allowed(p.get("providerId")):
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
            if not radar_window_allowed(p.get("providerId"), win.get("title")):
                continue
            percent = float(win["percent"])
            reset_ms = float(win.get("resetMs", -1))
            exhausted = percent >= EXHAUSTED
            imminent = reset_ms > 0 and reset_ms < IMMINENT_MS
            alarming = percent >= ALARMING
            band = radar_band(percent, reset_ms)
            rows.append({
                "providerId": p.get("providerId"),
                "harness": harness,
                "account": account_label(p),
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
                "pool": radar_pool(win.get("title") or "Limit"),
                "why": radar_why(percent, reset_ms, exhausted, alarming, imminent),
                "balanceText": balance_text if i == 0 else "",
            })
    rows.sort(key=lambda r: (r["band"], -r["score"], r["harness"]))
    return rows


def radar_tier(p):
    tier = str((p or {}).get("tierLabel") or "")
    return (tier[:1].upper() + tier[1:]) if tier else ""


def account_label(p):
    email = str((p or {}).get("accountEmail") or "").strip()
    name = str((p or {}).get("accountName") or "").strip()
    if email and name and name.lower() not in email.lower():
        return f"{name} · {email}"
    return email or name


def account_auth_broken(p):
    if not p:
        return False
    if str(p.get("quotaState") or "") == "ok":
        return False
    if (p.get("limits") or []) and str(p.get("quotaState") or "") != "auth":
        return False
    return bool(str(p.get("usageStatusText") or "")) and bool(str(p.get("authHelpText") or ""))


def allowed_windows(p):
    picked = []
    for win in p.get("limits") or []:
        title = win.get("title") or win.get("label") or ""
        if radar_window_allowed(p.get("providerId"), title):
            picked.append(win)
    return picked


def account_quota_missing(p):
    if not p or p.get("providerId") == "all":
        return False
    if not radar_provider_allowed(p.get("providerId")):
        return False
    state = str(p.get("quotaState") or "")
    if state == "unread":
        return True
    if state in ("ok", "auth"):
        return False
    if p.get("limits"):
        return False
    balance = p.get("balance") or {}
    if float(balance.get("funded") or 0) > 0:
        return False
    return radar_tier(p) != ""


def account_reading(p):
    if str(p.get("quotaState") or "") == "auth" or account_auth_broken(p):
        return "login caiu"
    picked = None
    for win in allowed_windows(p):
        if picked is None or float(win.get("percent") or 0) > float(picked.get("percent") or 0):
            picked = win
    if picked is not None:
        title = picked.get("title") or picked.get("label") or ""
        return f"{title} {round(float(picked.get('percent') or 0) * 100)}%"
    balance = p.get("balance") or {}
    if float(balance.get("funded") or 0) > 0:
        remaining = float(balance.get("remaining") or 0)
        currency = str(balance.get("currency") or "USD")
        prefix = "$" if currency == "USD" else currency + " "
        return f"{prefix}{remaining:.2f} restantes"
    if account_quota_missing(p):
        return "cota não veio"
    return "sem leitura"


def build_account_rows(providers):
    rows = []
    for p in providers:
        if not p or p.get("providerId") == "all":
            continue
        if not radar_provider_allowed(p.get("providerId")):
            continue
        tier = radar_tier(p)
        held = tier != "" or account_auth_broken(p) or str(p.get("quotaState") or "") == "auth"
        if not held and allowed_windows(p):
            held = True
        balance = p.get("balance") or {}
        if not held and float(balance.get("funded") or 0) > 0:
            held = True
        if not held:
            continue
        broken = account_auth_broken(p) or str(p.get("quotaState") or "") == "auth"
        if not broken and not account_quota_missing(p):
            continue
        rows.append({
            "providerId": p.get("providerId"),
            "harness": p.get("chipName") or p.get("providerName"),
            "account": account_label(p),
            "tier": tier,
            "reading": account_reading(p),
            "action": "entrar" if broken else "reler",
            "stale": True,
        })
    rows.sort(key=lambda row: str(row["harness"]))
    return rows


def build_byo_rows(providers):
    rows = []
    for p in providers:
        if not p or p.get("providerId") == "all":
            continue
        if not radar_provider_allowed(p.get("providerId")):
            continue
        windows = p.get("limits") or []
        balance = p.get("balance")
        if windows:
            continue
        if balance and float(balance.get("funded") or 0) > 0:
            continue
        if radar_tier(p) or account_auth_broken(p) or str(p.get("quotaState") or "") == "auth":
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
                {"title": "Weekly", "percent": 0.95, "resetMs": 2 * day},
            ]},
            {"providerId": "codex", "chipName": "Codex", "limits": [
                {"title": "Session", "percent": 0.02, "resetMs": 3 * hour},
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
        self.assertTrue(rows[0]["why"].startswith("100% livre"))
        self.assertIn("reset em 7d", rows[0]["why"])
        self.assertEqual(rows[0]["pool"], "")

    def test_only_the_five_weeklies_surface(self):
        keys = self.keys(build_quota_rows(self.live_machine()))
        self.assertEqual(keys, [
            "Codex Weekly",
            "Cursor Cursor Models",
            "AGY Gemini Weekly",
            "Claude Weekly",
            "Cursor Other Models",
            "Grok Weekly",
        ])
        joined = " ".join(keys)
        for dropped in ("Session", "Fable", "Claude / GPT", "Hermes", "OpenCode", "Devin"):
            self.assertNotIn(dropped, joined)

    def test_exhausted_weekly_sinks_and_gets_a_badge(self):
        rows = build_quota_rows([{
            "providerId": "claude", "chipName": "Claude",
            "limits": [{"title": "Weekly", "percent": 1.0, "resetMs": 3 * 24 * 3_600_000}],
        }, {
            "providerId": "codex", "chipName": "Codex",
            "limits": [{"title": "Weekly", "percent": 0.1, "resetMs": 6 * 24 * 3_600_000}],
        }])
        last = rows[-1]
        self.assertEqual(last["harness"], "Claude")
        self.assertTrue(last["exhausted"])
        self.assertEqual(last["badge"], "esgotado")
        self.assertIn("esgotado", last["why"])

    def test_alarming_weekly_sits_near_bottom(self):
        rows = build_quota_rows(self.live_machine())
        last = rows[-1]
        self.assertEqual(last["harness"], "Grok")
        self.assertEqual(last["title"], "Weekly")
        self.assertEqual(last["band"], 2)
        self.assertEqual(last["badge"], "alarmante")

    def test_alarming_with_imminent_reset_stays_usable(self):
        providers = [{
            "providerId": "codex", "chipName": "Codex",
            "limits": [{"title": "Weekly", "percent": 0.91, "resetMs": 20 * 60 * 1000}],
        }]
        rows = build_quota_rows(providers)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["band"], 1)
        self.assertEqual(rows[0]["badge"], "quase reset")
        self.assertIn("quase reset", rows[0]["why"])

    def test_all_aggregate_is_skipped(self):
        keys = self.keys(build_quota_rows(self.live_machine()))
        self.assertNotIn("Ignored", " ".join(keys))

    def test_byo_lists_only_the_five(self):
        self.assertEqual(build_byo_rows(self.live_machine()), [])
        providers = [
            {"providerId": "codex", "chipName": "Codex", "limits": [], "todayTotalTokens": 8000},
            {"providerId": "hermes", "chipName": "Hermes", "limits": [], "todayTotalTokens": 9000},
        ]
        byo = build_byo_rows(providers)
        self.assertEqual([r["harness"] for r in byo], ["Codex"])
        self.assertIn("sem cota", byo[0]["why"])

    def test_prepaid_only_survives_on_the_five(self):
        prepaid = {
            "limits": [],
            "balance": {"remaining": 4.2, "funded": 20.0, "currency": "USD"},
        }
        fireworks = [{"providerId": "fireworks", "chipName": "Fireworks", **prepaid}]
        self.assertEqual(build_quota_rows(fireworks), [])
        self.assertEqual(build_byo_rows(fireworks), [])
        cursor = [{"providerId": "cursor", "chipName": "Cursor", **prepaid}]
        rows = build_quota_rows(cursor)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Prepaid")
        self.assertAlmostEqual(rows[0]["percent"], 0.79)
        self.assertIn("$4.20 restantes", rows[0]["balanceText"])

    def test_sooner_reset_nudge_does_not_outrank_real_headroom(self):
        rows = build_quota_rows([
            {"providerId": "grok", "chipName": "Grok", "limits": [
                {"title": "Weekly", "percent": 0.80, "resetMs": 10 * 60 * 1000},
            ]},
            {"providerId": "codex", "chipName": "Codex", "limits": [
                {"title": "Weekly", "percent": 0.10, "resetMs": 7 * 24 * 3_600_000},
            ]},
        ])
        self.assertEqual(rows[0]["harness"], "Codex")
        self.assertEqual(rows[1]["harness"], "Grok")

    def test_named_plan_without_a_percentage_is_an_account_not_byo(self):
        grok = {
            "providerId": "grok",
            "chipName": "Grok",
            "tierLabel": "SuperGrok Heavy",
            "quotaState": "unread",
            "limits": [],
            "todayTotalTokens": 1200,
        }
        claude = {
            "providerId": "claude",
            "chipName": "Claude",
            "tierLabel": "Max 5x",
            "limits": [{"title": "Weekly", "percent": 0.73, "resetMs": 6 * 3_600_000}],
        }
        self.assertEqual(build_byo_rows([grok, claude]), [])
        self.assertEqual(build_quota_rows([grok]), [])
        accounts = build_account_rows([grok, claude])
        by_id = {row["providerId"]: row for row in accounts}
        self.assertEqual(by_id["grok"]["reading"], "cota não veio")
        self.assertTrue(by_id["grok"]["stale"])
        self.assertEqual(by_id["grok"]["tier"], "SuperGrok Heavy")
        self.assertEqual(by_id["grok"]["action"], "reler")
        # A healthy account is already a ranked row; it gets no warning line.
        self.assertNotIn("claude", by_id)

    def test_pool_names_drop_the_word_weekly(self):
        self.assertEqual(radar_pool("Weekly"), "")
        self.assertEqual(radar_pool("Gemini Weekly"), "Gemini")
        self.assertEqual(radar_pool("Other Models"), "Other Models")

    def test_exhausted_row_says_when_it_comes_back(self):
        self.assertEqual(radar_why(1.0, 3 * 86_400_000, True, True, False), "esgotado · volta em 3d 0h")
        self.assertEqual(radar_why(0.05, 4 * 3_600_000, False, False, False), "95% livre · reset em 4h 0m")

    def test_dropped_login_is_an_account_row(self):
        claude = {
            "providerId": "claude",
            "chipName": "Claude",
            "tierLabel": "Max 5x",
            "quotaState": "auth",
            "usageStatusText": "Sign-in expired",
            "authHelpText": "Run `claude auth login` to restore authoritative usage.",
            "limits": [],
        }
        rows = build_account_rows([claude])
        self.assertEqual(rows[0]["reading"], "login caiu")
        self.assertEqual(rows[0]["action"], "entrar")
        self.assertTrue(rows[0]["stale"])
        self.assertEqual(build_byo_rows([claude]), [])

    def test_codex_with_a_live_meter_is_not_a_dropped_login(self):
        codex = {
            "providerId": "codex",
            "chipName": "Codex",
            "tierLabel": "pro",
            "quotaState": "ok",
            "usageStatusText": "",
            "authHelpText": "Run `codex login` to authenticate.",
            "accountName": "Juliana",
            "accountEmail": "ju@example.com",
            "limits": [{"title": "Weekly", "percent": 0.55, "resetMs": 2 * 86_400_000}],
        }
        self.assertEqual(build_account_rows([codex]), [])
        rows = build_quota_rows([codex])
        self.assertEqual(rows[0]["why"].split(" · ")[0], "45% livre")
        self.assertEqual(rows[0]["account"], "Juliana · ju@example.com")

    def test_a_slow_probe_is_not_a_dropped_login(self):
        codex = {
            "providerId": "codex",
            "chipName": "Codex",
            "tierLabel": "pro",
            "quotaState": "unread",
            "usageStatusText": "Cota do Codex não respondeu",
            "authHelpText": "",
            "limits": [],
        }
        rows = build_account_rows([codex])
        self.assertEqual(rows[0]["reading"], "cota não veio")
        self.assertEqual(rows[0]["action"], "reler")

    def test_a_gateway_label_is_not_a_missing_quota(self):
        router = {
            "providerId": "9router",
            "chipName": "9Router",
            "tierLabel": "Local",
            "limits": [],
        }
        self.assertFalse(account_quota_missing(router))


if __name__ == "__main__":
    unittest.main()
