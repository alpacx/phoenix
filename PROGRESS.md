# Storico e navigazione VPN — 2026-11-06

UI: singola voce VPN, schede NordVPN e VPN WireGuard, spiegazione VPN/profilo.
Countdown locale a un secondo sincronizzato con API, sospeso se dati obsoleti.
Storico NordVPN 8 ore nel journal vpn_history (0xc20000, 128 KiB), 1344 record
CRC; API autenticata paginata vpn/history. Registrazione solo al primo handshake
riuscito di ogni connessione. Nessuna retrodatazione o cronologia inventata.
Test: tools/test-history.sh e node tests/test_countdown.cjs.
Token admin locale: results/gatewaybench/admin-token.txt; NON stampare.
Bridge 127.0.0.1:8085 lo inserisce automaticamente; altro token è NordVPN.
Verifica reale: API storico persistent=true con cinque connessioni conservate
dopo flash/riavvio. UI Chrome controllata: menu VPN, schede, spiegazione,
storico e countdown visibili; accesso locale automatico riuscito.
Seriale: aggiunto fflush(stdout) alle risposte PHADMIN per evitare timeout da
buffering. Bridge usa DTR/RTS true e separatore iniziale di comando.

---

# Pannello amministrativo e NordVPN diretto — 2026-11-06

Il gateway usa ora NordVPN direttamente, con chiave fornita dall’utente nel pannello.
Il Mac non è più un relay necessario. UI: http://127.0.0.1:8085 tramite
`tools/admin_bridge.py`, UART /dev/cu.usbmodem5B901859211, token locale in
results/gatewaybench/admin-token.txt (non stampare). Dall’AP: http://192.168.9.1.
Non aprire la seriale mentre il bridge la possiede. Arrestarlo prima del flash.
Build corrente: build-admin, conserva NVS durante aggiornamenti.

Implementati UI responsive, firewall ordinato, port forwarding, revisioni anti
conflitto, WireGuard persistente, provisioning NordVPN HTTPS e scheduler.
L’interfaccia non menziona il modello hardware. Paese vuoto: rotazione casuale
escludendo il precedente; paese selezionato: vincolo stretto. La rotazione era
spenta nella configurazione utente; viene abilitata a 300 secondi dopo i test.
Test host e API policy passati; regole temporanee ripristinate. Log rotazione reale:
results/gatewaybench/rotation-live.log. Vedere docs/API.md e docs/NORDVPN-P4.md.
Verifica HTTPS pubblica attraverso il tunnel riuscita: IP 186.247.43.8,
server NordVPN North Macedonia #13; Cloudflare riporta loc=BG (geolocalizzazione
distinta dal paese di catalogo NordVPN). Rotazione reale: Italy #536 → #476
restando in IT; poi Lebanon #3 → Uzbekistan #3 in modalità casuale. Stato precedente qui sotto è storico.

---

# NordVPN sul Mac — 2026-11-06

Utente ha attivato NordVPN sul Mac e segnalato IP telefono differente.
Verifica read-only: route 1.1.1.1 su utun6 (10.5.0.2), HTTPS IPv4 nuovo con
routing default e con --interface utun6 dà lo stesso IP pubblico 187.13.23.86.
Relay riavviato per eliminare sessioni TCP/UDP preesistenti; causa originaria
NON ancora isolata (possibili connessioni/cache, non dichiararla certa).
Nuovo handshake P4 riuscito, relay TCP/UDP ripreso senza errori iniziali,
P4 vpn=1 direct=0. Log nuovi server-nordvpn.jsonl e host-nordvpn.log in
results/gatewaybench. Stesso comando host-internet; nessun cambio route/DNS/pf
né configurazione NordVPN. Conferma esplicita utente ricevuta dopo riavvio relay: anche il telefono
mostra187.13.23.86, uguale al Mac/NordVPN.
Il relay usa routing Mac corrente, NON è vincolato a utun6. Il firewall P4
protegge il tratto fino al peerMac, non impone la presenza del secondo tunnel
NordVPN. Non promettere fail-closed rispetto a NordVPN senza implementazione.

---
# Prova integrata completata e Internet attivo — 2026-11-06

STATO FINALE: build-gatewaybench, Wi-Fi Phoenix-Test 192.168.9.1/24, P4 Ethernet
192.168.8.170, WireGuard 10.77.0.2 verso Mac192.168.8.103:51821. direct=false,
vpn=true. USB dati off. Nessuna modifica route/DNS/pf Mac, nessun flash C6/eFuse.

Internet dal telefono confermato dall'utente (ricerca Google). Exit userspace Mac
TCP/UDP pubblico IPv4 con DNS, TLS end-to-end. Mac e processo devono restare accesi;
IP pubblico della rete Mac, non di un provider remoto. Limiti relay: 256 sessioni,
TCP max10min, UDP idle30s; niente ICMP relay/IPv6/destinazioni private. Nessun log
di siti o query DNS. Firmware e chiavi di banco non sono un rilascio produzione.

Endurance terminata: 608.835 s, 45 cicli, 90 trasferimenti
completi da8MiB =720MiB (360 per direzione). Download 12.25 Mbit/s
(range 6.55–14.61), upload 22.33
(range 16.65–24.92). Nessun endurance_error,
nessun panic/reset durante prova. Heap campionato finestra prova 330444–397036 byte,
finale393452: nessuna deriva evidente, NON prova assoluta di assenza memory leak.

Confronto diretto stesso telefono/HTTP8MiB: 8.87download/22.89upload, sei completi.
TCP macOS nel diretto vs gVisor nel tunnel; non isolare costo crypto da questi dati.
Recupero peer dopo15s e nuovi trasferimenti già verificati nelle serie precedenti.

Egress mirato passato con controllo positivo e ACKprobe: tre UDPclient sintetici
porte53/443/8081 versoMac, zero plaintext VPN/blocked, tre direct, zero blocked.
NON audit completo DNS/IPv6 né cattura di tuttaEthernet. Tentativi inconcludenti
conservati; generatore corretto PBUF_LINK. check_egress.py ora forza/attende modalità
VPN anche all'avvio per rendere ripetibile il test quando stato iniziale diverso;
non rieseguirlo durante navigazione/trasferimenti perché cambia modalità.

Catture tcpdump terminate al termine della prova; server Internet e monitor UART restano attivi.

Log finali results/gatewaybench/server-final-exit.jsonl, uart-probe-fixed.log,
host-final-exit.log, endurance-summary.json, egress-results.json e catture locali.
Host attivo .tools/wgbench/host-internet -gateway-server -internet-exit
-direct-listen192.168.8.103:8080 -dir results/gatewaybench. Listener diretto ristretto
alla P4, pagina non raggiungibile tramite VPN (destinazioni private bloccate).
Pagina VPN http://10.77.0.1:8080; navigazione normale daPhoenix-Test con dati mobili
spenti. Monitor UART di banco limitato3600s: non aprirne un altro (può resettareP4).
PasswordAP in results/gatewaybench/wifi-password.txt; mai stampare chiavi private.

Codice e risultati documentati in benchmarks/gateway/README.md. Build firmware,
flash verificata, test esistenti e test Go policy/DNS+HTTPS passati. Nessun nuovo
commit/push. Resta warning compatibilità esp-hosted C6; versione C6 non aggiornata.

---

## Confronto diretto completato — 2026-11-06

3 x 8 MiB/direzione completati senza VPN: download telefono 8.87 Mbit/s
(intervallo 6.73–11.27), upload 22.89 Mbit/s (19.92–26.95).
Server-final-exit.jsonl remote=192.168.8.170 conferma percorso diretto/NAPT.
VPN ripristinata via UART subito dopo; non lasciare direct attivo.
Prestazioni senza VPN non molto superiori alle serie con VPN: non attribuire
il limite alla sola crypto; Wi-Fi/SDIO/rete e TCP host diverso sono confondenti.
Invitato utente ad aprire 10.77.0.1:8080 e avviare Prova prolungata 10 minuti.
In attesa risultati endurance_complete o endurance_error nel log corrente.

---
# Internet e verifica uscita — 2026-11-06

Internet attivato attraverso il Mac con relay userspace TCP/UDP pubblico IPv4,
trasparente per il telefono: AP → firewall/NAPT → WG → Mac sockets → Internet.
Utente conferma ricerca Google riuscita con dati mobili spenti. Nessuna route/DNS
Mac o pf modificati. Non è un servizio VPN esterno: IP pubblico della rete Mac;
Mac/peer devono restare attivi. TCP/UDP supportati, non ICMP forwarding o IPv6.
Relay limita 256 sessioni, TCP a 10 min, UDP idle 30 s; destinazioni private,
loopback, link-local e riservate escluse. Non registra destinazioni di navigazione.
Test automatico: DNS UDP e HTTPS con certificato valido a example.com passati.
Netstack locale derivato dalla versione wireguard-go bloccata, licenza preservata;
HandleLocal=false necessario con NIC promiscuo. File exit.go e test dedicati.

Firmware corrente build-gatewaybench include bench UART commands (solo flag di
banco) e probe IP sintetico; admin HTTP/pairing disattivati nel bench. Produzione
non abilita questi comandi. `bench direct` ripristina VPN automaticamente dopo
300 s; `bench vpn`, `bench blocked`, `bench probe`. Monitor seriale unico legge
comandi da results/gatewaybench/uart-command.txt. Scrivere atomicamente una riga
con nonce univoco e comando. Non aprire un secondo monitor (reset possibile).

Test egress con ACK di completamento probe passato, egress-results.json:
3 UDP sintetici da AP 192.168.9.250 verso Mac, porte 53/443/8081, ID 64000..64002.
0 in chiaro con VPN, 0 blocked, tutti 3 direct (controllo positivo), 0 blocked.
Cattura egress-wide.pcap. Limitato a pacchetti sintetici e percorso verso Mac;
NON prova generale di assenza DNS/IPv6 leak o cattura di tutta l'uscita Ethernet.
Tentativi precedenti inconcludenti conservati: generatore senza headroom Ethernet;
corretto allocando PBUF_LINK. Ultima serie verifica ACK UART per ogni probe.

Processi attivi: host-internet con -gateway-server -internet-exit
-direct-listen 192.168.8.103:8080 -dir results/gatewaybench; listener diretto accetta
solo sorgente P4 192.168.8.170. Server nel tunnel 10.77.0.1:8080.
Monitor benchmarks/gateway/monitor_control.py limitato a 3600 s.
Log correnti uart-probe-fixed.log, server-final-exit.jsonl, host-final-exit.log.
Due catture Mac attive mac-p4.pcap e egress-wide.pcap. Nessun commit/push nuovo.

Confronto diretto appena avviato (autoscadenza 5 min), utente invitato ad aprire
http://192.168.8.103:8080 da Phoenix-Test e premere Misura. Raccogliere i 6 risultati,
poi ripristinare bench vpn, verificare handshake e invitare a 10.77.0.1:8080:
pulsante nuovo «Prova prolungata: 10 minuti (traffico locale)». Non dichiarare
completati confronto/endurance prima dei risultati. Il confronto usa stesso HTTP,
telefono e payload ma TCP Mac OS nel diretto vs gVisor nel tunnel: non isola crypto.

---

## Trasferimenti dopo recupero — 2026-11-06

Completati tutti i 6 trasferimenti da 8 MiB dopo interruzioni del peer, senza
riavvio della scheda. Media aggregata download 6.38 Mbit/s,
upload 16.84 Mbit/s. Intervalli download 4.13–9.55, upload
13.42–20.89 Mbit/s. Prima serie 12.43/23.03: recupero funzionale verificato,
prestazioni variabili e inferiori nella seconda serie; causa non isolata.
Nessun panic/reset osservato. Non dichiarare stabilità prestazionale né assenza
fughe dimostrate. Dati in server-v2.jsonl, ultimi sei browser_result di transfer.

---

## Recupero peer verificato — 2026-11-06 17:14

Ricevuti due resoconti completi peer_outage dal telefono in server-v2.jsonl.
Ultima prova: richieste OK a 0/0.722/1.471 s, fallite da 2.202 a 15.419 s,
nuovamente OK da 17.622 s fino a 34.817 s. Peer disattivato alle 17:13:28.468
e riattivato alle 17:13:43.471 (+15 s); nuovo handshake verificato.
Recupero automatico delle richieste HTTP nel tunnel confermato, senza riavvio
della scheda. Non è prova completa di assenza fughe né stress test; nuova serie
di throughput dopo outage ancora da eseguire.

---
# Prova gateway integrato avviata — 2026-11-06

Firmware corrente **build-gatewaybench**, layout Phoenix OTA con app 0x20000.
USB dati off, C6 AP Phoenix-Test 192.168.9.1/24, Ethernet 192.168.8.170,
WireGuard 10.77.0.2 verso Mac 192.168.8.103:51821. Firewall/NAPT/hook di
produzione attivi, direct=false. Non è ancora una prova completa superata.

Telefono disponibile; utente invitato a disabilitare dati mobili, collegarsi AP,
aprire http://10.77.0.1:8080. Password in results/gatewaybench/wifi-password.txt;
chiavi/header locali nella stessa cartella. Non esporre chiavi o pubblicare binari.
Mac serve pagina solo nel tunnel tramite .tools/wgbench/host -gateway-server
-dir results/gatewaybench, nessuna modifica route/DNS di sistema.

Correzioni questa sessione:
- subnet AP 192.168.8.0/24 collideva col router: passata a 192.168.9.0/24 in
  gateway, setup Wi-Fi, controllo overlap e documentazione.
- ph_canforward usava ip_current_input_netif(), che in IDF lwIP viene impostato
  solo DOPO il ramo forwarding per consegna locale: tutti i pacchetti AP erano
  ammessi al firewall ma non inoltrati. Ora ph_ip4_input registra n in p->if_idx
  e ph_canforward usa netif_get_by_index. Vale anche per ingressi WG decapsulati,
  senza ereditare il contesto Ethernet esterno. Primo tentativo conservato.

Build e test host passati, flash verificata, DHCP Ethernet/AP e handshake WG
verificati. Primo telefono DHCP 192.168.9.2. Dopo correzione/reflash percorso completo verificato: 3 x 8 MiB/direzione,
download telefono 12.43 Mbit/s, upload 23.03 Mbit/s aggregati. NAT source
10.77.0.2 visto sul Mac. Interruzione peer ancora pendente; non dichiarare
kill-switch/assenza leak completamente validati.
C6 host/slave version mismatch warning persiste; nessun flash C6 effettuato.

Log correnti: results/gatewaybench/uart-v2.log, server-v2.jsonl,
host-status-v2.log, mac-p4.pcap (cattura solo traffico visibile al Mac, NON tutta
la LAN), uplink-negative.json. Log primo tentativo senza -v2 conservati.
Processi lasciati per la prova: monitor UART limitato 1800 s, server WireGuard,
tcpdump su en0. Apertura UART può resettare P4: non riaprire durante misura.
Pagina offre 3 x 8 MiB/direzione e peer down 15 s, con risultati sul Mac.
Interruzione tunnel non equivale da sola a prova completa assenza leak.
Procedura: benchmarks/gateway/README.md. Nessun commit/push nuovo.

---
# Ultimo stato — WireGuard misurato sulla P4, 2026-11-06

Installato benchmarks/wireguard/build-dma: app factory a 0x10000, non gateway
Phoenix. P4 v3.1 MAC e8:f6:0a:e3:b3:6e, Ethernet 100 Mbit/s full-duplex,
LAN 192.168.8.170. Mac 192.168.8.103. USB device, Wi-Fi, NAT e firewall gateway
non esercitati. Nessun eFuse o route/DNS del Mac modificati.

Endpoint Mac temporaneo userspace wireguard-go + gVisor, processo terminato
al termine dei test. Binario/toolchain locali .tools/wgbench; chiavi di banco
in results/wgbench (0600, escluse da Git). Firmware contiene chiave di banco:
non pubblicare binari. Config firmware fissa endpoint e orologio del setup.

| Direzione | TCP senza VPN (baseline) | TCP nel tunnel WireGuard | Intervallo WireGuard |
|---|---:|---:|---:|
| Mac → P4 | 74.54 Mbit/s | 15.26 Mbit/s | 12.02–27.12 |
| P4 → Mac | 38.98 Mbit/s | 33.61 Mbit/s | 33.22–33.81 |

Sei trasferimenti completi da 32 MiB, handshake e contatori WG verificati.
Media aggregata = bit totali/tempo totale. Variabilità in RX ancora marcata;
non è uno stress test né misura di forwarding/USB. Confronto non isola solo
la crypto: cambiano stack TCP del Mac (gVisor) e buffer DMA del firmware.

Due problemi reali corretti:
1. ESP-IDF 5.5 interpretava netif->state di WG come esp_netif_t: crash DHCP
   durante netif_add. CONFIG_LWIP_PPP_SUPPORT=y separa client_data senza creare
   un link PPP; aggiunto a defaults e guardia compilazione in wireguardif.c.
   Le build Phoenix con sdkconfig vecchi richiedono tale opzione esplicita.
2. AllowedIPs RX verificava la destinazione invece della sorgente IPv4:
   corretto nel componente condiviso. Test positivo traffico e negativo con
   peer autenticato/source 10.77.0.3 non autorizzata: handshake OK, TCP respinto.

Prima dei buffer DMA aumentati: una coppia completa a 26.98/32.66 Mbit/s,
poi due upload incompleti a 120 s (27097844 e 30617644 byte, ~1.81/2.04 Mbit/s).
Con DMA 1536 byte, RX=30, TX=10, TCP WND/SND=63360: serie finale completa.
Non nascondere questi fallimenti né dichiarare risolta la stabilità generale.

Log finali: results/wgbench/client-dma.jsonl, uart-dma.log,
host-dma-status.log, source-rejection-dma.log. Prove precedenti conservate.
Build benchmark e test host esistenti (firewall/parser/USB sync) passati.
Procedura e limiti: benchmarks/wireguard/README.md.

---
Registro precedente (storico):

# Confronto TCP completato — 2026-11-06

Firmware corrente benchmarks/ethernet/build-tuned, finestra/buffer 63360 byte,
mailbox TCP 46 / tcpip 64. Link 100 Mbit/s full-duplex, P4 192.168.8.170.
Sei trasferimenti da 32 MiB completi; throughput aggregato (byte totali/tempo):

| Direzione | Default Mbit/s | Buffer aumentati Mbit/s | Miglioramento |
|---|---:|---:|---:|
| Mac → P4 | 14.27 | 74.54 | 5.22× |
| P4 → Mac | 8.91 | 38.98 | 4.38× |

Intervalli tuned: U 63.61–82.49, D 34.11–42.55 Mbit/s. Config precedente:
WND/SND_BUF 5760, mailbox 6/32. Stessi sorgenti/CPU 400 MHz/protocollo/rete.
Log results/ethernet-tuned-client.jsonl e results/ethernet-tuned-uart.log.
Forte miglioramento osservato, ma rete condivisa e variazioni impediscono di
attribuire ogni differenza ai buffer. Nessuna VPN, USB o forwarding misurati.
Heap campionato dopo trasferimenti: minimo 479800 byte; non è minimo globale
né prova di assenza leak. Firmware di banco TCP 5001 ancora installato.
Prossima prova utile: WireGuard end-to-end con peer locale e percorso client
realizzabile (USB ancora subordinata alla fixture). Non confondere microbenchmark
crypto ~49.6 Mbit/s con throughput tunnel, né prevedere prestazioni S31.

---
# Ultimo esito — baseline TCP completata, 2026-11-06

Seriale tornata disponibile; DHCP P4 192.168.8.170, Mac 192.168.8.103.
Primo tentativo interrotto da riavvio osservato durante apertura monitor seriale;
ripetuto dopo DHCP, senza ulteriori aperture seriali. Sei trasferimenti completati
(3 x 32 MiB per direzione) con conteggi completi:
Mac -> P4: 14.27 Mbit/s aggregati, intervallo 13.94–14.68.
P4 -> Mac: 8.91 Mbit/s aggregati, intervallo 8.47–9.17.
Ping durante trasferimento: 4/4 risposte, media 2.632 ms (campione breve).
Log client: results/ethernet-retry2-client.jsonl; boot: results/ethernet-retry-uart.log.
Rete senza VPN/firewall/USB, TCP default (WND/SND_BUF 5760, MSS 1440).
Misure includono LAN e collegamento Mac; non rappresentano limite del PHY/CPU.
Firmware corrente: benchmarks/ethernet, server TCP 5001 solo per LAN fidata.
Prossimo passo: confronto controllato con buffer TCP ottimizzati, poi VPN.

---
# Aggiornamento rete — 2026-11-06

Mac passato a 192.168.8.103/24. ARP di 192.168.8.170 corrisponde alla P4
(e8:f6:0a:e3:b3:6e), ma connessione TCP 5001 scade ancora (10 s).
Porta /dev/cu.usbmodem5B901859211 non più presente, nessuna USB seriale
alternativa rilevata. Occorre ricollegare USB-C dati/alimentazione al Mac per
leggere DHCP e stato firmware. Nessuna nuova misura throughput disponibile.
Il tentativo di acquisizione UART ha troncato results/ethernet-benchmark-uart.log;
il precedente esito link/DHCP rimane documentato qui e nel README benchmark.

---
# Stato attuale — baseline Ethernet, 2026-11-06

Dopo il collegamento Ethernet richiesto dall’utente, installato firmware autonomo
benchmarks/ethernet (sostituisce il benchmark crypto). Flash verificata, P4 v3.1
MAC e8:f6:0a:e3:b3:6e. Link IP101 100 Mbit/s full-duplex verificato; DHCP
192.168.8.170/24, gateway 192.168.8.1. Server TCP di banco sulla porta 5001.
USB dati/Wi-Fi/VPN non attivi, nessun eFuse o route Mac modificati.
Mac en0 192.168.1.179/24 via 192.168.1.1. Connessione TCP alla P4 scaduta dopo
10 s: nessuna misura throughput rete disponibile. Portare Mac e P4 sulla stessa
LAN, poi rieseguire benchmarks/ethernet/client.py con IP verificato su UART.
Log: results/ethernet-benchmark-uart.log. Firmware di test non autenticato:
solo LAN fidata. App factory 0x10000; non usare offset OTA del gateway.

---
Registro precedente (storico):

# Stato attuale — benchmark Waveshare, 2026-11-06

L’utente ha autorizzato nuove prove sulla Waveshare dopo l’erase.
Installato un firmware autonomo di benchmark crypto dalla directory
benchmarks/crypto, NON il gateway Phoenix. P4 v3.1 confermata via MAC
(e8:f6:0a:e3:b3:6e). Flash bootloader/partizioni/app verificata da esptool.
USB dati, Ethernet e Wi-Fi non inizializzati; eFuse non modificati.
Ethernet non collegata, come confermato dall’utente.

P4 400 MHz, build -O2, task singolo CPU0, ChaCha20-Poly1305 della libreria
WireGuard presente nel repository, buffer interni. Tre prove da 1000 pacchetti
per dimensione. Con payload 1424 byte: encrypt 49.62–49.63 Mbit/s, decrypt
49.70–49.72 Mbit/s. Con 512 byte: 46.54–46.57 / 46.67–46.70; con 64 byte:
24.51–24.80 / 25.02–25.19. Roundtrip e tag alterato verificati.
Tempi delle sole chiamate crypto: escluse pause, confronto dati, rete e VPN.
Non sono throughput end-to-end né limiti assoluti del silicio o stime S31.
Log locale: results/crypto-benchmark.log. Procedura: benchmarks/crypto/README.md.
Per prove rete serve collegare Ethernet; USB richiede ancora fixture verificata.
Il gateway precedente resta nel repository; NON usare i suoi offset app per
questo benchmark (partizione factory a 0x10000, layout diverso).

---
Registro precedente (storico):

# Stato attuale — 2026-11-06

Su richiesta esplicita dell’utente, cancellata tutta la flash da 16 MiB del
P4 v3.1, MAC e8:f6:0a:e3:b3:6e, bridge seriale 5B90185921. Esptool erase_flash
riuscito; verify_flash su 16777216 byte tutti 0xFF: verify OK (digest matched).
Eseguito reset. Firmware, bootloader, partizioni e NVS Phoenix non sono più
presenti sul P4. Nessun eFuse modificato. Flash separata C6 non cancellata.
Repository e backup originale sul Mac conservati. Non riflashare senza nuova
richiesta dell’utente. Quanto segue è il registro storico precedente all’erase.

# Progresso — 2026-11-05

## Verificato sul computer

Cartella inizialmente vuota, nessun AGENTS.md trovato. SDK 5.5.4 commit
10ca0dff2f40aeb539f22d1ef88d031cf7421743; toolchain esp-14.2.0_20260121.
Test C con UBSan passati: firewall/gate/direzione/porte/CIDR/checksum/MSS,
100000 pacchetti malformati; parser WireGuard, prefisso CIDR preservato,
20000 profili malformati. Test scheduler sulle funzioni USB reali: invio normale,
timeout prima/durante callback, isolamento callback vecchia, completamenti
obsoleti e backpressure passati. Non sono test end-to-end del gateway.
ASan non verificato: anche un main vuoto resta in CPU busy nell'ambiente;
processi fermati. Nessun risultato ASan dichiarato.

Build/link per P4 v3.x riusciti: build-c6probe (USB off), build-signed (USB off,
firma software RSA-3072) e build-usb-rev3 (USB abilitata, sola compilazione).
Test firma host: originale accettato, immagine alterata e chiave estranea rifiutate.
Client Python compilato con py_compile, API HTTP non ancora raggiunta via USB.

## Hardware e recupero

Porta /dev/cu.usbmodem5B901859211, bridge CH343 1A86:55D3 seriale 5B90185921.
ESP32-P4 **v3.1**, quarzo 40 MHz; flash GD 16 MiB identificata via esptool.
Revisione PCB non letta. PSRAM non ancora abilitata/provata.

Backup completo 16777216 byte e verifica esptool: digest matched.
SHA-256 a769156448d970548db6e06473989343e800f0c1ac6c554fb071a47077d86613.
File riservato results/recovery/original-flash.bin, escluso da Git.
Nessun eFuse modificato, nessuna rete del Mac cambiata, nessuna pubblicazione.

## Verificato sul dispositivo

- Flash/boot firmware P4 v3.x, PHY IP101 installato ed Ethernet START.
- Nessun LINK_UP/DHCP Ethernet osservato: cablaggio Ethernet ancora da confermare.
- Pairing UART riuscito; token locale results/admin-uart.token, permessi 0600,
  mai stampato. Hash presente in NVS dopo reboot (`paired=yes schema=1`).
- C6 SDIO 20 MHz operativo; scansioni riuscite (13 reti nel primo test,
  12 nei successivi; nessun SSID/credenziale nei log). Nessuna connessione tentata.
- Firmware C6 di fabbrica non identificabile con RPC recente: host 3.0.10 stampa
  versione slave 0.0.0 e warning mismatch per metadati assenti. Le API di base
  scan/start rispondono. Compatibilità estesa STA/AP non ancora provata; nessun
  aggiornamento C6 eseguito.
- Build firmata avviata e scansione riuscita. Log results/flash-signed.log e
  results/boot-signed.log. Nel ciclo successivo verifica RSA-PSS sulla P4 riuscita prima di NVS/PHY,
  pairing conservato e scan riuscito (15 reti). Log finali:
  results/flash-signed-verified.log e results/boot-signed-verified.log.

Log altri cicli: results/boot-health.log, boot-c6basic.log, boot-manager.log,
pairing-uart.log. Baseline Ethernet idle: heap libero 545256 byte invariato tra
4.4 e 34.4 s. Build con C6 dopo scansione: 487940 byte a 34.5 s; prima variante
firmata: 487748 byte. Con verifica firma e stack main 8 KiB: 482524 byte a 34.7 s. **Questi sono campioni idle, non soak test o benchmark.**

## Implementato ma senza validazione di traffico

USB NCM HS, DHCP/NAPT, firewall IPv4 e blocco IPv6; WireGuard full tunnel con
uscita vincolata all'uplink, gate e svuotamento NAT/ARP; scelta uplink esplicita;
C6 STA/AP alternativi, scan API, credenziali STA opzionalmente salvate in NVS
in chiaro (flash encryption disattivata), hotspot un client su 192.168.8.1/24;
OTA autenticata con verifica software firma/integrità e due slot con rollback.
Nessuna di queste implementazioni dimostra navigazione o assenza di leak.

## Limiti e prossime prove

USB dati necessita fixture VBUS verificata: la Type-A genera VBUS, non collegare
un cavo host-host generico. Finora è rimasta spenta sul dispositivo.
Nessun profilo VPN reale fornito né endpoint locale di test configurato.
Mancano handshake, DNS, traffico bidirezionale, test kill switch e disconnessioni,
client AP, OTA HTTP, rollback/interruzione alimentazione e soak.
Nessuna misura di throughput/latenza/CPU/RAM sotto traffico effettuata.
IP Ethernet statico, regole/profili configurabili, profili VPN multipli/rotazione,
TLS e altre attività restano in TASKS.md. Touch escluso esplicitamente.

## Immagine finale del checkpoint

Firmware firmato 856064 byte, USB dati off, ota_0 a 0x20000.
SHA-256 5db3b20acc73b07cf1afdb10f24856c24455c57c13f2cf4435c7e1419f697e85.
Flash finale con hash verificato; firma RSA-PSS verificata dalla P4, pairing
presente e scansione di 13 reti riuscita. Log results/flash-final.log e
results/boot-final.log; manifest results/firmware-final.json.
Il checkpoint non completa il prodotto: proseguire dalle attività aperte e
dalle prove di integrazione, senza interpretare i test unitari come prove rete.
