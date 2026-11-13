#!/usr/bin/env python3
"""Draft J3 parallel power bus. No current-rating or modem-load qualification."""
import pcbnew as p,json,math,shutil,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];D=R/'migration-rk3562/experiments/stacked-expansion/pcb';b=p.LoadBoard(str(D/'input-feed.kicad_pcb'));f=next(f for f in b.GetFootprints() if f.GetReference()=='J3');pads={a.GetNumber():a for a in f.Pads()};code=b.FindNet('+5V_ADDON').GetNetCode()
def pt(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
def line(a,z,w):
 t=p.PCB_TRACK(b);t.SetStart(pt(a));t.SetEnd(pt(z));t.SetLayer(p.F_Cu);t.SetWidth(p.FromMM(w));t.SetNetCode(code);b.Add(t)
for i in range(1,9):
 a=pads[str(i)];assert a.GetNetname()=='+5V_ADDON';x,y=p.ToMM(a.GetPosition().x),p.ToMM(a.GetPosition().y);edge=.45 if i%2 else 4.55
 line((x,y),(x,edge),.15)
for y in [.45,4.55]:line((62.5,y),(64.9,y),.3)
line((62.5,.45),(62.5,4.55),.3)
v=p.PCB_VIA(b);v.SetPosition(pt((62.5,2.0)));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(code);b.Add(v)
p.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();reached={q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(v)}
for i in range(1,9):assert pads[str(i)].m_Uuid.AsString() in reached
out=D/'output-bus.kicad_pcb';p.SaveBoard(str(out),b)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(D/f'candidate.{ext}',out.with_suffix('.'+ext))
with out.with_suffix('.kicad_dru').open('a') as o:o.write('''\n(rule "Accessory connector power fingers" (condition "A.NetName == '+5V_ADDON'") (constraint track_width (min 0.15mm)))\n''')
(D/'output-bus.json').write_text(json.dumps({'status':'BUS_CONTINUITY_CHECKED_DRC_PENDING','pins':list(range(1,9)),'root_via_mm':[62.5,2.0],'finger_width_mm':.15,'bus_width_mm':.3,'current_rating_qualified':False,'efuse_output_connected':False,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'assembly_ready':False},indent=2)+'\n')
