#!/usr/bin/env python3
"""Geometric BUCK5 output trial, including interlayer via. Not power qualification."""
import pcbnew as p,json,math,hashlib,subprocess,shutil,os
from pathlib import Path
from local_pcb_router import LocalRouter,smd_copper_layer
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-buck5/pcb';source=os.environ.get('PHOENIX_BUCK5_OUTPUT_SOURCE','output-front');stage=os.environ.get('PHOENIX_BUCK5_OUTPUT_STAGE','output');src=D/(source+'.kicad_pcb');out=D/(stage+'.kicad_pcb');b=p.LoadBoard(str(src));pads={(f.GetReference(),a.GetNumber()):a for f in b.GetFootprints() for a in f.Pads()};base=json.loads((D/(source+'-drc.json')).read_text());CLI='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli';held=[];records=[]
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
def vec(q):return p.VECTOR2I(*(p.FromMM(v) for v in q))
def trial(s,t,paths,via=None):
 added=[]
 for layer,width,path in paths:
  for a,z in zip(path,path[1:]):
   if math.dist(a,z)<1e-6:continue
   tr=p.PCB_TRACK(b);tr.SetStart(vec(a));tr.SetEnd(vec(z));tr.SetWidth(p.FromMM(width));tr.SetLayer(layer);tr.SetNetCode(s.GetNetCode());b.Add(tr);added.append(tr)
 if via:
  v=p.PCB_VIA(b);v.SetPosition(vec(via));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(s.GetNetCode());b.Add(v);added.append(v)
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run([CLI,'pcb','drc','--format','json','-o',str(D/(stage+'-drc.json')),str(out)],check=True,capture_output=True);new=introduced(base,json.loads((D/(stage+'-drc.json')).read_text()));b.BuildConnectivity();connected=t.m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(s)}
 if not new and connected:return True
 for item in added:b.Remove(item)
 held.extend(added);return False
for sk,tk in [(('L405','2'),('C435','1')),(('C435','1'),('C445','1'))]:
 if os.environ.get('PHOENIX_BUCK5_PRIMARY_OUTPUT_ONLY')=='1' and sk[0]=='C435':continue
 s,t=pads[sk],pads[tk];name=s.GetNetname();assert name==t.GetNetname();accepted=False
 b.BuildConnectivity()
 if t.m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(s)}:records.append({'source':'.'.join(sk),'target':'.'.join(tk),'accepted':True,'already_connected':True});continue
 for width in [.6,.4]:
  r=LocalRouter(b,(54,.5,63,9),width=width,grid=.05);r.max_expansions=60000;start=r.cell(r.xy(s));goal=r.cell(r.xy(t));front=r.blocked(smd_copper_layer(s),name);back=r.blocked(smd_copper_layer(t),name)
  if smd_copper_layer(s)==smd_copper_layer(t):
   path=r.solve(front,start,goal)
   if path:accepted=trial(s,t,[(smd_copper_layer(s),width,[r.xy(s)]+path+[r.xy(t)])])
  else:
   tree=r.paths_from(front,start,4);forbidden=set()
   for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden|=r.blocked(layer,name,.45,True)
   options=sorted(set(tree['distances'])-forbidden,key=lambda q:tree['distances'][q]+math.dist(r.world(q),r.xy(t)))
   print('Output via options',width,len(options),flush=True)
   for q in options[:30]:
    path=r.solve(back,q,goal)
    if path and trial(s,t,[(smd_copper_layer(s),width,[r.xy(s)]+r.path_from_tree(tree,q)),(smd_copper_layer(t),width,path+[r.xy(t)])],r.world(q)):accepted=True;break
  if accepted:break
 record={'source':'.'.join(sk),'target':'.'.join(tk),'accepted':accepted,'width_mm':width if accepted else None};records.append(record);print(record,flush=True)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run([CLI,'pcb','drc','--format','json','-o',str(D/(stage+'-drc.json')),str(out)],check=True,capture_output=True)
(D/(stage+'.json')).write_text(json.dumps({'status':'LOCAL_OUTPUT_ROUTING_TRIAL','source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'connections':records,'power_qualified':False,'assembly_ready':False},indent=2)+'\n')
