"""Place PWRON_N's 100 nF capacitor beside the RK809 and close both land groups."""
from pathlib import Path
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
rotated='--rotated' in sys.argv
meta=json.loads((root/('rotated-bypass-source-mixed.json' if rotated else 'layout-soc-tx-series.json')).read_text());src=root/meta['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
ref=b.FindFootprintByReference('C412')
signal=ref.FindPadByNumber('1');ground=ref.FindPadByNumber('2')
pin=b.FindFootprintByReference('U4').FindPadByNumber('52');pos=pin.GetPosition()
assert ref.GetValue()=='100n' and signal.GetNetname()==pin.GetNetname()=='PMIC_PWRON_N' and ground.GetNetname()=='GND'
obsolete={'7bf6e5fa-46b7-490b-a63e-fc42414ff413','62729452-a410-45ec-bf72-699f6a813fe5'}
if rotated:
    assert '--rear' not in sys.argv
    parent_metadata=json.loads((src.parent/'output-legs.json').read_text())
    branches=next(row['layout']['branches_nm'] for row in parent_metadata['restored_ground_banks'] if row['part']=='C412')
    segments={tuple(sorted((tuple(a),tuple(z)))) for path in branches for a,z in zip(path,path[1:])}
    obsolete={t.m_Uuid.AsString() for t in b.GetTracks() if t.GetLayer()==p.B_Cu and t.GetNetname()=='GND' and tuple(sorted((tuple(t.GetStart()),tuple(t.GetEnd())))) in segments}
    assert len(obsolete)==len(segments)
    ref.Flip(ref.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
original_tracks=list(b.GetTracks())
for old in original_tracks:
    if old.m_Uuid.AsString() in obsolete:
        assert old.GetNetname()=='GND';b.Remove(old)
rear='--rear' in sys.argv
launch_tracks=[];launchpoint=None;pincontact=pin
if rear:
    ref.Flip(ref.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
    trials=json.loads((root/'pmic-pwron-launches.json').read_text())
    assert trials['coupon_sha256']==meta['sha256']
    choice=min((q for r in trials['circuits'] for q in r['via_paths']),key=lambda q:q['length_mm'])
    raw=choice['track_nm'];pts=[]
    for xy in raw:
        if pts and pts[-1]==xy:continue
        if len(pts)>1:
            i,j=pts[-2:];d=(j[0]-i[0],j[1]-i[1]);e=(xy[0]-j[0],xy[1]-j[1])
            if d[0]*e[1]==d[1]*e[0] and d[0]*e[0]+d[1]*e[1]>0:pts.pop()
        pts.append(xy)
    for a,z in zip(pts,pts[1:]):
        t=p.PCB_TRACK(b);t.SetWidth(200000);t.SetNetCode(signal.GetNetCode());t.SetLayer(p.F_Cu);t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z));launch_tracks.append(t)
    assert launch_tracks[0].GetEffectiveShape(p.F_Cu).Collide(pin.GetEffectiveShape(p.F_Cu),0)
    launchpoint=p.VECTOR2I(*choice['via_nm'])
    v=p.PCB_VIA(b);v.SetNetCode(signal.GetNetCode());v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetWidth(450000);v.SetDrill(200000);v.SetPosition(launchpoint);launch_tracks.append(v);pincontact=v
    for t in launch_tracks:b.Add(t)
allitems=[x for x in [t for t in original_tracks if t.m_Uuid.AsString() not in obsolete]+[o for f in b.GetFootprints() if f.GetReference()!='C412' for o in f.Pads()] if inflated_box(x,6000000).Contains(pos)]
side=p.B_Cu if rear else p.F_Cu;geom=[(x.GetNetCode(),x.GetEffectiveShape(side),x.GetBoundingBox()) for x in allitems if x.IsOnLayer(side)]
holes=[(x.GetNetCode(),x.GetEffectiveHoleShape()) for x in allitems if isinstance(x,p.PCB_VIA)]
courts=[f.GetCourtyard(side) for f in b.GetFootprints() if f.GetLayer()==side and f.GetReference()!='C412' and inflated_box(f,6000000).Contains(pos)]
areas=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.IsOnLayer(side) and z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
def clean(obj):
    box=inflated_box(obj,350000);sh=obj.GetEffectiveShape(side);code=obj.GetNetCode()
    return not(any(code!=c and box.Intersects(bb) and sh.Collide(g,202000) for c,g,bb in geom) or any(code!=c and sh.Collide(h,250000) for c,h in holes) or any(sh.Collide(a,0) for a in areas))
def route(a,z,width,code,avoid):
    dd=z-a;tail=min(abs(dd.x),abs(dd.y));diag=p.VECTOR2I(int(math.copysign(tail,dd.x)),int(math.copysign(tail,dd.y)))
    for corner in (a+diag,z-diag):
        lines=[]
        for start,end in ((a,corner),(corner,z)):
            if start==end:continue
            t=p.PCB_TRACK(b);t.SetLayer(side);t.SetNetCode(code);t.SetWidth(width);t.SetStart(start);t.SetEnd(end)
            if not clean(t) or t.GetEffectiveShape(side).Collide(avoid,202000):break
            lines.append(t)
        else:
            if lines:return lines
    return []
gnd=ground.GetNetCode();gnodes=set()
island={q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference('U4').FindPadByNumber('69'))}
for o in allitems:
    if o.GetNetCode()!=gnd or not o.IsOnLayer(side) or o.m_Uuid.AsString() not in island:continue
    if isinstance(o,(p.PAD,p.PCB_VIA)):gnodes.add(tuple(o.GetPosition()))
    else:gnodes.update((tuple(o.GetStart()),tuple(o.GetEnd())))
options=[]; counts=[0,0,0]
toes=[pos+p.VECTOR2I(dx,dy) for dx,dy in [(0,-440000),(100000,-350000),(110000,0),(100000,350000),(0,440000)]]
if rotated:
    relative=pos-b.FindFootprintByReference('U4').GetPosition()
    direction=(int(math.copysign(1,relative.x)),0) if abs(relative.x)>abs(relative.y) else (0,int(math.copysign(1,relative.y)))
    nx,ny=direction
    toes=[pos+p.VECTOR2I(nx*d-ny*h,ny*d+nx*h) for d in (-350000,0,325000,425000) for h in (0,80000,-80000)]
if rear:toes=[launchpoint]
for angle in (0,90,180,270):
    ref.SetOrientationDegrees(angle)
    for x in (range(-40,41,2) if rotated else range(-12,48,2)):
        for y in (range(-40,41,2) if rotated else range(-44,30,2)):
            center=pos+p.VECTOR2I(x*100000,y*100000);ref.SetPosition(center)
            if any(ref.GetCourtyard(side).Collide(c,100000) for c in courts) or not clean(signal) or not clean(ground):continue
            counts[0]+=1
            for toe in toes:
                if math.dist(tuple(toe),tuple(signal.GetPosition()))>3500000:continue
                lines=route(toe,signal.GetPosition(),200000,signal.GetNetCode(),ground.GetEffectiveShape(side))
                if not lines or not lines[0].GetEffectiveShape(side).Collide(pincontact.GetEffectiveShape(side),0):continue
                counts[1]+=1
                ground_pt=ground.GetPosition()
                for pt in sorted(gnodes,key=lambda c:math.dist(c,tuple(ground_pt))):
                    if math.dist(pt,tuple(ground_pt))>2000000:break
                    g=route(ground_pt,p.VECTOR2I(*pt),300000,gnd,signal.GetEffectiveShape(side))
                    if not g or any(v.GetEffectiveShape(side).Collide(w.GetEffectiveShape(side),202000) for v in lines for w in g):continue
                    counts[2]+=1
                    total=sum(q.GetLength() for q in lines+g)
                    options.append((total,angle,tuple(center),tuple(toe),pt));break
accepted=False;attempts=[]
folder=root/('runs/rotated-pwron-front-filter' if rotated else 'runs/pmic-pwron-rear-filter' if rear else 'runs/pmic-pwron-filter');folder.mkdir(exist_ok=True)
for total,angle,xy,toe,dest in sorted(options)[:15]:
    ref.SetOrientationDegrees(angle);ref.SetPosition(p.VECTOR2I(*xy))
    if screen(b):continue
    lines=route(p.VECTOR2I(*toe),signal.GetPosition(),200000,signal.GetNetCode(),ground.GetEffectiveShape(side))
    returns=route(ground.GetPosition(),p.VECTOR2I(*dest),300000,gnd,signal.GetEffectiveShape(side))
    for t in lines+returns:b.Add(t)
    for n in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/n,folder/n)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    attempts.append(dict(xy_nm=xy,signal_mm=sum(t.GetLength() for t in lines)/1e6,ground_mm=sum(t.GetLength() for t in returns)/1e6,delta=delta))
    if not delta:
        saved=p.LoadBoard(str(out));saved.BuildConnectivity();audit=verify_preservation(p.LoadBoard(str(src)),saved,replaced_copper=obsolete)
        q=saved.FindFootprintByReference('C412').FindPadByNumber('1')
        assert pin.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(q)}
        if rotated:
            assert ground.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('U4').FindPadByNumber('69'))}
            parent_metadata.update(board_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),pwron_filter_front=attempts[-1])
            (folder/'output-legs.json').write_text(json.dumps(parent_metadata,indent=2)+'\n')
        accepted=True;break
    for t in lines+returns:b.Remove(t)
report=dict(parent_sha256=meta['sha256'],adopted=accepted,search_counts=counts,attempts=attempts)
if accepted: report.update(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),preservation=audit,pair=['U4.52','C412.1'])
(root/('rotated-pwron-front-filter.json' if rotated else 'pmic-pwron-rear-filter.json' if rear else 'pmic-pwron-filter.json')).write_text(json.dumps(report,indent=2)+'\n')
print(accepted,counts,len(attempts),flush=True);os._exit(0)
