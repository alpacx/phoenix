"""Attach grounded, fixed bypass capacitors to physically existing supply banks with short wide copper."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

import pcbnew as pcb
import native_front_splice as splice
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'layout-usb-direction-complete.json').read_text())
current=root/base['board']
digest=lambda file:hashlib.sha256(file.read_bytes()).hexdigest()
assert digest(current)==base['sha256']
uid=lambda o:o.m_Uuid.AsString()
def pad(board,ref,number):
    return board.FindFootprintByReference(ref).FindPadByNumber(number)
def ids(board,item):
    return {uid(o) for o in board.GetConnectivity().GetConnectedItems(item)}
def taps(board,group,side,origin):
    out=set()
    for o in [*list(board.GetTracks()),*(q for f in board.GetFootprints() for q in f.Pads())]:
        if uid(o) not in group or not o.IsOnLayer(side):continue
        if isinstance(o,pcb.PAD):
            if min(o.GetSize().x,o.GetSize().y)<500000:continue
            points=[tuple(o.GetPosition())]
        elif isinstance(o,pcb.PCB_VIA):
            # Existing paired or broad copper is preferred; single barrels do not qualify as a wide branch origin.
            continue
        elif o.GetWidth()>=500000:
            a,z=tuple(o.GetStart()),tuple(o.GetEnd());dx,dy=z[0]-a[0],z[1]-a[1]
            f=max(0,min(1,((origin[0]-a[0])*dx+(origin[1]-a[1])*dy)/max(1,dx**2+dy**2)))
            points=[a,z,(round(a[0]+f*dx),round(a[1]+f*dy))]
        else:continue
        out.update(pt for pt in points if math.dist(origin,pt)<=2000000)
    chosen=[]
    for xy in sorted(out,key=lambda v:math.dist(origin,v)):
        if all(math.dist(xy,other)>250000 for other in chosen):chosen.append(xy)
    return chosen

seed=pcb.LoadBoard(str(current));seed.BuildConnectivity()
profiles=[('VDD_CPU','L1001','2'),('+1V1_LPDDR4','C1666','1'),('EMMC_3V3','C8007','1'),('EMMC_IO_1V8','C8002','1')]
records=[];held=[];owners=[seed]
for net,reference,num in profiles:
    anchor=pad(seed,reference,num)
    assert anchor.GetNetname()==net
    refs=[f.GetReference() for f in seed.GetFootprints() if f.GetReference().startswith('C') and f.FindPadByNumber('1') and f.FindPadByNumber('1').GetNetname()==net and f.FindPadByNumber('2') and f.FindPadByNumber('2').GetNetname()=='GND']
    pending=set(refs)
    while pending:
        b=pcb.LoadBoard(str(current));owners.append(b);b.BuildConnectivity()
        rail=ids(b,pad(b,reference,num));ground=ids(b,pad(b,'U4','69'))
        connections=[]
        for ref in sorted(pending):
            target=pad(b,ref,'1')
            if uid(target) in rail or uid(pad(b,ref,'2')) not in ground:continue
            splice.side=target.GetParentFootprint().GetLayer()
            pt=tuple(target.GetPosition())
            for xy in taps(b,rail,splice.side,pt):
                route,info=splice.recover(b,[(pt,xy,500000,target.GetNetCode())],net,None,True,True,False,202000)
                if route and len(route)>=2 and info['length_mm']<=2.0:
                    connections.append((info['length_mm'],ref,splice.side,route))
        if not connections:break
        length,ref,layer,route=min(connections,key=lambda q:q[:2])
        pending.remove(ref)
        target=pad(b,ref,'1');splice.side=layer
        for x,y in zip(route,route[1:]):b.Add(splice.wire(b,x,y,target.GetNetCode(),500000))
        folder=root/'runs'/('grounded-bypass-bank-'+ref);folder.mkdir(exist_ok=True)
        for cfg in ('phy-joint.kicad_dru','phy-joint.kicad_pro','fp-lib-table'):shutil.copy2(current.parent/cfg,folder/cfg)
        out=folder/current.name;pcb.ZONE_FILLER(b).Fill(b.Zones());pcb.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
        delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
        if delta:
            held.append(dict(ref=ref,new_drc=delta));continue
        original=pcb.LoadBoard(str(current));saved=pcb.LoadBoard(str(out));owners.extend([original,saved])
        guard=verify_preservation(original,saved)
        assert uid(pad(saved,ref,'1')) in ids(saved,pad(saved,reference,num)) and uid(pad(saved,ref,'2')) in ids(saved,pad(saved,'U4','69')) and not screen(saved)
        records.append(dict(ref=ref,rail=net,pair=[ref+'.1',reference+'.'+num],ground_pair=[ref+'.2','U4.69'],width_mm=.5,length_mm=length,existing_groups=guard['existing_connected_pad_groups_preserved']))
        current=out;print(net,ref,round(length,3),flush=True)
report=dict(parent_sha256=base['sha256'],board=str(current.relative_to(root)),sha256=digest(current),records=records,held=held,assembly_ready=False)
(root/'grounded-bypass-bank-links.json').write_text(json.dumps(report,indent=2)+'\n')
print('added',len(records),flush=True);os._exit(0)
