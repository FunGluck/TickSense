import unittest
import pandas as pd
from analysis.event_insights import build_insights, performance_health


class InsightsTest(unittest.TestCase):
    def frame(self, mspt, tps=None):
        n=len(mspt)
        return pd.DataFrame(dict(timestamp_utc=pd.date_range('2026-01-01',periods=n,freq='10s',tz='UTC'),session_id=1,
                                 players_online=1,mspt_avg=mspt,tps_1m=tps or [20]*n,source_file='test.csv',csv_row=range(2,n+2),
                                 ml_anomaly=True,anomaly_score=-.1))

    def test_exclusive_levels_and_boundaries(self):
        df=self.frame([24.9,25,49.9,50,100])
        r=build_insights(df)
        high=[e for e in r['display_performance_events'] if e['signal']=='high_mspt']
        elevated=[e for e in r['display_performance_events'] if e['signal']=='elevated_mspt']
        self.assertEqual(high[0]['source_rows'],[5,6]);self.assertEqual(elevated[0]['source_rows'],[3,4])
        with self.assertRaises(ValueError):build_insights(df,high_mspt=20)

    def test_group_boundaries_and_missing_context(self):
        df=self.frame([2]*10);df['ml_anomaly']=df.ml_anomaly.astype(object);df.loc[:1,'ml_anomaly']=None;df.loc[4,'ml_anomaly']=False
        df.loc[7:,'session_id']=2
        r=build_insights(df)['ml_episodes'];self.assertEqual(sorted(e['measurements'] for e in r),[2,2,3])
        self.assertIsNone(r[0]['context']['entities_delta']['sum'])
        self.assertEqual(sum(e['measurements'] for e in r),7)
        df.loc[3:,'timestamp_utc']+=pd.Timedelta(seconds=60)
        self.assertEqual(len(build_insights(df)['ml_episodes']),4)

    def test_context_ranking_and_immutable(self):
        df=self.frame([2,2,2,2,80,80]);df.loc[3,'ml_anomaly']=False
        df['entities_delta']=[None,4,-2,None,16000,0];df['gc_time_delta_ms']=[-1,3,4,-1,5,6]
        copy=df.copy(deep=True);r=build_insights(df)['ml_episodes']
        self.assertEqual(r[0]['peak_mspt'],80);self.assertEqual(r[0]['context']['entities_delta']['sum'],16000)
        self.assertEqual(r[0]['context']['gc_time_delta_ms']['sum'],11)
        self.assertTrue(r[0]['suggested_checks']);pd.testing.assert_frame_equal(df,copy)

    def test_health_scenarios(self):
        self.assertEqual(performance_health(self.frame([2]*20))['state'],'GREEN')
        self.assertEqual(performance_health(self.frame([2]*10+[120]+[2]*9))['state'],'YELLOW')
        self.assertEqual(performance_health(self.frame([30,2]*10))['state'],'YELLOW')
        self.assertEqual(performance_health(self.frame([110]*8,[10]*8))['state'],'RED')
        self.assertEqual(performance_health(self.frame([110]*2,[10]*2))['state'],'UNKNOWN')
        # ML count does not change health; gaps cannot turn isolated observations into RED.
        df=self.frame([110]*8,[10]*8);df['timestamp_utc']=pd.date_range('2026-01-01',periods=8,freq='40s',tz='UTC')
        self.assertEqual(performance_health(df)['state'],'UNKNOWN')
        a=self.frame([2]*20);b=a.copy();b['ml_anomaly']=False
        self.assertEqual(performance_health(a),performance_health(b))

    def test_files_and_health_time_boundaries(self):
        df=self.frame([2]*10);df.loc[5:,'source_file']='next.csv'
        r=build_insights(df)['ml_episodes']
        self.assertEqual(len(r),1)
        self.assertEqual({x['source_file'] for x in r[0]['source_records']},{'test.csv','next.csv'})
        self.assertEqual(performance_health(self.frame([110]*6,[10]*6))['state'],'YELLOW')
        self.assertEqual(performance_health(self.frame([110]*7,[10]*7))['state'],'RED')
        df=self.frame([50]*7,[18]*7)
        self.assertEqual(performance_health(df)['state'],'YELLOW')  # No strong (<15 TPS / >=100 ms) observation.
        events=build_insights(df)['display_performance_events']
        self.assertEqual({e['signal'] for e in events},{'high_mspt','low_tps'})
