"""Detector agreement and JSON-compatible evaluation summary."""
import json
import pandas as pd

if __package__:
    from .performance_events import detect_performance_events
    from .explanations import add_explanations
else:
    from performance_events import detect_performance_events
    from explanations import add_explanations


def compare_detectors(df: pd.DataFrame) -> dict:
    stat, ml = df["stat_anomaly"], df["ml_anomaly"]
    known = ml.notna()
    ml = ml.eq(True).fillna(False)
    return {
        "stat_anomalies": int(stat.sum()), "ml_anomalies": int(ml.sum()),
        "both": int((stat & ml).sum()), "only_stat": int((stat & known & ~ml).sum()),
        "only_ml": int((~stat & ml).sum()), "neither": int((~stat & known & ~ml).sum()),
    }


def build_report(df: pd.DataFrame, *, performance_event_options: dict | None = None) -> dict:
    columns = ["timestamp_utc", "elapsed_ms", "session_id", "mspt_avg", "players_online",
               "tps_1m", "anomaly_score", "stat_anomaly", "ml_anomaly"]
    top = df.dropna(subset=["anomaly_score"]).nsmallest(10, "anomaly_score")[columns]
    return {
        "measurements": len(df), "sessions": int(df["session_id"].nunique()),
        "mspt_avg_mean": None if df.mspt_avg.isna().all() else float(df.mspt_avg.mean()),
        "mspt_avg_max": None if df.mspt_avg.isna().all() else float(df.mspt_avg.max()),
        "stat_evaluable_measurements": int(df["rolling_threshold"].notna().sum()),
        **compare_detectors(df),
        "top_10_lowest_scores": json.loads(top.to_json(orient="records", date_format="iso", double_precision=15)),
        "performance_events": add_explanations(df, detect_performance_events(df, **(performance_event_options or {}))),
    }
