"""Train on the first CSV; report on the second CSV."""
import argparse
import json
from pathlib import Path

if __package__:
    from .data import load_data
    from .statistical import detect_statistical
    from .isolation import train_model, predict_anomalies
    from .report import build_report
    from .visualization import plot_metrics
else:
    from data import load_data
    from statistical import detect_statistical
    from isolation import train_model, predict_anomalies
    from report import build_report
    from visualization import plot_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="TickSense metrics analysis")
    parser.add_argument("csv_path", type=Path, help="Training CSV")
    parser.add_argument("test_csv_path", type=Path, help="Evaluation CSV")
    parser.add_argument("--json", type=Path, dest="json_path", help="Save JSON report")
    parser.add_argument("--png", type=Path, dest="png_path", help="Save PNG plot")
    parser.add_argument("--no-show", action="store_true", help="Do not open a plot window")
    args = parser.parse_args()
    try:
        training = load_data(args.csv_path)
        evaluation = detect_statistical(load_data(args.test_csv_path))
        evaluation = predict_anomalies(train_model(training), evaluation)
        output = json.dumps(build_report(evaluation), ensure_ascii=False, indent=2, allow_nan=False)
        print(output)
        if args.json_path:
            args.json_path.parent.mkdir(parents=True, exist_ok=True)
            args.json_path.write_text(output + "\n", encoding="utf-8")
        if args.png_path or not args.no_show:
            plot_metrics(evaluation, args.png_path, show=not args.no_show)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
