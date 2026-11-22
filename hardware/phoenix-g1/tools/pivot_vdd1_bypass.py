"""Rotate an isolated VDD1 MLCC about its grounded land and join the memory-side bank."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_power_leg import make
from pcb_preservation import verify_preservation
from pcb_bounds import inflated_box

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda name:json.loads((root/name).read_text())
cp=read('layout-lpddr-vdd1-bank.json')
src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
baseline=p.LoadBoard(str(src))
folder=root/'runs/vdd1-fixed-return'
folder.mkdir(exist_ok=True)
for ext in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):
    shutil.copy2(src.parent/ext,folder/ext)
uid=lambda o:o.m_Uuid.AsString()
records=[]
current=src
for ref in ('C2303','C2301'):
    b=p.LoadBoard(str(current))
    b.BuildConnectivity()
    fp=b.FindFootprintByReference(ref)
    pad=fp.FindPadByNumber('1')
    ground=fp.FindPadByNumber('2')
    rail=b.FindFootprintByReference('C2305').FindPadByNumber('1')
    old=p.LoadBoard(str(current))
    pos=fp.GetPosition()
    angle=fp.GetOrientationDegrees()
    fixed=ground.GetPosition()
    side=fp.GetLayer()
    assert side==p.B_Cu and rail.GetNetCode()==pad.GetNetCode()
    if b.GetConnectivity().GetConnectedTracks(pad):
        records.append(dict(ref=ref,held='positive land already has attached copper'))
        continue
    rail_ids={uid(o) for o in b.GetConnectivity().GetConnectedItems(rail)}
    others=[x for x in b.GetFootprints() if uid(x)!=uid(fp)]
    copper=[*b.GetTracks(),*(q for x in others for q in x.Pads())]
    copper=[x for x in copper if inflated_box(x,8000000).Contains(pos)]
    goals=[]
    for x in copper:
        if uid(x) not in rail_ids or not x.IsOnLayer(side):continue
        if isinstance(x,p.PAD) or isinstance(x,p.PCB_VIA):goals.append(tuple(x.GetPosition()))
        elif x.GetWidth()>=500000:
            n=max(1,math.ceil(x.GetLength()/150000))
            goals.extend(tuple(round(a+(z-a)*i/n) for a,z in zip(x.GetStart(),x.GetEnd())) for i in range(n+1))
    obs=[(x.GetNetCode(),x.GetEffectiveShape(side)) for x in copper if x.IsOnLayer(side)]
    holes=[x.GetEffectiveHoleShape() for x in copper if isinstance(x,p.PCB_VIA) or isinstance(x,p.PAD) and x.GetDrillSize().x]
    courts=[x.GetCourtyard(side) for x in others if x.GetLayer()==side and inflated_box(x,2500000).Contains(pos)]
    guard_zones=[z.Outline() for z in b.Zones() if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
    result=dict(ref=ref,orientations=[])
    records.append(result)
    winner=False
    for change in (90,-90,180):
        fp.SetPosition(pos);fp.SetOrientationDegrees(angle+change)
        fp.SetPosition(pos+fixed-ground.GetPosition())
        assert tuple(ground.GetPosition())==tuple(fixed)
        if any(fp.GetCourtyard(side).Collide(c,100000) for c in courts):continue
        if any(q.GetEffectiveShape(side).Collide(g,202000) for q in fp.Pads() for code,g in obs if q.GetNetCode()!=code):continue
        if any(q.GetEffectiveShape(side).Collide(h,252000) for q in fp.Pads() for h in holes):continue
        record=dict(change_deg=change,clear_paths=0)
        result['orientations'].append(record)
        start=tuple(pad.GetPosition());code=pad.GetNetCode()
        blocks=[s for nc,s in obs if nc!=code]+[ground.GetEffectiveShape(side)]
        for goal in sorted(set(goals),key=lambda xy:math.dist(xy,start)):
            if math.dist(start,goal)>6000000:break
            dx,dy=(goal[i]-start[i] for i in range(2))
            diag=min(abs(dx),abs(dy))
            step=(round(math.copysign(diag,dx)),round(math.copysign(diag,dy)))
            for bend in (start,(start[0]+step[0],start[1]+step[1]),(goal[0]-step[0],goal[1]-step[1])):
                pts=(start,bend,goal)
                wires=[make(b,a,z,500000,code,side) for a,z in zip(pts,pts[1:]) if a!=z]
                if any(t.GetEffectiveShape(side).Collide(s,202000) for t in wires for s in blocks):continue
                if any(t.GetEffectiveShape(side).Collide(h,252000) for t in wires for h in holes):continue
                if any(t.GetEffectiveShape(side).Collide(z,0) for t in wires for z in guard_zones):continue
                record['clear_paths']+=1
                for t in wires:b.Add(t)
                folder2=folder/ref;folder2.mkdir(exist_ok=True)
                for ext in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/ext,folder2/ext)
                out=folder2/src.name
                p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
                dr=folder2/'drc.json'
                subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],check=True,capture_output=True)
                delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads(dr.read_text()))
                saved=p.LoadBoard(str(out));saved.BuildConnectivity()
                q=saved.FindFootprintByReference(ref).FindPadByNumber('1')
                group={uid(o) for o in saved.GetConnectivity().GetConnectedItems(q)}
                if not delta and uid(rail) in group and not screen(saved):
                    guard=verify_preservation(old,saved)
                    result.update(board=str(out.relative_to(root)),angle=change,path_nm=pts,preservation=guard)
                    current=out;winner=True;break
                for t in wires:b.Remove(t)
            if winner:break
        if winner:break
(root/'vdd1-fixed-return-pivot.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),records=records,assembly_ready=False),indent=2)+'\n')
print([(r['ref'],r.get('angle'),r.get('orientations')) for r in records])
