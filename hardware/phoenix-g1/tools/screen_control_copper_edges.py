"""Find short connections between existing copper edges of distinct slow-control islands."""
from collections import defaultdict
from pathlib import Path
import hashlib,heapq,json,math,sys
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
io='--io-signals' in sys.argv
extended='--long-controls' in sys.argv or io
analog='--analog-bypass' in sys.argv
bypass='--bypass-banks' in sys.argv
bank='--io-banks' in sys.argv
output='--output-banks' in sys.argv
core='--core' in sys.argv or output
base=json.loads((root/('layout-npu-c434-paired-load.json' if bypass or analog or extended else 'layout-npu-output-cap-c444.json' if bank else 'layout-logic-output-cap-c441.json' if output else 'layout-io-bank-copper-contact.json' if core else 'layout-ground-copper-contact.json')).read_text())
src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
objs=[*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())]
uid=lambda o:o.m_Uuid.AsString()
V=lambda pt:p.VECTOR2I(*pt)
def pad(n):
    ref,num=n.split('.');return b.FindFootprintByReference(ref).FindPadByNumber(num)
def tiles(bb,s=500000):
    return ((i,j) for i in range(bb.GetLeft()//s,bb.GetRight()//s+1) for j in range(bb.GetTop()//s,bb.GetBottom()//s+1))
rows=[]
nets=('RESET_N','PMIC_INT_N','WIFI_REG_ON','ETH_RESET_GPIO_N','PMIC_SLEEP','THERMAL_SHUTDOWN','EXP_GPIO2','EXP_GPIO3','EXP_UART_RX','EXP_UART_TX','DEBUG_TX','DEBUG_RX','LCD_RESET_N','PHY_CFG_LDO0','PHY_CFG_LDO1','PHY_CFG_EXT','SOC_VBUS_DET','RECOVERY_ADC','I2C0_SDA','I2C0_SCL')
power='--power' in sys.argv or bank
if power:
    nets=('+3V3_PMU','+3V3_IO','+1V8_SYS','PMIC_1V8A','PMIC_1V8D','VDDA_0V9','EMMC_3V3','EMMC_IO_1V8','VCCA_1V8','VCCA1V8_PMU','VCCIO_ACODEC','VDDA0V9_IMAGE','USB_AVDD_1V8','USB_AVDD_0V9')
if core:
    nets=('VDD_CPU','VDD_NPU','VDD_GPU','VDD_LOGIC','+1V1_LPDDR4','PMIC_VDC')
if io:
    nets=[n for n in base['open_nets'] if n.startswith(('ETH_TX','ETH_RX','PHY_TX','PHY_RX','EMMC_D','WIFI_D','SOC_EMMC','EMMC_C','ETH_MD','WIFI_CLK','WIFI_CMD')) and not n.endswith(('_P','_N'))]
if analog:nets=('VDDA0V9_PMU','VCCA_1V8','VDDA0V9_IMAGE','VCCA1V8_IMAGE','+3V3_PMU','VDDA_0V9','VCCA1V8_PMU','VCCIO_ACODEC','USB_AVDD_0V9','USB_AVDD_1V8')
if bypass:nets=('VDD_GPU','VDD_NPU','VDD_LOGIC','VDD_CPU')
for net in nets:
    groups=base['open_nets'][net];code=b.FindNet(net).GetNetCode()
    index={uid(o):i for i,g in enumerate(groups) for o in b.GetConnectivity().GetConnectedItems(pad(g[0]))}
    index.update({uid(pad(label)):i for i,g in enumerate(groups) for label in g})
    members=[o for o in objs if uid(o) in index]
    if bypass:members=[o for o in members if isinstance(o,p.PAD) and o.GetParentFootprint().GetReference().startswith('C16')]
    reach=range(-40,41) if extended else range(-24,25) if output or bank or bypass else range(-16,17)
    if output or bank:
        members=[o for o in members if isinstance(o,p.PAD) and o.GetParentFootprint().GetReference().startswith(('C','L')) or isinstance(o,p.PCB_VIA) and o.GetDrillValue()>=300000 or isinstance(o,p.PCB_TRACK) and not isinstance(o,p.PCB_VIA) and o.GetWidth()>=(500000 if bank else 600000)]
    for side in (p.F_Cu,p.B_Cu,p.In2_Cu,p.In3_Cu):
        seeds=defaultdict(set);goals=defaultdict(list)
        for o in members:
            if not o.IsOnLayer(side):continue
            group=index[uid(o)];sh=o.GetEffectiveShape(side);bb=o.GetBoundingBox()
            for k in tiles(bb):goals[k].append((group,sh,uid(o)))
            # Multiple interior points at each pad/trace. Quantize to the same XY grid.
            if isinstance(o,p.PCB_TRACK) and not isinstance(o,p.PCB_VIA):
                a,z=tuple(o.GetStart()),tuple(o.GetEnd());n=max(1,math.ceil(o.GetLength()/100000))
                pts=[tuple(round((u+(v-u)*i/n)/100000)*100000 for u,v in zip(a,z)) for i in range(n+1)]
            else:
                pts=[(x*100000,y*100000) for x in range(bb.GetLeft()//100000,bb.GetRight()//100000+1) for y in range(bb.GetTop()//100000,bb.GetBottom()//100000+1)]
            seeds[group].update(pt for pt in pts if sh.Collide(V(pt),0))
        if len(seeds)<2:continue
        around=set()
        for g,ps in seeds.items():
            for k in {(x//500000,y//500000) for x,y in ps}:
                if any(h!=g for i in reach for j in reach for h,_,_ in goals.get((k[0]+i,k[1]+j),())):around.add(k)
        if not around:continue
        foreign=defaultdict(list)
        for o in objs:
            if o.GetNetCode()==code:continue
            sh=o.GetEffectiveShape(side) if o.IsOnLayer(side) else None
            hole=o.GetEffectiveHoleShape() if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x else None
            if sh or hole:
                for k in tiles(inflated_box(o,500000)):foreign[k].append((sh,hole))
        keep=[z.Outline() for z in [*b.Zones(),*(z for f in b.GetFootprints() for z in f.Zones())] if z.IsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()] if hasattr(p.ZONE,'IsRuleArea') else [z.Outline() for z in [*b.Zones(),*(z for f in b.GetFootprints() for z in f.Zones())] if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
        way=make(b,(0,0),(0,0),300000 if analog else 600000 if bypass else 800000 if core else 500000 if power else 200000,code,side)
        bounds=b.GetBoardEdgesBoundingBox();bounds.Inflate(-400000)
        def clear(a,z):
            if extended and (not bounds.Contains(V(a)) or not bounds.Contains(V(z))):return False
            way.SetStart(V(a));way.SetEnd(V(z));s=way.GetEffectiveShape(side)
            return not any((t and s.Collide(t,202000)) or (h and s.Collide(h,252000)) for t,h in foreign[(a[0]//500000,a[1]//500000)]) and not any(s.Collide(q,0) for q in keep)
        for g,ps in seeds.items():
            cost={at:0 for at in ps if (at[0]//500000,at[1]//500000) in around};parents={};queue=[(0,at) for at in cost];heapq.heapify(queue)
            found=None
            while queue:
                d,at=heapq.heappop(queue)
                if cost[at]!=d:continue
                k=at[0]//500000,at[1]//500000
                m=next(((h,i) for h,s,i in goals.get(k,[]) if h>g and s.Collide(V(at),0)),None)
                if m:
                    path=[at]
                    while path[-1] in parents:path.append(parents[path[-1]])
                    found=dict(groups=[groups[g][0],groups[m[0]][0]],path_nm=path[::-1],length_mm=d/1e6);break
                for i,j in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
                    z=at[0]+i*100000,at[1]+j*100000;dd=d+math.hypot(i,j)*100000
                    if dd<=(20000000 if extended else 12000000 if output or bank or bypass else 8000000) and dd<cost.get(z,math.inf) and clear(at,z):
                        cost[z]=dd;parents[z]=at;heapq.heappush(queue,(dd,z))
            rows.append(dict(net=net,layer=b.GetLayerName(side),group=g,nodes=len(cost),found=found))
    (root/('interface-copper-edge-candidates.json' if io else 'management-long-copper-edges.json' if extended else 'analog-bypass-copper-edges.json' if analog else 'local-soc-bypass-cap-pairs.json' if bypass else 'io-bank-wide-branches.json' if bank else 'output-bank-copper-edge-search.json' if output else 'core-copper-edge-search.json' if core else 'power-copper-edge-search.json' if power else 'control-copper-edge-search.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],rows=rows),indent=2)+'\n')
print([(r['net'],r['layer'],r['found']['length_mm']) for r in rows if r['found']])
