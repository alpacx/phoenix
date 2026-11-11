# Phoenix ESP32

Implementazione esistente ESP-IDF/FreeRTOS, mantenuta durante il port Linux.
`main/` contiene entrypoint, backend amministrativo, adattatori rete/Wi-Fi/VPN,
persistenza NVS, Kconfig e manifest delle dipendenze.

La root resta l'entrypoint ESP-IDF: eseguire `./tools/build.sh` dalla root.
`CMakeLists.txt` registra questa directory main e `shared/phoenix_core`
tramite EXTRA_COMPONENT_DIRS. Asset web incorporati da `shared/web`.
Non creare copie della UI o un secondo sdkconfig implicito.

Restano in root per compatibilità: sdkconfig.*, partitions.csv,
dependencies.lock, components/wireguard, components_overrides e tools/build.sh.
I build esistenti richiedono riconfigurazione dopo lo spostamento dei sorgenti.
Consultare docs/HARDWARE.md prima di flash/cablaggio e NEXT_SESSION.md per
le prove storiche: indirizzi, porte seriali e stato dispositivo vanno rilevati
nuovamente, non presunti ancora attuali.
