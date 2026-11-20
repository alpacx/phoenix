#!/usr/bin/env python3
import pcbnew as p,json,hashlib,os
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel';s=p.LoadBoard(str(D/'ground-vias.kicad_pcb'));b=p.LoadBoard(str(D/'ram-ground-vias.kicad_pcb'));old={t.m_Uuid.AsString() for t in s.GetTracks()};tracks=[]
for t in b.GetTracks():
 if t.m_Uuid.AsString() in old:continue

 tracks.append({'uuid':t.m_Uuid.AsString(),'net':t.GetNetname(),'layer':b.GetLayerName(t.GetLayer()),'width_mm':p.ToMM(t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth()),'via':isinstance(t,p.PCB_VIA),'drill_mm':p.ToMM(t.GetDrillValue()) if isinstance(t,p.PCB_VIA) else None,'start_mm':[p.ToMM(t.GetStart().x),p.ToMM(t.GetStart().y)],'end_mm':[p.ToMM(t.GetEnd().x),p.ToMM(t.GetEnd().y)]})
r={'baseline_sha256':hashlib.sha256((D/'ground-vias.kicad_pcb').read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256((D/'ram-ground-vias.kicad_pcb').read_bytes()).hexdigest(),'tracks':tracks,'checks':[{'from':ref+'.2','to':'C435.2'} for ref in ['C1666','C1657','C1658','C1667','C1672','C1650','C1664']],'assembly_ready':False,'qualification':'Ground continuity and DRC only; power integrity not qualified.'}
# Preserve source UUIDs, applying the integrated assembly-clearance correction.
for t in r['tracks']:
 for key in ['start_mm','end_mm']:
  for old,new in [([23.8,20.5],[23.3,20.6]),([23.3,17],[23.15,17])]:
   if t[key]==old:t[key]=new
r['geometry_override']='Two via endpoints corrected after source export; candidate_sha256 identifies pre-correction source, not applied geometry. Integrated DRC and pad-clearance audit are authoritative.'
(D/'ram-ground-vias-delta.json').write_text(json.dumps(r,indent=2)+'\n');print(len(tracks),flush=True);os._exit(0)
