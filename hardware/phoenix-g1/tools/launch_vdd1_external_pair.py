"""Verify a tented VDD1 distribution pair outside L405, reusing one existing barrel."""
from pathlib import Path
import hashlib
import json
import math
import shutil
import subprocess
import pcbnew as p
from pcb_power_leg import make
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced

stage=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda n:json.loads((stage/(n+'.json')).read_text())
cp=read('layout-lpddr-vdd1-bank')
sites=read('vdd1-external-bent-sites')
reuse=read('vdd1-resize-existing-source')
src=stage/cp['board']
assert cp['sha256']==sites['parent_sha256']==reuse['parent_sha256']==hashlib.sha256(src.read_bytes()).hexdigest()
oldsite,=reuse['legal']
choices=[s for s in sites['legal'] if 800000<=math.dist(s['at_nm'],oldsite['at_nm'])<=1200000]
original=p.LoadBoard(str(src))
uid=lambda o:o.m_Uuid.AsString()
folder=stage/'runs/vdd1-external-pair'
folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):
    shutil.copy2(src.parent/name,folder/name)
trials=[];winner=None
for layer in (p.In3_Cu,p.In2_Cu):
    for site in sorted(choices,key=lambda s:s['length_mm']):
        board=p.LoadBoard(str(src))
        pin=board.FindFootprintByReference('L405').FindPadByNumber('2')
        code=pin.GetNetCode()
        existing=next(v for v in board.GetTracks() if isinstance(v,p.PCB_VIA) and v.GetNetCode()==code and list(v.GetPosition())==oldsite['at_nm'])
        new=p.PCB_VIA(board);new.SetViaType(p.VIATYPE_THROUGH);new.SetLayerPair(p.F_Cu,p.B_Cu);new.SetPosition(p.VECTOR2I(*site['at_nm']));new.SetNetCode(code)
        board.Add(new)
        for via in (existing,new):
            via.SetWidth(600000);via.SetDrill(300000)
            via.SetFrontTentingMode(p.TENTING_MODE_TENTED);via.SetBackTentingMode(p.TENTING_MODE_TENTED)
        seen=set()
        for leg in (oldsite,site):
            path=[leg['anchor_nm'],leg['bend_nm'],leg['at_nm']]
            for a,z in zip(path,path[1:]):
                key=tuple(sorted([tuple(a),tuple(z)]))
                if a!=z and key not in seen:
                    board.Add(make(board,a,z,600000,code,p.F_Cu));seen.add(key)
        tie=make(board,oldsite['at_nm'],site['at_nm'],600000,code,layer);board.Add(tie)
        out=folder/src.name;p.ZONE_FILLER(board).Fill(board.Zones());p.SaveBoard(str(out),board)
        dr=folder/'drc.json'
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],check=True,capture_output=True)
        delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads(dr.read_text()))
        trials.append(dict(new_at_nm=site['at_nm'],layer=board.GetLayerName(layer),new_drc=delta))
        if delta:continue
        saved=p.LoadBoard(str(out));saved.BuildConnectivity();q=saved.FindFootprintByReference('L405').FindPadByNumber('2')
        ids={uid(o) for o in saved.GetConnectivity().GetConnectedItems(q)}
        assert {uid(existing),uid(new),uid(tie)}<=ids
        if screen(saved):continue
        guard=verify_preservation(original,saved,replaced_copper={uid(existing)})
        winner=dict(board=str(out.relative_to(stage)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),barrels=[uid(existing),uid(new)],resized=uid(existing),bridge=uid(tie),bridge_layer=board.GetLayerName(layer),source_legs=[oldsite,site],preservation=guard)
        break
    if winner:break
(stage/'vdd1-external-pair.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],choices=len(choices),candidate=winner,trials=trials,assembly_ready=False),indent=2)+'\n')
print(len(choices),len(trials),bool(winner))
