"""Command-line entry point for future TickSense metrics analysis."""

import argparse
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="TickSense metrics analysis scaffold")
    parser.add_argument("csv_path", type=Path, help="Path to a metrics CSV file")
    args = parser.parse_args()

    df = pd.read_csv(args.csv_path)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["session_id"] = (df["elapsed_ms"].diff() < 0).cumsum() + 1
    # При перезапуске сервера разница между elapsed_ms становится отрицательной. Фиксируем данный момент и указываем,
    # что началась другая сессия

    # session_nums = df.groupby("session_id")["mspt_avg"].agg(["count", "mean", "max"])

    # Сгруппируй строки по session_id, выбери столбец mspt_avg. Вычисли количество измерений,
    # средний и максимальный MSPT для каждой сессии

    df["rolling_mean"] = (
        df.groupby("session_id")["mspt_avg"]
        .transform(lambda s: s.shift(1).rolling(window=6).mean())
    )
    df["rolling_std"] = (
        df.groupby("session_id")["mspt_avg"]
        .transform(lambda s: s.shift(1).rolling(window=6).std())
    )
    # шифт чтобы действующее значение не участвовало в измерении и резкий скачок учитывался за аномалию
    df["rolling_threshold"] = df["rolling_mean"] + 3 * df["rolling_std"]
    df["excess_mspt"] = df["mspt_avg"] - df["rolling_threshold"]
    # excess_mspt - то, насколько сильно mspt отклонился от динамического порога

    dynamic_anomalies = df[df["mspt_avg"] > df["rolling_threshold"]]
    df["online_changed"] = (
            df["players_online"] != df["players_online"].shift(1).fillna(df["players_online"])
    )

    print(dynamic_anomalies[df["online_changed"] == True])
    # .size() возвращает количество строк в каждой группе.

    plt.plot(
        df["timestamp_utc"],
        df["mspt_avg"],
        label="Исходный MSPT",
        alpha=0.4
    )

    plt.plot(
        df["timestamp_utc"],
        df["rolling_mean"],
        label="Скользящее среднее (6 измерений)",
        linewidth=2
    )
    plt.plot(
        df["timestamp_utc"],
        df["rolling_threshold"],
        label="Динамический порог (6 измерений)",
        linewidth=2
    )

    plt.title("MSPT, скользящее среднее и динамический порог")
    plt.xlabel("Время (UTC)")
    plt.ylabel("MSPT (мс)")
    plt.grid(True, alpha=0.3)
    plt.legend()

    plt.scatter(
        dynamic_anomalies["timestamp_utc"],
        dynamic_anomalies["mspt_avg"],
        color="red",
        label="Динамические аномалии",
        zorder=3
    )

    df["previous_online"] = df["players_online"].shift(1).fillna(0)
    joins_df = df[(df["previous_online"] == 0) & (df["players_online"] > 0)]  # подключения
    leaves_df = df[(df["previous_online"] > 0) & (df["players_online"] == 0)]

    for timestamp in joins_df["timestamp_utc"]:
        plt.axvline(timestamp, color="green", linestyle="--", label="Подключение")
    for timestamp in leaves_df["timestamp_utc"]:
        plt.axvline(timestamp, color="red", linestyle="--", label="Отключение")

    # .iloc[0], чтобы взять первую СТРОКУ
    plt.show()


if __name__ == "__main__":
    main()
