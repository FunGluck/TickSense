"""Persistent ML regression checks use synthetic CSVs only."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from sklearn.ensemble import IsolationForest

from analysis import analyze
from analysis.compare_saved_models import compare_models
from analysis.data_quality import load_period
from analysis.features import engineer_features
from analysis.isolation import FEATURES, predict_anomalies, train_model
from analysis.model_store import load_model
from analysis.performance_events import detect_performance_events
from analysis.statistical import detect_statistical
from analysis.synthetic_pilot import generate
from analysis.train_model import train_candidate


class PersistentMLTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.folder = Path(directory.name)
        self.frame = generate().iloc[:60].copy()
        self.frame.timestamp_utc -= pd.Timedelta(hours=12, minutes=3)
        self.frame.loc[30:, "elapsed_ms"] -= self.frame.loc[30, "elapsed_ms"]
        self.paths = self.write_days(self.frame, "history")
        self.model_path = self.folder / "test-v1.joblib"

    def write_days(self, frame, prefix):
        paths = []
        for date, rows in frame.groupby(frame.timestamp_utc.dt.date):
            path = self.folder / f"{prefix}-{date}.csv"
            rows.to_csv(path, index=False)
            paths.append(path)
        return paths

    def train(self):
        return train_candidate(self.paths, self.model_path, server_id="synthetic")[0]

    def test_chronological_training_and_round_trip(self):
        details = self.train()
        self.assertEqual(len(self.paths), 2)
        self.assertEqual(details["data_quality"]["sessions"], 2)
        self.assertEqual(details["training"]["measurements"], 48)
        self.assertEqual(details["validation"]["evaluated"], 12)
        self.assertLess(pd.Timestamp(details["training"]["end_utc"]), pd.Timestamp(details["validation"]["start_utc"]))

        frame = engineer_features(load_period(self.paths))
        self.assertEqual(frame.session_id.iloc[17:19].tolist(), [1, 1])  # UTC midnight
        self.assertEqual(frame.session_id.iloc[29:31].tolist(), [1, 2])  # restart
        before = predict_anomalies(train_model(frame.iloc[:48]), frame.iloc[48:])
        saved, metadata = load_model(self.model_path)
        after = predict_anomalies(saved, frame.iloc[48:])
        pd.testing.assert_frame_equal(before, after)
        self.assertEqual(metadata["parameters"], IsolationForest(
            n_estimators=100, contamination=.05, max_samples="auto", random_state=42,
        ).get_params())
        self.assertEqual(metadata["features"], FEATURES)

        changed = self.frame.copy()
        changed.loc[48:, "mspt_avg"] = 100
        updated = self.folder / "test-v2.joblib"
        train_candidate(self.write_days(changed, "changed"), updated, server_id="synthetic")
        second, _ = load_model(updated)
        pd.testing.assert_series_equal(
            predict_anomalies(saved, frame).anomaly_score,
            predict_anomalies(second, frame).anomaly_score,
        )
        with self.assertRaisesRegex(ValueError, "после"):
            compare_models(self.paths, [self.model_path, updated])
        future = self.frame.copy()
        future.timestamp_utc += pd.Timedelta(days=10)
        comparison = compare_models(self.write_days(future, "independent"), [self.model_path, updated])
        self.assertEqual([row["evaluated"] for row in comparison["models"]], [60, 60])
        self.assertEqual(comparison["models"][0]["decision_function_quantiles"],
                         comparison["models"][1]["decision_function_quantiles"])

    def test_rejects_artifact_mismatches_and_overwrite(self):
        self.train()
        before = self.model_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "Версия уже существует"):
            self.train()
        self.assertEqual(self.model_path.read_bytes(), before)
        sidecar = self.model_path.with_suffix(".metadata.json")
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        for changes, message in [
            ({"features": FEATURES[::-1]}, "порядок"),
            ({"feature_schema_version": 2}, "схемы"),
            ({"environment": dict(metadata["environment"], numpy="wrong")}, "окружение"),
        ]:
            with self.subTest(changes=changes), patch("analysis.model_store.joblib.load") as deserialize:
                sidecar.write_text(json.dumps(dict(metadata, **changes)), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    load_model(self.model_path)
                deserialize.assert_not_called()
        sidecar.write_text(json.dumps(metadata), encoding="utf-8")
        self.model_path.write_bytes(before + b"broken")
        with patch("analysis.model_store.joblib.load") as deserialize:
            with self.assertRaisesRegex(ValueError, "Контрольная сумма"):
                load_model(self.model_path)
            deserialize.assert_not_called()
        with self.assertRaisesRegex(ValueError, "локальный"):
            load_model("https://example.invalid/model.joblib")

    def test_saved_cli_full_history_and_missing_features(self):
        self.train()
        future = self.frame.copy()
        future.timestamp_utc += pd.Timedelta(days=10)
        future.loc[8:11, ["mspt_avg", "tps_1m"]] = [120, 12]
        future.loc[20, "players_online"] = float("nan")
        future.loc[22, "mspt_avg"] = float("nan")
        future.loc[24, "tps_1m"] = float("nan")
        paths = self.write_days(future, "new")
        html_path, json_path = self.folder / "result.html", self.folder / "result.json"
        args = ["analyze", "--pilot-files", *map(str, paths), "--model", str(self.model_path),
                "--html", str(html_path), "--json", str(json_path), "--no-show"]
        with patch.object(sys, "argv", args), patch("analysis.isolation.IsolationForest.fit",
                                                     side_effect=AssertionError("unexpected fit")), redirect_stdout(io.StringIO()):
            analyze.main()
        report = json.loads(json_path.read_text(encoding="utf8"))
        payload = json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>',
                                       html_path.read_text(encoding="utf8"), re.S)[1])
        self.assertIsNone(report["full_period"]["ml_boundary"])
        self.assertEqual(report["full_period"]["scope"], "saved_model")
        self.assertEqual(report["ml_model"]["evaluated_measurements"], 57)
        self.assertEqual(report["ml_model"]["unscored_measurements"], 3)
        self.assertEqual(len(payload["columns"]["ml_anomaly"]), 60)
        self.assertEqual(payload["columns"]["ml_anomaly"].count(None), 3)
        self.assertEqual(payload["ml_model"]["version"], "test-v1")
        prepared = detect_statistical(engineer_features(load_period(paths, allow_missing_model_metrics=True)))
        expected = predict_anomalies(load_model(self.model_path)[0], prepared)
        self.assertEqual(payload["columns"]["stat_anomaly"], prepared.stat_anomaly.tolist())
        scores = expected.anomaly_score.astype(object).where(expected.anomaly_score.notna(), None)
        self.assertEqual(payload["columns"]["anomaly_score"], scores.tolist())
        self.assertEqual(report["performance_events"]["episode_counts"],
                         detect_performance_events(prepared)["episode_counts"])
        self.assertTrue(report["event_insights"]["ml_episodes"])
        self.assertEqual(sum(episode["measurements"] for episode in report["event_insights"]["ml_episodes"]),
                         report["ml_anomalies"])


if __name__ == "__main__":
    unittest.main()
