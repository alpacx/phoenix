"""Reconnect the VDC sense divider on the rear face of the rotated-PMIC coupon."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import pcbnew as p
from drc_regression import introduced
from local_pcb_router import LocalRouter

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel/runs'
source=root/'pmic-five-stage-boundary-0'
dest=root/'pmic-five-stage-divider-0'
dest.mkdir(exist_ok=True)
for n in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source/n,dest/n)
j=json.loads((source/'output-legs.json').read_text())
board='phy-joint.kicad_pcb'
assert hashlib.sha256((source/board).read_bytes()).hexdigest()==j['board_sha256']
b=p.LoadBoard(str(source/board))
def pad(name):
    r,n=name.split('.');return b.FindFootprintByReference(r).FindPadByNumber(n)
def connected(left,right):
    return pad(right).m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pad(left))}
def check():
    b.BuildConnectivity()
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(dest/board),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dest/'drc.json'),str(dest/board)],check=True,capture_output=True)
    return introduced(json.loads((source/'drc.json').read_text()),json.loads((dest/'drc.json').read_text()))
planned=[]
for left,right in [('R410.2','R411.1'),('R411.1','C410.1'),('R410.2','C410.1')]:
    b.BuildConnectivity()
    if connected(left,right):continue
    pa,pz=pad(left),pad(right)
    router=LocalRouter(b,(57,4,67,13),width=.2,clearance=.205,grid=.05)
    layer=p.B_Cu;net=pa.GetNetname();assert net==pz.GetNetname()=='PMIC_VDC'
    a,z=router.xy(pa),router.xy(pz)
    obstacles=router.blocked(layer,net)
    path=router.solve(obstacles,router.cell(a),router.cell(z))
    if not path:planned.append(dict(left=left,right=right,reason='no rear route'));continue
    points=[a]+path+[z]
    total=sum(math.dist(m,n) for m,n in zip(points,points[1:]))
    if total>1.8*math.dist(a,z):planned.append(dict(left=left,right=right,excessive_mm=total));continue
    new=[]
    for m,n in zip(points,points[1:]):
        v=lambda pt:p.VECTOR2I(*[round(val*1000000) for val in pt])
        if v(m)==v(n):continue
        t=p.PCB_TRACK(b);t.SetNetCode(pa.GetNetCode());t.SetLayer(layer);t.SetWidth(200000);t.SetStart(v(m));t.SetEnd(v(n));b.Add(t);new.append(t)
    delta=check()
    if not connected(left,right) or delta:
        for t in new:b.Remove(t)
        planned.append(dict(left=left,right=right,rejected=delta));continue
    planned.append(dict(left=left,right=right,path=points,length_mm=total))
delta=check();b=p.LoadBoard(str(dest/board));b.BuildConnectivity()
for row in planned:row['connected_after_reload']=connected(row['left'],row['right'])
j['board_sha256']=hashlib.sha256((dest/board).read_bytes()).hexdigest();j['divider_restoration']=dict(rows=planned,delta=delta)
(dest/'output-legs.json').write_text(json.dumps(j,indent=2)+'\n')
print(planned,flush=True);os._exit(0)
