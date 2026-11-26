from pathlib import Path
import argparse
import json
import hashlib
import pcbnew as p

parser = argparse.ArgumentParser(description='Classify pad-to-track gaps under 90 um on the front U1 BGA.')
parser.add_argument('board', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
from collections import Counter
from math import dist
b = p.LoadBoard(str(args.board))
board_hash = hashlib.sha256(args.board.read_bytes()).hexdigest()
u = b.FindFootprintByReference('U1')
pads = {q.GetNumber(): q for q in u.Pads()}
tmap = {}
for t in b.GetTracks():
    if isinstance(t, p.PCB_VIA) or not t.IsOnLayer(p.F_Cu):
        continue
    bb = t.GetBoundingBox()
    bb.Inflate(90000)
    if u.GetBoundingBox().Intersects(bb):
        tmap[t.m_Uuid.AsString()] = (t, bb)
rows = []
for ref, pad in pads.items():
    shape = pad.GetEffectiveShape(p.F_Cu)
    for key, (t, bb) in tmap.items():
        if t.GetNetCode() == pad.GetNetCode() or not bb.Intersects(pad.GetBoundingBox()):
            continue
        if shape.Collide(t.GetEffectiveShape(p.F_Cu), 90000):
            rows.append((ref, pad.GetNetname(), key, t.GetNetname(), t.GetWidth(), tuple(t.GetStart()), tuple(t.GetEnd())))
rows.sort(key=lambda row: (row[0], row[2]))

def gap(obj, tr):
 a=obj.GetEffectiveShape(p.F_Cu);h=tr.GetEffectiveShape(p.F_Cu);lo,hi=0,350000
 if not a.Collide(h,hi):return None
 while hi-lo>100:
  m=(hi+lo)//2
  if a.Collide(h,m):hi=m
  else:lo=m
 return [lo,hi]
def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def sub(a,b):return (a[0]-b[0],a[1]-b[1])
def intersects(a,z,u,v):
 az=sub(z,a);uv=sub(v,u);d=cross(az,uv)
 if not d:return False
 t=cross(sub(u,a),uv)/d;s=cross(sub(u,a),az)/d
 return 0<=t<=1 and 0<s<1
out=[]
for ref,net,k,tn,w,a,z in rows:
 q=pads[ref];a0=tuple(q.GetPosition());t=tmap[k][0]
 pairs=[]
 for v in pads.values():
  if v.GetNumber()==ref or v.GetNetCode()==t.GetNetCode():continue
  pos=tuple(v.GetPosition())
  if q.GetShape()!=p.PAD_SHAPE_CIRCLE or v.GetShape()!=p.PAD_SHAPE_CIRCLE:continue
  pitch=dist(a0,pos)
  cap=(pitch-(q.GetSize().x+v.GetSize().x)/2-w)/2
  if 0<=cap<90000 and intersects(a,z,a0,pos):
    pairs.append({'pad':v.GetNumber(),'pitch_nm':round(pitch),'balanced_gap_nm':round(cap),'other_observed_gap_nm':gap(v,t)})
 current=gap(q,t);assert current and current[0]<90000
 out.append(dict(pad=ref,pad_net=net,track=k,track_net=tn,width_nm=w,point_a=a,point_z=z,current_gap_nm=current,strict_bottleneck=pairs))
summary = {
    'strict_ball_channel_records': sum(bool(x['strict_bottleneck']) for x in out),
    'distinct_tracks_with_strict_ball_channel': len({x['track'] for x in out if x['strict_bottleneck']}),
    'remaining_records_per_net': dict(Counter(x['track_net'] for x in out if not x['strict_bottleneck'])),
    'bounded_balanced_gaps_nm': dict(Counter(v['balanced_gap_nm'] for x in out for v in x['strict_bottleneck'])),
}
args.output.write_text(json.dumps({'board_sha256':board_hash, 'summary':summary, 'rows':out},indent=2)+'\n')
for k in (True,False):
 samples=[x for x in out if bool(x['strict_bottleneck'])==k]
 print(k,len(samples),len({x['track'] for x in samples}),Counter(x['track_net'] for x in samples))
