#!/usr/bin/env python3
"""ERC direction model for the selected operating functions, not pad-cell specs."""
import json,collections
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'migration-rk3562/review'
a=json.loads((R/'initial-function-allocation.json').read_text())['signals'];rows=[]
inputs={'SOC_VBUS_DET','XIN24M','RESET_N','RECOVERY_ADC','DEBUG_RX','EXP_SPI_MISO','EXP_UART_RX','WIFI_HOST_WAKE','PMIC_INT_N'}
outputs={'XOUT24M','WIFI_CLK','FSPI_CLK','FSPI_CS_N','DEBUG_TX','THERMAL_SHUTDOWN','EXP_SPI_CLK','EXP_SPI_MOSI','EXP_SPI_CS0_N','EXP_SPI_CS1_N','EXP_UART_TX','WIFI_REG_ON','ETH_RESET_GPIO_N','PMIC_SLEEP','ETH_MDC'}
for s in a:
 n=s['net'];kind=None;basis='Selected function direction; pinmux must select this function before enabling output.'
 if n.startswith('DDR3_'):kind='bidirectional' if n.startswith('DDR3_DQ') else 'output';basis='DDR3 controller role: DQ/DQS read/write; address, control, clock and DM driven by controller.'
 elif n.startswith(('SOC_USB_RX_','ETH_RX')) or n in inputs:kind='input'
 elif n.startswith(('SOC_USB_TX_','ETH_TX','LCD_')) or n in outputs:kind='output'
 elif n in ('USB_DP','USB_DM','ETH_MDIO') or n.startswith(('I2C','EXP_I2C','EXP_GPIO','WIFI_D','WIFI_CMD','FSPI_D')):kind='bidirectional'
 assert kind, n
 rows.append({'ball':s['soc_ball'],'net':n,'function':s['function'],'erc_type':kind,'basis':basis})
(R/'signal-electrical-types.json').write_text(json.dumps({'status':'LOGICAL ERC MODEL; NOT ELECTRICAL CHARACTERISTICS OR RESET-STATE QUALIFICATION','pins':rows,'counts':dict(collections.Counter(p['erc_type'] for p in rows))},indent=2)+'\n');print(len(rows),'signal directions modelled')
