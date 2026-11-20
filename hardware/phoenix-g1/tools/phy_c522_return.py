"""Build a local C522 bypass on the pin-38 escape and check its ground return."""
import json, os, math, shutil, subprocess
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation

import sys
compact="--compact" in sys.argv
pair="--pair" in sys.argv
joint="--joint" in sys.argv or pair or compact
wide="--wide" in sys.argv or joint
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=root/'runs/c522-pin38-escape'
name='phy-joint.kicad_pcb'
b=p.LoadBoard(str(base/name))
c=b.FindFootprintByReference('C522')
c.Flip(c.GetPosition(),False)
def pt(x,y):return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
def wire(a,z,net):
    t=p.PCB_TRACK(b);t.SetNetCode(b.GetNetcodeFromNetname(net));t.SetLayer(p.B_Cu);t.SetWidth(200000);t.SetStart(a);t.SetEnd(z);return t
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
pin=pt(59.94,32.06)
objects=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() if f.GetReference()!='C522' for q in f.Pads()] if o.GetNetname()!='GND' and o.GetBoundingBox().Inflate(6000000).Contains(pin)]
shapes={l:[o.GetEffectiveShape(l) for o in objects if o.IsOnLayer(l)] for l in layers}
via=p.PCB_VIA(b);via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetWidth(450000);via.SetDrill(200000);via.SetNetCode(b.GetNetcodeFromNetname('GND'))
sites=json.loads((root/('c522-rear-wide.json' if wide else 'c522-rear-new-return.json')).read_text())
if joint:
    sites=[dict(r["site"],power=r["power"]) for r in json.loads((root/'c522-joint-sites.json').read_text())]
found=None
cache={}
ground_vias=[t for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()=="GND" and math.dist(tuple(t.GetPosition()),tuple(pin))<6e6]
all_vias=[t for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and math.dist(tuple(t.GetPosition()),tuple(pin))<7e6]
for site in sites:
    c.SetPosition(pt(*site['center']));c.SetOrientationDegrees(site['angle'])
    a,g=(c.FindPadByNumber(n) for n in ('1','2'))
    broad=[]
    if joint:
        path=site['power']
        if pair:
            x,y=path[0]
            nearby=[t for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()=='+1V0_PHY' and t.GetDrillValue()==300000 and 0.25<math.dist((x,y),[p.ToMM(i) for i in t.GetPosition()])<.85]
            if not nearby:continue
            other=[p.ToMM(i) for i in nearby[0].GetPosition()]
            path=[other]+path
        for a0,z0 in zip(path,path[1:]):
            trunk=wire(pt(*a0),pt(*z0),'+1V0_PHY')
            trunk.SetWidth(1550000)
            broad.append(trunk)
    if pair and any(t.GetEffectiveShape(p.B_Cu).Collide(g.GetEffectiveShape(p.B_Cu),200000) or any(t.GetEffectiveShape(p.B_Cu).Collide(o.GetEffectiveShape(p.B_Cu),200000) for o in list(b.GetTracks()) if o.IsOnLayer(p.B_Cu) and o.GetNetname()!="+1V0_PHY" and o.GetBoundingBox().Inflate(1500000).Intersects(t.GetBoundingBox())) for t in broad):continue
    sig=wire(pin,a.GetPosition(),'+1V0_PHY')
    if sig.GetEffectiveShape(p.B_Cu).Collide(g.GetEffectiveShape(p.B_Cu),200000):continue
    shifts=sorted(((x*.1,y*.1) for x in range(-22,23) for y in range(-22,23)),key=lambda v:math.hypot(*v))
    options=[(v.GetPosition(),True) for v in sorted(ground_vias,key=lambda t:math.dist(tuple(t.GetPosition()),tuple(g.GetPosition()))) if math.dist(tuple(v.GetPosition()),tuple(g.GetPosition()))<3.5e6]+[(g.GetPosition()+pt(dx,dy),False) for dx,dy in shifts]
    for pos,reuse in options:
        if compact and math.dist(tuple(pos),tuple(g.GetPosition()))>1500000:continue
        via.SetPosition(pos)
        key=tuple(pos)
        if key not in cache:
            cache[key]=all(not via.GetEffectiveShape(l).Collide(s,200000) for l in layers for s in shapes[l])
        if not cache[key]:continue
        if any(via.GetEffectiveShape(p.B_Cu).Collide(t.GetEffectiveShape(p.B_Cu),200000) for t in broad):continue
        if not reuse and any(math.dist(tuple(pos),tuple(t.GetPosition()))<350000+t.GetDrillValue()/2 for t in all_vias):continue
        ret=wire(g.GetPosition(),pos,'GND')
        shape=ret.GetEffectiveShape(p.B_Cu)
        own=[a.GetEffectiveShape(p.B_Cu),sig.GetEffectiveShape(p.B_Cu)]+[t.GetEffectiveShape(p.B_Cu) for t in broad]
        if any(shape.Collide(s,200000) for s in shapes[p.B_Cu]+own):continue
        if any(via.GetEffectiveShape(p.B_Cu).Collide(s,200000) for s in own):continue
        found=site;break
    if found:break
if not found:print("No local return",len(cache),flush=True);os._exit(0)
for t in broad:b.Add(t)
if not reuse:b.Add(via)
b.Add(sig)
if ret.GetLength():b.Add(ret)
removed=[];held=[]
for t in list(b.GetTracks()):
    if t.GetClass()=='PCB_TRACK' and t.GetNetname()=='GND' and t.GetLayer()==p.F_Cu and t.GetStart().y==34500000 and 82980000<=t.GetStart().x<=83000000:
        removed.append(t.m_Uuid.AsString());b.Remove(t);held.append(t)
dest=root/('runs/c522-compact-return' if compact else 'runs/c522-paired-bypass' if pair else 'runs/c522-joint-bypass' if joint else 'runs/c522-wide-bypass' if wide else 'runs/c522-local-bypass');dest.mkdir(exist_ok=True)
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(base/file,dest/file)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(dest/name),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dest/'drc.json'),str(dest/name)],check=True,capture_output=True)
saved=p.LoadBoard(str(dest/name));pres=verify_preservation(p.LoadBoard(str(base/name)),saved,replaced_copper=removed)
def linked(ref,pin,other,number):
    q=saved.FindFootprintByReference(ref).FindPadByNumber(pin)
    target=saved.FindFootprintByReference(other).FindPadByNumber(number)
    return target.m_Uuid.AsString() in {t.m_Uuid.AsString() for t in saved.GetConnectivity().GetConnectedItems(q)}
report=dict(power_path_mm=path if joint else [],existing_ground_via=reuse,site=found,return_via_mm=[p.ToMM(i) for i in via.GetPosition()],preservation=pres,new_drc=introduced(json.loads((root/'runs/phy-bulk-corridor-In2.Cu-east/drc.json').read_text()),json.loads((dest/'drc.json').read_text())),pin38_connected=linked('U5','38','C522','1'),return_connected=linked('C522','2','C511','2'),rail_connected=linked('C511','1','C522','1'))
(root/('c522-compact-return.json' if compact else 'c522-paired-bypass.json' if pair else 'c522-joint-bypass.json' if joint else 'c522-wide-bypass.json' if wide else 'c522-local-bypass.json')).write_text(json.dumps(report,indent=2)+'\n')
print({k:v for k,v in report.items() if k!='preservation'},flush=True);os._exit(0)
