# Prima verifica fisica — 2026-11-12

## Stato aggiornato: installato e verificato sul banco

Phoenix 0.1.0-rock1 è installato, con aggiornamento firmato sequenza 1
attivato tramite API HTTPS. Entrambi i servizi sono attivi dopo un riavvio
fisico del sistema, senza riavvii automatici per errore. Frontend come
phoenix-web, worker privilegiato, firewall inizialmente bloccato.

Correzioni applicate:
- Ed25519 su OpenSSL 1.1.1 usa python3-cryptography 3.3.2; backend CLI
  conservato su OpenSSL 3. Test di equivalenza firme e rifiuto alterazioni.
- Keyring Radxa ufficiale 0.2.2; backports obsoleto disabilitato; repository
  security Bullseye spostato ad archive.debian.org. apt update termina senza
  errori, senza disabilitare GPG o validità degli indici. Backup /root/phoenix-apt-before.
- AF_PACKET aggiunto alla sandbox del solo worker con approvazione esplicita
  dell'utente. Serve per hostapd e DHCP. Capability non ampliate.
- dnsmasq DHCP-only eseguito con --no-daemon per evitare setgroups non
  autorizzato dalla sandbox; pannello rimasto non root.
- Profili STA generati come keyfile, senza nmcli --offline assente in NM 1.30.
  Parser NetworkManager reale verificato anche con SSID UTF-8 e caratteri
  speciali; profilo di test mai attivato e poi rimosso.

Prove completate:
- 69 test Python superati direttamente sulla ROCK; 8 test aggiornamenti
  superati sul Mac con OpenSSL 3, inclusa interoperabilità del backend legacy.
- HTTPS /healthz e API autenticate; verifica TLS anche dal Mac attraverso SSH.
- AP Phoenix-Test attivo su wlan0; DHCP 192.168.9.20–200, porta 67 vincolata
  alla radio. Nessun telefono ancora associato in questa sessione.
- Client virtuale veth/namespace sulla ROCK: blocco iniziale, HTTP Internet
  attraverso Ethernet in modalità diretta, blocco dopo disconnect. Risorse
  temporanee rimosse e policy ripristinata. Non è una prova USB fisica.
- Upload, verifica Ed25519 e attivazione reale della release firmata; reboot
  conserva la release e riavvia AP/DHCP/pannello in modalità bloccata.
- Temperature osservate 49–54 °C per attività leggere. Nessuno stress test.

Accesso: HTTPS loopback 8443 via tunnel SSH. Certificato pubblico disponibile
sul target /etc/phoenix/admin-cert.pem; token /var/lib/phoenix/admin-token;
password AP /etc/phoenix/ap-password. Non pubblicare i due segreti. La chiave
di firma usata è di banco e privata sul Mac, non una chiave di produzione.
Non è stata aggiunta alcuna nuova chiave SSH; credenziali esistenti invariate.

Limiti: Debian 11 b60 è una base diagnostica con pacchetti archiviati, non
una base di produzione aggiornata. USB gadget, associazione client fisico,
VPN con account reale, throughput e validazione termica restano separati.
Nessuna connessione NordVPN configurata senza credenziali dell'utente.

## Evidenza iniziale, precedente alle correzioni

Target identificato via device tree: Radxa ROCK 4C+. Accesso SSH riuscito
sull'immagine diagnostica ufficiale b60, Debian 11, kernel 5.10.110-20-rockchip.
Non confondere questa immagine con Debian 12 utilizzata nei test VM/container.

- microSD espansa: root circa 29 GB, 26 GB liberi; RAM totale circa 3,8 GiB.
- Python 3.9.2: 61 test eseguiti con successo; suite complessiva fallita perché
  setUpClass di UpdateTests non riesce a firmare con OpenSSL 1.1.1n.
  I test di quella classe non sono stati eseguiti. Nessuna certificazione
  generale di compatibilità Python 3.9.
- systemd 247: verifica sintattica delle unità senza diagnostica; servizi
  Phoenix non installati né avviati.
- Installati da repository Debian autenticati: nftables, libnftables1,
  conntrack, wireguard-tools. iw era già presente in /usr/sbin.
- Creazione interfaccia WireGuard riuscita in un namespace temporaneo,
  poi rimosso. Non è una prova di handshake o throughput.
- Driver Wi-Fi dichiara modalità AP e managed; radio non ancora provata
  con client. Nessun controller USB device esposto in /sys/class/udc.
- Nessuna tabella nftables preesistente; servizio nftables inattivo dopo
  installazione. Rete Ethernet e routing principale non modificati.
- Temperature osservate circa 49–52 °C durante attività leggere senza
  dissipatore. Nessuna prova termica sotto carico.

## Incompatibilità da risolvere prima del deployment completo

L'immagine b60 include OpenSSL 1.1.1: il percorso Ed25519 pkeyutl -rawin
del gestore aggiornamenti non funziona. Non aggirare la verifica delle firme.
Scegliere e validare un runtime supportato prima di abilitare gli aggiornamenti.

apt-get update scarica correttamente gli indici Debian, ma termina con errore:
bullseye-backports non esiste più al vecchio URL e i repository Radxa richiedono
chiavi non presenti (67A474DD40402951, 5D93177D0752732A). Nessuna verifica GPG
disabilitata, nessun cambio di distribuzione o aggiornamento del kernel eseguito.

Restano da verificare installazione/avvio reale Phoenix, TLS e accesso al pannello,
AP/DHCP, traffico firewall/VPN, USB gadget e prestazioni. Le credenziali di fabbrica
SSH sono ancora attive: predisporre accesso alternativo verificato prima di
ruotarle, senza pubblicare segreti. IP da riscoprire a ogni cambio di rete.

## Preparazione USB — 2026-11-12

Ethernet ristabilita e target identificato. Attivato overlay ufficiale già
presente `rk3399-dwc3-0-peripheral.dtbo`, tramite copia del relativo `.disabled`
in /boot/dtbo e u-boot-update. Backup configurazione precedente:
/root/phoenix-extlinux-before-usb.conf. Dopo reboot: UDC fe800000.usb presente,
dr_mode peripheral, servizi Phoenix attivi. Il tentativo runtime debugfs
`device` non aveva cambiato host: necessario l'overlay di boot.

Correzione dell'inventario iniziale: CONFIG_USB_CONFIGFS_ECM non selezionato,
ma usb_f_ecm e u_ether sono moduli già installati con alias usbfunc:ecm.
Il pacchetto Radxa preesistente crea automaticamente radxa-otgutils con
ECM e ADB, UDC associato, usb0 DOWN senza indirizzo. Configurazione Radxa
attuale dichiara bcdUSB 0x0200; non dichiarare SuperSpeed o rete pronta.
Non sono stati aggiunti DHCP USB né integrazione del ciclo di vita gadget.

BLOCCO COLLEGAMENTO FISICO: vbus_typec risulta abilitato, gpio-35
(vbus-typec) output high anche in peripheral. Lo schema ufficiale V1.411,
pagina 23, mostra U8507 SY6280AAC fra VCC5V0_SYS e VBUS_TYPEC della porta
OTG, controllato da VCC5V0_TYPEC0_EN. Il device tree mantiene il regolatore
always-on. Nessuna disattivazione VBUS ancora applicata né tensione misurata.
L'utente ha un cavo USB-C maschio / USB-A maschio: non è stato autorizzato
il collegamento fisico. Verificare VBUS e adeguatezza del cavo prima della
prova Mac; non presumere che cambiare dr_mode disattivi i 5 V. Nessuna prova
fisica USB completata. Dopo reboot la VPN riparte bloccata come previsto.

Fonte schema: https://dl.radxa.com/rockpi4/docs/hw/rockpi4/ROCK-4C%2B-V1.411-SCH.pdf
Per annullare l'overlay, rimuovere soltanto la copia attiva aggiunta,
eseguire u-boot-update e riavviare; conservare il file originale .disabled.

## Speedtest nel pannello — 2026-11-12

Implementato in Rete, capability Linux, risultati/annullamento e limiti di tempo
ed energia termica. 73 test Python passati sulla ROCK. Browser Chromium reale:
avvio, annullamento, risultati e layout desktop/mobile verificati con fixture;
nessun errore JavaScript o overflow orizzontale. Fixture non è una misura di rete.
Nuova rete rilevata: IPv4 192.168.1.28 (temporaneo, riscoprire sempre).

## Benchmark nativo remoto e VPN Italia — 2026-11-12

Endpoint scelto: https://speedtest3.serverius.net/ (il gestore dichiara 10GE).
Test HTTPS: quattro processi curl nativi, IPv4, --interface eth0 oppure phwg0,
--noproxy '*', file /files/1000mb.bin, output /dev/null, limite 10 secondi.
Mbps calcolati dai byte effettivamente ricevuti / tempo totale del supervisore;
include avvio/TLS, non è throughput a regime. Exit curl 28 previsto per limite
volontario, HTTP 200 verificato per ogni flusso. Python orchestra e raccoglie
contatori, non trasferisce i dati. Arresto termico a 75 °C.

- Diretto HTTPS DC1: 209,54 Mbps; DC3: 893,31 Mbps. Stesso provider non significa
  stessa prestazione: non assumere garantita banda disponibile dai 10GE nominali.
- Diretto iperf3 3.9, quattro stream, otto secondi: DC1 360,67 Mbps, DC3 390,52
  Mbps. Protocolli/porte e momenti diversi: non attribuire differenze alla sola CPU.
- VPN configurazione iniziale casuale, Bahrain #3: 273,04 Mbps HTTPS DC3.
- Su richiesta impostato paese fisso IT, conservate esclusioni/intervallo e
  rotazione disattivata. Italy #453: 314,40 e 325,93 Mbps in due prove HTTPS DC3.
  Delta WireGuard RX 432.480.464 e 449.694.592 byte: traffico nel tunnel verificato.
- CPU complessiva occupata 53,7–56,7%; CPU0 94,7% medio in entrambe le prove IT.
  Possibile collo di bottiglia del processamento rete: non provato causalmente,
  non esclude limiti NordVPN/percorso. Picco termico 62,5 °C, poi 55,6 °C.
- Stato finale: VPN Italia connessa, modalità diretta spenta, entrambi i servizi
  attivi. Nessuna modifica a routing/firewall del Mac o tuning CPU della ROCK.

Evidenze locali: results/rock4c-plus/native-remote/*.json. Risultati HTTPS diretti
riportati dal supervisore in sessione; JSON persistiti per VPN e iperf.
Il pannello usa ancora sivel/speedtest-cli Python: questi test NON ne certificano
accuratezza né hanno sostituito quel backend. Il risultato mostrato nel pannello
resta la precedente misura. Nessuna prova upload VPN o forwarding client qui.
893 Mbps dimostrano capacità del percorso diretto con il client nativo; 326 Mbps
sono una misura VPN di banco, non il massimo assoluto garantito della ROCK.
Fonti: https://speedtest3.serverius.net/ ; https://github.com/sivel/speedtest-cli#inconsistency ;
https://software.es.net/iperf/faq.html .

## Pannello con benchmark curl nativo — 2026-11-12

Distribuita release firmata 0.1.0-rock3, sequenza 3, ID 3-a1d0ac24fe38d8ba.
Sostituito speedtest-cli con quattro processi curl nativi sul medesimo endpoint
HTTPS DC3, device obbligatorio `if!`, niente proxy/redirect/.curlrc/retry.
UI mostra download, MB ricevuti e durata; upload/ping null, non misurati.
Regola oif 17691 per uplink selezionato aggiunta al lifecycle routing e cleanup;
VPN usa la preesistente regola oif phwg0. Test del routing generato passato;
uplink Wi-Fi fisico non riprovato in questa modifica.

74 test Python passati sulla ROCK; suite locale Mac non è prova Linux (socket
bloccati dalla sandbox e SO_MARK non disponibile). Chromium desktop/mobile:
avvio, annullamento, metriche e assenza overflow/JS errors verificati su fixture.
Annullamento di tutti i figli e validazione HTTP/timeout coperti dai test.

Prova API reale dopo deployment, VPN Italy #534 con paese IT fisso:
322,31 Mbps, 410,3 MB, 10,19 secondi, picco 59,4 °C. WireGuard RX incrementato
442.880.048 byte. Stato finale connesso. Il primo stato pre-update era error;
riconnessione esplicita della configurazione Italia eseguita e verificata.
Nessuna misura upload introdotta; prova non certifica throughput forwarding.
