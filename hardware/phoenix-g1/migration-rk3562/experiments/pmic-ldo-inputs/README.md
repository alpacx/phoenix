# Ingressi PMIC — checkpoint corrente

Il checkpoint `working-candidate.json` deriva da `../system-3v3/working-candidate.json`.
PCB corrente: `pcb/five-volt-testpoint.kicad_pcb`. Continuità/geometria verificate;
nessuna qualifica elettrica o produttiva e nessuna prova fisica di accensione.

## Stato verificato

- 119 coppie di pad collegate, 20 test passati, nessuna nuova violazione DRC.
- 233 reti multi-pad ancora aperte: non è una percentuale di completamento.
- +3V3_SYS distribuita da U17 al PMIC, TP4 e R410; VCC9/VCC8 uniti.
- Ingressi VCC7/VCC8/VCC6/VCC5/VCC_SPK_HP/VCC_RTC/VCC4 collegati.
- R410/R411/C410 collegati localmente; U4.61 (PMIC_VDC) ancora aperto.
- C480, TP4, R410, R411, C410 riposizionati; due elementi GND della baseline
  sostituiti esplicitamente. Pad e gruppi di connessioni preesistenti preservati.
- Il nuovo `vcc9-link` è ACCETTATO: supera il precedente tentativo rifiutato.

## Riproduzione

Usare il Python incluso in KiCad, dalla root, in quest'ordine:

```
python hardware/phoenix-g1/tools/route_pmic_vcc7.py
python hardware/phoenix-g1/tools/route_pmic_vcc8.py
python hardware/phoenix-g1/tools/route_pmic_vcc6.py
python hardware/phoenix-g1/tools/route_pmic_vcc5.py
python hardware/phoenix-g1/tools/route_pmic_audio_input.py
python hardware/phoenix-g1/tools/route_pmic_rail_links.py
python hardware/phoenix-g1/tools/route_pmic_buck_input_link.py
python hardware/phoenix-g1/tools/route_pmic_upper_cap_grounds.py
python hardware/phoenix-g1/tools/route_pmic_upper_cap_power.py
python hardware/phoenix-g1/tools/route_pmic_rtc_link.py
python hardware/phoenix-g1/tools/route_pmic_vcc4_input.py
python hardware/phoenix-g1/tools/route_pmic_vcc9_link.py
python hardware/phoenix-g1/tools/route_system_pmic_feed.py
python hardware/phoenix-g1/tools/route_pmic_vdc_input.py
python hardware/phoenix-g1/tools/route_pmic_vdc_passives.py
python hardware/phoenix-g1/tools/route_cpu_input_feed.py
python hardware/phoenix-g1/tools/route_five_volt_testpoint.py
python hardware/phoenix-g1/tools/audit_pmic_ldo_inputs.py
python hardware/phoenix-g1/tools/test_pmic_ldo_input_audit.py
python hardware/phoenix-g1/tools/inventory_stacked_connectivity.py --checkpoint hardware/phoenix-g1/migration-rk3562/experiments/pmic-ldo-inputs/working-candidate.json
```

## Verifiche ancora necessarie

- Chiudere U4.61, ramo R1803 del display, enable e uscite PMIC.
- Bus 3V3 da 0,8 mm, neck da 0,15 mm e via: corrente, cadute di tensione,
  impedenza e temperatura non qualificate. Nessuna portata nominale attribuita.
- Via-in-pad C425/C481 e C1304/C1305: riempimento e copertura POFV richiesti;
  vedere `pcb/via-in-pad-process-review.json`. Nessuna conferma d'ordine/DFM.
- `pcb/startup-margin-review.json`: partitore 180k/100k/100n, VDC ideale
  1,179 V a 3,3 V e RC 6,43 ms; non sono tempi misurati. Soglie, OTP RK809-5
  e sequenziamento da qualificare, inclusa discrepanza narrativa VB_OK.
- Bypass SoC/DDR/eMMC, routing restante, integrità dei segnali e dissipazione.
- PCB ancora 90×40 mm; obiettivo 85×35 mm non validato.
- Stock e preventivo JLCPCB da riconfermare prima di eventuali ordini.

Correzione nomenclatura: U4.45 è VCC_RTC, U4.66 è VCC4 e U4.33 è
VCC_SPK_HP. I vecchi nomi degli script restano per riproducibilità.

## Ingresso CPU e TP3 — ripresa dopo banco USB

Collegato C1001/C1002/U10 alla distribuzione +5V_MAIN tramite derivazione dal
via esistente (52,6;31,55) e pista da 0,8 mm su In2.Cu, lunga circa 22,59 mm.
Nuovo via 0,6/0,3 mm a (64,5;20,5), raccordo frontale da 0,4 mm ai bypass.
Il punto di misura TP3 sul retro mantiene la posizione originale ed è collegato
tramite via (45,6;32,5) e ramo da 0,3 mm. Dieci elementi aggiunti nei due stadi,
nessun componente mosso né rame preesistente rimosso. Nessun nuovo MPN.

Questo non completa VDD_CPU verso il SoC né qualifica la corrente del percorso:
la derivazione condivide la distribuzione +5V_MAIN esistente e due transizioni
verticali. Verificare corrente cumulativa, metallizzazione dei via, caduta totale,
ritorni e transitori prima di considerarla un'alimentazione utilizzabile.
