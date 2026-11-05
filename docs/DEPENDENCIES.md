# Dipendenze e fonti

| Componente | Blocco versione | Licenza / modifiche |
|---|---|---|
| ESP-IDF | 5.5.4 commit 10ca0dff2f40aeb539f22d1ef88d031cf7421743 | Apache-2.0 e licenze componenti; SDK non modificato |
| lwIP Espressif | fd432e4ee2cfb7f7f1c7eb7227e0173412e7b84e, submodule SDK | BSD; hook del progetto, nessuna modifica SDK |
| esp_hosted | 3.0.10, dependencies.lock | Apache-2.0; nessuna modifica upstream |
| esp_wifi_remote | 1.6.5, dependencies.lock | Apache-2.0 |
| esp_tinyusb | 2.0.1, dependencies.lock | Apache-2.0; override locale del solo tinyusb_net.c |
| tinyusb | 0.21.0~4, dependencies.lock | MIT |
| WireGuard ESPHome | tag v0.4.8, commit 9b7660fed27151abdcbf32b43861044cf4a32497 | BSD-3-Clause, vendorizzati solo src/include/build/license |
| esphome/libsodium | dependencies.lock | ISC e attribuzioni incluse nel pacchetto |
| mbedTLS | submodule ESP-IDF 9d669eadb1955d348986b9280156710aaaadf79f | Apache-2.0 |

WireGuard upstream ha manifest interno 0.4.6 anche nel tag v0.4.8: l'identità
riproducibile è il commit sopra. Patch locale wireguardif.c: richiede bind_netif
esplicita, elimina autodetect per nomi, pulisce private_key sul ritorno. Conservata
la licenza in components/wireguard/LICENSE. Patch wireguard-platform.c: abilita
l’entropia SAR P4 ad ogni richiesta del DRBG (anche reseed), arresta il firmware
se la generazione DRBG fallisce anziché utilizzare byte non validi. La libreria è attivamente pubblicata,
ma non è stato eseguito un audit crittografico indipendente. Non copiare ESP-KVM.

Fonti esaminate:
- [WireGuard sorgente](https://github.com/esphome-libs/wireguard)
- [ESP-KVM](https://github.com/espkvm/espkvm): il tunnel per il dispositivo non prova NAT/gateway USB.
- [wired_nic](https://github.com/espressif/esp-iot-bridge/tree/master/examples/wired_nic): nessun preset P4 nella directory esaminata; non assunto supporto plug-and-play.
- Esempio tusb_ncm del checkout SDK: il suo percorso Wi-Fi bridge non realizza il gateway firewall richiesto.
- [ESP-Hosted MCU](https://docs.espressif.com/projects/esp-techpedia/en/latest/esp-friends/solution-introduction/multimedia/application-solution/esp-hosted-mcu.html): serve coerenza versioni host/slave; trasporto e scansione verificati, STA/AP da provare. Il firmware C6 presente non pubblica i metadati richiesti dal nuovo host: warning 0.0.0, non una versione realmente identificata. Nessun aggiornamento C6 eseguito.


Override `components_overrides/esp_tinyusb/tinyusb_net.c`: copia del file 2.0.1
con licenza Apache-2.0 allegata. CMake verifica SHA-256 del sorgente originale e
sostituisce solo questa unità di compilazione, senza scrivere nelle dipendenze.
Patch: verifica calloc prima del dereference async; identificatore generazionale
per callback sync differite; consumo singolo del pacchetto; pubblicazione del
completamento prima del rilascio del semaforo; cancellazione eventi obsoleti.
Il driver Phoenix usa solo sync, resta unico proprietario del buffer e lo libera
anche dopo timeout; nessuna callback di free ambigua. Test con scheduler simulato
compilano le funzioni effettive e coprono callback vecchie/timeout/backpressure.
Le prestazioni e i percorsi fisici USB restano da provare sul banco.
