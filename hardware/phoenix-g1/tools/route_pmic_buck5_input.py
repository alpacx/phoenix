#!/usr/bin/env python3
"""Short top-layer BUCK5 input connection; no electrical/thermal qualification."""
import pcbnew as p,json,math,hashlib,subprocess,shutil,time,os
from pathlib import Path
from local_pcb_router import LocalRouter
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-buck5/pcb';source=os.environ.get('PHOENIX_BUCK5_INPUT_SOURCE','feedback');src=D/(source+'.kicad_pcb');out=D/'input.kicad_pcb';b=p.LoadBoard(str(src));pads={(f.GetReference(),a.GetNumber()):a for f in b.GetFootprints() for a in f.Pads()};s=pads['U4','54'];t=pads['C425','1'];name='+3V3_SYS';base=json.loads((D/(source+'-drc.json')).read_text());CLI='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli';held=[];records=[]
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
with out.with_suffix('.kicad_dru').open('a') as f:f.write('\n(rule "BUCK5 pin neck width - current qualification pending" (condition "A.NetName == \'+3V3_SYS\'") (constraint track_width (min 0.127mm)))\n')
def vec(q):return p.VECTOR2I(*(p.FromMM(v) for v in q))
r=LocalRouter(b,(55,.3,65,7),width=.127,grid=.025);neck_blocked=r.blocked(p.F_Cu,name);neck_blocked|={(x,y) for x in range(2492,2601) for y in range(172,281)};tree=r.paths_from(neck_blocked,r.cell(r.xy(s)),2.5);found=False;print('Neck reachable cells',len(tree['distances']),flush=True)
for width in [.5,.35]:
 main=LocalRouter(b,(55,.3,65,7),width=width,grid=.025);main.max_expansions=60000;blocked=main.blocked(p.F_Cu,name);options=[q for q in tree['distances'] if q not in blocked and r.world(q)[1]<=4.0];options.sort(key=lambda q:tree['distances'][q]+math.dist(r.world(q),r.xy(t)));deadline=time.monotonic()+40;print('Width',width,'bridge options',len(options),flush=True)
 for q in options[:150]:
  if time.monotonic()>deadline:break
  path=main.solve(blocked,q,main.cell(main.xy(t)))
  if not path:continue
  neck=[r.xy(s)]+r.path_from_tree(tree,q);path=path+[r.xy(t)];added=[]
  for w,points in [(.127,neck),(width,path)]:
   for a,z in zip(points,points[1:]):
    if math.dist(a,z)<1e-6:continue
    tr=p.PCB_TRACK(b);tr.SetStart(vec(a));tr.SetEnd(vec(z));tr.SetWidth(p.FromMM(w));tr.SetLayer(p.F_Cu);tr.SetNetCode(s.GetNetCode());b.Add(tr);added.append(tr)
  p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run([CLI,'pcb','drc','--format','json','-o',str(D/'input-drc.json'),str(out)],check=True,capture_output=True);new=introduced(base,json.loads((D/'input-drc.json').read_text()));b.BuildConnectivity();connected=t.m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(s)}
  rec={'main_width_mm':width,'neck_length_mm':sum(math.dist(a,z) for a,z in zip(neck,neck[1:])),'main_length_mm':sum(math.dist(a,z) for a,z in zip(path,path[1:])),'new_violations':new,'accepted':connected and not new};records.append(rec);print(rec,flush=True)
  if rec['accepted']:found=True;break
  for item in added:b.Remove(item)
  held.extend(added)
 if found:break
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run([CLI,'pcb','drc','--format','json','-o',str(D/'input-drc.json'),str(out)],check=True,capture_output=True)
(D/'input.json').write_text(json.dumps({'status':'INPUT_BYPASS_GEOMETRY_CHECKED' if found else 'NO_ACCEPTED_INPUT_ROUTE','source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'trials':records,'current_and_EMI_qualified':False,'assembly_ready':False},indent=2)+'\n');print('Input route accepted:',found)
