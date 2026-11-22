"""Find native 0.20 mm round-ended launches on the exposed edges of RK860 and SoC I2C balls."""
from pathlib import Path
import json
import math
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
cp=json.loads((root/"layout-command-ca1.json").read_text())
board=p.LoadBoard(str(root/cp["board"]))
items=list(board.GetTracks())+[q for f in board.GetFootprints() for q in f.Pads()]
rows=[]
for ref in ("U1","U10"):
    footprint=board.FindFootprintByReference(ref)
    for net in ("I2C0_SCL","I2C0_SDA"):
        land=next(q for q in footprint.Pads() if q.GetNetname()==net)
        at=tuple(land.GetPosition());code=land.GetNetCode();layer=p.F_Cu
        near=[o for o in items if o.IsOnLayer(layer) and o.GetNetCode()!=code and inflated_box(o,1000000).Contains(land.GetPosition())]
        shape=land.GetEffectiveShape(layer)
        available=[];counts={};short=[]
        for dx,dy in ((1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1)):
            for radial in (0,25000,50000,75000,100000):
                shift=lambda distance:tuple(round(start+component*distance/math.hypot(dx,dy)) for start,component in zip(at,(dx,dy)))
                tip=shift(radial);out=shift(400000)
                # Keep the center of the start cap strictly inside its own etched land.
                if not shape.Collide(p.VECTOR2I(*tip),0):continue
                line=make(board,tip,out,200000,code,layer)
                def blockers(line):
                    trace=line.GetEffectiveShape(layer)
                    return [obj for obj in near if trace.Collide(obj.GetEffectiveShape(layer),202000) or isinstance(obj,p.PCB_VIA) and trace.Collide(obj.GetEffectiveHoleShape(),252000)]
                obstacles=blockers(line)
                if obstacles:
                    for length in (100000,150000,200000):
                        elbow=shift(radial+length)
                        first=make(board,tip,elbow,200000,code,layer)
                        if blockers(first):continue
                        for change in (-45,45):
                            a=math.atan2(dy,dx)+math.radians(change)
                            finish=[round(elbow[0]+300000*math.cos(a)),round(elbow[1]+300000*math.sin(a))]
                            if not blockers(make(board,elbow,finish,200000,code,layer)):
                                short.append({"origin_nm":tip,"elbow_nm":elbow,"tip_nm":finish})
                for obj in obstacles:
                    tag=(obj.GetParentFootprint().GetReference()+"."+obj.GetNumber()) if isinstance(obj,p.PAD) else obj.GetNetname()
                    counts[tag]=counts.get(tag,0)+1
                if not obstacles:
                    available.append({"origin_nm":tip,"tip_nm":out,"offset_mm":radial/1e6})
                    break
        rows.append({"pad":ref+"."+land.GetNumber(),"net":net,"land_size_mm":[v/1e6 for v in land.GetSize()],"launches":available,"bent_launches":short,"blocking_incidence":counts})
(root/"cpu-regulator-i2c-land-exits.json").write_text(json.dumps({"sha256":cp["sha256"],"rows":rows},indent=2)+"\n")
print([(r["pad"],len(r["launches"]),len(r["bent_launches"]),sorted(r["blocking_incidence"],key=r["blocking_incidence"].get,reverse=True)[:3]) for r in rows])
