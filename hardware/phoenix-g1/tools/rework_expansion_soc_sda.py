"""Move a two-segment In3 SPI chip-select bend to open the CPU's SDA escape."""
from collections import Counter,defaultdict
from pathlib import Path
import hashlib
import heapq
import json
import math
import os
import sys
import shutil
import subprocess
import pcbnew as p
from pcb_bounds import inflated_box
from drc_regression import introduced
from pcb_preservation import verify_preservation
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
def read(n):return json.loads((root/(n+'.json')).read_text())
enable='--cpu-enable' in sys.argv
base=read('layout-exp-spi0-pullup' if enable else 'layout-exp-sda-land');src=root/base['board'];window=read('cpu-enable-rail-window' if enable else 'exp-sda-soc-window')
assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']==window['parent_sha256']
folder=root/('runs/cpu-enable-vbat-elbow' if enable else 'runs/exp-sda-soc-launch');folder.mkdir(exist_ok=True);out=folder/src.name
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
prior=json.loads((src.parent/'drc.json').read_text());uid=lambda o:o.m_Uuid.AsString();v=lambda xy:p.VECTOR2I(*xy)
def segment(b,a,z,net,layer,width):
    t=p.PCB_TRACK(b);t.SetStart(v(a));t.SetEnd(v(z));t.SetNetCode(net);t.SetLayer(layer);t.SetWidth(width);return t
winner=None;attempts=[]
for c in window['single_obstacle_candidates']:
    allowed=[('WIFI_VBAT',('In3.Cu','In3.Cu'))] if enable else [('EXP_SPI_CS0_N',('In3.Cu','In3.Cu')),('GND',('B.Cu','B.Cu'))]
    if (c['name'],tuple(l for u,l in c['obstacles'])) not in allowed:continue
    b=p.LoadBoard(str(src));original=list(b.GetTracks());ids={u for u,l in c['obstacles']};old=[t for t in original if uid(t) in ids]
    ends=Counter(tuple(pt) for t in old for pt in (t.GetStart(),t.GetEnd()))
    if len(ends)!=3 or max(ends.values())!=2:continue
    a,z=[pt for pt,n in ends.items() if n==1];width=old[0].GetWidth();code=old[0].GetNetCode();side=old[0].GetLayer()
    outer_a,outer_z=a,z
    if enable:
        bend=next(pt for pt,count in ends.items() if count==2)
        def cut(pt):
            dx,dy=pt[0]-bend[0],pt[1]-bend[1]
            scale=min(1,900000/max(abs(dx),abs(dy)))
            return (bend[0]+round(dx*scale),bend[1]+round(dy*scale))
        a,z=cut(a),cut(z)
    for t in old:b.Remove(t)
    at=tuple(c['via_nm']);pin=b.FindFootprintByReference('R1002' if enable else 'U1').FindPadByNumber('1' if enable else 'AE15')
    via=p.PCB_VIA(b);via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetWidth(450000);via.SetDrill(200000);via.SetNetCode(pin.GetNetCode());via.SetPosition(v(at))
    b.Add(via);ts=[via];raw=c['path_nm'];compressed=[raw[0]]
    for u,w in zip(raw[1:],raw[2:]+[None]):
        if w is not None:
            first=compressed[-1];e=(u[0]-first[0],u[1]-first[1]);f=(w[0]-u[0],w[1]-u[1])
            if e[0]*f[1]==e[1]*f[0] and e[0]*f[0]+e[1]*f[1]>0:continue
        compressed.append(u)
    for x,y in zip(compressed,compressed[1:]):
        t=segment(b,x,y,pin.GetNetCode(),p.F_Cu,200000 if enable else 76200);b.Add(t);ts.append(t)
    near=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if inflated_box(o,round(max(math.dist(a,at),math.dist(z,at)))+3450000).Contains(v(at)) and o.GetNetCode()!=code]
    shapes=[(o.GetEffectiveShape(side),o.GetBoundingBox()) for o in near if o.IsOnLayer(side)]
    holes=[o.GetEffectiveHoleShape() for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    t=segment(b,a,z,code,side,width)
    def legal(x,y):
        t.SetStart(v(x));t.SetEnd(v(y));sh=t.GetEffectiveShape(side);bb=inflated_box(t,260000)
        return not any(bb.Intersects(box) and sh.Collide(s,202000) for s,box in shapes) and not any(sh.Collide(h,252000) for h in holes)
    costs={a:0};queue=[(math.dist(a,z),a)];parent={};end=None
    while queue:
        _,pt=heapq.heappop(queue)
        if math.dist(pt,z)<55000 and legal(pt,z):end=pt;break
        for dx,dy in ((0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)):
            dest=(pt[0]+dx*50000,pt[1]+dy*50000);g=costs[pt]+math.hypot(dx,dy)*50000
            if g+math.dist(dest,z)>math.dist(a,z)+3200000 or g>=costs.get(dest,math.inf) or not legal(pt,dest):continue
            costs[dest]=g;parent[dest]=pt;heapq.heappush(queue,(g+math.dist(dest,z),dest))
    if end is None:attempts.append(dict(at=at,reason='inner route blocked'));continue
    path=[end]
    while path[-1] in parent:path.append(parent[path[-1]])
    path=list(reversed(path));path.append(z);clean=[path[0]]
    while len(path)>1:
        k=max(i for i in range(1,len(path)) if legal(path[0],path[i]));clean.append(path[k]);path=path[k:]
    if enable:clean=[outer_a]+clean+[outer_z]
    old_length=sum(t.GetLength() for t in old)
    new_length=sum(math.dist(x,y) for x,y in zip(clean,clean[1:]))
    if enable and (width!=1000000 or new_length>old_length+500000):
        attempts.append(dict(at=at,reason='VBAT length budget',delta_mm=(new_length-old_length)/1e6));continue
    for x,y in zip(clean,clean[1:]):
        if x!=y:b.Add(segment(b,x,y,code,side,width))
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    delta=introduced(prior,json.loads((folder/'drc.json').read_text()))
    if any(r['type']!='via_dangling' or r['items']!=[uid(via)] for r in delta):attempts.append(dict(at=at,delta=delta));continue
    saved=p.LoadBoard(str(out));saved.BuildConnectivity();q=saved.FindFootprintByReference('R1002' if enable else 'U1').FindPadByNumber('1' if enable else 'AE15')
    if uid(via) not in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(q)}:continue
    proof=verify_preservation(p.LoadBoard(str(src)),saved,replaced_copper=ids)
    winner=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),preservation=proof,new_drc=delta,site_nm=at,via_uuid=uid(via),reworked_net=c['name'],reworked_width_mm=width/1e6,length_delta_mm=(new_length-old_length)/1e6);break
(root/('cpu-enable-vbat-elbow.json' if enable else 'exp-sda-soc-launch.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],candidate=winner,attempts=attempts,assembly_ready=False),indent=2)+'\n')
print(bool(winner),attempts,flush=True);os._exit(0)
