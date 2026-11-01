import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from analysis.compare_models import compare, prepare_files, complete_cases, load_events, EXTENDED


class ComparisonTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.train = self.write("train.csv", 0)
        self.test = self.write("Dragon Run.csv", 100)

    def write(self, name, offset):
        n = 24
        df = pd.DataFrame({
            "timestamp_utc": pd.date_range("2026-11-01", periods=n, freq="10s", tz="UTC"),
            "elapsed_ms": list(range(12)) * 2, "mspt_avg": np.arange(n) + offset + 1,
            "players_online": np.arange(n) % 3, "tps_1m": 20,
            "gc_collection_count": np.arange(n), "gc_collection_time_ms": np.arange(n) * 2,
            "loaded_chunks": np.arange(n) + 10, "entities_total": np.arange(n) + 20,
            "jvm_heap_used_bytes": 50, "jvm_heap_committed_bytes": 100,
        })
        path = self.folder / name
        df.to_csv(path, index=False)
        return path

    def test_same_rows_and_no_evaluation_fit(self):
        models = []
        def factory(**kwargs):
            model = IsolationForest(**kwargs)
            model.fit = unittest.mock.Mock(wraps=model.fit)
            model.predict = unittest.mock.Mock(wraps=model.predict)
            models.append(model)
            return model
        with patch("analysis.compare_models.IsolationForest", side_effect=factory):
            report = compare([self.train], self.test)
        self.assertEqual(report["status"], "ok")
        for model in models:
            self.assertEqual(model.fit.call_count, 1)
            self.assertLess(model.fit.call_args.args[0].mspt_avg.max(), 100)
            self.assertGreater(model.predict.call_args.args[0].mspt_avg.min(), 100)
        self.assertEqual(models[0].fit.call_args.args[0].index.tolist(), models[1].fit.call_args.args[0].index.tolist())
        self.assertEqual(models[0].predict.call_args.args[0].index.tolist(), models[1].predict.call_args.args[0].index.tolist())

    def test_file_and_session_boundaries_and_nan(self):
        second = self.write("second.csv", 0)
        frame = prepare_files([self.train, second])
        self.assertTrue(frame.loc[[0, 12, 24, 36], "gc_count_delta"].isna().all())
        frame.loc[1, "heap_used_ratio"] = np.nan
        selected, info = complete_cases(frame)
        self.assertEqual(info["excluded"], 5)
        self.assertNotIn(1, selected.index)
        self.assertTrue(np.isfinite(selected[EXTENDED]).all().all())
        self.assertEqual(info["invalid_by_feature"]["heap_used_ratio"], 1)
        self.assertEqual(info["excluded_rows"][0]["reasons"]["gc_count_delta"], "first_row_of_session_or_file")

    def test_json_and_reproducibility(self):
        report = compare([self.train], self.test)
        self.assertEqual(report, compare([self.train], self.test))
        self.assertEqual(json.loads(json.dumps(report, allow_nan=False)), report)
        self.assertEqual(report["selection"]["evaluation"]["used"], 22)
        counts = report["comparison"]
        self.assertEqual(sum(counts[k] for k in ["both", "baseline_only", "extended_only", "neither"]), 22)
        self.assertEqual(len(counts["disagreements"]), counts["baseline_only"] + counts["extended_only"])

    def test_no_complete_rows_reports_exclusions(self):
        df = pd.read_csv(self.test)
        df["gc_collection_count"] = -1
        df.to_csv(self.test, index=False)
        report = compare([self.train], self.test)
        self.assertEqual(report["status"], "insufficient_complete_rows")
        self.assertEqual(report["selection"]["evaluation"]["excluded"], 24)
        self.assertEqual(report["models"], {})

    def test_timezone_and_interval_counts(self):
        path = self.folder / "events.json"
        path.write_text(json.dumps([dict(name="Nether", start="2026-11-01T05:00:00+05:00",
                                         end="2026-11-01T05:01:00+05:00")]), encoding="utf-8")
        report = compare([self.train], self.test, load_events(path))
        self.assertEqual(report["intervals"][0]["total_rows"], 7)
        self.assertEqual(report["intervals"][0]["used_rows"], 6)
        path.write_text('[{"name":"bad","start":"2026-11-01","end":"2026-11-02"}]', encoding="utf-8")
        with self.assertRaises(ValueError):
            load_events(path)

    def test_reject_evaluation_as_training(self):
        with self.assertRaises(ValueError):
            compare([self.test], self.test)


if __name__ == "__main__":
    unittest.main()
