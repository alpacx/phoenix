"""Screen footprint mask openings against other pads and unrelated surface traces."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import pcbnew as pcb


def cells(box, margin=0):
    for x in range((box.GetLeft() - margin) // 1000000, (box.GetRight() + margin) // 1000000 + 1):
        for y in range((box.GetTop() - margin) // 1000000, (box.GetBottom() + margin) // 1000000 + 1):
            yield x, y


def check(board, side, mask):
    pads = [q for f in board.GetFootprints() for q in f.Pads() if q.IsOnLayer(mask)]
    tracks = [t for t in board.GetTracks() if t.IsOnLayer(side) and not isinstance(t, pcb.PCB_VIA)]
    copper = defaultdict(list)
    openings = defaultdict(list)
    web_counts = Counter()
    narrow = []
    near_trace = []
    for t in tracks:
        for k in cells(t.GetBoundingBox(), 90000):
            copper[k].append(t)
    for q in pads:
        margin = q.GetSolderMaskExpansion(mask)
        assert margin == 0, "The current screening assumes a 1:1 LDI opening."
        shape = q.GetEffectiveShape(side if q.IsOnLayer(side) else mask)
        label = q.GetParentFootprint().GetReference() + "." + q.GetNumber()
        neighbors = {}
        nearby_copper = {}
        for k in cells(q.GetBoundingBox(), 200000):
            neighbors.update((pad.m_Uuid.AsString(), (pad, other, name)) for pad, other, name in openings[k])
            nearby_copper.update((t.m_Uuid.AsString(), t) for t in copper[k])
        for pad, other, name in neighbors.values():
            if not shape.Collide(other, 200000):
                continue
            distance = shape.GetClearance(other)
            for limit in (100000, 130000, 200000):
                if distance < limit:
                    web_counts[str(limit)] += 1
            if distance < 100000:
                narrow.append([label, name, distance, q.GetNetCode() == pad.GetNetCode()])
        for key, track in nearby_copper.items():
            if track.GetNetCode() == q.GetNetCode():
                continue
            trace = track.GetEffectiveShape(side)
            if shape.Collide(trace, 89999):
                near_trace.append([label, track.GetNetname(), key, shape.GetClearance(trace)])
        for k in cells(q.GetBoundingBox()):
            openings[k].append((q, shape, label))
    return dict(pad_openings=len(pads), webs_below_nm=web_counts,
                sub_100um=sorted(narrow), foreign_trace_under_90um=sorted(near_trace))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkpoint", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    data = json.loads(args.checkpoint.read_text())
    path = args.checkpoint.parent / data["board"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == data["sha256"]
    board = pcb.LoadBoard(str(path))
    result = dict(sha256=data["sha256"], source="https://jlcpcb.com/capabilities/Capabilities%2C/",
                  scope="CAD pad openings, 1:1 expansion. Thresholds depend on colour and copper weight. Excludes vias, mask graphics, tooling compensation and CAM changes.")
    for name, side, mask in (("front", pcb.F_Cu, pcb.F_Mask), ("back", pcb.B_Cu, pcb.B_Mask)):
        result[name] = check(board, side, mask)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
