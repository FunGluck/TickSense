"""Command-line entry point for future TickSense metrics analysis."""

import argparse
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="TickSense metrics analysis")
    parser.add_argument("csv_path", type=Path, help="Path to a metrics CSV file")
    args = parser.parse_args()

    window = 6

    # Загрузка данных
    df = pd.read_csv(args.csv_path)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)

    # Разделение по перезапускам сервера
    df["session_id"] = (df["elapsed_ms"].diff() < 0).cumsum() + 1

    # Динамический порог на основе предыдущих измерений каждой сессии
    grouped = df.groupby("session_id")["mspt_avg"]

    df["rolling_mean"] = grouped.transform(
        lambda s: s.shift(1).rolling(window).mean()
    )
    df["rolling_std"] = grouped.transform(
        lambda s: s.shift(1).rolling(window).std()
    )

    df["rolling_threshold"] = df["rolling_mean"] + 3 * df["rolling_std"]
    df["excess_mspt"] = df["mspt_avg"] - df["rolling_threshold"]

    dynamic_anomalies = df[df["excess_mspt"] > 0]

    # Изменения онлайна внутри серверных сессий
    previous_online = df.groupby("session_id")["players_online"].shift(1)
    df["online_changed"] = (
            previous_online.notna()
            & (df["players_online"] != previous_online)
    )

    # Статистика
    print(f"Количество сессий: {df['session_id'].nunique()}")
    print(f"Обнаружено аномалий: {len(dynamic_anomalies)}")
    print(
        f"Аномалии при изменении онлайна: "
        f"{df.loc[dynamic_anomalies.index, 'online_changed'].sum()}"
    )

    # График
    plt.figure(figsize=(12, 6))

    plt.plot(
        df["timestamp_utc"],
        df["mspt_avg"],
        label="MSPT",
        alpha=0.4
    )
    plt.plot(
        df["timestamp_utc"],
        df["rolling_mean"],
        label="Скользящее среднее",
        linewidth=2
    )
    plt.plot(
        df["timestamp_utc"],
        df["rolling_threshold"],
        label="Динамический порог",
        linewidth=2
    )

    plt.scatter(
        dynamic_anomalies["timestamp_utc"],
        dynamic_anomalies["mspt_avg"],
        color="red",
        label="Аномалии",
        zorder=3
    )

    # Отмечаем изменения количества игроков
    changes = df[df["online_changed"]]

    for timestamp in changes["timestamp_utc"]:
        plt.axvline(timestamp, color="green", linestyle="--", alpha=0.5)

    plt.title("TickSense — анализ MSPT")
    plt.xlabel("Время (UTC)")
    plt.ylabel("MSPT (мс)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
