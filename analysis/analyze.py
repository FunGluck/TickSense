"""Analyze Minecraft telemetry using a saved model or the legacy fit modes."""
import argparse
import json
from pathlib import Path
from pandas import Timestamp

if __package__:
    from .event_insights import build_insights, performance_health
    from .history import attach_predictions, summarize_history
    from .interpretation import interpret_results
    from .data_quality import load_period, assess_quality, chronological_split
    from .data import load_data
    from .features import engineer_features
    from .statistical import detect_statistical
    from .isolation import train_model, predict_anomalies
    from .model_store import load_model
    from .report import build_report
    from .visualization import plot_metrics
    from .html_report import write_html_report
else:
    from event_insights import build_insights, performance_health
    from history import attach_predictions, summarize_history
    from interpretation import interpret_results
    from data_quality import load_period, assess_quality, chronological_split
    from data import load_data
    from features import engineer_features
    from statistical import detect_statistical
    from isolation import train_model, predict_anomalies
    from model_store import load_model
    from report import build_report
    from visualization import plot_metrics
    from html_report import write_html_report


def main() -> None:
    parser = argparse.ArgumentParser(description="TickSense metrics analysis")
    parser.add_argument("csv_path", nargs="?", type=Path, help="Training CSV")
    parser.add_argument("test_csv_path", nargs="?", type=Path, help="Evaluation CSV")
    parser.add_argument("--json", type=Path, dest="json_path", help="Save JSON report")
    parser.add_argument("--png", type=Path, dest="png_path", help="Save PNG plot")
    parser.add_argument("--no-show", action="store_true", help="Do not open a plot window")
    parser.add_argument("--html", type=Path, dest="html_path", help="Save standalone HTML dashboard")
    parser.add_argument("--pilot-files", nargs="+", type=Path, help="CSV in chronological file order; early 70%% trains, later 30%% evaluates")
    parser.add_argument("--model", type=Path, help="Use a trusted local .joblib without fitting (requires --pilot-files)")
    args = parser.parse_args()
    if args.pilot_files and (args.csv_path or args.test_csv_path):
        parser.error("--pilot-files cannot be combined with TRAIN/TEST")
    if args.model and not args.pilot_files:
        parser.error("--model requires --pilot-files CSV [CSV ...]")
    if not args.pilot_files and not (args.csv_path and args.test_csv_path):
        parser.error("Specify TRAIN TEST or --pilot-files CSV [CSV ...]")
    try:
        if args.model:
            model, metadata = load_model(args.model)
            period = load_period(args.pilot_files, allow_missing_model_metrics=True)
            history = evaluation = predict_anomalies(model, detect_statistical(engineer_features(period)))
            training = None
            scope = "saved_model"
            quality = assess_quality(period, split={"method": scope})
            unscored = int(evaluation.anomaly_score.isna().sum())
            quality["ml_unscored_measurements"] = unscored
            if unscored:
                quality["warnings"].append(f"Измерений без ML-оценки из-за пропущенных признаков: {unscored}.")
            if period.timestamp_utc.iloc[0] <= Timestamp(metadata["training"]["end_utc"]):
                quality["warnings"].append("Период начинается до конца обучения модели или совпадает с ним. Возможны измерения из обучающей истории.")
            if quality["warnings"]:
                quality["status"] = "warning"
        elif args.pilot_files:
            period = load_period(args.pilot_files)
            # Features and rolling statistics are causal; compute before slicing to retain past context.
            prepared = detect_statistical(engineer_features(period))
            training, evaluation, split = chronological_split(prepared)
            quality = assess_quality(period, split=split)
            scope = "pilot_full"
        else:
            training = engineer_features(load_data(args.csv_path))
            raw = load_data(args.test_csv_path)
            evaluation = detect_statistical(engineer_features(raw))
            quality = assess_quality(raw, split={"method": "separate_files"})
            scope = "evaluation_only"
        if training is not None:
            evaluation = predict_anomalies(train_model(training), evaluation)
            history = attach_predictions(prepared, evaluation) if scope == "pilot_full" else evaluation
        report = build_report(evaluation)
        report["full_period"] = summarize_history(
            history, evaluation, scope=scope,
            performance_events=report["performance_events"] if history is evaluation else None,
        )
        report["data_quality"] = quality
        report["interpretation"] = interpret_results(training, evaluation, report["performance_events"]["episodes"])
        if args.model:
            report["ml_model"] = {key: metadata[key] for key in ("model_type", "version", "trained_at_utc", "server_id")}
            report["ml_model"]["training_measurements"] = metadata["training"]["measurements"]
            report["ml_model"]["evaluated_measurements"] = len(evaluation) - unscored
            report["ml_model"]["unscored_measurements"] = unscored
        report["event_insights"] = build_insights(history)
        report["performance_health"] = performance_health(history)
        output = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
        print(output)
        if args.json_path:
            args.json_path.parent.mkdir(parents=True, exist_ok=True)
            args.json_path.write_text(output + "\n", encoding="utf-8")
        if args.png_path or not args.no_show:
            plot_metrics(evaluation, args.png_path, show=not args.no_show)
        if args.html_path:
            write_html_report(history, report, args.html_path)
        columns = [
            "timestamp_utc",
            "mspt_avg",
            "tps_1m",
            "loaded_chunks_delta",
            "entities_delta",
            "gc_count_delta",
            "gc_time_delta_ms",
            "heap_used_ratio",
        ]

        print(
            evaluation.nlargest(10, "mspt_avg")[columns]
            .to_string(index=False)
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
