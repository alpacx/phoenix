"""Join nearby grounded bypass islands in the LPDDR4 bank on the back surface."""
from functools import lru_cache
from pathlib import Path
import hashlib
import heapq
import json
import math
import os
import shutil
import subprocess
import sys

import pcbnew as p
from pcb_bounds import inflated_box

from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
bulk='--regulator-output-bulk' in sys.argv
wifi_feed='--wifi-pullup-feed' in sys.argv
controls='--short-controls' in sys.argv or wifi_feed
auxiliary='--auxiliary-banks' in sys.argv
stage='regulator-output-bulk' if bulk else 'wifi-pullup-feed' if wifi_feed else 'short-control-branches' if controls else 'aux-cap-banks' if auxiliary else 'ram-cap-bank'
meta=json.loads((root/('layout-wifi-sdio-bias.json' if wifi_feed or bulk else 'layout-aux-cap-banks.json' if controls else 'layout-ram-cap-bank.json' if auxiliary else 'layout-ground-island-barrels.json')).read_text())
src=root/meta['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
b=p.LoadBoard(str(src))
b.BuildConnectivity()
layer=p.B_Cu
width=1550000 if bulk else 250000 if wifi_feed else 200000 if controls else 500000
grid=100000
def ids(q):
    return {k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(q)}|{q.m_Uuid.AsString()}
def label(q):
    return q.GetParentFootprint().GetReference()+'.'+q.GetNumber()
gnd=ids(b.FindFootprintByReference('C511').FindPadByNumber('2'))
allpads=[q for f in b.GetFootprints() for q in f.Pads()]
rails={'+3V3_IO','+1V8_SYS','EMMC_3V3','EMMC_IO_1V8','VDD_CPU','VDD_GPU','VDD_NPU','VDD_LOGIC','VDDA_0V9','VCCA_1V8','VCCA1V8_PMU','VCCA1V8_IMAGE','+3V3_PMU','VCCIO_ACODEC','USB_AVDD_1V8','USB_AVDD_0V9'} if auxiliary else {'+1V1_LPDDR4'}
caps=[q for q in allpads if q.GetNetname() in rails and q.GetParentFootprint().GetReference().startswith('C') and q.IsOnLayer(layer) and any(s.m_Uuid.AsString() in gnd for s in q.GetParentFootprint().Pads())]
if controls:
    permitted={'PMIC_INT_N','I2C0_SCL','I2C0_SDA','RESET_N','PMIC_SLEEP','PMIC_PWRON_N','EXP_I2C_SDA','EXP_SPI_CS0_N','EXP_SPI_CS1_N','EXP_GPIO2','EXP_GPIO3','EXP_UART_RX','EXP_UART_TX','DEBUG_TX','DEBUG_RX','LCD_RESET_N','LCD_CS_N','USB_MUX_ENABLE_N','USB_ORIENTATION','ETH_RESET_GPIO_N','WIFI_REG_ON','WIFI_HOST_WAKE','THERMAL_SHUTDOWN','PHY_CFG_LDO0','PHY_CFG_LDO1','PHY_CFG_EXT','ETH_MDC','ETH_MDIO'}
    caps=[q for q in allpads if q.GetNetname() in permitted]
pairs=sorted([((a.GetPosition()-z.GetPosition()).EuclideanNorm(),a,z) for i,a in enumerate(caps) for z in caps[i+1:] if a.GetNetCode()==z.GetNetCode() and (a.GetPosition()-z.GetPosition()).EuclideanNorm()<=(9000000 if controls else 4500000)],key=lambda t:t[0])
if wifi_feed:
    pull=b.FindFootprintByReference('R2012').FindPadByNumber('2')
    rail=b.FindFootprintByReference('U25').FindPadByNumber('22')
    targets=[q for q in allpads if q.GetNetCode()==pull.GetNetCode() and q.m_Uuid.AsString() in ids(rail) and q.IsOnLayer(layer)]
    pairs=sorted([((q.GetPosition()-pull.GetPosition()).EuclideanNorm(),pull,q) for q in targets if (q.GetPosition()-pull.GetPosition()).EuclideanNorm()<12000000],key=lambda t:t[0])
if bulk:
    groups=[['L401','C431','C441','C451'],['L402','C432','C442','C452'],['L403','C433','C443'],['L1001','C1011','C1012','C1013','C1014']]
    pairs=[]
    for refs in groups:
        endpoints=[]
        for ref in refs:
            f=b.FindFootprintByReference(ref)
            if not f:continue
            key='2' if ref.startswith('L') else '1'
            q=f.FindPadByNumber(key)
            if ref.startswith('C') and not any(k.m_Uuid.AsString() in gnd for k in f.Pads()):continue
            endpoints.append(q)
        for i,q in enumerate(endpoints):
            for z in endpoints[i+1:]:
                if q.GetNetCode()!=z.GetNetCode() or q.GetParentFootprint().GetLayer()!=z.GetParentFootprint().GetLayer():continue
                dist=(q.GetPosition()-z.GetPosition()).EuclideanNorm()
                if dist<=7000000:pairs.append((dist,q,z))
    pairs.sort(key=lambda k:k[0])
def toes(q):
    center=q.GetPosition()
    return [tuple(v) for dx,dy in ((0,0),(-100000,0),(100000,0),(0,-100000),(0,100000)) if q.HitTest(v:=center+p.VECTOR2I(dx,dy))]
def path(a,z,dist):
    center=a.GetPosition()
    objs=[k for k in allpads+list(b.GetTracks()) if k.IsOnLayer(layer) and k.GetNetCode()!=a.GetNetCode() and inflated_box(k,int(dist+2000000)).Contains(center)]
    obs=[(k.GetEffectiveShape(layer),k.GetBoundingBox()) for k in objs]
    holes=[k.GetEffectiveHoleShape() for k in objs if isinstance(k,p.PCB_VIA)]
    keep=[zone.GetBoundingBox() for zone in b.Zones() if zone.IsOnLayer(layer) and zone.GetIsRuleArea() and zone.GetDoNotAllowTracks()]
    if bulk:
        endpoints={a.GetParentFootprint().GetReference(),z.GetParentFootprint().GetReference()}
        keep.extend(f.GetCourtyard(layer).BBox() for f in b.GetFootprints() if f.GetLayer()==layer and f.GetReference().startswith(('L','Y')) and f.GetReference() not in endpoints)
    t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetWidth(width)
    @lru_cache(None)
    def free(u,v):
        t.SetStart(p.VECTOR2I(*u));t.SetEnd(p.VECTOR2I(*v))
        box=inflated_box(t,202000)
        sh=t.GetEffectiveShape(layer)
        return not (any(box.Intersects(k) for k in keep) or any(box.Intersects(bb) and sh.Collide(s,202000) for s,bb in obs) or any(sh.Collide(h,250000) for h in holes))
    goals=toes(z)
    target=tuple(z.GetPosition())
    def heuristic(pt):
        return max(0,math.dist(pt,target)-100000)
    best={}
    parent={}
    queue=[]
    for toe in toes(a):
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                pt=(round(toe[0]/grid)*grid+dx*grid,round(toe[1]/grid)*grid+dy*grid)
                d=math.dist(toe,pt)
                if d>=best.get(pt,math.inf) or not free(toe,pt):continue
                best[pt]=d;parent[pt]=[toe]
                heapq.heappush(queue,(d+heuristic(pt),d,pt))
    while queue:
        _,d,pt=heapq.heappop(queue)
        if d!=best[pt] or d+heuristic(pt)>min(8000000 if bulk else 16000000 if wifi_feed else 11000000 if controls else 5000000,dist*1.6):continue
        for goal in goals:
            if math.dist(pt,goal)<160000 and free(pt,goal):
                pts=[goal,pt]
                while isinstance(parent[pt],tuple):
                    pt=parent[pt];pts.append(pt)
                pts.append(parent[pt][0]);pts.reverse()
                final=[]
                for point in pts:
                    if final and point==final[-1]:continue
                    if len(final)>=2:
                        before,last=final[-2:]
                        if (last[0]-before[0])*(point[1]-last[1])==(last[1]-before[1])*(point[0]-last[0]):
                            final[-1]=point;continue
                    final.append(point)
                return final
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)):
            nxt=(pt[0]+dx*grid,pt[1]+dy*grid)
            nd=d+grid*math.hypot(dx,dy)
            if nd>=best.get(nxt,math.inf) or not free(pt,nxt):continue
            best[nxt]=nd;parent[nxt]=pt
            heapq.heappush(queue,(nd+heuristic(nxt),nd,nxt))
    return []
records=[]
for dist,a,z in pairs:
    if z.m_Uuid.AsString() in ids(a):continue
    if controls or bulk:
        common=[l for l in (p.F_Cu,p.B_Cu) if a.IsOnLayer(l) and z.IsOnLayer(l)]
        if not common:continue
        layer=common[0]
    points=path(a,z,dist)
    if not points:continue
    for u,v in zip(points,points[1:]):
        t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetWidth(width);t.SetNetCode(a.GetNetCode());t.SetStart(p.VECTOR2I(*u));t.SetEnd(p.VECTOR2I(*v));b.Add(t)
    b.BuildConnectivity()
    assert z.m_Uuid.AsString() in ids(a)
    records.append(dict(pair=[label(a),label(z)],length_mm=sum(math.dist(u,v) for u,v in zip(points,points[1:]))/1e6))
out=src
if records:
    folder=root/'runs'/stage;folder.mkdir(exist_ok=True)
    for n in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/n,folder/n)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    assert not delta,delta
    saved=p.LoadBoard(str(out));saved.BuildConnectivity();verify_preservation(p.LoadBoard(str(src)),saved);assert not screen(saved)
    for rec in records:
        a,z=[saved.FindFootprintByReference(ref).FindPadByNumber(num) for ref,num in (q.split('.') for q in rec['pair'])]
        assert z.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(a)}
(root/(stage+'.json')).write_text(json.dumps(dict(parent_sha256=meta['sha256'],board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),width_mm=width/1e6,records=records,assembly_ready=False),indent=2)+'\n')
print(records,flush=True)
os._exit(0)
