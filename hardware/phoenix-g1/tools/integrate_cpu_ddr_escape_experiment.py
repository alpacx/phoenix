#!/usr/bin/env python3
"""Place verified CPU coupon copper in a disposable full-board interference experiment."""
import json,shutil,hashlib,math
from pathlib import Path
import pcbnew
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'migration-rk3562/experiments/lpddr4-1gb';D=P/'cpu-board-integration';SOURCE=P/'system/kicad/pcb/phoenix-lpddr4-placement.kicad_pcb'
def main():
    D.mkdir(exist_ok=True);b=pcbnew.LoadBoard(str(SOURCE));coupon=pcbnew.LoadBoard(str(P/'cpu-simultaneous-coupon/cpu-simultaneous.kicad_pcb'));audit=json.loads((P/'cpu-simultaneous-coupon/audit.json').read_text());assert audit['board_sha256']==hashlib.sha256((P/'cpu-simultaneous-coupon/cpu-simultaneous.kicad_pcb').read_bytes()).hexdigest()
    u=next(f for f in b.GetFootprints() if f.GetReference()=='U1');cu=next(iter(coupon.GetFootprints()));assert u.GetOrientationDegrees()==cu.GetOrientationDegrees()==0
    b.BuildConnectivity();conn=b.GetConnectivity();assert not any(len(conn.GetConnectedTracks(p)) for p in u.Pads())
    def point(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
    def box(f):
        r=f.GetBoundingBox(False,False);return tuple(pcbnew.ToMM(v) for v in (r.GetX(),r.GetY(),r.GetRight(),r.GetBottom()))
    def hit(a,z,g=.1):return a[0]<z[2]+g and a[2]>z[0]-g and a[1]<z[3]+g and a[3]>z[1]-g
    protected={f.GetReference() for f in b.GetFootprints() if f.GetReference()=='U2' or f.GetReference().startswith(('Y','J')) or any(len(conn.GetConnectedTracks(p)) for p in f.Pads())}
    obs=[(box(f),f.GetReference() in protected) for f in b.GetFootprints() if f!=u and f.GetLayer()==pcbnew.F_Cu]
    # Avoid existing top copper and through-vias with the CPU courtyard; inner/back copper checked by DRC.
    copper=[]
    for t in b.GetTracks():
        if t.GetLayer()!=pcbnew.F_Cu and not isinstance(t,pcbnew.PCB_VIA):continue
        r=t.GetBoundingBox();copper.append(tuple(pcbnew.ToMM(v) for v in (r.GetX(),r.GetY(),r.GetRight(),r.GetBottom())))
    candidates=[]
    for xi in range(20,160):
        for yi in range(18,64):
            x,y=xi/2,yi/2
            u.SetPosition(point(x,y));bb=box(u)
            if any(hit(bb,z) for z in copper) or any(hit(bb,z) and keep for z,keep in obs):continue
            candidates.append((sum(hit(bb,z) for z,keep in obs),math.hypot(x-30,y-9),x,y))
    (D/'placement-search.json').write_text(json.dumps({'candidate_count':len(candidates),'grid_mm':.5,'search_center_x_mm':[10,79.5],'search_center_y_mm':[9,31.5],'guard_mm':.1,'protects':'Existing routed circuits, connectors, crystals, RAM; conservative top-copper and via bounding boxes','interpretation':'No solution in this bounded conservative search does not establish impossibility','requires_replanning':not bool(candidates)},indent=2)+'\n')
    _,_,x,y=min(candidates) if candidates else (0,0,43,20);u.SetPosition(point(x,y));relocations=[{'ref':'U1','old_xy_mm':[43,20],'xy_mm':[x,y],'reason':'Placement search candidate' if candidates else 'Original position retained for interference diagnosis; bounded relocation search failed'}]
    for f in list(b.GetFootprints()):
        if not candidates or f==u or f.GetLayer()!=pcbnew.F_Cu or not hit(box(f),box(u)):continue
        assert f.GetReference() not in protected
        old=[pcbnew.ToMM(f.GetPosition().x),pcbnew.ToMM(f.GetPosition().y)];other=[box(a) for a in b.GetFootprints() if a!=f and a.GetLayer()==pcbnew.F_Cu]+copper;spots=[]
        for xx in range(2,89):
            for yy in range(2,39):
                f.SetPosition(point(xx,yy));bb=box(f)
                if bb[0]<1 or bb[1]<1 or bb[2]>89 or bb[3]>39 or any(hit(bb,z) for z in other):continue
                spots.append((math.hypot(xx-old[0],yy-old[1]),xx,yy))
        assert spots,('No location for displaced unrouted part',f.GetReference())
        _,xx,yy=min(spots);f.SetPosition(point(xx,yy));relocations.append({'ref':f.GetReference(),'old_xy_mm':old,'xy_mm':[xx,yy]})
    offset=u.GetPosition()-cu.GetPosition();nets={str(k):v for k,v in b.GetNetsByName().items()};added=0
    for old in coupon.GetTracks():
        t=old.Duplicate();t.SetNet(nets[old.GetNetname()]);t.Move(offset);b.Add(t);added+=1
    b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(D/'candidate.kicad_pcb'),b)
    pro=json.loads(SOURCE.with_suffix('.kicad_pro').read_text());pro['board']['design_settings']['rules']['min_track_width']=.0762;(D/'candidate.kicad_pro').write_text(json.dumps(pro,indent=2)+'\n')
    rules=SOURCE.with_suffix('.kicad_dru').read_text();rules+='(rule "Experimental CPU escape width" (condition "A.NetName == \'LPDDR4_*\'") (constraint track_width (min 0.0762mm)))\n(rule "Experimental CPU land spacing" (condition "A.memberOfFootprint(\'U1\')") (constraint clearance (min 0.0762mm)))\n(rule "Experimental DDR copper spacing" (condition "A.NetName == \'LPDDR4_*\'") (constraint clearance (min 0.0762mm)))\n';(D/'candidate.kicad_dru').write_text(rules)
    (D/'fp-lib-table').write_text((SOURCE.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}/../',str((SOURCE.parent/'..').resolve())+'/'))
    (D/'manifest.json').write_text(json.dumps({'status':'FULL_BOARD_INTERFERENCE_EXPERIMENT_NOT_RELEASE','source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'coupon_sha256':audit['board_sha256'],'relocations':relocations,'added_copper_items':added,'cpu_escapes':audit['connected_escape_count'],'source_unchanged':True,'assembly_ready':False,'limits':['Exploratory DDR clearance rules require process qualification and final scoping','No end-to-end DDR routing','No impedance or timing qualification']},indent=2)+'\n');print('CPU copper transferred into separate interference experiment')
if __name__=='__main__':main()
