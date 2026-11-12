# Installazione sul target — build di ingegneria

Non eseguire sul Mac. Identificare modello, kernel, interfacce e servizi di rete
prima di installare. [Immagine ROCK](../boards/rock4c-plus/README.md).

## Requisiti

Python 3.9+ (3.9 su ROCK b60, 3.11 nel banco Debian 12), systemd, iproute2, nftables, wireguard-tools, conntrack, curl,
ca-certificates, openssl, iw, hostapd, dnsmasq-base e NetworkManager.
Con OpenSSL 1.1.1 installare anche `python3-cryptography`: Ed25519 usa
la libreria di sistema, perché la CLI 1.1.1 non supporta `pkeyutl -rawin`.
Con OpenSSL 3 resta il backend CLI. Nessun fallback dopo una firma non valida.
Il kernel deve supportare WireGuard, nftables e policy routing. L'USB gadget
non viene creata automaticamente: la sua fattibilità è una verifica separata.

Le risorse possedute sono `inet phoenix`, `inet phoenix_stop`, `phwg0`, tabelle
routing 17700/17710, mark 0x5048, priorità 17690, 17700–17702, 17710–17711.
Devono essere riservate a Phoenix. Gateway dedicato: non un host Docker o router
con configurazione preesistente da sovrascrivere. Le transizioni puliscono
conntrack per 192.168.7.0/24 e 192.168.9.0/24.

## Prima installazione

1. Preparare target.json dal template, con modello esatto letto da
   `/proc/device-tree/model` senza NUL e nomi da `ip -j address`.
2. Creare un bundle allowlisted e trasferirlo con il checkout fidato via SSH.
3. Usare l'installatore descritto in [UPDATES.md](UPDATES.md). Rifiuta modello
   diverso e installazioni esistenti. Crea utente di servizio, token e certificato
   locale; non avvia servizi e non cambia la rete.
4. Dopo verifica delle assegnazioni: `sudo systemctl daemon-reload`, quindi
   `sudo systemctl enable --now phoenix.service`.

`phoenix.service` è il frontend HTTPS senza privilegi. Richiede
`phoenix-control.service`, worker root con capability ristrette e socket Unix
privato. Solo l'UID phoenix-web può inviare RPC. Il worker valida nuovamente
policy e comandi. Il frontend riceve token e materiale TLS con LoadCredential;
non accede direttamente al vault VPN o alla configurazione persistente.

Il worker ammette AF_PACKET, necessario per hostapd e DHCP; il frontend no.
dnsmasq DHCP-only usa `--no-daemon` sotto il worker: mantiene UID e capability
già imposti da systemd, senza richiedere CAP_SETUID/CAP_SETGID. Non è un
resolver DNS e non gestisce richieste TCP. Processi e arresto sono gestiti
da Phoenix. La modalità è documentata da dnsmasq come debug: non equiparare
questo deployment di ingegneria a una validazione di produzione.

I profili STA sono keyfile senza password, con SSID codificato come byte decimali;
non richiedono `nmcli --offline`. La password resta nel file privato temporaneo
passato con `passwd-file`, eliminato anche in caso di errore.

Dopo ogni avvio il traffico è bloccato, selezione Ethernet; il pannello deve
richiedere esplicitamente connessione VPN o uscita diretta. Credenziali salvate
non autorizzano un fallback automatico. Il vecchio HTTP monoprocesso resta
solo uno strumento locale di sviluppo, non l'unità installata.

## Accesso HTTPS

Dal Mac: `ssh -L 8443:127.0.0.1:8443 utente@IP_DELLA_ROCK`.
Aprire **https://127.0.0.1:8443**. Host/Origin devono corrispondere; non usare
una porta locale diversa. Token privato: /var/lib/phoenix/admin-token sul target.
Non inviarlo in chat o inserirlo negli argomenti della shell.

L'installatore genera un certificato self-signed specifico per il dispositivo,
con SAN 127.0.0.1/localhost, valido 365 giorni. Trasferire la sola parte pubblica
`/etc/phoenix/admin-cert.pem` via SSH autenticato, verificarne l'impronta e
configurarla come attendibile nel client. Non disabilitare la verifica TLS.
La chiave /etc/phoenix/admin-key.pem resta privata (0600). Prima della scadenza,
rinnovare il certificato mantenendo i SAN, distribuirne la fiducia e riavviare
il frontend. Il health check dell'updater usa il certificato locale come trust
anchor; non accetta certificati arbitrari. Nessuna modifica automatica al
portachiavi del Mac. Per esposizione diretta su LAN/AP serve un deployment
separato con nomi/certificati e regole d'accesso appropriati: non abilitato qui.

## AP e STA opt-in

AP previsto 192.168.9.1/24, USB eventuale 192.168.7.1/24. Esempio target.json:

```json
"access_point": {
  "ssid": "Phoenix-Test",
  "password_file": "/etc/phoenix/ap-password",
  "country": "IT",
  "dns": "103.86.96.100"
},
"station_interface": "nome_radio_verificato"
```

Radio identificata con supporto AP, paese reale e password ASCII 8–63 caratteri
in file 0600 del servizio. Senza station_interface le azioni STA sono disabilitate.
AP richiede interfaccia non gestita da NetworkManager; se assegnata anche a STA,
Phoenix gestisce il passaggio solo dopo avere escluso connessioni altrui.

Su radio condivisa il passaggio a STA spegne l'AP; selezionare Ethernet lo
ripristina. Su radio separata AP resta attivo. Il profilo STA runtime è in
/run/NetworkManager/system-connections, autoconnect disabilitato, IPv6 disabilitato,
password temporanea privata senza segreti in argv; la copia salvata è nel vault.
All'avvio si recupera soltanto un profilo Phoenix rimasto attivo dopo un crash.

Il routing client/tunnel è dedicato. DNS per le API usa DoH autenticato a
1.1.1.1; DoH e TLS api.nordvpn.com sono vincolati all'uplink scelto, con fwmark
quando attiva la tabella dedicata. Nessun uso di resolv.conf, proxy d'ambiente,
redirect o altra interfaccia come fallback. Se bootstrap DNS o API falliscono,
il tunnel rimane bloccato e il gestore riprova rispettando il paese scelto.
Serve orologio corretto per TLS. I normali servizi del sistema operativo
continuano a usare la loro configurazione di rete: Phoenix non cambia la
route principale di SSH, aggiornamenti OS o sincronizzazione oraria.

DHCP distribuisce il DNS del profilo; dopo un cambio rinnovare i lease client.
I processi AP/DHCP sono dedicati; rollback rimuove soltanto risorse proprie.
SIGTERM e ExecStopPost bloccano l'inoltro; la ripartenza ripulisce le route
possedute e rimuove lo stop guard solo dopo aver installato la nuova barriera.

## Fonti tecniche

- [NetworkManager nmcli](https://manpages.debian.org/bookworm/network-manager/nmcli.1.en.html)
- [Credenziali systemd](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec)
- [Cloudflare DoH JSON](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/)
