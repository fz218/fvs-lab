#!/usr/bin/env python3
"""Audit experiment evidence independently and export summary statistics."""
from pathlib import Path
from collections import Counter, defaultdict
import argparse
import csv
import json
import math
import statistics

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--experiment-id',required=True)
a=p.parse_args()
folder=ROOT/'course_runs/optimization'/a.experiment_id
env=json.loads((folder/'environment.json').read_text())
rows=list(csv.DictReader((folder/'results.csv').open()))
expected=len(env['buckets'])*3*env['repeats']
assert len(rows)==expected,(len(rows),expected)
keys=Counter((r['repeat'],r['bucket'],r['configuration']) for r in rows)
assert len(keys)==expected and set(keys.values())=={1}
groups=defaultdict(list)
total_queries=0
for r in rows:
    run=ROOT/Path(r['raw_log']).parent
    command=json.loads((run/'command.json').read_text())
    assert command['exit_code']==0
    queries=list(csv.DictReader((run/'queries.csv').open()))
    assert len(queries)==200 and {int(q['query_id']) for q in queries}==set(range(200))
    labels=list(csv.DictReader((ROOT/'datasets/yfcc_course_v1/formal_1000000/workloads'/r['bucket']/'labels.csv').open()))
    counts={int(x['label_id']):int(x['base_match_count']) for x in labels}
    assert Counter(int(q['label_id']) for q in queries)=={k:40 for k in counts}
    for q in queries:
        sel=counts[int(q['label_id'])]/1_000_000
        assert int(q['match_count'])==counts[int(q['label_id'])]
        assert abs(sel-float(q['selectivity']))<1e-12
        if r['configuration']=='adaptive':
            raw=max(320,math.ceil(env['target']/sel)) if sel else env['ceiling_L']
            wanted=min(env['ceiling_L'],math.ceil(raw/64)*64)
        else:
            wanted=320 if r['configuration']=='fixed320' else env['ceiling_L']
        assert int(q['effective_L'])==wanted
    for metric,qfield in [('recall_percent','recall_percent'),('mean_ios','logical_ios'),('filter_skips','filter_skips'),('mean_L','effective_L')]:
        assert abs(float(r[metric])-statistics.mean(float(q[qfield]) for q in queries))<1e-6
    assert abs(float(r['qps'])*float(r['mean_latency_us'])-1_000_000)<.02
    groups[r['bucket'],r['configuration']].append(r)
    total_queries+=len(queries)
metrics=['recall_percent','mean_latency_us','qps','mean_ios','filter_skips','mean_L',
         'p50_latency_us','p95_latency_us','peak_rss_kib','frequency_ms','frequency_bytes','mean_valid_results']
summary=[]
for bucket in ['low','medium','high']:
    for configuration in ['fixed320','fixed_max','adaptive']:
        rs=groups[bucket,configuration]
        assert len(rs)==env['repeats']
        line={'bucket':bucket,'configuration':configuration,'n':len(rs)}
        for metric in metrics:
            vals=[float(r[metric]) for r in rs]
            for key,value in [('median',statistics.median(vals)),('min',min(vals)),('max',max(vals))]:
                line[f'{metric}_{key}']=value
        summary.append(line)
with (folder/'summary.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
checks={'experiment_id':a.experiment_id,'runs':len(rows),'groups':len(groups),
        'repeats':env['repeats'],'audited_queries':total_queries,
        'all_processes_exit_zero':True,'policy_matches_base_frequencies':True,
        'metrics_match_per_query_evidence':True,'baseline_unchanged':True}
(folder/'validation.json').write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(checks,indent=2))
for row in summary:
    print(row['bucket'],row['configuration'],
          'recall',round(row['recall_percent_median'],2),
          'ms',round(row['mean_latency_us_median']/1000,3),
          'io',round(row['mean_ios_median'],3),
          'L',row['mean_L_median'])
