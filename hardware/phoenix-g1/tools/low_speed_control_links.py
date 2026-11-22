"""Route short, named control branches on fixed footprints and verify the cumulative PCB."""
from pathlib import Path
import hashlib,json,os,subprocess,shutil,math
import pcbnew as p
from phy_corridor_path import geometry
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--usb-controls',action='store_true');parser.add_argument('--reset-feed',action='store_true');args=parser.parse_args();usb=args.usb_controls;reset=args.reset_feed
cp=json.loads((root/('reset-bias-verified.json' if reset else 'pmic-control-bus.json' if usb else 'memory-zq-verified.json')).read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
original=p.LoadBoard(str(src));current=src;accepted=[];attempts=[]
def pad(b,s):
    r,n=s.split('.');return b.FindFootprintByReference(r).FindPadByNumber(n)
pairs=[('R416.2','R414.1'),('R417.2','R415.1'),('R416.1','R417.1'),('R412.1','R417.1')]
if reset:pairs=[('R412.1','R416.1')]
if usb:pairs=[('U16.4','U6.12'),('R602.2','U6.11')]
for a,z in pairs:
    b=p.LoadBoard(str(current));one,two=pad(b,a),pad(b,z);net=one.GetNetCode()
    assert net==two.GetNetCode() and one.IsOnLayer(p.F_Cu) and two.IsOnLayer(p.F_Cu)
    c,obstacles=geometry(b,p.F_Cu,net)
    for zone in b.Zones():
        if zone.GetIsRuleArea() and zone.IsOnLayer(p.F_Cu) and zone.GetDoNotAllowTracks():
            v=zone.GetBoundingBox();obstacles.append((v.GetLeft(),v.GetTop(),v.GetRight(),v.GetBottom()))
    # Avoid unintentionally joining other supply consumers to a pull-up-only branch.
    if one.GetNetname().startswith('+'):
        allow={a,z,'R416.1','R417.1','R412.1'}
        for f in b.GetFootprints():
            for q in f.Pads():
                if q.GetNetCode()==net and q.IsOnLayer(p.F_Cu) and f.GetReference()+'.'+q.GetNumber() not in allow:
                    v=q.GetBoundingBox();obstacles.append((v.GetLeft(),v.GetTop(),v.GetRight(),v.GetBottom()))
    obj=dict(geometry=[c,obstacles],ends=[tuple(one.GetPosition()),tuple(two.GetPosition())],width=200000)
    sol=json.loads(subprocess.run(['python3',str(Path(__file__).with_name('reset_link_grid.py'))],input=json.dumps(obj),capture_output=True,text=True,check=True).stdout)
    if not sol:attempts.append(dict(pair=[a,z],status='no planar route in search'));continue
    for pos,end in zip(sol,sol[1:]):
        t=p.PCB_TRACK(b);t.SetLayer(p.F_Cu);t.SetWidth(200000);t.SetNetCode(net);t.SetStart(p.VECTOR2I(*pos));t.SetEnd(p.VECTOR2I(*end));b.Add(t)
    folder=root/'runs'/('control-link-'+a);folder.mkdir(exist_ok=True)
    for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    drc=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    candidate=p.LoadBoard(str(out));pres=verify_preservation(original,candidate)
    connected=two.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in candidate.GetConnectivity().GetConnectedItems(pad(candidate,a))}
    if drc or not connected:attempts.append(dict(pair=[a,z],status='rejected',drc=drc));continue
    assert not screen(candidate)
    accepted.append(dict(pair=[a,z],net=one.GetNetname(),length_mm=sum(math.dist(i,j) for i,j in zip(sol,sol[1:]))/1e6,preservation=pres));current=out
report=dict(board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),accepted=accepted,other=attempts,assembly_ready=False)
(root/('reset-pull-feed.json' if reset else 'usb-mux-controls.json' if usb else 'low-speed-links.json')).write_text(json.dumps(report,indent=2)+'\n')
print([(e['pair'],e['length_mm']) for e in accepted],attempts,flush=True);os._exit(0)
