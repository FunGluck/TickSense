"""Plot evaluation data interactively or export with the Agg backend."""
from pathlib import Path
import pandas as pd


def plot_metrics(df: pd.DataFrame, png_path: Path | None = None, *, show: bool = True) -> None:
    import matplotlib

    if not show:
        matplotlib.use("Agg")

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 6))

    try:
        breaks = df.session_id.ne(df.session_id.shift()) | df.timestamp_utc.diff().dt.total_seconds().gt(30)
        for index, (_, session) in enumerate(df.groupby(breaks.cumsum(), sort=False)):
            ax.plot(session["timestamp_utc"], session["mspt_avg"], color="steelblue", alpha=0.5,
                    label="MSPT" if index == 0 else None)
            ax.plot(session["timestamp_utc"], session["rolling_threshold"], color="orange",
                    label="Rolling threshold" if index == 0 else None)

        for column, color, marker, label in [
            ("stat_anomaly", "orange", "o", "Statistical anomalies"),
            ("ml_anomaly", "red", "x", "ML anomalies"),
        ]:
            points = df[df[column]]
            ax.scatter(points["timestamp_utc"], points["mspt_avg"], color=color, marker=marker, label=label, zorder=3)

        for timestamp in df.loc[df["online_changed"], "timestamp_utc"]:
            ax.axvline(timestamp, color="green", linestyle="--", alpha=0.3)

        ax.set(title="TickSense — evaluation CSV", xlabel="Time (UTC)", ylabel="MSPT (ms)")
        ax.grid(alpha=0.3)
        ax.legend()
        fig.tight_layout()

        if png_path:
            png_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(png_path, format="png", dpi=150)

        if show:
            plt.show()

    finally:
        plt.close(fig)
