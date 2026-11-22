"""Replay adopted power and USB changes on the independently verified external RF coupon."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pcbnew as p

from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_preservation import verify_preservation

root = Path(__file__).resolve().parents[1] / "migration-rk3562/experiments/phy-power-parallel"


def load(name):
    entry = json.loads((root / (name + ".json")).read_text())
    path = root / entry["board"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    return path, entry["sha256"], p.LoadBoard(str(path))


def tracks(board):
    return {item.m_Uuid.AsString(): item for item in board.GetTracks()}


def geometry(item):
    if isinstance(item, p.PCB_VIA):
        return (item.GetNetname(), tuple(item.GetPosition()), item.GetWidth(p.F_Cu),
                item.GetDrillValue(), item.TopLayer(), item.BottomLayer())
    return (item.GetNetname(), item.GetLayer(), tuple(item.GetStart()), tuple(item.GetEnd()), item.GetWidth())


def pose(fp):
    return (tuple(fp.GetPosition()), fp.GetOrientationDegrees(), fp.GetLayer())


def main():
    _, base_sha, base = load("layout-usb-enable-trunk")
    source, adopted_sha, adopted = load("layout-usb-direction-complete")
    coupon_path, coupon_sha, coupon = load("rf-external-return-cleanup")
    folder = root / "runs/rf-external-usb-direction"
    folder.mkdir(exist_ok=True)
    for name in ("phy-joint.kicad_pro", "phy-joint.kicad_dru", "fp-lib-table"):
        assert (source.parent / name).read_bytes() == (coupon_path.parent / name).read_bytes()
        shutil.copy2(source.parent / name, folder / name)
    original, new, rf = map(tracks, (base, adopted, coupon))
    changed = {i for i in original.keys() & new.keys() if geometry(original[i]) != geometry(new[i])}
    removed = original.keys() - new.keys() | changed
    added = new.keys() - original.keys() | changed
    for key in sorted(removed):
        assert key in rf and geometry(rf[key]) == geometry(original[key]), key
        coupon.Remove(rf[key])
    for key in sorted(added):
        assert key not in rf or key in changed, key
        item = new[key].Duplicate()
        item.SetUuid(new[key].m_Uuid)
        item.SetNet(coupon.FindNet(new[key].GetNetname()))
        coupon.Add(item)
    moved = []
    for footprint in adopted.GetFootprints():
        name = footprint.GetReference()
        old = base.FindFootprintByReference(name)
        dest = coupon.FindFootprintByReference(name)
        assert old and dest
        if pose(old) == pose(footprint):
            continue
        assert pose(dest) == pose(old), name
        if dest.GetLayer() != footprint.GetLayer():
            dest.Flip(dest.GetPosition(), p.FLIP_DIRECTION_LEFT_RIGHT)
        dest.SetOrientationDegrees(footprint.GetOrientationDegrees())
        dest.SetPosition(footprint.GetPosition())
        moved.append(name)
    p.ZONE_FILLER(coupon).Fill(coupon.Zones())
    out = folder / source.name
    p.SaveBoard(str(out), coupon)
    checked = p.LoadBoard(str(out))
    a = tracks(checked)
    replaced = [key for key, item in new.items() if key not in a or geometry(item) != geometry(a[key])]
    preservation = verify_preservation(adopted, checked, replaced_copper=replaced)
    subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli", "pcb", "drc",
                    "--format", "json", "-o", str(folder / "drc.json"), str(out)], check=True, capture_output=True)
    drc = lambda directory: json.loads((directory / "drc.json").read_text())
    delta = introduced(drc(source.parent), drc(folder))
    mounts = screen(checked)
    data = dict(board=str(out.relative_to(root)), sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
                common_base_sha256=base_sha, adopted_parent_sha256=adopted_sha, rf_coupon_sha256=coupon_sha,
                replayed_moves=sorted(moved), replayed_tracks_added=len(added), replayed_tracks_removed=len(removed),
                preservation=preservation, new_drc=delta, mount_conflicts=mounts,
                adopted=False, assembly_ready=False)
    (root / "rf-external-usb-direction.json").write_text(json.dumps(data, indent=2) + "\n")
    print(sorted(moved), len(added), len(removed), len(delta), len(mounts), flush=True)


if __name__ == "__main__":
    main()
