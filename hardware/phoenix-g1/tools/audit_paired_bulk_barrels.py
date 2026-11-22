"""Reload both PMIC rear bulk branches and quantify only the added copper/chosen barrels."""
from pathlib import Path
import hashlib,json,math
import pcbnew as p
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((r/'layout-npu-c434-paired-load.json').read_text());src=r/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();uid=lambda x:x.m_Uuid.AsString();vias={tuple(x.GetPosition()):x for x in b.GetTracks() if isinstance(x,p.PCB_VIA)}
def island(q):return {uid(t) for t in b.GetConnectivity().GetConnectedItems(q)}
ground=island(b.FindFootprintByReference('U4').FindPadByNumber('69'));rows=[]
for report,ref in [('logic-c431-paired-load','C431'),('npu-c434-paired-load','C434')]:
    result=json.loads((r/(report+'.json')).read_text())['winner'];cap=b.FindFootprintByReference(ref);qp,qg=[cap.FindPadByNumber(n) for n in ('1','2')];qids=island(qp);rows0=[]
    for at,path in zip(result['sites'],result['source_branches']):
        via=vias[tuple(at)];assert uid(via) in qids
        lengths=(sum(math.dist(a,z) for a,z in zip(path,path[1:]))/1e6,math.dist(tuple(qp.GetPosition()),at)/1e6)
        rows0.append(dict(site_mm=[k/1e6 for k in at],land_mm=via.GetWidth(p.F_Cu)/1e6,drill_mm=via.GetDrillValue()/1e6,front_path_mm=lengths[0],rear_path_mm=lengths[1]))
    rv=vias[tuple(result['return_via'])];assert uid(rv) in ground and uid(qg) in ground
    gdist=math.dist(tuple(qg.GetPosition()),tuple(rv.GetPosition()))/1e6
    resistance=[]
    for foil_um,plating_um,temp_c in [(35,25,20),(30,20,85)]:
        rho=1.724e-8*(1+.00393*(temp_c-20))
        def rtrace(length_mm):return rho*length_mm*.001/(.0008*foil_um*1e-6)*1e3
        def rbarrel(finished_mm):
            ri=finished_mm*.001/2;rout=ri+plating_um*1e-6
            return rho*.0016/(math.pi*(rout*rout-ri*ri))*1e3
        branches=[rtrace(q['front_path_mm']+q['rear_path_mm'])+rbarrel(q['drill_mm']) for q in rows0]
        resistance.append(dict(foil_um=foil_um,plating_um=plating_um,temp_c=temp_c,isolated_branch_mohm=branches,ideal_independent_parallel_mohm=1/sum(1/x for x in branches),shorter_branch_only_mohm=min(branches),rear_ground_trace_only_mohm=rtrace(gdist)))
    rows.append(dict(ref=ref,feed=rows0,return_site_mm=[k/1e6 for k in rv.GetPosition()],return_drill_mm=rv.GetDrillValue()/1e6,rear_ground_trace_mm=gdist,resistance_cases=resistance))
(r/'paired-bulk-barrel-model.json').write_text(json.dumps(dict(board_sha256=base['sha256'],rows=rows,assumptions=dict(copper_resistivity_ohm_m_at_20C=1.724e-8,board_thickness_mm=1.6,drill_interpretation='finished diameter assumed for the annular barrel model',trace_width_mm=.8),limitations='DC conductor estimate only. Shared copper at the branch ends, land spreading, planes, capacitor ESR/ESL and switching-loop impedance are excluded. These are not measured operating currents, temperatures or load regulation.'),indent=2)+'\n')
print([(q['ref'],q['rear_ground_trace_mm'],[c['ideal_independent_parallel_mohm'] for c in q['resistance_cases']]) for q in rows])
