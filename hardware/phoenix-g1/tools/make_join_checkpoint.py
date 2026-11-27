"""Write a routing checkpoint after closing open joins on a copy of a parent checkpoint.

Checks on the reloaded PCB: every parent verified pad pair still shares an
island, each closed join now connects a pad of both former islands, parent
tracks/vias are unchanged (none removed or moved), and native DRC adds no
violation by type and object UUIDs. Run with KiCad Python from any directory:

  make_join_checkpoint.py PARENT.json RUN_DIR OUT.json --routes RUN_DIR/routes.jsonl
"""
import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

import pcbnew as p

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drc_regression import introduced  # noqa: E402

LAYOUT = Path(__file__).resolve().parents[1] / "migration-rk3562/experiments/phy-power-parallel"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pad_of(board, key):
    ref, num = key.split(".")
    return board.FindFootprintByReference(ref).FindPadByNumber(num)


def item(board, key):
    for t in board.GetTracks():
        if t.m_Uuid.AsString() == key:
            return t
    for f in board.GetFootprints():
        for pad in f.Pads():
            if pad.m_Uuid.AsString() == key:
                return pad
    raise KeyError(key)


def island_pads(board, it):
    conn = board.GetConnectivity()
    found = [it] + list(conn.GetConnectedItems(it))
    return sorted({f"{x.GetParentFootprint().GetReference()}.{x.GetNumber()}"
                   for x in found if isinstance(x, p.PAD) and x.GetNetname() == it.GetNetname()})


def copper(board):
    out = {}
    for t in board.GetTracks():
        if isinstance(t, p.PCB_VIA):
            out[t.m_Uuid.AsString()] = ("via", t.GetNetname(), tuple(t.GetPosition()), t.GetWidth(p.F_Cu), t.GetDrillValue())
        else:
            out[t.m_Uuid.AsString()] = ("track", t.GetNetname(), t.GetLayer(), tuple(t.GetStart()), tuple(t.GetEnd()), t.GetWidth())
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("parent", type=Path)
    ap.add_argument("run", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--routes", type=Path, required=True)
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    parent = json.loads(args.parent.read_text())
    parent_board = args.parent.parent / parent["board"]
    assert sha(parent_board) == parent["sha256"], "parent hash"
    board_path = args.run / "phy-joint.kicad_pcb"
    old, new = p.LoadBoard(str(parent_board)), p.LoadBoard(str(board_path))
    old.BuildConnectivity()
    new.BuildConnectivity()
    routes = [json.loads(line) for line in args.routes.read_text().splitlines() if line.strip()]
    closed = []
    for r in routes:
        a, b = island_pads(old, item(old, r["a"])), island_pads(old, item(old, r["b"]))
        assert a and b, ("island without pad", r["a"], r["b"])
        joined = island_pads(new, pad_of(new, a[0]))
        assert b[0] in joined, ("not joined", a[0], b[0])
        closed.append({"net": r["net"], "pads": [a[0], b[0]], "island_pads_before": [a, b],
                       "width_mm": r["width"], "length_mm": r["length_mm"], "new_vias": r["vias"],
                       "segments": r["segments"]})
    pairs = [list(x) for x in parent["verified_pairs"]]
    for pair in pairs:
        assert pair[1] in island_pads(new, pad_of(new, pair[0])), pair
    known = {tuple(x) for x in pairs}
    added_pairs = [c["pads"] for c in closed if tuple(c["pads"]) not in known]
    before, after = copper(old), copper(new)
    removed = sorted(k for k in before if k not in after)
    changed = sorted(k for k in before if k in after and before[k] != after[k])
    assert not removed and not changed, (removed[:3], changed[:3])
    pads_old = {pd.m_Uuid.AsString(): (pd.GetNetname(), tuple(pd.GetPosition())) for f in old.GetFootprints() for pd in f.Pads()}
    pads_new = {pd.m_Uuid.AsString(): (pd.GetNetname(), tuple(pd.GetPosition())) for f in new.GetFootprints() for pd in f.Pads()}
    assert pads_old == pads_new, "pads changed"
    drc_old = json.loads((parent_board.parent / "drc.json").read_text())
    drc_new = json.loads((args.run / "drc.json").read_text())
    new_drc = introduced(drc_old, drc_new)
    assert not new_drc, new_drc
    nets = {re.search(r"\[(.*?)\]", u["items"][0]["description"]).group(1) for u in drc_new["unconnected_items"]}
    out = {
        "board": str(board_path.resolve().relative_to(args.output.resolve().parent)),
        "sha256": sha(board_path),
        "parent_checkpoint": args.parent.name,
        "parent_sha256": parent["sha256"],
        "verified_pairs": pairs + added_pairs,
        "remaining_minimum_joins": len(drc_new["unconnected_items"]),
        "parent_remaining_minimum_joins": parent["remaining_minimum_joins"],
        "open_nets": len(nets),
        "drc_counts": dict(collections.Counter(v["type"] for v in drc_new["violations"])),
        "new_drc": new_drc,
        "assembly_ready": False,
        "closed_joins": closed,
        "preservation": {"pads_unchanged": len(pads_new), "parent_tracks_vias_unchanged": len(before),
                         "added_tracks_vias": len(after) - len(before), "parent_pairs_verified": len(pairs)},
        "scope": "CAD continuity and native DRC on the reloaded PCB. Grid router with conservative clearances; "
                 "no signal-integrity, current, thermal or fabrication qualification. " + args.note,
        "drc": str((args.run / "drc.json").resolve().relative_to(args.output.resolve().parent)),
    }
    args.output.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("sha256", "remaining_minimum_joins", "open_nets", "drc_counts")}),
          "pairs", len(out["verified_pairs"]))


if __name__ == "__main__":
    main()
