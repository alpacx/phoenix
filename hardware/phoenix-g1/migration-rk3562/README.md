# Phoenix RK3562 — checkpoint del PCB

## Checkpoint corrente

Il [PCB corrente](experiments/phy-power-parallel/layout-batch4.json) ha **304 unioni aperte su 194 reti** (−14 rispetto alle 318 del [checkpoint +5V_MAIN](experiments/phy-power-parallel/layout-main-5v-switch-output-width.json)). La catena è `layout-power-stubs` (317) → `layout-batch2` (310) → `layout-batch3` (306) → `layout-batch4` (304); ogni JSON riporta hash, padre, pad uniti, larghezza, lunghezza, strati e vie di ciascun raccordo. Su ogni PCB ricaricato: tutte le coppie del padre restano connesse (ora 902 coppie di layout più quattro del selettore USB), il rame e le piazzole del padre sono invariati, il DRC nativo conserva le stesse 121 segnalazioni via_dangling confrontate per tipo e UUID, e il [controllo dei ritorni](experiments/phy-power-parallel/runs/batch4/via-returns.json) non trova perdite di riferimento In1/In4 sotto il rame esistente vicino alle 10 vie aggiunte. Nessun rame non GND entra in In1/In4.

Raccordi chiusi: C1624.1 al tronco VDD_NPU su In2 (0,35 mm, 3,3 mm); R421.1 e C451.1 su VDD_LOGIC, C451.2–R421.2 (VDD_LOGIC_COM, 23,3 mm), R422.1–C452.1 su VDD_GPU, R431.1 (feedback DDR) su +1V1_LPDDR4, R1502.1–R1501.1 su XOUT24M (4,1 mm su F.Cu), il ponte J1.B7–J1.A7 di USB_DM (1,29 mm), U1.C21 con C1001.2 su GND, U1.1M4 su +3V3_IO (collo da 0,127 mm), il ramo VCCA_1V8 C1644/C1636 su B.Cu, la sfera U2.W12 di +1V1_LPDDR4 (10,4 mm a 0,20 mm su F.Cu, raccordo debole da qualificare) e due vie GND per U2.G10 e U2.T10. Vicino alle piste LPDDR, GND usa la distanza di regola di 0,0762 mm e le alimentazioni 0,10 mm; i segnali restano a 0,20 mm. Corrente, caduta, decoupling e integrità del segnale non sono qualificati.

Respinti dopo DRC e controllo del piano superati: i rami dei quarzi SoC e Wi-Fi (12–21 mm con 2–3 vie, limitati dal piazzamento), C1605–C1607 di VDD_CPU tramite 15,4 mm a 0,20 mm e la gamba singola USB_DM J1.A7–U9.2. [Evidenza](experiments/phy-power-parallel/rejected-306-crystal-decap-single-leg.json). Le quattro unioni +1V8_SYS agli angoli di U2 trovano un percorso solo con vie che tolgono riferimento In1 a DQ4_A, DQ4_B, DQ12_A e A3_B: non adottate.

Strumenti: [router a griglia](../tools/route_open_join.py), [driver con verifica](../tools/auto_close_joins.py), [scrittura del checkpoint](../tools/make_join_checkpoint.py); selettore USB con `experiments/usb-current-selector/verify_layout_delta.py`. Con le regole attuali, finestre di 3 e 6 mm e guardia delle vie 0,45–0,7 mm, il router non trova altri raccordi ([esiti](experiments/phy-power-parallel/screen-304-wide-window.json)). Delle 304 unioni, circa 97 coinvolgono U1: con la regola di 0,20 mm per le reti non DDR una pista non passa fra sfere a passo 0,5 mm, e una via passante non entra fra quattro sfere. Le coppie MDI e USB SS dipendono dalla scelta dello stack (7628/3313). Le uscite RGMII di U5 (RX pin 25/26, TX pin 13–20, circa 11 unioni) non si chiudono nemmeno togliendo le deviazioni esistenti (`--rip`, `--keepout`) o ricollocando i passivi liberi ([place_passive.py](../tools/place_passive.py)): serve ricollocare in gruppo i passivi attorno al PHY ([esito](experiments/phy-power-parallel/rejected-304-phy-u5-escape.json)).

Checkpoint precedente: Il [PCB corrente](experiments/phy-power-parallel/layout-main-5v-switch-output-width.json) ha **318 unioni aperte su 194 reti**. Due tratti su F.Cu all’uscita U15.5 di +5V_MAIN alimentano i pin U17.10, U17.11 e U17.12 del convertitore di sistema. Il rame raggiunge 0,60 e 0,70 mm nelle sezioni allargate. La resistenza geometrica dei due tratti scende da 6,838 a 5,415 quadrati (−20,81%). Nello scenario con rame esterno da 35 µm a 20 °C la resistenza stimata passa da 3,368 a 2,667 mΩ. Le 694 vie e i piani di massa In1 e In4 conservano la geometria precedente. Il DRC verifica le stesse 121 segnalazioni. La copia con il selettore USB verifica 888 coppie di layout e quattro del selettore. [Geometria, tagli e gruppi fisici](experiments/phy-power-parallel/runs/main-5v-switch-output-width/verification.json) · [DRC](experiments/phy-power-parallel/runs/main-5v-switch-output-width/drc.json) · [Selettore USB](experiments/phy-power-parallel/runs/main-5v-switch-output-width/usb.json)

Sulla eMMC, il passo da 0,50 mm e le quattro piazzole adiacenti a U8001.C2 chiudono il passaggio per EMMC_VDDI con pista e distanza rame entrambe da 0,20 mm. Sul banco VCCQ, la via candidata al riuso serve già C8003.1 e le sfere P3/P5. Liberare la sola via RESET_N vicina a M4 lascia forature incompatibili con il rame degli altri strati. [Sezioni, ostacoli e prova di interruzione](experiments/phy-power-parallel/emmc-318-vddi-vccq-breakout.json)

Nel [checkpoint LPDDR4 da 1,8 V](experiments/phy-power-parallel/layout-lpddr-c2301-1v8-bank.json), C2301.1 raggiunge l’uscita L405.2 del rail da 1,8 V con 6,677 mm di pista da 0,35 mm sul retro. In4 offre riferimento in tutti i 1.731 campioni sul nuovo ramo. La copia combinata con il selettore USB verifica 888 coppie di layout e quattro del selettore. Il DRC conserva le 121 segnalazioni preesistenti. [Verifica e inventario fisico](experiments/phy-power-parallel/runs/lpddr-c2301-1v8-bank/verification.json) · [DRC](experiments/phy-power-parallel/runs/lpddr-c2301-1v8-bank/drc.json) · [Selettore USB](experiments/phy-power-parallel/runs/lpddr-c2301-1v8-bank/usb.json)

La via da 1,1 V che alimenta le sfere U2.R5 e R8 si attesta ora sulla pista del proprio rail. Le prove di interruzione confermano che entrambi i rami mantengono la funzione precedente. La distanza dalla via GND più vicina scende da 1,152 a 0,852 mm. Sui tratti preesistenti restano 187 campioni che perdono riferimento, tutti entro l’apertura della via sul proprio ramo da 1,1 V. La proiezione poligonale conferma la conservazione del piano sotto il rame dei segnali. Restano da verificare la risposta ai transitori e la caduta sotto carico. [Confronto degli 88 siti](experiments/phy-power-parallel/runs/lpddr-c2301-1v8-bank/via-sites.json)

Le due polarità DQS1 del byte alto del canale A hanno già vie a entrambi i terminali. Nelle finestre esaminate, il modello con i margini di progetto non trova un corridoio continuo per la coppia. Riducendo la distanza di prova a 76,2 µm verso tutto il rame estraneo, i due rami separati trovano percorsi su In3, ma nessuno dei 16 tentativi riesce a farli coesistere. Il passaggio più vicino interessa A1_A e le vie DQ6_A, DQ0_A e GND. [Terminali, geometria e ostacoli](experiments/phy-power-parallel/lpddr-318-channel-a-upper-byte-strobe.json)

Per SDIO Wi-Fi, due pose di R2013 presso il modulo rispettano le distanze del rame ma lasciano aperto il collegamento tra WIFI_D3 e la sua alimentazione attraverso il resistore. La ricerca locale non trova vie ordinarie per D0 o D3 sui terminali di modulo e SoC. [Pose dei resistori e uscite dei segnali](experiments/phy-power-parallel/wifi-318-d0-d3-bias-and-escape.json)

Nel [checkpoint precedente](experiments/phy-power-parallel/layout-sys-3v3-pmic-trunk-width.json), il tronco +3V3_SYS di 24,65 mm su In4 alimenta da C1304.1 gli ingressi buck del PMIC, inclusi U4.10 e U4.11. Tre allargamenti riducono il rapporto lunghezza/larghezza complessivo da 30,813 a 28,607 quadrati (−7,16%). Con rame interno da 15,2 µm a 20 °C la resistenza stimata del tratto scende da 34,95 a 32,45 mΩ. Il margine al bordo resta 0,450 mm. [Geometria e gruppi fisici](experiments/phy-power-parallel/runs/sys-3v3-pmic-trunk-width/verification.json) · [Prove di interruzione](experiments/phy-power-parallel/runs/sys-3v3-pmic-trunk-width/cut-inventory.json)

L’allargamento occupa 7,757 mm² del piano GND di In4. Il piano resta continuo e il passaggio di massa più stretto nella finestra conserva 0,424 mm. Il confronto dei poligoni non rileva perdite di riferimento sotto piste, pad o vie di B.Cu e In3, anche estendendone le proiezioni di 0,10 mm. Il PCB verifica tutte le 887 coppie di layout e quattro del selettore USB, con le stesse 121 segnalazioni DRC. [Piano GND](experiments/phy-power-parallel/runs/sys-3v3-pmic-trunk-width/plane-global.json) · [Sezioni del corridoio](experiments/phy-power-parallel/runs/sys-3v3-pmic-trunk-width/corridor.json) · [DRC](experiments/phy-power-parallel/runs/sys-3v3-pmic-trunk-width/drc.json) · [Selettore USB](experiments/phy-power-parallel/runs/sys-3v3-pmic-trunk-width/usb.json)

Sul rail VDD_CPU restano aperti il positivo di C1014 verso L1001.2 e il banco di C1603/C1604/TP8 verso le sfere del SoC. Delle 21 pose posteriori di C1014 che rispettano i controlli su rame, fori e nodo di commutazione, nessuna ha dato entrambi i rami locali di alimentazione e massa nelle geometrie provate. La ricerca del raccordo di TP8 sul retro e di una via ordinaria fuori piazzola ha dato zero soluzioni nelle finestre esaminate. [Criteri, finestre e risultati](experiments/phy-power-parallel/cpu-319-c1014-and-probe-bank-access.json)

Nel [checkpoint LPDDR4](experiments/phy-power-parallel/layout-lpddr-1v8-source-width.json), sull’alimentazione LPDDR4 da 1,8 V, due sezioni del percorso fra L405.2 e U2.F1 sono più larghe su In3. La rimozione dei singoli segmenti su copie identifica quali interrompono la connessione al carico. Per queste piste in serie, la somma dei rapporti lunghezza/larghezza scende da 29,414 a 26,712 quadrati (−9,19%). Con rame interno da 15,2 µm, come nella variante di stackup JLC studiata, la resistenza stimata a 20 °C passa da 33,36 a 30,30 mΩ. La stima esclude vie, strati esterni e transitori. Il margine al bordo resta 0,300 mm e tutti i 4.371 campioni sotto i tratti modificati trovano rame di massa su In4. [Verifica del rame](experiments/phy-power-parallel/runs/lpddr-1v8-source-width/verification.json) · [Prove di interruzione](experiments/phy-power-parallel/runs/lpddr-1v8-source-width/cut-inventory.json)

Il DRC conferma le 121 segnalazioni preesistenti. Il controllo dei gruppi fisici conferma la connettività del checkpoint precedente e la copia combinata con il selettore USB verifica 887 coppie di layout più quattro del selettore. [DRC](experiments/phy-power-parallel/runs/lpddr-1v8-source-width/drc.json) · [Selettore USB](experiments/phy-power-parallel/runs/lpddr-1v8-source-width/usb.json)

Nel [checkpoint precedente](experiments/phy-power-parallel/layout-lpddr-d1-feed.json), la sfera U2.D1 della LPDDR4 raggiunge il banco da +1,1 V di C1646 e l’uscita L403.2 tramite tre tratti su F.Cu, larghi 0,20 mm e lunghi complessivamente 3,646 mm. Il raccordo usa una via esistente. Nel passaggio accanto a U2.A2, B2 e C2 restano 0,10 mm dalle piazzole e 0,20 mm dalla pista GND di C1, ai minimi nominali del layout. Dei 1.107 campioni su In1, i 161 esterni al rame di massa cadono tutti nell’apertura della via di arrivo. La risposta ai transitori e il margine di fabbricazione restano da qualificare. [Misure sul PCB ricaricato](experiments/phy-power-parallel/runs/lpddr-d1-feed/verification.json)

Sul fronte, una ricerca su griglie da 15 e 10 µm non ha trovato un percorso da U2.D5 o U2.D8 al banco da +1,1 V entro 7 mm con pista da 0,20 mm. Anche la ricerca locale di vie passanti da 0,45/0,20 mm ha dato zero siti utilizzabili nei vincoli provati. Il ponte diretto D5–D8 lascerebbe entrambe le sfere scollegate da L403.2. [Coordinate e limiti della ricerca](experiments/phy-power-parallel/lpddr-319-d5-d8-powered-bank-screen.json)

Le sette sfere VDD_LOGIC del SoC sono unite solo sul fronte. Le due vie dello stesso rail appartengono al gruppo separato di L401.2. Per la presa di feedback R421/C451, la ricerca di una pista da 0,20 mm su griglia da 10 µm si ferma almeno 4,415 mm prima del perimetro di U1, anche con distanza rame ridotta a 76,2 µm nel modello. Lo studio individua nel fanout del SoC il primo punto da riprogettare per raggiungere il carico. [Schema, gruppi fisici e ricerca su F.Cu](experiments/phy-power-parallel/logic-319-kelvin-load-access.json)

Il ritorno fra i piani del clock PHY_RXCLK resta a 1,363 mm dalla via del segnale. Le 1.413 pose posteriori di R507 che conservano la distanza dal pin sorgente U5.25 non liberano uno dei 437 siti di ritorno esaminati. La via GND candidata al riuso è anche la più vicina al pad esposto U5.41 (0,700 mm). [Posizioni e confronto dei ritorni](experiments/phy-power-parallel/phy-319-rxclk-ground-reuse.json)

R424 e C454 sono sul retro e raggiungono il banco NPU presso C1622.1. La presa lato carico è riferita a In4. Restano aperti il feedback a U4.64 e il raccordo tra L404.2 e il carico. La stabilità dell’anello richiede una verifica elettrica.

Lo studio meccanico sul PCB corrente trova una piastra rettangolare da 14,10 × 15,80 mm, con contatto da 12 mm centrato sul SoC, almeno 0,20 mm dalle sagome frontali e 0,96 mm dal rame di TP11. Nel modello in pianta un solo appoggio posteriore aggiuntivo non racchiude il contatto. Due appoggi candidati da Ø4 mm danno un margine di 2,565 mm ai suoi angoli con i tre fissaggi ausiliari. Restano da verificare quote verticali, tolleranze, precarico e prestazioni termiche. [Proiezioni CAD](experiments/phy-power-parallel/spreader-320-rectangular-plate-and-rear-support.json)

La prova di riposizionamento congiunto di C1501 e C1502 presso Y1 chiude i due carichi del quarzo con 318 unioni aperte e 888 coppie di layout, più quattro del selettore USB. Il layout di partenza di quella prova aveva 320 unioni. Y1.1 dista ancora 16,29 mm da U1.AG25, e il percorso tramite R1501 verso U1.AF25 misura almeno 23,28 mm in pianta. Entrambi i raccordi al SoC sono aperti. [Prova su PCB ricaricato](experiments/phy-power-parallel/soc-crystal-320-load-bank-transfer.json)

Una copia del layout corrente riposiziona U22 sul retro e chiude MDI0 e MDI1 fra U22 e J2. Il controllo su disco dà 316 unioni aperte, 891 coppie di layout e quattro collegamenti del selettore USB senza nuove segnalazioni DRC. Le proiezioni sui piani di riferimento non mostrano vuoti estranei ai terminali nei punti campionati. L’esportazione della variante di schema conferma U22.6 su ETH_MDI1_N come unica modifica su 1.996 assegnazioni. L’analisi delle uscite lato PHY non trova una coppia di vie ordinarie libera per MDI0 o MDI1 nel campo provato. Restano aperti i quattro raccordi al PHY e la verifica dell’impedenza al connettore. [Netlist e uscite PHY](experiments/phy-power-parallel/runs/u22-320-two-jack-pairs-transfer/schematic-and-phy-parity.json) [Copia sperimentale](experiments/phy-power-parallel/mdi-320-u22-mdi01-cumulative-transfer.json)

Nessun pinmux alternativo rende già accessibili MOSI, clock e chip select del display. I gruppi SPI0_M0 e SPI1_M0 servono espansione ed Ethernet. I gruppi M1 esaminati richiedono tre nuove uscite. La revisione registra anche una divergenza fra le tensioni riportate nella tabella operativa e le opzioni degli schemi di riferimento e del TRM. Il PCB dichiara 1,6 mm senza uno stackup esplicito, benché il progetto includa l’altezza nelle misure di lunghezza. [Mappa SPI e domini](experiments/phy-power-parallel/display-320-spi-pinmux-domain-audit.json) · [Vincoli di stackup](experiments/phy-power-parallel/stack-320-routing-constraints-audit.json)

Una copia KiCad rende esplicito lo stackup JLC06161H-3313 a sei strati. Il nominale del PCB è 1,6 mm e la somma degli spessori pubblicati per rame e dielettrici è 1,5384 mm. La prova conserva 320 unioni aperte, 886 coppie di layout e quattro collegamenti del selettore USB senza nuove segnalazioni DRC. Il confronto geometrico rileva 147 coppie piazzola–pista sotto 0,09 mm attorno a U1. Restano da concordare il processo BGA e la geometria d’impedenza. [Variante e misure CAD](experiments/phy-power-parallel/stack-320-jlc06161h-3313-variant.json)

Il checkpoint adottato riposiziona due brevi tratti da 0,20 mm accanto a U1. Le distanze minime passano da 79,1 a 95,1 µm presso AB26 e da 82,6 a 99,2 µm presso AG21. Le coppie piazzola–pista sotto 0,09 mm scendono da 147 a 137, da 143 a 137 contando una sola volta le piste coincidenti. Il tratto DEBUG_RX conserva il riferimento In1 e il PCB verifica 320 unioni, 886 coppie di layout e quattro collegamenti USB senza nuove segnalazioni DRC. [Copia DFM cumulativa](experiments/phy-power-parallel/dfm-320-ab26-ag21-spacing.json)

La prova su EXP_I2C_SDA è stata respinta. Spostando un nodo di 10 µm, il margine verso AE22 sale da 86,9 a 90,3 µm, ma quello verso AE21 scende da 86,9 a 82,8 µm. Nella sezione fra le due sfere, il passo di 500 µm, il diametro delle piazzole di 250 µm e la pista da 76,2 µm consentono al massimo 86,9 µm per lato con pista centrata. [Misure e confronto sulla copia](experiments/phy-power-parallel/runs/dfm-320-lotto1-ae22-study/study.json)

Sul checkpoint DFM da 320 unioni, 134 dei 137 casi sotto 90 µm riguardano 64 segmenti che attraversano una sezione con margine bilanciato massimo di 86,9 µm. Gli altri tre riguardano segmenti consecutivi del clock LPDDR4_CLKP_B adiacenti alla stessa strozzatura C14–C15. Modificare quella fuga richiede di riesaminare entrambi i rami del clock e il piano di riferimento. [Classificazione per piazzola e tratto](experiments/phy-power-parallel/runs/dfm-320-lotto2-residual-classification/classification.json)

## Distribuzione locale di +1V1_LPDDR4

Il [checkpoint storico](experiments/phy-power-parallel/layout-debug-rx-front-probe.json) aveva **327 unioni aperte su 195 reti**. Sulla LPDDR4 il CAD verifica le sfere collegate al rispettivo banco o piano di massa: 28 su 46 a +1V1_LPDDR4, 2 su 8 a +1V8_SYS, 56 su 58 a GND. Restano da qualificare la risposta ai transitori e la distribuzione della corrente. [Inventario per sfera](experiments/phy-power-parallel/ddr-336-supply-balls-by-physical-bank.json)

Il punto di prova UART RX TP11 da 1 mm è sul lato componenti e raggiunge U1.AF20 con una pista da 0,20 mm lunga 3,25 mm, con riferimento di massa continuo su In1. La via del segnale accessorio CS0 usa rame/foro da 0,45/0,20 mm. I tre raccordi modificati conservano la continuità originale, compreso J3.34. Il punto si sonda prima del montaggio del dissipatore e del case. L’accesso con la dima resta da provare. [DRC e continuità sul PCB ricaricato](experiments/phy-power-parallel/debug-328-rx-front-probe-native.json)

I banchi GPU di C1617/C1619/C1620 e NPU di C1623 raggiungono i rispettivi condensatori locali e le sfere del SoC. I tratti GPU da 0,40 mm e NPU da 0,50 mm coesistono sul PCB ricaricato. La resistenza stimata delle sole piste a 20 °C è rispettivamente 38,4 e 23,2 mΩ. Il modello esclude vie, condensatori e transitori. Restano aperti i raccordi di alimentazione da L402 e L404. [Geometria e ipotesi di calcolo](experiments/phy-power-parallel/soc-dual-inner-bulk-geometry.json) · [Controllo dei corridoi LPDDR4](experiments/phy-power-parallel/soc-328-paired-ddr-region-parity.json)

C1618 da 22 µF raggiunge le sei sfere VDD_GPU del SoC attraverso una via passante e una pista sul retro da 0,27 mm. La piazzola negativa conserva il contatto con la pista di massa esistente. Il foro è esterno alle piazzole su entrambe le facce. Il collegamento del regolatore a questo banco resta aperto. [Verifica della geometria e della continuità](experiments/phy-power-parallel/gpu-331-c1618-package-native.json)

C1622 da 22 µF è collegato al banco VDD_NPU di C1621 e alle cinque sfere SoC servite dal banco. C1614 da 22 µF entra nel banco locale VDD_LOGIC di C1610 e C1611. La distanza in pianta dalla sfera più vicina del rispettivo rail passa da 11,42 a 5,00 mm per C1622 e da 5,71 a 7,33 mm per C1614. Entrambi i collegamenti ai regolatori e il raccordo fra banco VDD_LOGIC e SoC restano aperti. [Verifica del rame](experiments/phy-power-parallel/soc-333-bulk-site-exchange-native.json)

C1632 e C1631 condividono il banco locale VCCA1V8_PMU. La distanza in pianta fra il positivo di C1632 e la sfera SoC più vicina dello stesso rail passa da 18.65 a 9.75 mm. Restano aperti i collegamenti del banco al regolatore e al SoC.

C1610 e C1611 condividono il banco locale VDD_LOGIC. La distanza in pianta fra il positivo di C1610 e la sfera SoC più vicina dello stesso rail passa da 9.24 a 8.33 mm. Restano aperti i collegamenti del banco al regolatore e al SoC.

C1629 e C1630 condividono il banco locale VDDA0V9_PMU. La distanza in pianta fra il positivo di C1629 e la sfera SoC più vicina dello stesso rail passa da 4.81 a 1.21 mm. Restano aperti i collegamenti del banco al regolatore e al SoC.

Sul PCB ricaricato, i sei interventi su R1507, R514, R2103, C1305, C1011 e R521 hanno distanze minime dal bordo dei fori superiori a 0,11 mm. Restano undici intersezioni foro–rame su passivi. [Distanze misurate nel CAD](experiments/phy-power-parallel/passive-336r-six-reloaded-land-gaps.json) · [Intersezioni residue](experiments/phy-power-parallel/passive-336r-drill-overlap-inventory.json)

Il pull-up RXD3 R521 sul retro raggiunge il via con un ramo da 0,20 mm fuori dalla sua piazzola. Sul fronte il medesimo foro interseca ancora R510.2. Il pin U5.22 resta da collegare.

C1011 è ruotato di 15° sullo stesso centro. Il rame del rail CPU e il ritorno di massa conservano tutte le piste e tutti i via. Il foro del rail è fuori dalla piazzola.

C1305 mantiene il rail da 0,80 mm e ha un ritorno dedicato da 0,40 mm verso un nuovo via 0,60/0,30 mm. Le lunghezze positive e di massa complessive fra le piazzole e i via scendono da 2,801 a 2,666 mm. Il foro di alimentazione è fuori dalla piazzola. [Verifica della disposizione](experiments/phy-power-parallel/bulk-336p-simultaneous-capacitor-and-return-via.json)

Il pull-up R2103 sul retro mantiene CS0 e alimentazione PMU, con il foro CS0 fuori piazzola. Il rame aggiunto è da 0,20 mm sul segnale e 0,35 mm sul rail.

Anche il pull-up MDIO R514 ha il foro di alimentazione fuori piazzola e mantiene il ramo da 0,20 mm verso il via PHY. Il segnale MDIO del resistore resta aperto.

Il resistore R1507 è spostato di 0,60 mm per liberare dal foro di RESET_N la sua piazzola. Il raccordo da 0,20 mm va direttamente al via esistente. Il collegamento THERMAL_SHUTDOWN al SoC è ancora aperto.

Il foro passante sul ramo di alimentazione BUCK5 è stato spostato fuori dalla piazzola positiva di C425. La distanza nominale foro–rame della piazzola è 0,125 mm. Il rame tra condensatore e U4.54 è conservato. Il raccordo tra strati aggiunge 0,95 mm per lato e la distanza dal via di massa più vicino passa da 2,283 a 2,864 mm. La risposta ai transitori resta da misurare.

Il via di massa del condensatore di carico C521 del quarzo PHY ha ora 0,121 mm di distanza nominale fra foro e piazzola. Il percorso di massa si allunga di 0,212 mm. Avvio e frequenza del quarzo restano da misurare sul prototipo.

Sul ramo di pull-up eMMC D0 il foro passante dista ora 0,134 mm dal rame di R8001.2. Il ramo è più lungo di 0,192 mm. Il via di ritorno più vicino dista 0,680 mm. Restano aperte la chiusura e la verifica temporale del bus eMMC.

Le sfere N11 e P12 della LPDDR4 raggiungono la massa comune con un raccordo F.Cu da 0,20 mm lungo 1,975 mm. La pista di alimentazione sulla sfera R12 conserva 0,35 mm di larghezza e termina 30 µm più a est. Il riferimento In1 è continuo in tutti i punti campionati lungo i due percorsi. [Verifica CAD](experiments/phy-power-parallel/ground-343-n11-connected-return.json)

Le sfere R1 e T2 raggiungono ora C1646 e l’uscita di L403 su un ramo F.Cu da 0,35 mm. Per liberare il passaggio, P1 usa un nuovo via di massa da 0,60/0,30 mm. Il vecchio via resta collegato. Sul tratto di massa modificato la resistenza geometrica passa da 3,89 a 3,60 quadri, mentre la distanza fra il nuovo via e il via VDD più vicino cresce da 0,81 a 1,57 mm. L’impedenza del percorso resta da qualificare. [Geometria e riferimento](experiments/phy-power-parallel/ddr-342-r1-barrel-reference-boundary.json)

C1625 raggiunge il banco +3V3_PMU attraverso 1,195 mm di rame. Il ritorno di massa misura 0,674 mm e la piazzola positiva dista 3,155 mm dalla sfera SoC 1L11 in proiezione. Il collegamento alle sfere del SoC e quello a U4.31 restano aperti. [Verifica CAD](experiments/phy-power-parallel/pmu-341-c1625-return-reference.json)

Anche C1626 raggiunge il banco +3V3_PMU. Il rame misura 0,365 mm sul positivo e 0,716 mm dal terminale di massa al nuovo via da 0,45/0,20 mm. Le sfere SoC e U4.31 restano da collegare. [Verifica CAD](experiments/phy-power-parallel/pmu-340-c1626-return-reference.json)

La sfera H5 della LPDDR4 raggiunge H8 e L403.2 tramite 2,242 mm di rame da 0,35 mm. Due rami di massa usano il tronco già collegato al via da 0,60/0,30 mm. Il via di cucitura preesistente è conservato. [Verifica CAD](experiments/phy-power-parallel/ddr-339-h5-local-reference.json)

La sfera R5 è connessa a L403 con due tratti da 0,35 mm e lunghezza totale 1,562 mm. Il via GND riposizionato riunisce le due sfere e il ritorno di C1632. Un secondo via GND da 0,45/0,20 mm porta il ritorno più vicino a CS0N_B da 1,173 a 0,790 mm. [Verifica dei siti](experiments/phy-power-parallel/ddr-336-r5-cs-return-site-screen.json)

Il banco di L403 alimenta ora anche le sfere G2 e H1. Il ramo GND di J1 raggiunge la piazzola K2 e condivide il suo accesso al piano. L’impedenza del ritorno condiviso resta da validare. [Percorsi CAD](experiments/phy-power-parallel/ddr-338-g2-final-paths.json)

Le sfere W5 e W8 della LPDDR4 sono collegate tra loro con 2,168 mm di rame da 0,35 mm. Per alimentarle resta da raccordare questo gruppo al banco. I due rami di massa hanno accessi separati. La distanza dal via di ritorno più vicino è conservata entro 1 µm per i via delle altre reti entro 3 mm dalla modifica. [Verifica dei ritorni](experiments/phy-power-parallel/ddr-338-w5-nearby-return-vias.json)

Il banco di C1646 è già collegato al lato di uscita L403.2. Restano aperti il nodo di commutazione PMIC_SW3 verso L403.1 e il feedback DDR_FB. Caduta complessiva e transitori richiedono verifica elettrica. Il PCB ricaricato conserva 880 coppie fisiche e passa il DRC differenziale. [Verifica dei singoli tratti](experiments/phy-power-parallel/ddr-377-package-branch-native.json) · [Inventario delle connessioni](experiments/phy-power-parallel/debug-rx-front-probe-independent-inventory.json)

Due ulteriori raccordi da 0,30 mm, lunghi 0,711 mm, collegano AA10 al banco alimentato e A9 al gruppo B8–B10. Il gruppo A9–B8–B10 ora raggiunge L403.2. Con rame da 35 µm a 20 °C ciascun tratto vale circa 1,17 mΩ, esclusi pad e package. [Verifica di rame, riferimento e DRC](experiments/phy-power-parallel/ddr-365-local-300um-native.json)

La sfera W1 raggiunge L403.2 con 2,425 mm di rame da 0,30 mm sul fronte, un via da 0,45/0,20 mm e 1,261 mm di rame da 0,50 mm sul retro. I due via di massa più vicini distano 0,805 e 0,850 mm. Tre campioni ai bordi si trovano entro 2,5 µm oltre il raggio nominale degli antipad del rail. [Continuità](experiments/phy-power-parallel/ddr-363-w1-local-feed-native.json) · [Ritorni](experiments/phy-power-parallel/ddr-362-w1-current-reference.json)

Anche H8 raggiunge L403.2. Il ramo corre per 2,070 mm sul fronte e 9,819 mm su In2. La proiezione su In1 conserva il riferimento per le altre piste sui 305 campioni confrontati. La resistenza del ramo e la risposta del carico richiedono verifica sullo stackup definitivo. [Misure geometriche](experiments/phy-power-parallel/ddr-361-h8-current-reference.json)

R8 raggiunge la stessa uscita con 1,994 mm sul fronte e 11,184 mm su In2. Il via GND più vicino dista 1,152 mm. I 59 campioni sugli altri segnali non mostrano perdita di piano rispetto al checkpoint precedente. [Riferimento del ramo R8](experiments/phy-power-parallel/ddr-360-r8-current-reference.json)

K1 e N1 raggiungono L403.2 tramite un nuovo via e un percorso su In3. Nessuna perdita di piano sui 238 campioni delle piste circostanti. La prima variante A9 è stata scartata perché il suo antipad interrompe il riferimento di DM1_A, DQ14_A e DQ15_A in 89 campioni. [Verifica K1](experiments/phy-power-parallel/ddr-359-k1-current-reference.json) · [Esclusione A9](experiments/phy-power-parallel/ddr-358-a9-foreign-track-plane-delta.json)

Sul retro, il condensatore C443 da 22 µF raggiunge i due via di uscita di L403 con piste da 0,8 mm lunghe 1,445 e 2,192 mm. I due rami di massa da 0,985 mm terminano su via da 0,60/0,30 mm collegati a entrambi i piani. Nel campionamento CAD due punti ai bordi delle piste di alimentazione ricadono appena oltre il raggio nominale degli antipad. La risposta ai transitori del convertitore rimane da verificare. [DRC e continuità](experiments/phy-power-parallel/ddr-366-c443-offset-native.json) · [Geometria dei ritorni](experiments/phy-power-parallel/ddr-365-c443-current-loop-reference.json)

Il ramo VDD1 da 1,8 V raggiunge F12. Il collegamento del singolo pin misura 2,497 mm da 0,20 mm sul fronte e 3,059 mm da 0,50 mm su In3. Il via GND più vicino dista 0,767 mm. La geometria conserva il riferimento di tutte le piste vicine nei 224 punti confrontati. [Ramo F12](experiments/phy-power-parallel/ddr-358-f12-current-reference.json)

Il confronto dei riempimenti GND fra i checkpoint a 383 e 358 unioni copre 12 posizioni di via e 3.331 punti sulle piste preesistenti. Le 60 variazioni di copertura ricadono tutte nell’antipad del medesimo rail da 1,1 V sul retro. La stessa verifica sulla variante A9 respinta rileva 89 punti di perdita su tre segnali DDR. [Confronto cumulativo](experiments/phy-power-parallel/return-plane-comparison-383-to-358.json) · [Controprova A9](experiments/phy-power-parallel/return-plane-comparison-a9-exclusion.json)

Per A9 il nuovo passaggio da 0,25 mm conserva il piano sotto tutti i segnali vicini. L’alimentazione percorre 4,835 mm totali sul fronte e su In2. Un via GND da 0,45/0,20 mm riunisce i due piani a 0,707 mm dal via del rail. [Verifica del percorso](experiments/phy-power-parallel/ddr-357-a9-safe-current-reference.json) · [Verifica della cucitura GND](experiments/phy-power-parallel/ddr-357-a9-stitch-native.json)

Il ritorno di C1605.2 raggiunge In1 e In4 con un via ordinario da 0,45/0,20 mm e due tratti da 0,30 mm. La distanza del via di +3V3_IO più vicino da un ritorno GND scende da 6,46 a 1,26 mm. C1605.1, sul rail VDD_CPU, è ancora aperto. [Verifica dei due piani, continuità e DRC](experiments/phy-power-parallel/ground-356-c1605-io-stitch-native.json) · [Coesistenza con il selettore USB](experiments/phy-power-parallel/usb-selector-c1605-io-ground-return-coexistence.json)

Le sfere GND M27 e P26 del processore raggiungono ora la massa principale con 5,748 mm di pista da 0,25 mm sul fronte. Tutti i 1.518 campioni centrali e laterali hanno un piano di riferimento su In1. Il ramo presenta circa 11,3 mΩ di resistenza del rame a 20 °C, ipotizzando 35 µm di spessore. [Continuità, maschera e DRC](experiments/phy-power-parallel/ground-355-m27-p26-native.json) · [Coesistenza del selettore USB](experiments/phy-power-parallel/usb-selector-m27-p26-ground-coexistence.json)

Per G3, T3 e T10 della LPDDR4, il controllo a passo 12,5 µm usa il contorno dell’apertura di maschera e il foro da 0,20 mm. Il miglior margine geometrico foro–apertura raggiunge 0,088 mm su T10 e circa 0,002 mm su G3 e T3. Riservando nominalmente 0,20 mm, tutti i candidati a singolo ostacolo ricadono contro altre piazzole fisse del package. Questi via restano esclusi sulla versione adottata. [Finestre ai bordi delle piazzole](experiments/phy-power-parallel/ground-355-lpddr-offland-mask-web.json) · [Ostacoli rimanenti](experiments/phy-power-parallel/ground-355-lpddr-reserved-mask-obstacles.json)

Il secondo condensatore di uscita da 22 µF, C433, è ora sul retro. Due piste da 0,8 mm raggiungono l’uscita di L403 e due rami da 0,8 mm arrivano ai piani GND mediante fori da 0,30 mm. Il nuovo tratto di PMIC_SCL misura 9,187 mm con pista da 0,20 mm. Il controllo a passo 12 µm dei tre percorsi conserva i riferimenti salvo gli antipad del rispettivo segnale. Il regolatore richiede ancora la chiusura di SW e feedback e la verifica dei transitori. [Verifica su rame e fori](experiments/phy-power-parallel/ddr-354-c433-restored-scl-current-qualification.json) · [DRC e connessioni](experiments/phy-power-parallel/ddr-354-c433-restored-scl-terminals.json)

### Alimentazione eMMC

Il condensatore di bypass da 100 nF C8003 è ora sul fronte e raggiunge la sfera P3 attraverso la via VCCQ esistente. Le due piste nuove sono larghe 0,30 mm. Il ramo di alimentazione misura 1,003 mm fino alla via e il ramo di massa 1,098 mm. Sul PCB ricaricato le due piazzole raggiungono rispettivamente P3 e la massa principale. Restano da collegare alla distribuzione VCCQ i gruppi C6, M4–N4, P5 e il dominio del processore. [Verifica elettrica CAD e DRC](experiments/phy-power-parallel/emmc-353-c8003-native-p3.json)

### Bypass locale del processore

Il condensatore C1602 da 4,7 µF raggiunge il gruppo di sei sfere VDD_CPU attraverso la stessa via del carico. I due rami sul retro hanno larghezza 0,60 mm. Entrambi arrivano ai terminali previsti e conservano il riferimento a In4, salvo l’antipad del via di alimentazione. Il collegamento tra l’uscita dell’induttore L1001 e il gruppo del processore è ancora aperto. [Controllo delle piazzole e dei ritorni](experiments/phy-power-parallel/cpu-352-c1602-local-decoupling.json)

### Alimentazione della sfera P5 della eMMC

La sfera P5 è collegata a P3 sulla rete VCCQ tramite rame da 0,225 mm. I ritorni di P4 e P6 mantengono lo stesso foro passante da 0,30 mm e le stesse larghezze delle piste di massa. Il diametro esterno delle due vie è ora 0,55 mm, con anello nominale da 0,125 mm. Le regole del progetto richiedono almeno 0,10 mm. JLCPCB indica per il multistrato una differenza diametrale preferita di almeno 0,15 mm, qui pari a 0,25 mm. I controlli CAD non sostituiscono l’ispezione e la prova di accensione. [PCB ricaricato e verifiche](experiments/phy-power-parallel/emmc-351-p5-supply-coupon.json) · [Capacità JLCPCB](https://jlcpcb.com/capabilities/pcb-capabilities)

### Alimentazione I/O del processore

Un ramo da 0,30 mm collega le sfere 1G15 e 1H14 di U1. Per ricavare il passaggio è stato spostato di 0,088 mm il terminale di una pista di massa da 0,50 mm entro la sua piazzola. Le connessioni di ritorno di 1F15, 1G14 e 1G13 sono conservate. Il piano di massa copre tutti i 582 campioni del controllo locale. Il collegamento fra queste due sfere lascia aperta l’alimentazione degli altri gruppi I/O. [Verifica CAD](experiments/phy-power-parallel/soc-350-g15-h14-io-native.json)

### Alimentazione LPDDR4 di U2.R12

La sfera R12 ora raggiunge il banco di uscita di L403 attraverso N12. La pista da 0,35 mm misura 1,596 mm. Un tratto del PWM del display è stato spostato lateralmente di 0,225 mm mantenendo entrambi gli estremi e la larghezza da 0,20 mm. I 1.404 campioni su entrambi i percorsi sono coperti da massa su In1. Il percorso di commutazione e il feedback di BUCK3 rimangono aperti. [Verifica CAD e continuità](experiments/phy-power-parallel/ddr-349-n12-r12-pwm-native.json)

### Ritorno di massa della sfera U2.T12

U2.T12 raggiunge la massa principale attraverso U2.V12. I tre tratti sul fronte misurano in totale 1,459 mm e hanno larghezza 0,25 mm. Il piano In1 copre tutti i 378 campioni del ramo. Il controllo ha verificato la continuità fino alla piazzola esposta U4.69 e il rame precedente è conservato per intero. [Verifica sul PCB ricaricato](experiments/phy-power-parallel/ddr-348-t12-ground-native.json)

### Masse G3 e T3 della LPDDR4

Due rami simmetrici da 0,25 mm collegano G3 a J3 e T3 a P3. Ogni ramo misura 1,341 mm, resta su F.Cu e ha un riferimento continuo su In1. L’intersezione geometrica fra rame di pista e piazzola vale 0,0241 mm² alla partenza e 0,0271 mm² all’arrivo. Il PCB ricaricato conferma entrambe le connessioni alla massa principale. [Contatti e continuità](experiments/phy-power-parallel/ddr-348-ground-g3-t3-pad-entry.json)

### Induttore e configurazione del PHY Ethernet

I pin 33 e 34 di U5 raggiungono rispettivamente R528 sul retro e R529 sul fronte. Le due resistenze raggiungono la massa principale. La rotazione di L501 accorcia il percorso commutato a 2,12 mm e porta la sua distanza minima dal rame del quarzo da 0,35 a 1,48 mm. Per l’uscita filtrata la distanza passa da 1,73 a 1,24 mm. Il ramo di distribuzione su In3 passa da 5,20 a 6,26 mm, mantenendo 1,55 mm di larghezza e tutti i gruppi di carico precedenti. Lo spostamento di un via di R528 di 10 µm in X e 20 µm in Y conserva il riferimento di massa su tutti i 2.374 campioni controllati sulle piste preesistenti vicine ai nuovi via. La risposta del convertitore e il campionamento delle strap all’avvio restano da misurare sul prototipo. [Connettività sul PCB](experiments/phy-power-parallel/layout-phy-both-boot-straps.json) · [Distanze dal quarzo](experiments/phy-power-parallel/phy-345-strap34-native-complete.json)

### Dissipatore passivo

Il disegno Rockchip quota il package da 0,795 a 0,947 mm rispetto al piano di appoggio. Un contatto quadrato da 12 mm centrato lascia almeno 0,90 mm per lato rispetto al contorno minimo del package. Una piastra piana da 16 mm si sovrappone invece al corpo di Y2001 per 0,35 × 3,40 mm nel caso dimensionale massimo. L’oscillatore può sporgere di 0,505 mm sopra il processore prima di includere le tolleranze di montaggio. Per quella piastra serve uno scarico locale oppure una distanza verticale che comprenda anche saldature, flessione e tolleranze del case. La verifica della temperatura e del precarico richiede il prototipo. [Quote e sovrapposizioni sul PCB corrente](experiments/phy-power-parallel/rk3562-spreader-xy.json)

### Ethernet Gigabit

Un via GND da 0,45/0,20 mm collega In1 e In4 a 1,154 mm dal passaggio di PHY_RXD3, prima a 1,860 mm dal ritorno più vicino. Sul PCB adottato rimangono 356 unioni. Il controllo conserva i corridoi dei quattro coupon Ethernet e la copertura delle piste vicine. Il ritorno aggiuntivo di PHY_XIN resta sul solo coupon, perché occupa un corridoio MDI0. [Verifica del riferimento e degli ingombri](experiments/phy-power-parallel/phy-356-reserved-return-ethernet-compatibility.json)

Il modello planare dei due stack dà 100,7 Ω sul 3313 e 97,5 Ω sul 7628 per una coppia interna con piste e spazio da 0,20 mm. Il coupon tra U23 e J2 collega entrambe le polarità della coppia MDI3. Il DRC differenziale conserva i controlli precedenti e lo scarto di lunghezza planare è 0,003 mm. La proiezione su strato adiacente mostra però 2,179 mm di sovrapposizione quasi parallela tra la polarità positiva e SDA dell'espansione. Il coupon è separato dal PCB corrente in attesa della correzione o di una verifica elettrica della geometria. Restano da collegare U5 e le altre coppie. [Geometrie sui due stack](experiments/phy-power-parallel/mdi-357-two-stack-geometry.json) · [Continuità e DRC](experiments/phy-power-parallel/mdi-355-matched-native.json) · [Riferimenti e incroci](experiments/phy-power-parallel/mdi-355-matched-reference-map.json)

Sul secondo coupon MDI3 il percorso evita le sovrapposizioni fra conduttori di reti diverse con angolo inferiore a 30°. Le due polarità attraversano ancora il rame di +5V_MAIN per circa 4,97 e 3,59 mm di proiezione complessiva. Lo scarto planare è 0,00274 mm, con ritorno al cambio di strato a 0,75 e 1,34 mm. Le 818 coppie fisiche superano il controllo sul PCB ricaricato. Il coupon rimane separato per verificare la discontinuità locale di impedenza e il fanout del PHY. [DRC e continuità](experiments/phy-power-parallel/mdi-355-opposite-matched-native.json) · [Incroci per lunghezza e angolo](experiments/phy-power-parallel/mdi-355-opposite-matched-map.json) · [Confronto piani di massa](experiments/phy-power-parallel/mdi-355-opposite-matched-foreign-plane.json)

La simulazione elettrostatica della geometria interna da 0,20/0,214 mm dà 103,3 Ω sul 3313 e 99,9 Ω sul 7628. Introducendo un piano equipotenziale continuo sullo strato adiacente i valori diventano rispettivamente 75,0 e 88,8 Ω. Il rame reale attraversa la coppia a tratti e in modo asimmetrico. La simulazione individua una discontinuità da qualificare con il disegno tridimensionale del canale o con un coupon fisico. [Parametri, convergenza e risposte delle sezioni ipotetiche](experiments/phy-power-parallel/mdi-355-adjacent-rail-sensitivity.json)

La prova di riposizionamento della protezione Ethernet U22 trova 74 pose con quattro uscite contemporanee; una, sul retro a (75,25; 18,50) mm con rotazione 180°, ammette anche i due nuovi collegamenti di massa. Sulla copia KiCad questi sei collegamenti sono continui e le 816 coppie precedenti sono conservate. Il controllo segnala due vecchi tratti di massa pendenti e quattro via di segnale in attesa di instradamento. La scheda adottata resta al checkpoint da 357. [Uscite e ritorni](experiments/phy-power-parallel/mdi-357-u22-four-launches-ground.json) · [Verifica nativa](experiments/phy-power-parallel/mdi-357-u22-native-jack-launch.json) · [Pinout TPD4E05U06DQA, tabella 4-2](https://www.ti.com/lit/ds/symlink/tpd4e05u06.pdf)

Dalla nuova posizione la prima coppia U22.1/.2 raggiunge J2.P2/P3 nella copia, attraverso In3 e In2. Il controllo nativo scende da 357 a 355 unioni e conserva i due rami di massa. Per la seconda coppia sono stati analizzati 207 corridoi preliminari: ricostruendo le piste con l'ingombro reale entrambe le polarità interferiscono in tutti i casi. La variante resta separata. [Prima coppia ricaricata](experiments/phy-power-parallel/mdi-357-u22-pair0-native.json) · [Controllo reciproco della seconda](experiments/phy-power-parallel/mdi-353-u22-both-pairs-native.json)

La tabella 4-2 di TI consente di proseguire una pista sui piedini NC del package DQA. Facendo passare la polarità negativa sul pad U22.6, si chiude anche il tratto U22–J2 della seconda coppia. Il coupon arriva a 353 unioni residue, con 821 coppie di pad verificate dopo la ricarica e nessuna nuova violazione DRC o apertura di maschera. Il coupon comprende uno schema e una variante locale del simbolo. L’esportazione dell’intero progetto conferma che U22.6 è l’unica assegnazione modificata. Prima dell’adozione occorrono la verifica del percorso fino al PHY e la revisione dell’impedenza al connettore. Sovrapponendo la variante MDI3 si ottengono 22 violazioni aggiuntive, fra cui nove corti: i due disegni non si possono combinare direttamente. [Copia U22 a due coppie](experiments/phy-power-parallel/mdi-353-u22-flowthrough-ground-cleanup.json) · [Confronto delle netlist](experiments/phy-power-parallel/mdi-353-u22-schematic-pin-parity.json) · [Prova di coesistenza con MDI3](experiments/phy-power-parallel/mdi-351-three-jack-pairs-coexistence.json)

La correzione di lunghezza sul coupon da 353 porta gli scarti planari a meno di 0,001 mm per entrambe le coppie. Sono state ricaricate e controllate tutte le 821 coppie di pad; il DRC comparativo non aggiunge violazioni. Questi valori coprono il tratto di rame dalla protezione al connettore e non includono i contatti interni del jack. [Rame salvato e coppie controllate](experiments/phy-power-parallel/coupon-u22-mdi01-matched.json) · [Proiezioni sui piani di riferimento](experiments/phy-power-parallel/mdi-353-u22-final-reference.json)







Con MDI3 mantenuta, una diversa posa di U22 collega MDI1 al jack e ripristina le due masse sul coupon da 353. Per MDI0 il confronto trova 244 finestre per il cambio strato, tutte occupate rispetto alla coppia di via ordinari richiesta. Il coupon resta separato dal layout adottato. [Alternative con MDI3](experiments/phy-power-parallel/coupon-u22-ports-with-mdi3.json) · [Finestre di transizione](experiments/phy-power-parallel/mdi-353-u22-pair0-sliding-transfers.json)

Sul PHY la separazione nominale di 0,200 mm fra i conduttori in uscita dai pin adiacenti permette le otto uscite contemporanee quando si libera temporaneamente il campo di alimentazione. Sulla copia del PCB interamente popolata, KiCad ricollega ciascuno degli otto pad al proprio via senza violazioni reciproche fra le otto uscite. Il rame esistente produce però 52 corti, sei violazioni foro–rame e cinque foro–foro che coinvolgono queste uscite. Per usare la geometria occorre riprogettare i tratti di alimentazione e i bypass presenti nella stessa zona. [Compatibilità combinatoria](experiments/phy-power-parallel/mdi-357-phy-exhaustive-pair-domain-compatibility.json) · [Conflitti per UUID sul PCB popolato](experiments/phy-power-parallel/mdi-357-phy-eight-populated-obstructions.json)

### GPIO di espansione

Il controllo ha considerato sfere libere con pull-down di reset e banco già alimentato a 3,3 V. Nel prolungamento dei sette percorsi che raggiungevano il confine della prima ricerca, U1.L2 e U1.M2 raggiungono un via ordinario rispettivamente dopo 3,761 e 3,719 mm di pista. Sul connettore le regioni accessibili dai contatti J3.29 e J3.30 si chiudono entro 4,225 e 7,382 mm senza un sito per il via. Il calcolo comprende il contorno fisico della scheda e i keepout. Il pinout resta quello del checkpoint. [Selezione e percorsi sul rame](experiments/phy-power-parallel/gpio-357-reaching-boundary-extended-escapes.json)

Su una copia successiva J3.30 raggiunge U1.L2 conservando il pinout. Il tratto di alimentazione +5V_ADDON resta largo 1,00 mm e passa da 5,400 a 5,731 mm per lasciare spazio al via del connettore. Il percorso completo del segnale misura 127,718 mm e conserva tutte le 818 coppie verificate senza violazioni DRC aggiuntive. Il via del connettore conserva il riferimento di EXP_GPIO0. La verifica del segnale ai centri e ai bordi non rileva vuoti al di fuori dei propri antipad. La distanza dal ritorno GND più vicino raggiunge 2,067 mm. Il percorso rimane su coupon in attesa di una geometria più corta e di verifiche dei fronti. [Coupon EXP_GPIO3](experiments/phy-power-parallel/gpio-355-gpio3-referenced-native.json) · [Lunghezza per strato, copertura e continuità](experiments/phy-power-parallel/gpio-355-gpio3-referenced-native-profile.json)

Nel confronto fra audit storico, schema corrente e PCB, dieci sfere precedentemente elencate come inutilizzate servono ora LPDDR4, eMMC o USB di espansione. In particolare L26 porta EMMC_STRB. Lo schema corrente e il PCB concordano su tutte e dieci. [Assegnazioni correnti](experiments/phy-power-parallel/soc-357-legacy-nc-live-assignments.json)

### Massa della eMMC

Il [checkpoint precedente](experiments/phy-power-parallel/layout-emmc-a6-ground.json) ha **377 unioni aperte su 198 reti**. La sfera A6 della flash raggiunge la massa principale con una via ordinaria da 0,45/0,20 mm. Una deviazione locale di 0,050 mm su In2 mantiene EXP_GPIO1 alla larghezza originaria di 0,20 mm. Il controllo su disco conserva le 795 coppie di pad, la copertura di riferimento precedente nei 1.998 campioni e le distanze preesistenti dalle aperture di maschera. [Verifica della connessione](experiments/phy-power-parallel/emmc-378-a6-ground-native.json) · [Coesistenza del selettore USB](experiments/phy-power-parallel/usb-selector-emmc-a6-coexistence.json)

### Collegamenti di massa sotto SoC e LPDDR4

Il [checkpoint precedente](experiments/phy-power-parallel/layout-lpddr-n11-p12-ground.json) ha **378 unioni aperte su 198 reti**. La coppia di massa N11–P12 della LPDDR4 è collegata con un ramo da 0,225 mm lungo 0,791 mm. Resta da portarla al piano GND principale. [Verifica della LPDDR4](experiments/phy-power-parallel/ground-379-lpddr-n11-p12-native.json)

 Due piste frontali da 0,25 mm uniscono C25–D25 e M27–P26 del SoC, rispettivamente per 0,250 e 0,920 mm. Entrambe le coppie richiedono ancora una connessione al piano GND principale. La verifica cumulativa su disco conserva 794 coppie di pad, la copertura del piano In1 e il conteggio delle aperture di maschera. [Verifica delle piste](experiments/phy-power-parallel/ground-381-soc-ddr-land-qualified-native.json) · [Inventario elettrico indipendente](experiments/phy-power-parallel/soc-ground-ball-pairs-independent-inventory.json)

### Aperture della maschera sul SoC

Il [checkpoint precedente](experiments/phy-power-parallel/layout-soc-mask-four-junctions.json) mantiene **381 unioni aperte su 198 reti**. Lo spostamento congiunto di 30 coppie di vertici riduce da 207 a 147 le occorrenze di un segmento entro 90 µm dall’apertura di un altro pad sul fronte. Sul retro il conteggio resta zero. La variazione totale di lunghezza di ogni net LPDDR4 interessata è inferiore a 0,001 mm. I 4.218 campioni di confronto conservano la copertura GND precedente su In1. I conteggi riguardano segmenti e aperture nel CAD; una seconda modifica al percorso di massa elimina altre due occorrenze. Le 145 occorrenze residue e le capacità di fabbricazione restano aperte. [Verifica delle modifiche](experiments/phy-power-parallel/soc-mask-paired-junctions-native.json) · [Verifica del rame GND](experiments/phy-power-parallel/soc-mask-four-junctions-native.json) · [Verifica delle connessioni con selettore USB](experiments/phy-power-parallel/usb-selector-soc-mask-four-coexistence.json)

### Prima alimentazione VCCQ della flash

Il [checkpoint precedente](experiments/phy-power-parallel/layout-soc-mask-hostwake.json) ha **381 unioni aperte su 198 reti**. R8006.2 e il banco C8002 raggiungono la sfera P3 di U8001 sul rail I/O da 1,8 V. La revisione del segnale WIFI_HOST_WAKE elimina due interferenze con le aperture della maschera del SoC. Sul fronte restano 207 casi sotto 90 µm, sul retro zero. [Controllo geometrico](experiments/phy-power-parallel/soc-mask-expansion-hostwake-381-native.json)

I due tratti esterni misurano in totale 3,96 mm, quello interno 5,26 mm. Il percorso usa un’uscita da 0,25 mm sotto il package, un tratto da 0,50 mm e due vie. Entrambi i tratti esterni e In3 hanno come riferimento In4. La tensione dinamica sotto carico e l’avvio restano da misurare. [Verifica del ramo](experiments/phy-power-parallel/emmc-382-p3-vccq-native.json) · [Piano di massa](experiments/phy-power-parallel/emmc-381-p3-reference.json)

### Distribuzione VCC sotto la flash

Il [checkpoint precedente](experiments/phy-power-parallel/layout-emmc-vcc-middle-balls.json) ha **382 unioni aperte su 198 reti**. Le sfere E6 e F5 di U8001 sono collegate tra loro sul retro con una pista da 0,25 mm lunga 0,762 mm. Il percorso mantiene il riferimento GND su In4 e passa il controllo indipendente delle aperture di solder mask. Resta da unire questo gruppo al banco VCC che alimenta J10 e K9. [Verifica CAD](experiments/phy-power-parallel/emmc-383-vcc-middle-balls-native.json) · [Verifica delle 790 coppie con il selettore USB](experiments/phy-power-parallel/usb-selector-emmc-vcc-middle-balls-coexistence.json)

### Ingresso a 3,3 V della eMMC

Il [checkpoint precedente](experiments/phy-power-parallel/layout-emmc-main-return.json) ha **383 unioni aperte su 198 reti**. R8007.1 raggiunge la distribuzione +3V3_IO principale. A ponticello montato, il percorso disegnato alimenta le sfere flash J10 e K9 tramite R8007.2. Due vie GND collegano i piani In1 e In4 a 0,762 e 1,128 mm dalle rispettive vie di alimentazione. Il collegamento al rame di massa è verificato dopo il riempimento. [Verifica delle vie di ritorno](experiments/phy-power-parallel/emmc-383-individual-return-native.json)

Il ramo nuovo contiene circa 13,4 mm di rame sul retro, 19,8 mm su In2 e due vie. Una stima a 20 °C sui soli tratti nuovi da 0,50 mm dà 52 mΩ e 2,6 mV a 50 mA, valore RMS VCC della tabella Samsung su 100 ms. Picchi, ponticello, caduta a monte e transitorio di avvio richiedono verifica. Le sfere E6 e F5 restano aperte. [CAD e stima resistiva](experiments/phy-power-parallel/emmc-383-r8007-reference.json) · [Inventario indipendente](experiments/phy-power-parallel/emmc-r8007-main-supply-independent-inventory.json)

### Alimentazione della eMMC

Il [checkpoint precedente](experiments/phy-power-parallel/layout-emmc-j10-active-bank.json) ha **384 unioni aperte su 198 reti**. Il banco C8007/C8008/C8009 e il ponticello R8007.2 raggiungono le sfere J10 e K9 della flash tramite rame da 0,35 mm e una via da 0,45/0,20 mm. Nei campioni di riferimento sulle piste, le sole interruzioni del piano GND coincidono con i disimpegni delle vie di questo stesso ramo. Restano aperte le sfere E6 e F5, l’ingresso di R8007 e il bus dati. La verifica CAD conserva 788 coppie di pad. [Verifica nativa](experiments/phy-power-parallel/emmc-385-j10-active-bank-native.json) · [Piano di riferimento](experiments/phy-power-parallel/emmc-384-j10-bank-reference.json)

### Alimentazione di C1683

Il [checkpoint precedente](experiments/phy-power-parallel/layout-io-c1683-c1619.json) ha **385 unioni aperte su 198 reti**. C1683.1 raggiunge il banco +3V3_IO con rame da 0,80 mm e via da 0,45/0,20 mm. La rotazione di C1683 attorno al pad di massa e lo spostamento di 0,056 mm del vicino C1619 conservano il contatto dei terminali con il rame precedente. La nuova via dista 0,918 mm dalla via di massa più vicina. Il DRC e la verifica indipendente confermano 787 coppie fisiche sul PCB salvato. [Contatti dei condensatori](experiments/phy-power-parallel/io-385-moved-cap-solder-contacts.json) · [Riferimento di massa](experiments/phy-power-parallel/io-385-c1683-c1619-reference.json) · [Coesistenza selettore USB](experiments/phy-power-parallel/usb-selector-io-c1683-c1619-coexistence.json)

### Alimentazione di C1640

Il [checkpoint precedente](experiments/phy-power-parallel/layout-io-c1640-main-bank.json) ha **386 unioni aperte su 198 reti**. C1640.1 raggiunge il banco principale +3V3_IO con rame da 0,80 mm e due vie da 0,45 mm con foro da 0,20 mm. C1640.2 raggiunge la massa principale. Tutti i 1.167 campioni di riferimento ricadono su massa o nel disimpegno di vie appartenenti allo stesso ramo di alimentazione. Il DRC differenziale e le 786 coppie verificate sul PCB ricaricato confermano la continuità. Restano aperte le connessioni alle sfere del SoC e la qualifica del comportamento elettrico del banco. [Verifica delle piste e delle vie](experiments/phy-power-parallel/io-387-c1640-main-bank-native.json) · [Verifica del riferimento](experiments/phy-power-parallel/io-386-main-bank-reference.json)

### Strap RXD1 del PHY Ethernet

Il [checkpoint precedente](experiments/phy-power-parallel/layout-phy-rxd1-strap.json) ha **387 unioni aperte**. Il resistore di strap R525 da 4,7 kΩ raggiunge la linea U5.24–R508.2. Il ramo sul retro è lungo 3,012 mm. Il collegamento all'alimentazione del resistore misura 1,170 mm. La via GND più vicina che collega entrambi i piani di riferimento dista 0,673 mm dalla nuova via del segnale. Dei 657 campioni del riferimento, 112 ricadono nel disimpegno della via stessa e tutti i rimanenti sul piano di massa. L'integrità del segnale RGMII e il collegamento dal resistore serie al SoC restano da verificare sul bus completo. [Verifica nativa](experiments/phy-power-parallel/phy-388-rxd1-strap-native.json)

### Ritorni di massa del SoC

Il [checkpoint dei ritorni](experiments/phy-power-parallel/layout-soc-ground-e3-c14.json) ha **388 unioni aperte**. Le sfere U1.C14 e U1.E3 raggiungono la massa principale su F.Cu con piste da 0,30 mm, lunghe 0,177 e 0,379 mm. Il controllo della continuità conta 783 coppie sul PCB ricaricato. I nuovi segmenti hanno riferimento In1 continuo e rispettano la distanza da maschere di altre reti. [Misure sul PCB](experiments/phy-power-parallel/ground-390-soc-e3-c14-native.json)

### Alimentazione LPDDR4 a 1,1 V

Il [checkpoint della memoria](experiments/phy-power-parallel/layout-ddr-1v1-aa8-aa5.json) ha **390 unioni aperte**. U2.AA5 e U2.AA8 raggiungono il banco di C1646 con due raccordi rispettivamente di 0,630 e 0,600 mm, larghi 0,50 mm. Sul ramo AA8, 30 campioni della proiezione della pista ricadono nella zona priva di rame attorno alla stessa via di alimentazione collegata al banco. Il ritorno GND più vicino collega In1 e In4 a 0,707 mm da quella via. Restano aperti altri terminali di alimentazione e la verifica dell'integrità dell'alimentazione sotto carico. [Riscontro sul PCB ricaricato](experiments/phy-power-parallel/ddr-aa8-aa5-package-native.json)

### Banco analogico immagini

Il [checkpoint del banco immagini](experiments/phy-power-parallel/layout-vcca-image-package-bank.json) ha **392 unioni aperte**. Sul fronte, U1.1N9 raggiunge il gruppo U1.1M8–U1.1M7 con 0,545 mm di rame da 0,30 mm. Il controllo su In1 conferma il riferimento continuo lungo il percorso. Sono verificate 779 coppie dopo la ricarica. Il collegamento fra questo gruppo e il regolatore resta aperto. [Verifica sul PCB](experiments/phy-power-parallel/image-393-fine-package-native.json)

### Distribuzione VCCA_1V8

Il [checkpoint della distribuzione](experiments/phy-power-parallel/layout-vcca-linked-load-banks.json) ha **393 unioni aperte**. C1644.1 è collegato sul retro al gruppo C1645–U1.1E14–U1.1E15. Il percorso è lungo 12,97 mm e largo 0,30 mm. Il controllo del riferimento In4 ai due bordi e lungo il centro della pista ha trovato copertura continua. Il PCB ricaricato conserva 778 coppie di pad e il DRC differenziale. Rimangono da collegare U4.3 e gli altri carichi della rete. [Misure del percorso](experiments/phy-power-parallel/vcca-394-shared-rear-bank-native.json)

### Bypass VCCA_1V8 del SoC

Il [checkpoint del bypass](experiments/phy-power-parallel/layout-vcca-soc-c1645.json) ha **394 unioni aperte**. C1645 da 100 nF raggiunge entrambe le sfere U1.1E14 e U1.1E15, con 0,65 mm di pista sul retro, una via da 0,45/0,20 mm e 0,30 mm sul fronte. Il ritorno misurato in pianta alla via GND scende da 3,73 a 3,23 mm. Il bypass resta da qualificare alle frequenze operative. Il tratto +3V3_IO spostato su In2 mantiene 0,20 mm di larghezza e conserva tutte le 29 piazzole collegate. Il controllo sul PCB ricaricato conferma 777 coppie e nessuna nuova segnalazione DRC. La sorgente U4.3 resta aperta. [Geometria e controlli](experiments/phy-power-parallel/vcca-c1645-shared-corridor-validation.json)

### Maschera di saldatura del SoC

Il [checkpoint della maschera](experiments/phy-power-parallel/layout-soc-mask-memory-junctions.json) conserva 395 unioni aperte e 774 coppie verificate. Dieci spostamenti di vertici sulle piste di massa o di controllo eliminano 17 accostamenti sotto 90 µm. Una seconda correzione su 25 vertici di segnali LPDDR4 ne elimina altre 25. Restano 209 accostamenti al fronte presso U1. La variazione di lunghezza per segnale è al massimo 0,00635 mm. Il controllo su 2.379 campioni del riferimento In1 non rileva nuove interruzioni. Su 39 passaggi rete/coppia di pad il canale fra aperture misura 0,250 mm. Una pista da 0,0762 mm con 0,090 mm per lato richiede 0,2562 mm. Per quei passaggi serve una topologia di uscita diversa o una geometria di maschera qualificata per il package. Sul retro la ricerca non ne rileva. Il controllo considera piste superficiali di altre reti e aperture delle piazzole in scala 1:1. La qualifica delle aperture per le vie e la verifica CAM restano aperte. [Misure CAD](experiments/phy-power-parallel/pad-mask-memory-junctions-395.json) · [Geometria dei passaggi BGA](experiments/phy-power-parallel/soc-mask-bga-corridor-budget.json) · [Capacità dichiarate da JLCPCB](https://jlcpcb.com/capabilities/Capabilities%2C/)

### Banco analogico del SoC a 0,9 V

Il [checkpoint del banco analogico](experiments/phy-power-parallel/layout-soc-analog-c1633-bank.json) ha 395 unioni aperte. C1633 da 100 nF raggiunge sul retro il gruppo di C1642 e R1601 mediante rame da 0,30 mm e dispone di un ritorno alla massa principale. Il DRC sul file ricaricato conserva le 121 segnalazioni pregresse di via terminali e conferma 774 coppie di pad. La sorgente di alimentazione e le sfere analogiche del SoC restano da raccordare. [Verifica sul PCB](experiments/phy-power-parallel/soc-analog-c1633-native-trials.json)

### Banco analogico USB a 1,8 V

Il checkpoint precedente è [layout-usb-analog-dual-bypass.json](experiments/phy-power-parallel/layout-usb-analog-dual-bypass.json). R1602 alimenta C1681 da 100 nF e C1682 da 1 µF. Il ritorno del 100 nF raggiunge un nuovo foro di massa in 0,68 mm. Il ritorno del condensatore da 1 µF percorre 0,30 mm di pista e circa 1,04 mm di rame esistente fino al foro. La distanza in pianta del 100 nF dalla sfera U1.1M15 scende da 15,90 a 7,66 mm. Restano da chiudere la distribuzione VCCA_1V8 a monte e il collegamento alla sfera del SoC. L’inventario fisico riporta 396 unioni e 199 reti aperte. La [verifica sulla copia combinata con il selettore USB](experiments/phy-power-parallel/usb-selector-dual-bypass-coexistence.json) conferma 772 coppie e 396 unioni residue. I cinque nuovi segmenti hanno riferimento GND continuo nei punti campionati. L’impedenza del banco resta da qualificare sul prototipo.

### Clock di ricezione RGMII

Il checkpoint del clock è `experiments/phy-power-parallel/layout-rgmii-rxclock-source-return.json`, con 397 unioni residue su 199 reti. La sorgente U5.27 raggiunge R512.2 e il relativo strap R522.1; resta da instradare ETH_RXCLK dal resistore al SoC. Il riassetto locale mantiene le sezioni di +3V3_PHY (0,20 mm al pin, 1,05 mm nella distribuzione interna) e la continuità dei 15 pad del ramo. Il tratto interno aumenta di 0,992 mm. Sul file ricaricato sono verificate 770 coppie senza nuove violazioni DRC. Il confronto su copia combinata con il selettore USB è conservato in `usb-selector-rgmii-rxclk-coexistence.json`. Il cambio strato del clock ha un ritorno GND esistente a 1,363 mm; 240 campioni del rame su In1 e In4 risultano coperti oltre il raggio di 0,45 mm attorno alla via. Restano aperte la verifica di integrità del segnale e la temporizzazione del bus completo.

### Alimentazione del pull-up SDIO D1

Il checkpoint intermedio è `experiments/phy-power-parallel/layout-sdio-pullup-supply.json`. R2011 occupa il retro presso il lato host del bus. Una pista da 0,136 mm collega il pin 2 al banco +3V3_IO di C1628. La linea dati fra U1.V25, R2011.1 e U25.19 resta aperta. Sul PCB ricaricato sono conservate 769 coppie di pad, con 398 unioni residue su 200 reti e nessuna nuova violazione DRC rispetto al checkpoint precedente. L’inventario indipendente è in `sdio-pullup-independent-inventory.json`. La variante separata del selettore di corrente USB conserva la propria base a 399 unioni.

### Alimentazione immagine al checkpoint C468

Al checkpoint `experiments/phy-power-parallel/layout-pmic-image-c468.json` restavano 399 unioni su 200 reti. C468 da 1 µF raggiunge U4.6 sulla faccia superiore attraverso 2,494 mm di rame. Il tratto sulla piazzola è largo 0,20 mm e lungo 0,304 mm. Il resto è largo 0,30 mm. Il ritorno GND misura 0,598 mm fino al foro già collegato al piano. C421 è stato traslato di 0,20 mm e mantiene ciascuno dei sei contatti diretti precedenti. Il controllo sui bordi e sul centro delle piste conferma che il piano di riferimento è continuo.

L’inventario indipendente sul PCB ricaricato coincide con il checkpoint. Le 768 coppie sono collegate, il DRC comparativo e il controllo degli ingombri non rilevano regressioni. Il collegamento dell’uscita ai carichi del SoC, la verifica dell’anello di regolazione e le misure fisiche restano aperti.

### PCB di prova con selettore USB-C

Per le prove di alimentazione usare [il PCB con selettore](experiments/usb-current-selector/phy-joint.kicad_pcb), derivato dal checkpoint C468. Montare esattamente uno fra R1104 (standard, 3 A annunciati) e R1105 (banco, 1,5 A oppure 3 A annunciati). Sul banco usare una sorgente USB-C dati con annuncio controllato e limitazione indipendente della corrente totale. R1201 resta da 806 Ω e il limite nominale di U15 è 2,52 A sul solo ramo principale. Il montaggio di R1105 da solo non protegge una porta da 1,5 A.

Il [verificatore](experiments/usb-current-selector/verify.py), da eseguire con Python KiCad, esporta l'intera gerarchia, confronta le assegnazioni dei pin, ricarica il rame e ripete il DRC. Controlla anche la continuità del resistore di limite, del condensatore di rampa e del punto di misura TP3 fino a U15. Prima di provare un Mac, registrare insieme corrente all'ingresso USB-C, VBUS su TP2, +5V_MAIN su TP3 e stato USB dell'host, prima da spento e poi con radio, VPN e display sotto carico. Ripetere con corrente standard annunciata e verificare che il ramo principale rimanga spento. Tenere separati gli esiti di limitazione della sorgente, caduta sul cavo, reset della scheda e mancata enumerazione. La ROCK non qualifica questo circuito.

### Ingresso USB-C da 1,5 A sul checkpoint C468

Lo [screening riproducibile](review/usb-1a5-screen.json) rilegge il PCB, controlla il digest e verifica le 768 coppie. Il nuovo DRC KiCad ritrova gli stessi 121 rilievi e 399 unioni aperte; alcune coppie rappresentative delle isole aperte differiscono nel ratsnest. La capacità nominale direttamente assegnata a +5V_MAIN è 67,2 µF, incluso C8101. Alla rampa tipica il solo contributo capacitivo vale 128 mA.

In modalità UFP GPIO, U6.OUT1 segnala sia 1,5 sia 3 A quando è basso. U14 oggi richiede anche OUT2 basso. Per abilitare il nuovo profilo si può usare l'inversione del solo OUT1, conservando le altre condizioni di abilitazione. Prima del cambio verificare il limite del ramo principale e i carichi sempre alimentati a monte di U15. Il limite nominale attuale di 2,52 A supera il budget dell'intero ingresso. Lo screening include tre valori alternativi di R1201 e il margine che lascerebbero per i carichi a monte. La scelta dipende anche dalla corrente minima disponibile per l'avvio nel caso di intervento anticipato della protezione.

Con 1 A ipotizzato sul ramo Wi-Fi a 3,584 V, a 5 V e con rendimento ipotizzato dell'85–90% restano 3,28–3,52 W per tutti gli altri carichi e perdite. La specifica del modulo indica il picco a 3,3 V. Questa proiezione serve per dimensionare la prova di carico simultaneo. Riprodurre con il Python di KiCad eseguendo `tools/screen_usb_1a5_checkpoint.py` dalla directory hardware/phoenix-g1. Per la prova termica in involucro registrare i tempi effettivi dei campioni: il benchmark ROCK ha evidenziato lacune durante il duplex.

Lo screening combinato include anche la LPDDR4 montata (lettura burst IDD4R: 0,733 W a 3200 MT/s o 0,817 W a 3733 MT/s), l’eMMC da 8 GB (0,489 W sulle alimentazioni nominali usando i valori RMS su 100 ms della tabella HS400) e il ramo LED da circa 10 mA. Con questi carichi simultanei, a 5 V / 1,5 A restano **1,70–2,11 W complessivi** per RK3562, PHY Gigabit e tutti gli altri carichi e perdite esclusi dal modello. A 4,75 V sulla scheda restano 1,32–1,74 W. Il modello usa efficienze ipotizzate dell’85–90% e include il picco radio ipotizzato sopra. I valori di frequenza DRAM sono condizioni di caratterizzazione del componente. La qualifica richiede un profilo temporale di avvio e di carico reale, compresi i picchi più brevi della finestra RMS e la verifica del limite minimo del ramo U15. I dati PHY a collegamento spento e le percentuali CPU misurate sulla ROCK non permettono di chiudere il bilancio in watt.

**Margine a valle di U15.** Il residuo calcolato lato USB non è tutto disponibile al processore. Con R1201 ipotizzata da 1,62 kΩ il limite inferiore stimato del ramo principale è 1,168 A. A 5 V, nello scenario combinato, resterebbero appena 0,037–0,450 W per SoC, PHY e altri carichi a valle. A 4,75 V l’intervallo diventa −0,252…+0,161 W. Un residuo negativo indica che i carichi ipotizzati da soli superano la soglia inferiore del modello. Le cadute sui dispositivi di protezione e sulle piste riducono ulteriormente il margine. A titolo di confronto la tabella 7.5 TI riporta 1,09/1,17/1,24 A con 1,78 kΩ nelle sue condizioni di prova. I risultati per gli altri resistori sono stime. Nessuno dei tre valori studiati chiude il dimensionamento con i carichi coincidenti. Per scegliere la protezione servono le forme d’onda della corrente a monte e a valle di U15 e della tensione +5V_MAIN in avvio e durante traffico simultaneo con radio attiva; il punto di lavoro effettivo del modulo radio è particolarmente influente.

**Percorso completo fino al regolatore radio.** Sul PCB R1905 da 33,2 kΩ programma U24 a circa 2,68 A tipici. U24 è a monte dei carichi permanenti e di U15. Impostare 1,5 A nominali con l’equazione TI (59,3 kΩ ideali) non garantirebbe la corrente massima alla porta, né la selettività fra i due stadi. U24.19 (IMON) non ha una pista instradata: per il collaudo usare una misura esterna di VBUS sincronizzata con +5V_MAIN all’ingresso di U26. Un punto di misura IMON resta una variante opzionale e richiederebbe anche una resistenza verso massa.

Con 4,75 V alla scheda, correnti imposte di 1,5 A su U24 e 1,2 A su U15 e resistenze di conduzione massime a caldo di 64 e 53 mΩ, risultano circa 4,590 V prima delle perdite sulle piste. Per il ramo radio nominale da 3,584 V rimangono appena 6,4 mV rispetto alla condizione VIN ≥ VOUT + 1 V usata per l’accuratezza PWM del TPS62130. È un confronto con la condizione di specifica, non una previsione di dropout. Verificare VIN di U26, VBAT sul modulo e reset della radio sotto traffico; non aumentare la corrente limite per compensare una caduta di tensione.

**Variante di banco per la decodifica da 1,5 A.** Il [foglio KiCad alternativo](experiments/usb-1a5-prototype/usb-power-control.kicad_sch) collega U14.2 a GND mantenendo separata la rete OUT2 del controller. La [verifica](experiments/usb-1a5-prototype/verify.py) esporta le netlist del foglio e di una copia temporanea del progetto integrato. Su 1.775 assegnazioni pin-rete cambia soltanto U14.2. Nei sei stati statici valutati cambia una sola uscita: con 1,5 A annunciati e AON_READY attivo viene abilitato U15. Il PCB adottato conserva il consenso a 3 A. La variante serve per la caratterizzazione con sorgente da banco con limite di corrente, annuncio Type-C coerente e misura di VBUS; la risposta a distacco, cambi di annuncio e brownout richiede verifica dinamica. [Esito e tabella degli stati](experiments/usb-1a5-prototype/verification.json).

## Bypass da 1 µF sul banco I/O a 3,3 V

Il checkpoint adottato è `experiments/phy-power-parallel/layout-io-c1628-local.json`. Restano 400 unioni su 200 reti. C1628 raggiunge il banco di distribuzione con 0,72 mm di pista larga 0,50 mm. La sfera SoC a 3,3 V più vicina dista 1,703 mm contro i 6,973 mm precedenti. Il gruppo di distribuzione resta separato dalle sfere del SoC. Tutte le 766 coppie verificate e il rame precedente sono conservati. I due raccordi sul retro hanno riferimento continuo sul piano GND adiacente nei 264 campioni verificati.

Il percorso geometrico stimato dal terminale di massa al primo foro connesso al piano passa da 1,564 a 1,678 mm. L'aumento di 0,114 mm accompagna il collegamento del terminale positivo prima isolato e l'avvicinamento al carico. L'impedenza effettiva resta da qualificare. L'inventario indipendente sul PCB ricaricato coincide con il checkpoint. Il confronto DRC non introduce nuove violazioni.

## Bypass da 100 nF per VDD1 della LPDDR4

Il checkpoint adottato è `experiments/phy-power-parallel/layout-ddr1-c2303-local.json`. Restano 401 unioni. C2303 raggiunge il gruppo da 1,8 V già collegato a U2.F1. Il ramo positivo da 0,50 mm termina sul rame esistente a 0,054 mm dal centro della piazzola. Il ritorno da 0,721 mm raggiunge una via di massa con foro da 0,30 mm. Il centro del condensatore passa da 2,967 a 2,025 mm dalla sfera VDD1 più vicina. Sul file ricaricato risultano verificati il riferimento sotto entrambi i raccordi, tutti i gruppi precedenti e 764 coppie di piazzole. Le altre sette sfere VDD1 della memoria restano separate dal banco.

## Banco di bypass GPU

Il PCB adottato è `experiments/phy-power-parallel/layout-gpu-c1617-bypass.json`. Restano 402 unioni. C1617 da 4,7 µF raggiunge il gruppo C1619–C1620 tramite 1,720 mm di rame da 0,80 mm. Il ritorno alla via di massa misura 1,586 mm contro i precedenti 3,302 mm. La distanza tra il centro del condensatore e la sfera GPU più vicina scende da 11,150 a 9,909 mm. Sul PCB ricaricato sono verificati i gruppi pregressi, 762 coppie di piazzole e il piano di riferimento sotto entrambi i raccordi. Sono ancora aperti il collegamento del banco al carico e la qualifica della distribuzione di alimentazione.

## Bypass VCCIO_ACODEC

Il checkpoint adottato è `experiments/phy-power-parallel/layout-codec-bypass-exposed.json`. Restano 403 unioni su 200 reti aperte. Il condensatore C463 da 1 µF raggiunge U4.28 con 0,591 mm sul fronte, una via e 1,575 mm sul retro. Il ritorno da 1,354 mm termina direttamente su uno dei nove fori metallizzati da 0,30 mm del pad esposto U4.69. Il ricollocamento adiacente conserva entrambi i raccordi di C482. Il percorso da 0,60 mm dell'alimentazione a 3,3 V su In4 misura ora 4,880 mm. Nel confronto locale dei piani, 41 campioni su piste di massa perdono la copertura della massa adiacente; tutti i campioni precedentemente coperti sulle piste di segnale e alimentazione restano coperti. Il DRC ricaricato conserva i risultati precedenti e 760 coppie di piazzole risultano connesse. L’impedenza del bypass e la risposta ai transitori richiedono ancora qualifica elettrica.

## TXD3 e percorso del reset

Il checkpoint adottato è `experiments/phy-power-parallel/layout-rgmii-txd3-reset-referenced.json`. Restano 404 unioni. U1.AB2 raggiunge R504.1 con 2,897 mm sul fronte. Il reset usa due vie esistenti e 28,756 mm su In3. La verifica a PCB ricaricato conserva 758 coppie e tutti i gruppi di piazzole preesistenti, con zero nuove segnalazioni DRC. Il riferimento di massa del reset sulle sezioni piane è stato campionato fino ai due antipad. La continuità delle sezioni complete RGMII verso il PHY e l'effetto elettrico della nuova lunghezza di reset richiedono ancora verifica.

## Ritorni condivisi sotto i BGA

## Clock TX del bus RGMII

Il PCB corrente è `experiments/phy-power-parallel/layout-rgmii-short-source-clock.json`, con 405 unioni aperte. La sfera U1.Y2 raggiunge il resistore serie da 22 Ω R506.1 con 2,397 mm di rame da 0,20 mm sul fronte, senza cambi di strato. La posa congiunta riduce da 3,817 a 3,445 mm la distanza in linea retta fra il vicino R502.1 e la sua sorgente U1.AA2. Sul file ricaricato il riferimento di massa In1 è continuo ai tre punti trasversali campionati ogni 25 µm o meno. I test locali di uscita dalle piazzole, le connessioni storiche e le riserve meccaniche sono conservati; il DRC non introduce nuove segnalazioni. Il controllo XY del dissipatore conserva libera la sagoma da 13,9 mm. La piastra ipotetica da 16 mm ora intercetta sei componenti invece dei cinque del checkpoint precedente. Il tratto R506.2–U5.20, TXD1, il ritardo MAC/PHY e lo skew del bus completo sono aperti.

## Banco NPU su entrambi i lati

Il checkpoint corrente è `experiments/phy-power-parallel/layout-npu-c434-paired-load.json`, con 406 unioni aperte. C434 (22 µF nominali) è passato sul retro a (79,80; 10,50) mm. Due vie 0,65/0,30 mm a interasse 0,86 mm e piste da 0,80 mm lo collegano a C444.1–L404.2. Il ritorno raggiunge la via di massa esistente a (80,50; 8,60) mm. Il PCB ricaricato conserva i gruppi precedenti, presenta zero nuove segnalazioni DRC e supera il controllo delle riserve di montaggio. La misura di stabilità, il percorso verso il carico e il collegamento Kelvin restano aperti.

## Banco LOGIC su entrambi i lati

Il checkpoint corrente è `experiments/phy-power-parallel/layout-logic-c431-paired-load.json`, con 407 unioni aperte. C431 è stato riposizionato sul retro a (74,50; 9,90) mm. Due vie 0,65/0,30 mm a interasse 0,80 mm e rami di rame da 0,80 mm lo collegano al nodo di uscita già verificato L401.2–C441.1. Il ritorno di C431 raggiunge la via GND esistente a (74,55; 9,00) mm. Sul file ricaricato sono conservati tutti i gruppi di pad precedenti. Il vecchio tratto di massa di C431 è l’unico elemento in rame sostituito. Nessuna nuova segnalazione DRC o interferenza con le riserve meccaniche. La distribuzione al SoC e la verifica di stabilità sono aperte.

## Uscita BUCK4 verso il banco NPU

Il PCB corrente è `experiments/phy-power-parallel/layout-npu-output-cap-c444.json` con 408 unioni aperte. Sul fronte il rame da 0,80 mm fra C444.1 e L404.2 misura 8,24 mm; C444.2 appartiene già alla rete fisica di massa principale. La presa di feedback R424.1 deve ancora raggiungere il punto di misura vicino al carico SoC, come richiesto dallo schema PMIC. Riempimento, DRC e verifica delle connessioni sul file ricaricato conservano tutte le coppie precedenti. Restano da verificare la stabilità dell’anello e la distribuzione DC fino al carico.

## Condensatori di uscita CPU e LOGIC

Il checkpoint adottato è `experiments/phy-power-parallel/layout-logic-output-cap-c441.json` con 409 unioni aperte. I tre rami da 0,80 mm sono stati inseriti e verificati in sequenza sul PCB ricaricato. Sul retro C1608 raggiunge il nodo locale C1601 con 1,75 mm di rame e C1606 raggiunge C1608 con 6,18 mm. L’unica via verso questo gruppo di sfere CPU è ancora 0,45/0,20 mm; la connessione DC dimensionata da L1001 è aperta. Sul fronte il banco di uscita LOGIC C441 raggiunge il pad di uscita L401.2 con 6,99 mm. Tutte le coppie precedenti sono conservate, nessuna nuova segnalazione DRC. Stabilità dei convertitori e impedenza della rete di alimentazione richiedono ulteriori verifiche.


## Collegamento fra i banchi di bypass a 3,3 V

Il PCB adottato è indicato da `experiments/phy-power-parallel/layout-io-bank-copper-contact.json`. Il ramo sul retro fra i gruppi C1627.1 e C1639.1 misura 7,42 mm ed è largo 0,50 mm. Dopo riempimento e ricaricamento KiCad verifica 412 unioni ancora aperte, tutte le coppie precedenti conservate e nessuna nuova segnalazione DRC. La misura riguarda la continuità dei due gruppi. L’impedenza dell’alimentazione e la corrente disponibile ai carichi restano da verificare.


U1.AF24 e U2.D9, Y5 e Y8 raggiungono la massa principale usando quattro raccordi ai via esistenti. Restano 414 unioni aperte. [Checkpoint precedente](experiments/phy-power-parallel/layout-reused-ground-barrels.json) · [Percorsi ricaricati e DRC per raccordo](experiments/phy-power-parallel/bga-reused-ground-barrels.json)

U1.B14 raggiunge ora il rame di massa esistente sullo stesso lato. Restano 413 unioni aperte. [Checkpoint adottato](experiments/phy-power-parallel/layout-ground-copper-contact.json)

## Bypass locale NPU

C1621 da 100 nF raggiunge le cinque sfere VDD_NPU di U1 tramite un via ordinario. Il condensatore era già collegato al piano di massa. Il via GND più vicino dista 1,409 mm; la qualifica d’impedenza del bypass e il collegamento di potenza al regolatore restano aperti. Restano 418 unioni aperte. [Checkpoint precedente](experiments/phy-power-parallel/layout-npu-local-bypass.json) · [Verifica geometrica e dei ritorni](experiments/phy-power-parallel/npu-local-bypass.json)

## Ritorni del processore e della memoria

Dieci nuovi via di massa da 0,45/0,20 mm collegano al piano dodici ulteriori pin del processore e della memoria. Il rame dei via mantiene almeno 0,10 mm dalle piazzole e i fori almeno 0,252 mm dal rame delle altre reti nei controlli geometrici eseguiti. Il DRC sul PCB ricaricato e le coppie precedenti sono verificati. Restano 428 unioni aperte, rispetto a 439 prima dei due passaggi. [Checkpoint intermedio](experiments/phy-power-parallel/layout-bga-ground-remaining.json) · [Primi quattro via](experiments/phy-power-parallel/ground-bga-physical-drops.json) · [Altri sei via](experiments/phy-power-parallel/ground-bga-physical-remaining.json)

La ricerca successiva applica il margine di saldatura e la presenza dei due piani prima di selezionare i siti. Altri nove ritorni arrivano alla massa principale. Il PCB ricaricato conserva 121 segnalazioni storiche e 419 unioni aperte. [Checkpoint precedente](experiments/phy-power-parallel/layout-bga-ground-qualified.json) · [Verifiche individuali](experiments/phy-power-parallel/ground-bga-physical-qualified.json)

## Strobe eMMC

Il pin U8001.H5 raggiunge il pulldown R8005 con 1,14 mm di rame. Il secondo pin del resistore raggiunge la massa principale. Il PWM del display conserva la continuità e il tratto LPDDR4_A1_A riposizionato resta sopra il piano a tutti i 326 punti campionati. Il via di ritorno più vicino dista 1,001 mm. L’apertura del piano sotto la linea strobe si estende fino a 0,415 mm dal centro del via. Il pin host U1.L26 resta da collegare e la temporizzazione completa è da verificare. Restano 439 unioni aperte. [Checkpoint precedente](experiments/phy-power-parallel/layout-emmc-strobe-pulldown.json) · [Verifica dei ritorni](experiments/phy-power-parallel/emmc-strobe-ca-reference.json)

## Punto di test del recupero

R1504 e TP10 sono ora sul retro vicino a U1.D26. Il punto di test raggiunge il pin 1 del resistore e il pin 2 raggiunge C1636.1 sulla rete analogica da 1,8 V. Restano aperti il collegamento al pin ADC del processore e la distribuzione del rail fino a C1636. La riposizione conserva le connessioni precedenti e le riserve meccaniche verificate. Restano 440 unioni aperte. [Checkpoint precedente](experiments/phy-power-parallel/layout-recovery-adc-relocated.json)

## Ritorni GND sotto U1

Quattro piste F.Cu da 0,25 mm, ciascuna lunga 0,919 mm, portano U1.1B9, U1.1L2 e U1.1R12 alla massa principale e uniscono i due gruppi di massa U1.1F15 e U1.1G13. Quest’ultimo gruppo di dieci sfere resta separato dal piano di massa. Sul PCB ricaricato restano 444 unioni aperte e 121 segnalazioni storiche. [Checkpoint iniziale](experiments/phy-power-parallel/layout-ground-surface-islands.json) · [Verifica CAD](experiments/phy-power-parallel/ground-surface-islands.json)

Il passaggio successivo connette C1609.2 e C1618.2 con 2,054 mm di rame su B.Cu. Restano 443 unioni aperte. [Checkpoint intermedio](experiments/phy-power-parallel/layout-ground-surface-bends.json)

C1609 e C1618 raggiungono ora il piano attraverso il via GND esistente alle coordinate (42,90; 18,65) mm. Il raccordo sul retro è lungo circa 3,40 mm. Il circuito necessita ancora della verifica di impedenza del ritorno in frequenza. Restano 442 unioni. [Checkpoint intermedio](experiments/phy-power-parallel/layout-ground-cap-existing-barrel.json)

I dieci pin di massa dei gruppi U1.1F15 e U1.1G13 raggiungono ora il via esistente a (48,45; 24,60) mm attraverso un raccordo F.Cu lungo 6,19 mm. La continuità è verificata sul PCB ricaricato. Restano da dimensionare i ritorni distribuiti sotto U1 per corrente e induttanza. Restano 441 unioni aperte. [Checkpoint precedente](experiments/phy-power-parallel/layout-soc-ground-existing-barrel.json)

## Bypass locale del processore

Sul [checkpoint CPU](experiments/phy-power-parallel/layout-cpu-local-hf-bypass.json), C1601 da 100 nF è montato sotto U1. Un via interstiziale da 0,45/0,20 mm collega il condensatore ai sei pin VDD_CPU e due via di massa esistenti chiudono il ritorno. Le 698 coppie precedenti sono conservate. Le unioni aperte scendono da 449 a 448. Rimane da collegare il gruppo al convertitore dimensionando il percorso per la corrente del processore. La verifica riguarda geometria e continuità CAD. [Controlli sul PCB ricaricato](experiments/phy-power-parallel/cpu-bypass-referenced-preservation.json)

## Uscita BGA con foro esterno alla piazzola

Il [checkpoint precedente](experiments/phy-power-parallel/layout-bga-referenced-barrel.json) porta il via di DQ10_B fuori dalla piazzola U1.B27, mantenendo il diametro di rame di 0,45 mm e il foro da 0,20 mm. Il nuovo via di massa collega i piani interni e riduce la distanza del ritorno da 1,304 a 0,658 mm. Il DRC conserva 121 segnalazioni storiche; il PCB ricaricato conserva 698 coppie già collegate e 449 unioni aperte. [Controlli di conservazione](experiments/phy-power-parallel/bga-referenced-barrel-preservation.json)

Il nuovo tratto da 0,350 mm passa sopra l'apertura del piano attorno al via. Serve il modello dell'intera transizione per verificarne la risposta ad alta frequenza. Dei 113 via di fuga esaminati, 32 fori nominali continuano a intersecare la piazzola di origine. Altre quattro correzioni restano in prova per la distanza del ritorno di massa. [Geometria ricaricata](experiments/phy-power-parallel/ddr-referenced-escape-land-proximity.json)

La variante [DQ9_B da U1.C27](experiments/phy-power-parallel/bga-c27-referenced-barrel.json) usa il ritorno di B27 a 0,782 mm e supera i controlli di continuità e distanza. Il tratto aggiunge 2,769 mm di rame e sposta l'uscita più lontano dalla RAM. La stima planare 2116A del rame presente su DQ9_B cresce di 16,72 ps, mentre DQS1P_B e DQS1N_B sono ancora aperti. Il percorso minimo geometrico passa da 16,97 a 21,09 mm, contro 15,79 e 16,00 mm per le due polarità DQS. La differenza fra minimi geometrici non misura lo skew finale. Il coupon resta separato fino al routing del byte. [Analisi geometrica del byte](experiments/phy-power-parallel/bga-c27-byte-budget.json)

## Primo collegamento del bus comandi LPDDR4

Il [checkpoint CA1, canale A](experiments/phy-power-parallel/layout-command-ca1.json) collega U1.A10 a U2.J2. Il tratto su In3 misura 17,86 mm e conserva 0,20 mm di larghezza. Due nuovi via di massa distano 0,671 e 0,707 mm dai via del segnale. Il controllo geometrico sullo strato adiacente esclude tratti paralleli entro 0,20 mm con angolo inferiore a 15° nel percorso campionato. Il [confronto dei ritorni](experiments/phy-power-parallel/ddr-ca1-plane-impact.json) ha esaminato 32 segmenti preesistenti senza rilevare peggioramenti nell’area proiettata. Restano da qualificare impedenza, ritardi rispetto al clock e margini di setup/hold dell’intero gruppo su entrambi i canali.

Il PCB ricaricato verifica **698 coppie**, con 203 reti aperte, 449 unioni minime e 121 segnalazioni di via ancora senza prosecuzione. Il percorso alternativo CA5 resta sperimentale.

### Studio dei clock LPDDR4

Su una copia del PCB, il [clock B](experiments/phy-power-parallel/ddr-clock-b-recovered.json) collega entrambe le polarità fra processore e RAM e conserva 700 coppie di pad verificate. Il percorso richiede di ricollocare 19 uscite BGA e presenta una differenza di lunghezza P/N di 1,906 mm. Il clock A e i riferimenti temporali dei due bus comando restano aperti. Questi risultati appartengono al coupon sperimentale.

Una [seconda disposizione della coppia B](experiments/phy-power-parallel/ddr-clock-b-preserved-recovered.json) conserva altri tre via originali. Rimangono 16 uscite da ripristinare e 9 nuove segnalazioni di estremità libere rispetto al PCB adottato. Le [lunghezze sul PCB ricaricato](experiments/phy-power-parallel/ddr-clock-b-preserved-budget.json) sono 18,511 mm per P e 16,627 mm per N. La differenza di 1,884 mm richiede una revisione dei tratti terminali e del percorso accoppiato. Nel [campionamento geometrico](experiments/phy-power-parallel/ddr-clock-b-preserved-coupling.json), su In3 oltre 1,42 mm del conduttore P e 1,19 mm del conduttore N hanno un distacco fra i bordi superiore a 0,50 mm. Il modello planare a linee singole non quantifica la conversione di modo in questi tratti.

Sul precedente checkpoint CA1, [33 dei 113 fori di fuga esaminati](experiments/phy-power-parallel/ddr-escape-land-proximity.json) intersecano in pianta il rame della rispettiva sfera. Per queste posizioni servono il confronto con le tolleranze di foratura e registrazione, il disegno della maschera e la conferma del processo di riempimento e metallizzazione oppure una fuga esterna alla piazzola. La continuità CAD da sola non verifica la saldabilità.

## Alimentazione VCCQ e primo tratto DAT0 della eMMC

Il [checkpoint eMMC](experiments/phy-power-parallel/layout-emmc-data-power.json) verifica L405.2–R8006.1, R8006.2–C8002.1 e il pull-up DAT0 da 10 kΩ. La sfera A3 della memoria raggiunge R8001.2 con 18,90 mm di rame e due cambi strato. I via di ritorno più vicini distano 0,90 e 0,91 mm. La connessione a U1.J25, le restanti alimentazioni, la temporizzazione del bus e l’avvio fisico restano da verificare. Il PCB ricaricato conserva 697 coppie con 450 unioni residue e 123 segnalazioni storiche.

## Alimentazione delle sfere N12 e K12

Il [checkpoint N12](experiments/phy-power-parallel/layout-memory-n12.json) verifica L403.2–U2.N12 con una derivazione posteriore da 0,60 mm lunga 8,60 mm e due via lato memoria. La [derivazione verso K12](experiments/phy-power-parallel/layout-memory-n12-neighbors.json) aggiunge 1,47 mm di rame frontale da 0,50 mm. Il PCB ricaricato verifica 694 coppie con 453 unioni residue. Rimane da qualificare il disaccoppiamento locale della sfera.

## Calibrazione ZQ della memoria

Il [PCB ricaricato](experiments/phy-power-parallel/layout-memory-zq-supply.json) unisce il lato alimentazione di R201 alla sfera U2.A4 e all’uscita L403.2 attraverso una derivazione da 0,60 mm lunga 12,70 mm. Il lato opposto del resistore da 240 Ω conserva il collegamento a U2.A5. Risultano verificate 692 coppie con 455 unioni residue e 123 segnalazioni preesistenti. Il comportamento della calibrazione ZQ richiede il sistema fisico e la verifica del rail in esercizio.

## Sezioni dei tronchi di alimentazione della memoria

Il [PCB verificato](experiments/phy-power-parallel/layout-memory-trunk-widths.json) allarga 14 tratti originari fino a 1,40 mm dove rame, fori e segnali adiacenti lo permettono. Nel [modello resistivo](experiments/phy-power-parallel/memory-trunk-widths.json) con rame esterno da 35 µm e interno da 18 µm a 20 °C, il tronco da 1,1 V passa da 66,35 a 43,82 mΩ e quello da 1,8 V da 43,42 a 32,15 mΩ. Entrambi i [piani di riferimento](experiments/phy-power-parallel/memory-trunk-widths-projection.json) conservano la stessa area e sagoma. L’audit conta 690 coppie, 457 unioni aperte e 123 avvisi DRC preesistenti. La resistenza delle vie e la risposta dinamica del circuito richiedono ancora verifica.

## Distribuzione da L403 alla memoria

Il [PCB adottato](experiments/phy-power-parallel/layout-lpddr-vddq-source.json) collega L403.2 a U2.AB4 e al banco di 33 condensatori. Il tragitto misura 46,95 mm su quattro strati con rame largo 0,60 mm. Il ripristino di J3.32–U1.AG19 elimina il moncone del precedente percorso MOSI. La verifica cumulativa conta 690 coppie e 457 unioni aperte; restano 123 avvisi DRC preesistenti. Sono ancora aperti il nodo di commutazione U4.25–L403.1, il feedback del BUCK3 e altre sfere di memoria. La [stima resistiva](experiments/phy-power-parallel/memory-trunk-dc-estimate.json) separa il solo rame del percorso dalle impedenze di via, induttore e regolatore.

## Distribuzione da L405 alla memoria

Nel [PCB adottato](experiments/phy-power-parallel/layout-lpddr-vdd1-source.json) L405.2 alimenta il banco di U2.F1 attraverso 28,18 mm di piste da 0,60 mm, con due vie a ogni estremità della distribuzione interna. La rete di commutazione U4.53–L405.1 e il ritorno di misura U4.59 sono connessi. Il [controllo delle proiezioni](experiments/phy-power-parallel/vdd1-source-barrel-projections.json) confronta le due piste vicine ai quattro fori introdotti o allargati. Il totale è di 687 coppie CAD verificate e 458 unioni residue. Restano la distribuzione alle altre sfere e le verifiche di caduta di tensione, transitori e temperatura.

## Rail VDD1 della LPDDR4

Sul [PCB ricaricato](experiments/phy-power-parallel/layout-lpddr-vdd1-bank.json) C2302, C2304, C2306 e C2307 raggiungono la sfera U2.F1 attraverso il banco C2305/C2308. Il nuovo tratto sul retro misura 7.50 mm ed è largo 0,50 mm. L405, sorgente del rail, resta separato. La verifica cumulativa conta 685 coppie, 459 unioni aperte e 123 avvisi preesistenti.

## Risveglio host dal modulo Wi-Fi

Sul [PCB verificato con ritorni di massa](experiments/phy-power-parallel/layout-radio-returns.json) U25.13 raggiunge U1.V26. Il passaggio dal retro usa una via da 0,45/0,20 mm; il reset del PHY adiacente conserva i due punti di connessione originali. Restano 460 unioni minime aperte tra i pad presenti su 204 reti. Due vie di massa collegano i piani a 0,71 e 0,82 mm dalle rispettive transizioni del segnale, rispetto ai precedenti 1,57 e 5,55 mm. Il terzo punto esaminato resta a 3,01 mm. Il percorso completo di risveglio misura 73,42 mm e comprende otto vie; la risposta elettrica resta da qualificare. Le 681 coppie fisiche sono state ricontrollate e il DRC segnala 123 vie pendenti preesistenti. La [verifica dello schema](experiments/phy-power-parallel/routed-schematic-review.md) identifica separatamente i dieci terminali funzionali del display ancora assenti dal PCB.

## Banco GPU

Il [PCB ricaricato](experiments/phy-power-parallel/layout-gpu-cap-bank.json) collega C1619 e C1620 con 7,38 mm di rame largo 0,60 mm sul retro. Entrambi i condensatori raggiungono la massa di U4.69. Restano da collegare L402 e il carico U1. Il controllo cumulativo copre 680 coppie su 205 reti, con 461 unioni aperte e 123 segnalazioni DRC preesistenti.

## Checkpoint corrente del banco di bypass LPDDR4

Il [PCB verificato](experiments/phy-power-parallel/layout-memory-cap-return.json) unisce tutti i 33 condensatori da C1646 a C1678, TP7 e la sfera U2.AB4 su +1V1_LPDDR4. L’ultimo tratto è lungo 2,41 mm e largo 0,50 mm. C1648 e la sua via di massa sono stati spostati insieme di 0,106 mm. Il [controllo del ritorno](experiments/phy-power-parallel/memory-bank-cap-return-projection.json) conferma la copertura sotto le tre piste vicine e la distanza dalla massa delle tre vie di segnale circostanti. Il totale è di 677 coppie e 462 unioni aperte su 205 reti, con 123 avvisi preesistenti. La distribuzione dall’induttore L403 e verso le altre sfere resta da completare.

## Collegamenti del banco a 1,1 V

Sul [PCB con derivazione posteriore](experiments/phy-power-parallel/layout-memory-bank-rear-taps.json), C1669.1 e C1677.1 raggiungono U2.AB4 e C1666.1 mediante 2,32 mm di rame largo 0,50 mm sul retro. La verifica cumulativa conta 676 coppie, 463 unioni aperte e 123 avvisi DRC preesistenti. Il gruppo di C1663, C1668 e C1676 è ancora separato, come l’uscita dell’induttore L403.

## Alimentazione LPDDR4

Sul [PCB adottato](experiments/phy-power-parallel/layout-memory-ab4-bank.json), U2.AB4 e il suo condensatore C1674 sono connessi al banco di C1666 su In3. Le diramazioni da 0,50 mm utilizzano due passaggi paralleli al lato del banco. Il controllo cumulativo conta 675 coppie, 464 unioni aperte su 205 reti e 123 avvisi di via pendente. La [proiezione sullo strato adiacente](experiments/phy-power-parallel/memory-ab4-bank-broadside.json) individua due attraversamenti di +3V3_IO e nessuna pista dati entro il margine analizzato di 0,35 mm. La [normalizzazione geometrica](experiments/phy-power-parallel/memory-ab4-normalized.json) rimuove dieci segmenti completamente ricoperti da rame collineare della stessa rete. L’uscita dell’induttore L403 e le altre sfere di alimentazione della memoria richiedono ancora collegamenti.

## Bypass della memoria

Il [PCB ricaricato](experiments/phy-power-parallel/layout-memory-ab4-bypass.json) collega la sfera U2.AB4 al condensatore da 100 nF C1674, riposizionato sul retro. Due vie da 0,45/0,20 mm trasferiscono il rail da 1,1 V e due il ritorno. Il ramo positivo più lungo misura 4,87 mm ed è largo 0,50 mm. La copertura di massa sotto le piste LPDDR esistenti coincide nel [controllo precedente](experiments/phy-power-parallel/lpddr-return-before-ab4.json) e in quello [successivo allo spostamento](experiments/phy-power-parallel/lpddr-return-after-ab4.json), campionati ogni 0,025 mm. L’audit conta 674 coppie, 465 unioni aperte e 123 avvisi preesistenti. L’efficacia del bypass alle frequenze della memoria resta da qualificare.

## Ritorni della memoria

Il [PCB ricaricato](experiments/phy-power-parallel/layout-ground-land-offsets.json) aggiunge quattro collegamenti di massa fra sfere vicine della LPDDR4 e porta altre 17 sfere al gruppo di massa di U4.69 mediante tratti da 0,30 mm di larghezza e da 0,73 a 1,84 mm di lunghezza. Il totale è di 672 coppie verificate, 466 unioni aperte su 205 reti e 123 avvisi di via pendente. Questi dati misurano la continuità CAD.

## Ritorni del SoC

Sul [PCB verificato](experiments/phy-power-parallel/layout-soc-ground-neighbors.json) 30 ulteriori sfere di U1 raggiungono la massa di U4.69. Sono state controllate sia le nuove coppie di pad sia l’appartenenza di ciascuna sfera al gruppo di massa centrale. La verifica cumulativa conta 651 coppie distinte e 487 unioni aperte su 205 reti. Il DRC mantiene i 123 avvisi di via pendente. Il confronto copre la continuità CAD. L’impedenza dei ritorni ad alta frequenza richiede una verifica separata.

## Alimentazioni del SoC

Il [PCB ricaricato](experiments/phy-power-parallel/layout-soc-core-neighbors.json) collega U1.1E8–U1.1E9 sul rail LPDDR4 da 1,1 V e U1.1G10–U1.1H10 su VDD_LOGIC. Entrambe le piste misurano 0,45 mm e sono larghe 0,50 mm. Il controllo cumulativo conta 621 coppie distinte, 517 unioni aperte su 205 reti e 123 avvisi di via pendente. La distribuzione a monte dei due banchi resta incompleta.

## Controllo USB e alimentazione eMMC

Il [PCB con controllo di orientamento USB-C](experiments/phy-power-parallel/layout-usb-direction-complete.json) collega U6.11 al pull-up R602.2. La via attraversa lo spazio liberato da C1665. Il controllo KiCad conta 619 coppie distinte, 519 unioni minime aperte su 205 reti e 123 avvisi via_dangling preesistenti. La commutazione con cavo reversibile richiede una prova su prototipo.


Il [PCB verificato con C1665 riposizionato](experiments/phy-power-parallel/layout-memory-bank-c1665.json) collega il condensatore da 100 nF al banco da 1,1 V della LPDDR4 e alla massa. Il ramo positivo misura 1,11 mm. La verifica sul PCB ricaricato conta 618 coppie distinte, 520 unioni minime aperte e 123 avvisi via_dangling preesistenti.


Sul [PCB adottato](experiments/phy-power-parallel/layout-emmc-perimeter-supply.json) le sfere M4 e N4 di U8001 sono unite da 0,30 mm di rame largo 0,35 mm sulla rete I/O a 1,8 V. Le sfere J10 e K9 sono collegate da 2,24 mm di rame largo 0,30 mm sulla rete a 3,3 V. Entrambi i percorsi sono sul lato del componente. Dopo il ricaricamento risultano 616 coppie verificate e 521 unioni aperte su 206 reti, con 123 avvisi di via pendente preesistenti. L’alimentazione e l’avvio della eMMC richiedono ancora il completamento della distribuzione.

## Antenna esterna sul layout USB corrente

Sul [coupon U.FL aggiornato](experiments/phy-power-parallel/rf-external-usb-direction.json) le modifiche al layout USB ed eMMC conservano i gruppi di pad preesistenti, i fissaggi e il risultato del DRC. Le [sette verifiche RF e di massa](experiments/phy-power-parallel/rf-external-plane-projection-usb-direction.json) passano per entrambe le geometrie in esame. Per lo stack 3313 le piste larghe 0,154 mm violano otto volte la regola di larghezza. Sul 7628 le aperture di tre pin passanti Ethernet interrompono il margine laterale di massa di 0,20 mm sotto le piste. La [mappa degli ostacoli](experiments/phy-power-parallel/rf-external-reference-obstructions.json) identifica i pin per UUID. La [ricerca delle deviazioni](experiments/phy-power-parallel/rf-external-plane-detours.json) a passi di 0,10 mm e con i pad fissi non ha trovato un percorso nella finestra locale. Il coupon resta separato dal PCB adottato.

## Coupon del PMIC ruotato

Sul [coupon verificato](experiments/phy-power-parallel/runs/rotated-buck-return-pair-C422-C432/boundary-contracts.json) sono stati recuperati dieci ritorni di condensatori. Il primo passaggio ha chiuso C482, il secondo sette ulteriori condensatori e i due successivi C412 e C483. Sono state ripristinate le dieci connessioni tra le masse perimetrali del PMIC e il pad esposto. Entrambe le linee di gestione I²C raggiungono i rispettivi resistori. Per SCL è stata riutilizzata una via già collegata al pin U4.1. Le piste da 0,50 mm collegano anche U4.45 e U4.33 al gruppo di alimentazione di C1304.1. Sul retro, percorsi da 0,50 mm uniscono i positivi di C421/C422 e C423/C482/C483. Il banco C423/C482/C483 raggiunge C1304.1 con due vie distanziate di 0,608 mm e piste da 0,50 mm. Il banco C421/C422 attende la connessione alla sorgente. Il ritorno locale tra C422 e C432 misura 2,35 mm con una pista da 0,60 mm e richiede ancora il collegamento al piano di massa. Restano 25 ricongiungimenti per recuperare i gruppi della baseline del coupon. L’alimentazione dei cinque convertitori e la risposta sotto carico sono ancora da completare e qualificare. Una prova con un piano locale sul retro unisce quattro condensatori in KiCad. La verifica del corridoio di ritorno largo 0,60 mm (0,30 mm per C470) trova una sola via raggiungibile da C432 e nessuna dagli altri tre entro 2,4 mm. La [verifica dei percorsi](experiments/phy-power-parallel/rotated-buck-plane-paths.json) e la [mappa dei siti di foratura](experiments/phy-power-parallel/rotated-buck-plane-barrel-screen.json) tengono il piano su un coupon separato.

## Checkpoint dei filtri analogici USB

Sul [PCB ricaricato](experiments/phy-power-parallel/layout-usb-analog-1v8.json) il filtro a 1,8 V collega C1635.1 a R1602.1 e R1602.2 a C1682.1. C1682.2 raggiunge la massa di U4.69. La verifica cumulativa conta 614 coppie, 523 unioni aperte su 206 reti e 123 avvisi preesistenti di via pendente. Il PMIC e le sfere analogiche USB del SoC richiedono ancora il completamento dei percorsi di alimentazione.

## Checkpoint del filtro analogico USB a 0,9 V

Il [PCB adottato](experiments/phy-power-parallel/layout-usb-analog-0v9.json) collega R1601.1 a C1642.1 e R1601.2 al banco C1679.1–C1680.1. Il trasferimento conserva il rame precedentemente adottato e sposta R1601 fuori dalla zona proposta per l’antenna interna. Il controllo cumulativo sul file ricaricato verifica 611 coppie di pad e conta 525 unioni aperte su 206 reti. Il DRC riporta i 123 avvisi di via pendente già presenti. L’alimentazione dal regolatore e il collegamento alla sfera USB del SoC sono ancora aperti.

## Checkpoint del controllo USB

Il [PCB adottato](experiments/phy-power-parallel/layout-usb-enable-trunk.json) collega il consenso del mux da U16.4 a U6.12 con un tronco da 6,70 mm. Il tratto adiacente AON_READY è stato reinstradato a larghezza invariata di 0,20 mm. La verifica del PCB ricaricato conta 608 coppie distinte verificate, 527 unioni ancora da chiudere su 206 reti e 123 avvisi di via pendente preesistenti. La commutazione e il funzionamento SuperSpeed richiedono il completamento dei collegamenti USB e la prova su prototipo.

## Checkpoint della selezione del display

Il [PCB adottato](experiments/phy-power-parallel/layout-lcd-select-trunk.json) collega U1.M3 a U21.6 e R1815.1 con 14,71 mm di nuovo tronco LCD_CS_N. Il ritorno dedicato di U1.1F1 raggiunge la propria via con un tratto da 0,30 mm largo e 0,478 mm lungo. La [verifica del riferimento LPDDR4](experiments/phy-power-parallel/lpddr-return-after-display.json) conserva la copertura di massa già campionata. L’audit conta 607 coppie distinte, 528 unioni su 207 reti e 123 avvisi preesistenti. Restano aperti il reset e i dati del display lato SoC.

## Checkpoint del clock del display

Il [PCB verificato](experiments/phy-power-parallel/layout-lcd-clock-trunk.json) collega U1.N3 a U21.3 e R1812.1 sulla linea LCD_SCLK. Una traslazione di R8001 di 0,10 mm, con orientamento invariato, libera l’uscita del SoC preservando la connettività eMMC. Il nuovo tronco misura 16,43 mm. Restano aperti MOSI, CS e reset lato CPU. L’audit conta 605 coppie distinte, 529 unioni minime su 208 reti e 123 avvisi preesistenti di via pendente.

## Checkpoint del consenso di accensione CPU

Il [PCB adottato](experiments/phy-power-parallel/layout-cpu-enable-bias.json) chiude il pull-up da 51 kΩ del regolatore CPU. R1002.1 raggiunge la distribuzione +3V3_PMU e R1002.2 raggiunge U10.A2. La [modifica al gomito di WIFI_VBAT](experiments/phy-power-parallel/cpu-enable-vbat-elbow.json) conserva la larghezza di 1,00 mm su In3 e abbrevia quel tratto di 0,143 mm. Dopo ricarica e DRC risultano 603 coppie distinte verificate, 530 unioni minime aperte su 209 reti e 123 avvisi preesistenti. Il collegamento della sorgente U4.31 alla distribuzione +3V3_PMU rimane aperto.

## Checkpoint del chip-select SPI di espansione

Il [PCB adottato](experiments/phy-power-parallel/layout-exp-spi0-pullup.json) collega J3.34, U1.AG17 e R2103.1 sulla prima linea di selezione SPI. R2103.2 torna al gruppo di alimentazione +3V3_PMU. Il [controllo del ritorno all’alimentazione](experiments/phy-power-parallel/exp-spi0-restore-feed.json) e l’audit cumulativo verificano 602 coppie distinte, con 531 unioni aperte su 209 reti e 123 avvisi preesistenti. La sorgente della tensione +3V3_PMU e la seconda linea di selezione richiedono ancora cablaggio.

## Checkpoint del bus I²C di espansione

Il [PCB ricaricato](experiments/phy-power-parallel/layout-exp-sda-complete.json) collega entrambe le linee I²C del SoC a J3 e ai resistori da 4,7 kΩ. Su SDA sono stati verificati U1.AE15, J3.23 e R2101.1. R2101.2 raggiunge U4.55. Il ritorno di massa sul retro del SoC e GPIO1 vicino al connettore conservano i collegamenti verificati. L’audit conta 599 coppie distinte, 532 unioni minime aperte, 210 reti aperte e 123 avvisi preesistenti.

La [stima dei tempi di salita](experiments/phy-power-parallel/exp-i2c-rise-estimate.json) considera 95,54 mm di rame per SDA e 56,01 mm per SCL. I due stack esaminati danno circa 9,8 pF e 5,7–5,8 pF per le sole piste. Con i pull-up nominali rimangono circa 65 pF di margine su SDA per contenere la salita entro 300 ns a 400 kHz. Questo margine deve coprire pad, vie, pin e accessorio. La misura sul prototipo e sul modulo di espansione completerà la verifica.

## Checkpoint delle alimentazioni dei pull-up

Il [PCB verificato](experiments/phy-power-parallel/layout-wifi-io-pullup-bank.json) collega alla tensione I/O i due resistori di pull-up I²C dell’espansione e quattro dei cinque resistori di pull-up SDIO. J3.24 raggiunge R2102.1 e U4.55 raggiunge R2102.2. Sul modulo Wi-Fi U25.14 raggiunge R2012.1 e R2012.2 raggiunge la tensione I/O. Restano aperti la linea dati I²C dell’espansione, l’alimentazione di R2011 e parte del cablaggio SDIO. L’audit conta 596 coppie di pad distinte dopo la normalizzazione dei versi, 534 unioni minime aperte su 211 reti e 123 avvisi di via pendente.

## Checkpoint del piano di riferimento LPDDR4

Il [PCB adottato](experiments/phy-power-parallel/layout-lpddr-dq0-reference.json) riposiziona due vie delle linee DQ4_B e DQ5_B per riportare rame di massa sotto DQ0_B. Dopo il riempimento e la ricarica, tutti i 72 punti della finestra campionata sul piano hanno massa, rispetto agli otto precedenti. La [verifica geometrica](experiments/phy-power-parallel/lpddr-dq0-reference.json) conserva larghezza e foratura, le 589 coppie già validate e i tre ritorni di clock. Restano 540 unioni minime aperte su 211 reti e 123 avvisi di via pendente. Questa verifica riguarda la geometria locale.

## Checkpoint dei ritorni di clock LPDDR4

Il [PCB adottato e ricaricato](experiments/phy-power-parallel/layout-lpddr-clock-return.json) aggiunge tre vie di massa passanti da 0,45/0,20 mm fra i due piani di riferimento. Sul lato RAM di entrambi i canali, la via di ritorno dista al più 1,01 mm dalle due vie della coppia di clock. Sul lato SoC del canale A la distanza massima è 1,48 mm. I [riscontri geometrici](experiments/phy-power-parallel/lpddr-clock-return-stitches.json) comprendono il rame attorno alle nuove vie su entrambi i piani e la connettività con la massa del PMIC. Il controllo cumulativo conserva 589 coppie e conta 540 unioni aperte su 211 reti e 123 avvisi preesistenti di via pendente. Il clock end-to-end e il timing RAM restano aperti.

Il [confronto simulato dei due stack a sei strati](experiments/phy-power-parallel/usb-ddr-stack-simulation.json) distingue i segnali esterni da quelli sulle due facce interne di segnale. Sul 7628, assumendo Dk 4,4, le coppie esterne larghe 0,30 mm con gap 0,25 mm raggiungono circa 91 Ω; con larghezza 0,24 mm raggiungono circa 100 Ω. Sul 3313 le stesse geometrie esterne danno circa 65 e 74 Ω. Il [modello MDI](experiments/phy-power-parallel/outer-pair-impedance-simulation.json) esplicita geometria del rame, maschera e convergenza numerica. Lo stack definitivo, le tolleranze di fabbricazione, le discontinuità ai package e la misura sul coupon restano da qualificare.

## Checkpoint del filtro di accensione

Il [PCB verificato](experiments/phy-power-parallel/layout-pmic-pwron-filter.json) porta il condensatore C412 da 100 nF sul retro del PMIC. U4.52 raggiunge C412.1 attraverso una via passante. Il ritorno di C412.2 raggiunge la massa comune di U4.69 con una pista da 0,30 mm. Il controllo cumulativo dopo ricarica verifica 589 coppie, 540 unioni minime ancora aperte su 211 reti e 123 vie pendenti. La prova di accensione e le forme d’onda richiedono un prototipo.

Il [coupon del partitore VDC](experiments/phy-power-parallel/runs/vdc-placement-0/restore-status.json) unisce U4.61 ai tre componenti del filtro e chiude entrambi i ritorni del partitore. Rimangono da ripristinare il feedback BUCK5, il positivo del partitore e il ritorno di C481. Il coupon è separato dal PCB corrente.

Sul [coupon di riposizionamento congiunto del PMIC](experiments/phy-power-parallel/runs/pmic-five-stage-secondary-0/boundary-contracts.json) le cinque uscite di commutazione raggiungono i rispettivi induttori e ciascun induttore raggiunge il suo condensatore principale. BUCK5 recupera sette degli otto collegamenti locali del progetto originario, compresi il feedback prelevato su C435 e il secondo condensatore d’uscita C445. Rimane aperta U4.54–C425.1. Le due bancate del connettore di espansione raggiungono il ramo originale da 1 mm su In3. Il coupon conserva 537 delle 589 coppie del PCB corrente. Restano 54 ricongiungimenti minimi per recuperare i gruppi originari e 586 per chiudere tutte le reti del coupon. Sono verifiche di continuità e geometria in KiCad. Il comportamento dei regolatori sotto carico richiede misure.

## Checkpoint del bus Ethernet RGMII

Il [PCB ricaricato](experiments/phy-power-parallel/layout-soc-tx-series.json) collega U1.AA1 a R501.1 con 1,190 mm di rame da 0,20 mm senza vie. È chiuso il tratto sorgente di TXD0. Restano da realizzare il tratto lato PHY e la verifica dei tempi del bus. Il controllo cumulativo conta 587 coppie, 541 unioni minime aperte su 212 reti e 123 vie pendenti.

Il [checkpoint del ramo ricevente](experiments/phy-power-parallel/layout-phy-source-series.json) collega l’uscita RXD1 del PHY, U5.24, al resistore serie R508.2 con una pista da 0,20 mm lunga 2,229 mm, senza vie. Nel modello CAD il percorso presenta rame GND su In1 lungo la derivazione. Restano da collegare il resistore di strap e il percorso R508–SoC e da verificare impedenza, tempi del bus e funzionamento fisico. Il DRC differenziale sul PCB ricaricato conserva le protezioni preesistenti.

## Checkpoint del connettore Ethernet

Il [PCB verificato](experiments/phy-power-parallel/layout-hanrun-hole-stagger.json) corregge di 0,110 mm i centri dei cinque fori pari di J2, da P2 a P10. Il [disegno HanRun HR911130A, pagina 2](../reference/HR911130A.pdf) quota P6 a 0,64 mm dall’asse e 2,54 mm fra pin consecutivi della stessa fila. Una pista di ritorno GND da 0,40 mm conserva i suoi terminali e passa 0,10 mm più lontano da P2. Il [confronto dimensionale e DRC](experiments/phy-power-parallel/hanrun-hole-stagger.json) conserva tutte le connessioni già verificate. Il montaggio richiede riscontro sul campione fisico.

P10 è il ritorno del condensatore interno da 1 nF / 2 kV della terminazione lato cavo, come indicato a pagina 1 del disegno HanRun. Il [controllo della regione chassis](experiments/phy-power-parallel/ethernet-chassis-clearance.json) individua entrambi i piani GND sotto i due possibili collegamenti diretti. Il PCB mantiene aperta la definizione della regione chassis e la qualifica EMC.

## Checkpoint del rame sovrapposto

Il [PCB ricaricato e verificato](experiments/phy-power-parallel/layout-coincident-cleanup.json) conserva 585 coppie, con 543 unioni minime aperte su 213 reti e 123 vie pendenti. Sono state eliminate 149 copie perfettamente sovrapposte di segmenti rettilinei. Per ogni UUID rimosso è registrato il segmento equivalente ancora presente. Restano 6.593 oggetti fra piste e vie. Il DRC differenziale e la connettività nativa confermano il risultato.

Il [coupon USB](experiments/phy-power-parallel/usb-selective-padfield.json) trova una geometria delle due derivazioni reversibili con due vie per polarità, lunga rispettivamente 3,411 e 3,576 mm. Per ripristinare CC1, CC2 e +3V3_AON dopo questo spostamento serve un'altra disposizione dei lanci. Il [controllo del primo ripristino](experiments/phy-power-parallel/usb-restored-pair-0.json) individua la strozzatura attorno a J1.B5. La coppia è attualmente esclusa dal PCB verificato.

## Checkpoint dei collegamenti locali del SoC

Il [PCB verificato dopo il salvataggio](experiments/phy-power-parallel/layout-cpu-load-sense.json) comprende 33 collegamenti locali fra pad GND di U1 su rame da 0,50 mm. Due ulteriori tratti da 0,50 mm collegano pad di VDD_CPU e VDD_LOGIC. Otto rami da 0,50 mm uniscono altri gruppi alla massa comune. Altri sette ritorni da 0,50 mm raggiungono il rame di massa esistente, inclusi U2.G12 e U2.P1. Un via passante da 0,45/0,20 mm porta al piano il gruppo di quattro pad attorno a U1.1J4 con un tratto da 0,361 mm. Sette rami da 0,50 mm completano collegamenti locali tra condensatori del rail LPDDR4 da 1,1 V. Tre ulteriori rami collegano i condensatori C1679–C1680, C2304–C2302 e C1603–C1604. Sul retro R2012.1 raggiunge U25.14 con un ramo di pull-up da 1,763 mm su WIFI_D2. Restano da collegare il rail del resistore e il segnale verso il SoC. TP6 misura il ramo +3V3_IO di U25, TP7 il gruppo di bypass +1V1_LPDDR4 di C1650. TP8 misura VDD_CPU sul ramo di C1603. I tre pad di misura da 1 mm sono sul retro. Sono verificate 585 coppie. Restano 543 unioni minime su 213 reti e 123 via con estremità aperta. I gruppi locali richiedono ulteriori ritorni al piano di massa.

## Checkpoint delle derivazioni di alimentazione

Il [PCB ricaricato](experiments/phy-power-parallel/layout-bank-feeds.json) comprende il ramo da 0,50 mm tra R8001.1 e R8006.2 su EMMC_IO_1V8 e 12 ulteriori collegamenti fra condensatori. Sono verificate 520 coppie. Restano 610 unioni minime su 213 reti. Il ritorno locale delle alimentazioni e la regolazione sotto carico restano da misurare.

## Checkpoint dei fissaggi USB-C

Sul [PCB verificato](experiments/phy-power-parallel/layout-usb-shell.json) i quattro terminali della schermatura di J1 formano un unico gruppo. Due tratti da 1 mm sono sul retro e il terzo è su In3.Cu. Le verifiche usano gli UUID dei quattro pad perché condividono tutti il numero SH. Restano 623 unioni minime su 213 reti. La terminazione dello schermo e la compatibilità elettromagnetica restano da qualificare.

## Checkpoint delle alimentazioni locali

Il [PCB verificato](experiments/phy-power-parallel/layout-peripheral-supply-balls.json) collega 27 coppie di sfere di alimentazione adiacenti e aggiunge 15 collegamenti locali tra condensatori. Le piste sono larghe 0,50 mm. La continuità di questi gruppi lascia ancora aperta la distribuzione dai regolatori. Restano 626 unioni minime su 214 reti e 123 segnalazioni di vie pendenti. Sono verificate 507 coppie sul PCB ricaricato.

## Checkpoint di alimentazione del PHY

Il [PCB ricaricato](experiments/phy-power-parallel/layout-phy-pin40-powered.json) collega C515, R530, C518 e U5.40. Il nuovo ramo su In2.Cu è largo 1,05 mm e lungo 5,719 mm. La deviazione di +5V_MAIN mantiene 0,80 mm su tutto il percorso sostituito. Due [prove di interruzione su copie del PCB](experiments/phy-power-parallel/phy-pin40-cut-tests.json) distinguono il tronco di distribuzione dalla via locale di C518. Sul PCB integro passano 465 verifiche di coppia. Restano 668 unioni minime su 214 reti. Le verifiche CAD non misurano ripple, stabilità del regolatore o avvio del quarzo.

## Checkpoint del pin 40 del PHY

Nel [PCB verificato](experiments/phy-power-parallel/layout-phy-pin40.json) C518 è sul retro. Il terminale di alimentazione raggiunge U5.40 con una via riempita e ricoperta. Il ritorno di C518 e quello del condensatore di carico C520 raggiungono la massa di C511. Il ramo C518–U5.40 deve ancora raggiungere il tronco +3V3_PHY. Restano 669 unioni minime su 215 reti. Le 464 verifiche di coppia includono i collegamenti del regolatore già validati. La geometria del ritorno e il circuito del quarzo richiedono verifica sul prototipo.

## Checkpoint dei ritorni BGA

Il [PCB verificato](experiments/phy-power-parallel/layout-outer-ground-mesh.json) include otto nuove vie di massa fuori piazzola e quattro rami sul SoC. Restano 670 unioni minime su 215 reti. Verificate 461 coppie sul PCB ricaricato, con 123 segnalazioni di vie pendenti.

## Checkpoint del SoC

Il [PCB con ritorni di massa del SoC](experiments/phy-power-parallel/layout-core-ground-mesh.json) aggiunge 13 vie passanti fuori piazzola (rame 0,45 mm, foro 0,20 mm) e 45 ulteriori rami verso la massa esistente. Le nuove vie sono distanti almeno 1 mm dai centri dei pad LPDDR4 vicini. Sono verificate 449 coppie sul PCB ricaricato. Restano 682 unioni minime su 215 reti e 123 segnalazioni di vie pendenti. Distribuzione della corrente, impedenza dei ritorni e producibilità del fanout richiedono ulteriori verifiche.

## Checkpoint dei ritorni di massa

Il [PCB ricaricato e verificato](experiments/phy-power-parallel/layout-all-ground-surface.json) include 15 nuovi rami di massa, dodici sul SoC e tre sui condensatori C1641, C1628 e C1636. Sono verificate 391 coppie. Restano 742 unioni minime su 215 reti e 123 segnalazioni di vie pendenti. La continuità in rame lascia da valutare impedenza e corrente dei ritorni condivisi.

## Checkpoint del tronco +3V3_PHY verso C516

Il [PCB verificato](experiments/phy-power-parallel/layout-phy-full-feed.json) collega R530 e C515 a C516 e U5.11. Il tronco su In2.Cu è lungo 8,817 mm e largo 1,05 mm. Due vie da 0,60/0,30 mm trasferiscono la corrente al lato componenti. Il ramo locale da C516 a U5.11 è lungo 1,248 mm. Le [cinque prove di interruzione](experiments/phy-power-parallel/phy-full-feed-proof.json) verificano il funzionamento delle vie in parallelo e la continuità del tronco anche isolandolo dal vecchio rame In2 della stessa rete.

La posizione del supporto ausiliario H8105 sul PCB corrente è **(70,20; 34,00) mm**. Il foro M2 da 2,20 mm e l’intera riserva meccanica sono traslati insieme di +0,20 mm lungo X. Le posizioni dei fissaggi della scheda figlia sono conservate. Per la staffa e il case usare le [coordinate dei cinque fori M2](experiments/phy-power-parallel/mounting-interface-current.json), confrontate con l’esportazione di foratura Excellon. C516 è a (66,90; 33,20) mm. Quote riferite alle coordinate KiCad.

Verificate 376 coppie sul PCB ricaricato. Rimangono 758 unioni minime su 215 reti e 123 avvisi di via pendente. La continuità CAD del nuovo ramo richiede ancora la verifica della caduta di tensione e della risposta ai transitori. Restano separati C518.1 e U5.40.

## Checkpoint del bypass LPDDR4

[PCB e audit cumulativo](experiments/phy-power-parallel/layout-opposite-bypass.json). C2308.1 raggiunge U2.F1 su +1V8_SYS con due tratti da 0,50 mm, lunghi complessivamente 1,563 mm, e una via da 0,60/0,30 mm. Le 374 verifiche di coppia sono passate sul PCB ricaricato. Restano almeno 759 unioni su 215 reti e 123 avvisi di via pendente. La ricerca di un ritorno aggiuntivo entro 1,20 mm dalla via di alimentazione non ha prodotto una geometria accettabile. Impedenza della distribuzione e risposta ai transitori restano da verificare.

### Vincoli verificati sullo stesso PCB

La [ricerca congiunta di C516 e del tronco da 1,05 mm](experiments/phy-power-parallel/phy-joint-pad-entry.json) include l’orientamento del condensatore, il suo ramo su U5.11 e le due coppie di vie di alimentazione esistenti. Nessun ingresso raggiunto nella finestra esplorata. Lo [spostamento di prova di H8105](experiments/phy-power-parallel/phy-bracket-trial.json) supera il DRC a +0,20 mm su X, ma non risolve il passaggio del tronco. Nel checkpoint del bypass LPDDR4 il foro conserva la posizione originale.

Su 64 segnali LPDDR4 aperti esaminati, [59 hanno una via collegata a entrambe le estremità](experiments/phy-power-parallel/ddr-reference-corridors.json). Cinque DQ mancano ancora della via dal lato SoC. Una [prova separata su In3](experiments/phy-power-parallel/ddr-byte-b1-maze-inner-all-data.json) collega tre segnali con verifica di continuità. Il controllo campiona il piano In4 lungo le piste, esclusi i primi e gli ultimi 0,60 mm. Impedenza, lunghezze interne ai package, temporizzazione del gruppo e ritorno alle transizioni restano aperti. Questo rame è salvato solo sulla copia di prova.

## Checkpoint dei ritorni dei package

[PCB e inventario](experiments/phy-power-parallel/layout-package-local.json). Rispetto al checkpoint R514, 34 unioni GND chiuse. Il CAD ricaricato conserva 373 verifiche di coppia, 215 reti con gruppi separati e 760 unioni residue. I sette nuovi fori sono esterni al rettangolo delle sfere con margine sul centro del foro di 0,35 mm. Tre sfere interne del SoC raggiungono vie già presenti. Restano aperti la verifica dei ritorni ad alta frequenza e il fanout dei segnali.

## Checkpoint dei ritorni sul rame esistente

[PCB ricaricato e verificato](experiments/phy-power-parallel/layout-ground-bends.json). Aggiunti 15 ritorni GND. Le 354 verifiche di coppia includono entrambi i pad di massa di J2001. Restano almeno 779 unioni su 215 reti e 123 avvisi di via pendente. Le prove di continuità non qualificano impedenza RF o induttanza di disaccoppiamento. Lo schema Ethernet con R514 da 1,5 kΩ è nel checkpoint precedente.

## Checkpoint R514

[PCB e foglio Ethernet](experiments/phy-power-parallel/layout-mdio-pullup.json). R514 da 1,5 kΩ, Yageo C114759. Netlist esportata e DRC verificati.

## Checkpoint corrente dei ritorni di massa

Il [PCB con l’audit cumulativo](experiments/phy-power-parallel/layout-peripheral-returns.json) aggiunge i ritorni al piano di J2001.2 e U23.3, lunghi rispettivamente 0,70 e 0,65 mm. Dopo la ricarica da disco risultano 339 verifiche di coppia superate e almeno 794 unioni residue su 215 reti. Rimangono 123 avvisi di via pendente. Il segnale RF di J2001 resta aperto.

La ricerca inversa del corridoio +3V3_PHY su griglia da 0,10 mm conserva C516 isolato dal tronco. La verifica documentale ha individuato una differenza indipendente sul bus di gestione Ethernet. R514 sul PCB vale 1,8 kΩ, mentre il datasheet RTL8211F rev. 1.9 prescrive 1,5 kΩ per MDIO. Il candidato 0402 da 1% è [Yageo RC0402FR-071K5L, C114759](https://jlcpcb.com/partdetail/YAGEO-RC0402FR071K5L/C114759). Il valore presente nel checkpoint resta 1,8 kΩ.

## Checkpoint corrente del regolatore PHY

Il [PCB verificato e l’inventario delle reti](experiments/phy-power-parallel/layout-regulator-joint.json) conservano le connessioni del checkpoint storage/I/O. Sul PCB ricaricato risultano 337 controlli di coppia superati, 215 reti ancora separate in più gruppi e almeno 796 unioni da completare. Il DRC cumulativo conserva i 123 avvisi di via pendente. Le 796 unioni sono una misura topologica distinta dagli avvisi.

C516 raggiunge U5.11 con un tratto da 1,04 mm. Sul ramo U5.30–L501.1 la lunghezza esposta prima del rame da 1,55 mm è 0,360 mm. Il detour da 1,55 mm su +1V0_PHY lascia spazio a una via GND da 0,55/0,30 mm nel pad esposto U5.41, salvata con riempimento e copertura. Restano da qualificare il processo di assemblaggio, la saldatura del pad e la dissipazione. Lo spostamento della via di ritorno accanto a C516 mantiene il ramo a 0,65 mm. La ricerca multistrato del collegamento da 1,05 mm tra il tronco +3V3_PHY e C516 rimane aperta. Gli esiti geometrici precedenti sono in [phy-c516-wide-ground-pad-entry.json](experiments/phy-power-parallel/phy-c516-wide-ground-pad-entry.json).

## Checkpoint del bus PMIC, dei controlli e della distribuzione eMMC

Il [checkpoint cumulativo](experiments/phy-power-parallel/layout-pmic-bus.json) include SCL tra U4.1 e R414.2 e SDA tra U4.2 e R415.2. Due prove di interruzione, in processi KiCad separati, rimuovono una via per ramo e verificano la perdita della sola continuità attesa rispetto ai controlli PHY. Restano aperti il collegamento dal SoC e la verifica dei tempi I²C. Sono inclusi sei tratti locali da 0,50 mm tra link e condensatori eMMC, senza qualifica della distribuzione completa né dei transitori.

## Checkpoint cumulativo dopo il routing dei ritorni e del reset

Il [PCB e il suo inventario di connettività](experiments/phy-power-parallel/layout-reset-connectivity.json) comprendono 42 ritorni di condensatori, la massa di R432 e il punto di prova TP1. R412 raggiunge C411 sul lato RESET_N e il gruppo di pull-up R416/R417 sul lato +3V3_PMU. La distribuzione a monte del gruppo è ancora aperta. Il conteggio delle unioni residue deriva dai gruppi di pad fisici ricalcolati sul PCB ricaricato.

## Ripresa della variante cumulativa PHY e memoria

Il [checkpoint del bus di gestione](experiments/phy-power-parallel/pmic-control-bus.json) identifica il PCB su disco. Comprende la riconciliazione dei fissaggi H8104/H8105 e del ritorno C1623, il reset LPDDR4, il collegamento locale di R201 e tre rami delle resistenze I²C. Gli otto collegamenti elencati in `held` restano aperti nella ricerca con componenti fissi. Il riferimento VDDQ di R201 e la distribuzione a monte dei pull-up richiedono ancora routing.

## Checkpoint della variante con punti di prova e polarizzazioni

La variante cumulativa verificata è identificata da [integrated-fixture-trunk.json](experiments/phy-power-parallel/integrated-fixture-trunk.json). Il file contiene il percorso relativo del PCB, SHA-256, 18 coppie di pad verificate, cinque prove di interruzione e le otto interferenze meccaniche residue. Il PCB principale conserva il proprio checkpoint separato.

Il controllo su disco preserva le 5.814 piste e vie e i 70 gruppi di pad del checkpoint C522. Tutte e cinque le resistenze di polarizzazione toccano il ramo +3V3_PHY e R521 raggiunge R510 sul lato RXD3. I restanti segnali e il bus RGMII completo richiedono ancora routing e verifica temporale. TP14, TP5 e TP9 raggiungono rispettivamente U17.4, C465.1 e U16.2. TP14 ha superficie di contatto libera dal foro di via. Il filtro C1503 e il partitore R1505/R1506 sono connessi localmente. Il ball U1.1P14 resta isolato. Lo schema porta al partitore +3V3_IO: prima di collegarlo al SoC occorre confermare la semantica di VBUSDET rispetto a inserzione USB e alimentazioni alternative.

I tentativi di escape non sovrapposti alle piazzole per i cinque bypass SoC interferenti sono registrati in [soc-bypass-escape.json](experiments/phy-power-parallel/soc-bypass-escape.json). Lo screening riguarda 13 ball, finestra ±1,2 mm, griglia 0,05 mm, traccia e clearance 0,20 mm, vie 0,45/0,20 mm. In tale finestra nessuna uscita rettilinea soddisfa i controlli. La qualifica del fanout BGA richiede il processo PCB e la geometria appropriati.

## Variante PHY verificata in CAD — 19 novembre 2026

La variante più avanzata della revisione congiunta di L501 e dei bypass PHY è identificata da [c522-verified.json](experiments/phy-power-parallel/c522-verified.json). Le modifiche restano nello studio isolato. Il [checkpoint di ingresso](experiments/phy-power-parallel/phy-upstream-verified.json) copre R530–C515 e le sue due coppie di vie. Il checkpoint successivo aggiunge la distribuzione a C522, il pin 38 e il ritorno a massa. Le prove di rimozione delle vie sono state eseguite su copie in memoria del PCB ricaricato da disco.

Il percorso a monte da 1,05 mm comprende 27,44 mm su In2. Il ramo a valle da 1,55 mm misura 5,40 mm, con ritorno di C522 da 3,43 mm. La modifica al quarzo porta XIN da 8,83 a 9,98 mm. Restano da qualificare il comportamento del convertitore, il fanout locale, il quarzo e l'assemblaggio delle vie in prossimità delle piazzole. I conteggi del checkpoint principale seguente si riferiscono al PCB principale.

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
