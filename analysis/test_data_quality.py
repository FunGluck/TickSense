import json
from pathlib import Path
import tempfile
import unittest
import pandas as pd
from analysis.synthetic_pilot import generate
from analysis.data_quality import load_period, assess_quality, chronological_split
from analysis.features import engineer_features
from analysis.statistical import detect_statistical


class PilotQualityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def save(self, df, name='input.csv'):
        path = self.root / name
        df.to_csv(path, index=False)
        return path

    def test_daily_continuity_restart_gap(self):
        df = generate()
        paths = [self.save(g, str(day)+'.csv') for day, g in df.groupby(df.timestamp_utc.dt.date)]
        loaded = load_period(paths)
        self.assertEqual(len(loaded), 8640)
        q = assess_quality(loaded)
        self.assertEqual(q['sessions'], 2)
        self.assertEqual(q['long_gaps'], 1)
        self.assertEqual(q['source_csv_count'], 2)
        json.dumps(q, allow_nan=False)

    def test_invalid_inputs(self):
        df = generate().iloc[:10].copy()
        for column, value in [('mspt_avg', -2), ('players_online', 'bad'),
                              ('gc_collection_count', -2), ('timestamp_utc', 'not a date'),
                              ('entities_total', None)]:
            broken = df.astype(object).copy(); broken.loc[0, column] = value
            with self.subTest(column=column), self.assertRaises(ValueError):
                load_period([self.save(broken)])
        with self.assertRaises(ValueError):
            load_period([self.save(df.iloc[:0])])
        with self.assertRaises(ValueError):
            load_period([self.save(df.drop(columns='mspt_avg'))])

    def test_repeated_header_and_incomplete(self):
        path = self.save(generate().iloc[:10])
        original = path.read_text()
        for extra in [original.splitlines()[0], '2026-11-05T12:10:00Z,1']:
            path.write_text(original + extra + '\n')
            with self.assertRaises(ValueError):
                load_period([path])

    def test_overlap_order_and_duplicates(self):
        df = generate().iloc[:20]
        with self.assertRaises(ValueError):
            load_period([self.save(df, 'a.csv'), self.save(df, 'b.csv')])
        doubled = pd.concat([df.iloc[:1], df], ignore_index=True)
        q = assess_quality(load_period([self.save(doubled)]))
        self.assertEqual(q['duplicate_measurements'], 1)
        self.assertTrue(q['warnings'])

    def test_split_and_no_future_leakage(self):
        raw = load_period([self.save(generate().iloc[:100])])
        prepared = detect_statistical(engineer_features(raw))
        train, test, info = chronological_split(prepared)
        self.assertLess(train.timestamp_utc.max(), test.timestamp_utc.min())
        self.assertTrue(set(train.index).isdisjoint(test.index))
        changed = raw.copy(); changed.loc[70:, 'mspt_avg'] = 1000
        changed.loc[70:, 'loaded_chunks'] = 9000
        pd.testing.assert_frame_equal(prepared.iloc[:70], detect_statistical(engineer_features(changed)).iloc[:70])
        with self.assertRaises(ValueError):
            chronological_split(prepared.iloc[:3])

    def test_feature_session_boundaries(self):
        raw = load_period([self.save(generate())])
        features = engineer_features(raw)
        self.assertTrue(features.loc[6000, ['gc_count_delta', 'loaded_chunks_delta']].isna().all())

    def test_cli_html_json(self):
        import subprocess
        import sys
        df = generate().iloc[:100]
        a = self.save(df.iloc[:50], 'a.csv')
        b = self.save(df.iloc[50:], 'b.csv')
        for inputs in [['--pilot-files', str(a), str(b)], ['--pilot-files', str(a)], [str(a), str(b)]]:
            output, html = self.root/'out.json', self.root/'out.html'
            subprocess.run([sys.executable, '-m', 'analysis.analyze', *inputs,
                            '--no-show', '--json', str(output), '--html', str(html)],
                           check=True, capture_output=True)
            report = json.loads(output.read_text(encoding='utf8'))
            self.assertIn('data_quality', report)
            self.assertIn('performance_events', report)
            page = html.read_text(encoding='utf8')
            self.assertIn('Качество данных', page)
            self.assertIn('quality-content', page)
