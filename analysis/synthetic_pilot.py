"""Deterministic synthetic fixtures, NOT real Pilot training data."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd


def generate():
    rng = np.random.default_rng(42)
    n = 8640
    seconds = np.arange(n) * 10
    seconds[5000:] += 120
    elapsed = seconds * 1000
    elapsed[6000:] -= elapsed[6000]
    mspt = np.maximum(0, rng.normal(4, 0.5, n))
    mspt[3500:3504] = 118.33
    return pd.DataFrame(dict(
        timestamp_utc=pd.Timestamp('2026-11-05T12:00:00Z') + pd.to_timedelta(seconds, unit='s'),
        elapsed_ms=elapsed, tps_1m=np.where(mspt > 50, 17.36, 20), mspt_avg=mspt,
        players_online=np.where((seconds > 10000) & (seconds < 70000), 5, 0),
        jvm_heap_used_bytes=200000000 + rng.integers(0, 1000000, n),
        loaded_chunks=300 + (seconds > 20000).astype(int)*50,
        entities_total=100 + (seconds > 30000).astype(int)*30,
        block_entities_total=np.full(n, 40), jvm_heap_committed_bytes=np.full(n, 500000000),
        gc_collection_count=np.arange(n)//20, gc_collection_time_ms=np.arange(n)//20*5))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    df = generate()
    for day, rows in df.groupby(df.timestamp_utc.dt.date):
        path = args.directory / f'synthetic-v2-{day}.csv'
        if path.exists():
            raise FileExistsError(path)
        rows.to_csv(path, index=False)
