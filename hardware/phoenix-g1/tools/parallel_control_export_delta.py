#!/usr/bin/env python3
import pcbnew as p,json,hashlib,os
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel';s=p.LoadBoard(str(D/'baseline/source.kicad_pcb'));b=p.LoadBoard(str(D/'ground-returns-three.kicad_pcb'));old={t.m_Uuid.AsString() for t in s.GetTracks()};tracks=[]
for t in b.GetTracks():
 if t.m_Uuid.AsString() in old:continue
 assert not isinstance(t,p.PCB_VIA)
 tracks.append({'uuid':t.m_Uuid.AsString(),'net':t.GetNetname(),'layer':b.GetLayerName(t.GetLayer()),'width_mm':p.ToMM(t.GetWidth()),'start_mm':[p.ToMM(t.GetStart().x),p.ToMM(t.GetStart().y)],'end_mm':[p.ToMM(t.GetEnd().x),p.ToMM(t.GetEnd().y)]})
refs=[]
for stem in ['ground-returns','ground-returns-two','ground-returns-three']:refs.extend(x['pad'] for x in json.loads((D/(stem+'.json')).read_text())['checks'])
r={'baseline_sha256':hashlib.sha256((D/'baseline/source.kicad_pcb').read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256((D/'ground-returns-three.kicad_pcb').read_bytes()).hexdigest(),'tracks':tracks,'checks':[{'from':x,'to':'C435.2'} for x in refs],'assembly_ready':False,'qualification':'Connectivity and differential DRC only; decoupling loop inductance and final power integrity remain unqualified.'}
(D/'delta.json').write_text(json.dumps(r,indent=2)+'\n');print(len(tracks),len(refs),flush=True);os._exit(0)
