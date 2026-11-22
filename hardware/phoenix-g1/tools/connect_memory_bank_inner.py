"""Connect the AB4 escape barrels to the populated memory bank over a signal-layer power branch."""
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_bounds import inflated_box
from pcb_power_leg import route_leg, make
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda name:json.loads((root/(name+'.json')).read_text())
entry=read('layout-memory-ab4-bypass');src=root/entry['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==entry['sha256']
original=p.LoadBoard(str(src))
original.BuildConnectivity()
anchor=original.FindFootprintByReference('C1666').FindPadByNumber('1')
net=anchor.GetNetname()
source_group={o.m_Uuid.AsString() for o in original.GetConnectivity().GetConnectedItems(anchor)}
pair=[tuple(pt) for pt in read('memory-ab4-bypass-placement')['candidate']['via_pair_nm']]
mid=tuple(round((a+b)/2) for a,b in zip(*pair))
spacing=math.dist(*pair)
tie_ends=[tuple(round(a+75000*(b-a)/spacing) for a,b in zip(foot,other)) for foot,other in (pair,pair[::-1])]
assert all(math.dist(foot,end)<100000 for foot,end in zip(pair,tie_ends))
taps=set()
for obj in [*original.GetTracks(),*(q for f in original.GetFootprints() for q in f.Pads())]:
    if obj.m_Uuid.AsString() not in source_group or not obj.IsOnLayer(p.B_Cu):continue
    if isinstance(obj,p.PAD):
        taps.add(tuple(obj.GetPosition()))
    elif isinstance(obj,p.PCB_TRACK) and not isinstance(obj,p.PCB_VIA) and obj.GetWidth()>=500000:
        count=max(1,math.ceil(obj.GetLength()/400000))
        taps.update(tuple(round(x+(y-x)*k/count) for x,y in zip(obj.GetStart(),obj.GetEnd())) for k in range(count+1))
samples=[]
for pt in sorted(taps,key=lambda pt:math.dist(mid,pt)):
    if math.dist(mid,pt)<=8500000 and all(math.dist(a,pt)>=650000 for a in samples):
        samples.append(pt)
folder=root/'runs/memory-ab4-bank-rail';folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):
    shutil.copy2(src.parent/name,folder/name)
bend_window='--bend-window' in sys.argv
if bend_window:
    previous=read('memory-ab4-bank-inner')
    assert previous['parent_sha256']==entry['sha256']
    ranked=sorted((row for row in previous['tested'] if row.get('source_reached') and row.get('sink_reached')),
                  key=lambda row:(-min(row['source_reached'],row['sink_reached']),math.dist(mid,row['at_nm'])))
    selected=[]
    for row in ranked:
        at=tuple(row['at_nm'])
        if all(math.dist(at,x)>=2000000 for x in selected):selected.append(at)
        if len(selected)==3:break
    samples=selected
outcome=None;tested=[]
for layer in (p.In2_Cu,p.In3_Cu):
    tie=make(original,*tie_ends,600000,anchor.GetNetCode(),layer)
    sh=tie.GetEffectiveShape(layer);bb=inflated_box(tie,350000)
    allitems=[*original.GetTracks(),*(q for f in original.GetFootprints() for q in f.Pads())]
    hits=[o.GetNetname() for o in allitems if o.GetNetCode()!=anchor.GetNetCode() and o.IsOnLayer(layer)
          and bb.Intersects(o.GetBoundingBox()) and (sh.Collide(o.GetEffectiveShape(layer),202000) or
              (isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x) and sh.Collide(o.GetEffectiveHoleShape(),252000))]
    if hits:
        tested.append(dict(layer=original.GetLayerName(layer),tie_blockers=hits));continue
    for at in samples:
        b=p.LoadBoard(str(src))
        b.Add(make(b,*tie_ends,600000,b.FindNet(net).GetNetCode(),layer))
        rec=route_leg(b,net,at,p.B_Cu,mid,layer,500000,10.0,shifted=bend_window,allow_supply_bends=bend_window)
        stats={k:val for k,val in rec.items() if k in ('connected','legal_sites','source_reached','sink_reached','both_faces_reached')}
        tested.append(dict(at_nm=at,layer=b.GetLayerName(layer),**stats))
        if not rec['connected']:continue
        out=folder/src.name
        p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
        drc=lambda path:json.loads((path/'drc.json').read_text())
        diff=introduced(drc(src.parent),drc(folder))
        if diff:
            tested[-1]['new_drc']=diff;continue
        saved=p.LoadBoard(str(out))
        if screen(saved):continue
        pres=verify_preservation(original,saved)
        items={x.m_Uuid.AsString() for x in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('C1666').FindPadByNumber('1'))}
        assert all(saved.FindFootprintByReference(ref).FindPadByNumber(number).m_Uuid.AsString() in items for ref,number in [('U2','AB4'),('C1674','1')])
        outcome=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),layer=b.GetLayerName(layer),
                     paths=rec,target_barrel_centres_nm=pair,new_drc=diff,preservation=pres)
        break
    if outcome:break
(root/('memory-ab4-bank-bent.json' if bend_window else 'memory-ab4-bank-inner.json')).write_text(json.dumps(dict(parent_sha256=entry['sha256'],sample_count=len(samples),
        tested=tested,candidate=outcome,assembly_ready=False),indent=2)+'\n')
print(len(samples),len(tested),bool(outcome),flush=True)
