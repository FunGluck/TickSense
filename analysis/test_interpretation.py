"""Interpretation does not change detector results or training."""
import unittest
import pandas as pd
from analysis.interpretation import interpret_results
from analysis.isolation import train_model, FEATURES


class InterpretationTest(unittest.TestCase):
    def frame(self):
        return pd.DataFrame(dict(players_online=[0, 1, 1, 0], mspt_avg=[1, 2, 3, 1],
                                 tps_1m=[20]*4, anomaly_score=[-.1, .1, -.2, None],
                                 ml_anomaly=[True, False, True, True],
                                 stat_anomaly=[True, True, False, False],
                                 rolling_threshold=[None, 1, 2, 2]))

    def test_counts_denominators_union_and_immutable(self):
        df = self.frame(); original = df.copy(deep=True)
        r = interpret_results(df, df, [])
        pd.testing.assert_frame_equal(df, original)
        self.assertEqual(r['ml'], dict(count=2, evaluated=3, percent=200/3))
        self.assertEqual(r['statistical'], dict(count=1, evaluated=3, percent=100/3))
        self.assertEqual(r['unique'], 3); self.assertEqual(r['both'], 0)
        df.loc[0, 'rolling_threshold'] = 0
        self.assertEqual(interpret_results(df, df, [])['both'], 1)
        pd.testing.assert_frame_equal(original, self.frame())
        self.assertIn('не обнаружено', r['conclusion'])
        self.assertIn('Обнаружено', interpret_results(df, df, [{}])['conclusion'])

    def test_empty_missing_and_partial_predictions(self):
        empty = pd.DataFrame()
        r = interpret_results(empty, empty, [])
        self.assertIsNone(r['ml']['percent']); self.assertEqual(r['coverage_warnings'], [])
        self.assertIn('измерений нет', r['conclusion'])
        df = self.frame().drop(columns=['ml_anomaly', 'anomaly_score'])
        self.assertIn('недоступны', interpret_results(empty, df, [])['conclusion'])
        self.assertIn('недостаточно', interpret_results(empty, self.frame(), [])['conclusion'])
        self.assertIn('части', interpret_results(self.frame(), self.frame(), [])['conclusion'])

    def test_coverage_boundary(self):
        test = self.frame()
        for count, warning in [(0, True), (4, True), (5, False), (50, False)]:
            train = pd.DataFrame({'players_online': [0]*count + [1]*(100-count)})
            r = interpret_results(train, test, [])
            self.assertEqual(bool(r['coverage_warnings']), warning)
            self.assertEqual(r['coverage'][0]['train']['count'], count)
            self.assertEqual(r['coverage'][0]['test']['count'], 2)
            self.assertEqual(r['coverage'][0]['test_ml']['count'], 1)
        # No warning for a weak TRAIN regime that is absent from TEST.
        r = interpret_results(pd.DataFrame({'players_online':[1]*100}), test.iloc[1:3], [])
        self.assertFalse(r['coverage_warnings'])

    def test_model_parameters_unchanged(self):
        model = train_model(self.frame())
        self.assertEqual(FEATURES, ['mspt_avg','players_online','tps_1m'])
        self.assertEqual([model.n_estimators, model.contamination, model.random_state], [100, .05, 42])
