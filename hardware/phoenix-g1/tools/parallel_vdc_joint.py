#!/usr/bin/env python3
"""Joint C425/power escapes/VDC experiment; specific sense-neck rule is documented."""
import pcbnew as p,json,hashlib,shutil,subprocess,sys,os
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/vdc-joint-parallel';D.mkdir(exist_ok=True)
S=D.parent/'pmic-ldo-inputs/pcb/parallel-local-copper.kicad_pcb';src=D/'source.kicad_pcb';out=D/'candidate.kicad_pcb'
RULE='\n(rule "RK809 VDC sense pin neck" (condition "A.Type == \'Track\' && A.NetName == \'PMIC_VDC\' && A.intersectsCourtyard(\'U4\')") (constraint track_width (min 0.15mm)))\n'
if not src.exists():
 for ext in ['kicad_pcb','kicad_pro','kicad_dru']:shutil.copy2(S.with_suffix('.'+ext),src.with_suffix('.'+ext))
 shutil.copy2(S.parent/'parallel-local-copper-drc.json',D/'source-drc.json');(D/'fp-lib-table').write_text((S.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(S.parent.resolve())))
if '--verify' in sys.argv:
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'drc.json'),str(out)],check=True,capture_output=True)
 a=p.LoadBoard(str(src));b=p.LoadBoard(str(out));b.BuildConnectivity();pads={f.GetReference()+'.'+q.GetNumber():q for f in b.GetFootprints() for q in f.Pads()};new=introduced(json.loads((D/'source-drc.json').read_text()),json.loads((D/'drc.json').read_text()));removed=json.loads((D/'removed.json').read_text());checks=[]
 for aa,zz in [('U4.61','R410.2'),('U4.59','L405.2'),('U4.57','C425.1'),('C481.1','R410.1')]:checks.append({'from':aa,'to':zz,'connected':pads[zz].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[aa])}})
 r={'status':'GEOMETRY_ACCEPTED' if not new and all(c['connected'] for c in checks) else 'REJECTED','source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'new_violations':new,'checks':checks,'preservation':verify_preservation(a,b,replaced_copper=removed),'assembly_ready':False,'electrical_power_and_thermal_qualification':False}
 (D/'checkpoint.json').write_text(json.dumps(r,indent=2)+'\n');print(r['status'],len(new),checks,flush=True);os._exit(0)
b=p.LoadBoard(str(src));fs={f.GetReference():f for f in b.GetFootprints()};fs['C425'].SetPosition(p.VECTOR2I(p.FromMM(59.35),p.FromMM(3.325)));removed=[];held=[]
def xy(v):return (round(p.ToMM(v.x),6),round(p.ToMM(v.y),6))
for t in list(b.GetTracks()):
 if isinstance(t,p.PCB_VIA):continue
 a,z=xy(t.GetStart()),xy(t.GetEnd());net=t.GetNetname();take=False
 if net=='+1V8_SYS' and t.GetLayer()==p.F_Cu and min(a[0],z[0])>=59.3 and min(a[1],z[1])>=2.65 and max(a[1],z[1])<=4.9:take=True
 if net=='+3V3_SYS' and t.GetLayer()==p.F_Cu and (a,z) in [((61.05,4.95),(60.4,4.3)),((60.4,4.3),(60.4,3.7))]:take=True
 if net=='+3V3_SYS' and t.GetLayer()==p.B_Cu and (a,z) in [((58.8,4.3),(59.1,4.8)),((59.1,4.8),(60.48,4.8)),((60.48,4.8),(60.48,4.0))]:take=True
 if take:removed.append(t.m_Uuid.AsString());b.Remove(t);held.append(t)
def route(net,w,pts,layer):
 for a,z in zip(pts,pts[1:]):
  t=p.PCB_TRACK(b);t.SetNetCode(b.GetNetcodeFromNetname(net));t.SetLayer(layer);t.SetWidth(p.FromMM(w));t.SetStart(p.VECTOR2I(*(p.FromMM(v) for v in a)));t.SetEnd(p.VECTOR2I(*(p.FromMM(v) for v in z)));b.Add(t)
def via(pt):
 v=p.PCB_VIA(b);v.SetPosition(p.VECTOR2I(*(p.FromMM(x) for x in pt)));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname('PMIC_VDC'));b.Add(v)
route('+1V8_SYS',.2,[(59.3,2.65),(59.3,4.35),(60.3,4.35),(60.3,4.9)],p.F_Cu)
route('+3V3_SYS',.3,[(61.05,4.95),(61.05,4)],p.F_Cu)
route('+3V3_SYS',.3,[(58.8,4.3),(58.8,5.5),(60.48,5.5),(60.48,4)],p.B_Cu)
route('PMIC_VDC',.15,[(59.65,5.59),(59.65,4.89)],p.F_Cu);via((59.65,4.89));via((57.15,6.4))
route('PMIC_VDC',.2,[(59.65,4.89),(58.66,4.89),(57.15,6.4)],p.In3_Cu)
route('PMIC_VDC',.2,[(57.15,6.4),(57.15,6.34),(57.49,6)],p.B_Cu)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
out.with_suffix('.kicad_dru').write_text(src.with_suffix('.kicad_dru').read_text()+RULE)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);(D/'removed.json').write_text(json.dumps(removed));os.execv(sys.executable,[sys.executable,__file__,'--verify'])
