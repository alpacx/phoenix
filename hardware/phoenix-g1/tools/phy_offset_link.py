"""Move the wide trace ends within the link pads, retaining the specified width."""
import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import pcbnew as p

from drc_regression import introduced
from pcb_preservation import verify_preservation

study = Path(__file__).resolve().parents[1] / 'migration-rk3562/experiments/phy-power-parallel'
parent = study / 'runs/input-ground-local-002'
name = 'phy-joint.kicad_pcb'
baseline = p.LoadBoard(str(parent / name))
before = json.loads((parent / 'drc.json').read_text())
results = []
held = []
import sys
reroute = "--reroute" in sys.argv
for index in ((0,) if "--array" in sys.argv else (0,1)):
    source = study / 'runs' / f'phy-directed-link-{index}'
    board = p.LoadBoard(str(source / name))
    link = board.FindFootprintByReference('R530')
    inp, out = (link.FindPadByNumber(n) for n in ('1','2'))
    feed, = [t for t in board.GetTracks() if t.GetLayer()==p.F_Cu and t.GetEnd()==inp.GetPosition() and t.GetWidth()==p.FromMM(1.05)]
    origin = inp.GetPosition()
    offset = p.VECTOR2I(p.FromMM(.24), 0)
    assert inp.HitTest(origin-offset) and out.HitTest(out.GetPosition()+offset)
    feed.SetEnd(origin-offset)
    replaced = []
    if reroute:
        def point(x,y):
            return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
        for old in list(board.GetTracks()):
            if old.GetClass()!='PCB_TRACK' or old.GetLayer()!=p.F_Cu or old.GetNetCode()!=inp.GetNetCode() or old==feed:
                continue
            if all(51.84<=p.ToMM(pos.x)<=52.51 and 25.34<=p.ToMM(pos.y)<=27.36 for pos in (old.GetStart(),old.GetEnd())):
                replaced.append(old.m_Uuid.AsString())
                board.Remove(old)
                held.append(old)
        assert replaced
        route=[point(51.85,27.35),point(51.85,25.48),point(51.98,25.35)]
        for a,z in zip(route,route[1:]):
            t=p.PCB_TRACK(board)
            t.SetStart(a)
            t.SetEnd(z)
            t.SetWidth(p.FromMM(.2))
            t.SetNetCode(inp.GetNetCode())
            t.SetLayer(p.F_Cu)
            board.Add(t)
    shift_ground = "--ground" in sys.argv
    if shift_ground:
        original_via=point(54.5,26.45)
        reuse=sys.argv[-1]=="reuse"
        destination=point(53.45,24.3) if reuse else point(54.5,float(sys.argv[-1]))
        for t in list(board.GetTracks()):
            if t.IsOnLayer(p.F_Cu) and t.GetNetname()=="GND" and t.GetEnd()==original_via:
                replaced.append(t.m_Uuid.AsString())
                if isinstance(t,p.PCB_VIA):
                    if reuse:
                        board.Remove(t)
                        held.append(t)
                    else:
                        t.SetPosition(destination)
                else:
                    t.SetEnd(destination)
        assert any(isinstance(t,p.PCB_VIA) and t.GetPosition()==destination for t in board.GetTracks())
    suffix=f"{index}-{int(reroute)}" + ("-ground-"+sys.argv[-1] if shift_ground else "")
    start = out.GetPosition()+offset
    track = p.PCB_TRACK(board)
    track.SetStart(start)
    track.SetWidth(p.FromMM(1.05))
    track.SetLayer(p.F_Cu)
    track.SetNetCode(out.GetNetCode())
    objects = list(board.GetTracks()) + [q for f in board.GetFootprints() for q in f.Pads()]
    obstacles = [o.GetEffectiveShape(p.F_Cu) for o in objects if o.IsOnLayer(p.F_Cu) and o.GetNetname()!=out.GetNetname() and o.GetBoundingBox().Inflate(p.FromMM(7)).Contains(start)]
    choices = []
    for angle in range(-90,91,5):
        rad = math.radians(angle)
        for length in (5,4,3,2,1.5,1,.75,.5):
            end = start+p.VECTOR2I(p.FromMM(length*math.cos(rad)),p.FromMM(length*math.sin(rad)))
            track.SetEnd(end)
            if all(not track.GetEffectiveShape(p.F_Cu).Collide(shape,p.FromMM(.2)) for shape in obstacles):
                choices.append((length,angle,end))
                break
    report = dict(input_variant=index, valid_directions=len(choices))
    if choices or reroute:
        length,angle,end = max(choices,key=lambda row:row[0]) if choices else (0,0,start)
        if "--array" in sys.argv:
            end=point(55.11,27.05)
            for vx,vy in [(54.61,26.675),(55.11,27.05)]:
                via=p.PCB_VIA(board)
                via.SetLayerPair(p.F_Cu,p.B_Cu)
                via.SetViaType(p.VIATYPE_THROUGH)
                via.SetWidth(p.FromMM(.6))
                via.SetDrill(p.FromMM(.3))
                via.SetPosition(point(vx,vy))
                via.SetNetCode(out.GetNetCode())
                board.Add(via)
            suffix+="-array"
            length=math.dist(tuple(start),tuple(end))/1e6
            angle=math.degrees(math.atan2(end.y-start.y,end.x-start.x))
        track.SetEnd(end)
        if choices:
            board.Add(track)
        folder = study/'runs'/f'phy-offset-link-{suffix}'
        folder.mkdir(exist_ok=True)
        for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):
            shutil.copy2(parent/file,folder/file)
        p.ZONE_FILLER(board).Fill(board.Zones())
        p.SaveBoard(str(folder/name),board)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(folder/name)],check=True,capture_output=True)
        saved=p.LoadBoard(str(folder/name))
        report.update(length_mm=length,angle=angle,end_mm=[p.ToMM(i) for i in end],preservation=verify_preservation(baseline,saved,replaced_copper=replaced),new_drc=introduced(before,json.loads((folder/'drc.json').read_text())))
    results.append(report)
(study/('r530-output-array.json' if '--array' in sys.argv else ('r530-shift-ground-'+sys.argv[-1]+'.json') if shift_ground else 'r530-corridor-offset.json' if reroute else 'r530-offset-link.json')).write_text(json.dumps(results,indent=2)+'\n')
print(results,flush=True)
os._exit(0)
