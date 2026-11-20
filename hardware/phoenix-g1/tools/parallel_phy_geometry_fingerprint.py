#!/usr/bin/env python3
"""Compare rebuilt routed geometry independent of generated copper UUIDs."""
import json,hashlib,os
from pathlib import Path
import pcbnew as p
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
def fingerprint(path):
 b=p.LoadBoard(str(path));pads=[];tracks=[];footprints=[]
 for f in b.GetFootprints():
  footprints.append((f.GetReference(),f.GetValue(),f.GetFPIDAsString(),tuple(f.GetPosition()),f.GetOrientationDegrees(),f.GetLayer()))
  for q in f.Pads():pads.append((f.GetReference(),q.GetNumber(),q.m_Uuid.AsString(),q.GetNetname(),tuple(q.GetPosition()),tuple(q.GetSize()),q.GetOrientationDegrees(),tuple(q.GetDrillSize())))
 for t in b.GetTracks():
  tracks.append((t.GetClass(),t.GetNetname(),t.GetLayer(),tuple(t.GetStart()),tuple(t.GetEnd()),t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth(),t.GetDrillValue() if isinstance(t,p.PCB_VIA) else 0))
 obj={'pads':sorted(pads),'footprints':sorted(footprints),'tracks':sorted(tracks)};return {'hash':hashlib.sha256(json.dumps(obj,sort_keys=True).encode()).hexdigest(),'pads':len(pads),'footprints':len(footprints),'tracks':len(tracks)}
a=D/'runs/load-in3-c513d/phy-joint.kicad_pcb';z=D/'runs/rebuild-c513d/phy-joint.kicad_pcb';fa=fingerprint(a);fz=fingerprint(z);assert fa==fz;report=json.loads(z.with_name('report.json').read_text());assert not report['new_violations'];assert all(x['connected'] for x in report['checks'])
out={'status':'GEOMETRY_REBUILD_MATCH','reference':str(a),'rebuild':str(z),'geometry_fingerprint':fa,'includes':['footprint ref/value/id/placement/side','pad UUID/net/size/placement/drill','track/via class/net/layer/endpoints/width/drill'],'excludes':['generated copper UUIDs','zone fill polygon serialization'],'rebuild_drc_new_violations':0,'power_layout_accepted':False};(D/'rebuild-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],flush=True);os._exit(0)
