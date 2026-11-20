"""Probe the saved R530 departures with actual through vias and a refilled KiCad DRC."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import pcbnew as p
from drc_regression import introduced

study = Path(__file__).resolve().parents[1] / 'migration-rk3562/experiments/phy-power-parallel'
base = study / 'runs/input-ground-local-002'
source = base / 'phy-joint.kicad_pcb'
def read(path):
    return json.loads(path.read_text())
assert hashlib.sha256(source.read_bytes()).hexdigest() == read(base/'report.json')['candidate_sha256']
reference = read(base/'drc.json')
results = []
def point(x,y):
    return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
for index, (dx,dy,angle,length) in enumerate(read(base/'r530-departures.json')['offset_x_y_angle_deg_length_mm']):
    board = p.LoadBoard(str(source))
    pad = board.FindFootprintByReference('R530').FindPadByNumber('2')
    start = pad.GetPosition() + point(dx,dy)
    end = start + point(length*math.cos(math.radians(angle)),length*math.sin(math.radians(angle)))
    track = p.PCB_TRACK(board)
    track.SetStart(start)
    track.SetEnd(end)
    track.SetWidth(p.FromMM(1.05))
    track.SetLayer(p.F_Cu)
    track.SetNet(pad.GetNet())
    board.Add(track)
    via = p.PCB_VIA(board)
    via.SetViaType(p.VIATYPE_THROUGH)
    via.SetLayerPair(p.F_Cu,p.B_Cu)
    via.SetPosition(end)
    via.SetWidth(p.FromMM(.6))
    via.SetDrill(p.FromMM(.3))
    via.SetNet(pad.GetNet())
    board.Add(via)
    run = study / 'runs' / f'r530-via-exit-{index+1}'
    run.mkdir(exist_ok=True)
    target = run/source.name
    for name in ['phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table']:
        shutil.copy2(base/name,run/name)
    p.ZONE_FILLER(board).Fill(board.Zones())
    p.SaveBoard(str(target),board)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(run/'drc.json'),str(target)],capture_output=True,check=True)
    drc = read(run/'drc.json')
    delta = introduced(reference,drc)
    results.append(dict(case=run.name,via_center_mm=[p.ToMM(end.x),p.ToMM(end.y)],new_violations=delta,assembly_ready=False))
(study/'r530-via-exit-results.json').write_text(json.dumps(results,indent=2)+'\n')
print([(r['case'],len(r['new_violations'])) for r in results],flush=True)
os._exit(0)
