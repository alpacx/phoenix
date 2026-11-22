from pathlib import Path
import json,sys,os,math,hashlib,shutil,subprocess
import pcbnew as p

from pcb_power_leg import route_leg
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';input_pair='--buck-input-pair' in sys.argv; meta=json.loads((root/('rotated-bypass-source-mixed.json' if input_pair else 'rotated-bypass-islands.json')).read_text());src=root/meta['board'];digest=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();assert digest(src)==meta['sha256']
def pin(b,ref,num='1'):return b.FindFootprintByReference(ref).FindPadByNumber(num)
def group(b,q):return {x.m_Uuid.AsString() for x in b.GetConnectivity().GetConnectedItems(q)}
records=[];held=[];current=src;owners=[]
source_ref,source_pin=('U4','11') if input_pair else ('C1304','1')
for ref in (('C421','C422') if input_pair else ('C483','C423','C482','C485')):
 b=p.LoadBoard(str(current));owners.append(b);b.BuildConnectivity();q=pin(b,ref);pt=tuple(q.GetPosition());rail=group(b,pin(b,source_ref,source_pin))
 if q.m_Uuid.AsString() in rail:continue
 anchors=[]
 for t in b.GetTracks():
  if t.m_Uuid.AsString() not in rail or isinstance(t,p.PCB_VIA) or t.GetLayer()!=p.F_Cu or t.GetWidth()<(350000 if input_pair else 500000):continue
  a,z=tuple(t.GetStart()),tuple(t.GetEnd());dx,dy=z[0]-a[0],z[1]-a[1];k=min(1,max(0,((pt[0]-a[0])*dx+(pt[1]-a[1])*dy)/max(1,dx**2+dy**2)));points=[(round(a[0]+k*dx),round(a[1]+k*dy)),a,z]
  for anc in points:
   if math.dist(anc,pt)<3900000:anchors.append(anc)
 selected=[]
 for a in sorted(set(anchors),key=lambda a:math.dist(a,pt)):
  if all(math.dist(a,z)>550000 for z in selected):selected.append(a)
 for a in selected:
  leg=route_leg(b,'+3V3_SYS',pt,p.B_Cu,a,p.F_Cu,500000,4.3,shifted=True,reuse_supply_barrels=[via for via in b.GetTracks() if isinstance(via,p.PCB_VIA) and via.m_Uuid.AsString() in rail])
  if not leg['connected']:
   held.append(dict(cap=ref,tap_nm=a,sites=leg.get('legal_sites'),both=leg.get('both_faces_reached')));continue
  folder=root/'runs'/(('rotated-buck-input-' if input_pair else 'rotated-bypass-source-')+ref);folder.mkdir(exist_ok=True)
  for cfg in ('phy-joint.kicad_dru','phy-joint.kicad_pro','fp-lib-table'):shutil.copy2(current.parent/cfg,folder/cfg)
  out=folder/current.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
  subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
  delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
  if delta:
   held.append(dict(cap=ref,tap_nm=a,drc=delta));b=p.LoadBoard(str(current));owners.append(b);continue
  old=p.LoadBoard(str(current));saved=p.LoadBoard(str(out));owners.extend([old,saved]);guard=verify_preservation(old,saved);assert pin(saved,ref).m_Uuid.AsString() in group(saved,pin(saved,source_ref,source_pin)) and not screen(saved)
  records.append(dict(part=ref,tap_nm=a,leg=leg,groups=guard['existing_connected_pad_groups_preserved']));summary=json.loads((current.parent/'output-legs.json').read_text());summary.update(board_sha256=digest(out),bypass_source=records);(folder/'output-legs.json').write_text(json.dumps(summary,indent=2)+'\n');current=out;print(ref,leg,flush=True);break
(root/('rotated-buck-input-pair.json' if input_pair else 'rotated-bypass-source-mixed.json')).write_text(json.dumps(dict(parent_sha256=meta['sha256'],board=str(current.relative_to(root)),sha256=digest(current),records=records,held=held,assembly_ready=False),indent=2)+'\n');print(len(records),len(held),flush=True);os._exit(0)
