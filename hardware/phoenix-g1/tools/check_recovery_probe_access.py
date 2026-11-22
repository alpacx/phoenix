"""Compare rear test-point contact window against neighboring body courtyards and GND probes."""
from pathlib import Path
import hashlib,json,math
import pcbnew as p
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
rows=[]
for state in ('layout-soc-ground-existing-barrel','layout-recovery-adc-relocated'):
    cp=json.loads((root/(state+'.json')).read_text());src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
    board=p.LoadBoard(str(src));tp=board.FindFootprintByReference('TP10');pad=tp.FindPadByNumber('1');at=pad.GetPosition()
    margin=[]
    for f in board.GetFootprints():
        if f.GetReference()=='TP10' or f.GetLayer()!=tp.GetLayer():continue
        poly=f.GetCourtyard(tp.GetLayer())
        if not poly.OutlineCount():continue
        mm=poly.Distance(at)/1e6
        margin.append((round(mm,4),f.GetReference()))
    grounds=[(math.dist(tuple(at),tuple(q.GetPosition()))/1e6,f.GetReference()) for f in board.GetFootprints() if f.GetLayer()==tp.GetLayer() and f.GetReference().startswith('TP') for q in f.Pads() if q.GetNetname()=='GND']
    rows.append(dict(sha256=cp['sha256'],position_nm=tuple(at),contact_pad_nm=tuple(pad.GetSize()),nearest_courtyards=sorted(margin)[:4],nearest_ground_probe_mm=min(grounds,default=None),soc_ball_distance_mm=math.dist(tuple(at),tuple(board.FindFootprintByReference('U1').FindPadByNumber('D26').GetPosition()))/1e6))
(root/'recovery-probe-access.json').write_text(json.dumps(dict(cases=rows,scope='Planar rear-face clear radius about contact center; fixture approach, stop and probe compression require physical verification.'),indent=2)+'\n');print(rows)
