"""Relocate the existing 100 nF CPU bypass at a clean interstitial CPU supply via."""
import hashlib
import itertools
import json
import math
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_bounds import inflated_box
from pcb_power_leg import barrel, make, route_leg
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
record=lambda n:json.loads((root/(n+'.json')).read_text())
entry=record('layout-bga-referenced-barrel')
src=root/entry['board']
report=record('soc-cpu-decoupler-pitch-centers')
assert hashlib.sha256(src.read_bytes()).hexdigest()==entry['sha256']==report['parent_sha256']
paths={tuple(row['via_nm']):[row['source_nm'],row['via_nm']] for row in report['branch_options']}
original=p.LoadBoard(str(src));board=p.LoadBoard(str(src))
ref='C1601';foot=board.FindFootprintByReference(ref)
rail,gnd=[foot.FindPadByNumber(n) for n in ('1','2')]
side=p.B_Cu;point=lambda o:tuple(o.GetPosition());v=lambda xy:p.VECTOR2I(*xy)
center=(42025000,20325000)
parts=[f for f in board.GetFootprints() if f.GetReference()!=ref and inflated_box(f,5000000).Contains(v(center))]
courts=[f.GetCourtyard(side) for f in parts if f.GetLayer()==side and f.GetCourtyard(side).OutlineCount()]
objs=[q for f in parts for q in f.Pads() if q.IsOnLayer(side)]
objs.extend(t for t in board.GetTracks() if t.IsOnLayer(side) and inflated_box(t,5000000).Contains(v(center)))
obs=[(o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in objs]
holes=[o.GetEffectiveHoleShape() for o in objs if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
rules=[z.Outline() for z in board.Zones() if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
def clear(o):
    sh=o.GetEffectiveShape(side);bounds=inflated_box(o,350000)
    return not(any(bounds.Intersects(bb) and n!=o.GetNetCode() and sh.Collide(shape,202000) for n,shape,bb in obs) or
               any(sh.Collide(h,252000) for h in holes) or any(sh.Collide(poly,0) for poly in rules))
via_shapes={at:barrel(board,at,rail.GetNetCode()).GetEffectiveShape(side) for at in paths}
stats=Counter();poses=[]
for angle in (0,90,180,270):
    foot.SetOrientationDegrees(angle)
    for xx in range(395,448):
        for yy in range(179,233):
            pos=(xx*100000,yy*100000);foot.SetPosition(v(pos))
            pad=point(rail)
            options=[at for at in paths if math.dist(pad,at)<1500000]
            if not options:continue
            bounds=foot.GetCourtyard(side)
            if any(bounds.Collide(other,100000) for other in courts):continue
            stats['courtyard']+=1
            if not clear(rail) or not clear(gnd):continue
            stats['land']+=1
            usable=[]
            for at in options:
                if any(via_shapes[at].Collide(q.GetEffectiveShape(side),75000) for q in (rail,gnd)):continue
                tr=make(board,pad,at,250000,rail.GetNetCode(),side)
                if clear(tr) and not tr.GetEffectiveShape(side).Collide(gnd.GetEffectiveShape(side),202000):
                    usable.append(at)
            for at in usable:
                score=math.dist(at,pad)+math.dist(at,center)
                poses.append((score,pos,angle,(at,)))
stats['power_poses']=len(poses)
outcome=None
folder=root/'runs/soc-c1601-cap-local';folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):
    shutil.copy2(src.parent/name,folder/name)
for score,pos,angle,pair in sorted(poses)[:80]:
    candidate=p.LoadBoard(str(src));f=candidate.FindFootprintByReference(ref)
    f.SetOrientationDegrees(angle);f.SetPosition(v(pos));q=f.FindPadByNumber('1');code=q.GetNetCode()
    placed=set()
    for at in pair:
        candidate.Add(barrel(candidate,at,code))
        for u,w in zip(paths[at],paths[at][1:]):
            edge=tuple(sorted((tuple(u),tuple(w))))
            if edge not in placed:
                candidate.Add(make(candidate,u,w,250000,code,p.F_Cu));placed.add(edge)
        candidate.Add(make(candidate,point(q),at,250000,code,side))
    candidate.Add(make(candidate,(52370000,18150000),(52520000,18000000),300000,candidate.FindNet('GND').GetNetCode(),p.B_Cu))
    g=f.FindPadByNumber('2');pt=point(g)
    ret=route_leg(candidate,'GND',pt,side,pt,p.In4_Cu,300000,1.8,shifted=True)
    if not ret['connected']:continue
    stats['return']+=1
    target=folder/src.name
    p.ZONE_FILLER(candidate).Fill(candidate.Zones());p.SaveBoard(str(target),candidate)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(target)],capture_output=True,check=True)
    drc=lambda path:json.loads((path/'drc.json').read_text())
    diff=introduced(drc(src.parent),drc(folder))
    retired=set()
    original_copper={t.m_Uuid.AsString():t for t in original.GetTracks()}
    origin=original.FindFootprintByReference(ref).FindPadByNumber('2').GetPosition()
    for _ in range(5):
        if not diff or any(e['type'] not in ('track_dangling','via_dangling') for e in diff):break
        ids={uid for e in diff for uid in e['items']}
        if not all(uid in original_copper and original_copper[uid].GetNetname()=='GND'
                   and math.dist(tuple(origin),point(original_copper[uid]))<2500000 for uid in ids):break
        cleanup=p.LoadBoard(str(target))
        tracks={t.m_Uuid.AsString():t for t in cleanup.GetTracks()}
        for uid in ids:cleanup.Remove(tracks[uid])
        retired.update(ids)
        p.ZONE_FILLER(cleanup).Fill(cleanup.Zones());p.SaveBoard(str(target),cleanup)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(target)],capture_output=True,check=True)
        diff=introduced(drc(src.parent),drc(folder))
    if diff:
        stats.update(set('drc_'+e['type'] for e in diff));continue
    reopened=p.LoadBoard(str(target))
    if screen(reopened):continue
    preservation=verify_preservation(original,reopened,replaced_copper=retired)
    def check(n,other,pin):
        start=reopened.FindFootprintByReference(ref).FindPadByNumber(n)
        ids={x.m_Uuid.AsString() for x in reopened.GetConnectivity().GetConnectedItems(start)}
        assert reopened.FindFootprintByReference(other).FindPadByNumber(pin).m_Uuid.AsString() in ids
    check('1','U1','1H6');check('2','U4','69')
    outcome=dict(board=str(target.relative_to(root)),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                 cap_xy_nm=pos,via_pair_nm=pair,ground=ret,preservation=preservation,new_drc=diff,backside_branch_mm=score/1e6)
    break
(root/'soc-c1601-local-placement.json').write_text(json.dumps(dict(parent_sha256=entry['sha256'],tested=dict(stats),candidate=outcome,assembly_ready=False),indent=2)+'\n')
print(stats,bool(outcome),flush=True)
