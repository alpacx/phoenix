# Evidenze hardware e cablaggio

## Verificato

Il 2026-11-05 esptool identifica la scheda su `/dev/cu.usbmodem5B901859211`
come ESP32-P4 v3.1, quarzo 40 MHz. Bridge USB VID:PID 1A86:55D3.
La revisione PCB non è leggibile tramite esptool: resta da confrontare fisicamente.

[Documentazione Waveshare](https://docs.waveshare.com/ESP32-P4-NANO):
32 MB PSRAM, 16 MB NOR; USB-C per seriale, Type-A per OTG HS. La memoria
fisica va confrontata con flash_id e test PSRAM; PSRAM non ancora abilitata.

[Schema ufficiale](https://files.waveshare.com/wiki/ESP32-P4-NANO/ESP32-P4-NANO-schematic.pdf),
archiviato in hardware/, esaminato visivamente:

| Funzione | GPIO P4 |
|---|---|
| IP101 RMII TX_EN/TXD0/TXD1 | 49 / 34 / 35 |
| CRS_DV/RXD0/RXD1 | 28 / 29 / 30 |
| MDC/MDIO/RESET/REF_CLK esterno | 31 / 52 / 51 / 50 |
| C6 SDIO CLK/CMD/D0/D1/D2/D3 | 18 / 19 / 14 / 15 / 16 / 17 |
| C6 EN / IO2 | 54 / 6 |
| UART programmazione | 37 / 38 |
| BOOT | 35, condiviso con TXD1 |
| I2C scheda | 7 / 8 |

U2 DIO7003 alimenta VBUS_OUT da VCC_5V, EN collegato tramite R2.
R12 è un bypass opzionale NC/0R. La Type-A usa VBUS_OUT; USB-C ha USB0_5V.
Non è dimostrata l'assenza di conflitto tra due sorgenti VBUS.

## Fixture USB richiesta, non realizzata

Proposta per banco: scheda autoalimentata da USB-C; D+/D-/GND verso host,
VBUS dell'host elettricamente separata da VBUS_OUT della scheda e monitorata
tramite circuito adatto a 3.3 V su GPIO5 (P1 pin 11, riservato).
Non applicare 5 V direttamente a un GPIO. Verificare schema reale, popolamento
R12/U2, continuità a scheda spenta, tensioni e assenza di ritorni di corrente.
Il progetto non certifica un adattatore/cavo commerciale. USB NCM è abilitabile
solo in una build laboratorio con sensing GPIO5; il default rimane spento.
Descrittori self-powered, consumo VBUS dichiarato 0 mA, nessun remote wakeup.

## Versioni e ipotesi

L'SDK locale distingue in modo mutuamente esclusivo silicio <3.0 e >=3.0
(`components/esp_hw_support/port/esp32p4/Kconfig.hw_support`). La build v3 usa
revision minima 3.0 e supporta la v3.1 rilevata. PHY address è autodetect,
non inventato; va registrato sul banco. Nessun GPIO touch assegnato.
C6 presente da schema, firmware slave e versione ancora da interrogare.
MicroSD/audio/display occupano ulteriori GPIO: non riusarli senza verifica.
