#!/usr/bin/env python3
"""Explicit local VCC2 bypass geometry trial; current/loop qualification remains open."""
import pcbnew as p,json,hashlib,math,shutil,subprocess
from pathlib import Path
from drc_regression import introduced
from pcb_preservation import verify_preservation
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';B=E/'pmic-buck5';cp=json.loads((B/'working-candidate.json').read_text());src=B/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];D=E/'pmic-inputs/pcb';D.mkdir(parents=True,exist_ok=True);out=D/'buck2-input.kicad_pcb';b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};s,t=pads['U4','10'],pads['C422','1'];assert s.GetNetname()==t.GetNetname()=='+3V3_SYS';base=json.loads(src.with_name(src.stem+'-drc.json').read_text());held=[];trials=[];accepted=False
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
shutil.copy2(src.parent/'fp-lib-table',D/'fp-lib-table')
def vec(q):return p.VECTOR2I(*(p.FromMM(v) for v in q))
def xy(q):return p.ToMM(q.GetPosition().x),p.ToMM(q.GetPosition().y)
for vx,vy in [(55.65,10.2),(55.7,10.25),(55.8,10.3),(55.6,10.3),(55.65,10.5)]:
 added=[];vias=[(vx,vy),(vx,vy+.7)];paths=[(p.F_Cu,.127,[xy(s),(55.85,9.35)]),(p.F_Cu,.5,[(55.85,9.35),(vx,9.55),vias[0],vias[1]])]
 paths += [(p.B_Cu,.5,[via,(54.95,via[1]),xy(t)]) for via in vias]
 for layer,width,path in paths:
  for a,z in zip(path,path[1:]):
   if math.dist(a,z)<1e-6:continue
   tr=p.PCB_TRACK(b);tr.SetStart(vec(a));tr.SetEnd(vec(z));tr.SetWidth(p.FromMM(width));tr.SetLayer(layer);tr.SetNetCode(s.GetNetCode());b.Add(tr);added.append(tr)
 for pos in vias:
  v=p.PCB_VIA(b);v.SetPosition(vec(pos));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(s.GetNetCode());b.Add(v);added.append(v)
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'buck2-input-drc.json'),str(out)],check=True,capture_output=True);new=introduced(base,json.loads((D/'buck2-input-drc.json').read_text()));b.BuildConnectivity();connected=t.m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(s)};trials.append({'vias_mm':vias,'new_violations':new,'connected':connected});print('VCC2',vias,'new DRC',len(new),'connected',connected,flush=True)
 if not new and connected:accepted=True;break
 for item in added:b.Remove(item)
 held.extend(added)
report={'status':'VCC2_LOCAL_BYPASS_CONNECTED' if accepted else 'NO_ACCEPTED_VCC2_ROUTE','source_sha256':cp['sha256'],'trials':trials,'electrical_current_and_loop_qualified':False,'assembly_ready':False}
if accepted:report.update(sha256=hashlib.sha256(out.read_bytes()).hexdigest(),preservation=verify_preservation(p.LoadBoard(str(src)),b))
(D/'buck2-input.json').write_text(json.dumps(report,indent=2)+'\n')
