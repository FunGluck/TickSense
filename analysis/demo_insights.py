"""Generate four synthetic health demonstrations locally, never real Pilot data."""
import argparse
from pathlib import Path
import subprocess
import sys
import pandas as pd


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args();args.directory.mkdir(parents=True,exist_ok=True)
    for name,mspt,tps,n in [('GREEN',3,20,80),('YELLOW',30,20,80),('RED',110,10,80),('UNKNOWN',3,20,3)]:
        df=pd.DataFrame(dict(timestamp_utc=pd.date_range('2026-01-01',periods=n,freq='10s',tz='UTC'),
                             elapsed_ms=[i*10000 for i in range(n)],mspt_avg=mspt,tps_1m=tps,players_online=1))
        csv=args.directory/(name+'.csv');df.to_csv(csv,index=False)
        # Separate-file mode permits a small UNKNOWN history without weakening Pilot minimums.
        subprocess.run([sys.executable,'-m','analysis.analyze',str(csv),str(csv), '--html',str(args.directory/(name+'.html')),
                        '--json',str(args.directory/(name+'.json')),'--no-show'],check=True,stdout=subprocess.DEVNULL)


if __name__=='__main__':
    main()

