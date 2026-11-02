"""Threshold observations, independent of ML and statistical anomaly labels."""
import math
import pandas as pd


def detect_performance_events(df: pd.DataFrame, *, high_mspt: float = 50,
                              low_tps: float = 19, elevated_mspt: float = 25,
                              max_gap_seconds: float = 30) -> dict:
    """Group consecutive matching rows; span is NOT the duration of a lag.

    Original row order is preserved. Invalid rows break every signal. Backward
    timestamps, file/session changes and gaps exceeding max_gap_seconds split
    episodes. Source CSV record numbers include the header (first record = 2).
    """
    settings = dict(high_mspt=high_mspt, low_tps=low_tps,
                    elevated_mspt=elevated_mspt, max_gap_seconds=max_gap_seconds)
    if any(not math.isfinite(value) or value < 0 for value in settings.values()):
        raise ValueError("Performance event thresholds and gap must be finite and nonnegative")
    required = {"timestamp_utc", "session_id", "mspt_avg", "tps_1m"}
    if not required.issubset(df.columns):
        raise ValueError("Performance events require: " + ", ".join(sorted(required)))
    times = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce", format="mixed")
    mspt = pd.to_numeric(df["mspt_avg"], errors="coerce")
    tps = pd.to_numeric(df["tps_1m"], errors="coerce")
    episodes = []
    active = {}
    invalid_rows = 0
    previous = None
    for position in range(len(df)):
        row = df.iloc[position]
        time, m, t, session = times.iloc[position], mspt.iloc[position], tps.iloc[position], row["session_id"]
        valid = (not pd.isna(time) and not pd.isna(session) and pd.notna(m) and pd.notna(t)
                 and math.isfinite(m) and math.isfinite(t) and m >= 0 and t >= 0)
        if not valid:
            active.clear()
            previous = None
            invalid_rows += 1
            continue
        source = row.get("source_file", None)
        if pd.isna(source):
            source = None
        session = session.item() if hasattr(session, "item") else session
        csv_row = row.get("csv_row", position + 2)
        csv_row = int(csv_row) if pd.notna(csv_row) else position + 2
        if previous is not None:
            last_time, last_session, last_source = previous
            gap = (time - last_time).total_seconds()
            if session != last_session or source != last_source or gap < 0 or gap > max_gap_seconds:
                active.clear()
        previous = (time, session, source)
        signals = {"high_mspt": m > high_mspt, "low_tps": t < low_tps,
                   "elevated_mspt": m > elevated_mspt}
        for signal, matches in signals.items():
            if not matches:
                active.pop(signal, None)
                continue
            if signal not in active:
                episode = dict(signal=signal, session_id=session, source_file=source,
                               start_utc=time.isoformat(), last_observed_utc=time.isoformat(),
                               measurements=0, peak_mspt=float(m), min_tps=float(t),
                               source_rows=[], single_observation=True, observed_span_seconds=None)
                episodes.append(episode)
                active[signal] = (episode, time)
            episode, start = active[signal]
            episode["last_observed_utc"] = time.isoformat()
            episode["measurements"] += 1
            episode["peak_mspt"] = max(episode["peak_mspt"], float(m))
            episode["min_tps"] = min(episode["min_tps"], float(t))
            episode["source_rows"].append(csv_row)
            episode["single_observation"] = episode["measurements"] == 1
            if not episode["single_observation"]:
                episode["observed_span_seconds"] = (time - start).total_seconds()
    return {
        "thresholds": settings,
        "episode_counts": {signal: sum(e["signal"] == signal for e in episodes)
                           for signal in ("high_mspt", "low_tps", "elevated_mspt")},
        "invalid_rows": invalid_rows,
        "episodes": episodes,
        "note": "Threshold observations, not proof of impaired gameplay. Span is not exact lag duration; signals overlap independently.",
    }
