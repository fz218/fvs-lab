#!/usr/bin/env python3
"""Blocked randomized controls, preserving exact commands and per-query audit."""
from pathlib import Path
import argparse
from collections import Counter
import csv
import datetime
import hashlib
import json
import os
import platform
import random
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--experiment-id', default='adaptive-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
p.add_argument('--repeats', type=int, default=3)
p.add_argument('--buckets', nargs='+', default=['low','medium','high'], choices=['low','medium','high'])
p.add_argument('--target', type=float, default=32)
p.add_argument('--ceiling', type=int, default=8192)
p.add_argument('--seed', type=int, default=20261101)
a = p.parse_args()
if a.repeats < 1 or a.target <= 0 or a.ceiling < 320:
    p.error('invalid experiment parameters')
out = ROOT / 'course_runs/optimization' / a.experiment_id
out.mkdir(parents=True, exist_ok=False)
dataset = ROOT / 'datasets/yfcc_course_v1/formal_1000000'
binary = ROOT / 'optimization/build/search_yfcc_adaptive'
if not binary.is_file():
    raise SystemExit('build optimization first')
env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
metadata = {
    'experiment_id': a.experiment_id, 'created_at': datetime.datetime.now().astimezone().isoformat(),
    'repeats': a.repeats, 'buckets': a.buckets, 'seed': a.seed,
    'target': a.target, 'ceiling_L': a.ceiling, 'threads':1,'beamwidth':8,'k':10,
    'io_backend':'aio','full_adj_neighbors':32,'mem_L':0,'cache_budget':0,
    'kernel':platform.platform(),
    'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
    'frequency_source':'base metadata only; no ground truth used by policy',
    'source': json.loads((ROOT/'optimization/build/source_manifest.json').read_text()),
    'ordering':'shuffle all (bucket, policy) pairs separately within each repeat',
    'repeat_note':'same queries, repeated processes; not independent dataset samples',
}
(out/'environment.json').write_text(json.dumps(metadata,indent=2)+'\n')
rows=[]
policies=[('fixed320',320,'fixed'),('fixed_max',a.ceiling,'fixed'),('adaptive',320,'adaptive')]
for repeat in range(1,a.repeats+1):
    cells=[(bucket,*policy) for bucket in a.buckets for policy in policies]
    random.Random(a.seed+repeat).shuffle(cells)
    for order,(bucket,name,l,policy) in enumerate(cells,1):
        run=out/f'r{repeat}-{order:02d}-{bucket}-{name}'
        run.mkdir()
        workload=dataset/'workloads'/bucket
        command=[str(binary),'uint8',str(ROOT/'course_runs/indices/gateann/formal_1000000/yfcc'),
                 '1','8',str(workload/'query.u8bin'),str(dataset/'base.metadata.spmat'),
                 str(workload/'query.metadata.spmat'),str(workload/'ground_truth.ids.ibin'),
                 '10','l2','pq','8','0','0','32',str(l),f'--policy={policy}',
                 f'--target={a.target}',f'--ceiling={a.ceiling}',f'--audit={run / "queries.csv"}']
        record={'repeat':repeat,'order':order,'bucket':bucket,'configuration':name,'command':command,
                'environment_overrides':{'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}}
        (run/'command.json').write_text(json.dumps(record,indent=2)+'\n')
        start=time.perf_counter()
        lines=[]
        with (run/'run.log').open('w') as log:
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                     text=True,env=env)
            for line in process.stdout:
                log.write(line);log.flush();lines.append(line)
            _,status,usage=os.wait4(process.pid,0)
            process.returncode=os.waitstatus_to_exitcode(status)
        record.update(exit_code=process.returncode,elapsed_seconds=time.perf_counter()-start,
                      peak_rss_kib=usage.ru_maxrss)
        (run/'command.json').write_text(json.dumps(record,indent=2)+'\n')
        if process.returncode:
            raise RuntimeError(f'failed run: {run}')
        metrics=[json.loads(line[len('METRIC '):]) for line in lines if line.startswith('METRIC ')]
        init=[json.loads(line[len('INIT '):]) for line in lines if line.startswith('INIT ')]
        if len(metrics)!=1 or len(init)!=1:
            raise RuntimeError(f'missing metrics: {run}')
        audit=list(csv.DictReader((run/'queries.csv').open()))
        labels=list(csv.DictReader((workload/'labels.csv').open()))
        counts={int(x['label_id']):int(x['base_match_count']) for x in labels}
        assert len(audit)==200 and Counter(int(q['label_id']) for q in audit)=={int(x['label_id']):40 for x in labels}
        for q in audit:
            assert int(q['match_count'])==counts[int(q['label_id'])]
            assert abs(float(q['selectivity'])-int(q['match_count'])/1000000)<1e-10
            assert 320<=int(q['effective_L'])<=a.ceiling
        latencies=sorted(float(q['latency_us']) for q in audit)
        m=metrics[0]
        assert abs(m['recall_percent']-statistics.mean(float(q['recall_percent']) for q in audit))<1e-6
        assert abs(m['mean_ios']-statistics.mean(float(q['logical_ios']) for q in audit))<1e-6
        row={'repeat':repeat,'order':order,'bucket':bucket,'configuration':name,**m,**init[0],
             'p50_latency_us':statistics.median(latencies),'p95_latency_us':latencies[189],
             'peak_rss_kib':usage.ru_maxrss,'elapsed_seconds':record['elapsed_seconds'],
             'query_count':len(audit),'mean_valid_results':statistics.mean(int(q['valid_results']) for q in audit),
             'raw_log':str((run/'run.log').relative_to(ROOT))}
        rows.append(row)
        with (out/'results.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(row));writer.writeheader();writer.writerows(rows)
        print(json.dumps({k:row[k] for k in ['repeat','order','bucket','configuration','recall_percent','mean_latency_us','mean_ios','mean_L'] }),flush=True)
print('OPTIMIZATION_EXPERIMENT_PASS',out,flush=True)

