"""Jointly solve C516 orientation, pin bypass and full-width supply entry on the cumulative PCB."""
import hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
from phy_corridor_path import geometry
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
reuse_ground='--existing-return' in sys.argv
terminal='--paired-terminal' in sys.argv or reuse_ground
stage='phy-joint-existing-return' if reuse_ground else 'phy-joint-terminal' if terminal else 'phy-joint-pad-entry'
shift='--shift-bracket' in sys.argv
if shift:stage+='-shift'
cp=json.loads((root/('phy-bracket-trial.json' if shift else 'layout-opposite-bypass.json')).read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));base=p.LoadBoard(str(src));base.BuildConnectivity()
replaced={'0c0e9ecf-cfbc-49dd-aee5-3f8206518f5a','4be7a273-3951-47a2-b0a0-617d5821b21b','fa425619-8809-49bc-860b-00120a1848e7'}
remove=[t for t in b.GetTracks() if t.m_Uuid.AsString() in replaced];assert len(remove)==3
for t in remove:b.Remove(t)
cap=b.FindFootprintByReference('C516');pin=b.FindFootprintByReference('U5').FindPadByNumber('11')
rail,gnd=[cap.FindPadByNumber(n) for n in ('1','2')];net=rail.GetNetCode()
v2=p.VECTOR2I
near=lambda o:o.GetBoundingBox().Inflate(6500000).Contains(pin.GetPosition())
pads=[q for f in b.GetFootprints() if f.GetReference()!='C516' for q in f.Pads() if near(q)]
traces=[t for t in b.GetTracks() if near(t)]
courts=[f.GetCourtyard(p.F_Cu).BBox() for f in b.GetFootprints() if f.GetReference()!='C516' and f.GetLayer()==p.F_Cu and near(f)]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
stack=[p.F_Cu,p.B_Cu,p.In2_Cu,p.In3_Cu]
obs={l:[(q.GetNetCode(),q.GetEffectiveShape(l)) for q in pads+traces if q.IsOnLayer(l)] for l in layers}
def free(t,l):
    shape=t.GetEffectiveShape(l)
    return all(k==t.GetNetCode() or not shape.Collide(s,200000) for k,s in obs[l])
def line(a,z,w,n,l):
    t=p.PCB_TRACK(b);t.SetWidth(w);t.SetStart(v2(*a));t.SetEnd(v2(*z));t.SetNetCode(n);t.SetLayer(l);return t
def via(site,n):
    v=p.PCB_VIA(b);v.SetPosition(v2(*site));v.SetWidth(600000);v.SetDrill(300000);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetViaType(p.VIATYPE_THROUGH);v.SetNetCode(n);return v
box=pin.GetBoundingBox()
starts=[(x,y) for x in range(box.GetLeft()+10000,box.GetRight(),50000) for y in range(box.GetTop()+10000,box.GetBottom(),30000) if pin.HitTest(v2(x,y))]
poses={}
for ix in range(-16,32):
 for iy in range(-23,30):
  loc=pin.GetPosition()+v2(ix*100000,iy*100000)
  for angle in (0,90,180,270):
    cap.SetOrientationDegrees(angle);cap.SetPosition(loc)
    if any(cap.GetCourtyard(p.F_Cu).BBox().Intersects(c) for c in courts) or not all(free(q,p.F_Cu) for q in cap.Pads()):continue
    pos=tuple(rail.GetPosition())
    for start in sorted(starts,key=lambda a:math.dist(a,pos)):
        sig=line(start,pos,200000,net,p.F_Cu)
        if sig.GetLength()>1450000:break
        if not free(sig,p.F_Cu) or sig.GetEffectiveShape(p.F_Cu).Collide(gnd.GetEffectiveShape(p.F_Cu),200000):continue
        if shift and screen(b):break
        for dx in (-200000,-100000,0,100000,200000):
            for dy in (-200000,-100000,0,100000,200000):
                end=rail.GetPosition()+v2(dx,dy)
                if not rail.HitTest(end):continue
                broad=line(tuple(end),tuple(end),1050000,net,p.F_Cu)
                if free(broad,p.F_Cu) and not broad.GetEffectiveShape(p.F_Cu).Collide(gnd.GetEffectiveShape(p.F_Cu),200000):
                    poses.setdefault(tuple(end),[]).append((angle,tuple(loc),start))
        break
cap.SetPosition(v2(-20000000,-20000000))
geos={}
for l in layers:
    polys=[]
    for zone in b.Zones():
        if zone.GetIsRuleArea() and zone.IsOnLayer(l) and (zone.GetDoNotAllowTracks() or zone.GetDoNotAllowVias()):
            for i in range(zone.Outline().OutlineCount()):
                o=zone.Outline().Outline(i);polys.append([tuple(o.CPoint(j)) for j in range(o.PointCount())])
    geos[l]=[*geometry(b,l,net,oval_caps=True),polys]
allpads=[q.GetBoundingBox() for f in b.GetFootprints() for q in f.Pads()]
holes=[[tuple(t.GetPosition()),tuple(t.GetPosition()),t.GetDrillValue()+400000] for t in b.GetTracks() if isinstance(t,p.PCB_VIA)]
req=dict(grid_nm=100000,bounds=[52000000,21200000,74000000,39500000],width_nm=1050000,via_nm=600000,paired_vias=True,layers=[geos[l] for l in stack],through=list(geos.values()),via_keepouts=[holes,[(o.GetLeft(),o.GetTop(),o.GetRight(),o.GetBottom()) for o in allpads]])
ids={k.m_Uuid.AsString() for k in base.GetConnectivity().GetConnectedItems(base.FindFootprintByReference('C515').FindPadByNumber('1'))}
vsites={tuple(t.GetPosition()) for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.m_Uuid.AsString() in ids and t.GetDrillValue()>=300000}
pairs=[(a,z) for a in vsites for z in vsites if a<z and math.dist(a,z)<=800000]
ends=[];pair_lookup={}
for i,l in enumerate(stack):
    targets=set()
    for t in b.GetTracks():
        if t.m_Uuid.AsString() not in ids or isinstance(t,p.PCB_VIA) or t.GetLayer()!=l or t.GetWidth()<1050000:continue
        a,z=tuple(t.GetStart()),tuple(t.GetEnd());n=max(1,math.ceil(t.GetLength()/150000))
        targets.update(tuple(round(u+(v-u)*j/n) for u,v in zip(a,z)) for j in range(n+1))
    for a,z in pairs:
        for pt in (a,z):
            if pt not in targets:pair_lookup[(i,pt)]=(a,z);targets.add(pt)
    ends.append(list(targets))
landings={}
physical_sites=[]
if terminal:
    disabled=[z for z in b.Zones() if z.GetIsRuleArea() and (z.GetDoNotAllowVias() or z.GetDoNotAllowTracks())]
    for ix in range(642,710):
      for iy in range(285,370):
        pt=(ix*100000,iy*100000);v=via(pt,net)
        if any(q.GetBoundingBox().Inflate(351000).Contains(v.GetPosition()) for q in pads):continue
        if any(isinstance(t,p.PCB_VIA) and math.dist(pt,tuple(t.GetPosition()))<800000 for t in traces):continue
        if any(zone.Outline().Collide(v.GetEffectiveShape(p.F_Cu),0) for zone in disabled):continue
        if all(free(v,l) for l in layers):physical_sites.append(pt)
    # Screen the fixed obstacles once per terminal entry before checking moving lands.
    for entry,placements in poses.items():
        sites=[]
        for pt in physical_sites:
            if math.dist(entry,pt)>2000000:continue
            t=line(entry,pt,1050000,net,p.F_Cu)
            if free(t,p.F_Cu) and not any(z.Outline().Collide(t.GetEffectiveShape(p.F_Cu),0) for z in disabled):sites.append((pt,t))
        for a,t in sites:
          for z,_ in sites:
            if not 800000<=math.dist(a,z)<=1100000:continue
            bridge=line(a,z,1050000,net,p.F_Cu)
            if not free(bridge,p.F_Cu) or any(k.Outline().Collide(bridge.GetEffectiveShape(p.F_Cu),0) for k in disabled):continue
            for angle,loc,start in placements:
                cap.SetOrientationDegrees(angle);cap.SetPosition(v2(*loc))
                if any(q.GetBoundingBox().Inflate(351000).Contains(v2(*pt)) for q in (rail,gnd) for pt in (a,z)):continue
                if any(k.GetEffectiveShape(p.F_Cu).Collide(gnd.GetEffectiveShape(p.F_Cu),200000) for k in (bridge,t)):continue
                for i,l in enumerate(stack[1:],1):
                    if free(line(a,z,1050000,net,l),l):
                        landings.setdefault((i,a),[]).append((entry,z,angle,loc,start))
    cap.SetPosition(v2(-20000000,-20000000))
    req.update(start=[[pt for k,pt in landings if k==i] for i in range(len(stack))],end=ends)
else:
    req.update(start=[list(poses),[],[],[]],end=ends)
def solve():
    return json.loads(subprocess.run(['python3',str(Path(__file__).with_name('control_board_grid.py'))],input=json.dumps(req),capture_output=True,text=True,check=True).stdout)
folder=root/'runs'/stage;folder.mkdir(exist_ok=True)
for n in ('fp-lib-table','phy-joint.kicad_dru','phy-joint.kicad_pro'):shutil.copy2(src.parent/n,folder/n)
rec=None;trials=0;reached=0
mechanical_ok=set();entry_ok=set()
ground_ids={k.m_Uuid.AsString() for k in base.GetConnectivity().GetConnectedItems(base.FindFootprintByReference('C511').FindPadByNumber('2'))}
known_ground=[tuple(k.GetPosition()) for k in traces if isinstance(k,p.PCB_VIA) and k.m_Uuid.AsString() in ground_ids]
mount_cache={}
while any(req['start']):
    sol=solve()
    if not sol:break
    reached+=1;path=sol['path'];entry=tuple(path[0][1:]);items=[];bridges=iter(sol['bridges'])
    for (i,x,y),(j,u,v) in zip(path,path[1:]):
        if i==j:items.append(line((x,y),(u,v),1050000,net,stack[i]))
        else:
            at=(x,y);mate=next(bridges);items.extend([via(at,net),via(mate,net),line(at,mate,1050000,net,stack[i]),line(at,mate,1050000,net,stack[j])])
    i,x,y=path[-1]
    if (i,(x,y)) in pair_lookup:items.append(line(*pair_lookup[(i,(x,y))],1050000,net,stack[i]))
    first_layer=path[0][0]
    moves=landings[(first_layer,entry)] if terminal else [(entry,None,*record) for record in poses[entry]]
    base_items=items
    for cap_entry,mate,angle,loc,start in moves:
        items=list(base_items)
        if terminal:
            items.extend([via(entry,net),via(mate,net),line(entry,mate,1050000,net,stack[first_layer]),line(entry,mate,1050000,net,p.F_Cu),line(cap_entry,entry,1050000,net,p.F_Cu)])
        cap.SetOrientationDegrees(angle);cap.SetPosition(v2(*loc))
        if (angle,loc) not in mount_cache:mount_cache[angle,loc]=not bool(screen(b))
        if not mount_cache[angle,loc]:continue
        mechanical_ok.add((angle,loc))
        sig=line(start,tuple(rail.GetPosition()),200000,net,p.F_Cu)
        if any(t.IsOnLayer(p.F_Cu) and t.GetEffectiveShape(p.F_Cu).Collide(gnd.GetEffectiveShape(p.F_Cu),200000) for t in items):continue
        entry_ok.add((angle,loc))
        offsets=sorted(((i,j) for i in range(-10,11) for j in range(-10,11) if i*i+j*j<=110),key=lambda xy:sum(k*k for k in xy))
        sites=known_ground if reuse_ground else [tuple(gnd.GetPosition()+v2(dx*100000,dy*100000)) for dx,dy in offsets]
        for gs in sites:
            if math.dist(gs,tuple(gnd.GetPosition()))>1100000:continue
            v=via(gs,gnd.GetNetCode());gt=line(tuple(gnd.GetPosition()),gs,300000,gnd.GetNetCode(),p.F_Cu)
            if not reuse_ground and any(q.GetBoundingBox().Inflate(351000).Contains(v.GetPosition()) for q in pads+[gnd,rail]):continue
            if not all(free(v,l) for l in layers) or not free(gt,p.F_Cu):continue
            if any(k.IsOnLayer(l) and k.GetEffectiveShape(l).Collide(v.GetEffectiveShape(l),200000) for k in items+[sig,rail] for l in layers):continue
            if any(k.IsOnLayer(p.F_Cu) and k.GetEffectiveShape(p.F_Cu).Collide(gt.GetEffectiveShape(p.F_Cu),200000) for k in items+[sig,rail]):continue
            add=items+[sig,gt]+([] if reuse_ground else [v])
            for k in add:b.Add(k)
            out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
            subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
            delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()));trials+=1
            if not delta:
                saved=p.LoadBoard(str(out));pres=verify_preservation(base,saved,replaced_copper=replaced);assert not screen(saved)
                target=saved.FindFootprintByReference('U5').FindPadByNumber('11')
                assert base.FindFootprintByReference('C515').FindPadByNumber('1').m_Uuid.AsString() in {t.m_Uuid.AsString() for t in saved.GetConnectivity().GetConnectedItems(target)}
                rec=dict(location_nm=loc,angle=angle,entry_nm=entry,path=path,ground_site_nm=gs,preservation=pres);break
            for k in add:b.Remove(k)
        if rec:break
    if rec:break
    req['start'][first_layer].remove(entry)
if not rec:out=src
(root/(stage+'.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],terminal_sites=len(poses),free_barrels=len(physical_sites),layer_landing_sites=len(landings),mechanical_ok=len(mechanical_ok),entry_ok=len(entry_ok),placements=len({(angle,loc) for variants in poses.values() for angle,loc,_ in variants}),reached=reached,drc_trials=trials,change=rec,assembly_ready=False),indent=2)+'\n')
print(len(poses),reached,trials,bool(rec),flush=True);os._exit(0)
