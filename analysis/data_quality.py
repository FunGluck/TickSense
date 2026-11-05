"""Strict loading and descriptive quality diagnostics; never repair rows silently."""
from pathlib import Path
import pandas as pd

if __package__:
    from .data import load_data
else:
    from data import load_data

MAX_GAP_SECONDS = 30


def load_period(paths):
    """Read files in supplied order; midnight is not a server restart."""
    frames = [load_data(Path(path)) for path in paths]
    if not frames:
        raise ValueError("Не указаны CSV")
    schema = set(frames[0])
    if any(set(frame) != schema for frame in frames):
        raise ValueError("Несогласованные схемы дневных CSV")
    df = pd.concat(frames, ignore_index=True)
    if (df.timestamp_utc.diff().dt.total_seconds() < 0).any():
        raise ValueError("Перекрытие файлов или обратный порядок времени; автоматическая сортировка отключена")
    df['session_id'] = (df.elapsed_ms.diff() < 0).cumsum() + 1
    previous = df.groupby('session_id').players_online.shift()
    df['online_changed'] = previous.notna() & df.players_online.ne(previous)
    return df


def assess_quality(df, *, split=None, max_gap_seconds=MAX_GAP_SECONDS):
    gaps = df.groupby('session_id').timestamp_utc.diff().dt.total_seconds()
    identity = [c for c in df if c not in {'source_file', 'csv_row', 'session_id', 'online_changed'}]
    duplicates = int(df.duplicated(subset=identity).sum())
    warnings = []
    if duplicates:
        warnings.append(f'Повторяющиеся измерения: {duplicates}. Строки сохранены.')
    count = int((gaps > max_gap_seconds).sum())
    if count:
        warnings.append(f'Разрывы наблюдений свыше {max_gap_seconds} с: {count}. Причина неизвестна.')
    if df.elapsed_ms.diff().eq(0).any():
        warnings.append('Есть одинаковые elapsed_ms; проверьте повторные записи.')
    return dict(status='warning' if warnings else 'ok',
                start_utc=df.timestamp_utc.iloc[0].isoformat(),
                end_utc=df.timestamp_utc.iloc[-1].isoformat(),
                source_csv_count=int(df.source_file.nunique()), measurements=len(df),
                sessions=int(df.session_id.nunique()), long_gaps=count,
                max_interval_seconds=float(gaps.max()) if gaps.notna().any() else None,
                max_gap_seconds=max_gap_seconds, duplicate_measurements=duplicates,
                warnings=warnings, split=split,
                limitations=['Сессии определяются по уменьшению elapsed_ms: некоторые перезапуски неразличимы.',
                             'Разрыв наблюдений не доказывает лаг. Интервал зависит от TPS; 30 с — диагностический порог.',
                             'ML-сигналы не являются подтверждёнными лагами или оценкой точности.'])


def chronological_split(df, fraction=0.7):
    if not 0 < fraction < 1:
        raise ValueError('Доля обучения должна быть между 0 и 1')
    boundary = int(len(df) * fraction)
    # Equal timestamps must never occur on both sides of the split.
    while 0 < boundary < len(df) and df.timestamp_utc.iloc[boundary] == df.timestamp_utc.iloc[boundary-1]:
        boundary += 1
    if boundary < 6 or len(df) - boundary < 2:
        raise ValueError('Недостаточно данных: нужны минимум 6 обучающих и 2 проверочных измерения')
    info = dict(method='chronological', training_measurements=boundary,
                evaluation_measurements=len(df)-boundary,
                training_last_utc=df.timestamp_utc.iloc[boundary-1].isoformat(),
                evaluation_first_utc=df.timestamp_utc.iloc[boundary].isoformat())
    return df.iloc[:boundary].copy(), df.iloc[boundary:].copy(), info
