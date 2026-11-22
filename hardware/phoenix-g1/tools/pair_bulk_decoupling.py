"""Place isolated 22-uF capacitors beside power-bank peers, with explicit wide return and supply."""
from pathlib import Path
import hashlib
import json
import math
import shutil
import subprocess

import pcbnew as p

from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_bounds import inflated_box
from pcb_power_leg import make
from pcb_preservation import verify_preservation

root = Path(__file__).resolve().parents[1] / "migration-rk3562/experiments/phy-power-parallel"
entry = json.loads((root/"layout-usb-direction-complete.json").read_text())
src = root / entry["board"]
assert hashlib.sha256(src.read_bytes()).hexdigest() == entry["sha256"]
original = p.LoadBoard(str(src))

def point(obj):
    return tuple(obj.GetPosition())

def within(sh, center):
    return inflated_box(sh,5000000).Contains(p.VECTOR2I(*center))

def search(board, ref, peer):
    f = board.FindFootprintByReference(ref)
    old = point(f)
    anchor = board.FindFootprintByReference(peer)
    q1,q2 = (f.FindPadByNumber(n) for n in ("1","2"))
    a1,a2 = (anchor.FindPadByNumber(n) for n in ("1","2"))
    balls = [point(q) for q in board.FindFootprintByReference("U1").Pads() if q.GetNetname()==q1.GetNetname()]
    source_distance = min(math.dist(old,ball) for ball in balls)
    side=anchor.GetLayer()
    assert f.GetLayer()==side==p.B_Cu and q1.GetNetname()==a1.GetNetname() and q2.GetNetname()==a2.GetNetname()=="GND"
    parts = [x for x in board.GetFootprints() if x.GetReference()!=ref and within(x,point(anchor))]
    courts = [x.GetCourtyard(side) for x in parts if x.GetLayer()==side and x.GetCourtyard(side).OutlineCount()]
    items = [q for x in parts for q in x.Pads() if q.IsOnLayer(side)]
    items.extend(t for t in board.GetTracks() if t.IsOnLayer(side) and within(t,point(anchor)))
    shapes = [(o.GetNetCode(),o.GetEffectiveShape(side)) for o in items]
    holes = [o.GetEffectiveHoleShape() for o in items if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    rules = [z.Outline() for z in board.Zones() if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
    def clear(o):
        shape = o.GetEffectiveShape(side)
        return (not any(shape.Collide(sh,202000) for n,sh in shapes if n!=o.GetNetCode())
                and not any(shape.Collide(sh,252000) for sh in holes)
                and not any(shape.Collide(sh,0) for sh in rules))
    candidates = []
    for angle in (0,90,180,270):
        f.SetOrientationDegrees(angle)
        for dx in range(-24,25):
            for dy in range(-24,25):
                pos=tuple(round(v+d*100000) for v,d in zip(point(anchor),(dx,dy)))
                if min(math.dist(pos,s) for s in balls)>=source_distance: continue
                f.SetPosition(p.VECTOR2I(*pos))
                cy=f.GetCourtyard(side)
                if any(cy.Collide(c,100000) for c in courts) or not clear(q1) or not clear(q2): continue
                lines=[make(board,point(q),point(a),600000,q.GetNetCode(),side) for q,a in ((q1,a1),(q2,a2))]
                if any(t.GetLength()>2400000 or not clear(t) for t in lines): continue
                if lines[0].GetEffectiveShape(side).Collide(lines[1].GetEffectiveShape(side),202000):continue
                if any(t.GetEffectiveShape(side).Collide(q.GetEffectiveShape(side),202000) for t,q in zip(lines,(q2,q1))):continue
                candidates.append((sum(t.GetLength() for t in lines),pos,angle))
    return sorted(candidates)

def main():
    source=src
    summary=[]
    for ref,peers in (("C1605",("C1606","C1607","C1608","C1604","C1603")),
                      ("C1618",("C1619","C1620","C1621","C1617","C1616"))):
        landed=False
        for peer in peers:
            b=p.LoadBoard(str(source))
            cap=b.FindFootprintByReference(ref);a=b.FindFootprintByReference(peer)
            if cap.FindPadByNumber("1").GetNetname()!=a.FindPadByNumber("1").GetNetname():continue
            opts=search(b,ref,peer)
            row=dict(ref=ref,peer=peer,placements=len(opts))
            summary.append(row)
            if not opts:continue
            folder=root/"runs"/("bulk-bank-"+ref+"-"+peer);folder.mkdir(exist_ok=True)
            for name in ("phy-joint.kicad_pro","phy-joint.kicad_dru","fp-lib-table"):shutil.copy2(source.parent/name,folder/name)
            for _,pos,angle in opts[:12]:
                cap.SetPosition(p.VECTOR2I(*pos));cap.SetOrientationDegrees(angle)
                paths=[]
                for n in ("1","2"):
                    x=cap.FindPadByNumber(n);y=a.FindPadByNumber(n)
                    tr=make(b,point(x),point(y),600000,x.GetNetCode(),p.B_Cu)
                    b.Add(tr);paths.append(tr)
                out=folder/source.name
                p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
                subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(out)],check=True,capture_output=True)
                read=lambda folder:json.loads((folder/"drc.json").read_text())
                delta=introduced(read(source.parent),read(folder))
                check=p.LoadBoard(str(out))
                if not delta and not screen(check):
                    verify_preservation(original,check);check.BuildConnectivity()
                    for n in ("1","2"):
                        linked={q.m_Uuid.AsString() for q in check.GetConnectivity().GetConnectedItems(check.FindFootprintByReference(ref).FindPadByNumber(n))}
                        assert check.FindFootprintByReference(peer).FindPadByNumber(n).m_Uuid.AsString() in linked
                        if n=="2":assert check.FindFootprintByReference("U4").FindPadByNumber("69").m_Uuid.AsString() in linked
                    row.update(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),lengths_mm=[t.GetLength()/1e6 for t in paths])
                    source=out;landed=True;break
                for t in paths:b.Remove(t)
            if landed:break
    (root/"bulk-decoupling-local-pairs.json").write_text(json.dumps(dict(parent_sha256=entry["sha256"],width_mm=.60,steps=summary),indent=2)+"\n")
    print(summary,flush=True)

if __name__=="__main__":main()
