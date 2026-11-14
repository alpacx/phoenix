#!/usr/bin/env python3
"""Bounded SWOUT1 escape search; source is never overwritten."""
import pcbnew as p,json,subprocess,shutil,hashlib
from pathlib import Path
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-buck5/pcb';src=D/'feedback.kicad_pcb';out=D/'io-escape.kicad_pcb';b=p.LoadBoard(str(src));base=json.loads((D/'feedback-drc.json').read_text());held=[]
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
old=p.VECTOR2I(p.FromMM(61.75),p.FromMM(4.65));items=[]
for t in b.GetTracks():
 if t.GetNetname()=='+3V3_IO' and (t.GetStart()==old or t.GetEnd()==old):items.append((t,t.GetStart()==old,t.GetEnd()==old))
assert len(items)==4
trials=[];accepted=False
for x,y in [(61.4,4.65),(61.4,4.4),(61.75,4.0),(61.7,3.8),(61.5,4.2),(61.4,4.0),(61.25,4.5),(61.25,4.25)]:
 pos=p.VECTOR2I(p.FromMM(x),p.FromMM(y))
 for t,start,end in items:
  if isinstance(t,p.PCB_VIA):t.SetPosition(pos)
  else:
   if start:t.SetStart(pos)
   if end:t.SetEnd(pos)
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'io-escape-drc.json'),str(out)],check=True,capture_output=True)
 new=introduced(base,json.loads((D/'io-escape-drc.json').read_text()));rec={'via':[x,y],'new_violations':new};trials.append(rec);print(x,y,len(new),flush=True)
 if not new:accepted=True;break
(D/'io-escape.json').write_text(json.dumps({'accepted':accepted,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'changed_items':[t.m_Uuid.AsString() for t,_,_ in items],'trials':trials,'assembly_ready':False},indent=2)+'\n')
