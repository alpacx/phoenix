#!/usr/bin/env python3
"""Connect external eMMC bypass grounds to existing planes; geometry only."""
import pcbnew as p, json,math,shutil,subprocess,hashlib,os
from pathlib import Path
from local_pcb_router import LocalRouter
from drc_regression import introduced
R=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/emmc-system/pcb';source=os.environ.get('PHOENIX_EMMC_GROUND_SOURCE','emmc-repacked');stage=os.environ.get('PHOENIX_EMMC_GROUND_STAGE','emmc-ground');src=R/(source+'.kicad_pcb');out=R/(stage+'.kicad_pcb');b=p.LoadBoard(str(src));fs=list(b.GetFootprints());pads={(f.GetReference(),a.GetNumber()):a for f in fs for a in f.Pads()};baseline=json.loads((R/'emmc-repacked-drc.json').read_text());cli='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli';records=[];held=[]
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
def vec(q):return p.VECTOR2I(*(p.FromMM(v) for v in q))
for key in [(f'C{n}','2') for n in range(8001,8011)]+[('R8005','2')]:
 pad=pads[key];assert pad.GetNetname()=='GND';b.BuildConnectivity()
 if pads['U4','69'].m_Uuid.AsString() in {a.m_Uuid.AsString() for a in b.GetConnectivity().GetConnectedItems(pad)}:records.append({'pad':'.'.join(key),'accepted':True,'already_connected':True});continue
 sx,sy=p.ToMM(pad.GetPosition().x),p.ToMM(pad.GetPosition().y);r=LocalRouter(b,(max(.5,sx-8),max(.5,sy-8),min(89.5,sx+8),min(39.5,sy+8)),width=.2,grid=.05);blocked=r.blocked(p.B_Cu,'GND');tree=r.paths_from(blocked,r.cell((sx,sy)),12);forbidden=set()
 for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden|=r.blocked(layer,'GND',.45,True)
 existing={r.cell(r.xy(t)) for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND'} & set(tree['distances'])
 options=sorted(existing | (set(tree['distances'])-forbidden),key=lambda q:tree['distances'][q]);accepted=False;trials=0;last=[]
 for q in options:
  xy=r.world(q)
  if math.dist(xy,(sx,sy))<.6:continue
  if tree['distances'][q]>2:break
  trials+=1
  if trials>12:break
  path=[(sx,sy)]+r.path_from_tree(tree,q);added=[]
  for a,z in zip(path,path[1:]):
   if math.dist(a,z)<1e-6:continue
   t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(.2));t.SetLayer(p.B_Cu);t.SetNetCode(pad.GetNetCode());b.Add(t);added.append(t)
  if q not in existing:
   v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(pad.GetNetCode());b.Add(v);added.append(v)
  p.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();connected=pads['U4','69'].m_Uuid.AsString() in {a.m_Uuid.AsString() for a in b.GetConnectivity().GetConnectedItems(pad)}
  p.SaveBoard(str(out),b);drc=R/(stage+'-drc.json');subprocess.run([cli,'pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True);last=introduced(baseline,json.loads(drc.read_text()))
  if connected and not last:accepted=True;break
  for item in added:b.Remove(item)
  held.extend(added)
 rec={'pad':'.'.join(key),'accepted':accepted,'trials':trials,'via_mm':xy if accepted else None,'reused_ground_via':q in existing if accepted else False,'length_mm':round(sum(math.dist(a,z) for a,z in zip(path,path[1:])),4) if accepted else None,'last_new_violations':last if not accepted else []};records.append(rec);print(rec,flush=True)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run([cli,'pcb','drc','--format','json','-o',str(R/(stage+'-drc.json')),str(out)],check=True,capture_output=True)
(R/(stage+'.json')).write_text(json.dumps({'status':'EXTERNAL_BYPASS_GROUND_GEOMETRY_ONLY','source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'board_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'connections':records,'EMMC_BGA_ground_fanout_complete':False,'power_integrity_qualified':False,'assembly_ready':False},indent=2)+'\n')
