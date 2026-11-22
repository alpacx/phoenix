"""Place one rotated RK809 input capacitor beside its pin, with a bounded pin neck and paired return."""
import hashlib,itertools,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make,route_leg
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
ldo='--released-io-cap' in sys.argv
base=json.loads((root/('rotated-buck-return-pairs.json' if ldo else 'rotated-existing-scl-complete.json')).read_text());src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));initial=p.LoadBoard(str(src))
ref,num=('C470','55') if ldo else ('C421','11') if '--buck1' in sys.argv else ('C422','10')
cap=b.FindFootprintByReference(ref);pin=b.FindFootprintByReference('U4').FindPadByNumber(num);code=pin.GetNetCode();side=p.F_Cu;primary=cap.FindPadByNumber('1');ground=cap.FindPadByNumber('2')
retired=[]
if ldo:
    b.BuildConnectivity()
    for q in (primary,ground):
        island=list(b.GetConnectivity().GetConnectedItems(q))
        assert all(not isinstance(x,p.PAD) or x.m_Uuid==q.m_Uuid for x in island)
        for t in island:
            if not isinstance(t,p.PCB_TRACK):continue
            assert not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.B_Cu and all((v-q.GetPosition()).EuclideanNorm()<1500000 for v in (t.GetStart(),t.GetEnd()))
            retired.append(t)
    for t in retired:b.Remove(t)
if cap.GetLayer()!=side:cap.Flip(cap.GetPosition(),False)
v=lambda xy:p.VECTOR2I(*xy);origin=pin.GetPosition();pm=b.FindFootprintByReference('U4');delta=origin-pm.GetPosition()
nx,ny=(int(math.copysign(1,delta.x)),0) if abs(delta.x)>abs(delta.y) else (0,int(math.copysign(1,delta.y)))
objects=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() if f.GetReference()!=ref for q in f.Pads()] if inflated_box(o,6500000).Contains(origin)]
geometry=[(o.GetNetCode(),o.GetEffectiveShape(side)) for o in objects if o.IsOnLayer(side)]
drills=[(o.GetNetCode(),o.GetEffectiveHoleShape()) for o in objects if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
other_courts=[f.GetCourtyard(side) for f in b.GetFootprints() if f.GetReference()!=ref and f.GetLayer()==side and inflated_box(f,6500000).Contains(origin)]
other_courts.extend(o.GetEffectiveShape(side) for o in objects if isinstance(o,p.PAD) and o.GetAttribute() in (p.PAD_ATTRIB_PTH,p.PAD_ATTRIB_NPTH))
edge=b.GetBoardEdgesBoundingBox();edge.Inflate(-252000)
def clear(item):
    shape=item.GetEffectiveShape(side);n=item.GetNetCode()
    return edge.Contains(item.GetBoundingBox()) and all(n==k or not shape.Collide(sh,202000) for k,sh in geometry) and all(n==k or not shape.Collide(h,252000) for k,h in drills)
def offset(d,t):return tuple(origin+p.VECTOR2I(nx*d-ny*t,ny*d+nx*t))
launches=[]
for w,inside,out,lat in itertools.product((200000,150000,127000),(250000,325000,375000),(600000,750000,900000),(0,50000,-50000,100000,-100000)):
    a,z=offset(inside,0),offset(out,lat)
    t=make(b,a,z,w,code,side)
    if t.GetLength()>740000 or not clear(t) or not t.GetEffectiveShape(side).Collide(pin.GetEffectiveShape(side),0):continue
    trunk=make(b,z,z,500000,code,side)
    if clear(trunk):launches.append((w,t,z))
counts=dict(launches=len(launches),courts=0,lands=0,power=0,grounds=0);poses=[];held=[]
for angle in (0,90,180,270):
    cap.SetOrientationDegrees(angle)
    for i,j in itertools.product(range(-20,21),repeat=2):
        cap.SetPosition(origin+p.VECTOR2I(i*200000,j*200000));court=cap.GetCourtyard(side)
        if not edge.Contains(court.BBox()) or any(court.Collide(c,50000) for c in other_courts):continue
        counts['courts']+=1
        if not all(clear(q) for q in cap.Pads()):continue
        counts['lands']+=1;cap_pos=tuple(primary.GetPosition())
        for w,neck,z in launches:
            t=make(b,z,cap_pos,500000,code,side)
            if t.GetLength()>2300000 or not clear(t) or t.GetEffectiveShape(side).Collide(ground.GetEffectiveShape(side),202000):continue
            counts['power']+=1;poses.append((t.GetLength()+neck.GetLength()-(w-127000)*2,tuple(cap.GetPosition()),angle,w,neck,t))
base_report=json.loads((src.parent/'drc.json').read_text());result=None;tried=set();folder=root/'runs'/('rotated-local-source-'+ref);folder.mkdir(exist_ok=True)
for cfg in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/cfg,folder/cfg)
for _,xy,angle,w,neck,t in sorted(poses,key=lambda row:row[:4]):
    if (xy,angle) in tried:continue
    tried.add((xy,angle));cap.SetPosition(v(xy));cap.SetOrientationDegrees(angle)
    if screen(b):continue
    before={o.m_Uuid.AsString() for o in b.GetTracks()};b.Add(neck);b.Add(t)
    ret=route_leg(b,'GND',tuple(ground.GetPosition()),side,tuple(ground.GetPosition()),p.In1_Cu,600000,2.4,shifted=True)
    if ret['connected']:
        counts['grounds']+=1;out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
        delta=introduced(base_report,json.loads((folder/'drc.json').read_text()))
        if not delta:
            saved=p.LoadBoard(str(out));guard=verify_preservation(initial,saved,replaced_copper={t.m_Uuid.AsString() for t in retired})
            for leg,ref2,num2 in [('1','U4',num),('2','U4','69')]:
                pad=saved.FindFootprintByReference(ref).FindPadByNumber(leg)
                assert saved.FindFootprintByReference(ref2).FindPadByNumber(num2).m_Uuid.AsString() in {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(pad)}
            result=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),pin=num,capacitor=ref,position_nm=xy,neck_width_mm=w/1e6,neck_length_mm=neck.GetLength()/1e6,positive_width_mm=.5,positive_mm=t.GetLength()/1e6,return_width_mm=.6,return_path=ret,preservation=guard,new_drc=delta);break
        held.append(dict(xy=xy,new_drc=delta))
    for o in list(b.GetTracks()):
        if o.m_Uuid.AsString() not in before:b.Remove(o)
report=dict(parent_sha256=base['sha256'],counts=counts,poses_tested=len(tried),rejected_drc=held,candidate=result,assembly_ready=False)
(root/('rotated-local-source-'+ref+'.json')).write_text(json.dumps(report,indent=2)+'\n');print(ref,counts,len(tried),bool(result),flush=True);os._exit(0)
