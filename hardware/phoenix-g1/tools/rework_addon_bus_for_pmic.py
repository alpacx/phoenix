#!/usr/bin/env python3
"""Move only the lower J3 power-bus connection off the PMIC escape corridor."""
import pcbnew as p,json,hashlib,math,shutil,subprocess
from pathlib import Path
from drc_regression import introduced
from local_pcb_router import LocalRouter
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-buck5/pcb';src=D/'placement.kicad_pcb';b=p.LoadBoard(str(src));net=b.FindNet('+5V_ADDON');changed=[];held=[];out=D/'bus-clearance.kicad_pcb';cli='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli';base=json.loads((D/'placement-drc.json').read_text())
def xy(v):return p.ToMM(v.x),p.ToMM(v.y)
def near(a,z):return math.dist(a,z)<1e-5
def point(q):return p.VECTOR2I(*(p.FromMM(v) for v in q))
for t in list(b.GetTracks()):
 if t.GetNetname()!='+5V_ADDON' or isinstance(t,p.PCB_VIA) or t.GetLayer()!=p.F_Cu:continue
 a,z=xy(t.GetStart()),xy(t.GetEnd())
 if near(a,(62.5,.45)) and near(z,(62.5,4.55)):
  changed.append({'uuid':t.m_Uuid.AsString(),'action':'shorten_front_vertical_bus','old_end':z});t.SetEnd(point((62.5,2)))
 elif near(a,(62.5,4.55)) and abs(z[1]-4.55)<1e-5:
  changed.append({'uuid':t.m_Uuid.AsString(),'action':'shorten_lower_bus_left_end','old_start':a});t.SetStart(point((63.7,4.55)))
assert len(changed)==2,changed
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
r=LocalRouter(b,(62,3.9,66,7),width=.3,grid=.05);r.pad_clearances={a.m_Uuid.AsString():.17 for f in b.GetFootprints() if f.GetReference()=='J3' for a in f.Pads()};r.via_pad_clearances=r.pad_clearances.copy();forbidden=set()
for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden|=r.blocked(layer,'+5V_ADDON',.6,True)
tree=r.paths_from(r.blocked(p.F_Cu,'+5V_ADDON'),r.cell((64.3,4.55)),3);options=sorted(set(tree['distances'])-forbidden,key=lambda q:tree['distances'][q]+math.dist(r.world(q),(62.5,2)));found=False;trials=[]
print('Available lower-bus via positions:',len(options),flush=True)
for width in [.8,.6]:
 inner=LocalRouter(b,(59,.8,80,10),width=width,grid=.05);inner.max_expansions=120000
 for layer in [p.In3_Cu,p.In2_Cu,p.B_Cu]:
  blocked=inner.blocked(layer,'+5V_ADDON')
  for q in options[:20]:
   dest=r.world(q);path=inner.solve(blocked,inner.cell((62.5,2)),inner.cell(dest))
   if not path:continue
   front=r.path_from_tree(tree,q);added=[]
   for pts,w,lvl in [(front,.3,p.F_Cu),(path,width,layer)]:
    for a,z in zip(pts,pts[1:]):
     t=p.PCB_TRACK(b);t.SetStart(point(a));t.SetEnd(point(z));t.SetWidth(p.FromMM(w));t.SetLayer(lvl);t.SetNetCode(net.GetNetCode());b.Add(t);added.append(t)
   v=p.PCB_VIA(b);v.SetPosition(point(dest));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(net.GetNetCode());b.Add(v);added.append(v)
   p.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();pads={(f.GetReference(),a.GetNumber()):a for f in b.GetFootprints() for a in f.Pads()};connected={q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads['U8101','5'])};okay=all(pads['J3',str(n)].m_Uuid.AsString() in connected for n in range(1,9));p.SaveBoard(str(out),b);drc=D/'bus-clearance-drc.json';subprocess.run([cli,'pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True);new=introduced(base,json.loads(drc.read_text()));record={'via_mm':dest,'bridge_layer':b.GetLayerName(layer),'bridge_width_mm':width,'bridge_length_mm':sum(math.dist(a,z) for a,z in zip(path,path[1:])),'new_violations':new,'accepted':okay and not new};trials.append(record);print(record,flush=True)
   if record['accepted']:found=True;break
   for item in added:b.Remove(item)
   held.extend(added)
  if found:break
 if found:break
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run([cli,'pcb','drc','--format','json','-o',str(D/'bus-clearance-drc.json'),str(out)],check=True,capture_output=True)
(D/'bus-clearance.json').write_text(json.dumps({'status':'BUS_CONTINUITY_AND_GEOMETRY_CHECKED' if found else 'NO_ACCEPTED_LOWER_BUS_BRIDGE','source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'intentional_copper_changes':changed,'J3_power_pins_connected':list(range(1,9)) if found else None,'trials':trials,'current_thermal_and_EMI_qualified':False,'assembly_ready':False},indent=2)+'\n');print('Bus rework accepted:',found)
