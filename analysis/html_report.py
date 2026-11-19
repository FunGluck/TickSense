"""Offline HTML presentation of existing analysis results; no detectors here."""
import base64
import gzip
import math
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
    points = {}
    for key in columns:
        if key not in df:
            if key == "csv_row":
                points[key] = list(range(2, len(df) + 2))
            continue
        values = df[key].tolist()
        if key == "source_file":
            names = {name: PureWindowsPath(str(name)).name for name in df[key].dropna().unique()}
            values = [names.get(value) for value in values]
        elif key == "timestamp_utc":
            values = [value.isoformat() if pd.notna(value) else None for value in values]
        else:
            values = [None if pd.isna(value) or isinstance(value, float) and not math.isfinite(value)
                      else value for value in values]
        points[key] = values

    insights = report.get("event_insights")
    full = report.get("full_period")
    events = (insights["display_performance_events"] if insights else
              (full or report)["performance_events"]["episodes"])
    # The standalone JSON report retains all original structures. The dashboard
    # needs just one event list and the part of the summary used by the UI.
    metadata = _presentation({
        "event_insights": {key: value for key, value in insights.items()
                           if key != "display_performance_events"} if insights else None,
        "full_period": {key: value for key, value in full.items()
                        if key != "performance_events"} if full else None,
        "performance_health": report.get("performance_health"),
        "interpretation": report.get("interpretation"),
        "data_quality": report.get("data_quality"),
        **({"ml_model": report["ml_model"]} if "ml_model" in report else {}),
        "events": events,
    })
    return {**metadata, "columns": points}


def render_html(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    template = (ASSETS / "template.html").read_text(encoding="utf-8")
    code = (ASSETS / "dashboard.js").read_text(encoding="utf-8")
    if len(payload) >= 2_000_000:
        payload = base64.b64encode(gzip.compress(payload.encode("utf-8"), compresslevel=3, mtime=0)).decode("ascii")
        template = template.replace('id="report-data" type="application/json"',
                                    'id="report-data" type="application/octet-stream"')
        code = (ASSETS / "load_report.js").read_text(encoding="utf-8").replace("/*DASHBOARD*/", code)
    else:
        for character, replacement in [("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"),
                                       ("\u2028", "\\u2028"), ("\u2029", "\\u2029")]:
            payload = payload.replace(character, replacement)
    # Substitute payload last, so data cannot masquerade as a template marker.
    return template.replace("/*STYLE*/", (ASSETS / "style.css").read_text(encoding="utf-8")).replace(
        "/*CODE*/", code).replace("/*DATA*/", payload)


def write_html_report(df: pd.DataFrame, report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(prepare_html_data(df, report)), encoding="utf-8")
