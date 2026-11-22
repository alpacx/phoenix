"""Identify the first foreign copper limiting a 0.30-mm lead from each USB analog LDO."""
from collections import Counter
from pathlib import Path
import hashlib,json,math,os
import pcbnew as p
from pcb_bounds import inflated_box

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'layout-usb-analog-1v8.json').read_text());path=root/cp['board']
assert hashlib.sha256(path.read_bytes()).hexdigest()==cp['sha256']
board=p.LoadBoard(str(path));rows=[]
for number,dx,dy in [('3',-1,0),('21',0,1)]:
    q=board.FindFootprintByReference('U4').FindPadByNumber(number);start=q.GetPosition()
    near=[(o,o.GetEffectiveShape(p.F_Cu)) for o in list(board.GetTracks())+[q for fp in board.GetFootprints() for q in fp.Pads()] if o.IsOnLayer(p.F_Cu) and o.GetNetCode()!=q.GetNetCode() and inflated_box(o,3500000).Contains(start)]
    t=p.PCB_TRACK(board);t.SetNetCode(q.GetNetCode());t.SetWidth(300000);t.SetLayer(p.F_Cu)
    a=start+p.VECTOR2I(dx*470000,dy*470000);t.SetStart(a)
    outcomes=[]
    for angle in range(-60,61,15):
        rad=math.radians(angle)
        cos=dx*math.cos(rad)-dy*math.sin(rad);sin=dx*math.sin(rad)+dy*math.cos(rad)
        clear_length=0;first=[]
        for step in range(0,2500001,25000):
            t.SetEnd(a+p.VECTOR2I(round(step*cos),round(step*sin)));sh=t.GetEffectiveShape(p.F_Cu)
            assert sh.Collide(q.GetEffectiveShape(p.F_Cu),0)
            hits=[o for o,s in near if sh.Collide(s,200000)]
            if hits:
                first=[dict(ref=o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else type(o).__name__,net=o.GetNetname(),uuid=o.m_Uuid.AsString()) for o in hits];break
            clear_length=step
        outcomes.append(dict(degrees_from_outward_normal=angle,clear_length_mm=clear_length/1e6,first_blockers=first))
    rows.append(dict(pin='U4.'+number,net=q.GetNetname(),toe_nm=tuple(a),rays=outcomes))
(root/'usb-ldo-source-launch-obstacles.json').write_text(json.dumps(dict(board_sha256=cp['sha256'],copper_width_mm=.30,foreign_clearance_mm=.20,examined_mm=2.5,results=rows,assembly_ready=False),indent=2)+'\n')
for row in rows:print(row['pin'],[(q['degrees_from_outward_normal'],q['clear_length_mm'],[(i['ref'],i['net']) for i in q['first_blockers']]) for q in row['rays']],flush=True)
os._exit(0)
