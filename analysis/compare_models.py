"""Reproducible, complete-case comparison of two Isolation Forest feature sets."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest

if __package__:
    from .data import load_data
    from .features import engineer_features
    from .isolation import FEATURES
else:
    from data import load_data
    from features import engineer_features
    from isolation import FEATURES

BASE = list(FEATURES)
EXTENDED = BASE + ["loaded_chunks_delta", "entities_delta", "gc_count_delta",
                   "gc_time_delta_ms", "heap_used_ratio"]
PARAMETERS = dict(n_estimators=100, contamination=0.05, random_state=42)


def prepare_files(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        # Engineer BEFORE concatenation: each file has its own session history.
        frame = engineer_features(load_data(path))
        frame["source_file"] = str(path.resolve())
        frame["csv_row"] = np.arange(len(frame)) + 2  # header is line 1
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def complete_cases(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    invalid = ~np.isfinite(frame[EXTENDED].astype(float))
    excluded = invalid.any(axis=1)
    first = ~frame.duplicated(["source_file", "session_id"])
    sources = {"loaded_chunks_delta": "loaded_chunks", "entities_delta": "entities_total",
               "gc_count_delta": "gc_collection_count", "gc_time_delta_ms": "gc_collection_time_ms"}
    previous = frame.groupby(["source_file", "session_id"], sort=False).shift(1)
    details = []
    for index in frame.index[excluded]:
        reasons = {}
        for feature in invalid.columns[invalid.loc[index]]:
            if feature == "heap_used_ratio":
                reasons[feature] = "missing_or_invalid_heap_values"
            elif feature in sources:
                source = sources[feature]
                if source not in frame or pd.isna(frame.at[index, source]):
                    reasons[feature] = "missing_source_value"
                elif first.at[index]:
                    reasons[feature] = "first_row_of_session_or_file"
                else:
                    current_value = pd.to_numeric(pd.Series([frame.at[index, source]]), errors="coerce").iloc[0]
                    previous_value = pd.to_numeric(pd.Series([previous.at[index, source]]), errors="coerce").iloc[0]
                    if not np.isfinite(current_value) or not np.isfinite(previous_value) or min(current_value, previous_value) < 0:
                        reasons[feature] = "unavailable_or_invalid_interval_endpoint"
                    else:
                        reasons[feature] = "cumulative_counter_decreased"
            else:
                reasons[feature] = "missing_or_nonfinite_value"
        details.append({"source_file": frame.at[index, "source_file"],
                        "csv_row": int(frame.at[index, "csv_row"]),
                        "invalid_features": invalid.columns[invalid.loc[index]].tolist(),
                        "reasons": reasons})
    return frame.loc[~excluded].copy(), {
        "total": len(frame), "used": int((~excluded).sum()), "excluded": int(excluded.sum()),
        "invalid_by_feature": {name: int(invalid[name].sum()) for name in EXTENDED},
        "excluded_rows": details,
    }


def load_events(path: Path | None) -> list[dict]:
    if path is None:
        return []
    events = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise ValueError("Events JSON must be a list")
    result = []
    for event in events:
        if not isinstance(event, dict) or not all(key in event for key in ("name", "start", "end")):
            raise ValueError("Each event requires name, start and end")
        if not isinstance(event["name"], str):
            raise ValueError("Event name must be a string")
        bounds = []
        for key in ("start", "end"):
            if not isinstance(event[key], str):
                raise ValueError("Event timestamps must be ISO 8601 strings with timezone")
            timestamp = pd.Timestamp(event[key])
            if pd.isna(timestamp) or timestamp.tzinfo is None:
                raise ValueError("Event timestamps require an explicit timezone (Z or UTC offset)")
            bounds.append(timestamp.tz_convert("UTC"))
        if bounds[0] > bounds[1]:
            raise ValueError("Event start must not exceed end")
        result.append(dict(name=event["name"], start=bounds[0], end=bounds[1]))
    return result


def compare(training_paths: list[Path], evaluation_path: Path, events: list[dict] | None = None) -> dict:
    resolved = [path.resolve() for path in training_paths]
    if not resolved or len(set(resolved)) != len(resolved):
        raise ValueError("Provide distinct training files")
    if evaluation_path.resolve() in resolved:
        raise ValueError("Evaluation file must not be used for training")
    training_raw = prepare_files(training_paths)
    evaluation_raw = prepare_files([evaluation_path])
    training, train_selection = complete_cases(training_raw)
    evaluation, test_selection = complete_cases(evaluation_raw)
    report = {
        "parameters": PARAMETERS.copy(),
        "feature_sets": {"baseline": BASE.copy(), "extended": EXTENDED.copy()},
        "versions": {"pandas": pd.__version__, "numpy": np.__version__, "scikit_learn": sklearn.__version__},
        "files": [{"path": str(path.resolve()), "role": role,
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                  for role, paths in [("training", training_paths), ("evaluation", [evaluation_path])]
                  for path in paths],
        "selection": {"training": train_selection, "evaluation": test_selection},
        "models": {}, "comparison": None, "intervals": [],
        "note": "Agreement and event responses are not accuracy; fewer anomalies do not imply improvement.",
    }
    if training.empty or evaluation.empty:
        report["status"] = "insufficient_complete_rows"
        return report
    report["status"] = "ok"
    results = evaluation[["source_file", "csv_row", "timestamp_utc", "session_id", "mspt_avg"]].copy()
    for name, columns in [("baseline", BASE), ("extended", EXTENDED)]:
        model = IsolationForest(**PARAMETERS)
        model.fit(training[columns])  # evaluation is NEVER fitted
        results[name + "_anomaly"] = model.predict(evaluation[columns]) == -1
        results[name + "_score"] = model.decision_function(evaluation[columns])
        report["models"][name] = {"features": columns.copy(), "training_rows": len(training),
                                  "evaluation_rows": len(evaluation),
                                  "anomalies": int(results[name + "_anomaly"].sum())}
    base, extended = results.baseline_anomaly, results.extended_anomaly
    different = results.loc[base != extended]
    report["comparison"] = {
        "both": int((base & extended).sum()), "baseline_only": int((base & ~extended).sum()),
        "extended_only": int((~base & extended).sum()), "neither": int((~base & ~extended).sum()),
        "disagreements": json.loads(different.to_json(orient="records", date_format="iso", double_precision=15)),
    }
    for event in events or []:
        raw_mask = evaluation_raw.timestamp_utc.between(event["start"], event["end"])
        mask = results.timestamp_utc.between(event["start"], event["end"])
        report["intervals"].append({
            "name": event["name"], "start": event["start"].isoformat(), "end": event["end"].isoformat(),
            "total_rows": int(raw_mask.sum()), "used_rows": int(mask.sum()),
            "excluded_rows": int(raw_mask.sum() - mask.sum()),
            "baseline_anomalies": int((base & mask).sum()),
            "extended_anomalies": int((extended & mask).sum()),
            "both": int((base & extended & mask).sum()),
        })
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", nargs="+", type=Path, required=True, help="Training CSV v2 files")
    parser.add_argument("--test", type=Path, required=True, help="Evaluation CSV, e.g. Dragon Run")
    parser.add_argument("--events", type=Path, help="JSON event intervals with explicit timezones")
    parser.add_argument("--json", type=Path, help="Save report (also printed to stdout)")
    args = parser.parse_args()
    try:
        report = compare(args.train, args.test, load_events(args.events))
        output = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
        print(output)
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(output + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
