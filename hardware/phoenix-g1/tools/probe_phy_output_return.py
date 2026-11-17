#!/usr/bin/env python3
"""Widen C511 ground branch, retain its via and add a second ground via."""
import json,hashlib,tempfile,shutil,sys,os,subprocess
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
S=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-compact-inductor'
if '--audit' in sys.argv:
 m=json.loads(Path(sys.argv[-1]).read_text());src=Path(m['source']);out=Path(m['candidate']);drc=out.parent/'drc.json'
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
 raw=json.loads(drc.read_text());new=introduced(json.loads((src.parent/'drc.json').read_text()),raw);ids={i for r in new for i in r['items']};m.update(new_violations=new,details=[r for r in raw['violations'] if any(i['uuid'] in ids for i in r['items'])],status='OUTPUT_RETURN_REJECTED',assembly_ready=False)
 if not new:
  original=p.LoadBoard(str(src));candidate=p.LoadBoard(str(out));m['preservation']=verify_preservation(original,candidate,replaced_copper=m['changed']);m['status']='OUTPUT_RETURN_GEOMETRY_PASSED'
 (S/'output-return-probe.json').write_text(json.dumps(m,indent=2)+'\n');print(m['status'],flush=True);os._exit(0)
proof=json.loads((S/'bulk-return-probe.json').read_text());assert proof['status']=='BULK_RETURN_GEOMETRY_PASSED';src=Path(proof['candidate']);assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['candidate_sha256']
g=json.loads((S.parent/'pmic-ldo-inputs/pcb/phy-compact-0603-ground-probe.json').read_text())['capacitors']['C511'];b=p.LoadBoard(str(src));vec=lambda q:p.VECTOR2I(*(p.FromMM(c) for c in q));edges={(tuple(vec(a)),tuple(vec(z))) for a,z in zip(g['path_mm'],g['path_mm'][1:]) if vec(a)!=vec(z)};changed=[]
for t in b.GetTracks():
 if t.GetNetname()=='GND' and not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.F_Cu and (tuple(t.GetStart()),tuple(t.GetEnd())) in edges:
  assert t.GetWidth()==p.FromMM(.2);t.SetWidth(p.FromMM(.5));changed.append(t.m_Uuid.AsString())
assert len(changed)==len(edges)
t=p.PCB_TRACK(b);t.SetStart(vec((58.85,32.1)));t.SetEnd(vec((58.85,31.625)));t.SetWidth(p.FromMM(.5));t.SetLayer(p.F_Cu);t.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(t)
v=p.PCB_VIA(b);v.SetPosition(vec((58.85,31.625)));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(v)
outdir=Path(tempfile.mkdtemp(prefix='phoenix-output-return-'));out=outdir/src.name
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',outdir/'fp-lib-table');filler=p.ZONE_FILLER(b);filler.Fill(b.Zones());p.SaveBoard(str(out),b)
m={'source':str(src),'candidate':str(out),'parent_sha256':proof['candidate_sha256'],'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'changed':changed,'width_mm':.5,'old_width_mm':.2,'added_ground_via_mm':[58.85,31.625,.45,.2],'original_ground_via_preserved':True,'limitations':['Geometry and continuity only; via current sharing, ripple return and plane currents are not qualified.','Regulator switching node and source distribution remain open.']}
mp=outdir/'input.json';mp.write_text(json.dumps(m));os.execv(sys.executable,[sys.executable,str(Path(__file__).resolve()),'--audit',str(mp)])
