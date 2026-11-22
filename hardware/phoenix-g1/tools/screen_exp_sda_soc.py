"""Find a legal short package-width SDA escape to a standard through-via using native pad shapes."""
from collections import defaultdict,Counter
from pathlib import Path
import hashlib
import heapq
import json
import math
import os
import sys
import pcbnew as p
from pcb_bounds import inflated_box
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
xtal=next((n for n in ('XIN24M','XOUT24M') if n in sys.argv),None)
service=next((n for n in ('THERMAL_SHUTDOWN','ETH_RESET_GPIO_N','WIFI_REG_ON','WIFI_HOST_WAKE','PMIC_INT_N','PMIC_SLEEP','I2C0_SCL','I2C0_SDA','RESET_N') if n in sys.argv),None)
wifi_terminal=service=="WIFI_HOST_WAKE" and "--radio-terminal" in sys.argv
pmic_terminal=service=="PMIC_INT_N" and "--pmic-terminal" in sys.argv
emmc=next((n for n in ('EMMC_D0','EMMC_D1','EMMC_D2','EMMC_D3','EMMC_D4','EMMC_D5','EMMC_D6','EMMC_D7','EMMC_CLK','SOC_EMMC_CLK','EMMC_CMD','EMMC_STRB') if n in sys.argv),None)
emmc_socket=emmc and '--socket' in sys.argv
factory=emmc or service or next((n for n in ('RECOVERY_ADC','DEBUG_TX','DEBUG_RX') if n in sys.argv),None)
released_dir='--released-mux-dir' in sys.argv
dir_cap='--mux-dir-cap-window' in sys.argv
mux_dir='--mux-dir' in sys.argv or dir_cap or released_dir
mux_aon='--mux-aon-relief' in sys.argv
mux='--mux-enable' in sys.argv or mux_aon or mux_dir
gpio_case=next((int(a.split('=')[1]) for a in sys.argv if a.startswith('--reset-gpio=')),None)
display=next((n for n in ('LCD_RESET_N','LCD_CS_N','LCD_MOSI','LCD_SCLK') if n in sys.argv),None)
reset_ctrl='--reset-controls' in sys.argv
u3_first='--u3-first' in sys.argv
keep_u3='--keep-u3' in sys.argv or u3_first
ground_vias='--ground-via-relief' in sys.argv
ground_relief='--front-ground-relief' in sys.argv or ground_vias
fixed_only='--fixed-pad-envelope' in sys.argv
ldo='--ldo6' in sys.argv
cpu_enable='--cpu-enable' in sys.argv
cp=json.loads((root/('layout-emmc-data-power.json' if emmc else 'wifi_host_wake-service-launch.json' if wifi_terminal else 'layout-gpu-cap-bank.json' if service else 'layout-usb-direction-complete.json' if factory else 'layout-memory-bank-c1665.json' if released_dir else 'layout-usb-enable-trunk.json' if mux_dir or xtal else 'layout-lcd-select-trunk.json' if reset_ctrl or mux else 'display-mosi-u3-first.json' if u3_first else 'layout-lcd-select-trunk.json' if ground_relief else 'layout-lcd-clock-trunk.json' if fixed_only and display else 'layout-cpu-enable-bias.json' if ldo or display else 'layout-exp-spi0-pullup.json' if cpu_enable else 'layout-exp-sda-land.json')).read_text());protected_ids=set(cp['returns'][0]['added']) if u3_first else {'6841ac21-0249-448b-b073-05b4644b1e46','7743df3c-c137-4076-8d7f-fecf0c0f2619'};cp=cp['candidate'] if u3_first or wifi_terminal else cp;src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
ground_ball=next((arg.split('=',1)[1] for arg in sys.argv if arg.startswith('--ground-ball=')),None)
if ground_ball:
    factory='GND'
    cp=json.loads((root/('layout-bga-ground-remaining.json' if '--qualified-ground' in sys.argv else 'layout-bga-ground-drops.json' if '--remaining-ground' in sys.argv else 'layout-emmc-strobe-pulldown.json')).read_text())
    src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
host_relief=emmc=='EMMC_STRB' and '--host-wifi-i2c' in sys.argv
if host_relief:
    cp=json.loads((root/'layout-emmc-strobe-pulldown.json').read_text())
    src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
if gpio_case is not None:
    src=root/'runs/display-reset-gpio-chain'/('gpio-coupon-'+str(gpio_case)+'.kicad_pcb')
b=p.LoadBoard(str(src));f=b.FindFootprintByReference('U8001' if emmc_socket else 'U25' if wifi_terminal else 'U4' if pmic_terminal else 'U6' if mux else 'U4' if ldo else 'R1002' if cpu_enable else 'U1');q=f.FindPadByNumber('11' if mux_dir else '12' if mux else '31' if ldo else '1' if cpu_enable else 'AE15');q=next(o for o in f.Pads() if o.GetNetname()==(factory or xtal or display)) if factory or display or xtal else f.FindPadByNumber('L3') if gpio_case is not None else q;center=tuple(q.GetPosition());v=lambda xy:p.VECTOR2I(*xy)
if ground_ball:
    ref,num=ground_ball.split('.');f=b.FindFootprintByReference(ref);q=f.FindPadByNumber(num);assert q.GetNetname()=='GND';center=tuple(q.GetPosition())
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
obs=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if o.GetNetCode()!=q.GetNetCode() and inflated_box(o,6700000).Contains(v(center))]
omitted=[]
if host_relief:
    omitted=[o for o in obs if isinstance(o,p.PCB_TRACK) and o.GetNetname() in ('EXP_I2C_SCL','+3V58_WIFI')]
    omit_ids={o.m_Uuid.AsString() for o in omitted};obs=[o for o in obs if o.m_Uuid.AsString() not in omit_ids]
if ground_relief:obs=[o for o in obs if isinstance(o,p.PAD) or keep_u3 and o.m_Uuid.AsString() in protected_ids or o.GetNetname()!='GND' or not (o.GetLayer()==p.F_Cu and (ground_vias or not isinstance(o,p.PCB_VIA)))]
if reset_ctrl:obs=[o for o in obs if isinstance(o,p.PAD) or isinstance(o,p.PCB_VIA) or o.GetNetname() not in ('EXP_GPIO1','LCD_DC')]
if dir_cap:obs=[o for o in obs if not(isinstance(o,p.PAD) and o.GetParentFootprint().GetReference()=='C1665' and o.GetNumber()=='1')]
if mux_aon:obs=[o for o in obs if o.m_Uuid.AsString()!='03cfdf46-4da6-49b4-93f5-da1a296aa0ce']
if fixed_only:obs=[o for o in obs if isinstance(o,p.PAD)]
cell=500000;indexed=defaultdict(list)
for o in obs:
    box=inflated_box(o,640000)
    clear=78200 if isinstance(o,p.PAD) and o.GetParentFootprint().GetReference()=='U1' or o.GetNetname().startswith('LPDDR4_') else 200000 if mux and isinstance(o,p.PAD) and o.GetParentFootprint().GetReference()=='U6' else 202000
    sh={l:o.GetEffectiveShape(l) for l in layers if o.IsOnLayer(l)}
    hole=o.GetEffectiveHoleShape() if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x else None
    for xx in range(box.GetLeft()//cell,box.GetRight()//cell+1):
        for yy in range(box.GetTop()//cell,box.GetBottom()//cell+1):indexed[xx,yy].append((o,sh,clear,hole))
same_net_holes=[o.GetEffectiveHoleShape() for o in b.GetTracks() if isinstance(o,p.PCB_VIA) and o.GetNetCode()==q.GetNetCode() and inflated_box(o,6700000).Contains(v(center))]
zones=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
via=p.PCB_VIA(b);via.SetWidth(450000);via.SetDrill(200000);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetViaType(p.VIATYPE_THROUGH)
surface=f.GetLayer()
t=p.PCB_TRACK(b);t.SetWidth(200000 if factory or cpu_enable or ldo or display or mux or xtal else 76200);t.SetLayer(surface)
qualified_ground=ground_ball and '--qualified-ground' in sys.argv
if qualified_ground:
    localpads=[(pad.GetBoundingBox(),pad.GetEffectiveShape(fp.GetLayer())) for fp in b.GetFootprints() for pad in fp.Pads() if inflated_box(pad,6800000).Contains(v(center))]
    groundplanes=[next(z.GetFilledPolysList(l) for z in b.Zones() if z.GetNetname()=='GND' and z.HasFilledPolysForLayer(l)) for l in (p.In1_Cu,p.In4_Cu)]
def near(pt):return indexed[pt[0]//cell,pt[1]//cell]
def run():
    front_termination=emmc=='SOC_EMMC_CLK' and '--front-termination' in sys.argv
    if front_termination:
        coords=[]
    starts=[(center[0]+x*25000,center[1]+y*25000) for x in range(-4,5) for y in range(-4,5) if math.hypot(x,y)<=4]
    if cpu_enable:
        starts=[(center[0]+x*25000,center[1]+y*25000) for x in range(-12,13) for y in range(-15,16) if q.HitTest(v((center[0]+x*25000,center[1]+y*25000)))]
    if mux:
        shape=q.GetEffectiveShape(surface);bb=q.GetBoundingBox();starts=[(x,y) for x in range(center[0]-250000,center[0]+250001,25000) for y in range(center[1]-100000,center[1]+100001,25000) if shape.Collide(v((x,y)),0)]
    if ldo or pmic_terminal or wifi_terminal:
        bb=q.GetBoundingBox();shape=q.GetEffectiveShape(surface)
        starts=[(x,y) for x in range(bb.GetLeft()-75000,bb.GetRight()+75001,25000) for y in range(bb.GetTop()-75000,bb.GetBottom()+75001,25000) if shape.Collide(v((x,y)),80000)]
    queue=[(0,pt) for pt in starts];heapq.heapify(queue);dist=dict.fromkeys(starts,0);parent={};blocked=set();sites=[];singletons={};histo=Counter();far=0
    while queue:
        cost,at=heapq.heappop(queue)
        if cost!=dist[at]:continue
        far=max(far,math.dist(at,center))
        if front_termination and at[0]%100000==0 and at[1]%100000==0:
            path=[at]
            while path[-1] in parent:path.append(parent[path[-1]])
            coords.append(dict(cost_nm=cost,path_nm=list(reversed(path))))
        via.SetPosition(v(at));land=via.GetEffectiveShape(surface);drill=via.GetEffectiveHoleShape()
        blockers=set();stuck=set()
        for o,sl,c,h in near(at):
            if any(land.Collide(s,c) or drill.Collide(s,252000) for s in sl.values()) or h and (land.Collide(h,252000) or drill.Collide(h,252000)):
                stuck.add((o.m_Uuid.AsString(),o.GetLayerName()));blockers.add(o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else o.GetNetname())
        if (service or emmc or ground_ball) and any(drill.Collide(h,252000) for h in same_net_holes):blockers.add('existing same-net barrel')
        if land.Collide(q.GetEffectiveShape(surface),100000 if host_relief or ground_ball else 75000):blockers.add('source pad')
        if any(z.Collide(land,0) for z in zones):blockers.add('keepout')
        if qualified_ground and not blockers:
            box=inflated_box(via,120000)
            if any(box.Intersects(bb) and land.Collide(sh,100000) for bb,sh in localpads):blockers.add("solder clearance")
            if not all(pl.Contains(v(at)) for pl in groundplanes):blockers.add("ground plane aperture")
        if not blockers:
            path=[at]
            while path[-1] in parent:path.append(parent[path[-1]])
            if not (ground_relief or reset_ctrl or dir_cap or gpio_case is not None) or all(math.dist(at,r['path_nm'][-1])>=(45000 if dir_cap else 275000) for r in sites):
                sites.append(dict(length_mm=cost/1e6,path_nm=list(reversed(path))))
            if len(sites)>=16:break
        else:
            histo[tuple(sorted(blockers))]+=1
            if len(blockers)==1 and 0<len(stuck)<=8 and 'source pad' not in blockers:
                code=tuple(sorted(stuck)); name=next(iter(blockers))
                if code not in singletons:
                    path=[at]
                    while path[-1] in parent:path.append(parent[path[-1]])
                    singletons[code]=dict(name=name,via_nm=at,obstacles=code,length_mm=cost/1e6,path_nm=list(reversed(path)))
        for dx,dy in ((1,0),(0,1),(-1,0),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
            end=(at[0]+dx*25000,at[1]+dy*25000);step=math.hypot(dx,dy)*25000
            if cost+step>6000000 or dist.get(end,math.inf)<=cost+step or (at,end) in blocked:continue
            t.SetStart(v(at));t.SetEnd(v(end));sh=t.GetEffectiveShape(surface)
            if any(surface in sl and sh.Collide(sl[surface],c) or h and sh.Collide(h,252000) for o,sl,c,h in near(at)):
                blocked.add((end,at));continue
            dist[end]=cost+step;parent[end]=at;heapq.heappush(queue,(cost+step,end))
    if front_termination:
        (root/'emmc-clock-front-reach.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],sites=coords),separators=(',',':'))+'\n')
    return dict(parent_sha256=cp['sha256'],surface=b.GetLayerName(surface),pin=f.GetReference()+'.'+q.GetNumber() if factory or display or xtal else 'U6.11' if mux_dir else 'U6.12' if mux else 'U1.L3' if gpio_case is not None else 'U4.31' if ldo else 'R1002.1' if cpu_enable else 'U1.AE15',width_mm=.2 if factory or cpu_enable or ldo or display or mux or xtal else .0762,grid_mm=.025,via_mm=[.45,.20],ground_relief=ground_relief,ground_via_relief=ground_vias,existing_tracks_and_vias_included=not fixed_only and not ground_relief,single_obstacle_candidates=list(singletons.values()),reachable_positions=len(dist),farthest_mm=far/1e6,sites=sites,via_obstacles=[dict(names=k,positions=n) for k,n in sorted(histo.items(),key=lambda z:(len(z[0]),-z[1]))[:20]],assembly_ready=False)
d=run();
if host_relief:d['diagnostic_omitted']=[o.m_Uuid.AsString() for o in omitted]
d['source_sha256']=hashlib.sha256(src.read_bytes()).hexdigest();(root/(('bga-ground-qualified-' if '--qualified-ground' in sys.argv else 'bga-ground-remaining-' if '--remaining-ground' in sys.argv else 'bga-ground-drop-')+ground_ball+'.json' if ground_ball else 'emmc-host-wifi-i2c-relief.json' if host_relief else emmc.lower()+('-socket-window.json' if emmc_socket else '-host-window.json') if emmc else 'wifi-host-wake-radio-window.json' if wifi_terminal else 'pmic-interrupt-terminal-window.json' if pmic_terminal else service.lower()+'-service-window.json' if service else factory.lower()+'-factory-window.json' if factory else 'usb-dir-c1665-released-window.json' if released_dir else ('reset-gpio-via-window-'+str(gpio_case)+'.json') if gpio_case is not None else xtal.lower()+'-soc-window.json' if xtal else 'usb-mux-dir-cap-window.json' if dir_cap else 'usb-mux-dir-window.json' if mux_dir else 'usb-mux-enable-aon-window.json' if mux_aon else 'usb-mux-enable-window.json' if mux else 'lcd-reset-control-window.json' if reset_ctrl else display.lower()+'-u3-first-window.json' if u3_first else display.lower()+'-preserve-u3.json' if keep_u3 else display.lower()+'-ground-via-relief.json' if ground_vias else display.lower()+'-ground-relief.json' if ground_relief else display.lower()+'-fixed-pad-envelope.json' if fixed_only and display else display.lower()+'-soc-window.json' if display else 'ldo6-pmu-native-window.json' if ldo else 'cpu-enable-rail-window.json' if cpu_enable else 'exp-sda-soc-window.json')).write_text(json.dumps(d,indent=2)+'\n');print(d['reachable_positions'],d['farthest_mm'],len(d['sites']),d['via_obstacles'][:3],flush=True);os._exit(0)
