"""Locate obstructions to adjacent-layer RF image current on the rebased antenna coupon."""
import hashlib
import json
from pathlib import Path
from pcb_bounds import inflated_box

import pcbnew as p

root = Path(__file__).resolve().parents[1] / "migration-rk3562/experiments/phy-power-parallel"


def main():
    entry = json.loads((root / "rf-external-usb-direction.json").read_text())
    path = root / entry["board"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    board = p.LoadBoard(str(path))
    layer = p.In4_Cu
    ground = p.SHAPE_POLY_SET()
    for zone in board.Zones():
        if zone.GetNetname() == "GND" and zone.IsOnLayer(layer) and zone.HasFilledPolysForLayer(layer):
            ground.BooleanAdd(zone.GetFilledPolysList(layer))
    margin = 200000
    physical = [o for o in board.GetTracks() if o.IsOnLayer(layer) and o.GetNetname() != "GND"]
    physical.extend(q for f in board.GetFootprints() for q in f.Pads() if q.IsOnLayer(layer) and q.GetNetname() != "GND")
    report = {}
    for net in ("WIFI_ANT", "WIFI_RF"):
        envelope = p.SHAPE_POLY_SET()
        for t in board.GetTracks():
            if t.GetNetname() == net:
                poly = p.SHAPE_POLY_SET()
                t.TransformShapeToPolygon(poly, p.B_Cu, margin, 500, p.ERROR_OUTSIDE)
                envelope.BooleanAdd(poly)
        envelope.BooleanSubtract(ground)
        bb = envelope.BBox()
        blockers = []
        for obj in physical:
            if not bb.Intersects(inflated_box(obj,350000)):
                continue
            shape = p.SHAPE_POLY_SET()
            obj.TransformShapeToPolygon(shape, layer, 250000, 500, p.ERROR_OUTSIDE)
            shape.BooleanIntersection(envelope)
            if shape.Area() > 0:
                blockers.append(dict(uuid=obj.m_Uuid.AsString(), net=obj.GetNetname(), type=obj.GetClass(),
                                     start_nm=list(obj.GetPosition()), overlap_mm2=shape.Area()/1e12))
        report[net] = dict(missing_mm2=envelope.Area()/1e12, blockers=sorted(blockers,key=lambda r:-r["overlap_mm2"]))
    out = dict(parent_sha256=entry["sha256"], projected_margin_mm=.20,
               assumed_obstruction_clearance_mm=.25, nets=report)
    (root / "rf-external-reference-obstructions.json").write_text(json.dumps(out,indent=2)+"\n")
    for net, result in report.items():
        print(net, [(item["net"],round(item["overlap_mm2"],4)) for item in result["blockers"]])


if __name__ == "__main__":
    main()
