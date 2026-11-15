#!/usr/bin/env python3
"""Audit local bypass continuity; does not qualify power integrity or production."""
import hashlib,json
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments'
D=E/'pmic-inputs';base=E/'pmic-buck5';cp=json.loads((base/'working-candidate.json').read_text())
src=base/cp['board'];out=D/'pcb/pmic-ground-pins.kicad_pcb'
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
report=json.loads((D/'pcb/pmic-ground-pins.json').read_text())
assert report['status']=='PMIC_GROUND_PINS_CONNECTED'
assert hashlib.sha256(out.read_bytes()).hexdigest()==report['sha256']
a,b=p.LoadBoard(str(src)),p.LoadBoard(str(out));b.BuildConnectivity()
pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
pairs=[
(('U4','53'),('L405','1')),(('L405','2'),('C435','1')),
(('L405','2'),('C445','1')),(('U4','59'),('C435','1')),
(('U4','54'),('C425','1')),(('C425','2'),('C435','2')),
(('C445','2'),('C435','2')),(('U4','55'),('C470','1')),
(('C470','2'),('C435','2')),(('C422','2'),('C435','2')),
(('U4','10'),('C422','1')),(('U4','11'),('C421','1')),
(('C421','2'),('C435','2'))]
pairs.extend([(('U4','45'),('C424','1')),(('C424','2'),('C435','2'))])
pairs.extend((('U4',n),('C435','2')) for n in ['14','15','16','17','19','40','47','56','62','63'])
checks=[]
# Check every exposed-pad instance, not only one pad selected by its number.
ground_members={q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads['C435','2'])}
ep=[q for f in b.GetFootprints() if f.GetReference()=='U4' for q in f.Pads() if q.GetNumber()=='69']
assert len(ep)==10
assert all(q.m_Uuid.AsString() in ground_members for q in ep)
# Only the ten new local ground necks use the bounded 0.15 mm exception.
old_ids={t.m_Uuid.AsString() for t in a.GetTracks()}
necks=[t for t in b.GetTracks() if t.m_Uuid.AsString() not in old_ids and t.GetNetname()=='GND' and t.GetWidth()<p.FromMM(.2)]
assert len(necks)==10
assert all(t.GetWidth()==p.FromMM(.15) and t.GetLength()<p.FromMM(1) for t in necks)

for x,y in pairs:
 connected=pads[y].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[x])}
 assert connected,(x,y)
 checks.append({'from':'.'.join(x),'to':'.'.join(y),'connected':True})
replacement=json.loads((D/'pcb/buck2-front.json').read_text())['replaced_copper']
preserved=verify_preservation(a,b,replaced_copper=replacement)
new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'pcb/pmic-ground-pins-drc.json').read_text()))
assert not new,new
sha=hashlib.sha256(out.read_bytes()).hexdigest()
audit={'status':'LOCAL_BYPASS_CONNECTED_NOT_POWER_QUALIFIED','source_sha256':cp['sha256'],'sha256':sha,'checks':checks,'exposed_pad_instances_grounded':len(ep),'ground_necks_width_mm':0.15,'ground_necks_max_length_mm':max(p.ToMM(t.GetLength()) for t in necks),'preservation':preserved,'new_violations':new,'assembly_ready':False}
(D/'pcb/input-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
checkpoint={'status':audit['status'],'board':'pcb/pmic-ground-pins.kicad_pcb','sha256':sha,'verification':'pcb/input-audit.json','schematic':'../emmc-system/system/kicad/integrated/phoenix-g1.kicad_sch','assembly_ready':False}
(D/'working-candidate.json').write_text(json.dumps(checkpoint,indent=2)+'\n')
print(json.dumps(audit,indent=2))
