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

## Checkpoint clock Ethernet — 16 novembre 2026

Ripartire da `hardware/phoenix-g1/migration-rk3562/experiments/pmic-ldo-inputs/working-candidate.json`.
PCB `pcb/ethernet-clock-pins.kicad_pcb`: gruppo quarzo PHY riposizionato e collegato.
Y501 libera la riserva H8105; C520/C521 vicini al quarzo, masse e pin U5.36/37
collegati. L501 sul retro: layout del suo convertitore ancora da qualificare.
172 coppie, 51 test CAD passati; nessuna nuova violazione DRC. Due test ulteriori
verificano rollback e rilevamento dell'interferenza meccanica. 227 reti multi-pad
ancora aperte; non è una percentuale di completamento.
Ricostruzione: `hardware/phoenix-g1/tools/rebuild_local_copper.py` con Python KiCad.
Ristretto collo da 0,15 mm solo sui due segnali clock dentro il courtyard U5;
clearance invariate, regola confrontata esattamente nell'audit cumulativo.
19 possibili conflitti meccanici preesistenti restano aperti. Il tentativo R513
non è adottato. Contorno 90×40 mm, obiettivo 85×35 non qualificato.
Nessun nuovo MPN, ordine, commit/push o modifica ROCK. Nessuna qualifica elettrica,
termica, EMC o produttiva. Le sezioni seguenti sono storiche.

## Active memory direction — 2026-11-10

User approved migration toward **1 GB LPDDR4 in one package**, compact layout, non-touch display and board-mounted five-way control. Qualification work is in `experiments/lpddr4-1gb/`. Active CAD remains DDR3 until the new memory electrical map, power and boot requirements are qualified. This supersedes the DDR3 direction as a target, not as a claim of completed CAD migration.


### Joint Wi-Fi power candidate — 2026-11-09

`experiments/wifi-vddio/joint-placement/final.kicad_pcb` is a separate candidate, not the accepted PCB or the transactional rebuild output. It passes geometric DRC and the independent Wi-Fi continuity audit including local VDDIO bypass, module grounds, internal buck and LPO. A negative test removes the 12 VDDIO back tracks and detects the intended disconnection without losing other module checks.

This resolves the previous bounded-routing failures by repositioning the buck/capacitor group, using an internal-layer buck output bridge and allowing a 7.3024 mm U25.20 ground path. The output bridge is approximately 11.516 mm; both paths require electrical layout review before adoption. Upstream PMIC and oscillator power are still incomplete. Displaced SoC decoupling also remains unqualified. No simulation or physical verification was performed; no fabrication release. The main PCB and its accepted reports are unchanged. See the candidate `result.json` for hashes and evidence.

### Oscillator supply candidate — 2026-11-09

`experiments/wifi-vddio/oscillator/candidate.kicad_pcb` extends the joint candidate with C2007 on the front at (52,28), local oscillator bypass and a connection to the module IO rail. DRC reports zero geometric violations; independent continuity and a deliberately disconnected feed test pass. Front copper was visually inspected. PMIC power remains absent, so this is not an operational clock/Wi-Fi result.

U4.55 escape is incompatible with the current generic 0.20 mm track/0.20 mm clearance recipe: adjacent 0.15 mm pads on 0.35 mm pitch leave 0.175 mm clearance around a centered 0.20 mm trace. A qualified fine-pitch power escape is needed, not a global relaxation of DRC. Source reservoir placement, current capacity and sequencing remain open. Main PCB and accepted reports remain unchanged.
