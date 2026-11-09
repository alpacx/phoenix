#!/usr/bin/env python3
"""Netlist-derived first-order USB input screening; no bench/simulation claims."""
import json,math,re,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    x=ET.parse(ROOT/'review/integrated.xml');components={c.get('ref'):c for c in x.findall('.//components/comp')}
    nets={}
    for n in x.findall('.//nets/net'):
        for pin in n.findall('node'):nets[(pin.get('ref'),pin.get('pin'))]=n.get('name')
    def value(ref):return components[ref].findtext('value')
    def capacitance(v):
        m=re.match(r'([0-9.]+)([pnu])',v)
        return float(m[1])*{'p':1e-12,'n':1e-9,'u':1e-6}[m[2]] if m else None
    caps={rail:[] for rail in ['VBUS_RAW','VBUS_PROTECTED','+5V_MAIN','+3V3_AON']}
    for ref,c in components.items():
        if not ref.startswith('C'):continue
        pins={nets.get((ref,'1')),nets.get((ref,'2'))};cap=capacitance(c.findtext('value',''))
        if cap is None:continue
        for rail in caps:
            if pins=={rail,'GND'}:caps[rail].append({'ref':ref,'nominal_uf':cap*1e6})
    assert value('R1201')=='806R 1%' and value('C1202').startswith('22n')
    r=806;rtol=.01;accuracy=.075
    typ=2000/r+.04
    # Datasheet +/-7.5% used for engineering screening only; full limits at R=806 not tabulated.
    low=(2000/(r*(1+rtol))+.04)*(1-accuracy)
    high=(2000/(r*(1-rtol))+.04)*(1+accuracy)
    slew=42000/(22e-9*1e12) # Eq3: CdVdt[pF] = 42000 / SR[V/ms]
    direct_uf=sum(c['nominal_uf'] for c in caps['+5V_MAIN'])
    current=direct_uf*1e-6*slew*1000
    report={'status':'ENGINEERING SCREEN ONLY - NOT A GUARANTEED POWER BUDGET',
      'source':'https://www.ti.com/lit/ds/symlink/tps2595.pdf',
      'efuse':{'ref':'U15','rilm_ohm':r,'nominal_limit_a':typ,'screen_low_a':low,'screen_high_a':high,
               'remaining_to_3a_at_screen_high_a':3-high,'ron_max_ohm_at_125c_vin_ge4v':.053,
               'loss_at_2a_w':2**2*.053,'drop_at_2a_v':2*.053},
      'direct_shunt_capacitors':caps,
      'startup_typical':{'dvdt_cap_nf':22,'slew_v_per_ms':slew,'rise_to_5v_ms':5/slew,
                         'main_direct_cap_nominal_uf':direct_uf,'main_direct_cap_charge_current_a':current},
      'limits':['Current-range calculation combines typical equation with +/-7.5% screening and1% resistor tolerance; it is not a new guaranteed datasheet limit.',
                'Always-on loads bypass U15 but pass through U24 and must fit in the remaining USB current budget.',
                'Wi-Fi AP6256 is in the netlist and has a dedicated3.584V converter; the module datasheet specifies1A peak at3.3V; complete RK3568/RAM/PHY worst-case budget is still absent.',
                'Direct capacitance excludes IC/package capacitance and downstream converters; startup load is greater than the calculated capacitive current.',
                'MLCC tolerance/DC bias and dVdt tolerance are not included in typical startup figures.',
                'No per-rail worst-case RK3568/RAM/PHY load characterization or converter efficiency budget exists yet.',
                'TPS259531 clamp onset can reach5.9V; 5.7V typical onset must not be treated as a guaranteed5.5V supply ceiling.',
                'U24 upstream guard feeds VBUS_PROTECTED and the always-on loads; U15 separately gates +5V_MAIN. U24 transient response and both-stage loss require qualification.',
                'UVLO, discharge, load transients, USB suspend and thermal qualification remain open.']}
    (ROOT/'review/usb-power-budget.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['efuse','startup_typical']},indent=2))
if __name__=='__main__':main()
