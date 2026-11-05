# Ripresa

1. Leggere README, PROGRESS, TASKS, docs/HARDWARE.md e docs/OTA.md. Touch escluso.
2. SDK bloccato: ~/esp/esp-idf commit 10ca0dff2f40aeb539f22d1ef88d031cf7421743.
   Python: ~/.espressif/python_env/idf5.5_py3.9_env/bin/python.
3. Scheda identificata ESP32-P4 v3.1, porta /dev/cu.usbmodem5B901859211,
   CH343 1A86:55D3 seriale 5B90185921. Backup originale completo già verificato:
   results/recovery/original-flash.bin, hash in PROGRESS. Non leggerne il contenuto
   nei log. Non concorrere su seriale con altri monitor/flash.
4. Non caricare build/ o build-lab/: sono per silicio precedente.
   Firmware di banco USB off: build-signed. Include scan C6 al boot e firma software.
   Chiave riservata esistente results/signing/development.pem: NON rigenerarla,
   NON stamparla. Token attivo results/admin-uart.token: NON stamparlo.
5. Build e test:
   ./tools/test.sh
   ./tools/build.sh -B build-signed -D SDKCONFIG=build-signed/sdkconfig -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.rev3;sdkconfig.c6probe;sdkconfig.signed'
   python tools/test_signatures.py build-signed/phoenix.bin results/signing/development.pem
   Usare il Python IDF per espsecure/serial. Build richiede ambiente locale fuori
   sandbox per component manager/sysctl. Non cambiare globalmente SDK o rete Mac.
6. Prima di flash verificare CONFIG_SECURE_BOOT e CONFIG_SECURE_FLASH_ENC_ENABLED
   disattivati, revision min 300 e USB off. Per aggiornare solo app attuale ota_0:
   python -m esptool --chip esp32p4 --port /dev/cu.usbmodem5B901859211 --baud 460800 --after no_reset write_flash 0x20000 build-signed/phoenix.bin
   python tools/monitor.py --port /dev/cu.usbmodem5B901859211 --reset --seconds 45
   Dopo una futura OTA controllare slot attivo prima di riutilizzare questo indirizzo.
7. USB compilata separatamente in build-usb-rev3, NON flash finché fixture/power
   non siano verificati. USB-C è programmazione; Type-A OTG sorgente VBUS.
   Era stata chiesta descrizione dei cavi Ethernet/alimentazione/USB: controllare
   eventuale risposta utente prima di richiedere nuovamente queste informazioni.
8. C6 scan passa; warning versione slave 0.0.0 non equivale a incompatibilità
   delle API base. Non aggiornare C6 alla cieca. STA/AP/client ancora da provare.
9. Ultimo boot verificato: results/boot-final.log (firma RSA-PSS, pairing, scan
   13 reti); immagine/hash in results/firmware-final.json. Priorità: link/DHCP Ethernet con
   cavo confermato; fixture USB, enumerazione Mac/DHCP e percorso NAT; solo dopo
   prova VPN con profilo fornito o endpoint locale di test. Nessuna modifica
   automatica delle route del Mac. Test leak/OTA indicati nei documenti.
10. Continuare implementazione IP statico, profili/regole configurabili e
    robustezza. Non dichiarare terminato il prodotto o provati NAT/VPN dalla build.
