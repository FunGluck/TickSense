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
    active_df = df[df["players_online"] > 0]
    empty_df = df[df["players_online"] == 0]
    empty_threshold = empty_df["mspt_avg"].mean() + 3 * empty_df["mspt_avg"].std()
    active_threshold = active_df["mspt_avg"].mean() + 3 * active_df["mspt_avg"].std()

    empty_anomalies = empty_df[empty_df["mspt_avg"] > empty_threshold]
    active_anomalies = active_df[active_df["mspt_avg"] > active_threshold]

    plt.scatter(
        empty_anomalies["timestamp_utc"],
        empty_anomalies["mspt_avg"],
        color="orange",
        label=f"MSPT > {empty_threshold:.2f} мс",
        zorder=3
    )
    plt.scatter(
        active_anomalies["timestamp_utc"],
        active_anomalies["mspt_avg"],
        color="red",
        label=f"MSPT > {active_threshold:.2f} мс",
        zorder=3
    )

    df["previous_online"] = df["players_online"].shift(1).fillna(0)
    joins_df = df[(df["previous_online"] == 0) & (df["players_online"] > 0)] # подключения
    leaves_df = df[(df["previous_online"] > 0) & (df["players_online"] == 0)]

    for timestamp in joins_df["timestamp_utc"]:
        plt.axvline(timestamp, color="green", linestyle="--", label="Подключение")
    for timestamp in leaves_df["timestamp_utc"]:
        plt.axvline(timestamp, color="red", linestyle="--", label="Отключение")

    plt.plot(df["timestamp_utc"], df["mspt_avg"])
    plt.title("Зависимость MSPT от времени")
    plt.xlabel("Время (UTC)")
    plt.ylabel("Средний MSPT (мс)")
    plt.grid(True, alpha=0.3)
    # .iloc[0] чтобы взять первую СТРОКУ

    plt.legend()
    plt.show()

    active_write_amount = len(active_df)
    empty_write_amount = len(empty_df)
    active_mspt_mean = active_df["mspt_avg"].mean()
    empty_mspt_mean = empty_df["mspt_avg"].mean()
    active_mspt_max = active_df["mspt_avg"].max()
    empty_mspt_max = empty_df["mspt_avg"].max()
    active_mspt_min = active_df["mspt_avg"].min()
    empty_mspt_min = empty_df["mspt_avg"].min()
    active_max_online = active_df["players_online"].max()
    empty_max_online = empty_df["players_online"].max()
    active_tps_min = active_df["tps_1m"].min()
    empty_tps_min = empty_df["tps_1m"].min()

    ratio = active_mspt_mean / empty_mspt_mean


    print(f"MSPT с игроком выше в {ratio:.2f} раза")
    print("Пустой сервер:")
    print(f"Количество записей: {empty_write_amount}")
    print(f"Средний MSPT за весь период: {empty_mspt_mean:.2f}")
    print(f"Максимальный MSPT: {empty_mspt_max:.2f}")
    print(f"Минимальный MSPT: {empty_mspt_min:.2f}")
    print(f"Максимальное количество игроков онлайн: {empty_max_online}")
    print(f"Минимальный TPS: {empty_tps_min:.2f}")
    print("--------------------")
    print("Не пустой сервер:")
    print(f"Количество записей: {active_write_amount}")
    print(f"Средний MSPT за весь период: {active_mspt_mean:.2f}")
    print(f"Максимальный MSPT: {active_mspt_max:.2f}")
    print(f"Минимальный MSPT: {active_mspt_min:.2f}")
    print(f"Максимальное количество игроков онлайн: {active_max_online}")
    print(f"Минимальный TPS: {active_tps_min:.2f}")


if __name__ == "__main__":
    main()
