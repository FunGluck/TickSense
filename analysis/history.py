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


def summarize_history(history, evaluation, *, scope, performance_events=None):
    valid = evaluation.anomaly_score.notna() & np.isfinite(evaluation.anomaly_score)
    first = evaluation.loc[valid].iloc[0] if scope != "saved_model" and valid.any() else None
    values = [history.mspt_avg.mean(), history.mspt_avg.max(), history.tps_1m.min()]
    mean, peak, minimum = [float(value) if np.isfinite(value) else None for value in values]
    if performance_events is None:
        performance_events = add_explanations(history, detect_performance_events(history))
    return dict(scope=scope, measurements=len(history), sessions=int(history.session_id.nunique()),
                mspt_avg_mean=mean, mspt_avg_max=peak, tps_1m_min=minimum,
                stat_anomalies=int(history.stat_anomaly.sum()),
                stat_evaluable_measurements=int(history.rolling_threshold.notna().sum()),
                performance_events=performance_events,
                ml_boundary=None if first is None else dict(timestamp_utc=first.timestamp_utc.isoformat(),
                                                           session_id=int(first.session_id)))
