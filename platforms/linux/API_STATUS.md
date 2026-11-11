# Stato API Linux rispetto a ESP32

| Endpoint | Stato |
|---|---|
| GET / e asset | UI condivisa, HTTPS loopback nel deployment separato |
| GET status | Dati kernel reali solo con runtime inizializzato; altrimenti 503 |
| GET/POST policy | Validazione, revisione, persistenza, compilazione/applicazione nft |
| GET vpn | Stato e countdown; nessuna chiave |
| POST vpn | Comandi asincroni (202), un comando alla volta |
| GET vpn/history | SQLite, ultime 8 ore, paginazione |
| GET capabilities | Funzioni disponibili esplicite |
| GET preflight | Inventario read-only |
| POST uplink, wifi | 202 asincrono, solo con configurazione target esplicita; rete bloccata in transizione |
| GET wifi/scan | NetworkManager, percentuale segnale; non dBm inventati; rifiutato sulla radio AP attiva |
| GET/POST firmware | Stato e upload binario .phx firmato, solo con chiave fidata provisionata |
| GET healthz | Readiness e identità release, loopback senza token; usato per rollback |

Azioni VPN: wireguard, nordvpn, connect, disconnect, direct, forget, rotate,
catalog_test, verify_exit. Verifica IP vincolata a phwg0, senza proxy ambiente
o fallback in chiaro. NordVPN API/account NON provati con un abbonamento Linux.

Divergenze: default post-reboot bloccato anche con credenziali salvate;
ritentativi automatici con backoff 5–60 secondi, senza fallback geografico. Contatori riferiti al ruleset
corrente e azzerati quando viene sostituito. `heap_free` riporta MemAvailable
Linux per compatibilità UI, non heap embedded. `malformed_counter_available`
è false; UI mostra Non disponibile. Stato link AP non prova associazione client.
Il supporto USB non è dedotto dalla sola presenza del controller.

Autenticazione Bearer 64 hex; Host e Origin limitati all’endpoint HTTPS loopback.
Frontend UID phoenix-web; RPC Unix con SO_PEERCRED e operazioni allowlisted.
La CLI di sviluppo conserva HTTP loopback, senza abilitare il deployment di rete.
Errore 503 senza runtime, 501 per POST non implementati, 404 per GET sconosciuti.
Gli errori non includono stdout/stderr dei comandi o payload delle richieste.

L'hotspot è ora configurabile al bootstrap con access_point in target.json.
POST wifi/STA usa l’adattatore NetworkManager opt-in; non prova il funzionamento della radio fisica. Richieste VPN malformate sono rifiutate prima di
mutare la rete; un errore diagnostico non interrompe il tunnel esistente.

Gli aggiornamenti riguardano solo l’applicazione, non OS/bootloader: deploy/UPDATES.md.
DNS e API NordVPN sono ora vincolati all’uplink scelto, senza dipendenza da Ethernet.
I servizi OS restano separati: vedere deploy/README.md.
