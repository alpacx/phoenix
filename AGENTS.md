# Istruzioni per agenti — Phoenix

Leggere README.md e docs/PROJECT_STRUCTURE.md, poi il README della piattaforma
interessata. NEXT_SESSION.md/PROGRESS.md contengono contesto storico: non
assumere ancora validi IP, seriali, credenziali o dispositivi collegati.

## Confini del lavoro

- Mantenere ESP32 funzionante mentre si sviluppa Linux. Non sostituire un backend
  con l'altro né usare codice ESP-IDF nei servizi Linux.
- UI unica in shared/web; C portabile in shared/phoenix_core.
- ESP32 in platforms/esp32/main; Linux in platforms/linux.
- Conservare i comandi di build dalla root e aggiornare tutti i riferimenti
  quando si spostano file. Non modificare SDK globali o managed_components.
- Documentare divergenze API; non presentare scaffold o mock come funzioni operative.
- Per il software non modificare il CAD. Per il CAD consultare il checkpoint
  corrente; non dichiarare produzione pronta in base a ERC/DRC soltanto.

## Validazione e sicurezza operativa

Eseguire i test pertinenti elencati in docs/PROJECT_STRUCTURE.md. Le modifiche
al cablaggio CMake richiedono anche build ESP-IDF. Non flashare per un refactor
organizzativo. Identificare il target prima di modificare rete, storage o firmware.
Non applicare nftables/routing al computer host. Non stampare o committare token,
chiavi, backup flash o file privati in results/. Non modificare eFuse.

Procedere autonomamente nelle attività autorizzate e reversibili; chiedere
informazioni soltanto se indispensabili. Non acquistare o ordinare componenti.
Riportare cosa è stato verificato e quali limiti rimangono; non confondere
stime di performance con misure. Commit/push solo quando richiesti.
