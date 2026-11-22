#!/usr/bin/env python3
"""Check proposed SDIO allocation against current SoC netlist; no circuit approval."""
import csv,json,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    rows=list(csv.DictReader((ROOT/'review/rk3568-manufacturer-pins.csv').open()))
    tree=ET.parse(ROOT/'review/integrated.xml')
    nets={n.get('pin'):net.get('name') for net in tree.findall('.//nets/net') for n in net.findall('node') if n.get('ref')=='U1'}
    # AP6256 datasheet pp13-14: signal/pin pairs, independent of imported CAD.
    mapping=[('SDMMC1_D0','18','WIFI_D0'),('SDMMC1_D1','19','WIFI_D1'),('SDMMC1_D2','14','WIFI_D2'),('SDMMC1_D3','15','WIFI_D3'),('SDMMC1_CMD','16','WIFI_CMD'),('SDMMC1_CLK','17','WIFI_CLK'),('SDMMC1_PWREN','12','WIFI_REG_ON'),('SDMMC1_DET','13','WIFI_HOST_WAKE')]
    module={n.get('pin'):net.get('name') for net in tree.findall('.//nets/net') for n in net.findall('node') if n.get('ref')=='U25'}
    assert module, 'Wi-Fi module absent from integrated netlist'
    result=[]
    for function,pin,target in mapping:
        matches=[r for r in rows if function in r['functions'].split(' | ')]
        assert len(matches)==1,function
        row=matches[0];existing=nets.get(row['ball'])
        assert row['power_domain']=='VCCIO4',function
        assert existing==target,(function,existing)
        assert module[pin]==target,(pin,module.get(pin))
        result.append({'soc_function':function,'soc_ball':row['ball'],'module_pin':pin,'planned_net':target,'existing_net':existing})
    assert len({r['soc_ball'] for r in result})==8
    for pin in ['1','3','20','31','33','36','29','34']:assert module[pin]=='GND',(pin,module.get(pin))
    for pin,net in {'9':'WIFI_VBAT','22':'+3V3_IO','23':'WIFI_BUCK_OUT','21':'WIFI_BUCK_SW','24':'WIFI_LPO','10':'WIFI_XIN','11':'WIFI_XOUT','2':'WIFI_RF'}.items():assert module[pin]==net
    for pin in ['4','5','8','30','32','35','45','46','47']:assert module.get(pin,'unconnected-').startswith('unconnected-')
    report={'status':'PASS INTEGRATED SDIO CONNECTIVITY; NOT FUNCTIONALLY QUALIFIED','connections':result,'io_voltage_V':3.3,'module_SDIO_VSEL_pin29':'GND for 3.3V IO, per module datasheet','module_BT_REG_ON_pin34':'Must be driven low when Bluetooth disabled; not floating','clock':{'module_pin':'24','frequency_Hz':32768,'required_accuracy_ppm':30,'candidate_jlc':'C5274152','status':'Stock checked; exact oscillator total accuracy, jitter, footprint and supply range not qualified','existing_PMIC_clock':'RK809 CLK32K currently NC, external crystal absent; RC clock not accepted without accuracy evidence'},'power':{'module_VBAT_peak_A':1,'nominal_voltage_V':3.584,'additional_peak_USB_input_A_at_5V_90pct_efficiency':round(3.584/(5*.9),3),'note':'Illustrative conversion only, not a complete USB load budget; module IO and converter tolerances excluded'},'integration_holds':['Oscillator load/drive, internal-buck component ratings and assembly land-pattern qualification','Dedicated3.584V regulator current/transient and sequencing validation','Linux firmware/NVRAM and hotspot mode','Antenna RF routing and exact land pattern']}
    (ROOT/'review/wifi-allocation-check.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status']);print('8 signal assignments checked; illustrative USB peak', report['power']['additional_peak_USB_input_A_at_5V_90pct_efficiency'], 'A')
if __name__=='__main__':main()
