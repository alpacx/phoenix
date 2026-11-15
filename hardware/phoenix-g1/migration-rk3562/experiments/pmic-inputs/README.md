# Ingressi PMIC — candidato geometrico, non qualificato
Checkpoint: working-candidate.json. Baseline intatta: ../pmic-buck5/working-candidate.json.

## Verificato nel CAD
- C422 spostato da B(54,10.5) a F(54,11.5), orientamento 180°; R1814 non collegato spostato a F(51,10.5).
- VCC2 U4.10 collegato al positivo C422; precedente pista di massa sostituita esplicitamente, mantenendo il via GND (52.1,10.5).
- VCC1 U4.11 collegato al positivo C421; C421.2 collegato a GND.
- Entrambi gli ingressi sono sulla stessa rete +3V3_SYS. Questo non prova che la sorgente a monte sia collegata.
- 25 coppie locali verificate, inclusi i collegamenti BUCK5 preesistenti; preservati 2005 pad e i gruppi connessi della baseline.
- Nessuna nuova violazione DRC individuale. Restano 125 avvisi e 239 reti multi-pad aperte.
- Test del controllo di preservazione: 7 superati, inclusi casi negativi di sostituzione rame.

## Riproduzione
Dalla root, con Python pcbnew di KiCad:
1. tools/place_route_pmic_buck2_front.py
2. tools/route_pmic_buck1_input.py
3. tools/route_pmic_buck4_input.py
4. tools/route_pmic_ground_pins.py
5. tools/audit_pmic_inputs.py
6. tools/inventory_stacked_connectivity.py --checkpoint <questo studio>/working-candidate.json

I percorsi tools sono relativi a hardware/phoenix-g1.
Gli script rifiutano hash sorgente diversi da quelli dei rispettivi checkpoint.
route_pmic_buck2_input.py conserva una prova sul retro respinta per conflitti con l'espansione. Non usarne il PCB.
Eventuali altre prove non entrano nel checkpoint finché l'audit non le accetta.

## Limiti
Neck locali da 0.127 mm, piste principali da 0.5 mm; corrente, caduta, loop di ritorno e stabilità non qualificati.
Pin verificati documentalmente su RK809-5 Rev2.3: pin10 VCC2, pin11 VCC1.
Nessuna simulazione elettrica o prova fisica. Processo via-in-pad, dissipazione, bypass restanti, routing generale e dimensione finale rimangono da verificare.
Nessun nuovo componente selezionato: disponibilità/prezzi non ricontrollati in questo passaggio.

## VCC_RTC e ritorni di massa
Il nome storico dello script `route_pmic_buck4_input.py` è impreciso: U4.45 è VCC_RTC, mentre VCC4 è U4.66. Il cablaggio non cambia. C424 resta nella posizione originale: positivo collegato a U4.45 (VCC_RTC), massa al via esistente (65.3,5.25).
Dieci pin di massa U4 (14,15,16,17,19,40,47,56,62,63) collegati al pad esposto.
Tutte le dieci istanze del pad 69 sono fisicamente connesse: un pad centrale e nove fori metallizzati già presenti, diametro 0.3 mm.
Una prova di nuovi via sovrapposti è stata respinta: pmic-ground.kicad_pcb NON è il checkpoint.
I dieci raccordi di massa sono larghi 0.15 mm (come i pad), lunghi meno di 1 mm.
Regola locale di larghezza limitata alle piste GND che intersecano il courtyard U4; clearance invariata.
Non si tratta di una qualifica di corrente o di un'approvazione del processo via-in-pad.

## VCC3 ancora aperto
La prova buck3-input è respinta: l'area davanti ai pin inferiori è occupata anche dall'induttore L1001 e dal circuito sul retro U25.
Non promuovere tale PCB. La disposizione di C423 richiede riesame con il percorso di potenza BUCK3, senza spostare alla cieca L1001.
