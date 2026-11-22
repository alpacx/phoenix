"""Create an SCLK escape by displacing R8001 while retaining its connected eMMC rail pad."""
from pathlib import Path
import hashlib,json,math,os,shutil,subprocess,sys
dir_site=next((int(a.split('=')[1]) for a in sys.argv if a.startswith('--dir-site=')),None)
pivot_dir='--rotate-dir-cap' in sys.argv
dir_mode=pivot_dir or '--mux-dir' in sys.argv or dir_site is not None
part_ref,pin_ref,pin_num,block_pin,support_pin=('C1665','U6','11','1','2') if dir_mode else ('R8001','U1','N3','2','1')
stem='usb-dir-cap-fanout' if dir_mode else 'lcd-clock-soc-launch'
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
if pivot_dir:stem+='-pivot'
if dir_site is not None:stem+='-'+str(dir_site)
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda k:json.loads((root/(k+'.json')).read_text());base=read('layout-emmc-perimeter-supply' if pivot_dir else 'layout-usb-enable-trunk' if dir_mode else 'layout-cpu-enable-bias');window=read('usb-mux-dir-window' if dir_mode else 'lcd_sclk-soc-window')
src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
if not pivot_dir:assert base['sha256']==window['parent_sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();part=b.FindFootprintByReference(part_ref);a=part.FindPadByNumber(support_pin);z=part.FindPadByNumber(block_pin);pin=b.FindFootprintByReference(pin_ref).FindPadByNumber(pin_num);uid=lambda o:o.m_Uuid.AsString();v=lambda xy:p.VECTOR2I(*xy)
c=next(row for row in window['single_obstacle_candidates'] if row['name']==part_ref+'.'+block_pin)
assert c['obstacles'][0][0]==uid(z)
if dir_site is not None:
    row=read('usb-mux-dir-cap-window')['sites'][dir_site];c=dict(path_nm=row['path_nm'],via_nm=row['path_nm'][-1],length_mm=row['length_mm'])
at=tuple(c['via_nm']);origin=tuple(part.GetPosition());pos_a=tuple(a.GetPosition());angle=part.GetOrientationDegrees();side=p.B_Cu
objects=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() if f.GetReference()!=part_ref for q in f.Pads()] if inflated_box(o,3500000).Contains(v(origin))]
contact=[k for k in objects if k.IsOnLayer(side) and k.GetNetCode()==a.GetNetCode() and k.GetEffectiveShape(side).Collide(a.GetEffectiveShape(side),0)]
shapes=[(o.GetNetCode(),o.GetEffectiveShape(side)) for o in objects if o.IsOnLayer(side)]
holes=[o.GetEffectiveHoleShape() for o in objects if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
courts=[f.GetCourtyard(side) for f in b.GetFootprints() if f.GetReference()!=part_ref and f.GetLayer()==side and inflated_box(f,3500000).Contains(v(origin))]
barrel=p.PCB_VIA(b);barrel.SetPosition(v(at));barrel.SetWidth(450000);barrel.SetDrill(200000);barrel.SetViaType(p.VIATYPE_THROUGH);barrel.SetLayerPair(p.F_Cu,p.B_Cu);barrel.SetNetCode(pin.GetNetCode())
def lines():
    pts=[c['path_nm'][0]]
    for pt,nxt in zip(c['path_nm'][1:],c['path_nm'][2:]+[None]):
        if nxt is not None:
            u,w=(pt[0]-pts[-1][0],pt[1]-pts[-1][1]),(nxt[0]-pt[0],nxt[1]-pt[1])
            if u[0]*w[1]==u[1]*w[0] and u[0]*w[0]+u[1]*w[1]>0:continue
        pts.append(pt)
    for a0,a1 in zip(pts,pts[1:]):
        t=p.PCB_TRACK(b);t.SetStart(v(a0));t.SetEnd(v(a1));t.SetLayer(p.F_Cu);t.SetNetCode(pin.GetNetCode());t.SetWidth(200000);yield t
items=[barrel]+list(lines());folder=root/'runs'/stem;folder.mkdir(exist_ok=True);out=folder/src.name
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
prior=json.loads((src.parent/'drc.json').read_text());rejected=[];winner=None;poses=[]
prior_to_load=None
if pivot_dir:
    load_lands=[q.GetPosition() for f in b.GetFootprints() if f.GetReference() in ('U1','U2') for q in f.Pads() if q.GetNetname()==z.GetNetname()]
    assert load_lands
    prior_to_load=min((pt-z.GetPosition()).EuclideanNorm() for pt in load_lands)
for off in ((90,-90,180) if pivot_dir else (0,) if dir_mode else (0,90,-90,180)):
    part.SetOrientationDegrees(angle+off);part.Move(v(pos_a)-a.GetPosition());aligned=tuple(part.GetPosition())
    for dx in range(-5,6):
        for dy in range(-5,6):
            pose=(aligned[0]+dx*50000,aligned[1]+dy*50000);part.SetPosition(v(pose))
            if pivot_dir and min((pt-z.GetPosition()).EuclideanNorm() for pt in load_lands)>prior_to_load: continue
            if not any(a.GetEffectiveShape(side).Collide(t.GetEffectiveShape(side),0) for t in contact):continue
            if any(part.GetCourtyard(side).Collide(k,100000) for k in courts):continue
            good=True
            for pad in part.Pads():
                sh=pad.GetEffectiveShape(side)
                if sh.Collide(barrel.GetEffectiveShape(side),202000) or sh.Collide(barrel.GetEffectiveHoleShape(),252000) or any(n!=pad.GetNetCode() and sh.Collide(s,202000) for n,s in shapes) or any(sh.Collide(h,252000) for h in holes):good=False;break
            if good:poses.append((math.dist(pose,origin),off,pose))
for _,off,pose in sorted(poses):
    part.SetOrientationDegrees(angle+off);part.SetPosition(v(pose))
    if screen(b):continue
    for t in items:b.Add(t)
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    delta=introduced(prior,json.loads((folder/'drc.json').read_text()))
    if all(d['type']=='via_dangling' and d['items']==[uid(barrel)] for d in delta):
        saved=p.LoadBoard(str(out));saved.BuildConnectivity();cpu=saved.FindFootprintByReference(pin_ref).FindPadByNumber(pin_num)
        if uid(barrel) in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(cpu)}:
            try:proof=verify_preservation(p.LoadBoard(str(src)),saved)
            except AssertionError:proof=None
            if proof:
                winner=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),preservation=proof,new_drc=delta,old_pos_nm=origin,pos_nm=pose,rotation_deg=off,via_uuid=uid(barrel),launch_mm=c['length_mm']);break
    rejected.append(dict(pose=pose,delta=delta))
    for t in items:b.Remove(t)
    if len(rejected)>=10:break
(root/(stem+'.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],candidate=winner,poses=len(poses),rejected=rejected,assembly_ready=False),indent=2)+'\n');print(bool(winner),len(poses),len(rejected),flush=True);os._exit(0)
