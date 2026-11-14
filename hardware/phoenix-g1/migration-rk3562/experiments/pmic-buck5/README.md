# BUCK5 — routing locale verificato, non qualificato elettricamente

Checkpoint di lavoro: `working-candidate.json`, PCB `pcb/layout-reviewed.kicad_pcb`.
La baseline eMMC rimane conservata in `../emmc-system/working-candidate.json`.
Non è una scheda pronta alla fabbricazione: mancano molte reti, qualifica del
regolatore e alimentazione a monte.

## Risultato del 14 novembre 2026

Gli otto collegamenti locali richiesti sono fisicamente connessi:
U4.53→L405.1, L405.2→C435.1/C445.1, U4.59→C435.1,
U4.54→C425.1 e masse di C425/C435/C445. Non è una deduzione dai nomi delle net:
`pcb/local-connectivity.json` contiene l'esito sul rame del PCB salvato.

- L405: fronte (60.5,1.4) mm, avvicinato al PMIC.
- C425: fronte (59.45,3.7), C435: fronte (57.3,1.4), C445: retro (55.5,7.75).
- SW5: collo 0.127 mm lungo 1.485 mm, parte principale 0.5 mm lunga 3.2781 mm.
- Ingresso VCC9: collo 0.127 mm lungo 1.8482 mm, parte principale 0.5 mm lunga 1.2993 mm.
- Feedback: collo 0.127 mm lungo 0.7307 mm, parte principale 0.2 mm lunga 4.6713 mm.
- Primo condensatore d'uscita collegato con pista 0.6 mm; secondo con pista 0.4 mm
  e via 0.45/0.20 mm. Il percorso del secondo condensatore non è qualificato per PI.
- Massa C435: raccordo da 0.95 mm. C445 è stato spostato di 0.25 mm dopo il routing; il rame resta connesso, ma la precedente misura centro-pad→via non è aggiornata. C425 conserva il raccordo preesistente,
  ma il suo piazzamento è stato spostato di 0.25 mm: non riusare automaticamente
  la vecchia lunghezza centro-pad→via come misura aggiornata.

Per liberare l'ingresso è stato rifatto il fanout SWOUT1 (+3V3_IO): quattro
primitive originali sono sostituite, con via 0.45/0.20 mm a (61.625,4.775).
Le due diramazioni In2 conservano le larghezze 0.2/0.5 mm. La portata del nuovo
via e del collo resta da verificare. Prima si instrada VCC9, poi SW5 e feedback;
l'ordine inverso occlude il corridoio.

Il bus +5 V J3 conserva ingresso e via originali: due segmenti sono accorciati,
con UUID autorizzati dall'audit, e un ponte In3 largo 0.8 mm conserva gli otto pin.
Tutti i 43 gruppi di pad già collegati nella baseline eMMC restano collegati.
Audit: 2003 istanze di pad; 4083 primitive originali conservate geometricamente
salvo le due estremità dichiarate, quattro primitive sostituite; il numero aggiornato delle aggiunte è nel report di audit del checkpoint.
Cinque aree meccaniche conservate. Nessuna nuova violazione DRC individuale;
**125 avvisi via_dangling rimangono**; i 14 avvisi di serigrafia sono stati risolti. Inventario: 239 reti multi-pad aperte.

R1811 passa a (51,7) e R431 a (84,6.5). C422 è sul retro a (54,10.5),
C470 sul retro a (63,6.5), ruotato per avvicinare il pin di alimentazione al via
SWOUT1 e la massa al ritorno esistente. Masse collegate: C422 0.95 mm, C470
1.8678 mm. C470.1 raggiunge U4.55 con pista B.Cu da 0.5 mm lunga 1.9010 mm.
C422.1 resta aperto: non è completata l'alimentazione BUCK2.

Le due riserve H8101 (53,4) e H8102 (83,3) sono libere dai corpi dei componenti
su entrambi i lati, nel raggio di 2.7 mm. Inseriti due fori NPTH da 2.2 mm,
candidati M2. C445 si sposta di 0.25 mm per liberare completamente H8101;
la conservazione della sua connessione è verificata sul rame, non presunta.
I tre fissaggi ausiliari restano riserve senza fori e richiedono revisione.
Quote di distanziali/viti, assemblaggio della scheda superiore, involucro e
compattazione a 85×35 mm non sono qualificati. Il PCB resta 90×40 mm.

## Riproduzione e controlli

Eseguire `tools/rebuild_pmic_buck5.py` con il Python incluso in KiCad. La sequenza
parte dalla baseline eMMC, ricostruisce piazzamento, bus, routing locale e
spostamenti meccanici; conserva una copia dei PCB e dei puntatori e li ripristina
se un comando o una verifica fallisce. Non ordinare i file generati.

I file `io-escape.*` descrivono prove dirette fallite, non il checkpoint.
La sequenza riuscita usa `reroute_pmic_io_escape.py`, `prepare_pmic_input_first.py`
e i passaggi `input`, `switch-reclosed`, `feedback-reclosed`, `second-output`,
`second-ground`, `local-complete`, `mount-local-trial`, `mount-bypasses`,
`mount-bypasses-ground`, `daughterboard-holes`, `io-bypass`, infine `layout-reviewed`.

Corretta anche la selezione dello strato dei pad SMD: `PAD.GetLayer()` può
restituire F.Cu per un pad presente soltanto su B.Cu. Ora il routing usa il
layer set effettivo. Tre test coprono fronte, retro e rifiuto di pad multistrato;
i controlli DRC avevano impedito di accettare le vecchie piste errate.

## Qualifica ancora necessaria

Il datasheet RK809-5 Rev.2.3, applicazione a pagina 11, usa 0.47 uH e 33 uF
nominali in uscita. C435/C445 sono due candidati da 22 uF: 44 uF nominali non
provano capacità effettiva, ESR o stabilità, specialmente con percorsi diversi.
Verificare derating, loop, ripple, transitori, correnti/via, temperatura e EMI.
Verificare anche alimentazione a monte, sequenza PMIC, distribuzione dei rail,
boot, resto del routing, SI/PI e raffreddamento passivo. Nessuna misura fisica
o simulazione elettrica è stata eseguita in questo passaggio.

## Serigrafia e metadati meccanici

Cinque riferimenti del gruppo C230x sono sul livello di assemblaggio, così non
intersecano i pad sulla serigrafia. U2 è etichettato dentro il bordo, rispettando
l'altezza minima del testo. Nessuna regola DRC è stata disabilitata: i 125
avvisi dei fanout incompleti restano. I due fori sono elementi solo PCB, esclusi
da distinta e file di posizionamento dei componenti. Il conteggio DRC non
include tutte le reti aperte: usare anche l'inventario di connettività.
