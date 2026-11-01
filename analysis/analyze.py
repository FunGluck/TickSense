
"""TickSense: Minecraft server metrics analysis."""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.ensemble import IsolationForest


WINDOW = 6
FEATURES = ["mspt_avg", "players_online"]


def prepare_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)

    # Не смешиваем измерения разных запусков сервера.
    df["session_id"] = (df["elapsed_ms"].diff() < 0).cumsum() + 1

    grouped = df.groupby("session_id")["mspt_avg"]

    # Текущее измерение не участвует в расчёте своего порога.
    df["rolling_mean"] = grouped.transform(
        lambda s: s.shift(1).rolling(WINDOW).mean()
    )
    df["rolling_std"] = grouped.transform(
        lambda s: s.shift(1).rolling(WINDOW).std()
    )

    df["rolling_threshold"] = df["rolling_mean"] + 3 * df["rolling_std"]
    df["excess_mspt"] = df["mspt_avg"] - df["rolling_threshold"]
    df["stat_anomaly"] = df["excess_mspt"] > 0

    previous_online = df.groupby("session_id")["players_online"].shift(1)
    df["online_changed"] = (
            previous_online.notna()
            & (df["players_online"] != previous_online)
    )

    return df


# def detect_ml_anomalies(df: pd.DataFrame) -> pd.DataFrame:
#     model = IsolationForest(
#         n_estimators=100,
#         contamination=0.05,
#         random_state=42
#     )
#
#     X = df[FEATURES]
#     model.fit(X)
#
#     df["ml_prediction"] = model.predict(X)
#     df["ml_anomaly"] = df["ml_prediction"] == -1
#
#     return df


def plot_metrics(df: pd.DataFrame) -> None:
    stat_anomalies = df[df["stat_anomaly"]]
    ml_anomalies = df[df["ml_anomaly"]]

    plt.figure(figsize=(12, 6))

    plt.plot(
        df["timestamp_utc"],
        df["mspt_avg"],
        label="MSPT",
        alpha=0.4
    )
    plt.plot(
        df["timestamp_utc"],
        df["rolling_threshold"],
        label="Статистический порог",
        linewidth=2
    )

    plt.scatter(
        stat_anomalies["timestamp_utc"],
        stat_anomalies["mspt_avg"],
        color="orange",
        label="Статистические аномалии",
        zorder=3
    )
    plt.scatter(
        ml_anomalies["timestamp_utc"],
        ml_anomalies["mspt_avg"],
        color="red",
        marker="x",
        label="ML-аномалии",
        zorder=4
    )

    for timestamp in df.loc[df["online_changed"], "timestamp_utc"]:
        plt.axvline(timestamp, color="green", linestyle="--", alpha=0.5)

    plt.title("TickSense — сравнение детекторов")
    plt.xlabel("Время (UTC)")
    plt.ylabel("MSPT (мс)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description="TickSense metrics analysis")
    parser.add_argument("csv_path", type=Path, help="Path to metrics CSV")
    parser.add_argument("test_csv_path", type=Path)
    args = parser.parse_args()

    df = prepare_data(args.csv_path)
    # df = detect_ml_anomalies(df)
    test_df = prepare_data(args.test_csv_path)

    model = IsolationForest(
        n_estimators=100,
        contamination=0.05,
        random_state=42
    )

    X = df[FEATURES]
    X_test = test_df[FEATURES]
    model.fit(X)

    df["ml_prediction"] = model.predict(X)
    df["ml_anomaly"] = df["ml_prediction"] == -1
    test_df["ml_prediction"] = model.predict(X_test)
    test_df["anomaly_score"] = model.decision_function(X_test)
    test_df["ml_anomaly"] = test_df["ml_prediction"] == -1

    both = df[df["stat_anomaly"] & df["ml_anomaly"]]
    only_stat = df[df["stat_anomaly"] & ~df["ml_anomaly"]]
    only_ml = df[df["ml_anomaly"] & ~df["stat_anomaly"]]
    normal = df[~df["stat_anomaly"] & ~df["ml_anomaly"]]

    # smallest_score = test_df.nsmallest(5, "anomaly_score")
    # max_mspt_index = test_df["mspt_avg"].idxmax() # макс мспт по всей таблице

    print(
        test_df[test_df["ml_anomaly"]]
        [["timestamp_utc", "mspt_avg", "players_online", "anomaly_score"]]
        .sort_values("anomaly_score")
        .to_string(index=False)
    )
    # print(f"Самый низкий anomaly score: {smallest_score}")
    # print(max_mspt_index in smallest_score.index) # ищем среди аномалий макс мспт
    # print(f'Число AFK-измерений: {len(test_df)}')
    # print(f'Число найденных AFK-аномалий: {test_df["ml_anomaly"].sum()}')
    print(f"Сессий: {df['session_id'].nunique()}")
    print(f"Оба детектора: {len(both)}")
    print(f"Только статистика: {len(only_stat)}")
    print(f"Только ML: {len(only_ml)}")
    print(f"Оба считают нормой: {len(normal)}")
    print("Средний MSPT старого датасета:", df["mspt_avg"].mean())
    print("Средний MSPT AFK-датасета:", test_df["mspt_avg"].mean())

    print("Максимальный MSPT AFK-датасета:", test_df["mspt_avg"].max())
    print("Количество игроков в AFK-датасете:")
    print(test_df["players_online"].value_counts())

    plot_metrics(df)
    plot_metrics(test_df)


if __name__ == "__main__":
    main()
