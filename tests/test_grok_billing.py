import importlib.machinery
import importlib.util
import unittest
from pathlib import Path

_path = Path(__file__).parents[1] / "bin/omarchy-agent-usage-grok"
_loader = importlib.machinery.SourceFileLoader("grok_usage", str(_path))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
grok = importlib.util.module_from_spec(_spec)
_loader.exec_module(grok)


class GrokBillingTests(unittest.TestCase):
    def test_named_plan_without_a_percentage_is_unread_not_empty(self):
        # Live shape from a SuperGrok Heavy account after unified billing
        # stopped sending creditUsagePercent. The plan is back; the meter is not.
        parsed = grok.parse_billing({
            "config": {
                "currentPeriod": {
                    "type": "USAGE_PERIOD_TYPE_WEEKLY",
                    "end": "2026-10-04T13:24:53.895663+00:00",
                },
                "onDemandCap": {"val": 0},
                "onDemandUsed": {"val": 0},
                "prepaidBalance": {"val": 0},
                "isUnifiedBillingUser": True,
            },
            "subscription_tier": "SuperGrok Heavy",
        })
        self.assertEqual(parsed["tierLabel"], "SuperGrok Heavy")
        self.assertEqual(parsed["limits"], [])
        self.assertIsNone(parsed["balance"])
        self.assertEqual(parsed["quotaState"], "unread")
        self.assertEqual(parsed["authHelpText"], "")

    def test_credit_percentage_still_fills_the_weekly_meter(self):
        parsed = grok.parse_billing({
            "config": {
                "creditUsagePercent": 40,
                "currentPeriod": {"type": "USAGE_PERIOD_TYPE_WEEKLY", "end": "2026-10-04T00:00:00+00:00"},
                "prepaidBalance": {"val": 0},
                "onDemandCap": {"val": 0},
                "onDemandUsed": {"val": 0},
            },
            "subscription_tier": "SuperGrok Heavy",
        })
        self.assertEqual(parsed["quotaState"], "ok")
        self.assertEqual(len(parsed["limits"]), 1)
        self.assertEqual(parsed["limits"][0]["label"], "Weekly")
        self.assertAlmostEqual(parsed["limits"][0]["percent"], 0.4)
