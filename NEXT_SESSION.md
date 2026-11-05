# Ripresa

1. Leggere README, PROGRESS, TASKS e docs/HARDWARE.md. Touch escluso.
2. Non caricare build/ o build-lab/ sulla scheda v3.1: sono per silicio precedente.
3. Controllare results/recovery/backup.log, dimensione/hash original-flash.bin.
   Backup potrebbe essere in corso: non avviare un secondo accesso seriale concorrente.
4. Controllare /tmp/phoenix-build-rev3.log. La build target corretta è build-rev3.
5. `./tools/test.sh` per core nativo. Build v3:
   `./tools/build.sh -B build-rev3 -D SDKCONFIG=build-rev3/sdkconfig -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.rev3'`
6. Identificare sempre la scheda prima di flash; porta osservata /dev/cu.usbmodem5B901859211,
   ESP32-P4 v3.1. Autorizzazione utente copre flash dedicato dopo backup, non eFuse.
7. Prossima attività: primo boot seriale della build USB-disabled corretta ed Ethernet.
8. Non dichiarare VPN, NAT o prestazioni provati sulla sola base della compilazione.
9. Continuare Wi-Fi/AP e robustezza dopo aver verificato il percorso USB/Ethernet.
