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
storage='--storage-rail' in sys.argv
full='--full-feed' in sys.argv
toe='--pad-toe' in sys.argv or full or storage
phy_controls=toe or '--phy-management' in sys.argv
checkpoint_name='storage-rail-groups' if storage else 'control-full-feed' if full else 'management-pad-toe' if toe else 'phy-management' if phy_controls else 'control-groups'
parent_name='emmc-pullup-supply' if storage else 'layout-phy-full-feed' if full else 'ground-package-local' if toe else 'layout-regulator-joint' if phy_controls else 'emmc-ball-cap'
source=json.loads((root/(parent_name+'.json')).read_text());current=root/source['board']
assert hashlib.sha256(current.read_bytes()).hexdigest()==source['sha256']
stack=[p.F_Cu,p.In3_Cu,p.In2_Cu,p.B_Cu]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
nets=['PMIC_INT_N','I2C0_SCL','I2C0_SDA','RESET_N','PMIC_SLEEP','PMIC_PWRON_N',
      'EXP_I2C_SDA','EXP_SPI_CS0_N','EXP_SPI_CS1_N','EXP_GPIO2','EXP_GPIO3','EXP_UART_RX','EXP_UART_TX',
      'DEBUG_TX','DEBUG_RX','LCD_RESET_N','LCD_CS_N','USB_MUX_ENABLE_N','USB_ORIENTATION',
      'ETH_RESET_GPIO_N','WIFI_REG_ON','WIFI_HOST_WAKE','THERMAL_SHUTDOWN','RECOVERY_ADC']
if phy_controls and not full:
    nets=['PHY_CFG_LDO0','PHY_CFG_LDO1','PHY_CFG_EXT','ETH_MDC','ETH_MDIO','SOC_VBUS_DET']
if storage:nets=['EMMC_IO_1V8','EMMC_3V3']
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
    if len(groups)<2:break
    geos={}
    for l in layers:
        tracks,boxes=geometry(b,l,code,oval_caps=True);polygons=[]
        for zone in b.Zones():
            if zone.GetIsRuleArea() and zone.IsOnLayer(l) and (zone.GetDoNotAllowTracks() or zone.GetDoNotAllowVias()):
                for i in range(zone.Outline().OutlineCount()):
                    o=zone.Outline().Outline(i);polygons.append([tuple(o.CPoint(j)) for j in range(o.PointCount())])
        geos[l]=[tracks,boxes,polygons]
    holes=[[tuple(t.GetPosition()),tuple(t.GetPosition()),t.GetDrillValue()+400000] for t in b.GetTracks() if isinstance(t,p.PCB_VIA)]
    boxes=[q.GetBoundingBox() for q in pads]
    req=dict(layers=[geos[l] for l in stack],through=list(geos.values()),via_keepouts=[holes,[(v.GetLeft(),v.GetTop(),v.GetRight(),v.GetBottom()) for v in boxes]],bounds=[500000,500000,89500000,39500000],grid_nm=100000 if toe else 200000)
    if storage:req.update(width_nm=500000,via_nm=600000,bounds=[27000000,500000,52000000,23000000])
    order=sorted(itertools.combinations(groups,2),key=lambda pair:math.dist(tuple(pair[0][0].GetPosition()),tuple(pair[1][0].GetPosition())))
    for (qa,ga),(qz,gz) in order:
        a=label(qa);z=label(qz)
        req.update(start=[points(ga,l) for l in stack],end=[points(gz,l) for l in stack])
        result=subprocess.run(['python3',str(Path(__file__).with_name('control_board_grid.py'))],input=json.dumps(req),text=True,capture_output=True,check=True)
        solution=json.loads(result.stdout)
        if not solution:continue
        if storage and sum(math.dist(h[1:],j[1:]) for h,j in zip(solution['path'],solution['path'][1:]))>12000000:continue
        candidate=p.LoadBoard(str(current));items=[];path=solution['path']
        for (l,x,y),(k,u,v) in zip(path,path[1:]):
            if l==k:
                t=p.PCB_TRACK(candidate);t.SetLayer(stack[l]);t.SetWidth(500000 if storage else 200000);t.SetStart(p.VECTOR2I(x,y));t.SetEnd(p.VECTOR2I(u,v))
            else:
                assert (x,y)==(u,v)
                t=p.PCB_VIA(candidate);t.SetPosition(p.VECTOR2I(x,y));t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetWidth(600000 if storage else 450000);t.SetDrill(300000 if storage else 200000)
            t.SetNetCode(code);candidate.Add(t);items.append(t.m_Uuid.AsString())
        folder=root/'runs'/(checkpoint_name+'-'+a+'-'+z if phy_controls else 'io-group-'+a+'-'+z);folder.mkdir(exist_ok=True)
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
