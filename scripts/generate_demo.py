"""Regenerate the public Dragon Run demo using its verified original CSV inputs.

No downloads, no alternate data discovery, no deployment. Run with the analysis venv.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    'metrics-v2-2026-11-01.csv': 'f0e7a79e84a03cf83b779c5ed97f542aeed722d5284ad85d146364a170e78510',
    'Dragon Run.csv': '1664341aa0e065c09e65affc10e715cc47f7f4e0784d782e0d8159c6e7b93267',
}


def verify_input(path, expected):
    if not path.is_file():
        raise ValueError(f'Missing approved demo input: {path.name}. Restore the original locally; do not substitute Pilot data.')
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f'Demo input checksum mismatch: {path.name}. No report generated.')


def main():
    for name, expected in INPUTS.items():
        verify_input(ROOT / 'datasets' / name, expected)
    with tempfile.TemporaryDirectory(prefix='ticksense-demo-') as temp:
        report = Path(temp) / 'report.json'
        subprocess.run([sys.executable, '-m', 'analysis.analyze',
                        str(ROOT / 'datasets' / 'metrics-v2-2026-11-01.csv'),
                        str(ROOT / 'datasets' / 'Dragon Run.csv'),
                        '--html', str(ROOT / 'site' / 'pilot-dragon.html'),
                        '--json', str(report), '--no-show'], cwd=ROOT, check=True,
                       stdout=subprocess.DEVNULL)
        result = json.loads(report.read_text(encoding='utf8'))
        print(json.dumps(dict(output='site/pilot-dragon.html', measurements=result['measurements'],
                              ml=result['ml_anomalies'], statistical=result['stat_anomalies'],
                              ml_periods=len(result['event_insights']['ml_episodes']),
                              health=result['performance_health']['state']), ensure_ascii=False))


if __name__ == '__main__':
    main()
