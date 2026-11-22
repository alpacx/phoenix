# Alimentazioni di avvio — routing locale, non qualifica

Checkpoint corrente: working-candidate.json. Baseline preservata: ../aux-mount-clear.
Non è un circuito pronto da alimentare né una scheda producibile.

## Collegamenti verificati nel CAD
- U4.24 (VCC3) → C423.1 e ritorno C423.2 a massa. C423 portato sul fronte.
- L1001 ruotato e spostato; via GND Wi-Fi a (59.4,15.4) trasferito a (59.4,17.2), prolungando il ramo sul retro.
- U10 ruotato 180°: quattro ball LX collegati a L1001.1, quattro VIN ai due condensatori C1001/C1002.
- U10: sette ball di massa collegati; ritorni di massa C1001/C1002.
- L1001.2 collegato a C1013/C1012 sul fronte e C1011 sul retro, con ritorni di massa.
- R1001/C1020 riposizionati e collegati ad A4. Il ramo Kelvin parte dal lato C1012; non è il percorso di corrente del carico.
- R1002 riposizionato e collegato localmente ad A2 (enable).
- L402/L403 ancora non instradati, riposizionati per liberare il banco CPU. Nessun valore, MPN o net cambiato.

Audit complessivo: 64 coppie di pad, inclusi i collegamenti PMIC e LCD precedenti.
Conservati 2006 pad e tutti i gruppi fisici della baseline; un solo via preesistente spostato esplicitamente.
Nessuna nuova violazione DRC individuale. Restano 125 avvisi via_dangling.
Reti multi-pad aperte: 236 contro 239 nella baseline. Non è una percentuale di completamento.

## Riproduzione
Dalla root, Python pcbnew KiCad; script sotto hardware/phoenix-g1/tools:
1. route_startup_vcc3.py
2. route_startup_cpu_switch.py
3. route_startup_cpu_caps.py
4. route_startup_cpu_output_bank.py
5. route_startup_cpu_feedback.py
6. route_startup_cpu_enable.py
7. audit_startup_power.py
8. inventory_stacked_connectivity.py --checkpoint hardware/phoenix-g1/migration-rk3562/experiments/startup-power/working-candidate.json
9. test_startup_power_audit.py

I report di ogni stadio devono avere stato accettato prima di proseguire.
Il checkpoint è scritto solo dall'audit finale. Le copie per le prove negative non sono promosse.

## Riferimento e limiti elettrici
RK860-0, datasheet locale Rev1.2:
- pp.4/6: VIN 2.7–5.5 V operativi, 6 V absolute maximum; A4 deve rilevare il lato condensatore.
- Induttore raccomandato 0.22–0.47 uH; COUT 44–88 uF; ingresso almeno due 10 uF nella descrizione pin.
- La capacità nominale collegata localmente è 2×22 uF all'ingresso, 3×22 uF all'uscita.
  C1014 (ulteriori 22 uF) resta non instradato; DC bias, tolleranze e transitori non sono qualificati.
- Capacità di corrente 6 A dichiarata per il chip, NON per queste piste.
  I neck da 0.2 mm, dorsale LX da 0.8 mm, ritorni e vias richiedono verifica di perdite e riscaldamento.
- Valori RC di R1001/C1020 conservati dal progetto; non è stata verificata la stabilità del loop.
- Il guard USB precedente ha soglia OVP statica massima circa 5.846 V: non garantisce VIN≤5.5 V in guasto.
  Non confondere il limite operativo con quello assoluto; transitori e selettività restano da qualificare.

Ancora aperti: alimentazione a monte dei condensatori CPU, sorgente +3V3_PMU dell'enable,
I²C/VSEL, distribuzione VDD_CPU al SoC, regolatore 3.3 V di sistema e distribuzione al PMIC,
altre alimentazioni, memoria, routing generale e qualifica SI/PI/termica.
Il PCB resta 90×40 mm, target 85×35 non dimostrato. Nessun test fisico, ordine o nuovo componente.
Disponibilità/prezzi non ri-verificati: non c'è una nuova selezione di componenti in questo passaggio.

### Carico complessivo del convertitore CPU

Sul [checkpoint CA1](../phy-power-parallel/layout-command-ca1.json), tre condensatori da 22 µF raggiungono sia L1001.2 sia la massa di U10.B4. La [verifica di tutti i condensatori](../phy-power-parallel/cpu-external-buck-cap-budget.json) trova **66 µF nominali collegati** e **224,8 µF nominali previsti a cablaggio completo**. Il conteggio comprende 88 µF presso il convertitore e 136,8 µF presso il SoC. C1020 appartiene alla compensazione del feedback ed è escluso dalla somma.

La scheda di riferimento RK3562 Oomwoo, foglio 4, usa per VDD_CPU C1000 da 100 nF, C1001–C1003 da 1 µF e C1004–C1005 da 22 µF, pari a 47,1 µF nominali presso il SoC. Il foglio 16 usa una distribuzione di potenza diversa da Phoenix. Copiarne la popolazione sul nostro convertitore richiederebbe comunque una verifica del circuito completo. [Schema di riferimento](../../../reference/rk3562-oomwoo-reference.pdf)

La capacità nominale popolata da Phoenix è 2,55 volte il limite superiore raccomandato, 88 µF. Per rientrare in quel valore per sola riduzione della capacità, i componenti dovrebbero fornire meno del 39,2% della somma nominale. I dieci condensatori da 22 µF sono Samsung CL21A226MOCLRNC. A 1,0 V la caratteristica tipica indica −7,61%, pari a 203,27 µF per i dieci componenti; a 1,5 V indica 185,84 µF complessivi. Samsung dichiara 25 °C, 120 Hz e stimolo di 0,5 V per questa caratteristica. Restano da valutare l’impedenza alla frequenza dell’anello, la distribuzione del rame e la risposta al gradino di carico. [Curva Samsung](https://product.samsungsem.com/mlcc/CL21A226MOCLRN.do) · [Calcolo per la distinta attuale](../phy-power-parallel/cpu-output-cap-bias.json) Il datasheet non fornisce una deroga per i condensatori lato SoC. Il confronto evidenzia un rischio di stabilità e avvio da risolvere prima della produzione. [RK860, pp. 5–6](../../../reference/RK860-0-C19188628.pdf)
