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
