"""Restore capacitor return paths on the rotated RK809 engineering coupon."""
from pathlib import Path
import hashlib,json,math,os,shutil,subprocess,sys
import pcbnew as p
from drc_regression import introduced
from pcb_power_leg import route_leg
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
mixed='--mixed-barrels' in sys.argv
filled='--filled-cap-land' in sys.argv
edge='--edge-aware' in sys.argv
bent='--bent-near' in sys.argv or edge or filled or mixed
near_plane='--nearest-plane' in sys.argv or bent
base=root/'runs'/('rotated-bypass-source-C483' if mixed else 'rotated-left-sda-trunk-R415.2-U4.2' if filled else 'rotated-bent-plane-C412' if edge else 'rotated-package-ground-necks' if bent else 'rotated-restore-return-C482' if near_plane else 'pmic-five-stage-secondary-0');source=base/'phy-joint.kicad_pcb'
meta=json.loads((base/'output-legs.json').read_text());digest=lambda file:hashlib.sha256(file.read_bytes()).hexdigest()
assert digest(source)==meta['board_sha256']
current=source;records=[];tries=[];uid=lambda q:q.m_Uuid.AsString()
def pin(board,ref,n):return board.FindFootprintByReference(ref).FindPadByNumber(n)
def connected(b,q):return {uid(o) for o in b.GetConnectivity().GetConnectedItems(q)}
for name in ('C431','C432','C433','C421','C422','C423','C424','C480','C481','C482','C483','C484','C485','C470','C412'):
    if edge and name!="C432":continue
    b=p.LoadBoard(str(current));b.BuildConnectivity();q=pin(b,name,'2');g=pin(b,'U4','69')
    assert q.GetNetname()=='GND'
    if uid(q) in connected(b,g):continue
    side=q.GetParentFootprint().GetLayer()
    w=600000 if name in ('C431','C432','C433','C421','C422','C423','C424') else 300000
    center=tuple(q.GetPosition());shape=q.GetEffectiveShape(side);success=None
    options=[(0,center)]+sorted((math.hypot(x,y),(center[0]+x,center[1]+y)) for x in (-150000,0,150000) for y in (-150000,0,150000) if (x or y) and q.HitTest(p.VECTOR2I(center[0]+x,center[1]+y)))
    if mixed:
        # Sample well inside the existing rectangular land, preserving its attachment width.
        box=q.GetBoundingBox()
        step=100000
        options += sorted((math.dist(center,pt),pt) for x in range(box.GetLeft()+w//2,box.GetRight()-w//2,step) for y in range(box.GetTop()+w//2,box.GetBottom()-w//2,step) for pt in [(x,y)] if q.HitTest(p.VECTOR2I(*pt)) and all(math.dist(pt,old[1])>50000 for old in options))
    grounded=connected(b,g)
    barrels=[v for v in b.GetTracks() if isinstance(v,p.PCB_VIA) and uid(v) in grounded and math.dist(tuple(v.GetPosition()),center)<2800000] if mixed else []
    for _,pos in options:
        new=route_leg(b,'GND',pos,side,pos,p.In4_Cu if near_plane and side==p.B_Cu else p.In1_Cu,w,2.4,passive_vip=filled,shifted=bent,reuse_supply_barrels=barrels)
        if new['connected']:
            success=new;break
    if not success:
        tries.append(dict(part=name,land_positions=len(options),reason='no paired via or existing barrel pair'));continue
    folder=root/'runs'/(('rotated-mixed-gnd-' if mixed else 'rotated-filled-gnd-' if filled else 'rotated-edge-aware-' if edge else 'rotated-bent-plane-' if bent else 'rotated-short-plane-' if near_plane else 'rotated-restore-return-')+name);folder.mkdir(exist_ok=True)
    for cfg in ('fp-lib-table','phy-joint.kicad_pro','phy-joint.kicad_dru'):shutil.copy2(current.parent/cfg,folder/cfg)
    out=folder/source.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    saved=p.LoadBoard(str(out));saved.BuildConnectivity()
    if delta or uid(pin(saved,name,'2')) not in connected(saved,pin(saved,'U4','69')):
        tries.append(dict(part=name,reason='saved circuit or DRC',new_drc=delta));continue
    orig=p.LoadBoard(str(current));pres=verify_preservation(orig,saved)
    assert not screen(saved)
    records.append(dict(part=name,pair=[name+'.2','U4.69'],width_mm=w/1e6,layout=success,existing_groups=pres['existing_connected_pad_groups_preserved']))
    current=out
    progress=dict(meta,board_sha256=digest(out),parent_coupon_sha256=digest(source),restored_ground_banks=(meta.get('restored_ground_banks',[]) if mixed else [])+records,failed_ground_banks=tries)
    (folder/'output-legs.json').write_text(json.dumps(progress,indent=2)+'\n')
    print(name,success['kind'],flush=True)
(root/('rotated-mixed-ground-returns.json' if mixed else 'rotated-pmic-filled-cap-returns.json' if filled else 'rotated-pmic-edge-aware-returns.json' if edge else 'rotated-pmic-bent-plane-returns.json' if bent else 'rotated-pmic-short-plane-returns.json' if near_plane else 'rotated-pmic-return-banks.json')).write_text(json.dumps(dict(source_sha256=digest(source),board=str(current.relative_to(root)),sha256=digest(current),restored=records,attempted=tries,assembly_ready=False),indent=2)+'\n')
print('restored',len(records),'unresolved',len(tries),flush=True);os._exit(0)
