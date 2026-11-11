#!/usr/bin/env python3
"""Migrate pads into a separate PCB placement candidate; never auto-route DDR."""
import json,hashlib,math
from pathlib import Path
import pcbnew
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'migration-rk3562';P=BASE/'experiments/lpddr4-1gb';OUT=P/'system/kicad/pcb'
SOURCE=BASE/'experiments/pmic-io-feed/candidate.kicad_pcb'
def mm(v):return pcbnew.ToMM(v)
def pos(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
def box(f):
    r=f.GetBoundingBox(False,False);return (mm(r.GetX()),mm(r.GetY()),mm(r.GetRight()),mm(r.GetBottom()))
def overlap(a,b,g=.15):return a[0]<b[2]+g and a[2]>b[0]-g and a[1]<b[3]+g and a[3]>b[1]-g
def main():
    OUT.mkdir(parents=True,exist_ok=True);board=pcbnew.LoadBoard(str(SOURCE));board.BuildConnectivity();conn=board.GetConnectivity();removed=[]
    rows=json.loads((P/'system/review/integrated-contract.json').read_text());target={(r['ref'],r['pin']):r['net'] for r in rows}
    active={r['ref'] for r in rows};nets={str(k):v for k,v in board.GetNetsByName().items()}
    for name in sorted({v for v in target.values() if v is not None}):
        if name not in nets:
            n=pcbnew.NETINFO_ITEM(board,name);board.Add(n);nets[name]=n
    def setnet(pad,net):
        if net:pad.SetNet(nets[net])
        else:pad.SetNetCode(0)
    changed=[];obsolete=[]
    for f in list(board.GetFootprints()):
        ref=f.GetReference()
        if ref=='U2' or ref not in active:
            for pad in f.Pads():assert len(conn.GetConnectedTracks(pad))==0,('Cannot silently remove routed component',ref)
            removed.append(f);board.Remove(f);obsolete.append(ref);continue
        for pad in f.Pads():
            key=(ref,pad.GetNumber())
            if key not in target:continue
            net=target[key];old=pad.GetNetname()
            if old!=(net or ''):
                assert len(conn.GetConnectedTracks(pad))==0,('Changed routed pad requires explicit copper migration',key,old,net)
                changed.append({'ref':ref,'pad':pad.GetNumber(),'old':old,'new':net});setnet(pad,net)
        if ref in ['R431','R432']:f.SetValue({'R431':'45.3k 0.1%','R432':'121k 0.1%'}[ref])
    ram=pcbnew.FootprintLoad(str(P/'Phoenix_LPDDR4_Draft.pretty'),'H9HCNNN8KUMLHR_FBGA200_10x15_P0.8x0.65_DRAFT');assert ram
    ram.SetReference('U2');ram.SetValue('H9HCNNN8KUMLHR-NME');board.Add(ram)
    for pad in ram.Pads():setnet(pad,target['U2',pad.GetNumber()])
    front=[f for f in board.GetFootprints() if f!=ram and f.GetLayer()==pcbnew.F_Cu]
    routed={f.GetReference() for f in front if f.GetReference()=='U1' or f.GetReference().startswith('Y') or any(len(conn.GetConnectedTracks(p)) for p in f.Pads())}
    obstacles=[(box(f),1000 if f.GetReference() in routed else 1) for f in front]
    copper=[]
    for t in board.GetTracks():
        if t.GetLayer()==pcbnew.F_Cu or isinstance(t,pcbnew.PCB_VIA):
            r=t.GetBoundingBox();copper.append((mm(r.GetX()),mm(r.GetY()),mm(r.GetRight()),mm(r.GetBottom())))
    candidates=[]
    for angle in [0,90]:
        ram.SetOrientationDegrees(angle)
        for x in range(16,34):
            for y in range(9,32):
                ram.SetPosition(pos(x,y));b=box(ram)
                if b[0]<1 or b[1]<1 or b[2]>89 or b[3]>39:continue
                if any(overlap(b,o) and weight==1000 for o,weight in obstacles):continue
                if any(overlap(b,o,.25) for o in copper):continue
                hits=sum(overlap(b,o) for o,weight in obstacles)
                candidates.append((hits,math.hypot(43-x,20-y),x,y,angle))
    assert candidates,'No memory placement preserving routed circuits and clocks'
    best=min(candidates);ram.SetOrientationDegrees(best[4]);ram.SetPosition(pos(best[2],best[3]));placements=[{'ref':'U2','xy_mm':[best[2],best[3]],'angle_deg':best[4],'initial_overlap_count':best[0]}]
    # Move only unrouted obstructing components; protect every existing routed group.
    rb=box(ram)
    for f in front:
        if not overlap(rb,box(f)):continue
        assert f.GetReference() not in routed,('RAM would displace routed component',f.GetReference())
        oldxy=[mm(f.GetPosition().x),mm(f.GetPosition().y)]
        obs=[box(a) for a in board.GetFootprints() if a!=f and a.GetLayer()==pcbnew.F_Cu]
        choices=[]
        for x in range(3,88):
            for y in range(3,38):
                f.SetPosition(pos(x,y));bb=box(f)
                if bb[0]<1 or bb[1]<1 or bb[2]>89 or bb[3]>39:continue
                if any(overlap(bb,o,.3) for o in obs+copper):continue
                choices.append((math.hypot(x-oldxy[0],y-oldxy[1]),x,y))
        assert choices,('No safe relocation',f.GetReference())
        _,x,y=min(choices);f.SetPosition(pos(x,y));placements.append({'ref':f.GetReference(),'old_xy_mm':oldxy,'xy_mm':[x,y],'reason':'unrouted component obstructing RAM envelope'})
    # Transfer isolated RAM signal dogbones; route endpoints remain intentionally unfinished.
    coupon=json.loads((P/'fanout-coupon/assignment.json').read_text())
    assert best[4]==0,'Rotated coupon transform must be implemented before use'
    rampads={p.GetNumber():p for p in ram.Pads()}
    for entry in coupon['assignments']:
        pad=rampads[entry['ball']];x,y=entry['via_xy'];x+=best[2]-10;y+=best[3]-12
        via=pcbnew.PCB_VIA(board);via.SetPosition(pos(x,y));via.SetWidth(pcbnew.FromMM(.45));via.SetDrill(pcbnew.FromMM(.2));via.SetViaType(pcbnew.VIATYPE_THROUGH);via.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);via.SetNet(pad.GetNet());board.Add(via)
        track=pcbnew.PCB_TRACK(board);track.SetStart(pad.GetPosition());track.SetEnd(via.GetPosition());track.SetLayer(pcbnew.F_Cu);track.SetWidth(pcbnew.FromMM(.1));track.SetNet(pad.GetNet());board.Add(track)
    # Existing unrouted backside bypass parts must clear the new through-vias.
    via_boxes=[]
    for t in board.GetTracks():
        if isinstance(t,pcbnew.PCB_VIA) and t.GetNetname().startswith('LPDDR4_'):
            r=t.GetBoundingBox();via_boxes.append((mm(r.GetX()),mm(r.GetY()),mm(r.GetRight()),mm(r.GetBottom())))
    for f in list(board.GetFootprints()):
        if f.GetLayer()!=pcbnew.B_Cu or not any(overlap(box(f),v,.2) for v in via_boxes):continue
        # Preserve already-routed back-side circuitry; initial preexisting via overlaps are ignored there.
        if any(len(conn.GetConnectedTracks(p)) for p in f.Pads()):continue
        oldxy=[mm(f.GetPosition().x),mm(f.GetPosition().y)]
        obs=[box(a) for a in board.GetFootprints() if a!=f and a.GetLayer()==pcbnew.B_Cu]+via_boxes
        for t in board.GetTracks():
            if t.GetLayer()==pcbnew.B_Cu:
                r=t.GetBoundingBox();obs.append((mm(r.GetX()),mm(r.GetY()),mm(r.GetRight()),mm(r.GetBottom())))
        choices=[]
        for xi in range(32,74):
            for yi in range(4,76):
                x,y=xi/2,yi/2;f.SetPosition(pos(x,y));bb=box(f)
                if not any(overlap(bb,o,.25) for o in obs):choices.append((math.hypot(x-oldxy[0],y-oldxy[1]),x,y))
        assert choices,('No backside relocation',f.GetReference())
        _,x,y=min(choices);f.SetPosition(pos(x,y));placements.append({'ref':f.GetReference(),'old_xy_mm':oldxy,'xy_mm':[x,y],'reason':'clear RAM through-vias; unrouted bypass relocation'})
    # New bypass parts on reverse side close to RAM, conservative rectangle clearance search.
    for i in range(8):
        ref='C'+str(2301+i);bulk=i in (0,4);name='C_0805_2012Metric' if bulk else 'C_0402_1005Metric'
        f=pcbnew.FootprintLoad(str(P/'system/kicad/Phoenix_Passives.pretty'),name);assert f
        f.SetReference(ref);f.SetValue('10u' if bulk else '100n');board.Add(f);f.SetPosition(pos(0,0));f.Flip(f.GetPosition(),False)
        for pad in f.Pads():setnet(pad,target[ref,pad.GetNumber()])
        obs=[box(a) for a in board.GetFootprints() if a!=f and a.GetLayer()==pcbnew.B_Cu]
        for t in board.GetTracks():
            if t.GetLayer()==pcbnew.B_Cu or isinstance(t,pcbnew.PCB_VIA):
                r=t.GetBoundingBox();obs.append((mm(r.GetX()),mm(r.GetY()),mm(r.GetRight()),mm(r.GetBottom())))
        spots=[]
        for xi in range(30,65):
            for yi in range(6,75):
                x,y=xi/2,yi/2;f.SetPosition(pos(x,y));b=box(f)
                if not any(overlap(b,o,.3) for o in obs):spots.append((math.hypot(x-best[2],y-best[3]),x,y))
        assert spots,('No candidate bypass placement',ref)
        score,x,y=min(spots);f.SetPosition(pos(x,y));placements.append({'ref':ref,'xy_mm':[x,y],'layer':'B.Cu'})
    board.BuildConnectivity();pcbnew.ZONE_FILLER(board).Fill(board.Zones());pcbnew.SaveBoard(str(OUT/'phoenix-lpddr4-placement.kicad_pcb'),board)
    (OUT/'fp-lib-table').write_text((P/'system/kicad/fp-lib-table').read_text().replace('${KIPRJMOD}/','${KIPRJMOD}/../'))
    source_project=SOURCE.with_suffix('.kicad_pro')
    if source_project.exists():
        project=json.loads(source_project.read_text());project['board']['design_settings']['rules']['min_track_width']=.1;project['meta']['filename']='phoenix-lpddr4-placement.kicad_pro'
        (OUT/'phoenix-lpddr4-placement.kicad_pro').write_text(json.dumps(project,indent=2)+'\n')
    rules='''(version 1)
(rule "Non DDR width" (constraint track_width (min 0.2mm)))
(rule "DDR escape width" (condition "A.NetName == 'LPDDR4_*'") (constraint track_width (min 0.1mm)))
(rule "DDR package spacing" (condition "A.memberOfFootprint('U2')") (constraint clearance (min 0.1mm)))
'''
    (OUT/'phoenix-lpddr4-placement.kicad_dru').write_text(rules)
    report={'status':'RAM_FANOUT_CANDIDATE_FULL_DDR_UNROUTED','source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'removed_footprints':obsolete,'changed_pads':changed,'placements':placements,'total_copper_items':len(board.GetTracks()),'new_ram_fanout_copper_items':130,'missing_footprints':sorted(active-{f.GetReference() for f in board.GetFootprints()}),'limits':['Bounding-box screen only; DRC and mechanical review required','No DDR routing or SI qualification','Original 90x40 outline retained','No thermal or boot test']}
    (P/'system/review/pcb-migration.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='changed_pads'})
if __name__=='__main__':main()
