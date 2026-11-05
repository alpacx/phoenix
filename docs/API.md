# API v1

Trasporto attuale HTTP sulla sola LAN USB; token Bearer di 64 caratteri hex.
Non usare su una LAN condivisa/non fidata: TLS locale/pinning è ancora da implementare.
Il firewall blocca HTTP sull'uplink prima di NAT e consegna locale.
Nessuna CORS permissiva; POST mode accetta solo Origin locale o client senza Origin.
Le risposte API non contengono chiavi.

| Metodo/percorso | Richiesta | Risposta |
|---|---|---|
| GET / | — | Pannello pubblico, nessun segreto |
| GET /api/v1/status | Bearer | Stato Ethernet, USB configurata, VPN, contatori, heap, uptime |
| POST /api/v1/mode | `{"direct":true}` oppure false | 200; arresta VPN e cancella NAT/ARP |
| POST /api/v1/vpn | testo wg-quick, max 4096 byte | 202 connecting, 400 formato, 409 avvio fallito e blocco attivo |

401 senza token valido, 403 per Origin non ammessa. VPN importabile dal client
locale; chiamate browser con Origin sono rifiutate per questo endpoint.
Lo stato `vpn_up` indica sessione crittografica valida, non accessibilità Internet.
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
