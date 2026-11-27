"""Try to close open joins one at a time on a working copy, keeping only verified ones.

For each open join whose net matches --nets (regex), route_open_join.py is run on
a temporary copy for each option set. A route is kept only when the reloaded copy
(1) has fewer native-DRC open joins, (2) adds no DRC violation by type and object
UUIDs, and (3) when vias were added, check_changed_via_returns finds no ground
reference loss on existing straight copper of other nets near those vias.

  auto_close_joins.py RUN_DIR --nets REGEX [--skip REGEX] [--opts "..."]...
Run with KiCad Python. RUN_DIR holds phy-joint.kicad_pcb and its drc.json.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pcbnew

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from drc_regression import introduced  # noqa: E402
from check_changed_via_returns import compare  # noqa: E402

CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"


def drc(board, out):
    subprocess.run([CLI, "pcb", "drc", "--format", "json", "-o", str(out), str(board)],
                   check=True, capture_output=True)
    return json.loads(out.read_text())


def net_of(u):
    return re.search(r"\[(.*?)\]", u["items"][0]["description"]).group(1)


def foreign_loss(old_path, new_path, net):
    old, new = pcbnew.LoadBoard(str(old_path)), pcbnew.LoadBoard(str(new_path))
    rep = compare(old, new)
    bad = {k: v["lost"] for k, v in rep["samples_by_net_and_layer"].items()
           if v["lost"] and k.split(" ")[0] != net}
    same = {k: (v["lost"], v["lost_in_same_rail_antipad"]) for k, v in rep["samples_by_net_and_layer"].items()
            if v["lost"] and k.split(" ")[0] == net}
    return bad, same


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run", type=Path)
    ap.add_argument("--nets", required=True)
    ap.add_argument("--skip", default="$^")
    ap.add_argument("--opts", action="append", default=[])
    ap.add_argument("--max", type=int, default=1000)
    args = ap.parse_args()
    opts = args.opts or ["--guard .45", "--guard .6", "--guard .7"]
    work = args.run / "phy-joint.kicad_pcb"
    cdir = args.run / "cand"
    cdir.mkdir(exist_ok=True)
    for name in ("phy-joint.kicad_pro", "phy-joint.kicad_dru"):
        shutil.copy2(args.run / name, cdir / name)
    (cdir / "fp-lib-table").write_text((args.run / "fp-lib-table").read_text()
                                       .replace("${KIPRJMOD}", str(args.run.resolve())))
    tmp = cdir / "phy-joint.kicad_pcb"  # same basename: kicad-cli loads the copied rules
    base = drc(work, args.run / "drc.json")
    tried, kept = set(), 0
    log = args.run / "auto-log.jsonl"
    while kept < args.max:
        todo = [u for u in base["unconnected_items"]
                if re.fullmatch(args.nets, net_of(u)) and not re.search(args.skip, net_of(u))
                and (u["items"][0]["uuid"], u["items"][1]["uuid"]) not in tried]
        if not todo:
            break
        u = todo[0]
        key = (u["items"][0]["uuid"], u["items"][1]["uuid"])
        tried.add(key)
        net = net_of(u)
        outcome = {"net": net, "a": key[0], "b": key[1], "attempts": []}
        for o in opts:
            r = subprocess.run([sys.executable, str(TOOLS / "route_open_join.py"), str(work), str(tmp),
                                "--a", key[0], "--b", key[1]] + o.split(), capture_output=True, text=True)
            lines = [x for x in r.stdout.splitlines() if x.startswith("{")]
            res = json.loads(lines[-1]) if lines else {"result": "error"}
            att = {"opts": o, "result": res["result"]}
            outcome["attempts"].append(att)
            if res["result"] != "path":
                if res["result"] in ("blocked_endpoint",):
                    break
                continue
            cand = drc(tmp, cdir / "drc.json")
            new = introduced(base, cand)
            att.update(joins=len(cand["unconnected_items"]), new_drc=len(new))
            if new or len(cand["unconnected_items"]) >= len(base["unconnected_items"]):
                att["new_drc_types"] = sorted({v["type"] for v in new})
                continue
            if res["vias"]:
                try:
                    bad, same = foreign_loss(work, tmp, net)
                except ValueError as e:
                    bad, same = {"error": str(e)}, {}
                att.update(foreign_loss=bad, same_net_loss=same)
                if bad:
                    continue
            shutil.copy2(tmp, work)
            shutil.copy2(cdir / "drc.json", args.run / "drc.json")
            base = cand
            res["accepted_opts"] = o
            with open(args.run / "routes.jsonl", "a") as f:
                f.write(json.dumps(res) + "\n")
            outcome["kept"] = True
            kept += 1
            print("KEPT", net, o, res["length_mm"], len(res["vias"]), "joins", len(base["unconnected_items"]), flush=True)
            break
        with open(log, "a") as f:
            f.write(json.dumps(outcome) + "\n")
    shutil.rmtree(cdir)
    print("done kept", kept, "joins", len(base["unconnected_items"]))


if __name__ == "__main__":
    main()
