"""Try full-width 1V0 branches to the selected local bypass."""
import json,os,subprocess,shutil,sys,math
from pathlib import Path
import pcbnew as p
from phy_corridor_path import geometry
from pcb_preservation import verify_preservation
from drc_regression import introduced

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
name='phy-joint.kicad_pcb'
wide='--wide' in sys.argv
source=root/('runs/c522-wide-bypass' if wide else 'runs/c522-local-bypass')
orig=p.LoadBoard(str(source/name))
net=orig.GetNetcodeFromNetname('+1V0_PHY')
def pt(x):return p.VECTOR2I(*(p.FromMM(v) for v in x))
def xy(x):return tuple(p.ToMM(v) for v in x)
options=[]
for layer in (p.B_Cu,p.In3_Cu):
    obs,pads=geometry(orig,layer,net)
    ends=[(59.94,32.06)] if layer==p.In3_Cu else [(59.97,32.5),(59.94,32.06)]
    if wide and layer==p.B_Cu:ends=[json.loads((root/"c522-wide-bypass.json").read_text())["site"]["wide_tip"]]
    starts=set()
    for t in orig.GetTracks():
        if t.GetNetCode()!=net or not t.IsOnLayer(layer):continue
        if not isinstance(t,p.PCB_VIA) and t.GetWidth()<1550000:continue
        for a in (t.GetStart(),t.GetEnd()):
            pos=xy(a)
            if 2<math.dist(pos,ends[0])<14:starts.add(pos)
    for end in ends:
        for start in sorted(starts,key=lambda a:math.dist(a,end))[:16]:
            args=[tuple(pt(start)),tuple(pt(end)),obs,pads,976000]
            run=subprocess.run(['/usr/bin/env','python3',str(Path(__file__).with_name('phy_corridor_grid.py'))],input=json.dumps(args),capture_output=True,text=True,check=True)
            pts=json.loads(run.stdout)
            if pts:options.append((sum(math.dist(a,z) for a,z in zip(pts,pts[1:])),layer,pts))
report=[]
for length,layer,points in sorted(options)[:3]:
    b=p.LoadBoard(str(source/name))
    for a,z in zip(points,points[1:]):
        t=p.PCB_TRACK(b);t.SetNetCode(net);t.SetLayer(layer);t.SetWidth(1550000);t.SetStart(pt(a));t.SetEnd(pt(z));b.Add(t)
    folder=root/'runs'/('c522-distribution-'+('wide-' if wide else '')+str(len(report)))
    folder.mkdir(exist_ok=True)
    for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source/file,folder/file)
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(folder/name),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(folder/name)],check=True,capture_output=True)
    saved=p.LoadBoard(str(folder/name));pres=verify_preservation(orig,saved)
    pad=saved.FindFootprintByReference('C511').FindPadByNumber('1')
    loads={o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(pad)}
    def linked(r,n):return saved.FindFootprintByReference(r).FindPadByNumber(n).m_Uuid.AsString() in loads
    delta=introduced(json.loads((source/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    report.append(dict(layer=b.GetLayerName(layer),length=length,path=points,delta=delta,bulk_connected=linked('C522','1'),pin_connected=linked('U5','38'),preservation=pres))
(root/('c522-distribution-wide.json' if wide else 'c522-distribution.json')).write_text(json.dumps(report,indent=2)+'\n')
print([(r['length'],r['layer'],len(r['delta']),r['pin_connected']) for r in report],flush=True);os._exit(0)
