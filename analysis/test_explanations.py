import json
import unittest
from copy import deepcopy
from unittest.mock import patch
import numpy as np
import pandas as pd
from analysis.explanations import add_explanations
from analysis.features import engineer_features
from analysis.performance_events import detect_performance_events
from analysis.report import build_report


class ExplanationsTest(unittest.TestCase):
    def data(self):
        return pd.DataFrame({
            "timestamp_utc": pd.date_range("2026-11-01", periods=4, freq="10s", tz="UTC"),
            "session_id": [1] * 4, "mspt_avg": [1, 60, 70, 1], "tps_1m": [20, 18, 17, 20],
            "source_file": "example.csv", "csv_row": [2, 3, 4, 5],
            "loaded_chunks_delta": [np.nan, 567, -20, 99999],
            "entities_delta": [np.nan, 160, -10, 99999],
            "gc_count_delta": [np.nan, 2, 3, 99999],
            "gc_time_delta_ms": [np.nan, 330, 10, 99999],
            "heap_used_ratio": [0.2, 0.4, 0.6, 1.0],
        })

    def explanation(self, df):
        events = add_explanations(df, detect_performance_events(df))
        return next(e["explanation"] for e in events["episodes"] if e["signal"] == "high_mspt")

    def test_single_episode(self):
        result = self.explanation(self.data().iloc[:2])
        self.assertEqual(result["measurements"], 1)
        self.assertEqual(result["source_rows"], [3])
        self.assertEqual(result["telemetry_context"]["gc_time_delta_ms"]["sum_delta"], 330)
        self.assertIn("60.00", result["description"])

    def test_multirow_aggregation(self):
        result = self.explanation(self.data())
        context = result["telemetry_context"]
        self.assertEqual(result["matched_rows"], 2)
        self.assertEqual(context["gc_time_delta_ms"]["sum_delta"], 340)
        self.assertEqual(context["gc_count_delta"]["sum_delta"], 5)
        self.assertEqual(context["loaded_chunks_delta"]["net_delta"], 547)
        self.assertEqual(context["loaded_chunks_delta"]["max_positive_delta"], 567)
        self.assertEqual(context["heap_used_ratio"]["max"], 0.6)
        self.assertEqual(context["heap_used_ratio"]["available_observations"], 2)
        self.assertNotIn("sum_delta", context["heap_used_ratio"])

    def test_derived_features_from_raw(self):
        df = self.data().drop(columns=["gc_count_delta", "gc_time_delta_ms", "loaded_chunks_delta", "entities_delta", "heap_used_ratio"])
        df["gc_collection_count"] = [10, 12, 15, 20]
        df["gc_collection_time_ms"] = [100, 430, 440, 500]
        df["loaded_chunks"] = [100, 667, 647, 1000]
        result = self.explanation(engineer_features(df))
        self.assertEqual(result["telemetry_context"]["gc_time_delta_ms"]["sum_delta"], 340)
        self.assertEqual(result["telemetry_context"]["loaded_chunks_delta"]["net_delta"], 547)

    def test_v1_missing_context(self):
        df = self.data().iloc[:, :6]
        result = self.explanation(df)
        self.assertTrue(all(v["status"] == "unavailable" for v in result["telemetry_context"].values()))
        self.assertIsNone(result["telemetry_context"]["loaded_chunks_delta"]["net_delta"])
        self.assertIn("Сопутствующий контекст телеметрии недоступен.", result["observed_facts"])
        self.assertEqual(len(result["observed_facts"]), 2)

    def test_unavailable_gc_not_zero(self):
        df = self.data()
        df["gc_count_delta"] = -1
        df["gc_time_delta_ms"] = np.nan
        result = self.explanation(df)["telemetry_context"]
        self.assertIsNone(result["gc_count_delta"]["sum_delta"])
        self.assertEqual(result["gc_count_delta"]["available_observations"], 0)
        self.assertIsNone(result["gc_time_delta_ms"]["sum_delta"])

    def test_negative_changes_are_valid(self):
        df = self.data().iloc[:2].copy()
        df["loaded_chunks_delta"] = -1
        df["entities_delta"] = -160
        result = self.explanation(df)["telemetry_context"]
        self.assertEqual(result["loaded_chunks_delta"]["net_delta"], -1)
        self.assertEqual(result["entities_delta"]["net_delta"], -160)
        self.assertEqual(result["entities_delta"]["available_observations"], 1)

    def test_future_rows_do_not_affect_explanation(self):
        self.assertEqual(self.explanation(self.data()), self.explanation(self.data().iloc[:3]))

    def test_session_and_file_isolation(self):
        df = self.data()
        original = self.explanation(df)
        other = df.copy()
        other["session_id"] = 2
        other["gc_time_delta_ms"] = 99999
        combined = pd.concat([df, other], ignore_index=True)
        self.assertEqual(self.explanation(combined), original)
        other["session_id"] = 1
        other["source_file"] = "another.csv"
        self.assertEqual(self.explanation(pd.concat([df, other], ignore_index=True)), original)

    def test_deterministic_json_and_no_mutations(self):
        df = self.data()
        original = df.copy(deep=True)
        events = detect_performance_events(df)
        saved = deepcopy(events)
        enriched = add_explanations(df, events)
        self.assertEqual(enriched, add_explanations(df, events))
        self.assertEqual(json.loads(json.dumps(enriched, ensure_ascii=False, allow_nan=False)), enriched)
        self.assertEqual(events, saved)
        pd.testing.assert_frame_equal(df, original)
        for event, old in zip(enriched["episodes"], saved["episodes"]):
            self.assertEqual({k: v for k, v in event.items() if k != "explanation"}, old)
        text = " ".join(enriched["episodes"][0]["explanation"]["observed_facts"])
        self.assertNotIn("вызвал", text)
        self.assertNotIn("загрузка мира", text)

    def test_previous_report_fields_preserved(self):
        df = self.data()
        df["elapsed_ms"] = [0, 10, 20, 30]
        df["players_online"] = 1
        df["anomaly_score"] = 0.1
        df["stat_anomaly"] = False
        df["ml_anomaly"] = False
        df["rolling_threshold"] = np.nan
        report = build_report(df)
        with patch("analysis.report.add_explanations", side_effect=lambda df, events: events):
            old_report = build_report(df)
        for event in report["performance_events"]["episodes"]:
            del event["explanation"]
        self.assertEqual(report, old_report)


if __name__ == "__main__":
    unittest.main()
