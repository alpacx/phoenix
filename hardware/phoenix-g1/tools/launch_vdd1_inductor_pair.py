"""Try a filled and capped pair inside L405's output land with an inner 0.6 mm bridge."""
import hashlib
import itertools
import json
import math
from pathlib import Path
import shutil
import subprocess
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make
from pcb_preservation import verify_preservation
from drc_regression import introduced

stage=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda name:json.loads((stage/name).read_text())
cp=read('layout-lpddr-vdd1-bank.json')
search=read('vdd1-l405-via-obstacles.json')
src=stage/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==search['parent_sha256']==cp['sha256']
b=p.LoadBoard(str(src))
q=b.FindFootprintByReference('L405').FindPadByNumber('2')
padshape=q.GetEffectiveShape(p.F_Cu)
sites=next(row['sites_nm'] for row in search['low_conflict_sites'] if row['blockers']==['L405.2'])
# Circle polygon inscribed approximation is avoided by testing copper-land erosion directly.
ps=p.SHAPE_POLY_SET()
q.TransformShapeToPolygon(ps,p.F_Cu,0,300,p.ERROR_INSIDE)
ps.Deflate(402000,p.CORNER_STRATEGY_CHAMFER_ALL_CORNERS,1000)
sites=[tuple(pt) for pt in sites if ps.Contains(p.VECTOR2I(*pt))]
uid=lambda o:o.m_Uuid.AsString()
original=p.LoadBoard(str(src))
folder=stage/'runs/vdd1-l405-plugged-pair';folder.mkdir(exist_ok=True)
for ext in ('phy-joint.kicad_dru','phy-joint.kicad_pro','fp-lib-table'):
    shutil.copy2(src.parent/ext,folder/ext)
pairs=sorted((a,z) for a,z in itertools.combinations(sites,2) if 800000<=math.dist(a,z)<=1200000)
tested=[];winner=None
for layer in (p.In3_Cu,p.In2_Cu):
    solids=[o.GetEffectiveShape(layer) for o in [*b.GetTracks(),*(pad for f in b.GetFootprints() for pad in f.Pads())] if o.IsOnLayer(layer) and o.GetNetCode()!=q.GetNetCode() and inflated_box(o,3000000).Contains(q.GetPosition())]
    for a,z in sorted(pairs,key=lambda pair:math.dist(*pair)):
        tie=make(b,a,z,600000,q.GetNetCode(),layer)
        if any(tie.GetEffectiveShape(layer).Collide(s,202000) for s in solids):continue
        b.Add(tie);vs=[]
        for xy in (a,z):
            v=p.PCB_VIA(b);v.SetPosition(p.VECTOR2I(*xy));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(q.GetNetCode());v.SetWidth(600000);v.SetDrill(300000)
            v.SetCappingMode(p.CAPPING_MODE_CAPPED);v.SetFillingMode(p.FILLING_MODE_FILLED);b.Add(v);vs.append(v)
        out=folder/src.name
        p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        dr=folder/'drc.json';subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],capture_output=True,check=True)
        delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads(dr.read_text()));tested.append(dict(a=a,z=z,layer=b.GetLayerName(layer),new_drc=delta))
        if not delta:
            saved=p.LoadBoard(str(out));saved.BuildConnectivity();pin=saved.FindFootprintByReference('L405').FindPadByNumber('2')
            ids={uid(o) for o in saved.GetConnectivity().GetConnectedItems(pin)}
            assert all(uid(v) in ids for v in [tie,*vs])
            winner=dict(board=str(out.relative_to(stage)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),vias=[uid(v) for v in vs],bridge=uid(tie),layer=b.GetLayerName(layer),ends_nm=[a,z],preservation=verify_preservation(original,saved))
            break
        for o in [tie,*vs]:b.Remove(o)
    if winner:break
(stage/'vdd1-l405-plugged-pair.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],copper_land_setback_min_mm=.10,legal_contained_sites=len(sites),candidate_pairs=len(pairs),trials=tested,candidate=winner,release_constraints='Class VII filled and copper capped barrels; qualified component land/data and PCBA price pending. The inner bridge alone does not connect the load.',assembly_ready=False),indent=2)+'\n')
print(len(sites),len(pairs),bool(winner))
