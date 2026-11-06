# WireGuard Ethernet benchmark

Prova di TCP terminato sulla P4 attraverso un tunnel WireGuard locale, non del
forwarding USB/firewall/NAT del gateway. P4 400 MHz, IP101 100 Mbit/s, buffer
TCP 63360 byte, MTU tunnel 1420. Nessuna radio C6 o PSRAM richiesta.

Il Mac usa wireguard-go + gVisor netstack in un processo userspace: nessuna
interfaccia VPN di sistema, route, DNS o modifica della connessione Internet.
Questa differenza rispetto al client TCP nativo della baseline introduce un
fattore aggiuntivo: il rapporto di velocità non misura soltanto il costo crypto.

## Preparazione

Host Go in host/, versioni bloccate da go.mod/go.sum. Toolchain locale verificato
tramite SHA256 ufficiale in .tools/wgbench/go (Go 1.27.3). Cache locale in .tools.
Esempio dalla radice, dopo aver predisposto tale toolchain:

```sh
GOPATH="$PWD/.tools/wgbench/gopath" GOCACHE="$PWD/.tools/wgbench/gocache" \
  .tools/wgbench/go/bin/go -C benchmarks/wireguard/host build \
  -o ../../../.tools/wgbench/host .
.tools/wgbench/host -setup -host-ip 192.168.8.103 -p4-ip 192.168.8.170
IDF_TARGET=esp32p4 ./tools/build.sh -C benchmarks/wireguard -B benchmarks/wireguard/build
```

Setup genera chiavi isolate e header in results/wgbench, escluso da Git, permessi
0600. Non stampa chiavi né sovrascrive quelle esistenti. L’immagine compilata
contiene la chiave privata di banco: non pubblicarla. L’orologio P4 parte dal
momento setup: rigenerare setup per sessioni lontane nel tempo (nuova directory
privata e percorso include coerente), soprattutto se si riusa un peer attivo.
Non usare questi materiali per un tunnel di produzione.

Flash completo con flash_args nella directory build, dopo identificazione
P4 v3.x e verifica secure boot/flash encryption disabilitati. Layout factory
0x10000; non usare offset OTA Phoenix. Aprire monitor prima del client,
attendere DHCP, poi lasciare seriale stabile:

```sh
.tools/wgbench/host -trials 3 > results/wgbench/client.jsonl \
  2> results/wgbench/host-status.log
```

Host UDP 51821, P4 UDP 51820. Indirizzi interni 10.77.0.1 (Mac) e 10.77.0.2
(P4), allowed IP del solo peer. Server TCP 5001 bind esclusivo 10.77.0.2.
Tre trasferimenti da 32 MiB per direzione, timeout globale socket 125 s;
P4 interrompe il ciclo dopo 120 s (socket inactivity timeout 10 s).
U: Mac invia, P4 conferma conteggio. D: Mac verifica conteggio ricevuto.
Risultati contano payload TCP, non overhead WireGuard. Al termine il processo
chiude il peer e stampa solo contatori e timestamp handshake, mai la config.

## Correzione integrazione ESP-IDF 5.5

Primo avvio ha riprodotto un crash in esp_netif_internal_dhcpc_cb durante
netif_add: senza LWIP_ESP_NETIF_DATA, ESP-IDF interpreta netif->state come
esp_netif_t, ma WireGuard lo usa per i propri dati. CONFIG_LWIP_PPP_SUPPORT=y
abilita la separazione client_data nella versione SDK bloccata, senza creare
una connessione PPP. Impostazione aggiunta anche ai defaults Phoenix e controllo
di compilazione nella libreria per impedire build con configurazione errata.
Per sdkconfig preesistenti disabilitati, abilitarla esplicitamente o rigenerare
una nuova build; i defaults non sovrascrivono valori già presenti.

Sorgenti ufficiali endpoint: https://git.zx2c4.com/wireguard-go/ (esempio netstack).

Un secondo difetto è emerso con AllowedIPs ristretto: wireguardif.c confrontava
l’indirizzo IPv4 di destinazione del pacchetto decifrato con gli indirizzi del
peer. Corretto per confrontare la sorgente come richiesto da WireGuard.
Il profilo full-tunnel 0.0.0.0/0 avrebbe nascosto il problema.

Verifica negativa dopo una prova positiva (senza riavviare la P4):

```sh
.tools/wgbench/host -test-rejected-source
```

Il peer mantiene la stessa identità crittografica ma usa sorgente 10.77.0.3,
non consentita dalla P4 (10.77.0.1/32). Il test richiede handshake riuscito e
mancata connessione TCP; una mancata handshake rende la prova inconcludente.

## Diagnostica del degrado sotto carico

Prima coppia completa: circa 26.98 Mbit/s Mac->P4 e 32.66 Mbit/s P4->Mac.
Il secondo upload scade a 120 s dopo 27097844 byte (~1.81 Mbit/s): non usare
la prima coppia come prestazione sostenuta. Baseline DMA Ethernet: 20 RX buffer
da 512 byte, che possono accogliere molti meno frame MTU pieni rispetto alla
finestra TCP. Una variante sperimentale sdkconfig.dma porta i buffer a 1536 byte
(allineati a 64, come richiesto dal P4) e RX count a 30. È un’ipotesi di tuning,
non una causa già dimostrata. Conservare e riportare anche le prove fallite.

## Risultato finale — 2026-11-06

| Direzione | TCP senza VPN (baseline) | TCP nel tunnel WireGuard | Intervallo WireGuard |
|---|---:|---:|---:|
| Mac → P4 | 74.54 Mbit/s | 15.26 Mbit/s | 12.02–27.12 |
| P4 → Mac | 38.98 Mbit/s | 33.61 Mbit/s | 33.22–33.81 |

Tutti e sei i trasferimenti da 32 MiB completi nella variante DMA, nessun panic
nel log finale. Handshake confermato; al termine contatori host TX 114711220,
RX 110369308 byte (incapsulamento/ritrasmissioni inclusi, non payload utile).
Controllo source 10.77.0.3 respinto con handshake riuscito anche sulla build finale.
Due upload precedenti con DMA default erano incompleti a 120 s: 27097844 e
30617644 byte, rispettivamente ~1.81/2.04 Mbit/s. La serie finale non equivale
a una prova lunga di stabilità; RX resta variabile da 12 a 27 Mbit/s.

Riproduzione variante finale:

```sh
IDF_TARGET=esp32p4 ./tools/build.sh -C benchmarks/wireguard \
  -B benchmarks/wireguard/build-dma \
  -D SDKCONFIG="$PWD/benchmarks/wireguard/build-dma/sdkconfig" \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.dma'
```

File locali: results/wgbench/client-dma.jsonl, uart-dma.log,
host-dma-status.log, source-rejection-dma.log. Confronto con baseline Ethernet
non isola il solo costo crypto: differiscono anche stack TCP host e DMA.
Le chiavi non sono nei sorgenti versionabili; la build le include da results.
