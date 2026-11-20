"""Search rear-side bypass sites sharing the existing 1V0 distribution via array."""
import json, math, os, sys
local="--local" in sys.argv
from pathlib import Path
import pcbnew as p

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=root/'runs/c522-pin38-escape'
b=p.LoadBoard(str(base/'phy-joint.kicad_pcb'))
def pt(x,y):return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
def xy(a):return tuple(p.ToMM(i) for i in a)
c=b.FindFootprintByReference('C522')
c.Flip(c.GetPosition(),False)
pin=pt(59.94,32.06)
srcs=[pt(61.9,34.5),pt(62.45,34.5),pt(56.2,30.7),pt(56.2,31.5)]
objs=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() if f.GetReference()!='C522' for q in f.Pads()] if o.IsOnLayer(p.B_Cu) and o.GetBoundingBox().Inflate(7000000).Contains(pin)]
shapes=[(o.GetNetname(),o.GetEffectiveShape(p.B_Cu)) for o in objs]
bodies=[f.GetCourtyard(p.B_Cu).BBox() for f in b.GetFootprints() if f.GetReference()!='C522' and f.GetLayer()==p.B_Cu]
def clear(shape,n):return all(k==n or not shape.Collide(s,200000) for k,s in shapes)
def route(a,z,width,n):
    t=p.PCB_TRACK(b)
    t.SetLayer(p.B_Cu);t.SetWidth(p.FromMM(width));t.SetStart(a);t.SetEnd(z)
    return clear(t.GetEffectiveShape(p.B_Cu),n)
out=[]
power='+1V0_PHY'
gnds=[o.GetPosition() for o in objs if isinstance(o,p.PCB_VIA) and o.GetNetname()=='GND']
for ix in range(570,631):
 for iy in range(295,350):
    loc=pt(ix/10,iy/10)
    for angle in (0,90,180,270):
        c.SetPosition(loc);c.SetOrientationDegrees(angle)
        if any(c.GetCourtyard(p.B_Cu).BBox().Intersects(box) for box in bodies):continue
        a,g=(c.FindPadByNumber(n) for n in ('1','2'))
        if not all(clear(q.GetEffectiveShape(p.B_Cu),q.GetNetname()) for q in (a,g)):continue
        pos=a.GetPosition()
        if not route(pin,pos,.2,power):continue
        if local and "--new-return" in sys.argv:
            if math.dist(xy(pin),xy(pos))<1.5:
                direction=pos-g.GetPosition()
                tip=pos+p.VECTOR2I(round(direction.x*.35),round(direction.y*.35))
                feasible=route(tip,tip,1.55,power)
                if "--wide" not in sys.argv or feasible:
                    out.append(dict(center=xy(loc),angle=angle,return_pad=xy(g.GetPosition()),wide_tip=xy(tip),pin_length=math.dist(xy(pin),xy(pos))))
            continue
        if local:
            for ground in gnds:
                if math.dist(xy(ground),xy(g.GetPosition()))>.95 or not route(ground,g.GetPosition(),.2,'GND'):continue
                if math.dist(xy(pin),xy(pos))<1.5:
                    out.append(dict(center=xy(loc),angle=angle,ground=xy(ground),pin_length=math.dist(xy(pin),xy(pos))))
            continue
        for src in srcs:
            if math.dist(xy(src),xy(pos))>3.5 or not route(src,pos,1.55,power):continue
            # The broad trunk must also clear the new capacitor ground pad.
            t=p.PCB_TRACK(b);t.SetLayer(p.B_Cu);t.SetWidth(1550000);t.SetStart(src);t.SetEnd(pos)
            if t.GetEffectiveShape(p.B_Cu).Collide(g.GetEffectiveShape(p.B_Cu),200000):continue
            for ground in gnds:
                if math.dist(xy(ground),xy(g.GetPosition()))<1.4 and route(ground,g.GetPosition(),.2,'GND'):
                    out.append(dict(center=xy(loc),angle=angle,source=xy(src),ground=xy(ground),pin_length=math.dist(xy(pin),xy(pos))))
out.sort(key=lambda r:r['pin_length'])
(root/('c522-rear-wide.json' if '--wide' in sys.argv else 'c522-rear-new-return.json' if '--new-return' in sys.argv else 'c522-rear-local-sites.json' if local else 'c522-rear-sites.json')).write_text(json.dumps(out,indent=2)+'\n')
print(len(out),out[:1],flush=True);os._exit(0)
