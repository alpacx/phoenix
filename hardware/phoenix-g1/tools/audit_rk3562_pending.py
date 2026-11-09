#!/usr/bin/env python3
"""Inventory every unresolved ball without silently converting it to NC."""
import csv,json,re,collections
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'migration-rk3562/review'
used={x['soc_ball'] for x in json.loads((R/'initial-function-allocation.json').read_text())['signals']}
used|={x['ball'] for x in json.loads((R/'candidate-power-map.json').read_text())['pins']}
out=[]
for p in csv.DictReader((R/'manufacturer-pins.csv').open()):
 if p['ball'] in used:continue
 n=p['name'];category='REVIEW';action='Resolve against hardware guide before assigning an electrical disposition.'
 if 'GPIO' in n:category='UNUSED_MULTIPLEXED_GPIO';action='No selected interface uses this ball. Unconnected externally by design. Firmware must keep this unused pad in a safe input/bias state; reset defaults and boot behavior still require bring-up verification. No external function or voltage strap is assigned.'
 elif 'AVDD' in n or n=='OTP_VCC_1V8':category='UNRESOLVED_SUPPLY';action='Must determine powered versus unpowered requirement even when peripheral is unused. Never mark NC based only on unused function.'
 elif n in ('DDR_RZQ','DDR_VREFOUT'):category='REQUIRED_DDR_SUPPORT';action='Obtain DDR3-specific connection prescription. Existing DDR3 support net is deliberately not assumed valid for RK3562.'
 elif 'DDR3_' in n:category='UNUSED_DDR_ADDRESS_OR_RANK';action='Two x16 2Gbit devices share one rank; H5TQ2G63GFR Rev1.2 addressing table requires A0..A13 for x16, so A14/A15 are unused; CS1/ODT1 have no second-rank loads. Leave these outputs unconnected and configure loader for one 32-bit rank.'
 elif n.startswith('SARADC'):category='UNUSED_ANALOG_INPUT';action='Tie dedicated unused SARADC inputs to GND so they cannot float. These balls have no alternate function in the manufacturer pin table; boot ADC is separately allocated and excluded.'
 elif n.startswith(('MIPI','PCIE20_REFCLK','USB20_HOST')):category='UNUSED_HIGH_SPEED_INTERFACE';action='Interface has no external connection in Phoenix: leave signal balls NC and disable the unused receiver/transmitter in firmware. Analog supplies are handled separately and are NOT assumed removable.'
 elif n=='USB30_OTG0_ID':category='DEVICE_ROLE_CONTROL';action='NC by design for fixed UFP/device role. RK3562 TRM Part1 PDFp391 GRF_USBPHY_CON0: ID pull-up reset=1; IDDIG override is available. Firmware must select peripheral role, retain ID bias and never enable host VBUS. Boot-ROM/device enumeration remains a bench test.'
 out.append({'ball':p['ball'],'name':n,'category':category,'action':action,'schematic_disposition':('NC_BY_DESIGN' if category in ('UNUSED_MULTIPLEXED_GPIO','UNUSED_DDR_ADDRESS_OR_RANK','UNUSED_HIGH_SPEED_INTERFACE','DEVICE_ROLE_CONTROL') else 'GND_BY_DESIGN' if category=='UNUSED_ANALOG_INPUT' else 'PENDING; unchanged')})
assert len(out)+len(used)==478
report={'status':'UNALLOCATED BALLS CLASSIFIED; UNUSED SIGNALS HAVE EXPLICIT NC/GND DISPOSITIONS; SUPPLIES AND REQUIRED SUPPORT REMAIN OPEN','counts':dict(collections.Counter(p['category'] for p in out)),'pins':out,'production_ready':False}
(R/'pending-pin-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(report['counts'])
