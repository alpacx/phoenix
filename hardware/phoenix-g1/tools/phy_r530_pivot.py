"""Rotate R530 about its connected input and screen both placement and copper."""
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
import sys
angles = tuple(map(int,sys.argv[1:])) or (45,90,135,180,225,270,315)
for angle in angles:
    board = p.LoadBoard(str(source))
    resistor = board.FindFootprintByReference('R530')
    pivot = resistor.FindPadByNumber('1').GetPosition()
    resistor.Rotate(pivot,p.EDA_ANGLE(angle,p.DEGREES_T))
    assert resistor.FindPadByNumber('1').GetPosition() == pivot
    end = resistor.FindPadByNumber('2').GetPosition()
    run = study / 'runs' / f'r530-pivot-{angle}'
    run.mkdir(exist_ok=True)
    target = run/source.name
    for name in ['phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table']:
        shutil.copy2(base/name,run/name)
    p.ZONE_FILLER(board).Fill(board.Zones())
    p.SaveBoard(str(target),board)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(run/'drc.json'),str(target)],capture_output=True,check=True)
    drc = read(run/'drc.json')
    delta = introduced(reference,drc)
    results.append(dict(case=run.name,output_pad_mm=[p.ToMM(end.x),p.ToMM(end.y)],new_violations=delta,assembly_ready=False))
(study/('r530-pivot-fine-results.json' if sys.argv[1:] else 'r530-pivot-results.json')).write_text(json.dumps(results,indent=2)+'\n')
print([(r['case'],len(r['new_violations'])) for r in results],flush=True)
os._exit(0)
