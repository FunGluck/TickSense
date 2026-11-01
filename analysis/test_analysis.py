"""Small deterministic tests, without Minecraft or external datasets."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from analysis.data import load_data
from analysis.statistical import detect_statistical
from analysis.isolation import FEATURES, train_model, predict_anomalies
from analysis.report import compare_detectors, build_report


class AnalysisTest(unittest.TestCase):
    def load(self, elapsed, mspt):
        data = pd.DataFrame({
            "timestamp_utc": pd.date_range("2026-11-01", periods=len(elapsed), freq="10s", tz="UTC"),
            "elapsed_ms": elapsed, "mspt_avg": mspt,
            "players_online": 2, "tps_1m": 20.0,
        })
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "metrics.csv"
            data.to_csv(path, index=False)
            return load_data(path)

    def test_sessions_reset_windows(self):
        data = self.load([100, 200, 300, 400, 500, 600, 700, 100, 200], [10] * 9)
        result = detect_statistical(data)
        self.assertEqual(result.session_id.tolist(), [1] * 7 + [2] * 2)
        self.assertEqual(result.rolling_threshold.iloc[6], 10)
        self.assertTrue(result.rolling_threshold.iloc[7:].isna().all())
        self.assertFalse(result.online_changed.iloc[7])

    def test_threshold_uses_six_previous_values_and_sample_std(self):
        result = detect_statistical(self.load(range(8), [1, 2, 3, 4, 5, 6, 100, 1]))
        self.assertTrue(result.rolling_threshold.iloc[:6].isna().all())
        self.assertAlmostEqual(result.rolling_threshold.iloc[6], 3.5 + 3 * (3.5 ** 0.5))
        self.assertTrue(result.stat_anomaly.iloc[6])
        self.assertAlmostEqual(result.rolling_mean.iloc[7], (2 + 3 + 4 + 5 + 6 + 100) / 6)

    def test_detector_comparison(self):
        counts = compare_detectors(pd.DataFrame({
            "stat_anomaly": [True, True, False, False],
            "ml_anomaly": [True, False, True, False],
        }))
        self.assertEqual(counts, dict(stat_anomalies=2, ml_anomalies=2, both=1,
                                      only_stat=1, only_ml=1, neither=1))

    def test_fit_only_receives_training_and_prediction_does_not_refit(self):
        training = self.load(range(20), list(range(20)))
        evaluation = self.load(range(12), list(range(100, 112)))
        with patch("analysis.isolation.IsolationForest", autospec=True) as forest:
            model = train_model(training)
            pd.testing.assert_frame_equal(model.fit.call_args.args[0], training[FEATURES])
            model.predict.return_value = [-1] * len(evaluation)
            model.decision_function.return_value = [-0.1] * len(evaluation)
            predict_anomalies(model, evaluation)
            self.assertEqual(model.fit.call_count, 1)
            pd.testing.assert_frame_equal(model.predict.call_args.args[0], evaluation[FEATURES])
            forest.assert_called_once_with(n_estimators=100, contamination=0.05, random_state=42)

    def test_report_uses_evaluation_and_sorts_top_ten(self):
        data = detect_statistical(self.load(range(12), list(range(12))))
        data["anomaly_score"] = list(reversed(range(12)))
        data["ml_anomaly"] = False
        report = build_report(data)
        self.assertEqual(report["measurements"], 12)
        self.assertEqual(report["mspt_avg_mean"], 5.5)
        self.assertEqual(report["mspt_avg_max"], 11)
        self.assertEqual([row["anomaly_score"] for row in report["top_10_lowest_scores"]], list(range(10)))
        json.dumps(report, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
