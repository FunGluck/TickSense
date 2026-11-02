"""Load CSV without reordering measurements; identify elapsed-time resets."""
from pathlib import Path
import numpy as np
import pandas as pd

REQUIRED = ["timestamp_utc", "elapsed_ms", "mspt_avg", "players_online", "tps_1m"]


def load_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    missing = set(REQUIRED) - set(df.columns)
    if missing:
        raise ValueError(f"{csv_path}: missing columns: {', '.join(sorted(missing))}")

    if df.empty:
        raise ValueError(f"{csv_path}: CSV contains no measurements")

    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, format="ISO8601")
    if df["timestamp_utc"].isna().any():
        raise ValueError(f"{csv_path}: missing timestamps")

    for column in REQUIRED[1:]:
        df[column] = pd.to_numeric(df[column], errors="raise")
        if not np.isfinite(df[column].to_numpy(dtype=float)).all():
            raise ValueError(f"{csv_path}: {column} contains missing or non-finite values")

    df["session_id"] = (df["elapsed_ms"].diff() < 0).cumsum() + 1
    previous = df.groupby("session_id")["players_online"].shift(1)
    df["online_changed"] = previous.notna() & df["players_online"].ne(previous)
    df["source_file"] = str(csv_path.resolve())
    df["csv_row"] = np.arange(len(df)) + 2

    return df
