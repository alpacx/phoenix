"""Route nearby low-speed pad pairs on a common surface using actual pad outlines."""
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pcbnew as p
from pcb_bounds import inflated_box

from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_preservation import verify_preservation

root = Path(__file__).resolve().parents[1] / 'migration-rk3562/experiments/phy-power-parallel'
plane_mode='--island-returns' in sys.argv
supply_mode='--supply-islands' in sys.argv
meta = json.loads((root / ('layout-supply-islands.json' if plane_mode else 'layout-ground-islands.json' if supply_mode else 'layout-bank-feeds.json')).read_text())
src = root / meta['board']
assert hashlib.sha256(src.read_bytes()).hexdigest() == meta['sha256']
b = p.LoadBoard(str(src))
b.BuildConnectivity()
pads = [q for f in b.GetFootprints() for q in f.Pads()]
controls = {'PMIC_INT_N','I2C0_SCL','I2C0_SDA','RESET_N','PMIC_SLEEP','PMIC_PWRON_N','EXP_I2C_SDA','EXP_SPI_CS0_N','EXP_SPI_CS1_N','EXP_GPIO2','EXP_GPIO3','EXP_UART_RX','EXP_UART_TX','DEBUG_TX','DEBUG_RX','LCD_RESET_N','LCD_CS_N','USB_MUX_ENABLE_N','USB_ORIENTATION','ETH_RESET_GPIO_N','WIFI_REG_ON','WIFI_HOST_WAKE','THERMAL_SHUTDOWN','PHY_CFG_LDO0','PHY_CFG_LDO1','PHY_CFG_EXT'}

def label(q):
    return q.GetParentFootprint().GetReference()+'.'+q.GetNumber()

def toes(q):
    center=q.GetPosition()
    box=q.GetBoundingBox()
    return [v for v in (center, *(center+p.VECTOR2I(round(x*box.GetWidth()*.40), round(y*box.GetHeight()*.40)) for x,y in ((1,0),(-1,0),(0,1),(0,-1)))) if q.HitTest(v)]

def connected(a,z):
    return z.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(a)}

def branch(a,z,layer):
    obstacles = [k for k in pads+list(b.GetTracks()) if k.IsOnLayer(layer) and k.GetNetCode()!=a.GetNetCode() and inflated_box(k,9000000).Contains(a.GetPosition())]
    shapes = [k.GetEffectiveShape(layer) for k in obstacles]
    for u in toes(a):
        for v in toes(z):
            dx,dy=v-u
            d=min(abs(dx),abs(dy))
            delta=p.VECTOR2I(int(math.copysign(d,dx)), int(math.copysign(d,dy)))
            for c in (u+delta,v-delta):
                trace=[]
                for i,j in ((u,c),(c,v)):
                    if i==j:continue
                    t=p.PCB_TRACK(b)
                    t.SetWidth(500000 if ground_mode or supply_mode else 200000)
                    t.SetNetCode(a.GetNetCode())
                    t.SetLayer(layer)
                    t.SetStart(i)
                    t.SetEnd(j)
                    if any(t.GetEffectiveShape(layer).Collide(s,202000) for s in shapes):break
                    trace.append(t)
                else:
                    if trace:return trace
    return []

ground_mode='--ground-islands' in sys.argv or plane_mode
if ground_mode:
    controls={'GND'}
if supply_mode:
    controls={'+1V1_LPDDR4','+1V8_SYS','EMMC_IO_1V8','EMMC_3V3','+3V3_IO','VDD_CPU','VDD_GPU','VDD_LOGIC','VDD_NPU','VCCA_1V8','VCCA1V8_PMU','VDDA0V9_PMU','VDDA_0V9','USB_AVDD_0V9','USB_AVDD_1V8','VDDA0V9_IMAGE','+3V3_PMU','VCCIO_SD','VCCA1V8_IMAGE','+3V3_SD','VCCIO_ACODEC'}
stage='island-returns' if plane_mode else 'supply-short-islands' if supply_mode else 'ground-short-islands' if ground_mode else 'control-surface'
anchor=b.FindFootprintByReference('C511').FindPadByNumber('2')
def ground_members():
    return {i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(anchor)}
members=ground_members()
records=[]
for i,a in enumerate(pads):
    if a.GetNetname() not in controls:continue
    for z in pads[i+1:]:
        if plane_mode and ((a.GetPosition()-z.GetPosition()).EuclideanNorm()>2800000 or ((a.m_Uuid.AsString() in members)==(z.m_Uuid.AsString() in members))):continue
        if (ground_mode or supply_mode) and not plane_mode and (a.GetParentFootprint().GetReference()!=z.GetParentFootprint().GetReference() or (a.GetPosition()-z.GetPosition()).EuclideanNorm()>1400000):continue
        if z.GetNetCode()!=a.GetNetCode() or (a.GetPosition()-z.GetPosition()).EuclideanNorm()>8000000 or connected(a,z):continue
        for layer in (p.F_Cu,p.B_Cu):
            if a.IsOnLayer(layer) and z.IsOnLayer(layer):
                tracks=branch(a,z,layer)
                if tracks:
                    for t in tracks:b.Add(t)
                    b.BuildConnectivity()
                    assert connected(a,z)
                    if plane_mode:members=ground_members()
                    records.append(dict(pair=[label(a),label(z)],net=a.GetNetname(),length_mm=sum(t.GetLength() for t in tracks)/1e6))
                    break
out=src
if records:
    folder=root/'runs'/stage
    folder.mkdir(exist_ok=True)
    for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):
        shutil.copy2(src.parent/name,folder/name)
    out=folder/src.name
    p.ZONE_FILLER(b).Fill(b.Zones())
    p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    assert not delta,delta
    b=p.LoadBoard(str(out))
    b.BuildConnectivity()
    verify_preservation(p.LoadBoard(str(src)),b)
    assert not screen(b)
    for row in records:
        a,z=[b.FindFootprintByReference(ref).FindPadByNumber(num) for ref,num in (s.split('.') for s in row['pair'])]
        assert connected(a,z)
(root/(stage+'.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=meta['sha256'],records=records,assembly_ready=False),indent=2)+'\n')
print(records,flush=True)
os._exit(0)
