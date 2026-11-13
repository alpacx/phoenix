# eMMC nel sistema completo — candidato verificato nella netlist

Il candidato integra KLM8G1GETF-B041 8 GB e sostituisce il foglio NOR FSPI.
Non aggiorna il PCB: il riferimento di routing resta `../stacked-expansion/working-candidate.json`.

## Verifiche eseguite

- Netlist KiCad esportata: 1.992 assegnazioni dei pin confrontate con il contratto.
- Undici segnali eMMC e VCCIO2 U1.1F14 modificati; 1.600 altri collegamenti preservati.
- VCCIO3 invariato; VDDI collegato soltanto al condensatore locale.
- R8005 47 kohm candidato tra STRB e GND, secondo tabella 37 del datasheet Samsung rev.1.21.
- C8010 100 nF candidato dedicato a VCCIO2 presso il SoC, distinto dal bypass della memoria.
- ERC: 17 alimentazioni non pilotate e una label isolata. Nessuna soppressione aggiunta.
- Footprint isolato: 153 pad verificati rispetto alla mappa; land/pasta ancora da qualificare.

Le alimentazioni EMMC_IO_1V8 ed EMMC_3V3 sono intenzionalmente prive di sorgente:
non collegarle a un rail solo perché la tensione nominale coincide. Vedere
`system/review/power-requirements.json`: carico memoria HS400 di 180 mA a 1,8 V
più 50 mA a 3,3 V, RMS su 100 ms; picchi e carico SoC non compresi.
Reset, sequenza, budget PMIC, boot/recovery, componenti di supporto e layout restano aperti.

## Riproduzione

Eseguire `tools/rebuild_emmc_system.py` con Python dotato di sexpdata.
La pipeline rigenera i candidati, esporta le netlist e gli ERC con KiCad,
poi esegue i due audit. Interrompe l'esecuzione in caso di errore.
`system/review/migration-audit.json` è il risultato autorevole, non i report
storici eventualmente ereditati dal sistema di partenza.

Nessuna prova fisica, nessuna qualifica HS400, nessun rilascio alla produzione.

## Sourcing dei due supporti aggiunti

R8005 usa il candidato JLCPCB C25792/0402WGF4702TCE, C8010 il candidato
C1525/CL05B104KO5NNNC, con footprint 0402 della libreria locale. I dati pubblici
aggiornati, inclusa la eMMC C499918, sono in `system/review/current-selected-stock.json`.
Non sono riserve di magazzino e non costituiscono una BOM completa valorizzata.
