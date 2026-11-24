"""Compare ground coverage under existing tracks near added or moved through vias."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

import pcbnew


def load(checkpoint):
    snapshot = json.loads(checkpoint.read_text())
    path = checkpoint.parent / snapshot["board"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != snapshot["sha256"]:
        raise ValueError(f"PCB hash differs from {checkpoint}")
    return snapshot, pcbnew.LoadBoard(str(path))


def track_id(item):
    return item.m_Uuid.AsString()


def via_positions(board):
    return {
        track_id(item): (tuple(item.GetPosition()), item.GetWidth(pcbnew.F_Cu), item.GetDrillValue())
        for item in board.GetTracks() if isinstance(item, pcbnew.PCB_VIA)
    }


def compare(previous, current, radius_mm=1.0, pitch_mm=0.012):
    radius, pitch = round(radius_mm * 1e6), round(pitch_mm * 1e6)
    if radius <= 0 or pitch <= 0:
        raise ValueError("Sampling radius and pitch must be positive")
    old_vias, new_vias = via_positions(previous), via_positions(current)
    centers = {entry[0] for uid in old_vias.keys() | new_vias.keys()
               if old_vias.get(uid) != new_vias.get(uid)
               for entry in (old_vias.get(uid), new_vias.get(uid)) if entry}
    added = [via for via in current.GetTracks() if isinstance(via, pcbnew.PCB_VIA)
             and old_vias.get(track_id(via)) != new_vias[track_id(via)]]
    previous_tracks = {track_id(t): t for t in previous.GetTracks()}
    references = {pcbnew.F_Cu: pcbnew.In1_Cu, pcbnew.In2_Cu: pcbnew.In1_Cu,
                  pcbnew.In3_Cu: pcbnew.In4_Cu, pcbnew.B_Cu: pcbnew.In4_Cu}
    samples = defaultdict(lambda: {"sampled": 0, "lost": 0, "gained": 0, "lost_in_same_rail_antipad": 0, "lost_examples": []})
    for layer, reference in references.items():
        planes = [[zone.GetFilledPolysList(reference) for zone in board.Zones()
                   if zone.GetNetname() == "GND" and zone.HasFilledPolysForLayer(reference)]
                  for board in (previous, current)]
        if not all(planes):
            raise ValueError(f"A saved GND fill is missing on {current.GetLayerName(reference)}")
        clearance = min(zone.GetLocalClearance() for zone in current.Zones()
                        if zone.GetNetname() == "GND" and zone.HasFilledPolysForLayer(reference))
        for track in current.GetTracks():
            if isinstance(track, pcbnew.PCB_VIA) or track.GetLayer() != layer or track.GetNetname() == "GND":
                continue
            old = previous_tracks.get(track_id(track))
            if old is None or (old.GetLayer(), old.GetStart(), old.GetEnd(), old.GetWidth(), old.GetNetname()) != (
                    layer, track.GetStart(), track.GetEnd(), track.GetWidth(), track.GetNetname()):
                continue
            box = track.GetBoundingBox()
            box.Inflate(radius)
            near = [xy for xy in centers if box.Contains(pcbnew.VECTOR2I(*xy))]
            if not near:
                continue
            a, z = track.GetStart(), track.GetEnd()
            length = track.GetLength()
            if not length:
                continue
            if isinstance(track, pcbnew.PCB_ARC):
                raise ValueError(f"Arc {track_id(track)} needs curved sampling")
            n = math.ceil(length / pitch)
            dx, dy = z.x - a.x, z.y - a.y
            for i in range(n + 1):
                for offset in (-track.GetWidth() / 2, 0, track.GetWidth() / 2):
                    at = pcbnew.VECTOR2I(round(a.x + dx*i/n - offset*dy/length),
                                         round(a.y + dy*i/n + offset*dx/length))
                    if all(math.dist(at, xy) > radius for xy in near):
                        continue
                    before, after = (any(poly.Contains(at) for poly in side) for side in planes)
                    row = samples[f"{track.GetNetname()} {current.GetLayerName(layer)}"]
                    row["sampled"] += 1
                    if before and not after:
                        row["lost"] += 1
                        if any(via.GetNetCode() == track.GetNetCode() and
                               math.dist(via.GetPosition(), at) <= via.GetWidth(reference)/2 + clearance
                               for via in added):
                            row["lost_in_same_rail_antipad"] += 1
                        if len(row["lost_examples"]) < 5:
                            row["lost_examples"].append({"track": track_id(track), "point_nm": tuple(at)})
                    elif after and not before:
                        row["gained"] += 1
    return {"changed_via_centers_nm": sorted(centers), "samples_by_net_and_layer": dict(sorted(samples.items())),
            "sample_pitch_mm": pitch_mm, "via_window_radius_mm": radius_mm,
            "scope": "Center and edges of unchanged straight copper only. Local ground-fill comparison; no field or impedance simulation."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("previous", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    previous_cp, previous = load(args.previous)
    current_cp, current = load(args.current)
    report = compare(previous, current)
    report.update(previous_sha256=previous_cp["sha256"], current_sha256=current_cp["sha256"])
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
