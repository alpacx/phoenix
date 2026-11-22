"""Estimate DC resistance of routed copper only, sweeping foil thickness and temperature."""
import hashlib
import json
import math
from pathlib import Path
import pcbnew as p
stage=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda n:json.loads((stage/n).read_text())
cp=read('layout-lpddr-vddq-source.json');src=stage/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));tracks={o.m_Uuid.AsString():o for o in b.GetTracks()}
records=[]
for net,name in [('+1V8_SYS','vdd1-external-pair-trunk.json'),('+1V1_LPDDR4','vddq-rail-first.json')]:
    record,=read(name)['records'];assert record['net']==net
    items=[tracks[k] for k in record['added']]
    # connect_control_groups appends [mate via, two side ties, main via] for each paired transition.
    transitions=0;series=[]
    i=0
    while i<len(items):
        item=items[i]
        if isinstance(item,p.PCB_VIA):
            mate,tie1,tie2,primary=items[i:i+4]
            assert isinstance(primary,p.PCB_VIA) and not isinstance(tie1,p.PCB_VIA) and not isinstance(tie2,p.PCB_VIA)
            assert {tuple(tie1.GetStart()),tuple(tie1.GetEnd())}=={tuple(mate.GetPosition()),tuple(primary.GetPosition())}
            transitions+=1;i+=4
        else:
            series.append(item);i+=1
    total=sum(t.GetLength()/1e6 for t in series)
    assert abs(total-record['length_mm'])<.001
    length={}
    for t in series:length[t.GetLayerName()]=length.get(t.GetLayerName(),0)+t.GetLength()/1e6
    assert all(t.GetWidth()==600000 for t in series)
    estimates=[]
    for inner_um,outer_um in ((18,35),(35,35)):
        for deg in (20,80):
            rho=1.724e-8*(1+.00393*(deg-20))
            ohms=sum(rho*(t.GetLength()*1e-9)/(t.GetWidth()*1e-9*((outer_um if t.GetLayer() in (p.F_Cu,p.B_Cu) else inner_um)*1e-6)) for t in series)
            estimates.append(dict(inner_copper_um=inner_um,outer_copper_um=outer_um,copper_temperature_C=deg,resistance_mohm=1000*ohms,drop_mV_at_0_5_A=500*ohms))
    records.append(dict(net=net,layer_lengths_mm=length,series_length_mm=total,width_mm=.60,paired_transitions_in_trunk=transitions,trace_only_sensitivity=estimates))
(stage/'memory-trunk-dc-estimate.json').write_text(json.dumps(dict(board_sha256=cp['sha256'],copper_resistivity_20C_ohm_m=1.724e-8,temperature_coefficient_per_C=.00393,branches=records,scope='Uniform rectangular copper trace only. Thickness, current and temperatures are scenarios. Omits PMIC, inductors, source entrance, via/contact/bank resistance, etch tolerance and transient response. No voltage margin or current capability has been qualified.',assembly_ready=False),indent=2)+'\n')
print([(r['net'],r['layer_lengths_mm'],[round(v['resistance_mohm'],2) for v in r['trace_only_sensitivity']]) for r in records])
