"""Causal rolling MSPT detector with independent session windows."""
import pandas as pd

WINDOW = 6


def detect_statistical(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    grouped = df.groupby("session_id")["mspt_avg"]
    df["rolling_mean"] = grouped.transform(lambda s: s.shift(1).rolling(WINDOW).mean())
    df["rolling_std"] = grouped.transform(lambda s: s.shift(1).rolling(WINDOW).std())
    df["rolling_threshold"] = df["rolling_mean"] + 3 * df["rolling_std"]
    df["excess_mspt"] = df["mspt_avg"] - df["rolling_threshold"]
    df["stat_anomaly"] = df["excess_mspt"] > 0
    return df
