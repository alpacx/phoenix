"""Clear one rear 1.1-V trunk by minimally translating the obstructing grounded MLCC."""
from collections import Counter
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_bounds import inflated_box
from pcb_power_leg import make
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda name:json.loads((root/(name+'.json')).read_text())
cp=read('layout-memory-bank-rear-taps');cases=read('memory-bank-rear-obstructions')
src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']==cases['parent_sha256']
original=p.LoadBoard(str(src));folder=root/'runs/memory-bank-cap-relief';folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
carry='--carry-return' in sys.argv
outcome=None;tried=[]
for case in cases['shortest_obstructions']:
    hits=case['blockers']
    if len(hits)!=1 or hits[0][1]!='PAD' or hits[0][3] not in ('C1648','C1653'):continue
    ref=hits[0][3];b=p.LoadBoard(str(src));f=b.FindFootprintByReference(ref)
    origin=tuple(f.GetPosition());layer=f.GetLayer()
    wire=make(b,case['start_nm'],case['end_nm'],500000,b.FindNet('+1V1_LPDDR4').GetNetCode(),layer)
    sh=wire.GetEffectiveShape(layer)
    parts=[o for o in b.GetFootprints() if o.GetReference()!=ref and inflated_box(o,2500000).Contains(f.GetPosition())]
    courts=[other.GetCourtyard(layer) for other in parts if other.GetLayer()==layer and other.GetCourtyard(layer).OutlineCount()]
    objects=[*b.GetTracks(),*(pad for other in parts for pad in other.Pads())]
    objects=[o for o in objects if inflated_box(o,2000000).Contains(f.GetPosition())]
    carried=set()
    if carry:
        via=next(t for t in b.GetTracks() if t.m_Uuid.AsString()=={'C1648':'624452ae-bb71-4109-8f93-bee697a812b8','C1653':'ab62826f-49c2-4d8f-87b3-733941841164'}[ref])
        via_origin=via.GetPosition();ground=f.FindPadByNumber('2')
        spur,=[t for t in b.GetTracks() if not isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND' and t.GetLayer()==layer and {tuple(t.GetStart()),tuple(t.GetEnd())}=={tuple(ground.GetPosition()),tuple(via_origin)}]
        begin,end=spur.GetStart(),spur.GetEnd()
        carried={via.m_Uuid.AsString(),spur.m_Uuid.AsString()}
        objects=[o for o in objects if o.m_Uuid.AsString() not in carried]
        all_layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
        foreign=[(o.GetEffectiveShape(l),l) for o in objects if o.GetNetCode()!=via.GetNetCode() for l in all_layers if o.IsOnLayer(l)]
        via_rules=[z.Outline() for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    shapes=[(o,o.GetNetCode(),o.GetEffectiveShape(layer)) for o in objects if o.IsOnLayer(layer)]
    holes=[(o,o.GetEffectiveHoleShape()) for o in objects if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    audit_drc=lambda path:json.loads((path/'drc.json').read_text())
    b.Add(wire)
    offsets=sorted((math.hypot(dx,dy),dx,dy) for dx in range(-15,16) for dy in range(-15,16) if 0<math.hypot(dx,dy)<=15)
    stages=Counter()
    obstruction_counts=Counter()
    screened=0
    for _,dx,dy in offsets:
        pos=origin[0]+dx*25000,origin[1]+dy*25000
        f.SetPosition(p.VECTOR2I(*pos))
        if carry:
            shift=p.VECTOR2I(dx*25000,dy*25000)
            via.SetPosition(via_origin+shift)
            spur.SetStart(begin+shift);spur.SetEnd(end+shift)
            barrel=via.GetEffectiveShape(p.F_Cu);hole=via.GetEffectiveHoleShape()
            if any(barrel.Collide(geom,202000) or hole.Collide(geom,252000) for geom,l in foreign):continue
            if any(hole.Collide(h,252000) or barrel.Collide(h,252000) for _,h in holes):continue
            if any(barrel.Collide(poly,0) for poly in via_rules):continue
            if any(q.GetEffectiveShape(layer).Collide(hole,252000) for q in f.Pads()):continue
            if sh.Collide(barrel,202000) or sh.Collide(hole,252000) or sh.Collide(spur.GetEffectiveShape(layer),202000):continue
            stages["barrel"]+=1
        if any(f.GetCourtyard(layer).Collide(c,100000) for c in courts):continue
        stages["courtyard"]+=1
        pads=list(f.Pads())
        if sh.Collide(f.FindPadByNumber('2').GetEffectiveShape(layer),202000):continue
        stages["trunk"]+=1
        blocked={(o.GetNetname(),o.GetClass(),o.m_Uuid.AsString(),"copper")
                 for q in pads for o,n,shape in shapes if q.GetNetCode()!=n and q.GetEffectiveShape(layer).Collide(shape,202000)}
        blocked.update((o.GetNetname(),o.GetClass(),o.m_Uuid.AsString(),"drill") for q in pads for o,h in holes if q.GetEffectiveShape(layer).Collide(h,252000))
        if blocked:
            obstruction_counts[tuple(sorted(blocked))]+=1
            continue
        stages["land"]+=1
        b.BuildConnectivity()
        def joins(board,r,n,r2,n2):
            q=board.FindFootprintByReference(r).FindPadByNumber(n)
            ids={x.m_Uuid.AsString() for x in board.GetConnectivity().GetConnectedItems(q)}
            return board.FindFootprintByReference(r2).FindPadByNumber(n2).m_Uuid.AsString() in ids
        stages['rail_connected']+=int(joins(b,ref,'1','U2','AB4'))
        stages['gnd_connected']+=int(joins(b,ref,'2','U4','69'))
        stages['banks_connected']+=int(joins(b,'C1663','1','U2','AB4'))
        if not (joins(b,ref,'1','U2','AB4') and joins(b,ref,'2','U4','69') and joins(b,'C1663','1','U2','AB4')):continue
        screened+=1
        out=folder/src.name
        p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
        diff=introduced(audit_drc(src.parent),audit_drc(folder))
        if diff:continue
        saved=p.LoadBoard(str(out))
        if screen(saved):continue
        try:pres=verify_preservation(original,saved,replaced_copper=carried)
        except AssertionError:continue
        assert joins(saved,'C1663','1','U2','AB4') and joins(saved,ref,'2','U4','69')
        outcome=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),changed_ref=ref,shift_nm=[dx*25000,dy*25000],
                     width_mm=.5,length_mm=wire.GetLength()/1e6,new_drc=diff,preservation=pres)
        break
    tried.append(dict(ref=ref,copper_passes=screened,stages=dict(stages),minimum_obstructions=sorted(obstruction_counts.items(),key=lambda k:(len(k[0]),-k[1]))[:3]))
    if outcome:break
(root/('memory-bank-cap-and-return.json' if carry else 'memory-bank-cap-relief.json')).write_text(json.dumps(dict(parent_sha256=cp['sha256'],trials=tried,candidate=outcome,assembly_ready=False),indent=2)+'\n')
print(tried,outcome and (outcome['shift_nm'],outcome['length_mm']),flush=True)
