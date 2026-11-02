"""Deterministic descriptions of measured context, without causal diagnosis."""
from copy import deepcopy
import numpy as np
import pandas as pd

LABELS = {"high_mspt": "Превышение высокого порога MSPT",
          "low_tps": "TPS ниже заданного порога",
          "elevated_mspt": "Превышение порога повышенного MSPT"}


def explain_episode(df: pd.DataFrame, episode: dict) -> dict:
    """Use only the episode's source records, file, session and time bounds.

    Deltas at a row describe the preceding interval, which can begin before
    the episode. No context from later rows is included or interpolated.
    """
    times = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce", format="mixed")
    rows = df["csv_row"] if "csv_row" in df else pd.Series(np.arange(len(df)) + 2, index=df.index)
    sources = df["source_file"].where(df["source_file"].notna(), None) if "source_file" in df else pd.Series(None, index=df.index, dtype=object)
    source_mask = sources.isna() if episode["source_file"] is None else sources.eq(episode["source_file"])
    selected = df.loc[source_mask & df["session_id"].eq(episode["session_id"])
                      & rows.isin(episode["source_rows"])
                      & times.between(pd.Timestamp(episode["start_utc"]), pd.Timestamp(episode["last_observed_utc"]))]
    context = {}
    facts = [f"{LABELS[episode['signal']]}. Пиковый MSPT — {episode['peak_mspt']:.2f} мс; минимальный TPS — {episode['min_tps']:.2f}."]
    for feature, label in [("loaded_chunks_delta", "Число загруженных чанков"),
                           ("entities_delta", "Число сущностей"),
                           ("gc_count_delta", "Счётчик сборок GC"),
                           ("gc_time_delta_ms", "Накопленное время GC"),
                           ("heap_used_ratio", "Доля использованного committed heap")]:
        values = (pd.to_numeric(selected[feature], errors="coerce").astype(float)
                  if feature in selected else pd.Series(dtype=float))
        values = values[np.isfinite(values)]
        if feature.startswith("gc_"):
            values = values[values >= 0]
        elif feature == "heap_used_ratio":
            values = values[(values >= 0) & (values <= 1)]
        count = len(values)
        item = {"available_observations": count, "unavailable_observations": episode["measurements"] - count,
                "status": "available" if count else "unavailable"}
        if feature == "heap_used_ratio":
            item.update(aggregation="min_max_of_available_ratios",
                        min=float(values.min()) if count else None,
                        max=float(values.max()) if count else None)
            if count:
                facts.append(f"{label}: от {values.min():.4f} до {values.max():.4f} ({count} наблюдений).")
        elif feature.startswith("gc_"):
            item.update(aggregation="sum_of_available_nonnegative_interval_deltas",
                        sum_delta=float(values.sum()) if count else None)
            if count:
                unit = " мс" if feature == "gc_time_delta_ms" else ""
                facts.append(f"{label}: сумма доступных интервальных приростов — {values.sum():g}{unit} ({count} наблюдений).")
        else:
            item.update(aggregation="sum_of_signed_interval_deltas_and_max_positive_delta",
                        net_delta=float(values.sum()) if count else None,
                        max_positive_delta=float(max(0, values.max())) if count else None)
            if count:
                facts.append(f"{label}: сумма знаковых изменений — {values.sum():g}, максимальный положительный прирост — {max(0, values.max()):g} ({count} наблюдений).")
        context[feature] = item
    if all(item["status"] == "unavailable" for item in context.values()):
        facts.append("Сопутствующий контекст телеметрии недоступен.")
    return {
        "signal": episode["signal"], "description": facts[0],
        "start_utc": episode["start_utc"], "last_observed_utc": episode["last_observed_utc"],
        "session_id": episode["session_id"], "peak_mspt": episode["peak_mspt"], "min_tps": episode["min_tps"],
        "measurements": episode["measurements"], "source_file": episode["source_file"],
        "source_rows": list(episode["source_rows"]), "matched_rows": len(selected),
        "observed_facts": facts, "telemetry_context": context,
        "possible_interpretation": "Пороговый сигнал возможного ухудшения производительности; доступные изменения телеметрии сопутствуют наблюдениям, но не устанавливают причину.",
        "limitations": [
            "Выборочные измерения не доказывают ухудшение игрового опыта и не задают точную длительность лага.",
            "Интервальный прирост относится к предыдущему интервалу той же сессии; первый интервал может начинаться до эпизода.",
            "Суммы относятся только к доступным интервалам, пропуски не означают нулевую активность.",
            "Знаковое изменение чанков/сущностей допускает уменьшение и не является общим числом загрузок/созданий.",
            "Прирост GC time не является длительностью лага или точным временем пауз сервера.",
            "Пересекающиеся сигналы могут описывать один временной участок и не считаются независимыми проблемами.",
        ],
    }


def add_explanations(df: pd.DataFrame, events: dict) -> dict:
    """Enrich a copy, leaving detector output and input telemetry unchanged."""
    result = deepcopy(events)
    for episode in result["episodes"]:
        episode["explanation"] = explain_episode(df, episode)
    return result
