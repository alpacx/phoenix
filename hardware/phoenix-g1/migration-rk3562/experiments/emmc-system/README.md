# eMMC nel sistema completo — candidato verificato nella netlist

Il candidato integra KLM8G1GETF-B041 8 GB e sostituisce il foglio NOR FSPI.
Il checkpoint di lavoro è `working-candidate.json`; la baseline precedente
`../stacked-expansion/working-candidate.json` rimane preservata.

## Verifiche eseguite

- Netlist KiCad esportata: 1.996 assegnazioni dei pin confrontate con il contratto.
- Undici segnali eMMC e VCCIO2 U1.1F14 modificati; 1.600 altri collegamenti preservati.
- VCCIO3 invariato; VDDI collegato soltanto al condensatore locale.
- R8005 47 kohm candidato tra STRB e GND, secondo tabella 37 del datasheet Samsung rev.1.21.
- C8010 100 nF candidato dedicato a VCCIO2 presso il SoC, distinto dal bypass della memoria.
- ERC: 17 alimentazioni non pilotate e una label isolata. Nessuna soppressione aggiunta.
- Footprint isolato: 153 pad verificati rispetto alla mappa; land/pasta ancora da qualificare.

Le alimentazioni sono ora collegate **nel candidato di schema**, tramite due
resistori da 0 ohm 0603 rimovibili: R8006 da +1V8_SYS a EMMC_IO_1V8,
R8007 da +3V3_IO a EMMC_3V3. Non sono state dichiarate qualificate.
Il riferimento RK3562, pagina 17, mostra il collegamento VCCIO_FLASH da 1,8 V
tramite 0 ohm; la pagina è stata verificata visivamente. La variante alternativa
3,3 V non popolata nel riferimento non va montata insieme a quella da 1,8 V.

Il candidato UNI-ROYAL 0603WAF0000T5E/C21189 specifica 1 A continuo e resistenza
inferiore a 50 mohm. Ai soli carichi memoria dichiarati (180 mA e 50 mA), la caduta
massima del componente è rispettivamente 9 mV e 2,5 mV: sono calcoli DC, non misure.
Budget totale, picchi, sequenza rispetto al processore, stabilità, decoupling,
reset, boot e recovery restano aperti. Vedere `system/review/power-requirements.json`.

## Riproduzione

Eseguire `tools/rebuild_emmc_system.py` con Python dotato di sexpdata.
La pipeline rigenera i candidati, esporta le netlist e gli ERC con KiCad,
poi esegue i due audit. Interrompe l'esecuzione in caso di errore.
`system/review/migration-audit.json` è il risultato autorevole, non i report
storici eventualmente ereditati dal sistema di partenza.

Nessuna prova fisica, nessuna qualifica HS400, nessun rilascio alla produzione.

## Sourcing dei 18 componenti dello storage

Tutte le 18 posizioni del candidato hanno MPN, codice JLCPCB e footprint locale.
Gli otto codici distinti e le quantità sono registrati in
`system/review/current-selected-stock.json`; i dati pubblici sono stati rilevati
il 13–14 novembre 2026. I prezzi non comprendono PCB, montaggio, trasporto e imposte.
Le disponibilità presale/overseas non equivalgono a stock PCBA immediatamente
allocabile e non sono prenotazioni. I condensatori richiedono ancora verifica
della capacità effettiva sotto polarizzazione; la selezione nominale non è
qualifica elettrica o di assemblaggio.

## PCB integrato e masse esterne — 14 novembre

`working-candidate.json` punta a `pcb/emmc-ground.kicad_pcb`.
L'audit verifica 1.816 pad esistenti, 187 nuovi, 4.051 piste/via originali e
43 gruppi fisicamente collegati. Tutti sono preservati. NOR e sei supporti sono
rimossi; 18 componenti storage sono inseriti. La eMMC è sul retro a (38; 9) mm.

La ricerca su griglia 0,5 mm, in due orientamenti e nell'area obiettivo 85×35,
ha individuato 279 posizioni senza conflitti con il rame fisso prima del
piazzamento dei passivi. Non è una prova della compattazione dell'intera scheda.
Sono riposizionati 15 bypass del processore ancora non instradati; la loro
posizione elettrica resta da qualificare. I passivi storage riservano punti di
massa vicini prima del routing, evitando i tentativi con ritorni lunghi.

Le 11 masse esterne (dieci condensatori e pull-down STRB) raggiungono i piani
con percorsi da 0,72 a 1,34 mm. Sono 36 primitive aggiunte; nessuna nuova
violazione DRC individuale. Massa del BGA, alimentazioni, segnali, PI e boot
restano aperti. I report precedenti `emmc-placement-search.json` e
`emmc-ground-extended.json` sono tentativi storici, non checkpoint utilizzabili.

Rigenerazione: `tools/rebuild_emmc_pcb.py`. Confronta DRC, reti e continuità,
e pubblica il puntatore solo dopo i controlli; in caso di fallimento ripristina
la copia precedente. Non sovrascrivere il checkpoint con generatori parziali.

Le regole JLC aggiornate sono in `system/review/bga-process-review.json`.
Il fanout a passo 0,5 mm richiede una scelta di processo documentata;
non sono autorizzate implicitamente riduzioni dei pad o via-in-pad non riempite.
Nessun preventivo definitivo, ordine, collaudo o rilascio alla produzione.
