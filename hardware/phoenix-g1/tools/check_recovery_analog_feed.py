"""Follow the relocated recovery pull-up backwards, retaining 0.5-mm analog supply routes."""
from pathlib import Path
import json,hashlib,subprocess,math
import pcbnew as p
from phy_corridor_path import geometry
tools=Path(__file__).resolve().parent;r=tools.parent/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((r/'layout-recovery-adc-relocated.json').read_text());src=r/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();code=b.FindNet('VCCA_1V8').GetNetCode()
def q(n):
 ref,num=n.split('.');return b.FindFootprintByReference(ref).FindPadByNumber(num)
groups=cp['open_nets']['VCCA_1V8']
examples=[]
for layer in (p.F_Cu,p.B_Cu):
    geo=geometry(b,layer,code,oval_caps=True);bygroup=[]
    for g in groups:
        sits={tuple(q(n).GetPosition()) for n in g if q(n).IsOnLayer(layer) and not n.startswith('R')}
        ids={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(q(g[0]))}
        for t in b.GetTracks():
            if t.m_Uuid.AsString() not in ids or not t.IsOnLayer(layer) or isinstance(t,p.PCB_VIA) or t.GetWidth()<500000:continue
            a,z=tuple(t.GetStart()),tuple(t.GetEnd());steps=max(1,math.ceil(t.GetLength()/250000));sits.update(tuple(round(u+(v-u)*i/steps) for u,v in zip(a,z)) for i in range(steps+1))
        bygroup.append(sorted(sits))
    for i,x in enumerate(bygroup):
        for j,y in enumerate(bygroup[:i]):
            if not x or not y:continue
            distance=min(math.dist(a,z) for a in x for z in y)
            if distance>16000000:continue
            req=dict(geometry=geo,width=500000,sites=x,target=y,limit=int(distance+4500000))
            proc=subprocess.run(['python3',str(tools/'screen_cpu_launch_corridor.py')],input=json.dumps(req),capture_output=True,text=True,check=True)
            d=json.loads(proc.stdout);examples.append(dict(a=groups[i],b=groups[j],layer=b.GetLayerName(layer),closest=d['closest'],front=d['front_nodes'],path=d['path']))
(r/'analog-recovery-bank-surface.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],cases=examples),indent=2)+'\n');print(len(examples),[(o['a'],o['b']) for o in examples if o['path']])
