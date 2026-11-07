"""Isolated sequential Paper smoke tests. Never accepts or writes Minecraft EULA."""
import argparse
import csv
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

ROOT = Path(r"C:\Users\Admin\Desktop\Development\TickSense-Compatibility")
REPO = Path(__file__).resolve().parents[1]
BUILDS = json.loads(Path(__file__).with_name("paper-builds.json").read_text())
FIELDS = 'timestamp_utc,elapsed_ms,tps_1m,mspt_avg,players_online,jvm_heap_used_bytes,loaded_chunks,entities_total,block_entities_total,jvm_heap_committed_bytes,gc_collection_count,gc_collection_time_ms'.split(',')
ERRORS = re.compile(r'NoSuchMethodError|NoClassDefFoundError|UnsupportedClassVersionError|IllegalPluginAccessException|Asynchronous .*|Metrics collection stopped|CSV shutdown exceeded|Dropped snapshots|Session dropped snapshots|Exception.*TickSense|Error occurred while (?:enabling|disabling) TickSense|Could not load.*TickSense', re.I)


class ProcessStillAlive(BaseException):
    """A fatal safety stop: never start the next server in this condition."""


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            value.update(block)
    return value.hexdigest()


def safe_dir(path):
    if path.is_symlink() or path.resolve() != path.absolute():
        raise ValueError(f"Refusing redirected test path: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def download(url, path, expected):
    if path.exists():
        if digest(path) != expected:
            raise ValueError(f"Existing file checksum mismatch, retained: {path}")
        return
    request = urllib.request.Request(url, headers={'User-Agent':'TickSense-Compatibility/0.8.1 (https://github.com/fungluck/TickSense)'})
    # The host and digest are fixed in the manifest, no third-party mirrors.
    with urllib.request.urlopen(request, timeout=90) as response:
        if urllib.parse.urlparse(response.url).hostname != 'fill-data.papermc.io':
            raise ValueError('Unexpected Paper download host')
        with path.open('xb') as output:
            shutil.copyfileobj(response, output)
    if digest(path) != expected:
        raise ValueError(f"Downloaded file checksum mismatch, retained: {path}")


def properties(text):
    return dict(line.split('=',1) for line in text.splitlines() if '=' in line and not line.startswith('#'))


def prepare(build, jar, index, root=ROOT):
    folder = root / ('paper-' + build['version'])
    safe_dir(folder)
    marker = folder / '.ticksense-compatibility'
    if not marker.exists() and any(folder.iterdir()):
        raise ValueError(f"Nonempty unowned directory, retained: {folder}")
    marker.write_text('TickSense compatibility harness\n')
    filename = f"paper-{build['version']}-{build['build']}.jar"
    server = folder / filename
    download(f"https://fill-data.papermc.io/v1/objects/{build['sha256']}/{filename}",server,build['sha256'])
    config = folder / 'server.properties'
    if not config.exists():
        config.write_text(f'server-ip=127.0.0.1\nserver-port={25611+index}\nonline-mode=true\nenable-rcon=false\nenable-query=false\nmax-players=1\nview-distance=2\nsimulation-distance=2\nlevel-name=world\npause-when-empty-seconds=0\nmotd=TickSense isolated compatibility test\n',encoding='utf-8')
    p = properties(config.read_text(encoding='utf-8'))
    for key, value in {'server-ip':'127.0.0.1','online-mode':'true','enable-rcon':'false','enable-query':'false','level-name':'world','server-port':str(25611+index)}.items():
        if p.get(key) != value:
            raise ValueError(f"Unsafe/unexpected {key} in {config}")
    plugins = safe_dir(folder/'plugins')
    existing = list(plugins.glob('*.jar'))
    if any(path.name != jar.name for path in existing):
        raise ValueError(f"Unexpected plugin, retained: {plugins}")
    plugin = plugins/jar.name
    if plugin.exists() and digest(plugin) != digest(jar):
        raise ValueError('Different experimental plugin already installed; no overwrite')
    if not plugin.exists():
        shutil.copy2(jar,plugin)
    return folder, server


def accepted(folder):
    path = folder/'eula.txt'
    return path.is_file() and properties(path.read_text()).get('eula','').strip().lower() == 'true'


def validate_csv(folder):
    files = sorted((folder/'plugins/TickSense/data').glob('metrics-v2-*.csv'))
    rows=[]
    for path in files:
        if not path.read_bytes().endswith(b'\n'):
            raise ValueError(f"Incomplete CSV tail: {path}")
        with path.open(encoding='utf-8', newline='') as f:
            reader=csv.DictReader(f)
            if reader.fieldnames != FIELDS: raise ValueError('CSV header mismatch')
            for row in reader:
                if None in row or any(v is None for v in row.values()): raise ValueError('Malformed CSV record')
                # Instant emits nanoseconds; Python 3.10 accepts at most microseconds.
                # Normalize only the validation copy, never the actual CSV value.
                iso=re.sub(r'(\.\d{6})\d+',r'\1',row['timestamp_utc'].replace('Z','+00:00'))
                timestamp=datetime.fromisoformat(iso)
                if timestamp.utcoffset() is None or timestamp.utcoffset().total_seconds()!=0: raise ValueError('Non-UTC timestamp')
                for field in FIELDS[1:]:
                    value=float(row[field]) if field in ('tps_1m','mspt_avg') else int(row[field])
                    if not __import__('math').isfinite(value): raise ValueError('Nonfinite value')
                    if value < (-1 if field.startswith('gc_') else 0): raise ValueError('Invalid negative counter')
                rows.append(row)
    return files,rows


def run_session(folder, server, java, label, *, plugin_version='0.8.1-compat-test', modern=False):
    log=folder/(label+'.console.log')
    if log.exists(): raise ValueError(f"Existing test log retained; do not overwrite {log}")
    with log.open('x',encoding='utf-8') as output:
        process=subprocess.Popen([java,'-Xms256M','-Xmx1024M','-jar',server.name,'--nogui'],cwd=folder,
                                 stdin=subprocess.PIPE,stdout=output,stderr=subprocess.STDOUT,text=True,
                                 creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        forced=False
        try:
            deadline=time.monotonic()+240
            while time.monotonic()<deadline:
                if process.poll() is not None: raise RuntimeError('Paper exited before ready')
                if 'Done (' in log.read_text(encoding='utf-8',errors='replace'): break
                time.sleep(1)
            else: raise TimeoutError('Paper startup exceeded 240 seconds')
            time.sleep(65 if modern else 45)  # Enough rows for a chronological HTML check on 26.x.
            if process.poll() is not None: raise RuntimeError('Paper exited during collection')
        finally:
            if process.poll() is None:
                try:
                    process.stdin.write('stop\n');process.stdin.flush();process.wait(timeout=60)
                except (OSError,subprocess.TimeoutExpired):
                    forced=True;process.terminate()
                    try: process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        try: process.wait(timeout=15)
                        except subprocess.TimeoutExpired: raise ProcessStillAlive('Previous test process did not stop; abort matrix')
            if process.poll() is None: raise ProcessStillAlive('Previous server is still alive; abort matrix')
    text=log.read_text(encoding='utf-8',errors='replace')
    if forced or process.returncode!=0: raise RuntimeError(f'Non-normal shutdown: forced={forced}, exit={process.returncode}')
    if ERRORS.search(text): raise RuntimeError('Compatibility/collection error in console log')
    if not re.search(r'Enabling TickSense v'+re.escape(plugin_version)+r'(?:\s|$)',text): raise RuntimeError('TickSense enable not observed')
    if 'Disabling TickSense' not in text: raise RuntimeError('TickSense disable not observed')
    world_dirs = ('world',) if modern else ('world','world_nether','world_the_end')
    if not all((folder/name).is_dir() for name in world_dirs):
        raise RuntimeError('Standard world directories not all present')
    return {'status':'PASS','console_log':str(log),'normal_exit':True,'plugin_loaded':True}


def save_report(report, root=ROOT):
    target=safe_dir(root/'results')
    (target/'compatibility-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# TickSense compatibility experiment','', '| Paper | Build | Status | Measurements | Note |','|---|---:|---|---:|---|']
    for result in report['versions']:
        lines.append(f"| {result['version']} | {result['build']} | {result['status']} | {result.get('measurements',0)} | {result.get('reason','')} |")
    lines+=['','Only exact tested builds can receive PASS. Empty-server smoke tests do not prove overhead or controlled chunk/entity workload.']
    (target/'compatibility-summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['Prepare','Run'])
    parser.add_argument('--jar',type=Path,required=True)
    parser.add_argument('--java',default='java')
    parser.add_argument('--series',choices=['1.21','26'],default='1.21')
    parser.add_argument('--resume',action='store_true',help='Reuse only previously recorded normally stopped first runs')
    args=parser.parse_args()
    modern=args.series=='26'
    root=REPO/'.gradle/compat26' if modern else ROOT
    builds=json.loads(Path(__file__).with_name('paper-builds-26.json').read_text()) if modern else BUILDS
    plugin_version='0.8.1-pilot' if modern else '0.8.1-compat-test'
    java_major=25 if modern else 21
    safe_dir(root)
    if args.jar.name!=f'TickSense-{plugin_version}.jar' or not args.jar.is_file(): raise ValueError('Expected TickSense JAR for this matrix')
    java=subprocess.run([args.java,'-version'],capture_output=True,text=True,check=True).stderr.strip()
    if not re.search(rf'version "{java_major}\.',java): raise ValueError(f'Use Java {java_major} for this fixed test matrix')
    report={'generated_utc':datetime.now(timezone.utc).isoformat(),'java':java,'ticksense_sha256':digest(args.jar),'versions':[]}
    previous={}
    old_report=root/'results/compatibility-report.json'
    if args.resume and old_report.is_file():
        old=json.loads(old_report.read_text(encoding='utf-8'))
        if old['ticksense_sha256']!=report['ticksense_sha256']: raise ValueError('Resume plugin SHA mismatch')
        previous={v['version']:v for v in old['versions']}
    # Cross-invocation lock: never run two harnesses against these servers.
    lock=root/'.compatibility.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    os.close(fd)
    abort=False
    try:
        if args.mode=='Run':
            sys.path.insert(0,str(REPO));importlib.import_module('analysis.data')
        for index,build in enumerate(builds):
            result={**build,'ticksense_sha256':report['ticksense_sha256'],'java':java,'measurements':0,'errors':[],'server_start':'NOT TESTED','plugin_load':'NOT TESTED','csv':'NOT TESTED','restart':'NOT TESTED','session_detection':'NOT TESTED','scope':'empty server; standard worlds only','not_tested':['controlled entity/chunk workload','player connections','overhead','UTC day rollover']}
            report['versions'].append(result)
            if abort:
                result.update(status='BLOCKED',reason='Previous test process could not be stopped; no further starts')
                save_report(report,root)
                continue
            try:
                folder,server=prepare(build,args.jar,index,root)
                if not accepted(folder):
                    result.update(status='BLOCKED',reason='Minecraft EULA not accepted; no server started',eula_path=str(folder/'eula.txt'))
                elif args.mode=='Prepare': result.update(status='NOT TESTED',reason='Prepared; Run mode not invoked')
                else:
                    before_files,before=validate_csv(folder)
                    saved=previous.get(build['version'],{})
                    if before:
                        if not args.resume or saved.get('first_run',{}).get('status')!='PASS' or saved.get('build')!=build['build']:
                            raise ValueError('Existing CSV retained; no verified first-run state for resume')
                        result['first_run']=saved['first_run']
                    else:
                        result['first_run']=run_session(folder,server,args.java,'first-run',plugin_version=plugin_version,modern=modern)
                    result['server_start']=result['plugin_load']='PASS'
                    files,first=validate_csv(folder)
                    if len(first)<3: raise ValueError('Fewer than 3 initial measurements')
                    result['second_run']=run_session(folder,server,args.java,'second-run',plugin_version=plugin_version,modern=modern)
                    files,all_rows=validate_csv(folder)
                    if len(all_rows)-len(first)<3: raise ValueError('Fewer than 3 appended measurements')
                    if modern:
                        period = importlib.import_module('analysis.data_quality').load_period(files)
                        sessions = int(period.session_id.nunique()) - 1
                    else:
                        loader=importlib.import_module('analysis.data').load_data
                        sessions=sum(int(loader(path).session_id.nunique())-1 for path in files)
                    if sessions<1: raise ValueError('Analyzer did not detect an elapsed_ms reset')
                    result.update(status='PASS',csv='PASS',restart='PASS',session_detection='PASS',measurements=len(all_rows),csv_files=[str(p) for p in files],reason='Two sequential empty-server sessions completed')
                    if modern:
                        html=folder/'report.html'
                        subprocess.run([sys.executable,'-m','analysis.analyze','--pilot-files',*map(str,files),
                                        '--html',str(html),'--no-show'],cwd=REPO,check=True,stdout=subprocess.DEVNULL)
                        result['html']='PASS'
            except ProcessStillAlive as error:
                abort=True
                result.update(status='BLOCKED',reason=str(error),errors=[str(error)])
            except Exception as error:
                result.update(status='FAIL' if args.mode=='Run' else 'BLOCKED',reason=str(error),errors=[str(error)])
            save_report(report,root)
    finally:
        if not abort: lock.unlink()
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
