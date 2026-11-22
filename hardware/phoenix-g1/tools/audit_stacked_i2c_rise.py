"""Apply single-ended quasi-TEM C' to actual expansion I2C copper on each candidate stack."""
from collections import Counter
from pathlib import Path
import hashlib,json,math,os
import pcbnew as p
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'layout-exp-sda-complete.json').read_text());src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));sim=json.loads((root/'usb-ddr-stack-simulation.json').read_text())
data={}
for net,ref in [('EXP_I2C_SCL','R2102'),('EXP_I2C_SDA','R2101')]:
    items=[t for t in b.GetTracks() if t.GetNetname()==net];lengths=Counter();res=b.FindFootprintByReference(ref);assert res.GetValue()=='4.7k'
    for t in items:
        if not isinstance(t,p.PCB_VIA):lengths[t.GetLayerName(),t.GetWidth()/1e6]+=t.GetLength()/1e6
    results={}
    for name,s in sim['stacks'].items():
        total=0;detail=[]
        for (layer,width),length in sorted(lengths.items()):
            family='outside' if layer in ('F.Cu','B.Cu') else 'inner'
            assert layer in ('F.Cu','B.Cu','In2.Cu','In3.Cu')
            models=sorted((x for x in s[family] if x['mode']=='single'),key=lambda x:x['width_mm'])
            lo=max((x for x in models if x['width_mm']<=width),key=lambda x:x['width_mm'])
            hi=min((x for x in models if x['width_mm']>=width),key=lambda x:x['width_mm'])
            coeff=lambda m:1e9*math.sqrt(m['effective_er'])/(299792458*m['ohms'])
            factor=(width-lo['width_mm'])/(hi['width_mm']-lo['width_mm']) if hi!=lo else 0
            cap=length*(coeff(lo)+(coeff(hi)-coeff(lo))*factor)
            total+=cap;detail.append(dict(layer=layer,width_mm=width,length_mm=length,simulation_width_bracket_mm=[lo['width_mm'],hi['width_mm']],capacitance_pF=cap))
        results[name]=dict(trace_capacitance_pF=total,trace_only_rise_ns=.8473*4700*total*.001,copper_groups=detail,
                           remaining_pF_before_other_loads={m:tr*1000/(.8473*4700)-total for m,tr in [('100kHz',1000),('400kHz',300),('1MHz',120)]})
    data[net]=dict(copper_length_mm=sum(lengths.values()),via_count=sum(isinstance(t,p.PCB_VIA) for t in items),pullup_ohms=4700,stacks=results)
result=dict(board_sha256=cp['sha256'],networks=data,model='Trace capacitance from C per length = sqrt(effective_er)/(c * Z0); 30%-70% rise = 0.8473 R C. Nominal pull-up.',
            excluded=['Via and pad capacitance, connector, attached accessory, IC pin capacitance, package, guard-band on R, switching aggressors and parasitic power paths.','Probe board plus accessory at each selected I2C mode. Check VOL/sink capability and clock stretching separately.'],
            reference='https://www.ti.com/lit/an/slva689/slva689.pdf',assembly_ready=False)
(root/'exp-i2c-rise-estimate.json').write_text(json.dumps(result,indent=2)+'\n');print([(n,round(d['copper_length_mm'],2),[(s,round(m['trace_capacitance_pF'],1)) for s,m in d['stacks'].items()]) for n,d in data.items()],flush=True);os._exit(0)
