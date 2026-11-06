"""Deterministic presentation episodes and whole-history health, independent of ML fitting."""
import numpy as np
import pandas as pd

if __package__:
    from .explanations import explain_episode
else:
    from explanations import explain_episode


ELEVATED_MSPT = 25
HIGH_MSPT = 50
LOW_TPS = 19

def runs(df, mask, *, max_gap_seconds=30, split_online=False, signal_keys=None):
    """Consecutive matching observations only. No normal-row bridging."""
    groups, active, previous = [], [], None
    previous_key = None
    for pos in range(len(df)):
        row = df.iloc[pos]
        t = row.timestamp_utc
        valid = bool(mask.iloc[pos]) and pd.notna(t) and pd.notna(row.session_id)
        split = previous is None
        if previous is not None:
            gap = (t - previous.timestamp_utc).total_seconds()
            split = row.session_id != previous.session_id or gap < 0 or gap > max_gap_seconds
            if split_online:
                split |= (row.players_online == 0) != (previous.players_online == 0)
        if signal_keys is not None and previous is not None:
            split |= signal_keys[pos] != previous_key
        if not valid or split:
            if active:
                groups.append(active)
            active = []
        if valid:
            active.append(pos)
        previous = row if valid else None
        previous_key = signal_keys[pos] if signal_keys is not None else None
    if active:
        groups.append(active)
    return groups


def summarize(df, positions):
    part = df.iloc[positions]
    first, last = part.iloc[0], part.iloc[-1]
    context = {}
    for col in ['entities_delta', 'loaded_chunks_delta', 'gc_count_delta', 'gc_time_delta_ms']:
        values = pd.to_numeric(part.get(col, pd.Series(dtype=float)), errors='coerce')
        values = values[np.isfinite(values)]
        if col.startswith('gc_'):
            values = values[values >= 0]
        context[col] = dict(available=int(len(values)), sum=float(values.sum()) if len(values) else None,
                            max_positive_delta=float(max(0,values.max())) if len(values) else None)
    online = pd.to_numeric(part.players_online, errors='coerce').dropna()
    return dict(start_utc=first.timestamp_utc.isoformat(), last_observed_utc=last.timestamp_utc.isoformat(),
                session_id=int(first.session_id), measurements=len(part), single_observation=len(part)==1,
                observed_span_seconds=None if len(part)==1 else (last.timestamp_utc-first.timestamp_utc).total_seconds(),
                peak_mspt=float(part.mspt_avg.max()), min_tps=float(part.tps_1m.min()),
                mean_mspt=float(part.mspt_avg.mean()), players_min=float(online.min()) if len(online) else None,
                players_max=float(online.max()) if len(online) else None, context=context,
                source_records=[dict(source_file=row.get('source_file'),csv_row=int(row.get('csv_row',pos+2))) for pos,(_,row) in zip(positions,part.iterrows())])


def build_insights(df, *, elevated_mspt=ELEVATED_MSPT, high_mspt=HIGH_MSPT, low_tps=LOW_TPS, max_gap_seconds=30):
    if not 0 <= elevated_mspt < high_mspt or low_tps < 0 or max_gap_seconds <= 0:
        raise ValueError('Invalid insight thresholds')
    masks = dict(high_mspt=df.mspt_avg.ge(high_mspt),
                 elevated_mspt=df.mspt_avg.ge(elevated_mspt) & df.mspt_avg.lt(high_mspt), low_tps=df.tps_1m.lt(low_tps))
    displayed = []
    for signal, mask in masks.items():
        # Preserve per-file references for existing event cards/explanations.
        for positions in runs(df,mask,max_gap_seconds=max_gap_seconds):
            for _, sub in (df.iloc[positions].groupby('source_file',sort=False,dropna=False) if 'source_file' in df else [(None,df.iloc[positions])]):
                indices=[p for p in positions if df.index[p] in sub.index]
                item=summarize(df,indices)
                item.update(signal=signal,source_file=sub.iloc[0].get('source_file'),source_rows=[r['csv_row'] for r in item['source_records']])
                item["explanation"]=explain_episode(df,item)
                if signal != 'low_tps':
                    label='Высокий MSPT' if signal=='high_mspt' else 'Повышенный MSPT'
                    fact=f'{label}. Пиковый MSPT — {item["peak_mspt"]:.2f} мс; минимальный TPS — {item["min_tps"]:.2f}.'
                    item['explanation']['observed_facts'][0]=fact
                    item['explanation']['description']=fact
                displayed.append(item)
    ml = df.get('ml_anomaly',pd.Series(False,index=df.index)).eq(True)
    if 'anomaly_score' in df:
        ml &= np.isfinite(pd.to_numeric(df.anomaly_score,errors='coerce'))
    episodes=[]
    keys=list(zip(df.mspt_avg.ge(elevated_mspt).astype(int)+df.mspt_avg.ge(high_mspt).astype(int),df.tps_1m.lt(low_tps)))
    for positions in runs(df,ml,max_gap_seconds=max_gap_seconds,split_online=True,signal_keys=keys):
        item=summarize(df,positions)
        item['threshold_signal']=bool(any(mask.iloc[positions].any() for mask in masks.values()))
        facts=[]; checks=[]
        for col,label in [('entities_delta','сущностей'),('loaded_chunks_delta','загруженных чанков')]:
            value=item['context'][col]['sum']
            peak=item['context'][col]['max_positive_delta']
            if value is not None and (value != 0 or peak > 0):
                facts.append(f'Сумма знаковых изменений числа {label}: {value:g}.')
                facts.append(f'Максимальный положительный интервальный прирост числа {label}: {peak:g}.')
                if peak > 0:
                    checks.append(f'Сопоставьте изменение числа {label} с действиями на сервере в это время.')
        item.update(observed_facts=facts, suggested_checks=checks,
                    limitation='Совпадение показателей не устанавливает причину. Охват наблюдений не равен длительности лага; интервальные приросты могут начинаться до периода, неизвестные значения не заменяются нулями.')
        episodes.append(item)
    # Lexicographic priority, not a lag severity score. ML count is deliberately excluded.
    def rank(e):
        change=sum(max(abs(e['context'][c]['sum'] or 0),e['context'][c]['max_positive_delta'] or 0) for c in ['entities_delta','loaded_chunks_delta'])
        return (-int(e['threshold_signal']),e['min_tps'],-e['peak_mspt'],-(e['observed_span_seconds'] or 0),-change,-(e['context']['gc_time_delta_ms']['sum'] or 0),e['start_utc'])
    episodes.sort(key=rank)
    return dict(ml_episodes=episodes,display_performance_events=displayed,
                rules=dict(elevated_mspt=elevated_mspt,high_mspt=high_mspt,low_tps=low_tps,max_gap_seconds=max_gap_seconds,normal_rows_bridged=0))


def performance_health(df, *, min_samples=6, min_observed_seconds=30, red_span_seconds=60, max_gap_seconds=30):
    result=dict(state='UNKNOWN',label='Недостаточно данных',reason='Недостаточно соседних наблюдений для оценки.', supported_seconds=0.,problem_measurements=0,problem_fraction=None)
    if len(df)<min_samples:
        return result
    valid=np.isfinite(df[['mspt_avg','tps_1m']]).all(axis=1)&df.mspt_avg.ge(0)&df.tps_1m.ge(0)
    if not valid.all():
        return result
    dt=df.timestamp_utc.diff().dt.total_seconds()
    edges=dt.where(df.session_id.eq(df.session_id.shift())&dt.gt(0)&dt.le(max_gap_seconds),0)
    result['supported_seconds']=float(edges.sum())
    if edges.sum()<min_observed_seconds:
        return result
    problem=df.mspt_avg.ge(ELEVATED_MSPT)|df.tps_1m.lt(LOW_TPS)
    severe=df.mspt_avg.ge(HIGH_MSPT)|df.tps_1m.lt(LOW_TPS)
    red=False
    for group in runs(df,severe,max_gap_seconds=max_gap_seconds):
        part=df.iloc[group];span=(part.timestamp_utc.iloc[-1]-part.timestamp_utc.iloc[0]).total_seconds()
        if len(part)>=3 and span>=red_span_seconds and (part.tps_1m.lt(15)|part.mspt_avg.ge(100)).any():
            red=True
    result.update(problem_measurements=int(problem.sum()),problem_fraction=float(problem.mean()))
    state='RED' if red else 'YELLOW' if problem.any() else 'GREEN'
    result.update(state=state,label={'GREEN':'Стабильная работа','YELLOW':'Обнаружены просадки','RED':'Серьёзные просадки'}[state],reason={'GREEN':'В доступных измерениях нет пороговых сигналов MSPT/TPS. Это не гарантия отсутствия лагов.','YELLOW':'Есть измерения повышенного MSPT или сниженного TPS; длительные тяжёлые просадки не подтверждены.','RED':'Есть последовательность тяжёлых наблюдений с охватом не менее минуты; точная длительность лагов неизвестна.'}[state])
    return result
