# Attività ordinate

- [x] Ispezione cartella inizialmente vuota, SDK e schema ufficiale.
- [x] Pin SDK e dipendenze, build P4 v1.x e USB laboratorio, test core UBSan.
- [x] Identificazione scheda collegata: P4 v3.1.
- [ ] Backup completo verificato e primo boot sulla scheda.
- [ ] Ethernet: link, DHCP, rinnovo, perdita cavo, IP statico.
- [ ] USB: fixture VBUS approvata elettricamente, enumerazione macOS, DHCP/DNS/NAT.
- [x] Implementazione API/pannello e hash token NVS; prove dispositivo ancora aperte.
- [x] Implementazione firewall/gate e WireGuard IPv4 subset; prove end-to-end aperte.
- [ ] Test leak, avvio/cambio mode/uplink/server, PMTU, frammentazione e reconnect.
- [ ] Estendere parser standard, endpoint DNS, più profili, storage protetto e rotazione disattivata di default.
- [ ] ESP-Hosted/esp_wifi_remote C6: versioni host/slave, scan, STA, credenziali, AP NAT e isolamento.
- [ ] Selezione/priorità uplink e transizioni atomiche anche Wi-Fi.
- [ ] Regole configurabili, profili casa/ufficio/viaggio, eccezioni LAN esplicite; DNS filtering opzionale.
- [ ] API TLS/pinning, rate limits, migrazioni configurazione e reset autenticato.
- [ ] OTA firmata, verifica immagine, rollback/power interruption e recupero.
- [ ] Soak, RAM/CPU, throughput/latency delle quattro modalità, ottimizzazione.
- Touch: escluso esplicitamente dall'utente; non implementare.
- Post-quantum: ricerca fuori dal percorso operativo, nessun protocollo inventato.
