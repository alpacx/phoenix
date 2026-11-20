"""Screen direct, non-via-in-pad escape of the five displaced SoC decouplers."""
from pathlib import Path
import hashlib,json,os,math
import pcbnew as p

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'integrated-fixture-trunk.json').read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));soc=b.FindFootprintByReference('U1');layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
obs=list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]
out=[]
for ref in ('C1625','C1631','C1640','C1642','C1679'):
    net=b.FindFootprintByReference(ref).FindPadByNumber('1').GetNetCode()
    for q in soc.Pads():
        if q.GetNetCode()!=net:continue
        pos=q.GetPosition();near=[o for o in obs if o.GetBoundingBox().Inflate(2500000).Contains(pos)]
        obstacles={l:[o.GetEffectiveShape(l) for o in near if o.IsOnLayer(l) and o.GetNetCode()!=net] for l in layers}
        lands=[o.GetEffectiveShape(p.F_Cu) for o in near if isinstance(o,p.PAD) and o.IsOnLayer(p.F_Cu)]
        v=p.PCB_VIA(b);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetWidth(450000);v.SetDrill(200000)
        t=p.PCB_TRACK(b);t.SetWidth(200000);t.SetLayer(p.F_Cu);t.SetStart(pos)
        legal=[]
        for ix in range(-24,25):
            for iy in range(-24,25):
                site=pos+p.VECTOR2I(ix*50000,iy*50000);v.SetPosition(site);t.SetEnd(site)
                if any(v.GetEffectiveShape(p.F_Cu).Collide(s,100000) for s in lands):continue
                if any(t.GetEffectiveShape(p.F_Cu).Collide(s,200000) for s in obstacles[p.F_Cu]):continue
                if any(v.GetEffectiveShape(l).Collide(s,200000) for l in layers for s in obstacles[l]):continue
                legal.append(tuple(site))
        out.append(dict(ref=ref,ball=q.GetNumber(),net=q.GetNetname(),sites=len(legal),landings_nm=legal))
(root/'soc-bypass-escape.json').write_text(json.dumps(dict(source_sha256=cp['sha256'],pitch_grid_mm=.05,radius_box_mm=1.2,via_mm=[.45,.20],trace_mm=.20,clearance_mm=.20,balls=out),indent=2)+'\n')
print([(r['ref'],r['ball'],r['sites']) for r in out],flush=True);os._exit(0)
