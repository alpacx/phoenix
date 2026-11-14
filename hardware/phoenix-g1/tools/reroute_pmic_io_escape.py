#!/usr/bin/env python3
"""Reroute only four explicitly identified SWOUT1 primitives, retaining endpoints."""
import pcbnew as p,json,subprocess,shutil,hashlib,math
from pathlib import Path
from local_pcb_router import LocalRouter
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-buck5/pcb';src=D/'output-ground.kicad_pcb';out=D/'io-reroute.kicad_pcb';b=p.LoadBoard(str(src));base=json.loads((D/'output-ground-drc.json').read_text());held=[];trials=[]
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
uids={'c56f9a86-4ded-4de3-ae32-4a3b6131078e','bc7687d7-f582-4e4a-ad03-c15395e31e54','3821fc34-7a67-4339-a7f4-be5a7eb84bca','4482cdb6-bf26-4b24-966f-71b01a80dc3b'}
for t in list(b.GetTracks()):
 if t.m_Uuid.AsString() in uids:b.Remove(t);held.append(t)
assert len(held)==4
f=next(f for f in b.GetFootprints() if f.GetReference()=='C425');f.SetPosition(p.VECTOR2I(p.FromMM(59.45),p.FromMM(3.7)))
pad=next(a for f in b.GetFootprints() if f.GetReference()=='U4' for a in f.Pads() if a.GetNumber()=='55');net=pad.GetNetname();r=LocalRouter(b,(57,1,68,10),width=.127,grid=.025);tree=r.paths_from(r.blocked(p.F_Cu,net),r.cell(r.xy(pad)),3);print('Reachable',len(tree['distances']),flush=True)
def vec(q):return p.VECTOR2I(*(p.FromMM(v) for v in q))
accepted=False
for diameter,drill in [(.45,.2)]:
 forbidden=set()
 for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden|=r.blocked(layer,net,diameter,True)
 options=sorted(set(tree['distances'])-forbidden,key=lambda q:(r.world(q)[0],r.world(q)[1]));print('Via',diameter,'options',len(options),flush=True)
 for q in options[:30]:
  xy=r.world(q);inner=LocalRouter(b,(57,1,69,11),width=.2,grid=.025);inner.max_expansions=60000;blocked=inner.blocked(p.In2_Cu,net);wide=LocalRouter(b,(57,1,69,11),width=.5,grid=.025);wide.max_expansions=60000;paths=[inner.solve(blocked,q,inner.cell((66.65,4.65))),wide.solve(wide.blocked(p.In2_Cu,net),q,wide.cell((61.75,7.15)))]
  if not all(paths):continue
  added=[]
  for layer,width,path in [(p.F_Cu,.127,[r.xy(pad)]+r.path_from_tree(tree,q))]+[(p.In2_Cu,width,path) for width,path in zip([.2,.5],paths)]:
   for a,z in zip(path,path[1:]):
    if math.dist(a,z)<1e-6:continue
    t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(pad.GetNetCode());b.Add(t);added.append(t)
  v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(diameter));v.SetDrill(p.FromMM(drill));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(pad.GetNetCode());b.Add(v);added.append(v)
  p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'io-reroute-drc.json'),str(out)],check=True,capture_output=True);new=introduced(base,json.loads((D/'io-reroute-drc.json').read_text()));trials.append({'via':xy,'diameter':diameter,'new_violations':new});print('Trial',xy,len(new),flush=True)
  if not new:accepted=True;break
  for t in added:b.Remove(t)
  held.extend(added)
 if accepted:break
(D/'io-reroute.json').write_text(json.dumps({'accepted':accepted,'removed_primitives':sorted(uids),'trials':trials,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'assembly_ready':False},indent=2)+'\n');print('Accepted',accepted,flush=True)
