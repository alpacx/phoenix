"""Identify the exact copper moves needed for a short RSET escape, including all via layers."""
import hashlib,json,math,os
from pathlib import Path
import pcbnew as p
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'layout-regulator-banks.json').read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));pin=b.FindFootprintByReference('U5').FindPadByNumber('39');code=pin.GetNetCode()
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
objects=[k for k in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if k.GetBoundingBox().Inflate(3000000).Contains(pin.GetPosition()) and k.GetNetCode()!=code]
def label(k):
    if isinstance(k,p.PAD):return k.GetParentFootprint().GetReference()+'.'+k.GetNumber()
    return k.GetNetname()
obs={l:[(k,k.GetEffectiveShape(l)) for k in objects if k.IsOnLayer(l)] for l in layers}
start=pin.GetPosition();v=p.PCB_VIA(b);v.SetWidth(450000);v.SetDrill(200000);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu)
trace=p.PCB_TRACK(b);trace.SetLayer(p.F_Cu);trace.SetWidth(200000)
results={}
for ix in range(-32,33):
    for iy in range(-25,26):
        site=start+p.VECTOR2I(ix*50000,iy*50000)
        if (site-start).EuclideanNorm()>1700000:continue
        v.SetPosition(site)
        bore={label(k) for l in layers for k,s in obs[l] if v.GetEffectiveShape(l).Collide(s,200000)}
        if any(isinstance(k,p.PAD) and k.GetBoundingBox().Inflate(276000).Contains(site) for k in objects):continue
        if any(isinstance(k,p.PCB_VIA) and (k.GetPosition()-site).EuclideanNorm()<650000 for k in objects if k.GetNetname() not in ('PHY_XIN','PHY_XOUT')):continue
        if len(bore)>3:continue
        for toe_x in (-350000,-300000,-250000,-200000,200000,250000,300000,350000):
            toe=start+p.VECTOR2I(toe_x,0)
            d=site-toe;diag=min(abs(d.x),abs(d.y));step=p.VECTOR2I(int(math.copysign(diag,d.x)),int(math.copysign(diag,d.y)))
            for c in (toe+step,site-step):
                conflicts=set(bore)
                for u,z in ((toe,c),(c,site)):
                    if u==z:continue
                    trace.SetStart(u);trace.SetEnd(z);s=trace.GetEffectiveShape(p.F_Cu)
                    conflicts.update(label(k) for k,shape in obs[p.F_Cu] if s.Collide(shape,200000))
                key=tuple(sorted(conflicts));dist=(site-c).EuclideanNorm()+(c-toe).EuclideanNorm()
                if key not in results or dist<results[key][0]:results[key]=(dist,tuple(toe),tuple(c),tuple(site))
cases=[dict(blockers=k,length_mm=row[0]/1e6,path_nm=row[1:]) for k,row in sorted(results.items(),key=lambda item:(len(item[0]),item[1][0]))[:30]]
(root/'phy-rset-coupled-windows.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],cases=cases),indent=2)+'\n')
print(cases[:5],flush=True);os._exit(0)
