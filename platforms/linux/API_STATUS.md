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

## Speedtest (Linux, capability `speedtest`)

- GET /api/v1/speedtest: ultima misura in memoria, percorso, endpoint,
  download_mbps, download_mb, measurement_seconds, streams, engine, picco termico.
  upload_mbps e ping_ms sono null: non misurati. Si azzera al riavvio.
- POST /api/v1/speedtest con `{"action":"start"}` o `{"action":"cancel"}`:
  autenticazione e protezioni Host/Origin; un solo lavoro, cooldown 60 secondi,
  quattro trasferimenti HTTPS nativi curl di 10 secondi, limite totale 20 secondi,
  stop a 75 °C. Annullamento/errore terminano tutti i processi figli.
- Richiede curl, non speedtest-cli. Endpoint fisso speedtest3.serverius.net,
  nessun proxy, redirect, retry o configurazione .curlrc. Verifica TLS attiva.
  Risposte diverse da HTTP 200, errori o stream vuoti invalidano il risultato.
  Timeout al termine dei 10 secondi è previsto e conteggia i byte ricevuti.
- VPN richiede handshake; diretto solo se già abilitato. `--interface if!NOME`
  impone il device senza fallback. Policy routing oif phwg0 usa tabella 17700;
  oif uplink selezionato usa 17710, regola 17691 rimossa allo shutdown.
  DNS iniziale usa il resolver OS. Nessuna modifica al routing del Mac.
- Cambi/rotazione serializzati; misura traffico originato dal gateway, non
  forwarding client. Include avvio/TLS e dipende da percorso/server: non è
  un massimo garantito. ESP32 non espone la capability; UI nascosta.

## USB Ethernet, 14 novembre 2026

Gadget ECM/NCM e DHCP implementati come provisioning target opt-in, senza nuova
API remota per configfs/VBUS. Le policy `ingress=usb` e il routing VPN esistenti
sono riutilizzati. Accesso web ancora HTTPS loopback/SSH. Nessuna prova fisica
USB/macOS o velocità dichiarata; vedere `deploy/USB_ETHERNET.md`.

## Login password HTTPS Linux (2026-11-15)

GET /api/v1/auth/status; POST /api/v1/auth/login {password},
/auth/password {current_password,new_password}, /auth/logout {}. POST richiede
Origin HTTPS esatto; cookie Secure/HttpOnly/Strict. Errori password: 401;
lockout: 429 con retry_after e Retry-After. Sessione iniziale limitata al cambio.
Token tecnico solo loopback; ESP32 conserva autenticazione Bearer preesistente.
Vedere deploy/USB_ADMIN.md.

## Hotspot Linux (2026-11-15)

Capability hotspot_configuration; GET/POST /api/v1/hotspot. POST enabled, ssid,
password (vuota conserva). Stato desiderato separato da active/radio_state;
password mai restituita. Gestione serializzata, rollback su errore e file
privato persistente. USB non riavviata per modifiche AP. ESP32 non espone
queste API: controlli nascosti per capability. Vedere deploy/HOTSPOT.md.

Status opzionale Linux temperature_c (massimo sensori interni, null se assente).
Speedtest: download_mbps e upload_mbps da server distinti; upload_error separato
per preservare un download valido in caso di upload indisponibile. Nessuna
misura ping, nessun fallback di percorso. Dati sintetici soltanto in upload.

## Import WireGuard esteso (Linux, capability `wireguard_import: "extended"`, 2026-11-19)

Divergenza dal parser ESP32 (`shared/phoenix_core/wg_profile.c`, invariato).
`POST /api/v1/vpn {"action":"wireguard","profile":TEXT}` accetta qualunque
profilo client wg/wg-quick fino a 8 KiB (limite dettato dai 16 KiB del corpo
JSON) con 1–16 sezioni `[Peer]`:

- nomi di sezione e chiave senza distinzione maiuscole/minuscole; BOM, CRLF e
  commenti `#`; `Address`, `DNS` e `AllowedIPs` ripetibili o separati da virgole;
- `Address`: primo IPv4 usato (senza prefisso = /32, /0 rifiutato); altri IPv4
  e tutti gli IPv6 ignorati; almeno un IPv4 obbligatorio;
- `DNS` facoltativo: fino a 3 IPv4 distribuiti via DHCP ad AP/USB; IPv6 e domini
  di ricerca ignorati; nessun IPv4 → 1.1.1.1 raggiunto attraverso il tunnel;
- `MTU` 1280–1500 (default 1380); `PersistentKeepalive` 0–65535 o `off`;
  `PresharedKey` applicata;
- `Endpoint` IPv4:porta o nome:porta (RFC 1123). Il nome viene risolto a ogni
  connessione/riconnessione con DoH autenticato verso 1.1.1.1 vincolato
  all'uplink scelto (come l'API NordVPN), mai con il resolver di sistema né
  passato a `wg`. Errore → stato `endpoint_resolution_failed`, traffico
  bloccato, ritentativi con il backoff esistente. Endpoint IPv6 rifiutato;
- `AllowedIPs`: reti IPv4 passate a `wg setconf` così come sono, IPv6 ignorate,
  almeno una rete IPv4. Se non coprono tutto IPv4 (tunnel parziale) Phoenix
  continua a instradare tutto il traffico dei client in `phwg0`: le
  destinazioni fuori da `AllowedIPs` vengono scartate, mai inviate in chiaro.
  Se un DNS distribuito ai client (compreso il ripiego 1.1.1.1) è fuori da
  tutte le `AllowedIPs`, il profilo è accettato con la nota
  `dns_outside_allowed_ips` (le richieste DNS verrebbero bloccate);
- più `[Peer]` (dal 2026-11-19): chiavi pubbliche distinte
  (`duplicate_peer`), ognuno con `Endpoint` e almeno un `AllowedIPs` IPv4.
  Peer con insiemi IPv4 di `AllowedIPs` identici formano un **gruppo di
  failover** (ordine del file): in `wg` c'è un solo membro per gruppo; se il
  membro in uso non ha un handshake recente (≤ 180 s) per 30 s dalla sua
  attivazione, il gruppo passa al successivo (`wg set peer … remove` +
  `wg addconf` da stdin, gli altri gruppi non vengono toccati, il nome
  dell'endpoint viene risolto di nuovo). Gruppi con reti diverse sono usati
  insieme come wg-quick (contenimento ammesso, es. 0.0.0.0/0 e 10.0.0.0/8);
  gruppi che condividono solo alcune reti identiche →
  `allowed_ips_partial_overlap`. Connesso = almeno un membro con handshake e,
  se un gruppo copre tutto IPv4 (uscita Internet), il suo membro in uso ha
  l'handshake. Quando tutti i membri del gruppo di uscita hanno fallito si
  applica la regola esistente: blocco e riconnessione completa con backoff.
  Gli altri gruppi continuano a ruotare; il loro traffico, finché non hanno
  handshake, viene scartato da WireGuard. Kill switch invariato;
- `ListenPort`, `FwMark`, `Table`, `SaveConfig`, `PreUp`, `PostUp`, `PreDown`,
  `PostDown` accettati ma **mai eseguiti o applicati**; altre chiavi sconosciute
  rifiutate.

Risposte: profilo rifiutato → 400 `{"error": CODICE}` con codice specifico
(`duplicate_peer`, `allowed_ips_partial_overlap`, `too_many_peers`,
`ipv6_endpoint_unsupported`,
`ipv4_address_required`, `ipv4_allowed_ips_required`, `invalid_endpoint`,
`invalid_key`, `invalid_dns`, `invalid_number`, `invalid_section`,
`unknown_or_duplicate_field`, `missing_profile_fields`, …) senza toccare il
tunnel attivo; accettato → 202 `{"accepted": true, "profile_notes": [...],
"profile_details": {...}}`. `GET /api/v1/vpn` riporta `profile_notes` e
`profile_details` del profilo salvato e, per i profili WireGuard personalizzati,
`peers`: per ogni peer in ordine di file `{group, public_key_fingerprint
(primi 8 caratteri della chiave pubblica), endpoint (come scritto),
address (IP risolto del membro in uso o null), allowed_ips, active,
latest_handshake_age_s, connected}`. `endpoint` resta quello del membro in
uso del gruppo di uscita (altrimenti del primo gruppo); lo storico registra
quell'endpoint. Note: `ignored_ipv6`, `ignored_hooks`, `dns_fallback`,
`dns_search_ignored`, `dns_truncated`, `split_allowed_ips`,
`extra_addresses`, `hostname_endpoint`, `dns_outside_allowed_ips`
(`profile_details.dns_outside_allowed_ips`: elenco dei server),
`multiple_peers` (`profile_details.multiple_peers`: `{peers, groups}`).
Nessuna nota o errore contiene chiavi. Profili accettati dal parser precedente
restano identici (test di parità). RPC interna: metodo `wireguard_check` (dry
run, nessuna scrittura).

