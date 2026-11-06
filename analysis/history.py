"""Full descriptive history with TEST predictions attached by original row index."""
import numpy as np

if __package__:
    from .performance_events import detect_performance_events
    from .explanations import add_explanations
else:
    from performance_events import detect_performance_events
    from explanations import add_explanations


def attach_predictions(prepared, evaluation):
    """Pilot frames share original unique indexes; never predict TRAIN."""
    result = prepared.copy()
    if not prepared.index.is_unique or not evaluation.index.is_unique:
        raise ValueError('History requires unique row indexes')
    if not evaluation.index.isin(prepared.index).all():
        raise ValueError('Evaluation rows outside history')
    for column in ['ml_prediction', 'ml_anomaly', 'anomaly_score']:
        result[column] = evaluation[column].reindex(result.index)
    return result


def summarize_history(history, evaluation, *, scope):
    valid = evaluation.anomaly_score.notna() & np.isfinite(evaluation.anomaly_score)
    first = evaluation.loc[valid].iloc[0] if valid.any() else None
    return dict(scope=scope, measurements=len(history), sessions=int(history.session_id.nunique()),
                mspt_avg_mean=float(history.mspt_avg.mean()), mspt_avg_max=float(history.mspt_avg.max()),
                tps_1m_min=float(history.tps_1m.min()),
                stat_anomalies=int(history.stat_anomaly.sum()),
                stat_evaluable_measurements=int(history.rolling_threshold.notna().sum()),
                performance_events=add_explanations(history, detect_performance_events(history)),
                ml_boundary=None if first is None else dict(timestamp_utc=first.timestamp_utc.isoformat(),
                                                           session_id=int(first.session_id)))
