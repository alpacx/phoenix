#!/usr/bin/env python3
"""Independent low-speed auxiliary routing trials; each accepted only after DRC.
No timing/impedance qualification; default CPU escape process is experimental.
"""
import pcbnew as p,math,json,shutil,hashlib,subprocess,collections,time,os
from pathlib import Path
from local_pcb_router import LocalRouter
R=Path(__file__).resolve().parents[1];D=R/'migration-rk3562/experiments/stacked-expansion/pcb';CLI='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli';source=os.environ.get('PHOENIX_ROUTE_SOURCE','logic-reference'); stage=os.environ.get('PHOENIX_ROUTE_STAGE','aux-io'); signal_layer=getattr(p,os.environ.get('PHOENIX_ROUTE_LAYER','In3_Cu')); b=p.LoadBoard(str(D/(source+'.kicad_pcb')));pads={(f.GetReference(),a.GetNumber()):a for f in b.GetFootprints() for a in f.Pads()};out=D/(stage+'.kicad_pcb');basecounts=collections.Counter(v['type'] for v in json.loads((D/'logic-reference-drc.json').read_text())['violations']);records=[]
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(D/f'{source}.{ext}',out.with_suffix('.'+ext))
with out.with_suffix('.kicad_dru').open('a') as o:o.write('''\n(rule "Auxiliary CPU escapes" (condition "A.NetName == 'EXP_*'") (constraint track_width (min 0.0762mm)))\n''')
copper_layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
assert len(set(copper_layers))==6, 'Via clearance must include every copper layer'
via_diameter=float(os.environ.get('PHOENIX_VIA_DIAMETER','.6'));via_drill=float(os.environ.get('PHOENIX_VIA_DRILL','.3'))
assert via_diameter>=.45 and via_drill>=.2 and (via_diameter-via_drill)/2>=.1
connector_width=float(os.environ.get('PHOENIX_CONNECTOR_WIDTH','.127'))
def pt(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
nets=[pads['J3',str(n)].GetNetname() for n in [25,26,29,30,23,24,31,32,33,34,35]]
for name in nets:
 b.BuildConnectivity()
 ends=[a for (ref,_),a in pads.items() if ref in ['U1','J3'] and a.GetNetname()==name]
 if len(ends)==2 and ends[1].m_Uuid.AsString() in {i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(ends[0])}:
  records.append({'net':name,'accepted':True,'preserved_existing_route':True});continue
 src=next(a for (ref,_),a in pads.items() if ref=='U1' and a.GetNetname()==name);dst=next(a for (ref,_),a in pads.items() if ref=='J3' and a.GetNetname()==name)
 sx,sy=p.ToMM(src.GetPosition().x),p.ToMM(src.GetPosition().y)
 cpu=LocalRouter(b,(max(1,sx-5),max(.5,sy-5),min(89,sx+5),min(39,sy+5)),width=.0762,clearance=.0762);cpu.copper_clearance=.2;cpu.max_expansions=25000
 con=LocalRouter(b,(58,.5,78,14),width=connector_width);con.max_expansions=25000;con.pad_clearances={q.m_Uuid.AsString():.17 for f in b.GetFootprints() if f.GetReference()=='J3' for q in f.Pads()}
 inner=LocalRouter(b,(30,.5,84,34),width=.2);inner.max_expansions=160000;middle=inner.blocked(signal_layer,name)
 def options(router,pad,is_cpu):
  blocked=router.blocked(p.F_Cu,name);forbidden=set()
  for layer in copper_layers:forbidden|=router.blocked(layer,name,via_diameter,True)
  start=router.cell(router.xy(pad));opts=[];deadline=time.monotonic()+30
  candidates={(start[0]+dx,start[1]+dy) for dx in range(-80 if is_cpu else -160,81 if is_cpu else 161,2) for dy in range(-80 if is_cpu else -160,81 if is_cpu else 161,2)}
  for q in sorted(candidates,key=lambda q:math.dist(q,start)):
   if time.monotonic()>deadline:break
   x,y=router.world(q)
   if not router.within(q) or q in forbidden or inner.cell((x,y)) in middle:continue
   if is_cpu and not (x<=35.8 or x>=50.2 or y<=12.8 or y>=27.2):continue
   if any(math.dist((x,y),router.xy(v))<.25+via_drill/2+p.ToMM(v.GetDrillValue())/2-1e-6 for v in b.GetTracks() if isinstance(v,p.PCB_VIA)):continue
   path=router.solve(blocked,start,q)
   if path and sum(math.dist(a,z) for a,z in zip(path,path[1:]))<(8 if is_cpu else 14):opts.append((q,[router.xy(pad)]+path))
   if len(opts)==8:break
  return opts
 first=options(cpu,src,True);second=options(con,dst,False);found=None;bridge_deadline=time.monotonic()+30
 for q,path in first:
  if time.monotonic()>bridge_deadline:break
  for z,tail in second:
   if time.monotonic()>bridge_deadline:break
   if math.dist(cpu.world(q),con.world(z))<.8:continue
   bridge=inner.solve(middle,inner.cell(cpu.world(q)),inner.cell(con.world(z)))
   if bridge:found=q,path,z,tail,bridge;break
  if found:break
 if not found:
  rec={'net':name,'accepted':False,'reason':'No bounded geometric route','CPU_options':len(first),'J3_options':len(second)};records.append(rec);print(rec,flush=True);continue
 q,path,z,tail,bridge=found;added=[]
 for layer,width,points in [(p.F_Cu,.0762,path),(p.F_Cu,connector_width,tail),(signal_layer,.2,bridge)]:
  for a,c in zip(points,points[1:]):
   if math.dist(a,c)<1e-6:continue
   t=p.PCB_TRACK(b);t.SetStart(pt(a));t.SetEnd(pt(c));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(src.GetNetCode());b.Add(t);added.append(t)
 for xy in [cpu.world(q),con.world(z)]:
  v=p.PCB_VIA(b);v.SetPosition(pt(xy));v.SetWidth(p.FromMM(via_diameter));v.SetDrill(p.FromMM(via_drill));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(src.GetNetCode());b.Add(v);added.append(v)
 p.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();assert dst.m_Uuid.AsString() in {i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(src)}
 p.SaveBoard(str(out),b);drc=D/(stage+'-drc.json');result=subprocess.run([CLI,'pcb','drc','--format','json','-o',str(drc),str(out)],capture_output=True,text=True);result.check_returncode();counts=collections.Counter(v['type'] for v in json.loads(drc.read_text())['violations']);new={k:v-basecounts[k] for k,v in counts.items() if v>basecounts[k]}
 accepted=not new
 if not accepted:
  for item in added:b.Remove(item)
 rec={'net':name,'accepted':accepted,'new_violations':new,'CPU_escape_mm':sum(math.dist(a,c) for a,c in zip(path,path[1:])),'via_positions_mm':[cpu.world(q),con.world(z)]};records.append(rec);print(rec,flush=True)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run([CLI,'pcb','drc','--format','json','-o',str(D/(stage+'-drc.json')),str(out)],check=True,capture_output=True)
(D/(stage+'.json')).write_text(json.dumps({'status':'GEOMETRY_AND_CONTINUITY_ONLY','source_stage':source,'via_diameter_mm':via_diameter,'via_drill_mm':via_drill,'signal_layer':b.GetLayerName(signal_layer),'via_clearance_layers':[b.GetLayerName(layer) for layer in copper_layers],'routes':records,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'pullups_and_signal_integrity_qualified':False,'assembly_ready':False},indent=2)+'\n')
