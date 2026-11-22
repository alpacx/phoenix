#!/usr/bin/env python3
import pcbnew as p,json,hashlib,os
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel';s=p.LoadBoard(str(D/'lcd-dc.kicad_pcb'));b=p.LoadBoard(str(D/'ground-vias.kicad_pcb'));old={t.m_Uuid.AsString() for t in s.GetTracks()};tracks=[]
for t in b.GetTracks():
 if t.m_Uuid.AsString() in old:continue

 tracks.append({'uuid':t.m_Uuid.AsString(),'net':t.GetNetname(),'layer':b.GetLayerName(t.GetLayer()),'width_mm':p.ToMM(t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth()),'via':isinstance(t,p.PCB_VIA),'drill_mm':p.ToMM(t.GetDrillValue()) if isinstance(t,p.PCB_VIA) else None,'start_mm':[p.ToMM(t.GetStart().x),p.ToMM(t.GetStart().y)],'end_mm':[p.ToMM(t.GetEnd().x),p.ToMM(t.GetEnd().y)]})
r={'baseline_sha256':hashlib.sha256((D/'lcd-dc.kicad_pcb').read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256((D/'ground-vias.kicad_pcb').read_bytes()).hexdigest(),'tracks':tracks,'checks':[{'from':ref+'.2','to':'C435.2'} for ref in ['C1670','C1659','C1653','C1648','C1660']],'assembly_ready':False,'qualification':'Ground continuity and DRC only; power integrity not qualified.'}
(D/'ground-vias-delta.json').write_text(json.dumps(r,indent=2)+'\n');print(len(tracks),flush=True);os._exit(0)
