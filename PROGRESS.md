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
