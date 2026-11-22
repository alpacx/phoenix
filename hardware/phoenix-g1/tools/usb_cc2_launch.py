"""Move the CC2 launch away from the row-B USB2 escape, preserving its other endpoints."""
from pathlib import Path
import hashlib
import json
import math
import os
import shutil
import subprocess
import pcbnew as p
from pcb_bounds import inflated_box, point_distance_squared
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'usb-contact-corridor.json').read_text())
src=root/meta['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
b=p.LoadBoard(str(src))
removed={'0cd03017-7a47-435c-809c-0932accb433d','cd40213e-5cea-40d0-babe-8dc01d2c5f9d','fbd8e1cb-c4ff-4df4-afbf-80e74d3de64a','4b352c41-58d4-4276-a34f-6cade39070fc','91b792df-6f39-409d-9c58-8d573b6e17a1'}
cut=[t for t in b.GetTracks() if t.m_Uuid.AsString() in removed];assert len(cut)==5 and all(t.GetNetname()=='USB_CC2' for t in cut)
template=next(t for t in cut if isinstance(t,p.PCB_VIA));d=template.GetDrillValue();w=template.GetWidth(p.F_Cu);assert (w,d)==(450000,200000)
for t in cut:b.Remove(t)
q=b.FindFootprintByReference('J1').FindPadByNumber('B5');code=q.GetNetCode();base=p.VECTOR2I(8200000,20550000)
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
zones=list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()]
objects=[k for k in list(b.GetTracks())+[pad for f in b.GetFootprints() for pad in f.Pads()] if inflated_box(k,3500000).Contains(q.GetPosition())]
obs={l:[(k.GetEffectiveShape(l),k.GetBoundingBox()) for k in objects if k.IsOnLayer(l) and k.GetNetCode()!=code] for l in layers}
holes=[k.GetEffectiveHoleShape() for k in objects if isinstance(k,p.PCB_VIA) and k.GetNetCode()!=code]
def free(k,l):
    s=k.GetEffectiveShape(l);box=inflated_box(k,300000)
    return not (any(box.Intersects(bb) and s.Collide(o,202000) for o,bb in obs[l]) or any(s.Collide(h,250000) for h in holes) or any(z.GetIsRuleArea() and z.IsOnLayer(l) and (z.GetDoNotAllowVias() if isinstance(k,p.PCB_VIA) else z.GetDoNotAllowTracks()) and z.Outline().Collide(s,0) for z in zones))
def lines(a,z,l):
    d=z-a;dd=min(abs(d.x),abs(d.y));s=p.VECTOR2I(int(math.copysign(dd,d.x)),int(math.copysign(dd,d.y)))
    options=[]
    for corner in (a+s,z-s):
        tracks=[]
        for u,e in ((a,corner),(corner,z)):
            if u==e:continue
            t=p.PCB_TRACK(b);t.SetNetCode(code);t.SetLayer(l);t.SetWidth(200000);t.SetStart(u);t.SetEnd(e)
            if not free(t,l):break
            tracks.append(t)
        else:options.append(tracks)
    return options
v=p.PCB_VIA(b);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetWidth(w);v.SetDrill(d);v.SetNetCode(code)
options=[]
for ix in range(-36,65):
 for iy in range(-35,35):
    site=p.VECTOR2I(7050000+ix*50000,20550000+iy*50000)
    if math.dist(tuple(site),(7050000,20550000))<90000:continue
    v.SetPosition(site)
    if not all(free(v,l) for l in layers):continue
    if any(v.GetEffectiveHoleShape().Collide(o,250000) for l in layers for o,bb in obs[l] if point_distance_squared(bb,site)<500000**2):continue
    if any(isinstance(k,p.PAD) and k.IsOnLayer(p.F_Cu) and v.GetEffectiveShape(p.F_Cu).Collide(k.GetEffectiveShape(p.F_Cu),100000) for k in objects):continue
    for front in lines(q.GetPosition(),site,p.F_Cu):
     for back in lines(site,base,p.B_Cu):
        length=sum(t.GetLength() for t in front+back)
        options.append((length,tuple(site),front+back))
out=src;result=dict(source_sha256=meta['sha256'],adopted=False,viable_sites=len({s for _,s,_ in options}))
folder=root/'runs/usb-cc2-clearance';folder.mkdir(exist_ok=True)
for n in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/n,folder/n)
for length,site,tracks in sorted(options,key=lambda o:o[0]):
    v.SetPosition(p.VECTOR2I(*site))
    for k in tracks+[v]:b.Add(k)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if not delta:
        saved=p.LoadBoard(str(out));saved.BuildConnectivity();pres=verify_preservation(p.LoadBoard(str(src)),saved,replaced_copper=removed);assert not screen(saved)
        a=saved.FindFootprintByReference('J1').FindPadByNumber('B5');z=saved.FindFootprintByReference('U9').FindPadByNumber('5')
        assert z.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(a)}
        result.update(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),via_nm=site,path_mm=length/1e6,preservation=pres,new_drc=delta);break
    for k in tracks+[v]:b.Remove(k)
(root/'usb-cc2-clearance.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['viable_sites'],result.get('via_nm'),flush=True)
os._exit(0)
