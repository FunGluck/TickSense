"""Fit and validate a new, versioned Isolation Forest on CSV v2 telemetry."""
import argparse
import json
from pathlib import Path
from time import perf_counter

if __package__:
    from .data_quality import assess_quality, chronological_split, load_period
    from .event_insights import build_insights
    from .features import engineer_features
    from .isolation import FEATURES, eligible_rows, predict_anomalies, train_model
    from .model_store import require_new_artifact, save_model, sha256
    from .statistical import detect_statistical
else:
    from data_quality import assess_quality, chronological_split, load_period
    from event_insights import build_insights
    from features import engineer_features
    from isolation import FEATURES, eligible_rows, predict_anomalies, train_model
    from model_store import require_new_artifact, save_model, sha256
    from statistical import detect_statistical


def summarize_scores(predictions):
    scores = predictions.anomaly_score.dropna()
    anomalous = int(predictions.ml_anomaly.sum())
    episodes = build_insights(predictions)["ml_episodes"]
    quantiles = scores.quantile([0, .05, .5, .95, 1]) if len(scores) else {}
    return dict(evaluated=len(scores), unscored=len(predictions)-len(scores), anomalies=anomalous,
                anomaly_fraction=anomalous/len(scores) if len(scores) else None,
                decision_function_quantiles={str(q): float(value) for q, value in quantiles.items()},
                ml_episodes=len(episodes),
                ml_episodes_with_threshold_signal=sum(e["threshold_signal"] for e in episodes))


def measurement_period(frame):
    return dict(measurements=len(frame), sessions=int(frame.session_id.nunique()),
                start_utc=frame.timestamp_utc.iloc[0].isoformat(),
                end_utc=frame.timestamp_utc.iloc[-1].isoformat())


def train_candidate(paths, output, *, server_id):
    require_new_artifact(output)
    if not server_id.strip():
        raise ValueError("Укажите непустой идентификатор одного сервера")
    manifest = []
    start = perf_counter()
    for path in paths:
        with path.open("rb") as stream:
            manifest.append(dict(sha256=sha256(stream), bytes=stream.tell()))
    period = load_period(paths, require_v2=True, allow_missing_model_metrics=True)
    loaded = perf_counter()
    prepared = detect_statistical(engineer_features(period))
    earlier, holdout, split = chronological_split(prepared, fraction=.8)
    train = earlier.loc[eligible_rows(earlier)]
    if len(train) < 6 or eligible_rows(holdout).sum() < 2:
        raise ValueError("Нужны минимум 6 пригодных строк для обучения и 2 для отложенной проверки")
    prepared_at = perf_counter()
    model = train_model(train)
    fitted_at = perf_counter()
    predictions = predict_anomalies(model, holdout)
    scored_at = perf_counter()

    quality = assess_quality(period, split=split)
    quality.update(
        missing_model_features={feature: int(period[feature].isna().sum()) for feature in FEATURES},
        rolling_context_unavailable=int(prepared.rolling_threshold.isna().sum()),
        training_rows_excluded=len(earlier)-len(train),
    )
    quality["limitations"].append(
        "Нагрузочные эксперименты не размечены. История используется без фильтрации по ML-меткам или порогам нагрузки."
    )
    validation = dict(**measurement_period(holdout), **summarize_scores(predictions), method="chronological_holdout")
    details = save_model(output, model, server_id=server_id.strip(), training=measurement_period(train),
                         validation=validation, quality=quality,
                         dataset=dict(files=manifest, order="chronological", duplicate_policy="retain_and_report"))
    return details, dict(load_s=loaded-start, prepare_features_s=prepared_at-loaded,
                         fit_s=fitted_at-prepared_at, predict_and_score_s=scored_at-fitted_at,
                         total_s=perf_counter()-start)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--data-dir", type=Path, help="One server's directory of CSV files named in date order")
    source.add_argument("--files", type=Path, nargs="+", help="One server's CSV files in chronological order")
    parser.add_argument("--server-id", required=True, help="Non-personal identifier of the source server")
    parser.add_argument("--output", type=Path, required=True, help="New local .joblib path")
    args = parser.parse_args()
    try:
        if args.data_dir is not None and not args.data_dir.is_dir():
            raise ValueError("Каталог CSV не найден")
        paths = sorted(args.data_dir.glob("*.csv")) if args.data_dir is not None else args.files
        details, timings = train_candidate(paths, args.output, server_id=args.server_id)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(dict(metadata=details, timings=timings), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
