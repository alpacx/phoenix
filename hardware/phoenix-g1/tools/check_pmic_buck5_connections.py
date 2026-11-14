#!/usr/bin/env python3
"""Report actual BUCK5 connectivity; never infer completeness from equal net names."""
import pcbnew as p,json,hashlib,os
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-buck5';stage=os.environ.get('PHOENIX_BUCK5_CONNECTION_STAGE','local-complete');path=D/('pcb/'+stage+'.kicad_pcb');b=p.LoadBoard(str(path));b.BuildConnectivity();pads={(f.GetReference(),a.GetNumber()):a for f in b.GetFootprints() for a in f.Pads()}
def connected(a,z):return pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}
pairs=[(('U4','53'),('L405','1')), (('L405','2'),('C435','1')), (('U4','59'),('C435','1')), (('C425','2'),('U4','69')), (('C435','2'),('U4','69')), (('U4','54'),('C425','1')), (('L405','2'),('C445','1')), (('C445','2'),('U4','69'))]
if stage in ('io-bypass','layout-reviewed'):pairs += [(('U4','55'),('C470','1')),(('C470','2'),('U4','69')),(('C422','2'),('U4','69'))]
audit=json.loads((D/('pcb/'+stage+'-preservation-audit.json')).read_text());assert audit['sha256']==hashlib.sha256(path.read_bytes()).hexdigest();assert not audit['new_drc_violations']
rows=[{'from':'.'.join(a),'to':'.'.join(z),'connected':connected(a,z)} for a,z in pairs]
assert all(r['connected'] for r in rows),rows
report={'status':'LOCAL_BUCK5_TOPOLOGY_CONNECTED_NOT_POWER_QUALIFIED','board_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'connections':rows,'external_input_feed_qualified':False,'loop_stability_qualified':False,'effective_capacitance_qualified':False,'current_capacity_qualified':False,'thermal_qualified':False,'assembly_ready':False}
(D/'pcb/local-connectivity.json').write_text(json.dumps(report,indent=2)+'\n')
(D/'study-checkpoint.json').write_text(json.dumps({'status':report['status'],'board':'pcb/'+stage+'.kicad_pcb','sha256':report['board_sha256'],'verification':'pcb/'+stage+'-preservation-audit.json','connectivity':'pcb/local-connectivity.json','promoted_to_main':False,'assembly_ready':False},indent=2)+'\n');print(json.dumps(report,indent=2))
