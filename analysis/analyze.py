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
    df["rolling_mean"] = df["mspt_avg"].shift(1).rolling(window=6).mean()
    df["rolling_std"] = df["mspt_avg"].shift(1).rolling(window=6).std()
    df["rolling_threshold"] = df["rolling_mean"] + 3 * df["rolling_std"]

    dynamic_anomalies = df[df["mspt_avg"] > df["rolling_threshold"]]
    # шифт чтобы действующее значение не участвовало в измерении и резкий скачок учитывался за аномалию
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

    active_df = df[df["players_online"] > 0]
    empty_df = df[df["players_online"] == 0]
    empty_threshold = empty_df["mspt_avg"].mean() + 3 * empty_df["mspt_avg"].std()
    active_threshold = active_df["mspt_avg"].mean() + 3 * active_df["mspt_avg"].std()

    # empty_anomalies = empty_df[empty_df["mspt_avg"] > empty_threshold]
    # active_anomalies = active_df[active_df["mspt_avg"] > active_threshold]

    # plt.scatter(
    #     empty_anomalies["timestamp_utc"],
    #     empty_anomalies["mspt_avg"],
    #     color="orange",
    #     label=f"MSPT > {empty_threshold:.2f} мс",
    #     zorder=3
    # )
    # plt.scatter(
    #     active_anomalies["timestamp_utc"],
    #     active_anomalies["mspt_avg"],
    #     color="red",
    #     label=f"MSPT > {active_threshold:.2f} мс",
    #     zorder=3
    # )
    plt.scatter(
        dynamic_anomalies["timestamp_utc"],
        dynamic_anomalies["mspt_avg"],
        color="red",
        label="Динамические аномалии",
        zorder=3
    )

    df["previous_online"] = df["players_online"].shift(1).fillna(0)
    joins_df = df[(df["previous_online"] == 0) & (df["players_online"] > 0)] # подключения
    leaves_df = df[(df["previous_online"] > 0) & (df["players_online"] == 0)]

    for timestamp in joins_df["timestamp_utc"]:
        plt.axvline(timestamp, color="green", linestyle="--", label="Подключение")
    for timestamp in leaves_df["timestamp_utc"]:
        plt.axvline(timestamp, color="red", linestyle="--", label="Отключение")

    # .iloc[0] чтобы взять первую СТРОКУ

    plt.legend()
    plt.show()

    print(len(dynamic_anomalies))


if __name__ == "__main__":
    main()
