"""Remove pure duplicate straight segments only; verify identical copper on native reload."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation

root = Path(__file__).resolve().parents[1] / 'migration-rk3562/experiments/phy-power-parallel'
source = json.loads((root / 'layout-cpu-load-sense.json').read_text())
board = root / source['board']
assert hashlib.sha256(board.read_bytes()).hexdigest() == source['sha256']
folder = root / 'runs/coincident-track-cleanup'
folder.mkdir(exist_ok=True)
output = folder / board.name
for name in ('phy-joint.kicad_pro', 'phy-joint.kicad_dru', 'fp-lib-table'):
    shutil.copy2(board.parent / name, folder / name)
text = board.read_text()
segment = re.compile(r'^\t\(segment\n.*?^\t\)\n', re.M | re.S)
fields = re.compile(
    r'\t\(segment\n\t\t\(start ([-.\d]+ [-.\d]+)\)\n\t\t\(end ([-.\d]+ [-.\d]+)\)\n'
    r'\t\t\(width ([-.\d]+)\)\n\t\t\(layer ("[^"]+")\)\n\t\t\(net ("[^"]+")\)\n'
    r'\t\t\(uuid "([a-f\d-]+)"\)\n\t\)\n')
seen = {}
duplicates = {}
# A UUID mentioned by a PCB group, tuning pattern or another stored object must be retained.
refs = Counter(re.findall(r'"([a-f\d-]{36})"', text))
def select(match):
    parsed = fields.fullmatch(match.group())
    if not parsed:
        return match.group()
    a, b, width, layer, net, uid = parsed.groups()
    key = tuple(sorted((a, b))), width, layer, net
    if key in seen and refs[uid] == 1:
        duplicates[uid] = seen[key]
        return ''
    seen[key] = uid
    return match.group()
clean = segment.sub(select, text)
assert duplicates and len(set(duplicates)&set(duplicates.values()))==0
output.write_text(clean)
original, saved = (p.LoadBoard(str(path)) for path in (board, output))
preservation = verify_preservation(original, saved, replaced_copper=duplicates)
def geometry(t):
    return (t.GetClass(), t.GetLayer(), t.GetNetname(), t.GetWidth(), tuple(sorted((tuple(t.GetStart()),tuple(t.GetEnd())))))
old_items = {t.m_Uuid.AsString():t for t in original.GetTracks()}
new_items = {t.m_Uuid.AsString():t for t in saved.GetTracks()}
for removed, kept in duplicates.items():
    assert geometry(old_items[removed]) == geometry(new_items[kept])
drc=folder/'drc.json'
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(output)],check=True,capture_output=True)
before=json.loads((board.parent/'drc.json').read_text())
after=json.loads(drc.read_text())
delta= introduced(before, after)
assert not delta, delta
result = dict(parent_sha256=source['sha256'],board=str(output.relative_to(root)),sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
              equivalent_retained_segments=duplicates,native_preservation=preservation,new_drc=delta)
(root/'coincident-track-cleanup.json').write_text(json.dumps(result,indent=2)+'\n')
print(len(duplicates),len(old_items),len(new_items),flush=True)
os._exit(0)
