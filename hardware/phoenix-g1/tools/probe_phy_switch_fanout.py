#!/usr/bin/env python3
"""Isolated SW pin fanout feasibility; explicitly held against the historical width guide."""
import json,hashlib,tempfile,shutil,sys,os,subprocess,math
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
from pcb_route_guards import require_constant_width_branch
S=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-compact-inductor/corridor'
if '--audit' in sys.argv:
 m=json.loads(Path(sys.argv[-1]).read_text());src=Path(m['source']);out=Path(m['candidate']);drc=out.parent/'drc.json'
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
 raw=json.loads(drc.read_text());new=introduced(json.loads((src.parent/'drc.json').read_text()),raw);ids={i for r in new for i in r['items']};m.update(new_violations=new,details=[r for r in raw['violations'] if any(i['uuid'] in ids for i in r['items'])],status='SW_FANOUT_GEOMETRY_REJECTED',assembly_ready=False)
 if not new:
  original=p.LoadBoard(str(src));candidate=p.LoadBoard(str(out));m['preservation']=verify_preservation(original,candidate);pads={(f.GetReference(),q.GetNumber()):q for f in candidate.GetFootprints() for q in f.Pads()};candidate.BuildConnectivity();m['connected']=pads['L501','1'].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in candidate.GetConnectivity().GetConnectedItems(pads['U5','30'])}
  if m['connected']:m['status']='SW_GEOMETRY_PASSED_POWER_FANOUT_HOLD'
 (S/'switch-fanout-probe.json').write_text(json.dumps(m,indent=2)+'\n');print(m['status'],flush=True);os._exit(0)
cp=json.loads((S/'checkpoint.json').read_text());src=S/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src));vec=lambda q:p.VECTOR2I(*(p.FromMM(c) for c in q));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};assert tuple(pads['U5','30'].GetPosition())==tuple(vec((61.2,28.6)))
trunk=[(60.3,27.9),(58.825,29.375),(58.825,30)];neck=[(61.2,28.6),(60.9,28.3)];items=[]
for points,width in [(trunk,1.55),(neck,.2)]:
 tracks=[]
 for a,z in zip(points,points[1:]):
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetLayer(p.F_Cu);t.SetWidth(p.FromMM(width));t.SetNetCode(pads['U5','30'].GetNetCode());b.Add(t);tracks.append(t);items.append(t.m_Uuid.AsString())
 require_constant_width_branch(tracks,net='PHY_SW',layer=p.F_Cu,width_mm=width,start_mm=points[0],end_mm=points[-1])
outdir=Path(tempfile.mkdtemp(prefix='phoenix-sw-fanout-'));out=outdir/src.name
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',outdir/'fp-lib-table');filler=p.ZONE_FILLER(b);filler.Fill(b.Zones());p.SaveBoard(str(out),b)
m={'source':str(src),'candidate':str(out),'parent_sha256':cp['sha256'],'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'trunk_path_mm':trunk,'trunk_width_mm':1.55,'pin_fanout_path_mm':neck,'pin_fanout_width_mm':.2,'pin_fanout_length_mm':math.dist(*neck),'new_copper_uuids':items,'historical_60mil_width_met_on_entire_path':False,'power_layout_accepted':False,'checkpoint_modified':False,'limitations':['A short QFN pin fanout is narrower than the historical >60 mil guideline. This trial does not waive that requirement or qualify the power path.','Need the applicable Realtek layout guide/reference fanout or manufacturer confirmation, plus ripple/current/thermal verification, before adoption.','Source rail and load distribution remain incomplete. No physical test.']}
mp=outdir/'input.json';mp.write_text(json.dumps(m));os.execv(sys.executable,[sys.executable,str(Path(__file__).resolve()),'--audit',str(mp)])
