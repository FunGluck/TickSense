"""Load CSV without reordering measurements; identify elapsed-time resets."""
import csv
from pathlib import Path
import numpy as np
import pandas as pd

REQUIRED = ["timestamp_utc", "elapsed_ms", "mspt_avg", "players_online", "tps_1m"]


def load_data(csv_path: Path) -> pd.DataFrame:
    with open(csv_path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader, [])
        if not header or len(set(header)) != len(header):
            raise ValueError(f"{csv_path}: empty or duplicate header")
        for number, row in enumerate(reader, 2):
            if len(row) != len(header) or row == header:
                raise ValueError(f"{csv_path}: malformed CSV record {number}")
    df = pd.read_csv(csv_path)
    missing = set(REQUIRED) - set(df.columns)
    if missing:
        raise ValueError(f"{csv_path}: missing columns: {', '.join(sorted(missing))}")

    if df.empty:
        raise ValueError(f"{csv_path}: CSV contains no measurements")

    if not df["timestamp_utc"].astype(str).str.contains(r"(?:Z|[+-]00:00)$", regex=True).all():
        raise ValueError(f"{csv_path}: timestamps must explicitly specify UTC")
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, format="ISO8601")
    if df["timestamp_utc"].isna().any():
        raise ValueError(f"{csv_path}: missing timestamps")

    for column in REQUIRED[1:]:
        df[column] = pd.to_numeric(df[column], errors="raise")
        if not np.isfinite(df[column].to_numpy(dtype=float)).all():
            raise ValueError(f"{csv_path}: {column} contains missing or non-finite values")

    if (df[REQUIRED[1:]] < 0).any().any():
        raise ValueError(f"{csv_path}: negative metric values")
    for column in set(df.columns) - {"timestamp_utc"}:
        if column in {"jvm_heap_used_bytes", "loaded_chunks", "entities_total", "block_entities_total",
                      "jvm_heap_committed_bytes", "gc_collection_count", "gc_collection_time_ms"}:
            df[column] = pd.to_numeric(df[column], errors="raise")
            minimum = -1 if column.startswith("gc_collection_") else 0
            if not np.isfinite(df[column]).all() or (df[column] < minimum).any():
                raise ValueError(f"{csv_path}: invalid {column}")
    counts = [c for c in df if c not in {"timestamp_utc", "mspt_avg", "tps_1m"}]
    if any((df[c] % 1 != 0).any() for c in counts):
        raise ValueError(f"{csv_path}: fractional counter")
    if (df["timestamp_utc"].diff().dt.total_seconds() < 0).any():
        raise ValueError(f"{csv_path}: timestamps are out of order; data not sorted automatically")
    df["session_id"] = (df["elapsed_ms"].diff() < 0).cumsum() + 1
    previous = df.groupby("session_id")["players_online"].shift(1)
    df["online_changed"] = previous.notna() & df["players_online"].ne(previous)
    df["source_file"] = str(csv_path.resolve())
    df["csv_row"] = np.arange(len(df)) + 2

    return df
