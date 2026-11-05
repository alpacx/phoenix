# OTA firmata in software

Implementata con la verifica standard ESP-IDF Secure Boot v2 RSA-3072 sulle
immagini OTA, **senza abilitare hardware Secure Boot**, senza flash encryption
e senza programmare eFuse. La chiave fidata è ricavata dalla firma dell'app
in esecuzione. Fonte: [Espressif, verifica app senza hardware Secure Boot](https://docs.espressif.com/projects/esp-idf/en/release-v5.5/esp32p4/security/secure-boot-v2.html#signed-app-verification-without-hardware-secure-boot).
Verificata anche l'implementazione nel commit SDK bloccato nel progetto.

## Preparazione riproducibile

La chiave locale di sviluppo è `results/signing/development.pem`, directory 0700,
file 0600, esclusa da Git. Non stamparla né distribuirla. Conservarne un backup
riservato: perderla impedisce OTA con la stessa radice di fiducia. Non è una
chiave di produzione. Generarla solo se assente, dall'ambiente ESP-IDF:

```sh
umask 077
mkdir -p results/signing
python -m espsecure generate_signing_key --version 2 --scheme rsa3072 results/signing/development.pem
./tools/build.sh -B build-signed -D SDKCONFIG=build-signed/sdkconfig \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.rev3;sdkconfig.c6probe;sdkconfig.signed'
python tools/test_signatures.py build-signed/phoenix.bin results/signing/development.pem
```

`phoenix.bin` è firmato; `phoenix-unsigned.bin` non deve essere usato per OTA.
La prima app firmata va installata via seriale sulla scheda dedicata identificata,
con backup già verificato. Non abilitare CONFIG_SECURE_BOOT o FLASH_ENC.
La build ordinaria non consente OTA. La firma software non impedisce sostituzione
fisica della flash o reflashing via UART; non equivale al secure boot hardware.

## Protocollo e recupero

POST autenticato `/api/v1/firmware`, body binario, Content-Length 4096..6291456.
Solo USB LAN; Origin browser rifiutata. Il client incluso:

```sh
python tools/phoenixctl.py --token-file results/admin-uart.token firmware build-usb-rev3/phoenix.bin
```

Usare esclusivamente una build coerente con la fixture fisica presente. L'esempio
USB richiede la fixture VBUS già verificata. La scheda passa a inoltro bloccato,
scrive lo slot inattivo e verifica con `esp_ota_end`. Controlla anche il nome
progetto phoenix, seleziona lo slot solo dopo verifica e riavvia dopo un secondo.
Un errore conserva l'app precedente e il blocco. NVS non viene cancellata.

Il bootloader ha rollback abilitato. Il nuovo firmware conferma PENDING_VERIFY
quando NVS, netif, driver Ethernet e relativo evento START funzionano. È un
controllo minimo di avvio, non una prova di Internet/VPN. Se si riavvia prima
della conferma, il bootloader può tornare allo slot precedente valido.
Nessuna anti-rollback eFuse/versione monotona: un'immagine precedente firmata
con la stessa chiave può essere accettata. La rotazione chiavi non è implementata.

## Risultati e prove aperte

Compilazione della variante firmata riuscita; firma dell’app in esecuzione
verificata anche dalla P4 prima di inizializzare i servizi. Test host espsecure: immagine
originale accettata, alterazione del byte 64 rifiutata, chiave estranea rifiutata.
Queste prove non sostituiscono le prove OTA sul dispositivo.

Restano: invio HTTP via USB, verifica delle risposte per firma errata/troncamento,
transizione ota_0 → ota_1, reboot anticipato e rollback, interruzione alimentazione
durante erase/write/boot selection, conservazione NVS e mancata riapertura del
traffico. Eseguire con fixture e alimentazione controllate; mai interrompere il
backup originale. Log e stato della scheda in PROGRESS.md.
