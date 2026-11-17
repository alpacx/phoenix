#!/usr/bin/env python3
"""Move RXCLK strap next to its unrouted termination and clear the input corridor."""
import json,hashlib,tempfile,shutil,sys,os,subprocess,math
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
S=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-compact-inductor/corridor'
if '--audit' in sys.argv:
 m=json.loads(Path(sys.argv[-1]).read_text());src=Path(m['source']);out=Path(m['candidate']);drc=out.parent/'drc.json'
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
 raw=json.loads(drc.read_text());new=introduced(json.loads((src.parent/'drc.json').read_text()),raw);ids={i for r in new for i in r['items']};m.update(new_violations=new,details=[r for r in raw['violations'] if any(i['uuid'] in ids for i in r['items'])],status='RXCLK_STRAP_REJECTED',assembly_ready=False)
 if not new:
  original=p.LoadBoard(str(src));candidate=p.LoadBoard(str(out));m['preservation']=verify_preservation(original,candidate,replaced_copper=m['removed']);key=lambda r:(r['reservation'],r['ref']);m['mechanical_conflicts']=sorted({key(r) for r in screen(candidate)}-{key(r) for r in screen(original)})
  if not m['mechanical_conflicts']:m['status']='RXCLK_STRAP_GEOMETRY_PASSED'
 (S/'rxclk-strap-probe.json').write_text(json.dumps(m,indent=2)+'\n');print(m['status'],flush=True);os._exit(0)
cp=json.loads((S/'checkpoint.json').read_text());src=S/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()};pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};assert not b.GetConnectivity().GetConnectedTracks(pads['R522','1'])
ids=['4457e05f-b871-4c78-b5c1-2b6bd399ad0b','d38ef377-f080-4d21-a29d-694417a69587'];held=[]
for t in list(b.GetTracks()):
 if t.m_Uuid.AsString() in ids:
  assert t.GetNetname()=='GND' and t.GetWidth()==p.FromMM(.2);b.Remove(t);held.append(t)
assert len(held)==2
vec=lambda q:p.VECTOR2I(*(p.FromMM(c) for c in q));f=fs['R522'];f.Flip(f.GetPosition(),False)
from local_pcb_router import LocalRouter
r=LocalRouter(b,(60,26,67,33),width=.2,grid=.025);r.pads=[q for q in r.pads if q.GetParentFootprint().GetReference()!='R522'];blocked={q.GetNumber():r.blocked(p.B_Cu,q.GetNetname(),math.hypot(p.ToMM(q.GetSize().x),p.ToMM(q.GetSize().y))) for q in f.Pads()};boxes=[g.GetCourtyard(p.B_Cu).BBox() for g in b.GetFootprints() if g.GetReference()!='R522' and g.GetLayer()==p.B_Cu]
choices=sorted([(x/4,y/4) for x in range(244,265) for y in range(108,129)],key=lambda q:math.dist(q,(63.25,29.5)));found=False
for xy in choices:
 for angle in [180,0,90,270]:
  f.SetPosition(vec(xy));f.SetOrientationDegrees(angle)
  if any(f.GetCourtyard(p.B_Cu).BBox().Intersects(q) for q in boxes):continue
  if any(r.cell(r.xy(q)) in blocked[q.GetNumber()] for q in f.Pads()):continue
  rr=LocalRouter(b,(60,26,67,33),width=.2,grid=.025);path=rr.solve(rr.blocked(p.B_Cu,'PHY_RXCLK'),rr.cell(rr.xy(pads['R512','2'])),rr.cell(rr.xy(pads['R522','1'])))
  if not path:continue
  path=[rr.xy(pads['R512','2'])]+path+[rr.xy(pads['R522','1'])];length=sum(math.dist(a,z) for a,z in zip(path,path[1:]))
  if length>2.5:continue
  found=True;break
 if found:break
assert found,'No short strap placement/path in bounded region'
def route(net,points):
 for a,z in zip(points,points[1:]):
  if vec(a)==vec(z):continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(.2));t.SetLayer(p.B_Cu);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
route('PHY_RXCLK',path)
r=LocalRouter(b,(58,24,69,35),width=.2,grid=.025);start=r.xy(pads['R522','2']);tree=r.paths_from(r.blocked(p.B_Cu,'GND'),r.cell(start),5);forbidden=set()
for lay in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden |= r.blocked(lay,'GND',.45,True)
existing={r.cell(r.xy(v)):v for v in b.GetTracks() if isinstance(v,p.PCB_VIA) and v.GetNetname()=='GND'};sites=sorted((q for q in tree['distances'] if q not in forbidden or q in existing),key=lambda q:(tree['distances'][q],q));assert sites,'No ground escape'
q=sites[0];gp=[start]+r.path_from_tree(tree,q);route('GND',gp)
if q not in existing:
 v=p.PCB_VIA(b);v.SetPosition(vec(r.world(q)));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(v)
outdir=Path(tempfile.mkdtemp(prefix='phoenix-rxclk-strap-'));out=outdir/src.name
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
(outdir/'fp-lib-table').write_text((src.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(src.parent)));filler=p.ZONE_FILLER(b);filler.Fill(b.Zones());p.SaveBoard(str(out),b)
m={'source':str(src),'candidate':str(out),'parent_sha256':cp['sha256'],'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'removed':ids,'R522_position_mm':r.xy(f),'R522_orientation_deg':f.GetOrientationDegrees(),'layer':'B.Cu','strap_path_mm':path,'strap_length_mm':length,'ground_path_mm':gp,'ground_via_mm':r.world(q),'reused_ground_via':q in existing,'limitations':['Short bias branch only; RGMII PHY-to-MAC path remains open and timing/impedance are not qualified.','Existing 4.7k resistor and all copper widths retained.']}
mp=outdir/'input.json';mp.write_text(json.dumps(m));os.execv(sys.executable,[sys.executable,str(Path(__file__).resolve()),'--audit',str(mp)])
