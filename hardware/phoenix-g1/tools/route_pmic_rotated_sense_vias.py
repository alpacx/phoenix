"""Connect the rotated PMIC feedback and filtered voltage-sense paths from legal QFN launches."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pcbnew as p
from local_pcb_router import LocalRouter
from drc_regression import introduced

runs=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel/runs'
first='--feedback-first' in sys.argv
inner='--inner' in sys.argv or first
src=runs/('pmic-five-stage-sense-0' if inner else 'pmic-five-stage-filter-0');dest=runs/('pmic-five-stage-feedback-0' if first else 'pmic-five-stage-inner-0' if inner else 'pmic-five-stage-sense-0');dest.mkdir(exist_ok=True)
fn='phy-joint.kicad_pcb'
for n in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src/n,dest/n)
j=json.loads((src/'output-legs.json').read_text());sweep=json.loads((src/'alternate-return-vias.json').read_text())
assert hashlib.sha256((src/fn).read_bytes()).hexdigest()==j['board_sha256']==sweep['coupon_sha256']
b=p.LoadBoard(str(src/fn))
def pad(name):
    ref,n=name.split('.');return b.FindFootprintByReference(ref).FindPadByNumber(n)
def check():
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(dest/fn),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dest/'drc.json'),str(dest/fn)],check=True,capture_output=True)
    return introduced(json.loads((src/'drc.json').read_text()),json.loads((dest/'drc.json').read_text()))
def connected(board,left,right):
    def q(s):
        ref,n=s.split('.');return board.FindFootprintByReference(ref).FindPadByNumber(n)
    return q(right).m_Uuid.AsString() in {i.m_Uuid.AsString() for i in board.GetConnectivity().GetConnectedItems(q(left))}
def segments(pts,layer,code,width):
    reduced=[]
    for pt in pts:
        pt=tuple(pt)
        if reduced and pt==reduced[-1]:continue
        if len(reduced)>1:
            a,z=reduced[-2:];d=(z[0]-a[0],z[1]-a[1]);v=(pt[0]-z[0],pt[1]-z[1])
            if d[0]*v[1]==d[1]*v[0] and d[0]*v[0]+d[1]*v[1]>0:reduced.pop()
        reduced.append(pt)
    result=[]
    for a,z in zip(reduced,reduced[1:]):
        t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetNetCode(code);t.SetWidth(width);t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z));result.append(t)
    return result
choices={r['label']:r for r in sweep['circuits']}
rows=[]
def interior_sense():
    # Each sense line gets its own pickup via at the target footprint.
    # Evaluate reference-plane-adjacent inner copper only.
    circuits=[('U4.61',['R410.2','R411.1','C410.1'],6.0),('U4.59',['C435.1'],7.5)]
    for name, targets, limit in (reversed(circuits) if first else circuits):
        q=pad(name);paths=[];attempts=[]
        for layer in (p.In2_Cu,p.In3_Cu):
            router=LocalRouter(b,(57,5,71,15),width=.2,clearance=.205,grid=.05)
            blocked=router.blocked(layer,q.GetNetname())
            for l in choices[name]['via_paths']:
                a=tuple(l['via_nm']);awm=tuple(i*1e-6 for i in a)
                tree=router.paths_from(blocked,router.cell(awm),limit-l['length_mm'])
                for target in targets:
                    for r in choices[target]['via_paths']:
                        z=tuple(r['via_nm']);zwm=tuple(i*1e-6 for i in z)
                        path=router.path_from_tree(tree,router.cell(zwm))
                        if not path:continue
                        points=[a]+[tuple(round(i*1e6) for i in xy) for xy in path]+[z]
                        length=l['length_mm']+r['length_mm']+sum(math.dist(x,y)*1e-6 for x,y in zip(points,points[1:]))
                        if length<=limit:paths.append((length,layer,target,l,r,points))
        ok=False
        for length,layer,target,l,r,points in sorted(paths,key=lambda x:x[0]):
            route=segments(l['track_nm'],p.F_Cu,q.GetNetCode(),200000)+segments(points,layer,q.GetNetCode(),200000)+segments(r['track_nm'],p.B_Cu,q.GetNetCode(),200000)
            for key in (l,r):
                v=p.PCB_VIA(b);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetPosition(p.VECTOR2I(*key['via_nm']));v.SetDrill(200000);v.SetWidth(450000);v.SetNetCode(q.GetNetCode());route.append(v)
            for t in route:b.Add(t)
            delta=check();probe=p.LoadBoard(str(dest/fn));probe.BuildConnectivity();native=connected(probe,name,target)
            attempts.append(dict(target=target,layer=b.GetLayerName(layer),length_mm=length,source_via_nm=l['via_nm'],target_via_nm=r['via_nm'],introduced=delta,connected=native))
            if native and not delta:ok=True;break
            for t in route:b.Remove(t)
        rows.append(dict(source=name,connected=ok,possible=len(paths),attempts=attempts))
if inner:interior_sense()
else:
    for name,targets,budget in [('R411.2',['U4.69'],2.2),('U4.61',['C410.1','R411.1','R410.2'],5.0),('U4.59',['C435.1'],6.0)]:
        row=choices[name];q=pad(name);side=q.GetParentFootprint().GetLayer()
        router=LocalRouter(b,(56,5,71,16),width=.20,clearance=.205,grid=.05)
        blocked=router.blocked(p.B_Cu,q.GetNetname()) if name!='R411.2' else set()
        reached=False;attempts=[]
        for launch in row['via_paths']:
            pt=tuple(launch['via_nm']);world=tuple(v/1e6 for v in pt)
            for target in targets:
                bpath=[]
                if name!='R411.2':
                    endpoint=router.xy(pad(target))
                    line=router.solve(blocked,router.cell(world),router.cell(endpoint))
                    if not line:continue
                    bpath=[pt]+[tuple(round(i*1e6) for i in xy) for xy in line]+[tuple(pad(target).GetPosition())]
                length=launch['length_mm']+sum(math.dist(l,r)*1e-6 for l,r in zip(bpath,bpath[1:]))
                if length>budget:continue
                route=segments(launch['track_nm'],side,q.GetNetCode(),row['width_nm'])+segments(bpath,p.B_Cu,q.GetNetCode(),200000)
                v=p.PCB_VIA(b);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetPosition(p.VECTOR2I(*pt));v.SetDrill(200000);v.SetWidth(450000);v.SetNetCode(q.GetNetCode());route.append(v)
                for t in route:b.Add(t)
                delta=check();test=p.LoadBoard(str(dest/fn));test.BuildConnectivity()
                native=connected(test,name,target)
                attempts.append(dict(via_nm=pt,target=target,length_mm=length,introduced=delta,connected=native))
                if native and not delta:reached=True;break
                for t in route:b.Remove(t)
            if reached:break
        rows.append(dict(source=name,connected=reached,attempts=attempts))
assert not check();b=p.LoadBoard(str(dest/fn));b.BuildConnectivity()
for row in rows:
    if row['connected']:assert connected(b,row['source'],row['attempts'][-1]['target'])
j['board_sha256']=hashlib.sha256((dest/fn).read_bytes()).hexdigest();j['inner_sense_vias' if inner else 'sense_vias']=rows
(dest/'output-legs.json').write_text(json.dumps(j,indent=2)+'\n')
print([(r['source'],r['connected'],len(r['attempts'])) for r in rows],flush=True);os._exit(0)
