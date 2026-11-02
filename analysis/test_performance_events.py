import json
import unittest
import numpy as np
import pandas as pd
from analysis.performance_events import detect_performance_events
from analysis.report import build_report


class PerformanceEventsTest(unittest.TestCase):
    def data(self, mspt, tps=None, seconds=None, sessions=None):
        n = len(mspt)
        return pd.DataFrame({
            "timestamp_utc": [pd.Timestamp("2026-11-01T00:00:00Z") + pd.Timedelta(seconds=s)
                              for s in (seconds if seconds is not None else range(0, n * 10, 10))],
            "session_id": sessions if sessions is not None else [1] * n,
            "mspt_avg": mspt, "tps_1m": tps if tps is not None else [20] * n,
            "source_file": "example.csv", "csv_row": list(range(2, n + 2)),
        })

    def test_single_observation(self):
        result = detect_performance_events(self.data([60]))
        self.assertEqual(result["episode_counts"], dict(high_mspt=1, low_tps=0, elevated_mspt=1))
        event = result["episodes"][0]
        self.assertTrue(event["single_observation"])
        self.assertIsNone(event["observed_span_seconds"])
        self.assertEqual(event["source_rows"], [2])

    def test_consecutive_and_normal_row_break(self):
        result = detect_performance_events(self.data([60, 70, 10, 80]))
        events = [e for e in result["episodes"] if e["signal"] == "high_mspt"]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["measurements"], 2)
        self.assertEqual(events[0]["observed_span_seconds"], 10)
        self.assertEqual(events[0]["source_rows"], [2, 3])
        self.assertEqual(events[0]["peak_mspt"], 70)

    def test_independent_signals(self):
        result = detect_performance_events(self.data([30, 60, 10], [18, 20, 18]))
        self.assertEqual(result["episode_counts"], dict(high_mspt=1, low_tps=2, elevated_mspt=1))
        elevated = next(e for e in result["episodes"] if e["signal"] == "elevated_mspt")
        self.assertEqual(elevated["min_tps"], 18)
        self.assertEqual(elevated["source_rows"], [2, 3])

    def test_restart_and_file_boundaries(self):
        result = detect_performance_events(self.data([60, 60], sessions=[1, 2]))
        self.assertEqual(result["episode_counts"]["high_mspt"], 2)
        df = self.data([60, 60])
        df.loc[1, "source_file"] = "another.csv"
        self.assertEqual(detect_performance_events(df)["episode_counts"]["high_mspt"], 2)

    def test_gap_strict_boundary_and_backward_time(self):
        df = self.data([60, 60, 60], seconds=[0, 30, 61])
        self.assertEqual(detect_performance_events(df)["episode_counts"]["high_mspt"], 2)
        self.assertEqual(detect_performance_events(df, max_gap_seconds=31)["episode_counts"]["high_mspt"], 1)
        self.assertEqual(detect_performance_events(self.data([60, 60], seconds=[10, 0]))["episode_counts"]["high_mspt"], 2)

    def test_exact_thresholds_and_custom_parameters(self):
        df = self.data([25, 50], [19, 19])
        self.assertEqual(detect_performance_events(df)["episode_counts"], dict(high_mspt=0, low_tps=0, elevated_mspt=1))
        self.assertEqual(detect_performance_events(df, high_mspt=49, low_tps=20, elevated_mspt=50)["episode_counts"],
                         dict(high_mspt=1, low_tps=1, elevated_mspt=0))

    def test_invalid_rows_break_events_and_do_not_mutate(self):
        for column, invalid in [("mspt_avg", np.nan), ("mspt_avg", np.inf), ("mspt_avg", -1),
                                ("tps_1m", "bad"), ("timestamp_utc", "bad"), ("session_id", None)]:
            with self.subTest(column=column, invalid=invalid):
                df = self.data([60, 60, 60])
                df[column] = df[column].astype(object)
                df.loc[1, column] = invalid
                original = df.copy(deep=True)
                result = detect_performance_events(df)
                self.assertEqual(result["invalid_rows"], 1)
                self.assertEqual(result["episode_counts"]["high_mspt"], 2)
                pd.testing.assert_frame_equal(df, original)
        with self.assertRaises(ValueError):
            detect_performance_events(self.data([60]).drop(columns="tps_1m"))
        with self.assertRaises(ValueError):
            detect_performance_events(self.data([60]), max_gap_seconds=-1)

    def test_json_report_integration(self):
        df = self.data([60, 70])
        df["elapsed_ms"] = [0, 10000]
        df["players_online"] = 1
        df["anomaly_score"] = [0.1, -0.1]
        df["stat_anomaly"] = [False, True]
        df["ml_anomaly"] = [False, True]
        df["rolling_threshold"] = np.nan
        report = build_report(df)
        serialized = json.loads(json.dumps(report, allow_nan=False))
        self.assertEqual(serialized["performance_events"]["episodes"][0]["session_id"], 1)
        self.assertEqual(serialized["ml_anomalies"], 1)
        self.assertEqual(serialized["performance_events"]["episodes"][0]["last_observed_utc"], "2026-11-01T00:00:10+00:00")


if __name__ == "__main__":
    unittest.main()
