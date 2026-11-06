# API v1

Trasporto HTTP sulle interfacce locali abilitate (AP/USB), oppure bridge UART locale; token Bearer di 64 caratteri hex.
Non usare su una LAN condivisa/non fidata: TLS locale/pinning è ancora da implementare.
Il firewall blocca HTTP sull'uplink prima di NAT e consegna locale.
Nessuna CORS permissiva; POST mode accetta solo Origin locale o client senza Origin.
Le risposte API non contengono chiavi.

| Metodo/percorso | Richiesta | Risposta |
|---|---|---|
| GET / | — | Pannello pubblico, nessun segreto |
| GET /api/v1/status | Bearer | Uplink pronto (`uplink_ready`), USB configurata, VPN, contatori, heap, uptime |
| POST /api/v1/mode | `{"direct":true}` oppure false | 200; arresta VPN e cancella NAT/ARP |
| POST /api/v1/uplink | `{"uplink":"ethernet"}` oppure `"wifi"` | 200; VPN e inoltro bloccati; Wi-Fi deve essere inizializzato |
| GET /api/v1/wifi/scan | Bearer | Fino a 16 reti; 503 se AP attivo/errore |
| POST /api/v1/wifi | JSON descritto sotto, max 256 byte | 202 configurato; non prova connettività Internet |
| POST /api/v1/firmware | immagine firmata binaria, 4 KiB..6 MiB | 202 verificata, reboot; 400 rifiutata; 503 build non firmata |
| GET /api/v1/vpn | Bearer | Stato, paese, rotazione, countdown, account configurato; nessuna chiave |
| POST /api/v1/vpn | JSON action, descritto sotto | 202 accodato, 400 configurazione, 409 comando in corso |
| GET /api/v1/policy | Bearer | Regole, forwarding e revisione |
| POST /api/v1/policy | Policy completa con revisione attesa | 200 salvata, 409 conflitto, 400 validazione |

401 senza token valido, 403 per Origin non ammessa. Chiamate browser ammesse solo dalle origini locali autorizzate.
Lo stato `vpn_up` indica sessione crittografica valida, non accessibilità Internet.
`ethernet_link`/`wifi_link` descrivono link netif, i campi `_ip` la presenza
di IPv4; non provano accesso Internet. `ap_active` indica netif AP attiva.
`usb_mounted`/`usb_suspended` vengono dallo stack USB.
`usb_configured` significa interfaccia creata; non equivale a cavo connesso.

## Sottoinsieme WireGuard supportato

Un Interface e un Peer, PrivateKey/PublicKey base64, eventuale PresharedKey,
Address IPv4/CIDR, un DNS IPv4 obbligatorio, Endpoint IPv4 numerico:porta,
AllowedIPs esattamente 0.0.0.0/0, MTU 1280..1420 (default 1380),
PersistentKeepalive 0..65535 (default 0). Commenti # ammessi.
Duplicati, sezioni multiple, hostname, IPv6, liste, script PostUp/PostDown,
ListenPort e altre direttive sono rifiutati, mai ignorati silenziosamente.
Importazione persistente in NVS; nessuna chiave di esempio operativa nel repository.
Rinnovare DHCP sul client dopo un cambio DNS. Il cambio server interrompe sessioni.

## Comandi VPN e persistenza

`POST /api/v1/vpn` riceve JSON con `action`:

- `wireguard`: `profile` contiene il testo wg-quick supportato.
- `nordvpn`: `token` facoltativo se la chiave è già configurata, `country`
  codice ISO oppure stringa vuota, `rotation` booleano, `interval` 30–86400.
- `connect`, `disconnect`, `direct`, `forget`, `rotate`, `catalog_test`, `verify_exit`.

202 indica accettazione, non successo della connessione: consultare GET vpn.
Il controllo IP usa solo il tunnel e non effettua fallback sull'uplink.
`next_rotation_seconds` è zero quando il timer non è attivo; controllare anche
`rotation`, `enabled` e `state`. Il timer parte dal tunnel connesso.

NVS conserva profilo VPN, chiave NordVPN, modalità diretta e preferenze di
rotazione. Il token NordVPN viene scartato dopo lo scambio HTTPS. Namespace
`phoenix` conserva hash del token admin e policy; `vpn_manager` il profilo.
Il pairing fisico può sostituire il token amministrativo. Flash encryption
non è abilitata nella build di sviluppo.

## Policy firewall

Fino a 20 regole ordinate e 8 inoltri porte. GET restituisce il formato completo
usato da POST; `revision` evita sovrascritture concorrenti. Le regole locali
obbligatorie di amministrazione restano attive. Le mappature hanno protocollo,
porta esterna/interna, destinazione AP/USB, CIDR sorgente e modalità VPN/diretta.
Le porte riservate e le mappature ambigue sono rifiutate. `active` distingue
una mappatura installata da una soltanto configurata. Le risposte ai forwarding
restano soggette alle regole firewall di uscita.

## Wi-Fi e selezione uplink

`{"mode":"sta","ssid":"...","password":"...","save":true}` configura WPA2
(minimo), con al massimo cinque tentativi di riconnessione per ciclo di connessione.
`{"mode":"sta","saved":true}` carica le credenziali salvate. Non connette automaticamente
al boot. La password è richiesta con getpass dal client, mai sulla riga di comando.
Le credenziali salvate sono **in chiaro in NVS**, perché flash encryption non è attiva:
usare save solo accettando questo limite del banco di sviluppo.

`{"mode":"ap","ssid":"...","password":"..."}` configura un hotspot NAT
192.168.9.1/24, WPA2, canale 6, massimo un client. Il limite evita di promettere
isolamento L2 multi-client non verificato. STA+AP simultanei e persistenza AP
non implementati. La scansione non interrompe un AP attivo: restituisce errore.

Ogni configurazione Wi-Fi e cambio uplink chiude VPN/NAT e blocca inoltro.
Selezionare esplicitamente l'uplink, poi importare VPN oppure richiedere direct.
L’amministrazione è disponibile su AP e USB LAN se abilitate, oltre al bridge UART.
DNS DHCP viene aggiornato su USB/AP all'importazione VPN: rinnovare i lease.

## Aggiornamento

Il client `firmware <immagine>` invia il binario senza Origin. La build deve
richiedere firme software; la build ordinaria rifiuta l'endpoint con 503.
Il dispositivo scrive lo slot inattivo, verifica con ESP-IDF firma/integrità
contro la chiave dell'app in esecuzione e controlla project_name=phoenix.
Solo dopo seleziona lo slot e si riavvia. Timeout totale 120 secondi; ogni
fallimento lascia l'inoltro bloccato. Vedere [OTA](OTA.md) per limiti e prove.

## Storico VPN

`GET /api/v1/vpn/history?before=<id>` restituisce fino a 32 connessioni NordVPN
riuscite, in ordine inverso, limitate alle ultime 8 ore. `next_before=0` indica
fine pagina. Ogni voce contiene `id`, `connected_at` Unix, `country` e `server`.
`persistent` segnala lo stato del salvataggio. Journal dedicato da 128 KiB,
1344 record, CRC e recupero dopo scritture interrotte; nessuna credenziale.
La finestra di 8 ore è garantita alla cadenza minima automatica di 30 secondi;
un numero eccezionale di cambi manuali può saturare il limite di record.
La scadenza filtra l’accesso; i settori flash vengono cancellati al riutilizzo.

La UI mostra una sola voce VPN con sezioni NordVPN e VPN WireGuard. Il countdown
avanza localmente ogni secondo e si riallinea allo stato ogni 5 secondi; dopo
20 secondi senza aggiornamenti mostra dati non disponibili.
