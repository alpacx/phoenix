"""Locate both AC coupling capacitors as a pair on the mux surface with matched leads."""
from collections import Counter
import sys
import hashlib
import json
from pathlib import Path
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make

root = Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
base = json.loads((root/"layout-emmc-data-power.json").read_text())
source = root/base["board"]
assert hashlib.sha256(source.read_bytes()).hexdigest() == base["sha256"]
rows = []
release_enable = "--release-u19" in sys.argv
released = {}
for pin_ids, refs in [(("17","16"),("C601","C602")),(("21","20"),("C603","C604"))]:
    board = p.LoadBoard(str(source))
    mux = board.FindFootprintByReference("U6")
    if release_enable:
        gate = board.FindFootprintByReference("U19")
        connection = board.GetConnectivity()
        detached = {}
        for terminal in gate.Pads():
            attached = [t for t in connection.GetConnectedTracks(terminal) if t.IsOnLayer(p.F_Cu)
                        and t.GetEffectiveShape(p.F_Cu).Collide(terminal.GetEffectiveShape(p.F_Cu), 0)]
            released[terminal.GetNetname()] = sorted(t.m_Uuid.AsString() for t in attached)
            for t in attached:
                detached[t.m_Uuid.AsString()] = t
        for t in detached.values():
            board.Remove(t)
        board.Remove(gate)
    pins = [mux.FindPadByNumber(n) for n in pin_ids]
    caps = [board.FindFootprintByReference(n) for n in refs]
    for cap in caps:
        for pad in cap.Pads():
            assert len(board.GetConnectivity().GetConnectedItems(pad)) == 1
        cap.Flip(cap.GetPosition(), p.FLIP_DIRECTION_TOP_BOTTOM)
        cap.SetOrientationDegrees(90)
        # The downstream pad must face away from the top edge of U6.
        if cap.FindPadByNumber("2").GetPosition().y > cap.FindPadByNumber("1").GetPosition().y:
            cap.SetOrientationDegrees(-90)
    near = [o for o in list(board.GetTracks())+[pad for f in board.GetFootprints() if f.GetReference() not in refs for pad in f.Pads()]
            if o.IsOnLayer(p.F_Cu) and inflated_box(o,6500000).Contains(pins[0].GetPosition())]
    shapes = [(o,o.GetEffectiveShape(p.F_Cu),o.GetBoundingBox()) for o in near]
    courts = [(f.GetReference(),f.GetCourtyard(p.F_Cu)) for f in board.GetFootprints()
              if f.GetLayer()==p.F_Cu and f.GetReference() not in refs and inflated_box(f,7000000).Contains(pins[0].GetPosition())]
    counts = Counter()
    blockers = Counter()
    copper_blockers = Counter()
    options = []
    for offset in range(350000,1150001,50000):
        for run in range(600000,4000001,100000):
            leads = []
            for pin,cap,sign in zip(pins,caps,(-1,1)):
                edge = pin.GetBoundingBox().GetTop()
                start = (pin.GetPosition().x,edge+25000)
                center = (start[0]+sign*offset,edge-run-offset-100000)
                cap.SetPosition(cap.GetPosition()+p.VECTOR2I(*center)-cap.FindPadByNumber("1").GetPosition())
                elbow = (start[0],edge-run)
                diagonal = (center[0],elbow[1]-offset)
                points = [start,elbow,diagonal,center]
                leads.extend(make(board,a,b,200000,pin.GetNetCode(),p.F_Cu) for a,b in zip(points,points[1:]))
            hits=set()
            for cap in caps:
                court=cap.GetCourtyard(p.F_Cu)
                hits.update(n for n,c in courts if court.Collide(c,100000))
            if caps[0].GetCourtyard(p.F_Cu).Collide(caps[1].GetCourtyard(p.F_Cu),100000):
                hits.add("other coupling capacitor")
            if hits:
                blockers.update([" + ".join(sorted(hits))]);continue
            counts["both_courtyards"]+=1
            for obj in leads+[pad for f in caps for pad in f.Pads()]:
                shape=obj.GetEffectiveShape(p.F_Cu);bounds=inflated_box(obj,205000)
                for o,other,bb in shapes:
                    if obj.GetNetCode()!=o.GetNetCode() and bounds.Intersects(bb) and shape.Collide(other,200000):
                        hits.add(o.GetParentFootprint().GetReference()+"."+o.GetNumber() if isinstance(o,p.PAD) else o.GetNetname())
            if hits:
                copper_blockers.update([" + ".join(sorted(hits))]); continue
            counts["external_copper_clear"]+=1
            options.append({"positions_nm":[tuple(c.GetPosition()) for c in caps],"offset_nm":offset,"straight_nm":run})
    rows.append({"pins":pin_ids,"caps":refs,"counts":dict(counts),"trial_poses":595,
                 "most_frequent_obstacles":blockers.most_common(15),"external_copper_blockers":copper_blockers.most_common(12),"options":options})
report={"parent_sha256":base["sha256"],"pairs":rows,"u19_attached_copper_released":released,"board_adopted":False,
        "conditions":"Simultaneous symmetric 0.20 mm F.Cu routes out of the mux with 45-degree unstacked fanout, no vias, both footprints preserve polarity; courtyard clearance 0.10 mm. Candidate geometry requires field solver, cap transitions, reference plane and native DRC before adoption."}
(root/("usb3-mux-coupling-u19-release.json" if release_enable else "usb3-mux-coupling-pair-window.json")).write_text(json.dumps(report,indent=2)+"\n")
print([(r["caps"],r["counts"],len(r["options"])) for r in rows])
