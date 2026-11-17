#!/usr/bin/env python3
"""Restore C517 after joint experimental move, retaining bypass/ground widths."""
import json,hashlib,tempfile,shutil,sys,os,subprocess,math
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
S=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-compact-inductor'
if '--audit' in sys.argv:
 m=json.loads(Path(sys.argv[-1]).read_text());src=Path(m['source']);out=Path(m['candidate']);drc=out.parent/'drc.json'
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
 raw=json.loads(drc.read_text());new=introduced(json.loads((src.parent/'phy-compact-output-drc.json').read_text()),raw);ids={i for r in new for i in r['items']}
 m.update(new_violations=new,details=[r for r in raw['violations'] if any(i['uuid'] in ids for i in r['items'])],status='CORRIDOR_BYPASS_REJECTED',assembly_ready=False)
 if not new:
  original=p.LoadBoard(str(src));candidate=p.LoadBoard(str(out));m['preservation']=verify_preservation(original,candidate,replaced_copper=m['removed'])
  key=lambda r:(r['reservation'],r['ref']);m['mechanical_conflicts']=sorted({key(r) for r in screen(candidate)}-{key(r) for r in screen(original)})
  if not m['mechanical_conflicts']:m['status']='CORRIDOR_BYPASS_GEOMETRY_PASSED'
 (S/m['report']).write_text(json.dumps(m,indent=2)+'\n');print(m['status'],flush=True);os._exit(0)
input_mode='--input-corridor' in sys.argv
cp=json.loads((S/'study-checkpoint.json').read_text());root=S/cp['board'];proof=json.loads((S/('input-corridor-placement.json' if input_mode else 'switch-corridor-placement-searched.json')).read_text());src=Path(proof['candidate']);assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['candidate_sha256'];assert hashlib.sha256(root.read_bytes()).hexdigest()==proof['parent_sha256']==cp['candidate_sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};removed=[];held=[]
for t in list(b.GetTracks()):
 coords=[p.ToMM(v) for v in (t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y)]
 ground=t.m_Uuid.AsString() in ['b78a7fd7-95e8-4fe2-9bea-c07cc6cce27b','f0c00b44-fe1d-4b1d-a1d4-66650688c703']
 power=t.GetNetname()=='+3V3_PHY' and 58.8<=min(coords[0],coords[2]) and max(coords[0],coords[2])<=62 and min(coords[1],coords[3])>=27.7 and max(coords[1],coords[3])<=28.1
 if ground or power:
  assert not isinstance(t,p.PCB_VIA) and t.GetWidth()==p.FromMM(.2) and t.GetLayer()==p.F_Cu
  removed.append(t.m_Uuid.AsString());b.Remove(t);held.append(t)
assert len(removed)==17,len(removed)
vec=lambda q:p.VECTOR2I(*(p.FromMM(c) for c in q))
def route(net,points):
 for a,z in zip(points,points[1:]):
  if vec(a)==vec(z):continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(.2));t.SetLayer(p.F_Cu);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
power=[(62,27.8),(61.72,27.52),(61.72,27)] if input_mode else [(62,27.8),(62.18,27.8),(62.5,27.48)];route('+3V3_PHY',power)
input_path=[]
if input_mode:
 from pcb_route_guards import require_constant_width_branch
 input_path=[(61.975,24.2),(61.975,25.3),(61.6,25.675),(61.6,27)];wide=[]
 for a,z in zip(input_path,input_path[1:]):
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(1.05));t.SetLayer(p.F_Cu);t.SetNetCode(pads['C515','1'].GetNetCode());b.Add(t);wide.append(t)
 require_constant_width_branch(wide,net='+3V3_PHY',layer=p.F_Cu,width_mm=1.05,start_mm=input_path[0],end_mm=input_path[-1])
from local_pcb_router import LocalRouter
r=LocalRouter(b,(60,23,66,30),width=.2,grid=.025);start=r.xy(pads['C517','2']);tree=r.paths_from(r.blocked(p.F_Cu,'GND'),r.cell(start),3);forbidden=set()
for lay in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden |= r.blocked(lay,'GND',.45,True)
choices=sorted((q for q in tree['distances'] if q not in forbidden),key=lambda q:(tree['distances'][q],q));assert choices,'No ground escape in revised placement'
q=choices[0];ground=[start]+r.path_from_tree(tree,q);route('GND',ground)
v=p.PCB_VIA(b);v.SetPosition(vec(r.world(q)));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(pads['C517','2'].GetNetCode());b.Add(v)
outdir=Path(tempfile.mkdtemp(prefix='phoenix-corridor-bypass-'));out=outdir/src.name
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',outdir/'fp-lib-table');filler=p.ZONE_FILLER(b);filler.Fill(b.Zones());p.SaveBoard(str(out),b)
m={'report':'input-corridor-bypass.json' if input_mode else 'switch-corridor-bypass.json','input_path_mm':input_path,'input_width_mm':1.05 if input_mode else None,'source':str(root),'candidate':str(out),'parent_sha256':cp['candidate_sha256'],'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'removed':removed,'moves':proof['moves'],'power_branch_mm':power,'ground_branch_mm':ground,'ground_via_mm':r.world(q),'widths_mm':{'bypass':.2,'ground':.2},'limitations':['Only bypass relocation. Input, switch node and load distribution remain open.','RX terminations require new fanout and signal-integrity assessment. No electrical qualification.']}
mp=outdir/'input.json';mp.write_text(json.dumps(m));os.execv(sys.executable,[sys.executable,str(Path(__file__).resolve()),'--audit',str(mp)])
