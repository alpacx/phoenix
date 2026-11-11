# Phoenix Linux

Stato: struttura predisposta; backend Linux non ancora implementato o provato.
Prima piattaforma di banco: ROCK 4C+ acquistata dall'utente. Non confondere
il suo RK3399 con il RK3562 della scheda custom.

## Confini

- UI unica in `shared/web/`; niente copie specifiche per Linux.
- Contratto HTTP di partenza: `docs/API.md`; inventariare anche gli endpoint
  effettivi in `platforms/esp32/main/admin_api.inc` prima di implementare.
- `shared/phoenix_core/` contiene C portabile testato su host. Linux può
  riutilizzarlo dove utile, ma non deve usare il dataplane embedded.
- Backend previsto: WireGuard del kernel, nftables, servizi di rete Linux.
  Nessuna di queste integrazioni è ancora operativa nel progetto.

## Ordine di implementazione

1. Avvio da microSD/eMMC, identificazione scheda, OS/kernel e accesso SSH.
2. Inventario interfacce e capacità; verifica separata USB device sul banco.
3. Backend in `service/`, test in `tests/`, installazione in `deploy/`,
   profili specifici in `boards/rock4c-plus/` (creare quando implementati).
4. Configurazione persistente, autenticazione locale e API per la UI comune.
5. Gateway Wi-Fi/Ethernet, firewall ordinato, NAT e port forwarding.
6. WireGuard/NordVPN, selezione paesi, esclusioni, rotazione e storico.
7. Test del blocco traffico all'avvio/caduta VPN, DNS/IPv6, riavvii,
   prestazioni e temperature.

Non applicare regole firewall o routing al Mac di sviluppo. Le modifiche
alla rete vanno eseguite sul target identificato, con accesso di recupero.
Non esporre l'amministrazione sull'uplink. Non simulare capacità assenti nella UI.
Non copiare token, chiavi o configurazioni private dal banco ESP32 nel repo.
