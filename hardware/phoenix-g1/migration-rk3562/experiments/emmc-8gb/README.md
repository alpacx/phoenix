# eMMC saldata per Phoenix — candidato isolato

Aggiornato 2026-11-13. Non integrato nel PCB o nello schema di sistema.
Il checkpoint verificato LPDDR4 resta invariato; nessuna produzione autorizzata.

## Risultato concreto

- Foglio KiCad `kicad/emmc-storage-candidate.kicad_sch`, con 14 componenti:
  eMMC, quattro resistenze, nove condensatori; supporti ancora da qualificare.
- Samsung KLM8G1GETF-B041, C499918, 8 GB, 153 ball, 11,5 × 13 × 0,8 mm,
  passo 0,5 mm. Footprint locale con land provvisorio 0,25 mm: NON qualificato
  come land pattern di produzione, maschera/stencil/assemblaggio aperti.
- 153 disposizioni: 33 contatti funzionali/alimentazione, 107 NC, 13 RFU.
  RFU lasciati aperti, compresi E9/E10/F10/K10: non copiare i VSF del simbolo
  generico della reference come connessioni valide del componente Samsung.
- 11 segnali controller mappati contro il CSV RK3562 e schema reference;
  RSTN con pull-up candidato, non inventato un pin reset dedicato del SoC.
- Audit su netlist esportata da KiCad: 179 disposizioni di pin verificate,
  più ancore indipendenti per dati/clock/strobe/reset/alimentazioni/VDDI.
  Import footprint nativo KiCad: 153 pad e coordinate coerenti con ball map.
- ERC: 3 alimentazioni non pilotate e 9 etichette isolate (interfacce esterne
  al foglio). Nessun errore di griglia, link libreria o footprint dopo correzione.
  Nessuna esclusione ERC. Render dello schema ispezionato visivamente.

## Cambi necessari prima dell'integrazione

L'eMMC sostituisce il circuito SPI NOR attuale sugli stessi pin, non si aggiunge
in parallelo. `signal-map.json` riporta i net precedenti e le palle del SoC.
Il dominio interessato è **VCCIO2 / U1.1F14**, attualmente +3V3_IO. Il candidato
usa IO a 1,8 V e VCC NAND a 3,3 V; la migrazione deve separare quel dominio e
qualificarne sorgente/sequenza, senza cambiare gli altri VCCIO.

Valori di supporto derivati dalla reference RK3562 pagine 8/14: serie clock
22 ohm, pull-up DAT0/CMD/RSTN 10 kohm, VDDI 2,2 uF, quattro bypass IO 100 nF
più 4,7 uF, due bypass VCC 100 nF più 4,7 uF. Sono candidati: MPN, capacità
utile con bias, layout e prescrizioni Samsung specifiche ancora aperti.
Il nodo VDDI è interno e NON va collegato a una sorgente esterna.

Boot strap, pin mux, loader LPDDR4/eMMC, recovery USB e reset devono essere
qualificati insieme prima di rimuovere la NOR dalla scheda di sistema. Non
presumere che l'immagine microSD della ROCK entri o avvii su questa eMMC: serve
un'immagine RK3562 dimensionata sullo spazio effettivo, con margine per update.

## Disponibilità e ingombro

`stock-observation.json`: osservazione diretta della pagina JLCPCB C499918,
2026-11-13, canPresaleNumber 997, overseasStockCount 1057, initialPrice
17,7555 USD, preMinPurchaseNum 1. Sono campi del catalogo: non disponibilità
PCBA garantita o prenotazione. Non sommare le due quantità. Nessun acquisto.

`review/85x35-body-screen.json`: screening conservativo a posizioni attuali,
fronte/retro e due orientamenti. Include l'intero bounding box dei componenti
forati su entrambi i lati; non trova una posizione senza conflitti nella griglia
campionata. Non prova impossibilità: sono necessari spostamenti coordinati.
Non include fattibilità rame/vias, supporti, dissipatore, case, DDR o timing.
Nessuna posizione è stata applicata al PCB. Obiettivo 85×35 resta da verificare.

## Riproduzione

1. `/tmp/phoenix-eda-venv/bin/python hardware/phoenix-g1/tools/build_rk3562_emmc_candidate.py`
   (Python con sexpdata; genera solo questo esperimento).
2. Esportare netlist `--format kicadxml` in `review/netlist.xml` e ERC JSON in
   `review/erc.json` dal foglio candidato con kicad-cli.
3. Eseguire `tools/audit_rk3562_emmc_candidate.py` con Python di KiCad/pcbnew.
4. Eseguire `tools/screen_emmc_85x35.py` con lo stesso Python per lo screening.

Fonti locali: `reference/samsung-klm8g1getf-b041.pdf` pagine 4–6 (tabella e
ball-side-down verificati visivamente); `reference/rk3562-oomwoo-reference.pdf`
pagine 8 e 14; `migration-rk3562/review/manufacturer-pins.csv`.
Stock: https://jlcpcb.com/partdetail/C499918 .

Non sono stati eseguiti simulazioni SI/PI, routing di questa memoria, prove
fisiche, ordini o qualifica di produzione.
