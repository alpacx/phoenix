"""Validate a routed checkpoint together with the USB selector in a temporary KiCad project."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pcbnew

SELECTOR = Path(__file__).resolve().parent
LAYOUT = SELECTOR.parent / "phy-power-parallel"
sys.path.insert(0, str(SELECTOR.parents[2] / "tools"))

from drc_regression import introduced
from verify import CLI


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# KiCad 10 writes one top-level multiline record at a single tab of indentation.
_RECORD = re.compile(r'^\t\((segment|arc|via|footprint)\b[^\n]*\n.*?^\t\)\n', re.M | re.S)
_UUID = re.compile(r'^\t\t\(uuid "([^"]+)"\)', re.M)
_REF = re.compile(r'^\t\t\(property "Reference" "([^"]+)"', re.M)


def records(board):
    items = {}
    for match in _RECORD.finditer(board):
        record = match.group()
        key = _UUID.search(record).group(1)
        assert key not in items
        items[key] = record
    return items


def write_combined_layout(original, routed, selector, destination):
    before = records(original.read_text())
    after = records(routed.read_text())
    text = selector.read_text()
    merged = records(text)
    assert len(before) > 1000 and len(after) > 1000
    removed = before.keys() - after.keys()
    added = after.keys() - before.keys()
    changed = {key for key in before.keys() & after.keys() if before[key] != after[key]}
    moved = []
    for key in removed | changed:
        assert merged[key] == before[key], key
        if key in changed:
            assert _RECORD.match(before[key]).group(1) == _RECORD.match(after[key]).group(1), key
        if key in changed and before[key].startswith("\t(footprint "):
            moved.append(_REF.search(after[key]).group(1))
    def replace(match):
        key = _UUID.search(match.group()).group(1)
        return "" if key in removed else after[key] if key in changed else match.group()
    text = _RECORD.sub(replace, text)
    assert all(key not in merged for key in added)
    last = text.rindex(")")
    text = text[:last] + "".join(after[key] for key in sorted(added)) + text[last:]
    destination.write_text(text)
    board = pcbnew.LoadBoard(str(destination))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(destination), board)
    return sorted(moved)


def check_connectivity(board, pairs):
    board.BuildConnectivity()
    islands = {}

    def pad(key):
        ref, number = key.split(".")
        return board.FindFootprintByReference(ref).FindPadByNumber(number)

    def check(first, second):
        if first not in islands:
            islands[first] = {item.m_Uuid.AsString()
                              for item in board.GetConnectivity().GetConnectedItems(pad(first))}
        assert pad(second).m_Uuid.AsString() in islands[first], (first, second)

    for pair in pairs:
        check(*["R1104.1" if pin == "U14.2" else pin for pin in pair])
    for first, second in [("U14.2", "R1104.2"), ("U14.2", "R1105.2"),
                          ("U6.26", "R1104.1"), ("U14.3", "R1105.1")]:
        check(first, second)


def verify(checkpoint):
    original = json.loads((LAYOUT / "layout-pmic-image-c468.json").read_text())
    variant = json.loads((SELECTOR / "verification.json").read_text())
    candidate = json.loads(checkpoint.read_text())
    old_path = LAYOUT / original["board"]
    new_path = LAYOUT / candidate["board"]
    selector_path = SELECTOR / "phy-joint.kicad_pcb"
    assert digest(old_path) == original["sha256"] == variant["parent"]
    assert digest(new_path) == candidate["sha256"]
    assert digest(selector_path) == variant["pcb_sha256"]
    with tempfile.TemporaryDirectory() as temp:
        directory = Path(temp)
        for name in ("phy-joint.kicad_pro", "phy-joint.kicad_dru"):
            shutil.copy2(SELECTOR / name, directory / name)
        libraries = (SELECTOR / "fp-lib-table").read_text()
        (directory / "fp-lib-table").write_text(libraries.replace("${KIPRJMOD}", str(SELECTOR)))
        board_path = directory / selector_path.name
        poses = directory / "moved.json"
        subprocess.run([sys.executable, str(Path(__file__).resolve()), str(checkpoint.resolve()),
                        "--write-temporary-board", str(board_path)], check=True, capture_output=True)
        moved = json.loads(poses.read_text())
        # Loading in a fresh KiCad runtime also verifies that all changes survived serialization.
        subprocess.run([sys.executable, str(Path(__file__).resolve()), str(checkpoint.resolve()),
                        "--check-temporary-board", str(board_path)], check=True, capture_output=True)
        report = directory / "drc.json"
        subprocess.run([CLI, "pcb", "drc", "--format", "json", "-o", str(report), str(board_path)],
                       check=True, capture_output=True)
        drc = json.loads(report.read_text())
        baseline = json.loads(new_path.with_name("drc.json").read_text())
        assert not introduced(baseline, drc)
        assert len(drc["unconnected_items"]) == candidate["remaining_minimum_joins"]
    return {
        "layout_sha256": candidate["sha256"],
        "selector_sha256": variant["pcb_sha256"],
        "shared_parent_sha256": original["sha256"],
        "changed_footprint_poses": moved,
        "validated_layout_pairs": len(candidate["verified_pairs"]),
        "validated_selector_pairs": 4,
        "remaining_minimum_joins": candidate["remaining_minimum_joins"],
        "introduced_drc": [],
        "scope": "Reloaded temporary combined PCB; source boards retained.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--write-temporary-board", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--check-temporary-board", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, help="Save the verification report as JSON.")
    args = parser.parse_args()
    if args.write_temporary_board:
        original = json.loads((LAYOUT / "layout-pmic-image-c468.json").read_text())
        routed = json.loads(args.checkpoint.read_text())
        moved = write_combined_layout(LAYOUT / original["board"], LAYOUT / routed["board"],
                                      SELECTOR / "phy-joint.kicad_pcb", args.write_temporary_board)
        args.write_temporary_board.with_name("moved.json").write_text(json.dumps(moved))
    elif args.check_temporary_board:
        saved = pcbnew.LoadBoard(str(args.check_temporary_board))
        check_connectivity(saved, json.loads(args.checkpoint.read_text())["verified_pairs"])
    else:
        report = json.dumps(verify(args.checkpoint), indent=2) + "\n"
        if args.output:
            args.output.write_text(report)
        else:
            print(report, end="")
