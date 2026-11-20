## Ripresa sequenziale — 18 novembre 2026

Decisione utente: continuare la scheda attuale RK3562, senza agenti paralleli. Studi Wi-Fi gigabit e alternative RAM restano non applicati. Nessun commit/push.

Checkpoint autorevole: `pmic-ldo-inputs/working-candidate.json`, SHA `c29d07e1eca29d367b1194504bc58288253b281572404bd8820ac6b030a12824`.
Corretti due via RAM troppo vicini a pad; integrati cinque ritorni GND aggiuntivi, incluso C1627 con via riposizionato lontano da C2204 e EXP_SPI_MOSI. **246 coppie verificate**, ricostruzione completa di 24 stadi superata, **67 test ereditati + 7 test integrati** superati. Screen conservativo dei **30 nuovi via** superato; aggiunta regressione per overlap con pad della stessa net. Nessun nuovo errore DRC o conflitto meccanico introdotto.

Restano 225 reti multipad aperte e 901 unioni topologiche minime. VDC pin61, distribuzione alimentazioni PHY/RAM, routing restante, display e verifiche SI/PI/assemblaggio restano aperti. Due via preesistenti presso U21.19/C521.2 richiedono revisione assemblaggio separata: il nuovo screen non ne certifica l'idoneità. La scheda non è pronta alla produzione.

Dettagli e tentativi esclusi: `control-routing-parallel/SEQUENTIAL_RESUME.md`. Le sezioni successive sono storico, non attività di agenti attualmente in esecuzione.

## Salvataggio parziale — 17 novembre 2026, RXCLK e corridoi PHY

Checkpoint principale: `bdeb44f58dea3d0261469c1d3f7eeb5a9e6df03e95648710393c9e09c83f6aeb`.
RXCLK: R512/R522 sul retro, ramo di bias da 1,374 mm e massa ripristinata.
Ricostruzione completa superata: **195 coppie, 67 test CAD**, 23 stadi.
Restano 226 reti multipad aperte e 951 unioni topologiche minime.
Nessuna qualifica elettrica o di produzione.

Variante separata: `phy-compact-inductor/corridor/checkpoint.json`:
C517 riposizionato, ramo di ingresso da 1,05 mm, ritorni C511/C515 da 0,50 mm,
secondo via GND C511 e bias RXCLK. Ricostruzione transazionale e 7 test
isolati superati. Non adottata nella BOM o nel PCB principale.
Riprodurre con Python KiCad 10 e `tools/rebuild_phy_corridor_study.py`
sotto `hardware/phoenix-g1/`.

Ultima prova `corridor/switch-fanout-probe.json` RESPINTA dal DRC, non
adottata. Il tratto di uscita dal pin proposto è anche più stretto della
raccomandazione storica Realtek: nessuna deroga approvata. Restano aperti
nodo SW, alimentazione a monte, distribuzione 1 V e qualifiche SI/PI/termiche.
Le sezioni successive sono storico e possono contenere conteggi superati.

## Reset PHY integrato e variante compatta — 17 novembre 2026

Checkpoint autorevole (percorso dalla root):
`hardware/phoenix-g1/migration-rk3562/experiments/pmic-ldo-inputs/working-candidate.json`, SHA
`96b01d90aa6225a873dac818f007459245adeb207920009b7f11e223b8266394`. Collegato U5.12 a R515.2 sul fronte,
0,20 mm, 6,748 mm, senza via. Ricostruzione completa dei 23 stadi superata:
194 coppie, 65 test CAD, test corto XIN/5V, rilevamento meccanico e rollback.
Restano 226 reti multipad aperte e 952 unioni topologiche minime;
19 possibili conflitti meccanici preesistenti. Nessuna qualifica elettrica.

La revisione congiunta è descritta in
`hardware/phoenix-g1/migration-rk3562/experiments/phy-compact-inductor/README.md`:
induttore 2,5×2 mm, C511/C515 0603 e corridoi GND ripristinati mantenendo
le larghezze originali. Ramo L501.2–C511.1 da 1,55 mm sul fronte senza via,
2,511 mm, verificato con DRC, preservazione e cinque test dedicati.
Variante sperimentale separata, NON adottata nella BOM né nel PCB autorevole.
Il regolatore richiede ancora ingresso, nodo SW e distribuzione ai carichi;
restano da qualificare DCR/ripple, capacità effettiva, stabilità e termica.
La disponibilità JLC osservata è presale/overseas, non allocazione PCBA.

Le sezioni seguenti sono storico e possono riportare conteggi superati.

## Ricerca deviazione GND ampliata — 17 novembre 2026

Eseguite tutte le 13 posizioni C511 che nel DRC esatto erano ostacolate
soltanto dal segmento GND da 0,80 mm. Campo ampliato a (44,24)-(58,38) mm,
griglia 0,05 mm, entrambe le rotazioni pertinenti: nessun percorso trovato
senza restringimento. Gli estremi della ricerca non sono bloccati;
il fallimento riguarda il corridoio nel modello geometrico conservativo.
Non equivale a dimostrare impossibilità globale o a un DRC di tutte le
possibili deviazioni. Non ripetere la stessa matrice senza cambiare ipotesi.

Strumento `probe_phy_bulk_detour_matrix.py`, risultato
`pcb/phy-bulk-detour-matrix.json`. Lo script di prova supporta ora
`--detour-extent`, `--capacitor-position`, `--capacitor-angle`.
Prima di estendere ulteriormente il routing serve una revisione congiunta
del gruppo induttore/condensatori o dei corridoi di alimentazione Wi-Fi.

Aggiunto `pcb_route_guards.py`: per il ramo sostitutivo verifica larghezza
costante 0,80 mm, net, layer, continuità ed estremi. Sei test in
`test_pcb_route_guards.py` passati, incluso il difetto reale 0,80→0,20 mm.
Lo script verifica anche le larghezze dei segmenti originali prima di
rimuoverli. Sono controlli geometrici, non una qualifica di corrente.

Nessuna nuova posizione adottata: checkpoint, reti aperte e stato della
qualifica invariati. Nessun commit/push, ordine o modifica software.

## Rettifica finale della prova C511 — 17 novembre 2026

La prova congiunta descritta sotto è SCARTATA, non adottata.
Il segmento GND `545b053b-db69-41f9-bd1f-f3135bcf88b9` originale è largo
0,80 mm; la prima deviazione passava DRC/continuità ma era larga 0,20 mm.
Questo restringimento non è accettato. Ripetendo la ricerca con 0,80 mm
non esiste un percorso nel campo (48,27)-(55,33) mm alla griglia 0,05 mm.
Non è una prova di impossibilità globale: occorre estendere/revisionare il
percorso e il relativo ritorno Wi-Fi prima di adottare C511 in questa zona.

`phy-output-bulk-ground-probe.json` e `phy-combined-bulk-ground-probe.json`
riportano ora REJECTED_NO_GROUND_DETOUR_AT_ORIGINAL_WIDTH. I vecchi candidati
in directory temporanee sono rifiutati, anche se il loro DRC era passato.
La prova indipendente C515 resta valida solo come posizionamento/massa;
il suo percorso di alimentazione principale rimane aperto.
Checkpoint autorevole invariato. Le sezioni successive descrivono lo storico.

## Prova congiunta C511/C515 — 17 novembre 2026

Superata la prova geometrica e di continuità dei due condensatori insieme:
C511 sul fronte a (52;30,25) mm, 180°, e C515 a (61,7;24) mm, 90°.
Il condensatore di uscita non richiede necessariamente lo spostamento del
convertitore Wi-Fi: una posizione è stata liberata deviando una pista GND.

Il DRC esatto di 63 posizioni C511, inizialmente scartate dal filtro
conservativo, non trovava posizioni senza modificare rame. Alcune però
interferivano con una sola pista GND. Nella prova questa pista è deviata
verso il pad C2204.2, conservando tutte le connessioni preesistenti.
Rimossi esplicitamente i due vecchi rami GND dei condensatori e il segmento
GND deviato (cinque segmenti in totale); nessun'altra pista originale alterata.

Prova combinata: nessuna nuova violazione DRC o interferenza meccanica;
2006 pad preservati e verifica dei gruppi connessi contro il checkpoint
originale. Masse dei condensatori ripristinate. Nessuna clearance allentata.

NON promosso al checkpoint: ingresso +3V3_PHY, uscita +1V0_PHY e nodo SW
restano da progettare come percorsi di potenza. La prova non qualifica
corrente, impedenza del ritorno, stabilità, accoppiamenti o produzione.
Il PCB autorevole e il relativo conteggio delle reti aperte sono invariati.

Riproduzione con Python KiCad, nell'ordine:
1. `hardware/phoenix-g1/tools/probe_phy_input_bulk_ground.py`
2. `hardware/phoenix-g1/tools/probe_phy_output_bulk_ground.py --with-input-bulk`

Risultato: `pcb/phy-combined-bulk-ground-probe.json` nello studio
pmic-ldo-inputs; contiene percorso temporaneo, SHA candidato e preservazione
rispetto al checkpoint originale. Per il controllo di posizionamento esatto:
`probe_phy_bulk_placement.py`, poi `probe_phy_bulk_exact_clearance.py`.
La prima prova esatta escludeva dangling/unconnected SOLO dalla selezione
geometrica: la successiva prova combinata non esclude nuove violazioni.
Nessun acquisto, commit/push o modifica software.

## Studio alimentazioni PHY — 17 novembre 2026, seguito

Checkpoint autorevole invariato: `ethernet-dvdd33-bypass`, SHA
`a250b2670de4fe5c42deb37589dd6d8f8fabd6aef7982c5572683cc5c3690164`.

- Screening condensatori a passo 0,10 mm: nessuna posizione C511 nel campo
  provato, 91 posizioni C515. La rotazione ipotetica di L501 a 0/90/270 gradi
  non risolve C511 nel campo a passo 0,25 mm. Non è una prova di impossibilità.
- Il report ora identifica i gruppi di courtyard che bloccano le posizioni;
  fra quelli isolati di C511 compaiono induttore, quarzo e componenti Wi-Fi.
  Non spostare il convertitore Wi-Fi già instradato senza revisione congiunta.
- Prova locale C515 a (61,7;24) mm, 90 gradi: massa ripristinata mediante
  via (62,45;24,25), nessuna nuova violazione DRC o interferenza meccanica.
  Sostituiti esplicitamente due segmenti GND, lunghi complessivamente 0,72 mm,
  del vecchio ramo. Conservati 2006 pad e 69 gruppi di connessione preesistenti.
  Candidato temporaneo NON promosso: manca ancora il percorso principale
  +3V3_PHY, con verifica di larghezza, ritorno e stabilità.
- Inventario delle alimentazioni: PHY_SW 2 gruppi (1 unione minima),
  +1V0_PHY 8 gruppi (7), +3V3_PHY 11 gruppi (10). Totale 18 unioni
  topologiche minime, non piste. Il rame sottile già presente non qualifica
  la distribuzione di potenza.

Strumenti riproducibili in `hardware/phoenix-g1/tools/`:
`probe_phy_bulk_placement.py` (opzioni `--placement-step`, `--inductor-angle`,
`--output`), `probe_phy_input_bulk_ground.py`, `report_phy_power_topology.py`.
Risultati nel `pcb/` dello studio pmic-ldo-inputs: `phy-bulk-*-probe.json`,
`phy-input-bulk-ground-probe.json`, `phy-power-topology.json`.
I percorsi temporanei sono diagnostici; rigenerare la prova se non esistono.
Nessuna modifica al PCB autorevole, al software o ai componenti ordinabili.
Nessuna nuova qualifica elettrica, termica o di produzione. Nessun commit/push.

## Checkpoint induttore PHY sul fronte — 17 novembre 2026

Ripartire da `migration-rk3562/experiments/pmic-ldo-inputs/working-candidate.json`
(`working-candidate.json` nella directory dello studio).
PCB finale: `pcb/ethernet-dvdd33-bypass.kicad_pcb`.

L501 sul fronte a (57,4; 30,8) mm, ruotata 180°; Y501 a (57,75; 34,8) mm.
C1014 è sul retro a (62; 36) mm; U23 sul retro a (75,5; 25,5) mm.
Questi due componenti erano privi di piste collegate. Conservati pin/net,
connessioni precedenti e bypass PHY. Nessun componente o valore aggiunto.

XIN attraversa il retro con due via 0,45/0,20 mm; XOUT resta sul fronte.
Per evitare un corto con il via XIN, un segmento +5V_MAIN su In2 da 0,8 mm
è sostituito da tre segmenti della stessa larghezza: 8,78 mm contro 8,45 mm.
La sostituzione è esplicita nella prova di preservazione dello stadio clock.
Nessuna regola di clearance o larghezza minima allentata.

Ricostruzione completa di 23 stadi superata: **193 coppie, 64 test CAD**,
più test del corto XIN/5V, rilevamento meccanico e rollback.
Il test del corto rimette il vecchio segmento su una copia e verifica il
corto preciso fra la pista a 5V e il via XIN; il checkpoint resta invariato.
L'audit rifiuta L501 sul retro. Nessuna nuova violazione DRC o interferenza;
restano 19 possibili conflitti meccanici preesistenti.

**Non è una qualifica del convertitore o dell'oscillatore.** Restano aperti
commutazione, alimentazioni principali, ritorni, stabilità e corrente.
Le lunghezze aggregate di rame del clock sono circa 8,83 mm per XIN e
10,40 mm per XOUT, includendo i rami dei condensatori; non includono
la lunghezza verticale dei via e non sono una verifica SI.
Parassiti e accoppiamento al futuro percorso SW richiedono revisione e prove.
U23 sul retro richiede ancora il progetto dei percorsi ESD, C1014 quello
del disaccoppiamento CPU. `pcb/phy-regulator-layout-review.json` aggiornato.

Attività successive già esaminate: `probe_phy_bulk_placement.py` non trova
una posizione frontale isolata per C511 nel campo provato; trova 16
possibilità per C515, ancora senza percorso di potenza verificato.
`report_current_rgmii_placement.py` usa il checkpoint RK3562 corrente:
terminazioni TX a 3,01–5,32 mm dalla sorgente, RX a 1,63–3,87 mm.
Sono distanze in linea retta, non lunghezze instradate o risultati di timing.
Tutti i 12 resistori hanno zero piste collegate: una revisione congiunta
con il percorso di potenza è possibile, ma non ancora adottata.

I vecchi studi isolati sono storici e conservano gli hash della rispettiva
prova. Il generatore precedente del clock è in `probe-inputs/`; le prove
isolate copiano ora anche le librerie footprint per evitare DRC spurii.
Rigenerare con Python KiCad e `hardware/phoenix-g1/tools/rebuild_local_copper.py`.

227 reti multi-pad ancora aperte, 953 giunzioni topologiche minime:
non sono un conteggio di piste o una percentuale. PCB 90×40 mm, target
85×35 non qualificato; 13 pad display assenti. Nessuna prova fisica,
ordine, commit/push o modifica ROCK/software. Nessun nuovo MPN o prezzo
verificato. Le sezioni seguenti sono storico.

## Checkpoint bypass Ethernet — 17 novembre 2026

Fonte corrente: `migration-rk3562/experiments/pmic-ldo-inputs/working-candidate.json`
(dalla directory dello studio: `working-candidate.json`).
PCB `pcb/ethernet-dvdd33-bypass.kicad_pcb`.
Cinque condensatori riposizionati e collegati ai rispettivi pin PHY:
C514→U5.21, C516→U5.11, C512→U5.3, C517→U5.28, C519→U5.29.
Ristabilite tutte le loro masse; raccordati U5.28/29. Nessun nuovo MPN.

Audit cumulativo di **193 coppie**, **63 test CAD passati**, ricostruzione completa
di **23 stadi** dopo five-volt-testpoint riuscita. Nessuna nuova violazione DRC
o interferenza meccanica; restano 19 possibili interferenze preesistenti.
Le nuove diramazioni sono larghe 0,20 mm e misurano circa 1,53–4,11 mm;
non sono una qualifica di corrente o disaccoppiamento. Le tre uscite dei pin
ravvicinati usano un tratto rettilineo esplicito da 0,80 mm senza ridurre
larghezze/clearance. I test di guasto isolano anche percorsi alternativi.

Inventario: 227 reti multi-pad aperte; **953 giunzioni topologiche minime**
fra gruppi ancora separati. Non sono 953 piste, né una percentuale di completamento.
Conservati clock, fissaggi e connessioni precedenti. Display: 13 pad ancora assenti.

Revisione del convertitore: `pcb/phy-regulator-layout-review.json`.
La rev. 1.1 Realtek reperita su Boardcon esplicita induttore/bulk sul fronte,
tratti di potenza larghi e senza via nei percorsi indicati. È precedente alla
rev. 1.2 locale: evidenza conservativa, da riconciliare con la guida corrente.
**L501 sul retro resta provvisoria e non approvata**; i nuovi rami da 0,20 mm
non sostituiscono dorsali di potenza dimensionate. C511/C515 restano da riavvicinare.

`probe_phy_inductor_front.py` non trova un piazzamento isolato nel campo
esaminato: gli esempi meno congestionati interferiscono con C520/Y501.
`probe_phy_clock_inductor_joint.py` prova sei disposizioni in una copia temporanea,
senza modificare il checkpoint: nessuna conclude il piazzamento locale dei due
condensatori del quarzo. Rapporti `phy-inductor-front-probe.json` e
`phy-clock-inductor-joint-probe.json`. Non è una prova di impossibilità.
I tentativi C513/C518/C522 non sono promossi; servono un riassetto congiunto
più ampio e la revisione del percorso di potenza, non altre piste isolate.

Rigenerazione: Python KiCad con `tools/rebuild_local_copper.py` nella cartella hardware.
Audit distanze/assegnazioni: `tools/report_phy_supply_placement.py`.
I report di tentativi precedenti mantengono gli hash della rispettiva prova;
non sono checkpoint alternativi utilizzabili. Nessun aggiornamento dei prezzi:
nessun nuovo componente scelto, nessuna dichiarazione di stock corrente.

Nessun ordine, commit/push o modifica software/ROCK. PCB ancora 90×40 mm,
obiettivo 85×35 mm non qualificato. Alimentazioni, SI/PI, termica passiva,
avvio, EMC/DFM e prove fisiche restano aperti. Le sezioni seguenti sono storiche.

## Checkpoint masse condensatori PHY — 17 novembre 2026

Checkpoint corrente: `migration-rk3562/experiments/pmic-ldo-inputs/working-candidate.json`
(in questa directory: `working-candidate.json`). PCB: `pcb/ethernet-cap-grounds.kicad_pcb`.
Dieci ritorni GND C511–C519/C522 collegati con 30 nuove primitive, senza
rimuovere rame o spostare componenti; nessuna nuova violazione DRC.
Audit cumulativo: 182 coppie. I 51 test precedenti passano; il nuovo test
di interruzione passa dopo aver corretto il selettore della rete nel test.
Il rame è verificato geometricamente, non elettricamente.

La pipeline comprende ora 17 stadi dopo five-volt-testpoint, incluso
`route_ethernet_cap_grounds.py`. Questa prosecuzione ha eseguito il nuovo
stadio e gli audit, non una ricostruzione completa dei 17 stadi.
`report_phy_supply_placement.py` genera `pcb/phy-supply-placement.json`:
i condensatori sono a 12,30–18,05 mm in linea retta dal più vicino pin PHY
dello stesso rail. Non interpretare le masse collegate come disaccoppiamento
qualificato: occorre riesaminare il piazzamento, assegnare i bypass ai pin
e chiudere i loop prima del routing dei rail. Rilavorazione locale prevista.

Restano 227 reti multi-pad aperte, 13 pad display assenti e i conflitti
meccanici preesistenti; nessuna qualifica di avvio, SI/PI, termica o produzione.
Nessun nuovo componente/MPN: nessuna nuova attestazione di stock o prezzo.
Nessuna modifica software/ROCK, ordine o commit/push.

# Ingressi PMIC — checkpoint corrente

Il checkpoint `working-candidate.json` deriva da `../system-3v3/working-candidate.json`.
PCB corrente: `pcb/ethernet-clock-pins.kicad_pcb`. Continuità/geometria verificate;
nessuna qualifica elettrica o produttiva e nessuna prova fisica di accensione.

## Stato verificato

- 172 coppie di pad collegate; 51 test passati, nessuna nuova violazione DRC.
- Inventario delle reti aperte in `pcb/connectivity-inventory.json`: non è una percentuale di completamento.
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
python hardware/phoenix-g1/tools/rebuild_local_copper.py
python hardware/phoenix-g1/tools/test_display_rebuild_rollback.py
```

## Verifiche ancora necessarie

- Chiudere U4.61, enable CPU e uscite PMIC; completare segnali e collegamenti al display.
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

## Display: nove stadi locali — 16 novembre 2026

La ricostruzione transazionale parte da `five-volt-testpoint` verificato e
ripristina PCB, report e puntatore precedenti se una fase fallisce. Il test di
rollback usa file temporanei e un guasto simulato; non rappresenta una prova
fisica. Non lanciare due ricostruzioni o modifiche CAD contemporaneamente.

- R1803 alimentata dal bus +5V_MAIN; U20.EN raggiunge +3V3_IO. Il lungo ramo
  enable porta il solo ingresso logico, non la corrente del pannello.
- C1811 è vicino a U21, con bypass locale e massa. R1811–R1815 sono riposizionate
  e collegate ai cinque ingressi; quattro ritornano a GND, CS a +3V3_IO.
- U21.1/7/8/9/10 hanno ritorni GND. C1812 è ora a (22;35) sul fronte,
  collegato a +3V0_LCD e massa; R1804 è a (32;29) con i due terminali collegati.
- R1801/R1802/Q1 hanno base e ritorni di massa collegati. PWM a monte e pannello
  a valle non sono completati dalla chiusura di questi collegamenti locali.

Lo stadio input-pulls sostituisce esplicitamente i 58 elementi del precedente
ramo buffer, conservando le connessioni già richieste. Il nuovo +3V0_LCD passa
su In2.Cu (10,98 mm) e fronte (2,41 mm), con due via 0,45/0,2 mm; larghezza
0,3 mm. La connessione CS locale misura 19,57 mm. Queste lunghezze non sono
una qualifica SI/PI o di corrente. `pcb/display-routing-metrics.json` riporta
le geometrie per stadio; nessun nuovo centro via cade nei bounding box dei pad,
ma ciò non sostituisce il DFM né elimina i via-in-pad delle fasi precedenti.

L'audit complessivo preserva le connessioni ereditate e verifica 152 coppie.
I 39 test comprendono tagli deliberati di alimentazioni, segnali e masse.
`pcb/display-integration-audit.json` rimane INCOMPLETE_DISPLAY_INTEGRATION:
zero mismatch e zero gruppi separati fra i pad presenti nel contratto locale,
ma i 13 pad DS1 non sono implementati. CPU e qualifiche a monte sono esclusi
esplicitamente da questo contratto. Nessuna accensione fisica o simulazione.

### Attacco del pannello: qualifica aperta

`pcb/display-attachment-review.json` documenta la revisione della pagina 5
(disegno osservato) e delle pagine 6–7 del datasheet Wisevision C2890616.
Flex 13 contatti, passo 0,7 mm, spessore 0,13 ±0,03 mm: non assumere compatibile
un connettore per flex da 0,3 mm. Mancano un connettore esatto oppure un processo
approvato di collegamento diretto, tolleranze cumulative, orientamento montato,
supporto meccanico e chiarimento VDD/VDDIO. Non è stato inventato un footprint
produttivo. `pcb/display-manufacturer-questions.txt` contiene una richiesta
tecnica pronta, NON inviata. Nessuna autorizzazione a ordini o messaggi esterni.

### Disponibilità parziale JLCPCB

`pcb/display-stock-refresh.json`: controllo pubblico del 16 novembre 2026,
10 posizioni / 6 codici, quantità ordinabili tutte positive. Display C2890616:
296 pezzi ordinabili; buffer C113281: 18.529; LDO C963429: 9.760. Totale dei
soli dieci componenti a prezzo unitario 1+: 2,6777 USD. Non è la distinta
completa né il prezzo della scheda; esclusi PCB, assemblaggio, scarti, imposte
e spedizione. Disponibilità catalogo non equivale a conferma di assemblaggio.
Nessun nuovo MPN o ordine. Riconfermare prima di produzione.

### PMIC e qualifiche residue

I tentativi U4.61 sono respinti (`pcb/vdc-pin-rejected-trial.json`): il
percorso frontale è chiuso dall'escape +1V8_SYS e dalle geometrie adiacenti.
Serve un riassetto congiunto; nessuna clearance è stata ridotta per accettarli.
Restano alimentazioni/uscite e sequenze, bypass SoC/DDR/eMMC, routing segnali,
integrità elettrica, termica passiva, meccanica e DFM. Nessuna dichiarazione
di scheda pronta alla produzione o di prestazioni/temperature misurate.

## Ethernet locale — prosecuzione del 16 novembre 2026

Quattro ulteriori stadi accettati dopo il display, tutti senza nuove violazioni
DRC e senza muovere footprint, cambiare componenti o rimuovere rame precedente:

| Stadio | Collegamenti | Nuovi elementi rame/via |
|---|---|---:|
| ethernet-reset-passives | R515.2, R516.1 e C501.1; masse R516/C501 | 126 |
| ethernet-strap-grounds | masse R522/R523/R524 | 12 |
| ethernet-center-tap | J2.P1–C531.1 e massa C531 | 35 |
| ethernet-bias-grounds | masse R513/R528/R529 | 11 |

Il reset locale ha 28,82 mm complessivi di pista frontale da 0,2 mm; non è una
raccomandazione di lunghezza né una qualifica di rumore/sequenza. U5.12 e il
GPIO a monte rimangono aperti. La pista center tap è frontale da 0,3 mm e misura
12,51 mm. Il contratto esistente richiede P1 collegato capacitivamente a massa,
non a 3,3 V; resta la qualifica specifica dell'abbinamento HR911130A/RTL8211F,
oltre a isolamento, chassis, EMC e protezioni. Nessuna prova Ethernet fisica.
Le masse aggiunte misurano complessivamente 8,30 mm. Metriche per stadio in
`pcb/display-routing-metrics.json` (nome storico, comprende anche Ethernet).

Il checkpoint cumulativo ha 164 verifiche di coppie e 45 test CAD, con cinque
prove di interruzione Ethernet e una per le masse bias. Le 229 reti
multi-pad aperte non misurano una percentuale di completamento. Il comando
`rebuild_local_copper.py` ricostruisce tutti i tredici stadi e verifica audit,
regressioni, inventario e hash. `rebuild_display_controls.py` resta compatibile
ma ora include anche Ethernet. Il test rollback è aggiuntivo ai 45 test CAD.

### Tentativi non adottati e dipendenze

- `pcb/control-routing-rejected-trials.json`: USB_ORIENTATION, USB_MUX_ENABLE_N
  ed EMMC_RESET_N non hanno trovato un'uscita via nella ricerca limitata.
  Occorre studiare escape e pad dei package con le regole/processo produttivo.
  Nessuna modifica alla scheda deriva dai tentativi; non provano impossibilità.
- `pcb/ethernet-clock-placement-trial.json`: prova di spostamento di C520 vicino
  a Y501, quattro orientamenti, passo 0,25 mm, percorso massimo 4 mm. I candidati
  rimasti dopo i courtyard non hanno percorso segnale; C521 non è stato
  affrontato dopo quel fallimento. Script `probe_ethernet_clock_placement.py`,
  uscita 2 quando non trova una soluzione. Nessun PCB candidato adottato.
- Il collegamento di massa Y501 provato con ricerca limitata a 3 mm non ha
  trovato un via nuovo legale; i ritorni del quarzo e i condensatori C520/C521
  richiedono riassetto congiunto, non piste lunghe aggiunte al layout attuale.
- Anche i bypass del PHY richiedono verifica della posizione rispetto ai pin:
  non sono stati collegati indiscriminatamente solo per ridurre le reti aperte.

Nessun nuovo MPN introdotto: questo lavoro non costituisce una nuova verifica
stock o preventivo dell'intera BOM. Restano tutte le qualifiche generali già
elencate, inclusi avvio PMIC, LPDDR4/eMMC, USB3, termica e fabbricazione.

## Riassetto clock Ethernet — 16 novembre 2026, checkpoint corrente

Supera il blocco geometrico del quarzo descritto nei tentativi precedenti.
La causa identificata era la riserva rame di H8105, che intercettava i pad
Y501: le riserve vietano piste/via/piani ma ammettono ancora footprint/pad
per rendere espliciti i conflitti preesistenti, come documentato in
`protect_stacked_mounts.py`. Non sono fori già eseguiti né fissaggi qualificati.
La zona non è stata eliminata o ridotta.

| Componente | Nuova posizione mm | Lato / orientamento |
|---|---|---|
| Y501 | 57,5; 31,9 | fronte / 180° |
| C520 | 58,5; 29,5 | fronte / secondo PCB |
| C521 | 56,5; 34,25 | fronte / secondo PCB |
| L501 | 64,5; 29 | retro / 0° |

Nessuno dei quattro componenti aveva connessioni rame iniziali. Le istanze pad,
reti e connessioni precedenti sono preservate; nessun rame esistente rimosso.
Lo spostamento L501 libera spazio davanti al PHY ma non ne qualifica il loop
SW, la corrente nei via, il rendimento, le interferenze col clock, la quota
sul retro o la meccanica del case. Quelle connessioni restano aperte.

Tre nuovi stadi: `ethernet-clock-placement`, `ethernet-clock-grounds`,
`ethernet-clock-pins`. I rami locali C520/Y501 e C521/Y501 misurano circa
1,71 e 1,66 mm; masse aggiunte complessive circa 3,46 mm. Il ramo U5.36
misura 2,06 mm; U5.37 raggiunge C521 sul fronte con 7,56 mm, poi il quarzo
attraverso il ramo locale. Il percorso di uscita rimane più lungo di quello
di ingresso e richiede analisi del carico/parassiti e prova dell'oscillatore.
Nessun via sui due segnali clock; i via sono sui ritorni di massa.
Il ramo di uscita è stato affinato dopo la prima ricostruzione completa;
ultimo stadio, audit, test e inventari rieseguiti sulla geometria finale.

La regola `PHY crystal pin neck` consente 0,15 mm solo alle piste PHY_XIN/XOUT
che intersecano il courtyard U5. I due colli misurano 0,8 mm ciascuno; il resto
è da 0,2 mm. Nessuna clearance ridotta. Il file regole finale deve coincidere
con la baseline più l'esatta appendice in `phy_clock_rules.py`; l'audit fallisce
se il contenuto diverge. Questa scelta non costituisce approvazione DFM.

Verifiche: 172 coppie, 51 test CAD, zero nuove violazioni DRC. Aggiuntivi:
1 test di rollback e 1 test che rimette Y501 nella posizione vecchia in memoria
e verifica che venga rilevata l'interferenza H8105. Il taglio C521 è geometrico
vicino al pad, perché tagliare solo gli elementi di uno stadio può lasciare
un percorso attraverso il rame aggiunto in seguito. I mock dei test non sono
misure sul dispositivo.

`pcb/mount-component-screen.json` confronta il nuovo PCB con ethernet-bias-grounds:
nessun nuovo conflitto, risolto Y501/H8105, 19 possibili interferenze restanti.
È uno screening conservativo fra rettangoli dei courtyard e cerchi circoscritti
alle riserve, non una verifica tridimensionale di montaggio. Non usare il solo
DRC come evidenza della compatibilità dei fissaggi.

`pcb/ethernet-rset-trial.json`: tentativo di avvicinare R513 e ricostruire la massa
respinto per assenza di percorso frontale e di via raggiungibile dal pin U5.39.
Cinque elementi massa erano rimossi soltanto nella copia in memoria. Nessun PCB
incompleto adottato: R513 mantiene posizione e massa precedenti; PHY_RSET aperta.

Restano frequenza/drive/load del quarzo (20 pF invariati), capacità parassite,
ritorni, alimentazione e avvio PHY, RSET, RGMII, MDI, magnetiche, bypass e
qualifiche elettriche/termiche/EMC. Nessuna prova fisica o simulazione analogica.
Nessun cambio MPN o nuova affermazione di disponibilità/prezzo JLCPCB.
