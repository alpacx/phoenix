# Prima verifica fisica — 2026-11-12

## Ripresa USB — 2026-11-15

Target nuovamente identificato via SSH: ROCK 4C+, kernel 5.10.110-20-rockchip,
release applicativa 3-a1d0ac24fe38d8ba. Phoenix e phoenix-control attivi.
Indirizzi osservati (non assumerli stabili): Ethernet 192.168.8.171 e link-local
fe80::1310:6c3c:3ddd:d8e8. Cavo dati scollegato dall'utente prima delle verifiche.

UDC fe800000.usb: not attached, maximum_speed super-speed. Quest'ultimo è una
capacità dichiarata, non una velocità negoziata o misurata. Modulo usb_f_ecm
presente; usb_f_ncm assente. Gadget radxa-otgutils già associato, gestito da
radxa-adbd.service. Non è stato sostituito né arrestato.

GPIO35 vbus-typec ancora output high; regolatore vbus_typec abilitato.
Il device tree attivo contiene regulator-always-on e regulator-boot-on.
Preparato usb-vbus-off.dts: disabilita il nodo del regolatore e riserva GPIO1_A3
come output-low tramite gpio-hog. Compilazione dtc e applicazione fdtoverlay
a una COPIA del device tree attivo riuscite sulla ROCK; fdtget conferma status
disabled e gpio-hog output-low su pin 3 del controller gpio1.

Il candidato è soltanto in /tmp sulla ROCK: NON installato in /boot, NON
applicato al kernel, nessun reboot. Non cambia bootloader, tensioni o servizi.
Il datasheet Silergy conferma reverse blocking in shutdown, ma ciò non prova
lo stato elettrico della scheda reale. Prima del cavo Mac servono verifica
elettrica e gestione del rischio VBUS anche durante avvio/reboot; il solo
gpio-hog Linux non garantisce quest'ultima. Non impostare vbus_verified=true
sulla base di questa compilazione. Nessuna enumerazione, DHCP o velocità USB
fisica verificata. Configurazione VPN e firewall invariata.

Fonte componente: https://www.silergy.com/download/downloadFile?ftype=note&id=4369&type=product

### Aggiornamento successivo: overlay applicato e reboot verificato

Su richiesta di proseguire, validato anche il DTB originale di boot insieme
all'overlay periferica Radxa. Installato /boot/dtbo/phoenix-usb-vbus-off.dtbo
e rigenerato extlinux con u-boot-update. Backup di extlinux.conf e
/etc/default/u-boot in /root/phoenix-usb-backup-20261115/. Riavvio riuscito,
accesso SSH IPv4 192.168.8.171 e servizi phoenix/phoenix-control attivi.
GPIO35 ora `phoenix-usb-source-o`, output LOW; nodo vbus-typec disabled,
regolatore vbus_typec assente dal riepilogo attivo. VBUS host delle altre porte
rimane attivo. UDC not attached: nessun cavo dati/test di enumerazione.

Queste osservazioni superano lo stato "non installato" descritto sopra,
ma non costituiscono una misura della tensione al connettore. Non verificata
la fase bootloader. Un dispositivo che non si carica NON prova VBUS assente.
Non impostato vbus_verified. Per rollback, a cavo dati scollegato, rimuovere
soltanto /boot/dtbo/phoenix-usb-vbus-off.dtbo, eseguire u-boot-update e riavviare:
questo RIPRISTINA la sorgente 5 V, non è una procedura di sicurezza USB.

Suite USB eseguita sul Python 3.9 della ROCK in /tmp/phoenix-usb-validation:
11 test passati dopo aver completato le fixture importate (test_lan,
test_runtime, test_policy, test_vpn). Sono test simulati di configfs/DHCP e
controller, non scambi USB fisici. Inspect conferma configfs disponibile,
gadget Radxa associato, current_speed UNKNOWN, electrical_safety_verified false.
Release attiva non sostituita; nessuna modifica a credenziali o policy.

### Tentativo con cavo diretto USB-C maschio / USB-A maschio

Utente riferisce alimentatore separato e cavo dati inserito nella porta OTG.
Target riscoperto su 192.168.8.171, GPIO35 sempre output LOW, Phoenix attivo.
UDC resta not attached, current_speed UNKNOWN; nessun dispositivo Radxa nel
bus IOUSB del Mac e nessuna nuova interfaccia di rete osservata. Gadget ancora
radxa-otgutils. Non è una prova di guasto né di tensione zero.

Individuato un limite del cablaggio precedentemente trascurato: un cavo legacy
standard A maschio / C maschio usa Rp sul CC e prevede la sorgente/host lato A;
non equivale a un adattatore C host / A femmina con Rd. La disposizione attuale
è quindi incompatibile con il ruolo host richiesto al Mac per un cavo conforme.
Non riabilitare VBUS per tentare di farlo rilevare. Richiesto scollegamento
del cavo diretto e inventario di eventuale hub/adattatore host disponibile.
Un eventuale collegamento A-A richiede ulteriore verifica del cablaggio OTG
specifico e VBUS; non è autorizzato implicitamente da questo inventario.
Fonte: https://chromium.googlesource.com/playground/chromium-org-site/+/refs/heads/main/chromium-os/cable-and-adapter-tips-and-tricks/index.md

### Enumerazione fisica con A–A tramite hub — 15 novembre 2026

Utente collega un cavo A–A reperito, modello/cablaggio non documentati.
Mac IOUSB mostra USB2.0 Hub e OTG Utils; NetworkSetup espone OTG Utils su en10.
Separatamente l'hub espone USB 10/100 LAN su en7: non confondere le interfacce.
ROCK identificata via SSH a 192.168.8.171: UDC configured, current_speed
high-speed, GPIO35 phoenix-usb-source-o output LOW; servizi Phoenix attivi.
È la prima enumerazione USB fisica confermata in questa sessione.

usb0 sulla ROCK resta DOWN, en10 sul Mac inactive, nessuna lease DHCP.
Gadget ancora radxa-otgutils; release/applicazione non modificate in questa
verifica. Nessun trasferimento IP, navigazione, VPN o throughput USB provati.
High-speed significa link USB 2.0 (480 Mbit/s nominali), non velocità applicativa
misurata; l'hub osservato è USB2.0, non prova un limite intrinseco della ROCK.
Il riscontro GPIO non è una misura elettrica né una verifica del bootloader.
Nessuna modifica al routing/firewall del Mac; evitare reboot con dati inseriti.

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


## 2026-11-15 — Phoenix USB: prova fisica completata sul banco

Release firmata `5-ebf8d0b5e08827d9` (`0.1.0-rock5-usb`); suite Linux sul
 target: 91 test passati. CDC-ECM, UDC `fe800000.usb` configured/high-speed,
 `phusb0` 192.168.7.1; Mac `en14` Phoenix USB Ethernet con DHCP 192.168.7.137,
 router 192.168.7.1 e DNS 103.86.96.100. Hub USB 2.0, alimentazione separata.

- Curl vincolato a en14: example.com HTTPS 200 e IP pubblico 187.13.216.248,
  uguale alla richiesta ROCK vincolata a phwg0 (NordVPN Italy #510).
- Disconnessione VPN con riconnessione systemd programmata dopo 15 secondi:
  richiesta USB con IP destinazione fissato, senza dipendenza DNS, bloccata
  (curl exit 28, HTTP 000). Dopo riconnessione, IP 187.13.213.223 identico
  su Mac/en14 e ROCK/phwg0. Nessun fallback diretto configurato.
- iperf3 locale, quattro flussi, sei secondi, indirizzi USB espliciti:
  Mac→ROCK 279.06 Mbps ricevuti (298.98 inviati);
  ROCK→Mac 309.41 Mbps ricevuti (312.97 inviati).
  Sono misure brevi del percorso USB locale, NON throughput Internet/VPN.
- Temperatura finale 48.75 °C. Servizi phoenix, phoenix-control e
  phoenix-usb-gadget active. Server iperf temporaneo terminato con timeout.

Il test non certifica VBUS, comportamento al boot o stabilità prolungata.
`vbus_verified` resta false: eccezione esplicita di banco root-only in /run,
valida solo per il boot corrente. Non riavviare con A–A inserito. Al reboot
il permesso scade e BindsTo blocca il worker finché si ripristina la modalità
senza USB oppure si prepara nuovamente una sessione di banco autorizzata.
Backup root-only: /root/phoenix-usb-backup-20261115. Nessuna route o regola
firewall del Mac è stata impostata manualmente. Il precedente stallo SSH
è stato recuperato con power cycle a USB scollegata; causa non dimostrata.

## Web USB e password — 2026-11-15

Release firmata 6-df2c19f2b6fd037c ha introdotto listener HTTP/HTTPS vincolati
a phusb0. Release firmata 7-e5be66d837ffa82f aggiunge login password, primo
cambio obbligatorio e lockout 3 tentativi/300 secondi. 100 test Linux passati
sulla ROCK; browser su fixture temporanea e build ESP32 passati. Verificati
sul target redirect 308, HTTPS 200 con certificato validato, login iniziale,
policy negata prima del cambio e logout. Nessuna password personale impostata.
VPN riconnessa dopo update; uscita osservata 187.13.215.138. Dettagli e limiti
in ../../deploy/USB_ADMIN.md. Permesso VBUS ancora solo per il boot corrente.

## Upload e temperatura — 2026-11-15

Release 8-b9aeb544805ab476: download Serverius seguito da upload Cloudflare
https://speed.cloudflare.com/__up (endpoint documentato da cloudflare/speedtest).
Quattro processi curl paralleli, file sintetici sparsi, dimensione adattiva
256 KiB iniziali fino a 16 MiB; conteggio solo richieste complete HTTP 200.
Nessun file utente caricato, nessun fallback di interfaccia; metrica conservativa
che include overhead e scarta richieste parziali alla scadenza.
Prova VPN Germany #1158: download 285.06 Mbps, upload 73.99 Mbps, 20.21 s,
361.1 MB ricevuti e 93.2 MB upload confermati, picco 55.6 °C. Server diversi:
non è una misura del massimo hardware o del collegamento USB.

Release 9-1186e398fc08713b aggiunge temperature_c nello stato e nella pagina
Sistema (massimo dei sensori thermal disponibili). Verificati 49.4 °C,
VPN connessa e USB configurata. 103 test Linux e build ESP32 passati.

Durante l'update 8, il browser riattivava il servizio USB via socket e annullava
lo stop dell'updater: release 7 rimasta attiva, nessuno switch parziale.
Correzione opt-in /etc/systemd/system/phoenix-update.service.d/usb.conf da
platforms/linux/deploy/phoenix-update-usb.conf: stop socket/servizi USB prima,
ripartenza socket dopo. Retry dello stesso stage già verificato, senza abbassare
sequence né bypassare firma; update 8 e successivo 9 riusciti.

## Hotspot configurabile — 2026-11-15

Release firmata 10-91dfb3026f3ceaba installata; 107 test Linux passati e build
ESP32 passata senza flash. Rete: enable/disable, SSID e password opzionale
(vuota conserva la precedente). Stato confermato da control socket hostapd,
non solo da interfaccia UP. API e persistenza descritte in deploy/HOTSPOT.md.

Verifica fisica mediante API loopback autenticata: hotspot disabilitato,
USB ancora configurata; hotspot riabilitato mantenendo SSID/password originali.
Durante avvio radio_state COUNTRY_UPDATE, poi ENABLED. VPN e USB rimaste
attive, temperatura 48.8 °C. Nessun client associato al momento della lettura;
visibilità dal telefono ancora da confermare. Non dichiarare risolto un
problema RF soltanto perché hostapd è ENABLED.

L'utente ha dovuto reinserire il cavo USB durante l'aggiornamento applicativo.
Registrato come mancato recupero automatico, non attribuito con certezza al
DHCP. Il cambio delle sole impostazioni AP è stato invece eseguito sulla stessa
sessione SSH USB senza perdita del collegamento. Non eseguire reboot con A–A.

Target Ethernet osservato ora 192.168.1.28, USB 192.168.7.1; riverificare sempre.
Driver: bande 2.4/5 GHz; combinazione AP <=1, channels <=1: niente dual-band
AP simultaneo con questa radio/driver. Hotspot attuale 2.4 GHz canale 6.

Nota diagnostica: hostapd è in PrivateTmp del worker; hostapd_cli lanciato fuori
namespace può non ricevere risposta. Usare GET /api/v1/hotspot (worker nello
stesso namespace), non dedurre guasto dal timeout del comando nella shell root.

### Hotspot non visibile dal telefono: indagine RF

Utente conferma rete assente sul telefono anche dopo restart AP. Scansione
CoreWLAN read-only dal Mac (radio già accesa): 11 reti, Phoenix-Test rilevata
su canale6 a -90 dBm; BSSID redatto da macOS, quindi identificazione basata
sul nome, non prova univoca del trasmettitore. Nessuna modifica Wi-Fi del Mac.
Documentazione ufficiale Radxa indica AW-CM256 con antenna esterna obbligatoria
per ROCK 4C+: https://wiki.radxa.com/Rockpi4/hardware/models . Chiesto all'utente
se l'antenna è collegata; assenza/connessione errata è ipotesi coerente col
segnale debole, non ancora verificata fisicamente. Non dichiarare problema risolto.

Kernel boot log indicava regulatory.db non trovato, ma ora pacchetto e file
sono presenti. iw reg set IT sul target non ha cambiato il dominio mostrato 00;
nessun pacchetto/kernel/firmware sostituito. Non attribuire causalità a questo
messaggio storico. Radio firmware BCM4345/6 7.45.251, brcmfmac/cyfmac43455-sdio.

## Chiusura sessione — 15 novembre 2026

Utente conferma: antenna esterna prima scollegata; dopo collegamento vede
Phoenix-Test e conferma funzionamento dal telefono. Hotspot verificato quindi
anche dal client, oltre a hostapd. Lavoro sospeso su richiesta dell’utente;
commit/push software e checkpoint hardware richiesti. Nessun ulteriore ordine,
flash o modifica hardware. Resta la qualifica elettrica USB/VBUS e del reboot.
