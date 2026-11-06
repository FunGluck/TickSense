"""Offline HTML presentation of existing analysis results; no detectors here."""
from copy import deepcopy
import json
from pathlib import Path, PureWindowsPath
import re
import pandas as pd

ASSETS = Path(__file__).with_name("dashboard")


def _presentation(value):
    if isinstance(value, dict):
        return {key: (PureWindowsPath(str(item)).name if key == "source_file" and item else _presentation(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [_presentation(item) for item in value]
    if isinstance(value, str):
        value = value.replace("GC time", "времени GC").replace("committed heap", "выделенной памяти JVM")
        def observation(match):
            n = int(match[1])
            word = "наблюдений" if 11 <= n % 100 <= 14 else ("наблюдение" if n % 10 == 1 else "наблюдения" if 2 <= n % 10 <= 4 else "наблюдений")
            return f"{n} {word}"
        value = re.sub(r"(\d+) наблюдений", observation, value)
        return re.sub(r"(?<=\d)\.(?=\d)", ",", value) if not re.match(r"^\d{4}-\d\d-\d\dT", value) else value
    return value


def prepare_html_data(df: pd.DataFrame, report: dict) -> dict:
    columns = ["timestamp_utc", "session_id", "players_online", "mspt_avg", "tps_1m", "stat_anomaly",
               "ml_anomaly", "anomaly_score", "rolling_threshold", "excess_mspt", "csv_row", "source_file"]
    points = df.reindex(columns=columns).copy()
    if "csv_row" not in df:
        points["csv_row"] = range(2, len(df) + 2)
    # pandas emits null for NaN/inf, including absent v2 metrics.
    records = json.loads(points.to_json(orient="records", date_format="iso", date_unit="ns"))
    return _presentation({"interpretation": deepcopy(report.get("interpretation")), "data_quality": deepcopy(report.get("data_quality")), "points": records, "events": deepcopy(report["performance_events"]["episodes"])})


def render_html(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False)
    for character, replacement in [("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"),
                                   ("\u2028", "\\u2028"), ("\u2029", "\\u2029")]:
        payload = payload.replace(character, replacement)
    template = (ASSETS / "template.html").read_text(encoding="utf-8")
    # Substitute payload last, so data cannot masquerade as a template marker.
    return template.replace("/*STYLE*/", (ASSETS / "style.css").read_text(encoding="utf-8")).replace(
        "/*CODE*/", (ASSETS / "dashboard.js").read_text(encoding="utf-8")).replace("/*DATA*/", payload)


def write_html_report(df: pd.DataFrame, report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(prepare_html_data(df, report)), encoding="utf-8")
