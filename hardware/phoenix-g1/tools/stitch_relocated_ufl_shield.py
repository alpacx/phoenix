"""Bond both U.FL shield lands to nearby independent ground barrels and preserve clock-cap returns."""
from pathlib import Path
import math,hashlib,json,os,shutil,subprocess
import pcbnew as p
from pcb_power_leg import route_leg
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';read=lambda n:json.loads((root/(n+'.json')).read_text());cp=read('rf-local-ufl-pth-safe')['candidate'];src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src));j=b.FindFootprintByReference('J2001');side=p.B_Cu;v=lambda xy:p.VECTOR2I(*xy);uid=lambda o:o.m_Uuid.AsString()
results=[]
for n in ('2','3'):
 q=j.FindPadByNumber(n);c=tuple(q.GetPosition());bb=q.GetBoundingBox();opts=[(0,c)]
 for i in range(-5,6):
  for k in range(-5,6):
   u=(c[0]+i*150000,c[1]+k*150000)
   if q.HitTest(v(u)) and abs(u[0]-c[0])<bb.GetWidth()/2-90000 and abs(u[1]-c[1])<bb.GetHeight()/2-90000:opts.append((math.dist(c,u),u))
 found=None;attempts=[]
 for _,u in sorted(set(opts)):
  rec=route_leg(b,'GND',u,side,u,p.In1_Cu,300000,2.2)
  if rec['connected']:found=dict(tap_nm=u,**rec);break
  attempts.append([u,rec.get('legal_sites',0),rec.get('source_reached',0)])
 results.append(dict(land=n,return_path=found,attempts=attempts))
folder=root/'runs/local-ufl-shield-stitches';folder.mkdir(exist_ok=True);out=folder/src.name
for ext in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/ext,folder/ext)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);dr=folder/'drc.json';subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],capture_output=True,check=True)
delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads(dr.read_text()));saved=p.LoadBoard(str(out));saved.BuildConnectivity();gg={uid(o) for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('U4').FindPadByNumber('69'))}
def pin(r,n):return saved.FindFootprintByReference(r).FindPadByNumber(n)
guards={r+'.'+n:uid(pin(r,n)) in gg for r,n in [('C2008','2'),('C2009','2'),('J2001','2'),('J2001','3')]}
(root/'rf-local-shield-return.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),returns=results,ground_after_reload=guards,new_drc=delta,assembly_ready=False),indent=2)+'\n');print(guards,delta,flush=True);os._exit(0)
