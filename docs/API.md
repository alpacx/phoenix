# API v1

Trasporto attuale HTTP sulla sola LAN USB; token Bearer di 64 caratteri hex.
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
| POST /api/v1/vpn | testo wg-quick, max 4096 byte | 202 connecting, 400 formato, 409 avvio fallito e blocco attivo |

401 senza token valido, 403 per Origin non ammessa. VPN importabile dal client
locale; chiamate browser con Origin sono rifiutate per questo endpoint.
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
Importazione solo in RAM; nessuna chiave di esempio operativa nel repository.
Rinnovare DHCP sul client dopo un cambio DNS. Il cambio server interrompe sessioni.

[NordVPN ufficiale](https://nordvpn.com/blog/nordvpn-config-files/) documenta
il download di configurazioni WireGuard manuali dall'account. Non sono state
fornite credenziali/profili: interoperabilità non provata; nessuna promessa
NordLynx o delle protezioni proprietarie. Un file con direttive fuori dal
sottoinsieme viene rifiutato anche se valido per wg-quick.

## Persistenza

NVS namespace phoenix, schema versione 1, hash token `admin`. Versioni sconosciute
non vengono interpretate e NVS non viene cancellata automaticamente. Pairing
fisico via UART può sostituire il token. Mode direct non persiste: reboot chiuso.
Migrazioni per schemi successivi, salvataggio profili VPN e reset autenticato
sono attività aperte, non endpoint simulati.

## Wi-Fi e selezione uplink

`{"mode":"sta","ssid":"...","password":"...","save":true}` configura WPA2
(minimo), con al massimo cinque tentativi di riconnessione per ciclo di connessione.
`{"mode":"sta","saved":true}` carica le credenziali salvate. Non connette automaticamente
al boot. La password è richiesta con getpass dal client, mai sulla riga di comando.
Le credenziali salvate sono **in chiaro in NVS**, perché flash encryption non è attiva:
usare save solo accettando questo limite del banco di sviluppo.

`{"mode":"ap","ssid":"...","password":"..."}` configura un hotspot NAT
192.168.8.1/24, WPA2, canale 6, massimo un client. Il limite evita di promettere
isolamento L2 multi-client non verificato. STA+AP simultanei e persistenza AP
non implementati. La scansione non interrompe un AP attivo: restituisce errore.

Ogni configurazione Wi-Fi e cambio uplink chiude VPN/NAT e blocca inoltro.
Selezionare esplicitamente l'uplink, poi importare VPN oppure richiedere direct.
L'amministrazione resta disponibile solo sulla USB LAN, non sull'hotspot.
DNS DHCP viene aggiornato su USB/AP all'importazione VPN: rinnovare i lease.

## Aggiornamento

Il client `firmware <immagine>` invia il binario senza Origin. La build deve
richiedere firme software; la build ordinaria rifiuta l'endpoint con 503.
Il dispositivo scrive lo slot inattivo, verifica con ESP-IDF firma/integrità
contro la chiave dell'app in esecuzione e controlla project_name=phoenix.
Solo dopo seleziona lo slot e si riavvia. Timeout totale 120 secondi; ogni
fallimento lascia l'inoltro bloccato. Vedere [OTA](OTA.md) per limiti e prove.
