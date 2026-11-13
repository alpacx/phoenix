#!/usr/bin/env python3
"""Uncapped pad-network inventory, independent of the DRC report item limit."""
import pcbnew as p,json,hashlib,collections
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/stacked-expansion';cp=json.loads((R/'working-candidate.json').read_text());src=R/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src));b.BuildConnectivity();conn=b.GetConnectivity();nets=collections.defaultdict(dict)
for f in b.GetFootprints():
 for a in f.Pads():
  if a.GetNetCode()>0:nets[a.GetNetname()][a.m_Uuid.AsString()]=(f.GetReference()+'.'+a.GetNumber(),a)
rows=[]
for net,pads in sorted(nets.items()):
 pending=set(pads);groups=[]
 while pending:
  seed=next(iter(pending));connected={q.m_Uuid.AsString() for q in conn.GetConnectedItems(pads[seed][1])}|{seed};group=pending&connected;pending-=group;groups.append(sorted(pads[k][0] for k in group))
 rows.append({'net':net,'pad_count':len(pads),'connected_groups':sorted(groups),'group_count':len(groups),'fully_connected':len(groups)==1})
report={'status':'PAD_CONNECTIVITY_INVENTORY_NOT_ELECTRICAL_QUALIFICATION','source_sha256':cp['sha256'],'nets_total':len(rows),'multi_pad_nets':sum(r['pad_count']>1 for r in rows),'open_multi_pad_nets':sum(r['group_count']>1 for r in rows),'single_pad_nets_not_proof_of_completion':sum(r['pad_count']==1 for r in rows),'nets':rows,'DRC_cap_not_used':True,'assembly_ready':False};(R/'pcb/connectivity-inventory.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='nets'})
