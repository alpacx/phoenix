"""Bridge power-stage capacitors on the rotated engineering coupon with paired through vias."""
from functools import lru_cache
from pathlib import Path
from collections import Counter
import hashlib
import heapq
import json
import math
import os
import shutil
import subprocess
import sys
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import route_leg
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'layout-pmic-pwron-filter.json').read_text());base=root/meta['board'];coupled='--coupled' in sys.argv;shifted='--shifted' in sys.argv;start_dir=root/('runs/pmic-five-stage-new-inductor-0' if shifted else 'runs/pmic-five-stage-coupled-0' if coupled else 'runs/pmic-five-stage-copper-0')
source=start_dir/base.name;parent=json.loads((start_dir/'power-paths.json').read_text());assert hashlib.sha256(source.read_bytes()).hexdigest()==parent['board_sha256']
b=p.LoadBoard(str(source));b.BuildConnectivity();ls=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
def vec(pt):return p.VECTOR2I(*pt)
def make(a,z,w,code,l):
    t=p.PCB_TRACK(b);t.SetNetCode(code);t.SetLayer(l);t.SetWidth(w);t.SetStart(vec(a));t.SetEnd(vec(z));return t
def barrel(a,code):
    v=p.PCB_VIA(b);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(code);v.SetPosition(vec(a));v.SetWidth(450000);v.SetDrill(200000);return v
def leg(net,a,la,z,lz,width,maxsum):
    return route_leg(b,net,a,la,z,lz,width,maxsum,'--passive-vip' in sys.argv,shifted)
def pad(ref,n):return b.FindFootprintByReference(ref).FindPadByNumber(n)
rows=[]
for k in (3,1,2,4,5):
    a,z=pad(f'L40{k}','2'),pad(f'C43{k}','1')
    assert a.GetNetCode()==z.GetNetCode()
    row=leg(a.GetNetname(),tuple(a.GetPosition()),a.GetParentFootprint().GetLayer(),tuple(z.GetPosition()),z.GetParentFootprint().GetLayer(),600000,4.0)
    rows.append(dict(stage=k,role='LC output',net=a.GetNetname(),width_mm=.6,**row))
inputs='--supplies' in sys.argv;returns='--grounds' in sys.argv
def supply(k,pin):
    q=pad('U4',pin);cap=pad(f'C42{k}','1');code=q.GetNetCode();assert code==cap.GetNetCode()
    mid=q.GetPosition();center=b.FindFootprintByReference('U4').GetPosition();ax,ay=mid.x-center.x,mid.y-center.y
    nx,ny=(int(math.copysign(1,ax)),0) if abs(ax)>abs(ay) else (0,int(math.copysign(1,ay)))
    toe=mid+p.VECTOR2I(nx*440000,ny*440000);objects=[o for o in list(b.GetTracks())+[v for f in b.GetFootprints() for v in f.Pads()] if o.IsOnLayer(p.F_Cu) and o.GetNetCode()!=code and inflated_box(o,1000000).Contains(toe)]
    candidates=[]
    # The accepted CAD has 0.127 mm input necks at 10/11/24/54 and
    # 0.150 mm at pin 66. Preserve or improve the actual copper throat.
    prior_width,prior_length={1:(127000,740000),2:(127000,740000),3:(127000,940000),4:(150000,590000),5:(127000,685000)}[k]
    for w,start_delta in ((200000,440000),(prior_width,250000),(prior_width,350000)):
      toe=mid+p.VECTOR2I(nx*start_delta,ny*start_delta)
      for length in (300000,400000,500000,575000):
        for skew in (0,50000,-50000,100000,-100000,150000,-150000,200000,-200000):
            start=tuple(toe+p.VECTOR2I(nx*length-ny*skew,ny*length+nx*skew));wire=make(tuple(toe),start,w,code,p.F_Cu)
            if wire.GetLength()>prior_length:continue
            if not wire.GetEffectiveShape(p.F_Cu).Collide(q.GetEffectiveShape(p.F_Cu),0):continue
            if any(wire.GetEffectiveShape(p.F_Cu).Collide(o.GetEffectiveShape(p.F_Cu),202000) for o in objects):continue
            candidates.append((math.dist(start,tuple(cap.GetPosition())),length,abs(skew),start,wire))
    for _,length,_,start,wire in sorted(candidates,key=lambda row:row[:3]):
        trial=leg(q.GetNetname(),start,p.F_Cu,tuple(cap.GetPosition()),cap.GetParentFootprint().GetLayer(),500000,4.1)
        if trial['connected']:
            b.Add(wire);return dict(**trial,neck_length_mm=wire.GetLength()/1e6,neck_mm=wire.GetWidth()/1e6,old_neck_mm=prior_width/1e6,old_neck_length_mm=prior_length/1e6)
    return dict(connected=False,launch_candidates=len(candidates))
def relocate_input_cap(row):
    pairs=row.get('source_map',[])
    if not pairs:return None
    cap=b.FindFootprintByReference('C425');old=tuple(cap.GetPosition());old_angle=cap.GetOrientationDegrees()
    pwr=cap.FindPadByNumber('1');gnd=cap.FindPadByNumber('2');code=pwr.GetNetCode();layer=p.B_Cu
    pair_divider='--couple-r410' in sys.argv
    divider=b.FindFootprintByReference('R410');div_xy=tuple(divider.GetPosition());div_angle=divider.GetOrientationDegrees();excluded={'C425','R410'} if pair_divider else {'C425'}
    counts=dict(bodies=0,pads=0,single_via=0,both_vias=0,divider=0)
    ids=[tuple(entry['pt_nm']) for entry in pairs];par={tuple(e['pt_nm']):e['route_nm'] for e in pairs}
    area=vec((64500000,10700000))
    objs=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() if f.GetReference() not in excluded for q in f.Pads()] if inflated_box(o,6300000).Contains(area)]
    shapes=[(o.GetNetCode(),o.GetEffectiveShape(layer),o.GetBoundingBox()) for o in objs if o.IsOnLayer(layer)]
    drills=[(o.GetNetCode(),o.GetEffectiveHoleShape()) for o in objs if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    courts=[f.GetCourtyard(layer) for f in b.GetFootprints() if f.GetLayer()==layer and f.GetReference() not in excluded and inflated_box(f,6300000).Contains(area)]
    alien_holes=[o.GetEffectiveHoleShape() for o in objs if isinstance(o,p.PAD) and o.GetDrillSize().x and o.GetParentFootprint().GetLayer()!=layer]
    def clear(o):
        geom=o.GetEffectiveShape(layer);bb=inflated_box(o,370000);nc=o.GetNetCode()
        return not(any(c!=nc and bb.Intersects(box) and geom.Collide(g,202000) for c,g,box in shapes) or any(c!=nc and geom.Collide(h,250000) for c,h in drills))
    opts=[]
    for angle in (0,90,180,270):
        cap.SetOrientationDegrees(angle)
        for x in range(601,690,2):
            for y in range(65,141,2):
                xy=(x*100000,y*100000);cap.SetPosition(vec(xy));court=cap.GetCourtyard(layer)
                if any(court.Collide(other,100000) for other in courts) or any(court.Collide(h,50000) for h in alien_holes):continue
                counts['bodies']+=1
                if not clear(pwr) or not clear(gnd):continue
                counts['pads']+=1
                pos=tuple(pwr.GetPosition());land=pwr.GetEffectiveShape(layer);g=gnd.GetEffectiveShape(layer);usable=[]
                for pt in ids:
                    if math.dist(pt,pos)+sum(math.dist(u,v) for u,v in zip(par[pt],par[pt][1:]))>4100000:continue
                    via=barrel(pt,code);s=via.GetEffectiveShape(layer)
                    if s.Collide(g,202000):continue
                    if s.Collide(land,75000) and not all(pwr.HitTest(vec((pt[0]+round(275000*math.cos(i*math.tau/24)),pt[1]+round(275000*math.sin(i*math.tau/24))))) for i in range(24)):continue
                    wire=make(pos,pt,500000,code,layer)
                    if clear(wire) and not wire.GetEffectiveShape(layer).Collide(g,202000):usable.append(pt)
                combos=[(math.dist(pos,pt)+math.dist(pos,at),pt,at) for i,pt in enumerate(usable) for at in usable[:i] if 600000<=math.dist(pt,at)<=1050000]
                if usable:counts['single_via']+=1
                if combos:
                    counts['both_vias']+=1
                    score,pt,at=min(combos);opts.append((score+math.dist(old,xy)*.15,xy,angle,pt,at))
    ground_fail=0
    for _,xy,angle,v1,v2 in sorted(opts):
        cap.SetOrientationDegrees(angle);cap.SetPosition(vec(xy))
        if pair_divider:
            picked=None
            for dx,dy in sorted([(i,j) for i in range(-7,8) for j in range(-7,8)],key=lambda d:math.hypot(*d)):
                for ang in (div_angle,div_angle+90,div_angle+180,div_angle+270):
                    dv=(div_xy[0]+dx*250000,div_xy[1]+dy*250000)
                    divider.SetPosition(vec(dv));divider.SetOrientationDegrees(ang)
                    court=divider.GetCourtyard(layer)
                    if any(court.Collide(other,100000) for other in courts+[cap.GetCourtyard(layer)]) or any(court.Collide(h,50000) for h in alien_holes):continue
                    if not all(clear(q) for q in divider.Pads()):continue
                    picked=(dv,ang);break
                if picked:break
            if not picked:continue
            counts['divider']+=1
        if screen(b):continue
        bits=[];seen=set();land=pwr.GetEffectiveShape(layer)
        for at in (v1,v2):
            via=barrel(at,code)
            if via.GetEffectiveShape(layer).Collide(land,0):
                via.SetFillingMode(p.FILLING_MODE_FILLED);via.SetCappingMode(p.CAPPING_MODE_CAPPED)
            bits.append(via)
            for side,coords in [(p.F_Cu,par[at]),(layer,[tuple(pwr.GetPosition()),at])]:
                for u,v in zip(coords,coords[1:]):
                    key=(side,tuple(u),tuple(v))
                    if u!=v and key not in seen:bits.append(make(u,v,500000,code,side));seen.add(key)
        for item in bits:b.Add(item)
        pos=tuple(gnd.GetPosition());ret=leg('GND',pos,layer,pos,p.In1_Cu,500000,4)
        if ret['connected']:
            return dict(connected=True,kind='relocated capacitor with two parallel input vias',location_nm=xy,angle=angle,via_centres_nm=[v1,v2],return_route=ret,divider_nm=tuple(divider.GetPosition()),divider_angle=divider.GetOrientationDegrees(),counts=counts,feasible_poses=len(opts),earlier_ground_failures=ground_fail)
        ground_fail+=1
        for item in bits:b.Remove(item)
    cap.SetOrientationDegrees(old_angle);cap.SetPosition(vec(old));divider.SetPosition(vec(div_xy));divider.SetOrientationDegrees(div_angle)
    return dict(connected=False,counts=counts,kind='relocation screen',feasible_supply_poses=len(opts),ground_failures=ground_fail)
if inputs:
    for k,pin in [(3,'24'),(1,'11'),(2,'10'),(4,'66'),(5,'54')]:
        tap=next((t for t in parent.get('vcc_taps',[]) if t['stage']==k and t['connected']),None)
        if tap:
            q=pad(f'C42{k}','1');result=leg('+3V3_SYS',tuple(tap['terminal_nm']),p.F_Cu,tuple(q.GetPosition()),q.GetParentFootprint().GetLayer(),500000,4.1)
        else:result=supply(k,pin)
        if k==5 and '--relocate-c425' in sys.argv and not result['connected']:
            altered=relocate_input_cap(result)
            if altered:
                if altered['connected']:result=altered
                else:result['placement_result']=altered
        rows.append(dict(stage=k,role='PMIC to input bypass',net='+3V3_SYS',width_mm=.5,**result))
if returns:
    for k in (3,1,2,4,5):
        for family in ('C42','C43'):
            q=pad(f'{family}{k}','2');layer=q.GetParentFootprint().GetLayer();pt=tuple(q.GetPosition())
            prior=next((r.get('return_route') for r in rows if r['stage']==5 and 'return_route' in r),None)
            res=prior if prior and k==5 and family=='C42' else leg('GND',pt,layer,pt,p.In1_Cu,500000,4)
            rows.append(dict(stage=k,role=family+' ground',net='GND',width_mm=.5,**res))
folder=root/('runs/pmic-five-stage-c425-r410-0' if '--couple-r410' in sys.argv else 'runs/pmic-five-stage-c425-0' if '--relocate-c425' in sys.argv else 'runs/pmic-five-stage-shifted-0' if shifted else 'runs/pmic-five-stage-pofv-0' if '--passive-vip' in sys.argv else 'runs/pmic-five-stage-full-coupled-0' if coupled else 'runs/pmic-five-stage-power-0' if inputs and returns else 'runs/pmic-five-stage-inputs-0' if inputs else 'runs/pmic-five-stage-grounds-0' if returns else 'runs/pmic-five-stage-capacitors-0');folder.mkdir(exist_ok=True)
for n in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(base.parent/n,folder/n)
out=folder/base.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
b=p.LoadBoard(str(out));b.BuildConnectivity()
for r in rows:
    k=r['stage']
    if r['role']=='LC output':a,z=pad(f'L40{k}','2'),pad(f'C43{k}','1')
    elif r['role']=='PMIC to input bypass':a,z=pad('U4',{1:'11',2:'10',3:'24',4:'66',5:'54'}[k]),pad(f'C42{k}','1')
    else:a,z=pad(r['role'].split()[0]+str(k),'2'),pad('U4','69')
    r['native_connected']=z.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(a)}
drc=json.loads((folder/'drc.json').read_text());delta=introduced(json.loads((start_dir/'drc.json').read_text()),drc)
state=dict(verified_base_sha256=meta['sha256'],coupon_parent=parent['board_sha256'],adopted=False,rows=rows,new_delta=delta,board_sha256=hashlib.sha256(out.read_bytes()).hexdigest())
(folder/'output-legs.json').write_text(json.dumps(state,indent=2)+'\n');print([(r['stage'],r['native_connected'],r.get('legal_sites'),r.get('both_faces_reached')) for r in rows],len(delta),flush=True);os._exit(0)
