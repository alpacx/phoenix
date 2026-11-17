# Variante compatta del regolatore PHY — sperimentale

Artefatto: `pcb/phy-compact-output.kicad_pcb`; prove e hash in
`study-checkpoint.json`. Non sostituisce il checkpoint autorevole né la BOM.

## Riproduzione

Dalla root, con il Python incluso in KiCad 10:

```sh
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 hardware/phoenix-g1/tools/rebuild_phy_compact_study.py
```

La procedura usa la copia congelata `baseline/source.kicad_pcb` (SHA in
`baseline/checkpoint.json`), quindi rimane riproducibile dopo modifiche al
PCB principale. Esegue posizionamento, ripristino masse, ramo di uscita e
reset, salvataggio persistente e cinque test con iniezione di guasti.
Ultima esecuzione completa superata il 17 novembre 2026. Nessun acquisto.

## Modifiche e verifiche

- L501: AFE252012S2R2MBT, 2,2 µH, impronta ricavata dal disegno del produttore;
  pad 0,95×2,10 mm, gap 0,70 mm, ingombro esterno pad 2,60 mm.
- C511/C515: CL10A475KP8NNNC, 4,7 µF 10 V X5R, 0603. Posizioni in `moves.json`.
- R516 spostata; deviazione reset mantenuta a 0,20 mm.
- Ramo GND spostato mantenendo 0,50 mm e via 0,60/0,30 mm; tronco Wi-Fi
  da 0,80 mm invariato. Connessioni preesistenti preservate.
- L501.2–C511.1: 1,55 mm, 2,511 mm, F.Cu, nessun via. DRC senza nuove
  violazioni rispetto alla baseline; nessun nuovo conflitto meccanico.
- Reset U5.12–R515.2 presente anche nella variante.

## Limiti elettrici e sourcing

Il ramo di uscita non completa il convertitore: nodo SW, ingresso 3,3 V e
carichi 1,0 V restano aperti. La larghezza confrontata con la vecchia rev1.1
non sostituisce la guida layout della revisione esatta e la verifica PI/termica.
DCR massimo dell'alternativa 65 mΩ contro 39 mΩ dell'originale: non è un
ricambio già qualificato. Le correnti del datasheet e le condizioni di prova
sono trascritte in `component-review.json`, senza convertirle in garanzie.

Mancano curve di capacità effettiva sotto bias/temperatura/aging e verifica
ESR/stabilità. Il PDF JLC per C1705 è un catalogo generico; la specifica del
codice esatto è sul sito Samsung. Non usare il catalogo per stimare il bias.

JLC C22459322 e C1705 interrogati il 17 novembre 2026; stock/prezzi grezzi
in `../../../sourcing/public/`, condizioni e URL in `component-review.json`.
I campi presale/overseas e `assemblyComponentFlag=false` non dimostrano
allocabilità per un ordine PCBA. Nessun ordine o prenotazione effettuati.

Non pronto alla produzione. Nessuna prova fisica o simulazione di stabilità.

## Ulteriore prova congiunta clock/RSET

Dopo il ramo di uscita è stata tentata l'uscita del pin analogico RSET.
Il percorso frontale verso R513 non è disponibile nel modello locale:
`pmic-ldo-inputs/pcb/phy-rset-pin-probe.json`.

`probe_phy_clock_rset_escape.py` ha poi modificato XOUT su una copia per
liberare un via di uscita RSET. Entrambe le geometrie sono RIFIUTATE:

- `clock-rset-escape-probe.json`: via a (59,9;32,4), conflitti con XIN sul
  retro e clearance del ramo 5V su In2.
- `clock-rset-shifted-probe.json` (`--shifted`): via a (59,5;32,4), corto
  con 5V In2 e deviazione XOUT in conflitto con masse preesistenti.

Non ripetere queste due geometrie. Serve considerare simultaneamente XIN,
XOUT, masse e tronco 5V su tutti gli strati; nessuna larghezza è stata ridotta.
Il DRC è sufficiente per respingerle; la preservazione non viene dichiarata
superata per candidati già respinti. Nessuno dei due cambia il PCB salvato.
La costruzione e l'audit sono separati in processi per evitare instabilità
SWIG osservate dopo la modifica del rame; il DRC viene eseguito da KiCad CLI.
