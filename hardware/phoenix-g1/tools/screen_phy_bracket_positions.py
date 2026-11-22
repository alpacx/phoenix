"""Identify positions that preserve the complete H8105 case-bracket envelope and existing copper."""
import hashlib,json,math,os
from pathlib import Path
import pcbnew as p
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
prior=json.loads((root/'layout-opposite-bypass.json').read_text());src=root/prior['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==prior['sha256']
b=p.LoadBoard(str(src));mount=b.FindFootprintByReference('H8105');zone=next(z for z in b.Zones() if z.GetZoneName()=='H8105 mechanical reservation')
center=mount.GetPosition();radius=max(zone.GetBoundingBox().GetWidth(),zone.GetBoundingBox().GetHeight())//2
courts=[f.GetCourtyard(f.GetLayer()).BBox() for f in b.GetFootprints() if f.GetReference()!='H8105' and f.GetBoundingBox(False,False).Inflate(14000000).Contains(center)]
pads=[q for f in b.GetFootprints() if f.GetReference()!='H8105' for q in f.Pads() if q.GetBoundingBox().Inflate(14000000).Contains(center)]
tracks=[t for t in b.GetTracks() if t.GetBoundingBox().Inflate(14000000).Contains(center)]
edge=b.GetBoardEdgesBoundingBox()
def boxdist(z,bb):return math.hypot(max(bb.GetLeft()-z.x,0,z.x-bb.GetRight()),max(bb.GetTop()-z.y,0,z.y-bb.GetBottom()))
def trackdist(z,t):
    a,v=t.GetStart(),t.GetEnd();dx,dy=v-a
    k=max(0,min(1,((z.x-a.x)*dx+(z.y-a.y)*dy)/max(dx*dx+dy*dy,1)))
    w=t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth()
    return math.hypot(z.x-a.x-k*dx,z.y-a.y-k*dy)-w/2
legal=[];geometric=[]
c516=b.FindFootprintByReference('C516').FindPadByNumber('1').GetPosition()
for x in range(-20,41):
 for y in range(-30,22):
    z=center+p.VECTOR2I(x*200000,y*200000)
    if math.dist(tuple(z),tuple(center))>8000000 or min(z.x-edge.GetLeft(),edge.GetRight()-z.x,z.y-edge.GetTop(),edge.GetBottom()-z.y)<radius+250000:continue
    if any(boxdist(z,bb)<radius for bb in courts):continue
    if any(boxdist(z,q.GetBoundingBox())<radius for q in pads):continue
    geometric.append(tuple(z))
    if any(trackdist(z,t)<radius for t in tracks):continue
    legal.append(dict(center_nm=tuple(z),movement_mm=math.dist(tuple(z),tuple(center))/1e6,terminal_to_envelope_mm=(math.dist(tuple(z),tuple(c516))-radius)/1e6))
legal.sort(key=lambda row:-row['terminal_to_envelope_mm'])
report=dict(source_sha256=prior['sha256'],original_center_nm=tuple(center),radius_nm=radius,pad_and_body_clear=len(geometric),clear_existing_copper=len(legal),positions=legal,assembly_ready=False)
(root/'phy-bracket-freedom.json').write_text(json.dumps(report,indent=2)+'\n')
print(len(geometric),len(legal),legal[:3],flush=True);os._exit(0)
