"""Compare two trusted local models on the same later, unused CSV period."""
import argparse
import json
from pathlib import Path

if __package__:
    from .data_quality import load_period
    from .features import engineer_features
    from .isolation import predict_anomalies
    from .model_store import load_model
    from .train_model import measurement_period, summarize_scores
else:
    from data_quality import load_period
    from features import engineer_features
    from isolation import predict_anomalies
    from model_store import load_model
    from train_model import measurement_period, summarize_scores

import pandas as pd


def compare_models(paths, model_paths):
    candidates = [load_model(path) for path in model_paths]
    if len({details["server_id"] for _, details in candidates}) != 1:
        raise ValueError("Для сравнения нужны модели одного сервера")
    latest = max(pd.Timestamp(details["validation"]["end_utc"]) for _, details in candidates)
    period = load_period(paths, allow_missing_model_metrics=True)
    if period.timestamp_utc.iloc[0] <= latest:
        raise ValueError(f"CSV сравнения должны начинаться после {latest.isoformat()} (конец обеих проверок)")
    prepared = engineer_features(period)
    return dict(period=measurement_period(period), models=[
        dict(version=details["version"], **summarize_scores(predict_anomalies(model, prepared)))
        for model, details in candidates
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, nargs=2, required=True)
    parser.add_argument("--files", type=Path, nargs="+", required=True)
    args = parser.parse_args()
    try:
        result = compare_models(args.files, args.models)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
