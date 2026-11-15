# Fissaggio H8103 e bypass display — candidato non qualificato

Checkpoint corrente: working-candidate.json. Deriva dal checkpoint pmic-inputs, conservato.

## Modifiche CAD verificate
- C1801 (1u / 10V) da (23.5,2) a (29.25,34.25), vicino all'ingresso U20.
- C1802 (2.2u / 10V) da (21,2) a (24.5,34.25), ruotato 180°, vicino all'uscita U20.
- R1815, pull-up LCD_CS_N non ancora instradato, da (23,4) a (20,6.5).
- H8103: foro NPTH 2.2 mm a (21,3), riserva corpo raggio 2.7 mm libera sui due lati.
  Escluso da BOM e file posizionamento; fissaggio M2 candidato, non qualificato con il case.
- Collegamenti U20.1–C1801.1 e U20.5–C1802.1, ritorni GND e ingresso al bus +5V_MAIN esistente su In3.
- Le piste locali sono 0.3 mm; tre via da 0.6/0.3 mm, esterni ai pad di saldatura.
- Sei coppie di pad controllate; i 48 gruppi già connessi della baseline preservati.
- Tutte le altre impronte conservano posizione, rotazione e lato. Regole DRC/progetto immutate.
- Nessuna nuova violazione individuale; restano 125 avvisi e 239 reti multi-pad aperte.

## Rigenerazione
Dalla root, usare il Python fornito con KiCad sui seguenti script in hardware/phoenix-g1/tools:
1. clear_aux_mount_h8103.py
2. add_aux_mount_h8103.py
3. route_lcd_bypass.py
4. audit_aux_mount_clear.py
5. inventory_stacked_connectivity.py --checkpoint hardware/phoenix-g1/migration-rk3562/experiments/aux-mount-clear/working-candidate.json

Le prove intermedie non sostituiscono il checkpoint finché l'audit finale non passa.

## Limiti e continuazione
H8101/H8102/H8103 sono ora fori reali nel CAD; H8104/H8105 sono ancora riserve.
La ricerca geometrica nella baseline pmic-inputs non trovava cerchi liberi da 5.4 mm nel target 85x35:
non dimostra impossibilità, ma richiede ricollocazioni. Il PCB resta 90x40.

LDO U20: ingresso e bypass locali collegati; enable +3V3_IO e distribuzione al display ancora da completare.
Non dichiarare display alimentato/funzionante. Stabilità con capacità effettiva, dissipazione e avvio non provati.
Restano VCC3 PMIC, altre alimentazioni, eMMC/segnali, compattazione, processo BGA e qualifica elettrica/termica.
Nessun componente aggiunto alla BOM elettronica, nessun nuovo prezzo o stock verificato, nessun ordine.
