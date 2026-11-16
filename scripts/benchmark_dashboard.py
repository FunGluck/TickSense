"""Repeatable dashboard format and rendering benchmark with synthetic data."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import tracemalloc

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def fixture(size):
    rng = np.random.default_rng(42)
    index = np.arange(size)
    gaps = (index // 7000) * 180
    timestamps = pd.Timestamp('2026-01-01T00:00:00Z') + pd.to_timedelta(index * 10 + gaps, unit='s')
    spike = index % 997 == 151
    low = index % 1901 < 16
    return pd.DataFrame(dict(timestamp_utc=timestamps, session_id=index // 25000 + 1,
                             source_file=timestamps.strftime('%Y-%m-%d.csv'), csv_row=index + 2,
                             players_online=index % 8, mspt_avg=np.where(spike,120.,5+rng.random(size)),
                             tps_1m=np.where(low,12.,20-rng.random(size)*.1),
                             stat_anomaly=spike, ml_anomaly=np.where(index<size*7//10,None,low|spike),
                             anomaly_score=np.where(index<size*7//10,np.nan,rng.normal(0,.1,size)),
                             rolling_threshold=np.where(index%25000<6,np.nan,10.), excess_mspt=np.where(spike,110.,-4.)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'reports/dashboard-benchmark')
    parser.add_argument('--sizes', type=int, nargs='+', default=[1000,10000,100000,150000])
    parser.add_argument('--source', type=Path, default=ROOT, help='TickSense checkout to measure')
    parser.add_argument('--memory', action='store_true', help='Track Python allocations (changes timing)')
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    from analysis.html_report import prepare_html_data, render_html
    from analysis.event_insights import build_insights, performance_health
    args.output.mkdir(parents=True,exist_ok=True)
    for size in args.sizes:
        df = fixture(size)
        # Analysis is outside the rendering stopwatch and identical in both versions.
        insights = build_insights(df)
        report = dict(event_insights=insights, performance_health=performance_health(df),
                      full_period=dict(performance_events=dict(episodes=insights['display_performance_events']),
                                       ml_boundary=None))
        if args.memory:
            tracemalloc.start()
        start = time.perf_counter()
        data = prepare_html_data(df,report)
        prepared = time.perf_counter()
        html = render_html(data)
        rendered = time.perf_counter()
        path = args.output/f'{size}.html'
        path.write_text(html,encoding='utf8')
        written = time.perf_counter()
        peak = tracemalloc.get_traced_memory()[1] if args.memory else None
        if args.memory:
            tracemalloc.stop()
        print(json.dumps(dict(rows=size,peak_python_bytes=peak,bytes=path.stat().st_size,prepare_s=prepared-start,
                              serialize_s=rendered-prepared,write_s=written-rendered)),flush=True)
        subprocess.run(['node',str(ROOT/'scripts/benchmark_dashboard.cjs'),str(path)],check=True)


if __name__ == '__main__':
    main()
