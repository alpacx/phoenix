"""Recover short source termination, oscillator bypass, enable and ground returns on the clock coupon."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess
import pcbnew as p
from pcb_power_leg import route_leg
from drc_regression import introduced
from native_front_splice import recover,wire
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';read=lambda n:json.loads((root/(n+'.json')).read_text());cp=read('wake-clock-relocation-coupon')['candidate'];src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src));side=p.F_Cu;records=[]
def pad(label):
 ref,num=label.split('.');return b.FindFootprintByReference(ref).FindPadByNumber(num)
for a,z,w,limit in [('Y2001.3','R2003.1',200000,4),('Y2001.4','C2007.1',300000,3.75),('Y2001.1','Y2001.4',250000,6.0),('C2007.2','Y2001.2',300000,6.0)]:
 q=pad(a);target=pad(z);assert q.GetNetCode()==target.GetNetCode()
 rec=route_leg(b,q.GetNetname(),tuple(q.GetPosition()),side,tuple(target.GetPosition()),side,w,limit)
 if not rec['connected'] and q.GetNetname()=='WIFI_LPO_SRC':
  ends=[(tuple(q.GetPosition()),tuple(target.GetPosition()),w,q.GetNetCode())]
  path,check=recover(b,ends,q.GetNetname(),False)
  if path is not None and check['length_mm']<=limit:
   for first,last in zip(path,path[1:]):b.Add(wire(b,first,last,q.GetNetCode(),w))
   rec=dict(connected=True,kind='native front path',path_nm=path)
  else:rec['front_search']=check
 records.append(dict(a=a,z=z,width_nm=w,**rec))
for a in ('C2007.2','Y2001.2'):
 q=pad(a);rec=route_leg(b,'GND',tuple(q.GetPosition()),side,tuple(q.GetPosition()),p.In1_Cu,300000,3.2)
 records.append(dict(a=a,z='plane',width_nm=300000,**rec))
folder=root/'runs/relocated-wake-local';folder.mkdir(exist_ok=True);out=folder/src.name
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));saved=p.LoadBoard(str(out));saved.BuildConnectivity();anchors={o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('U4').FindPadByNumber('69'))}
for rec in records:
 def q(s):
  ref,n=s.split('.');return saved.FindFootprintByReference(ref).FindPadByNumber(n)
 ids=anchors if rec['z']=='plane' else {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(q(rec['z']))}
 rec['joined_on_disk']=q(rec['a']).m_Uuid.AsString() in ids
(root/'wake-clock-local-recovery.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),new_drc=delta,records=records,assembly_ready=False),indent=2)+'\n');print([(r['a'],r['z'],r['joined_on_disk']) for r in records],delta,flush=True);os._exit(0)
