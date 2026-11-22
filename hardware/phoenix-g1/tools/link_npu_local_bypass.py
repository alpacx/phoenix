"""Join the existing grounded C1621 to the bonded NPU supply balls on an ordinary interstitial escape."""
from pathlib import Path
import hashlib,json,math,subprocess,shutil
from collections import Counter
import pcbnew as p
from pcb_power_leg import barrel,make
from phy_corridor_path import geometry
from pcb_preservation import verify_preservation
from drc_regression import introduced
tools=Path(__file__).resolve().parent;r=tools.parent/'migration-rk3562/experiments/phy-power-parallel';cp=json.loads((r/'layout-bga-ground-qualified.json').read_text());src=r/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();scan=json.loads((r/'core-bank-supply-1G3.json').read_text());assert scan['parent_sha256']==cp['sha256']
s=scan['branch_options'][0];xy=tuple(s['via_nm']);ref=b.FindFootprintByReference('C1621');cap=ref.FindPadByNumber('1');code=cap.GetNetCode()
req=dict(geometry=geometry(b,p.B_Cu,code,oval_caps=True),sites=[xy],target=[tuple(cap.GetPosition())],width=250000,limit=3100000)
rep=subprocess.run(['python3',str(tools/'screen_cpu_launch_corridor.py')],input=json.dumps(req),capture_output=True,text=True,check=True)
result=json.loads(rep.stdout);report=dict(parent_sha256=cp['sha256'],window=s,back=result)
if result['path']:
    b.Add(barrel(b,xy,code))
    pts=[s['source_nm'],s['elbow_nm'],xy]
    for layer,path in [(p.F_Cu,pts),(p.B_Cu,result['path'])]:
        for a,z in zip(path,path[1:]):
            if tuple(a)!=tuple(z):b.Add(make(b,a,z,250000,code,layer))
    out=r/'runs/npu-local-bypass';out.mkdir(exist_ok=True,parents=True);file=out/src.name
    for ext in ('.kicad_pro','.kicad_dru'):shutil.copy2(src.with_suffix(ext),file.with_suffix(ext))
    shutil.copy2(src.parent/'fp-lib-table',out/'fp-lib-table');p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(file),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(out/'drc.json'),str(file)],capture_output=True,check=True)
    db=json.loads((out/'drc.json').read_text());delta=introduced(json.loads((src.parent/'drc.json').read_text()),db);saved=p.LoadBoard(str(file));saved.BuildConnectivity()
    report.update(sha256=hashlib.sha256(file.read_bytes()).hexdigest(),board=str(file.relative_to(r)),remaining=len(db['unconnected_items']),new_drc=delta,preservation=verify_preservation(p.LoadBoard(str(src)),saved))
(r/'npu-local-bypass.json').write_text(json.dumps(report,indent=2)+'\n');print(result.get('path'),report.get('remaining'),report.get('new_drc'))
if result['path'] and not delta:
    refs={p.F_Cu:p.In1_Cu,p.In2_Cu:p.In1_Cu,p.In3_Cu:p.In4_Cu,p.B_Cu:p.In4_Cu}
    def plane(board,l):return next(z.GetFilledPolysList(l) for z in board.Zones() if z.GetNetname()=='GND' and z.HasFilledPolysForLayer(l))
    oldboard=p.LoadBoard(str(src))
    oldplanes={l:plane(oldboard,l) for l in set(refs.values())};newplanes={l:plane(saved,l) for l in set(refs.values())}
    from pcb_bounds import inflated_box
    losses=[];center=p.VECTOR2I(*xy)
    for t in oldboard.GetTracks():
        if isinstance(t,p.PCB_VIA) or t.GetLayer() not in refs or not t.GetNetname().startswith(('LPDDR4_','EMMC_','SOC_EMMC','USB_','ETH_','WIFI_')) or not inflated_box(t,1200000).Contains(center):continue
        area=p.SHAPE_POLY_SET();t.TransformShapeToPolygon(area,t.GetLayer(),200000,500,p.ERROR_OUTSIDE);l=refs[t.GetLayer()];area.BooleanIntersection(oldplanes[l]);area.BooleanSubtract(newplanes[l])
        if area.Area()>1e5:losses.append((t.GetNetname(),area.Area()/1e12))
    def pad(label):
        a,n=label.split('.');return saved.FindFootprintByReference(a).FindPadByNumber(n)
    g={o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(pad('U4.69'))}
    assert pad('C1621.2').m_Uuid.AsString() in g
    ret=min((math.dist(xy,tuple(t.GetPosition()))/1e6,tuple(t.GetPosition())) for t in saved.GetTracks() if isinstance(t,p.PCB_VIA) and t.m_Uuid.AsString() in g)
    report.update(fast_plane_losses=losses,nearest_ground=ret)
    (r/'npu-local-bypass.json').write_text(json.dumps(report,indent=2)+'\n')
    if not losses:
        nets=cp['open_nets'].copy();groups=nets['VDD_NPU'];local=next(g for g in groups if 'C1621.1' in g);soc=next(g for g in groups if 'U1.1G3' in g)
        nets['VDD_NPU']=[g for g in groups if g!=local and g!=soc]+[sorted(local+soc)]
        assert sum(len(g)-1 for g in nets.values())==report['remaining']
        pairs=sorted({tuple(sorted(pair)) for pair in cp['verified_pairs']}|{tuple(sorted(('C1621.1',s))) for s in soc}|{('C1621.2','U4.69')})
        cache={}
        for a,z in pairs:
            if a not in cache:cache[a]={o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(pad(a))}
            assert pad(z).m_Uuid.AsString() in cache[a]
        d=dict(board=report['board'],sha256=report['sha256'],parent_sha256=cp['sha256'],preservation=report['preservation'],verified_pairs=pairs,remaining_minimum_joins=report['remaining'],open_nets=nets,new_drc=[],drc_counts=dict(Counter(v['type'] for v in db['violations'])),assembly_ready=False)
        (r/'layout-npu-local-bypass.json').write_text(json.dumps(d,indent=2)+'\n')
    print('losses',losses,'ground',ret)
