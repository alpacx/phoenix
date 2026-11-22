#!/usr/bin/env python3
"""Static worst-case calculations. These do not replace transient/thermal tests."""
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def divider(top,bottom,tolerance):
    low=.784*(1+top*(1-tolerance)/(bottom*(1+tolerance)))
    high=.816*(1+top*(1+tolerance)/(bottom*(1-tolerance)))
    return {'r_top_ohm':top,'r_bottom_ohm':bottom,'resistor_tolerance':tolerance,
        'nominal_v':.8*(1+top/bottom),'min_v':low,'max_v':high,
        'margin_to_ddr_min_v':low-1.425,'margin_to_ddr_max_v':1.575-high}

def main():
    proposed=divider(105000,120000,.001)
    reference=divider(110000,120000,.01)
    # Conservative ideal CCM calculation at the chosen operating envelope.
    # Vendor FNR5020SR24NT: +/-30% L, DCR max 11mOhm at its specified conditions.
    vin=5.5;vout=1.5;frequency=2.2e6;inductance=.24e-6*.7;load=4
    ripple=vout*(1-vout/vin)/(inductance*frequency)
    rms=math.sqrt(load**2+ripple**2/12)
    result={
        'status':'DESIGN CALCULATIONS ONLY - no simulation, measurement or release approval',
        'ddr_limits_v':[1.425,1.575],
        'ddr_feedback_reference_v':[.784,.8,.816],
        'ddr_proposed_divider':proposed,
        'ddr_divider_with_independent_25ppm_drift_60C':divider(105000,120000,.001+25e-6*60),
        'ddr_rockchip_reference_divider':reference,
        'ddr_notes':['Source: RK809 Rev2.3 external-divider Vfb3 limits; Hynix Rev1.2 supply limits.',
            'Selected RT0603BRD07105KL C861072 and RT0603BRD07120KL C705720: 0603,0.1%,25ppm/C. Stock observation saved.',
            'Separate temperature screen includes independent25ppm/C drift over60C from reference; ripple, transients, aging and PCB IR drop remain excluded.',
            'Do not treat the typical 17mV transient number in the PMIC datasheet as a guaranteed maximum.'],
        'cpu_inductor_screen':{
            'part':'FNR5020SR24NT','load_assumption_a':load,'vin_v':vin,'vout_v':vout,
            'switching_frequency_hz':frequency,'inductance_min_h':inductance,
            'ideal_ripple_peak_to_peak_a':ripple,'ideal_peak_a':load+ripple/2,
            'ideal_rms_a':rms,'copper_loss_w_at_11_milliohm':rms*rms*.011,
            'datasheet_current_values_a':{'isat_column_max':8,'isat_typical':10,'irms_column_max':5.3,'irms_typical':6},
            'qualification':'Candidate only. NOT a 6A continuous stage qualification. Hot inductance, derating, fault current and closed-case temperature unresolved.'},
        'cpu_capacitance':{'regulator_nominal_uf':88,'required_soc_nominal_uf':132,
            'total_nominal_uf':220,'vendor_minimum_uf':135,
            'required_total_retention_fraction':135/220,
            'notes':'Effective capacitance must be checked using exact MPN bias/temperature curves; nominal sums do not establish compliance.'},
        'usb_boot_policy':{'mode':'UFP sink only, no PD','requested_envelope':'5V, Type-C 3A advertisement',
            'start_condition':'OUT1==0 AND OUT2==0 AND valid supply sequencing',
            'notes':['HD3SS3220 Table6-3: OUT1=1 OUT2=0 is default-current, NOT 3A.',
                'On insufficient current keep main rails disabled; no assumption that every Mac port provides 3A.',
                'Current gating, eFuse and always-on supply are drafted; physical ramp and brownout validation remain.']}}
    assert proposed['margin_to_ddr_min_v']>0 and proposed['margin_to_ddr_max_v']>0
    (ROOT/'review/power-margins.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f"DDR proposed static range {proposed['min_v']:.4f}-{proposed['max_v']:.4f} V; dynamic margins still to qualify.")
    print(f'CPU screening at 4A: ideal peak {load+ripple/2:.3f}A, copper loss {rms*rms*.011:.3f}W (not total loss).')

if __name__=='__main__':main()
