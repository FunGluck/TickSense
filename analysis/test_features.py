"""Feature semantics on small synthetic session histories."""
import unittest
import numpy as np
import pandas as pd
from analysis.features import engineer_features

FEATURES = ["gc_count_delta", "gc_time_delta_ms", "loaded_chunks_delta",
            "entities_delta", "heap_used_ratio"]


class FeaturesTest(unittest.TestCase):
    def test_correct_deltas_and_ratio(self):
        df = pd.DataFrame({"session_id": [1, 1, 1],
                           "gc_collection_count": [2, 4, 4],
                           "gc_collection_time_ms": [10, 15, 18],
                           "loaded_chunks": [100, 90, 110],
                           "entities_total": [40, 50, 35],
                           "jvm_heap_used_bytes": [20, 40, 80],
                           "jvm_heap_committed_bytes": [100, 100, 100]})
        result = engineer_features(df)
        for name, expected in [("gc_count_delta", [np.nan, 2, 0]),
                               ("gc_time_delta_ms", [np.nan, 5, 3]),
                               ("loaded_chunks_delta", [np.nan, -10, 20]),
                               ("entities_delta", [np.nan, 10, -15]),
                               ("heap_used_ratio", [0.2, 0.4, 0.8])]:
            np.testing.assert_allclose(result[name], expected, equal_nan=True)

    def test_session_boundaries(self):
        df = pd.DataFrame({"session_id": [1, 1, 2, 2]})
        for source in ["gc_collection_count", "gc_collection_time_ms", "loaded_chunks", "entities_total"]:
            df[source] = [100, 101, 10, 12]
        result = engineer_features(df)
        for feature in FEATURES[:4]:
            np.testing.assert_allclose(result[feature], [np.nan, 1, np.nan, 2], equal_nan=True)

    def test_unavailable_gc_and_recovery(self):
        for source, feature in [("gc_collection_count", "gc_count_delta"),
                                ("gc_collection_time_ms", "gc_time_delta_ms")]:
            df = pd.DataFrame({"session_id": [1] * 6, source: [10, -1, 20, 22, -1, -1]})
            np.testing.assert_allclose(engineer_features(df)[feature],
                                       [np.nan, np.nan, np.nan, 2, np.nan, np.nan], equal_nan=True)

    def test_gc_reset_is_unknown_then_resumes(self):
        df = pd.DataFrame({"session_id": [1] * 4, "gc_collection_count": [10, 12, 1, 3],
                           "gc_collection_time_ms": [20, 30, 0, 5]})
        result = engineer_features(df)
        np.testing.assert_allclose(result.gc_count_delta, [np.nan, 2, np.nan, 2], equal_nan=True)
        np.testing.assert_allclose(result.gc_time_delta_ms, [np.nan, 10, np.nan, 5], equal_nan=True)

    def test_invalid_heap(self):
        df = pd.DataFrame({"session_id": [1] * 9,
                           "jvm_heap_used_bytes": [1, 1, 1, 1, 1, -1, np.inf, 101, 0],
                           "jvm_heap_committed_bytes": [0, -1, np.nan, np.inf, "bad", 100, 100, 100, 100]})
        result = engineer_features(df)
        self.assertTrue(result.heap_used_ratio.iloc[:8].isna().all())
        self.assertEqual(result.heap_used_ratio.iloc[8], 0)

    def test_old_schema_and_partial_columns(self):
        df = pd.DataFrame({"session_id": [1, 1], "jvm_heap_used_bytes": [10, 20]})
        result = engineer_features(df)
        self.assertTrue(result[FEATURES].isna().all().all())
        df["loaded_chunks"] = [10, 11]
        result = engineer_features(df)
        self.assertEqual(result.loaded_chunks_delta.iloc[1], 1)
        self.assertTrue(result.gc_count_delta.isna().all())

    def test_input_unchanged_and_index_preserved(self):
        df = pd.DataFrame({"session_id": [1, 1], "gc_collection_count": [0, 2]}, index=[7, 3])
        original = df.copy(deep=True)
        result = engineer_features(df)
        pd.testing.assert_frame_equal(df, original)
        self.assertIsNot(result, df)
        self.assertEqual(result.index.tolist(), [7, 3])

    def test_future_rows_do_not_change_previous_features(self):
        df = pd.DataFrame({"session_id": [1, 1, 1], "gc_collection_count": [2, 3, 1000],
                           "loaded_chunks": [10, 11, 0]})
        pd.testing.assert_frame_equal(engineer_features(df).iloc[:2], engineer_features(df.iloc[:2]))


if __name__ == "__main__":
    unittest.main()
