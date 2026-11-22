"""Complete low-speed nets from existing connected copper, with saved-board verification."""
import hashlib,itertools,json,math,os,shutil,subprocess
from collections import defaultdict
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from phy_corridor_path import geometry
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
import sys
rot_bus=next((n for n in ('scl','sda') if '--rotated-pmic-'+n in sys.argv),None)
mux_dir='--usb-direction-trunk' in sys.argv
mux_enable='--usb-enable-trunk' in sys.argv or mux_dir
lcd_cs='--lcd-select-trunk' in sys.argv
lcd_clock='--lcd-clock-trunk' in sys.argv or lcd_cs
n12_supply='--n12-supply-feed' in sys.argv
zq_supply='--zq-supply-feed' in sys.argv or n12_supply
restore_mosi='--restore-vddq-mosi' in sys.argv
vddq_first='--vddq-rail-first' in sys.argv
vddq_reverse='--vddq-load-frontier' in sys.argv
vddq_rear='--vddq-rear-bank-copper' in sys.argv or vddq_reverse or vddq_first
vddq='--lpddr-vddq-feed' in sys.argv or vddq_rear or zq_supply
rail_link='--moved-emmc-link' in sys.argv
restore_pull='--restore-emmc-pullup' in sys.argv
sys_tap=next((pad for pad in ('R8006.1','C2303.1','C2301.1') if '--sys-feed='+pad in sys.argv),None)
vdd1_extended='--vdd1-external-pair' in sys.argv
vdd1='--lpddr-vdd1-feed' in sys.argv or vdd1_extended or vddq or bool(sys_tap) or rail_link or restore_pull
current_vcc='--current-vcc' in sys.argv
emmc_rear='--emmc-rear-channel' in sys.argv
emmc_staggered='--emmc-staggered' in sys.argv or emmc_rear or current_vcc
emmc_wide='--emmc-wide-root' in sys.argv or emmc_staggered
emmc_link='--emmc-vcc-link' in sys.argv or emmc_wide
cpu_elbow='--cpu-enable-from-elbow' in sys.argv
cpu_pivot='--cpu-enable-pivot-route' in sys.argv
cpu_enable='--cpu-enable-bias' in sys.argv or cpu_pivot or cpu_elbow
spi_feed='--exp-chip-select-feed' in sys.argv or cpu_enable
chip_select='--exp-chip-select' in sys.argv
wifi_bank='--wifi-bank-feed' in sys.argv
sda_soc='--exp-sda-complete' in sys.argv
sda_launch='--exp-sda-from-launch' in sys.argv or sda_soc
sda_signal='--exp-data-signal' in sys.argv or sda_launch
exp_sda='--exp-data-pullup' in sys.argv or sda_signal
exp_clock='--exp-clock-pullup' in sys.argv or exp_sda
wifi_pullup='--wifi-pullup' in sys.argv or exp_clock or wifi_bank or spi_feed
storage='--storage-rail' in sys.argv
full='--full-feed' in sys.argv
toe='--pad-toe' in sys.argv or full or storage or wifi_pullup or bool(rot_bus)
phy_controls=mux_enable or lcd_clock or emmc_link or chip_select or toe or '--phy-management' in sys.argv
checkpoint_name='lcd-select-grid-route' if lcd_cs else 'lcd-clock-grid-route' if lcd_clock else 'emmc-vcc-wide-source' if emmc_wide else 'emmc-vcc-io-source' if emmc_link else 'cpu-enable-elbow-route' if cpu_elbow else 'cpu-enable-pivot-route' if cpu_pivot else 'cpu-enable-bias-feed' if cpu_enable else 'exp-spi0-restore-feed' if spi_feed else 'exp-chip-select-trunks' if chip_select else 'exp-sda-complete' if sda_soc else 'exp-sda-after-launch' if sda_launch else 'wifi-io-pullup-bank-feed' if wifi_bank else 'exp-i2c-sda-signal' if sda_signal else 'exp-data-pullup-feed' if exp_sda else 'exp-clock-pullup-feed' if exp_clock else 'wifi-pullup-vias' if wifi_pullup else 'storage-rail-groups' if storage else 'control-full-feed' if full else 'management-pad-toe' if toe else 'phy-management' if phy_controls else 'control-groups'
parent_name='display-cs-gnd-fanout' if lcd_cs else 'lcd-clock-soc-launch' if lcd_clock else 'layout-cpu-enable-bias' if emmc_link else 'cpu-enable-vbat-elbow' if cpu_elbow else 'cpu-enable-pivot-input' if cpu_pivot else 'layout-exp-spi0-pullup' if cpu_enable else 'spi0-local-signal' if spi_feed else 'layout-exp-sda-complete' if chip_select else 'exp-sda-soc-launch' if sda_soc else 'exp-sda-gpio1-launch' if sda_launch else 'layout-exp-data-pullup' if sda_signal or wifi_bank else 'layout-exp-clock-pullup' if exp_sda else 'layout-lpddr-dq0-reference' if exp_clock else 'layout-wifi-sdio-bias' if wifi_pullup else 'emmc-pullup-supply' if storage else 'layout-phy-full-feed' if full else 'ground-package-local' if toe else 'layout-regulator-joint' if phy_controls else 'emmc-ball-cap'
if mux_enable:
    checkpoint_name='usb-mux-enable-trunk';parent_name='usb-enable-aon-fanout'
if mux_dir:
    checkpoint_name='usb-orientation-trunk';parent_name='usb-orientation-released-escape'
if emmc_staggered:
    checkpoint_name='emmc-rear-channel' if emmc_rear else 'emmc-staggered-feed';parent_name='layout-lcd-select-trunk'
if current_vcc:
    checkpoint_name='emmc-vcc-source-window';parent_name='layout-emmc-data-power'
if rot_bus:
    label=('rotated-c422-' if '--after-c422' in sys.argv else 'rotated-left-' if '--left-first' in sys.argv else 'rotated-pmic-')+rot_bus
    checkpoint_name=label+'-trunk';parent_name=label+'-launch'
service=next((n for n in ('PMIC_INT_N','WIFI_HOST_WAKE') if n in sys.argv),None)
if service:
    checkpoint_name=service.lower()+'-service-trunk';parent_name=service.lower()+'-service-launch'
    if '--recovered-radio-wake' in sys.argv:
        assert service=='WIFI_HOST_WAKE'
        checkpoint_name='radio-wake-fewer-vias' if '--minimize-transitions' in sys.argv else 'radio-wake-complete';parent_name='radio-wake-reset-rework'
    if '--existing-service-via' in sys.argv:
        checkpoint_name=service.lower()+'-existing-service-trunk';parent_name='layout-gpu-cap-bank'
reuse_bus='--existing-pmic-via' in sys.argv
if reuse_bus:
    assert rot_bus=='scl'
    checkpoint_name='rotated-existing-scl-trunk';parent_name='rotated-left-sda-complete'
if vdd1:
    checkpoint_name='vdd1-external-pair-trunk' if vdd1_extended else 'lpddr-vdd1-source-feed';parent_name='vdd1-external-pair' if vdd1_extended else 'layout-lpddr-vdd1-bank'
if vddq:checkpoint_name='lpddr-vddq-load-frontier' if vddq_reverse else 'lpddr-vddq-rear-source-feed' if vddq_rear else 'lpddr-vddq-source-feed';parent_name='layout-lpddr-vdd1-source'
if vddq_first:checkpoint_name='vddq-rail-first';parent_name='vddq-reserved-mosi'
if zq_supply:checkpoint_name='vddq-zq-source';parent_name='ram-front-zq'
if n12_supply:checkpoint_name='vddq-n12-source';parent_name='memory-n12-escape'
if sys_tap:checkpoint_name='sys-feed-'+sys_tap.lower();parent_name='layout-memory-n12-neighbors'
if sys_tap and '--tap-frontier' in sys.argv:checkpoint_name+='-load'
if rail_link:checkpoint_name='emmc-vccq-moved-link-source';parent_name='emmc-io-link-keep-pullup'
if restore_pull:checkpoint_name='emmc-vccq-fixed-pullup-feed';parent_name='emmc-vccq-moved-link-source'
if restore_mosi:checkpoint_name='vddq-mosi-restored';parent_name='vddq-rail-first'
source=json.loads((root/(parent_name+'.json')).read_text());source=source['candidate'] if rail_link or n12_supply or vdd1_extended or (service and '--existing-service-via' not in sys.argv) or (rot_bus and not reuse_bus) or mux_enable or sda_launch or lcd_clock or cpu_elbow or (spi_feed and not cpu_enable) else source;current=root/source['board']
assert hashlib.sha256(current.read_bytes()).hexdigest()==source['sha256']
stack=[p.F_Cu,p.In3_Cu,p.In2_Cu,p.B_Cu]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
nets=['PMIC_INT_N','I2C0_SCL','I2C0_SDA','RESET_N','PMIC_SLEEP','PMIC_PWRON_N',
      'EXP_I2C_SDA','EXP_SPI_CS0_N','EXP_SPI_CS1_N','EXP_GPIO2','EXP_GPIO3','EXP_UART_RX','EXP_UART_TX',
      'DEBUG_TX','DEBUG_RX','LCD_RESET_N','LCD_CS_N','USB_MUX_ENABLE_N','USB_ORIENTATION',
      'ETH_RESET_GPIO_N','WIFI_REG_ON','WIFI_HOST_WAKE','THERMAL_SHUTDOWN','RECOVERY_ADC']
if phy_controls and not full:
    nets=['PHY_CFG_LDO0','PHY_CFG_LDO1','PHY_CFG_EXT','ETH_MDC','ETH_MDIO','SOC_VBUS_DET']
if wifi_pullup:nets=['+3V3_IO']
if sda_signal:nets=['EXP_I2C_SDA']
if storage:nets=['EMMC_IO_1V8','EMMC_3V3']
if lcd_clock:nets=['LCD_CS_N'] if lcd_cs else ['LCD_SCLK']
if mux_enable:nets=['USB_ORIENTATION' if mux_dir else 'USB_MUX_ENABLE_N']
if emmc_link:nets=['+3V3_IO']
if spi_feed:nets=['+3V3_PMU']
if chip_select:nets=['EXP_SPI_CS0_N','EXP_SPI_CS1_N']
if rot_bus:nets=["PMIC_"+rot_bus.upper()]
if restore_mosi:nets=['EXP_SPI_MOSI']
if service:nets=[service]
if vdd1:nets=['EMMC_IO_1V8' if restore_pull else '+1V1_LPDDR4' if vddq else '+1V8_SYS']
records=[];held=[]
def label(q):return q.GetParentFootprint().GetReference()+'.'+q.GetNumber()
def points(group,l):
    positions=set()
    for k in group:
        if not k.IsOnLayer(l):continue
        if isinstance(k,p.PAD):
            center=k.GetPosition();positions.add(tuple(center));box=k.GetBoundingBox()
            xs={center.x,*[round(box.GetLeft()+box.GetWidth()*f) for f in (.07,.15,.27,.73,.85,.93)]}
            ys={center.y,*[round(box.GetTop()+box.GetHeight()*f) for f in (.07,.15,.27,.73,.85,.93)]}
            positions.update((x,y) for x in xs for y in ys if k.HitTest(p.VECTOR2I(x,y)))
            if toe:
                for x in (box.GetLeft()-50000,box.GetRight()+50000):
                    positions.add((x,center.y))
                for y in (box.GetTop()-50000,box.GetBottom()+50000):
                    positions.add((center.x,y))
        elif isinstance(k,p.PCB_TRACK):
            a,z=tuple(k.GetStart()),tuple(k.GetEnd());count=max(1,math.ceil(k.GetLength()/400000))
            positions.update(tuple(round(x+(y-x)*i/count) for x,y in zip(a,z)) for i in range(count+1))
    return sorted(positions)
def pad_ids(g):return {i.m_Uuid.AsString() for i in g if isinstance(i,p.PAD)}
def write():
    (root/(checkpoint_name+'.json')).write_text(json.dumps(dict(board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),parent_sha256=source['sha256'],records=records,held=held,assembly_ready=False),indent=2)+'\n')
for net in nets:
  while True:
    b=p.LoadBoard(str(current));b.BuildConnectivity();code=b.GetNetcodeFromNetname(net)
    pads=[q for f in b.GetFootprints() for q in f.Pads()]
    native={k.m_Uuid.AsString():k for k in pads+list(b.GetTracks())}
    seen=set();groups=[]
    for q in pads:
        if q.GetNetCode()!=code or q.m_Uuid.AsString() in seen:continue
        uids={k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(q)} | {q.m_Uuid.AsString()}
        g=[native[i] for i in sorted(uids) if i in native];seen.update(pad_ids(g));groups.append((q,g))
    if wifi_pullup and not sda_signal:
        targets=({'R2010.2','R2011.2','R2012.2','R2013.2','R2014.2','U4.55'} if wifi_bank else {'R2101.2','U4.55'}) if (exp_sda or wifi_bank) else {'R2102.2','U4.55'} if exp_clock else {'R2012.2','U25.22'}
        if spi_feed:targets={'R1002.1','TP5.1'} if cpu_enable else {'R2103.2','TP5.1'}
        groups=[entry for entry in groups if targets.intersection(label(k) for k in entry[1] if isinstance(k,p.PAD))]
    if emmc_link:
        targets={'C470.1','R8007.1'}
        groups=[g for g in groups if targets.intersection(label(o) for o in g[1] if isinstance(o,p.PAD))]
    if vdd1:
        targets={'R8001.1','R8006.2'} if restore_pull else {'L405.2','R8006.1'} if rail_link else {'L405.2',sys_tap} if sys_tap else {'L403.2','U2.N12'} if n12_supply else {'L403.2','R201.2'} if zq_supply else {'L403.2','C1666.1'} if vddq else {'L405.2','C2305.1'}
        groups=[g for g in groups if targets.intersection(label(o) for o in g[1] if isinstance(o,p.PAD))]
    if len(groups)<2:break
    geos={}
    for l in layers:
        tracks,boxes=geometry(b,l,code,oval_caps=True,df40_pitch=sda_signal or chip_select or restore_mosi);polygons=[]
        for zone in b.Zones():
            if zone.GetIsRuleArea() and zone.IsOnLayer(l) and (zone.GetDoNotAllowTracks() or zone.GetDoNotAllowVias()):
                for i in range(zone.Outline().OutlineCount()):
                    o=zone.Outline().Outline(i);polygons.append([tuple(o.CPoint(j)) for j in range(o.PointCount())])
        geos[l]=[tracks,boxes,polygons]
    holes=[[tuple(t.GetPosition()),tuple(t.GetPosition()),t.GetDrillValue()+400000] for t in b.GetTracks() if isinstance(t,p.PCB_VIA)]
    boxes=[q.GetBoundingBox() for q in pads]
    req=dict(layers=[geos[l] for l in stack],through=list(geos.values()),via_keepouts=[holes,[(v.GetLeft(),v.GetTop(),v.GetRight(),v.GetBottom()) for v in boxes]],bounds=[500000,500000,89500000,39500000],grid_nm=100000 if toe or chip_select else 200000)
    if '--minimize-transitions' in sys.argv:req['via_cost_nm']=12000000
    if wifi_pullup:req.update(width_nm=250000,bounds=[49000000,20500000,68500000,34500000])
    if exp_clock:req.update(bounds=[27500000,24500000,61000000,39800000])
    if wifi_bank:req.update(bounds=[18500000,4000000,72000000,39700000])
    if sda_signal:req.update(width_nm=200000,bounds=[26000000,500000,80000000,36500000])
    if sda_soc or spi_feed:req.update(bounds=[500000,500000,89500000,39500000])
    if storage:req.update(width_nm=500000,via_nm=600000,bounds=[27000000,500000,52000000,23000000])
    if lcd_clock or mux_enable or service or restore_mosi:req.update(grid_nm=100000)
    if emmc_link:req.update(width_nm=500000,via_nm=600000,paired_vias=True,grid_nm=100000,bounds=[39500000,500000,70500000,18500000])
    if vdd1:req.update(width_nm=600000,via_nm=600000,paired_vias=True,grid_nm=100000,explain=True,export_frontier=True)
    order=sorted(itertools.combinations(groups,2),key=lambda pair:math.dist(tuple(pair[0][0].GetPosition()),tuple(pair[1][0].GetPosition())))
    for (qa,ga),(qz,gz) in order:
        if wifi_bank and 'U4.55' not in {label(q) for q in ga+gz if isinstance(q,p.PAD)}:continue
        a=label(qa);z=label(qz)
        req.update(start=[points(ga,l) for l in stack],end=[points(gz,l) for l in stack])
        if emmc_link:
            left=[q for q in ga if isinstance(q,p.PAD) and label(q) in targets]
            right=[q for q in gz if isinstance(q,p.PAD) and label(q) in targets]
            assert len(left)==len(right)==1
            req.update(start=[points(left,l) for l in stack],end=[points(right,l) for l in stack])
            if emmc_wide:
                inventory=json.loads((root/('emmc-vcc-current-source.json' if current_vcc else 'emmc-staggered-source-inventory.json' if emmc_staggered else 'emmc-wide-source-inventory.json')).read_text())
                assert inventory['parent_sha256']==source['sha256']
                if emmc_staggered:
                    req['explain']=True;req['export_frontier']=True
                    req['pair_offsets_nm']=sorted(((x*100000,y*100000) for x in range(-11,12) for y in range(-11,12) if 8<=math.hypot(x,y)<=11),key=lambda p:math.hypot(*p))
                source_groups={l:[native[r['uuid']] for r in inventory['wide_source_objects'] if r['layer']==b.GetLayerName(l)] for l in stack}
                req['start' if label(left[0])=='C470.1' else 'end']=[points(source_groups[l],l) for l in stack]
                req['bounds']=[500000,500000,89500000,39500000]
        if vdd1:
            for name,group in [('start',ga),('end',gz)]:
                allowed=[o for o in group if isinstance(o,p.PAD) and label(o) in targets]
                if zq_supply and any(label(o)=='L403.2' for o in allowed):
                    allowed.extend(o for o in group if isinstance(o,p.PAD) and o.GetParentFootprint().GetReference() in {f'C{i}' for i in range(1646,1679)})
                    allowed.extend(o for o in group if not isinstance(o,(p.PAD,p.PCB_VIA)) and o.GetWidth()>=600000)
                if vddq and not zq_supply and any(label(o)=='C1666.1' for o in allowed):
                    allowed.extend(o for o in group if isinstance(o,p.PAD) and o.GetParentFootprint().GetReference() in {f'C{i}' for i in range(1646,1679)})
                if vddq_rear and any(label(o)=='C1666.1' for o in allowed):
                    allowed.extend(o for o in group if not isinstance(o,(p.PAD,p.PCB_VIA)) and o.GetLayer()==p.B_Cu and o.GetWidth()>=500000)
                if not vddq and any(label(o)=='C2305.1' for o in allowed):
                    allowed.extend(o for o in group if isinstance(o,p.PAD) and o.GetParentFootprint().GetReference() in ('C2302','C2304','C2306','C2307','C2308'))
                if (sys_tap or rail_link) and any(label(o)=='L405.2' for o in allowed if isinstance(o,p.PAD)):
                    allowed.extend(o for o in group if not isinstance(o,(p.PAD,p.PCB_VIA)) and o.GetWidth()>=600000)
                if restore_pull and any(label(o)=='R8006.2' for o in allowed if isinstance(o,p.PAD)):
                    allowed.extend(o for o in group if not isinstance(o,(p.PAD,p.PCB_VIA)) and o.GetWidth()>=500000)
                req[name]=[points(allowed,l) for l in stack]
                if n12_supply and any(label(o)=='U2.N12' for o in allowed if isinstance(o,p.PAD)):
                    req[name]=[points([native[source['tie']]],l) for l in stack]
                if vdd1_extended and any(label(o)=='L405.2' for o in allowed):
                    bridge=native[source['bridge']]
                    assert bridge.GetWidth()==600000
                    req[name]=[points([bridge],l) for l in stack]
        if sys_tap and '--tap-frontier' in sys.argv and any(isinstance(o,p.PAD) and label(o)==sys_tap for o in gz):
            req['start'],req['end']=req['end'],req['start']
        if vddq_reverse:req['start'],req['end']=req['end'],req['start']
        if emmc_rear:
            req['layers']=[geos[p.B_Cu]]
            req['start'],req['end']=[req['end'][-1]],[req['start'][-1]]
            req['bounds']=[39500000,500000,70500000,18500000]
        result=subprocess.run(['python3',str(Path(__file__).with_name('control_board_grid.py'))],input=json.dumps(req),text=True,capture_output=True,check=True)
        solution=json.loads(result.stdout)
        if solution.get('blocked'):
            if 'frontier_nm' in solution and vdd1:
                (root/('runs/'+checkpoint_name+'-frontier.json' if sys_tap or rail_link or restore_pull else 'runs/vddq-n12-source-frontier.json' if n12_supply else 'runs/vddq-zq-source-frontier.json' if zq_supply else 'runs/lpddr-vddq-reserved-frontier.json' if vddq_first else 'runs/lpddr-vddq-load-frontier.json' if vddq_reverse else 'runs/lpddr-vddq-copper-frontier.json' if vddq_rear else 'runs/lpddr-vddq-l403-frontier.json' if vddq else 'runs/vdd1-external-source-frontier.json' if vdd1_extended else 'runs/lpddr-vdd1-l405-frontier.json')).write_text(json.dumps(solution.pop('frontier_nm'))+'\n')
            if 'frontier_nm' in solution:
                (root/('runs/emmc-vcc-current-frontier.json' if current_vcc else 'runs/emmc-rear-target-frontier.json' if emmc_rear else 'runs/emmc-staggered-frontier.json')).write_text(json.dumps(solution.pop('frontier_nm'))+'\n')
            held.append(solution);continue
        if not solution:
            if emmc_link:held.append(dict(reason='no paired-via path from reservoir to 0R',ends=[a,z]))
            continue
        if emmc_link:
            assert not emmc_rear, 'review newly-found rear route before materialization'
            length=sum(math.dist(h[1:],j[1:]) for h,j in zip(solution['path'],solution['path'][1:]))
            if length>25000000:
                held.append(dict(reason='eMMC supply route length',length_mm=length/1e6));continue
        if storage and sum(math.dist(h[1:],j[1:]) for h,j in zip(solution['path'],solution['path'][1:]))>12000000:continue
        candidate=p.LoadBoard(str(current));items=[];path=solution['path'];mates=iter(solution.get('bridges',[]))
        for (l,x,y),(k,u,v) in zip(path,path[1:]):
            if l==k:
                t=p.PCB_TRACK(candidate);t.SetLayer(stack[l]);t.SetWidth(600000 if vdd1 else 500000 if emmc_link else 200000 if sda_signal else 250000 if wifi_pullup else 500000 if storage else 200000);t.SetStart(p.VECTOR2I(x,y));t.SetEnd(p.VECTOR2I(u,v))
            else:
                assert (x,y)==(u,v)
                t=p.PCB_VIA(candidate);t.SetPosition(p.VECTOR2I(x,y));t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetWidth(600000 if storage or emmc_link or vdd1 else 450000);t.SetDrill(300000 if storage or emmc_link or vdd1 else 200000)
                if emmc_link or vdd1:
                    mate=p.VECTOR2I(*next(mates));anchor=p.VECTOR2I(x,y)
                    other=p.PCB_VIA(candidate);other.SetViaType(p.VIATYPE_THROUGH);other.SetLayerPair(p.F_Cu,p.B_Cu);other.SetPosition(mate);other.SetWidth(600000);other.SetDrill(300000);other.SetNetCode(code);candidate.Add(other);items.append(other.m_Uuid.AsString())
                    for side in (stack[l],stack[k]):
                        stub=p.PCB_TRACK(candidate);stub.SetWidth(600000 if vdd1 else 500000);stub.SetLayer(side);stub.SetStart(anchor);stub.SetEnd(mate);stub.SetNetCode(code);candidate.Add(stub);items.append(stub.m_Uuid.AsString())
            t.SetNetCode(code);candidate.Add(t);items.append(t.m_Uuid.AsString())
        folder=root/'runs'/(checkpoint_name+'-'+a+'-'+z if phy_controls or service or vdd1 or restore_mosi else 'io-group-'+a+'-'+z);folder.mkdir(exist_ok=True)
        for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(current.parent/name,folder/name)
        out=folder/current.name;p.ZONE_FILLER(candidate).Fill(candidate.Zones());p.SaveBoard(str(out),candidate)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
        delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
        if delta:continue
        saved=p.LoadBoard(str(out));saved.BuildConnectivity()
        r,n=a.split('.');anchor=saved.FindFootprintByReference(r).FindPadByNumber(n)
        expected=pad_ids(ga)|pad_ids(gz)
        saved_pad_ids={pad.m_Uuid.AsString() for fp in saved.GetFootprints() for pad in fp.Pads()}
        actual={k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(anchor)} & saved_pad_ids
        if actual!=expected:continue
        verify_preservation(b,saved);assert not screen(saved)
        current=out;records.append(dict(pair=[a,z],net=net,added=items,length_mm=sum(math.dist(h[1:],j[1:]) for h,j in zip(path,path[1:]))/1e6))
        print(net,a,z,flush=True);write();break
    else:
        held.append(dict(net=net,groups=[sorted(label(q) for q in g if isinstance(q,p.PAD)) for _,g in groups]));write();break
write();os._exit(0)
