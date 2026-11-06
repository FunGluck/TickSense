"""Public artifact checks require no private/local CSV files."""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from scripts.generate_demo import verify_input
from analysis.html_report import ASSETS

ROOT = Path(__file__).resolve().parents[1]


class PublicDemoTest(unittest.TestCase):
    def test_public_demo_current_and_safe(self):
        html=(ROOT/'site/pilot-dragon.html').read_text(encoding='utf8')
        payload=json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>',html,re.S)[1])
        self.assertEqual(len(payload['points']),872)
        self.assertEqual(sum(p['ml_anomaly'] is True for p in payload['points']),1)
        self.assertEqual(sum(p['stat_anomaly'] is True for p in payload['points']),44)
        self.assertEqual(len(payload['event_insights']['ml_episodes']),1)
        self.assertEqual(payload['performance_health']['state'],'GREEN')
        self.assertEqual({p['source_file'] for p in payload['points']},{'Dragon Run.csv'})
        self.assertEqual(payload['full_period']['scope'],'evaluation_only')
        # Generator assets, not an independently maintained demo Dashboard.
        for name in ['dashboard.js','style.css']:
            self.assertIn((ASSETS/name).read_text(encoding='utf8'),html)
        self.assertNotIn('energy-core',html)
        self.assertNotIn('core-arrival',html)
        self.assertNotRegex(html,r'(?i)(?:[a-z]:\\|https?://|<script[^>]+src=|@import)')
        self.assertIn('var(--health-glow)',html)
        self.assertIn('href="pilot-dragon.html"',(ROOT/'site/index.html').read_text(encoding='utf8'))

    def test_demo_rejects_missing_or_replaced_data(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'input.csv'
            with self.assertRaises(ValueError):verify_input(p,'unused')
            p.write_bytes(b'original')
            digest=hashlib.sha256(b'original').hexdigest()
            verify_input(p,digest)
            p.write_bytes(b'replacement')
            with self.assertRaises(ValueError):verify_input(p,digest)
