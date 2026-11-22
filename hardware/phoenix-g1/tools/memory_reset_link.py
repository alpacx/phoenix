"""Close the LPDDR4 reset path between existing fanouts; do not alter DQ/DQS geometry."""
import hashlib,json,math,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from phy_corridor_path import geometry
from pcb_preservation import verify_preservation
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'reconciled-c1623.json').read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
orig=p.LoadBoard(str(src));net=orig.GetNetcodeFromNetname('LPDDR4_RESETN')
vias=[t for t in orig.GetTracks() if t.GetNetCode()==net and isinstance(t,p.PCB_VIA)]
assert len(vias)==2
opts=[]
for layer in (p.In2_Cu,p.In3_Cu):
    copper,pads=geometry(orig,layer,net)
    for z in orig.Zones():
        if z.GetIsRuleArea() and z.IsOnLayer(layer) and z.GetDoNotAllowTracks():
            v=z.GetBoundingBox();pads.append((v.GetLeft(),v.GetTop(),v.GetRight(),v.GetBottom()))
    obj=dict(geometry=[copper,pads],ends=[tuple(t.GetPosition()) for t in vias],width=200000)
    run=subprocess.run(['python3',str(Path(__file__).with_name('reset_link_grid.py'))],input=json.dumps(obj),text=True,capture_output=True,check=True)
    path=json.loads(run.stdout)
    if path:opts.append((sum(math.dist(a,z) for a,z in zip(path,path[1:])),layer,path))
print('paths',[(x/1e6,orig.GetLayerName(l)) for x,l,_ in opts],flush=True)
for length,layer,path in sorted(opts):
    b=p.LoadBoard(str(src));new=[]
    for a,z in zip(path,path[1:]):
        t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetNetCode(net);t.SetWidth(200000);t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z));b.Add(t);new.append(t.m_Uuid.AsString())
    folder=root/'runs/memory-reset-link';folder.mkdir(exist_ok=True)
    for f in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/f,folder/f)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    before=json.loads((src.parent/'drc.json').read_text());after=json.loads((folder/'drc.json').read_text());delta=introduced(before,after)
    if delta:print(delta,flush=True);continue
    saved=p.LoadBoard(str(out));pres=verify_preservation(orig,saved)
    def linked(b):
        b.BuildConnectivity()
        source=b.FindFootprintByReference('U1').FindPadByNumber('1B11')
        target=b.FindFootprintByReference('U2').FindPadByNumber('T11')
        return target.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(source)}
    assert linked(saved) and not linked(orig)
    cut=next(t for t in saved.GetTracks() if t.m_Uuid.AsString()==new[len(new)//2]);saved.Remove(cut)
    assert not linked(saved)
    rep=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],new_drc=delta,layer=b.GetLayerName(layer),length_mm=length/1e6,width_mm=.20,path_nm=path,cut_detected=True,preservation=pres,unconnected_items=len(after['unconnected_items']),drc_warning_count=len(after['violations']),assembly_ready=False)
    (root/'memory-reset-verified.json').write_text(json.dumps(rep,indent=2)+'\n')
    print(rep['unconnected_items'],flush=True);break
os._exit(0)
