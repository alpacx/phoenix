# Ripresa sequenziale — 18 novembre 2026

Nessun subagente avviato. Si mantiene RK3562 e la BOM attuale; niente migrazione Wi-Fi o RAM. Nessun commit/push.

## Modifiche

- Via C1650: da (23.8,20.5) a (23.3,20.6) mm.
- Via C1664: da (23.3,17) a (23.15,17) mm.
- Conservati UUID e piste da 0.30 mm, via 0.60/0.30 mm.
- Integrati C1626, C1643, C1637 e C1602 da studio precedente.
- C1627: via spostato da (49.3,28) a (50.65,29.75) mm; evita C2204 e EXP_SPI_MOSI su In3.Cu. DRC isolato e screen pad superati.
- Integrazione usa right-ground-safe-delta.json. La delta originale resta riferimento storico; generatori aggiornati.
- Controllo geometrico dei nuovi via contro tutti i pad su F/B con margine conservativo >0.05 mm aggiunto a parallel_local_copper_checks.py. Include pad della stessa net.
- Test negativo aggiunto: sovrapposizione a pad GND, altrimenti invisibile al normale controllo di cortocircuito.

## Tentativi esclusi

C1650 (24.55,19.0) e (23.65,21.2) introducono conflitti; C1664 (23.0,17) respinto nello studio iniziale. C1627 (50.25,29.75), (50.4,29.5), (50.4,29.2) confliggono con EXP_SPI_MOSI. Non ripetere senza cambiare geometria.

Lo screen globale rispetto al vecchio baseline segnala anche via preesistenti presso U21.19 e C521.2: non sono stati introdotti in questa ripresa e non vengono qualificati come privi di via-in-pad. Serve revisione assemblaggio separata. Il controllo integrato limita la sua attestazione alle delte aggiunte.

La ricostruzione transazionale completa è il gate finale: leggere working-candidate.json e final-audit.json, non inferire l’accettazione dal solo studio. Nessuna qualifica PI/SI o produzione.

Esito finale: ricostruzione 24 stadi PASS; 246 coppie; 67+7 test PASS; 30 nuovi via con margine >0.05 mm PASS. SHA c29d07e1eca29d367b1194504bc58288253b281572404bd8820ac6b030a12824.
