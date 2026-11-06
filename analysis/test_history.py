import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import pandas as pd
from analysis.data_quality import load_period, chronological_split
from analysis.features import engineer_features
from analysis.statistical import detect_statistical
from analysis.isolation import train_model, predict_anomalies
from analysis.history import attach_predictions, summarize_history
from analysis.html_report import prepare_html_data
from analysis.report import build_report


class HistoryTest(unittest.TestCase):
    def test_history_and_no_training_predictions(self):
        df = pd.DataFrame(dict(timestamp_utc=pd.date_range('2026-11-05T23:58:00Z',periods=30,freq='10s'),
                               elapsed_ms=list(range(20))+list(range(10)),players_online=1,
                               mspt_avg=[2]*8+[80]+[2]*21,tps_1m=20))
        with tempfile.TemporaryDirectory() as folder:
            paths=[]
            for day,g in df.groupby(df.timestamp_utc.dt.date):
                path=Path(folder)/f'{day}.csv';g.to_csv(path,index=False);paths.append(path)
            full=detect_statistical(engineer_features(load_period(paths)))
            train,test,split=chronological_split(full)
            model=train_model(train);pred=predict_anomalies(model,test)
            history=attach_predictions(full,pred)
            self.assertTrue(history.loc[train.index,'ml_anomaly'].isna().all())
            pd.testing.assert_series_equal(history.loc[pred.index,'anomaly_score'],pred.anomaly_score)
            self.assertEqual(history.session_id.nunique(),2)  # Midnight is not a restart.
            self.assertEqual(len(history),30)
            summary=summarize_history(history,pred,scope='pilot_full')
            self.assertEqual(summary['mspt_avg_max'],80)
            self.assertEqual(summary['stat_anomalies'],1)
            self.assertEqual(summary['stat_evaluable_measurements'],18)
            self.assertEqual(len(summary['performance_events']['episodes']),2)
            self.assertEqual(summary['ml_boundary']['timestamp_utc'],pred.timestamp_utc.iloc[0].isoformat())
            report=build_report(pred);report['full_period']=summary
            payload=prepare_html_data(history,report)
            self.assertEqual(len(payload['points']),30)
            self.assertIsNone(payload['points'][0]['ml_anomaly'])
            self.assertEqual(len(payload['events']),2)  # TRAIN events are retained.
            changed=full.copy();changed.loc[test.index,'mspt_avg']=999
            causal=detect_statistical(engineer_features(changed))
            pd.testing.assert_series_equal(causal.loc[train.index,'rolling_threshold'],full.loc[train.index,'rolling_threshold'])
            missing=pred.copy();missing['anomaly_score']=float('nan')
            self.assertIsNone(summarize_history(history,missing,scope='pilot_full')['ml_boundary'])
            # Both CLI modes keep separate training/evaluation semantics.
            for inputs,n,scope in [(['--pilot-files',*map(str,paths)],30,'pilot_full'),
                                   ([str(paths[0]),str(paths[1])],len(pd.read_csv(paths[1])),'evaluation_only')]:
                out=Path(folder)/'out.json';html=Path(folder)/'out.html'
                subprocess.run([sys.executable,'-m','analysis.analyze',*inputs,'--no-show','--json',str(out),'--html',str(html)],check=True,capture_output=True)
                r=json.loads(out.read_text(encoding='utf8'))
                self.assertEqual(r['full_period']['measurements'],n)
                self.assertEqual(r['full_period']['scope'],scope)

    def test_gaps_and_source_links(self):
        with tempfile.TemporaryDirectory() as folder:
            df=pd.DataFrame(dict(timestamp_utc=['2026-11-05T23:59:50Z','2026-11-06T00:00:00Z','2026-11-06T00:02:00Z'],elapsed_ms=[0,10000,130000],players_online=0,mspt_avg=80,tps_1m=20))
            paths=[]
            for i,part in enumerate([df.iloc[:1],df.iloc[1:]]):
                p=Path(folder)/f'{i}.csv';part.to_csv(p,index=False);paths.append(p)
            full=detect_statistical(engineer_features(load_period(paths)))
            full['anomaly_score']=0.;full['ml_anomaly']=False
            result=summarize_history(full,full,scope='pilot_full')
            self.assertEqual(full.session_id.nunique(),1)
            self.assertEqual(full.source_file.nunique(),2)
            self.assertEqual(full.csv_row.tolist(),[2,2,3])
            episodes=result['performance_events']['episodes']
            self.assertEqual(len(episodes),6)  # File boundary and long gap split both signals.
