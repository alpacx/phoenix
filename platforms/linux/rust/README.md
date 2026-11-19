# Phoenix Linux — servizi in Rust

Servizi Linux di Phoenix. Sostituiscono l'implementazione Python originale
(stessa API e stessi file di stato; rimossa dal repository il 18/11/2026, resta
nella storia git). Obiettivo: RAM minima per la scheda RK3562 da 1 GB. ESP32
non cambia.

Un solo binario statico (musl, aarch64) `phoenix`, con la UI `shared/web`
inclusa al momento della build:

| Ruolo | Comando |
|---|---|
| Worker privilegiato (RPC su socket Unix) | `phoenix control --state-dir … --target-config … --worker-socket …` |
| Frontend HTTPS non privilegiato | `phoenix frontend --token-file … --tls-key … --tls-cert … [--usb-socket]` |
| Redirect HTTP→HTTPS USB | `phoenix usb-redirect` |
| Gadget USB Ethernet | `phoenix usb-gadget inspect\|start\|stop` |
| Aggiornamenti firmati | `phoenix update activate\|recover [--restart]`, `phoenix update sign …` |
| Blocco su stop/crash | `phoenix stop-guard` |
| Inventario read-only | `phoenix preflight` |
| Bundle applicativo | `phoenix package build\|verify` |
| Prima installazione | `phoenix install --bundle B --target-config F [--public-key P]` |

Unità systemd in [`../deploy/`](../deploy/README.md) (il blocco d'arresto gira
dalla copia di bootstrap, così una release guasta resta comunque bloccata).

## Build e test (dalla root, solo Docker)

```sh
tools/test-linux.sh                      # = tools/rust-linux.sh test: unit + parità
tools/rust-linux.sh build --release      # target/release/phoenix (~2,9 MB)
tools/linux-bundle.sh OUT.zip            # bundle formato 2
tools/linux-bundle.sh OUT.phx --sign KEY.pem --version V --sequence N
tools/rust-kernel-tests.sh               # test kernel_* + systemd-analyze verify
python3 platforms/linux/tests/integration/rust_blackbox.py [--soak SECONDI] [--keep]
```

- `tests/parity/fixtures.json`: output dell'implementazione Python originale
  su un corpus deterministico (policy, nftables, WireGuard, hostapd/dnsmasq,
  IPv4), congelato il 18/11/2026; `tests/parity.rs` richiede output identico.
  Un cambio voluto di questi formati richiede di aggiornare le fixture a mano.
  Eccezione documentata: l'import WireGuard esteso (19/11) può accettare
  profili che il Python rifiutava solo nelle categorie elencate in
  `wireguard_relaxation` (vedi [API_STATUS.md](../API_STATUS.md)); i profili
  già accettati restano identici e senza note.
- `tools/rust-kernel-tests.sh`: compila i test nel container di build ed
  esegue i test `#[ignore]` `kernel_*` in `phoenix-linux-test:local`
  (NET_ADMIN, SYS_ADMIN solo per `ip netns`, mai rete dell'host): transizioni
  nft/ip/wg/conntrack (`runtime.rs`), dnsmasq + DHCP reale con `busybox
  udhcpc` su veth, anche con 3 DNS (`lan.rs`), `dnsmasq --test` della
  configurazione AP con 1 e 3 DNS (`access_point.rs`), tabella
  `phoenix_stop` (`stop_guard.rs`), keyfile caricato da un NetworkManager
  reale senza radio (`station.rs`), DoH e TLS solo attraverso l'uplink scelto
  verso un namespace peer, compresa la risoluzione di un endpoint WireGuard
  per nome, senza ripiego dopo la caduta del link (`uplink_http.rs`, CA di
  test passata solo nel test). Poi `systemd-analyze verify` delle unità di `../deploy`.
- `rust_blackbox.py`: container usa e getta (NET_ADMIN + SYS_ADMIN solo nel
  proprio namespace, per simulare il modello device-tree e rendere scrivibile
  `ip_forward`), servizi avviati come le unità systemd, solo HTTPS: login con
  cambio password, origin check, blocco iniziale, NAT diretto, policy con
  revisione/conflitto/deny, port forwarding con default deny e filtro
  sorgente, tunnel WireGuard reale con handshake e storico, perdita del tunnel
  e disconnessione senza fallback, profili wg-quick importati (BOM/CRLF,
  maiuscole, IPv6 e PostUp ignorati e mai eseguiti, PresharedKey, MTU,
  codici di rifiuto, AllowedIPs parziali senza uscita fuori tunnel e avviso
  DNS), più `[Peer]` (failover da un membro morto a un'alternativa, uscita e
  sito su un quarto container usati insieme), arresto con forwarding spento. `--soak`
  (30–1200 s) ripete connessione/perdita/disconnessione/diretto e verifica
  RSS (crescita < 2 MiB) e descrittori del worker.
- `tests/vm/`: VM QEMU aarch64 con systemd reale (solo host ARM64, fuori CI):
  installazione, aggiornamenti firmati, rollback, reboot. Comandi in
  [VALIDATION.md](../VALIDATION.md).
- `tests/browser/` + `tests/integration/ui_harness.py`: Playwright (Chromium,
  WebKit, Firefox) contro i servizi Rust in container; comandi nel job
  `browser` di `.github/workflows/software.yml`.

## Formato bundle 2

ZIP solo STORED (lettore proprio: rifiuta nomi duplicati, zip64, compressione,
cifratura, CRC errati, dati in coda): `manifest.json`
(`{"format":2,"signed":false,"files":{nome:sha256}}`), `bin/phoenix`,
`deploy/<unità>`. Release firmata: `release.json` canonico (`format: 2`),
`payload.zip`, `signature.bin` Ed25519 (ring). I bundle/release formato 1
(Python) sono rifiutati.

## Differenze rispetto all'implementazione Python

- HTTP: header ripiegati o nomi con spazi → 400; nessun header `Date`,
  `Connection: close` esplicito; pagine d'errore HTML più brevi.
- `Runtime::handshake()` restituisce `false` se il tool fallisce invece di
  propagare l'eccezione allo stato.
- Il certificato generato dall'installatore è `CA:FALSE` con `serverAuth`
  (il Python generava `CA:TRUE`). Il controllo di salute dell'updater
  confronta il certificato byte per byte (pinning), quindi funziona anche con
  il certificato esistente della ROCK.
- Rimossi `install --replace-python` (usato una volta per migrare la ROCK) e
  il confronto RSS con il Python nel test black-box.
- Campi USB gadget (`udc`, `serial`, `vendor_id`, `product_id`) devono essere
  stringhe in `target.json`.

## Misure (non stime)

Container Docker aarch64 (Apple Silicon, kernel linuxkit), dopo lo stesso
scenario API, `VmRSS` da `/proc/<pid>/status`, 18/11/2026:

| Processo | Python 3.11 | Rust |
|---|---|---|
| worker | 40,8 MB (anon 30,1) | 2,7 MB (anon 0,16) |
| frontend | 24,8 MB (anon 13,8) | 2,1 MB (anon 0,11) |

La parte file-backed del Rust è lo stesso binario, condiviso in page cache fra
i due processi.

ROCK 4C+ (Debian 12, kernel 6.1.115), servizi systemd a riposo dopo la
migrazione del 18/11/2026:

| Processo | Python 3.11 (17/11) | Rust |
|---|---|---|
| `phoenix-control` | 24,3 MB RSS, cgroup 19,1 MB | 2,4 MB RSS (anon 0,11), cgroup 0,28 MB |
| `phoenix` (frontend) | 24,2 MB RSS, cgroup 16,1 MB | 1,6 MB RSS (anon 0,04), cgroup 0,26 MB |
