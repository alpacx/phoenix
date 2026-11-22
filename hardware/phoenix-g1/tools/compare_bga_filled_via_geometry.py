"""Inspect filled/capped launch alternatives on copies with unmodified production rules."""
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import sys

import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
emmc='--emmc-bus' in sys.argv
meta=json.loads((root/('layout-emmc-data-power.json' if emmc else 'layout-soc-tx-series.json')).read_text());src=root/meta['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
if not emmc:
    ring=json.loads((root/'bga-closed-escape-rings.json').read_text());assert ring['board_sha256']==meta['sha256']
cli='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
original=p.LoadBoard(str(src));original.BuildConnectivity()
before=json.loads((src.parent/'drc.json').read_text())
base=original.FindFootprintByReference('U1')
if emmc:
    # DAT0 already exits the memory. Rack every remaining 8-bit bus terminal at
    # its real end; there is no host RSTN in the present reset strap topology.
    pins=[('U8001',q) for q in ('A4','A5','B2','B3','B4','B5','B6','M5','M6','H5')]
    pins.extend(('U1',q) for q in ('J25','J26','H25','K27','K26','K25','H26','H27','M26','M25','L26'))
else:
    pins=[('U1',r['pin']) for r in ring['closed_singletons']]
def plane_clearance(board,at):
    result={}
    for l in (p.In1_Cu,p.In4_Cu):
        planes=[z.GetFilledPolysList(l) for z in board.Zones() if z.GetNetname()=='GND' and z.IsOnLayer(l) and z.HasFilledPolysForLayer(l)]
        rays=[]
        for i in range(16):
            c=math.cos(i*math.tau/16);s=math.sin(i*math.tau/16)
            for r in range(0,1000001,10000):
                if any(poly.Contains(at+p.VECTOR2I(round(r*c),round(r*s))) for poly in planes):break
            else:r=1010000
            rays.append(r/1e6)
        result[board.GetLayerName(l)]={'min_mm':min(rays),'max_mm':max(rays),'center_has_plane':min(rays)==0}
    return result
def flashes(path,centers):
    # KiCad 4.6 decimal mm, absolute coordinates, circular apertures used at these native pads.
    apertures={};selected=None;found={name:[] for name in centers}
    for line in path.read_text().splitlines():
        m=re.fullmatch(r'%ADD(\d+)([^,]+),([^*]+)\*%',line)
        if m:apertures[int(m[1])]=(m[2],m[3]);continue
        m=re.fullmatch(r'D(\d+)\*',line)
        if m:selected=int(m[1]);continue
        m=re.fullmatch(r'X(-?\d+)Y(-?\d+)D03\*',line)
        if m:
            xy=(int(m[1]),-int(m[2]))
            for name,center in centers.items():
                if xy==center:found[name].append(apertures.get(selected))
    return found
cases=[]
for name,diameter,drill in [('current',450000,200000),('supplier-example',250000,150000)]:
    b=p.LoadBoard(str(src));soc=b.FindFootprintByReference('U1');sites={}
    for ref,number in pins:
        comp=b.FindFootprintByReference(ref);pin=(ref+'.'+number) if emmc else number
        pad=comp.FindPadByNumber(number);at=pad.GetPosition();v=p.PCB_VIA(b);v.SetPosition(at);v.SetNetCode(pad.GetNetCode());v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetWidth(diameter);v.SetDrill(drill)
        v.SetFillingMode(p.FILLING_MODE_FILLED);v.SetCappingMode(p.CAPPING_MODE_CAPPED);v.SetFrontTentingMode(p.TENTING_MODE_TENTED);v.SetBackTentingMode(p.TENTING_MODE_TENTED);b.Add(v)
        sites[pin]=dict(center_nm=tuple(at),pitch_mm=.5,land_mm=pad.GetSize().x/1e6,nominal_mask_mm=(pad.GetSize().x+2*pad.GetSolderMaskExpansion(comp.GetLayer()))/1e6,nominal_paste_mm=(pad.GetSize().x+2*pad.GetSolderPasteMargin(comp.GetLayer()).x)/1e6,baseline_plane_radius_sample=plane_clearance(original,at))
    folder=root/'runs'/(('emmc-bus-in-pad-' if emmc else 'bga-filled-')+name);folder.mkdir(exist_ok=True)
    for fn in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/fn,folder/fn)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run([cli,'pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    saved=p.LoadBoard(str(out));verify_preservation(original,saved)
    delta=introduced(before,json.loads((folder/'drc.json').read_text()))
    for pin,data in sites.items():
        ref,number=pin.split('.') if emmc else ('U1',pin)
        pad=saved.FindFootprintByReference(ref).FindPadByNumber(number)
        data['trial_plane_radius_sample']=plane_clearance(saved,pad.GetPosition())
    with tempfile.TemporaryDirectory() as raw:
        dest=Path(raw)
        subprocess.run([cli,'pcb','export','gerbers','--no-protel-ext','--precision','6','-l','F.Cu,F.Mask,F.Paste,B.Cu,B.Mask,B.Paste' if emmc else 'F.Cu,F.Mask,F.Paste','-o',raw,str(out)],check=True,capture_output=True)
        plotted={f.name:flashes(f,{k:v['center_nm'] for k,v in sites.items()}) for f in dest.glob('*.gbr')}
        if emmc:
            assert len(plotted)==6
            for file,report in plotted.items():
                side='U8001.' if '-B_' in file else 'U1.'
                assert all(v for k,v in report.items() if k.startswith(side)),file
        else:assert len(plotted)==3 and all(v for report in plotted.values() for v in report.values()),plotted
    cases.append(dict(name=name,board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),drill_mm=drill/1e6,copper_land_mm=diameter/1e6,annulus_mm=(diameter-drill)/2e6,via_projected_outside_original_land_mm=(diameter-250000)/2e6,aspect_ratio=round(saved.GetDesignSettings().GetBoardThickness()/drill,2),pins=sites,gerber_flash_apertures=plotted,regressions=dict(Counter(r['type'] for r in delta))))
report=dict(source_sha256=meta['sha256'],layer_count=original.GetCopperLayerCount(),thickness_mm=original.GetDesignSettings().GetBoardThickness()/1e6,cases=cases,sources=['https://jlcpcb.com/help/article/bga-design-guidelines---pcb-layout-recommendations-for-bga-packages','https://jlcpcb.com/help/article/via-in-pad-pofv-guide'],notes=['JLCPCB shows a 0.25/0.15 mm filled example for 0.5 mm pitch and separately advises at least 0.35 mm land where possible. Applicability to the actual 1.6 mm six-layer stack, drill registration, retained annulus and cost are unconfirmed. Standard 6-layer POFV alone does not confirm this geometry.','Plane radii are sampled every 0.01 mm in 16 directions; 1.01 means no GND encountered within 1 mm.','No project design rule was changed. No trial is adopted. No DFM approval, electrical/thermal simulation, or physical sample.'],adopted=False)
(root/('emmc-bus-in-pad-process.json' if emmc else 'bga-filled-via-process.json')).write_text(json.dumps(report,indent=2)+'\n')
print([(r['name'],r['regressions']) for r in cases],flush=True);os._exit(0)
