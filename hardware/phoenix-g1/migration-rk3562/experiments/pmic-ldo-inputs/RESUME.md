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

Ulteriori prove escluse: RSET frontale e due deviazioni clock/RSET su copia
compatta, in conflitto con XIN/5V/masse. Leggere `clock-rset-escape-probe.json`
e `clock-rset-shifted-probe.json` nello studio compatto prima di ritentare.
Resoconto del lavoro: `pmic-ldo-inputs/pcb/joint-phy-progress.json`.

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

# Ripresa hardware — 16 novembre 2026

Fonte: `working-candidate.json`, percorso e SHA256 correnti.
PCB `pcb/ethernet-clock-pins.kicad_pcb`: 172 coppie, 51 test CAD passati,
nessuna nuova violazione DRC. Test aggiuntivi: rollback e interferenza H8105.
Dalla root, Python KiCad + `hardware/phoenix-g1/tools/rebuild_local_copper.py`.
Sono sedici stadi dopo five-volt-testpoint. README documenta regola aggiunta,
misure geometriche, prove e limiti. Nessuna modifica ROCK.

Y501/C520/C521 riposizionati; L501 spostato sul retro. Quarzo, condensatori,
masse e due pin PHY collegati. H8105 liberato da Y501. 19 possibili interferenze
meccaniche preesistenti ancora aperte; leggere mount-component-screen.json.
Nessuna connessione precedente persa. R513 tentata ma non spostata; RSET aperta.

227 reti multi-pad aperte. PMIC, escape USB/eMMC, alimentazioni PHY (L501 incluso),
SI/PI, avvio, termica, EMC/DFM e DS1 restano da completare/qualificare. I 13 pad
del display non sono presenti. PCB 90×40 mm, obiettivo 85×35 non validato.
Nessun ordine, commit/push o prova fisica in questa prosecuzione.
