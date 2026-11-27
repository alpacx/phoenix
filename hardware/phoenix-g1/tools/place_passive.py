"""Search a new pose for an unconnected 2-pad passive so one of its pads can be routed to a target pad.

Only footprints whose pads have no copper attached and appear in no verified pair should be moved;
the caller checks that. Candidate poses (both sides, 4 rotations, grid around the target pad) are
kept when the courtyard does not overlap another courtyard on that side and every pad keeps the
net clearance from foreign copper, holes and the board edge. Candidates are tried nearest-first with
route_open_join.py; the first pose that routes is saved.

  place_passive.py SRC DST --ref R507 --pad 2 --to U5.25 [--radius 3] [--step .1] [--tries 40] [--router "..."]
Run with KiCad Python.
"""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pcbnew as p

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import route_open_join as r  # noqa: E402

MM = p.ToMM


def pose_ok(board, fp, others, masks, G, side):
    for pad in fp.Pads():
        track = masks[pad.GetNetname()]
        for l in (p.F_Cu, p.B_Cu, p.In2_Cu, p.In3_Cu, p.In1_Cu, p.In4_Cu):
            if not (pad.IsOnLayer(l) and pad.FlashLayer(l)):
                continue
            m = np.zeros((G.nx, G.ny), bool)
            G.poly_mask(m, r.pad_poly(pad, l), .001)
            if not m.any() or (m & track[l]).any():
                return False
    cy = fp.GetCourtyard(side)
    for o in others:
        oc = o.GetCourtyard(side)
        if oc.OutlineCount() and cy.OutlineCount() and cy.Collide(oc):
            return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--ref", required=True)
    ap.add_argument("--pad", required=True)
    ap.add_argument("--to", required=True)
    ap.add_argument("--radius", type=float, default=3)
    ap.add_argument("--step", type=float, default=.1)
    ap.add_argument("--tries", type=int, default=40)
    ap.add_argument("--sides", default="F,B")
    ap.add_argument("--router", default="", help="extra route_open_join.py options, quoted")
    args = ap.parse_args()
    board = p.LoadBoard(args.src)
    fp = board.FindFootprintByReference(args.ref)
    assert len(fp.Pads()) == 2
    tref, tnum = args.to.split(".")
    tgt = board.FindFootprintByReference(tref).FindPadByNumber(tnum)
    tx, ty = MM(tgt.GetPosition().x), MM(tgt.GetPosition().y)
    R = args.radius + 1.5
    G = r.Grid(board, [tx - R, ty - R, tx + R, ty + R], .025)
    board.Remove(fp)  # keep the reference alive; its own pads must not be obstacles
    board.BuildConnectivity()
    masks = {}
    for pad in fp.Pads():
        n = pad.GetNetname()
        if n not in masks:
            # width 0: masks hold the foreign copper grown by the net clearance
            masks[n] = r.build(board, G, n, 0.0, .2, list(r.ALL), .2, 0.0)[0]
    others = [o for o in board.GetFootprints()
              if math.hypot(MM(o.GetPosition().x) - tx, MM(o.GetPosition().y) - ty) < R + 8]
    orig = (fp.GetPosition(), fp.GetOrientationDegrees(), fp.IsFlipped())
    cands = []
    n = int(args.radius / args.step)
    sides = [s for s in args.sides.split(",")]
    for side in sides:
        layer = p.F_Cu if side == "F" else p.B_Cu
        if fp.GetLayer() != layer:
            fp.Flip(fp.GetPosition(), p.FLIP_DIRECTION_LEFT_RIGHT)
        for rot in (0, 90, 180, 270):
            fp.SetOrientationDegrees(rot)
            for i in range(-n, n + 1):
                for j in range(-n, n + 1):
                    x, y = tx + i * args.step, ty + j * args.step
                    fp.SetPosition(p.VECTOR2I(p.FromMM(x), p.FromMM(y)))
                    pad = fp.FindPadByNumber(args.pad)
                    dd = math.hypot(MM(pad.GetPosition().x) - tx, MM(pad.GetPosition().y) - ty)
                    if dd > args.radius:
                        continue
                    if pose_ok(board, fp, others, masks, G, layer):
                        cands.append((dd + (0 if layer == tgt.GetLayer() else .8), side, rot, x, y))
    cands.sort()
    print(json.dumps({"candidates": len(cands)}), flush=True)
    tmp = Path(args.dst).with_suffix(".place.kicad_pcb")
    board.Add(fp)
    for k, (score, side, rot, x, y) in enumerate(cands[:args.tries]):
        layer = p.F_Cu if side == "F" else p.B_Cu
        if fp.GetLayer() != layer:
            fp.Flip(fp.GetPosition(), p.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(p.VECTOR2I(p.FromMM(x), p.FromMM(y)))
        p.SaveBoard(str(tmp), board)
        res = subprocess.run([sys.executable, str(TOOLS / "route_open_join.py"), str(tmp), args.dst,
                              "--a", f"{args.ref}.{args.pad}", "--b", args.to] + args.router.split(),
                             capture_output=True, text=True)
        lines = [s for s in res.stdout.splitlines() if s.startswith("{")]
        out = json.loads(lines[-1]) if lines else {"result": "error"}
        if out["result"] == "path":
            out["placement"] = {"ref": args.ref, "side": side, "rot": rot, "x": round(x, 4), "y": round(y, 4),
                                "from": [MM(orig[0].x), MM(orig[0].y), orig[1], "B" if orig[2] else "F"]}
            tmp.unlink()
            print(json.dumps(out))
            return
    tmp.unlink(missing_ok=True)
    print(json.dumps({"result": "no_pose", "tried": min(len(cands), args.tries)}))
    sys.exit(3)


if __name__ == "__main__":
    main()
