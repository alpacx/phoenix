#!/usr/bin/env python3
"""Allocate simultaneous interfaces by exact manufacturer function names."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'migration-rk3562/review'
rows=list(csv.DictReader((ROOT/'manufacturer-pins.csv').open()));funcs={}
for row in rows:
 for f in row['name'].split('/'):funcs.setdefault(f,[]).append(row['ball'])
p=ROOT/'initial-function-allocation.json';v=json.loads(p.read_text());signals=v['signals'];by_net={s['net']:s for s in signals};used={s['soc_ball']:s['net'] for s in signals}
def add(f,net):
 assert len(funcs.get(f,[]))==1,(f,funcs.get(f));b=funcs[f][0]
 if net in by_net:assert by_net[net]['soc_ball']==b;return
 assert b not in used,(f,b,used.get(b));s={'net':net,'soc_ball':b,'function':f};signals.append(s);by_net[net]=s;used[b]=net
for s in ['TXD0','TXD1','TXD2','TXD3','TXEN','TXCLK','RXD0','RXD1','RXD2','RXD3','RXCLK','RXDV','MDC','MDIO']:
 add('RGMII_'+s+'_M0','ETH_'+('RXDV_CRS' if s=='RXDV' else s))
for s in ['D0','D1','D2','D3','CMD','CLK']:add('SDMMC1_'+s,'WIFI_'+s)
for s in ['D0','D1','D2','D3','CLK']:add('FSPI_'+s,'FSPI_'+s)
add('FSPI_CSN0','FSPI_CS_N')
for f,n in [('SPI2_MOSI_M0','LCD_MOSI'),('SPI2_CLK_M0','LCD_SCLK'),('SPI2_CSN0_M0','LCD_CS_N')]:add(f,n)
for f,n in [('PWR_CTRL0','PMIC_SLEEP'),('GPIO0_A3_u','PMIC_INT_N')]:add(f,n)
# Signal allocation only; IO domains and startup levels still require electrical review.
for f,n in [('nPOR','RESET_N'),('SARADC0_BOOT','RECOVERY_ADC'),('UART0_TX_M0','DEBUG_TX'),('UART0_RX_M0','DEBUG_RX'),('TSADC_SHUT_M0','THERMAL_SHUTDOWN'),('SPI0_CLK_M0','EXP_SPI_CLK'),('SPI0_MOSI_M0','EXP_SPI_MOSI'),('SPI0_MISO_M0','EXP_SPI_MISO'),('SPI0_CSN0_M0','EXP_SPI_CS0_N'),('SPI0_CSN1_M0','EXP_SPI_CS1_N'),('I2C2_SCL_M0','EXP_I2C_SCL'),('I2C2_SDA_M0','EXP_I2C_SDA'),('UART1_TX_M0','EXP_UART_TX'),('UART1_RX_M0','EXP_UART_RX'),('GPIO3_C4_d','LCD_DC'),('GPIO3_C5_d','LCD_RESET_N'),('PWM8_M0','LCD_BL_PWM'),('GPIO1_C7_d','WIFI_REG_ON'),('GPIO1_D0_d','WIFI_HOST_WAKE'),('GPIO4_B1_d','ETH_RESET_GPIO_N'),('GPIO3_A2_d','EXP_GPIO0'),('GPIO3_A3_d','EXP_GPIO1'),('GPIO3_A5_d','EXP_GPIO2'),('GPIO3_A7_d','EXP_GPIO3')]:add(f,n)
v['mux_rationale']='RGMII M0 avoids SDMMC1 Wi-Fi conflict on RGMII M1; display SPI2 M0 avoids RGMII M0 pins shared with SPI1 M0.'
v['holds']=['IO-bank voltage audit remains required','GPIO controls, expansion, reset, supplies, strap behavior and unused interfaces not yet allocated','NOR boot support and DDR loader not validated']
p.write_text(json.dumps(v,indent=2)+'\n');print(len(signals),'unique allocated signals')
