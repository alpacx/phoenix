"""Search low-speed controls from existing copper with true circular BGA obstacles."""
from pathlib import Path
import json,hashlib,math,subprocess
import pcbnew as p
from phy_corridor_path import geometry
tools=Path(__file__).resolve().parent
r=tools.parent/'migration-rk3562/experiments/phy-power-parallel'
d=json.loads((r/'layout-soc-ground-existing-barrel.json').read_text());src=r/d['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==d['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
def pad(name):
    ref,num=name.split('.');return b.FindFootprintByReference(ref).FindPadByNumber(num)
def get_sites(group,layer):
    q=pad(group[0]);ids={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(q)}
    sites=[tuple(pad(n).GetPosition()) for n in group if pad(n).IsOnLayer(layer)]
    for t in b.GetTracks():
        if t.m_Uuid.AsString() not in ids or not t.IsOnLayer(layer):continue
        if isinstance(t,p.PCB_VIA):sites.append(tuple(t.GetPosition()));continue
        a,z=tuple(t.GetStart()),tuple(t.GetEnd());steps=max(1,math.ceil(t.GetLength()/400000))
        sites.extend(tuple(round(u+(v-u)*k/steps) for u,v in zip(a,z)) for k in range(steps+1))
    return sorted(set(sites))
nets=('PMIC_INT_N','PMIC_SLEEP','RESET_N','ETH_RESET_GPIO_N','LCD_RESET_N','WIFI_REG_ON','RECOVERY_ADC','THERMAL_SHUTDOWN','EXP_GPIO2','EXP_GPIO3','DEBUG_RX','DEBUG_TX','EXP_SPI_CS1_N','I2C0_SCL','I2C0_SDA')
rows=[]
for net in nets:
    groups=d['open_nets'][net];code=pad(groups[0][0]).GetNetCode()
    for l in (p.F_Cu,p.B_Cu):
        traces,pads=geometry(b,l,code,oval_caps=True);rects=list(pads)
        for f in b.GetFootprints():
            for q in f.Pads():
                if q.GetNetCode()==code or not q.IsOnLayer(l) or q.GetShape()!=p.PAD_SHAPE_CIRCLE:continue
                bb=q.GetBoundingBox();key=(bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom())
                if key in rects:rects.remove(key);xy=tuple(q.GetPosition());traces.append((xy,xy,q.GetSize().x))
        gs=[get_sites(g,l) for g in groups]
        for i,a in enumerate(gs):
            for j,z in enumerate(gs[:i]):
                if not a or not z:continue
                dist=min(math.dist(x,y) for x in a for y in z)
                if dist>18000000:continue
                start=sorted(a,key=lambda x:min(math.dist(x,y) for y in z))[:4];goal=sorted(z,key=lambda y:min(math.dist(x,y) for x in a))[:6]
                req=dict(geometry=[traces,rects],width=200000,sites=start,target=goal,limit=int(dist+3500000))
                proc=subprocess.run(['python3',str(tools/'screen_cpu_launch_corridor.py')],input=json.dumps(req),text=True,capture_output=True,check=True)
                proof=json.loads(proc.stdout)
                rows.append(dict(net=net,groups=[groups[i][0],groups[j][0]],layer=b.GetLayerName(l),front=proof['front_nodes'],gap_nm=proof['closest'],path=proof['path']))
(r/'service-controls-reloaded-surface.json').write_text(json.dumps(dict(parent_sha256=d['sha256'],cases=rows),indent=2)+'\n')
print(len(rows),[(x['net'],x['groups']) for x in rows if x['path']])
