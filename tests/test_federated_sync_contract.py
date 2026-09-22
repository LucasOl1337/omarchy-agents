"""Static contract for preserving federated 9Router fields through sync."""

import unittest
from pathlib import Path


class FederatedSyncContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (Path(__file__).parents[1] / "Main.qml").read_text()

    def test_snapshot_serializes_federated_period_hour_and_source_fields(self):
        for expression in (
            "periodTokensByModel: cloneValue(record.periodTokensByModel, ({}))",
            "todayHours: cloneValue(record.todayHours, [])",
            "sources: cloneValue(record.sources, [])",
        ):
            self.assertIn(expression, self.source)

    def test_aggregate_preserves_federated_period_hour_and_source_fields(self):
        for expression in (
            "combineObjectNumbers(additive, acc.periodTokensByModel[periodName]",
            "acc.todayHours[hourLabel]",
            "acc.sources[sourceLabel]",
            "periodTokensByModel: acc.periodTokensByModel",
            "todayHours: todayHours",
            "sources: sources",
        ):
            self.assertIn(expression, self.source)


if __name__ == "__main__":
    unittest.main()
