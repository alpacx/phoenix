"""Screen a pivot of C424 on its ground contacts to release two independently reachable return barrels."""
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import pcbnew as pcb
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_bounds import inflated_box
from pcb_power_leg import barrel
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'rotated-buck-return-pairs.json').read_text());src=root/base['board']
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
assert digest(src)==base['sha256']
evidence=json.loads((root/'rotated-buck-plane-barrel-screen.json').read_text())
zone=json.loads((root/'rotated-buck-return-zone.json').read_text())
assert evidence['board_sha256']==zone['sha256'] and zone['parent_sha256']==base['sha256']
old=pcb.LoadBoard(str(src));b=pcb.LoadBoard(str(src));b.BuildConnectivity()
cap=b.FindFootprintByReference('C424');side=cap.GetLayer();positive=cap.FindPadByNumber('1');g=cap.FindPadByNumber('2')
origin=cap.GetPosition();ground_origin=g.GetPosition();angle=cap.GetOrientationDegrees()
package=b.FindFootprintByReference('U4').FindPadByNumber('45');limit=(positive.GetPosition()-package.GetPosition()).EuclideanNorm()
assert len([o for o in b.GetConnectivity().GetConnectedItems(positive) if isinstance(o,pcb.PAD)])==1
objects=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() if f.GetReference()!='C424' for q in f.Pads()] if inflated_box(o,5500000).Contains(origin)]
courts=[f.GetCourtyard(side) for f in b.GetFootprints() if f.GetReference()!='C424' and f.GetLayer()==side and inflated_box(f,5500000).Contains(origin)]
contacts={tuple(pt) for o in objects if isinstance(o,pcb.PCB_TRACK) and o.IsOnLayer(side) and o.GetNetCode()==g.GetNetCode() for pt in (o.GetStart(),o.GetEnd()) if g.HitTest(pt)}
shapes=[(o.GetNetCode(),o.GetEffectiveShape(side)) for o in objects if o.IsOnLayer(side)]
holes=[(o.GetNetCode(),o.GetEffectiveHoleShape()) for o in objects if isinstance(o,pcb.PCB_VIA) or isinstance(o,pcb.PAD) and o.GetDrillSize().x]
options={k:v['single_land_relief'].get('C424.1',[]) for k,v in evidence['candidate_centres'].items()}
via=barrel(b,(0,0),g.GetNetCode())
stages=dict(courtyard=0,pad_contacts=0,positive_distance=0,clear=0,two_barrels=0);candidates=[]
for turn,i,j in itertools.product((0,90,180,270),range(-6,7),range(-6,7)):
    if not (turn or i or j):continue
    cap.SetOrientationDegrees(angle+turn);cap.Move(ground_origin-g.GetPosition()+pcb.VECTOR2I(i*100000,j*100000))
    if any(cap.GetCourtyard(side).Collide(c,50000) for c in courts):continue
    stages['courtyard']+=1
    if any(not g.HitTest(pcb.VECTOR2I(*pt)) for pt in contacts):continue
    stages['pad_contacts']+=1
    dist=(positive.GetPosition()-package.GetPosition()).EuclideanNorm()
    if dist>limit:continue
    stages['positive_distance']+=1
    if any(q.GetNetCode()!=n and q.GetEffectiveShape(side).Collide(sh,202000) for q in cap.Pads() for n,sh in shapes):continue
    if any(q.GetNetCode()!=n and q.GetEffectiveShape(side).Collide(sh,252000) for q in cap.Pads() for n,sh in holes):continue
    stages['clear']+=1
    for name,rows in options.items():
        relative=[]
        for x,y,length in rows:
            via.SetPosition(pcb.VECTOR2I(x,y))
            if any(via.GetEffectiveShape(side).Collide(q.GetEffectiveShape(side),202000) or via.GetEffectiveHoleShape().Collide(q.GetEffectiveShape(side),252000) for q in cap.Pads()):continue
            relative.append(((x,y),length))
        pairs=[(a,z) for a,z in itertools.combinations(relative,2) if 600000<=math.dist(a[0],z[0])<=1050000]
        if pairs:
            best=min(pairs,key=lambda pair:sum(entry[1] for entry in pair));candidates.append((dist,math.dist(tuple(cap.GetPosition()),tuple(origin)),name,angle+turn,tuple(cap.GetPosition()),best));stages['two_barrels']+=1
winner=None;tested=set()
for dist,move,name,theta,center,sites in sorted(candidates):
    if (center,theta) in tested:continue
    tested.add((center,theta));cap.SetOrientationDegrees(theta);cap.SetPosition(pcb.VECTOR2I(*center))
    if screen(b):continue
    folder=root/'runs/rotated-buck-window-c424';folder.mkdir(exist_ok=True)
    for cfg in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/cfg,folder/cfg)
    out=folder/src.name;pcb.ZONE_FILLER(b).Fill(b.Zones());pcb.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if delta:continue
    saved=pcb.LoadBoard(str(out));guard=verify_preservation(old,saved)
    winner=dict(board=str(out.relative_to(root)),sha256=digest(out),target_cap=name,sites=sites,centre_nm=center,angle=theta,original_distance_mm=limit/1e6,new_distance_mm=dist/1e6,preservation=guard)
    break
(root/'rotated-buck-window-c424.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],screen=stages,required_original_ground_contacts=len(contacts),candidate=winner,assembly_ready=False),indent=2)+'\n')
print(stages,winner and winner['target_cap'],flush=True);os._exit(0)
