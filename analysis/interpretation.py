"""Presentation diagnostics only: never fit models or modify detector labels."""
import numpy as np
import pandas as pd

# A disclosed UI heuristic, not a universal representativeness requirement.
WEAK_COVERAGE_PERCENT = 5.0


def _metric(count, denominator):
    return dict(count=count, evaluated=denominator,
                percent=100 * count / denominator if denominator else None)


def interpret_results(training, evaluation, events):
    """Summarize actual evaluable predictions; missing predictions stay unknown."""
    def flags(column):
        return evaluation.get(column, pd.Series(index=evaluation.index, dtype=object))

    scores = pd.to_numeric(flags('anomaly_score'), errors='coerce')
    ml_valid = flags('ml_anomaly').notna() & np.isfinite(scores)
    stat_valid = flags('stat_anomaly').notna() & pd.to_numeric(
        flags('rolling_threshold'), errors='coerce').notna()
    ml = flags('ml_anomaly').fillna(False).astype(bool) & ml_valid
    stat = flags('stat_anomaly').fillna(False).astype(bool) & stat_valid
    coverage, warnings = [], []
    for key, label, empty in [('empty', 'Пустой сервер', True), ('active', 'С игроками', False)]:
        def regime(frame):
            values = pd.to_numeric(frame.get('players_online', pd.Series(index=frame.index, dtype=float)), errors='coerce')
            return values.eq(0) if empty else values.gt(0)
        tr, te = regime(training), regime(evaluation)
        a, b = int(tr.sum()), int(te.sum())
        share = 100 * a / len(training) if len(training) else None
        coverage.append(dict(mode=key, label=label, train=_metric(a, len(training)),
                             test=_metric(b, len(evaluation)),
                             test_ml=_metric(int((ml & te).sum()), int((ml_valid & te).sum()))))
        if b and len(training) and share < WEAK_COVERAGE_PERCENT:
            warnings.append(f'Режим «{label}» составляет {share:.2f}% TRAIN и {100*b/len(evaluation):.2f}% TEST. '
                            'Он отсутствует или слабо представлен в обучении по диагностической эвристике. '
                            'ML-метки этого режима требуют осторожной интерпретации; это не оценка точности.')
    count = len(events)
    conclusion = (f'Обнаружено пороговых эпизодов: {count}. Они соответствуют настроенным условиям MSPT/TPS, '
                  'но не доказывают ухудшение игрового опыта.') if count else (
                  'Пороговых событий ухудшения производительности не обнаружено. '
                  'Это означает отсутствие срабатываний настроенных условий MSPT/TPS, а не доказательство отсутствия лагов.')
    if not len(evaluation):
        conclusion = 'Проверочных измерений нет; интерпретация недоступна.'
    elif not ml_valid.any():
        conclusion += ' ML-результаты недоступны: нет оцениваемых предсказаний.'
    else:
        conclusion += f' ML выявила {int(ml.sum())} необычных измерений, которые не обязательно означают лаги.'
        if int(ml_valid.sum()) < len(evaluation):
            conclusion += ' ML-предсказания доступны только для части измерений.'
    if len(evaluation) and len(training) < 6:
        conclusion += ' Обучающих измерений недостаточно для содержательной интерпретации ML; технический минимум — 6, он не гарантирует репрезентативность.'
    if warnings and ml.any():
        conclusion += ' Покрытие режимов онлайна в TRAIN и TEST различается; это может влиять на интерпретацию ML-меток.'
    return dict(performance_events=count, ml=_metric(int(ml.sum()), int(ml_valid.sum())),
                statistical=_metric(int(stat.sum()), int(stat_valid.sum())),
                both=int((ml & stat).sum()), unique=int((ml | stat).sum()),
                train_measurements=len(training), test_measurements=len(evaluation),
                coverage=coverage, coverage_warnings=warnings,
                weak_coverage_percent=WEAK_COVERAGE_PERCENT, conclusion=conclusion)
