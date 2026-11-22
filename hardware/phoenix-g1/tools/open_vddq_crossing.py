"""Create a local alternate-layer bridge for an existing expansion line across the VDDQ corridor."""
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path
import shutil
import subprocess
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make,barrel
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

stage=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda n:json.loads((stage/n).read_text())
cp=read('layout-lpddr-vdd1-source.json');gaps=read('vddq-corridor-obstacles.json')
src=stage/cp['board'];assert cp['sha256']==gaps['parent_sha256']==hashlib.sha256(src.read_bytes()).hexdigest()
original=p.LoadBoard(str(src))
folder=stage/'runs/vddq-expansion-crossing';folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
uid=lambda o:o.m_Uuid.AsString()
winner=None;cases=[]
for row in gaps['trials']:
    if len(row['hits'])!=1 or row['rule_areas']:continue
    hit,=row['hits']
    if hit['type']!='PCB_TRACK' or hit['net'] not in ('EXP_SPI_MOSI','EXP_GPIO1'):continue
    b=p.LoadBoard(str(src))
    old=next(t for t in b.GetTracks() if uid(t)==hit['id'])
    origlayer=old.GetLayer();code=old.GetNetCode();width=old.GetWidth()
    a,z=tuple(old.GetStart()),tuple(old.GetEnd())
    n=max(1,math.ceil(math.dist(a,z)/50000))
    pos=lambda i:tuple(round(x+(y-x)*i/n) for x,y in zip(a,z))
    rail=make(b,row['source_nm'],row['load_nm'],600000,b.FindNet('+1V1_LPDDR4').GetNetCode(),origlayer)
    railshape=rail.GetEffectiveShape(origlayer)
    near=[o for o in [*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())] if inflated_box(old,3000000).Intersects(o.GetBoundingBox()) and uid(o)!=uid(old)]
    obs={l:[o.GetEffectiveShape(l) for o in near if o.IsOnLayer(l) and o.GetNetCode()!=code] for l in layers}
    holes=[o.GetEffectiveHoleShape() for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    lands=[o.GetEffectiveShape(o.GetParentFootprint().GetLayer()) for o in near if isinstance(o,p.PAD)]
    rules=[zone.Outline() for zone in [*b.Zones(),*(zone for f in b.GetFootprints() for zone in f.Zones())] if zone.GetIsRuleArea() and zone.GetDoNotAllowVias()]
    v=barrel(b,a,code);blocked_indices=[];sites=[]
    for i in range(1,n):
        xy=pos(i);v.SetPosition(p.VECTOR2I(*xy));sh=v.GetEffectiveShape(p.F_Cu);h=v.GetEffectiveHoleShape()
        if sh.Collide(railshape,202000) or h.Collide(railshape,252000):
            blocked_indices.append(i);continue
        if any(sh.Collide(s,202000) or h.Collide(s,252000) for solids in obs.values() for s in solids):continue
        if any(sh.Collide(s,252000) or h.Collide(s,252000) for s in holes):continue
        if any(sh.Collide(s,52000) for s in lands) or any(sh.Collide(s,0) for s in rules):continue
        sites.append(i)
    before=[i for i in sites if blocked_indices and i<min(blocked_indices)]
    after=[i for i in sites if blocked_indices and i>max(blocked_indices)]
    rec=dict(net=hit['net'],crossing=[row['source_nm'],row['load_nm']],before=len(before),after=len(after),clear_bridges=0)
    cases.append(rec)
    if not before or not after:continue
    alt_layers=(p.B_Cu,p.In2_Cu,p.F_Cu) if origlayer==p.In3_Cu else (p.F_Cu,p.In3_Cu,p.B_Cu)
    b.Remove(old)
    for alt in alt_layers:
        for i,j in sorted(itertools.product(before,after),key=lambda ij:ij[1]-ij[0]):
            x,y=pos(i),pos(j);bridge=make(b,x,y,width,code,alt);sh=bridge.GetEffectiveShape(alt)
            if any(sh.Collide(s,202000) for s in obs[alt]) or any(sh.Collide(h,252000) for h in holes):continue
            rec['clear_bridges']+=1
            added=[make(b,a,x,width,code,origlayer),make(b,y,z,width,code,origlayer),barrel(b,x,code),barrel(b,y,code),bridge]
            for item in added:b.Add(item)
            out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
            dr=folder/'drc.json';subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],check=True,capture_output=True)
            delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads(dr.read_text()))
            if not delta:
                saved=p.LoadBoard(str(out));saved.BuildConnectivity()
                if not screen(saved):
                    guard=verify_preservation(original,saved,replaced_copper={hit['id']})
                    winner=dict(board=str(out.relative_to(stage)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),replaced=hit['id'],from_layer=row['layer'],to_layer=b.GetLayerName(alt),barrels=[uid(t) for t in added if isinstance(t,p.PCB_VIA)],length_mm=math.dist(x,y)/1e6,preservation=guard)
                    break
            for item in added:b.Remove(item)
        if winner:break
    if winner:break
(stage/'vddq-expansion-crossing.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],cases=cases,candidate=winner,assembly_ready=False),indent=2)+'\n')
print([(c['net'],c['before'],c['after']) for c in cases],bool(winner))
