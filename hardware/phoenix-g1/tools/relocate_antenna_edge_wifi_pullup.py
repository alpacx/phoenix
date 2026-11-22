"""Move a floating SDIO pull-up out of the selected antenna aperture and wire it near U25."""
from collections import Counter
import hashlib
import json
import math
import os
import shutil
import subprocess
from pathlib import Path
import sys
import pcbnew as p
import native_front_splice as bend
from pcb_preservation import verify_preservation
from pcb_bounds import inflated_box
from audit_mount_component_reservations import screen
from drc_regression import introduced

root = Path(__file__).resolve().parents[1] / "migration-rk3562/experiments/phy-power-parallel"
cp = json.loads((root / "rf-external-return-cleanup.json").read_text())
if "--analog-1v8" in sys.argv:
    cp=json.loads((root/"rf-edge-r1601-joined.json").read_text())["result"][0]
src = root/cp["board"]
assert hashlib.sha256(src.read_bytes()).hexdigest() == cp["sha256"]
b = p.LoadBoard(str(src))
crystal = "--crystal" in sys.argv
ref = "R2004" if crystal else "R2011"
number = "11" if crystal else "19"
secondary_net = "WIFI_XTAL_OUT" if crystal else "+3V3_IO"
anchor = "U25"
analog = "--analog-1v8" in sys.argv or "--analog-0v9" in sys.argv
if analog:
    one_eight = "--analog-1v8" in sys.argv
    ref = "R1602" if one_eight else "R1601"
    number = "1"
    anchor = "C1635" if one_eight else "C1642"
    secondary_net = "USB_AVDD_1V8" if one_eight else "USB_AVDD_0V9"
bank_first="--bank-first" in sys.argv
start_pin,end_pin="1","2"
if bank_first:
    assert analog
    start_pin,end_pin="2","1"
    anchor="C1682" if one_eight else "C1679"
    secondary_net="VCCA_1V8" if one_eight else "VDDA_0V9"
if "--main-pcb" in sys.argv:
    cp=json.loads((root/"layout-usb-analog-0v9.json").read_text())
    src=root/cp["board"];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp["sha256"];b=p.LoadBoard(str(src))
if "--source-pin" in sys.argv:
    assert ref=="R1602" and not bank_first
    cp=json.loads((root/"layout-usb-analog-0v9.json").read_text())
    src=root/cp["board"]
    assert hashlib.sha256(src.read_bytes()).hexdigest()==cp["sha256"]
    b=p.LoadBoard(str(src))
    anchor,number="U4","3"
result_name = "rf-edge-" + ref.lower() + ("-bank-first" if bank_first else "-joined" if "--join-bank" in sys.argv else "-recovery")
if "--source-pin" in sys.argv: result_name += "-source"
if "--main-pcb" in sys.argv: result_name += "-main"
moving_cap = "--load-cap" in sys.argv
if moving_cap:
    assert "--analog-1v8" in sys.argv
    cp=json.loads((root/"rf-edge-r1602-recovery-main.json").read_text())["result"][0]
    src=root/cp["board"];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp["sha256"];b=p.LoadBoard(str(src))
    ref="C1681" if "--cap1" in sys.argv else "C1682"
    anchor,number="R1602","2"
    secondary_net="GND"
    result_name="usb-analog-1v8-"+ref.lower()+("-restored" if "--clean-return" in sys.argv else "-local")
paired_cap="--package-cap" in sys.argv
if paired_cap:
    cp=json.loads((root/"layout-usb-analog-1v8.json").read_text())
    src=root/cp["board"];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp["sha256"];b=p.LoadBoard(str(src))
    ref,anchor,number,secondary_net="C1681","R1602","2","GND"
    moving_cap=True
    result_name="usb-analog-1v8-package-bypass"
    if "--cap-tap" in sys.argv:
        anchor,number="C1682","1";result_name+="-tap"
ldo="--ldo-cap" in sys.argv
if ldo:
    cp=json.loads((root/"layout-usb-analog-1v8.json").read_text())
    src=root/cp["board"];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp["sha256"];b=p.LoadBoard(str(src))
    first="--ldo-0v9" not in sys.argv
    ref="C466" if first else "C461"
    anchor="U4";number="3" if first else "21"
    secondary_net="GND"
    moving_cap=True
    result_name="usb-analog-local-ldo-"+ref.lower()
cpu_bypass='--cpu-local-decoupling' in sys.argv
load_bypass = '--local-analog-load' in sys.argv or cpu_bypass
if load_bypass:
    cp=json.loads((root/'layout-usb-direction-complete.json').read_text())
    src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
    b=p.LoadBoard(str(src))
    ref,anchor,number,secondary_net='C1681','C1682','1','GND'
    result_name='usb-analog-load-bank-c1681'
    if cpu_bypass:
        ref,anchor,number='C1601','C1603','1'
        result_name='cpu-local-c1601-decoupling'
    moving_cap=True
    analog=True
memory_bypass = '--memory-w1-bypass' in sys.argv
if memory_bypass:
    cp=json.loads((root/'layout-emmc-perimeter-supply.json').read_text())
    src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
    b=p.LoadBoard(str(src))
    ref,anchor,number,secondary_net='C1665','U2','W1','GND'
    result_name='memory-w1-c1665-bypass'
    if '--memory-bank' in sys.argv:
        anchor,number='C1649','1'
        result_name='memory-w1-c1665-local-bank'
        destination=next((arg.partition('=')[2] for arg in sys.argv if arg.startswith('--memory-tap=')),None)
        if destination:
            anchor=destination
            result_name+='-'+destination
        if '--memory-copper-tap' in sys.argv:
            result_name+='-rail'
        if '--memory-ground-plane' in sys.argv:result_name+='-plane'
        if '--whole-load-radius' in sys.argv:result_name+='-radius'
    moving_cap=True
    analog=True
r = b.FindFootprintByReference(ref)
module = b.FindFootprintByReference(anchor)
layer = module.GetLayer()
d1 = module.FindPadByNumber(number)
origin = d1.GetPosition()
toe=tuple(origin)
if ldo:
    bounds=d1.GetBoundingBox()
    toe=(bounds.GetLeft()-100000,origin.y) if first else (origin.x,bounds.GetBottom()+100000)
before = p.LoadBoard(str(src))
if r.GetLayer() != layer:
    r.Flip(r.GetPosition(), False)
obs = []
courts = []
rail = []
for f in b.GetFootprints():
    if f.GetReference() == ref or not inflated_box(f, 9000000).Contains(origin): continue
    if f.GetLayer() == layer: courts.append(f.GetCourtyard(layer).BBox())
    for q in f.Pads():
        if q.GetAttribute() in (p.PAD_ATTRIB_PTH,p.PAD_ATTRIB_NPTH): courts.append(q.GetBoundingBox())
        if q.IsOnLayer(layer):
            obs.append(q)
            if q.GetNetname() == secondary_net: rail.append(tuple(q.GetPosition()))
for t in b.GetTracks():
    if t.IsOnLayer(layer) and inflated_box(t, 9000000).Contains(origin):
        obs.append(t)
        if t.GetNetname() == secondary_net: rail.extend((tuple(t.GetStart()), tuple(t.GetEnd())))
geometry = [(o.GetNetCode(),o.GetEffectiveShape(layer)) for o in obs]
excluded_tracks=[zone.Outline() for zone in [*list(b.Zones()),*(zone for f in b.GetFootprints() for zone in f.Zones())] if zone.GetIsRuleArea() and zone.IsOnLayer(layer) and zone.GetDoNotAllowTracks()] if memory_bypass or load_bypass else []
def clean(obj):
    sh = obj.GetEffectiveShape(layer)
    return all(n == obj.GetNetCode() or not sh.Collide(other,200000) for n,other in geometry) and (not isinstance(obj,p.PCB_TRACK) or not any(sh.Collide(poly,0) for poly in excluded_tracks))
def seg(q, dest, width):
    t = p.PCB_TRACK(b)
    t.SetNetCode(q.GetNetCode())
    t.SetWidth(width)
    t.SetLayer(layer)
    t.SetStart(q.GetPosition())
    t.SetEnd(p.VECTOR2I(*dest))
    return t
flexible_taps=load_bypass or memory_bypass and '--memory-copper-tap' in sys.argv
tap_for_pose={}
supply_points=set()
if flexible_taps:
    b.BuildConnectivity()
    for o in b.GetConnectivity().GetConnectedItems(d1):
        if not o.IsOnLayer(layer):continue
        if isinstance(o,p.PAD):
            supply_points.add(tuple(o.GetPosition()))
        elif isinstance(o,p.PCB_TRACK) and not isinstance(o,p.PCB_VIA) and o.GetWidth()>=300000:
            start,end=tuple(o.GetStart()),tuple(o.GetEnd())
            steps=max(1,math.ceil(o.GetLength()/400000))
            for index in range(steps+1):
                supply_points.add(tuple(round(a+(z-a)*index/steps) for a,z in zip(start,end)))
counts = Counter()
sites = []
for a in (0,90,180,270):
    r.SetOrientationDegrees(a)
    placement_grid=range(-42,43) if '--whole-load-radius' in sys.argv else range(-22,23)
    for i in placement_grid:
        for j in placement_grid:
            pos = origin + p.VECTOR2I(i*200000,j*200000)
            if '--whole-load-radius' in sys.argv and (pos-origin).EuclideanNorm()>7600000:continue
            if analog and 26000000 < pos.x < 46500000 and pos.y > 31500000: continue
            r.SetPosition(pos)
            box = r.GetCourtyard(layer).BBox()
            if any(box.Intersects(o) for o in courts): continue
            counts["courtyard"] += 1
            q1,q2 = (r.FindPadByNumber(n) for n in (start_pin,end_pin))
            if memory_bypass or load_bypass:
                ball=(b.FindFootprintByReference('U1').FindPadByNumber('1G8' if cpu_bypass else '1M15') if load_bypass else b.FindFootprintByReference('U2').FindPadByNumber('W1')).GetPosition()
                previous=before.FindFootprintByReference(ref).FindPadByNumber('1').GetPosition()
                if (q1.GetPosition()-ball).EuclideanNorm()>(previous-ball).EuclideanNorm():continue
            if not (clean(q1) and clean(q2)): continue
            counts["pad_clearance"] += 1
            if flexible_taps:
                choices=sorted((math.dist(tuple(q1.GetPosition()),pt),pt) for pt in supply_points if math.dist(tuple(q1.GetPosition()),pt)<1600000)
                found=None
                for _,pt in choices:
                    tr=seg(q1,pt,300000)
                    if tr.GetLength() and clean(tr) and not tr.GetEffectiveShape(layer).Collide(q2.GetEffectiveShape(layer),200000):
                        found=pt;break
                if found is None:continue
                tap_for_pose[(tuple(pos),a)]=found;toe=found
            t1=seg(q1,toe,300000 if analog else 200000)
            if ldo and not t1.GetEffectiveShape(layer).Collide(d1.GetEffectiveShape(layer),0):continue
            if t1.GetLength()>3000000 or not clean(t1) or t1.GetEffectiveShape(layer).Collide(q2.GetEffectiveShape(layer),200000): continue
            sites.append((t1.GetLength(),tuple(pos),a,None))
            for target in set(rail):
                if moving_cap and math.dist(tuple(q2.GetPosition()),target)>1900000:continue
                t2 = seg(q2,target,300000 if analog else 250000)
                if t2.GetLength()>6000000 or not clean(t2):continue
                sh=t2.GetEffectiveShape(layer)
                if sh.Collide(q1.GetEffectiveShape(layer),200000) or sh.Collide(t1.GetEffectiveShape(layer),200000):continue
                sites.append((t1.GetLength()+t2.GetLength(),tuple(pos),a,target))
sites.sort(key=lambda s:(s[3] is None,s[0],s[1:3]))
if load_bypass:
    ball=tuple(b.FindFootprintByReference('U1').FindPadByNumber('1G8' if cpu_bypass else '1M15').GetPosition())
    sites.sort(key=lambda s:(round(math.dist(s[1],ball)/250000),s[3] is None,s[0]))
if paired_cap:
    package_ball=tuple(b.FindFootprintByReference("U1").FindPadByNumber("1M15").GetPosition())
    sites.sort(key=lambda s:(s[3] is None,round(math.dist(s[1],package_ball)/250000),s[0]))
print(counts, "candidates",len(sites),sum(s[3] is not None for s in sites),flush=True)
folder=root/"runs"/result_name
folder.mkdir(exist_ok=True)
for name in ("phy-joint.kicad_pro","phy-joint.kicad_dru","fp-lib-table"):
    shutil.copy2(src.parent/name,folder/name)
baseline=json.loads((src.parent/"drc.json").read_text())
res=[]
old_tracks={t.m_Uuid.AsString() for t in before.GetTracks()}
old_position=tuple(before.FindFootprintByReference(ref).GetPosition())
keep_alive=[]
for length,pos,a,target in sites[:30]:
    r.SetOrientationDegrees(a)
    r.SetPosition(p.VECTOR2I(*pos))
    if flexible_taps:toe=tap_for_pose[(pos,a)]
    routes=[seg(r.FindPadByNumber(start_pin),toe,300000 if analog else 200000)]
    if target is None and (load_bypass or '--memory-ground-plane' in sys.argv):
        from pcb_power_leg import route_leg
        q=r.FindPadByNumber(end_pin)
        original_ids={t.m_Uuid.AsString() for t in b.GetTracks()}
        b.Add(routes[0])
        at=tuple(q.GetPosition())
        ret=route_leg(b,'GND',at,layer,at,p.In4_Cu if layer==p.B_Cu else p.In1_Cu,300000,2.4,shifted=True)
        new=[t for t in b.GetTracks() if t.m_Uuid.AsString() not in original_ids and t.m_Uuid.AsString()!=routes[0].m_Uuid.AsString()]
        for t in [*new,routes[0]]:b.Remove(t)
        if not ret['connected']:continue
        routes.extend(new)
    elif target is None and (bank_first or "--join-bank" in sys.argv):
        bend.side=layer
        b.Add(routes[0])
        q=r.FindPadByNumber(end_pin)
        for goal in sorted(set(rail),key=lambda xy:math.dist(tuple(q.GetPosition()),xy)):
            if math.dist(tuple(q.GetPosition()),goal)>(7500000 if ref=="R1602" else 4500000):continue
            path,info=bend.recover(b,[(tuple(q.GetPosition()),goal,300000,q.GetNetCode())],secondary_net,None,search_all_obstacles=True)
            if path and info["length_mm"] <= 9.0:
                routes.extend(bend.wire(b,x,y,q.GetNetCode(),300000) for x,y in zip(path,path[1:]))
                break
        b.Remove(routes[0])
        if len(routes)==1:continue
    if target: routes.append(seg(r.FindPadByNumber(end_pin),target,300000 if analog else 250000))
    for t in routes:b.Add(t)
    p.ZONE_FILLER(b).Fill(b.Zones())
    out=folder/src.name
    p.SaveBoard(str(out),b)
    subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(out)],capture_output=True,check=True)
    delta=introduced(baseline,json.loads((folder/"drc.json").read_text()))
    saved=p.LoadBoard(str(out))
    retired=set()
    if moving_cap and "--clean-return" in sys.argv:
        for _ in range(5):
            if not delta or any(d["type"] not in ("via_dangling","track_dangling") for d in delta):break
            suspects={uid for d in delta for uid in d["items"]}
            copper={t.m_Uuid.AsString():t for t in saved.GetTracks()}
            if not all(uid in old_tracks and uid in copper and copper[uid].GetNetname()=="GND" and math.dist(tuple(copper[uid].GetPosition()),old_position)<3200000 for uid in suspects):break
            for uid in suspects:
                t=copper[uid];saved.Remove(t);keep_alive.append(t)
            retired.update(suspects)
            p.ZONE_FILLER(saved).Fill(saved.Zones());p.SaveBoard(str(out),saved)
            subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(out)],capture_output=True,check=True)
            delta=introduced(baseline,json.loads((folder/"drc.json").read_text()))
            keep_alive.append(saved);saved=p.LoadBoard(str(out))
    if moving_cap and delta:
        for t in routes:b.Remove(t)
        continue
    try:
        guard=verify_preservation(before,saved,replaced_copper=retired)
    except AssertionError:
        if not moving_cap:raise
        for t in routes:b.Remove(t)
        continue
    bld=saved.FindFootprintByReference(ref)
    actual={x.m_Uuid.AsString() for x in saved.GetConnectivity().GetConnectedItems(bld.FindPadByNumber(start_pin))}
    assert saved.FindFootprintByReference(anchor).FindPadByNumber(number).m_Uuid.AsString() in actual
    secondary_pads=sorted({f"{q.GetParentFootprint().GetReference()}.{q.GetNumber()}" for q in saved.GetConnectivity().GetConnectedItems(bld.FindPadByNumber(end_pin)) if isinstance(q,p.PAD) and q.GetParentFootprint().GetReference()!=ref})
    if bank_first or "--join-bank" in sys.argv:
        assert secondary_pads
    if not delta and not [v for v in screen(saved) if v["ref"]==ref]:
        res.append(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),r_position_nm=pos,angle=a,primary_anchor=anchor+"."+number,secondary_connected_pads=secondary_pads,signal_stub_mm=routes[0].GetLength()/1e6,rail_contact_nm=target,rail_trace_mm=sum(t.GetLength() for t in routes[1:])/1e6 if len(routes)>1 else None,preservation=guard,new_drc=delta))
        break
    for t in routes:b.Remove(t)
(root/(result_name+".json")).write_text(json.dumps(dict(parent_sha256=cp["sha256"],screen_counts=counts,candidates=len(sites),two_contact_candidates=sum(s[3] is not None for s in sites),result=res,assembly_ready=False),indent=2)+"\n")
print(res[0]["signal_stub_mm"] if res else "no passes",flush=True)
os._exit(0)
