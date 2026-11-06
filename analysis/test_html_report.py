from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd
from analysis.data import load_data
from analysis.features import engineer_features
from analysis.statistical import detect_statistical
from analysis.report import build_report
from analysis.html_report import prepare_html_data, render_html, write_html_report, ASSETS


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.external = []
        self.scripts = 0
    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.scripts += 1
        for key, value in attrs:
            if key in ("src", "href") and value and not value.startswith("#"):
                self.external.append(value)


class HtmlReportTest(unittest.TestCase):
    def assert_body_typography(self, css):
        """Check the font shorthand values used by this stylesheet, not spacing."""
        css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
        bodies = re.findall(r'\bbody\s*\{([^}]+)\}', css, flags=re.I)
        fonts = [font for body in bodies for font in re.findall(r'(?:^|;)\s*font\s*:\s*([^;]+)', body, flags=re.I)]
        self.assertTrue(fonts, 'body must define its font')
        match = re.fullmatch(r'\s*(\d+(?:\.\d+)?)px\s*/\s*(\d+(?:\.\d+)?)\s+(.+?)\s*', fonts[-1])
        self.assertIsNotNone(match, 'Expected font size / unitless line-height and family stack')
        self.assertEqual(float(match[1]), 16)
        self.assertEqual(float(match[2]), 1.65)
        families = [part.strip().strip('\"\'').casefold() for part in match[3].split(',')]
        self.assertEqual(families, ['inter', 'segoe ui', 'arial', 'sans-serif'])

    def frame(self, folder, v2=False, event=True):
        frame = pd.DataFrame({"timestamp_utc": pd.date_range("2026-11-01", periods=8, freq="10s", tz="UTC"),
                              "elapsed_ms": list(range(4)) * 2, "mspt_avg": [1, 60 if event else 1] + [2] * 6,
                              "tps_1m": 20, "players_online": 1})
        if v2:
            frame["loaded_chunks"] = range(8)
            frame["entities_total"] = range(8)
            frame["gc_collection_count"] = range(8)
            frame["gc_collection_time_ms"] = range(8)
            frame["jvm_heap_used_bytes"] = 50
            frame["jvm_heap_committed_bytes"] = 100
        path = Path(folder) / "input.csv"
        frame.to_csv(path, index=False)
        result = detect_statistical(engineer_features(load_data(path)))
        result["anomaly_score"] = 0.1
        result["ml_anomaly"] = False
        return result

    def test_v1_v2_html_and_json_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            for v2 in (False, True):
                frame = self.frame(folder, v2)
                report = build_report(frame)
                original = deepcopy(report)
                original_frame = frame.copy(deep=True)
                path = Path(folder) / "nested/report.html"
                write_html_report(frame, report, path)
                html = path.read_text(encoding="utf-8")
                self.assertIn('<html lang="ru">', html)
                for label in ("Итог наблюдения", "Периоды повышенной нагрузки", "Необычные изменения", "Сессии сервера", "Средний MSPT", "Максимальный MSPT", "Минимальный TPS"):
                    self.assertIn(label, html)
                self.assertNotIn(str(Path(folder).resolve()), html)
                self.assertEqual(report, original)
                pd.testing.assert_frame_equal(frame, original_frame)

    def test_no_events_and_nan(self):
        with tempfile.TemporaryDirectory() as folder:
            frame = self.frame(folder, event=False)
            frame["anomaly_score"] = np.nan
            payload = prepare_html_data(frame, build_report(frame))
            self.assertEqual(payload["events"], [])
            self.assertIsNone(payload["points"][0]["rolling_threshold"])
            self.assertIsNone(payload["points"][0]["anomaly_score"])
            html = render_html(payload)
            self.assertIn("Событий не обнаружено", html)
            self.assertNotIn(": NaN", html)

    def test_untrusted_text_and_json_are_data(self):
        attack = '</script><img src="https://bad.invalid" onerror="alert(1)">&\u2028'
        html = render_html({"points": [], "events": [], "test": attack})
        parser = Tags()
        parser.feed(html)
        self.assertEqual(parser.scripts, 2)
        self.assertEqual(parser.external, [])
        embedded = re.search(r'<script id="report-data" type="application/json">(.*?)</script>', html, re.S)[1]
        self.assertEqual(json.loads(embedded)["test"], attack)
        self.assertNotIn('<img', html)
        self.assertIn('\\u003c/script', html)
        js = (ASSETS / "dashboard.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("eval(", js)
        self.assertIn("textContent", js)

    def test_offline_and_russian_presentation(self):
        html = render_html({"points": [], "events": []})
        parser = Tags(); parser.feed(html)
        self.assertEqual(parser.external, [])
        for forbidden in ("fetch(", "XMLHttpRequest", "https://", "http://", "@import", "WebSocket", "url("):
            self.assertNotIn(forbidden, html)
        self.assertIn("'ru-RU'", html)
        self.assertIn("['измерение','измерения','измерений']", html)
        self.assertIn("timeZone:'UTC'", html)
        for english in ("Overview", "No events detected", "Measurements", "Minimum TPS", "Performance Events", "Rolling threshold", "committed heap"):
            self.assertNotIn(english, html)
        for identifier in ("gc_time_delta_ms", "loaded_chunks_delta", "high_mspt"):
            self.assertRegex(html, identifier + r":'[^']*[А-Яа-я]")

    def test_cli_existing_options_and_json_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            self.frame(folder, v2=True)
            csv = Path(folder) / "input.csv"
            base = [sys.executable, "-m", "analysis.analyze", str(csv), str(csv), "--no-show"]
            old = Path(folder) / "old.json"; new = Path(folder) / "new.json"
            subprocess.run(base + ["--json", str(old)], check=True, capture_output=True)
            html = Path(folder) / "report.html"; png = Path(folder) / "report.png"
            subprocess.run(base + ["--json", str(new), "--html", str(html), "--png", str(png)], check=True, capture_output=True)
            self.assertEqual(old.read_bytes(), new.read_bytes())
            self.assertTrue(html.is_file()); self.assertTrue(png.is_file())

    @unittest.skipUnless(shutil.which("node"), "Node.js is optional for JavaScript logic tests")
    def test_javascript_interactions_and_localization(self):
        subprocess.run(["node", str(ASSETS / "test_dashboard.cjs")], check=True, capture_output=True)

    def test_administrator_structure_and_closed_diagnostics(self):
        template = (ASSETS / 'template.html').read_text(encoding='utf8')
        order = ['overview', 'charts', 'events', 'ml', 'quality', 'technical']
        positions = [template.index('id="' + section + '"') for section in order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('<details id="technical"><summary>Подробности анализа</summary>', template)
        self.assertNotIn('<details id="technical" open', template)
        before_charts = template[:template.index('<section id="charts">')]
        for term in ['TRAIN', 'TEST', 'Isolation Forest', 'elapsed_ms', 'эвристик', 'стандартных отклонений']:
            self.assertNotIn(term, before_charts)
        for identifier in ['quality-content', 'training-coverage', 'ml-technical', 'event-technical']:
            self.assertGreater(template.index('id="'+identifier+'"'), positions[-1])
        self.assertRegex(template, r'<input id="show-ml" type="checkbox">')
        self.assertIn('Как пользоваться графиком', template)

    def test_health_uses_original_ambient_light_without_core(self):
        css=(ASSETS/'style.css').read_text(encoding='utf8')
        template=(ASSETS/'template.html').read_text(encoding='utf8')
        for state in ['GREEN','YELLOW','RED']:
            self.assertIn('data-health="'+state+'"',css)
        self.assertIn('radial-gradient(ellipse at 85% 0, var(--health-glow) 0, transparent 40%)',css)
        self.assertIn('--health-glow:#18342f',css)
        for removed in ['energy-core','core-arrival','@keyframes','perspective(']:
            self.assertNotIn(removed,css+template)

    def test_navigator_and_typography(self):
        html = render_html({"points": [], "events": []})
        self.assertNotIn('id="from"', html)
        self.assertNotIn('id="to"', html)
        self.assertNotIn('type="range"', html)
        self.assertIn('id="navigator"', html)
        self.assertIn('id="nav-left"', html)
        self.assertIn('id="nav-pan"', html)
        self.assertIn('id="nav-right"', html)
        self.assertIn("setPointerCapture", html)
        self.assertIn("pointercancel", html)
        self.assertIn("lostpointercapture", html)
        self.assertIn("tabular-nums", html)
        self.assert_body_typography((ASSETS / 'style.css').read_text(encoding='utf-8'))
        self.assertIn('13px Inter, "Segoe UI", Arial, sans-serif', html)
        self.assertNotIn('11px system-ui', html)

    def test_typography_semantics_accept_spacing_and_reject_wrong_values(self):
        for declaration in ('16px/1.65 Inter,"Segoe UI",Arial,sans-serif',
                            '16px / 1.65 Inter, "Segoe UI", Arial, sans-serif'):
            self.assert_body_typography('body { font: ' + declaration + '; }')
        for declaration in ('14px/1.65 Inter,"Segoe UI",Arial,sans-serif',
                            '16px/1.2 Inter,"Segoe UI",Arial,sans-serif',
                            '16px/1.65 monospace'):
            with self.subTest(font=declaration), self.assertRaises(AssertionError):
                self.assert_body_typography('body { font: ' + declaration + '; }')


if __name__ == "__main__":
    unittest.main()
