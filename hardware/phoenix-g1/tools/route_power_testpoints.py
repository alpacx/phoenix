"""Connect rear rail probe pads to existing branches with short sense tracks."""
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path
import pcbnew as p
from pcb_bounds import inflated_box
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
load_sense='--cpu-load-sense' in sys.argv
stage='cpu-load-probe' if load_sense else 'power-probes'
meta=json.loads((root/('layout-power-probes.json' if load_sense else 'layout-wifi-sdio-bias.json')).read_text())
src=root/meta['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
current=src
records=[]
held=[]
probes=[('TP8','C1603','1')] if load_sense else [('TP6','U25','22'),('TP8','L1001','2'),('TP7','C1650','1')]
for ref,loadref,num in probes:
    b=p.LoadBoard(str(current));b.BuildConnectivity()
    f=b.FindFootprintByReference(ref);pad=f.FindPadByNumber('1');old=f.GetPosition()
    srcpad=b.FindFootprintByReference(loadref).FindPadByNumber(num)
    assert pad.GetNetCode()==srcpad.GetNetCode()
    assert not b.GetConnectivity().GetConnectedTracks(pad)
    group={k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(srcpad)}|{srcpad.m_Uuid.AsString()}
    layer=f.GetLayer();assert layer==p.B_Cu
    others=[g for g in b.GetFootprints() if g.GetReference()!=ref]
    objs=list(b.GetTracks())+[q for g in others for q in g.Pads()]
    targets=set()
    for k in objs:
        if not k.IsOnLayer(layer) or k.m_Uuid.AsString() not in group:continue
        if isinstance(k,p.PCB_TRACK) and not isinstance(k,p.PCB_VIA):
            a,z=k.GetStart(),k.GetEnd();n=max(1,math.ceil(k.GetLength()/700000))
            for i in range(n+1):
                targets.add(tuple(round(x+(y-x)*i/n) for x,y in zip(a,z)))
        else:targets.add(tuple(k.GetPosition()))
    if not targets:
        held.append(ref);continue
    centers=sorted(targets,key=lambda pt:math.dist(pt,tuple(old)))
    bounds=b.GetBoardEdgesBoundingBox()
    courts=[g.GetCourtyard(layer).BBox() for g in others if g.GetLayer()==layer]
    keep=[z.GetBoundingBox() for z in b.Zones() if z.GetIsRuleArea() and z.IsOnLayer(layer) and z.GetDoNotAllowTracks()]
    obstacles=[(k.GetEffectiveShape(layer),k.GetBoundingBox()) for k in objs if k.IsOnLayer(layer) and k.GetNetCode()!=pad.GetNetCode()]
    holes=[(v.GetEffectiveHoleShape(),v.GetPosition()) for v in b.GetTracks() if isinstance(v,p.PCB_VIA)]
    def clear(obj,clearance=202000):
        sh=obj.GetEffectiveShape(layer)
        bb=inflated_box(obj,clearance)
        return not any(bb.Intersects(r) for r in keep) and not any(bb.Intersects(r) and sh.Collide(s,clearance) for s,r in obstacles)
    options=[]
    for pt in centers:
        target=p.VECTOR2I(*pt)
        for dx in range(-7,8):
            for dy in range(-7,8):
                site=target+p.VECTOR2I(dx*400000,dy*400000)
                if (site-target).EuclideanNorm()>3000000:continue
                f.SetPosition(site)
                cb=f.GetCourtyard(layer).BBox()
                if not bounds.Contains(cb) or any(cb.Intersects(c) for c in courts) or not clear(pad):continue
                if any((site-pos).EuclideanNorm()<1000000 for _,pos in holes):continue
                delta=site-target;d=min(abs(delta.x),abs(delta.y));step=p.VECTOR2I(int(math.copysign(d,delta.x)),int(math.copysign(d,delta.y)))
                for middle in (target+step,site-step):
                    items=[]
                    for a,z in ((target,middle),(middle,site)):
                        if a==z:continue
                        t=p.PCB_TRACK(b);t.SetWidth(300000);t.SetLayer(layer);t.SetStart(a);t.SetEnd(z);t.SetNetCode(pad.GetNetCode())
                        if not clear(t) or any(inflated_box(t,400000).Contains(pos) and t.GetEffectiveShape(layer).Collide(h,250000) for h,pos in holes if pos!=target):break
                        items.append(t)
                    else:
                        length=sum(k.GetLength() for k in items)
                        options.append((round(length/100000)*100000+.1*(site-old).EuclideanNorm(),tuple(site),pt,tuple(middle),length))
                        break
    folder=root/'runs'/(('load-probe-' if load_sense else 'probe-')+ref);folder.mkdir(exist_ok=True)
    for n in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(current.parent/n,folder/n)
    for _,position,pt,middle,length in sorted(options)[:30]:
        f.SetPosition(p.VECTOR2I(*position))
        if screen(b):continue
        tracks=[]
        for u,z in ((pt,middle),(middle,position)):
            if u==z:continue
            t=p.PCB_TRACK(b);t.SetWidth(300000);t.SetLayer(layer);t.SetStart(p.VECTOR2I(*u));t.SetEnd(p.VECTOR2I(*z));t.SetNetCode(pad.GetNetCode());b.Add(t);tracks.append(t)
        out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
        delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
        if not delta:
            saved=p.LoadBoard(str(out));saved.BuildConnectivity();verify_preservation(p.LoadBoard(str(current)),saved);assert not screen(saved)
            probe=saved.FindFootprintByReference(ref).FindPadByNumber('1')
            load=saved.FindFootprintByReference(loadref).FindPadByNumber(num)
            assert load.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(probe)}
            records.append(dict(pair=[ref+'.1',loadref+'.'+num],rail=probe.GetNetname(),original_nm=tuple(old),position_nm=position,sense_length_mm=length/1e6))
            current=out;break
        for t in tracks:b.Remove(t)
    else:held.append(ref)
(root/(stage+'.json')).write_text(json.dumps(dict(parent_sha256=meta['sha256'],sha256=hashlib.sha256(current.read_bytes()).hexdigest(),board=str(current.relative_to(root)),records=records,held=held,assembly_ready=False),indent=2)+'\n')
print(records,held,flush=True);os._exit(0)
