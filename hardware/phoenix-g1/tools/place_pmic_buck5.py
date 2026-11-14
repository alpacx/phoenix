#!/usr/bin/env python3
"""Isolated BUCK5 local placement trial; preserve routed parts and source checkpoint."""
import pcbnew as p,json,hashlib,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';S=R/'emmc-system';D=R/'pmic-buck5/pcb';D.mkdir(parents=True,exist_ok=True);cp=json.loads((S/'working-candidate.json').read_text());src=S/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()};moves=[]
for ref,xy,angle,back in [('L405',(60.5,1.4),180,False),('C425',(59.7,3.7),180,False),('C435',(58,2.5),180,True),('C445',(58,6),180,True),('C421',(54,9),180,False),('R1813',(51,9),0,False)]:
 f=fs[ref];assert not any(b.GetConnectivity().GetConnectedTracks(a) for a in f.Pads()),ref;old={'position_mm':[p.ToMM(f.GetPosition().x),p.ToMM(f.GetPosition().y)],'layer':b.GetLayerName(f.GetLayer()),'angle':f.GetOrientationDegrees()}
 if f.IsFlipped()!=back:f.Flip(f.GetPosition(),False)
 f.SetPosition(p.VECTOR2I(*(p.FromMM(v) for v in xy)));f.SetOrientationDegrees(angle);f.Reference().SetVisible(False);moves.append({'reference':ref,'from':old,'to_mm':xy,'angle':angle})
p.ZONE_FILLER(b).Fill(b.Zones());out=D/'placement.kicad_pcb';p.SaveBoard(str(out),b)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
(D/'fp-lib-table').write_text((src.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}/../system/kicad','${KIPRJMOD}/../../emmc-system/system/kicad'))
shutil.copy2(src.parent/(src.stem+'-drc.json'),D/'baseline-drc.json')
(D/'placement.json').write_text(json.dumps({'status':'UNVERIFIED_LOCAL_PLACEMENT_TRIAL','source_checkpoint':'../../emmc-system/working-candidate.json','source_sha256':cp['sha256'],'board_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'moves':moves,'schematic_changed':False,'power_integrity_qualified':False,'assembly_ready':False},indent=2)+'\n')
print(out)
