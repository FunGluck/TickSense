"""Causal derived metrics in original row order, with unknown values as NaN."""
import numpy as np
import pandas as pd


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with five features; require session_id from the loader.

    Missing source columns yield NaN features, never synthetic zeros. GC
    counters must be available at both ends of an interval and nondecreasing.
    Chunk/entity differences are signed because unloading/removal is normal.
    """
    if "session_id" not in df.columns:
        raise ValueError("Feature engineering requires session_id")
    result = df.copy(deep=True)
    for source, feature, cumulative in [
        ("gc_collection_count", "gc_count_delta", True),
        ("gc_collection_time_ms", "gc_time_delta_ms", True),
        ("loaded_chunks", "loaded_chunks_delta", False),
        ("entities_total", "entities_delta", False),
    ]:
        result[feature] = np.nan
        if source not in df.columns:
            continue
        values = pd.to_numeric(df[source], errors="coerce").astype(float)
        values = values.where(np.isfinite(values) & values.ge(0))
        delta = values.groupby(df["session_id"], sort=False).diff()
        result[feature] = delta.where(delta.ge(0)) if cumulative else delta

    result["heap_used_ratio"] = np.nan
    if {"jvm_heap_used_bytes", "jvm_heap_committed_bytes"}.issubset(df.columns):
        used = pd.to_numeric(df["jvm_heap_used_bytes"], errors="coerce").astype(float)
        committed = pd.to_numeric(df["jvm_heap_committed_bytes"], errors="coerce").astype(float)
        valid = (np.isfinite(used) & used.ge(0) & np.isfinite(committed)
                 & committed.gt(0) & used.le(committed))
        result["heap_used_ratio"] = used.where(valid) / committed.where(valid)
    return result
